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


class WeeklyDeliveryHistoryReportTests(unittest.TestCase):
    def test_summarizes_recent_delivery_history_and_recurring_reasons(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "weekly_delivery_check_history.jsonl"
            write_history(
                history_path,
                [
                    {
                        "history_schema": "weekly_delivery_check_history",
                        "history_version": 1,
                        "delivery_check_schema": "weekly_delivery_check",
                        "as_of_date": "2026-06-14",
                        "status": "ready",
                        "freshness_status": "fresh",
                        "attention_reasons": [],
                        "candidate_count_total": 60,
                        "manual_review_pending_count": 4,
                    },
                    {
                        "history_schema": "weekly_delivery_check_history",
                        "history_version": 1,
                        "delivery_check_schema": "weekly_delivery_check",
                        "as_of_date": "2026-06-21",
                        "status": "needs_attention",
                        "freshness_status": "fresh",
                        "attention_reasons": ["missing_outputs"],
                        "conclusion_health_status": "needs_review",
                        "conclusion_health_score": 80,
                        "conclusion_health_reasons": ["manual_review_pending:6"],
                        "candidate_count_total": 62,
                        "manual_review_pending_count": 6,
                        "action_items_status": "missing",
                        "action_items_freshness_status": "unknown",
                        "action_items_count": 0,
                        "conclusion_signal_status": "missing",
                        "missing_conclusion_signals": ["automation.forecast_performance"],
                        "missing_conclusion_signal_fixes": {
                            "automation.forecast_performance": (
                                "rerun_self_analysis_and_weekly_conclusion: ensure latest_self_analysis_manifest.json "
                                "contains forecast_performance before show_weekly_conclusion.ps1"
                            )
                        },
                    },
                    {
                        "history_schema": "weekly_delivery_check_history",
                        "history_version": 1,
                        "delivery_check_schema": "weekly_delivery_check",
                        "as_of_date": "2026-06-28",
                        "status": "needs_attention",
                        "freshness_status": "fresh",
                        "attention_reasons": ["missing_outputs", "stale_conclusion_date"],
                        "conclusion_health_status": "needs_review",
                        "conclusion_health_score": 75,
                        "conclusion_health_reasons": ["manual_review_pending:6"],
                        "candidate_count_total": 64,
                        "manual_review_pending_count": 12,
                        "action_items_status": "missing",
                        "action_items_freshness_status": "unknown",
                        "action_items_count": 0,
                        "conclusion_signal_status": "missing",
                        "missing_conclusion_signals": [
                            "automation.data_quality_history",
                            "automation.forecast_performance",
                        ],
                        "missing_conclusion_signal_fixes": {
                            "automation.data_quality_history": (
                                "rerun_self_analysis_and_weekly_conclusion: ensure latest_self_analysis_manifest.json "
                                "contains data_quality_history before show_weekly_conclusion.ps1"
                            ),
                            "automation.forecast_performance": (
                                "rerun_self_analysis_and_weekly_conclusion: ensure latest_self_analysis_manifest.json "
                                "contains forecast_performance before show_weekly_conclusion.ps1"
                            ),
                        },
                    },
                ],
            )

            from weekly_delivery_history_report import (
                render_weekly_delivery_history_report,
                summarize_weekly_delivery_history,
            )

            summary = summarize_weekly_delivery_history(history_path, window=3)
            report = render_weekly_delivery_history_report(summary)

            self.assertEqual(summary["history_summary_schema"], "weekly_delivery_history_summary")
            self.assertEqual(summary["history_summary_version"], 1)
            self.assertEqual(summary["raw_history_count"], 3)
            self.assertEqual(summary["history_count"], 3)
            self.assertEqual(summary["window_size"], 3)
            self.assertEqual(summary["latest_status"], "needs_attention")
            self.assertEqual(summary["latest_candidate_count_total"], 64)
            self.assertEqual(summary["latest_manual_review_pending_count"], 12)
            self.assertEqual(summary["ready_count"], 1)
            self.assertEqual(summary["needs_attention_count"], 2)
            self.assertEqual(summary["recurring_attention_reasons"], [{"reason": "missing_outputs", "count": 2}])
            self.assertEqual(
                summary["recurring_health_reasons"],
                [{"reason": "manual_review_pending:6", "count": 2}],
            )
            self.assertEqual(summary["latest_conclusion_health_status"], "needs_review")
            self.assertEqual(summary["latest_conclusion_health_score"], 75)
            self.assertEqual(summary["latest_conclusion_health_reasons"], ["manual_review_pending:6"])
            self.assertEqual(summary["latest_action_items_status"], "missing")
            self.assertEqual(summary["latest_action_items_freshness_status"], "unknown")
            self.assertEqual(summary["latest_action_items_count"], 0)
            self.assertEqual(summary["action_items_ready_count"], 0)
            self.assertEqual(summary["action_items_problem_count"], 2)
            self.assertEqual(summary["recurring_action_items_issues"], [{"status": "missing", "count": 2}])
            self.assertEqual(summary["latest_conclusion_signal_status"], "missing")
            self.assertEqual(
                summary["latest_missing_conclusion_signals"],
                ["automation.data_quality_history", "automation.forecast_performance"],
            )
            self.assertEqual(summary["conclusion_signal_ready_count"], 0)
            self.assertEqual(summary["conclusion_signal_problem_count"], 2)
            self.assertEqual(
                summary["recurring_missing_conclusion_signals"],
                [{"signal": "automation.forecast_performance", "count": 2}],
            )
            self.assertEqual(
                summary["latest_missing_conclusion_signal_fixes"],
                {
                    "automation.data_quality_history": (
                        "rerun_self_analysis_and_weekly_conclusion: ensure latest_self_analysis_manifest.json "
                        "contains data_quality_history before show_weekly_conclusion.ps1"
                    ),
                    "automation.forecast_performance": (
                        "rerun_self_analysis_and_weekly_conclusion: ensure latest_self_analysis_manifest.json "
                        "contains forecast_performance before show_weekly_conclusion.ps1"
                    ),
                },
            )
            self.assertEqual(
                summary["recurring_missing_conclusion_signal_fixes"],
                [
                    {
                        "signal": "automation.forecast_performance",
                        "fix": (
                            "rerun_self_analysis_and_weekly_conclusion: ensure latest_self_analysis_manifest.json "
                            "contains forecast_performance before show_weekly_conclusion.ps1"
                        ),
                        "count": 2,
                    }
                ],
            )
            self.assertEqual(summary["recommended_action"], "review_recurring_delivery_issues")
            self.assertIn("# 每周最终交付历史摘要", report)
            self.assertIn("最近记录：3", report)
            self.assertIn("重复问题：missing_outputs (2)", report)
            self.assertIn("建议动作：review_recurring_delivery_issues", report)
            self.assertIn("raw_history_count: 3", report)
            self.assertIn("manual_review_pending:6 (2)", report)
            self.assertIn("每周人工处理清单：missing / 0", report)
            self.assertIn("missing (2)", report)
            self.assertIn("周结论关键信号：missing", report)
            self.assertIn("automation.forecast_performance (2)", report)
            self.assertIn("latest_self_analysis_manifest.json", report)
            self.assertIn("show_weekly_conclusion.ps1", report)

    def test_summary_uses_latest_record_per_as_of_date_for_trend_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "weekly_delivery_check_history.jsonl"
            write_history(
                history_path,
                [
                    {
                        "history_schema": "weekly_delivery_check_history",
                        "history_version": 1,
                        "delivery_check_schema": "weekly_delivery_check",
                        "as_of_date": "2026-06-21",
                        "status": "needs_attention",
                        "freshness_status": "fresh",
                        "attention_reasons": ["missing_outputs"],
                    },
                    {
                        "history_schema": "weekly_delivery_check_history",
                        "history_version": 1,
                        "delivery_check_schema": "weekly_delivery_check",
                        "as_of_date": "2026-06-28",
                        "status": "needs_attention",
                        "freshness_status": "fresh",
                        "attention_reasons": ["missing_outputs"],
                    },
                    {
                        "history_schema": "weekly_delivery_check_history",
                        "history_version": 1,
                        "delivery_check_schema": "weekly_delivery_check",
                        "as_of_date": "2026-06-28",
                        "status": "ready",
                        "freshness_status": "fresh",
                        "attention_reasons": [],
                    },
                ],
            )

            from weekly_delivery_history_report import summarize_weekly_delivery_history

            summary = summarize_weekly_delivery_history(history_path, window=8)

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
            history_path = root / "weekly_delivery_check_history.jsonl"
            output_path = root / "latest_weekly_delivery_history_summary.json"
            report_path = root / "latest_weekly_delivery_history_report.md"
            write_history(
                history_path,
                [
                    {
                        "history_schema": "weekly_delivery_check_history",
                        "history_version": 1,
                        "delivery_check_schema": "weekly_delivery_check",
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
                    str(PROJECT_ROOT / "weekly_delivery_history_report.py"),
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
            self.assertIn("每周最终交付历史摘要", output)
            payload = json.loads(output_path.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["history_summary_schema"], "weekly_delivery_history_summary")
            self.assertEqual(payload["latest_status"], "ready")
            self.assertEqual(payload["recommended_action"], "continue_monitoring")
            self.assertIn("建议动作：continue_monitoring", report_path.read_text(encoding="utf-8-sig"))

    def test_powershell_wrapper_static_contract(self):
        script = (PROJECT_ROOT / "scripts" / "show_weekly_delivery_history.ps1").read_text(encoding="utf-8-sig")

        self.assertIn("weekly_delivery_history_report.py", script)
        self.assertIn("weekly_delivery_check_history.jsonl", script)
        self.assertIn("latest_weekly_delivery_history_summary.json", script)
        self.assertIn("latest_weekly_delivery_history_report.md", script)
        self.assertIn("codex-primary-runtime", script)


if __name__ == "__main__":
    unittest.main()
