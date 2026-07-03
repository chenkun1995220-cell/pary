import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path


PRE_SUBMIT_REVIEW_SCHEMA = "pre_submit_review"
PRE_SUBMIT_REVIEW_VERSION = 1
HISTORY_SCHEMA = "pre_submit_review_history"
HISTORY_VERSION = 1
EXPECTED_COLLABORATION_EXECUTION_MODE = "single_codex_with_gpt55_review_checklist"

DEFAULT_CHECKLIST = "docs/提交前复核清单.md"
DEFAULT_GOVERNANCE_DOC = "docs/中期目标与模型协作规范.md"
DEFAULT_OUTPUT = "outputs/automation/latest_pre_submit_review.json"
DEFAULT_REPORT = "outputs/automation/latest_pre_submit_review.md"
DEFAULT_HISTORY = "outputs/automation/pre_submit_review_history.jsonl"

GOVERNANCE_REQUIRED_TERMS = [
    "gpt5.3-codex-spark",
    "gpt5.5",
    "快速迭代",
    "关键复核",
    "正式收口",
    "组合开发习惯",
    "证据三件套",
    "可回放",
    "回退策略",
    "收敛迭代",
    "正式发布判断",
    "影子层",
    "不得自动修改正式模型参数",
    "未启用自动多模型协作",
    "single_codex_with_gpt55_review_checklist",
]

INPUT_SPECS = {
    "weekly_delivery_check": {
        "path": "outputs/automation/latest_weekly_delivery_check.json",
        "schema_field": "delivery_check_schema",
        "schema_value": "weekly_delivery_check",
        "version_field": "delivery_check_version",
        "version_value": 1,
    },
    "weekly_ops_check": {
        "path": "outputs/automation/latest_weekly_ops_check.json",
        "schema_field": "ops_check_schema",
        "schema_value": "weekly_ops_check",
        "version_field": "ops_check_version",
        "version_value": 1,
    },
    "automation_check": {
        "path": "outputs/automation/latest_automation_check.json",
        "schema_field": "check_schema",
        "schema_value": "weekly_automation_check",
        "version_field": "check_version",
        "version_value": 1,
    },
    "weekly_conclusion": {
        "path": "outputs/automation/latest_weekly_conclusion.json",
        "schema_field": "conclusion_schema",
        "schema_value": "weekly_conclusion",
        "version_field": "conclusion_version",
        "version_value": 1,
    },
    "weekly_action_items": {
        "path": "outputs/automation/latest_weekly_action_items.json",
        "schema_field": "action_items_schema",
        "schema_value": "weekly_action_items",
        "version_field": "action_items_version",
        "version_value": 1,
    },
    "data_health_review": {
        "path": "outputs/automation/latest_data_health_review.json",
        "schema_field": "review_schema",
        "schema_value": "data_health_review",
        "version_field": "review_version",
        "version_value": 1,
    },
    "backtest_evidence_review": {
        "path": "outputs/automation/latest_backtest_evidence_review.json",
        "schema_field": "review_schema",
        "schema_value": "backtest_evidence_review",
        "version_field": "review_version",
        "version_value": 1,
    },
    "membership_evidence_import_plan": {
        "path": "outputs/automation/latest_membership_evidence_import_plan.json",
        "schema_field": "review_schema",
        "schema_value": "membership_evidence_import_plan",
        "version_field": "review_version",
        "version_value": 1,
    },
    "membership_evidence_apply_preview": {
        "path": "outputs/automation/latest_membership_evidence_apply_preview.json",
        "schema_field": "preview_schema",
        "schema_value": "membership_evidence_apply_preview",
        "version_field": "preview_version",
        "version_value": 1,
    },
    "sp500_current_membership_sources": {
        "path": "outputs/automation/latest_sp500_current_membership_sources.json",
        "schema_field": "source_schema",
        "schema_value": "sp500_current_membership_sources",
        "version_field": "source_version",
        "version_value": 1,
    },
    "sp500_current_membership_source_review_status": {
        "path": "outputs/automation/latest_sp500_current_membership_source_review_status.json",
        "schema_field": "review_status_schema",
        "schema_value": "sp500_current_membership_source_review_status",
        "version_field": "review_status_version",
        "version_value": 1,
    },
    "sp500_current_membership_source_inbox_status": {
        "path": "outputs/automation/latest_sp500_current_membership_source_inbox_status.json",
        "schema_field": "status_schema",
        "schema_value": "sp500_current_membership_source_inbox_status",
        "version_field": "status_version",
        "version_value": 1,
    },
    "candidate_findings_review": {
        "path": "outputs/automation/latest_candidate_findings_review.json",
        "schema_field": "review_schema",
        "schema_value": "candidate_findings_review",
        "version_field": "review_version",
        "version_value": 1,
    },
    "forecast_performance_review": {
        "path": "outputs/automation/latest_forecast_performance_review.json",
        "schema_field": "review_schema",
        "schema_value": "forecast_performance_review",
        "version_field": "review_version",
        "version_value": 1,
    },
    "medium_term_goal_review": {
        "path": "outputs/automation/latest_medium_term_goal_review.json",
        "schema_field": "review_schema",
        "schema_value": "medium_term_goal_review",
        "version_field": "review_version",
        "version_value": 1,
    },
    "model_handoff_review": {
        "path": "outputs/automation/latest_model_handoff_review.json",
        "schema_field": "handoff_schema",
        "schema_value": "model_handoff_review",
        "version_field": "handoff_version",
        "version_value": 1,
    },
}

FORECAST_PERFORMANCE_REQUIRED_TRACKING_FIELDS = [
    "latest_prediction_unavailable_count",
    "legacy_prediction_unavailable_count",
    "forecast_history_short_signal_missing_count",
    "latest_short_signal_missing_count",
    "legacy_short_signal_missing_count",
    "next_one_week_evaluation_date",
    "next_one_month_evaluation_date",
]

MEDIUM_TERM_GOAL_REVIEW_REQUIRED_FIELDS = [
    "strategy_code",
    "strategy_title",
    "period",
    "overall_completion_percent",
    "current_target_total_completion_percent",
    "development_completion_policy",
    "task_closeout_snapshot",
    "goals",
    "automatic_multi_model_collaboration_enabled",
    "collaboration_execution_mode",
    "collaboration_boundary_note",
]

MEDIUM_TERM_CLOSEOUT_REQUIRED_FIELDS = [
    "current_module",
    "module_completion_percent",
    "medium_term_overall_completion_percent",
    "current_target_total_completion_percent",
]

MODEL_HANDOFF_REQUIRED_FIELDS = [
    "current_module",
    "module_completion_percent",
    "medium_term_overall_completion_percent",
    "automatic_multi_model_collaboration_enabled",
    "collaboration_execution_mode",
    "collaboration_boundary_note",
    "spark_execution_summary",
    "gpt55_review_checklist",
    "validation_commands",
    "risk_notes",
    "formal_release_allowed",
]

CANDIDATE_FINDINGS_REQUIRED_QUALITY_FIELDS = [
    "candidate_count",
    "field_complete_count",
    "missing_field_count",
    "risk_coverage_count",
    "risk_missing_count",
    "risk_review_count",
    "formal_model_change_allowed",
]

DATA_HEALTH_REQUIRED_QUALITY_FIELDS = [
    "blocked_candidate_count",
    "refetch_gap_count",
    "manual_financial_review_count",
]

BACKTEST_EVIDENCE_REQUIRED_QUALITY_FIELDS = [
    "weeks_completed",
    "weeks_failed",
    "verified_membership_ratio",
    "weak_evidence_rows",
    "weak_evidence_weeks",
    "formal_model_upgrade_allowed",
]

