import csv
import json
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
    def test_uses_yahoo_fallback_when_eastmoney_retry_still_lacks_price(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            companies = root / "companies.csv"
            snapshot = root / "market_snapshot.csv"
            gaps = root / "quote_gaps.csv"
            output = root / "updated_snapshot.csv"
            report = root / "quote_retry.md"
            result_json = root / "quote_retry_results.json"
            write_csv(
                companies,
                ["market", "ticker", "raw_ticker", "company_name", "industry", "index_name", "currency"],
                [
                    {
                        "market": "HK",
                        "ticker": "02525.HK",
                        "raw_ticker": "02525",
                        "company_name": "HESAI - W",
                        "industry": "Software",
                        "index_name": "HSMI",
                        "currency": "HKD",
                    }
                ],
            )
            write_csv(
                snapshot,
                [
                    "market", "ticker", "company_name", "industry", "index_name", "currency",
                    "price", "market_cap", "pe", "pb", "roe", "quote_date", "source",
                    "data_quality_status",
                ],
                [
                    {
                        "market": "HK",
                        "ticker": "02525.HK",
                        "company_name": "HESAI - W",
                        "industry": "Software",
                        "index_name": "HSMI",
                        "currency": "HKD",
                        "price": "",
                        "market_cap": "161919334214",
                        "pe": "309.99",
                        "pb": "2.0",
                        "roe": "0.002",
                        "quote_date": "2026-07-11",
                        "source": "Eastmoney batch quote",
                        "data_quality_status": "partial",
                    }
                ],
            )
            write_csv(
                gaps,
                ["ticker", "issue_type", "remediation_type"],
                [
                    {
                        "ticker": "02525.HK",
                        "issue_type": "partial_quote",
                        "remediation_type": "refetch_or_supplement_quote",
                    }
                ],
            )
            eastmoney_payload = {
                "rc": 0,
                "data": {
                    "diff": [
                        {
                            "f2": "-",
                            "f9": 309.99,
                            "f12": "02525",
                            "f14": "HESAI - W",
                            "f20": 161919334214,
                            "f23": 2.0,
                            "f37": 0.2,
                            "f100": "Software",
                        }
                    ]
                },
            }
            fallback_tickers = []

            def fetch_fallback(ticker):
                fallback_tickers.append(ticker)
                return {
                    "ticker": ticker,
                    "price": 42.5,
                    "quote_date": "2026-07-10",
                    "quote_source": "Yahoo Finance chart",
                }

            result = run_regional_quote_retry(
                companies_path=companies,
                snapshot_path=snapshot,
                gaps_path=gaps,
                output_path=output,
                report_path=report,
                result_json_path=result_json,
                fetcher=lambda secids: eastmoney_payload,
                fallback_fetcher=fetch_fallback,
            )

            with output.open("r", encoding="utf-8-sig", newline="") as handle:
                row = next(csv.DictReader(handle))
            payload = json.loads(result_json.read_text(encoding="utf-8-sig"))

            self.assertEqual(result["updated"], 1)
            self.assertEqual(fallback_tickers, ["2525.HK"])
            self.assertEqual(row["price"], "42.5")
            self.assertEqual(row["quote_date"], "2026-07-10")
            self.assertEqual(row["data_quality_status"], "ready")
            self.assertIn("Eastmoney batch quote", row["source"])
            self.assertIn("Yahoo Finance chart", row["source"])
            self.assertEqual(payload["results"][0]["status"], "updated")

    def test_retries_refetchable_quote_gaps_and_updates_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            companies = root / "companies.csv"
            snapshot = root / "market_snapshot.csv"
            gaps = root / "quote_gaps.csv"
            output = root / "updated_snapshot.csv"
            report = root / "quote_retry.md"
            result_json = root / "quote_retry_results.json"

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
                result_json_path=result_json,
                fetcher=lambda secids: payload,
                quote_date="2026-06-28",
            )

            with output.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = {row["ticker"]: row for row in csv.DictReader(handle)}
            text = report.read_text(encoding="utf-8-sig")

            self.assertEqual(result["attempted"], 1)
            self.assertEqual(result["updated"], 1)
            self.assertTrue(result_json.exists())
            self.assertEqual(rows["00754.HK"]["price"], "5.6")
            self.assertEqual(rows["00754.HK"]["pe"], "8.5")
            self.assertEqual(rows["00754.HK"]["data_quality_status"], "ready")
            self.assertEqual(rows["00008.HK"]["pe"], "-1")
            self.assertIn("# 区域行情缺口重抓", text)
            self.assertIn("- 尝试重抓：1", text)
            self.assertIn("- 成功更新：1", text)
            self.assertIn("| 00754.HK | updated |", text)
            retry_payload = json.loads(result_json.read_text(encoding="utf-8-sig"))
            self.assertEqual(retry_payload["retry_schema"], "regional_quote_retry")
            self.assertEqual(retry_payload["attempted"], 1)
            self.assertEqual(retry_payload["updated"], 1)
            self.assertEqual(retry_payload["results"][0]["ticker"], "00754.HK")
            self.assertEqual(retry_payload["results"][0]["status"], "updated")


if __name__ == "__main__":
    unittest.main()
