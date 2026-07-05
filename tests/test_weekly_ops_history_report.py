import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_history(path, rows):
    history_path = Path(path)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8-sig",
    )


class WeeklyOpsHistoryReportTests(unittest.TestCase):
    def test_summarizes_recent_ops_history_and_recurring_reasons(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "weekly_ops_check_history.jsonl"
            write_history(
                history_path,
                [
                    {
                        "history_schema": "weekly_ops_check_history",
                        "history_version": 1,
                        "ops_check_schema": "weekly_ops_check",
                        "as_of_date": "2026-06-14",
                        "status": "ready",
                        "freshness_status": "fresh",
                        "attention_reasons": [],
                    },
                    {
                        "history_schema": "weekly_ops_check_history",
                        "history_version": 1,
                        "ops_check_schema": "weekly_ops_check",
                        "as_of_date": "2026-06-21",
                        "status": "needs_attention",
                        "freshness_status": "fresh",
                        "attention_reasons": ["missing_outputs"],
                    },
                    {
                        "history_schema": "weekly_ops_check_history",
                        "history_version": 1,
                        "ops_check_schema": "weekly_ops_check",
                        "as_of_date": "2026-06-28",
                        "status": "needs_attention",
                        "freshness_status": "fresh",
                        "attention_reasons": ["missing_outputs", "automation_config_drift"],
                        "forecast_next_one_week_evaluation_date": "2026-07-07",
                        "forecast_next_one_week_evaluation_count": 42,
                        "forecast_next_one_month_evaluation_date": "2026-07-28",
                        "forecast_next_one_month_evaluation_count": 42,
                    },
                ],
            )

            from weekly_ops_history_report import (
                render_weekly_ops_history_report,
                summarize_weekly_ops_history,
            )

            summary = summarize_weekly_ops_history(history_path, window=3)
            report = render_weekly_ops_history_report(summary)

            self.assertEqual(summary["history_summary_schema"], "weekly_ops_history_summary")
            self.assertEqual(summary["history_summary_version"], 1)
            self.assertEqual(summary["raw_history_count"], 3)
            self.assertEqual(summary["history_count"], 3)
            self.assertEqual(summary["window_size"], 3)
            self.assertEqual(summary["latest_status"], "needs_attention")
            self.assertEqual(summary["ready_count"], 1)
            self.assertEqual(summary["needs_attention_count"], 2)
            self.assertEqual(summary["latest_forecast_next_one_week_evaluation_date"], "2026-07-07")
            self.assertEqual(summary["latest_forecast_next_one_week_evaluation_count"], 42)
            self.assertEqual(summary["latest_forecast_next_one_month_evaluation_date"], "2026-07-28")
            self.assertEqual(summary["latest_forecast_next_one_month_evaluation_count"], 42)
            self.assertEqual(summary["recurring_attention_reasons"], [{"reason": "missing_outputs", "count": 2}])
            self.assertEqual(summary["recommended_action"], "review_recurring_ops_issues")
            self.assertIn("# 周度运维历史摘要", report)
            self.assertIn("最近记录：3", report)
            self.assertIn("重复问题：missing_outputs (2)", report)
            self.assertIn("建议动作：review_recurring_ops_issues", report)

            self.assertIn("raw_history_count: 3", report)
            self.assertIn("latest_forecast_next_one_week_evaluation_count: 42", report)
            self.assertIn("latest_forecast_next_one_month_evaluation_count: 42", report)

    def test_summary_uses_latest_record_per_as_of_date_for_trend_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "weekly_ops_check_history.jsonl"
            write_history(
                history_path,
                [
                    {
                        "history_schema": "weekly_ops_check_history",
                        "history_version": 1,
                        "ops_check_schema": "weekly_ops_check",
                        "as_of_date": "2026-06-21",
                        "status": "needs_attention",
                        "freshness_status": "fresh",
                        "attention_reasons": ["missing_outputs"],
                    },
                    {
                        "history_schema": "weekly_ops_check_history",
                        "history_version": 1,
                        "ops_check_schema": "weekly_ops_check",
                        "as_of_date": "2026-06-28",
                        "status": "needs_attention",
                        "freshness_status": "fresh",
                        "attention_reasons": ["missing_outputs"],
                    },
                    {
                        "history_schema": "weekly_ops_check_history",
                        "history_version": 1,
                        "ops_check_schema": "weekly_ops_check",
                        "as_of_date": "2026-06-28",
                        "status": "ready",
                        "freshness_status": "fresh",
                        "attention_reasons": [],
                    },
                ],
            )

            from weekly_ops_history_report import summarize_weekly_ops_history

            summary = summarize_weekly_ops_history(history_path, window=8)

            self.assertEqual(summary["raw_history_count"], 3)
            self.assertEqual(summary["history_count"], 2)
            self.assertEqual(summary["window_size"], 2)
            self.assertEqual(summary["latest_as_of_date"], "2026-06-28")
            self.assertEqual(summary["latest_status"], "ready")
            self.assertEqual(summary["needs_attention_count"], 1)
            self.assertEqual(summary["recurring_attention_reasons"], [])
            self.assertEqual(summary["recommended_action"], "continue_monitoring")

    def test_cli_writes_json_and_markdown_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            history_path = root / "weekly_ops_check_history.jsonl"
            output_path = root / "latest_weekly_ops_history_summary.json"
            report_path = root / "latest_weekly_ops_history_report.md"
            write_history(
                history_path,
                [
                    {
                        "history_schema": "weekly_ops_check_history",
                        "history_version": 1,
                        "ops_check_schema": "weekly_ops_check",
                        "as_of_date": "2026-06-28",
                        "status": "ready",
                        "freshness_status": "fresh",
                        "attention_reasons": [],
                    }
                ],
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "weekly_ops_history_report.py"),
                    "--history",
                    str(history_path),
                    "--window",
                    "4",
                    "--output",
                    str(output_path),
                    "--report",
                    str(report_path),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("周度运维历史摘要", output)
            payload = json.loads(output_path.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["history_summary_schema"], "weekly_ops_history_summary")
            self.assertEqual(payload["latest_status"], "ready")
            self.assertEqual(payload["recommended_action"], "continue_monitoring")
            self.assertIn("建议动作：continue_monitoring", report_path.read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
