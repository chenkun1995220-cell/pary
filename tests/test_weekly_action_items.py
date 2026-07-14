import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_manifest(path):
    manifest = {
        "manifest_schema": "self_analysis_manifest",
        "manifest_version": 1,
        "action_policy_version": 1,
        "candidate_review_actionable": False,
        "weekly_delivery_history_actionable": False,
        "as_of_date": "2026-06-28",
        "automation_status": "manual_review_needed",
        "automation_priority_actions": [
            "review_manual_queue",
            "review_data_health",
            "review_manual_review_backlog",
            "review_delivery_health_issues",
            "review_data_quality_score",
            "review_data_quality_trend",
            "review_forecast_performance",
            "continue_sample_accumulation",
        ],
        "manual_review_queue_count": 12,
        "weekly_delivery_history": {
            "latest_manual_review_pending_count": 12,
            "latest_conclusion_health_status": "needs_review",
            "latest_conclusion_health_score": 75,
            "latest_conclusion_health_reasons": [
                "automation_check:manual_review_needed",
                "manual_review_pending:12",
            ],
            "recurring_health_reasons": [
                {"reason": "manual_review_pending:12", "count": 2}
            ],
            "latest_conclusion_signal_status": "missing",
            "latest_missing_conclusion_signals": [
                "automation.data_quality_history",
                "automation.forecast_performance",
            ],
            "latest_missing_conclusion_signal_fixes": {
                "automation.data_quality_history": (
                    "rerun_self_analysis_and_weekly_conclusion: ensure latest_self_analysis_manifest.json "
                    "contains data_quality_history before show_weekly_conclusion.ps1"
                ),
                "automation.forecast_performance": (
                    "rerun_self_analysis_and_weekly_conclusion: ensure latest_self_analysis_manifest.json "
                    "contains forecast_performance before show_weekly_conclusion.ps1"
                ),
            },
            "recurring_missing_conclusion_signals": [
                {"signal": "automation.forecast_performance", "count": 2}
            ],
            "recurring_missing_conclusion_signal_fixes": [
                {
                    "signal": "automation.forecast_performance",
                    "fix": (
                        "rerun_self_analysis_and_weekly_conclusion: ensure latest_self_analysis_manifest.json "
                        "contains forecast_performance before show_weekly_conclusion.ps1"
                    ),
                    "count": 2,
                }
            ],
        },
        "data_quality_status": "needs_review",
        "data_quality_score": 79.0,
        "data_quality_summary": {
            "status": "needs_review",
            "average_score": 79.0,
            "markets": [
                {
                    "name": "美股周筛",
                    "quality_score": 100,
                    "quality_status": "ready",
                    "reasons": ["clear"],
                },
                {
                    "name": "港股周筛",
                    "quality_score": 57,
                    "quality_status": "needs_review",
                    "reasons": ["quote_coverage:84.10%", "quote_review_gap:50"],
                },
            ],
        },
        "data_quality_history": {
            "status": "manual_review_needed",
            "recommended_action": "review_data_quality_trend",
            "repeated_needs_review_markets": ["港股周筛"],
            "score_decline_markets": ["A股周筛"],
        },
        "data_health_status": "ready",
        "backtest_status": "sample_accumulating",
        "candidate_review_status": "needs_review",
        "model_audit_status": "sample_accumulating",
        "forecast_performance_status": "performance_review_needed",
        "forecast_performance": {
            "mature_evaluations": 30,
            "direction_hit_rate": 0.32,
            "average_excess_return": -0.04,
            "next_one_week_evaluation_date": "2026-07-07",
            "next_one_week_evaluation_count": 42,
            "next_one_month_evaluation_date": "2026-07-28",
            "next_one_month_evaluation_count": 42,
        },
    }
    Path(path).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_membership_import_plan(path, ready_count=2):
    payload = {
        "review_schema": "membership_evidence_import_plan",
        "review_version": 1,
        "as_of_date": "2026-06-28",
        "status": "ready",
        "ready_to_import_count": ready_count,
        "ready_to_import_weeks_affected": 210,
        "missing_source_count": 1,
        "missing_source_weeks_affected": 300,
        "invalid_source_count": 0,
        "invalid_source_weeks_affected": 0,
        "next_action": "run_membership_evidence_apply_preview",
        "items": [
            {
                "ticker": "HIGH",
                "company_name": "High Impact",
                "import_status": "ready_current_source",
                "weeks_affected": 200,
            },
            {
                "ticker": "LOW",
                "company_name": "Low Impact",
                "import_status": "ready_current_source",
                "weeks_affected": 10,
            },
        ],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_membership_apply_preview(path, preview_row_count=4):
    payload = {
        "preview_schema": "membership_evidence_apply_preview",
        "preview_version": 1,
        "as_of_date": "2026-07-06",
        "status": "ready",
        "current_source_pack": "outputs/automation/latest_membership_evidence_verified_source_pack.csv",
        "eligible_ticker_count": 1,
        "preview_row_count": preview_row_count,
        "preview_weeks_affected": 2,
        "invalid_source_ticker_count": 0,
        "applied_to_historical_membership": False,
        "formal_backtest_upgrade_allowed": False,
        "items": [
            {
                "week": "2026-06-19",
                "ticker": "ABT",
                "company_name": "Abbott Laboratories",
                "current_evidence": "secondary",
                "proposed_evidence": "verified",
                "proposed_membership_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
            }
        ],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_blocked_membership_import_plan(path):
    payload = {
        "review_schema": "membership_evidence_import_plan",
        "review_version": 1,
        "as_of_date": "2026-07-05",
        "status": "ready",
        "ready_to_import_count": 0,
        "ready_to_import_weeks_affected": 0,
        "missing_source_count": 0,
        "missing_source_weeks_affected": 0,
        "invalid_source_count": 50,
        "invalid_source_weeks_affected": 7800,
        "blocked_by_source_policy_count": 50,
        "next_action": "supplement_verified_membership_evidence",
        "formal_backtest_upgrade_allowed": False,
        "items": [
            {
                "rank": 1,
                "ticker": "ABT",
                "company_name": "Abbott Laboratories",
                "import_status": "invalid_current_source",
                "source_trust_level": "crosscheck_substitute",
                "membership_source_url": "local://sp500_crosscheck_substitute",
                "weeks_affected": 156,
            }
        ],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_membership_source_intake_status(path):
    payload = {
        "status_schema": "membership_evidence_source_intake_status",
        "status_version": 1,
        "as_of_date": "2026-07-07",
        "status": "awaiting_manual_evidence",
        "ready_to_import_count": 0,
        "pending_count": 50,
        "current_batch_id": "2026-07-06-p1",
        "current_batch_pending_count": 10,
        "current_batch_manual_checklist": [
            {
                "batch_rank": 1,
                "ticker": "ABT",
                "company_name": "Abbott Laboratories",
                "validation_status": "pending_manual_evidence",
                "validation_reason": "manual_evidence_missing",
                "official_domain_search_query": 'site:spglobal.com/spdji "S&P 500" "ABT" "Abbott Laboratories"',
                "official_domain_search_url": "https://www.google.com/search?q=site%3Aspglobal.com%2Fspdji+%22S%26P+500%22+%22ABT%22",
                "official_index_page_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
            },
            {
                "batch_rank": 2,
                "ticker": "ADM",
                "company_name": "Archer Daniels Midland",
                "validation_status": "pending_manual_evidence",
                "validation_reason": "manual_evidence_missing",
            },
            {
                "batch_rank": 3,
                "ticker": "AEP",
                "company_name": "American Electric Power",
                "validation_status": "pending_manual_evidence",
                "validation_reason": "manual_evidence_missing",
            },
            {
                "batch_rank": 4,
                "ticker": "BA",
                "company_name": "Boeing",
                "validation_status": "pending_manual_evidence",
                "validation_reason": "manual_evidence_missing",
            },
            {
                "batch_rank": 5,
                "ticker": "BMY",
                "company_name": "Bristol Myers Squibb",
                "validation_status": "pending_manual_evidence",
                "validation_reason": "manual_evidence_missing",
            },
        ],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_official_export_probe(path):
    payload = {
        "probe_schema": "sp500_official_export_probe",
        "as_of_date": "2026-07-07",
        "status": "forbidden",
        "http_status": 403,
        "official_export_url": "https://www.spglobal.com/spdji/en/idsexport/file.xls?indexId=340",
        "next_action": "retry_with_logged_in_browser_or_manual_export",
        "manual_export_target_file": "inputs/sp500_current_membership/official_constituents.csv",
        "manual_export_dry_run_command": (
            "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
            "scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> "
            "-DryRun -SourceFileInbox inputs\\sp500_current_membership\\official_constituents.csv"
        ),
        "formal_backtest_upgrade_allowed": False,
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_current_membership_sources(path):
    payload = {
        "source_schema": "sp500_current_membership_sources",
        "source_version": 1,
        "as_of_date": "2026-06-28",
        "status": "ready",
        "matched_count": 1,
        "missing_count": 1,
        "missing_tickers": ["ZZZ"],
        "missing_ticker_review_queue": [
            {
                "ticker": "ZZZ",
                "review_status": "open",
                "issue_type": "missing_from_official_current_source",
                "recommended_check": "Confirm official source coverage.",
            }
        ],
        "missing_ticker_review_queue_file": "outputs/automation/sp500_current_membership_source_review_queue.csv",
        "intake_coverage_status": "none",
        "intake_expected_count": 1,
        "intake_matched_count": 0,
        "intake_missing_count": 1,
        "intake_missing_tickers": ["ZZZ"],
        "next_action": "review_missing_tickers",
        "recommended_followup": "review_current_membership_source_status",
        "formal_backtest_upgrade_allowed": False,
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_current_membership_source_review_status(path):
    payload = {
        "review_status_schema": "sp500_current_membership_source_review_status",
        "review_status_version": 1,
        "as_of_date": "2026-06-28",
        "status": "review_needed",
        "queue_file": "outputs/automation/sp500_current_membership_source_review_queue.csv",
        "queue_exists": True,
        "queue_total_count": 1,
        "open_count": 1,
        "resolved_count": 0,
        "open_items": [{"ticker": "ZZZ", "review_status": "open"}],
        "resolved_items": [],
        "next_action": "review_open_queue_items",
        "review_decision_status": "missing",
        "manual_decision_next_step": "fill_decisions_template",
        "decision_pending_count": 1,
        "decision_pending_tickers": ["ZZZ"],
        "decision_ready_to_apply_count": 0,
        "decision_ready_to_apply_tickers": [],
        "decisions_template_file": "outputs/automation/sp500_current_membership_source_review_decisions_template.csv",
        "decisions_template_exists": True,
        "decisions_template_status": "ready",
        "decisions_template_total_count": 1,
        "decisions_template_matched_open_count": 1,
        "decisions_template_missing_open_tickers": [],
        "decisions_template_extra_tickers": [],
        "decisions_template_missing_fields": [],
        "formal_backtest_upgrade_allowed": False,
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_current_membership_source_inbox_status(path):
    payload = {
        "status_schema": "sp500_current_membership_source_inbox_status",
        "status_version": 1,
        "as_of_date": "2026-06-28",
        "status": "missing",
        "source_file_inbox": "inputs/sp500_current_membership/official_constituents.csv",
        "source_file_inbox_exists": False,
        "source_file_validation_status": "missing",
        "parsed_official_ticker_count": 0,
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
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_backtest_evidence_review(path):
    payload = {
        "review_schema": "backtest_evidence_review",
        "review_version": 1,
        "as_of_date": "2026-06-28",
        "status": "evidence_review_needed",
        "evidence_status": "evidence_review_needed",
        "evidence_next_action": "supplement_verified_membership_evidence",
        "weeks_failed": 0,
        "membership_evidence_action_required_count": 50,
        "membership_evidence_action_queue_count": 50,
        "membership_evidence_action_unqueued_count": 0,
        "backtest_sample_expansion_allowed": False,
        "backtest_sample_expansion_decision": "do_not_expand_backtest_sample",
        "backtest_sample_expansion_reason": [
            "verified_membership_ratio_below_threshold",
            "weak_evidence_rows_present",
        ],
        "required_verified_membership_ratio_for_expansion": 0.5,
        "verified_membership_ratio": 0.156,
        "weak_evidence_rows": 3382,
        "weak_evidence_weeks": 8,
        "membership_evidence_gate_status": "blocked",
        "membership_evidence_gate_decision": "verified_only_no_expansion",
        "membership_evidence_blocking_tiers": ["secondary", "weak"],
        "historical_membership_auto_update_allowed": False,
        "membership_evidence_action_queue": [
            {
                "ticker": "ABT",
                "action_type": "supplement_official_membership_source",
                "recommended_source": "official_spglobal_membership_evidence",
                "recommended_action": "supplement_official_spglobal_source",
            }
        ],
        "formal_model_upgrade_allowed": False,
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_closed_backtest_evidence_review(path):
    payload = {
        "review_schema": "backtest_evidence_review",
        "review_version": 1,
        "as_of_date": "2026-07-11",
        "status": "evidence_ceiling_confirmed",
        "evidence_ceiling_status": "evidence_ceiling_confirmed",
        "backtest_mode": "limited_verified_only",
        "recommended_action": "maintain_limited_backtest",
        "weeks_failed": 0,
        "membership_evidence_unresolved_gap_count": 425,
        "membership_evidence_action_required_count": 0,
        "membership_evidence_action_queue_count": 0,
        "membership_evidence_action_unqueued_count": 0,
        "membership_evidence_action_queue": [],
        "backtest_sample_expansion_allowed": False,
        "backtest_sample_expansion_decision": "do_not_expand_backtest_sample",
        "membership_evidence_gate_status": "blocked",
        "membership_evidence_gate_decision": "verified_only_no_expansion",
        "historical_membership_auto_update_allowed": False,
        "formal_model_upgrade_allowed": False,
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_forecast_performance_review(
    path,
    prediction_unavailable=87,
    pending_maturity=0,
    mature_evaluations=0,
    latest_prediction_unavailable=87,
    legacy_prediction_unavailable=0,
    next_one_week_evaluation_date="2026-07-07",
    next_one_week_evaluation_count=42,
    next_one_month_evaluation_date="2026-07-28",
    next_one_month_evaluation_count=42,
):
    payload = {
        "review_schema": "forecast_performance_review",
        "review_version": 1,
        "as_of_date": "2026-06-28",
        "status": "sample_accumulating",
        "total_evaluations": 87,
        "mature_evaluations": mature_evaluations,
        "one_week_mature": 0,
        "one_month_mature": 0,
        "latest_short_signal_missing_count": 0,
        "latest_prediction_unavailable_count": latest_prediction_unavailable,
        "legacy_prediction_unavailable_count": legacy_prediction_unavailable,
        "next_one_week_evaluation_date": next_one_week_evaluation_date,
        "next_one_week_evaluation_count": next_one_week_evaluation_count,
        "next_one_month_evaluation_date": next_one_month_evaluation_date,
        "next_one_month_evaluation_count": next_one_month_evaluation_count,
        "maturity_gap_reasons": {
            "prediction_unavailable": prediction_unavailable,
            "pending_maturity": pending_maturity,
            "other_not_evaluated": 0,
        },
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_one_week_shadow_review(path):
    payload = {
        "review_schema": "one_week_forecast_shadow_review",
        "review_version": 1,
        "as_of_date": "2026-06-28",
        "status": "shadow_review_needed",
        "one_week_evaluated_count": 64,
        "direction_hit_rate": 0.25,
        "opposite_miss_count": 12,
        "neutral_miss_count": 18,
        "recommended_shadow_actions": [
            "review_direction_mapping",
            "review_neutral_band",
            "keep_formal_model_unchanged",
        ],
        "formal_model_change_allowed": False,
        "formal_model_change_decision": "keep_formal_model_unchanged",
        "shadow_review_decision": "shadow_review_only",
        "priority_review_market": "港股周筛",
        "formal_model_change_blockers": [
            "direction_hit_rate_below_threshold",
            "opposite_miss_count_positive",
        ],
        "shadow_diagnosis_status": "review_needed",
        "shadow_diagnosis_reasons": [
            {
                "reason_code": "down_signal_reversal_risk",
                "priority_market": "港股周筛",
                "recommended_shadow_action": "review_down_signal_mapping_shadow_only",
                "formal_model_change_allowed": False,
            },
            {
                "reason_code": "neutral_band_too_narrow",
                "priority_market": "港股周筛",
                "recommended_shadow_action": "review_neutral_band_shadow_only",
                "formal_model_change_allowed": False,
            },
        ],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_one_week_calibration_review(path):
    payload = {
        "review_schema": "one_week_forecast_calibration_review",
        "review_version": 1,
        "as_of_date": "2026-06-28",
        "status": "calibration_review_needed",
        "one_week_evaluated_count": 64,
        "recommended_shadow_actions": [
            "review_down_signal_mapping_shadow_only",
            "review_neutral_band_shadow_only",
            "keep_formal_model_unchanged",
        ],
        "formal_model_change_allowed": False,
        "formal_model_change_decision": "keep_formal_model_unchanged",
        "shadow_review_decision": "shadow_review_only",
        "priority_review_market": "港股周筛",
        "formal_model_change_blockers": [
            "down_signal_opposite_misses",
            "neutral_band_review_needed",
        ],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def shadow_disposition_payload(action="continue_shadow_validation"):
    return {
        "disposition_schema": "one_week_forecast_shadow_disposition",
        "disposition_version": 1,
        "as_of_date": "2026-06-28",
        "status": "ready",
        "recommended_action": action,
        "disposition_counts": {
            "continue_observation": 3,
            "rejected": 0,
            "pending_human_approval": 0,
        },
        "candidate_dispositions": [],
        "next_one_week_evaluation_date": "2026-07-07",
        "next_one_week_evaluation_count": 42,
        "formal_model_change_allowed": False,
    }


def extended_shadow_tracker_payload(status="active", completed=1):
    actions = {
        "active": "continue_extended_shadow_validation",
        "ready_for_reapproval": "review_extended_shadow_validation_results",
        "paused_severe_deterioration": "request_shadow_safety_reapproval",
        "paused_two_consecutive_negative_batches": "request_shadow_safety_reapproval",
    }
    return {
        "tracker_schema": "extended_shadow_validation_tracker",
        "tracker_version": 1,
        "as_of_date": "2026-07-19",
        "status": status,
        "recommended_action": actions[status],
        "authorization_count": 1,
        "active_authorization_count": int(status == "active"),
        "ready_for_reapproval_count": int(status == "ready_for_reapproval"),
        "paused_count": int(status.startswith("paused_")),
        "items": [
            {
                "action_code": "shadow_demote_down_signal_to_neutral",
                "authorization_date": "2026-07-12",
                "evaluable_batch_count": completed,
                "remaining_evaluable_batch_count": max(3 - completed, 0),
                "status": status,
                "recommended_action": actions[status],
            }
        ],
        "issues": [],
        "trade_execution_allowed": False,
        "formal_model_change_allowed": False,
        "formal_model_conclusion_allowed": False,
    }


def write_manual_review_queue(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "as_of_date",
                "rank",
                "market",
                "review_type",
                "ticker",
                "company",
                "review_detail",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "as_of_date": "2026-06-28",
                "rank": "1",
                "market": "A股周筛",
                "review_type": "估值口径",
                "ticker": "300433.SZ",
                "company": "蓝思科技",
                "review_detail": "loss_making_or_negative_pe；pe=-457.21",
            }
        )


def write_data_health_review(path, refetch_gap_action_required_count=2):
    triage_status = "refetch_required" if refetch_gap_action_required_count else "monitor_only"
    payload = {
        "review_schema": "data_health_review",
        "as_of_date": "2026-06-29",
        "status": "acceptable_with_monitoring",
        "blocked_candidate_count": 0,
        "candidate_delivery_blocked": False,
        "data_health_triage_status": triage_status,
        "data_health_triage_decision": "refetch_or_supplement_quote"
        if refetch_gap_action_required_count
        else "monitor_next_run",
        "data_health_triage_counts": {
            "candidate_blocking": 0,
            "refetch_required": refetch_gap_action_required_count,
            "monitor_only": 2 if not refetch_gap_action_required_count else 0,
        },
        "refetch_gap_count": 2,
        "refetch_gap_action_required_count": refetch_gap_action_required_count,
        "markets": [
            {
                "name": "港股周筛",
                "blocked_candidate_count": 0,
                "refetch_gap_action_required_count": refetch_gap_action_required_count,
                "refetch_gaps": [
                    {
                        "ticker": "00754.HK",
                        "company": "HOPSON DEV HOLD",
                        "missing_fields": "price;pe",
                        "in_candidate_pool": False,
                    },
                    {
                        "ticker": "00823.HK",
                        "company": "LINK REIT",
                        "missing_fields": "pe;pb",
                        "in_candidate_pool": False,
                    },
                ],
            }
        ],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_quote_retry_results(path):
    payload = {
        "retry_schema": "regional_quote_retry",
        "retry_version": 1,
        "attempted": 2,
        "updated": 0,
        "errors": 0,
        "results": [
            {
                "ticker": "00754.HK",
                "status": "partial",
                "message": "重抓后仍未达到 ready",
            },
            {
                "ticker": "00823.HK",
                "status": "partial",
                "message": "重抓后仍未达到 ready",
            },
        ],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_candidate_findings_review(path, risk_action_required_count=14):
    payload = {
        "review_schema": "candidate_findings_review",
        "review_version": 1,
        "as_of_date": "2026-06-29",
        "status": "manual_review_needed",
        "recommended_action": "review_candidate_findings",
        "candidate_count": 64,
        "field_complete_count": 64,
        "missing_field_count": 0,
        "risk_missing_count": 0,
        "risk_review_count": 33,
        "risk_classified_count": 33,
        "risk_unclassified_count": 0,
        "risk_action_required_count": risk_action_required_count,
        "risk_action_queue_count": risk_action_required_count,
        "risk_action_unqueued_count": 0,
        "formal_model_change_allowed": False,
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_manifest_with_resolved_delivery_backlog(path):
    write_manifest(path)
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    payload["manual_review_queue_count"] = 0
    payload["automation_priority_actions"] = [
        "review_manual_review_backlog",
        "review_delivery_health_issues",
        "review_data_health",
    ]
    payload["weekly_delivery_history"] = {
        "latest_manual_review_pending_count": 0,
        "latest_conclusion_health_status": "needs_review",
        "latest_conclusion_health_score": 80,
        "latest_conclusion_health_reasons": [
            "automation_check:manual_review_needed",
            "data_quality_history:manual_review_needed",
        ],
        "recurring_health_reasons": [
            {"reason": "automation_check:manual_review_needed", "count": 5},
            {"reason": "data_quality_history:manual_review_needed", "count": 4},
            {"reason": "manual_review_pending:1", "count": 2},
        ],
        "latest_missing_conclusion_signals": ["weekly_report_path"],
        "recurring_missing_conclusion_signals": [],
        "latest_missing_conclusion_signal_fixes": {
            "weekly_report_path": "refresh weekly conclusion report"
        },
        "recurring_missing_conclusion_signal_fixes": [],
    }
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_manifest_with_duplicate_delivery_health_reason(path):
    write_manifest(path)
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    payload["manual_review_queue_count"] = 0
    payload["automation_priority_actions"] = [
        "review_data_quality_score",
        "review_data_quality_trend",
        "review_delivery_health_issues",
    ]
    payload["weekly_delivery_history"] = {
        "latest_manual_review_pending_count": 0,
        "latest_conclusion_health_status": "needs_review",
        "latest_conclusion_health_score": 80,
        "latest_conclusion_health_reasons": [
            "automation_check:manual_review_needed",
            "data_quality_history:manual_review_needed",
        ],
        "recurring_health_reasons": [
            {"reason": "automation_check:manual_review_needed", "count": 5},
            {"reason": "data_quality_history:manual_review_needed", "count": 4},
        ],
        "latest_conclusion_signal_status": "ready",
        "latest_missing_conclusion_signals": [],
        "latest_missing_conclusion_signal_fixes": {},
        "recurring_missing_conclusion_signals": [],
        "recurring_missing_conclusion_signal_fixes": [],
    }
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_manifest_with_routed_forecast_delivery_health_reason(path):
    write_manifest(path)
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    payload["manual_review_queue_count"] = 0
    payload["automation_priority_actions"] = [
        "review_forecast_performance",
        "review_delivery_health_issues",
    ]
    payload["weekly_delivery_history"] = {
        "latest_manual_review_pending_count": 0,
        "latest_conclusion_health_status": "needs_review",
        "latest_conclusion_health_score": 70,
        "latest_conclusion_health_reasons": [
            "automation_check:manual_review_needed",
            "data_quality_history:manual_review_needed",
            "forecast_performance:performance_review_needed",
        ],
        "recurring_health_reasons": [
            {"reason": "automation_check:manual_review_needed", "count": 7},
            {"reason": "data_quality_history:manual_review_needed", "count": 6},
            {"reason": "forecast_performance:performance_review_needed", "count": 2},
        ],
        "latest_conclusion_signal_status": "ready",
        "latest_missing_conclusion_signals": [],
        "latest_missing_conclusion_signal_fixes": {},
        "recurring_missing_conclusion_signals": [],
        "recurring_missing_conclusion_signal_fixes": [],
    }
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


class WeeklyActionItemsTests(unittest.TestCase):
    def test_load_manifest_rejects_missing_action_policy_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(
                json.dumps({"manifest_schema": "self_analysis_manifest", "manifest_version": 1}),
                encoding="utf-8-sig",
            )

            from weekly_action_items import load_manifest

            with self.assertRaisesRegex(ValueError, "manifest_action_policy_contract_missing"):
                load_manifest(path)

    def test_load_manifest_rejects_old_action_policy_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(
                json.dumps(
                    {
                        "manifest_schema": "self_analysis_manifest",
                        "manifest_version": 1,
                        "action_policy_version": 0,
                        "candidate_review_actionable": False,
                        "weekly_delivery_history_actionable": False,
                    }
                ),
                encoding="utf-8-sig",
            )

            from weekly_action_items import load_manifest

            with self.assertRaisesRegex(ValueError, "manifest_action_policy_version_mismatch"):
                load_manifest(path)

    def test_extended_shadow_tracker_routes_only_terminal_or_paused_actions(self):
        from weekly_action_items import build_weekly_action_items

        expected = {
            "active": None,
            "ready_for_reapproval": "review_extended_shadow_validation_results",
            "paused_severe_deterioration": "request_shadow_safety_reapproval",
            "paused_two_consecutive_negative_batches": "request_shadow_safety_reapproval",
        }
        for status, expected_action in expected.items():
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                manifest = root / "manifest.json"
                write_manifest(manifest)
                source = json.loads(manifest.read_text(encoding="utf-8-sig"))
                source["automation_priority_actions"] = ["continue_sample_accumulation"]
                manifest.write_text(json.dumps(source), encoding="utf-8-sig")
                tracker = root / "latest_extended_shadow_validation_tracker.json"
                tracker.write_text(
                    json.dumps(extended_shadow_tracker_payload(status), ensure_ascii=False),
                    encoding="utf-8-sig",
                )

                payload = build_weekly_action_items(
                    manifest,
                    extended_shadow_validation_tracker=tracker,
                )
                action_codes = [item["action_code"] for item in payload["items"]]

                if expected_action:
                    self.assertEqual(action_codes.count(expected_action), 1)
                else:
                    self.assertNotIn("review_extended_shadow_validation_results", action_codes)
                    self.assertNotIn("request_shadow_safety_reapproval", action_codes)

    def test_closes_delivery_health_when_candidate_findings_is_already_routed(self):
        from weekly_action_items import build_weekly_action_items

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.json"
            write_manifest(manifest)
            source = json.loads(manifest.read_text(encoding="utf-8-sig"))
            source["manual_review_queue_count"] = 0
            source["automation_priority_actions"] = ["review_delivery_health_issues"]
            source["weekly_delivery_history"] = {
                "latest_manual_review_pending_count": 0,
                "latest_conclusion_health_reasons": [
                    "automation_check:manual_review_needed",
                    "forecast_performance:performance_review_needed",
                    "candidate_findings_review:manual_review_needed",
                ],
                "recurring_health_reasons": [
                    {
                        "reason": "candidate_findings_review:manual_review_needed",
                        "count": 3,
                    }
                ],
                "latest_conclusion_signal_status": "ready",
                "latest_missing_conclusion_signals": [],
                "latest_missing_conclusion_signal_fixes": {},
                "recurring_missing_conclusion_signals": [],
                "recurring_missing_conclusion_signal_fixes": [],
            }
            manifest.write_text(
                json.dumps(source, ensure_ascii=False), encoding="utf-8-sig"
            )

            payload = build_weekly_action_items(manifest)

            self.assertEqual(payload["items"], [])

    def test_closes_stale_shadow_approval_action_after_inbox_decision(self):
        from weekly_action_items import build_weekly_action_items

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.json"
            write_manifest(manifest)
            source = json.loads(manifest.read_text(encoding="utf-8-sig"))
            source["automation_priority_actions"] = [
                "review_shadow_candidate_approval",
                "continue_sample_accumulation",
            ]
            manifest.write_text(
                json.dumps(source, ensure_ascii=False), encoding="utf-8-sig"
            )
            inbox = root / "latest_human_decision_inbox.json"
            inbox.write_text(
                json.dumps(
                    {
                        "inbox_schema": "human_decision_inbox",
                        "inbox_version": 1,
                        "as_of_date": "2026-07-12",
                        "status": "ready",
                        "item_count": 1,
                        "pending_count": 0,
                        "decided_count": 1,
                        "invalid_decision_count": 0,
                        "items": [
                            {
                                "item_type": "forecast_shadow",
                                "decision_status": "decided",
                                "decision": "approve_for_extended_shadow_validation",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8-sig",
            )

            payload = build_weekly_action_items(
                manifest, human_decision_inbox=inbox
            )

            action_codes = [item["action_code"] for item in payload["items"]]
            self.assertNotIn("review_shadow_candidate_approval", action_codes)
            self.assertIn("continue_sample_accumulation", action_codes)

    def test_adds_one_authoritative_human_decision_inbox_action(self):
        from weekly_action_items import build_weekly_action_items

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.json"
            write_manifest(manifest)
            inbox = root / "latest_human_decision_inbox.json"
            inbox.write_text(
                json.dumps(
                    {
                        "inbox_schema": "human_decision_inbox",
                        "inbox_version": 1,
                        "as_of_date": "2026-07-12",
                        "status": "manual_review_needed",
                        "item_count": 6,
                        "pending_count": 6,
                        "decided_count": 0,
                        "invalid_decision_count": 0,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8-sig",
            )

            payload = build_weekly_action_items(
                manifest, human_decision_inbox=inbox
            )

            matching = [
                item
                for item in payload["items"]
                if item["action_code"] == "review_human_decision_inbox"
            ]
            self.assertEqual(len(matching), 1)
            self.assertIn("pending=6", matching[0]["source"])

    def test_builds_action_items_from_self_analysis_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "latest_self_analysis_manifest.json"
            manual_queue_path = Path(tmp) / "latest_manual_review_queue.csv"
            data_health_path = Path(tmp) / "latest_data_health_review.json"
            write_manifest(manifest_path)
            write_manual_review_queue(manual_queue_path)
            write_data_health_review(data_health_path)

            from weekly_action_items import build_weekly_action_items, render_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                manual_review_queue=manual_queue_path,
                data_health_review=data_health_path,
            )
            report = render_weekly_action_items(payload)

            self.assertEqual(payload["action_items_schema"], "weekly_action_items")
            self.assertEqual(payload["action_items_version"], 1)
            self.assertEqual(payload["action_policy_version"], 1)
            self.assertEqual(payload["as_of_date"], "2026-06-29")
            self.assertEqual(payload["source_manifest"], str(manifest_path))
            self.assertEqual(payload["automation_status"], "manual_review_needed")
            self.assertEqual(payload["item_count"], 8)

            backlog = next(
                item
                for item in payload["items"]
                if item["action_code"] == "review_manual_review_backlog"
            )
            self.assertEqual(backlog["category"], "delivery_health")
            self.assertEqual(backlog["status"], "open")
            self.assertIn("人工复核积压", backlog["title"])
            self.assertIn("12", backlog["recommended_check"])
            self.assertIn("manual_review_pending:12", backlog["source"])

            delivery = next(
                item
                for item in payload["items"]
                if item["action_code"] == "review_delivery_health_issues"
            )
            self.assertIn("automation_check:manual_review_needed", delivery["source"])
            self.assertIn("automation.forecast_performance", delivery["source"])
            self.assertIn("latest_self_analysis_manifest.json", delivery["source"])
            self.assertIn("automation.data_quality_history", delivery["recommended_check"])
            self.assertIn("automation.forecast_performance", delivery["recommended_check"])
            self.assertIn("latest_self_analysis_manifest.json", delivery["recommended_check"])
            self.assertIn("show_weekly_conclusion.ps1", delivery["recommended_check"])
            self.assertIn("needs_review", delivery["recommended_check"])

            manual_queue = next(
                item
                for item in payload["items"]
                if item["action_code"] == "review_manual_queue"
            )
            self.assertIn("300433.SZ", manual_queue["recommended_check"])
            self.assertIn("蓝思科技", manual_queue["recommended_check"])
            self.assertIn("loss_making_or_negative_pe", manual_queue["recommended_check"])

            data_health = next(
                item
                for item in payload["items"]
                if item["action_code"] == "review_data_health"
            )
            self.assertIn("00754.HK", data_health["recommended_check"])
            self.assertIn("HOPSON DEV HOLD", data_health["recommended_check"])
            self.assertIn("price;pe", data_health["recommended_check"])
            self.assertIn("triage_status=refetch_required", data_health["recommended_check"])
            self.assertIn("candidate_blocking=0", data_health["recommended_check"])
            self.assertIn("refetch_required=2", data_health["recommended_check"])
            self.assertIn("00823.HK", data_health["recommended_check"])
            self.assertIn("LINK REIT", data_health["recommended_check"])
            self.assertIn("pe;pb", data_health["recommended_check"])

            data_quality = next(
                item
                for item in payload["items"]
                if item["action_code"] == "review_data_quality_score"
            )
            self.assertEqual(data_quality["category"], "data_quality")
            self.assertIn("needs_review", data_quality["source"])
            self.assertIn("79", data_quality["source"])
            self.assertIn("港股周筛", data_quality["recommended_check"])
            self.assertIn("57", data_quality["recommended_check"])

            data_quality_trend = next(
                item
                for item in payload["items"]
                if item["action_code"] == "review_data_quality_trend"
            )
            self.assertEqual(data_quality_trend["category"], "data_quality")
            self.assertIn("manual_review_needed", data_quality_trend["source"])
            self.assertIn("港股周筛", data_quality_trend["recommended_check"])
            self.assertIn("A股周筛", data_quality_trend["recommended_check"])

            sample = next(
                item
                for item in payload["items"]
                if item["action_code"] == "continue_sample_accumulation"
            )
            self.assertEqual(sample["category"], "model_tracking")
            self.assertIn("forecast_mature_evaluations:30", sample["source"])
            self.assertIn("forecast_one_week_mature:0", sample["source"])
            self.assertIn("forecast_one_month_mature:0", sample["source"])
            self.assertIn("forecast_next_one_week_evaluation_date:2026-07-07", sample["source"])
            self.assertIn("forecast_next_one_week_evaluation_count:42", sample["source"])
            self.assertIn("forecast_next_one_month_evaluation_date:2026-07-28", sample["source"])
            self.assertIn("forecast_next_one_month_evaluation_count:42", sample["source"])
            self.assertIn("sample_accumulating", sample["recommended_check"])
            self.assertIn("2026-07-07", sample["recommended_check"])
            self.assertIn("42", sample["recommended_check"])
            self.assertIn("2026-07-28", sample["recommended_check"])

            forecast = next(
                item
                for item in payload["items"]
                if item["action_code"] == "review_forecast_performance"
            )
            self.assertEqual(forecast["category"], "forecast_performance")
            self.assertIn("预测表现", forecast["title"])
            self.assertIn("30", forecast["source"])
            self.assertIn("32.00%", forecast["recommended_check"])
            self.assertIn("-4.00%", forecast["recommended_check"])

            self.assertIn("# 每周人工处理清单", report)
            self.assertIn("review_manual_review_backlog", report)
            self.assertIn("automation.forecast_performance", report)
            self.assertIn("show_weekly_conclusion.ps1", report)
            self.assertIn("review_data_quality_score", report)
            self.assertIn("review_forecast_performance", report)
            self.assertIn("人工复核积压", report)
            self.assertIn("不抓取行情", report)

    def test_data_health_action_includes_quote_retry_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "latest_self_analysis_manifest.json"
            data_health_path = Path(tmp) / "latest_data_health_review.json"
            quote_retry_path = Path(tmp) / "quote_retry_results.json"
            write_manifest(manifest_path)
            write_data_health_review(data_health_path)
            write_quote_retry_results(quote_retry_path)

            from weekly_action_items import build_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                data_health_review=data_health_path,
                quote_retry_results=quote_retry_path,
            )

            data_health = next(
                item
                for item in payload["items"]
                if item["action_code"] == "review_data_health"
            )
            self.assertIn("已重抓2条，成功0条", data_health["recommended_check"])
            self.assertIn("00754.HK partial", data_health["recommended_check"])
            self.assertIn("00823.HK partial", data_health["recommended_check"])
            self.assertIn("补充行情源或人工复核字段口径", data_health["recommended_check"])

    def test_forecast_action_includes_one_week_shadow_review_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            forecast_path = root / "latest_forecast_performance_review.json"
            shadow_path = root / "latest_one_week_forecast_shadow_review.json"
            calibration_path = root / "latest_one_week_forecast_calibration_review.json"
            write_manifest(manifest_path)
            write_forecast_performance_review(
                forecast_path,
                mature_evaluations=64,
                latest_prediction_unavailable=0,
                legacy_prediction_unavailable=0,
            )
            write_one_week_shadow_review(shadow_path)
            write_one_week_calibration_review(calibration_path)

            from weekly_action_items import build_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                forecast_performance=forecast_path,
                one_week_forecast_shadow_review=shadow_path,
                one_week_forecast_calibration_review=calibration_path,
            )

            forecast = next(
                item
                for item in payload["items"]
                if item["action_code"] == "review_forecast_performance"
            )
            self.assertIn("latest_one_week_forecast_shadow_review.json", forecast["recommended_check"])
            self.assertIn("review_direction_mapping", forecast["recommended_check"])
            self.assertIn("formal_model_change_decision=keep_formal_model_unchanged", forecast["recommended_check"])
            self.assertIn("priority_review_market=港股周筛", forecast["recommended_check"])
            self.assertIn("blockers=direction_hit_rate_below_threshold,opposite_miss_count_positive", forecast["recommended_check"])
            self.assertIn("diagnosis_status=review_needed", forecast["recommended_check"])
            self.assertIn("diagnosis=down_signal_reversal_risk,neutral_band_too_narrow", forecast["recommended_check"])
            self.assertIn("latest_one_week_forecast_calibration_review.json", forecast["recommended_check"])
            self.assertIn("review_down_signal_mapping_shadow_only", forecast["recommended_check"])
            self.assertIn("formal_model_change_allowed:false", forecast["source"])

    def test_disposition_routes_forecast_action_to_specific_shadow_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "latest_self_analysis_manifest.json"
            write_manifest(manifest_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            manifest["automation_priority_actions"] = ["continue_shadow_validation"]
            manifest["one_week_forecast_shadow_disposition"] = shadow_disposition_payload()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items

            payload = build_weekly_action_items(manifest_path)
            actions = [item["action_code"] for item in payload["items"]]
            item = next(
                item for item in payload["items"] if item["action_code"] == "continue_shadow_validation"
            )

            self.assertIn("continue_shadow_validation", actions)
            self.assertNotIn("review_forecast_performance", actions)
            self.assertEqual(item["category"], "forecast_performance")
            self.assertIn("继续观察=3", item["recommended_check"])
            self.assertIn("2026-07-07", item["recommended_check"])
            self.assertIn("formal_model_change_allowed=false", item["source"])

    def test_skips_data_health_action_when_review_only_requires_monitoring(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "latest_self_analysis_manifest.json"
            data_health_path = Path(tmp) / "latest_data_health_review.json"
            write_manifest(manifest_path)
            write_data_health_review(
                data_health_path,
                refetch_gap_action_required_count=0,
            )
            payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            payload["automation_priority_actions"] = ["review_data_health"]
            manifest_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items

            result = build_weekly_action_items(
                manifest_path,
                data_health_review=data_health_path,
            )

            self.assertEqual(result["items"], [])

    def test_skips_data_quality_actions_when_data_health_review_only_requires_monitoring(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "latest_self_analysis_manifest.json"
            data_health_path = Path(tmp) / "latest_data_health_review.json"
            write_manifest(manifest_path)
            write_data_health_review(
                data_health_path,
                refetch_gap_action_required_count=0,
            )
            payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            payload["automation_priority_actions"] = [
                "review_data_quality_score",
                "review_data_quality_trend",
            ]
            manifest_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items

            result = build_weekly_action_items(
                manifest_path,
                data_health_review=data_health_path,
            )

            self.assertEqual(result["items"], [])

    def test_skips_manual_review_backlog_when_latest_pending_is_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "latest_self_analysis_manifest.json"
            data_health_path = Path(tmp) / "latest_data_health_review.json"
            write_manifest_with_resolved_delivery_backlog(manifest_path)
            write_data_health_review(data_health_path)

            from weekly_action_items import build_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                data_health_review=data_health_path,
            )

            actions = [item["action_code"] for item in payload["items"]]
            self.assertNotIn("review_manual_review_backlog", actions)
            delivery = next(
                item
                for item in payload["items"]
                if item["action_code"] == "review_delivery_health_issues"
            )
            self.assertNotIn("manual_review_pending", delivery["source"])
            self.assertIn("data_quality_history:manual_review_needed", delivery["source"])

    def test_external_delivery_history_overrides_stale_manifest_manual_review_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "latest_self_analysis_manifest.json"
            delivery_history_path = Path(tmp) / "latest_weekly_delivery_history_summary.json"
            write_manifest(manifest_path)
            payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            payload["manual_review_queue_count"] = 0
            payload["automation_priority_actions"] = ["review_manual_review_backlog"]
            payload["weekly_delivery_history"] = {
                "latest_manual_review_pending_count": 1,
                "latest_conclusion_health_reasons": ["manual_review_pending:1"],
                "recurring_health_reasons": [{"reason": "manual_review_pending:1", "count": 2}],
            }
            manifest_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )
            delivery_history_path.write_text(
                json.dumps(
                    {
                        "latest_manual_review_pending_count": 0,
                        "latest_conclusion_health_reasons": [],
                        "recurring_health_reasons": [
                            {"reason": "manual_review_pending:1", "count": 2}
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items

            result = build_weekly_action_items(
                manifest_path,
                weekly_delivery_history=delivery_history_path,
            )

            self.assertEqual(result["items"], [])

    def test_skips_delivery_health_issue_when_it_only_duplicates_data_quality(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "latest_self_analysis_manifest.json"
            write_manifest_with_duplicate_delivery_health_reason(manifest_path)

            from weekly_action_items import build_weekly_action_items

            payload = build_weekly_action_items(manifest_path)

            actions = [item["action_code"] for item in payload["items"]]
            self.assertEqual(
                actions,
                ["review_data_quality_score", "review_data_quality_trend"],
            )
            self.assertNotIn("review_delivery_health_issues", actions)

    def test_skips_delivery_health_issue_when_forecast_reason_has_dedicated_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "latest_self_analysis_manifest.json"
            forecast_path = Path(tmp) / "latest_forecast_performance_review.json"
            write_manifest_with_routed_forecast_delivery_health_reason(manifest_path)
            write_forecast_performance_review(
                forecast_path,
                mature_evaluations=64,
            )
            forecast_payload = json.loads(forecast_path.read_text(encoding="utf-8-sig"))
            forecast_payload["status"] = "performance_review_needed"
            forecast_payload["recommended_action"] = "review_forecast_performance"
            forecast_payload["one_week_mature"] = 64
            forecast_path.write_text(
                json.dumps(forecast_payload, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                forecast_performance=forecast_path,
            )

            actions = [item["action_code"] for item in payload["items"]]
            self.assertEqual(actions, ["review_forecast_performance"])
            self.assertNotIn("review_delivery_health_issues", actions)

    def test_skips_candidate_findings_when_review_is_structured_and_below_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "latest_self_analysis_manifest.json"
            candidate_findings_path = Path(tmp) / "latest_candidate_findings_review.json"
            write_manifest(manifest_path)
            write_candidate_findings_review(candidate_findings_path)
            payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            payload["automation_priority_actions"] = ["review_candidate_findings"]
            manifest_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items

            result = build_weekly_action_items(
                manifest_path,
                candidate_findings_review=candidate_findings_path,
            )

            self.assertEqual(result["items"], [])

    def test_adds_apply_preview_action_when_membership_sources_are_ready_to_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            import_plan_path = root / "latest_membership_evidence_import_plan.json"
            write_manifest(manifest_path)
            write_membership_import_plan(import_plan_path)

            from weekly_action_items import build_weekly_action_items, render_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                membership_import_plan=import_plan_path,
            )
            report = render_weekly_action_items(payload)

            apply_item = next(
                item
                for item in payload["items"]
                if item["action_code"] == "run_membership_evidence_apply_preview"
            )
            self.assertEqual(payload["item_count"], 9)
            self.assertEqual(apply_item["category"], "backtest")
            self.assertIn("ready_to_import_count:2", apply_item["source"])
            self.assertIn("weeks_affected:210", apply_item["source"])
            self.assertIn("HIGH", apply_item["recommended_check"])
            self.assertIn("run_membership_evidence_import_plan.ps1", apply_item["recommended_check"])
            self.assertIn("run_membership_evidence_apply_preview.ps1", apply_item["recommended_check"])
            self.assertIn("run_membership_evidence_apply_preview", report)

    def test_adds_manual_confirmation_action_when_apply_preview_has_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            import_plan_path = root / "latest_membership_evidence_import_plan.json"
            apply_preview_path = root / "latest_membership_evidence_apply_preview.json"
            write_manifest(manifest_path)
            write_membership_import_plan(import_plan_path)
            write_membership_apply_preview(apply_preview_path)

            from weekly_action_items import build_weekly_action_items, render_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                membership_import_plan=import_plan_path,
                membership_apply_preview=apply_preview_path,
            )
            report = render_weekly_action_items(payload)

            confirm_item = next(
                item
                for item in payload["items"]
                if item["action_code"] == "confirm_membership_evidence_apply_preview"
            )
            self.assertEqual(confirm_item["category"], "backtest")
            self.assertIn("preview_row_count:4", confirm_item["source"])
            self.assertIn("eligible_ticker_count:1", confirm_item["source"])
            self.assertIn("applied_to_historical_membership:false", confirm_item["source"])
            self.assertIn("formal_backtest_upgrade_allowed:false", confirm_item["source"])
            self.assertIn("latest_membership_evidence_apply_preview.md", confirm_item["recommended_check"])
            self.assertIn("人工确认", confirm_item["recommended_check"])
            self.assertIn("不得自动修改 historical_membership.csv", confirm_item["recommended_check"])
            self.assertIn("confirm_membership_evidence_apply_preview", report)

    def test_adds_verified_membership_supplement_action_when_sources_are_policy_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            import_plan_path = root / "latest_membership_evidence_import_plan.json"
            source_intake_path = root / "latest_membership_evidence_source_intake_status.json"
            official_probe_path = root / "latest_sp500_official_export_probe.json"
            write_manifest(manifest_path)
            write_blocked_membership_import_plan(import_plan_path)
            write_membership_source_intake_status(source_intake_path)
            write_official_export_probe(official_probe_path)

            from weekly_action_items import build_weekly_action_items, render_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                membership_import_plan=import_plan_path,
                membership_evidence_source_intake_status=source_intake_path,
                sp500_official_export_probe=official_probe_path,
            )
            report = render_weekly_action_items(payload)

            supplement_item = next(
                item
                for item in payload["items"]
                if item["action_code"] == "supplement_verified_membership_evidence"
            )
            self.assertEqual(supplement_item["category"], "backtest")
            self.assertIn("blocked_by_source_policy_count:50", supplement_item["source"])
            self.assertIn("invalid_source_weeks_affected:7800", supplement_item["source"])
            self.assertIn("current_batch_id:2026-07-06-p1", supplement_item["source"])
            self.assertIn("current_batch_manual_checklist_count:5", supplement_item["source"])
            self.assertIn("official_export_probe_status:forbidden", supplement_item["source"])
            self.assertIn("official_export_probe_http_status:403", supplement_item["source"])
            self.assertIn("latest_membership_evidence_supplement_queue.md", supplement_item["recommended_check"])
            self.assertIn("current_batch_manual_checklist", supplement_item["recommended_check"])
            self.assertIn("ABT, ADM, AEP, BA, BMY", supplement_item["recommended_check"])
            self.assertIn("official_domain_search_query", supplement_item["recommended_check"])
            self.assertIn('site:spglobal.com/spdji "S&P 500" "ABT"', supplement_item["recommended_check"])
            self.assertIn("official_domain_search_url", supplement_item["recommended_check"])
            self.assertIn("https://www.google.com/search?q=site%3Aspglobal.com%2Fspdji", supplement_item["recommended_check"])
            self.assertIn("latest_membership_evidence_manual_work_package.csv", supplement_item["recommended_check"])
            self.assertIn("latest_membership_evidence_manual_work_package.md", supplement_item["recommended_check"])
            self.assertIn("retry_with_logged_in_browser_or_manual_export", supplement_item["recommended_check"])
            self.assertIn("inputs/sp500_current_membership/official_constituents.csv", supplement_item["recommended_check"])
            self.assertIn("run_sp500_current_membership_sources.ps1", supplement_item["recommended_check"])
            self.assertIn("-DryRun", supplement_item["recommended_check"])
            self.assertIn("official S&P Global", supplement_item["recommended_check"])
            self.assertIn("supplement_verified_membership_evidence", report)

    def test_supplement_action_omits_official_export_handoff_when_crosscheck_substitute_is_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            import_plan_path = root / "latest_membership_evidence_import_plan.json"
            source_intake_path = root / "latest_membership_evidence_source_intake_status.json"
            official_probe_path = root / "latest_sp500_official_export_probe.json"
            current_source_path = root / "latest_sp500_current_membership_sources.json"
            write_manifest(manifest_path)
            write_blocked_membership_import_plan(import_plan_path)
            write_membership_source_intake_status(source_intake_path)
            write_official_export_probe(official_probe_path)
            write_current_membership_sources(current_source_path)
            current_source = json.loads(current_source_path.read_text(encoding="utf-8-sig"))
            current_source.update(
                {
                    "status": "crosscheck_substitute_ready",
                    "source_trust_level": "crosscheck_substitute",
                    "membership_evidence": "secondary",
                    "recommended_followup": "refresh_crosscheck_substitute_weekly",
                    "formal_backtest_upgrade_allowed": False,
                }
            )
            current_source_path.write_text(
                json.dumps(current_source, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                membership_import_plan=import_plan_path,
                membership_evidence_source_intake_status=source_intake_path,
                sp500_official_export_probe=official_probe_path,
                current_membership_sources=current_source_path,
            )

            supplement_item = next(
                item
                for item in payload["items"]
                if item["action_code"] == "supplement_verified_membership_evidence"
            )
            self.assertNotIn("retry_with_logged_in_browser_or_manual_export", supplement_item["recommended_check"])
            self.assertNotIn("inputs/sp500_current_membership/official_constituents.csv", supplement_item["recommended_check"])
            self.assertNotIn("official_export_probe_status", supplement_item["source"])
            self.assertIn("crosscheck substitute", supplement_item["recommended_check"])
            self.assertIn("official S&P Global", supplement_item["recommended_check"])

    def test_supplement_action_prompts_next_batch_when_current_batch_search_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            import_plan_path = root / "latest_membership_evidence_import_plan.json"
            source_intake_path = root / "latest_membership_evidence_source_intake_status.json"
            current_source_path = root / "latest_sp500_current_membership_sources.json"
            write_manifest(manifest_path)
            write_blocked_membership_import_plan(import_plan_path)
            write_membership_source_intake_status(source_intake_path)
            write_current_membership_sources(current_source_path)
            source_intake = json.loads(source_intake_path.read_text(encoding="utf-8-sig"))
            source_intake.update(
                {
                    "pending_count": 40,
                    "official_source_not_found_count": 10,
                    "current_batch_pending_count": 0,
                    "current_batch_not_found_count": 10,
                    "current_batch_manual_checklist": [],
                }
            )
            source_intake_path.write_text(
                json.dumps(source_intake, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )
            current_source = json.loads(current_source_path.read_text(encoding="utf-8-sig"))
            current_source.update(
                {
                    "status": "crosscheck_substitute_ready",
                    "source_trust_level": "crosscheck_substitute",
                    "membership_evidence": "secondary",
                    "recommended_followup": "refresh_crosscheck_substitute_weekly",
                }
            )
            current_source_path.write_text(
                json.dumps(current_source, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                membership_import_plan=import_plan_path,
                membership_evidence_source_intake_status=source_intake_path,
                current_membership_sources=current_source_path,
            )

            supplement_item = next(
                item
                for item in payload["items"]
                if item["action_code"] == "supplement_verified_membership_evidence"
            )
            self.assertIn("current_batch_manual_checklist_count:0", supplement_item["source"])
            self.assertIn("official_source_not_found_count:10", supplement_item["source"])
            self.assertIn("pending_count:40", supplement_item["source"])
            self.assertIn("当前批次官方检索已记录", supplement_item["recommended_check"])
            self.assertIn("继续生成或处理下一批", supplement_item["recommended_check"])
            self.assertNotIn("优先处理 ABT, ADM, AEP, BA, BMY", supplement_item["recommended_check"])

    def test_omits_supplement_action_when_official_search_queue_is_exhausted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            import_plan_path = root / "latest_membership_evidence_import_plan.json"
            source_intake_path = root / "latest_membership_evidence_source_intake_status.json"
            write_manifest(manifest_path)
            write_blocked_membership_import_plan(import_plan_path)
            write_membership_source_intake_status(source_intake_path)
            source_intake = json.loads(source_intake_path.read_text(encoding="utf-8-sig"))
            source_intake.update(
                {
                    "status": "official_source_not_found_recorded",
                    "ready_to_import_count": 0,
                    "pending_count": 0,
                    "official_source_not_found_count": 50,
                    "current_batch_pending_count": 0,
                    "current_batch_not_found_count": 10,
                    "current_batch_manual_checklist": [],
                }
            )
            source_intake_path.write_text(
                json.dumps(source_intake, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                membership_import_plan=import_plan_path,
                membership_evidence_source_intake_status=source_intake_path,
            )

            self.assertNotIn(
                "supplement_verified_membership_evidence",
                [item["action_code"] for item in payload["items"]],
            )

    def test_adds_current_membership_source_review_action_when_missing_tickers_remain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            source_path = root / "latest_sp500_current_membership_sources.json"
            review_status_path = root / "latest_sp500_current_membership_source_review_status.json"
            write_manifest(manifest_path)
            write_current_membership_sources(source_path)
            write_current_membership_source_review_status(review_status_path)

            from weekly_action_items import build_weekly_action_items, render_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                current_membership_sources=source_path,
                current_membership_source_review_status=review_status_path,
            )
            report = render_weekly_action_items(payload)

            source_item = next(
                item
                for item in payload["items"]
                if item["action_code"] == "review_current_membership_source_status"
            )
            self.assertEqual(payload["item_count"], 9)
            self.assertEqual(source_item["category"], "backtest")
            self.assertIn("matched_count:1", source_item["source"])
            self.assertIn("missing_count:1", source_item["source"])
            self.assertIn("missing_ticker_review_queue_count:1", source_item["source"])
            self.assertIn("ZZZ", source_item["recommended_check"])
            self.assertIn("缺失复核队列 1 条", source_item["recommended_check"])
            self.assertIn("sp500_current_membership_source_review_queue.csv", source_item["recommended_check"])
            self.assertIn("latest_sp500_current_membership_source_review_status.json", source_item["recommended_check"])
            self.assertIn("sp500_current_membership_source_review_decisions_template.csv", source_item["recommended_check"])
            self.assertIn("决策模板 status=ready, matched_open=1, missing_open=0", source_item["recommended_check"])
            self.assertIn("review_status:review_needed", source_item["source"])
            self.assertIn("review_open_count:1", source_item["source"])
            self.assertIn("review_resolved_count:0", source_item["source"])
            self.assertIn("decisions_template_status:ready", source_item["source"])
            self.assertIn("decisions_template_matched_open_count:1", source_item["source"])
            self.assertIn("decisions_template_missing_open_count:0", source_item["source"])
            self.assertIn("review_decision_status:missing", source_item["source"])
            self.assertIn("manual_decision_next_step:fill_decisions_template", source_item["source"])
            self.assertIn("decision_pending_tickers:ZZZ", source_item["source"])
            self.assertIn("状态报告 open=1, resolved=0", source_item["recommended_check"])
            self.assertIn("手工决策下一步=fill_decisions_template", source_item["recommended_check"])
            self.assertIn("待决策 ticker=ZZZ", source_item["recommended_check"])
            self.assertIn("latest_sp500_current_membership_sources.json", source_item["recommended_check"])
            self.assertIn("sp500_current_membership_source_intake_template.csv", source_item["recommended_check"])
            self.assertIn("review_current_membership_source_status", report)

    def test_adds_current_membership_source_file_action_when_official_csv_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            source_path = root / "latest_sp500_current_membership_sources.json"
            inbox_status_path = root / "latest_sp500_current_membership_source_inbox_status.json"
            write_manifest(manifest_path)
            write_current_membership_sources(source_path)
            write_current_membership_source_inbox_status(inbox_status_path)
            inbox_status = json.loads(inbox_status_path.read_text(encoding="utf-8-sig"))
            inbox_status.update(
                {
                    "status": "invalid",
                    "source_file_validation_status": "invalid",
                    "source_file_rejection_reason": "intake_template_submitted_as_official_csv",
                    "source_file_available_columns": [
                        "expected_ticker",
                        "intake_status",
                        "required_source_url",
                    ],
                    "next_action": "provide_valid_official_constituents_csv",
                }
            )
            inbox_status_path.write_text(
                json.dumps(inbox_status, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            source.update(
                {
                    "as_of_date": "2026-07-04",
                    "status": "fetch_failed",
                    "matched_count": 0,
                    "missing_count": 50,
                    "missing_tickers": ["ABT", "ADM", "AEP"],
                    "intake_expected_count": 50,
                    "intake_matched_count": 0,
                    "intake_missing_count": 50,
                    "intake_missing_tickers": ["ABT", "ADM", "AEP"],
                    "next_action": "retry_official_source_or_provide_official_constituents_csv",
                    "recommended_followup": "provide_official_constituents_csv",
                    "official_export_url": (
                        "https://www.spglobal.com/spdji/en/idsexport/file.xls?"
                        "redesignExport=true&languageId=1&selectedModule=Constituents&"
                        "selectedSubModule=ConstituentsFullList&indexId=340"
                    ),
                    "source_file_required_columns": ["Symbol", "Ticker"],
                    "source_file_next_command": (
                        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                        "scripts\\run_sp500_current_membership_sources.ps1 "
                        "-ProjectRoot <project_root> -SourceFile <official_constituents.csv>"
                    ),
                    "source_file_dry_run_command": (
                        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                        "scripts\\run_sp500_current_membership_sources.ps1 "
                        "-ProjectRoot <project_root> -DryRun -SourceFile <official_constituents.csv>"
                    ),
                    "source_file_request_file": "outputs/automation/sp500_current_membership_source_file_request.md",
                    "source_file_inbox": "inputs/sp500_current_membership/official_constituents.csv",
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
                    "source_file_inbox_exists": False,
                    "source_file_validation_status": "missing",
                    "source_file_acceptance_criteria": [
                        "has_symbol_or_ticker_column",
                        "at_least_400_tickers",
                        "official_spglobal_constituents_export",
                    ],
                    "source_file_user_agent_hint": (
                        "Set SEC_USER_AGENT or pass -UserAgent <user_agent> when retrying official "
                        "S&P Global fetches through PowerShell entrypoints."
                    ),
                    "source_quality_flags": ["official_ticker_count_below_minimum"],
                    "fetch_error_type": "network_permission_denied",
                    "fetch_retryable_without_environment_change": False,
                    "fetch_error_next_action": "provide_official_constituents_csv_or_fix_network_permission",
                }
            )
            source_path.write_text(
                json.dumps(source, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items, render_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                current_membership_sources=source_path,
                current_membership_source_inbox_status=inbox_status_path,
            )
            report = render_weekly_action_items(payload)

            self.assertEqual(payload["as_of_date"], "2026-07-04")
            source_item = next(
                item
                for item in payload["items"]
                if item["action_code"] == "provide_official_constituents_csv"
            )
            self.assertEqual(source_item["category"], "backtest")
            self.assertIn("recommended_followup:provide_official_constituents_csv", source_item["source"])
            self.assertIn("source_file_required_columns:Symbol, Ticker", source_item["source"])
            self.assertIn(
                "source_file_accepted_ticker_columns:Symbol, Ticker, Ticker Symbol, Constituent Ticker, Constituent Symbol",
                source_item["source"],
            )
            self.assertIn(
                "source_file_acceptance_criteria:has_symbol_or_ticker_column, at_least_400_tickers",
                source_item["source"],
            )
            self.assertIn(
                "official_spglobal_constituents_export",
                source_item["source"],
            )
            self.assertIn("source_file_request_file:outputs/automation/sp500_current_membership_source_file_request.md", source_item["source"])
            self.assertIn("official_export_url:https://www.spglobal.com/spdji/en/idsexport/file.xls", source_item["source"])
            self.assertIn("source_file_inbox:inputs/sp500_current_membership/official_constituents.csv", source_item["source"])
            self.assertIn("source_file_inbox_exists:false", source_item["source"])
            self.assertIn("source_file_validation_status:missing", source_item["source"])
            self.assertIn("source_file_inbox_status:invalid", source_item["source"])
            self.assertIn("source_file_inbox_next_action:provide_valid_official_constituents_csv", source_item["source"])
            self.assertIn(
                "source_file_rejection_reason:intake_template_submitted_as_official_csv",
                source_item["source"],
            )
            self.assertIn("source_file_inbox_external_input_required:true", source_item["source"])
            self.assertIn("source_file_inbox_blocking_reason:official_constituents_csv_missing", source_item["source"])
            self.assertIn(
                "source_file_inbox_available_columns:expected_ticker, intake_status, required_source_url",
                source_item["source"],
            )
            self.assertIn("fetch_error_type:network_permission_denied", source_item["source"])
            self.assertIn("fetch_retryable_without_environment_change:false", source_item["source"])
            self.assertIn("source_file_user_agent_hint:Set SEC_USER_AGENT", source_item["source"])
            self.assertIn("-UserAgent <user_agent>", source_item["source"])
            self.assertIn(
                "fetch_error_next_action:provide_official_constituents_csv_or_fix_network_permission",
                source_item["source"],
            )
            self.assertIn("latest_sp500_current_membership_sources.json", source_item["recommended_check"])
            self.assertIn("sp500_current_membership_source_intake_template.csv", source_item["recommended_check"])
            self.assertIn("sp500_current_membership_source_file_request.md", source_item["recommended_check"])
            self.assertIn("official_export_url=https://www.spglobal.com/spdji/en/idsexport/file.xls", source_item["recommended_check"])
            self.assertIn("inputs/sp500_current_membership/official_constituents.csv", source_item["recommended_check"])
            self.assertIn("inbox_status=invalid", source_item["recommended_check"])
            self.assertIn("fetch_error_type=network_permission_denied", source_item["recommended_check"])
            self.assertIn("fetch_retryable_without_environment_change=false", source_item["recommended_check"])
            self.assertIn(
                "source_file_rejection_reason=intake_template_submitted_as_official_csv",
                source_item["recommended_check"],
            )
            self.assertIn(
                "fetch_error_next_action=provide_official_constituents_csv_or_fix_network_permission",
                source_item["recommended_check"],
            )
            self.assertIn(
                "inbox_available_columns=expected_ticker, intake_status, required_source_url",
                source_item["recommended_check"],
            )
            self.assertIn("提供官方 S&P Global constituents CSV", source_item["recommended_check"])
            self.assertIn("Symbol, Ticker", source_item["recommended_check"])
            self.assertIn("Ticker Symbol, Constituent Ticker, Constituent Symbol", source_item["recommended_check"])
            self.assertIn(
                "accepted_ticker_columns:Symbol, Ticker, Ticker Symbol, Constituent Ticker, Constituent Symbol",
                source_item["recommended_check"],
            )
            self.assertIn(
                "acceptance_criteria:has_symbol_or_ticker_column, at_least_400_tickers, official_spglobal_constituents_export",
                source_item["recommended_check"],
            )
            self.assertIn("-DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv", source_item["recommended_check"])
            self.assertIn("run_sp500_current_membership_sources.ps1", source_item["recommended_check"])
            self.assertIn("-SourceFileInbox inputs/sp500_current_membership/official_constituents.csv", source_item["recommended_check"])
            self.assertIn("latest_sp500_current_membership_source_inbox_status.json", source_item["recommended_check"])
            self.assertIn("inbox_next_action=provide_valid_official_constituents_csv", source_item["recommended_check"])
            self.assertIn("inbox_external_input_required=true", source_item["recommended_check"])
            self.assertIn("inbox_blocking_reason=official_constituents_csv_missing", source_item["recommended_check"])
            self.assertIn("parsed_official_ticker_count=0", source_item["recommended_check"])
            self.assertIn("inbox_intake_missing_count=50", source_item["recommended_check"])
            self.assertIn("source_file_user_agent_hint=Set SEC_USER_AGENT", source_item["recommended_check"])
            self.assertIn("-UserAgent <user_agent>", source_item["recommended_check"])
            self.assertIn("at_least_400_tickers", source_item["recommended_check"])
            self.assertIn("source_file_user_agent_hint", report)
            self.assertIn("official_export_url", report)
            self.assertIn("-UserAgent <user_agent>", report)
            self.assertIn("provide_official_constituents_csv", report)

    def test_skips_generic_backtest_review_when_official_csv_action_covers_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            backtest_path = root / "latest_backtest_evidence_review.json"
            source_path = root / "latest_sp500_current_membership_sources.json"
            inbox_status_path = root / "latest_sp500_current_membership_source_inbox_status.json"
            write_manifest(manifest_path)
            write_backtest_evidence_review(backtest_path)
            write_current_membership_sources(source_path)
            write_current_membership_source_inbox_status(inbox_status_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            manifest["automation_priority_actions"] = ["review_backtest_evidence"]
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            source.update(
                {
                    "status": "fetch_failed",
                    "matched_count": 0,
                    "missing_count": 50,
                    "missing_tickers": ["ABT", "ADM"],
                    "intake_missing_count": 50,
                    "intake_missing_tickers": ["ABT", "ADM"],
                    "recommended_followup": "provide_official_constituents_csv",
                    "fetch_error_type": "official_source_access_denied",
                    "fetch_retryable_without_environment_change": False,
                    "fetch_error_next_action": "provide_official_constituents_csv",
                }
            )
            source_path.write_text(
                json.dumps(source, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                backtest_evidence_review=backtest_path,
                current_membership_sources=source_path,
                current_membership_source_inbox_status=inbox_status_path,
            )

            actions = [item["action_code"] for item in payload["items"]]
            self.assertEqual(actions, ["provide_official_constituents_csv"])

    def test_backtest_review_action_uses_decision_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            backtest_path = root / "latest_backtest_evidence_review.json"
            write_manifest(manifest_path)
            write_backtest_evidence_review(backtest_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            manifest["automation_priority_actions"] = ["review_backtest_evidence"]
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                backtest_evidence_review=backtest_path,
            )

            self.assertEqual(payload["item_count"], 1)
            item = payload["items"][0]
            self.assertEqual(item["action_code"], "review_backtest_evidence")
            self.assertIn("latest_backtest_evidence_review.md", item["recommended_check"])
            self.assertIn("do_not_expand_backtest_sample", item["recommended_check"])
            self.assertIn("verified_membership_ratio=15.60%", item["recommended_check"])
            self.assertIn("weak_evidence_rows=3382", item["recommended_check"])
            self.assertIn("evidence_gate=blocked", item["recommended_check"])
            self.assertIn("gate_decision=verified_only_no_expansion", item["recommended_check"])
            self.assertIn("blocking_tiers=secondary,weak", item["recommended_check"])
            self.assertIn("不得自动更新 historical_membership.csv", item["recommended_check"])
            self.assertIn("正式模型不得自动升级", item["recommended_check"])

    def test_evidence_ceiling_suppresses_historical_evidence_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            backtest_path = root / "latest_backtest_evidence_review.json"
            import_plan_path = root / "latest_membership_evidence_import_plan.json"
            write_manifest(manifest_path)
            write_closed_backtest_evidence_review(backtest_path)
            write_membership_import_plan(import_plan_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            manifest["automation_priority_actions"] = ["review_backtest_evidence"]
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                membership_import_plan=import_plan_path,
                backtest_evidence_review=backtest_path,
            )

            action_codes = [item["action_code"] for item in payload["items"]]
            self.assertNotIn("review_backtest_evidence", action_codes)
            self.assertNotIn("supplement_verified_membership_evidence", action_codes)
            self.assertNotIn("run_membership_evidence_apply_preview", action_codes)

    def test_official_csv_action_includes_source_file_inbox_fingerprint_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            source_path = root / "latest_sp500_current_membership_sources.json"
            inbox_status_path = root / "latest_sp500_current_membership_source_inbox_status.json"
            write_manifest(manifest_path)
            write_current_membership_sources(source_path)
            write_current_membership_source_inbox_status(inbox_status_path)

            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            source.update(
                {
                    "status": "source_file_required",
                    "recommended_followup": "provide_official_constituents_csv",
                    "source_file_inbox": "inputs/sp500_current_membership/official_constituents.csv",
                    "source_file_inbox_exists": True,
                    "source_file_validation_status": "ready",
                    "source_file_request_file": "outputs/automation/sp500_current_membership_source_file_request.md",
                }
            )
            source_path.write_text(
                json.dumps(source, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            inbox_status = json.loads(inbox_status_path.read_text(encoding="utf-8-sig"))
            inbox_status.update(
                {
                    "status": "ready_for_import_preview",
                    "source_file_inbox_exists": True,
                    "source_file_validation_status": "ready",
                    "parsed_official_ticker_count": 500,
                    "source_file_inbox_size_bytes": 12345,
                    "source_file_inbox_sha256": "a" * 64,
                    "source_file_inbox_modified_at": "2026-07-04T03:12:00+00:00",
                    "external_input_required": False,
                    "blocking_reason": "",
                    "blocking_input": "",
                    "next_action": "run_source_file_inbox_dry_run_then_import",
                }
            )
            inbox_status_path.write_text(
                json.dumps(inbox_status, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                current_membership_sources=source_path,
                current_membership_source_inbox_status=inbox_status_path,
            )

            source_item = next(
                item
                for item in payload["items"]
                if item["action_code"] == "provide_official_constituents_csv"
            )
            self.assertIn("source_file_inbox_size_bytes:12345", source_item["source"])
            self.assertIn("source_file_inbox_sha256:" + "a" * 64, source_item["source"])
            self.assertIn(
                "source_file_inbox_modified_at:2026-07-04T03:12:00+00:00",
                source_item["source"],
            )
            self.assertIn("inbox_size_bytes=12345", source_item["recommended_check"])
            self.assertIn("inbox_sha256=" + "a" * 64, source_item["recommended_check"])
            self.assertIn(
                "inbox_modified_at=2026-07-04T03:12:00+00:00",
                source_item["recommended_check"],
            )

    def test_current_membership_source_action_defaults_to_inbox_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            source_path = root / "latest_sp500_current_membership_sources.json"
            write_manifest(manifest_path)
            write_current_membership_sources(source_path)
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            source.update(
                {
                    "status": "fetch_failed",
                    "matched_count": 0,
                    "missing_count": 50,
                    "missing_tickers": ["ABT", "ADM"],
                    "intake_missing_count": 50,
                    "intake_missing_tickers": ["ABT", "ADM"],
                    "next_action": "retry_official_source_or_provide_official_constituents_csv",
                    "recommended_followup": "provide_official_constituents_csv",
                    "source_file_required_columns": ["Symbol", "Ticker"],
                    "source_file_request_file": "outputs/automation/sp500_current_membership_source_file_request.md",
                    "source_file_inbox": "inputs/sp500_current_membership/official_constituents.csv",
                    "source_file_inbox_exists": False,
                    "source_file_validation_status": "missing",
                    "source_file_acceptance_criteria": [
                        "has_symbol_or_ticker_column",
                        "at_least_400_tickers",
                    ],
                }
            )
            source.pop("source_file_next_command", None)
            source.pop("source_file_dry_run_command", None)
            source.pop("source_file_inbox_next_command", None)
            source.pop("source_file_inbox_dry_run_command", None)
            source_path.write_text(
                json.dumps(source, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                current_membership_sources=source_path,
            )

            source_item = next(
                item
                for item in payload["items"]
                if item["action_code"] == "provide_official_constituents_csv"
            )
            self.assertIn(
                "-DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv",
                source_item["recommended_check"],
            )
            self.assertIn(
                "-SourceFileInbox inputs/sp500_current_membership/official_constituents.csv",
                source_item["recommended_check"],
            )
            self.assertNotIn("-SourceFile <official_constituents.csv>", source_item["recommended_check"])

    def test_adds_backlog_reduction_action_when_weekly_action_items_are_increasing(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "latest_self_analysis_manifest.json"
            write_manifest(manifest_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            manifest["weekly_delivery_action_items_actual_count"] = 9
            manifest["weekly_delivery_action_items_actual_count_delta"] = 3
            manifest["weekly_delivery_action_items_actual_count_trend"] = "increasing"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items, render_weekly_action_items

            payload = build_weekly_action_items(manifest_path)
            report = render_weekly_action_items(payload)

            reduction = payload["items"][-1]
            self.assertEqual(payload["item_count"], 9)
            self.assertEqual(reduction["action_code"], "reduce_weekly_action_backlog")
            self.assertEqual(reduction["category"], "delivery_health")
            self.assertIn("actual_count:9", reduction["source"])
            self.assertIn("delta:3", reduction["source"])
            self.assertIn("trend:increasing", reduction["source"])
            self.assertIn("latest_weekly_action_items.json", reduction["recommended_check"])
            self.assertIn("manual_review_decisions.csv", reduction["recommended_check"])
            self.assertIn("人工待办压降", reduction["title"])
            self.assertIn("不修改正式模型参数", reduction["recommended_check"])
            self.assertIn("reduce_weekly_action_backlog", report)
            self.assertEqual(payload["backlog_reduction_plan"][0]["category"], "delivery_health")
            self.assertEqual(payload["backlog_reduction_plan"][0]["count"], 3)
            self.assertEqual(
                payload["backlog_reduction_plan"][0]["first_action"],
                "review_manual_review_backlog",
            )
            self.assertEqual(payload["backlog_reduction_plan"][0]["target_count_after_close"], 0)
            self.assertIn("manual_review_decisions.csv", payload["backlog_reduction_plan"][0]["close_condition"])
            self.assertEqual(
                payload["backlog_reduction_plan"][0]["actions"],
                [
                    "review_manual_review_backlog",
                    "review_delivery_health_issues",
                    "reduce_weekly_action_backlog",
                ],
            )
            self.assertEqual(payload["backlog_reduction_plan"][1]["category"], "data_quality")
            self.assertEqual(payload["backlog_reduction_plan"][1]["count"], 2)
            self.assertEqual(payload["backlog_reduction_plan"][1]["first_action"], "review_data_quality_score")
            self.assertEqual(payload["backlog_reduction_plan"][1]["target_count_after_close"], 0)
            self.assertIn("## 待办压降分流", report)
            self.assertIn("| delivery_health | 3 |", report)
            self.assertIn("| data_quality | 2 |", report)
            self.assertLess(report.index("## 待办压降分流"), report.index("## 处理事项"))
            self.assertLess(report.index("## 待办压降分流"), report.index("action_code"))

    def test_backlog_reduction_plan_exposes_official_csv_blocking_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            source_path = root / "latest_sp500_current_membership_sources.json"
            inbox_status_path = root / "latest_sp500_current_membership_source_inbox_status.json"
            write_manifest(manifest_path)
            write_current_membership_sources(source_path)
            write_current_membership_source_inbox_status(inbox_status_path)
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            source.update(
                {
                    "status": "fetch_failed",
                    "matched_count": 0,
                    "missing_count": 50,
                    "missing_tickers": ["ABT", "ADM"],
                    "intake_expected_count": 50,
                    "intake_matched_count": 0,
                    "intake_missing_count": 50,
                    "intake_missing_tickers": ["ABT", "ADM"],
                    "next_action": "provide_official_constituents_csv_or_fix_network_permission",
                    "recommended_followup": "provide_official_constituents_csv",
                    "source_file_inbox": "inputs/sp500_current_membership/official_constituents.csv",
                    "fetch_error_type": "network_permission_denied",
                    "fetch_retryable_without_environment_change": False,
                    "fetch_error_next_action": "provide_official_constituents_csv_or_fix_network_permission",
                }
            )
            source_path.write_text(
                json.dumps(source, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                current_membership_sources=source_path,
                current_membership_source_inbox_status=inbox_status_path,
            )

            backtest_plan = next(
                entry
                for entry in payload["backlog_reduction_plan"]
                if entry["category"] == "backtest"
            )
            self.assertEqual(backtest_plan["first_action"], "provide_official_constituents_csv")
            self.assertIn(
                "inputs/sp500_current_membership/official_constituents.csv",
                backtest_plan["close_condition"],
            )
            self.assertIn("external_input_required=true", backtest_plan["close_condition"])

    def test_uses_backlog_reduction_template_when_action_comes_from_manifest_priority_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "latest_self_analysis_manifest.json"
            write_manifest(manifest_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            manifest["automation_priority_actions"].append("reduce_weekly_action_backlog")
            manifest["weekly_delivery_action_items_actual_count"] = 10
            manifest["weekly_delivery_action_items_actual_count_delta"] = 4
            manifest["weekly_delivery_action_items_actual_count_trend"] = "increasing"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items

            payload = build_weekly_action_items(manifest_path)

            reduction = next(
                item
                for item in payload["items"]
                if item["action_code"] == "reduce_weekly_action_backlog"
            )
            self.assertEqual(reduction["category"], "delivery_health")
            self.assertIn("人工待办压降", reduction["title"])
            self.assertIn("actual_count:10", reduction["source"])
            self.assertIn("delta:4", reduction["source"])
            self.assertNotIn("复查动作码", reduction["title"])
            self.assertEqual(payload["backlog_reduction_plan"][0]["category"], "delivery_health")
            self.assertEqual(payload["backlog_reduction_plan"][0]["count"], 3)

    def test_adds_prediction_unavailable_action_when_forecast_gap_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            forecast_path = root / "latest_forecast_performance_review.json"
            write_manifest(manifest_path)
            write_forecast_performance_review(forecast_path)

            from weekly_action_items import build_weekly_action_items, render_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                forecast_performance=forecast_path,
            )
            report = render_weekly_action_items(payload)

            action = next(
                item
                for item in payload["items"]
                if item["action_code"] == "review_prediction_unavailable_signals"
            )
            self.assertEqual(action["category"], "model_tracking")
            self.assertIn("prediction_unavailable:87", action["source"])
            self.assertIn("pending_maturity:0", action["source"])
            self.assertIn("mature_evaluations:0", action["source"])
            self.assertIn("latest_forecast_performance_review.json", action["recommended_check"])
            self.assertIn("formal model parameters", action["recommended_check"])
            self.assertIn("review_prediction_unavailable_signals", report)

    def test_ignores_legacy_only_prediction_unavailable_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            forecast_path = root / "latest_forecast_performance_review.json"
            write_manifest(manifest_path)
            write_forecast_performance_review(
                forecast_path,
                prediction_unavailable=87,
                latest_prediction_unavailable=0,
                legacy_prediction_unavailable=87,
            )

            from weekly_action_items import build_weekly_action_items, render_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                forecast_performance=forecast_path,
            )
            report = render_weekly_action_items(payload)

            self.assertNotIn(
                "review_prediction_unavailable_signals",
                [item["action_code"] for item in payload["items"]],
            )
            self.assertNotIn("review_prediction_unavailable_signals", report)

    def test_cli_writes_json_and_markdown_action_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            output_path = root / "latest_weekly_action_items.json"
            report_path = root / "latest_weekly_action_items.md"
            write_manifest(manifest_path)
            write_data_health_review(root / "latest_data_health_review.json")
            write_candidate_findings_review(root / "latest_candidate_findings_review.json")
            write_current_membership_source_inbox_status(
                root / "latest_sp500_current_membership_source_inbox_status.json"
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "weekly_action_items.py"),
                    "--manifest",
                    str(manifest_path),
                    "--output",
                    str(output_path),
                    "--report",
                    str(report_path),
                    "--membership-import-plan",
                    str(root / "latest_membership_evidence_import_plan.json"),
                    "--membership-evidence-source-intake-status",
                    str(root / "latest_membership_evidence_source_intake_status.json"),
                    "--sp500-official-export-probe",
                    str(root / "latest_sp500_official_export_probe.json"),
                    "--current-membership-sources",
                    str(root / "latest_sp500_current_membership_sources.json"),
                    "--forecast-performance",
                    str(root / "latest_forecast_performance_review.json"),
                    "--manual-review-queue",
                    str(root / "latest_manual_review_queue.csv"),
                    "--data-health-review",
                    str(root / "latest_data_health_review.json"),
                    "--candidate-findings-review",
                    str(root / "latest_candidate_findings_review.json"),
                    "--current-membership-source-inbox-status",
                    str(root / "latest_sp500_current_membership_source_inbox_status.json"),
                    "--human-decision-inbox",
                    str(root / "latest_human_decision_inbox.json"),
                    "--weekly-delivery-history",
                    str(root / "latest_weekly_delivery_history_summary.json"),
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
            payload = json.loads(output_path.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["action_items_schema"], "weekly_action_items")
            self.assertEqual(payload["item_count"], 8)
            self.assertIn("review_delivery_health_issues", output)
            self.assertIn("每周人工处理清单", report_path.read_text(encoding="utf-8-sig"))

    def test_powershell_wrapper_static_contract(self):
        script = (PROJECT_ROOT / "scripts" / "show_weekly_action_items.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("weekly_action_items.py", script)
        self.assertIn("latest_self_analysis_manifest.json", script)
        self.assertIn("latest_weekly_action_items.json", script)
        self.assertIn("latest_weekly_action_items.md", script)
        self.assertIn("--manifest", script)
        self.assertIn("--output", script)
        self.assertIn("--report", script)
        self.assertIn("--human-decision-inbox", script)
        self.assertIn("latest_human_decision_inbox.json", script)
        self.assertIn("--extended-shadow-validation-tracker", script)
        self.assertIn("latest_extended_shadow_validation_tracker.json", script)
        self.assertIn("--membership-import-plan", script)
        self.assertIn("latest_membership_evidence_source_intake_status.json", script)
        self.assertIn("--membership-evidence-source-intake-status", script)
        self.assertIn("latest_sp500_official_export_probe.json", script)
        self.assertIn("--sp500-official-export-probe", script)
        self.assertIn("--current-membership-sources", script)
        self.assertIn("--current-membership-source-review-status", script)
        self.assertIn("--forecast-performance", script)
        self.assertIn("latest_sp500_current_membership_sources.json", script)
        self.assertIn("latest_sp500_current_membership_source_review_status.json", script)
        self.assertIn("latest_sp500_current_membership_source_inbox_status.json", script)
        self.assertIn("--current-membership-source-inbox-status", script)
        self.assertIn("latest_forecast_performance_review.json", script)
        self.assertIn("latest_manual_review_queue.csv", script)
        self.assertIn("--manual-review-queue", script)
        self.assertIn("latest_data_health_review.json", script)
        self.assertIn("--data-health-review", script)
        self.assertIn("latest_candidate_findings_review.json", script)
        self.assertIn("--candidate-findings-review", script)
        self.assertIn("latest_backtest_evidence_review.json", script)
        self.assertIn("--backtest-evidence-review", script)
        self.assertIn("codex-primary-runtime", script)

    def test_first_one_month_waiting_action_is_monitor_only(self):
        from weekly_action_items import _action_template

        manifest = {
            "first_one_month_forecast_evaluation": {
                "status": "awaiting_maturity",
                "expected_sample_count": 37,
                "one_month_valid_count": 0,
                "recommended_action": "wait_for_one_month_maturity",
            }
        }

        action = _action_template("wait_for_one_month_maturity", manifest)

        self.assertEqual(action["category"], "forecast_performance")
        self.assertEqual(action["priority"], "monitor")
        self.assertIn("37", action["recommended_check"])


if __name__ == "__main__":
    unittest.main()
