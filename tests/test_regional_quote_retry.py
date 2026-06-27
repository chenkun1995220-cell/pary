import csv
import tempfile
import unittest
from pathlib import Path

from regional_quote_retry import run_regional_quote_retry


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class RegionalQuoteRetryTests(unittest.TestCase):
    def test_retries_refetchable_quote_gaps_and_updates_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            companies = root / "companies.csv"
            snapshot = root / "market_snapshot.csv"
            gaps = root / "quote_gaps.csv"
            output = root / "updated_snapshot.csv"
            report = root / "quote_retry.md"

            write_csv(
                companies,
                ["market", "ticker", "raw_ticker", "company_name", "industry", "index_name", "currency"],
                [
                    {
                        "market": "港股",
                        "ticker": "00754.HK",
                        "raw_ticker": "00754",
                        "company_name": "HOPSON DEV HOLD",
                        "industry": "地产",
                        "index_name": "HSMI",
                        "currency": "HKD",
                    },
                    {
                        "market": "港股",
                        "ticker": "00008.HK",
                        "raw_ticker": "00008",
                        "company_name": "PCCW",
                        "industry": "通信",
                        "index_name": "HSLI",
                        "currency": "HKD",
                    },
                ],
            )
            write_csv(
                snapshot,
                [
                    "market",
                    "ticker",
                    "company_name",
                    "industry",
                    "index_name",
                    "currency",
                    "price",
                    "market_cap",
                    "pe",
                    "pb",
                    "roe",
                    "quote_date",
                    "source",
                    "data_quality_status",
                ],
                [
                    {
                        "market": "港股",
                        "ticker": "00754.HK",
                        "company_name": "HOPSON DEV HOLD",
                        "industry": "地产",
                        "index_name": "HSMI",
                        "currency": "HKD",
                        "price": "",
                        "market_cap": "1000000000",
                        "pe": "",
                        "pb": "0.4",
                        "roe": "0.05",
                        "quote_date": "2026-06-27",
                        "source": "Eastmoney batch quote",
                        "data_quality_status": "partial",
                    },
                    {
                        "market": "港股",
                        "ticker": "00008.HK",
                        "company_name": "PCCW",
                        "industry": "通信",
                        "index_name": "HSLI",
                        "currency": "HKD",
                        "price": "4.2",
                        "market_cap": "30000000000",
                        "pe": "-1",
                        "pb": "0",
                        "roe": "0.02",
                        "quote_date": "2026-06-27",
                        "source": "Eastmoney batch quote",
                        "data_quality_status": "partial",
                    },
                ],
            )
            write_csv(
                gaps,
                ["ticker", "issue_type", "remediation_type"],
                [
                    {
                        "ticker": "00754.HK",
                        "issue_type": "partial_quote",
                        "remediation_type": "refetch_or_supplement_quote",
                    },
                    {
                        "ticker": "00008.HK",
                        "issue_type": "non_positive_metric",
                        "remediation_type": "manual_financial_review",
                    },
                ],
            )

            payload = {
                "rc": 0,
                "data": {
                    "diff": [
                        {
                            "f2": 5.6,
                            "f9": 8.5,
                            "f12": "00754",
                            "f14": "HOPSON DEV HOLD",
                            "f20": 1230000000,
                            "f23": 0.6,
                            "f37": 6.1,
                            "f100": "地产",
                        }
                    ]
                },
            }

            result = run_regional_quote_retry(
                companies_path=companies,
                snapshot_path=snapshot,
                gaps_path=gaps,
                output_path=output,
                report_path=report,
                fetcher=lambda secids: payload,
                quote_date="2026-06-28",
            )

            with output.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = {row["ticker"]: row for row in csv.DictReader(handle)}
            text = report.read_text(encoding="utf-8-sig")

            self.assertEqual(result["attempted"], 1)
            self.assertEqual(result["updated"], 1)
            self.assertEqual(rows["00754.HK"]["price"], "5.6")
            self.assertEqual(rows["00754.HK"]["pe"], "8.5")
            self.assertEqual(rows["00754.HK"]["data_quality_status"], "ready")
            self.assertEqual(rows["00008.HK"]["pe"], "-1")
            self.assertIn("# 区域行情缺口重抓", text)
            self.assertIn("- 尝试重抓：1", text)
            self.assertIn("- 成功更新：1", text)
            self.assertIn("| 00754.HK | updated |", text)


if __name__ == "__main__":
    unittest.main()
