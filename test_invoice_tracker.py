"""Tests for invoice_tracker.py — run with: python -m unittest test_invoice_tracker -v"""
import unittest
from pathlib import Path

import pandas as pd

from invoice_tracker import bucket_for, load_invoices, summarise

HERE = Path(__file__).parent
AS_OF = pd.Timestamp("2026-11-11")


class TestBuckets(unittest.TestCase):
    def test_bucket_boundaries(self):
        self.assertEqual(bucket_for(0), "Current (not yet due)")
        self.assertEqual(bucket_for(-5), "Current (not yet due)")
        self.assertEqual(bucket_for(1), "1-30 days overdue")
        self.assertEqual(bucket_for(30), "1-30 days overdue")
        self.assertEqual(bucket_for(31), "31-60 days overdue")
        self.assertEqual(bucket_for(60), "31-60 days overdue")
        self.assertEqual(bucket_for(61), "61-90 days overdue")
        self.assertEqual(bucket_for(90), "61-90 days overdue")
        self.assertEqual(bucket_for(91), "90+ days overdue")


class TestSampleData(unittest.TestCase):
    def setUp(self):
        self.df = load_invoices(HERE / "sample_invoices.csv", AS_OF)
        self.summary = summarise(self.df)

    def test_counts_and_totals(self):
        self.assertEqual(self.summary["total_invoices"], 15)
        self.assertEqual(self.summary["total_billed"], 777_400)
        self.assertEqual(self.summary["total_paid"], 127_000)
        self.assertEqual(self.summary["total_outstanding"], 650_400)

    def test_overdue(self):
        # As of 2026-11-11: INV-103, 104, 105, 106, 107, 110, 111, 112 are overdue.
        self.assertEqual(self.summary["overdue_count"], 8)
        self.assertEqual(self.summary["overdue_total"], 450_900)

    def test_paid_invoice_never_overdue(self):
        paid = self.df[self.df["status"] == "paid"]
        self.assertTrue((paid["days_overdue"] == 0).all())

    def test_bucket_totals_add_up(self):
        self.assertEqual(
            int(self.summary["bucket_totals"].sum()),
            self.summary["total_outstanding"],
        )

    def test_top_vendor(self):
        top = self.summary["vendor_totals"].iloc[0]
        self.assertEqual(top["vendor"], "DataBridge Analytics")
        self.assertEqual(int(top["total"]), 195_000)


if __name__ == "__main__":
    unittest.main()
