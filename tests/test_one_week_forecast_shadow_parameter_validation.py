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
    "evaluation_status",
    "predicted_direction",
    "actual_direction",
    "direction_hit",
    "actual_return",
    "excess_return",
]


def write_csv_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_plan(path):
    payload = {
        "plan_schema": "one_week_forecast_shadow_parameter_plan",
        "plan_version": 1,
        "as_of_date": "2026-07-06",
        "status": "shadow_plan_ready",
        "execution_mode": "shadow_only",
        "formal_model_change_allowed": False,
        "candidate_shadow_changes": [
            {
                "action_code": "shadow_demote_down_signal_to_neutral",
                "scope": "one_week_prediction",
                "target": "predicted_direction=down",
                "formal_model_change_allowed": False,
            },
            {
                "action_code": "shadow_widen_neutral_band",
                "scope": "one_week_prediction",
                "target": "direction_thresholds",
                "formal_model_change_allowed": False,
            },
            {
                "action_code": "shadow_review_hk_down_signal",
                "scope": "market_specific_one_week_prediction",
                "target": "港股周筛",
                "formal_model_change_allowed": False,
            },
        ],
        "acceptance_gates": ["keep_formal_model_unchanged_until_approved"],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


class OneWeekForecastShadowParameterValidationTests(unittest.TestCase):
    def test_validates_deterministic_shadow_mapping_against_current_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "plan.json"
            write_plan(plan)
            write_csv_rows(
                root / "outputs" / "hk_universe" / "forecast_evaluations.csv",
                [
                    {
                        "market": "港股",
                        "ticker": "00001.HK",
                        "company_name": "Neutral Win",
                        "generated_date": "2026-06-28",
                        "as_of_date": "2026-07-05",
                        "prediction_horizon": "1w",
                        "evaluation_status": "evaluated",
                        "predicted_direction": "down",
                        "actual_direction": "neutral",
                        "direction_hit": "false",
                        "actual_return": "0.01",
                        "excess_return": "0.02",
                    },
                    {
                        "market": "港股",
                        "ticker": "00002.HK",
                        "company_name": "Down Hit",
                        "generated_date": "2026-06-28",
                        "as_of_date": "2026-07-05",
                        "prediction_horizon": "1w",
                        "evaluation_status": "evaluated",
                        "predicted_direction": "down",
                        "actual_direction": "down",
                        "direction_hit": "true",
                        "actual_return": "-0.03",
                        "excess_return": "-0.01",
                    },
                ],
            )
            write_csv_rows(
                root / "outputs" / "us_universe" / "forecast_evaluations.csv",
                [
                    {
                        "market": "美股",
                        "ticker": "OLD",
                        "company_name": "Old Batch",
                        "generated_date": "2026-06-21",
                        "as_of_date": "2026-06-28",
                        "prediction_horizon": "1w",
                        "evaluation_status": "evaluated",
                        "predicted_direction": "down",
                        "actual_direction": "neutral",
                        "direction_hit": "false",
                        "actual_return": "0.02",
                        "excess_return": "0.01",
                    },
                    {
                        "market": "美股",
                        "ticker": "US1",
                        "company_name": "US Neutral",
                        "generated_date": "2026-06-28",
                        "as_of_date": "2026-07-05",
                        "prediction_horizon": "1w",
                        "evaluation_status": "evaluated",
                        "predicted_direction": "down",
                        "actual_direction": "neutral",
                        "direction_hit": "false",
                        "actual_return": "0.02",
                        "excess_return": "0.01",
                    },
                    {
                        "market": "美股",
                        "ticker": "US2",
                        "company_name": "US Hit",
                        "generated_date": "2026-06-28",
                        "as_of_date": "2026-07-05",
                        "prediction_horizon": "1w",
                        "evaluation_status": "evaluated",
                        "predicted_direction": "up",
                        "actual_direction": "up",
                        "direction_hit": "true",
                        "actual_return": "0.04",
                        "excess_return": "0.02",
                    },
                ],
            )

            from one_week_forecast_shadow_parameter_validation import build_shadow_parameter_validation

            payload = build_shadow_parameter_validation(root, plan, as_of_date="2026-07-06")

            self.assertEqual(payload["validation_schema"], "one_week_forecast_shadow_parameter_validation")
            self.assertEqual(payload["status"], "shadow_validation_ready")
            self.assertFalse(payload["formal_model_change_allowed"])
            self.assertEqual(payload["baseline"]["sample_count"], 4)
            self.assertEqual(payload["evaluation_as_of_date"], "2026-07-05")
            self.assertEqual(payload["baseline"]["direction_hit_rate"], 0.5)
            by_action = {item["action_code"]: item for item in payload["candidate_results"]}
            self.assertEqual(by_action["shadow_demote_down_signal_to_neutral"]["validation_status"], "validated")
            self.assertEqual(by_action["shadow_demote_down_signal_to_neutral"]["shadow_hit_rate"], 0.75)
            self.assertGreater(by_action["shadow_demote_down_signal_to_neutral"]["hit_rate_delta"], 0)
            self.assertEqual(by_action["shadow_review_hk_down_signal"]["affected_count"], 2)
            self.assertEqual(by_action["shadow_widen_neutral_band"]["validation_status"], "not_evaluable_current_fields")

    def test_cli_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "plan.json"
            output = root / "validation.json"
            report = root / "validation.md"
            write_plan(plan)
            write_csv_rows(root / "outputs" / "us_universe" / "forecast_evaluations.csv", [])

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "one_week_forecast_shadow_parameter_validation.py"),
                    "--project-root",
                    str(root),
                    "--plan",
                    str(plan),
                    "--as-of-date",
                    "2026-07-06",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["status"], "no_evaluable_samples")
            self.assertFalse(payload["formal_model_change_allowed"])
            self.assertIn("1周预测影子参数验证", report.read_text(encoding="utf-8-sig"))

    def test_wrapper_bundle_and_pre_submit_include_shadow_parameter_validation(self):
        wrapper = (PROJECT_ROOT / "scripts" / "run_one_week_forecast_shadow_parameter_validation.ps1").read_text(
            encoding="utf-8-sig"
        )
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )
        pre_submit = (PROJECT_ROOT / "pre_submit_review.py").read_text(encoding="utf-8-sig")

        self.assertIn("one_week_forecast_shadow_parameter_validation.py", wrapper)
        self.assertIn("latest_one_week_forecast_shadow_parameter_validation.json", wrapper)
        self.assertIn("run_one_week_forecast_shadow_parameter_validation", bundle)
        self.assertLess(
            bundle.index("run_one_week_forecast_shadow_parameter_plan"),
            bundle.index("run_one_week_forecast_shadow_parameter_validation"),
        )
        self.assertLess(
            bundle.index("run_one_week_forecast_shadow_parameter_validation"),
            bundle.index("run_medium_term_goal_review"),
        )
        self.assertIn("one_week_forecast_shadow_parameter_validation", pre_submit)


if __name__ == "__main__":
    unittest.main()