MEMBERSHIP_EVIDENCE_IMPORT_PLAN_REQUIRED_FIELDS = [
    "gap_count",
    "queue_count",
    "ready_to_import_count",
    "missing_source_count",
    "invalid_source_count",
    "ready_to_import_weeks_affected",
    "missing_source_weeks_affected",
    "invalid_source_weeks_affected",
    "formal_backtest_upgrade_allowed",
]

MEMBERSHIP_EVIDENCE_APPLY_PREVIEW_REQUIRED_FIELDS = [
    "membership_row_count",
    "eligible_ticker_count",
    "preview_row_count",
    "preview_weeks_affected",
    "invalid_source_ticker_count",
    "already_verified_row_count",
    "applied_to_historical_membership",
    "formal_backtest_upgrade_allowed",
]

SP500_CURRENT_MEMBERSHIP_SOURCE_REQUIRED_FIELDS = [
    "source_url",
    "requested_count",
    "parsed_official_ticker_count",
    "matched_count",
    "missing_count",
    "missing_ticker_review_queue",
    "next_action",
    "source_file_required_columns",
    "formal_backtest_upgrade_allowed",
]

SP500_CURRENT_MEMBERSHIP_SOURCE_REVIEW_STATUS_REQUIRED_FIELDS = [
    "queue_file",
    "decisions_template_file",
    "queue_exists",
    "queue_total_count",
    "open_count",
    "resolved_count",
    "open_items",
    "next_action",
    "formal_backtest_upgrade_allowed",
]

SP500_CURRENT_MEMBERSHIP_SOURCE_REVIEW_DECISION_OPTIONS = {
    "official_absent",
    "source_refresh_required",
    "keep_open",
    "not_applicable",
}

SP500_CURRENT_MEMBERSHIP_SOURCE_REVIEW_DECISION_REQUIRED_FIELDS = {
    "ticker",
    "review_decision",
    "official_source_checked",
    "required_source_url",
    "issue_type",
    "recommended_check",
    "decision_notes",
}

SP500_CURRENT_MEMBERSHIP_SOURCE_REVIEW_DECISION_APPLY = (
    "outputs/automation/latest_sp500_current_membership_source_review_decision_apply.json"
)

SP500_CURRENT_MEMBERSHIP_SOURCE_REVIEW_DECISION_APPLY_REQUIRED_FIELDS = [
    "status",
    "applied_count",
    "skipped_pending_count",
    "skipped_invalid_count",
    "formal_backtest_upgrade_allowed",
]

WEEKLY_CONCLUSION_REQUIRED_SUMMARY_FIELDS = [
    "candidate_count_total",
    "candidate_action_summary",
    "health",
    "automation",
    "markets",
    "priority_actions",
    "priority_action_details",
    "outputs",
]

WEEKLY_DELIVERY_REQUIRED_QUALITY_FIELDS = [
    "conclusion_status",
    "conclusion_health_status",
    "conclusion_health_score",
    "candidate_count_total",
    "manual_review_queue_count",
    "manual_review_pending_count",
    "conclusion_signal_status",
    "missing_conclusion_signals",
    "missing_conclusion_signal_fixes",
    "action_items_status",
    "action_items_freshness_status",
    "action_items_count",
    "action_items_actual_count",
    "missing_outputs",
    "attention_reasons",
]

WEEKLY_OPS_REQUIRED_QUALITY_FIELDS = [
    "automation_audit_status",
    "automation_check_status",
    "manifest_validation_status",
    "market_count",
    "markets_ready_count",
    "candidate_count_total",
    "manual_review_queue_count",
    "manual_review_repeat_count",
    "recommended_action",
    "priority_actions",
    "missing_outputs",
    "missing_output_paths",
    "automation_issues",
    "attention_reasons",
]

AUTOMATION_CHECK_REQUIRED_QUALITY_FIELDS = [
    "recommended_action",
    "priority_actions",
    "manifest_validation_status",
    "manifest_validation_errors",
    "market_count",
    "markets_ready_count",
    "not_ready_markets",
    "candidate_count_total",
    "market_candidate_counts",
    "manual_review_queue_count",
    "manual_review_repeat_count",
    "data_health_status",
    "data_quality_status",
    "data_quality_score",
    "data_quality_history_status",
    "candidate_review_status",
    "weekly_ops_history_status",
    "weekly_delivery_history_status",
    "model_audit_status",
    "forecast_performance_status",
    "backtest_status",
    "outputs",
]


