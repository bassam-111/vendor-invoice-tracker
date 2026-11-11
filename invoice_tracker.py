#!/usr/bin/env python3
"""Vendor Invoice Tracker.

Reads a CSV of vendor invoices, works out which ones are overdue and how
badly, summarises what is owed per vendor and per ageing bucket, and writes:
  - aging_report.html  (a small styled HTML report)
  - follow_up_drafts.md (a ready-to-send payment-chaser email per overdue vendor)

Usage:
    python invoice_tracker.py                 # uses sample_invoices.csv
    python invoice_tracker.py my_invoices.csv # uses your own file
    python invoice_tracker.py --as-of 2026-11-30 sample_invoices.csv
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

BUCKETS = [
    ("Current (not yet due)", lambda d: d <= 0),
    ("1-30 days overdue", lambda d: 1 <= d <= 30),
    ("31-60 days overdue", lambda d: 31 <= d <= 60),
    ("61-90 days overdue", lambda d: 61 <= d <= 90),
    ("90+ days overdue", lambda d: d > 90),
]


def bucket_for(days_overdue: int) -> str:
    for label, rule in BUCKETS:
        if rule(days_overdue):
            return label
    return "Unknown"


def load_invoices(path: Path, as_of: pd.Timestamp) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["invoice_date", "due_date"])
    df["amount_pkr"] = pd.to_numeric(df["amount_pkr"], errors="coerce").fillna(0).astype(int)
    df["days_overdue"] = (as_of - df["due_date"]).dt.days
    # A "paid" invoice is never overdue, whatever its due date says.
    df.loc[df["status"].str.lower() == "paid", "days_overdue"] = 0
    df["bucket"] = df["days_overdue"].apply(bucket_for)
    df["is_outstanding"] = df["status"].str.lower() != "paid"
    return df


def summarise(df: pd.DataFrame) -> dict:
    outstanding = df[df["is_outstanding"]]
    overdue = outstanding[outstanding["days_overdue"] > 0]
    bucket_totals = (
        outstanding.groupby("bucket")["amount_pkr"]
        .sum()
        .reindex([label for label, _ in BUCKETS], fill_value=0)
    )
    vendor_totals = (
        outstanding.groupby(["vendor", "contact_email"])["amount_pkr"]
        .agg(total="sum", n_invoices="count")
        .sort_values("total", ascending=False)
        .reset_index()
    )
    return {
        "total_invoices": len(df),
        "total_billed": int(df["amount_pkr"].sum()),
        "total_paid": int(df[~df["is_outstanding"]]["amount_pkr"].sum()),
        "total_outstanding": int(outstanding["amount_pkr"].sum()),
        "overdue_count": len(overdue),
        "overdue_total": int(overdue["amount_pkr"].sum()),
        "bucket_totals": bucket_totals,
        "vendor_totals": vendor_totals,
        "overdue": overdue.sort_values("days_overdue", ascending=False),
        "outstanding": outstanding.sort_values("due_date"),
    }


def write_html_report(summary: dict, as_of: pd.Timestamp, out_path: Path) -> None:
    rows = "\n".join(
        f"<tr><td>{label}</td><td>PKR {int(amount):,}</td></tr>"
        for label, amount in summary["bucket_totals"].items()
    )
    vendor_rows = "\n".join(
        f"<tr><td>{r.vendor}</td><td>{int(r.n_invoices)}</td>"
        f"<td>PKR {int(r.total):,}</td></tr>"
        for r in summary["vendor_totals"].itertuples()
    )
    overdue_rows = "\n".join(
        f"<tr><td>{r.invoice_id}</td><td>{r.vendor}</td><td>{r.service}</td>"
        f"<td>PKR {int(r.amount_pkr):,}</td><td>{r.due_date.date()}</td>"
        f"<td>{int(r.days_overdue)} days</td></tr>"
        for r in summary["overdue"].itertuples()
    ) or "<tr><td colspan='6'>Nothing overdue. Nice work.</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Vendor Invoice Aging Report — {as_of.date()}</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 820px; margin: 2rem auto; color: #222; }}
h1 {{ font-size: 1.5rem; }} h2 {{ font-size: 1.15rem; margin-top: 1.8rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; }}
th {{ background: #f0f0f0; }}
.kpi {{ display: flex; gap: 1rem; }} .kpi div {{ background: #f7f7f7; padding: 0.8rem 1rem; border-radius: 6px; }}
.kpi b {{ font-size: 1.2rem; display: block; }}
</style></head><body>
<h1>Vendor Invoice Aging Report</h1>
<p>As of {as_of.date()} &middot; {summary["total_invoices"]} invoices, PKR {summary["total_billed"]:,} billed in total.</p>
<div class="kpi">
<div>Outstanding<b>PKR {summary["total_outstanding"]:,}</b></div>
<div>Overdue ({summary["overdue_count"]} invoices)<b>PKR {summary["overdue_total"]:,}</b></div>
<div>Paid<b>PKR {summary["total_paid"]:,}</b></div>
</div>
<h2>Outstanding by ageing bucket</h2>
<table><tr><th>Bucket</th><th>Amount</th></tr>{rows}</table>
<h2>Outstanding by vendor</h2>
<table><tr><th>Vendor</th><th>Invoices</th><th>Amount</th></tr>{vendor_rows}</table>
<h2>Overdue invoices (worst first)</h2>
<table><tr><th>Invoice</th><th>Vendor</th><th>Service</th><th>Amount</th><th>Due</th><th>Overdue by</th></tr>{overdue_rows}</table>
</body></html>"""
    out_path.write_text(html, encoding="utf-8")


