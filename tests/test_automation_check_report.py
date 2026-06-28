import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AutomationCheckReportTests(unittest.TestCase):
    def test_renders_one_screen_chinese_summary_from_check_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            check_path = Path(tmp) / "latest_automation_check.json"
            check_path.write_text(
                json.dumps(
                    {
                        "check_schema": "weekly_automation_check",
                        "check_version": 1,
                        "as_of_date": "2026-06-28",
                        "status": "manual_review_needed",
                        "recommended_action": "review_manual_queue",
                        "manifest_validation_status": "valid",
                        "market_count": 3,
                        "markets_ready_count": 3,
                        "candidate_count_total": 64,
                        "manual_review_queue_count": 12,
                        "manual_review_repeat_count": 0,
                        "weekly_ops_history_status": "manual_review_needed",
                        "priority_actions": ["review_manual_queue", "review_data_health"],
                        "market_candidate_counts": [
                            {"name": "美股周筛", "status": "ready", "candidate_count": "22"},
                            {"name": "A股周筛", "status": "ready", "candidate_count": "7"},
                            {"name": "港股周筛", "status": "ready", "candidate_count": "35"},
                        ],
                        "outputs": {
                            "self_analysis": "outputs/automation/latest_self_analysis.md",
                            "manual_review_queue": "outputs/automation/latest_manual_review_queue.csv",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8-sig",
            )

            from automation_check_report import render_automation_check

            report = render_automation_check(check_path)

            self.assertIn("每周自动化验收结论", report)
            self.assertIn("日期：2026-06-28", report)
            self.assertIn("状态：需要人工复核", report)
            self.assertIn("三市场：3/3 ready", report)
            self.assertIn("候选总数：64", report)
            self.assertIn("人工复核队列：12", report)
            self.assertIn("manifest 校验：valid", report)
            self.assertIn("美股周筛：ready，候选 22", report)
            self.assertIn("下一步：review_manual_queue", report)

            self.assertIn("weekly_ops_history_status: manual_review_needed", report)

    def test_cli_prints_report_from_check_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            check_path = Path(tmp) / "latest_automation_check.json"
            check_path.write_text(
                json.dumps(
                    {
                        "check_schema": "weekly_automation_check",
                        "check_version": 1,
                        "as_of_date": "2026-06-28",
                        "status": "clear",
                        "recommended_action": "monitor_next_run",
                        "manifest_validation_status": "valid",
                        "market_count": 3,
                        "markets_ready_count": 3,
                        "candidate_count_total": 5,
                        "manual_review_queue_count": 0,
                        "manual_review_repeat_count": 0,
                        "priority_actions": [],
                        "market_candidate_counts": [],
                        "outputs": {},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8-sig",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "automation_check_report.py"),
                    "--check",
                    str(check_path),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("每周自动化验收结论", completed.stdout)
            self.assertIn("状态：通过", completed.stdout)


if __name__ == "__main__":
    unittest.main()
