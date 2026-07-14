import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig")


def write_ready_delivery_files(root, as_of_date="2026-06-28"):
    write_text(
        Path(root) / "outputs" / "automation" / "latest_weekly_conclusion.md",
        "# 每周低估候选统一结论\n\n## 人工复核合并摘要\n",
    )
    write_text(
        Path(root) / "outputs" / "automation" / "manual_review_decisions_template.csv",
        "as_of_date,market,review_type,ticker,company,review_detail,decision_status,decision_note,reviewer,decided_at\n",
    )
    write_text(
        Path(root) / "outputs" / "automation" / "latest_weekly_action_items.md",
        "# 每周人工处理清单\n\n- 事项数量：7\n",
    )
    write_json(
        Path(root) / "outputs" / "automation" / "latest_weekly_action_items.json",
        {
            "action_items_schema": "weekly_action_items",
            "action_items_version": 1,
            "action_policy_version": 1,
            "as_of_date": as_of_date,
            "automation_status": "manual_review_needed",
            "item_count": 7,
            "items": [
                {
                    "priority": 1,
                    "status": "open",
                    "action_code": "review_manual_queue",
                    "category": "manual_review",
                    "title": "检查本周人工复核队列",
                    "source": "manual_review_queue_count:12",
                    "recommended_check": "按优先级处理 12 条复核项。",
                }
            ],
        },
    )
    write_json(
        Path(root) / "outputs" / "automation" / "latest_weekly_action_items.json",
        {
            "action_items_schema": "weekly_action_items",
            "action_items_version": 1,
            "action_policy_version": 1,
            "as_of_date": as_of_date,
            "automation_status": "manual_review_needed",
            "item_count": 7,
            "items": [
                {
                    "priority": index,
                    "status": "open",
                    "action_code": f"review_manual_queue_{index}",
                    "category": "manual_review",
                    "title": "review manual queue",
                    "source": "manual_review_queue_count:12",
                    "recommended_check": "review manual items",
                }
                for index in range(1, 8)
            ],
        },
    )
    write_json(
        Path(root) / "outputs" / "automation" / "latest_weekly_conclusion.json",
        {
            "conclusion_schema": "weekly_conclusion",
            "conclusion_version": 1,
            "action_policy_version": 1,
            "as_of_date": as_of_date,
            "status": "ready",
            "health": {
                "status": "needs_review",
                "score": 75,
                "reasons": ["automation_check:manual_review_needed", "manual_review_pending:12"],
            },
            "candidate_count_total": 64,
            "manual_review_queue": {"count": 12},
            "manual_review_decisions": {"pending_count": 12},
            "manual_review_merge_summary": {
                "path": "outputs/automation/latest_manual_review_decision_merge.json",
                "exists": False,
            },
            "automation": {
                "automation_check": {
                    "status": "manual_review_needed",
                    "path": "outputs/automation/latest_automation_check.json",
                },
                "data_quality": {
                    "status": "needs_review",
                    "score": 79.0,
                    "path": "outputs/automation/latest_automation_check.json",
                },
                "data_quality_history": {
                    "status": "collecting",
                    "path": "outputs/automation/latest_automation_check.json",
                },
                "forecast_performance": {
                    "status": "sample_accumulating",
                    "mature_evaluations": 0,
                    "direction_hit_rate": None,
                    "average_excess_return": None,
                    "next_one_week_evaluation_date": "2026-07-07",
                    "next_one_week_evaluation_count": 42,
                    "next_one_month_evaluation_date": "2026-07-28",
                    "next_one_month_evaluation_count": 42,
                    "path": "outputs/automation/latest_self_analysis_manifest.json",
                },
            },
            "outputs": {
                "markdown": "outputs/automation/latest_weekly_conclusion.md",
                "json": "outputs/automation/latest_weekly_conclusion.json",
                "manual_review_decisions_template": "outputs/automation/manual_review_decisions_template.csv",
            },
        },
    )
    conclusion_json_path = Path(root) / "outputs" / "automation" / "latest_weekly_conclusion.json"
    conclusion_markdown_path = Path(root) / "outputs" / "automation" / "latest_weekly_conclusion.md"
    if conclusion_json_path.exists() and conclusion_markdown_path.exists():
        json_mtime = conclusion_json_path.stat().st_mtime
        os.utime(conclusion_markdown_path, (json_mtime + 1, json_mtime + 1))


