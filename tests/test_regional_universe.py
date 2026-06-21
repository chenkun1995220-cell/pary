import csv
import tempfile
import unittest
from pathlib import Path

from regional_universe import (
    normalize_csi300_records,
    parse_hk_size_payload,
    refresh_market_universe,
    validate_market_rows,
)


HK_PAYLOAD = {
    "requestDate": "2026-06-19 08:36:53",
    "indexSeriesList": [
        {
            "seriesName": "Hang Seng Composite Size Indexes",
            "indexList": [
                {
                    "indexName": "Hang Seng Composite LargeCap Index",
                    "constituentsCount": 2,
                    "constituentContent": [
                        {"code": "5", "constituentName": "HSBC HOLDINGS"},
                        {"code": "700", "constituentName": "TENCENT"},
                    ],
                },
                {
                    "indexName": "Hang Seng Composite MidCap Index",
                    "constituentsCount": 2,
                    "constituentContent": [
                        {"code": "300", "constituentName": "MIDEA GROUP"},
                        {"code": "700", "constituentName": "TENCENT"},
                    ],
                },
            ],
        }
    ],
}


class RegionalUniverseTests(unittest.TestCase):
    def test_normalize_csi300_records_builds_exchange_tickers(self):
        rows = normalize_csi300_records(
            [
                {
                    "成分券代码Constituent Code": "600000",
                    "成分券名称Constituent Name": "浦发银行",
                    "中证一级行业": "金融",
                },
                {
                    "成分券代码Constituent Code": "000001",
                    "成分券名称Constituent Name": "平安银行",
                    "中证一级行业": "金融",
                },
            ]
        )

        self.assertEqual(rows[0]["ticker"], "600000.SH")
        self.assertEqual(rows[0]["exchange"], "SSE")
        self.assertEqual(rows[1]["ticker"], "000001.SZ")
        self.assertEqual(rows[1]["exchange"], "SZSE")
        self.assertEqual(rows[0]["market"], "A股")
        self.assertEqual(rows[0]["index_name"], "沪深300")

    def test_parse_hk_size_payload_combines_large_and_mid_without_duplicates(self):
        rows = parse_hk_size_payload(HK_PAYLOAD)

        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["ticker"], "00005.HK")
        self.assertEqual(rows[0]["index_name"], "HSLI")
        tencent = next(row for row in rows if row["ticker"] == "00700.HK")
        self.assertEqual(tencent["index_name"], "HSLI,HSMI")
        self.assertEqual(tencent["currency"], "HKD")

    def test_validate_market_rows_rejects_duplicate_ticker(self):
        rows = normalize_csi300_records(
            [
                {"成分券代码": "600000", "成分券名称": "浦发银行"},
                {"成分券代码": "600000", "成分券名称": "浦发银行"},
            ]
        )

        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_market_rows(rows, minimum=1, maximum=5)

    def test_refresh_market_writes_cache_and_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "hk.csv"
            cache = root / "cache"

            result = refresh_market_universe(
                "HK",
                output,
                cache,
                fetcher=lambda: HK_PAYLOAD,
                minimum=3,
                maximum=5,
            )

            self.assertEqual(result["status"], "online")
            self.assertEqual(result["rows"], 3)
            self.assertTrue((cache / "constituents.csv").exists())
            self.assertTrue((cache / "source.json").exists())
            self.assertTrue((cache / "refresh_metadata.json").exists())
            with output.open("r", encoding="utf-8-sig", newline="") as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 3)

    def test_refresh_market_falls_back_to_last_good_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "hk.csv"
            cache = root / "cache"
            refresh_market_universe(
                "HK",
                output,
                cache,
                fetcher=lambda: HK_PAYLOAD,
                minimum=3,
                maximum=5,
            )
            output.unlink()

            result = refresh_market_universe(
                "HK",
                output,
                cache,
                fetcher=lambda: (_ for _ in ()).throw(OSError("offline")),
                minimum=3,
                maximum=5,
            )

            self.assertEqual(result["status"], "cache_fallback")
            self.assertIn("offline", result["warning"])
            self.assertTrue(output.exists())

    def test_refresh_market_raises_without_valid_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "no valid cache"):
                refresh_market_universe(
                    "CN",
                    root / "cn.csv",
                    root / "cache",
                    fetcher=lambda: (_ for _ in ()).throw(OSError("offline")),
                    parser=lambda value: [],
                    minimum=1,
                    maximum=5,
                )


if __name__ == "__main__":
    unittest.main()
