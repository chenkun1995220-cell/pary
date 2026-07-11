import json
import tempfile
import unittest
from pathlib import Path


def write_automation(root, automation_id, name, prompt, minute, model="gpt-5.6-terra"):
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
                f'model = "{model}"',
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
                "scripts\\run_us_universe_weekly.ps1 本任务只完成美股周筛，不提前运行三市场统一收口；读取 market_quotes.csv",
                5,
            )
            write_automation(
                tmp,
                "a-300-3",
                "A股沪深300每周筛选",
                "scripts\\run_cn_weekly.ps1 本任务只完成A股周筛，不提前运行三市场统一收口",
                10,
            )
            write_automation(
                tmp,
                "automation-5",
                "港股大中盘每周筛选",
                "scripts\\run_hk_weekly.ps1 -RunPostChecks 调用 scripts\\run_weekly_reporting_bundle.ps1；读取 latest_weekly_artifact_consistency.json、latest_first_one_month_forecast_evaluation_review.json 和 latest_pre_submit_review.json；要求三市场同一自然日",
                30,
                model="gpt-5.6-sol",
            )

            from codex_automation_audit import audit_automations, render_audit_report

            result = audit_automations(tmp)
            report = render_audit_report(result)

            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["ready_count"], 3)
            self.assertEqual(result["automation_count"], 3)
            self.assertEqual(result["checks"][2]["id"], "automation-5")
            self.assertIn("Codex 自动化任务配置审计", report)
            self.assertIn("总体状态：ready", report)
            self.assertIn("automation-5：ready", report)
            self.assertIn("run_weekly_reporting_bundle.ps1", report)
            self.assertIn("latest_weekly_artifact_consistency.json", report)
            self.assertIn("latest_pre_submit_review.json", report)
            self.assertEqual(result["checks"][0]["model"], "gpt-5.6-terra")
            self.assertEqual(result["checks"][2]["model"], "gpt-5.6-sol")
            self.assertNotIn("三条任务使用当前支持的 gpt-5.6-terra", report)
            self.assertIn("模型版本允许升级或切换", report)

    def test_audit_requires_a_model_but_does_not_pin_its_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            for automation_id, name, prompt, minute in (
                ("automation", "美股低估公司每周筛选", "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口 market_quotes.csv", 5),
                ("a-300-3", "A股沪深300每周筛选", "scripts\\run_cn_weekly.ps1 不提前运行三市场统一收口", 10),
                ("automation-5", "港股大中盘每周筛选", "scripts\\run_hk_weekly.ps1 -RunPostChecks scripts\\run_weekly_reporting_bundle.ps1 latest_weekly_artifact_consistency.json latest_first_one_month_forecast_evaluation_review.json latest_pre_submit_review.json 同一自然日", 30),
            ):
                write_automation(tmp, automation_id, name, prompt, minute, model="future-compatible-model")

            from codex_automation_audit import audit_automations

            result = audit_automations(tmp)

            self.assertEqual(result["status"], "ready")

    def test_audit_reports_missing_bundle_and_consistency_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_automation(
                tmp,
                "automation",
                "美股低估公司每周筛选",
                "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口；读取 market_quotes.csv",
                5,
            )
            write_automation(
                tmp,
                "a-300-3",
                "A股沪深300每周筛选",
                "scripts\\run_cn_weekly.ps1 不提前运行三市场统一收口",
                10,
            )
            write_automation(
                tmp,
                "automation-5",
                "港股大中盘每周筛选",
                "scripts\\run_hk_weekly.ps1",
                15,
            )

            from codex_automation_audit import audit_automations, render_audit_report

            result = audit_automations(tmp)
            report = render_audit_report(result)

            self.assertEqual(result["status"], "needs_attention")
            self.assertTrue(
                any(
                    "-RunPostChecks" in issue
                    for issue in result["checks"][2]["issues"]
                )
            )
            self.assertIn("weekly_bundle_contract_missing", report)
            self.assertTrue(
                any(
                    "latest_weekly_artifact_consistency.json" in issue
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
            self.assertIn("a-300-3", result["missing_automations"])
            self.assertIn("automation-5", result["missing_automations"])
            self.assertIn("rrule", result["checks"][0]["issues"][0])
            self.assertTrue(any("不提前运行三市场统一收口" in issue for issue in result["checks"][0]["issues"]))

    def test_audit_allows_model_change_but_reports_premature_postchecks(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_automation(
                tmp,
                "automation",
                "美股标普500每周筛选",
                "scripts\\run_us_universe_weekly.ps1 -RunPostChecks 不提前运行三市场统一收口；读取 market_quotes.csv",
                5,
                model="gpt-5.5",
            )

            from codex_automation_audit import audit_automations

            result = audit_automations(tmp)
            issues = result["checks"][0]["issues"]

            self.assertFalse(any("model expected" in issue for issue in issues))
            self.assertTrue(any("must not run -RunPostChecks" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
