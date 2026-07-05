import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_calibration(path):
    payload = {
        "review_schema": "one_week_forecast_calibration_review",
        "review_version": 1,
        "as_of_date": "2026-07-05",
        "status": "calibration_review_needed",
        "one_week_evaluated_count": 64,
        "recommended_shadow_actions": [
            "review_down_signal_mapping_shadow_only",
            "review_neutral_band_shadow_only",
            "keep_formal_model_unchanged",
        ],
        "formal_model_change_allowed": False,
        "direction_groups": [
            {
                "predicted_direction": "down",
                "sample_count": 41,
                "hit_count": 1,
                "direction_hit_rate": 0.0243902439,
                "opposite_miss_count": 19,
                "neutral_miss_count": 21,
                "average_actual_return": 0.0637,
                "average_excess_return": 0.0529,
            },
            {
                "predicted_direction": "up",
                "sample_count": 17,
                "hit_count": 5,
                "direction_hit_rate": 0.2941,
                "opposite_miss_count": 0,
                "neutral_miss_count": 12,
                "average_actual_return": 0.0391,
                "average_excess_return": 0.0217,
            },
            {
                "predicted_direction": "neutral",
                "sample_count": 6,
                "hit_count": 4,
                "direction_hit_rate": 0.6667,
                "opposite_miss_count": 0,
                "neutral_miss_count": 2,
                "average_actual_return": 0.0183,
                "average_excess_return": 0.054,
            },
        ],
        "market_groups": [
            {
                "market": "港股周筛",
                "sample_count": 35,
                "direction_hit_rate": 0.0286,
                "opposite_miss_count": 16,
                "neutral_miss_count": 18,
            }
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


class OneWeekForecastShadowParameterPlanTests(unittest.TestCase):
    def test_builds_shadow_only_parameter_plan_from_calibration_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calibration = root / "calibration.json"
            write_calibration(calibration)

            from one_week_forecast_shadow_parameter_plan import build_shadow_parameter_plan

            payload = build_shadow_parameter_plan(calibration, as_of_date="2026-07-06")

            self.assertEqual(payload["plan_schema"], "one_week_forecast_shadow_parameter_plan")
            self.assertEqual(payload["status"], "shadow_plan_ready")
            self.assertFalse(payload["formal_model_change_allowed"])
            self.assertEqual(payload["execution_mode"], "shadow_only")
            self.assertIn("run_shadow_backtest_before_formal_change", payload["acceptance_gates"])
            self.assertEqual(payload["one_week_evaluated_count"], 64)
            actions = [item["action_code"] for item in payload["candidate_shadow_changes"]]
            self.assertIn("shadow_demote_down_signal_to_neutral", actions)
            self.assertIn("shadow_widen_neutral_band", actions)
            self.assertIn("shadow_review_hk_down_signal", actions)

    def test_cli_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calibration = root / "calibration.json"
            output = root / "plan.json"
            report = root / "plan.md"
            write_calibration(calibration)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "one_week_forecast_shadow_parameter_plan.py"),
                    "--calibration-review",
                    str(calibration),
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
            self.assertEqual(payload["status"], "shadow_plan_ready")
            text = report.read_text(encoding="utf-8-sig")
            self.assertIn("1周预测影子参数方案", text)
            self.assertIn("shadow_demote_down_signal_to_neutral", text)

    def test_wrapper_bundle_and_pre_submit_include_shadow_parameter_plan(self):
        wrapper = (PROJECT_ROOT / "scripts" / "run_one_week_forecast_shadow_parameter_plan.ps1").read_text(
            encoding="utf-8-sig"
        )
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )
        pre_submit = (PROJECT_ROOT / "pre_submit_review.py").read_text(encoding="utf-8-sig")

        self.assertIn("one_week_forecast_shadow_parameter_plan.py", wrapper)
        self.assertIn("latest_one_week_forecast_shadow_parameter_plan.json", wrapper)
        self.assertIn("run_one_week_forecast_shadow_parameter_plan", bundle)
        self.assertLess(
            bundle.index("run_one_week_forecast_calibration_review"),
            bundle.index("run_one_week_forecast_shadow_parameter_plan"),
        )
        self.assertLess(
            bundle.index("run_one_week_forecast_shadow_parameter_plan"),
            bundle.index("run_medium_term_goal_review"),
        )
        self.assertIn("one_week_forecast_shadow_parameter_plan", pre_submit)


if __name__ == "__main__":
    unittest.main()
