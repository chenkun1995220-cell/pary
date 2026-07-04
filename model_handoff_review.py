import argparse
import json
from datetime import date
from pathlib import Path


HANDOFF_SCHEMA = "model_handoff_review"
HANDOFF_VERSION = 1
EXPECTED_COLLABORATION_EXECUTION_MODE = "single_codex_with_gpt55_review_checklist"
DEFAULT_MEDIUM_TERM_REVIEW = "outputs/automation/latest_medium_term_goal_review.json"
DEFAULT_SP500_CURRENT_MEMBERSHIP_SOURCES = (
    "outputs/automation/latest_sp500_current_membership_sources.json"
)
DEFAULT_FORECAST_PERFORMANCE_REVIEW = (
    "outputs/automation/latest_forecast_performance_review.json"
)
DEFAULT_OUTPUT = "outputs/automation/latest_model_handoff_review.json"
DEFAULT_REPORT = "outputs/automation/latest_model_handoff_review.md"


def _load_json(path):
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _int_value(value, default=0):
    try:
        return int(value if value not in ("", None) else default)
    except (TypeError, ValueError):
        return default


def _find_goal(payload, goal_code):
    for goal in payload.get("goals", []) or []:
        if isinstance(goal, dict) and goal.get("goal_code") == goal_code:
            return goal
    return {}


def _resolve_goal_code(payload, requested_goal_code):
    if requested_goal_code:
        return requested_goal_code
    snapshot = payload.get("task_closeout_snapshot", {})
    if isinstance(snapshot, dict) and snapshot.get("goal_code"):
        return snapshot["goal_code"]
    return "model_governance_handoff"


def _priority_actions(payload):
    actions = payload.get("priority_next_actions", [])
    if not isinstance(actions, list):
        return []
    result = []
    seen = set()
    for action in actions:
        text = str(action).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _resolve_project_path(project_root, value):
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else project_root / path


def _relative_or_text(project_root, value):
    if value and not Path(value).is_absolute():
        return str(value)
    path = _resolve_project_path(project_root, value)
    if not path:
        return ""
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def _source_request_manifest_status(project_root, request_file):
    path = _resolve_project_path(project_root, request_file)
    if not path or not path.exists():
        return "missing"
    text = path.read_text(encoding="utf-8-sig")
    required_terms = [
        "request_manifest_schema: sp500_current_membership_source_file_request",
        "request_manifest_version: 1",
        "acceptance_criteria: has_symbol_or_ticker_column, at_least_400_tickers, official_spglobal_constituents_export",
        "formal_backtest_upgrade_allowed: false",
        "formal_model_change_allowed: false",
    ]
    return "ready" if all(term in text for term in required_terms) else "incomplete"