def run_pre_submit_review(
    project_root,
    today=None,
    max_age_days=8,
    checklist=None,
    closeout_goal_code="",
):
    project_root = Path(project_root)
    checklist_path = _resolve_path(project_root, checklist or DEFAULT_CHECKLIST)
    governance_path = _resolve_path(project_root, DEFAULT_GOVERNANCE_DOC)
    attention_reasons = []
    missing_outputs = []
    missing_output_paths = {}
    invalid_inputs = []
    input_statuses = {}
    input_dates = {}
    input_age_days = {}
    input_freshness = {}
    payloads = {}

    if not checklist_path.exists():
        attention_reasons.append("missing_checklist")
    governance_status, governance_missing_terms = _governance_status(governance_path)
    if governance_status == "missing":
        attention_reasons.append("missing_governance_doc")
    elif governance_status == "needs_attention":
        attention_reasons.append("governance_doc_missing_terms")

    current_date = _parse_iso_date(today, "today") if today else date.today()
    for name, spec in INPUT_SPECS.items():
        path = _resolve_path(project_root, spec["path"])
        payload = _read_json(path)
        if payload is None:
            _add_missing(missing_outputs, missing_output_paths, name, path)
            continue
        payloads[name] = payload
        input_statuses[name] = _input_status(name, payload)

        input_date = str(payload.get("as_of_date", "unknown"))
        input_dates[name] = input_date
        freshness, age_days = _freshness(input_date, current_date, max_age_days)
        input_freshness[name] = freshness
        input_age_days[name] = age_days

        schema_issue = _schema_issue(name, payload, spec)
        if schema_issue:
            invalid_inputs.append(schema_issue)

    if missing_outputs:
        attention_reasons.append("missing_outputs")
    if invalid_inputs:
        attention_reasons.append("invalid_inputs")

    stale_or_future = [name for name, status in input_freshness.items() if status in {"stale", "future"}]
    if stale_or_future:
        attention_reasons.append("stale_inputs" if any(input_freshness[name] == "stale" for name in stale_or_future) else "future_inputs")

    attention_reasons.extend(_delivery_reasons(payloads.get("weekly_delivery_check", {})))
    attention_reasons.extend(_ops_reasons(payloads.get("weekly_ops_check", {})))
    attention_reasons.extend(_automation_reasons(payloads.get("automation_check", {})))
    attention_reasons.extend(_conclusion_reasons(payloads.get("weekly_conclusion", {})))
    attention_reasons.extend(_action_item_reasons(payloads.get("weekly_action_items", {})))
    attention_reasons.extend(
        _weekly_conclusion_action_item_sync_reasons(
            payloads.get("weekly_conclusion", {}),
            payloads.get("weekly_action_items", {}),
        )
    )
    attention_reasons.extend(_data_health_review_reasons(payloads.get("data_health_review", {})))
    attention_reasons.extend(_backtest_evidence_review_reasons(payloads.get("backtest_evidence_review", {})))
    attention_reasons.extend(
        _membership_evidence_import_plan_reasons(payloads.get("membership_evidence_import_plan", {}))
    )
    attention_reasons.extend(
        _membership_evidence_apply_preview_reasons(payloads.get("membership_evidence_apply_preview", {}))
    )
    attention_reasons.extend(
        _sp500_current_membership_source_reasons(
            payloads.get("sp500_current_membership_sources", {}),
            project_root=project_root,
        )
    )
    attention_reasons.extend(
        _sp500_current_membership_source_review_status_reasons(
            payloads.get("sp500_current_membership_source_review_status", {}),
            project_root=project_root,
        )
    )
    attention_reasons.extend(
        _sp500_current_membership_source_review_decision_apply_reasons(
            payloads.get("sp500_current_membership_source_review_status", {}),
            project_root=project_root,
        )
    )
    attention_reasons.extend(
        _membership_action_item_link_reasons(
            payloads.get("membership_evidence_import_plan", {}),
            payloads.get("weekly_action_items", {}),
        )
    )
    attention_reasons.extend(
        _sp500_current_membership_source_action_item_link_reasons(
            payloads.get("sp500_current_membership_sources", {}),
            payloads.get("weekly_action_items", {}),
        )
    )
    attention_reasons.extend(_candidate_findings_review_reasons(payloads.get("candidate_findings_review", {})))
    attention_reasons.extend(_forecast_performance_review_reasons(payloads.get("forecast_performance_review", {})))
    attention_reasons.extend(_medium_term_goal_review_reasons(payloads.get("medium_term_goal_review", {})))
    attention_reasons.extend(
        _model_handoff_review_reasons(
            payloads.get("model_handoff_review", {}),
            payloads.get("medium_term_goal_review", {}),
        )
    )
    attention_reasons = _unique(attention_reasons)

    automation_check = payloads.get("automation_check", {})
    weekly_conclusion = payloads.get("weekly_conclusion", {})
    action_items = payloads.get("weekly_action_items", {})
    membership_import_plan = payloads.get("membership_evidence_import_plan", {})
    membership_apply_preview = payloads.get("membership_evidence_apply_preview", {})
    medium_term_goal_review = payloads.get("medium_term_goal_review", {})

    return {
        "pre_submit_review_schema": PRE_SUBMIT_REVIEW_SCHEMA,
        "pre_submit_review_version": PRE_SUBMIT_REVIEW_VERSION,
        "status": "ready" if not attention_reasons else "needs_attention",
        "project_root": str(project_root),
        "as_of_date": current_date.isoformat(),
        "max_age_days": max_age_days,
        "checklist": _relative_path(project_root, checklist_path),
        "checklist_exists": checklist_path.exists(),
        "governance_doc": _relative_path(project_root, governance_path),
        "governance_status": governance_status,
        "governance_missing_terms": governance_missing_terms,
        "freshness_status": _overall_freshness(input_freshness),
        "input_statuses": input_statuses,
        "input_dates": input_dates,
        "input_freshness": input_freshness,
        "input_age_days": input_age_days,
        "candidate_count_total": _int_value(
            automation_check.get("candidate_count_total"),
            _int_value(weekly_conclusion.get("candidate_count_total"), 0),
        ),
        "manual_action_items_count": _int_value(action_items.get("item_count"), len(action_items.get("items", []) or [])),
        "membership_evidence_ready_to_import_count": _int_value(
            membership_import_plan.get("ready_to_import_count"), 0
        ),
        "membership_evidence_preview_row_count": _int_value(
            membership_apply_preview.get("preview_row_count"), 0
        ),
        "membership_evidence_preview_action_item_present": _has_action_item(
            action_items,
            "run_membership_evidence_apply_preview",
        ),
        "development_closeout": _development_closeout_summary(
            medium_term_goal_review,
            closeout_goal_code=closeout_goal_code,
        ),
        "development_priority_actions": _medium_term_priority_actions(medium_term_goal_review),
        "priority_actions": _combined_priority_actions(automation_check, action_items),
        "missing_outputs": missing_outputs,
        "missing_output_paths": missing_output_paths,
        "invalid_inputs": invalid_inputs,
        "attention_reasons": attention_reasons,
        "boundary": "只读取现有自动化验收产物，不抓取行情，不重新评分，不修改正式模型参数。",
    }


def render_pre_submit_review(result):
    lines = [
        "# 提交前复核结果",
        "",
        f"- 日期：{result.get('as_of_date', 'unknown')}",
        f"- 总体状态：{result.get('status', 'unknown')}",
        f"- 输入新鲜度：{result.get('freshness_status', 'unknown')}",
        f"- 候选总数：{result.get('candidate_count_total', 0)}",
        f"- 人工处理事项：{result.get('manual_action_items_count', 0)}",
        f"- 提交前复核清单：{result.get('checklist', DEFAULT_CHECKLIST)}",
        f"- 清单存在：{result.get('checklist_exists', False)}",
        f"- 开发治理规范：{result.get('governance_doc', DEFAULT_GOVERNANCE_DOC)}",
        f"- 开发治理状态：{result.get('governance_status', 'unknown')}",
        f"- 缺失输出：{_join_or_none(result.get('missing_outputs', []))}",
    ]
    if result.get("attention_reasons"):
        lines.extend(["", "## 需要处理"])
        for reason in result["attention_reasons"]:
            lines.append(f"- {reason}")
    if result.get("input_statuses"):
        lines.extend(["", "## 输入状态"])
        for name, status in result["input_statuses"].items():
            freshness = result.get("input_freshness", {}).get(name, "unknown")
            age_days = result.get("input_age_days", {}).get(name, "unknown")
            lines.append(f"- {name}: {status}, {freshness}, {age_days}天")
    if result.get("priority_actions"):
        lines.extend(["", "## priority_actions"])
        for action in result.get("priority_actions", []):
            lines.append(f"- {action}")
    if result.get("development_priority_actions"):
        lines.extend(["", "## development_priority_actions"])
        for action in result.get("development_priority_actions", []):
            lines.append(f"- {action}")
    closeout = result.get("development_closeout", {}) or {}
    if closeout:
        lines.extend(
            [
                "",
                "## 开发收尾摘要",
                f"- current_module={closeout.get('current_module', 'unknown')}",
                f"- module_completion_percent={closeout.get('module_completion_percent', 0)}",
                f"- medium_term_overall_completion_percent={closeout.get('medium_term_overall_completion_percent', 0)}",
                f"- current_target_total_completion_percent={closeout.get('current_target_total_completion_percent', 0)}",
                f"- strategy_code={closeout.get('strategy_code', 'unknown')}",
                f"- medium_term_status={closeout.get('medium_term_status', 'unknown')}",
                f"- automatic_multi_model_collaboration_enabled={closeout.get('automatic_multi_model_collaboration_enabled', False)}",
                f"- collaboration_execution_mode={closeout.get('collaboration_execution_mode', 'unknown')}",
                f"- sp500_current_source_inbox_external_input_required={closeout.get('sp500_current_source_inbox_external_input_required', False)}",
                f"- sp500_current_source_inbox_blocking_reason={closeout.get('sp500_current_source_inbox_blocking_reason', '')}",
                f"- sp500_current_source_inbox_blocking_input={closeout.get('sp500_current_source_inbox_blocking_input', '')}",
            ]
        )
    if result.get("missing_output_paths"):
        lines.extend(["", "## 缺失路径"])
        for name, path in result["missing_output_paths"].items():
            lines.append(f"- {name}: {path}")
    if result.get("invalid_inputs"):
        lines.extend(["", "## 结构异常"])
        for item in result["invalid_inputs"]:
            lines.append(f"- {item}")
    if result.get("governance_missing_terms"):
        lines.extend(["", "## 开发治理缺口"])
        for term in result["governance_missing_terms"]:
            lines.append(f"- {term}")
    lines.extend(
        [
            "",
            "## 边界",
            f"- {result.get('boundary', '')}",
            "- 该结果用于提交或周报发布前复核，不构成投资建议。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_pre_submit_review(result, output):
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8-sig",
    )
    return output_path


def write_pre_submit_report(result, report):
    report_path = Path(report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_pre_submit_review(result), encoding="utf-8-sig")
    return report_path


def append_pre_submit_history(result, history):
    history_path = Path(history)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "history_schema": HISTORY_SCHEMA,
        "history_version": HISTORY_VERSION,
        **result,
    }
    with history_path.open("a", encoding="utf-8-sig") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return history_path


