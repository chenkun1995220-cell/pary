import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_expected_automations(root, minute_overrides=None):
    from codex_automation_audit import EXPECTED_AUTOMATIONS

    minute_overrides = minute_overrides or {}
    for expected in EXPECTED_AUTOMATIONS:
        automation_id = expected["id"]
        minute = minute_overrides.get(automation_id, expected["minute"])
        path = Path(root) / automation_id / "automation.toml"
        path.parent.mkdir(parents=True, exist_ok=True)
        prompt = " ".join(expected["required_prompt_terms"])
        path.write_text(
            "\n".join(
                [
                    f"id = {json.dumps(automation_id, ensure_ascii=False)}",
                    'kind = "cron"',
                    f"name = {json.dumps(expected['name'], ensure_ascii=False)}",
                    f"prompt = {json.dumps(prompt, ensure_ascii=False)}",
                    'status = "ACTIVE"',
                    f'rrule = "FREQ=WEEKLY;INTERVAL=1;BYDAY=SU;BYHOUR=14;BYMINUTE={minute}"',
                    'model = "gpt-5.5"',
                    'reasoning_effort = "high"',
                    'execution_environment = "local"',
                    'cwds = ["F:\\\\chatgptssd\\\\project2"]',
                ]
            )
            + "\n",
            encoding="utf-8-sig",
        )


