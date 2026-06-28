import csv
import tempfile
import unittest
from pathlib import Path

from forecast_tracker import (
    due_checkpoints,
    evaluate_forecast,
    latest_on_or_before,
    run_forecast_tracking,
)


class ForecastCalculationTests(unittest.TestCase):
    def prices(self, values, start_day=1):
        return [
            {
                "date": f"2026-01-{start_day + index:02d}",
                "adjusted_close": str(value),
                "data_status": "ready",
            }
            for index, value in enumerate(values)
        ]

    def test_due_checkpoint_boundaries(self):
        self.assertEqual(due_checkpoints("2026-01-01", "2026-01-07"), [])
        self.assertEqual(due_checkpoints("2026-01-01", "2026-01-08"), [1])
        self.assertEqual(due_checkpoints("2026-01-01", "2026-01-29"), [1, 4])
        self.assertEqual(due_checkpoints("2026-01-01", "2026-07-02"), [1, 4, 12, 26])

    def test_latest_on_or_before_uses_seven_day_tolerance(self):
        rows = [{"date": "2026-01-30", "adjusted_close": "100"}]
        self.assertEqual(latest_on_or_before(rows, "2026-02-01")["date"], "2026-01-30")
        self.assertIsNone(latest_on_or_before(rows, "2026-02-08"))

    def test_evaluate_calculates_returns_error_and_path(self):
        forecast = {
            "market": "US", "ticker": "TEST", "generated_date": "2026-01-01",
            "model_version": "valuation_trend_v1", "current_price": "100",
            "target_price": "130", "expected_return": "0.30",
        }
        stock = [
            {"date": "2026-01-01", "adjusted_close": "100", "data_status": "ready"},
            {"date": "2026-01-15", "adjusted_close": "90", "data_status": "ready"},
            {"date": "2026-01-20", "adjusted_close": "130", "data_status": "ready"},
            {"date": "2026-01-29", "adjusted_close": "120", "data_status": "ready"},
        ]
        benchmark = [
            {"date": "2026-01-01", "adjusted_close": "100", "data_status": "ready"},
            {"date": "2026-01-29", "adjusted_close": "110", "data_status": "ready"},
        ]

        result = evaluate_forecast(forecast, stock, benchmark, "2026-01-29", 4)

        self.assertAlmostEqual(result["actual_return"], 0.20)
        self.assertAlmostEqual(result["benchmark_return"], 0.10)
        self.assertAlmostEqual(result["excess_return"], 0.10)
        self.assertAlmostEqual(result["target_error_pct"], 10 / 130)
        self.assertAlmostEqual(result["max_favorable_excursion"], 0.30)
        self.assertAlmostEqual(result["max_adverse_excursion"], -0.10)
        self.assertEqual(result["direction_hit"], True)
        self.assertEqual(result["prediction_horizon"], "12m")
        self.assertEqual(result["prediction_signal"], "expected_return")

    def test_short_horizon_checkpoints_use_short_horizon_forecasts(self):
        forecast = {
            "market": "US", "ticker": "TEST", "generated_date": "2026-01-01",
            "model_version": "valuation_trend_v1", "current_price": "100",
            "target_price": "130", "expected_return": "0.30",
            "one_week_expected_direction": "下行",
            "one_month_expected_direction": "震荡",
        }
        stock = [
            {"date": "2026-01-01", "adjusted_close": "100", "data_status": "ready"},
            {"date": "2026-01-08", "adjusted_close": "92", "data_status": "ready"},
            {"date": "2026-01-29", "adjusted_close": "103", "data_status": "ready"},
        ]

        one_week = evaluate_forecast(forecast, stock, [], "2026-01-29", 1)
        one_month = evaluate_forecast(forecast, stock, [], "2026-01-29", 4)

        self.assertEqual(one_week["prediction_horizon"], "1w")
        self.assertEqual(one_week["prediction_signal"], "下行")
        self.assertEqual(one_week["predicted_direction"], "down")
        self.assertEqual(one_week["actual_direction"], "down")
        self.assertEqual(one_week["direction_hit"], True)
        self.assertEqual(one_month["prediction_horizon"], "1m")
        self.assertEqual(one_month["prediction_signal"], "震荡")
        self.assertEqual(one_month["predicted_direction"], "neutral")
        self.assertEqual(one_month["actual_direction"], "neutral")
        self.assertEqual(one_month["direction_hit"], True)

    def test_short_horizon_checkpoint_without_short_prediction_is_not_evaluated(self):
        forecast = {
            "market": "US", "ticker": "TEST", "generated_date": "2026-01-01",
            "model_version": "valuation_trend_v1", "target_price": "130",
            "expected_return": "0.30",
        }
        stock = [
            {"date": "2026-01-01", "adjusted_close": "100", "data_status": "ready"},
            {"date": "2026-01-08", "adjusted_close": "92", "data_status": "ready"},
        ]

        result = evaluate_forecast(forecast, stock, [], "2026-01-08", 1)

        self.assertEqual(result["evaluation_status"], "prediction_unavailable")
        self.assertEqual(result["prediction_horizon"], "1w")
        self.assertEqual(result["predicted_direction"], "unknown")

    def test_unadjusted_company_action_is_excluded(self):
        forecast = {"generated_date": "2026-01-01", "expected_return": "0.2", "target_price": "120"}
        prices = [
            {"date": "2026-01-01", "adjusted_close": "100", "data_status": "corporate_action_review"},
            {"date": "2026-01-29", "adjusted_close": "110", "data_status": "ready"},
        ]
        result = evaluate_forecast(forecast, prices, [], "2026-01-29", 4)
        self.assertEqual(result["evaluation_status"], "corporate_action_review")


