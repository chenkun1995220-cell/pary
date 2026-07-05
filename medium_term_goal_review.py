import argparse
import json
import sys
from pathlib import Path


REVIEW_SCHEMA = "medium_term_goal_review"
REVIEW_VERSION = 1
PERIOD = "8 weeks"
STRATEGY_CODE = "evidence_prediction_decision_maturity"
STRATEGY_TITLE = "证据、预测与决策成熟化"
AUTOMATIC_MULTI_MODEL_COLLABORATION_ENABLED = False
COLLABORATION_EXECUTION_MODE = "single_codex_with_gpt55_review_checklist"
COLLABORATION_BOUNDARY_NOTE = (
    "当前未启用自动多模型协作；当前不是自动双模型协作，实际由单 Codex 执行，"
    "并通过清单模拟 gpt5.5 的关键复核角色。"
)
AUTOMATION_DIR = Path("outputs") / "automation"


INPUT_FILES = {
    "pre_submit": "latest_pre_submit_review.json",
    "automation_check": "latest_automation_check.json",
    "weekly_ops": "latest_weekly_ops_check.json",
    "weekly_ops_history": "latest_weekly_ops_history_summary.json",
    "weekly_delivery_history": "latest_weekly_delivery_history_summary.json",
    "weekly_action_items": "latest_weekly_action_items.json",
    "data_health": "latest_data_health_review.json",
    "candidate_findings": "latest_candidate_findings_review.json",
    "forecast_performance": "latest_forecast_performance_review.json",
    "backtest_evidence": "latest_backtest_evidence_review.json",
    "membership_evidence_import_plan": "latest_membership_evidence_import_plan.json",
    "membership_evidence_apply_preview": "latest_membership_evidence_apply_preview.json",
    "sp500_current_membership_sources": "latest_sp500_current_membership_sources.json",
    "sp500_current_membership_source_review_status": "latest_sp500_current_membership_source_review_status.json",
    "sp500_current_membership_source_inbox_status": "latest_sp500_current_membership_source_inbox_status.json",
}


GOAL_MODULES = {
    "weekly_delivery_stability": "每周自动交付稳定性",
    "data_quality_convergence": "数据质量收敛",
    "candidate_review_convergence": "候选公司研究清单成熟化",
    "forecast_tracking_maturity": "1周和1个月走势预测评估",
    "backtest_evidence_quality": "S&P 500 成分证据补强",
    "model_governance_handoff": "模型治理与多模型协作准备",
}

GOAL_TARGET_COMPLETION = {
    "backtest_evidence_quality": 70,
    "forecast_tracking_maturity": 60,
    "data_quality_convergence": 85,
    "candidate_review_convergence": 85,
    "weekly_delivery_stability": 90,
    "model_governance_handoff": 85,
}


STATUS_COMPLETION = {
    "blocked": 0,
    "needs_work": 30,
    "sample_accumulating": 40,
    "on_track": 75,
    "ready_for_phase_review": 100,
}


def _load_json(path):
    json_path = Path(path)
    if not json_path.exists():
        return {}
    return json.loads(json_path.read_text(encoding="utf-8-sig"))


def _int_value(value, default=0):
    try:
        return int(value if value not in ("", None) else default)
    except (TypeError, ValueError):
        return default


def _float_value(value, default=0.0):
    try:
        return float(value if value not in ("", None) else default)
    except (TypeError, ValueError):
        return default


def _first_value(*values, default="unknown"):
    for value in values:
        if value not in ("", None):
            return value
    return default


def _pre_submit_status_for_medium_term(pre_submit):
    status = pre_submit.get("status", "missing")
    reasons = pre_submit.get("attention_reasons", []) or []
    if (
        status == "needs_attention"
        and isinstance(reasons, list)
        and set(str(reason) for reason in reasons) == {"model_handoff_review_closeout_mismatch"}
    ):
        return "ready_refresh_required"
    return status


def _status_for_core(pre_submit, weekly_ops, automation_check):
    market_count = _int_value(automation_check.get("market_count"), _int_value(weekly_ops.get("market_count")))
    markets_ready = _int_value(
        automation_check.get("markets_ready_count"),
        _int_value(weekly_ops.get("markets_ready_count")),
    )
    if (
        _pre_submit_status_for_medium_term(pre_submit) in {"ready", "ready_refresh_required"}
        and weekly_ops.get("status") == "ready"
        and market_count
        and markets_ready == market_count
    ):
        return "ready"
    return "blocked"


def _has_action_item(action_items, action_code):
    items = action_items.get("items", []) or [] if isinstance(action_items, dict) else []
    return any(
        isinstance(item, dict) and item.get("action_code") == action_code
        for item in items
    )


def _backlog_reduction_plan_status(action_items):
    if not action_items:
        return "missing"
    if not _has_action_item(action_items, "reduce_weekly_action_backlog"):
        return "not_required"
    plan = action_items.get("backlog_reduction_plan", [])
    if not isinstance(plan, list):
        return "missing"
    for entry in plan:
        if not isinstance(entry, dict):
            continue
        actions = entry.get("actions", [])
        if (
            entry.get("category")
            and _int_value(entry.get("count"), 0) > 0
            and isinstance(actions, list)
            and "reduce_weekly_action_backlog" in actions
        ):
            return "ready"
    return "missing"


def _goal(goal_code, title, status, current, target, next_action):
    return {
        "goal_code": goal_code,
        "title": title,
        "status": status,
        "current": current,
        "target": target,
        "next_action": next_action,
    }


