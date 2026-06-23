import json
import os
import time
import unittest
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from historical_price_store import (
    build_historical_url,
    load_historical_prices,
    price_coverage,
    prices_available_as_of,
)


def yahoo_payload(
    closes=(10.0,),
    timestamps=(1704067200,),
    adj_closes=None,
    dividends=None,
    splits=None,
):
    if adj_closes is None:
        adj_closes = closes
    if dividends is None:
        dividends = {}
    if splits is None:
        splits = {}
    return {
        "chart": {
            "result": [
                {
                    "timestamp": list(timestamps),
                    "indicators": {
                        "quote": [{"close": list(closes)}],
                        "adjclose": [{"adjclose": list(adj_closes)}],
                    },
                    "events": {
                        "dividends": {
                            str(timestamp): {"amount": amount}
                            for timestamp, amount in dividends.items()
                        },
                        "splits": {
                            str(timestamp): {"numerator": numerator, "denominator": denominator}
                            for timestamp, (numerator, denominator) in splits.items()
                        },
                    },
                }
            ],
            "error": None,
        }
    }


class HistoricalPriceStoreTests(unittest.TestCase):
    def test_prices_available_as_of_excludes_future_and_sorts(self):
        rows = [
            {"date": "2024-01-03", "ticker": "C"},
            {"date": "2024-01-02", "ticker": "B", "seq": 1},
            {"date": "2024-01-04", "ticker": "D"},
            {"date": "2024-01-01", "ticker": "A", "seq": 2},
            {"date": "2024-01-02", "ticker": "E", "seq": 3},
        ]

        result = prices_available_as_of(rows, "2024-01-03")

        self.assertEqual(
            [row["ticker"] for row in result],
            ["A", "B", "E", "C"],
        )

    def test_prices_available_as_of_preserves_financial_fields(self):
        rows = [
            {
                "market": "US",
                "ticker": "AAPL",
                "date": "2024-02-01",
                "close": 100.0,
                "adjusted_close": 99.5,
                "dividend": 0.12,
                "split_ratio": 1.0,
                "source": "Yahoo Chart",
                "data_status": "ready",
            }
        ]

        [result] = prices_available_as_of(rows, date(2024, 2, 1))

        self.assertEqual(result["adjusted_close"], 99.5)
        self.assertEqual(result["dividend"], 0.12)
        self.assertEqual(result["split_ratio"], 1.0)
        self.assertEqual(result["source"], "Yahoo Chart")
        self.assertEqual(result["data_status"], "ready")

    def test_price_coverage_is_case_insensitive_and_deduplicates_tickers(self):
        rows = [
            {"ticker": "AAPL", "data_status": "ready"},
            {"ticker": "msft", "data_status": "ready"},
            {"ticker": "TSLA", "data_status": "unadjusted_fallback"},
        ]

        coverage = price_coverage(["aapl", "AAPL", "msft", "tsla"], rows)

        self.assertEqual(coverage, 2 / 3)

    def test_price_coverage_empty_tickers_returns_one(self):
        self.assertEqual(price_coverage([], [{"ticker": "AAPL", "data_status": "ready"}]), 1.0)

    def test_build_historical_url_brk_b_maps_symbol_and_query(self):
        url = build_historical_url("BRK.B")
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)

        self.assertEqual(parsed.path, "/v8/finance/chart/BRK-B")
        self.assertEqual(query["range"][0], "5y")
        self.assertEqual(query["interval"][0], "1d")
        self.assertEqual(query["events"][0], "history")
        self.assertIn("BRK-B", url)

    def test_load_historical_prices_success_writes_windows_safe_cache(self):
        with TemporaryDirectoryContext() as root:
            result = load_historical_prices(
                "A:B",
                root,
                range_name="5y",
                fetcher=lambda url: yahoo_payload(closes=(12.0,), timestamps=(1704067200,)),
            )

            self.assertEqual(result["source"], "network")
            self.assertEqual(len(result["rows"]), 1)
            self.assertEqual(result["cache_path"].name, "A_B.json")
            self.assertTrue(result["cache_path"].exists())

    def test_load_historical_prices_uses_fresh_cache_within_default_30_days(self):
        with TemporaryDirectoryContext() as root:
            cache_dir = root / "cache"
            cache_dir.mkdir()
            cache_path = (cache_dir / "MSFT.json")
            cache_payload = yahoo_payload(closes=(55.0,), timestamps=(1704067200,))
            cache_path.write_text(json.dumps(cache_payload), encoding="utf-8")
            mtime = time.time() - (29 * 86400)
            os.utime(cache_path, (mtime, mtime))

            result = load_historical_prices(
                "MSFT",
                cache_dir,
                fetcher=lambda url: (_ for _ in ()).throw(ConnectionError("offline")),
            )

            self.assertEqual(result["source"], "cache_fallback")
            self.assertEqual(result["rows"][0]["close"], 55.0)
            self.assertEqual(result["cache_path"].name, "MSFT.json")

    def test_load_historical_prices_rejects_stale_default_30_day_cache(self):
        with TemporaryDirectoryContext() as root:
            cache_dir = root / "cache"
            cache_dir.mkdir()
            cache_path = (cache_dir / "MSFT.json")
            cache_payload = yahoo_payload(closes=(55.0,), timestamps=(1704067200,))
            cache_path.write_text(json.dumps(cache_payload), encoding="utf-8")
            mtime = time.time() - (31 * 86400)
            os.utime(cache_path, (mtime, mtime))

            with self.assertRaises(Exception):
                load_historical_prices(
                    "MSFT",
                    cache_dir,
                    fetcher=lambda url: (_ for _ in ()).throw(ConnectionError("offline")),
                )

    def test_load_historical_prices_rejects_empty_or_unparsable_cache(self):
        with TemporaryDirectoryContext() as root:
            cache_dir = root / "cache"
            cache_dir.mkdir()
            cache_path = cache_dir / "MSFT.json"
            cache_path.write_text(json.dumps({"chart": {"result": []}}), encoding="utf-8")

            with self.assertRaises(Exception):
                load_historical_prices(
                    "MSFT",
                    cache_dir,
                    fetcher=lambda url: (_ for _ in ()).throw(ConnectionError("offline")),
                )

            cache_path.write_text("not json", encoding="utf-8")
            with self.assertRaises(Exception):
                load_historical_prices(
                    "MSFT",
                    cache_dir,
                    fetcher=lambda url: (_ for _ in ()).throw(ConnectionError("offline")),
                )


class TemporaryDirectoryContext:
    def __enter__(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self._path = Path(self._tmp.__enter__())
        return self._path

    def __exit__(self, exc_type, exc, tb):
        return self._tmp.__exit__(exc_type, exc, tb)


if __name__ == "__main__":
    unittest.main()
