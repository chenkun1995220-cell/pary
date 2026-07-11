import csv
import json
import tempfile
import unittest
from pathlib import Path

from regional_financials import (
    build_financial_url,
    normalize_financial_records,
    run_regional_financials,
)


A_RECORDS = [
    {
        "SECUCODE": "600519.SH",
        "REPORT_DATE": "2026-03-31 00:00:00",
        "REPORT_TYPE": "一季报",
        "TOTALOPERATEREVE": 54702912385.23,
        "PARENTNETPROFIT": 27242512886.45,
        "NETCASH_OPERATE_PK": 26909891269.13,
        "ROEJQ": 10.57,
        "ROIC": 9.83,
        "XSMLL": 89.76,
        "LD": 7.06,
        "ZCFZL": 12.12,
        "TOTALOPERATEREVETZ": 6.34,
        "PARENTNETPROFITTZ": 1.47,
    },
    {
        "SECUCODE": "600519.SH",
        "REPORT_DATE": "2025-12-31 00:00:00",
        "REPORT_TYPE": "年报",
        "TOTALOPERATEREVE": 180000000000,
    },
]

HK_RECORDS = [
    {
        "SECUCODE": "00700.HK",
        "REPORT_DATE": "2026-03-31 00:00:00",
        "REPORT_TYPE": "2026年一季报",
        "OPERATE_INCOME": 196458000000,
        "HOLDER_PROFIT": 58093000000,
        "NETCASH_OPERATE": 101351000000,
        "ROE_YEARLY": 20.37,
        "ROIC_YEARLY": 14.90,
        "GROSS_PROFIT_RATIO": 56.64,
        "CURRENT_RATIO": 1.43,
        "DEBT_ASSET_RATIO": 40.94,
        "OPERATE_INCOME_YOY": 9.13,
        "HOLDER_PROFIT_YOY": 21.48,
    }
]


class RegionalFinancialTests(unittest.TestCase):
    def test_build_url_uses_market_specific_report_and_batch_filter(self):
        cn_url = build_financial_url("CN", ["600519.SH", "000001.SZ"])
        hk_url = build_financial_url("HK", ["00700.HK"])

        self.assertIn("RPT_F10_FINANCE_MAINFINADATA", cn_url)
        self.assertIn("600519.SH", cn_url)
        self.assertIn("000001.SZ", cn_url)
        self.assertIn("RPT_HKF10_FN_MAININDICATOR", hk_url)

    def test_normalizes_cn_latest_report_and_percent_units(self):
        rows = normalize_financial_records("CN", A_RECORDS)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ticker"], "600519.SH")
        self.assertEqual(rows[0]["revenue"], 54702912385.23)
        self.assertAlmostEqual(rows[0]["roe"], 0.1057)
        self.assertAlmostEqual(rows[0]["roic"], 0.0983)
        self.assertAlmostEqual(rows[0]["gross_margin"], 0.8976)
        self.assertAlmostEqual(rows[0]["debt_to_assets"], 0.1212)
        self.assertAlmostEqual(rows[0]["revenue_growth"], 0.0634)
        self.assertEqual(rows[0]["financial_period_basis"], "一季报")

    def test_normalizes_hk_financial_fields(self):
        rows = normalize_financial_records("HK", HK_RECORDS)

        self.assertEqual(rows[0]["ticker"], "00700.HK")
        self.assertEqual(rows[0]["operating_cash_flow"], 101351000000)
        self.assertAlmostEqual(rows[0]["roe"], 0.2037)
        self.assertAlmostEqual(rows[0]["current_ratio"], 1.43)
        self.assertAlmostEqual(rows[0]["net_income_growth"], 0.2148)

    def test_run_financials_merges_snapshot_and_reports_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = root / "snapshot.csv"
            output = root / "financial.csv"
            raw_cache = root / "raw.json"
            snapshot_rows = [
                {"market": "A股", "ticker": "600519.SH", "company_name": "贵州茅台", "industry": "白酒", "pe": "14"},
                {"market": "A股", "ticker": "000001.SZ", "company_name": "平安银行", "industry": "银行", "pe": "4"},
            ]
            with snapshot.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=snapshot_rows[0].keys())
                writer.writeheader()
                writer.writerows(snapshot_rows)

            result = run_regional_financials(
                "CN",
                snapshot,
                output,
                raw_cache,
                fetcher=lambda market, tickers: {"success": True, "result": {"data": A_RECORDS}},
                batch_size=20,
                minimum_coverage=0,
            )

            self.assertEqual(result["rows"], 2)
            self.assertEqual(result["financial_rows"], 1)
            self.assertAlmostEqual(result["coverage"], 0.5)
            with output.open("r", encoding="utf-8-sig", newline="") as stream:
                merged = list(csv.DictReader(stream))
            self.assertEqual(merged[0]["financial_data_status"], "ready")
            self.assertEqual(merged[1]["financial_data_status"], "missing")
            self.assertEqual(json.loads(raw_cache.read_text(encoding="utf-8"))[0]["success"], True)

    def test_run_financials_retries_transient_batch_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = root / "snapshot.csv"
            output = root / "financial.csv"
            raw_cache = root / "raw.json"
            snapshot_rows = [
                {"market": "A\u80a1", "ticker": "600519.SH", "company_name": "Moutai", "industry": "Beverage", "pe": "14"}
            ]
            with snapshot.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=snapshot_rows[0].keys())
                writer.writeheader()
                writer.writerows(snapshot_rows)

            attempts = []
            delays = []

            def flaky_fetcher(market, tickers):
                attempts.append((market, list(tickers)))
                if len(attempts) < 3:
                    raise TimeoutError("temporary timeout")
                return {"success": True, "result": {"data": A_RECORDS}}

            result = run_regional_financials(
                "CN",
                snapshot,
                output,
                raw_cache,
                fetcher=flaky_fetcher,
                batch_size=20,
                minimum_coverage=0,
                max_attempts=3,
                retry_delay_seconds=2,
                sleeper=delays.append,
            )

            self.assertEqual(result["financial_rows"], 1)
            self.assertEqual(result["retry_count"], 2)
            self.assertEqual(len(attempts), 3)
            self.assertEqual(delays, [2, 4])


if __name__ == "__main__":
    unittest.main()
