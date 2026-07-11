import csv
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from candidate_price_history import (
    HISTORY_FIELDS,
    _cache_path,
    _load_candidates,
    _write_history_csv,
    _write_json,
    build_history_url,
    parse_hsi_official_history,
    parse_yahoo_history,
    provider_symbol,
    run_price_history,
)


def yahoo_payload(closes=(10.0, None), timestamps=(1704067200, 1704153600)):
    return {
        "chart": {
            "result": [
                {
                    "timestamp": list(timestamps),
                    "indicators": {"quote": [{"close": list(closes)}]},
                }
            ],
            "error": None,
        }
    }


def write_candidates(path, tickers):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["market", "ticker"])
        writer.writeheader()
        for ticker in tickers:
            writer.writerow({"market": "test", "ticker": ticker})


class CandidatePriceHistoryTests(unittest.TestCase):
    def test_history_fields_include_adjusted_price_and_corporate_actions(self):
        self.assertIn("adjusted_close", HISTORY_FIELDS)
        self.assertIn("dividend", HISTORY_FIELDS)
        self.assertIn("split_ratio", HISTORY_FIELDS)

    def test_parse_history_includes_adjusted_close_and_events(self):
        timestamp = 1704067200
        payload = {"chart": {"result": [{
            "timestamp": [timestamp],
            "indicators": {
                "quote": [{"close": [100.0]}],
                "adjclose": [{"adjclose": [98.0]}],
            },
            "events": {
                "dividends": {str(timestamp): {"amount": 1.0}},
                "splits": {str(timestamp): {"numerator": 2, "denominator": 1}},
            },
        }], "error": None}}

        row = parse_yahoo_history("US", "TEST", payload)[0]

        self.assertEqual(row["adjusted_close"], 98.0)
        self.assertEqual(row["dividend"], 1.0)
        self.assertEqual(row["split_ratio"], 2.0)
        self.assertEqual(row["data_status"], "ready")

    def test_parse_history_marks_unadjusted_fallback(self):
        row = parse_yahoo_history("US", "TEST", yahoo_payload())[0]

        self.assertEqual(row["adjusted_close"], row["close"])
        self.assertEqual(row["data_status"], "unadjusted_fallback")
    def test_provider_symbol_maps_three_markets(self):
        self.assertEqual(provider_symbol("US", "BRK.B"), "BRK-B")
        self.assertEqual(provider_symbol("CN", "600519.SH"), "600519.SS")
        self.assertEqual(provider_symbol("CN", "000001.SZ"), "000001.SZ")
        self.assertEqual(provider_symbol("HK", "01530.HK"), "1530.HK")
        self.assertEqual(provider_symbol("HK", "00700.HK"), "0700.HK")
        self.assertEqual(provider_symbol("US", "^GSPC"), "^GSPC")
        self.assertEqual(provider_symbol("CN", "000300.SS"), "000300.SS")
        self.assertEqual(provider_symbol("HK", "^HSCI"), "^HSCI")

    def test_benchmark_config_only_loads_requested_market(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "benchmarks.csv"
            config.write_text(
                "market,benchmark_name,provider_symbol\n"
                "US,S&P 500,^GSPC\n"
                "CN,CSI 300,000300.SS\n"
                "HK,Hang Seng Composite,^HSCI\n",
                encoding="utf-8",
            )

            self.assertEqual(_load_candidates(config, "CN"), ["000300.SS"])

    def test_hk_composite_benchmark_uses_official_hsi_history(self):
        self.assertEqual(provider_symbol("HK", "00011.00"), "00011.00")
        self.assertEqual(
            build_history_url("HK", "00011.00"),
            "https://www.hsi.com.hk/data/eng/indexes/00011.00/chart.json",
        )
        rows = parse_hsi_official_history(
            "HK",
            "00011.00",
            {"indexLevels-1y": [[1704067200000, 3500.5], [1704153600000, None]]},
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["adjusted_close"], 3500.5)
        self.assertEqual(rows[0]["source"], "Hang Seng Indexes official")

    def test_history_url_uses_one_year_daily_history(self):
        url = build_history_url("US", "BRK.B")

        self.assertIn("BRK-B", url)
        self.assertIn("range=1y", url)
        self.assertIn("interval=1d", url)
        self.assertIn("events=history", url)

    def test_parse_yahoo_history_skips_null_close(self):
        rows = parse_yahoo_history("CN", "600519.SH", yahoo_payload())

        self.assertEqual(
            rows,
            [
                {
                    "market": "CN",
                    "ticker": "600519.SH",
                    "date": "2024-01-01",
                    "close": 10.0,
                    "adjusted_close": 10.0,
                    "dividend": 0.0,
                    "split_ratio": 1.0,
                    "source": "Yahoo Chart",
                    "data_status": "unadjusted_fallback",
                }
            ],
        )

    def test_run_writes_csv_and_one_json_cache_per_ticker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidates.csv"
            output = root / "price_history.csv"
            cache = root / "cache"
            write_candidates(candidates, ["BRK.B", "AAPL"])

            result = run_price_history(
                candidates,
                output,
                cache,
                "US",
                fetcher=lambda url: yahoo_payload(closes=(10.0,), timestamps=(1704067200,)),
            )

            self.assertEqual(result["candidate_count"], 2)
            self.assertEqual(result["covered_count"], 2)
            self.assertEqual(result["coverage"], 1.0)
            self.assertEqual(result["candidates"], 2)
            self.assertEqual(result["ready"], 2)
            self.assertEqual(result["output"], output)
            self.assertEqual(result["cache_fallbacks"], 0)
            with output.open("r", encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([row["ticker"] for row in rows], ["BRK.B", "AAPL"])
            self.assertEqual(len(list(cache.glob("*.json"))), 2)
            self.assertTrue((cache / "BRK-B.json").exists())

    def test_network_failure_uses_fresh_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidates.csv"
            output = root / "price_history.csv"
            cache = root / "cache"
            cache.mkdir()
            write_candidates(candidates, ["600519.SH"])
            (cache / "600519.SS.json").write_text(
                json.dumps(yahoo_payload(closes=(99.5,), timestamps=(1704067200,))),
                encoding="utf-8",
            )

            result = run_price_history(
                candidates,
                output,
                cache,
                "CN",
                fetcher=lambda url: (_ for _ in ()).throw(OSError("network down")),
            )

            self.assertEqual(result["covered_count"], 1)
            self.assertEqual(result["candidates"], 1)
            self.assertEqual(result["ready"], 1)
            self.assertEqual(result["output"], output)
            self.assertEqual(result["cache_fallbacks"], 1)
            with output.open("r", encoding="utf-8-sig", newline="") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row["close"], "99.5")

    def test_strict_mode_rejects_fresh_cache_and_preserves_formal_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidates.csv"
            output = root / "price_history.csv"
            cache = root / "cache"
            cache.mkdir()
            write_candidates(candidates, ["600519.SH"])
            (cache / "600519.SS.json").write_text(
                json.dumps(yahoo_payload(closes=(99.5,), timestamps=(1704067200,))),
                encoding="utf-8",
            )
            output.write_text("existing-output", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "cache fallback used for 1 ticker"):
                run_price_history(
                    candidates,
                    output,
                    cache,
                    "CN",
                    fail_on_cache_fallback=True,
                    fetcher=lambda url: (_ for _ in ()).throw(OSError("network down")),
                )

            self.assertEqual(output.read_text(encoding="utf-8"), "existing-output")

    def test_network_failure_rejects_stale_cache_and_preserves_formal_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidates.csv"
            output = root / "price_history.csv"
            cache = root / "cache"
            cache.mkdir()
            write_candidates(candidates, ["600519.SH"])
            cache_path = cache / "600519.SS.json"
            cache_path.write_text(
                json.dumps(yahoo_payload(closes=(99.5,), timestamps=(1704067200,))),
                encoding="utf-8",
            )
            stale_time = time.time() - 11 * 86400
            os.utime(cache_path, (stale_time, stale_time))
            output.write_text("existing-output", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "coverage 0.00%"):
                run_price_history(
                    candidates,
                    output,
                    cache,
                    "CN",
                    cache_max_age_days=10,
                    fetcher=lambda url: (_ for _ in ()).throw(OSError("network down")),
                )

            self.assertEqual(output.read_text(encoding="utf-8"), "existing-output")

    def test_malformed_response_only_fails_its_ticker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidates.csv"
            output = root / "price_history.csv"
            write_candidates(candidates, ["AAPL", "MSFT"])

            def fetch(url):
                if "AAPL" in url:
                    return {"chart": "broken"}
                return yahoo_payload(closes=(42.0,), timestamps=(1704067200,))

            result = run_price_history(
                candidates,
                output,
                root / "cache",
                "US",
                minimum_coverage=0.50,
                fetcher=fetch,
            )

            self.assertEqual(result["ready"], 1)
            with output.open("r", encoding="utf-8-sig", newline="") as stream:
                self.assertEqual([row["ticker"] for row in csv.DictReader(stream)], ["MSFT"])

    def test_corrupt_cache_only_fails_its_ticker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidates.csv"
            output = root / "price_history.csv"
            cache = root / "cache"
            cache.mkdir()
            write_candidates(candidates, ["AAPL", "MSFT"])
            (cache / "AAPL.json").write_text("not-json", encoding="utf-8")

            def fetch(url):
                if "AAPL" in url:
                    raise OSError("network down")
                return yahoo_payload(closes=(42.0,), timestamps=(1704067200,))

            result = run_price_history(
                candidates,
                output,
                cache,
                "US",
                minimum_coverage=0.50,
                fetcher=fetch,
            )

            self.assertEqual(result["ready"], 1)
            self.assertEqual(result["cache_fallbacks"], 0)

    def test_network_failure_rejects_clearly_future_cache_mtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidates.csv"
            output = root / "price_history.csv"
            cache = root / "cache"
            cache.mkdir()
            write_candidates(candidates, ["AAPL"])
            cache_path = cache / "AAPL.json"
            cache_path.write_text(json.dumps(yahoo_payload()), encoding="utf-8")
            future_time = time.time() + 86400
            os.utime(cache_path, (future_time, future_time))
            output.write_text("existing-output", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "coverage 0.00%"):
                run_price_history(
                    candidates,
                    output,
                    cache,
                    "US",
                    fetcher=lambda url: (_ for _ in ()).throw(OSError("network down")),
                )

            self.assertEqual(output.read_text(encoding="utf-8"), "existing-output")

    def test_cache_filename_sanitizes_windows_illegal_and_reserved_names(self):
        self.assertEqual(_cache_path("cache", "US", "A:B").name, "A_B.json")
        self.assertEqual(_cache_path("cache", "US", "CON").name, "_CON.json")

    def test_invalid_ticker_does_not_stop_other_tickers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidates.csv"
            output = root / "price_history.csv"
            write_candidates(candidates, ["BAD", "600519.SH"])

            result = run_price_history(
                candidates,
                output,
                root / "cache",
                "CN",
                minimum_coverage=0.50,
                fetcher=lambda url: yahoo_payload(
                    closes=(42.0,), timestamps=(1704067200,)
                ),
            )

            self.assertEqual(result["ready"], 1)

    def test_unique_temp_names_do_not_clobber_conventional_temp_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidates.csv"
            output = root / "price_history.csv"
            cache = root / "cache"
            cache.mkdir()
            write_candidates(candidates, ["AAPL"])
            cache_marker = cache / "AAPL.json.tmp"
            output_marker = root / "price_history.csv.tmp"
            cache_marker.write_text("cache-marker", encoding="utf-8")
            output_marker.write_text("output-marker", encoding="utf-8")

            run_price_history(
                candidates,
                output,
                cache,
                "US",
                fetcher=lambda url: yahoo_payload(
                    closes=(42.0,), timestamps=(1704067200,)
                ),
            )

            self.assertEqual(cache_marker.read_text(encoding="utf-8"), "cache-marker")
            self.assertEqual(output_marker.read_text(encoding="utf-8"), "output-marker")

    def test_json_temp_file_is_cleaned_when_replace_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = set(root.iterdir())
            with patch.object(Path, "replace", side_effect=OSError("replace failed")):
                with self.assertRaisesRegex(OSError, "replace failed"):
                    _write_json(root / "cache.json", {"ok": True})
            self.assertEqual(set(root.iterdir()), before)

    def test_csv_temp_file_is_cleaned_when_replace_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = set(root.iterdir())
            row = dict.fromkeys(HISTORY_FIELDS, "value")
            with patch.object(Path, "replace", side_effect=OSError("replace failed")):
                with self.assertRaisesRegex(OSError, "replace failed"):
                    _write_history_csv(root / "history.csv", [row])
            self.assertEqual(set(root.iterdir()), before)

    def test_low_coverage_raises_without_overwriting_formal_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidates.csv"
            output = root / "price_history.csv"
            cache = root / "cache"
            write_candidates(candidates, ["AAPL", "MSFT"])
            output.write_text("existing-output", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "coverage"):
                run_price_history(
                    candidates,
                    output,
                    cache,
                    "US",
                    minimum_coverage=0.80,
                    cache_max_age_days=0,
                    fetcher=lambda url: yahoo_payload(closes=(), timestamps=()),
                )

            self.assertEqual(output.read_text(encoding="utf-8"), "existing-output")

    def test_zero_candidates_writes_empty_csv_successfully(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidates.csv"
            output = root / "price_history.csv"
            write_candidates(candidates, [])

            result = run_price_history(
                candidates,
                output,
                root / "cache",
                "HK",
                fetcher=lambda url: self.fail("fetcher must not be called"),
            )

            self.assertEqual(result["candidate_count"], 0)
            self.assertEqual(result["coverage"], 1.0)
            with output.open("r", encoding="utf-8-sig", newline="") as stream:
                self.assertEqual(list(csv.DictReader(stream)), [])

    def test_cli_exposes_required_arguments(self):
        module_path = Path(__file__).resolve().parents[1] / "candidate_price_history.py"
        completed = subprocess.run(
            [sys.executable, str(module_path), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0)
        for argument in (
            "--market",
            "--candidates",
            "--output",
            "--cache-dir",
            "--minimum-coverage",
            "--cache-max-age-days",
        ):
            self.assertIn(argument, completed.stdout)


if __name__ == "__main__":
    unittest.main()