def build_model_handoff_review(
    project_root,
    today=None,
    goal_code="",
    medium_term_review=None,
    validation_commands=None,
):
    project_root = Path(project_root)
    review_path = project_root / (medium_term_review or DEFAULT_MEDIUM_TERM_REVIEW)
    medium_term = _load_json(review_path)
    sp500_source_path = project_root / DEFAULT_SP500_CURRENT_MEMBERSHIP_SOURCES
    sp500_source = _load_json(sp500_source_path)
    forecast_path = project_root / DEFAULT_FORECAST_PERFORMANCE_REVIEW
    forecast = _load_json(forecast_path)
    current_date = today or date.today().isoformat()
    validation_commands = list(validation_commands or [])
    reasons = []

    if not medium_term:
        reasons.append("missing_medium_term_goal_review")

    goal_code = _resolve_goal_code(medium_term, goal_code)
    goal = _find_goal(medium_term, goal_code)
    if medium_term and not goal:
        reasons.append("missing_goal_in_medium_term_review")

    auto_collaboration = bool(
        medium_term.get("automatic_multi_model_collaboration_enabled")
    )
    collaboration_mode = medium_term.get(
        "collaboration_execution_mode",
        "unknown",
    )
    collaboration_note = str(medium_term.get("collaboration_boundary_note", ""))

    if auto_collaboration:
        reasons.append("automatic_multi_model_collaboration_claimed")
    if collaboration_mode != EXPECTED_COLLABORATION_EXECUTION_MODE:
        reasons.append("unexpected_collaboration_execution_mode")
    if medium_term and "未启用自动多模型协作" not in collaboration_note:
        reasons.append("missing_no_auto_collaboration_boundary")

    current = goal.get("current", {}) if isinstance(goal, dict) else {}
    if not isinstance(current, dict):
        current = {}
    source_request_file = str(sp500_source.get("source_file_request_file", "") or "")
    source_acceptance_criteria = sp500_source.get("source_file_acceptance_criteria", [])
    if not isinstance(source_acceptance_criteria, list):
        source_acceptance_criteria = []
    status = "ready" if not reasons else "needs_attention"
    return {
        "handoff_schema": HANDOFF_SCHEMA,
        "handoff_version": HANDOFF_VERSION,
        "as_of_date": current_date,
        "status": status,
        "goal_code": goal_code,
        "current_module": goal.get("module", "unknown"),
        "module_completion_percent": _int_value(goal.get("completion_percent"), 0),
        "medium_term_overall_completion_percent": _int_value(
            medium_term.get("overall_completion_percent"),
            0,
        ),
        "current_target_total_completion_percent": _int_value(
            medium_term.get(
                "current_target_total_completion_percent",
                medium_term.get("overall_completion_percent"),
            ),
            0,
        ),
        "strategy_code": medium_term.get("strategy_code", "unknown"),
        "strategy_title": medium_term.get("strategy_title", "unknown"),
        "development_priority_actions": _priority_actions(medium_term),
        "automatic_multi_model_collaboration_enabled": auto_collaboration,
        "collaboration_execution_mode": collaboration_mode,
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
        "sp500_current_source_request_file": _relative_or_text(
            project_root, source_request_file
        ),
        "sp500_current_source_request_manifest_status": _source_request_manifest_status(
            project_root, source_request_file
        ),
        "sp500_current_source_inbox_dry_run_command": sp500_source.get(
            "source_file_inbox_dry_run_command",
            "",
        ),
        "sp500_current_source_inbox_import_command": sp500_source.get(
            "source_file_inbox_next_command",
            "",
        ),
        "sp500_current_source_acceptance_criteria": source_acceptance_criteria,
        "sp500_current_source_recommended_followup": sp500_source.get(
            "recommended_followup",
            "",
        ),
        "sp500_current_source_fetch_error_type": sp500_source.get("fetch_error_type", ""),
        "forecast_performance_status": forecast.get("status", ""),
        "forecast_performance_recommended_action": forecast.get(
            "recommended_action",
            "",
        ),
        "forecast_total_evaluations": _int_value(forecast.get("total_evaluations"), 0),
        "forecast_mature_evaluations": _int_value(
            forecast.get("mature_evaluations"),
            0,
        ),
        "forecast_one_week_mature": _int_value(forecast.get("one_week_mature"), 0),
        "forecast_one_month_mature": _int_value(forecast.get("one_month_mature"), 0),
        "forecast_prediction_unavailable": _int_value(
            forecast.get("prediction_unavailable"),
            0,
        ),
        "forecast_latest_prediction_unavailable_count": _int_value(
            forecast.get("latest_prediction_unavailable_count"),
            0,
        ),
        "forecast_legacy_prediction_unavailable_count": _int_value(
            forecast.get("legacy_prediction_unavailable_count"),
            0,
        ),
        "forecast_latest_short_signal_missing_count": _int_value(
            forecast.get("latest_short_signal_missing_count"),
            0,
        ),
        "forecast_next_one_week_evaluation_date": forecast.get(
            "next_one_week_evaluation_date",
            "",
        ),
        "forecast_next_one_month_evaluation_date": forecast.get(
            "next_one_month_evaluation_date",
            "",
        ),
        "forecast_formal_model_change_allowed": bool(
            forecast.get("formal_model_change_allowed", False)
        ),
        "collaboration_boundary_note": collaboration_note,
        "spark_execution_summary": "单 Codex 按 gpt5.3-codex-spark 的小步实现习惯推进，并保留可回放证据。",
        "gpt55_review_checklist": [
            "gpt5.5 口径复核：不声称已启用自动双模型协作。",
            "gpt5.5 口径复核：不自动修改正式模型参数或正式评分权重。",
            "gpt5.5 口径复核：提交前必须能追溯当前模块完成度和整体完成度。",
        ],
        "validation_commands": validation_commands,
        "risk_notes": [
            "当前仍为单 Codex 执行 + gpt5.5 复核清单模拟，不是真正的自动双模型协作。",
        ],
        "formal_release_allowed": status == "ready",
        "attention_reasons": reasons,
        "source_files": {
            "medium_term_goal_review": str(review_path.relative_to(project_root))
            if review_path.is_relative_to(project_root)
            else str(review_path),
            "sp500_current_membership_sources": str(
                sp500_source_path.relative_to(project_root)
            )
            if sp500_source_path.exists()
            else "",
            "forecast_performance_review": str(forecast_path.relative_to(project_root))
            if forecast_path.exists()
            else "",
        },
        "boundary": "只读取现有中期目标看板，不抓取行情，不重新评分，不修改正式模型参数。",
    }


