import csv
import tempfile
import unittest
from pathlib import Path

from tests.test_sec_financial_metrics import duration_fact, metric_facts

from us_weekly_replay import assess_week_quality, leakage_findings, replay_week


class WeeklyReplayQualityTests(unittest.TestCase):
    def test_assess_week_quality_rejects_secondary_membership_and_passes_thresholds(self):
        rejected = assess_week_quality(
            membership_evidence="secondary",
            quote_coverage=0.97,
            financial_coverage=0.90,
            benchmark_ready=True,
            leakage_errors=0,
        )
        accepted = assess_week_quality(
            membership_evidence="verified",
            quote_coverage=0.95,
            financial_coverage=0.80,
            benchmark_ready=True,
            leakage_errors=0,
        )

        self.assertFalse(rejected["eligible"])
        self.assertIn("membership_not_verified", rejected["reasons"])
        self.assertTrue(accepted["eligible"])
        self.assertEqual(accepted["reasons"], [])

    def test_leakage_findings_detects_future_available_at(self):
        findings = leakage_findings(
            [
                {"ticker": "AAPL", "available_at": "2025-07-24"},
                {"ticker": "MSFT", "available_at": "2025-07-26"},
                {"ticker": "TSLA", "available_at": ""},
            ],
            "2025-07-25",
        )

        self.assertEqual(
            findings,
            [
                {
                    "generated_date": "2025-07-25",
                    "ticker": "MSFT",
                    "severity": "severe",
                    "available_at": "2025-07-26",
                    "reason": "future_data_used",
                }
            ],
        )


class WeeklyReplayIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.backtest_date = "2025-07-25"
        self.config_digest = "digest-1"
        self.membership_rows = [
            {
                "market": "US",
                "ticker": "AAPL",
                "cik": "320193",
                "company_name": "Apple Inc.",
                "industry": "Technology",
                "membership_evidence": "verified",
                "available_at": "2025-07-20",
                "market_cap": "100",
                "enterprise_value": "110",
                "net_assets": "50",
                "revenue_ttm": "100",
                "net_income_ttm": "20",
                "ebitda": "20",
                "free_cash_flow": "10",
                "roe": "0.20",
                "roic": "0.15",
                "gross_margin": "0.50",
                "debt_to_assets": "0.30",
                "net_debt_to_ebitda": "0.50",
                "current_ratio": "2.0",
                "revenue_cagr_3y": "0.20",
                "net_income_cagr_3y": "0.20",
                "audit_opinion": "标准无保留",
                "risk_flag": "无",
            },
            {
                "market": "US",
                "ticker": "MSFT",
                "cik": "789019",
                "company_name": "Microsoft Corp.",
                "industry": "Technology",
                "membership_evidence": "verified",
                "available_at": "2025-07-20",
                "market_cap": "1000",
                "enterprise_value": "2000",
                "net_assets": "5",
                "revenue_ttm": "100",
                "net_income_ttm": "10",
                "ebitda": "10",
                "free_cash_flow": "1",
                "roe": "0.05",
                "roic": "0.05",
                "gross_margin": "0.20",
                "debt_to_assets": "0.70",
                "net_debt_to_ebitda": "2.50",
                "current_ratio": "1.0",
                "revenue_cagr_3y": "0.05",
                "net_income_cagr_3y": "0.05",
                "audit_opinion": "标准无保留",
                "risk_flag": "重大",
            },
        ]
        self.company_facts_by_cik = {"320193": metric_facts(), "789019": metric_facts()}
        self.price_rows = [
            {
                "market": "US",
                "ticker": "AAPL",
                "date": "2025-07-24",
                "close": "10",
                "adjusted_close": "10",
                "data_status": "ready",
                "available_at": "2025-07-24",
            },
            {
                "market": "US",
                "ticker": "MSFT",
                "date": "2025-07-24",
                "close": "20",
                "adjusted_close": "20",
                "data_status": "ready",
                "available_at": "2025-07-24",
            },
        ]
        self.benchmark_rows = [
            {
                "market": "US",
                "ticker": "SPY",
                "date": "2025-07-24",
                "close": "500",
                "data_status": "ready",
                "available_at": "2025-07-24",
            }
        ]

    def _run_week(self, root):
        return replay_week(
            self.backtest_date,
            self.membership_rows,
            self.company_facts_by_cik,
            self.price_rows,
            self.benchmark_rows,
            root,
            self.config_digest,
        )

    def test_replay_week_uses_only_as_of_prices_in_history_and_forecasts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.price_rows.append(
                {
                    "market": "US",
                    "ticker": "AAPL",
                    "date": "2025-07-26",
                    "close": "99",
                    "adjusted_close": "99",
                    "data_status": "ready",
                    "available_at": "2025-07-26",
                }
            )
            result = self._run_week(root)

            price_history = (root / "price_history.csv").read_text(encoding="utf-8-sig")
            with (root / "backtest_forecasts.csv").open(encoding="utf-8-sig", newline="") as handle:
                forecasts = list(csv.DictReader(handle))

            self.assertFalse(result["eligible"])
            self.assertIn("data_leakage_detected", result["quality_reasons"])
            self.assertNotIn("2025-07-26", price_history)
            self.assertEqual(len(forecasts), 1)
            self.assertEqual(forecasts[0]["current_price"], "10.0")
            self.assertEqual(forecasts[0]["price_date"], "2025-07-24")
            self.assertEqual(forecasts[0]["week_eligible"], "false")
            self.assertEqual(forecasts[0]["input_available_at_max"], "2025-07-25")

    def test_replay_week_ignores_future_facts_in_screening_inputs(self):
        future_fact = duration_fact(
            9999,
            "2025-01-01",
            "2025-06-30",
            2025,
            "Q2",
            "10-Q",
            "2025-12-31",
        )
        self.company_facts_by_cik["320193"]["facts"]["us-gaap"][
            "RevenueFromContractWithCustomerExcludingAssessedTax"
        ]["units"]["USD"].append(future_fact)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self._run_week(root)

            with (root / "screening_results.csv").open(encoding="utf-8-sig", newline="") as handle:
                screening_rows = list(csv.DictReader(handle))

            self.assertTrue(result["eligible"])
            self.assertEqual(screening_rows[0]["latest_source_filed"], "2025-07-25")
            self.assertEqual(screening_rows[0]["revenue_ttm"], "1100")

    def test_replay_week_records_future_membership_price_and_benchmark_leakage(self):
        self.membership_rows.append(
            {
                "market": "US",
                "ticker": "GOOG",
                "cik": "1652044",
                "company_name": "Alphabet Inc.",
                "industry": "Technology",
                "membership_evidence": "secondary",
                "available_at": "2025-07-27",
            }
        )
        self.price_rows.append(
            {
                "market": "US",
                "ticker": "GOOG",
                "date": "2025-07-27",
                "close": "123",
                "adjusted_close": "123",
                "data_status": "ready",
                "available_at": "2025-07-27",
            }
        )
        self.benchmark_rows.append(
            {
                "market": "US",
                "ticker": "SPY",
                "date": "2025-07-27",
                "close": "501",
                "data_status": "ready",
                "available_at": "2025-07-27",
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self._run_week(root)

            with (root / "data_leakage_audit.csv").open(encoding="utf-8-sig", newline="") as handle:
                audit_rows = list(csv.DictReader(handle))

            severe_types = {
                row["record_type"]
                for row in audit_rows
                if row.get("severity") == "severe"
            }
            self.assertFalse(result["eligible"])
            self.assertIn("data_leakage_detected", result["quality_reasons"])
            self.assertIn("membership", severe_types)
            self.assertIn("price", severe_types)
            self.assertIn("benchmark", severe_types)
            self.assertTrue((root / "data_leakage_audit.md").exists())

    def test_replay_week_deduplicates_backtest_forecasts_by_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._run_week(root)
            self._run_week(root)

            with (root / "backtest_forecasts.csv").open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["market"], "US")
            self.assertEqual(rows[0]["ticker"], "AAPL")


if __name__ == "__main__":
    unittest.main()