def _governance_status(path):
    path = Path(path)
    if not path.exists():
        return "missing", GOVERNANCE_REQUIRED_TERMS[:]
    try:
        content = path.read_text(encoding="utf-8-sig")
    except OSError:
        return "needs_attention", GOVERNANCE_REQUIRED_TERMS[:]
    missing_terms = [term for term in GOVERNANCE_REQUIRED_TERMS if term not in content]
    return ("ready" if not missing_terms else "needs_attention"), missing_terms


def _delivery_reasons(payload):
    if not payload:
        return []
    reasons = []
    if any(field not in payload for field in WEEKLY_DELIVERY_REQUIRED_QUALITY_FIELDS):
        reasons.append("weekly_delivery_check_missing_quality_fields")
    if payload.get("status") != "ready":
        reasons.append("weekly_delivery_check_not_ready")
    if payload.get("conclusion_signal_status") not in {"ready", None}:
        reasons.append("weekly_delivery_conclusion_signals_not_ready")
    if payload.get("action_items_status") not in {"ready", None}:
        reasons.append("weekly_delivery_action_items_not_ready")
    for reason in payload.get("attention_reasons", []) or []:
        reasons.append(f"weekly_delivery_check:{reason}")
    return reasons


def _ops_reasons(payload):
    if not payload:
        return []
    reasons = []
    if any(field not in payload for field in WEEKLY_OPS_REQUIRED_QUALITY_FIELDS):
        reasons.append("weekly_ops_check_missing_quality_fields")
    if payload.get("status") != "ready":
        reasons.append("weekly_ops_check_not_ready")
    if payload.get("automation_audit_status") != "ready":
        reasons.append("automation_audit_not_ready")
    if payload.get("manifest_validation_status") != "valid":
        reasons.append("manifest_validation_not_valid")
    if _int_value(payload.get("market_count")) and _int_value(payload.get("markets_ready_count")) != _int_value(payload.get("market_count")):
        reasons.append("market_summary_not_ready")
    for reason in payload.get("attention_reasons", []) or []:
        reasons.append(f"weekly_ops_check:{reason}")
    return reasons


def _automation_reasons(payload):
    if not payload:
        return []
    reasons = []
    if any(field not in payload for field in AUTOMATION_CHECK_REQUIRED_QUALITY_FIELDS):
        reasons.append("automation_check_missing_quality_fields")
    if payload.get("manifest_validation_status") != "valid":
        reasons.append("automation_check_manifest_invalid")
    if _int_value(payload.get("market_count")) and _int_value(payload.get("markets_ready_count")) != _int_value(payload.get("market_count")):
        reasons.append("automation_check_markets_not_ready")
    if payload.get("status") not in {"ready", "manual_review_needed"}:
        reasons.append("automation_check_status_not_acceptable")
    return reasons


def _conclusion_reasons(payload):
    if not payload:
        return []
    reasons = []
    if payload.get("status") != "ready":
        reasons.append("weekly_conclusion_not_ready")
    if any(field not in payload for field in WEEKLY_CONCLUSION_REQUIRED_SUMMARY_FIELDS):
        reasons.append("weekly_conclusion_missing_summary_fields")
    health = payload.get("health", {}) if isinstance(payload.get("health", {}), dict) else {}
    if health.get("status") not in {"healthy", "needs_review"}:
        reasons.append("weekly_conclusion_health_not_acceptable")
    automation = payload.get("automation", {}) if isinstance(payload.get("automation", {}), dict) else {}
    for key in ("data_quality", "data_quality_history", "forecast_performance"):
        if key not in automation:
            reasons.append(f"weekly_conclusion_missing_{key}")
    return reasons


def _action_item_reasons(payload):
    if not payload:
        return []
    reasons = []
    if _int_value(payload.get("item_count"), len(payload.get("items", []) or [])) != len(payload.get("items", []) or []):
        reasons.append("weekly_action_items_count_mismatch")
    if _has_action_item(payload, "reduce_weekly_action_backlog") and not _has_backlog_reduction_plan(
        payload,
        "reduce_weekly_action_backlog",
    ):
        reasons.append("weekly_action_items_missing_backlog_reduction_plan")
    return reasons


def _weekly_conclusion_action_item_sync_reasons(weekly_conclusion, action_items):
    if not weekly_conclusion or not action_items:
        return []
    conclusion_actions = {
        str(action).strip()
        for action in weekly_conclusion.get("priority_actions", []) or []
        if str(action).strip()
    }
    action_item_codes = {
        str(item.get("action_code", "")).strip()
        for item in action_items.get("items", []) or []
        if isinstance(item, dict) and str(item.get("action_code", "")).strip()
    }
    if action_item_codes and not action_item_codes.issubset(conclusion_actions):
        return ["weekly_conclusion_missing_weekly_action_item_codes"]
    return []


def _combined_priority_actions(automation_check, action_items):
    weekly_actions = []
    for item in action_items.get("items", []) or [] if isinstance(action_items, dict) else []:
        if not isinstance(item, dict):
            continue
        action_code = str(item.get("action_code", "")).strip()
        if action_code and action_code not in weekly_actions:
            weekly_actions.append(action_code)
    if weekly_actions:
        return weekly_actions

    actions = []
    for action in automation_check.get("priority_actions", []) or []:
        action_code = str(action).strip()
        if action_code and action_code not in actions:
            actions.append(action_code)
    return actions


def _data_health_review_reasons(payload):
    if not payload:
        return []
    reasons = []
    if payload.get("status") not in {"clear", "acceptable_with_monitoring"}:
        reasons.append("data_health_review_not_acceptable")
    if any(field not in payload for field in DATA_HEALTH_REQUIRED_QUALITY_FIELDS):
        reasons.append("data_health_review_missing_quality_fields")
    if _int_value(payload.get("blocked_candidate_count"), 0) > 0:
        reasons.append("data_health_review_candidate_blocked")
    return reasons


def _backtest_evidence_review_reasons(payload):
    if not payload:
        return []
    reasons = []
    if payload.get("status") not in {"ready", "evidence_review_needed"}:
        reasons.append("backtest_evidence_review_not_acceptable")
    if any(field not in payload for field in BACKTEST_EVIDENCE_REQUIRED_QUALITY_FIELDS):
        reasons.append("backtest_evidence_review_missing_quality_fields")
    if _int_value(payload.get("weeks_failed"), 0) > 0:
        reasons.append("backtest_evidence_review_failed_weeks")
    if payload.get("formal_model_upgrade_allowed") and (
        _int_value(payload.get("weak_evidence_rows"), 0) > 0
        or payload.get("status") == "evidence_review_needed"
    ):
        reasons.append("backtest_evidence_upgrade_gate_unsafe")
    return reasons


def _membership_evidence_import_plan_reasons(payload):
    if not payload:
        return []
    reasons = []
    if payload.get("status") not in {"ready", None}:
        reasons.append("membership_evidence_import_plan_not_acceptable")
    if any(field not in payload for field in MEMBERSHIP_EVIDENCE_IMPORT_PLAN_REQUIRED_FIELDS):
        reasons.append("membership_evidence_import_plan_missing_quality_fields")
    if payload.get("formal_backtest_upgrade_allowed") and _int_value(payload.get("missing_source_count"), 0) > 0:
        reasons.append("membership_evidence_import_plan_upgrade_gate_unsafe")
    return reasons