class ForecastTrackerOutputTests(unittest.TestCase):
    def write_csv(self, path, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)

    def test_run_writes_tracking_and_deduplicates_evaluations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); output = root / "out"
            forecasts = root / "forecasts.csv"; stocks = root / "stocks.csv"; benchmark = root / "benchmark.csv"
            self.write_csv(forecasts, [{
                "market": "US", "ticker": "TEST", "company_name": "Test",
                "current_price": "100", "target_price": "120", "expected_return": "0.2",
                "generated_date": "2026-01-01", "model_version": "valuation_trend_v1",
                "valuation_confidence": "high",
                "one_week_expected_direction": "上行",
                "one_month_expected_direction": "震荡偏强",
            }])
            self.write_csv(stocks, [
                {"market": "US", "ticker": "TEST", "date": "2026-01-01", "close": "100", "adjusted_close": "100", "data_status": "ready"},
                {"market": "US", "ticker": "TEST", "date": "2026-01-08", "close": "108", "adjusted_close": "108", "data_status": "ready"},
                {"market": "US", "ticker": "TEST", "date": "2026-01-29", "close": "110", "adjusted_close": "110", "data_status": "ready"},
            ])
            self.write_csv(benchmark, [
                {"market": "US", "ticker": "^GSPC", "date": "2026-01-01", "close": "100", "adjusted_close": "100", "data_status": "ready"},
                {"market": "US", "ticker": "^GSPC", "date": "2026-01-29", "close": "105", "adjusted_close": "105", "data_status": "ready"},
            ])

            run_forecast_tracking(forecasts, stocks, benchmark, output, "US", "2026-01-29")
            run_forecast_tracking(forecasts, stocks, benchmark, output, "US", "2026-01-29")

            with (output / "tracking_snapshot.csv").open(encoding="utf-8-sig", newline="") as handle:
                tracking = list(csv.DictReader(handle))
            with (output / "forecast_evaluations.csv").open(encoding="utf-8-sig", newline="") as handle:
                evaluations = list(csv.DictReader(handle))
            self.assertEqual(len(tracking), 1)
            self.assertEqual(len(evaluations), 2)
            self.assertEqual([row["checkpoint_weeks"] for row in evaluations], ["1", "4"])
            self.assertEqual(evaluations[0]["prediction_horizon"], "1w")
            self.assertEqual(evaluations[1]["prediction_horizon"], "1m")
            self.assertTrue((output / "performance_report.md").exists())
            report = (output / "performance_report.md").read_text(encoding="utf-8-sig")
            self.assertIn("1周成熟评估", report)
            self.assertIn("1个月成熟评估", report)


if __name__ == "__main__":
    unittest.main()
