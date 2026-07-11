import csv
import json
import tempfile
import unittest
from pathlib import Path

from us_universe_builder import build_universe_rows, run_universe_build


def ticker_payload():
    return {
        "fields": ["cik", "name", "ticker", "exchange"],
        "data": [
            [320193, "Apple Inc.", "AAPL", "Nasdaq"],
            [789019, "Microsoft Corporation", "MSFT", "Nasdaq"],
            [1652044, "Alphabet Inc.", "GOOGL", "Nasdaq"],
        ],
    }


class UsUniverseBuilderTests(unittest.TestCase):
    def test_writes_identity_conflict_audit_for_configured_cik_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symbols_path = root / "symbols.csv"
            fixture_path = root / "company_tickers_exchange.json"
            output_path = root / "companies.csv"
            audit_path = root / "sec_identity_audit.csv"
            symbols_path.write_text(
                "source_ticker,ticker,company_name,industry,cik,enabled\n"
                "XOM,XOM,ExxonMobil,Energy,34088,1\n",
                encoding="utf-8-sig",
            )
            fixture_path.write_text(
                json.dumps(
                    {
                        "fields": ["cik", "name", "ticker", "exchange"],
                        "data": [[2115436, "ExxonMobil Holdings Corp", "XOM", "NYSE"]],
                    }
                ),
                encoding="utf-8",
            )

            result = run_universe_build(
                symbols_path,
                output_path,
                fixture_path=fixture_path,
                identity_audit_path=audit_path,
            )

            with audit_path.open("r", encoding="utf-8-sig", newline="") as handle:
                audit_rows = list(csv.DictReader(handle))
            self.assertEqual(result["identity_conflict_count"], 1)
            self.assertEqual(result["identity_audit_path"], audit_path)
            self.assertEqual(audit_rows[0]["ticker"], "XOM")
            self.assertEqual(audit_rows[0]["configured_cik"], "34088")
            self.assertEqual(audit_rows[0]["sec_candidate_ciks"], "2115436")
            self.assertEqual(audit_rows[0]["selected_cik"], "34088")
            self.assertEqual(audit_rows[0]["resolution"], "configured_identity_preserved")

    def test_preserves_configured_identity_when_sec_ticker_cik_conflicts(self):
        symbols = [
            {
                "ticker": "XOM",
                "cik": "34088",
                "company_name": "ExxonMobil",
                "industry": "Energy",
                "enabled": "1",
            }
        ]
        payload = {
            "fields": ["cik", "name", "ticker", "exchange"],
            "data": [[2115436, "ExxonMobil Holdings Corp", "XOM", "NYSE"]],
        }

        rows, missing = build_universe_rows(symbols, payload)

        self.assertEqual(missing, [])
        self.assertEqual(rows[0]["cik"], "34088")
        self.assertEqual(rows[0]["company_name"], "ExxonMobil")
        self.assertEqual(rows[0]["exchange"], "NYSE")

    def test_prefers_configured_cik_when_sec_payload_has_duplicate_ticker(self):
        symbols = [
            {
                "ticker": "XOM",
                "cik": "34088",
                "company_name": "ExxonMobil",
                "industry": "Energy",
                "enabled": "1",
            }
        ]
        payload = {
            "fields": ["cik", "name", "ticker", "exchange"],
            "data": [
                [34088, "EXXON MOBIL CORP", "XOM", "NYSE"],
                [2115436, "ExxonMobil Holdings Corp", "XOM", "NYSE"],
            ],
        }

        rows, missing = build_universe_rows(symbols, payload)

        self.assertEqual(missing, [])
        self.assertEqual(rows[0]["cik"], "34088")
        self.assertEqual(rows[0]["company_name"], "EXXON MOBIL CORP")

    def test_builds_company_rows_from_sec_ticker_payload(self):
        symbols = [
            {"ticker": "AAPL", "industry": "科技硬件", "enabled": "1"},
            {"ticker": "MSFT", "industry": "科技软件", "enabled": "1"},
        ]

        rows, missing = build_universe_rows(symbols, ticker_payload())

        self.assertEqual(missing, [])
        self.assertEqual(rows[0]["ticker"], "AAPL")
        self.assertEqual(rows[0]["cik"], "320193")
        self.assertEqual(rows[0]["company_name"], "Apple Inc.")
        self.assertEqual(rows[0]["exchange"], "Nasdaq")
        self.assertEqual(rows[0]["audit_opinion"], "标准无保留")
        self.assertEqual(rows[0]["risk_flag"], "无")

    def test_reports_enabled_tickers_missing_from_sec_payload(self):
        symbols = [{"ticker": "UNKNOWN", "industry": "科技软件", "enabled": "1"}]

        rows, missing = build_universe_rows(symbols, ticker_payload())

        self.assertEqual(rows, [])
        self.assertEqual(missing, ["UNKNOWN"])

    def test_runs_builder_with_local_sec_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symbols_path = root / "symbols.csv"
            fixture_path = root / "company_tickers_exchange.json"
            output_path = root / "companies.csv"
            symbols_path.write_text(
                "ticker,industry,enabled\nAAPL,科技硬件,1\nMSFT,科技软件,1\n",
                encoding="utf-8-sig",
            )
            fixture_path.write_text(json.dumps(ticker_payload()), encoding="utf-8")

            result = run_universe_build(
                symbols_path,
                output_path,
                fixture_path=fixture_path,
            )
            with output_path.open("r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))

            self.assertEqual(result["rows"], 2)
            self.assertEqual(result["missing"], [])
            self.assertEqual(rows[1]["ticker"], "MSFT")

    def test_build_script_refreshes_sp500_constituents_by_default(self):
        script = Path("scripts/build_us_universe.ps1").read_text(encoding="utf-8-sig")

        self.assertIn("sp500_constituents.py", script)
        self.assertIn("data\\cache\\sp500", script)
        self.assertIn("$SkipConstituentRefresh", script)
        self.assertIn("--identity-audit", script)

    def test_run_builder_rejects_low_sec_match_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symbols_path = root / "symbols.csv"
            fixture_path = root / "company_tickers_exchange.json"
            symbols_path.write_text(
                "ticker,industry,enabled\nAAPL,Technology,1\nUNKNOWN,Technology,1\n",
                encoding="utf-8-sig",
            )
            fixture_path.write_text(json.dumps(ticker_payload()), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "match rate"):
                run_universe_build(
                    symbols_path,
                    root / "companies.csv",
                    fixture_path=fixture_path,
                    minimum_match_rate=0.98,
                )


if __name__ == "__main__":
    unittest.main()