class WeeklyDeliveryCheckTests(unittest.TestCase):
    def test_delivery_check_propagates_current_action_policy_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root)

            from weekly_delivery_check import run_delivery_check

            result = run_delivery_check(root, today="2026-06-28")

            self.assertEqual(result["action_policy_version"], 1)
            self.assertEqual(result["status"], "ready")

    def test_delivery_check_rejects_missing_action_policy_versions(self):
        cases = (
            (
                "latest_weekly_conclusion.json",
                "weekly_conclusion_action_policy_version_missing",
            ),
            (
                "latest_weekly_action_items.json",
                "weekly_action_items_action_policy_version_missing",
            ),
        )
        for filename, reason in cases:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                write_ready_delivery_files(root)
                path = root / "outputs" / "automation" / filename
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
                del payload["action_policy_version"]
                write_json(path, payload)

                from weekly_delivery_check import run_delivery_check

                result = run_delivery_check(root, today="2026-06-28")

                self.assertEqual(result["status"], "needs_attention")
                self.assertIsNone(result["action_policy_version"])
                self.assertIn(reason, result["attention_reasons"])

    def test_delivery_check_rejects_noncurrent_conclusion_action_policy_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root)
            path = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            payload["action_policy_version"] = 0
            write_json(path, payload)

            from weekly_delivery_check import run_delivery_check

            result = run_delivery_check(root, today="2026-06-28")

            self.assertEqual(result["status"], "needs_attention")
            self.assertIsNone(result["action_policy_version"])
            self.assertIn(
                "weekly_conclusion_action_policy_version_mismatch",
                result["attention_reasons"],
            )
            self.assertIn("action_policy_version_inconsistent", result["attention_reasons"])

    def test_delivery_check_rejects_mixed_action_policy_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root)
            path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            payload["action_policy_version"] = 0
            write_json(path, payload)

            from weekly_delivery_check import run_delivery_check

            result = run_delivery_check(root, today="2026-06-28")

            self.assertEqual(result["status"], "needs_attention")
            self.assertIsNone(result["action_policy_version"])
            self.assertIn(
                "weekly_action_items_action_policy_version_mismatch",
                result["attention_reasons"],
            )
            self.assertIn("action_policy_version_inconsistent", result["attention_reasons"])

    def test_delivery_check_classifies_unparseable_action_policy_versions_as_mismatches(self):
        cases = (
            (
                "latest_weekly_conclusion.json",
                True,
                "weekly_conclusion_action_policy_version_mismatch",
                "weekly_conclusion_action_policy_version_missing",
            ),
            (
                "latest_weekly_action_items.json",
                "abc",
                "weekly_action_items_action_policy_version_mismatch",
                "weekly_action_items_action_policy_version_missing",
            ),
        )
        for filename, version, mismatch_reason, missing_reason in cases:
            with self.subTest(filename=filename, version=version), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                write_ready_delivery_files(root)
                path = root / "outputs" / "automation" / filename
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
                payload["action_policy_version"] = version
                write_json(path, payload)

                from weekly_delivery_check import run_delivery_check

                result = run_delivery_check(root, today="2026-06-28")

                self.assertEqual(result["status"], "needs_attention")
                self.assertIsNone(result["action_policy_version"])
                self.assertIn(mismatch_reason, result["attention_reasons"])
                self.assertNotIn(missing_reason, result["attention_reasons"])

    def test_delivery_check_reports_inconsistent_action_policy_contract_states(self):
        cases = (
            ("latest_weekly_conclusion.json", None),
            ("latest_weekly_action_items.json", "abc"),
        )
        for filename, version in cases:
            with self.subTest(filename=filename, version=version), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                write_ready_delivery_files(root)
                path = root / "outputs" / "automation" / filename
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
                if version is None:
                    del payload["action_policy_version"]
                else:
                    payload["action_policy_version"] = version
                write_json(path, payload)

                from weekly_delivery_check import run_delivery_check

                result = run_delivery_check(root, today="2026-06-28")

                self.assertEqual(result["status"], "needs_attention")
                self.assertIn("action_policy_version_inconsistent", result["attention_reasons"])

    def test_delivery_check_is_ready_when_final_outputs_exist_and_are_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root)

            from weekly_delivery_check import render_delivery_check, run_delivery_check

            result = run_delivery_check(root, today="2026-06-28", max_age_days=8)
            report = render_delivery_check(result)

            self.assertEqual(result["delivery_check_schema"], "weekly_delivery_check")
            self.assertEqual(result["delivery_check_version"], 1)
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["freshness_status"], "fresh")
            self.assertEqual(result["candidate_count_total"], 64)
            self.assertEqual(result["conclusion_health_status"], "needs_review")
            self.assertEqual(result["conclusion_health_score"], 75)
            self.assertEqual(result["action_items_status"], "ready")
            self.assertEqual(result["action_items_freshness_status"], "fresh")
            self.assertEqual(result["action_items_count"], 7)
            self.assertEqual(result["conclusion_signal_status"], "ready")
            self.assertEqual(result["missing_conclusion_signals"], [])
            self.assertEqual(result["forecast_next_one_week_evaluation_date"], "2026-07-07")
            self.assertEqual(result["forecast_next_one_week_evaluation_count"], 42)
            self.assertEqual(result["forecast_next_one_month_evaluation_date"], "2026-07-28")
            self.assertEqual(result["forecast_next_one_month_evaluation_count"], 42)
            self.assertEqual(
                result["conclusion_health_reasons"],
                ["automation_check:manual_review_needed", "manual_review_pending:12"],
            )
            self.assertEqual(result["manual_review_queue_count"], 12)
            self.assertEqual(result["manual_review_pending_count"], 12)
            self.assertEqual(result["missing_outputs"], [])
            self.assertIn("# 每周最终交付验收", report)
            self.assertIn("- 总体状态：ready", report)
            self.assertIn("needs_review / 75", report)
            self.assertIn("每周人工处理清单：ready / 7", report)
            self.assertIn("- 候选总数：64", report)

            self.assertIn("forecast_next_one_week_evaluation_date=2026-07-07", report)
            self.assertIn("forecast_next_one_week_evaluation_count=42", report)
            self.assertIn("forecast_next_one_month_evaluation_date=2026-07-28", report)
            self.assertIn("forecast_next_one_month_evaluation_count=42", report)

    def test_delivery_check_reports_external_input_blockers_from_conclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root)
            conclusion_path = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            conclusion = json.loads(conclusion_path.read_text(encoding="utf-8-sig"))
            conclusion["priority_input_gaps"] = [
                {
                    "action_code": "provide_official_constituents_csv",
                    "blocking_input": "inputs/sp500_current_membership/official_constituents.csv",
                    "blocking_reason": "official_constituents_csv_missing",
                    "next_action": "place_official_constituents_csv",
                    "official_export_url": (
                        "https://www.spglobal.com/spdji/en/idsexport/file.xls?"
                        "redesignExport=true&languageId=1&selectedModule=Constituents&"
                        "selectedSubModule=ConstituentsFullList&indexId=340"
                    ),
                    "dry_run_command": (
                        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                        "scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> "
                        "-DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv"
                    ),
                    "import_command": (
                        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                        "scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> "
                        "-SourceFileInbox inputs/sp500_current_membership/official_constituents.csv"
                    ),
                }
            ]
            write_json(conclusion_path, conclusion)

            from weekly_delivery_check import render_delivery_check, run_delivery_check

            result = run_delivery_check(root, today="2026-06-28", max_age_days=8)
            report = render_delivery_check(result)

            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["external_input_blocker_count"], 1)
            self.assertEqual(
                result["external_input_blockers"][0]["blocking_reason"],
                "official_constituents_csv_missing",
            )
            self.assertIn("official_export_url", result["external_input_blockers"][0])
            self.assertIn("spdji/en/idsexport/file.xls", result["external_input_blockers"][0]["official_export_url"])
            self.assertIn("official_constituents.csv", report)
            self.assertIn("official_export_url=https://www.spglobal.com/spdji/en/idsexport/file.xls", report)
            self.assertIn("place_official_constituents_csv", report)

    def test_delivery_check_needs_attention_when_conclusion_key_signals_are_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root)
            conclusion_path = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            conclusion = json.loads(conclusion_path.read_text(encoding="utf-8-sig"))
            conclusion["automation"].pop("data_quality_history")
            conclusion["automation"].pop("forecast_performance")
            write_json(conclusion_path, conclusion)

            from weekly_delivery_check import render_delivery_check, run_delivery_check

            result = run_delivery_check(root, today="2026-06-28", max_age_days=8)
            report = render_delivery_check(result)

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["conclusion_signal_status"], "missing")
            self.assertEqual(
                result["missing_conclusion_signals"],
                ["automation.data_quality_history", "automation.forecast_performance"],
            )
            self.assertEqual(
                result["missing_conclusion_signal_fixes"],
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
            self.assertIn("missing_conclusion_signals", result["attention_reasons"])
            self.assertIn("automation.data_quality_history", report)
            self.assertIn("automation.forecast_performance", report)
            self.assertIn("latest_self_analysis_manifest.json", report)
            self.assertIn("show_weekly_conclusion.ps1", report)

    def test_delivery_check_needs_attention_when_forecast_dates_are_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root)
            conclusion_path = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            conclusion = json.loads(conclusion_path.read_text(encoding="utf-8-sig"))
            forecast = conclusion["automation"]["forecast_performance"]
            forecast.pop("next_one_week_evaluation_date")
            forecast.pop("next_one_month_evaluation_date")
            write_json(conclusion_path, conclusion)

            from weekly_delivery_check import render_delivery_check, run_delivery_check

            result = run_delivery_check(root, today="2026-06-28", max_age_days=8)
            report = render_delivery_check(result)

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["conclusion_signal_status"], "missing")
            self.assertEqual(
                result["missing_conclusion_signals"],
                [
                    "automation.forecast_performance.next_one_week_evaluation_date",
                    "automation.forecast_performance.next_one_month_evaluation_date",
                ],
            )
            self.assertIn("missing_conclusion_signals", result["attention_reasons"])
            self.assertIn("next_one_week_evaluation_date", report)
            self.assertIn("next_one_month_evaluation_date", report)

    def test_delivery_check_needs_attention_when_conclusion_official_csv_detail_omits_blocking_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root)
            conclusion_path = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            conclusion = json.loads(conclusion_path.read_text(encoding="utf-8-sig"))
            conclusion["priority_actions"] = [
                "review_data_health",
                "continue_sample_accumulation",
                "provide_official_constituents_csv",
            ]
            conclusion["priority_action_details"] = [
                {"action": "review_data_health", "description": "review data health"},
                {"action": "continue_sample_accumulation", "description": "keep tracking"},
                {"action": "provide_official_constituents_csv", "description": "provide official S&P 500 CSV"},
            ]
            write_json(conclusion_path, conclusion)

            from weekly_delivery_check import run_delivery_check

            result = run_delivery_check(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_conclusion_official_csv_detail_missing_blocking_input",
                result["attention_reasons"],
            )

    def test_delivery_check_needs_attention_when_conclusion_health_needs_fix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root)
            conclusion_path = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            conclusion = json.loads(conclusion_path.read_text(encoding="utf-8-sig"))
            conclusion["health"] = {
                "status": "needs_fix",
                "score": 40,
                "reasons": ["missing_inputs:2"],
            }
            write_json(conclusion_path, conclusion)

            from weekly_delivery_check import render_delivery_check, run_delivery_check

            result = run_delivery_check(root, today="2026-06-28", max_age_days=8)
            report = render_delivery_check(result)

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["conclusion_health_status"], "needs_fix")
            self.assertEqual(result["conclusion_health_score"], 40)
            self.assertIn("conclusion_health_needs_fix", result["attention_reasons"])
            self.assertIn("needs_fix / 40", report)

    def test_delivery_check_needs_attention_when_required_final_output_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root)
            (root / "outputs" / "automation" / "manual_review_decisions_template.csv").unlink()

            from weekly_delivery_check import render_delivery_check, run_delivery_check

            result = run_delivery_check(root, today="2026-06-28", max_age_days=8)
            report = render_delivery_check(result)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("missing_outputs", result["attention_reasons"])
            self.assertEqual(result["missing_outputs"], ["manual_review_decisions_template"])
            self.assertIn("manual_review_decisions_template", report)

    def test_delivery_check_needs_attention_when_weekly_action_items_are_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root)
            (root / "outputs" / "automation" / "latest_weekly_action_items.json").unlink()
            (root / "outputs" / "automation" / "latest_weekly_action_items.md").unlink()

            from weekly_delivery_check import render_delivery_check, run_delivery_check

            result = run_delivery_check(root, today="2026-06-28", max_age_days=8)
            report = render_delivery_check(result)

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["action_items_status"], "missing")
            self.assertIn("missing_outputs", result["attention_reasons"])
            self.assertEqual(
                result["missing_outputs"],
                ["weekly_action_items_json", "weekly_action_items_markdown"],
            )
            self.assertIn("weekly_action_items_json", report)

    def test_delivery_check_needs_attention_when_weekly_action_items_are_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root, as_of_date="2026-06-10")
            conclusion_path = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            conclusion = json.loads(conclusion_path.read_text(encoding="utf-8-sig"))
            conclusion["as_of_date"] = "2026-06-28"
            write_json(conclusion_path, conclusion)

            from weekly_delivery_check import run_delivery_check

            result = run_delivery_check(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["action_items_status"], "stale")
            self.assertEqual(result["action_items_freshness_status"], "stale")
            self.assertIn("stale_action_items_date", result["attention_reasons"])

    def test_delivery_check_needs_attention_when_action_item_count_mismatches_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            action_items["item_count"] = 9
            write_json(action_items_path, action_items)

            from weekly_delivery_check import run_delivery_check

            result = run_delivery_check(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["action_items_status"], "needs_attention")
            self.assertEqual(result["action_items_count"], 9)
            self.assertEqual(result["action_items_actual_count"], 7)
            self.assertIn("weekly_action_items_count_mismatch", result["attention_reasons"])

    def test_delivery_check_needs_attention_when_conclusion_is_older_than_action_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root)
            conclusion_path = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            base_time = action_items_path.stat().st_mtime
            os.utime(conclusion_path, (base_time - 20, base_time - 20))
            os.utime(action_items_path, (base_time, base_time))

            from weekly_delivery_check import run_delivery_check

            result = run_delivery_check(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_conclusion_older_than_weekly_action_items",
                result["attention_reasons"],
            )

    def test_delivery_check_needs_attention_when_conclusion_markdown_is_older_than_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root)
            conclusion_json_path = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            conclusion_markdown_path = root / "outputs" / "automation" / "latest_weekly_conclusion.md"
            base_time = conclusion_json_path.stat().st_mtime
            os.utime(conclusion_markdown_path, (base_time - 20, base_time - 20))
            os.utime(conclusion_json_path, (base_time, base_time))

            from weekly_delivery_check import run_delivery_check

            result = run_delivery_check(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_conclusion_markdown_older_than_json",
                result["attention_reasons"],
            )

    def test_delivery_check_needs_attention_when_action_items_markdown_is_older_than_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root)
            action_items_json_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items_markdown_path = root / "outputs" / "automation" / "latest_weekly_action_items.md"
            base_time = action_items_json_path.stat().st_mtime
            os.utime(action_items_markdown_path, (base_time - 20, base_time - 20))
            os.utime(action_items_json_path, (base_time, base_time))

            from weekly_delivery_check import run_delivery_check

            result = run_delivery_check(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_action_items_markdown_older_than_json",
                result["attention_reasons"],
            )

    def test_delivery_check_needs_attention_when_conclusion_json_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root, as_of_date="2026-06-01")

            from weekly_delivery_check import run_delivery_check

            result = run_delivery_check(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["freshness_status"], "stale")
            self.assertIn("stale_conclusion_date", result["attention_reasons"])

    def test_cli_writes_delivery_check_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root)
            output = root / "outputs" / "automation" / "latest_weekly_delivery_check.json"
            history = root / "outputs" / "automation" / "weekly_delivery_check_history.jsonl"

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "weekly_delivery_check.py"),
                    "--project-root",
                    str(root),
                    "--today",
                    "2026-06-28",
                    "--output",
                    str(output),
                    "--history",
                    str(history),
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
            self.assertEqual(payload["delivery_check_schema"], "weekly_delivery_check")
            self.assertEqual(payload["status"], "ready")
            self.assertIn("每周最终交付验收", result.stdout)
            history_rows = [
                json.loads(line)
                for line in history.read_text(encoding="utf-8-sig").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(history_rows), 1)
            self.assertEqual(history_rows[0]["history_schema"], "weekly_delivery_check_history")
            self.assertEqual(history_rows[0]["history_version"], 1)
            self.assertEqual(history_rows[0]["delivery_check_schema"], "weekly_delivery_check")
            self.assertEqual(history_rows[0]["status"], "ready")

    def test_powershell_wrapper_static_contract(self):
        script = (PROJECT_ROOT / "scripts" / "run_weekly_delivery_check.ps1").read_text(encoding="utf-8-sig")

        self.assertIn("weekly_delivery_check.py", script)
        self.assertIn("latest_weekly_delivery_check.json", script)
        self.assertIn("weekly_delivery_check_history.jsonl", script)
        self.assertIn("--history", script)
        self.assertIn("-NoProfile -ExecutionPolicy Bypass", script)
        self.assertIn("codex-primary-runtime", script)


if __name__ == "__main__":
    unittest.main()
