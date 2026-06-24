import csv
import tempfile
import unittest
from pathlib import Path

from backtest_price_inputs import prepare_historical_price_inputs


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def yahoo_payload(close, timestamp=1704067200):
    return {
        "chart": {
            "result": [
                {
                    "timestamp": [timestamp],
                    "indicators": {
                        "quote": [{"close": [close]}],
                        "adjclose": [{"adjclose": [close]}],
                    },
                    "events": {"dividends": {}, "splits": {}},
                }
            ],
            "error": None,
        }
    }


class BacktestPriceInputsTests(unittest.TestCase):
    def test_prepares_unique_membership_prices_and_benchmark_with_available_at(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            membership = root / "historical_membership.csv"
            output = root / "out"
            cache = root / "cache"
            benchmarks = root / "market_benchmarks.csv"
            write_csv(
                membership,
                [
                    {"week": "2025-01-03", "market": "US", "ticker": "AAPL"},
                    {"week": "2025-01-10", "market": "US", "ticker": "aapl"},
                    {"week": "2025-01-03", "market": "US", "ticker": "BRK.B"},
                    {"week": "2025-01-03", "market": "HK", "ticker": "0005.HK"},
                ],
            )
            write_csv(benchmarks, [{"market": "US", "benchmark_name": "S&P 500", "provider_symbol": "^GSPC"}])

            def fetcher(url):
                if "AAPL" in url:
                    return yahoo_payload(10.0)
                if "BRK-B" in url:
                    return yahoo_payload(20.0)
                if "%5EGSPC" in url or "^GSPC" in url:
                    return yahoo_payload(100.0)
                raise AssertionError(url)

            result = prepare_historical_price_inputs(
                membership,
                output,
                cache,
                benchmarks,
                market="US",
                minimum_coverage=1.0,
                fetcher=fetcher,
            )

            self.assertEqual(result["candidate_count"], 2)
            self.assertEqual(result["covered_count"], 2)
            with (output / "price_history.csv").open(encoding="utf-8-sig", newline="") as handle:
                prices = list(csv.DictReader(handle))
            with (output / "benchmark_history.csv").open(encoding="utf-8-sig", newline="") as handle:
                benchmark = list(csv.DictReader(handle))
            self.assertEqual([row["ticker"] for row in prices], ["AAPL", "BRK.B"])
            self.assertEqual(benchmark[0]["ticker"], "^GSPC")
            self.assertTrue(all(row["available_at"] == row["date"] for row in prices + benchmark))

    def test_low_coverage_rejects_without_overwriting_existing_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            membership = root / "historical_membership.csv"
            output = root / "out"
            cache = root / "cache"
            benchmarks = root / "market_benchmarks.csv"
            write_csv(
                membership,
                [
                    {"week": "2025-01-03", "market": "US", "ticker": "AAPL"},
                    {"week": "2025-01-03", "market": "US", "ticker": "MSFT"},
                ],
            )
            write_csv(benchmarks, [{"market": "US", "benchmark_name": "S&P 500", "provider_symbol": "^GSPC"}])
            output.mkdir()
            old_price = output / "price_history.csv"
            old_price.write_text("old", encoding="utf-8")

            def fetcher(url):
                if "AAPL" in url:
                    return yahoo_payload(10.0)
                if "MSFT" in url:
                    raise ConnectionError("offline")
                return yahoo_payload(100.0)

            with self.assertRaisesRegex(RuntimeError, "price history coverage"):
                prepare_historical_price_inputs(
                    membership,
                    output,
                    cache,
                    benchmarks,
                    market="US",
                    minimum_coverage=0.80,
                    fetcher=fetcher,
                )

            self.assertEqual(old_price.read_text(encoding="utf-8"), "old")

    def test_missing_benchmark_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            membership = root / "historical_membership.csv"
            benchmarks = root / "market_benchmarks.csv"
            write_csv(membership, [{"week": "2025-01-03", "market": "US", "ticker": "AAPL"}])
            write_csv(benchmarks, [{"market": "HK", "benchmark_name": "Hang Seng", "provider_symbol": "00011.00"}])

            with self.assertRaisesRegex(ValueError, "benchmark"):
                prepare_historical_price_inputs(
                    membership,
                    root / "out",
                    root / "cache",
                    benchmarks,
                    market="US",
                    fetcher=lambda url: yahoo_payload(10.0),
                )


if __name__ == "__main__":
    unittest.main()
