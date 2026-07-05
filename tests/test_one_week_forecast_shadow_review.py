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


class OneWeekForecastShadowReviewTests(unittest.TestCase):
    def test_builds_shadow_review_without_allowing_formal_model_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_evaluations(
                root / "outputs" / "us_universe" / "forecast_evaluations.csv",
                [
                    {
                        "market": "US",
                        "ticker": "AAA",
                        "company_name": "Alpha",
                        "generated_date": "2026-06-28",
                        "as_of_date": "2026-07-05",
                        "prediction_horizon": "1w",
                        "prediction_signal": "up",
                        "evaluation_status": "evaluated",
                        "predicted_direction": "up",
                        "actual_direction": "up",
                        "direction_hit": "true",
                        "actual_return": "0.04",
                        "excess_return": "0.02",
                    },
                    {
                        "market": "US",
                        "ticker": "BBB",
                        "company_name": "Beta",
                        "generated_date": "2026-06-28",
                        "as_of_date": "2026-07-05",
                        "prediction_horizon": "1w",
                        "prediction_signal": "down",
                        "evaluation_status": "evaluated",
                        "predicted_direction": "down",
                        "actual_direction": "up",
                        "direction_hit": "false",
                        "actual_return": "0.06",
                        "excess_return": "0.03",
                    },
                    {
                        "market": "US",
                        "ticker": "OLD",
                        "company_name": "Old Month",
                        "generated_date": "2026-06-01",
                        "as_of_date": "2026-07-05",
                        "prediction_horizon": "1m",
                        "prediction_signal": "up",
                        "evaluation_status": "evaluated",
                        "predicted_direction": "up",
                        "actual_direction": "down",
                        "direction_hit": "false",
                    },
                ],
            )
            write_evaluations(
                root / "outputs" / "hk_universe" / "forecast_evaluations.csv",
                [
                    {
                        "market": "HK",
                        "ticker": "00123.HK",
                        "company_name": "Hong Kong Sample",
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
                        "company_name": "Neutral Sample",
                        "generated_date": "2026-06-28",
                        "as_of_date": "2026-07-05",
                        "prediction_horizon": "1w",
                        "prediction_signal": "up",
                        "evaluation_status": "evaluated",
                        "predicted_direction": "up",
                        "actual_direction": "neutral",
                        "direction_hit": "false",
                        "actual_return": "0.01",
                        "excess_return": "-0.01",
                    },
                ],
            )

            from one_week_forecast_shadow_review import (
                build_one_week_forecast_shadow_review,
                render_one_week_forecast_shadow_review,
            )

            payload = build_one_week_forecast_shadow_review(root, as_of_date="2026-07-05")
            report = render_one_week_forecast_shadow_review(payload)

            self.assertEqual(payload["review_schema"], "one_week_forecast_shadow_review")
            self.assertEqual(payload["status"], "shadow_review_needed")
            self.assertEqual(payload["one_week_evaluated_count"], 4)
            self.assertEqual(payload["direction_hits"], 1)
            self.assertAlmostEqual(payload["direction_hit_rate"], 0.25)
            self.assertEqual(payload["opposite_miss_count"], 2)
            self.assertEqual(payload["neutral_miss_count"], 1)
            self.assertEqual(payload["recommended_shadow_actions"][0], "review_direction_mapping")
            self.assertIn("review_neutral_band", payload["recommended_shadow_actions"])
            self.assertFalse(payload["formal_model_change_allowed"])
            self.assertEqual(payload["markets"][0]["one_week_evaluated_count"], 2)
            self.assertEqual(payload["markets"][1]["opposite_miss_count"], 1)
            self.assertEqual(payload["weak_samples"][0]["ticker"], "00123.HK")
            self.assertIn("1周预测影子分析", report)
            self.assertIn("review_direction_mapping", report)

    def test_cli_writes_json_and_markdown_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "shadow.json"
            report = root / "shadow.md"
            write_evaluations(root / "outputs" / "us_universe" / "forecast_evaluations.csv", [])

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "one_week_forecast_shadow_review.py"),
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
            self.assertEqual(payload["status"], "sample_accumulating")
            self.assertFalse(payload["formal_model_change_allowed"])
            self.assertIn("1周预测影子分析", report.read_text(encoding="utf-8-sig"))

    def test_powershell_wrapper_and_weekly_bundle_include_shadow_review(self):
        wrapper = (PROJECT_ROOT / "scripts" / "run_one_week_forecast_shadow_review.ps1").read_text(
            encoding="utf-8-sig"
        )
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("one_week_forecast_shadow_review.py", wrapper)
        self.assertIn("latest_one_week_forecast_shadow_review.json", wrapper)
        self.assertIn("run_one_week_forecast_shadow_review", bundle)
        self.assertLess(
            bundle.index("run_forecast_performance_review"),
            bundle.index("run_one_week_forecast_shadow_review"),
        )


if __name__ == "__main__":
    unittest.main()
