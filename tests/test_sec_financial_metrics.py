import csv
import json
import tempfile
import unittest
from pathlib import Path

from sec_financial_metrics import (
    calculate_financial_metrics,
    latest_ttm_value,
    run_financial_metrics_enhancement,
)


def duration_fact(value, start, end, fy, fp, form, filed):
    return {
        "val": value,
        "start": start,
        "end": end,
        "fy": fy,
        "fp": fp,
        "form": form,
        "filed": filed,
    }


def instant_fact(value, end="2025-06-30", fy=2025, fp="Q2", form="10-Q", filed="2025-07-25"):
    return {
        "val": value,
        "end": end,
        "fy": fy,
        "fp": fp,
        "form": form,
        "filed": filed,
    }


def metric_facts():
    annual_periods = [
        (2021, 700, 70),
        (2022, 800, 80),
        (2023, 900, 90),
        (2024, 1000, 100),
    ]

    def annual_series(index):
        return [
            duration_fact(
                period[index],
                f"{period[0]}-01-01",
                f"{period[0]}-12-31",
                period[0],
                "FY",
                "10-K",
                f"{period[0] + 1}-02-01",
            )
            for period in annual_periods
        ]

    revenue = annual_series(1) + [
        duration_fact(500, "2024-01-01", "2024-06-30", 2024, "Q2", "10-Q", "2024-07-25"),
        duration_fact(600, "2025-01-01", "2025-06-30", 2025, "Q2", "10-Q", "2025-07-25"),
    ]
    net_income = annual_series(2) + [
        duration_fact(50, "2024-01-01", "2024-06-30", 2024, "Q2", "10-Q", "2024-07-25"),
        duration_fact(70, "2025-01-01", "2025-06-30", 2025, "Q2", "10-Q", "2025-07-25"),
    ]

    def ttm_series(annual, prior_ytd, current_ytd):
        return [
            duration_fact(annual, "2024-01-01", "2024-12-31", 2024, "FY", "10-K", "2025-02-01"),
            duration_fact(prior_ytd, "2024-01-01", "2024-06-30", 2024, "Q2", "10-Q", "2024-07-25"),
            duration_fact(current_ytd, "2025-01-01", "2025-06-30", 2025, "Q2", "10-Q", "2025-07-25"),
        ]

    return {
        "cik": 320193,
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": revenue}},
                "NetIncomeLoss": {"units": {"USD": net_income}},
                "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": ttm_series(150, 70, 90)}},
                "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": ttm_series(40, 20, 25)}},
                "GrossProfit": {"units": {"USD": ttm_series(400, 200, 250)}},
                "OperatingIncomeLoss": {"units": {"USD": ttm_series(150, 70, 90)}},
                "DepreciationDepletionAndAmortization": {"units": {"USD": ttm_series(50, 25, 30)}},
                "IncomeTaxExpenseBenefit": {"units": {"USD": ttm_series(30, 14, 18)}},
                "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": {
                    "units": {"USD": ttm_series(130, 65, 85)}
                },
                "AssetsCurrent": {"units": {"USD": [instant_fact(500)]}},
                "LiabilitiesCurrent": {"units": {"USD": [instant_fact(250)]}},
                "StockholdersEquity": {"units": {"USD": [instant_fact(700)]}},
                "LongTermDebtCurrent": {"units": {"USD": [instant_fact(50)]}},
                "LongTermDebtNoncurrent": {"units": {"USD": [instant_fact(300)]}},
                "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [instant_fact(100)]}},
            }
        },
    }


class SecFinancialMetricsTests(unittest.TestCase):
    def test_latest_ttm_uses_fiscal_year_plus_current_ytd_minus_prior_ytd(self):
        facts = metric_facts()

        value, basis = latest_ttm_value(
            facts,
            ["RevenueFromContractWithCustomerExcludingAssessedTax"],
        )

        self.assertEqual(value, 1100)
        self.assertEqual(basis, "ttm")

    def test_latest_ttm_falls_back_to_latest_annual_value(self):
        facts = metric_facts()
        revenue_facts = facts["facts"]["us-gaap"][
            "RevenueFromContractWithCustomerExcludingAssessedTax"
        ]["units"]["USD"]
        facts["facts"]["us-gaap"][
            "RevenueFromContractWithCustomerExcludingAssessedTax"
        ]["units"]["USD"] = [fact for fact in revenue_facts if fact["form"] == "10-K"]

        value, basis = latest_ttm_value(
            facts,
            ["RevenueFromContractWithCustomerExcludingAssessedTax"],
        )

        self.assertEqual(value, 1000)
        self.assertEqual(basis, "annual_fallback")

    def test_calculates_core_financial_metrics(self):
        metrics = calculate_financial_metrics(metric_facts())

        self.assertEqual(metrics["revenue_ttm"], 1100)
        self.assertEqual(metrics["net_income_ttm"], 120)
        self.assertEqual(metrics["operating_cash_flow"], 170)
        self.assertEqual(metrics["capex"], -45)
        self.assertEqual(metrics["ebitda"], 225)
        self.assertAlmostEqual(metrics["gross_margin"], 450 / 1100)
        self.assertEqual(metrics["current_ratio"], 2)
        self.assertAlmostEqual(metrics["net_debt_to_ebitda"], 250 / 225)
        self.assertAlmostEqual(metrics["revenue_cagr_3y"], (1000 / 700) ** (1 / 3) - 1)
        self.assertAlmostEqual(metrics["net_income_cagr_3y"], (100 / 70) ** (1 / 3) - 1)
        expected_nopat = 170 * (1 - 34 / 150)
        self.assertAlmostEqual(metrics["roic"], expected_nopat / 950)
        self.assertEqual(metrics["metrics_period_basis"], "ttm")

    def test_enhances_standard_csv_using_company_facts_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "sec.csv"
            output_path = root / "enhanced.csv"
            fixture_dir = root / "fixtures"
            fixture_dir.mkdir()
            input_path.write_text(
                "market,ticker,company_name,source_cik,revenue_ttm\n"
                "美股,EXMPL,Example Inc.,0000320193,1000\n",
                encoding="utf-8-sig",
            )
            (fixture_dir / "CIK0000320193.json").write_text(
                json.dumps(metric_facts()), encoding="utf-8"
            )

            result = run_financial_metrics_enhancement(
                input_path,
                output_path,
                fixture_dir=fixture_dir,
            )
            with output_path.open("r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))

            self.assertEqual(result["rows"], 1)
            self.assertEqual(rows[0]["revenue_ttm"], "1100")
            self.assertEqual(rows[0]["ebitda"], "225")
            self.assertEqual(rows[0]["metrics_period_basis"], "ttm")


if __name__ == "__main__":
    unittest.main()