def render_model_handoff_review(result):
    lines = [
        "# 模型交接复核包",
        "",
        f"- 状态：{result.get('status', 'unknown')}",
        f"- 当前模块：{result.get('current_module', 'unknown')}",
        f"- 模块完成度：{result.get('module_completion_percent', 0)}%",
        f"- 中期目标整体完成度：{result.get('medium_term_overall_completion_percent', 0)}%",
        f"- 当前目标总完成度：{result.get('current_target_total_completion_percent', 0)}%",
        f"- 自动双模型协作：{'已启用' if result.get('automatic_multi_model_collaboration_enabled') else '未启用自动双模型协作'}",
        f"- 真实执行模式：{result.get('collaboration_execution_mode', 'unknown')}",
        f"- 边界：{result.get('collaboration_boundary_note', 'unknown')}",
        "",
        "## 快速实现口径",
        "",
        result.get("spark_execution_summary", "unknown"),
        "",
        "## gpt5.5 复核清单",
        "",
    ]
    for item in result.get("gpt55_review_checklist", []) or []:
        lines.append(f"- {item}")
    lines.extend(["", "## 验证命令", ""])
    for command in result.get("validation_commands", []) or []:
        lines.append(f"- `{command}`")
    if not result.get("validation_commands"):
        lines.append("- 未记录")
    lines.extend(["", "## 风险边界", ""])
    for note in result.get("risk_notes", []) or []:
        lines.append(f"- {note}")
    lines.extend(["", "## development_priority_actions", ""])
    for action in result.get("development_priority_actions", []) or []:
        lines.append(f"- {action}")
    if not result.get("development_priority_actions"):
        lines.append("- none")
    if result.get("attention_reasons"):
        lines.extend(["", "## 需处理原因", ""])
        for reason in result["attention_reasons"]:
            lines.append(f"- {reason}")
    lines.extend(
        [
            "",
            f"- sp500_current_source_inbox_external_input_required={result.get('sp500_current_source_inbox_external_input_required', False)}",
            f"- sp500_current_source_inbox_blocking_reason={result.get('sp500_current_source_inbox_blocking_reason', '')}",
            f"- sp500_current_source_inbox_blocking_input={result.get('sp500_current_source_inbox_blocking_input', '')}",
            f"- sp500_current_source_request_file={result.get('sp500_current_source_request_file', '')}",
            f"- sp500_current_source_request_manifest_status={result.get('sp500_current_source_request_manifest_status', '')}",
            f"- sp500_current_source_inbox_dry_run_command={result.get('sp500_current_source_inbox_dry_run_command', '')}",
            f"- sp500_current_source_inbox_import_command={result.get('sp500_current_source_inbox_import_command', '')}",
            "- sp500_current_source_acceptance_criteria="
            + ", ".join(result.get("sp500_current_source_acceptance_criteria", []) or []),
            f"- forecast_performance_status={result.get('forecast_performance_status', '')}",
            f"- forecast_performance_recommended_action={result.get('forecast_performance_recommended_action', '')}",
            f"- forecast_mature_evaluations={result.get('forecast_mature_evaluations', 0)}",
            f"- forecast_one_week_mature={result.get('forecast_one_week_mature', 0)}",
            f"- forecast_one_month_mature={result.get('forecast_one_month_mature', 0)}",
            f"- forecast_next_one_week_evaluation_date={result.get('forecast_next_one_week_evaluation_date', '')}",
            f"- forecast_next_one_month_evaluation_date={result.get('forecast_next_one_month_evaluation_date', '')}",
            f"- forecast_formal_model_change_allowed={result.get('forecast_formal_model_change_allowed', False)}",
        ]
    )
    lines.append("")
    return "\n".join(lines)


def write_json(result, output):
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8-sig",
    )
    return output_path


def write_report(result, report):
    report_path = Path(report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_model_handoff_review(result), encoding="utf-8-sig")
    return report_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build model handoff review package.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--today", default=None)
    parser.add_argument("--goal-code", default="")
    parser.add_argument("--medium-term-review", default=DEFAULT_MEDIUM_TERM_REVIEW)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--validation-command", action="append", default=[])
    args = parser.parse_args(argv)

    project_root = Path(args.project_root)
    result = build_model_handoff_review(
        project_root,
        today=args.today,
        goal_code=args.goal_code,
        medium_term_review=args.medium_term_review,
        validation_commands=args.validation_command,
    )
    output = project_root / args.output
    report = project_root / args.report
    write_json(result, output)
    write_report(result, report)
    print(f"模型交接复核：{result['status']}")
    print(f"Writes: {output}, {report}")
    return 0 if result["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
