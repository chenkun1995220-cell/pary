import csv
import tempfile
import unittest
from pathlib import Path

from regional_quote_gaps import run_regional_quote_gaps


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class RegionalQuoteGapsTests(unittest.TestCase):
    def test_writes_missing_and_partial_quote_gap_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            companies = root / "companies.csv"
            snapshot = root / "market_snapshot.csv"
            output = root / "quote_gaps.csv"
            report = root / "quote_gaps.md"

            write_csv(
                companies,
                ["market", "ticker", "raw_ticker", "company_name", "currency"],
                [
                    {
                        "market": "HK",
                        "ticker": "00700.HK",
                        "raw_ticker": "00700",
                        "company_name": "Tencent",
                        "currency": "HKD",
                    },
                    {
                        "market": "HK",
                        "ticker": "00005.HK",
                        "raw_ticker": "00005",
                        "company_name": "HSBC",
                        "currency": "HKD",
                    },
                    {
                        "market": "HK",
                        "ticker": "09999.HK",
                        "raw_ticker": "09999",
                        "company_name": "Missing Co",
                        "currency": "HKD",
                    },
                ],
            )
            write_csv(
                snapshot,
                [
                    "ticker",
                    "company_name",
                    "price",
                    "market_cap",
                    "pe",
                    "pb",
                    "data_quality_status",
                ],
                [
                    {
                        "ticker": "00700.HK",
                        "company_name": "Tencent",
                        "price": "380",
                        "market_cap": "3600000000000",
                        "pe": "18",
                        "pb": "4",
                        "data_quality_status": "ready",
                    },
                    {
                        "ticker": "00005.HK",
                        "company_name": "HSBC",
                        "price": "68",
                        "market_cap": "1200000000000",
                        "pe": "",
                        "pb": "0",
                        "data_quality_status": "partial",
                    },
                ],
            )

            result = run_regional_quote_gaps(
                companies_path=companies,
                snapshot_path=snapshot,
                output_path=output,
                report_path=report,
                market="HK",
                cache_dir=root / "cache",
            )

            with output.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            text = report.read_text(encoding="utf-8-sig")

            self.assertEqual(result["issue_count"], 2)
            self.assertEqual(rows[0]["ticker"], "00005.HK")
            self.assertEqual(rows[0]["issue_type"], "partial_quote")
            self.assertEqual(rows[0]["missing_fields"], "pe;pb")
            self.assertIn("重新运行 regional_market_snapshot.py", rows[0]["recommended_action"])
            self.assertEqual(rows[1]["ticker"], "09999.HK")
            self.assertEqual(rows[1]["issue_type"], "missing_quote")
            self.assertIn("Eastmoney batch quote 未返回该 ticker", rows[1]["reason"])
            self.assertIn("# 区域行情缺口诊断", text)
            self.assertIn("- 市场：HK", text)
            self.assertIn("- 缺口数量：2", text)
            self.assertIn("| 00005.HK | HSBC | partial_quote | pe;pb |", text)
            self.assertIn("| 09999.HK | Missing Co | missing_quote | all_quote_fields |", text)

    def test_classifies_non_positive_valuation_metrics_as_review_not_refetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            companies = root / "companies.csv"
            snapshot = root / "market_snapshot.csv"
            output = root / "quote_gaps.csv"
            report = root / "quote_gaps.md"

            write_csv(
                companies,
                ["market", "ticker", "company_name", "currency"],
                [
                    {
                        "market": "CN",
                        "ticker": "000002.SZ",
                        "company_name": "Vanke",
                        "currency": "CNY",
                    }
                ],
            )
            write_csv(
                snapshot,
                [
                    "ticker",
                    "company_name",
                    "price",
                    "market_cap",
                    "pe",
                    "pb",
                    "data_quality_status",
                ],
                [
                    {
                        "ticker": "000002.SZ",
                        "company_name": "Vanke",
                        "price": "3.01",
                        "market_cap": "35911435508",
                        "pe": "-1.51",
                        "pb": "0",
                        "data_quality_status": "partial",
                    }
                ],
            )

            run_regional_quote_gaps(
                companies_path=companies,
                snapshot_path=snapshot,
                output_path=output,
                report_path=report,
                market="CN",
                cache_dir=root / "cache",
            )

            with output.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            text = report.read_text(encoding="utf-8-sig")

            self.assertEqual(rows[0]["issue_type"], "non_positive_metric")
            self.assertEqual(rows[0]["missing_fields"], "pe;pb")
            self.assertEqual(rows[0]["remediation_type"], "manual_financial_review")
            self.assertEqual(rows[0]["review_category"], "loss_making_or_negative_pe;non_positive_book_value_or_pb")
            self.assertIn("pe=-1.51", rows[0]["review_detail"])
            self.assertIn("pb=0", rows[0]["review_detail"])
            self.assertIn("PE/PB 非正", rows[0]["reason"])
            self.assertNotIn("重新运行 regional_market_snapshot.py", rows[0]["recommended_action"])
            self.assertIn("- 非正估值指标：1", text)


    def test_flags_special_industry_non_positive_metrics_for_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            companies = root / "companies.csv"
            snapshot = root / "market_snapshot.csv"
            output = root / "quote_gaps.csv"
            report = root / "quote_gaps.md"

            write_csv(
                companies,
                ["market", "ticker", "company_name", "currency"],
                [
                    {
                        "market": "HK",
                        "ticker": "00823.HK",
                        "company_name": "Link REIT",
                        "currency": "HKD",
                    }
                ],
            )
            write_csv(
                snapshot,
                [
                    "ticker",
                    "company_name",
                    "industry",
                    "price",
                    "market_cap",
                    "pe",
                    "pb",
                    "data_quality_status",
                ],
                [
                    {
                        "ticker": "00823.HK",
                        "company_name": "Link REIT",
                        "industry": "REITs",
                        "price": "36.4",
                        "market_cap": "95500000000",
                        "pe": "-12.1",
                        "pb": "0",
                        "data_quality_status": "partial",
                    }
                ],
            )

            run_regional_quote_gaps(
                companies_path=companies,
                snapshot_path=snapshot,
                output_path=output,
                report_path=report,
                market="HK",
                cache_dir=root / "cache",
            )

            with output.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            text = report.read_text(encoding="utf-8-sig")

            self.assertIn("special_industry_valuation_review", rows[0]["review_category"])
            self.assertIn("industry=REITs", rows[0]["review_detail"])
            self.assertIn("special_industry_valuation_review", text)

    def test_classifies_special_industry_missing_valuation_metrics_as_review_not_refetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            companies = root / "companies.csv"
            snapshot = root / "market_snapshot.csv"
            output = root / "quote_gaps.csv"
            report = root / "quote_gaps.md"

            write_csv(
                companies,
                ["market", "ticker", "company_name", "currency"],
                [
                    {
                        "market": "HK",
                        "ticker": "00823.HK",
                        "company_name": "Link REIT",
                        "currency": "HKD",
                    }
                ],
            )
            write_csv(
                snapshot,
                [
                    "ticker",
                    "company_name",
                    "industry",
                    "price",
                    "market_cap",
                    "pe",
                    "pb",
                    "data_quality_status",
                ],
                [
                    {
                        "ticker": "00823.HK",
                        "company_name": "Link REIT",
                        "industry": "REITs",
                        "price": "36.4",
                        "market_cap": "95500000000",
                        "pe": "",
                        "pb": "",
                        "data_quality_status": "partial",
                    }
                ],
            )

            run_regional_quote_gaps(
                companies_path=companies,
                snapshot_path=snapshot,
                output_path=output,
                report_path=report,
                market="HK",
                cache_dir=root / "cache",
            )

            with output.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(rows[0]["issue_type"], "valuation_metric_unavailable")
            self.assertEqual(rows[0]["missing_fields"], "pe;pb")
            self.assertEqual(rows[0]["remediation_type"], "manual_financial_review")
            self.assertIn("special_industry_valuation_review", rows[0]["review_category"])
            self.assertIn("industry=REITs", rows[0]["review_detail"])
            self.assertNotIn("regional_market_snapshot.py", rows[0]["recommended_action"])


if __name__ == "__main__":
    unittest.main()