def _membership_evidence_apply_preview_reasons(payload):
    if not payload:
        return []
    reasons = []
    if payload.get("status") not in {"ready", None}:
        reasons.append("membership_evidence_apply_preview_not_acceptable")
    if any(field not in payload for field in MEMBERSHIP_EVIDENCE_APPLY_PREVIEW_REQUIRED_FIELDS):
        reasons.append("membership_evidence_apply_preview_missing_quality_fields")
    if payload.get("applied_to_historical_membership"):
        reasons.append("membership_evidence_apply_preview_wrote_historical_membership")
    if payload.get("formal_backtest_upgrade_allowed"):
        reasons.append("membership_evidence_apply_preview_upgrade_gate_unsafe")
    return reasons


def _sp500_current_membership_source_reasons(payload, project_root=None):
    if not payload:
        return []
    reasons = []
    if payload.get("status") not in {"ready", "fetch_failed", "source_file_required"}:
        reasons.append("sp500_current_membership_sources_not_acceptable")
    if any(field not in payload for field in SP500_CURRENT_MEMBERSHIP_SOURCE_REQUIRED_FIELDS):
        reasons.append("sp500_current_membership_sources_missing_quality_fields")
    review_queue = payload.get("missing_ticker_review_queue", []) or []
    review_queue_file = str(payload.get("missing_ticker_review_queue_file", "") or "").strip()
    if review_queue:
        if not review_queue_file:
            reasons.append("sp500_current_membership_source_review_queue_file_missing")
        else:
            queue_path = _resolve_path(project_root or ".", review_queue_file)
            if not queue_path.exists():
                reasons.append("sp500_current_membership_source_review_queue_file_missing")
            else:
                expected_tickers = _ticker_set_from_review_queue(review_queue)
                actual_tickers, csv_valid = _review_queue_csv_status(queue_path)
                if expected_tickers != actual_tickers:
                    reasons.append("sp500_current_membership_source_review_queue_file_mismatch")
                if not csv_valid:
                    reasons.append("sp500_current_membership_source_review_queue_file_invalid")
    if payload.get("recommended_followup") == "provide_official_constituents_csv":
        reasons.extend(_sp500_current_membership_source_file_guidance_reasons(payload, project_root))
    if payload.get("formal_backtest_upgrade_allowed"):
        reasons.append("sp500_current_membership_sources_upgrade_gate_unsafe")
    return reasons


def _sp500_current_membership_source_file_guidance_reasons(payload, project_root=None):
    reasons = []
    command = str(payload.get("source_file_next_command", "") or "").strip()
    criteria = set(payload.get("source_file_acceptance_criteria", []) or [])
    if (
        "run_sp500_current_membership_sources.ps1" not in command
        or "-SourceFile" not in command
        or "has_symbol_or_ticker_column" not in criteria
        or "at_least_400_tickers" not in criteria
    ):
        reasons.append("sp500_current_membership_sources_missing_source_file_guidance")
    if (
        "source_file_inbox" not in payload
        or "source_file_inbox_exists" not in payload
        or not str(payload.get("source_file_validation_status", "") or "").strip()
    ):
        reasons.append("sp500_current_membership_sources_missing_source_file_inbox_status")
    else:
        inbox_path = _resolve_path(project_root or ".", payload.get("source_file_inbox", ""))
        inbox_exists = inbox_path.exists()
        recorded_exists = bool(payload.get("source_file_inbox_exists"))
        validation_status = str(payload.get("source_file_validation_status", "") or "").strip()
        if inbox_exists != recorded_exists or (inbox_exists and validation_status == "missing"):
            reasons.append("sp500_current_membership_sources_source_file_inbox_status_mismatch")
    inbox_command = str(payload.get("source_file_inbox_next_command", "") or "").strip()
    inbox_dry_run_command = str(
        payload.get("source_file_inbox_dry_run_command", "") or ""
    ).strip()
    if (
        "run_sp500_current_membership_sources.ps1" not in inbox_command
        or "-SourceFileInbox" not in inbox_command
        or "run_sp500_current_membership_sources.ps1" not in inbox_dry_run_command
        or "-SourceFileInbox" not in inbox_dry_run_command
        or "-DryRun" not in inbox_dry_run_command
    ):
        reasons.append("sp500_current_membership_sources_missing_source_file_inbox_commands")

    intake_file = str(payload.get("source_file_intake_template", "") or "").strip()
    expected_count = _int_value(payload.get("intake_expected_count"))
    missing_count = _int_value(payload.get("intake_missing_count"))
    missing_tickers = _ticker_set(payload.get("intake_missing_tickers", []) or [])
    if not intake_file:
        reasons.append("sp500_current_membership_sources_intake_template_mismatch")
        return reasons

    intake_path = _resolve_path(project_root or ".", intake_file)
    intake_tickers, intake_valid = _source_file_intake_template_status(intake_path)
    if (
        not intake_valid
        or expected_count != len(intake_tickers)
        or missing_count != len(intake_tickers)
        or missing_tickers != intake_tickers
    ):
        reasons.append("sp500_current_membership_sources_intake_template_mismatch")
    request_file = str(payload.get("source_file_request_file", "") or "").strip()
    request_path = _resolve_path(project_root or ".", request_file) if request_file else None
    if not request_path or not request_path.exists():
        reasons.append("sp500_current_membership_sources_missing_source_file_request")
    elif _source_file_request_inbox_commands_missing(request_path):
        reasons.append("sp500_current_membership_sources_missing_source_file_request_inbox_commands")
    elif _source_file_request_acceptance_criteria_missing(request_path):
        reasons.append("sp500_current_membership_sources_missing_source_file_request_acceptance_criteria")
    elif _source_file_request_boundary_missing(request_path):
        reasons.append("sp500_current_membership_sources_missing_source_file_request_boundary")
    elif _source_file_request_stale(request_path, payload):
        reasons.append("sp500_current_membership_sources_stale_source_file_request")
    return reasons


def _source_file_request_inbox_commands_missing(path):
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return True

    inbox_dry_run = _line_value(lines, "inbox_dry_run_command")
    inbox_import = _line_value(lines, "inbox_import_command")
    return (
        "-SourceFileInbox" not in inbox_dry_run
        or "-DryRun" not in inbox_dry_run
        or "-SourceFileInbox" not in inbox_import
    )


def _source_file_request_acceptance_criteria_missing(path):
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError:
        return True
    required_terms = [
        "source_file_inbox:",
        "official_constituents.csv",
        "minimum_official_ticker_count: 400",
        "has_symbol_or_ticker_column",
        "at_least_400_tickers",
        "official_spglobal_constituents_export",
    ]
    return any(term not in text for term in required_terms)


def _source_file_request_boundary_missing(path):
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError:
        return True
    required_terms = [
        "Use only the official S&P Global constituents export",
        "Do not import the intake template as the source CSV",
        "Run the dry-run command before the import command",
    ]
    return any(term not in text for term in required_terms)


def _source_file_request_stale(path, payload):
    expected_date = str(payload.get("as_of_date", "") or "").strip()
    if not expected_date:
        return False
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return True
    request_date = _line_value(lines, "as_of_date")
    return request_date != expected_date


def _line_value(lines, key):
    prefix = f"- {key}:"
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix):].strip()
    return ""


def _ticker_set_from_review_queue(review_queue):
    return {
        str(item.get("ticker", "")).strip().upper()
        for item in review_queue
        if isinstance(item, dict) and str(item.get("ticker", "")).strip()
    }


def _ticker_set(values):
    return {str(value).strip().upper() for value in values if str(value).strip()}


REVIEW_QUEUE_CSV_REQUIRED_FIELDS = {
    "ticker",
    "review_status",
    "issue_type",
    "recommended_check",
}


def _review_queue_csv_status(path):
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or [])
            if not REVIEW_QUEUE_CSV_REQUIRED_FIELDS.issubset(fields):
                return set(), False
            tickers = set()
            valid = True
            for row in reader:
                if any(not str(row.get(field, "")).strip() for field in REVIEW_QUEUE_CSV_REQUIRED_FIELDS):
                    valid = False
                ticker = str(row.get("ticker", "")).strip().upper()
                if ticker:
                    tickers.add(ticker)
            return tickers, valid
    except OSError:
        return set(), False


