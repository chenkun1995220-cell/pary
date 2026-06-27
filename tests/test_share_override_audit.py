import csv
import tempfile
import unittest
from pathlib import Path

from share_override_audit import audit_share_overrides, run_share_override_audit


class ShareOverrideAuditTests(unittest.TestCase):
    def test_marks_current_stale_and_incomplete_overrides(self):
        rows = [
            {
                "ticker": "FRESH",
                "shares_outstanding": "100",
                "shares_unit": "million_shares",
                "as_of_date": "2026-01-01",
                "source": "SEC 10-Q",
                "source_url": "https://www.sec.gov/example.htm",
                "note": "reviewed",
            },
            {
                "ticker": "STALE",
                "shares_outstanding": "200",
                "shares_unit": "million_shares",
                "as_of_date": "2024-12-31",
                "source": "SEC 10-Q",
                "source_url": "https://www.sec.gov/example.htm",
                "note": "reviewed",
            },
            {
                "ticker": "MISS",
                "shares_outstanding": "",
                "shares_unit": "million_shares",
                "as_of_date": "",
                "source": "",
                "source_url": "",
                "note": "",
            },
        ]

        audited = audit_share_overrides(rows, run_date="2026-06-27", max_age_days=365)
        by_ticker = {row["ticker"]: row for row in audited}

        self.assertEqual(by_ticker["FRESH"]["status"], "current")
        self.assertEqual(by_ticker["FRESH"]["age_days"], "177")
        self.assertEqual(by_ticker["STALE"]["status"], "stale")
        self.assertEqual(by_ticker["STALE"]["age_days"], "543")
        self.assertEqual(by_ticker["MISS"]["status"], "incomplete")
        self.assertIn("shares_outstanding", by_ticker["MISS"]["missing_fields"])

    def test_run_share_override_audit_writes_csv_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            overrides = root / "overrides.csv"
            output_csv = root / "audit.csv"
            output_report = root / "audit.md"
            overrides.write_text(
                "\n".join(
                    [
                        "ticker,shares_outstanding,shares_unit,as_of_date,source,source_url,note",
                        "ERIE,52.30018,million_shares,2026-03-31,SEC 10-Q,https://www.sec.gov/example.htm,reviewed",
                    ]
                )
                + "\n",
                encoding="utf-8-sig",
            )

            result = run_share_override_audit(
                overrides,
                output_csv,
                output_report,
                run_date="2026-06-27",
            )

            self.assertEqual(result["rows"], 1)
            self.assertEqual(result["needs_review"], 0)
            self.assertTrue(output_csv.exists())
            self.assertTrue(output_report.exists())
            with output_csv.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["status"], "current")
            report = output_report.read_text(encoding="utf-8-sig")
            self.assertIn("人工股本覆盖审计", report)
            self.assertIn("需复核：0", report)


if __name__ == "__main__":
    unittest.main()
