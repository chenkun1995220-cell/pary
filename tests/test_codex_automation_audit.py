import json
import tempfile
import unittest
from pathlib import Path


def write_automation(root, automation_id, name, prompt, minute):
    path = Path(root) / automation_id / "automation.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f"id = {json.dumps(automation_id, ensure_ascii=False)}",
                'kind = "cron"',
                f"name = {json.dumps(name, ensure_ascii=False)}",
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


class CodexAutomationAuditTests(unittest.TestCase):
    def test_audits_three_weekly_automations_as_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_automation(
                tmp,
                "automation",
                "美股低估公司每周筛选",
                "scripts\\run_us_universe_weekly.ps1 运行并产出 outputs\\automation\\latest_automation_check.json；不要运行或引用旧 latest_automation_check.json",
                5,
            )
            write_automation(
                tmp,
                "a-300-2",
                "A股沪深300每周筛选",
                "scripts\\run_cn_weekly.ps1 运行并产出 outputs\\automation\\latest_automation_check.json；不要运行或引用旧 latest_automation_check.json",
                10,
            )
            write_automation(
                tmp,
                "automation-4",
                "港股大中盘每周筛选",
                "scripts\\run_hk_weekly.ps1 scripts\\run_self_analysis.ps1 scripts\\show_automation_check.ps1 scripts\\run_weekly_ops_check.ps1 scripts\\show_weekly_ops_history.ps1 scripts\\show_weekly_conclusion.ps1 scripts\\run_weekly_delivery_check.ps1 scripts\\show_weekly_delivery_history.ps1 scripts\\run_pre_submit_review.ps1",
                15,
            )

            from codex_automation_audit import audit_automations, render_audit_report

            result = audit_automations(tmp)
            report = render_audit_report(result)

            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["ready_count"], 3)
            self.assertEqual(result["automation_count"], 3)
            self.assertEqual(result["checks"][2]["id"], "automation-4")
            self.assertIn("Codex 自动化任务配置审计", report)
            self.assertIn("总体状态：ready", report)
            self.assertIn("automation-4：ready", report)
            self.assertIn("show_automation_check.ps1", report)
            self.assertIn("run_weekly_ops_check.ps1", report)
            self.assertIn("show_weekly_ops_history.ps1", report)
            self.assertIn("show_weekly_conclusion.ps1", report)
            self.assertIn("run_weekly_delivery_check.ps1", report)
            self.assertIn("show_weekly_delivery_history.ps1", report)
            self.assertIn("run_pre_submit_review.ps1", report)

    def test_audit_reports_missing_weekly_conclusion_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_automation(
                tmp,
                "automation",
                "美股低估公司每周筛选",
                "scripts\\run_us_universe_weekly.ps1 运行并产出 outputs\\automation\\latest_automation_check.json",
                5,
            )
            write_automation(
                tmp,
                "a-300-2",
                "A股沪深300每周筛选",
                "scripts\\run_cn_weekly.ps1 运行并产出 outputs\\automation\\latest_automation_check.json",
                10,
            )
            write_automation(
                tmp,
                "automation-4",
                "港股大中盘每周筛选",
                "scripts\\run_hk_weekly.ps1 scripts\\run_self_analysis.ps1 scripts\\show_automation_check.ps1 scripts\\run_weekly_ops_check.ps1 scripts\\show_weekly_ops_history.ps1",
                15,
            )

            from codex_automation_audit import audit_automations, render_audit_report

            result = audit_automations(tmp)
            report = render_audit_report(result)

            self.assertEqual(result["status"], "needs_attention")
            self.assertTrue(
                any(
                    "scripts\\show_weekly_conclusion.ps1" in issue
                    for issue in result["checks"][2]["issues"]
                )
            )
            self.assertIn("weekly_conclusion_report_missing", report)
            self.assertTrue(
                any(
                    "scripts\\run_pre_submit_review.ps1" in issue
                    for issue in result["checks"][2]["issues"]
                )
            )

    def test_audit_reports_schedule_and_prompt_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_automation(
                tmp,
                "automation",
                "美股低估公司每周筛选",
                "scripts\\run_us_universe_weekly.ps1",
                6,
            )

            from codex_automation_audit import audit_automations

            result = audit_automations(tmp)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("a-300-2", result["missing_automations"])
            self.assertIn("automation-4", result["missing_automations"])
            self.assertIn("rrule", result["checks"][0]["issues"][0])
            self.assertTrue(any("latest_automation_check.json" in issue for issue in result["checks"][0]["issues"]))


if __name__ == "__main__":
    unittest.main()
