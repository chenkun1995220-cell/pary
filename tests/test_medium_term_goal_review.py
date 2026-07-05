import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def write_review_fixtures(root):
    automation = root / "outputs" / "automation"
    write_json(
        automation / "latest_pre_submit_review.json",
        {
            "as_of_date": "2026-06-29",
            "status": "ready",
            "governance_status": "ready",
            "candidate_count_total": 64,
        },
    )
    write_json(
        automation / "latest_automation_check.json",
        {
            "as_of_date": "2026-06-29",
            "status": "manual_review_needed",
            "market_count": 3,
            "markets_ready_count": 3,
            "candidate_count_total": 64,
            "data_quality_score": 79.0,
            "data_quality_status": "needs_review",
            "priority_actions": [
                "review_data_health",
                "review_backtest_evidence",
                "continue_sample_accumulation",
            ],
        },
    )
    write_json(
        automation / "latest_weekly_ops_check.json",
        {
            "as_of_date": "2026-06-29",
            "status": "ready",
            "markets_ready_count": 3,
            "market_count": 3,
            "candidate_count_total": 64,
        },
    )
    write_json(
        automation / "latest_weekly_action_items.json",
        {
            "action_items_schema": "weekly_action_items",
            "action_items_version": 1,
            "as_of_date": "2026-06-29",
            "item_count": 3,
            "backlog_reduction_plan": [
                {
                    "category": "delivery_health",
                    "count": 2,
                    "actions": [
                        "review_delivery_health_issues",
                        "reduce_weekly_action_backlog",
                    ],
                },
                {
                    "category": "data_quality",
                    "count": 1,
                    "actions": ["review_data_quality_score"],
                },
            ],
            "items": [
                {
                    "priority": 1,
                    "status": "open",
                    "action_code": "review_delivery_health_issues",
                    "category": "delivery_health",
                },
                {
                    "priority": 2,
                    "status": "open",
                    "action_code": "reduce_weekly_action_backlog",
                    "category": "delivery_health",
                },
                {
                    "priority": 3,
                    "status": "open",
                    "action_code": "review_data_quality_score",
                    "category": "data_quality",
                },
            ],
        },
    )
    write_json(
        automation / "latest_data_health_review.json",
        {
            "as_of_date": "2026-06-29",
            "status": "acceptable_with_monitoring",
            "blocked_candidate_count": 0,
            "refetch_gap_count": 2,
            "manual_financial_review_count": 72,
            "manual_financial_review_classified_count": 72,
            "manual_financial_review_unclassified_count": 0,
            "refetch_gap_attempted_count": 2,
            "refetch_gap_action_required_count": 0,
            "refetch_gap_unresolved_non_candidate_count": 2,
        },
    )
    write_json(
        automation / "latest_candidate_findings_review.json",
        {
            "as_of_date": "2026-06-28",
            "status": "manual_review_needed",
            "candidate_count": 64,
            "field_complete_count": 64,
            "missing_field_count": 0,
            "risk_coverage_count": 64,
            "risk_missing_count": 0,
            "risk_review_count": 33,
            "risk_classified_count": 33,
            "risk_unclassified_count": 0,
            "risk_action_required_count": 14,
            "risk_action_queue_count": 14,
            "risk_action_unqueued_count": 0,
            "risk_action_queue_by_action": {
                "defer_research": 8,
                "manual_fundamental_review": 6,
            },
            "formal_model_change_allowed": False,
        },
    )
    write_json(
        automation / "latest_forecast_performance_review.json",
        {
            "as_of_date": "2026-06-29",
            "status": "sample_accumulating",
            "total_evaluations": 65,
            "mature_evaluations": 0,
            "one_week_mature": 0,
            "one_month_mature": 0,
            "latest_short_signal_missing_count": 0,
            "latest_prediction_unavailable_count": 0,
            "legacy_prediction_unavailable_count": 65,
            "next_one_week_evaluation_date": "2026-07-06",
            "next_one_week_evaluation_count": 64,
            "next_one_month_evaluation_date": "2026-07-27",
            "next_one_month_evaluation_count": 64,
            "maturity_gap_reasons": {
                "prediction_unavailable": 65,
                "pending_maturity": 0,
                "other_not_evaluated": 0,
            },
            "formal_model_change_allowed": False,
        },
    )
    write_json(
        automation / "latest_backtest_evidence_review.json",
        {
            "as_of_date": "2026-06-28",
            "status": "evidence_review_needed",
            "weeks_completed": 8,
            "weeks_failed": 0,
            "verified_membership_ratio": 0.156,
            "weak_evidence_rows": 3382,
            "weak_evidence_weeks": 8,
            "membership_evidence_action_required_count": 425,
            "membership_evidence_action_queue_count": 50,
            "membership_evidence_action_unqueued_count": 375,
            "formal_model_upgrade_allowed": False,
        },
    )
    write_json(
        automation / "latest_membership_evidence_import_plan.json",
        {
            "review_schema": "membership_evidence_import_plan",
            "gap_count": 425,
            "queue_count": 50,
            "ready_to_import_count": 0,
            "missing_source_count": 50,
            "invalid_source_count": 0,
            "ready_to_import_weeks_affected": 0,
            "missing_source_weeks_affected": 7800,
            "invalid_source_weeks_affected": 0,
            "next_action": "provide_current_membership_sources",
            "formal_backtest_upgrade_allowed": False,
        },
    )
    write_json(
        automation / "latest_membership_evidence_apply_preview.json",
        {
            "preview_schema": "membership_evidence_apply_preview",
            "preview_version": 1,
            "status": "ready",
            "membership_row_count": 7800,
            "eligible_ticker_count": 2,
            "preview_row_count": 312,
            "preview_weeks_affected": 156,
            "invalid_source_ticker_count": 1,
            "already_verified_row_count": 24,
            "applied_to_historical_membership": False,
            "formal_backtest_upgrade_allowed": False,
        },
    )
    write_json(
        automation / "latest_sp500_current_membership_sources.json",
        {
            "source_schema": "sp500_current_membership_sources",
            "source_version": 1,
            "as_of_date": "2026-06-29",
            "status": "fetch_failed",
            "source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
            "requested_count": 50,
            "parsed_official_ticker_count": 0,
            "matched_count": 0,
            "missing_count": 50,
            "missing_ticker_review_queue": [
                {
                    "ticker": "ABT",
                    "review_status": "open",
                    "issue_type": "missing_from_official_current_source",
                },
                {
                    "ticker": "ADM",
                    "review_status": "open",
                    "issue_type": "missing_from_official_current_source",
                },
            ],
            "missing_ticker_review_queue_file": "outputs/automation/sp500_current_membership_source_review_queue.csv",
            "next_action": "retry_official_source_or_provide_official_constituents_csv",
            "source_file_required_columns": ["Symbol", "Ticker"],
            "source_file_request_file": str(
                automation / "sp500_current_membership_source_file_request.md"
            ),
            "source_file_inbox": "inputs/sp500_current_membership/official_constituents.csv",
            "source_file_inbox_exists": False,
            "source_file_validation_status": "missing",
            "source_file_inbox_dry_run_command": (
                "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                "scripts\\run_sp500_current_membership_sources.ps1 "
                "-ProjectRoot <project_root> -DryRun -SourceFileInbox "
                "inputs/sp500_current_membership/official_constituents.csv"
            ),
            "source_file_inbox_next_command": (
                "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                "scripts\\run_sp500_current_membership_sources.ps1 "
                "-ProjectRoot <project_root> -SourceFileInbox "
                "inputs/sp500_current_membership/official_constituents.csv"
            ),
            "fetch_error_type": "network_permission_denied",
            "fetch_retryable_without_environment_change": False,
            "fetch_error_next_action": "provide_official_constituents_csv_or_fix_network_permission",
            "intake_coverage_status": "partial",
            "intake_expected_count": 50,
            "intake_matched_count": 0,
            "intake_missing_count": 50,
            "recommended_followup": "run_membership_evidence_import_plan_then_apply_preview",
            "formal_backtest_upgrade_allowed": False,
        },
    )
    write_json(
        automation / "latest_sp500_current_membership_source_inbox_status.json",
        {
            "status_schema": "sp500_current_membership_source_inbox_status",
            "status_version": 1,
            "as_of_date": "2026-06-29",
            "status": "missing",
            "source_file_inbox": "inputs/sp500_current_membership/official_constituents.csv",
            "source_file_inbox_exists": False,
            "source_file_validation_status": "missing",
            "parsed_official_ticker_count": 0,
            "source_file_inbox_size_bytes": 12345,
            "source_file_inbox_sha256": "a" * 64,
            "source_file_inbox_modified_at": "2026-07-04T03:12:00+00:00",
            "minimum_official_ticker_count": 400,
            "intake_coverage_status": "none",
            "intake_expected_count": 50,
            "intake_matched_count": 0,
            "intake_missing_count": 50,
            "external_input_required": True,
            "blocking_reason": "official_constituents_csv_missing",
            "blocking_input": "inputs/sp500_current_membership/official_constituents.csv",
            "next_action": "place_official_constituents_csv",
            "formal_backtest_upgrade_allowed": False,
            "formal_model_change_allowed": False,
        },
    )
    (automation / "sp500_current_membership_source_file_request.md").write_text(
        "# S&P 500 official constituents CSV request\n",
        encoding="utf-8-sig",
    )
    write_json(
        automation / "latest_sp500_current_membership_source_review_status.json",
        {
            "review_status_schema": "sp500_current_membership_source_review_status",
            "review_status_version": 1,
            "as_of_date": "2026-06-29",
            "status": "review_needed",
            "queue_file": "outputs/automation/sp500_current_membership_source_review_queue.csv",
            "queue_exists": True,
            "queue_total_count": 2,
            "open_count": 2,
            "resolved_count": 0,
            "open_items": [
                {"ticker": "ABT", "review_status": "open"},
                {"ticker": "ADM", "review_status": "open"},
            ],
            "resolved_items": [],
            "next_action": "review_open_queue_items",
            "decision_file": "outputs/automation/sp500_current_membership_source_review_decisions.csv",
            "decision_file_exists": True,
            "review_decision_status": "partial",
            "manual_decision_next_step": "fill_decisions_template",
            "decision_total_count": 1,
            "decision_matched_open_count": 1,
            "decision_ready_to_apply_count": 0,
            "decision_pending_count": 1,
            "decision_pending_tickers": ["MISS"],
            "decision_ready_to_apply_tickers": [],
            "decision_invalid_count": 0,
            "decisions_template_exists": True,
            "decisions_template_status": "ready",
            "decisions_template_total_count": 2,
            "decisions_template_matched_open_count": 2,
            "decisions_template_missing_open_tickers": [],
            "decisions_template_extra_tickers": [],
            "decisions_template_missing_fields": [],
            "formal_backtest_upgrade_allowed": False,
        },
    )
    return automation


