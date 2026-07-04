import json
import tempfile
import unittest
from pathlib import Path


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


class ModelHandoffReviewTests(unittest.TestCase):
    def test_builds_handoff_from_medium_term_goal_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(
                root / "outputs" / "automation" / "latest_medium_term_goal_review.json",
                {
                    "review_schema": "medium_term_goal_review",
                    "review_version": 1,
                    "as_of_date": "2026-07-01",
                    "strategy_code": "steady_delivery_evidence_first",
                    "strategy_title": "稳交付 + 补证据 + 等预测样本成熟",
                    "overall_completion_percent": 61,
                    "priority_next_actions": [
                        "continue_sample_accumulation",
                        "provide_official_constituents_csv_or_fix_network_permission",
                    ],
                    "automatic_multi_model_collaboration_enabled": False,
                    "collaboration_execution_mode": "single_codex_with_gpt55_review_checklist",
                    "collaboration_boundary_note": (
                        "当前未启用自动多模型协作；实际由单 Codex 执行并通过清单模拟复核。"
                    ),
                    "goals": [
                        {
                            "goal_code": "model_governance_handoff",
                            "module": "模型治理与多模型协作准备",
                            "completion_percent": 75,
                            "status": "on_track",
                            "next_action": "continue_governance_handoff",
                        }
                    ],
                },
            )

            from model_handoff_review import build_model_handoff_review, render_model_handoff_review

            result = build_model_handoff_review(
                root,
                today="2026-07-01",
                goal_code="model_governance_handoff",
                validation_commands=["python -m unittest discover -s tests"],
            )
            report = render_model_handoff_review(result)

            self.assertEqual(result["handoff_schema"], "model_handoff_review")
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["current_module"], "模型治理与多模型协作准备")
            self.assertEqual(result["module_completion_percent"], 75)
            self.assertEqual(result["medium_term_overall_completion_percent"], 61)
            self.assertEqual(result["current_target_total_completion_percent"], 61)
            self.assertEqual(
                result["development_priority_actions"],
                [
                    "continue_sample_accumulation",
                    "provide_official_constituents_csv_or_fix_network_permission",
                ],
            )
            self.assertFalse(result["automatic_multi_model_collaboration_enabled"])
            self.assertEqual(
                result["collaboration_execution_mode"],
                "single_codex_with_gpt55_review_checklist",
            )
            self.assertIn("gpt5.5", " ".join(result["gpt55_review_checklist"]))
            self.assertIn("development_priority_actions", report)
            self.assertIn("provide_official_constituents_csv_or_fix_network_permission", report)
            self.assertIn("未启用自动双模型协作", report)

    def test_defaults_to_medium_term_closeout_goal_when_goal_code_is_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(
                root / "outputs" / "automation" / "latest_medium_term_goal_review.json",
                {
                    "review_schema": "medium_term_goal_review",
                    "review_version": 1,
                    "as_of_date": "2026-07-02",
                    "strategy_code": "steady_delivery_evidence_first",
                    "strategy_title": "稳交付 + 补证据 + 等预测样本成熟",
                    "overall_completion_percent": 61,
                    "automatic_multi_model_collaboration_enabled": False,
                    "collaboration_execution_mode": "single_codex_with_gpt55_review_checklist",
                    "collaboration_boundary_note": "当前未启用自动多模型协作；实际由单 Codex 执行并通过清单模拟复核。",
                    "task_closeout_snapshot": {
                        "goal_code": "backtest_evidence_quality",
                        "current_module": "S&P 500 成分证据补强",
                        "module_completion_percent": 30,
                        "medium_term_overall_completion_percent": 61,
                    },
                    "goals": [
                        {
                            "goal_code": "model_governance_handoff",
                            "module": "模型治理与多模型协作准备",
                            "completion_percent": 75,
                            "status": "on_track",
                        },
                        {
                            "goal_code": "backtest_evidence_quality",
                            "module": "S&P 500 成分证据补强",
                            "completion_percent": 30,
                            "status": "needs_work",
                            "current": {
                                "sp500_current_source_inbox_external_input_required": True,
                                "sp500_current_source_inbox_blocking_reason": "official_constituents_csv_missing",
                                "sp500_current_source_inbox_blocking_input": (
                                    "inputs/sp500_current_membership/official_constituents.csv"
                                ),
                            },
                        },
                    ],
                },
            )
            write_json(
                root / "outputs" / "automation" / "latest_sp500_current_membership_sources.json",
                {
                    "source_schema": "sp500_current_membership_sources",
                    "source_version": 1,
                    "as_of_date": "2026-07-02",
                    "status": "fetch_failed",
                    "recommended_followup": "provide_official_constituents_csv",
                    "source_file_request_file": "outputs/automation/sp500_current_membership_source_file_request.md",
                    "source_file_inbox": "inputs/sp500_current_membership/official_constituents.csv",
                    "source_file_inbox_dry_run_command": (
                        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                        "scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> "
                        "-DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv"
                    ),
                    "source_file_inbox_next_command": (
                        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                        "scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> "
                        "-SourceFileInbox inputs/sp500_current_membership/official_constituents.csv"
                    ),
                    "source_file_acceptance_criteria": [
                        "has_symbol_or_ticker_column",
                        "at_least_400_tickers",
                        "official_spglobal_constituents_export",
                    ],
                    "fetch_error_type": "network_permission_denied",
                },
            )
            (
                root
                / "outputs"
                / "automation"
                / "sp500_current_membership_source_file_request.md"
            ).write_text(
                "# S&P 500 official constituents CSV request\n\n"
                "- request_manifest_schema: sp500_current_membership_source_file_request\n"
                "- request_manifest_version: 1\n"
                "- acceptance_criteria: has_symbol_or_ticker_column, at_least_400_tickers, official_spglobal_constituents_export\n"
                "- formal_backtest_upgrade_allowed: false\n"
                "- formal_model_change_allowed: false\n",
                encoding="utf-8-sig",
            )
            write_json(
                root / "outputs" / "automation" / "latest_forecast_performance_review.json",
                {
                    "review_schema": "forecast_performance_review",
                    "review_version": 1,
                    "as_of_date": "2026-07-02",
                    "status": "sample_accumulating",
                    "recommended_action": "continue_sample_accumulation",
                    "total_evaluations": 87,
                    "mature_evaluations": 0,
                    "one_week_mature": 0,
                    "one_month_mature": 0,
                    "prediction_unavailable": 87,
                    "latest_prediction_unavailable_count": 0,
                    "legacy_prediction_unavailable_count": 87,
                    "latest_short_signal_missing_count": 0,
                    "next_one_week_evaluation_date": "2026-07-07",
                    "next_one_month_evaluation_date": "2026-07-28",
                    "formal_model_change_allowed": False,
                },
            )

            from model_handoff_review import build_model_handoff_review, render_model_handoff_review

            result = build_model_handoff_review(root, today="2026-07-02")
            report = render_model_handoff_review(result)

            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["goal_code"], "backtest_evidence_quality")
            self.assertEqual(result["current_module"], "S&P 500 成分证据补强")
            self.assertEqual(result["module_completion_percent"], 30)
            self.assertEqual(result["medium_term_overall_completion_percent"], 61)
            self.assertEqual(result["current_target_total_completion_percent"], 61)
            self.assertTrue(result["sp500_current_source_inbox_external_input_required"])
            self.assertEqual(
                result["sp500_current_source_inbox_blocking_reason"],
                "official_constituents_csv_missing",
            )
            self.assertEqual(
                result["sp500_current_source_inbox_blocking_input"],
                "inputs/sp500_current_membership/official_constituents.csv",
            )
            self.assertEqual(
                result["sp500_current_source_request_file"],
                "outputs/automation/sp500_current_membership_source_file_request.md",
            )
            self.assertEqual(result["sp500_current_source_request_manifest_status"], "ready")
            self.assertIn(
                "-DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv",
                result["sp500_current_source_inbox_dry_run_command"],
            )
            self.assertIn(
                "-SourceFileInbox inputs/sp500_current_membership/official_constituents.csv",
                result["sp500_current_source_inbox_import_command"],
            )
            self.assertEqual(
                result["sp500_current_source_acceptance_criteria"],
                [
                    "has_symbol_or_ticker_column",
                    "at_least_400_tickers",
                    "official_spglobal_constituents_export",
                ],
            )
            self.assertEqual(result["forecast_performance_status"], "sample_accumulating")
            self.assertEqual(result["forecast_performance_recommended_action"], "continue_sample_accumulation")
            self.assertEqual(result["forecast_mature_evaluations"], 0)
            self.assertEqual(result["forecast_one_week_mature"], 0)
            self.assertEqual(result["forecast_one_month_mature"], 0)
            self.assertEqual(result["forecast_next_one_week_evaluation_date"], "2026-07-07")
            self.assertEqual(result["forecast_next_one_month_evaluation_date"], "2026-07-28")
            self.assertFalse(result["forecast_formal_model_change_allowed"])
            self.assertIn("sp500_current_source_inbox_external_input_required=True", report)
            self.assertIn(
                "sp500_current_source_inbox_blocking_reason=official_constituents_csv_missing",
                report,
            )
            self.assertIn(
                "sp500_current_source_request_manifest_status=ready",
                report,
            )
            self.assertIn(
                "sp500_current_membership_source_file_request.md",
                report,
            )
            self.assertIn("forecast_performance_status=sample_accumulating", report)
            self.assertIn("forecast_next_one_week_evaluation_date=2026-07-07", report)
            self.assertIn("forecast_next_one_month_evaluation_date=2026-07-28", report)

    def test_weekly_bundle_runs_handoff_before_pre_submit_review(self):
        project_root = Path(__file__).resolve().parents[1]
        bundle = (project_root / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )
        wrapper = (project_root / "scripts" / "run_model_handoff_review.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("run_model_handoff_review.ps1", bundle)
        self.assertLess(
            bundle.index("run_model_handoff_review.ps1"),
            bundle.index("run_pre_submit_review.ps1"),
        )
        self.assertIn("if ($GoalCode)", wrapper)

    def test_wrapper_records_default_validation_commands_when_not_provided(self):
        project_root = Path(__file__).resolve().parents[1]
        wrapper = (project_root / "scripts" / "run_model_handoff_review.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("$ValidationCommand.Count -eq 0", wrapper)
        self.assertIn("run_pre_submit_review.ps1 -MaxAgeDays 8", wrapper)
        self.assertIn("tests.test_model_handoff_review", wrapper)


if __name__ == "__main__":
    unittest.main()