SOURCE_FILE_INTAKE_TEMPLATE_REQUIRED_FIELDS = {
    "expected_ticker",
    "intake_status",
    "required_source_url",
    "required_source_columns",
}


def _source_file_intake_template_status(path):
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or [])
            if not SOURCE_FILE_INTAKE_TEMPLATE_REQUIRED_FIELDS.issubset(fields):
                return set(), False
            tickers = set()
            valid = True
            for row in reader:
                if any(not str(row.get(field, "")).strip() for field in SOURCE_FILE_INTAKE_TEMPLATE_REQUIRED_FIELDS):
                    valid = False
                ticker = str(row.get("expected_ticker", "")).strip().upper()
                if ticker:
                    tickers.add(ticker)
            return tickers, valid
    except OSError:
        return set(), False


def _sp500_current_membership_source_review_status_reasons(payload, project_root=None):
    if not payload:
        return []
    reasons = []
    if payload.get("status") not in {"review_needed", "clear"}:
        reasons.append("sp500_current_membership_source_review_status_not_acceptable")
    if any(
        field not in payload
        for field in SP500_CURRENT_MEMBERSHIP_SOURCE_REVIEW_STATUS_REQUIRED_FIELDS
    ):
        reasons.append("sp500_current_membership_source_review_status_missing_quality_fields")
    if payload.get("queue_exists") is not True:
        reasons.append("sp500_current_membership_source_review_status_queue_missing")
    if payload.get("formal_backtest_upgrade_allowed"):
        reasons.append("sp500_current_membership_source_review_status_upgrade_gate_unsafe")
    open_count = _int_value(payload.get("open_count"), 0)
    open_items = payload.get("open_items", [])
    if open_count > 0 and not isinstance(open_items, list):
        reasons.append("sp500_current_membership_source_review_status_invalid_open_items")
    elif open_count > 0 and len(open_items or []) != open_count:
        reasons.append("sp500_current_membership_source_review_status_open_count_mismatch")
    decisions_template = str(payload.get("decisions_template_file", "") or "").strip()
    if open_count > 0:
        if not decisions_template:
            reasons.append("sp500_current_membership_source_review_decisions_template_missing")
        else:
            decisions_path = _resolve_path(project_root or ".", decisions_template)
            if not decisions_path.exists():
                reasons.append("sp500_current_membership_source_review_decisions_template_missing")
            else:
                expected_tickers = _ticker_set_from_review_queue(open_items if isinstance(open_items, list) else [])
                actual_tickers, template_valid = _review_decisions_template_csv_status(decisions_path)
                if not template_valid:
                    reasons.append("sp500_current_membership_source_review_decisions_template_invalid")
                elif expected_tickers != actual_tickers:
                    reasons.append("sp500_current_membership_source_review_decisions_template_mismatch")
        if _sp500_current_membership_source_review_decision_guidance_missing(payload):
            reasons.append("sp500_current_membership_source_review_missing_decision_guidance")
    return reasons


def _review_decisions_template_csv_status(path):
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or [])
            if not SP500_CURRENT_MEMBERSHIP_SOURCE_REVIEW_DECISION_REQUIRED_FIELDS.issubset(
                fields
            ):
                return set(), False
            tickers = {
                str(row.get("ticker", "")).strip().upper()
                for row in reader
                if str(row.get("ticker", "")).strip()
            }
            return tickers, True
    except OSError:
        return set(), False


def _sp500_current_membership_source_review_decision_guidance_missing(payload):
    decision_options = payload.get("decision_options")
    if not isinstance(decision_options, list) or not decision_options:
        return True
    option_values = {
        str(item.get("review_decision", "")).strip()
        for item in decision_options
        if isinstance(item, dict)
    }
    if not SP500_CURRENT_MEMBERSHIP_SOURCE_REVIEW_DECISION_OPTIONS.issubset(option_values):
        return True

    required_fields = payload.get("decision_required_fields")
    if not isinstance(required_fields, list):
        return True
    normalized_required_fields = {
        str(field).strip()
        for field in required_fields
        if str(field).strip()
    }
    if not SP500_CURRENT_MEMBERSHIP_SOURCE_REVIEW_DECISION_REQUIRED_FIELDS.issubset(
        normalized_required_fields
    ):
        return True

    instructions = str(payload.get("manual_decision_instructions", "") or "").strip()
    return not instructions


def _sp500_current_membership_source_review_decision_apply_reasons(payload, project_root=None):
    if not payload:
        return []
    if not (
        payload.get("next_action") == "apply_review_decisions_to_queue"
        or payload.get("review_decision_status") == "ready_to_apply"
    ):
        return []
    apply_path = _resolve_path(
        project_root or ".",
        SP500_CURRENT_MEMBERSHIP_SOURCE_REVIEW_DECISION_APPLY,
    )
    apply_payload = _read_json(apply_path)
    if apply_payload is None:
        return ["sp500_current_membership_source_review_decision_apply_missing"]

    reasons = []
    if any(
        field not in apply_payload
        for field in SP500_CURRENT_MEMBERSHIP_SOURCE_REVIEW_DECISION_APPLY_REQUIRED_FIELDS
    ):
        reasons.append("sp500_current_membership_source_review_decision_apply_missing_quality_fields")
    if apply_payload.get("status") not in {"applied", "dry_run"}:
        reasons.append("sp500_current_membership_source_review_decision_apply_not_acceptable")
    if apply_payload.get("formal_backtest_upgrade_allowed"):
        reasons.append("sp500_current_membership_source_review_decision_apply_upgrade_gate_unsafe")
    expected = _int_value(payload.get("decision_ready_to_apply_count"))
    applied = _int_value(apply_payload.get("applied_count"))
    if expected > 0 and applied < expected:
        reasons.append("sp500_current_membership_source_review_decision_apply_incomplete")
    return reasons


def _membership_action_item_link_reasons(import_plan, action_items):
    if not import_plan or not action_items:
        return []
    if _int_value(import_plan.get("ready_to_import_count"), 0) <= 0:
        return []
    if _has_action_item(action_items, "run_membership_evidence_apply_preview"):
        return []
    return ["membership_evidence_apply_preview_action_item_missing"]


def _sp500_current_membership_source_action_item_link_reasons(source_status, action_items):
    if not source_status or not action_items:
        return []
    recommended_followup = source_status.get("recommended_followup")
    if recommended_followup not in {
        "review_current_membership_source_status",
        "provide_official_constituents_csv",
    }:
        return []
    missing_count = _int_value(source_status.get("missing_count"), 0)
    intake_missing_count = _int_value(source_status.get("intake_missing_count"), 0)
    if missing_count <= 0 and intake_missing_count <= 0:
        return []
    expected_action = (
        "provide_official_constituents_csv"
        if recommended_followup == "provide_official_constituents_csv"
        else "review_current_membership_source_status"
    )
    action_item = _find_action_item(action_items, expected_action)
    if not action_item:
        if expected_action == "provide_official_constituents_csv":
            return ["sp500_current_membership_source_official_csv_action_item_missing"]
        return ["sp500_current_membership_source_action_item_missing"]
    recommended_check = str(action_item.get("recommended_check", "") or "")
    if expected_action == "provide_official_constituents_csv":
        request_file = str(source_status.get("source_file_request_file", "") or "").strip()
        request_name = Path(request_file).name if request_file else ""
        if request_name and request_name not in recommended_check:
            return ["sp500_current_membership_source_official_csv_action_item_missing"]
        if _official_csv_action_item_inbox_commands_missing(recommended_check):
            return ["sp500_current_membership_source_official_csv_action_item_missing_commands"]
        if _official_csv_action_item_inbox_status_details_missing(recommended_check):
            return [
                "sp500_current_membership_source_official_csv_action_item_missing_inbox_status_details"
            ]
        if _official_csv_action_item_accepted_ticker_columns_missing(recommended_check):
            return [
                "sp500_current_membership_source_official_csv_action_item_missing_accepted_ticker_columns"
            ]
        return []
    review_queue_file = str(source_status.get("missing_ticker_review_queue_file", "") or "").strip()
    if review_queue_file:
        queue_name = Path(review_queue_file).name
        if queue_name and queue_name not in recommended_check:
            return ["sp500_current_membership_source_action_item_missing_review_queue_file"]
    return []


