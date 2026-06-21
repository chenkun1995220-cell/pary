import csv
import json
import tempfile
import unittest
from pathlib import Path

from regional_market_snapshot import (
    parse_eastmoney_snapshot,
    run_market_snapshot,
    ticker_to_secid,
)


PAYLOAD = {
    "rc": 0,
    "data": {
        "total": 2,
        "diff": [
            {
                "f2": 1215.0,
                "f9": 13.94,
                "f12": "600519",
                "f14": "贵州茅台",
                "f20": 1518849145215,
                "f23": 5.61,
                "f37": 10.57,
                "f100": "白酒Ⅱ",
            },
            {
                "f2": 10.52,
                "f9": 3.51,
                "f12": "000001",
                "f14": "平安银行",
                "f20": 204150259443,
                "f23": 0.45,
                "f37": 2.83,
                "f100": "银行Ⅱ",
            },
        ],
    },
}


COMPANIES = [
    {
        "market": "A股",
        "ticker": "600519.SH",
        "raw_ticker": "600519",
        "company_name": "贵州茅台",
        "industry": "主要消费",
        "currency": "CNY",
    },
    {
        "market": "A股",
        "ticker": "000001.SZ",
        "raw_ticker": "000001",
        "company_name": "平安银行",
        "industry": "金融",
        "currency": "CNY",
    },
    {
        "market": "A股",
        "ticker": "300750.SZ",
        "raw_ticker": "300750",
        "company_name": "宁德时代",
        "industry": "工业",
        "currency": "CNY",
    },
]


class RegionalMarketSnapshotTests(unittest.TestCase):
    def test_ticker_to_secid_handles_cn_and_hk_markets(self):
        self.assertEqual(ticker_to_secid("600519.SH"), "1.600519")
        self.assertEqual(ticker_to_secid("000001.SZ"), "0.000001")
        self.assertEqual(ticker_to_secid("00700.HK"), "116.00700")

    def test_parse_snapshot_preserves_standard_fields_and_units(self):
        rows, missing = parse_eastmoney_snapshot(
            PAYLOAD, COMPANIES, quote_date="2026-06-19"
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(missing, ["300750.SZ"])
        self.assertEqual(rows[0]["ticker"], "600519.SH")
        self.assertEqual(rows[0]["price"], 1215.0)
        self.assertEqual(rows[0]["market_cap"], 1518849145215)
        self.assertEqual(rows[0]["pe"], 13.94)
        self.assertEqual(rows[0]["pb"], 5.61)
        self.assertAlmostEqual(rows[0]["roe"], 0.1057)
        self.assertEqual(rows[0]["industry"], "主要消费")
        self.assertEqual(rows[0]["source"], "Eastmoney batch quote")

    def test_run_snapshot_writes_csv_raw_cache_and_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            companies_path = root / "companies.csv"
            output_path = root / "snapshot.csv"
            raw_cache = root / "raw.json"
            with companies_path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=COMPANIES[0].keys())
                writer.writeheader()
                writer.writerows(COMPANIES)

            result = run_market_snapshot(
                companies_path,
                output_path,
                raw_cache,
                fetcher=lambda secids: PAYLOAD,
                batch_size=100,
                quote_date="2026-06-19",
            )

            self.assertEqual(result["rows"], 2)
            self.assertEqual(result["missing"], ["300750.SZ"])
            self.assertAlmostEqual(result["coverage"], 2 / 3)
            self.assertTrue(output_path.exists())
            self.assertEqual(json.loads(raw_cache.read_text(encoding="utf-8"))[0]["rc"], 0)


if __name__ == "__main__":
    unittest.main()
