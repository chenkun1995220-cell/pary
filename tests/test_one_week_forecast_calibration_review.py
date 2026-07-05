import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIELDS = [
    "market",
    "ticker",
    "company_name",
    "generated_date",
    "as_of_date",
    "prediction_horizon",
    "prediction_signal",
    "evaluation_status",
    "predicted_direction",
    "actual_direction",
    "direction_hit",
    "actual_return",
    "excess_return",
]


def write_evaluations(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


class OneWeekForecastCalibrationReviewTests(unittest.TestCase):
    def test_groups_one_week_evaluations_by_predicted_direction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_evaluations(
                root / "outputs" / "hk_universe" / "forecast_evaluations.csv",
                [
                    {
                        "market": "HK",
                        "ticker": "00123.HK",
                        "company_name": "Opposite One",
                        "generated_date": "2026-06-28",
                        "as_of_date": "2026-07-05",
                        "prediction_horizon": "1w",
                        "prediction_signal": "down",
                        "evaluation_status": "evaluated",
                        "predicted_direction": "down",
                        "actual_direction": "up",
                        "direction_hit": "false",
                        "actual_return": "0.10",
                        "excess_return": "0.08",
                    },
                    {
                        "market": "HK",
                        "ticker": "00456.HK",
                        "company_name": "Opposite Two",
                        "generated_date": "2026-06-28",
                        "as_of_date": "2026-07-05",
                        "prediction_horizon": "1w",
                        "prediction_signal": "down",
                        "evaluation_status": "evaluated",
                        "predicted_direction": "down",
                        "actual_direction": "up",
                        "direction_hit": "false",
                        "actual_return": "0.12",
                        "excess_return": "0.09",
                    },
                    {
                        "market": "HK",
                        "ticker": "00789.HK",
                        "company_name": "Neutral Miss",
                        "generated_date": "2026-06-28",
                        "as_of_date": "2026-07-05",
                        "prediction_horizon": "1w",
                        "prediction_signal": "up",
                        "evaluation_status": "evaluated",
                        "predicted_direction": "up",
                        "actual_direction": "neutral",
                        "direction_hit": "false",
                        "actual_return": "0.01",
                        "excess_return": "-0.02",
                    },
                    {
                        "market": "HK",
                        "ticker": "00999.HK",
                        "company_name": "Hit Sample",
                        "generated_date": "2026-06-28",
                        "as_of_date": "2026-07-05",
                        "prediction_horizon": "1w",
                        "prediction_signal": "up",
                        "evaluation_status": "evaluated",
                        "predicted_direction": "up",
                        "actual_direction": "up",
                        "direction_hit": "true",
                        "actual_return": "0.04",
                        "excess_return": "0.01",
                    },
                    {
                        "market": "HK",
                        "ticker": "OLD.HK",
                        "company_name": "Month Sample",
                        "prediction_horizon": "1m",
                        "evaluation_status": "evaluated",
                        "predicted_direction": "down",
                        "actual_direction": "up",
                        "direction_hit": "false",
                    },
                ],
            )

            from one_week_forecast_calibration_review import (
                build_one_week_forecast_calibration_review,
                render_one_week_forecast_calibration_review,
            )

            payload = build_one_week_forecast_calibration_review(root, as_of_date="2026-07-05")
            report = render_one_week_forecast_calibration_review(payload)

            self.assertEqual(payload["review_schema"], "one_week_forecast_calibration_review")
            self.assertEqual(payload["status"], "calibration_review_needed")
            self.assertEqual(payload["one_week_evaluated_count"], 4)
            self.assertFalse(payload["formal_model_change_allowed"])
            self.assertIn("review_down_signal_mapping_shadow_only", payload["recommended_shadow_actions"])
            self.assertIn("review_neutral_band_shadow_only", payload["recommended_shadow_actions"])

            by_direction = {item["predicted_direction"]: item for item in payload["direction_groups"]}
            self.assertEqual(by_direction["down"]["sample_count"], 2)
            self.assertEqual(by_direction["down"]["opposite_miss_count"], 2)
            self.assertEqual(by_direction["down"]["direction_hit_rate"], 0)
            self.assertAlmostEqual(by_direction["down"]["average_actual_return"], 0.11)
            self.assertEqual(by_direction["up"]["sample_count"], 2)
            self.assertEqual(by_direction["up"]["hit_count"], 1)
            self.assertEqual(by_direction["up"]["neutral_miss_count"], 1)
            self.assertEqual(payload["weak_samples"][0]["market"], "港股周筛")

            self.assertIn("1周预测校准影子复盘", report)
            self.assertIn("review_down_signal_mapping_shadow_only", report)

    def test_cli_writes_json_and_markdown_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "calibration.json"
            report = root / "calibration.md"
            write_evaluations(root / "outputs" / "us_universe" / "forecast_evaluations.csv", [])

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "one_week_forecast_calibration_review.py"),
                    "--project-root",
                    str(root),
                    "--as-of-date",
                    "2026-07-05",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["status"], "insufficient_samples")
            self.assertFalse(payload["formal_model_change_allowed"])
            self.assertIn("1周预测校准影子复盘", report.read_text(encoding="utf-8-sig"))

    def test_powershell_wrapper_and_weekly_bundle_include_calibration_review(self):
        wrapper = (PROJECT_ROOT / "scripts" / "run_one_week_forecast_calibration_review.ps1").read_text(
            encoding="utf-8-sig"
        )
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("one_week_forecast_calibration_review.py", wrapper)
        self.assertIn("latest_one_week_forecast_calibration_review.json", wrapper)
        self.assertIn("run_one_week_forecast_calibration_review", bundle)
        self.assertLess(
            bundle.index("run_one_week_forecast_shadow_review"),
            bundle.index("run_one_week_forecast_calibration_review"),
        )
        self.assertLess(
            bundle.index("run_one_week_forecast_calibration_review"),
            bundle.index("run_medium_term_goal_review"),
        )


if __name__ == "__main__":
    unittest.main()