def _official_csv_action_item_inbox_commands_missing(recommended_check):
    text = str(recommended_check or "")
    return (
        "dry_run_command:" not in text
        or "import_command:" not in text
        or "-SourceFileInbox" not in text
        or "-DryRun" not in text
    )


def _official_csv_action_item_inbox_status_details_missing(recommended_check):
    text = str(recommended_check or "")
    required_marker_groups = [
        ["latest_sp500_current_membership_source_inbox_status.json"],
        ["source_file_inbox_status", "inbox_status"],
        ["source_file_inbox_next_action", "inbox_next_action"],
        ["parsed_official_ticker_count"],
        ["source_file_inbox_intake_missing_count", "inbox_intake_missing_count"],
    ]
    return any(not any(marker in text for marker in group) for group in required_marker_groups)


def _official_csv_action_item_accepted_ticker_columns_missing(recommended_check):
    text = str(recommended_check or "")
    required_columns = [
        "Ticker Symbol",
        "Constituent Ticker",
        "Constituent Symbol",
    ]
    return any(column not in text for column in required_columns)


def _has_action_item(action_items, action_code):
    return _find_action_item(action_items, action_code) is not None


def _find_action_item(action_items, action_code):
    items = action_items.get("items", []) or [] if isinstance(action_items, dict) else []
    return next(
        (
            item
            for item in items
            if isinstance(item, dict) and item.get("action_code") == action_code
        ),
        None,
    )


def _has_backlog_reduction_plan(action_items, action_code):
    plan = action_items.get("backlog_reduction_plan", []) if isinstance(action_items, dict) else []
    if not isinstance(plan, list):
        return False
    for entry in plan:
        if not isinstance(entry, dict):
            continue
        actions = entry.get("actions", [])
        if (
            entry.get("category")
            and _int_value(entry.get("count"), 0) > 0
            and isinstance(actions, list)
            and action_code in actions
            and entry.get("first_action") in actions
            and "target_count_after_close" in entry
            and _int_value(entry.get("target_count_after_close"), -1) >= 0
            and str(entry.get("close_condition", "") or "").strip()
        ):
            return True
    return False


def _candidate_findings_review_reasons(payload):
    if not payload:
        return []
    reasons = []
    if payload.get("status") not in {"ready", "manual_review_needed"}:
        reasons.append("candidate_findings_review_not_acceptable")
    if any(field not in payload for field in CANDIDATE_FINDINGS_REQUIRED_QUALITY_FIELDS):
        reasons.append("candidate_findings_review_missing_quality_fields")
    if _int_value(payload.get("missing_field_count"), 0) > 0:
        reasons.append("candidate_findings_review_missing_fields")
    if _int_value(payload.get("risk_missing_count"), 0) > 0:
        reasons.append("candidate_findings_review_missing_risk_coverage")
    if payload.get("formal_model_change_allowed"):
        reasons.append("candidate_findings_formal_model_change_unsafe")
    return reasons


def _forecast_performance_review_reasons(payload):
    if not payload:
        return []
    reasons = []
    if payload.get("status") not in {"ready", "sample_accumulating", "performance_review_needed"}:
        reasons.append("forecast_performance_review_not_acceptable")
    if any(field not in payload for field in FORECAST_PERFORMANCE_REQUIRED_TRACKING_FIELDS):
        reasons.append("forecast_performance_review_missing_tracking_fields")
    if _int_value(payload.get("missing_market_count"), 0) > 0:
        reasons.append("forecast_performance_review_missing_market")
    if _int_value(payload.get("latest_short_signal_missing_count"), 0) > 0:
        reasons.append("forecast_performance_latest_short_signals_missing")
    if payload.get("formal_model_change_allowed"):
        reasons.append("forecast_performance_formal_model_change_unsafe")
    return reasons


def _medium_term_goal_review_reasons(payload):
    if not payload:
        return []
    reasons = []
    if payload.get("status") not in {
        "ready_for_phase_review",
        "on_track_with_monitoring",
        "blocked",
    }:
        reasons.append("medium_term_goal_review_status_not_acceptable")
    if any(field not in payload for field in MEDIUM_TERM_GOAL_REVIEW_REQUIRED_FIELDS):
        reasons.append("medium_term_goal_review_missing_progress_fields")
    if payload.get("strategy_code") != "evidence_prediction_decision_maturity":
        reasons.append("medium_term_goal_review_strategy_not_current_target")
    if payload.get("period") != "8 weeks":
        reasons.append("medium_term_goal_review_period_not_8_weeks")
    snapshot = payload.get("task_closeout_snapshot")
    if not isinstance(snapshot, dict):
        reasons.append("medium_term_goal_review_missing_closeout_snapshot")
    elif any(field not in snapshot for field in MEDIUM_TERM_CLOSEOUT_REQUIRED_FIELDS):
        reasons.append("medium_term_goal_review_missing_closeout_snapshot_fields")
    elif _int_value(snapshot.get("medium_term_overall_completion_percent"), -1) != _int_value(
        payload.get("overall_completion_percent"),
        -2,
    ):
        reasons.append("medium_term_goal_review_closeout_overall_mismatch")
    elif _int_value(snapshot.get("current_target_total_completion_percent"), -1) != _int_value(
        payload.get("current_target_total_completion_percent"),
        -2,
    ):
        reasons.append("medium_term_goal_review_closeout_current_target_mismatch")
    goals = payload.get("goals", [])
    if not isinstance(goals, list) or not goals:
        reasons.append("medium_term_goal_review_missing_goals")
    elif any(
        not isinstance(goal, dict)
        or not goal.get("module")
        or "completion_percent" not in goal
        for goal in goals
    ):
        reasons.append("medium_term_goal_review_missing_goal_completion")
    elif isinstance(snapshot, dict):
        module = snapshot.get("current_module")
        matched_goal = next(
            (
                goal
                for goal in goals
                if isinstance(goal, dict) and goal.get("module") == module
            ),
            None,
        )
        if matched_goal and _int_value(snapshot.get("module_completion_percent"), -1) != _int_value(
            matched_goal.get("completion_percent"),
            -2,
        ):
            reasons.append("medium_term_goal_review_closeout_module_mismatch")
    collaboration_mode = payload.get("collaboration_execution_mode")
    collaboration_note = str(payload.get("collaboration_boundary_note", ""))
    if (
        not collaboration_mode
        or "未启用自动多模型协作" not in collaboration_note
        or "单 Codex" not in collaboration_note
    ):
        reasons.append("medium_term_goal_review_missing_collaboration_boundary")
    elif collaboration_mode != EXPECTED_COLLABORATION_EXECUTION_MODE:
        reasons.append("medium_term_goal_review_collaboration_mode_unsafe")
    if payload.get("automatic_multi_model_collaboration_enabled") is not False:
        reasons.append("medium_term_goal_review_auto_collaboration_boundary_unsafe")
    return reasons


