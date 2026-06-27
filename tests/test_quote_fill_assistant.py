import csv
import tempfile
import unittest
from pathlib import Path

from quote_fill_assistant import (
    find_quote_fill_gaps,
    run_quote_fill_check,
    write_gap_report,
)


QUOTE_HEADER = (
    "ticker,price,shares_outstanding,net_debt,currency,quote_date,"
    "price_unit,shares_unit,debt_unit,quote_source,updated_at"
)


class QuoteFillAssistantTests(unittest.TestCase):
    def test_finds_missing_fields_in_real_sample_quotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            quote_path = Path(tmp) / "quotes.csv"
            quote_path.write_text(
                "\n".join(
                    [
                        QUOTE_HEADER,
                        "AAPL,,,,USD,,USD/share,million_shares,USD_million,,",
                        "MSFT,,,,USD,,USD/share,million_shares,USD_million,,",
                        "GOOGL,,,,USD,,USD/share,million_shares,USD_million,,",
                    ]
                )
                + "\n",
                encoding="utf-8-sig",
            )

            gaps = find_quote_fill_gaps(quote_path)

        by_ticker = {gap["ticker"]: gap for gap in gaps}

        self.assertEqual(len(gaps), 3)
        self.assertIn("price", by_ticker["AAPL"]["missing_fields"])
        self.assertIn("shares_outstanding", by_ticker["AAPL"]["missing_fields"])
        self.assertNotIn("net_debt", by_ticker["AAPL"]["missing_fields"])
        self.assertIn("quote_source", by_ticker["AAPL"]["missing_fields"])
        self.assertEqual(by_ticker["AAPL"]["status"], "needs_fill")

    def test_treats_complete_quote_row_as_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            quote_path = Path(tmp) / "quotes.csv"
            with quote_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "ticker",
                        "price",
                        "shares_outstanding",
                        "net_debt",
                        "currency",
                        "quote_date",
                        "price_unit",
                        "shares_unit",
                        "debt_unit",
                        "quote_source",
                        "updated_at",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "ticker": "AAPL",
                        "price": "200",
                        "shares_outstanding": "15000",
                        "net_debt": "-50000",
                        "currency": "USD",
                        "quote_date": "2026-06-18",
                        "price_unit": "USD/share",
                        "shares_unit": "million_shares",
                        "debt_unit": "USD_million",
                        "quote_source": "manual",
                        "updated_at": "2026-06-18",
                    }
                )

            gaps = find_quote_fill_gaps(quote_path)

            self.assertEqual(gaps[0]["status"], "ready")
            self.assertEqual(gaps[0]["missing_fields"], "")

    def test_missing_net_debt_does_not_block_quote_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quotes.csv"
            path.write_text(
                QUOTE_HEADER + "\n"
                "TEST,100,10,,USD,2026-06-21,USD/share,million_shares,USD_million,Yahoo,2026-06-21\n",
                encoding="utf-8-sig",
            )

            gap = find_quote_fill_gaps(path)[0]

            self.assertEqual(gap["status"], "ready")
            self.assertNotIn("net_debt", gap["missing_fields"])

    def test_marks_manual_override_rows_as_applied(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quotes.csv"
            path.write_text(
                QUOTE_HEADER + "\n"
                "ERIE,237.11,52.3,,USD,2026-06-26,USD/share,million_shares,USD_million,"
                "Yahoo Finance chart; Manual share override (manual review),2026-06-27\n",
                encoding="utf-8-sig",
            )

            gap = find_quote_fill_gaps(path)[0]

            self.assertEqual(gap["status"], "manual_override_applied")
            self.assertEqual(gap["missing_fields"], "")

    def test_marks_sanity_failed_missing_shares_for_manual_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quotes.csv"
            path.write_text(
                QUOTE_HEADER + "\n"
                "ERIE,237.11,,,USD,2026-06-26,USD/share,million_shares,USD_million,"
                "Yahoo Finance chart; SEC Company Facts share sanity failed,2026-06-27\n",
                encoding="utf-8-sig",
            )

            gap = find_quote_fill_gaps(path)[0]

            self.assertEqual(gap["status"], "needs_manual_review")
            self.assertEqual(gap["missing_fields"], "shares_outstanding")

    def test_writes_csv_and_markdown_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            quote_path = root / "quotes.csv"
            output_csv = root / "quote_gaps.csv"
            output_md = root / "quote_gaps.md"
            quote_path.write_text(
                "\n".join(
                    [
                        QUOTE_HEADER,
                        "AAPL,,,,USD,,USD/share,million_shares,USD_million,,",
                        "MSFT,,,,USD,,USD/share,million_shares,USD_million,,",
                        "GOOGL,,,,USD,,USD/share,million_shares,USD_million,,",
                    ]
                )
                + "\n",
                encoding="utf-8-sig",
            )

            result = run_quote_fill_check(
                quote_path,
                output_csv,
                output_md,
            )

            self.assertEqual(result["rows"], 3)
            self.assertTrue(output_csv.exists())
            self.assertTrue(output_md.exists())
            report = output_md.read_text(encoding="utf-8-sig")
            self.assertIn("真实行情待补清单", report)
            self.assertIn("AAPL", report)
            self.assertIn("price", report)

    def test_markdown_report_handles_no_missing_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.md"

            write_gap_report(report_path, [{"ticker": "AAPL", "status": "ready", "missing_fields": ""}])

            report = report_path.read_text(encoding="utf-8-sig")
            self.assertIn("暂无待补字段", report)


if __name__ == "__main__":
    unittest.main()
