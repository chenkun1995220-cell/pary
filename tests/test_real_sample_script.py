import json
import subprocess
import tempfile
import unittest
from pathlib import Path


def sec_fact(value, fy=2024, filed="2025-02-01", form="10-K", fp="FY"):
    return {
        "val": value,
        "fy": fy,
        "fp": fp,
        "form": form,
        "filed": filed,
        "end": f"{fy}-12-31",
    }


def write_company_fact_fixture(fixture_dir, cik, revenue, net_income, equity, operating_cf, capex):
    facts = {
        "cik": int(cik),
        "entityName": f"Fixture {cik}",
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {"USD": [sec_fact(revenue)]}
                },
                "NetIncomeLoss": {"units": {"USD": [sec_fact(net_income)]}},
                "StockholdersEquity": {"units": {"USD": [sec_fact(equity)]}},
                "NetCashProvidedByUsedInOperatingActivities": {
                    "units": {"USD": [sec_fact(operating_cf)]}
                },
                "PaymentsToAcquirePropertyPlantAndEquipment": {
                    "units": {"USD": [sec_fact(capex)]}
                },
                "Assets": {"units": {"USD": [sec_fact(equity * 2)]}},
                "Liabilities": {"units": {"USD": [sec_fact(equity)]}},
            }
        },
    }
    padded = str(cik).zfill(10)
    (fixture_dir / f"CIK{padded}.json").write_text(
        json.dumps(facts), encoding="utf-8"
    )


class RealSampleScriptTests(unittest.TestCase):
    def test_script_uses_quote_coverage_gate_instead_of_requiring_every_row(self):
        script = (Path(__file__).resolve().parents[1] / "scripts" / "run_us_real_sample.ps1").read_text(encoding="utf-8-sig")

        self.assertIn("MinimumQuoteCoverage", script)
        self.assertIn("QuoteCoverage", script)
        self.assertIn("manual_override_applied", script)
        self.assertIn("share_override_audit.py", script)
    def test_fixture_mode_writes_outputs_to_requested_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture_dir = root / "fixtures"
            output_root = root / "sample_output"
            fixture_dir.mkdir()
            write_company_fact_fixture(fixture_dir, "320193", 1000, 120, 500, 180, 40)
            write_company_fact_fixture(fixture_dir, "789019", 2000, 500, 1200, 650, 60)
            write_company_fact_fixture(fixture_dir, "1652044", 1800, 420, 1100, 580, 55)

            result = subprocess.run(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "scripts\\run_us_real_sample.ps1",
                    "-FixtureDir",
                    str(fixture_dir),
                    "-OutputRoot",
                    str(output_root),
                    "-AllowIncompleteQuotes",
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                timeout=60,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue((output_root / "sec_us_stocks.csv").exists())
            self.assertTrue((output_root / "sec_us_stocks_metrics.csv").exists())
            self.assertTrue((output_root / "data_quality_report.md").exists())
            self.assertTrue((output_root / "screening_results.csv").exists())
            self.assertTrue((output_root / "reports").exists())

    def test_fixture_mode_stops_when_quotes_have_missing_fields_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture_dir = root / "fixtures"
            output_root = root / "sample_output"
            quotes_path = root / "incomplete_quotes.csv"
            fixture_dir.mkdir()
            quotes_path.write_text(
                "\n".join(
                    [
                        "ticker,price,shares_outstanding,net_debt,currency,quote_date,price_unit,shares_unit,debt_unit,quote_source,updated_at",
                        "AAPL,,,,USD,,USD/share,million_shares,USD_million,,",
                        "MSFT,,,,USD,,USD/share,million_shares,USD_million,,",
                        "GOOGL,,,,USD,,USD/share,million_shares,USD_million,,",
                    ]
                )
                + "\n",
                encoding="utf-8-sig",
            )
            write_company_fact_fixture(fixture_dir, "320193", 1000, 120, 500, 180, 40)
            write_company_fact_fixture(fixture_dir, "789019", 2000, 500, 1200, 650, 60)
            write_company_fact_fixture(fixture_dir, "1652044", 1800, 420, 1100, 580, 55)

            result = subprocess.run(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "scripts\\run_us_real_sample.ps1",
                    "-FixtureDir",
                    str(fixture_dir),
                    "-OutputRoot",
                    str(output_root),
                    "-Quotes",
                    str(quotes_path),
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                timeout=60,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Quote coverage", result.stderr + result.stdout)
            self.assertIn("below required", result.stderr + result.stdout)
            self.assertTrue((output_root / "quote_gaps.md").exists())
            self.assertFalse((output_root / "sec_us_stocks.csv").exists())

    def test_script_propagates_python_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            empty_fixture_dir = root / "fixtures"
            output_root = root / "sample_output"
            empty_fixture_dir.mkdir()

            result = subprocess.run(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "scripts\\run_us_real_sample.ps1",
                    "-FixtureDir",
                    str(empty_fixture_dir),
                    "-OutputRoot",
                    str(output_root),
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                timeout=60,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((output_root / "screening_results.csv").exists())


if __name__ == "__main__":
    unittest.main()