def write_weekly_check(root, outputs, as_of_date="2026-06-28"):
    check_path = Path(root) / "outputs" / "automation" / "latest_automation_check.json"
    check_path.parent.mkdir(parents=True, exist_ok=True)
    check_path.write_text(
        json.dumps(
            {
                "check_schema": "weekly_automation_check",
                "check_version": 1,
                "as_of_date": as_of_date,
                "status": "manual_review_needed",
                "recommended_action": "review_manual_queue",
                "manifest_validation_status": "valid",
                "market_count": 3,
                "markets_ready_count": 3,
                "candidate_count_total": 64,
                "manual_review_queue_count": 12,
                "manual_review_repeat_count": 2,
                "forecast_next_one_week_evaluation_date": "2026-07-07",
                "forecast_next_one_week_evaluation_count": 42,
                "forecast_next_one_month_evaluation_date": "2026-07-28",
                "forecast_next_one_month_evaluation_count": 42,
                "priority_actions": ["review_quote_gaps"],
                "outputs": outputs,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8-sig",
    )
    return check_path


class WeeklyOpsCheckTests(unittest.TestCase):
    def test_ops_check_is_ready_when_automations_and_weekly_outputs_are_valid(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as automation_tmp:
            root = Path(tmp)
            output_files = {
                "self_analysis": "outputs/automation/latest_self_analysis.md",
                "manifest": "outputs/automation/latest_self_analysis_manifest.json",
                "manual_review_queue": "outputs/automation/latest_manual_review_queue.csv",
                "automation_check": "outputs/automation/latest_automation_check.json",
            }
            for relative_path in output_files.values():
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("ok\n", encoding="utf-8-sig")
            check_path = write_weekly_check(root, output_files)
            write_expected_automations(automation_tmp)

            from weekly_ops_check import render_weekly_ops_check, run_weekly_ops_check

            result = run_weekly_ops_check(
                root,
                automation_tmp,
                check_path,
                today="2026-06-28",
                max_age_days=8,
            )
            report = render_weekly_ops_check(result)

            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["ops_check_schema"], "weekly_ops_check")
            self.assertEqual(result["ops_check_version"], 1)
            self.assertEqual(result["automation_audit_status"], "ready")
            self.assertEqual(result["automation_check_status"], "manual_review_needed")
            self.assertEqual(result["missing_outputs"], [])
            self.assertEqual(result["forecast_next_one_week_evaluation_date"], "2026-07-07")
            self.assertEqual(result["forecast_next_one_week_evaluation_count"], 42)
            self.assertEqual(result["forecast_next_one_month_evaluation_date"], "2026-07-28")
            self.assertEqual(result["forecast_next_one_month_evaluation_count"], 42)
            self.assertIn("# 周度运维总检查", report)
            self.assertIn("总体状态：ready", report)
            self.assertIn("自动任务配置：ready", report)
            self.assertIn("验收结论：manual_review_needed", report)
            self.assertIn("候选总数：64", report)
            self.assertIn("人工复核队列：12", report)

            self.assertIn("forecast_next_one_week_evaluation_date=2026-07-07", report)
            self.assertIn("forecast_next_one_week_evaluation_count=42", report)
            self.assertIn("forecast_next_one_month_evaluation_date=2026-07-28", report)
            self.assertIn("forecast_next_one_month_evaluation_count=42", report)

    def test_ops_check_reports_external_input_blockers_from_weekly_check(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as automation_tmp:
            root = Path(tmp)
            output_files = {
                "self_analysis": "outputs/automation/latest_self_analysis.md",
                "manifest": "outputs/automation/latest_self_analysis_manifest.json",
                "manual_review_queue": "outputs/automation/latest_manual_review_queue.csv",
                "automation_check": "outputs/automation/latest_automation_check.json",
            }
            for relative_path in output_files.values():
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("ok\n", encoding="utf-8-sig")
            check_path = write_weekly_check(root, output_files)
            check = json.loads(check_path.read_text(encoding="utf-8-sig"))
            check["external_input_blocker_count"] = 1
            check["external_input_blockers"] = [
                {
                    "action_code": "provide_official_constituents_csv",
                    "blocking_input": "inputs/sp500_current_membership/official_constituents.csv",
                    "blocking_reason": "official_constituents_csv_missing",
                    "next_action": "place_official_constituents_csv",
                }
            ]
            check_path.write_text(json.dumps(check, ensure_ascii=False, indent=2), encoding="utf-8-sig")
            write_expected_automations(automation_tmp)

            from weekly_ops_check import render_weekly_ops_check, run_weekly_ops_check

            result = run_weekly_ops_check(
                root,
                automation_tmp,
                check_path,
                today="2026-06-28",
                max_age_days=8,
            )
            report = render_weekly_ops_check(result)

            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["external_input_blocker_count"], 1)
            self.assertIn("provide_official_constituents_csv", report)
            self.assertIn("official_constituents.csv", report)
            self.assertIn("official_constituents_csv_missing", report)
            self.assertIn("place_official_constituents_csv", report)

    def test_ops_check_needs_attention_when_outputs_or_automations_drift(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as automation_tmp:
            root = Path(tmp)
            existing = root / "outputs" / "automation" / "latest_self_analysis.md"
            existing.parent.mkdir(parents=True, exist_ok=True)
            existing.write_text("ok\n", encoding="utf-8-sig")
            check_path = write_weekly_check(
                root,
                {
                    "self_analysis": "outputs/automation/latest_self_analysis.md",
                    "manifest": "outputs/automation/latest_self_analysis_manifest.json",
                    "manual_review_queue": "outputs/automation/latest_manual_review_queue.csv",
                    "automation_check": "outputs/automation/latest_automation_check.json",
                },
            )
            write_expected_automations(automation_tmp, minute_overrides={"automation": 6})

            from weekly_ops_check import render_weekly_ops_check, run_weekly_ops_check

            result = run_weekly_ops_check(
                root,
                automation_tmp,
                check_path,
                today="2026-06-28",
                max_age_days=8,
            )
            report = render_weekly_ops_check(result)

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["automation_audit_status"], "needs_attention")
            self.assertIn("manifest", result["missing_outputs"])
            self.assertIn("manual_review_queue", result["missing_outputs"])
            self.assertIn("缺失输出：manifest, manual_review_queue", report)

    def test_ops_check_needs_attention_when_weekly_check_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as automation_tmp:
            root = Path(tmp)
            output_files = {
                "self_analysis": "outputs/automation/latest_self_analysis.md",
                "manifest": "outputs/automation/latest_self_analysis_manifest.json",
                "manual_review_queue": "outputs/automation/latest_manual_review_queue.csv",
                "automation_check": "outputs/automation/latest_automation_check.json",
            }
            for relative_path in output_files.values():
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("ok\n", encoding="utf-8-sig")
            check_path = write_weekly_check(root, output_files, as_of_date="2026-06-28")
            write_expected_automations(automation_tmp)

            from weekly_ops_check import render_weekly_ops_check, run_weekly_ops_check

            result = run_weekly_ops_check(
                root,
                automation_tmp,
                check_path,
                today="2026-07-07",
                max_age_days=8,
            )
            report = render_weekly_ops_check(result)

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["freshness_status"], "stale")
            self.assertEqual(result["check_age_days"], 9)
            self.assertIn("stale_check_date", result["attention_reasons"])
            self.assertIn("验收日期新鲜度：stale", report)
            self.assertIn("验收文件过期", report)

    def test_ops_check_needs_attention_when_weekly_check_date_is_in_future(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as automation_tmp:
            root = Path(tmp)
            output_files = {
                "self_analysis": "outputs/automation/latest_self_analysis.md",
                "manifest": "outputs/automation/latest_self_analysis_manifest.json",
                "manual_review_queue": "outputs/automation/latest_manual_review_queue.csv",
                "automation_check": "outputs/automation/latest_automation_check.json",
            }
            for relative_path in output_files.values():
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("ok\n", encoding="utf-8-sig")
            check_path = write_weekly_check(root, output_files, as_of_date="2026-07-08")
            write_expected_automations(automation_tmp)

            from weekly_ops_check import render_weekly_ops_check, run_weekly_ops_check

            result = run_weekly_ops_check(
                root,
                automation_tmp,
                check_path,
                today="2026-07-07",
                max_age_days=8,
            )
            report = render_weekly_ops_check(result)

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["freshness_status"], "future")
            self.assertEqual(result["check_age_days"], -1)
            self.assertIn("future_check_date", result["attention_reasons"])
            self.assertIn("验收日期晚于当前日期", report)

    def test_cli_returns_zero_for_ready_ops_check(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as automation_tmp:
            root = Path(tmp)
            output_path = root / "outputs" / "automation" / "latest_weekly_ops_check.json"
            history_path = root / "outputs" / "automation" / "weekly_ops_check_history.jsonl"
            output_files = {
                "self_analysis": "outputs/automation/latest_self_analysis.md",
                "manifest": "outputs/automation/latest_self_analysis_manifest.json",
                "manual_review_queue": "outputs/automation/latest_manual_review_queue.csv",
                "automation_check": "outputs/automation/latest_automation_check.json",
            }
            for relative_path in output_files.values():
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("ok\n", encoding="utf-8-sig")
            check_path = write_weekly_check(root, output_files)
            write_expected_automations(automation_tmp)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "weekly_ops_check.py"),
                    "--project-root",
                    str(root),
                    "--automation-root",
                    str(automation_tmp),
                    "--check",
                    str(check_path),
                    "--today",
                    "2026-06-28",
                    "--max-age-days",
                    "8",
                    "--output",
                    str(output_path),
                    "--history",
                    str(history_path),
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
            self.assertIn("周度运维总检查", output)
            payload = json.loads(output_path.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["ops_check_schema"], "weekly_ops_check")
            self.assertEqual(payload["ops_check_version"], 1)
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["freshness_status"], "fresh")
            history = [
                json.loads(line)
                for line in history_path.read_text(encoding="utf-8-sig").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["history_schema"], "weekly_ops_check_history")
            self.assertEqual(history[0]["history_version"], 1)
            self.assertEqual(history[0]["ops_check_schema"], "weekly_ops_check")
            self.assertEqual(history[0]["status"], "ready")

            second = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "weekly_ops_check.py"),
                    "--project-root",
                    str(root),
                    "--automation-root",
                    str(automation_tmp),
                    "--check",
                    str(check_path),
                    "--today",
                    "2026-06-29",
                    "--max-age-days",
                    "8",
                    "--output",
                    str(output_path),
                    "--history",
                    str(history_path),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )
            second_output = second.stdout + second.stderr
            self.assertEqual(second.returncode, 0, second_output)
            history = [
                json.loads(line)
                for line in history_path.read_text(encoding="utf-8-sig").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(history), 2)
            self.assertEqual(history[1]["check_age_days"], 1)


if __name__ == "__main__":
    unittest.main()
