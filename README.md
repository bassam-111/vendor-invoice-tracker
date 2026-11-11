# Vendor Invoice Tracker

A small Python + Pandas tool for an operations executive who needs to know,
at a glance, what the business owes its vendors — and who to chase first.

It reads a CSV of vendor invoices, works out which ones are overdue and how
badly, summarises the outstanding balance per vendor and per ageing bucket,
and produces two outputs:

- **`aging_report.html`** — a clean, shareable report (KPIs, ageing buckets,
  outstanding by vendor, overdue invoices worst-first)
- **`follow_up_drafts.md`** — a ready-to-send payment-chaser email for every
  vendor with an overdue invoice, with the invoice details filled in

All data in `sample_invoices.csv` is fictional and for demo purposes only.

## How to run

```bash
pip install -r requirements.txt
python invoice_tracker.py --as-of 2026-11-11 sample_invoices.csv
```

Use your own file instead of the sample, and omit `--as-of` to report on
today's date:

```bash
python invoice_tracker.py my_invoices.csv
```

### CSV format

| column | meaning |
|---|---|
| `invoice_id` | invoice reference |
| `vendor` | vendor name |
| `service` | what the invoice is for |
| `amount_pkr` | amount in PKR |
| `invoice_date` | date issued (`YYYY-MM-DD`) |
| `due_date` | date payment is due (`YYYY-MM-DD`) |
| `status` | `paid`, `unpaid` or `overdue` |
| `contact_email` | vendor accounts contact |

Paid invoices are never counted as overdue, even if their due date has passed.

## Sample output

```
Report date: 2026-11-11
Invoices: 15 (billed PKR 777,400, paid PKR 127,000)
Outstanding: PKR 650,400
Overdue: 8 invoices, PKR 450,900

Outstanding by ageing bucket:
  Current (not yet due)      PKR 199,500
  1-30 days overdue          PKR 261,100
  31-60 days overdue         PKR 189,800
  61-90 days overdue         PKR 0
  90+ days overdue           PKR 0
```

Biggest outstanding balance: **DataBridge Analytics — PKR 195,000**
(2 overdue invoices, longest 32 days). The follow-up drafts include one
chaser email per overdue vendor, e.g. for DataBridge:

> Subject: Payment follow-up — 2 overdue invoice(s), PKR 195,000 outstanding

## Tests

```bash
python -m unittest test_invoice_tracker -v
```

6 tests, all passing — ageing-bucket boundaries, totals on the sample data,
overdue count/total, paid invoices never flagged overdue, and top vendor.

## Files

- `invoice_tracker.py` — the tracker (load, age, summarise, report, drafts)
- `sample_invoices.csv` — 15 fictional invoices across 6 vendors
- `test_invoice_tracker.py` — unit tests
- `requirements.txt` — pandas
- `aging_report.html` — generated report (from the sample run)
- `follow_up_drafts.md` — generated chaser emails (from the sample run)

## Skills used

Python, Pandas (data analysis), CSV handling, HTML report generation.
Built as a daily portfolio project — local only, no live vendor data.