def _model_handoff_review_reasons(payload, medium_term_goal_review=None):
    if not payload:
        return []
    medium_term_goal_review = medium_term_goal_review or {}
    reasons = []
    if payload.get("status") != "ready":
        reasons.append("model_handoff_review_not_ready")
    if any(field not in payload for field in MODEL_HANDOFF_REQUIRED_FIELDS):
        reasons.append("model_handoff_review_missing_quality_fields")
    if payload.get("automatic_multi_model_collaboration_enabled") is not False:
        reasons.append("model_handoff_review_auto_collaboration_boundary_unsafe")
    if payload.get("collaboration_execution_mode") != EXPECTED_COLLABORATION_EXECUTION_MODE:
        reasons.append("model_handoff_review_collaboration_mode_unsafe")
    collaboration_note = str(payload.get("collaboration_boundary_note", ""))
    if "未启用自动多模型协作" not in collaboration_note and "未启用自动双模型协作" not in collaboration_note:
        reasons.append("model_handoff_review_missing_collaboration_boundary")
    if not isinstance(payload.get("gpt55_review_checklist"), list) or not payload.get("gpt55_review_checklist"):
        reasons.append("model_handoff_review_missing_gpt55_checklist")
    if not isinstance(payload.get("validation_commands"), list):
        reasons.append("model_handoff_review_invalid_validation_commands")
    if payload.get("formal_release_allowed") is not True:
        reasons.append("model_handoff_review_formal_release_not_allowed")
    snapshot = medium_term_goal_review.get("task_closeout_snapshot", {})
    if isinstance(snapshot, dict) and snapshot:
        if (
            payload.get("goal_code") != snapshot.get("goal_code")
            or payload.get("current_module") != snapshot.get("current_module")
            or _int_value(payload.get("module_completion_percent"), -1)
            != _int_value(snapshot.get("module_completion_percent"), -2)
            or _int_value(payload.get("medium_term_overall_completion_percent"), -1)
            != _int_value(snapshot.get("medium_term_overall_completion_percent"), -2)
        ):
            reasons.append("model_handoff_review_closeout_mismatch")
    return reasons


def _development_closeout_summary(medium_term_goal_review, closeout_goal_code=""):
    snapshot = medium_term_goal_review.get("task_closeout_snapshot", {})
    if not isinstance(snapshot, dict):
        snapshot = {}
    goal = {}
    goals = medium_term_goal_review.get("goals", []) or []
    if closeout_goal_code and isinstance(goals, list):
        goal = next(
            (
                item
                for item in goals
                if isinstance(item, dict) and item.get("goal_code") == closeout_goal_code
            ),
            {},
        )
    if not goal and isinstance(goals, list):
        goal = next(
            (
                item
                for item in goals
                if isinstance(item, dict)
                and item.get("module") == snapshot.get("current_module")
            ),
            {},
        )
    current = goal.get("current", {}) if isinstance(goal, dict) else {}
    if not isinstance(current, dict):
        current = {}
    return {
        "goal_code": goal.get("goal_code", closeout_goal_code or "unknown"),
        "current_module": goal.get("module", snapshot.get("current_module", "unknown")),
        "module_completion_percent": _int_value(
            goal.get("completion_percent", snapshot.get("module_completion_percent")),
            0,
        ),
        "medium_term_overall_completion_percent": _int_value(
            snapshot.get("medium_term_overall_completion_percent"),
            _int_value(medium_term_goal_review.get("overall_completion_percent"), 0),
        ),
        "current_target_total_completion_percent": _int_value(
            snapshot.get("current_target_total_completion_percent"),
            _int_value(
                medium_term_goal_review.get(
                    "current_target_total_completion_percent",
                    medium_term_goal_review.get("overall_completion_percent"),
                ),
                0,
            ),
        ),
        "strategy_code": medium_term_goal_review.get("strategy_code", "unknown"),
        "strategy_title": medium_term_goal_review.get("strategy_title", "unknown"),
        "medium_term_status": medium_term_goal_review.get("status", "unknown"),
        "automatic_multi_model_collaboration_enabled": bool(
            medium_term_goal_review.get("automatic_multi_model_collaboration_enabled")
        ),
        "collaboration_execution_mode": medium_term_goal_review.get(
            "collaboration_execution_mode",
            "unknown",
        ),
        "collaboration_boundary_note": medium_term_goal_review.get(
            "collaboration_boundary_note",
            "unknown",
        ),
        "sp500_current_source_inbox_external_input_required": bool(
            current.get("sp500_current_source_inbox_external_input_required")
        ),
        "sp500_current_source_inbox_blocking_reason": current.get(
            "sp500_current_source_inbox_blocking_reason",
            "",
        ),
        "sp500_current_source_inbox_blocking_input": current.get(
            "sp500_current_source_inbox_blocking_input",
            "",
        ),
    }


def _medium_term_priority_actions(medium_term_goal_review):
    actions = medium_term_goal_review.get("priority_next_actions", [])
    if not isinstance(actions, list):
        return []
    return _unique(str(action).strip() for action in actions if str(action).strip())


def _input_status(name, payload):
    if name == "weekly_action_items":
        if _action_item_reasons(payload):
            return "needs_attention"
        return "ready"
    return str(payload.get("status", payload.get("automation_check_status", "unknown")))


def _schema_issue(name, payload, spec):
    schema_field = spec["schema_field"]
    version_field = spec["version_field"]
    if payload.get(schema_field) != spec["schema_value"]:
        return f"{name}: unexpected {schema_field}={payload.get(schema_field, '')}"
    if _int_value(payload.get(version_field), 0) != spec["version_value"]:
        return f"{name}: unexpected {version_field}={payload.get(version_field, '')}"
    return ""


def _freshness(raw_date, current_date, max_age_days):
    try:
        input_date = _parse_iso_date(raw_date, "as_of_date")
    except ValueError:
        return "invalid", None
    age_days = (current_date - input_date).days
    if age_days < 0:
        return "future", age_days
    if age_days > max_age_days:
        return "stale", age_days
    return "fresh", age_days


def _overall_freshness(input_freshness):
    values = set(input_freshness.values())
    if "invalid" in values:
        return "invalid"
    if "future" in values:
        return "future"
    if "stale" in values:
        return "stale"
    if values and values == {"fresh"}:
        return "fresh"
    return "unknown"


def _read_json(path):
    if not Path(path).exists():
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None


def _parse_iso_date(value, field_name):
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"invalid {field_name}: {value}") from exc


def _resolve_path(project_root, raw_path):
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return Path(project_root) / path


def _relative_path(project_root, path):
    try:
        return str(Path(path).resolve().relative_to(Path(project_root).resolve()))
    except ValueError:
        return str(path)


def _add_missing(missing_outputs, missing_output_paths, name, path):
    if name not in missing_outputs:
        missing_outputs.append(name)
    missing_output_paths[name] = str(path)


def _int_value(value, default=0):
    try:
        return int(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        return default


def _unique(values):
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _join_or_none(values):
    return ", ".join(str(value) for value in values) if values else "无"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run the pre-submit review gate.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--today", default="")
    parser.add_argument("--max-age-days", type=int, default=8)
    parser.add_argument("--checklist", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--report", default="")
    parser.add_argument("--history", default="")
    parser.add_argument("--closeout-goal-code", default="")
    args = parser.parse_args()

    project_root = Path(args.project_root)
    result = run_pre_submit_review(
        project_root,
        today=args.today or None,
        max_age_days=args.max_age_days,
        checklist=args.checklist or None,
        closeout_goal_code=args.closeout_goal_code,
    )
    output = args.output or str(project_root / DEFAULT_OUTPUT)
    report = args.report or str(project_root / DEFAULT_REPORT)
    history = args.history or str(project_root / DEFAULT_HISTORY)
    write_pre_submit_review(result, output)
    write_pre_submit_report(result, report)
    append_pre_submit_history(result, history)
    print(render_pre_submit_review(result), end="")
    if result["status"] != "ready":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
