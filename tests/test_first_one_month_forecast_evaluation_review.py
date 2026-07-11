import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HISTORY_FIELDS = [
    "market",
    "ticker",
    "company_name",
    "generated_date",
    "model_version",
    "one_week_expected_direction",
    "one_month_expected_direction",
]

EVALUATION_FIELDS = [
    "market",
    "ticker",
    "company_name",
    "generated_date",
    "model_version",
    "prediction_horizon",
    "prediction_signal",
    "predicted_direction",
    "actual_direction",
    "direction_hit",
    "actual_return",
    "benchmark_return",
    "excess_return",
    "evaluation_status",
]


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class FirstOneMonthForecastEvaluationReviewTests(unittest.TestCase):
    def make_project(
        self,
        cohort_size=37,
        one_week_count=37,
        one_month_count=0,
        duplicate_horizon="",
        one_month_overrides=None,
    ):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        history = []
        evaluations = []
        for index in range(cohort_size):
            ticker = f"{index + 1:05d}.HK"
            base = {
                "market": "港股",
                "ticker": ticker,
                "company_name": f"公司{index + 1}",
                "generated_date": "2026-07-06",
                "model_version": "valuation_trend_v1",
            }
            history.append(
                {
                    **base,
                    "one_week_expected_direction": "上行",
                    "one_month_expected_direction": "上行",
                }
            )
            if index < one_week_count:
                evaluations.append(
                    {
                        **base,
                        "prediction_horizon": "1w",
                        "prediction_signal": "上行",
                        "predicted_direction": "up",
                        "actual_direction": "up",
                        "direction_hit": "true",
                        "actual_return": "0.08",
                        "benchmark_return": "0.03",
                        "excess_return": "0.05",
                        "evaluation_status": "evaluated",
                    }
                )
            if index < one_month_count:
                evaluation = {
                    **base,
                    "prediction_horizon": "1m",
                    "prediction_signal": "上行",
                    "predicted_direction": "up",
                    "actual_direction": "up",
                    "direction_hit": "true",
                    "actual_return": "0.12",
                    "benchmark_return": "0.04",
                    "excess_return": "0.08",
                    "evaluation_status": "evaluated",
                }
                if one_month_overrides and index in one_month_overrides:
                    evaluation.update(one_month_overrides[index])
                evaluations.append(evaluation)
        if duplicate_horizon:
            duplicate = next(
                row for row in evaluations if row["prediction_horizon"] == duplicate_horizon
            )
            evaluations.append(dict(duplicate))
        write_csv(root / "outputs/hk_universe/forecast_history.csv", HISTORY_FIELDS, history)
        write_csv(root / "outputs/hk_universe/forecast_evaluations.csv", EVALUATION_FIELDS, evaluations)
        write_csv(root / "outputs/us_universe/forecast_evaluations.csv", EVALUATION_FIELDS, [])
        write_csv(root / "outputs/cn_universe/forecast_evaluations.csv", EVALUATION_FIELDS, [])
        return root

    def test_before_one_month_maturity_keeps_fixed_cohort_in_waiting_state(self):
        from first_one_month_forecast_evaluation_review import build_review

        root = self.make_project(cohort_size=37, one_week_count=37, one_month_count=0)
        payload = build_review(root, as_of_date="2026-07-20")

        self.assertEqual(payload["status"], "awaiting_maturity")
        self.assertEqual(payload["cohort"]["expected_sample_count"], 37)
        self.assertEqual(payload["one_week"]["valid_evaluation_count"], 37)
        self.assertEqual(payload["one_month"]["valid_evaluation_count"], 0)
        self.assertEqual(payload["recommended_action"], "wait_for_one_month_maturity")
        self.assertFalse(payload["formal_model_change_allowed"])
        self.assertFalse(payload["formal_model_conclusion_allowed"])

    def test_after_maturity_requires_all_37_one_month_evaluations(self):
        from first_one_month_forecast_evaluation_review import build_review

        payload = build_review(self.make_project(37, 37, 36), "2026-08-04")

        self.assertEqual(payload["status"], "sample_incomplete")
        self.assertEqual(payload["one_month"]["missing_evaluation_count"], 1)

    def test_complete_cohort_is_review_ready(self):
        from first_one_month_forecast_evaluation_review import build_review

        payload = build_review(self.make_project(37, 37, 37), "2026-08-04")

        self.assertEqual(payload["status"], "review_ready")
        self.assertEqual(payload["one_week"]["direction_hit_rate"], 1.0)
        self.assertEqual(payload["one_month"]["direction_hit_rate"], 1.0)
        self.assertAlmostEqual(payload["one_month"]["average_excess_return"], 0.08)

    def test_duplicate_evaluation_key_needs_attention(self):
        from first_one_month_forecast_evaluation_review import build_review

        root = self.make_project(37, 37, 37, duplicate_horizon="1m")
        payload = build_review(root, "2026-08-04")

        self.assertEqual(payload["status"], "needs_attention")
        self.assertIn("duplicate_evaluation_keys", payload["issues"])
        self.assertEqual(payload["duplicate_evaluation_key_count"], 1)

    def test_failure_types_are_mutually_exclusive(self):
        from first_one_month_forecast_evaluation_review import build_review

        root = self.make_project(
            37,
            37,
            37,
            one_month_overrides={
                0: {"predicted_direction": "up", "actual_direction": "down", "direction_hit": "false"},
                1: {"predicted_direction": "neutral", "actual_direction": "up", "direction_hit": "false"},
                2: {"predicted_direction": "down", "actual_direction": "neutral", "direction_hit": "false"},
                3: {"prediction_signal": "", "predicted_direction": "unknown", "direction_hit": "false"},
                4: {"actual_return": "", "excess_return": "", "direction_hit": "false"},
            },
        )
        payload = build_review(root, "2026-08-04")

        self.assertEqual(payload["status"], "sample_incomplete")
        self.assertEqual(
            payload["one_month"]["failure_type_counts"],
            {
                "opposite_direction": 1,
                "predicted_neutral_but_moved": 1,
                "predicted_move_but_actual_neutral": 1,
                "missing_prediction_signal": 1,
                "return_data_missing": 1,
            },
        )
        self.assertEqual(len(payload["one_month"]["failure_samples"]), 5)

    def test_hk_only_cohort_does_not_claim_cross_market_comparison(self):
        from first_one_month_forecast_evaluation_review import build_review

        payload = build_review(self.make_project(37, 37, 37), "2026-08-04")

        comparison = payload["market_comparison"]
        self.assertEqual(comparison["status"], "insufficient_market_coverage")
        self.assertEqual(comparison["markets"]["US"]["status"], "not_in_cohort")
        self.assertEqual(comparison["markets"]["CN"]["status"], "not_in_cohort")
        self.assertEqual(comparison["markets"]["HK"]["status"], "ready")

    def test_duplicate_cohort_key_needs_attention(self):
        from first_one_month_forecast_evaluation_review import build_review

        root = self.make_project(37, 37, 37)
        path = root / "outputs/hk_universe/forecast_history.csv"
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        rows[-1] = dict(rows[0])
        write_csv(path, HISTORY_FIELDS, rows)

        payload = build_review(root, "2026-08-04")

        self.assertEqual(payload["status"], "needs_attention")
        self.assertIn("duplicate_cohort_keys", payload["issues"])
        self.assertEqual(payload["duplicate_cohort_key_count"], 1)

    def test_cli_writes_json_and_markdown(self):
        root = self.make_project(37, 37, 0)
        output = root / "outputs/automation/review.json"
        report = root / "outputs/automation/review.md"

        completed = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parents[1] / "first_one_month_forecast_evaluation_review.py"),
                "--project-root",
                str(root),
                "--as-of-date",
                "2026-07-20",
                "--output",
                str(output),
                "--report",
                str(report),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(output.read_text(encoding="utf-8-sig"))
        self.assertEqual(payload["status"], "awaiting_maturity")
        markdown = report.read_text(encoding="utf-8-sig")
        self.assertIn("首批1个月预测评价", markdown)
        self.assertIn("37", markdown)
        self.assertIn("不允许形成正式模型结论", markdown)

    def test_wrapper_and_bundle_run_after_forecast_performance_before_shadow_review(self):
        project_root = Path(__file__).parents[1]
        wrapper_path = project_root / "scripts/run_first_one_month_forecast_evaluation_review.ps1"
        self.assertTrue(wrapper_path.exists())
        wrapper = wrapper_path.read_text(encoding="utf-8-sig")
        bundle = (project_root / "scripts/run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("first_one_month_forecast_evaluation_review.py", wrapper)
        self.assertIn("latest_first_one_month_forecast_evaluation_review.json", wrapper)
        self.assertLess(
            bundle.index('Label = "run_forecast_performance_review"'),
            bundle.index('Label = "run_first_one_month_forecast_evaluation_review"'),
        )
        self.assertLess(
            bundle.index('Label = "run_first_one_month_forecast_evaluation_review"'),
            bundle.index('Label = "run_one_week_forecast_shadow_review"'),
        )


if __name__ == "__main__":
    unittest.main()
