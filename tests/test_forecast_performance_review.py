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
    "model_version",
    "as_of_date",
    "checkpoint_weeks",
    "prediction_horizon",
    "prediction_signal",
    "evaluation_status",
    "predicted_direction",
    "actual_direction",
    "direction_hit",
    "actual_return",
    "excess_return",
    "valuation_confidence",
]
FORECAST_FIELDS = [
    "market",
    "ticker",
    "company_name",
    "generated_date",
    "one_week_expected_direction",
    "one_month_expected_direction",
]


def write_evaluations(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_forecast_history(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FORECAST_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_shadow_proposals(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["proposal_type", "parameter", "candidate_value", "status"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


class ForecastPerformanceReviewTests(unittest.TestCase):
    def test_review_summarizes_three_market_forecast_performance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_evaluations(
                root / "outputs" / "us_universe" / "forecast_evaluations.csv",
                [
                    {
                        "market": "美股",
                        "ticker": "AAA",
                        "company_name": "Alpha",
                        "generated_date": "2026-06-01",
                        "as_of_date": "2026-06-08",
                        "checkpoint_weeks": "1",
                        "prediction_horizon": "1w",
                        "evaluation_status": "evaluated",
                        "predicted_direction": "up",
                        "actual_direction": "up",
                        "direction_hit": "true",
                        "actual_return": "0.04",
                        "excess_return": "0.01",
                        "valuation_confidence": "high",
                    },
                    {
                        "market": "美股",
                        "ticker": "BBB",
                        "company_name": "Beta",
                        "generated_date": "2026-06-01",
                        "as_of_date": "2026-06-08",
                        "checkpoint_weeks": "1",
                        "prediction_horizon": "1w",
                        "evaluation_status": "prediction_unavailable",
                        "predicted_direction": "unknown",
                        "actual_direction": "down",
                        "direction_hit": "",
                        "actual_return": "-0.02",
                        "excess_return": "-0.03",
                        "valuation_confidence": "low",
                    },
                ],
            )
            write_forecast_history(
                root / "outputs" / "us_universe" / "forecast_history.csv",
                [
                    {
                        "market": "美股",
                        "ticker": "BBB",
                        "company_name": "Beta",
                        "generated_date": "2026-06-01",
                        "one_week_expected_direction": "",
                        "one_month_expected_direction": "",
                    },
                    {
                        "market": "美股",
                        "ticker": "AAA",
                        "company_name": "Alpha",
                        "generated_date": "2026-06-29",
                        "one_week_expected_direction": "上行",
                        "one_month_expected_direction": "下行",
                    },
                ],
            )
            write_evaluations(
                root / "outputs" / "cn_universe" / "forecast_evaluations.csv",
                [
                    {
                        "market": "A股",
                        "ticker": "CCC",
                        "company_name": "Gamma",
                        "generated_date": "2026-06-01",
                        "as_of_date": "2026-06-29",
                        "checkpoint_weeks": "4",
                        "prediction_horizon": "1m",
                        "evaluation_status": "evaluated",
                        "predicted_direction": "up",
                        "actual_direction": "down",
                        "direction_hit": "false",
                        "actual_return": "-0.05",
                        "excess_return": "-0.08",
                        "valuation_confidence": "medium",
                    }
                ],
            )
            write_evaluations(root / "outputs" / "hk_universe" / "forecast_evaluations.csv", [])
            (root / "outputs" / "us_universe" / "model_audit.md").write_text(
                "- 审计状态：sample_accumulating\n",
                encoding="utf-8-sig",
            )
            (root / "outputs" / "cn_universe" / "model_audit.md").write_text(
                "- 审计状态：shadow_analysis_ready\n",
                encoding="utf-8-sig",
            )
            (root / "outputs" / "hk_universe" / "model_audit.md").write_text(
                "- 审计状态：validation_sample_insufficient\n",
                encoding="utf-8-sig",
            )
            write_shadow_proposals(
                root / "outputs" / "cn_universe" / "shadow_model_proposals.csv",
                [
                    {
                        "proposal_type": "direction_threshold",
                        "parameter": "direction_threshold",
                        "candidate_value": "0.03",
                        "status": "analysis_candidate",
                    }
                ],
            )

            from forecast_performance_review import build_forecast_performance_review, render_forecast_performance_review

            payload = build_forecast_performance_review(root, today="2026-06-29")
            report = render_forecast_performance_review(payload)

            self.assertEqual(payload["review_schema"], "forecast_performance_review")
            self.assertEqual(payload["review_version"], 1)
            self.assertEqual(payload["status"], "sample_accumulating")
            self.assertEqual(payload["recommended_action"], "continue_sample_accumulation")
            self.assertEqual(payload["total_evaluations"], 3)
            self.assertEqual(payload["mature_evaluations"], 2)
            self.assertEqual(payload["one_week_mature"], 1)
            self.assertEqual(payload["one_month_mature"], 1)
            self.assertEqual(payload["prediction_unavailable"], 1)
            self.assertEqual(payload["prediction_unavailable_reasons"]["missing_prediction_signal"], 1)
            self.assertEqual(payload["maturity_gap_reasons"]["prediction_unavailable"], 1)
            self.assertEqual(payload["maturity_gap_reasons"]["pending_maturity"], 0)
            self.assertEqual(payload["markets"][0]["maturity_gap_reasons"]["prediction_unavailable"], 1)
            self.assertEqual(payload["markets"][0]["prediction_unavailable_reasons"]["missing_prediction_signal"], 1)
            self.assertEqual(payload["latest_prediction_unavailable_count"], 0)
            self.assertEqual(payload["legacy_prediction_unavailable_count"], 1)
            self.assertEqual(payload["markets"][0]["latest_prediction_unavailable_samples"], [])
            self.assertEqual(payload["markets"][0]["legacy_prediction_unavailable_samples"][0]["ticker"], "BBB")
            self.assertEqual(
                payload["markets"][0]["legacy_prediction_unavailable_samples"][0]["reason"],
                "missing_prediction_signal",
            )
            self.assertEqual(payload["forecast_history_short_signal_missing_count"], 1)
            self.assertEqual(payload["latest_short_signal_missing_count"], 0)
            self.assertEqual(payload["legacy_short_signal_missing_count"], 1)
            self.assertEqual(payload["markets"][0]["forecast_history"]["latest_generated_date"], "2026-06-29")
            self.assertEqual(payload["markets"][0]["forecast_history"]["latest_short_signal_missing_count"], 0)
            self.assertEqual(payload["markets"][0]["forecast_history"]["legacy_short_signal_missing_count"], 1)
            self.assertEqual(payload["markets"][0]["forecast_history"]["latest_one_week_evaluation_date"], "2026-07-06")
            self.assertEqual(payload["markets"][0]["forecast_history"]["latest_one_month_evaluation_date"], "2026-07-27")
            self.assertEqual(payload["next_one_week_evaluation_date"], "2026-07-06")
            self.assertEqual(payload["next_one_month_evaluation_date"], "2026-07-27")
            self.assertEqual(payload["markets"][0]["forecast_history"]["latest_missing_samples"], [])
            self.assertEqual(payload["markets"][0]["forecast_history"]["legacy_missing_samples"][0]["ticker"], "BBB")
            self.assertEqual(payload["missing_market_count"], 0)
            self.assertAlmostEqual(payload["direction_hit_rate"], 0.5)
            self.assertAlmostEqual(payload["average_excess_return"], -0.035)
            self.assertEqual(payload["model_audit_status_counts"]["sample_accumulating"], 1)
            self.assertEqual(payload["model_audit_status_counts"]["shadow_analysis_ready"], 1)
            self.assertEqual(payload["model_audit_status_counts"]["validation_sample_insufficient"], 1)
            self.assertEqual(payload["shadow_model_proposal_count"], 1)
            self.assertEqual(payload["markets"][1]["shadow_model_proposal_count"], 1)
            self.assertFalse(payload["formal_model_change_allowed"])
            self.assertIn("预测表现复核结论", report)
            self.assertIn("样本积累中", report)
            self.assertIn("预测字段缺失原因", report)
            self.assertIn("missing_prediction_signal", report)
            self.assertIn("最新批次预测不可评估样例", report)
            self.assertIn("legacy预测不可评估样例", report)
            self.assertIn("短周期预测字段覆盖", report)
            self.assertIn("最新批次短周期字段缺失样例", report)
            self.assertIn("legacy短周期字段缺失样例", report)
            self.assertIn("legacy", report)
            self.assertIn("forecast_history.csv", report)
            self.assertIn("maturity_gap_reasons", report)
            self.assertIn("next_one_week_evaluation_date", report)
            self.assertIn("2026-07-06", report)
            self.assertIn("shadow_model_proposal_count", report)
            self.assertIn("shadow_analysis_ready", report)
            self.assertIn("正式模型修改：不允许", report)

    def test_review_needs_attention_when_market_evaluation_file_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_evaluations(root / "outputs" / "us_universe" / "forecast_evaluations.csv", [])
            write_evaluations(root / "outputs" / "cn_universe" / "forecast_evaluations.csv", [])

            from forecast_performance_review import build_forecast_performance_review

            payload = build_forecast_performance_review(root, today="2026-06-29")

            self.assertEqual(payload["status"], "needs_attention")
            self.assertEqual(payload["recommended_action"], "collect_forecast_evaluations")
            self.assertEqual(payload["missing_market_count"], 1)
            self.assertFalse(payload["formal_model_change_allowed"])

    def test_review_needs_attention_when_latest_forecast_history_lacks_short_signals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in ("us_universe", "cn_universe", "hk_universe"):
                write_evaluations(root / "outputs" / folder / "forecast_evaluations.csv", [])
            write_forecast_history(
                root / "outputs" / "us_universe" / "forecast_history.csv",
                [
                    {
                        "market": "美股",
                        "ticker": "AAA",
                        "company_name": "Alpha",
                        "generated_date": "2026-06-29",
                        "one_week_expected_direction": "",
                        "one_month_expected_direction": "下行",
                    }
                ],
            )

            from forecast_performance_review import build_forecast_performance_review

            payload = build_forecast_performance_review(root, today="2026-06-29")

            self.assertEqual(payload["status"], "needs_attention")
            self.assertEqual(payload["recommended_action"], "fix_latest_short_prediction_fields")
            self.assertEqual(payload["latest_short_signal_missing_count"], 1)
            self.assertFalse(payload["formal_model_change_allowed"])

    def test_review_counts_pending_maturity_gap_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_evaluations(
                root / "outputs" / "us_universe" / "forecast_evaluations.csv",
                [
                    {
                        "market": "US",
                        "ticker": "AAA",
                        "company_name": "Alpha",
                        "generated_date": "2026-06-29",
                        "prediction_horizon": "1m",
                        "evaluation_status": "tracking",
                        "predicted_direction": "up",
                        "prediction_signal": "up",
                    }
                ],
            )
            write_evaluations(root / "outputs" / "cn_universe" / "forecast_evaluations.csv", [])
            write_evaluations(root / "outputs" / "hk_universe" / "forecast_evaluations.csv", [])

            from forecast_performance_review import build_forecast_performance_review

            payload = build_forecast_performance_review(root, today="2026-06-29")

            self.assertEqual(payload["maturity_gap_reasons"]["pending_maturity"], 1)
            self.assertEqual(payload["maturity_gap_reasons"]["prediction_unavailable"], 0)
            self.assertEqual(payload["markets"][0]["maturity_gap_reasons"]["pending_maturity"], 1)

    def test_review_counts_next_due_forecast_samples_by_earliest_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in ("us_universe", "cn_universe", "hk_universe"):
                write_evaluations(root / "outputs" / folder / "forecast_evaluations.csv", [])
            write_forecast_history(
                root / "outputs" / "us_universe" / "forecast_history.csv",
                [
                    {
                        "market": "US",
                        "ticker": "AAA",
                        "company_name": "Alpha",
                        "generated_date": "2026-06-30",
                        "one_week_expected_direction": "up",
                        "one_month_expected_direction": "up",
                    },
                    {
                        "market": "US",
                        "ticker": "BBB",
                        "company_name": "Beta",
                        "generated_date": "2026-06-30",
                        "one_week_expected_direction": "down",
                        "one_month_expected_direction": "",
                    },
                ],
            )
            write_forecast_history(
                root / "outputs" / "cn_universe" / "forecast_history.csv",
                [
                    {
                        "market": "CN",
                        "ticker": "CCC",
                        "company_name": "Gamma",
                        "generated_date": "2026-06-29",
                        "one_week_expected_direction": "up",
                        "one_month_expected_direction": "neutral",
                    },
                    {
                        "market": "CN",
                        "ticker": "DDD",
                        "company_name": "Delta",
                        "generated_date": "2026-06-29",
                        "one_week_expected_direction": "down",
                        "one_month_expected_direction": "down",
                    },
                ],
            )

            from forecast_performance_review import build_forecast_performance_review, render_forecast_performance_review

            payload = build_forecast_performance_review(root, today="2026-07-05")
            report = render_forecast_performance_review(payload)

            self.assertEqual(payload["next_one_week_evaluation_date"], "2026-07-06")
            self.assertEqual(payload["next_one_week_evaluation_count"], 2)
            self.assertEqual(payload["next_one_month_evaluation_date"], "2026-07-27")
            self.assertEqual(payload["next_one_month_evaluation_count"], 2)
            self.assertEqual(payload["markets"][0]["forecast_history"]["latest_one_week_evaluation_count"], 2)
            self.assertEqual(payload["markets"][0]["forecast_history"]["latest_one_month_evaluation_count"], 1)
            self.assertIn("next_one_week_evaluation_count", report)

    def test_cli_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in ("us_universe", "cn_universe", "hk_universe"):
                write_evaluations(root / "outputs" / folder / "forecast_evaluations.csv", [])
            output = root / "outputs" / "automation" / "latest_forecast_performance_review.json"
            report = root / "outputs" / "automation" / "latest_forecast_performance_review.md"

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "forecast_performance_review.py"),
                    "--project-root",
                    str(root),
                    "--today",
                    "2026-06-29",
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

            combined = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, combined)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8-sig"))["status"], "sample_accumulating")
            self.assertIn("预测表现复核结论", report.read_text(encoding="utf-8-sig"))

    def test_wrapper_and_reporting_bundle_contract(self):
        wrapper = (PROJECT_ROOT / "scripts" / "run_forecast_performance_review.ps1").read_text(
            encoding="utf-8-sig"
        )
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("forecast_performance_review.py", wrapper)
        self.assertIn("latest_forecast_performance_review.json", wrapper)
        self.assertIn("forecast_history.csv", wrapper)
        self.assertIn("run_forecast_performance_review", bundle)
        self.assertLess(
            bundle.index("run_candidate_findings_review"),
            bundle.index("run_forecast_performance_review"),
        )
        self.assertLess(
            bundle.index("run_forecast_performance_review"),
            bundle.index("run_pre_submit_review"),
        )


if __name__ == "__main__":
    unittest.main()
