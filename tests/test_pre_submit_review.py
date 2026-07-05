import json
import os
import subprocess
import sys
import tempfile
import unittest
import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def secondary_current_membership_payload():
    return {
        "source_schema": "sp500_current_membership_sources",
        "source_version": 1,
        "status": "secondary_ready",
        "source_url": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        "source_trust_level": "secondary",
        "current_screening_allowed": True,
        "source_usage_scope": "current_screening_only",
        "verified_historical_evidence_allowed": False,
        "requested_count": 50,
        "parsed_official_ticker_count": 0,
        "parsed_secondary_ticker_count": 503,
        "matched_count": 50,
        "missing_count": 0,
        "missing_ticker_review_queue": [],
        "next_action": "run_screening_with_secondary_current_membership",
        "source_file_required_columns": ["Symbol", "Ticker"],
        "recommended_followup": "obtain_official_spglobal_constituents_csv",
        "formal_backtest_upgrade_allowed": False,
        "rows": [
            {
                "ticker": "ABT",
                "membership_evidence": "secondary",
                "membership_source_url": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                "source_as_of_date": "2026-07-05",
                "notes": "secondary current membership source",
            }
        ],
    }


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def write_text(path, text="ok\n"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig")


def write_csv(path, rows, fieldnames):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_ready_review_inputs(root, as_of_date="2026-06-28"):
    root = Path(root)
    write_text(
        root / "docs" / "中期目标与模型协作规范.md",
        "\n".join(
            [
                "# 中期目标与模型协作规范",
                "",
                "gpt5.3-codex-spark 负责快速迭代。",
                "gpt5.5 负责关键复核和正式收口。",
                "组合开发习惯要求保留证据三件套。",
                "每次迭代必须是可回放改动，先完成收敛迭代，再进入正式发布判断。",
                "每次改动前明确回退策略。",
                "所有模型优化建议先进入影子层。",
                "不得自动修改正式模型参数。",
                "当前未启用自动多模型协作。",
                "真实执行模式为 single_codex_with_gpt55_review_checklist。",
            ]
        )
        + "\n",
    )
    write_text(
        root / "docs" / "提交前复核清单.md",
        "\n".join(
            [
                "# checklist",
                "",
                "外部输入阻塞必须跨层同步。",
                "当 sp500_current_membership_source_inbox_status 显示 external_input_required=true 时，",
                "automation_check 和 weekly_ops_check 必须包含匹配的 external_input_blockers。",
            ]
        )
        + "\n",
    )
    write_json(
        root / "outputs" / "automation" / "latest_model_handoff_review.json",
        {
            "handoff_schema": "model_handoff_review",
            "handoff_version": 1,
            "as_of_date": as_of_date,
            "status": "ready",
            "goal_code": "backtest_evidence_quality",
            "current_module": "S&P 500 成分证据补强",
            "module_completion_percent": 30,
            "medium_term_overall_completion_percent": 61,
            "automatic_multi_model_collaboration_enabled": False,
            "collaboration_execution_mode": "single_codex_with_gpt55_review_checklist",
            "collaboration_boundary_note": "当前未启用自动多模型协作；实际由单 Codex 执行并通过清单模拟复核。",
            "spark_execution_summary": "小步实现并保留验证证据。",
            "gpt55_review_checklist": [
                "确认未自动修改正式模型参数",
                "确认输出不声称已启用自动双模型协作",
            ],
            "validation_commands": [
                "powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_pre_submit_review.ps1 -MaxAgeDays 8",
                "python -m unittest discover -s tests",
            ],
            "risk_notes": ["当前仍为单 Codex 执行加复核清单。"],
            "formal_release_allowed": True,
            "sp500_current_source_inbox_external_input_required": True,
            "sp500_current_source_inbox_size_bytes": 12345,
            "sp500_current_source_inbox_sha256": "a" * 64,
            "sp500_current_source_inbox_modified_at": "2026-07-04T03:12:00+00:00",
            "sp500_current_source_inbox_blocking_reason": "official_constituents_csv_missing",
            "sp500_current_source_inbox_blocking_input": "inputs/sp500_current_membership/official_constituents.csv",
            "sp500_current_source_request_file": "outputs/automation/sp500_current_membership_source_file_request.md",
            "sp500_current_source_request_manifest_status": "ready",
            "sp500_current_source_inbox_dry_run_command": (
                "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                "scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> "
                "-DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv"
            ),
            "sp500_current_source_inbox_import_command": (
                "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                "scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> "
                "-SourceFileInbox inputs/sp500_current_membership/official_constituents.csv"
            ),
            "sp500_current_source_acceptance_criteria": [
                "has_symbol_or_ticker_column",
                "at_least_400_tickers",
                "official_spglobal_constituents_export",
            ],
            "forecast_performance_status": "sample_accumulating",
            "forecast_performance_recommended_action": "continue_sample_accumulation",
            "forecast_mature_evaluations": 0,
            "forecast_one_week_mature": 0,
            "forecast_one_month_mature": 0,
            "forecast_next_one_week_evaluation_date": "2026-07-07",
            "forecast_next_one_week_evaluation_count": 42,
            "forecast_next_one_month_evaluation_date": "2026-07-28",
            "forecast_next_one_month_evaluation_count": 42,
            "forecast_formal_model_change_allowed": False,
        },
    )
    write_json(
        root
        / "outputs"
        / "automation"
        / "latest_sp500_current_membership_source_review_status.json",
        {
            "review_status_schema": "sp500_current_membership_source_review_status",
            "review_status_version": 1,
            "as_of_date": as_of_date,
            "status": "review_needed",
            "queue_file": "outputs/automation/sp500_current_membership_source_review_queue.csv",
            "decisions_template_file": "outputs/automation/sp500_current_membership_source_review_decisions_template.csv",
            "queue_exists": True,
            "queue_total_count": 2,
            "open_count": 2,
            "resolved_count": 0,
            "review_decision_status": "missing",
            "manual_decision_next_step": "fill_decisions_template",
            "decision_ready_to_apply_count": 0,
            "decision_ready_to_apply_tickers": [],
            "decision_pending_tickers": ["ABT", "ADM"],
            "decision_pending_count": 2,
            "decisions_template_status": "ready",
            "open_items": [
                {
                    "ticker": "ABT",
                    "review_status": "open",
                    "issue_type": "missing_from_official_current_source",
                    "recommended_check": "Confirm official coverage.",
                    "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                    "source_status": "fetch_failed",
                },
                {
                    "ticker": "ADM",
                    "review_status": "open",
                    "issue_type": "missing_from_official_current_source",
                    "recommended_check": "Confirm official coverage.",
                    "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                    "source_status": "fetch_failed",
                },
            ],
            "resolved_items": [],
            "decision_options": [
                {
                    "review_decision": "official_absent",
                    "when_to_use": "Official current S&P source was checked and the ticker is absent.",
                    "effect": "Ready to close the open queue item when official_source_checked=yes.",
                },
                {
                    "review_decision": "source_refresh_required",
                    "when_to_use": "The current official export appears stale or incomplete.",
                    "effect": "Keeps the queue item open and asks for a fresher official source.",
                },
                {
                    "review_decision": "keep_open",
                    "when_to_use": "The item still needs more manual evidence before a decision.",
                    "effect": "Keeps the queue item open.",
                },
                {
                    "review_decision": "not_applicable",
                    "when_to_use": "The ticker is not applicable to the current S&P 500 source review.",
                    "effect": "Ready to close the open queue item when official_source_checked=yes.",
                },
            ],
            "decision_required_fields": [
                "ticker",
                "review_decision",
                "official_source_checked",
                "required_source_url",
                "issue_type",
                "recommended_check",
                "decision_notes",
            ],
            "manual_decision_instructions": (
                "Fill one row per open ticker in the decisions template. "
                "Set official_source_checked=yes when the official S&P source has been checked."
            ),
            "next_action": "review_open_queue_items",
            "formal_backtest_upgrade_allowed": False,
        },
    )
    write_json(
        root
        / "outputs"
        / "automation"
        / "latest_sp500_current_membership_source_inbox_status.json",
        {
            "status_schema": "sp500_current_membership_source_inbox_status",
            "status_version": 1,
            "as_of_date": as_of_date,
            "status": "missing",
            "source_file_inbox": "inputs/sp500_current_membership/official_constituents.csv",
            "source_file_inbox_exists": False,
            "source_file_validation_status": "missing",
            "parsed_official_ticker_count": 0,
            "minimum_official_ticker_count": 400,
            "intake_coverage_status": "none",
            "intake_expected_count": 2,
            "intake_matched_count": 0,
            "intake_missing_count": 2,
            "next_action": "place_official_constituents_csv",
            "external_input_required": True,
            "blocking_reason": "official_constituents_csv_missing",
            "blocking_input": "inputs/sp500_current_membership/official_constituents.csv",
            "formal_backtest_upgrade_allowed": False,
            "formal_model_change_allowed": False,
        },
    )
    write_csv(
        root / "outputs" / "automation" / "sp500_current_membership_source_review_decisions_template.csv",
        [
            {
                "ticker": "ABT",
                "review_decision": "",
                "official_source_checked": "",
                "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                "issue_type": "missing_from_official_current_source",
                "recommended_check": "Confirm official coverage.",
                "decision_notes": "",
            },
            {
                "ticker": "ADM",
                "review_decision": "",
                "official_source_checked": "",
                "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                "issue_type": "missing_from_official_current_source",
                "recommended_check": "Confirm official coverage.",
                "decision_notes": "",
            }
        ],
        [
            "ticker",
            "review_decision",
            "official_source_checked",
            "required_source_url",
            "issue_type",
            "recommended_check",
            "decision_notes",
        ],
    )
    write_json(
        root / "outputs" / "automation" / "latest_weekly_delivery_check.json",
        {
            "delivery_check_schema": "weekly_delivery_check",
            "delivery_check_version": 1,
            "as_of_date": as_of_date,
            "status": "ready",
            "freshness_status": "fresh",
            "conclusion_status": "ready",
            "conclusion_health_score": 80,
            "conclusion_health_status": "needs_review",
            "conclusion_health_reasons": [],
            "candidate_count_total": 64,
            "manual_review_queue_count": 0,
            "manual_review_pending_count": 0,
            "manual_review_merge_summary_exists": True,
            "conclusion_signal_status": "ready",
            "missing_conclusion_signals": [],
            "missing_conclusion_signal_fixes": {},
            "action_items_status": "ready",
            "action_items_freshness_status": "fresh",
            "action_items_count": 2,
            "action_items_actual_count": 2,
            "action_items_json": "outputs/automation/latest_weekly_action_items.json",
            "external_input_blocker_count": 1,
            "external_input_blockers": [
                {
                    "action_code": "provide_official_constituents_csv",
                    "blocking_input": "inputs/sp500_current_membership/official_constituents.csv",
                    "blocking_reason": "official_constituents_csv_missing",
                    "next_action": "place_official_constituents_csv",
                }
            ],
            "forecast_next_one_week_evaluation_date": "2026-07-07",
            "forecast_next_one_week_evaluation_count": 42,
            "forecast_next_one_month_evaluation_date": "2026-07-28",
            "forecast_next_one_month_evaluation_count": 42,
            "missing_outputs": [],
            "attention_reasons": [],
        },
    )
    write_json(
        root / "outputs" / "automation" / "latest_weekly_ops_check.json",
        {
            "ops_check_schema": "weekly_ops_check",
            "ops_check_version": 1,
            "as_of_date": as_of_date,
            "status": "ready",
            "freshness_status": "fresh",
            "automation_audit_status": "ready",
            "automation_check_status": "manual_review_needed",
            "manifest_validation_status": "valid",
            "market_count": 3,
            "markets_ready_count": 3,
            "candidate_count_total": 64,
            "manual_review_queue_count": 0,
            "manual_review_repeat_count": 0,
            "recommended_action": "review_data_health",
            "priority_actions": ["review_data_health", "continue_sample_accumulation"],
            "forecast_next_one_week_evaluation_date": "2026-07-07",
            "forecast_next_one_week_evaluation_count": 42,
            "forecast_next_one_month_evaluation_date": "2026-07-28",
            "forecast_next_one_month_evaluation_count": 42,
            "automation_issues": [],
            "external_input_blocker_count": 1,
            "external_input_blockers": [
                {
                    "action_code": "provide_official_constituents_csv",
                    "blocking_input": "inputs/sp500_current_membership/official_constituents.csv",
                    "blocking_reason": "official_constituents_csv_missing",
                    "next_action": "place_official_constituents_csv",
                }
            ],
            "missing_outputs": [],
            "missing_output_paths": {},
            "attention_reasons": [],
        },
    )
    write_json(
        root / "outputs" / "automation" / "latest_automation_check.json",
        {
            "check_schema": "weekly_automation_check",
            "check_version": 1,
            "as_of_date": as_of_date,
            "status": "manual_review_needed",
            "recommended_action": "review_data_health",
            "manifest_validation_status": "valid",
            "manifest_validation_errors": [],
            "market_count": 3,
            "markets_ready_count": 3,
            "not_ready_markets": [],
            "candidate_count_total": 64,
            "market_candidate_counts": [
                {"name": "美股周筛", "status": "ready", "candidate_count": 22},
                {"name": "A股周筛", "status": "ready", "candidate_count": 7},
                {"name": "港股周筛", "status": "ready", "candidate_count": 35},
            ],
            "manual_review_queue_count": 0,
            "manual_review_repeat_count": 0,
            "data_health_status": "manual_review_needed",
            "data_quality_status": "needs_review",
            "data_quality_score": 79.0,
            "data_quality_history_status": "manual_review_needed",
            "candidate_review_status": "manual_review_needed",
            "weekly_ops_history_status": "clear",
            "weekly_delivery_history_status": "manual_review_needed",
            "model_audit_status": "sample_accumulating",
            "forecast_performance_status": "sample_accumulating",
            "forecast_next_one_week_evaluation_date": "2026-07-07",
            "forecast_next_one_week_evaluation_count": 42,
            "forecast_next_one_month_evaluation_date": "2026-07-28",
            "forecast_next_one_month_evaluation_count": 42,
            "backtest_status": "evidence_review_needed",
            "external_input_blocker_count": 1,
            "external_input_blockers": [
                {
                    "action_code": "provide_official_constituents_csv",
                    "blocking_input": "inputs/sp500_current_membership/official_constituents.csv",
                    "blocking_reason": "official_constituents_csv_missing",
                    "next_action": "place_official_constituents_csv",
                }
            ],
            "outputs": {
                "self_analysis": "outputs/automation/latest_self_analysis.md",
                "manifest": "outputs/automation/latest_self_analysis_manifest.json",
                "automation_check": "outputs/automation/latest_automation_check.json",
            },
            "priority_actions": ["review_data_health", "continue_sample_accumulation"],
        },
    )
    write_json(
        root / "outputs" / "automation" / "latest_weekly_conclusion.json",
        {
            "conclusion_schema": "weekly_conclusion",
            "conclusion_version": 1,
            "as_of_date": as_of_date,
            "status": "ready",
            "recommended_action": "monitor_next_run",
            "priority_actions": [
                "review_data_health",
                "continue_sample_accumulation",
                "provide_official_constituents_csv",
            ],
            "priority_action_details": [
                {"action": "review_data_health", "description": "review data health"},
                {"action": "continue_sample_accumulation", "description": "keep tracking"},
                {
                    "action": "provide_official_constituents_csv",
                    "description": (
                        "投递入口=inputs/sp500_current_membership/official_constituents.csv；"
                        "阻塞原因=official_constituents_csv_missing；"
                        "校验命令=powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                        "scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> "
                        "-DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv；"
                        "导入命令=powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                        "scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> "
                        "-SourceFileInbox inputs/sp500_current_membership/official_constituents.csv"
                    ),
                },
            ],
            "priority_input_gaps": [
                {
                    "action_code": "provide_official_constituents_csv",
                    "blocking_input": "inputs/sp500_current_membership/official_constituents.csv",
                    "blocking_reason": "official_constituents_csv_missing",
                    "next_action": "place_official_constituents_csv",
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
            ],
            "candidate_count_total": 64,
            "candidate_action_summary": {"priority_research": 12, "watchlist": 52},
            "health": {"status": "needs_review", "score": 90, "reasons": []},
            "automation": {
                "data_quality": {"status": "needs_review"},
                "data_quality_history": {"status": "collecting"},
                "forecast_performance": {"status": "sample_accumulating"},
            },
            "markets": [{"market": "美股周筛", "status": "ready", "candidate_count": 22}],
            "candidates": [],
            "missing_inputs": [],
            "warnings": [],
            "outputs": {
                "markdown": "outputs/automation/latest_weekly_conclusion.md",
                "json": "outputs/automation/latest_weekly_conclusion.json",
                "manual_review_decisions_template": "outputs/automation/manual_review_decisions_template.csv",
            },
        },
    )
    write_json(
        root / "outputs" / "automation" / "latest_weekly_action_items.json",
        {
            "action_items_schema": "weekly_action_items",
            "action_items_version": 1,
            "as_of_date": as_of_date,
            "item_count": 3,
            "items": [
                {
                    "priority": 1,
                    "status": "open",
                    "action_code": "review_data_health",
                    "category": "data_health",
                    "title": "review",
                    "recommended_check": "check data health",
                },
                {
                    "priority": 2,
                    "status": "open",
                    "action_code": "continue_sample_accumulation",
                    "category": "model_tracking",
                    "title": "track",
                    "source": (
                        "model_audit_status:sample_accumulating; "
                        "forecast_mature_evaluations:0; "
                        "forecast_one_week_mature:0; "
                        "forecast_one_month_mature:0; "
                        "forecast_next_one_week_evaluation_date:2026-07-07; "
                        "forecast_next_one_week_evaluation_count:42; "
                        "forecast_next_one_month_evaluation_date:2026-07-28; "
                        "forecast_next_one_month_evaluation_count:42; "
                        "forecast_formal_model_change_allowed:false"
                    ),
                    "recommended_check": "keep tracking",
                },
                {
                    "priority": 3,
                    "status": "open",
                    "action_code": "provide_official_constituents_csv",
                    "category": "backtest",
                    "title": "provide official csv",
                    "source": (
                        "status:fetch_failed; "
                        "source_file_required_columns:Symbol, Ticker; "
                        "source_file_accepted_ticker_columns:Symbol, Ticker, Ticker Symbol, Constituent Ticker, Constituent Symbol; "
                        "source_file_request_file:outputs/automation/sp500_current_membership_source_file_request.md; "
                        "source_file_inbox:inputs/sp500_current_membership/official_constituents.csv; "
                        "source_file_inbox_exists:false; "
                        "source_file_validation_status:missing; "
                        "source_file_inbox_status:missing; "
                        "source_file_inbox_next_action:place_official_constituents_csv; "
                        "source_file_inbox_parsed_official_ticker_count:0; "
                        "source_file_inbox_intake_missing_count:2; "
                        "fetch_error_type:official_source_access_denied; "
                        "fetch_retryable_without_environment_change:false; "
                        "fetch_error_next_action:provide_official_constituents_csv; "
                        "source_file_acceptance_criteria:has_symbol_or_ticker_column, at_least_400_tickers, official_spglobal_constituents_export"
                    ),
                    "recommended_check": (
                        "source_file_request_file:outputs/automation/sp500_current_membership_source_file_request.md; "
                        "source_file_inbox:inputs/sp500_current_membership/official_constituents.csv; "
                        "inbox_status_file:outputs/automation/latest_sp500_current_membership_source_inbox_status.json; "
                        "inbox_status:missing; "
                        "inbox_next_action:place_official_constituents_csv; "
                        "parsed_official_ticker_count:0; "
                        "inbox_intake_missing_count:2; "
                        "accepted_ticker_columns:Symbol, Ticker, Ticker Symbol, Constituent Ticker, Constituent Symbol; "
                        "acceptance_criteria:has_symbol_or_ticker_column, at_least_400_tickers, official_spglobal_constituents_export; "
                        "dry_run_command:powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                        "scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> "
                        "-DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv; "
                        "import_command:powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                        "scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> "
                        "-SourceFileInbox inputs/sp500_current_membership/official_constituents.csv"
                    ),
                }
            ],
        },
    )
    write_json(
        root / "outputs" / "automation" / "latest_data_health_review.json",
        {
            "review_schema": "data_health_review",
            "review_version": 1,
            "as_of_date": as_of_date,
            "status": "acceptable_with_monitoring",
            "recommended_action": "monitor_next_run",
            "blocked_candidate_count": 0,
            "refetch_gap_count": 2,
            "manual_financial_review_count": 72,
        },
    )
    write_json(
        root / "outputs" / "automation" / "latest_backtest_evidence_review.json",
        {
            "review_schema": "backtest_evidence_review",
            "review_version": 1,
            "as_of_date": as_of_date,
            "status": "evidence_review_needed",
            "recommended_action": "supplement_verified_membership_evidence",
            "weeks_completed": 8,
            "weeks_failed": 0,
            "verified_membership_ratio": 0.156,
            "weak_evidence_rows": 3382,
            "weak_evidence_weeks": 8,
            "formal_model_upgrade_allowed": False,
        },
    )
    write_json(
        root / "outputs" / "automation" / "latest_membership_evidence_import_plan.json",
        {
            "review_schema": "membership_evidence_import_plan",
            "review_version": 1,
            "as_of_date": as_of_date,
            "status": "ready",
            "gap_count": 425,
            "queue_count": 50,
            "ready_to_import_count": 0,
            "missing_source_count": 50,
            "invalid_source_count": 0,
            "ready_to_import_weeks_affected": 0,
            "missing_source_weeks_affected": 7800,
            "invalid_source_weeks_affected": 0,
            "formal_backtest_upgrade_allowed": False,
        },
    )
    write_json(
        root / "outputs" / "automation" / "latest_membership_evidence_supplement_queue.json",
        {
            "queue_schema": "membership_evidence_supplement_queue",
            "queue_version": 1,
            "as_of_date": as_of_date,
            "status": "action_required",
            "queue_count": 50,
            "official_evidence_required_count": 50,
            "blocked_by_source_policy_count": 50,
            "formal_backtest_upgrade_allowed": False,
        },
    )
    write_json(
        root / "outputs" / "automation" / "latest_membership_evidence_supplement_batch.json",
        {
            "batch_schema": "membership_evidence_supplement_batch",
            "batch_version": 1,
            "as_of_date": as_of_date,
            "status": "batch_ready",
            "batch_id": f"{as_of_date}-p1",
            "batch_size": 10,
            "queue_count": 50,
            "selected_count": 10,
            "remaining_after_batch_count": 40,
            "batch_tickers": ["ABT", "ADM"],
            "batch_weeks_affected": 312,
            "completion_condition": (
                "Fill these tickers in inputs/sp500_membership_evidence/"
                "verified_membership_evidence_intake.csv and rerun source intake status."
            ),
            "applied_to_historical_membership": False,
            "formal_backtest_upgrade_allowed": False,
            "items": [],
        },
    )
    write_json(
        root / "outputs" / "automation" / "latest_membership_evidence_source_intake_status.json",
        {
            "status_schema": "membership_evidence_source_intake_status",
            "status_version": 1,
            "as_of_date": as_of_date,
            "status": "awaiting_manual_evidence",
            "queue_count": 50,
            "ready_to_import_count": 0,
            "ready_to_import_weeks_affected": 0,
            "invalid_count": 0,
            "invalid_weeks_affected": 0,
            "pending_count": 50,
            "template_status": "created",
            "formal_backtest_upgrade_allowed": False,
            "items": [],
        },
    )
    write_json(
        root / "outputs" / "automation" / "latest_membership_evidence_apply_preview.json",
        {
            "preview_schema": "membership_evidence_apply_preview",
            "preview_version": 1,
            "as_of_date": as_of_date,
            "status": "ready",
            "membership_row_count": 7800,
            "eligible_ticker_count": 0,
            "preview_row_count": 0,
            "preview_weeks_affected": 0,
            "invalid_source_ticker_count": 0,
            "already_verified_row_count": 0,
            "applied_to_historical_membership": False,
            "formal_backtest_upgrade_allowed": False,
        },
    )
    write_json(
        root / "outputs" / "automation" / "latest_membership_evidence_apply_confirmation_status.json",
        {
            "confirmation_schema": "membership_evidence_apply_confirmation_status",
            "confirmation_version": 1,
            "as_of_date": as_of_date,
            "status": "clear",
            "preview_row_count": 0,
            "approved_count": 0,
            "rejected_count": 0,
            "invalid_count": 0,
            "pending_count": 0,
            "approved_package_row_count": 0,
            "applied_to_historical_membership": False,
            "formal_backtest_upgrade_allowed": False,
            "items": [],
        },
    )
    write_json(
        root / "outputs" / "automation" / "latest_membership_evidence_approved_apply_plan.json",
        {
            "plan_schema": "membership_evidence_approved_apply_plan",
            "plan_version": 1,
            "as_of_date": as_of_date,
            "status": "clear",
            "approved_package_row_count": 0,
            "membership_row_count": 7800,
            "ready_to_apply_count": 0,
            "already_verified_count": 0,
            "missing_historical_row_count": 0,
            "invalid_approved_package_row_count": 0,
            "requires_manual_apply": False,
            "would_modify_historical_membership": False,
            "applied_to_historical_membership": False,
            "formal_backtest_upgrade_allowed": False,
            "items": [],
        },
    )
    write_json(
        root / "outputs" / "automation" / "latest_sp500_current_membership_sources.json",
        {
            "source_schema": "sp500_current_membership_sources",
            "source_version": 1,
            "as_of_date": as_of_date,
            "status": "fetch_failed",
            "source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
            "requested_count": 50,
            "parsed_official_ticker_count": 0,
            "matched_count": 0,
            "missing_count": 50,
            "missing_tickers": ["ABT", "ADM"],
            "missing_ticker_review_queue": [
                {
                    "ticker": "ABT",
                    "review_status": "open",
                    "issue_type": "missing_from_official_current_source",
                    "recommended_check": "Confirm official source coverage.",
                    "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                    "source_status": "fetch_failed",
                },
                {
                    "ticker": "ADM",
                    "review_status": "open",
                    "issue_type": "missing_from_official_current_source",
                    "recommended_check": "Confirm official source coverage.",
                    "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                    "source_status": "fetch_failed",
                },
            ],
            "missing_ticker_review_queue_file": "outputs/automation/sp500_current_membership_source_review_queue.csv",
            "next_action": "retry_official_source_or_provide_official_constituents_csv",
            "source_file_required_columns": ["Symbol", "Ticker"],
            "minimum_official_ticker_count": 400,
            "source_quality_flags": ["official_source_fetch_failed"],
            "source_file_next_command": (
                "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                "scripts\\run_sp500_current_membership_sources.ps1 "
                "-ProjectRoot <project_root> -SourceFile <official_constituents.csv>"
            ),
            "source_file_inbox_next_command": (
                "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                "scripts\\run_sp500_current_membership_sources.ps1 "
                "-ProjectRoot <project_root> -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv"
            ),
            "source_file_inbox_dry_run_command": (
                "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                "scripts\\run_sp500_current_membership_sources.ps1 "
                "-ProjectRoot <project_root> -DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv"
            ),
            "source_file_acceptance_criteria": [
                "has_symbol_or_ticker_column",
                "at_least_400_tickers",
                "official_spglobal_constituents_export",
            ],
            "source_file_intake_template": "outputs/automation/sp500_current_membership_source_intake_template.csv",
            "source_file_request_file": "outputs/automation/sp500_current_membership_source_file_request.md",
            "source_file_inbox": "inputs/sp500_current_membership/official_constituents.csv",
            "source_file_inbox_exists": False,
            "source_file_inbox_size_bytes": 0,
            "source_file_inbox_sha256": "",
            "source_file_inbox_modified_at": "",
            "source_file_validation_status": "missing",
            "intake_coverage_status": "none",
            "intake_expected_count": 2,
            "intake_matched_count": 0,
            "intake_missing_count": 2,
            "intake_missing_tickers": ["ABT", "ADM"],
            "recommended_followup": "provide_official_constituents_csv",
            "formal_backtest_upgrade_allowed": False,
            "rows": [],
            "error": "HTTP Error 403: Forbidden",
        },
    )
    write_csv(
        root / "outputs" / "automation" / "sp500_current_membership_source_intake_template.csv",
        [
            {
                "expected_ticker": "ABT",
                "intake_status": "official_export_required",
                "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                "required_source_columns": "Symbol or Ticker",
                "notes": "Download the official S&P Global constituents export.",
            },
            {
                "expected_ticker": "ADM",
                "intake_status": "official_export_required",
                "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                "required_source_columns": "Symbol or Ticker",
                "notes": "Download the official S&P Global constituents export.",
            },
        ],
        ["expected_ticker", "intake_status", "required_source_url", "required_source_columns", "notes"],
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
        f"- as_of_date: {as_of_date}\n"
        "- required_columns: Symbol or Ticker\n"
        "- accepted_ticker_columns: Symbol, Ticker, Ticker Symbol, Constituent Ticker, Constituent Symbol\n"
        "- acceptance_criteria: has_symbol_or_ticker_column, at_least_400_tickers, official_spglobal_constituents_export\n"
        "- minimum_official_ticker_count: 400\n"
        "- source_file_inbox: inputs/sp500_current_membership/official_constituents.csv\n"
        "- formal_backtest_upgrade_allowed: false\n"
        "- formal_model_change_allowed: false\n"
        "- dry_run_command: powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> -DryRun -SourceFile <official_constituents.csv>\n"
        "- import_command: powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> -SourceFile <official_constituents.csv>\n"
        "- inbox_dry_run_command: powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> -DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv\n"
        "- inbox_import_command: powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv\n"
        "\n## Acceptance criteria\n\n"
        "- has_symbol_or_ticker_column\n"
        "- at_least_400_tickers\n"
        "- official_spglobal_constituents_export\n"
        "\n## Current source file inbox fingerprint\n\n"
        "- source_file_inbox_size_bytes: 0\n"
        "- source_file_inbox_sha256: none\n"
        "- source_file_inbox_modified_at: none\n"
        "\n## Boundary\n\n"
        "- Use only the official S&P Global constituents export. Do not import the intake template as the source CSV.\n"
        "- Run the dry-run command before the import command.\n",
        encoding="utf-8-sig",
    )
    write_csv(
        root / "outputs" / "automation" / "sp500_current_membership_source_review_queue.csv",
        [
            {
                "ticker": "ABT",
                "review_status": "open",
                "issue_type": "missing_from_official_current_source",
                "recommended_check": "Confirm official source coverage.",
                "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                "source_status": "fetch_failed",
            },
            {
                "ticker": "ADM",
                "review_status": "open",
                "issue_type": "missing_from_official_current_source",
                "recommended_check": "Confirm official source coverage.",
                "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                "source_status": "fetch_failed",
            },
        ],
        [
            "ticker",
            "review_status",
            "issue_type",
            "recommended_check",
            "required_source_url",
            "source_status",
        ],
    )
    write_json(
        root / "outputs" / "automation" / "latest_candidate_findings_review.json",
        {
            "review_schema": "candidate_findings_review",
            "review_version": 1,
            "as_of_date": as_of_date,
            "status": "manual_review_needed",
            "recommended_action": "review_candidate_findings",
            "candidate_count": 64,
            "field_complete_count": 64,
            "missing_field_count": 0,
            "risk_coverage_count": 64,
            "risk_missing_count": 0,
            "risk_review_count": 33,
            "formal_model_change_allowed": False,
        },
    )
    write_json(
        root / "outputs" / "automation" / "latest_forecast_performance_review.json",
        {
            "review_schema": "forecast_performance_review",
            "review_version": 1,
            "as_of_date": as_of_date,
            "status": "sample_accumulating",
            "recommended_action": "continue_sample_accumulation",
            "total_evaluations": 65,
            "mature_evaluations": 0,
            "one_week_mature": 0,
            "one_month_mature": 0,
            "prediction_unavailable": 65,
            "latest_prediction_unavailable_count": 0,
            "legacy_prediction_unavailable_count": 65,
            "forecast_history_short_signal_missing_count": 240,
            "latest_short_signal_missing_count": 0,
            "legacy_short_signal_missing_count": 240,
            "next_one_week_evaluation_date": "2026-07-07",
            "next_one_week_evaluation_count": 42,
            "next_one_month_evaluation_date": "2026-07-28",
            "next_one_month_evaluation_count": 42,
            "missing_market_count": 0,
            "formal_model_change_allowed": False,
        },
    )
    write_json(
        root / "outputs" / "automation" / "latest_one_week_forecast_shadow_review.json",
        {
            "review_schema": "one_week_forecast_shadow_review",
            "review_version": 1,
            "as_of_date": as_of_date,
            "status": "sample_accumulating",
            "one_week_evaluated_count": 12,
            "recommended_shadow_actions": ["keep_formal_model_unchanged"],
            "formal_model_change_allowed": False,
        },
    )
    write_json(
        root / "outputs" / "automation" / "latest_one_week_forecast_calibration_review.json",
        {
            "review_schema": "one_week_forecast_calibration_review",
            "review_version": 1,
            "as_of_date": as_of_date,
            "status": "insufficient_samples",
            "one_week_evaluated_count": 12,
            "recommended_shadow_actions": ["keep_formal_model_unchanged"],
            "formal_model_change_allowed": False,
        },
    )
    write_json(
        root / "outputs" / "automation" / "latest_one_week_forecast_shadow_parameter_plan.json",
        {
            "plan_schema": "one_week_forecast_shadow_parameter_plan",
            "plan_version": 1,
            "as_of_date": as_of_date,
            "status": "insufficient_samples",
            "one_week_evaluated_count": 12,
            "execution_mode": "shadow_only",
            "candidate_shadow_changes": [],
            "candidate_change_count": 0,
            "acceptance_gates": [
                "run_shadow_backtest_before_formal_change",
                "compare_against_current_model",
                "require_human_approval",
                "keep_formal_model_unchanged_until_approved",
            ],
            "formal_model_change_allowed": False,
        },
    )
    write_json(
        root / "outputs" / "automation" / "latest_medium_term_goal_review.json",
        {
            "review_schema": "medium_term_goal_review",
            "review_version": 1,
            "as_of_date": as_of_date,
            "period": "8 weeks",
            "status": "on_track_with_monitoring",
            "strategy_code": "evidence_prediction_decision_maturity",
            "strategy_title": "证据、预测与决策成熟化",
            "overall_completion_percent": 61,
            "current_target_total_completion_percent": 61,
            "priority_next_actions": [
                "continue_sample_accumulation",
                "provide_official_constituents_csv_or_fix_network_permission",
            ],
            "automatic_multi_model_collaboration_enabled": False,
            "collaboration_execution_mode": "single_codex_with_gpt55_review_checklist",
            "collaboration_boundary_note": "当前未启用自动多模型协作；实际由单 Codex 执行并通过清单模拟复核。",
            "development_completion_policy": {
                "required_in_task_closeout": True,
                "closeout_fields": [
                    "current_module",
                    "module_completion_percent",
                    "medium_term_overall_completion_percent",
                    "current_target_total_completion_percent",
                ],
            },
            "task_closeout_snapshot": {
                "goal_code": "backtest_evidence_quality",
                "current_module": "S&P 500 成分证据补强",
                "module_completion_percent": 30,
                "medium_term_overall_completion_percent": 61,
                "current_target_total_completion_percent": 61,
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
                        "sp500_current_source_inbox_size_bytes": 12345,
                        "sp500_current_source_inbox_sha256": "a" * 64,
                        "sp500_current_source_inbox_modified_at": "2026-07-04T03:12:00+00:00",
                        "sp500_current_source_inbox_blocking_reason": "official_constituents_csv_missing",
                        "sp500_current_source_inbox_blocking_input": (
                            "inputs/sp500_current_membership/official_constituents.csv"
                        ),
                    },
                }
            ],
        },
    )
    conclusion_path = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
    action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
    if conclusion_path.exists() and action_items_path.exists():
        action_mtime = action_items_path.stat().st_mtime
        os.utime(conclusion_path, (action_mtime + 1, action_mtime + 1))
        delivery_path = root / "outputs" / "automation" / "latest_weekly_delivery_check.json"
        if delivery_path.exists():
            os.utime(delivery_path, (action_mtime + 2, action_mtime + 2))


