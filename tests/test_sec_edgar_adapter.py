import csv
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from sec_edgar_adapter import (
    cik_to_10_digits,
    load_company_facts,
    load_sec_config,
    normalize_company_facts,
    run_sec_import,
)


def sec_fact(value, fy=2024, filed="2025-02-01", form="10-K", fp="FY"):
    return {
        "val": value,
        "fy": fy,
        "fp": fp,
        "form": form,
        "filed": filed,
        "end": f"{fy}-12-31",
    }


class SecEdgarAdapterTests(unittest.TestCase):
    def test_load_company_facts_writes_download_to_shared_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            payload = {"cik": 320193, "entityName": "Apple Inc.", "facts": {}}

            result = load_company_facts(
                "320193",
                user_agent="Test test@example.com",
                cache_dir=cache_dir,
                fetcher=lambda cik, user_agent: payload,
            )

            cache_file = cache_dir / "CIK0000320193.json"
            self.assertEqual(result, payload)
            self.assertTrue(cache_file.exists())
            self.assertEqual(json.loads(cache_file.read_text(encoding="utf-8")), payload)

    def test_load_company_facts_reuses_fresh_cache_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            cache_dir.mkdir()
            payload = {"cik": 320193, "entityName": "Cached Apple", "facts": {}}
            (cache_dir / "CIK0000320193.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )

            def fail_fetch(cik, user_agent):
                raise AssertionError("fresh cache must not fetch")

            result = load_company_facts(
                "320193",
                cache_dir=cache_dir,
                fetcher=fail_fetch,
            )

            self.assertEqual(result["entityName"], "Cached Apple")

    def test_load_company_facts_falls_back_to_stale_cache_on_fetch_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            cache_dir.mkdir()
            cache_file = cache_dir / "CIK0000320193.json"
            payload = {"cik": 320193, "entityName": "Stale Apple", "facts": {}}
            cache_file.write_text(json.dumps(payload), encoding="utf-8")
            old_time = time.time() - (10 * 24 * 60 * 60)
            os.utime(cache_file, (old_time, old_time))

            result = load_company_facts(
                "320193",
                user_agent="Test test@example.com",
                cache_dir=cache_dir,
                max_age_hours=1,
                fetcher=lambda cik, user_agent: (_ for _ in ()).throw(
                    OSError("SEC unavailable")
                ),
            )

            self.assertEqual(result["entityName"], "Stale Apple")

    def test_cik_is_padded_to_ten_digits(self):
        self.assertEqual(cik_to_10_digits("320193"), "0000320193")

    def test_normalizes_company_facts_to_standard_screening_row(self):
        facts = {
            "cik": 320193,
            "entityName": "Example Inc.",
            "facts": {
                "us-gaap": {
                    "Revenues": {"units": {"USD": [sec_fact(1000, 2023), sec_fact(1200, 2024)]}},
                    "NetIncomeLoss": {"units": {"USD": [sec_fact(120, 2024)]}},
                    "StockholdersEquity": {"units": {"USD": [sec_fact(500, 2024)]}},
                    "NetCashProvidedByUsedInOperatingActivities": {
                        "units": {"USD": [sec_fact(180, 2024)]}
                    },
                    "PaymentsToAcquirePropertyPlantAndEquipment": {
                        "units": {"USD": [sec_fact(40, 2024)]}
                    },
                    "Assets": {"units": {"USD": [sec_fact(900, 2024)]}},
                    "Liabilities": {"units": {"USD": [sec_fact(300, 2024)]}},
                }
            },
        }
        metadata = {
            "ticker": "EXMPL",
            "company_name": "Example Inc.",
            "industry": "科技软件",
            "market_cap": "2400",
            "enterprise_value": "2600",
            "ebitda": "180",
            "industry_pe_median": "35",
            "industry_pb_median": "7",
            "industry_ev_ebitda_median": "22",
            "roic": "0.12",
            "gross_margin": "0.60",
            "current_ratio": "1.8",
            "revenue_cagr_3y": "0.08",
            "net_income_cagr_3y": "0.10",
        }

        row = normalize_company_facts(facts, metadata)

        self.assertEqual(row["market"], "美股")
        self.assertEqual(row["ticker"], "EXMPL")
        self.assertEqual(row["revenue_ttm"], 1200)
        self.assertEqual(row["net_income_ttm"], 120)
        self.assertEqual(row["net_assets"], 500)
        self.assertEqual(row["operating_cash_flow"], 180)
        self.assertEqual(row["capex"], -40)
        self.assertAlmostEqual(row["debt_to_assets"], 300 / 900)
        self.assertEqual(row["audit_opinion"], "标准无保留")
        self.assertEqual(row["risk_flag"], "无")

    def test_sec_import_uses_local_fixture_and_writes_standard_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture_dir = root / "fixtures"
            output_path = root / "sec_us_stocks.csv"
            config_path = root / "sec_us_companies.csv"
            fixture_dir.mkdir()

            facts = {
                "cik": 320193,
                "entityName": "Example Inc.",
                "facts": {
                    "us-gaap": {
                        "RevenueFromContractWithCustomerExcludingAssessedTax": {
                            "units": {"USD": [sec_fact(1200, 2024)]}
                        },
                        "NetIncomeLoss": {"units": {"USD": [sec_fact(120, 2024)]}},
                        "StockholdersEquity": {"units": {"USD": [sec_fact(500, 2024)]}},
                        "NetCashProvidedByUsedInOperatingActivities": {
                            "units": {"USD": [sec_fact(180, 2024)]}
                        },
                        "PaymentsToAcquirePropertyPlantAndEquipment": {
                            "units": {"USD": [sec_fact(40, 2024)]}
                        },
                    }
                },
            }
            (fixture_dir / "CIK0000320193.json").write_text(
                json.dumps(facts), encoding="utf-8"
            )
            with config_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "ticker",
                        "cik",
                        "company_name",
                        "industry",
                        "market_cap",
                        "enterprise_value",
                        "industry_pe_median",
                        "industry_pb_median",
                        "industry_ev_ebitda_median",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "ticker": "EXMPL",
                        "cik": "320193",
                        "company_name": "Example Inc.",
                        "industry": "科技软件",
                        "market_cap": "2400",
                        "enterprise_value": "2600",
                        "industry_pe_median": "35",
                        "industry_pb_median": "7",
                        "industry_ev_ebitda_median": "22",
                    }
                )

            config = load_sec_config(config_path)
            result = run_sec_import(config_path, output_path, fixture_dir=fixture_dir)

            self.assertEqual(len(config), 1)
            self.assertEqual(result["rows"], 1)
            output = output_path.read_text(encoding="utf-8-sig")
            self.assertIn("EXMPL", output)
            self.assertIn("revenue_ttm", output)

    def test_load_company_facts_accepts_utf8_bom_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp)
            (fixture_dir / "CIK0000320193.json").write_text(
                json.dumps({"cik": 320193, "facts": {}}),
                encoding="utf-8-sig",
            )

            facts = load_company_facts("320193", fixture_dir=fixture_dir)

            self.assertEqual(facts["cik"], 320193)


if __name__ == "__main__":
    unittest.main()