class MediumTermGoalReviewTests(unittest.TestCase):
    def test_secondary_current_membership_source_does_not_require_official_csv_blocker(self):
        from medium_term_goal_review import _requires_official_csv

        requires = _requires_official_csv(
            {"status": "secondary_ready", "source_trust_level": "secondary"},
            {
                "status": "missing",
                "external_input_required": True,
                "blocking_reason": "official_constituents_csv_missing",
            },
        )

        self.assertFalse(requires)

    def test_builds_medium_term_goal_dashboard_from_existing_reviews(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_review_fixtures(root)

            from medium_term_goal_review import (
                build_medium_term_goal_review,
                render_medium_term_goal_review,
            )

            payload = build_medium_term_goal_review(root)
            report = render_medium_term_goal_review(payload)

            self.assertEqual(payload["review_schema"], "medium_term_goal_review")
            self.assertEqual(payload["review_version"], 1)
            self.assertEqual(payload["as_of_date"], "2026-06-29")
            self.assertEqual(payload["period"], "8 weeks")
            self.assertEqual(payload["status"], "on_track_with_monitoring")
            self.assertEqual(payload["strategy_code"], "evidence_prediction_decision_maturity")
            self.assertEqual(payload["strategy_title"], "证据、预测与决策成熟化")
            self.assertEqual(payload["core_delivery_status"], "ready")
            self.assertEqual(payload["candidate_count_total"], 64)
            self.assertEqual(payload["markets_ready_count"], 3)
            self.assertEqual(payload["market_count"], 3)
            self.assertFalse(payload["formal_model_change_allowed"])
            self.assertFalse(payload["formal_model_upgrade_allowed"])
            self.assertFalse(payload["automatic_multi_model_collaboration_enabled"])
            self.assertEqual(
                payload["collaboration_execution_mode"],
                "single_codex_with_gpt55_review_checklist",
            )
            self.assertIn("未启用自动多模型协作", payload["collaboration_boundary_note"])
            self.assertTrue(payload["development_completion_policy"]["required_in_task_closeout"])
            self.assertEqual(
                payload["development_completion_policy"]["closeout_fields"],
                [
                    "current_module",
                    "module_completion_percent",
                    "medium_term_overall_completion_percent",
                    "current_target_total_completion_percent",
                ],
            )
            self.assertIn("overall_completion_percent", payload)
            self.assertEqual(
                payload["current_target_total_completion_percent"],
                payload["overall_completion_percent"],
            )
            self.assertGreater(payload["overall_completion_percent"], 0)

            goals = {item["goal_code"]: item for item in payload["goals"]}
            expected_targets = {
                "backtest_evidence_quality": 70,
                "forecast_tracking_maturity": 60,
                "data_quality_convergence": 85,
                "candidate_review_convergence": 85,
                "weekly_delivery_stability": 90,
                "model_governance_handoff": 85,
            }
            for goal_code, target_percent in expected_targets.items():
                self.assertEqual(
                    goals[goal_code]["target_completion_percent"],
                    target_percent,
                )
                self.assertEqual(
                    goals[goal_code]["completion_gap_percent"],
                    max(0, target_percent - goals[goal_code]["completion_percent"]),
                )
            self.assertEqual(goals["weekly_delivery_stability"]["status"], "on_track")
            self.assertEqual(goals["weekly_delivery_stability"]["module"], "每周自动交付稳定性")
            self.assertIn("completion_percent", goals["weekly_delivery_stability"])
            self.assertEqual(
                goals["weekly_delivery_stability"]["current"]["weekly_action_items_count"],
                3,
            )
            self.assertEqual(
                goals["weekly_delivery_stability"]["current"]["weekly_action_backlog_reduction_plan_status"],
                "ready",
            )
            self.assertEqual(
                goals["weekly_delivery_stability"]["current"]["weekly_action_backlog_reduction_plan_categories"],
                2,
            )
            self.assertEqual(
                goals["weekly_delivery_stability"]["current"]["weekly_delivery_history_ready_count"],
                0,
            )
            self.assertEqual(
                goals["weekly_delivery_stability"]["current"]["weekly_ops_history_ready_count"],
                0,
            )
            self.assertEqual(goals["data_quality_convergence"]["status"], "on_track")
            self.assertEqual(goals["candidate_review_convergence"]["status"], "on_track")
            self.assertEqual(goals["candidate_review_convergence"]["completion_percent"], 85)
            self.assertEqual(
                goals["candidate_review_convergence"]["current"]["risk_action_queue_by_action"],
                {"defer_research": 8, "manual_fundamental_review": 6},
            )
            self.assertEqual(goals["forecast_tracking_maturity"]["status"], "sample_accumulating")
            self.assertEqual(
                goals["forecast_tracking_maturity"]["current"]["maturity_gap_prediction_unavailable"],
                65,
            )
            self.assertEqual(
                goals["forecast_tracking_maturity"]["current"]["maturity_gap_pending_maturity"],
                0,
            )
            self.assertEqual(
                goals["forecast_tracking_maturity"]["current"]["next_one_week_evaluation_date"],
                "2026-07-06",
            )
            self.assertEqual(
                goals["forecast_tracking_maturity"]["current"]["next_one_week_evaluation_count"],
                64,
            )
            self.assertEqual(
                goals["forecast_tracking_maturity"]["current"]["next_one_month_evaluation_date"],
                "2026-07-27",
            )
            self.assertEqual(
                goals["forecast_tracking_maturity"]["current"]["next_one_month_evaluation_count"],
                64,
            )
            self.assertEqual(
                goals["forecast_tracking_maturity"]["next_action"],
                "continue_sample_accumulation",
            )
            self.assertEqual(goals["backtest_evidence_quality"]["status"], "needs_work")
            self.assertLess(
                goals["backtest_evidence_quality"]["completion_percent"],
                goals["weekly_delivery_stability"]["completion_percent"],
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["membership_evidence_action_queue_count"],
                50,
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["membership_evidence_action_unqueued_count"],
                375,
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["membership_evidence_ready_to_import_count"],
                0,
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["membership_evidence_missing_source_count"],
                50,
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["membership_evidence_ready_to_import_weeks_affected"],
                0,
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["membership_evidence_missing_source_weeks_affected"],
                7800,
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["membership_evidence_preview_row_count"],
                312,
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["membership_evidence_preview_weeks_affected"],
                156,
            )
            self.assertFalse(
                goals["backtest_evidence_quality"]["current"]["membership_evidence_preview_applied"]
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_status"],
                "fetch_failed",
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_next_action"],
                "retry_official_source_or_provide_official_constituents_csv",
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_matched_count"],
                0,
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_missing_ticker_review_queue_count"],
                2,
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_review_queue_file"],
                "outputs/automation/sp500_current_membership_source_review_queue.csv",
            )
            self.assertTrue(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_file_request_exists"]
            )
            self.assertTrue(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_file_request_file"].endswith(
                    "sp500_current_membership_source_file_request.md"
                )
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_file_inbox"],
                "inputs/sp500_current_membership/official_constituents.csv",
            )
            self.assertFalse(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_file_inbox_exists"]
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_file_validation_status"],
                "missing",
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_fetch_error_type"],
                "network_permission_denied",
            )
            self.assertFalse(
                goals["backtest_evidence_quality"]["current"][
                    "sp500_current_source_fetch_retryable_without_environment_change"
                ]
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_fetch_error_next_action"],
                "provide_official_constituents_csv_or_fix_network_permission",
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_inbox_status"],
                "missing",
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_inbox_next_action"],
                "place_official_constituents_csv",
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_inbox_validation_status"],
                "missing",
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_inbox_parsed_official_ticker_count"],
                0,
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_inbox_intake_missing_count"],
                50,
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"][
                    "sp500_current_source_inbox_size_bytes"
                ],
                12345,
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"][
                    "sp500_current_source_inbox_sha256"
                ],
                "a" * 64,
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"][
                    "sp500_current_source_inbox_modified_at"
                ],
                "2026-07-04T03:12:00+00:00",
            )
            self.assertTrue(
                goals["backtest_evidence_quality"]["current"][
                    "sp500_current_source_inbox_external_input_required"
                ]
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"][
                    "sp500_current_source_inbox_blocking_reason"
                ],
                "official_constituents_csv_missing",
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"][
                    "sp500_current_source_inbox_blocking_input"
                ],
                "inputs/sp500_current_membership/official_constituents.csv",
            )
            self.assertIn(
                "-DryRun -SourceFileInbox",
                goals["backtest_evidence_quality"]["current"].get(
                    "sp500_current_source_inbox_dry_run_command",
                    "",
                ),
            )
            self.assertIn(
                "-SourceFileInbox",
                goals["backtest_evidence_quality"]["current"].get(
                    "sp500_current_source_inbox_import_command",
                    "",
                ),
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_review_queue_open_count"],
                2,
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_review_queue_resolved_count"],
                0,
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_review_status"],
                "review_needed",
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_review_status_open_count"],
                2,
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_review_status_resolved_count"],
                0,
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_review_status_next_action"],
                "review_open_queue_items",
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_review_decision_status"],
                "partial",
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_review_manual_decision_next_step"],
                "fill_decisions_template",
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_review_decision_pending_tickers"],
                ["MISS"],
            )
            self.assertTrue(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_review_decision_file_exists"]
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_review_decision_ready_to_apply_count"],
                0,
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_review_decisions_template_status"],
                "ready",
            )
            self.assertTrue(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_review_decisions_template_exists"]
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_review_decisions_template_matched_open_count"],
                2,
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_review_decisions_template_missing_open_count"],
                0,
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_intake_coverage_status"],
                "partial",
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_intake_missing_count"],
                50,
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["sp500_current_source_recommended_followup"],
                "run_membership_evidence_import_plan_then_apply_preview",
            )
            self.assertEqual(
                goals["backtest_evidence_quality"]["current"]["membership_evidence_import_next_action"],
                "provide_current_membership_sources",
            )
            self.assertEqual(goals["model_governance_handoff"]["status"], "on_track")
            self.assertEqual(goals["model_governance_handoff"]["completion_percent"], 85)
            self.assertEqual(
                goals["model_governance_handoff"]["title"],
                "建立多模型协作治理准备",
            )
            self.assertFalse(
                goals["model_governance_handoff"]["current"]["automatic_multi_model_collaboration_enabled"]
            )
            self.assertEqual(
                goals["model_governance_handoff"]["current"]["governance_mode"],
                "single_codex_with_gpt55_review_checklist",
            )
            self.assertIn(
                "当前不是自动双模型协作",
                goals["model_governance_handoff"]["current"]["collaboration_boundary_note"],
            )
            self.assertEqual(
                payload["task_closeout_snapshot"]["current_module"],
                "S&P 500 成分证据补强",
            )
            self.assertEqual(
                payload["task_closeout_snapshot"]["goal_code"],
                "backtest_evidence_quality",
            )
            self.assertEqual(
                payload["task_closeout_snapshot"]["module_completion_percent"],
                goals["backtest_evidence_quality"]["completion_percent"],
            )
            self.assertEqual(
                payload["task_closeout_snapshot"]["medium_term_overall_completion_percent"],
                payload["overall_completion_percent"],
            )
            self.assertEqual(
                payload["task_closeout_snapshot"]["current_target_total_completion_percent"],
                payload["overall_completion_percent"],
            )

            self.assertEqual(
                payload["priority_next_actions"][0],
                "provide_official_constituents_csv_or_fix_network_permission",
            )
            self.assertIn("continue_sample_accumulation", payload["priority_next_actions"])
            self.assertNotIn("review_prediction_unavailable_signals", payload["priority_next_actions"])

            self.assertIn("中期目标进度看板", report)
            self.assertIn("8 weeks", report)
            self.assertIn("证据、预测与决策成熟化", report)
            self.assertIn("当前开发收尾摘要", report)
            self.assertIn("current_module=S&P 500 成分证据补强", report)
            self.assertIn("current_target_total_completion_percent=", report)
            self.assertIn("正式模型变更：不允许", report)
            self.assertIn("backtest_evidence_quality", report)
            self.assertIn("sp500_current_source_inbox_size_bytes=12345", report)
            self.assertIn("sp500_current_source_inbox_sha256=" + "a" * 64, report)
            self.assertIn(
                "sp500_current_source_inbox_modified_at=2026-07-04T03:12:00+00:00",
                report,
            )
            self.assertIn("sp500_current_source_inbox_external_input_required=True", report)

    def test_closeout_snapshot_can_select_goal_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_review_fixtures(root)

            from medium_term_goal_review import build_medium_term_goal_review, render_medium_term_goal_review

            payload = build_medium_term_goal_review(
                root,
                closeout_goal_code="candidate_review_convergence",
            )
            report = render_medium_term_goal_review(payload)

            snapshot = payload["task_closeout_snapshot"]
            goals = {item["goal_code"]: item for item in payload["goals"]}
            self.assertEqual(snapshot["goal_code"], "candidate_review_convergence")
            self.assertEqual(
                snapshot["current_module"],
                goals["candidate_review_convergence"]["module"],
            )
            self.assertEqual(snapshot["module_completion_percent"], 85)
            self.assertEqual(
                snapshot["medium_term_overall_completion_percent"],
                payload["overall_completion_percent"],
            )
            self.assertIn(
                "sp500_current_source_inbox_blocking_reason=official_constituents_csv_missing",
                report,
            )
            self.assertNotIn("review_prediction_unavailable_signals", report)
            self.assertIn("weekly_action_backlog_reduction_plan_status=ready", report)

    def test_weekly_delivery_reaches_target_with_four_ready_history_weeks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            automation = write_review_fixtures(root)
            write_json(
                automation / "latest_weekly_delivery_history_summary.json",
                {
                    "history_summary_schema": "weekly_delivery_history_summary",
                    "history_count": 4,
                    "window_size": 4,
                    "ready_count": 4,
                    "needs_attention_count": 0,
                    "stale_count": 0,
                    "recommended_action": "continue_monitoring",
                    "latest_status": "ready",
                    "latest_freshness_status": "fresh",
                    "action_items_ready_count": 4,
                    "action_items_problem_count": 0,
                    "conclusion_signal_ready_count": 4,
                    "conclusion_signal_problem_count": 0,
                },
            )
            write_json(
                automation / "latest_weekly_ops_history_summary.json",
                {
                    "history_summary_schema": "weekly_ops_history_summary",
                    "history_count": 4,
                    "window_size": 4,
                    "ready_count": 4,
                    "needs_attention_count": 0,
                    "stale_count": 0,
                    "recommended_action": "continue_monitoring",
                    "latest_status": "ready",
                    "latest_freshness_status": "fresh",
                },
            )

            from medium_term_goal_review import build_medium_term_goal_review

            payload = build_medium_term_goal_review(root)
            goals = {item["goal_code"]: item for item in payload["goals"]}
            current = goals["weekly_delivery_stability"]["current"]

            self.assertEqual(goals["weekly_delivery_stability"]["completion_percent"], 90)
            self.assertEqual(goals["weekly_delivery_stability"]["completion_gap_percent"], 0)
            self.assertEqual(current["weekly_delivery_history_ready_count"], 4)
            self.assertEqual(current["weekly_delivery_history_window_size"], 4)
            self.assertEqual(current["weekly_ops_history_ready_count"], 4)
            self.assertEqual(current["weekly_ops_history_window_size"], 4)

    def test_ignores_refreshable_pre_submit_closeout_mismatch_for_core_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            automation = write_review_fixtures(root)
            write_json(
                automation / "latest_pre_submit_review.json",
                {
                    "as_of_date": "2026-07-05",
                    "status": "needs_attention",
                    "governance_status": "ready",
                    "candidate_count_total": 64,
                    "attention_reasons": ["model_handoff_review_closeout_mismatch"],
                },
            )

            from medium_term_goal_review import build_medium_term_goal_review

            payload = build_medium_term_goal_review(
                root,
                closeout_goal_code="candidate_review_convergence",
            )
            goals = {item["goal_code"]: item for item in payload["goals"]}

            self.assertEqual(payload["core_delivery_status"], "ready")
            self.assertEqual(goals["weekly_delivery_stability"]["status"], "on_track")
            self.assertEqual(
                goals["weekly_delivery_stability"]["current"]["pre_submit_status"],
                "ready_refresh_required",
            )
            self.assertEqual(goals["model_governance_handoff"]["completion_percent"], 85)

    def test_data_quality_reaches_target_when_refetch_is_clear_and_manual_reviews_classified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            automation = write_review_fixtures(root)
            review_path = automation / "latest_data_health_review.json"
            review = json.loads(review_path.read_text(encoding="utf-8-sig"))
            review.update(
                {
                    "refetch_gap_count": 0,
                    "refetch_gap_attempted_count": 0,
                    "refetch_gap_action_required_count": 0,
                    "refetch_gap_unresolved_non_candidate_count": 1,
                    "manual_financial_review_count": 73,
                    "active_manual_financial_review_count": 0,
                    "closed_manual_financial_review_count": 73,
                    "candidate_manual_financial_review_count": 0,
                    "manual_financial_review_classified_count": 73,
                    "manual_financial_review_unclassified_count": 0,
                    "candidate_manual_financial_review_unclassified_count": 0,
                }
            )
            write_json(review_path, review)

            from medium_term_goal_review import build_medium_term_goal_review

            payload = build_medium_term_goal_review(
                root,
                closeout_goal_code="data_quality_convergence",
            )
            goals = {item["goal_code"]: item for item in payload["goals"]}

            self.assertEqual(goals["data_quality_convergence"]["status"], "on_track")
            self.assertEqual(goals["data_quality_convergence"]["completion_percent"], 85)
            self.assertEqual(goals["data_quality_convergence"]["completion_gap_percent"], 0)
            self.assertEqual(
                goals["data_quality_convergence"]["current"]["candidate_manual_financial_review_count"],
                0,
            )
            self.assertEqual(
                goals["data_quality_convergence"]["current"]["active_manual_financial_review_count"],
                0,
            )
            self.assertEqual(
                goals["data_quality_convergence"]["current"]["closed_manual_financial_review_count"],
                73,
            )
            self.assertEqual(
                goals["data_quality_convergence"]["current"][
                    "candidate_manual_financial_review_unclassified_count"
                ],
                0,
            )

    def test_dashboard_blocks_when_core_delivery_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            automation = write_review_fixtures(root)
            write_json(
                automation / "latest_pre_submit_review.json",
                {
                    "as_of_date": "2026-06-29",
                    "status": "blocked",
                    "governance_status": "ready",
                    "candidate_count_total": 64,
                },
            )

            from medium_term_goal_review import build_medium_term_goal_review

            payload = build_medium_term_goal_review(root)

            self.assertEqual(payload["status"], "blocked")
            self.assertEqual(payload["core_delivery_status"], "blocked")
            self.assertIn("restore_weekly_delivery_ready_state", payload["priority_next_actions"])

    def test_dashboard_prioritizes_latest_prediction_unavailable_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            automation = write_review_fixtures(root)
            forecast_path = automation / "latest_forecast_performance_review.json"
            forecast = json.loads(forecast_path.read_text(encoding="utf-8-sig"))
            forecast["latest_prediction_unavailable_count"] = 12
            forecast["legacy_prediction_unavailable_count"] = 0
            forecast["maturity_gap_reasons"]["prediction_unavailable"] = 12
            write_json(forecast_path, forecast)

            from medium_term_goal_review import build_medium_term_goal_review

            payload = build_medium_term_goal_review(root)
            goals = {item["goal_code"]: item for item in payload["goals"]}

            self.assertEqual(
                goals["forecast_tracking_maturity"]["next_action"],
                "review_prediction_unavailable_signals",
            )
            self.assertIn("review_prediction_unavailable_signals", payload["priority_next_actions"])

    def test_dashboard_needs_work_when_backlog_reduction_plan_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            automation = write_review_fixtures(root)
            action_items_path = automation / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            action_items["backlog_reduction_plan"] = []
            write_json(action_items_path, action_items)

            from medium_term_goal_review import build_medium_term_goal_review

            payload = build_medium_term_goal_review(root)
            goals = {item["goal_code"]: item for item in payload["goals"]}

            self.assertEqual(payload["core_delivery_status"], "ready")
            self.assertEqual(goals["weekly_delivery_stability"]["status"], "needs_work")
            self.assertEqual(
                goals["weekly_delivery_stability"]["current"]["weekly_action_backlog_reduction_plan_status"],
                "missing",
            )
            self.assertEqual(
                goals["weekly_delivery_stability"]["next_action"],
                "review_weekly_action_backlog_reduction_plan",
            )
            self.assertIn(
                "review_weekly_action_backlog_reduction_plan",
                payload["priority_next_actions"],
            )

    def test_dashboard_prioritizes_apply_preview_when_membership_sources_are_ready_to_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            automation = write_review_fixtures(root)
            plan_path = automation / "latest_membership_evidence_import_plan.json"
            plan = json.loads(plan_path.read_text(encoding="utf-8-sig"))
            plan["ready_to_import_count"] = 2
            plan["missing_source_count"] = 48
            plan["ready_to_import_weeks_affected"] = 312
            plan["next_action"] = "run_membership_evidence_apply_preview"
            write_json(plan_path, plan)

            from medium_term_goal_review import build_medium_term_goal_review

            payload = build_medium_term_goal_review(root)
            goals = {item["goal_code"]: item for item in payload["goals"]}

            self.assertEqual(
                goals["backtest_evidence_quality"]["next_action"],
                "run_membership_evidence_apply_preview",
            )
            self.assertIn("run_membership_evidence_apply_preview", payload["priority_next_actions"])

    def test_dashboard_prioritizes_import_plan_when_current_source_has_followup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            automation = write_review_fixtures(root)
            source_path = automation / "latest_sp500_current_membership_sources.json"
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            source["status"] = "ready"
            source["intake_coverage_status"] = "partial"
            source["matched_count"] = 2
            source["missing_count"] = 48
            source["recommended_followup"] = "run_membership_evidence_import_plan_then_apply_preview"
            write_json(source_path, source)

            from medium_term_goal_review import build_medium_term_goal_review

            payload = build_medium_term_goal_review(root)
            goals = {item["goal_code"]: item for item in payload["goals"]}

            self.assertEqual(
                goals["backtest_evidence_quality"]["next_action"],
                "run_membership_evidence_import_plan_then_apply_preview",
            )
            self.assertIn(
                "run_membership_evidence_import_plan_then_apply_preview",
                payload["priority_next_actions"],
            )

    def test_dashboard_prioritizes_current_source_review_when_source_has_missing_tickers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            automation = write_review_fixtures(root)
            source_path = automation / "latest_sp500_current_membership_sources.json"
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            source["status"] = "ready"
            source["matched_count"] = 1
            source["missing_count"] = 1
            source["next_action"] = "review_missing_tickers"
            source["recommended_followup"] = "review_current_membership_source_status"
            write_json(source_path, source)

            from medium_term_goal_review import build_medium_term_goal_review

            payload = build_medium_term_goal_review(root)
            goals = {item["goal_code"]: item for item in payload["goals"]}

            self.assertEqual(
                goals["backtest_evidence_quality"]["next_action"],
                "review_current_membership_source_status",
            )
            self.assertIn(
                "review_current_membership_source_status",
                payload["priority_next_actions"],
            )

    def test_dashboard_prioritizes_official_csv_when_current_source_fetch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            automation = write_review_fixtures(root)
            source_path = automation / "latest_sp500_current_membership_sources.json"
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            source["status"] = "fetch_failed"
            source["matched_count"] = 0
            source["missing_count"] = 50
            source["next_action"] = "retry_official_source_or_provide_official_constituents_csv"
            source["recommended_followup"] = "provide_official_constituents_csv"
            source["source_file_required_columns"] = ["Symbol", "Ticker"]
            source["fetch_error_type"] = "network_permission_denied"
            source["fetch_retryable_without_environment_change"] = False
            source["fetch_error_next_action"] = "provide_official_constituents_csv_or_fix_network_permission"
            write_json(source_path, source)

            from medium_term_goal_review import build_medium_term_goal_review

            payload = build_medium_term_goal_review(root)
            goals = {item["goal_code"]: item for item in payload["goals"]}

            self.assertEqual(
                goals["backtest_evidence_quality"]["next_action"],
                "provide_official_constituents_csv_or_fix_network_permission",
            )
            self.assertIn(
                "provide_official_constituents_csv_or_fix_network_permission",
                payload["priority_next_actions"],
            )
            self.assertEqual(
                payload["priority_next_actions"][0],
                "provide_official_constituents_csv_or_fix_network_permission",
            )

    def test_dashboard_does_not_skip_missing_official_csv_for_import_followup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            automation = write_review_fixtures(root)
            source_path = automation / "latest_sp500_current_membership_sources.json"
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            source["status"] = "fetch_failed"
            source["matched_count"] = 0
            source["missing_count"] = 50
            source["recommended_followup"] = "run_membership_evidence_import_plan_then_apply_preview"
            source["fetch_error_next_action"] = "provide_official_constituents_csv_or_fix_network_permission"
            write_json(source_path, source)

            inbox_path = automation / "latest_sp500_current_membership_source_inbox_status.json"
            inbox = json.loads(inbox_path.read_text(encoding="utf-8-sig"))
            inbox["status"] = "missing"
            inbox["external_input_required"] = True
            inbox["blocking_reason"] = "official_constituents_csv_missing"
            write_json(inbox_path, inbox)

            from medium_term_goal_review import build_medium_term_goal_review

            payload = build_medium_term_goal_review(root)
            goals = {item["goal_code"]: item for item in payload["goals"]}

            self.assertEqual(
                goals["backtest_evidence_quality"]["next_action"],
                "provide_official_constituents_csv_or_fix_network_permission",
            )
            self.assertEqual(
                payload["priority_next_actions"][0],
                "provide_official_constituents_csv_or_fix_network_permission",
            )

    def test_cli_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_review_fixtures(root)
            output = root / "outputs" / "automation" / "latest_medium_term_goal_review.json"
            report = root / "outputs" / "automation" / "latest_medium_term_goal_review.md"

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "medium_term_goal_review.py"),
                    "--project-root",
                    str(root),
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
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["status"], "on_track_with_monitoring")
            self.assertIn("中期目标进度看板", report.read_text(encoding="utf-8-sig"))
            self.assertIn("latest_medium_term_goal_review.md", combined)

    def test_wrapper_and_reporting_bundle_include_medium_term_goal_review(self):
        wrapper = (PROJECT_ROOT / "scripts" / "run_medium_term_goal_review.ps1").read_text(
            encoding="utf-8-sig"
        )
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("medium_term_goal_review.py", wrapper)
        self.assertIn("latest_medium_term_goal_review.json", wrapper)
        self.assertIn("latest_medium_term_goal_review.md", wrapper)
        self.assertIn("run_medium_term_goal_review", bundle)
        self.assertLess(
            bundle.index("run_forecast_performance_review"),
            bundle.index("run_medium_term_goal_review"),
        )
        self.assertLess(
            bundle.index("run_medium_term_goal_review"),
            bundle.index("show_automation_check"),
        )

    def test_development_closeout_summary_reports_module_and_overall_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_review_fixtures(root)

            from medium_term_goal_review import build_medium_term_goal_review
            from development_closeout_summary import (
                build_development_closeout_summary,
                render_development_closeout_summary,
            )

            review = build_medium_term_goal_review(root)
            review_path = root / "outputs" / "automation" / "latest_medium_term_goal_review.json"
            write_json(review_path, review)

            summary = build_development_closeout_summary(
                review_path,
                goal_code="backtest_evidence_quality",
            )
            default_summary = build_development_closeout_summary(review_path)
            report = render_development_closeout_summary(summary)

            self.assertEqual(summary["current_module"], "S&P 500 成分证据补强")
            self.assertEqual(summary["goal_code"], "backtest_evidence_quality")
            self.assertEqual(summary["module_completion_percent"], 30)
            self.assertEqual(default_summary["goal_code"], "backtest_evidence_quality")
            self.assertEqual(default_summary["current_module"], "S&P 500 成分证据补强")
            self.assertEqual(default_summary["module_completion_percent"], 30)
            self.assertEqual(
                summary["medium_term_overall_completion_percent"],
                review["overall_completion_percent"],
            )
            self.assertEqual(summary["strategy_code"], "evidence_prediction_decision_maturity")
            self.assertEqual(
                summary["current_target_total_completion_percent"],
                review["overall_completion_percent"],
            )
            self.assertFalse(summary["automatic_multi_model_collaboration_enabled"])
            self.assertEqual(
                summary["collaboration_execution_mode"],
                "single_codex_with_gpt55_review_checklist",
            )
            self.assertTrue(summary["sp500_current_source_inbox_external_input_required"])
            self.assertEqual(summary["sp500_current_source_inbox_size_bytes"], 12345)
            self.assertEqual(summary["sp500_current_source_inbox_sha256"], "a" * 64)
            self.assertEqual(
                summary["sp500_current_source_inbox_modified_at"],
                "2026-07-04T03:12:00+00:00",
            )
            self.assertEqual(
                summary["sp500_current_source_inbox_blocking_reason"],
                "official_constituents_csv_missing",
            )
            self.assertEqual(
                summary["sp500_current_source_inbox_blocking_input"],
                "inputs/sp500_current_membership/official_constituents.csv",
            )
            self.assertIn(
                "-DryRun -SourceFileInbox",
                summary.get("sp500_current_source_inbox_dry_run_command", ""),
            )
            self.assertIn(
                "-SourceFileInbox",
                summary.get("sp500_current_source_inbox_import_command", ""),
            )
            self.assertIn("当前开发内容所属模块：S&P 500 成分证据补强", report)
            self.assertIn("该模块完成度：30%", report)
            self.assertIn("中期目标整体完成度：", report)
            self.assertIn("当前目标总完成度：", report)
            self.assertIn("真实执行模式：single_codex_with_gpt55_review_checklist", report)

            self.assertIn("sp500_current_source_inbox_external_input_required=True", report)
            self.assertIn("sp500_current_source_inbox_size_bytes=12345", report)
            self.assertIn("sp500_current_source_inbox_sha256=" + "a" * 64, report)
            self.assertIn(
                "sp500_current_source_inbox_modified_at=2026-07-04T03:12:00+00:00",
                report,
            )
            self.assertIn(
                "sp500_current_source_inbox_blocking_reason=official_constituents_csv_missing",
                report,
            )
            self.assertIn("sp500_current_source_inbox_dry_run_command=", report)
            self.assertIn("sp500_current_source_inbox_import_command=", report)

    def test_development_closeout_wrapper_exists(self):
        wrapper = PROJECT_ROOT / "scripts" / "show_development_closeout.ps1"
        medium_term_wrapper = PROJECT_ROOT / "scripts" / "run_medium_term_goal_review.ps1"
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertTrue(wrapper.exists())
        text = wrapper.read_text(encoding="utf-8-sig")
        self.assertIn("development_closeout_summary.py", text)
        self.assertIn("GoalCode", text)
        medium_term_text = medium_term_wrapper.read_text(encoding="utf-8-sig")
        self.assertIn("CloseoutGoalCode", medium_term_text)
        self.assertIn("--closeout-goal-code", medium_term_text)
        self.assertIn("show_development_closeout.ps1", bundle)
        self.assertLess(
            bundle.index("run_pre_submit_review.ps1"),
            bundle.index("show_development_closeout.ps1"),
        )


if __name__ == "__main__":
    unittest.main()