class PreSubmitReviewTests(unittest.TestCase):
    def test_secondary_current_membership_source_is_acceptable_with_upgrade_gate_closed(self):
        from pre_submit_review import _sp500_current_membership_source_reasons

        reasons = _sp500_current_membership_source_reasons(
            secondary_current_membership_payload(),
            PROJECT_ROOT,
        )

        self.assertNotIn("sp500_current_membership_sources_not_acceptable", reasons)
        self.assertNotIn("sp500_current_membership_sources_upgrade_gate_unsafe", reasons)

    def test_crosscheck_substitute_current_membership_source_is_acceptable_with_upgrade_gate_closed(self):
        from pre_submit_review import _sp500_current_membership_source_reasons

        payload = secondary_current_membership_payload()
        payload.update(
            {
                "status": "crosscheck_substitute_ready",
                "source_url": "local://sp500_crosscheck_substitute",
                "source_trust_level": "crosscheck_substitute",
                "parsed_secondary_ticker_count": 0,
                "parsed_crosscheck_ticker_count": 503,
                "next_action": "run_screening_with_crosscheck_current_membership",
                "recommended_followup": "refresh_crosscheck_substitute_weekly",
                "crosscheck_constituents_file": (
                    "outputs/sp500_crosscheck_20260705/"
                    "sp500_full_constituents_crosscheck_20260705.xlsx"
                ),
                "source_file_required_columns": [],
                "formal_backtest_upgrade_allowed": False,
            }
        )

        reasons = _sp500_current_membership_source_reasons(payload, PROJECT_ROOT)

        self.assertNotIn("sp500_current_membership_sources_not_acceptable", reasons)
        self.assertNotIn("sp500_current_membership_sources_upgrade_gate_unsafe", reasons)

    def test_review_needs_attention_when_crosscheck_substitute_lacks_usage_policy(self):
        from pre_submit_review import _sp500_current_membership_source_reasons

        payload = secondary_current_membership_payload()
        payload.update(
            {
                "status": "crosscheck_substitute_ready",
                "source_url": "local://sp500_crosscheck_substitute",
                "source_trust_level": "crosscheck_substitute",
                "parsed_secondary_ticker_count": 0,
                "parsed_crosscheck_ticker_count": 503,
                "next_action": "run_screening_with_crosscheck_current_membership",
                "recommended_followup": "refresh_crosscheck_substitute_weekly",
                "crosscheck_constituents_file": (
                    "outputs/sp500_crosscheck_20260705/"
                    "sp500_full_constituents_crosscheck_20260705.xlsx"
                ),
                "source_file_required_columns": [],
                "formal_backtest_upgrade_allowed": False,
            }
        )
        payload.pop("current_screening_allowed", None)
        payload.pop("source_usage_scope", None)
        payload.pop("verified_historical_evidence_allowed", None)

        reasons = _sp500_current_membership_source_reasons(payload, PROJECT_ROOT)

        self.assertIn("sp500_current_membership_sources_missing_usage_policy", reasons)

    def test_review_is_ready_when_all_existing_checks_are_fresh_and_acceptable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)

            from pre_submit_review import render_pre_submit_review, run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)
            report = render_pre_submit_review(result)

            self.assertEqual(result["pre_submit_review_schema"], "pre_submit_review")
            self.assertEqual(result["pre_submit_review_version"], 1)
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["freshness_status"], "fresh")
            self.assertEqual(result["candidate_count_total"], 64)
            self.assertEqual(result["manual_action_items_count"], 3)
            self.assertEqual(result["governance_status"], "ready")
            self.assertIn("review_data_health", result["priority_actions"])
            self.assertIn("continue_sample_accumulation", result["priority_actions"])
            self.assertEqual(
                result["development_priority_actions"],
                [
                    "continue_sample_accumulation",
                    "provide_official_constituents_csv_or_fix_network_permission",
                ],
            )
            self.assertEqual(result["input_statuses"]["weekly_action_items"], "ready")
            self.assertEqual(result["input_statuses"]["data_health_review"], "acceptable_with_monitoring")
            self.assertEqual(result["input_statuses"]["backtest_evidence_review"], "evidence_review_needed")
            self.assertEqual(result["input_statuses"]["membership_evidence_import_plan"], "ready")
            self.assertEqual(result["input_statuses"]["membership_evidence_apply_preview"], "ready")
            self.assertEqual(result["input_statuses"]["sp500_current_membership_sources"], "fetch_failed")
            self.assertEqual(result["input_statuses"]["sp500_current_membership_source_inbox_status"], "missing")
            self.assertEqual(result["input_statuses"]["candidate_findings_review"], "manual_review_needed")
            self.assertEqual(result["input_statuses"]["forecast_performance_review"], "sample_accumulating")
            self.assertEqual(result["forecast_next_one_week_evaluation_date"], "2026-07-07")
            self.assertEqual(result["forecast_next_one_week_evaluation_count"], 42)
            self.assertEqual(result["forecast_next_one_month_evaluation_date"], "2026-07-28")
            self.assertEqual(result["forecast_next_one_month_evaluation_count"], 42)
            self.assertEqual(
                result["development_closeout"]["current_module"],
                "S&P 500 成分证据补强",
            )
            self.assertEqual(
                result["development_closeout"]["goal_code"],
                "backtest_evidence_quality",
            )
            self.assertEqual(result["development_closeout"]["module_completion_percent"], 30)
            self.assertEqual(
                result["development_closeout"]["medium_term_overall_completion_percent"],
                61,
            )
            self.assertEqual(
                result["development_closeout"]["current_target_total_completion_percent"],
                61,
            )
            self.assertFalse(
                result["development_closeout"]["automatic_multi_model_collaboration_enabled"]
            )
            self.assertEqual(
                result["development_closeout"]["collaboration_execution_mode"],
                "single_codex_with_gpt55_review_checklist",
            )
            self.assertTrue(
                result["development_closeout"][
                    "sp500_current_source_inbox_external_input_required"
                ]
            )
            self.assertEqual(
                result["development_closeout"]["sp500_current_source_inbox_size_bytes"],
                12345,
            )
            self.assertEqual(
                result["development_closeout"]["sp500_current_source_inbox_sha256"],
                "a" * 64,
            )
            self.assertEqual(
                result["development_closeout"]["sp500_current_source_inbox_modified_at"],
                "2026-07-04T03:12:00+00:00",
            )
            self.assertEqual(
                result["development_closeout"]["sp500_current_source_inbox_blocking_reason"],
                "official_constituents_csv_missing",
            )
            self.assertEqual(
                result["development_closeout"]["sp500_current_source_inbox_blocking_input"],
                "inputs/sp500_current_membership/official_constituents.csv",
            )
            self.assertIn(
                "-DryRun -SourceFileInbox",
                result["development_closeout"]["sp500_current_source_inbox_dry_run_command"],
            )
            self.assertIn(
                "-SourceFileInbox",
                result["development_closeout"]["sp500_current_source_inbox_import_command"],
            )
            self.assertEqual(result["attention_reasons"], [])
            self.assertEqual(result["missing_outputs"], [])
            self.assertIn("# 提交前复核结果", report)
            self.assertIn("总体状态：ready", report)
            self.assertIn("候选总数：64", report)

            self.assertIn("开发收尾摘要", report)
            self.assertIn("current_module=S&P 500 成分证据补强", report)
            self.assertIn("priority_actions", report)
            self.assertIn("development_priority_actions", report)
            self.assertIn("review_data_health", report)
            self.assertIn("provide_official_constituents_csv_or_fix_network_permission", report)
            self.assertIn("medium_term_overall_completion_percent=61", report)
            self.assertIn("current_target_total_completion_percent=61", report)
            self.assertIn(
                "collaboration_execution_mode=single_codex_with_gpt55_review_checklist",
                report,
            )
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
            self.assertIn("forecast_next_one_week_evaluation_date=2026-07-07", report)
            self.assertIn("forecast_next_one_week_evaluation_count=42", report)
            self.assertIn("forecast_next_one_month_evaluation_date=2026-07-28", report)
            self.assertIn("forecast_next_one_month_evaluation_count=42", report)

    def test_review_needs_attention_when_weekly_conclusion_is_older_than_action_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            conclusion_path = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            base_time = action_items_path.stat().st_mtime
            os.utime(conclusion_path, (base_time - 20, base_time - 20))
            os.utime(action_items_path, (base_time, base_time))

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_conclusion_older_than_weekly_action_items",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_delivery_check_is_older_than_weekly_conclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            conclusion_path = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            delivery_path = root / "outputs" / "automation" / "latest_weekly_delivery_check.json"
            base_time = conclusion_path.stat().st_mtime
            os.utime(delivery_path, (base_time - 20, base_time - 20))
            os.utime(conclusion_path, (base_time, base_time))

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_delivery_check_older_than_weekly_conclusion",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_medium_term_closeout_snapshot_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            medium_path = root / "outputs" / "automation" / "latest_medium_term_goal_review.json"
            medium = json.loads(medium_path.read_text(encoding="utf-8-sig"))
            medium.pop("task_closeout_snapshot")
            write_json(medium_path, medium)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "medium_term_goal_review_missing_closeout_snapshot",
                result["attention_reasons"],
            )

    def test_review_closeout_can_select_module_by_goal_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(
                root,
                today="2026-06-28",
                max_age_days=8,
                closeout_goal_code="backtest_evidence_quality",
            )

            self.assertEqual(result["status"], "ready")
            self.assertEqual(
                result["development_closeout"]["goal_code"],
                "backtest_evidence_quality",
            )
            self.assertEqual(
                result["development_closeout"]["current_module"],
                "S&P 500 成分证据补强",
            )
            self.assertEqual(result["development_closeout"]["module_completion_percent"], 30)
            self.assertEqual(
                result["development_closeout"]["medium_term_overall_completion_percent"],
                61,
            )

    def test_review_closeout_keeps_sp500_blocker_when_selecting_other_goal_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(
                root,
                today="2026-06-28",
                max_age_days=8,
                closeout_goal_code="model_governance_handoff",
            )

            self.assertEqual(result["status"], "ready")
            self.assertEqual(
                result["development_closeout"]["goal_code"],
                "model_governance_handoff",
            )
            self.assertTrue(
                result["development_closeout"][
                    "sp500_current_source_inbox_external_input_required"
                ]
            )
            self.assertEqual(
                result["development_closeout"]["sp500_current_source_inbox_blocking_reason"],
                "official_constituents_csv_missing",
            )
            self.assertEqual(
                result["development_closeout"]["sp500_current_source_inbox_blocking_input"],
                "inputs/sp500_current_membership/official_constituents.csv",
            )

    def test_review_priority_actions_include_weekly_action_item_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            action_items["items"].append(
                {
                    "priority": 3,
                    "status": "open",
                    "action_code": "review_current_membership_source_status",
                    "category": "backtest",
                    "title": "review source",
                    "recommended_check": "review source status",
                }
            )
            action_items["item_count"] = len(action_items["items"])
            write_json(action_items_path, action_items)
            conclusion_path = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            conclusion = json.loads(conclusion_path.read_text(encoding="utf-8-sig"))
            conclusion["priority_actions"].append("review_current_membership_source_status")
            conclusion["priority_action_details"].append(
                {
                    "action": "review_current_membership_source_status",
                    "description": "review source status",
                }
            )
            write_json(conclusion_path, conclusion)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "ready")
            self.assertIn(
                "review_current_membership_source_status",
                result["priority_actions"],
            )

    def test_review_priority_actions_follow_weekly_action_items_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            automation_path = root / "outputs" / "automation" / "latest_automation_check.json"
            automation = json.loads(automation_path.read_text(encoding="utf-8-sig"))
            automation["priority_actions"] = [
                "review_manual_review_backlog",
                "review_delivery_health_issues",
                "review_data_health",
            ]
            write_json(automation_path, automation)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            action_items["items"] = [
                {
                    "priority": 1,
                    "status": "open",
                    "action_code": "review_delivery_health_issues",
                },
                {
                    "priority": 2,
                    "status": "open",
                    "action_code": "review_data_health",
                },
            ]
            action_items["item_count"] = 2
            write_json(action_items_path, action_items)
            conclusion_path = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            conclusion = json.loads(conclusion_path.read_text(encoding="utf-8-sig"))
            conclusion["priority_actions"] = [
                "review_delivery_health_issues",
                "review_data_health",
            ]
            write_json(conclusion_path, conclusion)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(
                result["priority_actions"],
                ["review_delivery_health_issues", "review_data_health"],
            )
            self.assertNotIn("review_manual_review_backlog", result["priority_actions"])

    def test_review_needs_attention_when_weekly_conclusion_misses_weekly_action_item_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            action_items["items"].append(
                {
                    "priority": 3,
                    "status": "open",
                    "action_code": "review_current_membership_source_status",
                    "category": "backtest",
                    "title": "review source",
                    "recommended_check": "review source status",
                }
            )
            action_items["item_count"] = len(action_items["items"])
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_conclusion_missing_weekly_action_item_codes",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_weekly_conclusion_official_csv_detail_omits_blocking_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
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

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_conclusion_official_csv_detail_missing_blocking_input",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_medium_term_collaboration_mode_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            medium_path = root / "outputs" / "automation" / "latest_medium_term_goal_review.json"
            medium = json.loads(medium_path.read_text(encoding="utf-8-sig"))
            medium.pop("collaboration_execution_mode")
            write_json(medium_path, medium)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "medium_term_goal_review_missing_collaboration_boundary",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_medium_term_collaboration_mode_claims_automatic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            medium_path = root / "outputs" / "automation" / "latest_medium_term_goal_review.json"
            medium = json.loads(medium_path.read_text(encoding="utf-8-sig"))
            medium["collaboration_execution_mode"] = "automatic_multi_model_collaboration"
            write_json(medium_path, medium)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "medium_term_goal_review_collaboration_mode_unsafe",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_medium_term_closeout_overall_progress_mismatches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            medium_path = root / "outputs" / "automation" / "latest_medium_term_goal_review.json"
            medium = json.loads(medium_path.read_text(encoding="utf-8-sig"))
            medium["task_closeout_snapshot"]["medium_term_overall_completion_percent"] = 60
            write_json(medium_path, medium)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "medium_term_goal_review_closeout_overall_mismatch",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_medium_term_closeout_module_progress_mismatches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            medium_path = root / "outputs" / "automation" / "latest_medium_term_goal_review.json"
            medium = json.loads(medium_path.read_text(encoding="utf-8-sig"))
            medium["task_closeout_snapshot"]["current_module"] = medium["goals"][0]["module"]
            medium["task_closeout_snapshot"]["module_completion_percent"] = 74
            write_json(medium_path, medium)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "medium_term_goal_review_closeout_module_mismatch",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_backlog_reduction_action_lacks_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            action_items["items"].append(
                {
                    "priority": 3,
                    "status": "open",
                    "action_code": "reduce_weekly_action_backlog",
                    "category": "delivery_health",
                    "title": "reduce backlog",
                    "recommended_check": "review backlog split",
                }
            )
            action_items["item_count"] = len(action_items["items"])
            write_json(action_items_path, action_items)
            delivery_path = root / "outputs" / "automation" / "latest_weekly_delivery_check.json"
            delivery = json.loads(delivery_path.read_text(encoding="utf-8-sig"))
            delivery["action_items_count"] = action_items["item_count"]
            delivery["action_items_actual_count"] = action_items["item_count"]
            write_json(delivery_path, delivery)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["input_statuses"]["weekly_action_items"], "needs_attention")
            self.assertIn(
                "weekly_action_items_missing_backlog_reduction_plan",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_backlog_reduction_plan_lacks_execution_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            action_items["items"].append(
                {
                    "priority": 3,
                    "status": "open",
                    "action_code": "reduce_weekly_action_backlog",
                    "category": "delivery_health",
                    "title": "reduce backlog",
                    "recommended_check": "review backlog split",
                }
            )
            action_items["backlog_reduction_plan"] = [
                {
                    "category": "delivery_health",
                    "count": 1,
                    "actions": ["reduce_weekly_action_backlog"],
                }
            ]
            action_items["item_count"] = len(action_items["items"])
            write_json(action_items_path, action_items)
            delivery_path = root / "outputs" / "automation" / "latest_weekly_delivery_check.json"
            delivery = json.loads(delivery_path.read_text(encoding="utf-8-sig"))
            delivery["action_items_count"] = action_items["item_count"]
            delivery["action_items_actual_count"] = action_items["item_count"]
            write_json(delivery_path, delivery)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["input_statuses"]["weekly_action_items"], "needs_attention")
            self.assertIn(
                "weekly_action_items_missing_backlog_reduction_plan",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_official_csv_backlog_plan_omits_blocking_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            action_items["backlog_reduction_plan"] = [
                {
                    "category": "backtest",
                    "count": 1,
                    "actions": ["provide_official_constituents_csv"],
                    "first_action": "provide_official_constituents_csv",
                    "target_count_after_close": 0,
                    "close_condition": "Attach verified source evidence or keep the item open.",
                }
            ]
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["input_statuses"]["weekly_action_items"], "needs_attention")
            self.assertIn(
                "weekly_action_items_missing_official_csv_backlog_blocking_input",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_checklist_or_required_output_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            (root / "docs" / "提交前复核清单.md").unlink()
            (root / "outputs" / "automation" / "latest_weekly_ops_check.json").unlink()

            from pre_submit_review import render_pre_submit_review, run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)
            report = render_pre_submit_review(result)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("missing_checklist", result["attention_reasons"])
            self.assertIn("missing_outputs", result["attention_reasons"])
            self.assertEqual(result["missing_outputs"], ["weekly_ops_check"])
            self.assertIn("提交前复核清单", report)
            self.assertIn("weekly_ops_check", report)

    def test_review_needs_attention_when_checklist_lacks_external_input_blocker_sync_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            write_text(root / "docs" / "提交前复核清单.md", "# checklist\n")

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "checklist_missing_external_input_blocker_sync_terms",
                result["attention_reasons"],
            )
            self.assertIn(
                "sp500_current_membership_source_inbox_status",
                result["checklist_missing_terms"],
            )

    def test_review_needs_attention_when_weekly_ops_lacks_quality_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            ops_path = root / "outputs" / "automation" / "latest_weekly_ops_check.json"
            ops = json.loads(ops_path.read_text(encoding="utf-8-sig"))
            del ops["automation_check_status"]
            del ops["automation_issues"]
            write_json(ops_path, ops)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_ops_check_missing_quality_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_weekly_ops_lacks_external_input_blocker_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            ops_path = root / "outputs" / "automation" / "latest_weekly_ops_check.json"
            ops = json.loads(ops_path.read_text(encoding="utf-8-sig"))
            del ops["external_input_blocker_count"]
            del ops["external_input_blockers"]
            write_json(ops_path, ops)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_ops_check_missing_quality_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_automation_check_lacks_quality_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            check_path = root / "outputs" / "automation" / "latest_automation_check.json"
            check = json.loads(check_path.read_text(encoding="utf-8-sig"))
            del check["recommended_action"]
            del check["market_candidate_counts"]
            write_json(check_path, check)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "automation_check_missing_quality_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_automation_check_lacks_external_input_blocker_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            check_path = root / "outputs" / "automation" / "latest_automation_check.json"
            check = json.loads(check_path.read_text(encoding="utf-8-sig"))
            del check["external_input_blocker_count"]
            del check["external_input_blockers"]
            write_json(check_path, check)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "automation_check_missing_quality_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_automation_check_lacks_forecast_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            check_path = root / "outputs" / "automation" / "latest_automation_check.json"
            check = json.loads(check_path.read_text(encoding="utf-8-sig"))
            del check["forecast_next_one_week_evaluation_date"]
            del check["forecast_next_one_month_evaluation_date"]
            write_json(check_path, check)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "automation_check_missing_quality_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_automation_check_lacks_forecast_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            check_path = root / "outputs" / "automation" / "latest_automation_check.json"
            check = json.loads(check_path.read_text(encoding="utf-8-sig"))
            del check["forecast_next_one_week_evaluation_count"]
            del check["forecast_next_one_month_evaluation_count"]
            write_json(check_path, check)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "automation_check_missing_quality_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_data_health_review_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            (root / "outputs" / "automation" / "latest_data_health_review.json").unlink()

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("missing_outputs", result["attention_reasons"])
            self.assertIn("data_health_review", result["missing_outputs"])

    def test_review_needs_attention_when_data_health_lacks_quality_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            review_path = root / "outputs" / "automation" / "latest_data_health_review.json"
            review = json.loads(review_path.read_text(encoding="utf-8-sig"))
            del review["refetch_gap_count"]
            del review["manual_financial_review_count"]
            write_json(review_path, review)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "data_health_review_missing_quality_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_backtest_evidence_review_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            (root / "outputs" / "automation" / "latest_backtest_evidence_review.json").unlink()

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("missing_outputs", result["attention_reasons"])
            self.assertIn("backtest_evidence_review", result["missing_outputs"])

    def test_review_needs_attention_when_membership_evidence_import_plan_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            (root / "outputs" / "automation" / "latest_membership_evidence_import_plan.json").unlink()

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("missing_outputs", result["attention_reasons"])
            self.assertIn("membership_evidence_import_plan", result["missing_outputs"])

    def test_review_needs_attention_when_membership_apply_preview_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            (root / "outputs" / "automation" / "latest_membership_evidence_apply_preview.json").unlink()

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("missing_outputs", result["attention_reasons"])
            self.assertIn("membership_evidence_apply_preview", result["missing_outputs"])

    def test_review_needs_attention_when_membership_supplement_queue_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            (root / "outputs" / "automation" / "latest_membership_evidence_supplement_queue.json").unlink()

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("missing_outputs", result["attention_reasons"])
            self.assertIn("membership_evidence_supplement_queue", result["missing_outputs"])

    def test_review_needs_attention_when_sp500_current_source_status_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            (root / "outputs" / "automation" / "latest_sp500_current_membership_sources.json").unlink()

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("missing_outputs", result["attention_reasons"])
            self.assertIn("sp500_current_membership_sources", result["missing_outputs"])

    def test_review_needs_attention_when_sp500_current_source_lacks_status_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            source_path = root / "outputs" / "automation" / "latest_sp500_current_membership_sources.json"
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            del source["next_action"]
            del source["source_file_required_columns"]
            write_json(source_path, source)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_sources_missing_quality_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_current_source_file_guidance_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            source_path = root / "outputs" / "automation" / "latest_sp500_current_membership_sources.json"
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            del source["source_file_next_command"]
            del source["source_file_acceptance_criteria"]
            write_json(source_path, source)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_sources_missing_source_file_guidance",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_current_source_inbox_status_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            source_path = root / "outputs" / "automation" / "latest_sp500_current_membership_sources.json"
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            del source["source_file_inbox"]
            del source["source_file_inbox_exists"]
            del source["source_file_validation_status"]
            write_json(source_path, source)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_sources_missing_source_file_inbox_status",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_current_source_lacks_inbox_fingerprint_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            source_path = root / "outputs" / "automation" / "latest_sp500_current_membership_sources.json"
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            del source["source_file_inbox_size_bytes"]
            del source["source_file_inbox_sha256"]
            del source["source_file_inbox_modified_at"]
            write_json(source_path, source)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_sources_missing_source_file_inbox_status",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_current_source_inbox_commands_are_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            source_path = root / "outputs" / "automation" / "latest_sp500_current_membership_sources.json"
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            del source["source_file_inbox_next_command"]
            del source["source_file_inbox_dry_run_command"]
            write_json(source_path, source)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_sources_missing_source_file_inbox_commands",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_current_source_inbox_status_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            source_path = root / "outputs" / "automation" / "latest_sp500_current_membership_sources.json"
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            inbox_path = root / source["source_file_inbox"]
            inbox_path.parent.mkdir(parents=True, exist_ok=True)
            inbox_path.write_text("Symbol,Security\nABT,Abbott Laboratories\n", encoding="utf-8-sig")
            write_json(source_path, source)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_sources_source_file_inbox_status_mismatch",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_current_source_ready_inbox_keeps_provide_csv_followup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            source_path = root / "outputs" / "automation" / "latest_sp500_current_membership_sources.json"
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            inbox_path = root / source["source_file_inbox"]
            inbox_path.parent.mkdir(parents=True, exist_ok=True)
            rows = "Symbol,Security\n" + "\n".join(
                f"T{index:03d},Test Company {index}" for index in range(400)
            )
            inbox_path.write_text(rows + "\n", encoding="utf-8-sig")
            stat = inbox_path.stat()
            source["source_file_inbox_exists"] = True
            source["source_file_validation_status"] = "ready"
            source["source_file_inbox_size_bytes"] = stat.st_size
            source["source_file_inbox_sha256"] = hashlib.sha256(inbox_path.read_bytes()).hexdigest()
            source["source_file_inbox_modified_at"] = datetime.fromtimestamp(
                stat.st_mtime,
                tz=timezone.utc,
            ).isoformat()
            source["parsed_official_ticker_count"] = 400
            source["minimum_official_ticker_count"] = 400
            source["recommended_followup"] = "provide_official_constituents_csv"
            source["next_action"] = "provide_official_constituents_csv_or_fix_network_permission"
            write_json(source_path, source)

            source_report_path = root / "outputs" / "automation" / "latest_sp500_current_membership_sources.md"
            source_report_path.write_text(
                "# S&P 500 current membership sources\n\n"
                "- as_of_date: 2026-06-28\n"
                "- status: fetch_failed\n"
                "- source_file_validation_status: ready\n",
                encoding="utf-8-sig",
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_sources_stale_provide_csv_followup",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_existing_sp500_source_inbox_lacks_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            inbox_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_inbox_status.json"
            )
            inbox_status = json.loads(inbox_status_path.read_text(encoding="utf-8-sig"))
            inbox_status.update(
                {
                    "status": "ready_for_import_preview",
                    "source_file_inbox_exists": True,
                    "source_file_validation_status": "ready",
                    "parsed_official_ticker_count": 500,
                    "external_input_required": False,
                    "blocking_reason": "",
                    "blocking_input": "",
                }
            )
            for field in (
                "source_file_inbox_size_bytes",
                "source_file_inbox_sha256",
                "source_file_inbox_modified_at",
            ):
                inbox_status.pop(field, None)
            write_json(inbox_status_path, inbox_status)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_inbox_missing_fingerprint",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_missing_sp500_source_inbox_lacks_blocking_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            inbox_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_inbox_status.json"
            )
            inbox_status = json.loads(inbox_status_path.read_text(encoding="utf-8-sig"))
            inbox_status["status"] = "missing"
            inbox_status["source_file_validation_status"] = "missing"
            inbox_status["source_file_inbox_exists"] = False
            inbox_status["parsed_official_ticker_count"] = 0
            inbox_status["external_input_required"] = False
            inbox_status["blocking_reason"] = ""
            inbox_status["blocking_input"] = ""
            write_json(inbox_status_path, inbox_status)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_inbox_missing_status_inconsistent",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_missing_sp500_source_inbox_keeps_stale_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            inbox_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_inbox_status.json"
            )
            inbox_status = json.loads(inbox_status_path.read_text(encoding="utf-8-sig"))
            inbox_status["status"] = "missing"
            inbox_status["source_file_validation_status"] = "missing"
            inbox_status["source_file_inbox_exists"] = False
            inbox_status["source_file_inbox_size_bytes"] = 12345
            inbox_status["source_file_inbox_sha256"] = "a" * 64
            inbox_status["source_file_inbox_modified_at"] = "2026-07-04T03:12:00+00:00"
            inbox_status["parsed_official_ticker_count"] = 0
            inbox_status["external_input_required"] = True
            inbox_status["blocking_reason"] = "official_constituents_csv_missing"
            inbox_status["blocking_input"] = "inputs/sp500_current_membership/official_constituents.csv"
            write_json(inbox_status_path, inbox_status)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_inbox_missing_status_inconsistent",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_source_inbox_file_state_mismatches_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            inbox_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_inbox_status.json"
            )
            inbox_status = json.loads(inbox_status_path.read_text(encoding="utf-8-sig"))
            inbox_file = root / "inputs" / "sp500_current_membership" / "official_constituents.csv"
            inbox_file.parent.mkdir(parents=True, exist_ok=True)
            inbox_file.write_text("Symbol,Security\nABT,Abbott Laboratories\n", encoding="utf-8-sig")
            inbox_status["status"] = "missing"
            inbox_status["source_file_validation_status"] = "missing"
            inbox_status["source_file_inbox"] = "inputs/sp500_current_membership/official_constituents.csv"
            inbox_status["source_file_inbox_exists"] = False
            inbox_status["source_file_inbox_size_bytes"] = 0
            inbox_status["source_file_inbox_sha256"] = ""
            inbox_status["source_file_inbox_modified_at"] = ""
            inbox_status["parsed_official_ticker_count"] = 0
            inbox_status["external_input_required"] = True
            inbox_status["blocking_reason"] = "official_constituents_csv_missing"
            inbox_status["blocking_input"] = "inputs/sp500_current_membership/official_constituents.csv"
            write_json(inbox_status_path, inbox_status)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_inbox_file_state_mismatch",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_source_inbox_fingerprint_mismatches_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            inbox_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_inbox_status.json"
            )
            inbox_status = json.loads(inbox_status_path.read_text(encoding="utf-8-sig"))
            inbox_file = root / "inputs" / "sp500_current_membership" / "official_constituents.csv"
            inbox_file.parent.mkdir(parents=True, exist_ok=True)
            inbox_file.write_text("Symbol,Security\nABT,Abbott Laboratories\n", encoding="utf-8-sig")
            inbox_status["status"] = "ready_for_import_preview"
            inbox_status["source_file_validation_status"] = "ready"
            inbox_status["source_file_inbox"] = "inputs/sp500_current_membership/official_constituents.csv"
            inbox_status["source_file_inbox_exists"] = True
            inbox_status["source_file_inbox_size_bytes"] = 999999
            inbox_status["source_file_inbox_sha256"] = "a" * 64
            inbox_status["source_file_inbox_modified_at"] = "2026-07-04T03:12:00+00:00"
            inbox_status["parsed_official_ticker_count"] = 400
            inbox_status["external_input_required"] = False
            inbox_status["blocking_reason"] = ""
            inbox_status["blocking_input"] = ""
            write_json(inbox_status_path, inbox_status)

            report_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_inbox_status.md"
            )
            report_path.write_text(
                "# S&P 500 official constituents inbox status\n\n"
                "- as_of_date: 2026-06-28\n"
                "- status: ready_for_import_preview\n"
                "- source_file_inbox_size_bytes: 999999\n"
                f"- source_file_inbox_sha256: {'a' * 64}\n"
                "- source_file_inbox_modified_at: 2026-07-04T03:12:00+00:00\n"
                "- source_file_validation_status: ready\n",
                encoding="utf-8-sig",
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_inbox_fingerprint_mismatch",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_ready_sp500_source_inbox_count_is_below_minimum(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            inbox_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_inbox_status.json"
            )
            inbox_status = json.loads(inbox_status_path.read_text(encoding="utf-8-sig"))
            inbox_file = root / "inputs" / "sp500_current_membership" / "official_constituents.csv"
            inbox_file.parent.mkdir(parents=True, exist_ok=True)
            inbox_file.write_text(
                "Symbol,Security\nABT,Abbott Laboratories\nADM,Archer-Daniels-Midland\n",
                encoding="utf-8-sig",
            )
            stat = inbox_file.stat()
            modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            sha256 = hashlib.sha256(inbox_file.read_bytes()).hexdigest()
            inbox_status["status"] = "ready_for_import_preview"
            inbox_status["source_file_validation_status"] = "ready"
            inbox_status["source_file_inbox"] = "inputs/sp500_current_membership/official_constituents.csv"
            inbox_status["source_file_inbox_exists"] = True
            inbox_status["source_file_inbox_size_bytes"] = stat.st_size
            inbox_status["source_file_inbox_sha256"] = sha256
            inbox_status["source_file_inbox_modified_at"] = modified_at
            inbox_status["parsed_official_ticker_count"] = 2
            inbox_status["minimum_official_ticker_count"] = 400
            inbox_status["external_input_required"] = False
            inbox_status["blocking_reason"] = ""
            inbox_status["blocking_input"] = ""
            inbox_status["source_file_rejection_reason"] = ""
            write_json(inbox_status_path, inbox_status)

            report_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_inbox_status.md"
            )
            report_path.write_text(
                "# S&P 500 official constituents inbox status\n\n"
                "- as_of_date: 2026-06-28\n"
                "- status: ready_for_import_preview\n"
                f"- source_file_inbox_size_bytes: {stat.st_size}\n"
                f"- source_file_inbox_sha256: {sha256}\n"
                f"- source_file_inbox_modified_at: {modified_at}\n"
                "- source_file_validation_status: ready\n",
                encoding="utf-8-sig",
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_inbox_ready_status_inconsistent",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_invalid_sp500_source_inbox_lacks_rejection_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            inbox_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_inbox_status.json"
            )
            inbox_status = json.loads(inbox_status_path.read_text(encoding="utf-8-sig"))
            inbox_status["status"] = "invalid"
            inbox_status["source_file_validation_status"] = "invalid"
            inbox_status["source_file_available_columns"] = [
                "expected_ticker",
                "intake_status",
                "required_source_url",
            ]
            inbox_status.pop("source_file_rejection_reason", None)
            write_json(inbox_status_path, inbox_status)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_inbox_missing_rejection_reason",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_incomplete_sp500_source_inbox_lacks_rejection_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            inbox_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_inbox_status.json"
            )
            inbox_status = json.loads(inbox_status_path.read_text(encoding="utf-8-sig"))
            inbox_status["status"] = "incomplete"
            inbox_status["source_file_validation_status"] = "incomplete"
            inbox_status["source_file_inbox_exists"] = True
            inbox_status["source_file_inbox_size_bytes"] = 12345
            inbox_status["source_file_inbox_sha256"] = "a" * 64
            inbox_status["source_file_inbox_modified_at"] = "2026-07-04T03:12:00+00:00"
            inbox_status["parsed_official_ticker_count"] = 2
            inbox_status["external_input_required"] = True
            inbox_status["blocking_reason"] = "official_constituents_csv_incomplete"
            inbox_status["blocking_input"] = "inputs/sp500_current_membership/official_constituents.csv"
            inbox_status.pop("source_file_rejection_reason", None)
            write_json(inbox_status_path, inbox_status)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_inbox_missing_rejection_reason",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_incomplete_sp500_source_inbox_count_is_not_below_minimum(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            inbox_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_inbox_status.json"
            )
            inbox_status = json.loads(inbox_status_path.read_text(encoding="utf-8-sig"))
            inbox_status["status"] = "incomplete"
            inbox_status["source_file_validation_status"] = "incomplete"
            inbox_status["source_file_inbox_exists"] = True
            inbox_status["source_file_inbox_size_bytes"] = 12345
            inbox_status["source_file_inbox_sha256"] = "a" * 64
            inbox_status["source_file_inbox_modified_at"] = "2026-07-04T03:12:00+00:00"
            inbox_status["parsed_official_ticker_count"] = 400
            inbox_status["minimum_official_ticker_count"] = 400
            inbox_status["source_file_rejection_reason"] = "official_ticker_count_below_minimum"
            inbox_status["external_input_required"] = True
            inbox_status["blocking_reason"] = "official_constituents_csv_incomplete"
            inbox_status["blocking_input"] = "inputs/sp500_current_membership/official_constituents.csv"
            write_json(inbox_status_path, inbox_status)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_inbox_incomplete_count_not_below_minimum",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_weekly_action_items_omit_sp500_inbox_rejection_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            inbox_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_inbox_status.json"
            )
            inbox_status = json.loads(inbox_status_path.read_text(encoding="utf-8-sig"))
            inbox_status["status"] = "invalid"
            inbox_status["source_file_validation_status"] = "invalid"
            inbox_status["source_file_rejection_reason"] = (
                "intake_template_submitted_as_official_csv"
            )
            write_json(inbox_status_path, inbox_status)

            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item.get("action_code") == "provide_official_constituents_csv":
                    item["source"] = item.get("source", "").replace(
                        "source_file_rejection_reason:intake_template_submitted_as_official_csv",
                        "source_file_rejection_reason:none",
                    )
                    item["recommended_check"] = item.get("recommended_check", "").replace(
                        "source_file_rejection_reason=intake_template_submitted_as_official_csv",
                        "source_file_rejection_reason=none",
                    )
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_action_items_missing_sp500_inbox_rejection_reason",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_weekly_action_items_omit_incomplete_sp500_inbox_rejection_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            inbox_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_inbox_status.json"
            )
            inbox_status = json.loads(inbox_status_path.read_text(encoding="utf-8-sig"))
            inbox_status["status"] = "incomplete"
            inbox_status["source_file_validation_status"] = "incomplete"
            inbox_status["source_file_rejection_reason"] = "official_ticker_count_below_minimum"
            inbox_status["parsed_official_ticker_count"] = 2
            inbox_status["minimum_official_ticker_count"] = 400
            inbox_status["external_input_required"] = True
            inbox_status["blocking_reason"] = "official_constituents_csv_incomplete"
            inbox_status["blocking_input"] = "inputs/sp500_current_membership/official_constituents.csv"
            write_json(inbox_status_path, inbox_status)

            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item.get("action_code") == "provide_official_constituents_csv":
                    item["source"] = item.get("source", "").replace(
                        "source_file_rejection_reason:intake_template_submitted_as_official_csv",
                        "source_file_rejection_reason:none",
                    )
                    item["recommended_check"] = item.get("recommended_check", "").replace(
                        "source_file_rejection_reason=intake_template_submitted_as_official_csv",
                        "source_file_rejection_reason=none",
                    )
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_action_items_missing_sp500_inbox_rejection_reason",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_weekly_action_items_omit_sp500_inbox_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            inbox_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_inbox_status.json"
            )
            inbox_status = json.loads(inbox_status_path.read_text(encoding="utf-8-sig"))
            inbox_status.update(
                {
                    "status": "incomplete",
                    "source_file_inbox_exists": True,
                    "source_file_validation_status": "incomplete",
                    "parsed_official_ticker_count": 2,
                    "minimum_official_ticker_count": 400,
                    "source_file_inbox_size_bytes": 12345,
                    "source_file_inbox_sha256": "a" * 64,
                    "source_file_inbox_modified_at": "2026-07-04T03:12:00+00:00",
                    "source_file_rejection_reason": "official_ticker_count_below_minimum",
                    "external_input_required": True,
                    "blocking_reason": "official_constituents_csv_incomplete",
                    "blocking_input": "inputs/sp500_current_membership/official_constituents.csv",
                }
            )
            write_json(inbox_status_path, inbox_status)

            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item.get("action_code") == "provide_official_constituents_csv":
                    item["source"] = (
                        item.get("source", "")
                        + "; source_file_inbox_status:incomplete"
                        + "; source_file_inbox_next_action:place_official_constituents_csv"
                        + "; source_file_inbox_parsed_official_ticker_count:2"
                        + "; source_file_inbox_intake_missing_count:50"
                        + "; source_file_rejection_reason:official_ticker_count_below_minimum"
                    )
                    item["recommended_check"] = (
                        item.get("recommended_check", "")
                        + "; inbox_status=incomplete"
                        + "; source_file_rejection_reason=official_ticker_count_below_minimum"
                    )
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_action_items_missing_sp500_inbox_fingerprint",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_ready_sp500_source_inbox_keeps_provide_csv_action_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            inbox_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_inbox_status.json"
            )
            inbox_status = json.loads(inbox_status_path.read_text(encoding="utf-8-sig"))
            inbox_file = root / "inputs" / "sp500_current_membership" / "official_constituents.csv"
            inbox_file.parent.mkdir(parents=True, exist_ok=True)
            rows = "Symbol,Security\n" + "\n".join(
                f"T{index:03d},Test Company {index}" for index in range(400)
            )
            inbox_file.write_text(rows + "\n", encoding="utf-8-sig")
            stat = inbox_file.stat()
            modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            sha256 = hashlib.sha256(inbox_file.read_bytes()).hexdigest()
            inbox_status["status"] = "ready_for_import_preview"
            inbox_status["source_file_validation_status"] = "ready"
            inbox_status["source_file_inbox"] = "inputs/sp500_current_membership/official_constituents.csv"
            inbox_status["source_file_inbox_exists"] = True
            inbox_status["source_file_inbox_size_bytes"] = stat.st_size
            inbox_status["source_file_inbox_sha256"] = sha256
            inbox_status["source_file_inbox_modified_at"] = modified_at
            inbox_status["parsed_official_ticker_count"] = 400
            inbox_status["minimum_official_ticker_count"] = 400
            inbox_status["external_input_required"] = False
            inbox_status["blocking_reason"] = ""
            inbox_status["blocking_input"] = ""
            inbox_status["source_file_rejection_reason"] = ""
            write_json(inbox_status_path, inbox_status)

            report_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_inbox_status.md"
            )
            report_path.write_text(
                "# S&P 500 official constituents inbox status\n\n"
                "- as_of_date: 2026-06-28\n"
                "- status: ready_for_import_preview\n"
                f"- source_file_inbox_size_bytes: {stat.st_size}\n"
                f"- source_file_inbox_sha256: {sha256}\n"
                f"- source_file_inbox_modified_at: {modified_at}\n"
                "- source_file_validation_status: ready\n",
                encoding="utf-8-sig",
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_action_items_stale_sp500_inbox_provide_action",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_current_source_file_request_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            (
                root
                / "outputs"
                / "automation"
                / "sp500_current_membership_source_file_request.md"
            ).unlink()

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_sources_missing_source_file_request",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_current_source_file_request_lacks_inbox_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            request_path = (
                root
                / "outputs"
                / "automation"
                / "sp500_current_membership_source_file_request.md"
            )
            request_path.write_text(
                "# S&P 500 official constituents CSV request\n\n"
                "- required_columns: Symbol or Ticker\n"
                "- dry_run_command: powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> -DryRun -SourceFile <official_constituents.csv>\n"
                "- import_command: powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> -SourceFile <official_constituents.csv>\n",
                encoding="utf-8-sig",
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_sources_missing_source_file_request_inbox_commands",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_current_source_file_request_lacks_acceptance_criteria(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            request_path = (
                root
                / "outputs"
                / "automation"
                / "sp500_current_membership_source_file_request.md"
            )
            request_path.write_text(
                "# S&P 500 official constituents CSV request\n\n"
                "- required_columns: Symbol or Ticker\n"
                "- dry_run_command: powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> -DryRun -SourceFile <official_constituents.csv>\n"
                "- import_command: powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> -SourceFile <official_constituents.csv>\n"
                "- inbox_dry_run_command: powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> -DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv\n"
                "- inbox_import_command: powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv\n",
                encoding="utf-8-sig",
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_sources_missing_source_file_request_acceptance_criteria",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_current_source_file_request_lacks_manifest_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            request_path = (
                root
                / "outputs"
                / "automation"
                / "sp500_current_membership_source_file_request.md"
            )
            request_text = request_path.read_text(encoding="utf-8-sig")
            for line in [
                "- request_manifest_schema: sp500_current_membership_source_file_request\n",
                "- request_manifest_version: 1\n",
                "- accepted_ticker_columns: Symbol, Ticker, Ticker Symbol, Constituent Ticker, Constituent Symbol\n",
                "- acceptance_criteria: has_symbol_or_ticker_column, at_least_400_tickers, official_spglobal_constituents_export\n",
                "- formal_backtest_upgrade_allowed: false\n",
                "- formal_model_change_allowed: false\n",
            ]:
                request_text = request_text.replace(line, "")
            request_path.write_text(request_text, encoding="utf-8-sig")

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_sources_missing_source_file_request_manifest_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_current_source_file_request_lacks_fingerprint_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            request_path = (
                root
                / "outputs"
                / "automation"
                / "sp500_current_membership_source_file_request.md"
            )
            request_path.write_text(
                "- request_manifest_schema: sp500_current_membership_source_file_request\n"
                "- request_manifest_version: 1\n"
                "- as_of_date: 2026-06-28\n"
                "- source_file_inbox: inputs/sp500_current_membership/official_constituents.csv\n"
                "- accepted_ticker_columns: Symbol, Ticker, Ticker Symbol, Constituent Ticker, Constituent Symbol\n"
                "- acceptance_criteria: has_symbol_or_ticker_column, at_least_400_tickers, official_spglobal_constituents_export\n"
                "- minimum_official_ticker_count: 400\n"
                "- inbox_dry_run_command: powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> -DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv\n"
                "- inbox_import_command: powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv\n"
                "- formal_backtest_upgrade_allowed: false\n"
                "- formal_model_change_allowed: false\n"
                "\n"
                "## Boundary\n"
                "- Use only the official S&P Global constituents export. Do not import the intake template as the source CSV.\n"
                "- Run the dry-run command before the import command.\n",
                encoding="utf-8-sig",
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_sources_missing_source_file_request_fingerprint_guidance",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_current_source_file_request_lacks_fingerprint_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            request_path = (
                root
                / "outputs"
                / "automation"
                / "sp500_current_membership_source_file_request.md"
            )
            request_text = request_path.read_text(encoding="utf-8-sig")
            request_text = request_text.replace("- source_file_inbox_size_bytes: 0", "- source_file_inbox_size_bytes")
            request_text = request_text.replace("- source_file_inbox_sha256: none", "- source_file_inbox_sha256")
            request_text = request_text.replace("- source_file_inbox_modified_at: none", "- source_file_inbox_modified_at")
            request_path.write_text(request_text, encoding="utf-8-sig")

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_sources_missing_source_file_request_fingerprint_guidance",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_current_source_file_request_fingerprint_values_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            request_path = (
                root
                / "outputs"
                / "automation"
                / "sp500_current_membership_source_file_request.md"
            )
            request_text = request_path.read_text(encoding="utf-8-sig")
            request_text = request_text.replace(
                "- source_file_inbox_size_bytes: 0",
                "- source_file_inbox_size_bytes: 12345",
            )
            request_text = request_text.replace(
                "- source_file_inbox_sha256: none",
                "- source_file_inbox_sha256: " + "a" * 64,
            )
            request_text = request_text.replace(
                "- source_file_inbox_modified_at: none",
                "- source_file_inbox_modified_at: 2026-07-04T03:12:00+00:00",
            )
            request_path.write_text(request_text, encoding="utf-8-sig")

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_sources_stale_source_file_request_fingerprint",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_current_source_report_fingerprint_values_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            report_path = root / "outputs" / "automation" / "latest_sp500_current_membership_sources.md"
            report_path.write_text(
                "# sp500_current_membership_sources\n\n"
                "- as_of_date: 2026-06-28\n"
                "- status: fetch_failed\n"
                "- source_file_validation_status: missing\n"
                "- source_file_inbox_size_bytes: 12345\n"
                "- source_file_inbox_sha256: none\n"
                "- source_file_inbox_modified_at: none\n",
                encoding="utf-8-sig",
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_sources_stale_report_fingerprint",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_current_source_report_status_values_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            report_path = root / "outputs" / "automation" / "latest_sp500_current_membership_sources.md"
            report_path.write_text(
                "# sp500_current_membership_sources\n\n"
                "- as_of_date: 2026-06-28\n"
                "- status: ready\n"
                "- source_file_validation_status: ready\n"
                "- source_file_inbox_size_bytes: 0\n"
                "- source_file_inbox_sha256: none\n"
                "- source_file_inbox_modified_at: none\n",
                encoding="utf-8-sig",
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_sources_stale_report_status",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_source_inbox_status_report_status_values_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            report_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_inbox_status.md"
            )
            report_path.write_text(
                "# S&P 500 official constituents inbox status\n\n"
                "- as_of_date: 2026-06-28\n"
                "- status: ready_for_import_preview\n"
                "- source_file_inbox_size_bytes: 0\n"
                "- source_file_inbox_sha256: none\n"
                "- source_file_inbox_modified_at: none\n"
                "- source_file_validation_status: ready\n",
                encoding="utf-8-sig",
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_inbox_status_stale_report_status",
                result["attention_reasons"],
            )

    def test_review_accepts_sp500_source_inbox_status_report_empty_fingerprint_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            report_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_inbox_status.md"
            )
            report_path.write_text(
                "# S&P 500 official constituents inbox status\n\n"
                "- as_of_date: 2026-06-28\n"
                "- status: missing\n"
                "- source_file_inbox_size_bytes: 0\n"
                "- source_file_inbox_sha256: \n"
                "- source_file_inbox_modified_at: \n"
                "- source_file_validation_status: missing\n",
                encoding="utf-8-sig",
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "ready")

    def test_review_needs_attention_when_sp500_source_inbox_status_report_fingerprint_values_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            report_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_inbox_status.md"
            )
            report_path.write_text(
                "# S&P 500 official constituents inbox status\n\n"
                "- as_of_date: 2026-06-28\n"
                "- status: missing\n"
                "- source_file_inbox_size_bytes: 12345\n"
                "- source_file_inbox_sha256: none\n"
                "- source_file_inbox_modified_at: none\n"
                "- source_file_validation_status: missing\n",
                encoding="utf-8-sig",
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_inbox_status_stale_report_fingerprint",
                result["attention_reasons"],
            )

    def test_review_accepts_sp500_current_source_file_request_with_absolute_inbox_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            request_path = (
                root
                / "outputs"
                / "automation"
                / "sp500_current_membership_source_file_request.md"
            )
            absolute_inbox = root / "inputs" / "sp500_current_membership" / "official_constituents.csv"
            request_text = request_path.read_text(encoding="utf-8-sig").replace(
                "inputs/sp500_current_membership/official_constituents.csv",
                str(absolute_inbox),
            )
            request_path.write_text(request_text, encoding="utf-8-sig")

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "ready")

    def test_review_needs_attention_when_sp500_current_source_file_request_lacks_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            request_path = (
                root
                / "outputs"
                / "automation"
                / "sp500_current_membership_source_file_request.md"
            )
            request_text = request_path.read_text(encoding="utf-8-sig").split("## Boundary")[0]
            request_path.write_text(request_text, encoding="utf-8-sig")

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_sources_missing_source_file_request_boundary",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_current_source_file_request_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root, as_of_date="2026-06-28")
            request_path = (
                root
                / "outputs"
                / "automation"
                / "sp500_current_membership_source_file_request.md"
            )
            request_text = request_path.read_text(encoding="utf-8-sig").replace(
                "- as_of_date: 2026-06-28",
                "- as_of_date: 2026-06-20",
            )
            request_path.write_text(request_text, encoding="utf-8-sig")

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_sources_stale_source_file_request",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_official_csv_action_item_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            action_items["items"] = [
                item
                for item in action_items["items"]
                if item["action_code"] != "provide_official_constituents_csv"
            ]
            action_items["item_count"] = len(action_items["items"])
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_official_csv_action_item_missing",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_official_csv_action_item_lacks_inbox_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item["action_code"] == "provide_official_constituents_csv":
                    item["recommended_check"] = (
                        "outputs/automation/sp500_current_membership_source_file_request.md"
                    )
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_official_csv_action_item_missing_commands",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_official_csv_action_item_lacks_inbox_status_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item["action_code"] == "provide_official_constituents_csv":
                    item["recommended_check"] = (
                        "outputs/automation/sp500_current_membership_source_file_request.md; "
                        "dry_run_command:powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                        "scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> "
                        "-DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv; "
                        "import_command:powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                        "scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> "
                        "-SourceFileInbox inputs/sp500_current_membership/official_constituents.csv"
                    )
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_official_csv_action_item_missing_inbox_status_details",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_official_csv_action_item_lacks_source_file_path_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item["action_code"] == "provide_official_constituents_csv":
                    item["recommended_check"] = item["recommended_check"].replace(
                        "source_file_request_file:outputs/automation/sp500_current_membership_source_file_request.md",
                        "outputs/automation/sp500_current_membership_source_file_request.md",
                    ).replace(
                        "source_file_inbox:inputs/sp500_current_membership/official_constituents.csv",
                        "inputs/sp500_current_membership/official_constituents.csv",
                    )
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_official_csv_action_item_missing_source_file_path_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_official_csv_action_item_source_file_path_fields_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item["action_code"] == "provide_official_constituents_csv":
                    item["recommended_check"] = item["recommended_check"].replace(
                        "source_file_inbox:inputs/sp500_current_membership/official_constituents.csv; ",
                        "source_file_inbox:inputs/sp500_current_membership/wrong_constituents.csv; ",
                    )
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_official_csv_action_item_source_file_path_fields_mismatch",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_official_csv_action_item_lacks_accepted_ticker_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item["action_code"] == "provide_official_constituents_csv":
                    item["recommended_check"] = item["recommended_check"].replace(
                        "accepted_ticker_columns:Symbol, Ticker, Ticker Symbol, Constituent Ticker, Constituent Symbol; ",
                        "",
                    )
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_official_csv_action_item_missing_accepted_ticker_columns",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_official_csv_action_item_lacks_acceptance_criteria(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item["action_code"] == "provide_official_constituents_csv":
                    item["recommended_check"] = item["recommended_check"].replace(
                        "acceptance_criteria:has_symbol_or_ticker_column, at_least_400_tickers, official_spglobal_constituents_export; ",
                        "",
                    )
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_official_csv_action_item_missing_acceptance_criteria",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_official_csv_action_item_lacks_user_agent_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            source_path = root / "outputs" / "automation" / "latest_sp500_current_membership_sources.json"
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            source["source_file_user_agent_hint"] = (
                "Set SEC_USER_AGENT or pass -UserAgent <user_agent> when retrying official "
                "S&P Global fetches through PowerShell entrypoints."
            )
            write_json(source_path, source)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_official_csv_action_item_missing_user_agent_hint",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_official_csv_action_item_lacks_machine_readable_column_and_criteria_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item["action_code"] == "provide_official_constituents_csv":
                    item["recommended_check"] = item["recommended_check"].replace(
                        "accepted_ticker_columns:Symbol, Ticker, Ticker Symbol, Constituent Ticker, Constituent Symbol; ",
                        "accepted columns include Symbol, Ticker, Ticker Symbol, Constituent Ticker, Constituent Symbol; ",
                    ).replace(
                        "acceptance_criteria:has_symbol_or_ticker_column, at_least_400_tickers, official_spglobal_constituents_export; ",
                        "criteria include has_symbol_or_ticker_column, at_least_400_tickers, official_spglobal_constituents_export; ",
                    )
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_official_csv_action_item_missing_machine_readable_column_and_criteria_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_official_csv_action_item_acceptance_criteria_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item["action_code"] == "provide_official_constituents_csv":
                    item["recommended_check"] = item["recommended_check"].replace(
                        "acceptance_criteria:has_symbol_or_ticker_column, at_least_400_tickers, official_spglobal_constituents_export; ",
                        "acceptance_criteria:has_symbol_or_ticker_column, at_least_400_tickers, official_spglobal_constituents_export, accepts_any_csv; ",
                    )
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_official_csv_action_item_acceptance_criteria_mismatch",
                result["attention_reasons"],
            )

    def test_review_accepts_official_csv_action_item_chinese_acceptance_criteria_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item["action_code"] == "provide_official_constituents_csv":
                    item["recommended_check"] = item["recommended_check"].replace(
                        "acceptance_criteria:has_symbol_or_ticker_column, at_least_400_tickers, official_spglobal_constituents_export; ",
                        "验收条件：has_symbol_or_ticker_column, at_least_400_tickers, official_spglobal_constituents_export；",
                    )
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "ready")

    def test_review_needs_attention_when_official_csv_action_item_source_lacks_acceptance_criteria(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item["action_code"] == "provide_official_constituents_csv":
                    item["source"] = item["source"].replace(
                        "source_file_acceptance_criteria:has_symbol_or_ticker_column, at_least_400_tickers, official_spglobal_constituents_export",
                        "source_file_acceptance_criteria:none",
                    )
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_official_csv_action_item_source_missing_acceptance_criteria",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_official_csv_action_item_source_acceptance_criteria_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item["action_code"] == "provide_official_constituents_csv":
                    item["source"] = item["source"].replace(
                        "source_file_acceptance_criteria:has_symbol_or_ticker_column, at_least_400_tickers, official_spglobal_constituents_export",
                        "source_file_acceptance_criteria:has_symbol_or_ticker_column, at_least_400_tickers, official_spglobal_constituents_export, accepts_any_csv",
                    )
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_official_csv_action_item_source_acceptance_criteria_mismatch",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_official_csv_action_item_source_lacks_column_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item["action_code"] == "provide_official_constituents_csv":
                    item["source"] = item["source"].replace(
                        "source_file_required_columns:Symbol, Ticker; ",
                        "",
                    ).replace(
                        "source_file_accepted_ticker_columns:Symbol, Ticker, Ticker Symbol, Constituent Ticker, Constituent Symbol; ",
                        "",
                    )
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_official_csv_action_item_source_missing_column_rules",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_official_csv_action_item_source_column_rules_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item["action_code"] == "provide_official_constituents_csv":
                    item["source"] = item["source"].replace(
                        "source_file_accepted_ticker_columns:Symbol, Ticker, Ticker Symbol, Constituent Ticker, Constituent Symbol; ",
                        "source_file_accepted_ticker_columns:Symbol, Ticker, Ticker Symbol, Constituent Ticker, Constituent Symbol, CUSIP; ",
                    )
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_official_csv_action_item_source_column_rules_mismatch",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_official_csv_action_item_source_lacks_inbox_status_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item["action_code"] == "provide_official_constituents_csv":
                    item["source"] = (
                        "status:fetch_failed; "
                        "source_file_required_columns:Symbol, Ticker; "
                        "source_file_accepted_ticker_columns:Symbol, Ticker, Ticker Symbol, Constituent Ticker, Constituent Symbol; "
                        "source_file_acceptance_criteria:has_symbol_or_ticker_column, at_least_400_tickers, official_spglobal_constituents_export"
                    )
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_official_csv_action_item_source_missing_inbox_status_details",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_official_csv_action_item_source_lacks_source_file_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item["action_code"] == "provide_official_constituents_csv":
                    item["source"] = item["source"].replace(
                        "source_file_request_file:outputs/automation/sp500_current_membership_source_file_request.md; ",
                        "",
                    ).replace(
                        "source_file_inbox:inputs/sp500_current_membership/official_constituents.csv; ",
                        "",
                    ).replace(
                        "source_file_inbox_exists:false; ",
                        "",
                    ).replace(
                        "source_file_validation_status:missing; ",
                        "",
                    )
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_official_csv_action_item_source_missing_source_file_paths",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_official_csv_action_item_source_file_paths_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item["action_code"] == "provide_official_constituents_csv":
                    item["source"] = item["source"].replace(
                        "source_file_inbox:inputs/sp500_current_membership/official_constituents.csv; ",
                        "source_file_inbox:inputs/sp500_current_membership/wrong_constituents.csv; ",
                    )
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_official_csv_action_item_source_file_paths_mismatch",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_official_csv_action_item_source_lacks_fetch_error_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item["action_code"] == "provide_official_constituents_csv":
                    item["source"] = item["source"].replace(
                        "fetch_error_type:official_source_access_denied; ",
                        "",
                    ).replace(
                        "fetch_retryable_without_environment_change:false; ",
                        "",
                    ).replace(
                        "fetch_error_next_action:provide_official_constituents_csv; ",
                        "",
                    )
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_official_csv_action_item_source_missing_fetch_error_details",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_current_source_intake_counts_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            source_path = root / "outputs" / "automation" / "latest_sp500_current_membership_sources.json"
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            source["intake_expected_count"] = 1
            source["intake_missing_count"] = 1
            source["intake_missing_tickers"] = ["ABT"]
            write_json(source_path, source)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_sources_intake_template_mismatch",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_current_source_lacks_missing_ticker_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            source_path = root / "outputs" / "automation" / "latest_sp500_current_membership_sources.json"
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            del source["missing_ticker_review_queue"]
            write_json(source_path, source)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_sources_missing_quality_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_current_source_review_queue_file_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            source_path = root / "outputs" / "automation" / "latest_sp500_current_membership_sources.json"
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            source["missing_ticker_review_queue_file"] = (
                "outputs/automation/missing_sp500_current_membership_source_review_queue.csv"
            )
            write_json(source_path, source)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_review_queue_file_missing",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_current_source_review_queue_file_mismatches_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            write_csv(
                root / "outputs" / "automation" / "sp500_current_membership_source_review_queue.csv",
                [
                    {
                        "ticker": "ABT",
                        "review_status": "open",
                        "issue_type": "missing_from_official_current_source",
                        "recommended_check": "Confirm official source coverage.",
                        "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                        "source_status": "fetch_failed",
                    }
                ],
                [
                    "ticker",
                    "review_status",
                    "issue_type",
                    "recommended_check",
                    "required_source_url",
                    "source_status",
                ],
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_review_queue_file_mismatch",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_current_source_review_queue_file_has_incomplete_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            write_csv(
                root / "outputs" / "automation" / "sp500_current_membership_source_review_queue.csv",
                [
                    {
                        "ticker": "ABT",
                        "review_status": "",
                        "issue_type": "missing_from_official_current_source",
                        "recommended_check": "Confirm official source coverage.",
                        "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                        "source_status": "fetch_failed",
                    },
                    {
                        "ticker": "ADM",
                        "review_status": "open",
                        "issue_type": "missing_from_official_current_source",
                        "recommended_check": "Confirm official source coverage.",
                        "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                        "source_status": "fetch_failed",
                    },
                ],
                [
                    "ticker",
                    "review_status",
                    "issue_type",
                    "recommended_check",
                    "required_source_url",
                    "source_status",
                ],
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_review_queue_file_invalid",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_membership_import_plan_lacks_impact_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            review_path = root / "outputs" / "automation" / "latest_membership_evidence_import_plan.json"
            review = json.loads(review_path.read_text(encoding="utf-8-sig"))
            del review["ready_to_import_weeks_affected"]
            del review["missing_source_weeks_affected"]
            write_json(review_path, review)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "membership_evidence_import_plan_missing_quality_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_membership_import_ready_but_action_item_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            review_path = root / "outputs" / "automation" / "latest_membership_evidence_import_plan.json"
            review = json.loads(review_path.read_text(encoding="utf-8-sig"))
            review["ready_to_import_count"] = 2
            review["ready_to_import_weeks_affected"] = 210
            review["missing_source_count"] = 48
            write_json(review_path, review)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "membership_evidence_apply_preview_action_item_missing",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_current_source_review_action_item_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            source_path = root / "outputs" / "automation" / "latest_sp500_current_membership_sources.json"
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            source["status"] = "ready"
            source["matched_count"] = 1
            source["missing_count"] = 1
            source["next_action"] = "review_missing_tickers"
            source["recommended_followup"] = "review_current_membership_source_status"
            write_json(source_path, source)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_action_item_missing",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_current_source_import_preview_action_item_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            source_path = root / "outputs" / "automation" / "latest_sp500_current_membership_sources.json"
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            source["status"] = "ready"
            source["matched_count"] = 1
            source["missing_count"] = 1
            source["intake_coverage_status"] = "partial"
            source["intake_matched_count"] = 1
            source["intake_missing_count"] = 1
            source["recommended_followup"] = "run_membership_evidence_import_plan_then_apply_preview"
            source["next_action"] = "run_membership_evidence_import_plan_then_apply_preview"
            write_json(source_path, source)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_import_preview_action_item_missing",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_current_source_import_plan_action_item_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            source_path = root / "outputs" / "automation" / "latest_sp500_current_membership_sources.json"
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            source["status"] = "ready"
            source["matched_count"] = 1
            source["missing_count"] = 1
            source["intake_coverage_status"] = "partial"
            source["intake_matched_count"] = 1
            source["intake_missing_count"] = 1
            source["recommended_followup"] = "run_membership_evidence_import_plan_then_apply_preview"
            source["next_action"] = "run_membership_evidence_import_plan_then_apply_preview"
            write_json(source_path, source)
            action_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_path.read_text(encoding="utf-8-sig"))
            action_items["items"].append(
                {
                    "priority": 3,
                    "status": "open",
                    "action_code": "run_membership_evidence_apply_preview",
                    "category": "backtest",
                    "title": "Run membership evidence apply preview",
                    "source": "next_action:run_membership_evidence_import_plan_then_apply_preview",
                    "recommended_check": (
                        "Run scripts/run_membership_evidence_apply_preview.ps1 and compare "
                        "latest_membership_evidence_apply_preview.md; keep this as preview only."
                    ),
                }
            )
            action_items["item_count"] = len(action_items["items"])
            write_json(action_path, action_items)
            conclusion_path = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            conclusion = json.loads(conclusion_path.read_text(encoding="utf-8-sig"))
            conclusion["priority_actions"].append("run_membership_evidence_apply_preview")
            conclusion["priority_action_details"].append(
                {
                    "action": "run_membership_evidence_apply_preview",
                    "description": action_items["items"][-1]["recommended_check"],
                }
            )
            write_json(conclusion_path, conclusion)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_import_plan_action_item_missing",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_current_source_review_action_item_omits_queue_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            source_path = root / "outputs" / "automation" / "latest_sp500_current_membership_sources.json"
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            source["status"] = "ready"
            source["matched_count"] = 1
            source["missing_count"] = 1
            source["next_action"] = "review_missing_tickers"
            source["recommended_followup"] = "review_current_membership_source_status"
            write_json(source_path, source)
            action_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_path.read_text(encoding="utf-8-sig"))
            action_items["items"].append(
                {
                    "priority": 3,
                    "status": "open",
                    "action_code": "review_current_membership_source_status",
                    "category": "backtest",
                    "title": "核对当前 S&P 500 成分来源缺口",
                    "recommended_check": "核对 latest_sp500_current_membership_sources.json 中的缺失 ticker。",
                }
            )
            action_items["item_count"] = len(action_items["items"])
            write_json(action_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_action_item_missing_review_queue_file",
                result["attention_reasons"],
            )

    def test_review_exposes_membership_closed_loop_when_official_source_fixture_is_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            as_of_date = "2026-06-28"
            write_ready_review_inputs(root, as_of_date=as_of_date)
            source_url = "https://www.spglobal.com/spdji/en/indices/equity/sp-500/"

            template = root / "outputs" / "automation" / "us_sp500_current_membership_sources_template.csv"
            official_export = root / "official_constituents.csv"
            intake = root / "outputs" / "automation" / "sp500_current_membership_source_intake_template.csv"
            source_pack = root / "data" / "config" / "us_sp500_current_membership_sources.csv"
            source_json = root / "outputs" / "automation" / "latest_sp500_current_membership_sources.json"
            write_csv(
                template,
                [
                    {
                        "ticker": "ABT",
                        "membership_evidence": "verified",
                        "membership_source_url": "",
                        "source_as_of_date": "",
                        "notes": "",
                    }
                ],
                ["ticker", "membership_evidence", "membership_source_url", "source_as_of_date", "notes"],
            )
            official_rows = [{"Symbol": "ABT", "Security": "Abbott Laboratories"}]
            official_rows.extend(
                {"Symbol": f"T{index:03d}", "Security": f"Test Company {index}"}
                for index in range(399)
            )
            write_csv(official_export, official_rows, ["Symbol", "Security"])
            write_csv(
                intake,
                [
                    {
                        "expected_ticker": "ABT",
                        "intake_status": "official_export_required",
                        "required_source_url": source_url,
                        "required_source_columns": "Symbol or Ticker",
                        "notes": "",
                    }
                ],
                ["expected_ticker", "intake_status", "required_source_url", "required_source_columns", "notes"],
            )

            from sp500_current_membership_sources import (
                add_intake_coverage,
                build_current_membership_sources_from_tickers,
                parse_official_current_tickers_from_source_file,
                write_json as write_source_json,
                write_sources_csv,
            )

            source_payload = build_current_membership_sources_from_tickers(
                template,
                parse_official_current_tickers_from_source_file(official_export),
                source_url,
                as_of_date=as_of_date,
            )
            add_intake_coverage(source_payload, intake)
            write_sources_csv(source_payload, source_pack)
            write_source_json(source_payload, source_json)

            gaps = root / "outputs" / "automation" / "latest_membership_evidence_gaps.json"
            write_json(
                gaps,
                {
                    "schema": "membership_evidence_gap_report",
                    "version": 1,
                    "gap_count": 1,
                    "returned_gap_count": 1,
                    "gaps": [
                        {
                            "rank": 1,
                            "ticker": "ABT",
                            "company_name": "Abbott Laboratories",
                            "effective_date": "1957-03-04",
                            "current_evidence": "secondary",
                            "weeks_affected": 2,
                            "recommended_action": "supplement_official_spglobal_source",
                        }
                    ],
                },
            )

            from membership_evidence_import_plan import (
                build_membership_evidence_import_plan,
                write_json as write_plan_json,
            )

            plan_json = root / "outputs" / "automation" / "latest_membership_evidence_import_plan.json"
            plan_payload = build_membership_evidence_import_plan(gaps, source_pack, as_of_date=as_of_date)
            write_plan_json(plan_payload, plan_json)

            membership = root / "outputs" / "backtests" / "us_3y_weekly" / "historical_membership.csv"
            write_csv(
                membership,
                [
                    {
                        "week": "2026-06-21",
                        "market": "US",
                        "ticker": "ABT",
                        "cik": "0000001800",
                        "company_name": "Abbott Laboratories",
                        "industry": "Health Care",
                        "gics_sub_industry": "Health Care Equipment",
                        "date_added": "1957-03-04",
                        "effective_date": "1957-03-04",
                        "membership_evidence": "secondary",
                        "membership_source_url": "data/config/us_universe_symbols.csv",
                        "available_at": "2026-06-21",
                    },
                    {
                        "week": "2026-06-28",
                        "market": "US",
                        "ticker": "ABT",
                        "cik": "0000001800",
                        "company_name": "Abbott Laboratories",
                        "industry": "Health Care",
                        "gics_sub_industry": "Health Care Equipment",
                        "date_added": "1957-03-04",
                        "effective_date": "1957-03-04",
                        "membership_evidence": "secondary",
                        "membership_source_url": "data/config/us_universe_symbols.csv",
                        "available_at": "2026-06-28",
                    },
                ],
                [
                    "week",
                    "market",
                    "ticker",
                    "cik",
                    "company_name",
                    "industry",
                    "gics_sub_industry",
                    "date_added",
                    "effective_date",
                    "membership_evidence",
                    "membership_source_url",
                    "available_at",
                ],
            )

            from membership_evidence_apply_preview import build_apply_preview, write_json as write_preview_json

            preview_json = root / "outputs" / "automation" / "latest_membership_evidence_apply_preview.json"
            preview_payload = build_apply_preview(membership, source_pack, as_of_date=as_of_date)
            write_preview_json(preview_payload, preview_json)

            manifest = root / "outputs" / "automation" / "latest_self_analysis_manifest.json"
            write_json(
                manifest,
                {
                    "manifest_schema": "self_analysis_manifest",
                    "manifest_version": 1,
                    "as_of_date": as_of_date,
                    "automation_status": "manual_review_needed",
                    "automation_priority_actions": ["review_data_health"],
                    "data_health_status": "manual_review_needed",
                },
            )

            from weekly_action_items import build_weekly_action_items, write_json as write_action_json

            action_items_json = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_payload = build_weekly_action_items(manifest, membership_import_plan=plan_json)
            write_action_json(action_payload, action_items_json)
            conclusion_path = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            conclusion = json.loads(conclusion_path.read_text(encoding="utf-8-sig"))
            for item in action_payload["items"]:
                action_code = item["action_code"]
                if action_code not in conclusion["priority_actions"]:
                    conclusion["priority_actions"].append(action_code)
                    conclusion["priority_action_details"].append(
                        {
                            "action": action_code,
                            "description": item.get("recommended_check", ""),
                        }
                    )
            write_json(conclusion_path, conclusion)
            delivery_path = root / "outputs" / "automation" / "latest_weekly_delivery_check.json"
            delivery = json.loads(delivery_path.read_text(encoding="utf-8-sig"))
            delivery["action_items_count"] = action_payload["item_count"]
            write_json(delivery_path, delivery)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today=as_of_date, max_age_days=8)

            self.assertEqual(source_payload["recommended_followup"], "run_membership_evidence_import_plan_then_apply_preview")
            self.assertEqual(plan_payload["ready_to_import_count"], 1)
            self.assertEqual(preview_payload["preview_row_count"], 2)
            self.assertIn(
                "run_membership_evidence_apply_preview",
                [item["action_code"] for item in action_payload["items"]],
            )
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["membership_evidence_ready_to_import_count"], 1)
            self.assertEqual(result["membership_evidence_preview_row_count"], 2)
            self.assertTrue(result["membership_evidence_preview_action_item_present"])

    def test_review_needs_attention_when_backtest_evidence_lacks_quality_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            review_path = root / "outputs" / "automation" / "latest_backtest_evidence_review.json"
            review = json.loads(review_path.read_text(encoding="utf-8-sig"))
            del review["verified_membership_ratio"]
            del review["weak_evidence_weeks"]
            write_json(review_path, review)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "backtest_evidence_review_missing_quality_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_candidate_findings_review_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            (root / "outputs" / "automation" / "latest_candidate_findings_review.json").unlink()

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("missing_outputs", result["attention_reasons"])
            self.assertIn("candidate_findings_review", result["missing_outputs"])

    def test_review_needs_attention_when_forecast_performance_review_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            (root / "outputs" / "automation" / "latest_forecast_performance_review.json").unlink()

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("missing_outputs", result["attention_reasons"])
            self.assertIn("forecast_performance_review", result["missing_outputs"])

    def test_review_needs_attention_when_candidate_findings_have_missing_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            review_path = root / "outputs" / "automation" / "latest_candidate_findings_review.json"
            review = json.loads(review_path.read_text(encoding="utf-8-sig"))
            review["status"] = "needs_attention"
            review["missing_field_count"] = 3
            write_json(review_path, review)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("candidate_findings_review_missing_fields", result["attention_reasons"])

    def test_review_needs_attention_when_candidate_findings_lack_quality_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            review_path = root / "outputs" / "automation" / "latest_candidate_findings_review.json"
            review = json.loads(review_path.read_text(encoding="utf-8-sig"))
            del review["field_complete_count"]
            del review["risk_coverage_count"]
            write_json(review_path, review)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "candidate_findings_review_missing_quality_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_forecast_review_missing_market_or_allows_model_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            review_path = root / "outputs" / "automation" / "latest_forecast_performance_review.json"
            review = json.loads(review_path.read_text(encoding="utf-8-sig"))
            review["status"] = "needs_attention"
            review["missing_market_count"] = 1
            review["formal_model_change_allowed"] = True
            write_json(review_path, review)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("forecast_performance_review_not_acceptable", result["attention_reasons"])
            self.assertIn("forecast_performance_review_missing_market", result["attention_reasons"])
            self.assertIn("forecast_performance_formal_model_change_unsafe", result["attention_reasons"])

    def test_review_needs_attention_when_forecast_latest_short_signals_are_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            review_path = root / "outputs" / "automation" / "latest_forecast_performance_review.json"
            review = json.loads(review_path.read_text(encoding="utf-8-sig"))
            review["status"] = "needs_attention"
            review["latest_short_signal_missing_count"] = 2
            write_json(review_path, review)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("forecast_performance_review_not_acceptable", result["attention_reasons"])
            self.assertIn("forecast_performance_latest_short_signals_missing", result["attention_reasons"])

    def test_review_needs_attention_when_forecast_review_lacks_latest_legacy_tracking_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            review_path = root / "outputs" / "automation" / "latest_forecast_performance_review.json"
            review = json.loads(review_path.read_text(encoding="utf-8-sig"))
            del review["latest_prediction_unavailable_count"]
            del review["legacy_short_signal_missing_count"]
            write_json(review_path, review)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "forecast_performance_review_missing_tracking_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_forecast_review_lacks_maturity_schedule_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            review_path = root / "outputs" / "automation" / "latest_forecast_performance_review.json"
            review = json.loads(review_path.read_text(encoding="utf-8-sig"))
            del review["next_one_week_evaluation_date"]
            write_json(review_path, review)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "forecast_performance_review_missing_tracking_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_forecast_review_lacks_maturity_count_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            review_path = root / "outputs" / "automation" / "latest_forecast_performance_review.json"
            review = json.loads(review_path.read_text(encoding="utf-8-sig"))
            del review["next_one_week_evaluation_count"]
            write_json(review_path, review)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "forecast_performance_review_missing_tracking_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_one_week_shadow_review_is_missing_or_unsafe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            shadow_path = root / "outputs" / "automation" / "latest_one_week_forecast_shadow_review.json"
            shadow = json.loads(shadow_path.read_text(encoding="utf-8-sig"))
            shadow["formal_model_change_allowed"] = True
            write_json(shadow_path, shadow)
            (root / "outputs" / "automation" / "latest_one_week_forecast_calibration_review.json").unlink()

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("one_week_forecast_shadow_formal_model_change_unsafe", result["attention_reasons"])
            self.assertIn("one_week_forecast_calibration_review", result["missing_outputs"])

    def test_review_needs_attention_when_backtest_review_allows_upgrade_with_weak_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            review_path = root / "outputs" / "automation" / "latest_backtest_evidence_review.json"
            review = json.loads(review_path.read_text(encoding="utf-8-sig"))
            review["formal_model_upgrade_allowed"] = True
            review["weak_evidence_rows"] = 3382
            write_json(review_path, review)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("backtest_evidence_upgrade_gate_unsafe", result["attention_reasons"])

    def test_review_needs_attention_when_governance_doc_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            (root / "docs" / "中期目标与模型协作规范.md").unlink()

            from pre_submit_review import render_pre_submit_review, run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)
            report = render_pre_submit_review(result)

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["governance_status"], "missing")
            self.assertIn("missing_governance_doc", result["attention_reasons"])
            self.assertIn("中期目标与模型协作规范", report)

    def test_review_needs_attention_when_governance_doc_missing_required_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            write_text(root / "docs" / "中期目标与模型协作规范.md", "# incomplete\n")

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["governance_status"], "needs_attention")
            self.assertIn("governance_doc_missing_terms", result["attention_reasons"])
            self.assertIn("gpt5.3-codex-spark", result["governance_missing_terms"])

    def test_review_needs_attention_when_governance_doc_missing_combined_development_habits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            write_text(
                root / "docs" / "中期目标与模型协作规范.md",
                "\n".join(
                    [
                        "# 中期目标与模型协作规范",
                        "gpt5.3-codex-spark 负责快速迭代。",
                        "gpt5.5 负责关键复核和正式收口。",
                        "组合开发习惯要求保留证据三件套。",
                        "所有模型优化建议先进入影子层。",
                        "不得自动修改正式模型参数。",
                    ]
                )
                + "\n",
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["governance_status"], "needs_attention")
            self.assertIn("governance_doc_missing_terms", result["attention_reasons"])
            self.assertIn("可回放", result["governance_missing_terms"])
            self.assertIn("回退策略", result["governance_missing_terms"])
            self.assertIn("收敛迭代", result["governance_missing_terms"])

    def test_review_needs_attention_when_model_handoff_review_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            (
                root
                / "outputs"
                / "automation"
                / "latest_model_handoff_review.json"
            ).unlink()

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("missing_outputs", result["attention_reasons"])
            self.assertIn("model_handoff_review", result["missing_outputs"])

    def test_review_needs_attention_when_model_handoff_closeout_does_not_match_medium_term(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            handoff_path = (
                root
                / "outputs"
                / "automation"
                / "latest_model_handoff_review.json"
            )
            handoff = json.loads(handoff_path.read_text(encoding="utf-8-sig"))
            handoff["goal_code"] = "model_governance_handoff"
            handoff["current_module"] = "模型治理与多模型协作准备"
            handoff["module_completion_percent"] = 75
            write_json(handoff_path, handoff)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "model_handoff_review_closeout_mismatch",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_model_handoff_validation_commands_are_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            handoff_path = (
                root
                / "outputs"
                / "automation"
                / "latest_model_handoff_review.json"
            )
            handoff = json.loads(handoff_path.read_text(encoding="utf-8-sig"))
            handoff["validation_commands"] = []
            write_json(handoff_path, handoff)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "model_handoff_review_invalid_validation_commands",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_model_handoff_lacks_pre_submit_validation_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            handoff_path = (
                root
                / "outputs"
                / "automation"
                / "latest_model_handoff_review.json"
            )
            handoff = json.loads(handoff_path.read_text(encoding="utf-8-sig"))
            handoff["validation_commands"] = ["python -m unittest tests.test_model_handoff_review"]
            write_json(handoff_path, handoff)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "model_handoff_review_missing_pre_submit_validation_command",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_model_handoff_lacks_test_validation_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            handoff_path = (
                root
                / "outputs"
                / "automation"
                / "latest_model_handoff_review.json"
            )
            handoff = json.loads(handoff_path.read_text(encoding="utf-8-sig"))
            handoff["validation_commands"] = [
                "powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_pre_submit_review.ps1 -MaxAgeDays 8"
            ]
            write_json(handoff_path, handoff)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "model_handoff_review_missing_test_validation_command",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_model_handoff_lacks_sp500_source_request_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            handoff_path = (
                root
                / "outputs"
                / "automation"
                / "latest_model_handoff_review.json"
            )
            handoff = json.loads(handoff_path.read_text(encoding="utf-8-sig"))
            for field in [
                "sp500_current_source_request_file",
                "sp500_current_source_request_manifest_status",
                "sp500_current_source_inbox_dry_run_command",
                "sp500_current_source_inbox_import_command",
                "sp500_current_source_acceptance_criteria",
            ]:
                handoff.pop(field, None)
            write_json(handoff_path, handoff)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "model_handoff_review_missing_sp500_source_request_details",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_model_handoff_lacks_sp500_source_inbox_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            handoff_path = (
                root
                / "outputs"
                / "automation"
                / "latest_model_handoff_review.json"
            )
            handoff = json.loads(handoff_path.read_text(encoding="utf-8-sig"))
            for field in [
                "sp500_current_source_inbox_size_bytes",
                "sp500_current_source_inbox_sha256",
                "sp500_current_source_inbox_modified_at",
            ]:
                handoff.pop(field, None)
            write_json(handoff_path, handoff)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "model_handoff_review_missing_sp500_source_inbox_fingerprint",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_model_handoff_lacks_forecast_maturity_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            handoff_path = (
                root
                / "outputs"
                / "automation"
                / "latest_model_handoff_review.json"
            )
            handoff = json.loads(handoff_path.read_text(encoding="utf-8-sig"))
            for field in [
                "forecast_performance_status",
                "forecast_performance_recommended_action",
                "forecast_mature_evaluations",
                "forecast_one_week_mature",
                "forecast_one_month_mature",
                "forecast_next_one_week_evaluation_date",
                "forecast_next_one_week_evaluation_count",
                "forecast_next_one_month_evaluation_date",
                "forecast_next_one_month_evaluation_count",
                "forecast_formal_model_change_allowed",
            ]:
                handoff.pop(field, None)
            write_json(handoff_path, handoff)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "model_handoff_review_missing_forecast_maturity_details",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_model_handoff_lacks_forecast_maturity_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            handoff_path = (
                root
                / "outputs"
                / "automation"
                / "latest_model_handoff_review.json"
            )
            handoff = json.loads(handoff_path.read_text(encoding="utf-8-sig"))
            handoff.pop("forecast_next_one_week_evaluation_count", None)
            handoff.pop("forecast_next_one_month_evaluation_count", None)
            write_json(handoff_path, handoff)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "model_handoff_review_missing_forecast_maturity_details",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sample_accumulation_action_lacks_forecast_maturity_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item["action_code"] == "continue_sample_accumulation":
                    item["source"] = "model_audit_status:sample_accumulating"
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_action_items_missing_forecast_maturity_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sample_accumulation_action_lacks_forecast_maturity_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            action_items_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            action_items = json.loads(action_items_path.read_text(encoding="utf-8-sig"))
            for item in action_items["items"]:
                if item["action_code"] == "continue_sample_accumulation":
                    item["source"] = item["source"].replace(
                        "forecast_next_one_week_evaluation_count:42; ",
                        "",
                    )
            write_json(action_items_path, action_items)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_action_items_missing_forecast_maturity_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_source_review_status_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_status.json"
            ).unlink()

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("missing_outputs", result["attention_reasons"])
            self.assertIn(
                "sp500_current_membership_source_review_status",
                result["missing_outputs"],
            )

    def test_review_needs_attention_when_sp500_source_review_status_queue_file_mismatches_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            review_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_status.json"
            )
            review_status = json.loads(review_status_path.read_text(encoding="utf-8-sig"))
            review_status["queue_total_count"] = 1
            review_status["open_count"] = 1
            review_status["resolved_count"] = 0
            review_status["open_items"] = [{"ticker": "ZZZ", "review_status": "open"}]
            write_json(review_status_path, review_status)
            write_csv(
                root
                / "outputs"
                / "automation"
                / "sp500_current_membership_source_review_decisions_template.csv",
                [
                    {
                        "ticker": "ZZZ",
                        "review_decision": "",
                        "official_source_checked": "",
                        "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                        "issue_type": "missing_from_official_current_source",
                        "recommended_check": "Confirm official coverage.",
                        "decision_notes": "",
                    }
                ],
                [
                    "ticker",
                    "review_decision",
                    "official_source_checked",
                    "required_source_url",
                    "issue_type",
                    "recommended_check",
                    "decision_notes",
                ],
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_review_status_queue_file_mismatch",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_source_review_status_report_summary_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            report_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_status.md"
            )
            report_path.write_text(
                "# S&P 500 current membership source review status\n\n"
                "- queue_total_count=999\n"
                "- open_count=0\n"
                "- resolved_count=999\n"
                "- review_decision_status=ready_to_apply\n"
                "- manual_decision_next_step=apply_review_decisions_to_queue\n"
                "- decision_ready_to_apply_count=999\n"
                "- decisions_template_status=mismatch\n",
                encoding="utf-8-sig",
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_review_status_stale_report_summary",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_source_review_status_report_status_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            report_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_status.md"
            )
            report_path.write_text(
                "# S&P 500 current membership source review status\n\n"
                "- 状态：clear\n"
                "- queue_total_count=2\n"
                "- open_count=2\n"
                "- resolved_count=0\n"
                "- review_decision_status=missing\n"
                "- manual_decision_next_step=fill_decisions_template\n"
                "- decision_ready_to_apply_count=0\n"
                "- decisions_template_status=ready\n"
                "- 下一步：review_open_queue_items\n",
                encoding="utf-8-sig",
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_review_status_stale_report_summary",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_source_review_status_report_pending_tickers_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            report_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_status.md"
            )
            report_path.write_text(
                "# S&P 500 current membership source review status\n\n"
                "- 状态：review_needed\n"
                "- queue_total_count=2\n"
                "- open_count=2\n"
                "- resolved_count=0\n"
                "- review_decision_status=missing\n"
                "- manual_decision_next_step=fill_decisions_template\n"
                "- decision_ready_to_apply_count=0\n"
                "- decision_ready_to_apply_tickers=\n"
                "- decision_pending_tickers=ZZZ\n"
                "- decisions_template_status=ready\n"
                "- 下一步：review_open_queue_items\n",
                encoding="utf-8-sig",
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_review_status_stale_report_summary",
                result["attention_reasons"],
            )

    def test_review_accepts_sp500_source_review_status_report_zero_summary_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            report_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_status.md"
            )
            report_path.write_text(
                "# S&P 500 current membership source review status\n\n"
                "- 状态：review_needed\n"
                "- queue_total_count=2\n"
                "- open_count=2\n"
                "- resolved_count=0\n"
                "- review_decision_status=missing\n"
                "- manual_decision_next_step=fill_decisions_template\n"
                "- decision_ready_to_apply_count=0\n"
                "- decision_ready_to_apply_tickers=\n"
                "- decision_pending_tickers=ABT, ADM\n"
                "- decisions_template_status=ready\n"
                "- 下一步：review_open_queue_items\n",
                encoding="utf-8-sig",
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "ready")

    def test_review_needs_attention_when_sp500_source_review_decision_guidance_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            review_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_status.json"
            )
            review_status = json.loads(review_status_path.read_text(encoding="utf-8-sig"))
            review_status.pop("decision_options")
            review_status.pop("decision_required_fields")
            review_status.pop("manual_decision_instructions")
            write_json(review_status_path, review_status)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_review_missing_decision_guidance",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_source_review_decisions_template_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            review_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_status.json"
            )
            review_status = json.loads(review_status_path.read_text(encoding="utf-8-sig"))
            review_status["decisions_template_file"] = (
                "outputs/automation/sp500_current_membership_source_review_decisions_template.csv"
            )
            write_json(review_status_path, review_status)
            (
                root
                / "outputs"
                / "automation"
                / "sp500_current_membership_source_review_decisions_template.csv"
            ).unlink()

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_review_decisions_template_missing",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_source_review_decisions_template_has_missing_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            write_csv(
                root
                / "outputs"
                / "automation"
                / "sp500_current_membership_source_review_decisions_template.csv",
                [
                    {
                        "ticker": "ZZZ",
                        "review_decision": "",
                        "official_source_checked": "",
                    }
                ],
                [
                    "ticker",
                    "review_decision",
                    "official_source_checked",
                ],
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_review_decisions_template_invalid",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_source_review_decisions_template_missing_open_ticker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            write_csv(
                root
                / "outputs"
                / "automation"
                / "sp500_current_membership_source_review_decisions_template.csv",
                [
                    {
                        "ticker": "ABC",
                        "review_decision": "",
                        "official_source_checked": "",
                        "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                        "issue_type": "missing_from_official_current_source",
                        "recommended_check": "Confirm official coverage.",
                        "decision_notes": "",
                    }
                ],
                [
                    "ticker",
                    "review_decision",
                    "official_source_checked",
                    "required_source_url",
                    "issue_type",
                    "recommended_check",
                    "decision_notes",
                ],
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_review_decisions_template_mismatch",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_source_review_decisions_are_ready_but_apply_summary_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            review_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_status.json"
            )
            review_status = json.loads(review_status_path.read_text(encoding="utf-8-sig"))
            review_status["next_action"] = "apply_review_decisions_to_queue"
            review_status["review_decision_status"] = "ready_to_apply"
            review_status["decision_ready_to_apply_count"] = 1
            review_status["decision_file_exists"] = True
            write_json(review_status_path, review_status)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_review_decision_apply_missing",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_source_review_decision_file_mismatches_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            review_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_status.json"
            )
            review_status = json.loads(review_status_path.read_text(encoding="utf-8-sig"))
            review_status["next_action"] = "apply_review_decisions_to_queue"
            review_status["review_decision_status"] = "ready_to_apply"
            review_status["decision_ready_to_apply_count"] = 1
            review_status["decision_pending_count"] = 1
            review_status["decision_total_count"] = 1
            review_status["decision_matched_open_count"] = 1
            review_status["decision_invalid_count"] = 0
            review_status["decision_ready_to_apply_tickers"] = ["ABT"]
            review_status["decision_pending_tickers"] = ["ADM"]
            review_status["decision_file_exists"] = True
            review_status["decision_file"] = "outputs/automation/sp500_current_membership_source_review_decisions.csv"
            write_json(review_status_path, review_status)
            write_csv(
                root
                / "outputs"
                / "automation"
                / "sp500_current_membership_source_review_decisions.csv",
                [],
                [
                    "ticker",
                    "review_decision",
                    "official_source_checked",
                    "required_source_url",
                    "issue_type",
                    "recommended_check",
                    "decision_notes",
                ],
            )
            write_json(
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_decision_apply.json",
                {
                    "apply_schema": "sp500_current_membership_source_review_decision_apply",
                    "apply_version": 1,
                    "status": "dry_run",
                    "applied_count": 1,
                    "skipped_pending_count": 0,
                    "skipped_invalid_count": 0,
                    "formal_backtest_upgrade_allowed": False,
                },
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_review_status_decision_file_mismatch",
                result["attention_reasons"],
            )

    def test_review_is_ready_when_sp500_source_review_decisions_have_dry_run_apply_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            review_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_status.json"
            )
            review_status = json.loads(review_status_path.read_text(encoding="utf-8-sig"))
            review_status["next_action"] = "apply_review_decisions_to_queue"
            review_status["review_decision_status"] = "ready_to_apply"
            review_status["decision_ready_to_apply_count"] = 1
            review_status["decision_file_exists"] = True
            write_json(review_status_path, review_status)
            write_json(
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_decision_apply.json",
                {
                    "apply_schema": "sp500_current_membership_source_review_decision_apply",
                    "apply_version": 1,
                    "status": "dry_run",
                    "applied_count": 1,
                    "skipped_pending_count": 0,
                    "skipped_invalid_count": 0,
                    "formal_backtest_upgrade_allowed": False,
                },
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "ready")

    def test_review_needs_attention_when_sp500_source_review_decision_apply_report_mismatches_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            review_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_status.json"
            )
            review_status = json.loads(review_status_path.read_text(encoding="utf-8-sig"))
            review_status["next_action"] = "apply_review_decisions_to_queue"
            review_status["review_decision_status"] = "ready_to_apply"
            review_status["decision_ready_to_apply_count"] = 1
            review_status["decision_file_exists"] = True
            write_json(review_status_path, review_status)
            write_json(
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_decision_apply.json",
                {
                    "apply_schema": "sp500_current_membership_source_review_decision_apply",
                    "apply_version": 1,
                    "status": "dry_run",
                    "applied_count": 1,
                    "skipped_pending_count": 0,
                    "skipped_invalid_count": 0,
                    "formal_backtest_upgrade_allowed": False,
                },
            )
            (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_decision_apply.md"
            ).write_text(
                "# S&P 500 current membership source review decision apply\n\n"
                "- applied_count=0\n"
                "- skipped_pending_count=1\n"
                "- skipped_invalid_count=0\n",
                encoding="utf-8-sig",
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_review_decision_apply_stale_report_summary",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_source_review_decision_apply_report_status_mismatches_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            review_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_status.json"
            )
            review_status = json.loads(review_status_path.read_text(encoding="utf-8-sig"))
            review_status["next_action"] = "apply_review_decisions_to_queue"
            review_status["review_decision_status"] = "ready_to_apply"
            review_status["decision_ready_to_apply_count"] = 1
            review_status["decision_file_exists"] = True
            write_json(review_status_path, review_status)
            write_json(
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_decision_apply.json",
                {
                    "apply_schema": "sp500_current_membership_source_review_decision_apply",
                    "apply_version": 1,
                    "status": "dry_run",
                    "applied_count": 1,
                    "skipped_pending_count": 0,
                    "skipped_invalid_count": 0,
                    "formal_backtest_upgrade_allowed": False,
                },
            )
            (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_decision_apply.md"
            ).write_text(
                "# S&P 500 current membership source review decision apply\n\n"
                "- 状态：applied\n"
                "- applied_count=1\n"
                "- skipped_pending_count=0\n"
                "- skipped_invalid_count=0\n",
                encoding="utf-8-sig",
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_review_decision_apply_stale_report_summary",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_source_review_decision_apply_schema_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            review_status_path = (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_status.json"
            )
            review_status = json.loads(review_status_path.read_text(encoding="utf-8-sig"))
            review_status["next_action"] = "apply_review_decisions_to_queue"
            review_status["review_decision_status"] = "ready_to_apply"
            review_status["decision_ready_to_apply_count"] = 1
            review_status["decision_file_exists"] = True
            write_json(review_status_path, review_status)
            write_json(
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_decision_apply.json",
                {
                    "apply_schema": "unexpected_schema",
                    "apply_version": 99,
                    "status": "dry_run",
                    "applied_count": 1,
                    "skipped_pending_count": 0,
                    "skipped_invalid_count": 0,
                    "formal_backtest_upgrade_allowed": False,
                },
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_review_decision_apply_invalid_schema",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_source_review_decision_merge_report_mismatches_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            write_json(
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_decision_merge.json",
                {
                    "merge_schema": "sp500_current_membership_source_review_decision_merge",
                    "merge_version": 1,
                    "merged": 1,
                    "skipped_pending": 0,
                    "skipped_invalid": 0,
                    "row_count": 1,
                    "formal_backtest_upgrade_allowed": False,
                },
            )
            (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_decision_merge.md"
            ).write_text(
                "# S&P 500 current membership source review decision merge\n\n"
                "- 合并/更新：0\n"
                "- 跳过 pending：1\n"
                "- 跳过无效：0\n"
                "- 当前正式决策行数：0\n",
                encoding="utf-8-sig",
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_review_decision_merge_stale_report_summary",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_sp500_source_review_decision_merge_allows_backtest_upgrade(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            write_json(
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_decision_merge.json",
                {
                    "merge_schema": "sp500_current_membership_source_review_decision_merge",
                    "merge_version": 1,
                    "merged": 0,
                    "skipped_pending": 1,
                    "skipped_invalid": 0,
                    "row_count": 0,
                    "formal_backtest_upgrade_allowed": True,
                },
            )
            (
                root
                / "outputs"
                / "automation"
                / "latest_sp500_current_membership_source_review_decision_merge.md"
            ).write_text(
                "# S&P 500 current membership source review decision merge\n\n"
                "- 合并/更新：0\n"
                "- 跳过 pending：1\n"
                "- 跳过无效：0\n"
                "- 当前正式决策行数：0\n",
                encoding="utf-8-sig",
            )

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "sp500_current_membership_source_review_decision_merge_upgrade_gate_unsafe",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_model_handoff_claims_auto_collaboration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            handoff_path = (
                root
                / "outputs"
                / "automation"
                / "latest_model_handoff_review.json"
            )
            handoff = json.loads(handoff_path.read_text(encoding="utf-8-sig"))
            handoff["automatic_multi_model_collaboration_enabled"] = True
            write_json(handoff_path, handoff)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "model_handoff_review_auto_collaboration_boundary_unsafe",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_existing_check_reports_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            delivery_path = root / "outputs" / "automation" / "latest_weekly_delivery_check.json"
            delivery = json.loads(delivery_path.read_text(encoding="utf-8-sig"))
            delivery["status"] = "needs_attention"
            delivery["attention_reasons"] = ["missing_conclusion_signals"]
            write_json(delivery_path, delivery)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("weekly_delivery_check_not_ready", result["attention_reasons"])
            self.assertIn("weekly_delivery_check:missing_conclusion_signals", result["attention_reasons"])

    def test_review_needs_attention_when_delivery_check_lacks_quality_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            delivery_path = root / "outputs" / "automation" / "latest_weekly_delivery_check.json"
            delivery = json.loads(delivery_path.read_text(encoding="utf-8-sig"))
            del delivery["missing_conclusion_signal_fixes"]
            del delivery["action_items_count"]
            write_json(delivery_path, delivery)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_delivery_check_missing_quality_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_delivery_check_lacks_action_items_actual_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            delivery_path = root / "outputs" / "automation" / "latest_weekly_delivery_check.json"
            delivery = json.loads(delivery_path.read_text(encoding="utf-8-sig"))
            del delivery["action_items_actual_count"]
            write_json(delivery_path, delivery)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_delivery_check_missing_quality_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_delivery_check_lacks_action_items_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            delivery_path = root / "outputs" / "automation" / "latest_weekly_delivery_check.json"
            delivery = json.loads(delivery_path.read_text(encoding="utf-8-sig"))
            del delivery["action_items_json"]
            write_json(delivery_path, delivery)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_delivery_check_missing_quality_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_delivery_check_lacks_forecast_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            delivery_path = root / "outputs" / "automation" / "latest_weekly_delivery_check.json"
            delivery = json.loads(delivery_path.read_text(encoding="utf-8-sig"))
            del delivery["forecast_next_one_week_evaluation_date"]
            del delivery["forecast_next_one_month_evaluation_date"]
            write_json(delivery_path, delivery)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_delivery_check_missing_quality_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_delivery_check_lacks_forecast_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            delivery_path = root / "outputs" / "automation" / "latest_weekly_delivery_check.json"
            delivery = json.loads(delivery_path.read_text(encoding="utf-8-sig"))
            del delivery["forecast_next_one_week_evaluation_count"]
            del delivery["forecast_next_one_month_evaluation_count"]
            write_json(delivery_path, delivery)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_delivery_check_missing_quality_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_delivery_check_omits_external_input_blockers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            delivery_path = root / "outputs" / "automation" / "latest_weekly_delivery_check.json"
            delivery = json.loads(delivery_path.read_text(encoding="utf-8-sig"))
            delivery["external_input_blocker_count"] = 0
            delivery["external_input_blockers"] = []
            write_json(delivery_path, delivery)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_delivery_check_missing_external_input_blockers",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_weekly_conclusion_omits_sp500_external_input_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            conclusion_path = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            conclusion = json.loads(conclusion_path.read_text(encoding="utf-8-sig"))
            conclusion["priority_input_gaps"] = []
            write_json(conclusion_path, conclusion)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_conclusion_missing_sp500_external_input_gap",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_automation_check_omits_sp500_external_input_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            automation_path = root / "outputs" / "automation" / "latest_automation_check.json"
            automation = json.loads(automation_path.read_text(encoding="utf-8-sig"))
            automation["external_input_blocker_count"] = 0
            automation["external_input_blockers"] = []
            write_json(automation_path, automation)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "automation_check_missing_sp500_external_input_blocker",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_weekly_ops_check_omits_sp500_external_input_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            ops_path = root / "outputs" / "automation" / "latest_weekly_ops_check.json"
            ops = json.loads(ops_path.read_text(encoding="utf-8-sig"))
            ops["external_input_blocker_count"] = 0
            ops["external_input_blockers"] = []
            write_json(ops_path, ops)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_ops_check_missing_sp500_external_input_blocker",
                result["attention_reasons"],
            )

    def test_report_includes_delivery_external_input_blockers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            delivery_path = root / "outputs" / "automation" / "latest_weekly_delivery_check.json"
            delivery = json.loads(delivery_path.read_text(encoding="utf-8-sig"))
            delivery["external_input_blocker_count"] = 1
            delivery["external_input_blockers"] = [
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
                }
            ]
            write_json(delivery_path, delivery)

            from pre_submit_review import render_pre_submit_review, run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)
            report = render_pre_submit_review(result)

            self.assertEqual(result["external_input_blocker_count"], 1)
            self.assertIn("provide_official_constituents_csv", report)
            self.assertIn("official_constituents.csv", report)
            self.assertIn("official_constituents_csv_missing", report)
            self.assertIn("official_export_url=https://www.spglobal.com/spdji/en/idsexport/file.xls", report)
            self.assertIn("place_official_constituents_csv", report)

    def test_review_needs_attention_when_ops_check_lacks_forecast_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            ops_path = root / "outputs" / "automation" / "latest_weekly_ops_check.json"
            ops = json.loads(ops_path.read_text(encoding="utf-8-sig"))
            del ops["forecast_next_one_week_evaluation_date"]
            del ops["forecast_next_one_month_evaluation_date"]
            write_json(ops_path, ops)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_ops_check_missing_quality_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_ops_check_lacks_forecast_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            ops_path = root / "outputs" / "automation" / "latest_weekly_ops_check.json"
            ops = json.loads(ops_path.read_text(encoding="utf-8-sig"))
            del ops["forecast_next_one_week_evaluation_count"]
            del ops["forecast_next_one_month_evaluation_count"]
            write_json(ops_path, ops)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_ops_check_missing_quality_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_weekly_conclusion_lacks_summary_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            conclusion_path = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            conclusion = json.loads(conclusion_path.read_text(encoding="utf-8-sig"))
            del conclusion["candidate_action_summary"]
            del conclusion["outputs"]
            write_json(conclusion_path, conclusion)

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn(
                "weekly_conclusion_missing_summary_fields",
                result["attention_reasons"],
            )

    def test_review_needs_attention_when_any_input_date_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root, as_of_date="2026-06-10")

            from pre_submit_review import run_pre_submit_review

            result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["freshness_status"], "stale")
            self.assertIn("stale_inputs", result["attention_reasons"])
            self.assertEqual(result["input_age_days"]["weekly_delivery_check"], 18)

    def test_cli_writes_json_report_and_history_for_ready_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_review_inputs(root)
            output = root / "outputs" / "automation" / "latest_pre_submit_review.json"
            report = root / "outputs" / "automation" / "latest_pre_submit_review.md"
            history = root / "outputs" / "automation" / "pre_submit_review_history.jsonl"

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "pre_submit_review.py"),
                    "--project-root",
                    str(root),
                    "--today",
                    "2026-06-28",
                    "--max-age-days",
                    "8",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--history",
                    str(history),
                    "--closeout-goal-code",
                    "backtest_evidence_quality",
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
            self.assertIn("提交前复核结果", combined)
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(
                payload["development_closeout"]["goal_code"],
                "backtest_evidence_quality",
            )
            self.assertEqual(
                payload["development_closeout"]["current_module"],
                "S&P 500 成分证据补强",
            )
            self.assertIn("总体状态：ready", report.read_text(encoding="utf-8-sig"))
            self.assertEqual(len(history.read_text(encoding="utf-8-sig").splitlines()), 1)


    def test_pre_submit_wrapper_exposes_closeout_goal_code(self):
        wrapper = (PROJECT_ROOT / "scripts" / "run_pre_submit_review.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("CloseoutGoalCode", wrapper)
        self.assertIn("--closeout-goal-code", wrapper)


if __name__ == "__main__":
    unittest.main()