def _goal_completion_percent(goal):
    status = goal.get("status", "needs_work")
    percent = STATUS_COMPLETION.get(status, 0)
    current = goal.get("current", {}) or {}
    goal_code = goal.get("goal_code", "")
    if goal_code == "weekly_delivery_stability" and status == "on_track":
        action_count = _int_value(current.get("weekly_action_items_count"))
        percent = 85 if action_count <= 8 else 75
        if (
            percent >= 85
            and _int_value(current.get("weekly_delivery_history_ready_count")) >= 4
            and _int_value(current.get("weekly_delivery_history_window_size")) >= 4
            and _int_value(current.get("weekly_delivery_history_needs_attention_count")) == 0
            and _int_value(current.get("weekly_delivery_history_stale_count")) == 0
            and _int_value(current.get("weekly_delivery_history_action_items_problem_count")) == 0
            and _int_value(current.get("weekly_delivery_history_conclusion_signal_problem_count")) == 0
            and _int_value(current.get("weekly_ops_history_ready_count")) >= 4
            and _int_value(current.get("weekly_ops_history_window_size")) >= 4
            and _int_value(current.get("weekly_ops_history_needs_attention_count")) == 0
            and _int_value(current.get("weekly_ops_history_stale_count")) == 0
        ):
            percent = 90
    elif goal_code == "backtest_evidence_quality":
        ratio = _float_value(current.get("verified_membership_ratio"))
        weak_rows = _int_value(current.get("weak_evidence_rows"))
        evidence_percent = min(50, int(ratio * 100))
        weak_evidence_bonus = 20 if weak_rows == 0 else max(0, 20 - min(20, weak_rows // 200))
        percent = max(percent, min(70, evidence_percent + weak_evidence_bonus))
    elif goal_code == "forecast_tracking_maturity" and status == "sample_accumulating":
        one_week = _int_value(current.get("one_week_mature"))
        one_month = _int_value(current.get("one_month_mature"))
        percent = min(65, 35 + min(15, one_week // 2) + min(15, one_month // 2))
    elif goal_code == "data_quality_convergence" and status == "on_track":
        if (
            _int_value(current.get("blocked_candidate_count")) == 0
            and _int_value(current.get("refetch_gap_count")) == 0
            and _int_value(current.get("refetch_gap_action_required_count")) == 0
            and _int_value(current.get("manual_financial_review_unclassified_count")) == 0
        ):
            percent = max(percent, 85)
    elif goal_code == "candidate_review_convergence" and status == "on_track":
        candidate_count = _int_value(current.get("candidate_count"))
        complete = _int_value(current.get("field_complete_count"))
        if (
            candidate_count
            and complete == candidate_count
            and _int_value(current.get("missing_field_count")) == 0
            and _int_value(current.get("risk_missing_count")) == 0
            and _int_value(current.get("risk_unclassified_count")) == 0
            and _int_value(current.get("risk_action_unqueued_count")) == 0
            and _int_value(current.get("risk_action_required_count")) <= 20
        ):
            percent = max(percent, 85)
    elif goal_code == "model_governance_handoff" and status == "on_track":
        if (
            current.get("governance_status") == "ready"
            and current.get("pre_submit_status") in {"ready", "ready_refresh_required"}
            and current.get("collaboration_execution_mode")
            == "single_codex_with_gpt55_review_checklist"
            and current.get("automatic_multi_model_collaboration_enabled") is False
        ):
            percent = max(percent, 85)
    return max(0, min(100, percent))


def _attach_goal_progress(goals):
    for goal in goals:
        goal["module"] = GOAL_MODULES.get(goal.get("goal_code"), goal.get("title", "unknown"))
        goal["completion_percent"] = _goal_completion_percent(goal)
        goal["target_completion_percent"] = GOAL_TARGET_COMPLETION.get(goal.get("goal_code"), 100)
        goal["completion_gap_percent"] = max(
            0,
            _int_value(goal.get("target_completion_percent")) - _int_value(goal.get("completion_percent")),
        )
    return goals


def _overall_completion_percent(goals):
    if not goals:
        return 0
    return round(sum(_int_value(goal.get("completion_percent")) for goal in goals) / len(goals))


def _development_completion_policy():
    return {
        "required_in_task_closeout": True,
        "closeout_fields": [
            "current_module",
            "module_completion_percent",
            "medium_term_overall_completion_percent",
            "current_target_total_completion_percent",
        ],
        "module_completion_source": "outputs/automation/latest_medium_term_goal_review.json goals[].completion_percent",
        "scope_note": "每次小任务开发完成后，最终汇报必须说明当前开发内容所属模块、该模块完成度和当前目标总完成度。",
    }


def _closeout_goal(goals, goal_code=""):
    goals = [goal for goal in goals if isinstance(goal, dict)]
    if goal_code:
        goal = next((item for item in goals if item.get("goal_code") == goal_code), None)
        if goal:
            return goal
    for status in ("needs_work", "sample_accumulating", "blocked"):
        goal = next((item for item in goals if item.get("status") == status), None)
        if goal:
            return goal
    goal = next(
        (item for item in goals if item.get("goal_code") == "model_governance_handoff"),
        None,
    )
    return goal or (goals[0] if goals else {})


def _task_closeout_snapshot(goals, goal_code=""):
    overall = _overall_completion_percent(goals)
    goal = _closeout_goal(goals, goal_code=goal_code)
    return {
        "goal_code": goal.get("goal_code", "unknown"),
        "current_module": goal.get("module", "unknown"),
        "module_completion_percent": _int_value(goal.get("completion_percent")),
        "medium_term_overall_completion_percent": overall,
        "current_target_total_completion_percent": overall,
    }


def _weekly_delivery_goal(
    pre_submit,
    weekly_ops,
    automation_check,
    weekly_action_items=None,
    weekly_ops_history=None,
    weekly_delivery_history=None,
):
    weekly_action_items = weekly_action_items or {}
    weekly_ops_history = weekly_ops_history or {}
    weekly_delivery_history = weekly_delivery_history or {}
    backlog_plan = weekly_action_items.get("backlog_reduction_plan", [])
    core = _status_for_core(pre_submit, weekly_ops, automation_check)
    backlog_plan_status = _backlog_reduction_plan_status(weekly_action_items)
    if core != "ready":
        status = "blocked"
        next_action = "restore_weekly_delivery_ready_state"
    elif backlog_plan_status == "missing":
        status = "needs_work"
        next_action = "review_weekly_action_backlog_reduction_plan"
    else:
        status = "on_track"
        next_action = "continue_weekly_delivery_monitoring"
    return _goal(
        "weekly_delivery_stability",
        "稳定每周三市场交付",
        status,
        {
            "pre_submit_status": _pre_submit_status_for_medium_term(pre_submit),
            "weekly_ops_status": weekly_ops.get("status", "missing"),
            "markets_ready_count": _int_value(
                automation_check.get("markets_ready_count"),
                _int_value(weekly_ops.get("markets_ready_count")),
            ),
            "market_count": _int_value(
                automation_check.get("market_count"),
                _int_value(weekly_ops.get("market_count")),
            ),
            "weekly_action_items_count": _int_value(
                weekly_action_items.get("item_count"),
                len(weekly_action_items.get("items", []) or []),
            ),
            "weekly_action_backlog_reduction_plan_status": backlog_plan_status,
            "weekly_action_backlog_reduction_plan_categories": len(backlog_plan)
            if isinstance(backlog_plan, list)
            else 0,
            "weekly_delivery_history_ready_count": _int_value(
                weekly_delivery_history.get("ready_count")
            ),
            "weekly_delivery_history_window_size": _int_value(
                weekly_delivery_history.get("window_size")
            ),
            "weekly_delivery_history_needs_attention_count": _int_value(
                weekly_delivery_history.get("needs_attention_count")
            ),
            "weekly_delivery_history_stale_count": _int_value(
                weekly_delivery_history.get("stale_count")
            ),
            "weekly_delivery_history_action_items_problem_count": _int_value(
                weekly_delivery_history.get("action_items_problem_count")
            ),
            "weekly_delivery_history_conclusion_signal_problem_count": _int_value(
                weekly_delivery_history.get("conclusion_signal_problem_count")
            ),
            "weekly_ops_history_ready_count": _int_value(
                weekly_ops_history.get("ready_count")
            ),
            "weekly_ops_history_window_size": _int_value(
                weekly_ops_history.get("window_size")
            ),
            "weekly_ops_history_needs_attention_count": _int_value(
                weekly_ops_history.get("needs_attention_count")
            ),
            "weekly_ops_history_stale_count": _int_value(
                weekly_ops_history.get("stale_count")
            ),
        },
        "连续 4-6 周保持三市场 ready，提交前复核 ready，关键产物无缺失或过期。",
        next_action,
    )


def _data_quality_goal(data_health, automation_check):
    blocked = _int_value(data_health.get("blocked_candidate_count"))
    refetch = _int_value(data_health.get("refetch_gap_count"))
    refetch_action_required = _int_value(
        data_health.get("refetch_gap_action_required_count", refetch)
    )
    refetch_attempted = _int_value(data_health.get("refetch_gap_attempted_count"))
    refetch_unresolved_non_candidate = _int_value(
        data_health.get("refetch_gap_unresolved_non_candidate_count")
    )
    manual = _int_value(data_health.get("manual_financial_review_count"))
    candidate_manual = _int_value(data_health.get("candidate_manual_financial_review_count"))
    classified = _int_value(data_health.get("manual_financial_review_classified_count"))
    unclassified = _int_value(
        data_health.get(
            "manual_financial_review_unclassified_count",
            manual if manual else 0,
        )
    )
    candidate_unclassified = _int_value(
        data_health.get("candidate_manual_financial_review_unclassified_count")
    )
    manual_resolved = manual <= 40 or (manual > 0 and unclassified == 0)
    status = "on_track" if blocked == 0 and refetch_action_required == 0 and manual_resolved else "needs_work"
    if unclassified:
        next_action = "reduce_manual_financial_review_items"
    elif refetch_action_required:
        next_action = "resolve_refetch_gaps"
    else:
        next_action = "continue_data_quality_monitoring"
    return _goal(
        "data_quality_convergence",
        "数据质量从可监控提升到可解释可收敛",
        status,
        {
            "data_quality_score": _float_value(automation_check.get("data_quality_score")),
            "data_quality_status": automation_check.get("data_quality_status", "unknown"),
            "blocked_candidate_count": blocked,
            "refetch_gap_count": refetch,
            "refetch_gap_attempted_count": refetch_attempted,
            "refetch_gap_action_required_count": refetch_action_required,
            "refetch_gap_unresolved_non_candidate_count": refetch_unresolved_non_candidate,
            "manual_financial_review_count": manual,
            "candidate_manual_financial_review_count": candidate_manual,
            "manual_financial_review_classified_count": classified,
            "manual_financial_review_unclassified_count": unclassified,
            "candidate_manual_financial_review_unclassified_count": candidate_unclassified,
        },
        "候选阻断数保持 0，可重抓缺口收敛到 0，财务人工复核项降至 40 以下或全部完成分类。",
        next_action,
    )


def _candidate_review_goal(candidate_findings):
    candidate_count = _int_value(candidate_findings.get("candidate_count"))
    complete = _int_value(candidate_findings.get("field_complete_count"))
    missing = _int_value(candidate_findings.get("missing_field_count"))
    risk_missing = _int_value(candidate_findings.get("risk_missing_count"))
    risk_review = _int_value(candidate_findings.get("risk_review_count"))
    risk_classified = _int_value(candidate_findings.get("risk_classified_count"))
    risk_unclassified = _int_value(candidate_findings.get("risk_unclassified_count", risk_review))
    risk_action_required = _int_value(candidate_findings.get("risk_action_required_count", risk_review))
    risk_action_queue = _int_value(candidate_findings.get("risk_action_queue_count"))
    risk_action_unqueued = _int_value(
        candidate_findings.get("risk_action_unqueued_count", risk_action_required)
    )
    risks_resolved = risk_review <= 20 or (
        risk_review > 0 and risk_unclassified == 0 and risk_action_unqueued == 0
    )
    status = "on_track" if candidate_count and complete == candidate_count and missing == 0 and risk_missing == 0 and risks_resolved else "needs_work"
    if risk_unclassified:
        next_action = "classify_candidate_risks"
    elif risk_action_unqueued:
        next_action = "review_candidate_action_required_risks"
    else:
        next_action = "continue_candidate_review_monitoring"
    return _goal(
        "candidate_review_convergence",
        "候选结论变成可排序可复核的研究清单",
        status,
        {
            "candidate_count": candidate_count,
            "field_complete_count": complete,
            "missing_field_count": missing,
            "risk_missing_count": risk_missing,
            "risk_review_count": risk_review,
            "risk_classified_count": risk_classified,
            "risk_unclassified_count": risk_unclassified,
            "risk_action_required_count": risk_action_required,
            "risk_action_queue_count": risk_action_queue,
            "risk_action_unqueued_count": risk_action_unqueued,
        },
        "候选字段完整率保持 100%，风险提示全覆盖，风险复核项完成分类并逐步降至 20 以下。",
        next_action,
    )


def _forecast_goal(forecast_performance):
    mature = _int_value(forecast_performance.get("mature_evaluations"))
    latest_short_missing = _int_value(forecast_performance.get("latest_short_signal_missing_count"))
    maturity_gap_reasons = forecast_performance.get("maturity_gap_reasons", {}) or {}
    maturity_gap_prediction_unavailable = _int_value(maturity_gap_reasons.get("prediction_unavailable"))
    maturity_gap_pending_maturity = _int_value(maturity_gap_reasons.get("pending_maturity"))
    maturity_gap_other_not_evaluated = _int_value(maturity_gap_reasons.get("other_not_evaluated"))
    latest_prediction_unavailable_raw = forecast_performance.get("latest_prediction_unavailable_count")
    latest_prediction_unavailable = (
        maturity_gap_prediction_unavailable
        if latest_prediction_unavailable_raw is None
        else _int_value(latest_prediction_unavailable_raw, 0)
    )
    legacy_prediction_unavailable = _int_value(
        forecast_performance.get("legacy_prediction_unavailable_count"),
        0,
    )
    status = "needs_work" if latest_short_missing else "sample_accumulating" if mature < 30 else "on_track"
    if latest_short_missing:
        next_action = "fix_latest_short_prediction_fields"
    elif latest_prediction_unavailable and not maturity_gap_pending_maturity and mature < 30:
        next_action = "review_prediction_unavailable_signals"
    else:
        next_action = "continue_sample_accumulation"
    return _goal(
        "forecast_tracking_maturity",
        "1周和1个月走势预测进入可评估阶段",
        status,
        {
            "total_evaluations": _int_value(forecast_performance.get("total_evaluations")),
            "mature_evaluations": mature,
            "one_week_mature": _int_value(forecast_performance.get("one_week_mature")),
            "one_month_mature": _int_value(forecast_performance.get("one_month_mature")),
            "latest_short_signal_missing_count": latest_short_missing,
            "latest_prediction_unavailable_count": latest_prediction_unavailable,
            "legacy_prediction_unavailable_count": legacy_prediction_unavailable,
            "next_one_week_evaluation_date": forecast_performance.get(
                "next_one_week_evaluation_date",
                "unknown",
            ),
            "next_one_week_evaluation_count": _int_value(
                forecast_performance.get("next_one_week_evaluation_count"),
                0,
            ),
            "next_one_month_evaluation_date": forecast_performance.get(
                "next_one_month_evaluation_date",
                "unknown",
            ),
            "next_one_month_evaluation_count": _int_value(
                forecast_performance.get("next_one_month_evaluation_count"),
                0,
            ),
            "maturity_gap_prediction_unavailable": maturity_gap_prediction_unavailable,
            "maturity_gap_pending_maturity": maturity_gap_pending_maturity,
            "maturity_gap_other_not_evaluated": maturity_gap_other_not_evaluated,
        },
        "最新预测缺失数保持 0，成熟样本达到 30 条以上后再评估方向命中率和超额收益。",
        next_action,
    )


def _requires_official_csv(current_membership_sources, current_membership_source_inbox_status):
    if current_membership_sources.get("status") == "ready":
        return False
    if current_membership_source_inbox_status.get("external_input_required"):
        return True
    return current_membership_source_inbox_status.get("status") in {"missing", "invalid", "incomplete"}


def _backtest_next_action(
    membership_import_plan,
    current_membership_sources,
    current_membership_source_inbox_status=None,
):
    current_membership_source_inbox_status = current_membership_source_inbox_status or {}
    if _int_value(membership_import_plan.get("ready_to_import_count")) > 0:
        return "run_membership_evidence_apply_preview"
    if _requires_official_csv(current_membership_sources, current_membership_source_inbox_status):
        return (
            current_membership_sources.get("fetch_error_next_action")
            or "provide_official_constituents_csv"
        )
    recommended_followup = current_membership_sources.get("recommended_followup", "")
    if recommended_followup == "run_membership_evidence_import_plan_then_apply_preview":
        return recommended_followup
    if recommended_followup == "provide_official_constituents_csv":
        return current_membership_sources.get("fetch_error_next_action") or recommended_followup
    if recommended_followup == "review_current_membership_source_status":
        return recommended_followup
    return "supplement_verified_membership_evidence"


def _review_queue_status_counts(items):
    counts = {"open": 0, "resolved": 0}
    if not isinstance(items, list):
        return counts
    resolved_statuses = {"resolved", "closed", "done", "accepted", "ignored"}
    for item in items:
        if not isinstance(item, dict):
            continue
        status = str(item.get("review_status", "")).strip().lower()
        if status in resolved_statuses:
            counts["resolved"] += 1
        else:
            counts["open"] += 1
    return counts


def _path_exists(path):
    return bool(path) and Path(path).exists()


def _backtest_goal(
    backtest_evidence,
    membership_import_plan=None,
    membership_apply_preview=None,
    current_membership_sources=None,
    current_membership_source_review_status=None,
    current_membership_source_inbox_status=None,
):
    membership_import_plan = membership_import_plan or {}
    membership_apply_preview = membership_apply_preview or {}
    current_membership_sources = current_membership_sources or {}
    current_membership_source_review_status = current_membership_source_review_status or {}
    current_membership_source_inbox_status = current_membership_source_inbox_status or {}
    ratio = _float_value(backtest_evidence.get("verified_membership_ratio"))
    weak_rows = _int_value(backtest_evidence.get("weak_evidence_rows"))
    status = "on_track" if ratio >= 0.5 and weak_rows == 0 else "needs_work"
    next_action = _backtest_next_action(
        membership_import_plan,
        current_membership_sources,
        current_membership_source_inbox_status,
    )
    review_queue = current_membership_sources.get("missing_ticker_review_queue", []) or []
    review_queue_counts = _review_queue_status_counts(review_queue)
    return _goal(
        "backtest_evidence_quality",
        "补强回测证据，暂不升级模型",
        status,
        {
            "weeks_completed": _int_value(backtest_evidence.get("weeks_completed")),
            "weeks_failed": _int_value(backtest_evidence.get("weeks_failed")),
            "verified_membership_ratio": ratio,
            "weak_evidence_rows": weak_rows,
            "weak_evidence_weeks": _int_value(backtest_evidence.get("weak_evidence_weeks")),
            "membership_evidence_action_required_count": _int_value(
                backtest_evidence.get("membership_evidence_action_required_count")
            ),
            "membership_evidence_action_queue_count": _int_value(
                backtest_evidence.get("membership_evidence_action_queue_count")
            ),
            "membership_evidence_action_unqueued_count": _int_value(
                backtest_evidence.get("membership_evidence_action_unqueued_count")
            ),
            "membership_evidence_ready_to_import_count": _int_value(
                membership_import_plan.get("ready_to_import_count")
            ),
            "membership_evidence_missing_source_count": _int_value(
                membership_import_plan.get("missing_source_count")
            ),
            "membership_evidence_invalid_source_count": _int_value(
                membership_import_plan.get("invalid_source_count")
            ),
            "membership_evidence_ready_to_import_weeks_affected": _int_value(
                membership_import_plan.get("ready_to_import_weeks_affected")
            ),
            "membership_evidence_missing_source_weeks_affected": _int_value(
                membership_import_plan.get("missing_source_weeks_affected")
            ),
            "membership_evidence_invalid_source_weeks_affected": _int_value(
                membership_import_plan.get("invalid_source_weeks_affected")
            ),
            "membership_evidence_import_next_action": membership_import_plan.get(
                "next_action",
                "missing",
            ),
            "membership_evidence_preview_eligible_ticker_count": _int_value(
                membership_apply_preview.get("eligible_ticker_count")
            ),
            "membership_evidence_preview_row_count": _int_value(
                membership_apply_preview.get("preview_row_count")
            ),
            "membership_evidence_preview_weeks_affected": _int_value(
                membership_apply_preview.get("preview_weeks_affected")
            ),
            "membership_evidence_preview_invalid_source_ticker_count": _int_value(
                membership_apply_preview.get("invalid_source_ticker_count")
            ),
            "membership_evidence_preview_applied": bool(
                membership_apply_preview.get("applied_to_historical_membership")
            ),
            "sp500_current_source_status": current_membership_sources.get("status", "missing"),
            "sp500_current_source_next_action": current_membership_sources.get("next_action", "missing"),
            "sp500_current_source_matched_count": _int_value(
                current_membership_sources.get("matched_count")
            ),
            "sp500_current_source_missing_count": _int_value(
                current_membership_sources.get("missing_count")
            ),
            "sp500_current_source_missing_ticker_review_queue_count": len(
                review_queue
            ),
            "sp500_current_source_review_queue_file": current_membership_sources.get(
                "missing_ticker_review_queue_file",
                "",
            ),
            "sp500_current_source_file_request_file": current_membership_sources.get(
                "source_file_request_file",
                "",
            ),
            "sp500_current_source_file_request_exists": _path_exists(
                current_membership_sources.get("source_file_request_file", "")
            ),
            "sp500_current_source_file_inbox": current_membership_sources.get(
                "source_file_inbox",
                "",
            ),
            "sp500_current_source_file_inbox_exists": bool(
                current_membership_sources.get("source_file_inbox_exists")
            ),
            "sp500_current_source_file_validation_status": current_membership_sources.get(
                "source_file_validation_status",
                "unknown",
            ),
            "sp500_current_source_fetch_error_type": current_membership_sources.get(
                "fetch_error_type",
                "unknown",
            ),
            "sp500_current_source_fetch_retryable_without_environment_change": current_membership_sources.get(
                "fetch_retryable_without_environment_change"
            ),
            "sp500_current_source_fetch_error_next_action": current_membership_sources.get(
                "fetch_error_next_action",
                "unknown",
            ),
            "sp500_current_source_inbox_status": current_membership_source_inbox_status.get(
                "status",
                "missing",
            ),
            "sp500_current_source_inbox_next_action": current_membership_source_inbox_status.get(
                "next_action",
                "missing",
            ),
            "sp500_current_source_inbox_validation_status": current_membership_source_inbox_status.get(
                "source_file_validation_status",
                "unknown",
            ),
            "sp500_current_source_inbox_parsed_official_ticker_count": _int_value(
                current_membership_source_inbox_status.get("parsed_official_ticker_count")
            ),
            "sp500_current_source_inbox_intake_missing_count": _int_value(
                current_membership_source_inbox_status.get("intake_missing_count")
            ),
            "sp500_current_source_inbox_size_bytes": _int_value(
                current_membership_source_inbox_status.get("source_file_inbox_size_bytes")
            ),
            "sp500_current_source_inbox_sha256": current_membership_source_inbox_status.get(
                "source_file_inbox_sha256",
                "",
            ),
            "sp500_current_source_inbox_modified_at": current_membership_source_inbox_status.get(
                "source_file_inbox_modified_at",
                "",
            ),
            "sp500_current_source_inbox_external_input_required": bool(
                current_membership_source_inbox_status.get("external_input_required")
            ),
            "sp500_current_source_inbox_blocking_reason": current_membership_source_inbox_status.get(
                "blocking_reason",
                "",
            ),
            "sp500_current_source_inbox_blocking_input": current_membership_source_inbox_status.get(
                "blocking_input",
                "",
            ),
            "sp500_current_source_inbox_dry_run_command": current_membership_sources.get(
                "source_file_inbox_dry_run_command",
                "",
            ),
            "sp500_current_source_inbox_import_command": current_membership_sources.get(
                "source_file_inbox_next_command",
                "",
            ),
            "sp500_current_source_review_queue_open_count": review_queue_counts["open"],
            "sp500_current_source_review_queue_resolved_count": review_queue_counts["resolved"],
            "sp500_current_source_review_status": current_membership_source_review_status.get(
                "status",
                "missing",
            ),
            "sp500_current_source_review_status_open_count": _int_value(
                current_membership_source_review_status.get("open_count")
            ),
            "sp500_current_source_review_status_resolved_count": _int_value(
                current_membership_source_review_status.get("resolved_count")
            ),
            "sp500_current_source_review_status_next_action": current_membership_source_review_status.get(
                "next_action",
                "missing",
            ),
            "sp500_current_source_review_decision_status": current_membership_source_review_status.get(
                "review_decision_status",
                "unknown",
            ),
            "sp500_current_source_review_manual_decision_next_step": current_membership_source_review_status.get(
                "manual_decision_next_step",
                "unknown",
            ),
            "sp500_current_source_review_decision_pending_tickers": current_membership_source_review_status.get(
                "decision_pending_tickers",
                [],
            )
            or [],
            "sp500_current_source_review_decision_ready_to_apply_tickers": current_membership_source_review_status.get(
                "decision_ready_to_apply_tickers",
                [],
            )
            or [],
            "sp500_current_source_review_decision_file_exists": bool(
                current_membership_source_review_status.get("decision_file_exists")
            ),
            "sp500_current_source_review_decision_ready_to_apply_count": _int_value(
                current_membership_source_review_status.get("decision_ready_to_apply_count")
            ),
            "sp500_current_source_review_decision_pending_count": _int_value(
                current_membership_source_review_status.get("decision_pending_count")
            ),
            "sp500_current_source_review_decision_invalid_count": _int_value(
                current_membership_source_review_status.get("decision_invalid_count")
            ),
            "sp500_current_source_review_decisions_template_exists": bool(
                current_membership_source_review_status.get("decisions_template_exists")
            ),
            "sp500_current_source_review_decisions_template_status": current_membership_source_review_status.get(
                "decisions_template_status",
                "unknown",
            ),
            "sp500_current_source_review_decisions_template_total_count": _int_value(
                current_membership_source_review_status.get("decisions_template_total_count")
            ),
            "sp500_current_source_review_decisions_template_matched_open_count": _int_value(
                current_membership_source_review_status.get(
                    "decisions_template_matched_open_count"
                )
            ),
            "sp500_current_source_review_decisions_template_missing_open_count": len(
                current_membership_source_review_status.get(
                    "decisions_template_missing_open_tickers",
                    [],
                )
                or []
            ),
            "sp500_current_source_review_decisions_template_extra_count": len(
                current_membership_source_review_status.get(
                    "decisions_template_extra_tickers",
                    [],
                )
                or []
            ),
            "sp500_current_source_review_decisions_template_missing_field_count": len(
                current_membership_source_review_status.get(
                    "decisions_template_missing_fields",
                    [],
                )
                or []
            ),
            "sp500_current_source_intake_coverage_status": current_membership_sources.get(
                "intake_coverage_status",
                "missing",
            ),
            "sp500_current_source_intake_expected_count": _int_value(
                current_membership_sources.get("intake_expected_count")
            ),
            "sp500_current_source_intake_matched_count": _int_value(
                current_membership_sources.get("intake_matched_count")
            ),
            "sp500_current_source_intake_missing_count": _int_value(
                current_membership_sources.get("intake_missing_count")
            ),
            "sp500_current_source_recommended_followup": current_membership_sources.get(
                "recommended_followup",
                "missing",
            ),
        },
        "历史成分证据验证比例先提升到 50% 以上，并持续降低弱证据行数。",
        next_action,
    )


def _governance_goal(pre_submit):
    status = "on_track" if pre_submit.get("governance_status") == "ready" else "needs_work"
    return _goal(
        "model_governance_handoff",
        "建立多模型协作治理准备",
        status,
        {
            "governance_status": pre_submit.get("governance_status", "missing"),
            "pre_submit_status": _pre_submit_status_for_medium_term(pre_submit),
            "governance_mode": COLLABORATION_EXECUTION_MODE,
            "collaboration_execution_mode": COLLABORATION_EXECUTION_MODE,
            "collaboration_boundary_note": COLLABORATION_BOUNDARY_NOTE,
            "automatic_multi_model_collaboration_enabled": AUTOMATIC_MULTI_MODEL_COLLABORATION_ENABLED,
            "task_closeout_progress_required": True,
        },
        "建立面向多模型协作的治理流程；当前阶段由单 Codex 执行，并通过二次审查清单模拟 gpt5.5 复核角色，具备自动调度能力后再升级为真正自动协作。",
        "review_governance_handoff" if status != "on_track" else "continue_governance_handoff",
    )


def _priority_actions(goals):
    actions = []
    for goal in goals:
        if goal["status"] in {"blocked", "needs_work", "sample_accumulating"}:
            action = goal.get("next_action", "")
            if action and action not in actions:
                actions.append(action)
    priority_order = {
        "provide_official_constituents_csv_or_fix_network_permission": 0,
        "provide_official_constituents_csv": 1,
        "provide_valid_official_constituents_csv": 2,
        "run_membership_evidence_apply_preview": 3,
        "run_membership_evidence_import_plan_then_apply_preview": 4,
        "review_current_membership_source_status": 5,
        "review_prediction_unavailable_signals": 6,
        "continue_sample_accumulation": 7,
    }
    actions.sort(key=lambda action: priority_order.get(action, 100))
    return actions or ["continue_medium_term_monitoring"]


def build_medium_term_goal_review(project_root=".", closeout_goal_code=""):
    root = Path(project_root)
    inputs = {
        key: _load_json(root / AUTOMATION_DIR / filename)
        for key, filename in INPUT_FILES.items()
    }
    pre_submit = inputs["pre_submit"]
    automation_check = inputs["automation_check"]
    weekly_ops = inputs["weekly_ops"]
    weekly_ops_history = inputs["weekly_ops_history"]
    weekly_delivery_history = inputs["weekly_delivery_history"]
    weekly_action_items = inputs["weekly_action_items"]
    data_health = inputs["data_health"]
    candidate_findings = inputs["candidate_findings"]
    forecast_performance = inputs["forecast_performance"]
    backtest_evidence = inputs["backtest_evidence"]
    membership_import_plan = inputs["membership_evidence_import_plan"]
    membership_apply_preview = inputs["membership_evidence_apply_preview"]
    current_membership_sources = inputs["sp500_current_membership_sources"]
    current_membership_source_review_status = inputs[
        "sp500_current_membership_source_review_status"
    ]
    current_membership_source_inbox_status = inputs[
        "sp500_current_membership_source_inbox_status"
    ]

    core_delivery_status = _status_for_core(pre_submit, weekly_ops, automation_check)
    goals = [
        _weekly_delivery_goal(
            pre_submit,
            weekly_ops,
            automation_check,
            weekly_action_items,
            weekly_ops_history,
            weekly_delivery_history,
        ),
        _data_quality_goal(data_health, automation_check),
        _candidate_review_goal(candidate_findings),
        _forecast_goal(forecast_performance),
        _backtest_goal(
            backtest_evidence,
            membership_import_plan,
            membership_apply_preview,
            current_membership_sources,
            current_membership_source_review_status,
            current_membership_source_inbox_status,
        ),
        _governance_goal(pre_submit),
    ]
    goals = _attach_goal_progress(goals)
    overall_completion_percent = _overall_completion_percent(goals)
    if core_delivery_status != "ready":
        status = "blocked"
    elif any(goal["status"] in {"needs_work", "sample_accumulating"} for goal in goals):
        status = "on_track_with_monitoring"
    else:
        status = "ready_for_phase_review"

    return {
        "review_schema": REVIEW_SCHEMA,
        "review_version": REVIEW_VERSION,
        "as_of_date": _first_value(
            pre_submit.get("as_of_date"),
            automation_check.get("as_of_date"),
            weekly_ops.get("as_of_date"),
        ),
        "period": PERIOD,
        "strategy_code": STRATEGY_CODE,
        "strategy_title": STRATEGY_TITLE,
        "status": status,
        "core_delivery_status": core_delivery_status,
        "overall_completion_percent": overall_completion_percent,
        "current_target_total_completion_percent": overall_completion_percent,
        "candidate_count_total": _int_value(
            _first_value(
                pre_submit.get("candidate_count_total"),
                automation_check.get("candidate_count_total"),
                weekly_ops.get("candidate_count_total"),
                default=0,
            )
        ),
        "market_count": _int_value(_first_value(automation_check.get("market_count"), weekly_ops.get("market_count"), default=0)),
        "markets_ready_count": _int_value(
            _first_value(
                automation_check.get("markets_ready_count"),
                weekly_ops.get("markets_ready_count"),
                default=0,
            )
        ),
        "goals": goals,
        "priority_next_actions": _priority_actions(goals),
        "formal_model_change_allowed": False,
        "formal_model_upgrade_allowed": False,
        "automatic_multi_model_collaboration_enabled": AUTOMATIC_MULTI_MODEL_COLLABORATION_ENABLED,
        "collaboration_execution_mode": COLLABORATION_EXECUTION_MODE,
        "collaboration_boundary_note": COLLABORATION_BOUNDARY_NOTE,
        "development_completion_policy": _development_completion_policy(),
        "task_closeout_snapshot": _task_closeout_snapshot(
            goals,
            goal_code=closeout_goal_code,
        ),
        "inputs": {
            key: str(root / AUTOMATION_DIR / filename)
            for key, filename in INPUT_FILES.items()
        },
        "boundary": "只读取现有自动化复核产物，不抓取行情，不重新评分，不修改正式模型参数。",
    }


def _pct(value):
    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return "unknown"


def _status_label(status):
    labels = {
        "ready_for_phase_review": "可进入阶段复盘",
        "on_track_with_monitoring": "推进中，仍需监控",
        "blocked": "主链路阻断，先恢复交付",
        "on_track": "按计划推进",
        "needs_work": "需要处理",
        "sample_accumulating": "样本积累中",
    }
    return labels.get(status, status)


def _format_current(goal):
    current = goal.get("current", {}) or {}
    parts = []
    for key, value in current.items():
        if key == "verified_membership_ratio":
            value = _pct(value)
        parts.append(f"{key}={value}")
    return "; ".join(parts)


def render_medium_term_goal_review(payload):
    lines = [
        "# 中期目标进度看板",
        "",
        f"- 日期：{payload.get('as_of_date', 'unknown')}",
        f"- 周期：6-8 周",
        f"- 总体状态：{payload.get('status', 'unknown')}（{_status_label(payload.get('status', 'unknown'))}）",
        f"- 主交付链路：{payload.get('core_delivery_status', 'unknown')}",
        f"- 三市场 ready：{payload.get('markets_ready_count', 0)}/{payload.get('market_count', 0)}",
        f"- 候选公司数：{payload.get('candidate_count_total', 0)}",
        f"- 正式模型变更：{'允许' if payload.get('formal_model_change_allowed') else '不允许'}",
        f"- 正式模型升级：{'允许' if payload.get('formal_model_upgrade_allowed') else '不允许'}",
        "",
        "## 目标进度",
        "",
        "| 目标 | 状态 | 当前指标 | 中期目标 | 下一步 |",
        "|---|---|---|---|---|",
    ]
    for goal in payload.get("goals", []) or []:
        lines.append(
            f"| {goal.get('goal_code', '')} | {goal.get('status', '')}（{_status_label(goal.get('status', ''))}） | "
            f"{_format_current(goal)} | {goal.get('target', '')} | {goal.get('next_action', '')} |"
        )
    lines.extend(
        [
            "",
            "## 优先动作",
            "",
        ]
    )
    for index, action in enumerate(payload.get("priority_next_actions", []) or [], start=1):
        lines.append(f"{index}. {action}")
    lines.extend(
        [
            "",
            "## 边界",
            f"- {payload.get('boundary', '')}",
            "- 该看板用于中期目标治理和每周进度复盘，不构成投资建议。",
            "",
        ]
    )
    return "\n".join(lines)


def render_medium_term_goal_review(payload):
    lines = [
        "# 中期目标进度看板",
        "",
        f"- 日期：{payload.get('as_of_date', 'unknown')}",
        f"- 周期：{payload.get('period', PERIOD)}",
        f"- 推荐方案：{payload.get('strategy_title', STRATEGY_TITLE)}",
            f"- 总体状态：{payload.get('status', 'unknown')}（{_status_label(payload.get('status', 'unknown'))}）",
            f"- 中期目标整体完成度：{payload.get('overall_completion_percent', 0)}%",
            f"- 当前目标总完成度：{payload.get('current_target_total_completion_percent', payload.get('overall_completion_percent', 0))}%",
            f"- 主交付链路：{payload.get('core_delivery_status', 'unknown')}",
        f"- 三市场 ready：{payload.get('markets_ready_count', 0)}/{payload.get('market_count', 0)}",
        f"- 候选公司数：{payload.get('candidate_count_total', 0)}",
        f"- 自动双模型协作：{'已启用' if payload.get('automatic_multi_model_collaboration_enabled') else '未启用，当前为单 Codex 执行 + gpt5.5 复核清单模拟'}",
        f"- 真实执行模式：{payload.get('collaboration_execution_mode', 'unknown')}",
        f"- 协作边界：{payload.get('collaboration_boundary_note', 'unknown')}",
        f"- 正式模型变更：{'允许' if payload.get('formal_model_change_allowed') else '不允许'}",
        f"- 正式模型升级：{'允许' if payload.get('formal_model_upgrade_allowed') else '不允许'}",
        "",
        "## 目标进度",
        "",
        "| 目标 | 模块 | 状态 | 完成度 | 目标完成度 | 差距 | 当前指标 | 中期目标 | 下一步 |",
        "|---|---|---|---:|---:|---:|---|---|---|",
    ]
    for goal in payload.get("goals", []) or []:
        lines.append(
            f"| {goal.get('goal_code', '')} | {goal.get('module', '')} | "
            f"{goal.get('status', '')}（{_status_label(goal.get('status', ''))}） | "
            f"{goal.get('completion_percent', 0)}% | {goal.get('target_completion_percent', 0)}% | "
            f"{goal.get('completion_gap_percent', 0)}% | {_format_current(goal)} | "
            f"{goal.get('target', '')} | {goal.get('next_action', '')} |"
        )
    snapshot = payload.get("task_closeout_snapshot", {}) or {}
    lines.extend(
        [
            "",
            "## 当前开发收尾摘要",
            "",
            f"- current_module={snapshot.get('current_module', 'unknown')}",
            f"- module_completion_percent={snapshot.get('module_completion_percent', 0)}%",
            f"- medium_term_overall_completion_percent={snapshot.get('medium_term_overall_completion_percent', 0)}%",
            f"- current_target_total_completion_percent={snapshot.get('current_target_total_completion_percent', payload.get('current_target_total_completion_percent', 0))}%",
            "",
            "## 优先动作",
            "",
        ]
    )
    for index, action in enumerate(payload.get("priority_next_actions", []) or [], start=1):
        lines.append(f"{index}. {action}")
    lines.extend(
        [
            "",
            "## 边界",
            f"- {payload.get('boundary', '')}",
            "- 该看板用于中期目标治理和每周进度复盘，不构成投资建议。",
            "",
        ]
    )
    return "\n".join(lines)


def write_json(payload, output):
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8-sig",
    )
    return output_path


def write_text(text, output):
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8-sig")
    return output_path


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build medium-term goal dashboard from existing weekly reviews.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--output", default="outputs/automation/latest_medium_term_goal_review.json")
    parser.add_argument("--report", default="outputs/automation/latest_medium_term_goal_review.md")
    parser.add_argument("--closeout-goal-code", default="")
    args = parser.parse_args()

    payload = build_medium_term_goal_review(
        args.project_root,
        closeout_goal_code=args.closeout_goal_code,
    )
    report = render_medium_term_goal_review(payload)
    if args.output:
        write_json(payload, args.output)
    if args.report:
        write_text(report, args.report)
    print(report, end="")
    print(f"Medium-term goal review: {args.report}")


if __name__ == "__main__":
    main()