def write_follow_up_drafts(summary: dict, as_of: pd.Timestamp, out_path: Path) -> None:
    overdue = summary["overdue"]
    lines = [f"# Payment follow-up drafts — as of {as_of.date()}\n"]
    if overdue.empty:
        lines.append("No overdue invoices — no follow-ups needed.\n")
    else:
        for (vendor, email), group in overdue.groupby(["vendor", "contact_email"]):
            total = int(group["amount_pkr"].sum())
            worst = int(group["days_overdue"].max())
            items = "\n".join(
                f"- {r.invoice_id} — {r.service} — PKR {int(r.amount_pkr):,} "
                f"(due {r.due_date.date()}, {int(r.days_overdue)} days overdue)"
                for r in group.itertuples()
            )
            lines.append(
                f"## To: {vendor} <{email}>\n"
                f"**Subject:** Payment follow-up — {len(group)} overdue invoice(s), "
                f"PKR {total:,} outstanding\n\n"
                f"Hi team,\n\n"
                f"Hope you're well. I'm following up on the invoice(s) below, "
                f"which are now overdue (longest outstanding: {worst} days). "
                f"Could you please confirm the payment date?\n\n{items}\n\n"
                f"Total outstanding: PKR {total:,}\n\n"
                f"Thanks,\nBassam Zafar — Operations Executive\n\n---\n"
            )
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Vendor invoice ageing tracker")
    parser.add_argument("csv", nargs="?", default="sample_invoices.csv",
                        help="invoice CSV file (default: sample_invoices.csv)")
    parser.add_argument("--as-of", default=None,
                        help="report date YYYY-MM-DD (default: today)")
    args = parser.parse_args(argv)

    path = Path(args.csv)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 1

    as_of = pd.Timestamp(args.as_of) if args.as_of else pd.Timestamp.today().normalize()
    df = load_invoices(path, as_of)
    summary = summarise(df)

    out_dir = path.parent
    write_html_report(summary, as_of, out_dir / "aging_report.html")
    write_follow_up_drafts(summary, as_of, out_dir / "follow_up_drafts.md")

    print(f"Report date: {as_of.date()}")
    print(f"Invoices: {summary['total_invoices']} "
          f"(billed PKR {summary['total_billed']:,}, "
          f"paid PKR {summary['total_paid']:,})")
    print(f"Outstanding: PKR {summary['total_outstanding']:,}")
    print(f"Overdue: {summary['overdue_count']} invoices, "
          f"PKR {summary['overdue_total']:,}")
    print("\nOutstanding by ageing bucket:")
    for label, amount in summary["bucket_totals"].items():
        print(f"  {label:<26} PKR {int(amount):,}")
    print("\nWrote aging_report.html and follow_up_drafts.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
