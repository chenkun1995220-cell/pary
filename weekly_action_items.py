import argparse
import csv
import json
import sys
from pathlib import Path


ACTION_ITEMS_SCHEMA = "weekly_action_items"
ACTION_ITEMS_VERSION = 1
EXPECTED_MANIFEST_SCHEMA = "self_analysis_manifest"
EXPECTED_MANIFEST_VERSION = 1
DEFAULT_MEMBERSHIP_IMPORT_PLAN = "outputs/automation/latest_membership_evidence_import_plan.json"
DEFAULT_CURRENT_MEMBERSHIP_SOURCES = "outputs/automation/latest_sp500_current_membership_sources.json"
DEFAULT_CURRENT_MEMBERSHIP_SOURCE_REVIEW_STATUS = (
    "outputs/automation/latest_sp500_current_membership_source_review_status.json"
)
DEFAULT_CURRENT_MEMBERSHIP_SOURCE_INBOX_STATUS = (
    "outputs/automation/latest_sp500_current_membership_source_inbox_status.json"
)
DEFAULT_FORECAST_PERFORMANCE = "outputs/automation/latest_forecast_performance_review.json"
DEFAULT_MANUAL_REVIEW_QUEUE = "outputs/automation/latest_manual_review_queue.csv"
DEFAULT_DATA_HEALTH_REVIEW = "outputs/automation/latest_data_health_review.json"
DEFAULT_CANDIDATE_FINDINGS_REVIEW = "outputs/automation/latest_candidate_findings_review.json"
DEFAULT_BACKTEST_EVIDENCE_REVIEW = "outputs/automation/latest_backtest_evidence_review.json"
DEFAULT_HK_QUOTE_RETRY_RESULTS = "outputs/hk_universe/quote_retry_results.json"
DEFAULT_SOURCE_FILE_ACCEPTED_TICKER_COLUMNS = [
    "Symbol",
    "Ticker",
    "Ticker Symbol",
    "Constituent Ticker",
    "Constituent Symbol",
]
DELIVERY_HEALTH_MIRRORED_REASONS = {
    "automation_check:manual_review_needed",
    "data_quality_history:manual_review_needed",
}


def load_manifest(manifest):
    manifest_path = Path(manifest)
    payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if payload.get("manifest_schema") != EXPECTED_MANIFEST_SCHEMA:
        raise ValueError(f"unexpected manifest_schema: {payload.get('manifest_schema', '')}")
    if int(payload.get("manifest_version", 0) or 0) != EXPECTED_MANIFEST_VERSION:
        raise ValueError(f"unexpected manifest_version: {payload.get('manifest_version', '')}")
    return payload


def load_optional_json(path):
    if not path:
        return {}
    payload_path = Path(path)
    if not payload_path.exists():
        return {}
    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def load_optional_csv_rows(path):
    if not path:
        return []
    csv_path = Path(path)
    if not csv_path.exists():
        return []
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [
                {key.strip(): (value or "").strip() for key, value in row.items() if key}
                for row in csv.DictReader(handle)
            ]
    except OSError:
        return []


def _top_manual_review_item(rows):
    if not rows:
        return {}
    return sorted(rows, key=lambda row: _int_value(row.get("rank"), 999999))[0]


def _manual_review_queue_text(manifest, rows):
    count = manifest.get("manual_review_queue_count", 0)
    item = _top_manual_review_item(rows)
    if not item:
        return f"按优先级处理 latest_manual_review_queue.csv 中的 {count} 条复核项。"
    return (
        f"按优先级处理 latest_manual_review_queue.csv 中的 {count} 条复核项；"
        f"最高优先级：{item.get('market', 'unknown')} {item.get('ticker', '')} "
        f"{item.get('company', '')} / {item.get('review_type', '')} / "
        f"{item.get('review_detail', '')}。"
    )


def _delivery_history(manifest):
    history = manifest.get("weekly_delivery_history", {})
    return history if isinstance(history, dict) else {}


def _is_manual_review_pending_reason(reason):
    return str(reason or "").startswith("manual_review_pending:")


def _has_missing_conclusion_signal(history):
    return bool(
        history.get("latest_missing_conclusion_signals")
        or history.get("recurring_missing_conclusion_signals")
        or history.get("latest_missing_conclusion_signal_fixes")
        or history.get("recurring_missing_conclusion_signal_fixes")
    )


def _health_reasons(history):
    latest_reasons = {
        str(reason).strip()
        for reason in history.get("latest_conclusion_health_reasons", []) or []
        if str(reason).strip()
    }
    recurring_reasons = {
        str(item.get("reason", "")).strip()
        for item in history.get("recurring_health_reasons", []) or []
        if isinstance(item, dict) and str(item.get("reason", "")).strip()
    }
    reasons = latest_reasons | recurring_reasons
    if _manual_review_count({}, history) <= 0:
        reasons = {
            reason for reason in reasons if not _is_manual_review_pending_reason(reason)
        }
    return reasons


def _delivery_health_issue_is_actionable(history):
    if _manual_review_count({}, history) > 0:
        return True
    if _has_missing_conclusion_signal(history):
        return True
    return any(
        reason not in DELIVERY_HEALTH_MIRRORED_REASONS
        for reason in _health_reasons(history)
    )


def _health_reason_text(history):
    reasons = list(history.get("latest_conclusion_health_reasons", []) or [])
    latest_manual_pending = _int_value(history.get("latest_manual_review_pending_count"), 0)
    if latest_manual_pending <= 0:
        reasons = [reason for reason in reasons if not _is_manual_review_pending_reason(reason)]
    recurring = [
        f"{item.get('reason', 'unknown')} ({item.get('count', 0)})"
        for item in history.get("recurring_health_reasons", []) or []
        if isinstance(item, dict)
        and not (
            latest_manual_pending <= 0
            and _is_manual_review_pending_reason(item.get("reason"))
        )
    ]
    parts = []
    if reasons:
        parts.append("latest=" + ", ".join(reasons))
    if recurring:
        parts.append("recurring=" + ", ".join(recurring))
    return "; ".join(parts) if parts else "无交付健康原因"


def _missing_conclusion_signal_text(history):
    latest = [
        str(signal)
        for signal in history.get("latest_missing_conclusion_signals", []) or []
        if str(signal)
    ]
    recurring = [
        f"{item.get('signal', 'unknown')} ({item.get('count', 0)})"
        for item in history.get("recurring_missing_conclusion_signals", []) or []
        if isinstance(item, dict) and item.get("signal")
    ]
    parts = []
    if latest:
        parts.append("latest_missing_signals=" + ", ".join(latest))
    if recurring:
        parts.append("recurring_missing_signals=" + ", ".join(recurring))
    return "; ".join(parts)


def _missing_conclusion_signal_fix_text(history):
    latest_fixes = history.get("latest_missing_conclusion_signal_fixes", {}) or {}
    if not isinstance(latest_fixes, dict):
        latest_fixes = {}
    recurring_fixes = [
        f"{item.get('signal', 'unknown')}: {item.get('fix', '')} ({item.get('count', 0)})"
        for item in history.get("recurring_missing_conclusion_signal_fixes", []) or []
        if isinstance(item, dict) and item.get("signal") and item.get("fix")
    ]
    parts = []
    if latest_fixes:
        parts.append(
            "latest_signal_fixes="
            + ", ".join(f"{signal}: {fix}" for signal, fix in latest_fixes.items())
        )
    if recurring_fixes:
        parts.append("recurring_signal_fixes=" + ", ".join(recurring_fixes))
    return "; ".join(parts)


def _int_value(value, default=0):
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _manual_review_count(manifest, history):
    return _int_value(
        history.get("latest_manual_review_pending_count"),
        _int_value(manifest.get("manual_review_queue_count"), 0),
    )


def _percent_value(value):
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "unknown"


def _forecast_maturity_schedule_text(forecast_performance):
    one_week = forecast_performance.get("next_one_week_evaluation_date", "unknown")
    one_month = forecast_performance.get("next_one_month_evaluation_date", "unknown")
    one_week_count = _int_value(forecast_performance.get("next_one_week_evaluation_count"), 0)
    one_month_count = _int_value(forecast_performance.get("next_one_month_evaluation_count"), 0)
    if one_week != "unknown":
        one_week = f"{one_week} ({one_week_count} samples)"
    if one_month != "unknown":
        one_month = f"{one_month} ({one_month_count} samples)"
    if one_week == "unknown" and one_month == "unknown":
        return ""
    return f"；下一批1周可评估日期 {one_week}，1个月可评估日期 {one_month}"


def _quote_retry_text(quote_retry_results):
    if not isinstance(quote_retry_results, dict):
        return ""
    attempted = int(quote_retry_results.get("attempted", 0) or 0)
    if attempted <= 0:
        return ""
    updated = int(quote_retry_results.get("updated", 0) or 0)
    results = []
    for item in quote_retry_results.get("results", []) or []:
        if not isinstance(item, dict):
            continue
        ticker = item.get("ticker", "")
        status = item.get("status", "")
        if ticker and status:
            results.append(f"{ticker} {status}")
    detail = "；".join(results[:3])
    suffix = "；需补充行情源或人工复核字段口径" if updated < attempted else ""
    if detail:
        return f"；最近已重抓{attempted}条，成功{updated}条：{detail}{suffix}"
    return f"；最近已重抓{attempted}条，成功{updated}条{suffix}"


def _data_health_refetch_gap_text(data_health, quote_retry_results=None):
    if not isinstance(data_health, dict):
        return ""
    gaps = []
    for market in data_health.get("markets", []) or []:
        if not isinstance(market, dict):
            continue
        market_name = market.get("name", "unknown")
        for gap in market.get("refetch_gaps", []) or []:
            if not isinstance(gap, dict):
                continue
            ticker = gap.get("ticker", "")
            company = gap.get("company", "")
            missing_fields = gap.get("missing_fields", "")
            detail = " ".join(part for part in [market_name, ticker, company] if part)
            if missing_fields:
                detail = f"{detail} 缺失 {missing_fields}" if detail else f"缺失 {missing_fields}"
            if detail:
                gaps.append(detail)
    if not gaps:
        return _quote_retry_text(quote_retry_results)
    return "；当前可重抓缺口：" + "；".join(gaps[:3]) + _quote_retry_text(quote_retry_results)


def _data_quality_text(manifest):
    summary = manifest.get("data_quality_summary", {})
    if not isinstance(summary, dict):
        summary = {}
    markets = summary.get("markets", [])
    if not isinstance(markets, list):
        markets = []
    ranked = sorted(
        [market for market in markets if isinstance(market, dict)],
        key=lambda item: float(item.get("quality_score", 0) or 0),
    )
    if not ranked:
        return "暂无市场评分明细"
    weakest = ranked[0]
    reasons = "; ".join(weakest.get("reasons", []) or ["none"])
    return (
        f"优先复核 {weakest.get('name', 'unknown')}："
        f"评分 {weakest.get('quality_score', 0)}，"
        f"状态 {weakest.get('quality_status', 'unknown')}，"
        f"原因 {reasons}"
    )


def _data_quality_trend_text(manifest):
    history = manifest.get("data_quality_history", {})
    if not isinstance(history, dict):
        history = {}
    repeated = "、".join(history.get("repeated_needs_review_markets", []) or []) or "none"
    declining = "、".join(history.get("score_decline_markets", []) or []) or "none"
    return f"连续低分市场：{repeated}；分数下滑市场：{declining}"


def _action_template(action_code, manifest):
    if action_code == "reduce_weekly_action_backlog":
        action = _backlog_reduction_action(manifest)
        if action:
            return {
                "title": action["title"],
                "category": action["category"],
                "source": action["source"],
                "recommended_check": action["recommended_check"],
            }
    history = _delivery_history(manifest)
    manual_review_count = _manual_review_count(manifest, history)
    health_text = _health_reason_text(history)
    missing_signal_text = _missing_conclusion_signal_text(history)
    missing_signal_fix_text = _missing_conclusion_signal_fix_text(history)
    delivery_health_source = "; ".join(
        part for part in [health_text, missing_signal_text, missing_signal_fix_text] if part
    )
    delivery_signal_check = (
        f"；关键结论信号：{missing_signal_text}" if missing_signal_text else ""
    )
    delivery_signal_fix_check = (
        f"；修复指向：{missing_signal_fix_text}" if missing_signal_fix_text else ""
    )
    forecast_performance = manifest.get("forecast_performance", {})
    if not isinstance(forecast_performance, dict):
        forecast_performance = {}
    data_health_review = manifest.get("data_health_review", {})
    if not isinstance(data_health_review, dict):
        data_health_review = {}
    templates = {
        "review_manual_queue": {
            "title": "检查本周人工复核队列",
            "category": "manual_review",
            "source": f"manual_review_queue_count:{manifest.get('manual_review_queue_count', 0)}",
            "recommended_check": _manual_review_queue_text(
                manifest,
                manifest.get("manual_review_queue_items", []),
            ),
        },
        "review_manual_review_backlog": {
            "title": "处理人工复核积压",
            "category": "delivery_health",
            "source": health_text,
            "recommended_check": f"优先处理待复核 {manual_review_count} 条，确认是否需要合并 manual_review_decisions.csv。",
        },
        "review_delivery_health_issues": {
            "title": "复查最终交付健康提示",
            "category": "delivery_health",
            "source": delivery_health_source,
            "recommended_check": (
                "检查 weekly_delivery_history 中的健康状态 "
                f"{history.get('latest_conclusion_health_status', 'unknown')} / "
                f"{history.get('latest_conclusion_health_score', 0)}"
                f"{delivery_signal_check}{delivery_signal_fix_check}，"
                "区分人工积压、流程问题和周结论关键字段缺口。"
            ),
        },
        "review_data_health": {
            "title": "复查数据健康异常",
            "category": "data_health",
            "source": f"data_health_status:{manifest.get('data_health_status', 'unknown')}",
            "recommended_check": (
                "检查三市场 data_health_history.csv、quote_gaps.csv 和缺口分类，确认是否为可接受的数据缺口"
                f"{_data_health_refetch_gap_text(data_health_review, manifest.get('quote_retry_results'))}。"
            ),
        },
        "review_data_quality_score": {
            "title": "复核三市场数据质量评分",
            "category": "data_quality",
            "source": (
                f"data_quality_status:{manifest.get('data_quality_status', 'unknown')}; "
                f"score:{manifest.get('data_quality_score', 0)}"
            ),
            "recommended_check": (
                "检查 latest_self_analysis.md 的“数据质量评分”段落，并核对三市场 "
                f"data_health_history.csv、quote_gaps.csv 和 valuation_review_items.csv；{_data_quality_text(manifest)}。"
                "该动作只用于人工复核数据底座，不自动修改正式模型参数。"
            ),
        },
        "review_data_quality_trend": {
            "title": "复核数据质量历史趋势",
            "category": "data_quality",
            "source": f"data_quality_history_status:{manifest.get('data_quality_history_status', manifest.get('data_quality_history', {}).get('status', 'unknown'))}",
            "recommended_check": (
                "检查 data_quality_score_history.csv 和 latest_self_analysis.md 的“数据质量历史”段落；"
                f"{_data_quality_trend_text(manifest)}。"
                "若连续低分来自同一市场，优先复核该市场行情源、缺口分类和补数规则，不自动修改正式模型参数。"
            ),
        },
        "review_backtest_evidence": {
            "title": "复查回测证据质量",
            "category": "backtest",
            "source": f"backtest_status:{manifest.get('backtest_status', 'unknown')}",
            "recommended_check": "检查 latest_backtest_summary.md、成员证据等级和泄漏审计，再决定是否扩大回测样本。",
        },
        "review_candidate_findings": {
            "title": "复查候选结论质量",
            "category": "candidate_review",
            "source": f"candidate_review_status:{manifest.get('candidate_review_status', 'unknown')}",
            "recommended_check": "检查候选风险说明、目标价、建议买入价和数据质量说明是否完整。",
        },
        "review_forecast_performance": {
            "title": "复核预测表现",
            "category": "forecast_performance",
            "source": (
                f"forecast_performance_status:{manifest.get('forecast_performance_status', 'unknown')}; "
                f"mature:{forecast_performance.get('mature_evaluations', 0)}"
            ),
            "recommended_check": (
                "检查 forecast_evaluations.csv、performance_report.md 和预测方向阈值；"
                f"当前方向命中率 {_percent_value(forecast_performance.get('direction_hit_rate'))}，"
                f"平均超额收益 {_percent_value(forecast_performance.get('average_excess_return'))}。"
                "仅生成影子分析或人工复核建议，不自动修改正式模型参数。"
            ),
        },
        "continue_sample_accumulation": {
            "title": "继续积累模型跟踪样本",
            "category": "model_tracking",
            "source": (
                f"model_audit_status:{manifest.get('model_audit_status', 'unknown')}; "
                f"forecast_mature_evaluations:{_int_value(forecast_performance.get('mature_evaluations'), 0)}; "
                f"forecast_one_week_mature:{_int_value(forecast_performance.get('one_week_mature'), 0)}; "
                f"forecast_one_month_mature:{_int_value(forecast_performance.get('one_month_mature'), 0)}; "
                f"forecast_next_one_week_evaluation_date:{forecast_performance.get('next_one_week_evaluation_date', 'unknown')}; "
                f"forecast_next_one_week_evaluation_count:{_int_value(forecast_performance.get('next_one_week_evaluation_count'), 0)}; "
                f"forecast_next_one_month_evaluation_date:{forecast_performance.get('next_one_month_evaluation_date', 'unknown')}; "
                f"forecast_next_one_month_evaluation_count:{_int_value(forecast_performance.get('next_one_month_evaluation_count'), 0)}; "
                "forecast_formal_model_change_allowed:false"
            ),
            "recommended_check": (
                f"当前模型审计为 {manifest.get('model_audit_status', 'unknown')}"
                f"{_forecast_maturity_schedule_text(forecast_performance)}"
                "；继续保留跟踪，不自动升级正式参数。"
            ),
        },
        "continue_monitoring": {
            "title": "继续周度监控",
            "category": "monitoring",
            "source": f"automation_status:{manifest.get('automation_status', 'unknown')}",
            "recommended_check": "本周未识别出更高优先级处理项，继续保留周度监控。",
        },
    }
    return templates.get(
        action_code,
        {
            "title": f"复查动作码 {action_code}",
            "category": "monitoring",
            "source": f"automation_status:{manifest.get('automation_status', 'unknown')}",
            "recommended_check": "该动作码尚无专用模板，先查看 latest_self_analysis.md 中的上下文后人工判断。",
        },
    )


def _membership_import_plan_action(import_plan):
    ready_count = _int_value(import_plan.get("ready_to_import_count"), 0)
    if ready_count <= 0:
        return None

    weeks_affected = _int_value(import_plan.get("ready_to_import_weeks_affected"), 0)
    ready_items = [
        item
        for item in import_plan.get("items", []) or []
        if isinstance(item, dict) and item.get("import_status") == "ready_current_source"
    ]
    ready_items = sorted(
        ready_items,
        key=lambda item: (-_int_value(item.get("weeks_affected"), 0), str(item.get("ticker", ""))),
    )
    tickers = ", ".join(
        str(item.get("ticker", "")).strip()
        for item in ready_items[:5]
        if str(item.get("ticker", "")).strip()
    )
    ticker_text = tickers or "ready_current_source items"
    next_action = import_plan.get("next_action", "run_membership_evidence_apply_preview")

    return {
        "action_code": "run_membership_evidence_apply_preview",
        "category": "backtest",
        "title": "Run membership evidence apply preview",
        "source": (
            f"ready_to_import_count:{ready_count}; "
            f"weeks_affected:{weeks_affected}; "
            f"next_action:{next_action}"
        ),
        "recommended_check": (
            "Run scripts/run_membership_evidence_import_plan.ps1 first, then "
            "scripts/run_membership_evidence_apply_preview.ps1 for "
            f"{ticker_text}; compare latest_membership_evidence_import_plan.md and "
            "latest_membership_evidence_apply_preview.md; keep this as preview only, "
            "without modifying historical_membership.csv or formal model parameters."
        ),
    }


def _current_membership_source_action(source_status, review_status=None, inbox_status=None):
    review_status = review_status or {}
    inbox_status = inbox_status or {}
    recommended_followup = str(
        source_status.get("recommended_followup", "") or ""
    ).strip()
    if recommended_followup not in {
        "review_current_membership_source_status",
        "provide_official_constituents_csv",
    }:
        return None
    missing_count = _int_value(source_status.get("missing_count"), 0)
    intake_missing_count = _int_value(source_status.get("intake_missing_count"), 0)
    missing_queue_count = len(source_status.get("missing_ticker_review_queue", []) or [])
    if missing_count <= 0 and intake_missing_count <= 0:
        return None

    missing_tickers = [
        str(ticker).strip()
        for ticker in source_status.get("missing_tickers", []) or []
        if str(ticker).strip()
    ]
    intake_missing_tickers = [
        str(ticker).strip()
        for ticker in source_status.get("intake_missing_tickers", []) or []
        if str(ticker).strip()
    ]
    ticker_text = ", ".join((missing_tickers or intake_missing_tickers)[:10]) or "missing tickers"
    review_queue_file = (
        str(source_status.get("missing_ticker_review_queue_file", "") or "").strip()
        or "outputs/automation/sp500_current_membership_source_review_queue.csv"
    )
    review_status_file = "outputs/automation/latest_sp500_current_membership_source_review_status.json"
    review_status_value = review_status.get("status", "missing")
    review_open_count = _int_value(review_status.get("open_count"), 0)
    review_resolved_count = _int_value(review_status.get("resolved_count"), 0)
    decisions_template_file = str(
        review_status.get(
            "decisions_template_file",
            "outputs/automation/sp500_current_membership_source_review_decisions_template.csv",
        )
        or ""
    ).strip()
    decisions_template_status = str(
        review_status.get("decisions_template_status", "unknown") or "unknown"
    ).strip()
    decisions_template_matched = _int_value(
        review_status.get("decisions_template_matched_open_count"), 0
    )
    decisions_template_missing_open_count = len(
        review_status.get("decisions_template_missing_open_tickers", []) or []
    )
    source_file_required_columns = [
        str(column).strip()
        for column in source_status.get("source_file_required_columns", []) or []
        if str(column).strip()
    ]
    source_file_required_text = ", ".join(source_file_required_columns) or "none"
    source_file_accepted_ticker_columns = [
        str(column).strip()
        for column in source_status.get("source_file_accepted_ticker_columns", []) or []
        if str(column).strip()
    ] or DEFAULT_SOURCE_FILE_ACCEPTED_TICKER_COLUMNS
    source_file_accepted_ticker_columns_text = ", ".join(source_file_accepted_ticker_columns)
    source_file_next_command = str(
        source_status.get("source_file_inbox_next_command")
        or source_status.get("source_file_next_command", "")
        or ""
    ).strip()
    source_file_dry_run_command = str(
        source_status.get("source_file_inbox_dry_run_command")
        or source_status.get("source_file_dry_run_command", "")
        or ""
    ).strip()
    source_file_request_file = str(
        source_status.get("source_file_request_file", "") or ""
    ).strip()
    source_file_inbox = str(source_status.get("source_file_inbox", "") or "").strip()
    source_file_inbox_default = (
        source_file_inbox or "inputs/sp500_current_membership/official_constituents.csv"
    )
    source_file_next_command_default = (
        "run_sp500_current_membership_sources.ps1 "
        f"-SourceFileInbox {source_file_inbox_default}"
    )
    source_file_dry_run_command_default = (
        "run_sp500_current_membership_sources.ps1 "
        f"-DryRun -SourceFileInbox {source_file_inbox_default}"
    )
    source_file_inbox_exists_value = source_status.get("source_file_inbox_exists")
    if source_file_inbox_exists_value is None:
        source_file_inbox_exists = "unknown"
    else:
        source_file_inbox_exists = str(bool(source_file_inbox_exists_value)).lower()
    source_file_validation_status = str(
        source_status.get("source_file_validation_status", "unknown") or "unknown"
    ).strip()
    source_file_inbox_status = str(inbox_status.get("status", "missing") or "missing").strip()
    source_file_inbox_next_action = str(
        inbox_status.get("next_action", "missing") or "missing"
    ).strip()
    source_file_inbox_validation_status = str(
        inbox_status.get("source_file_validation_status", "unknown") or "unknown"
    ).strip()
    source_file_inbox_parsed_count = _int_value(
        inbox_status.get("parsed_official_ticker_count"), 0
    )
    source_file_inbox_intake_missing_count = _int_value(
        inbox_status.get("intake_missing_count"), 0
    )
    source_file_inbox_available_columns = [
        str(column).strip()
        for column in inbox_status.get("source_file_available_columns", []) or []
        if str(column).strip()
    ]
    source_file_inbox_available_columns_text = ", ".join(source_file_inbox_available_columns) or "none"
    source_file_rejection_reason = str(
        inbox_status.get("source_file_rejection_reason", "") or "none"
    ).strip()
    source_file_inbox_external_input_required = str(
        bool(inbox_status.get("external_input_required", False))
    ).lower()
    source_file_inbox_blocking_reason = str(
        inbox_status.get("blocking_reason", "") or "none"
    ).strip()
    source_file_inbox_blocking_input = str(
        inbox_status.get("blocking_input", "") or "none"
    ).strip()
    source_file_inbox_size_bytes = _int_value(
        inbox_status.get("source_file_inbox_size_bytes"), 0
    )
    source_file_inbox_sha256 = str(
        inbox_status.get("source_file_inbox_sha256", "") or "none"
    ).strip()
    source_file_inbox_modified_at = str(
        inbox_status.get("source_file_inbox_modified_at", "") or "none"
    ).strip()
    fetch_error_type = str(source_status.get("fetch_error_type", "unknown") or "unknown").strip()
    fetch_retryable_value = source_status.get("fetch_retryable_without_environment_change")
    if fetch_retryable_value is None:
        fetch_retryable_without_environment_change = "unknown"
    else:
        fetch_retryable_without_environment_change = str(bool(fetch_retryable_value)).lower()
    fetch_error_next_action = str(
        source_status.get("fetch_error_next_action", "unknown") or "unknown"
    ).strip()
    source_file_acceptance_criteria = [
        str(item).strip()
        for item in source_status.get("source_file_acceptance_criteria", []) or []
        if str(item).strip()
    ]
    source_file_criteria_text = ", ".join(source_file_acceptance_criteria) or "none"
    review_decision_status = str(
        review_status.get("review_decision_status", "unknown") or "unknown"
    ).strip()
    manual_decision_next_step = str(
        review_status.get("manual_decision_next_step", "unknown") or "unknown"
    ).strip()
    decision_pending_tickers = [
        str(ticker).strip()
        for ticker in review_status.get("decision_pending_tickers", []) or []
        if str(ticker).strip()
    ]
    decision_pending_ticker_text = ", ".join(decision_pending_tickers[:10]) or "none"
    source_file_action_prefix = (
        f"source_file_request_file:{source_file_request_file or 'outputs/automation/sp500_current_membership_source_file_request.md'}; "
        f"source_file_inbox:{source_file_inbox_default}; "
        f"accepted_ticker_columns:{source_file_accepted_ticker_columns_text}; "
        f"acceptance_criteria:{source_file_criteria_text}; "
        f"inbox_status={source_file_inbox_status}; "
        "inbox_status_file:outputs/automation/latest_sp500_current_membership_source_inbox_status.json; "
        f"inbox_next_action={source_file_inbox_next_action}; "
        f"parsed_official_ticker_count={source_file_inbox_parsed_count}; "
        f"inbox_intake_missing_count={source_file_inbox_intake_missing_count}; "
        f"inbox_available_columns={source_file_inbox_available_columns_text}; "
        f"source_file_rejection_reason={source_file_rejection_reason}; "
        f"inbox_external_input_required={source_file_inbox_external_input_required}; "
        f"inbox_blocking_reason={source_file_inbox_blocking_reason}; "
        f"inbox_blocking_input={source_file_inbox_blocking_input}; "
        f"inbox_size_bytes={source_file_inbox_size_bytes}; "
        f"inbox_sha256={source_file_inbox_sha256}; "
        f"inbox_modified_at={source_file_inbox_modified_at}; "
        f"fetch_error_type={fetch_error_type}; "
        f"fetch_retryable_without_environment_change={fetch_retryable_without_environment_change}; "
        f"fetch_error_next_action={fetch_error_next_action}; "
        f"dry_run_command:{source_file_dry_run_command or source_file_dry_run_command_default}; "
        f"import_command:{source_file_next_command or source_file_next_command_default}; "
    )
    ticker_text = f"{ticker_text}; {source_file_action_prefix}"
    ticker_text = (
        f"{ticker_text}; {review_status_file}；"
        f"状态报告 open={review_open_count}, resolved={review_resolved_count}；"
        f"{decisions_template_file}；"
        f"决策模板 status={decisions_template_status}, "
        f"matched_open={decisions_template_matched}, "
        f"missing_open={decisions_template_missing_open_count}；"
        f"手工决策下一步={manual_decision_next_step}；"
        f"待决策 ticker={decision_pending_ticker_text}"
    )

    return {
        "action_code": (
            "provide_official_constituents_csv"
            if recommended_followup == "provide_official_constituents_csv"
            else "review_current_membership_source_status"
        ),
        "category": "backtest",
        "title": "核对当前 S&P 500 成分来源缺口",
        "source": (
            f"status:{source_status.get('status', 'unknown')}; "
            f"matched_count:{_int_value(source_status.get('matched_count'), 0)}; "
            f"missing_count:{missing_count}; "
            f"missing_ticker_review_queue_count:{missing_queue_count}; "
            f"recommended_followup:{recommended_followup}; "
            f"source_file_required_columns:{source_file_required_text}; "
            f"source_file_accepted_ticker_columns:{source_file_accepted_ticker_columns_text}; "
            f"source_file_acceptance_criteria:{source_file_criteria_text}; "
            f"source_file_request_file:{source_file_request_file or 'missing'}; "
            f"source_file_inbox:{source_file_inbox or 'missing'}; "
            f"source_file_inbox_exists:{source_file_inbox_exists}; "
            f"source_file_validation_status:{source_file_validation_status}; "
            f"source_file_inbox_status:{source_file_inbox_status}; "
            f"source_file_inbox_next_action:{source_file_inbox_next_action}; "
            f"source_file_inbox_validation_status:{source_file_inbox_validation_status}; "
            f"source_file_inbox_parsed_official_ticker_count:{source_file_inbox_parsed_count}; "
            f"source_file_inbox_intake_missing_count:{source_file_inbox_intake_missing_count}; "
            f"source_file_inbox_available_columns:{source_file_inbox_available_columns_text}; "
            f"source_file_rejection_reason:{source_file_rejection_reason}; "
            f"source_file_inbox_external_input_required:{source_file_inbox_external_input_required}; "
            f"source_file_inbox_blocking_reason:{source_file_inbox_blocking_reason}; "
            f"source_file_inbox_blocking_input:{source_file_inbox_blocking_input}; "
            f"source_file_inbox_size_bytes:{source_file_inbox_size_bytes}; "
            f"source_file_inbox_sha256:{source_file_inbox_sha256}; "
            f"source_file_inbox_modified_at:{source_file_inbox_modified_at}; "
            f"fetch_error_type:{fetch_error_type}; "
            f"fetch_retryable_without_environment_change:{fetch_retryable_without_environment_change}; "
            f"fetch_error_next_action:{fetch_error_next_action}; "
            f"review_status:{review_status_value}; "
            f"review_open_count:{review_open_count}; "
            f"review_resolved_count:{review_resolved_count}; "
            f"review_decision_status:{review_decision_status}; "
            f"manual_decision_next_step:{manual_decision_next_step}; "
            f"decision_pending_tickers:{decision_pending_ticker_text}; "
            f"decisions_template_status:{decisions_template_status}; "
            f"decisions_template_matched_open_count:{decisions_template_matched}; "
            f"decisions_template_missing_open_count:{decisions_template_missing_open_count}; "
            f"intake_coverage_status:{source_status.get('intake_coverage_status', 'unknown')}; "
            f"intake_missing_count:{intake_missing_count}; "
            f"next_action:{source_status.get('next_action', 'unknown')}"
        ),
        "recommended_check": (
            "核对 outputs/automation/latest_sp500_current_membership_sources.json、"
            f"{review_queue_file} 和 "
            "outputs/automation/sp500_current_membership_source_intake_template.csv 中的 "
            f"{ticker_text}；当前缺失复核队列 {missing_queue_count} 条；"
            f"若 recommended_followup={recommended_followup}，提供官方 S&P Global constituents CSV，"
            f"默认投递入口：{source_file_inbox_default}；"
            f"要求列：{source_file_required_text}；可接受 ticker 列：{source_file_accepted_ticker_columns_text}；验收条件：{source_file_criteria_text}；"
            f"导入命令：{source_file_next_command or source_file_next_command_default}；"
            "确认缺失 ticker 是官方导出不覆盖，还是人工来源文件仍不完整。"
            "该动作只做证据复核，不修改 historical_membership.csv 或正式模型参数。"
        ),
    }


def _backlog_reduction_action(manifest):
    trend = str(manifest.get("weekly_delivery_action_items_actual_count_trend", "") or "")
    actual_count = _int_value(manifest.get("weekly_delivery_action_items_actual_count"), 0)
    delta = _int_value(manifest.get("weekly_delivery_action_items_actual_count_delta"), 0)
    if trend != "increasing" or delta <= 0:
        return None

    return {
        "action_code": "reduce_weekly_action_backlog",
        "category": "delivery_health",
        "title": "制定人工待办压降计划",
        "source": f"actual_count:{actual_count}; delta:{delta}; trend:{trend}",
        "recommended_check": (
            "按分类复核 outputs/automation/latest_weekly_action_items.json；"
            "通过 manual_review_decisions.csv 关闭已处理的人工复核项，"
            "合并重复的交付健康提示，并把该动作限定为运营清理，"
            "不修改正式模型参数。"
        ),
    }


def _forecast_prediction_unavailable_action(forecast_performance):
    if not forecast_performance:
        return None
    reasons = forecast_performance.get("maturity_gap_reasons", {}) or {}
    if not isinstance(reasons, dict):
        reasons = {}
    prediction_unavailable = _int_value(reasons.get("prediction_unavailable"), 0)
    pending_maturity = _int_value(reasons.get("pending_maturity"), 0)
    mature_evaluations = _int_value(forecast_performance.get("mature_evaluations"), 0)
    latest_prediction_unavailable_raw = forecast_performance.get("latest_prediction_unavailable_count")
    latest_prediction_unavailable = (
        prediction_unavailable
        if latest_prediction_unavailable_raw is None
        else _int_value(latest_prediction_unavailable_raw, 0)
    )
    legacy_prediction_unavailable = _int_value(
        forecast_performance.get("legacy_prediction_unavailable_count"),
        0,
    )
    latest_short_missing = _int_value(
        forecast_performance.get("latest_short_signal_missing_count"),
        0,
    )
    if (
        latest_prediction_unavailable <= 0
        or pending_maturity > 0
        or mature_evaluations >= 30
        or latest_short_missing > 0
    ):
        return None
    return {
        "action_code": "review_prediction_unavailable_signals",
        "category": "model_tracking",
        "title": "复核不可评估预测信号",
        "source": (
            f"prediction_unavailable:{prediction_unavailable}; "
            f"latest_prediction_unavailable:{latest_prediction_unavailable}; "
            f"legacy_prediction_unavailable:{legacy_prediction_unavailable}; "
            f"pending_maturity:{pending_maturity}; "
            f"mature_evaluations:{mature_evaluations}"
        ),
        "recommended_check": (
            "Check outputs/automation/latest_forecast_performance_review.json and each market "
            "forecast_evaluations.csv; confirm whether missing_prediction_signal comes from "
            "legacy rows or a current forecast write path gap. Keep this review in tracking only; "
            "do not change formal model parameters."
        ),
    }


def _candidate_review_issue_is_actionable(candidate_findings):
    if not isinstance(candidate_findings, dict) or not candidate_findings:
        return True
    if _int_value(candidate_findings.get("missing_field_count"), 0) > 0:
        return True
    if _int_value(candidate_findings.get("risk_missing_count"), 0) > 0:
        return True
    if _int_value(candidate_findings.get("risk_unclassified_count"), 0) > 0:
        return True
    if _int_value(candidate_findings.get("risk_action_unqueued_count"), 0) > 0:
        return True
    return _int_value(candidate_findings.get("risk_action_required_count"), 0) > 20


def _data_health_issue_is_actionable(data_health):
    if not isinstance(data_health, dict) or not data_health:
        return True
    status = str(data_health.get("status", "") or "").strip()
    if status not in {"ready", "acceptable_with_monitoring"}:
        return True
    if _int_value(data_health.get("blocked_candidate_count"), 0) > 0:
        return True
    if _int_value(data_health.get("refetch_gap_action_required_count"), 0) > 0:
        return True
    for market in data_health.get("markets", []) or []:
        if not isinstance(market, dict):
            continue
        if _int_value(market.get("blocked_candidate_count"), 0) > 0:
            return True
        if _int_value(market.get("refetch_gap_action_required_count"), 0) > 0:
            return True
    return False


def _current_source_requires_official_csv(source_status):
    if not isinstance(source_status, dict) or not source_status:
        return False
    return (
        source_status.get("recommended_followup") == "provide_official_constituents_csv"
        or source_status.get("fetch_error_next_action") == "provide_official_constituents_csv"
    )


def _backtest_evidence_issue_is_actionable(backtest_evidence, current_source_status):
    if not isinstance(backtest_evidence, dict) or not backtest_evidence:
        return True
    if _int_value(backtest_evidence.get("weeks_failed"), 0) > 0:
        return True
    if not _current_source_requires_official_csv(current_source_status):
        return True
    queue = [
        item
        for item in backtest_evidence.get("membership_evidence_action_queue", []) or []
        if isinstance(item, dict)
    ]
    if not queue:
        return True
    official_source_actions = {
        "supplement_official_membership_source",
        "supplement_official_spglobal_source",
    }
    for item in queue:
        values = {
            str(item.get("action_type", "")).strip(),
            str(item.get("recommended_action", "")).strip(),
            str(item.get("recommended_source", "")).strip(),
        }
        if not values & official_source_actions and (
            "official_spglobal_membership_evidence" not in values
        ):
            return True
    return False


def _backlog_reduction_plan(items):
    grouped = {}
    for item in items:
        if item.get("status") != "open":
            continue
        category = item.get("category", "unknown") or "unknown"
        entry = grouped.setdefault(
            category,
            {
                "category": category,
                "count": 0,
                "actions": [],
                "first_priority": _int_value(item.get("priority"), 9999),
                "close_context": [],
            },
        )
        entry["count"] += 1
        entry["actions"].append(item.get("action_code", ""))
        close_context = _backlog_reduction_close_context(item)
        if close_context:
            entry["close_context"].append(close_context)
        entry["first_priority"] = min(entry["first_priority"], _int_value(item.get("priority"), 9999))
    plan = sorted(
        grouped.values(),
        key=lambda entry: (-entry["count"], entry["first_priority"], entry["category"]),
    )
    for entry in plan:
        actions = [action for action in entry.get("actions", []) if action]
        entry["first_action"] = actions[0] if actions else ""
        entry["target_count_after_close"] = 0
        close_condition = _backlog_reduction_close_condition(entry["category"])
        close_context = "; ".join(
            context for context in entry.get("close_context", []) if context
        )
        if close_context:
            close_condition = f"{close_condition} {close_context}"
        entry["close_condition"] = close_condition
        entry.pop("first_priority", None)
        entry.pop("close_context", None)
    return plan


def _backlog_reduction_close_context(item):
    if item.get("action_code") != "provide_official_constituents_csv":
        return ""
    text = f"{item.get('source', '')}; {item.get('recommended_check', '')}"
    inbox = _extract_semicolon_field(
        text, "source_file_inbox_blocking_input"
    ) or _extract_semicolon_field(text, "source_file_inbox")
    external_required = _extract_semicolon_field(
        text, "source_file_inbox_external_input_required"
    ) or _extract_equals_field(text, "inbox_external_input_required")
    parts = []
    if inbox:
        parts.append(f"blocking_input={inbox}")
    if external_required:
        parts.append(f"external_input_required={external_required}")
    return "; ".join(parts)


def _extract_semicolon_field(text, key):
    marker = f"{key}:"
    for part in str(text or "").split(";"):
        stripped = part.strip()
        if stripped.startswith(marker):
            return stripped[len(marker):].strip()
    return ""


def _extract_equals_field(text, key):
    marker = f"{key}="
    for part in str(text or "").split(";"):
        stripped = part.strip()
        if stripped.startswith(marker):
            return stripped[len(marker):].strip()
    return ""


def _backlog_reduction_close_condition(category):
    conditions = {
        "delivery_health": (
            "Close resolved manual_review_decisions.csv items and merge duplicate delivery health prompts."
        ),
        "data_quality": "Classify or route each data quality issue to a concrete market data follow-up.",
        "backtest": "Attach verified source evidence or keep the item open with an explicit source-file request.",
        "manual_review": "Resolve or explicitly defer each manual review queue row.",
        "data_health": "Confirm whether each data health gap is acceptable, refetchable, or needs manual review.",
        "model_tracking": "Keep sample accumulation open until mature forecast evaluations are available.",
        "candidate_review": "Confirm each candidate finding has risk, valuation, and data-quality rationale.",
    }
    return conditions.get(category, "Resolve, defer, or route every open action in this category.")


def _latest_as_of_date(*payloads):
    dates = [
        str(payload.get("as_of_date", "") or "").strip()
        for payload in payloads
        if isinstance(payload, dict) and str(payload.get("as_of_date", "") or "").strip()
    ]
    return max(dates) if dates else "unknown"


def build_weekly_action_items(
    manifest,
    membership_import_plan=None,
    current_membership_sources=None,
    current_membership_source_review_status=None,
    current_membership_source_inbox_status=None,
    forecast_performance=None,
    manual_review_queue=None,
    data_health_review=None,
    candidate_findings_review=None,
    backtest_evidence_review=None,
    quote_retry_results=None,
):
    manifest_path = Path(manifest)
    source = load_manifest(manifest_path)
    import_plan = load_optional_json(membership_import_plan)
    current_source_status = load_optional_json(current_membership_sources)
    current_source_review_status = load_optional_json(current_membership_source_review_status)
    current_source_inbox_status = load_optional_json(current_membership_source_inbox_status)
    forecast_performance_review = load_optional_json(forecast_performance)
    manual_review_rows = load_optional_csv_rows(manual_review_queue)
    data_health_payload = load_optional_json(data_health_review)
    candidate_findings_payload = load_optional_json(candidate_findings_review)
    backtest_evidence_payload = load_optional_json(backtest_evidence_review)
    quote_retry_payload = load_optional_json(quote_retry_results)
    if manual_review_rows:
        source["manual_review_queue_items"] = manual_review_rows
    if data_health_payload:
        source["data_health_review"] = data_health_payload
    if candidate_findings_payload:
        source["candidate_findings_review"] = candidate_findings_payload
    if backtest_evidence_payload:
        source["backtest_evidence_review"] = backtest_evidence_payload
    if quote_retry_payload:
        source["quote_retry_results"] = quote_retry_payload
    if forecast_performance_review:
        manifest_forecast = source.get("forecast_performance", {})
        if not isinstance(manifest_forecast, dict):
            manifest_forecast = {}
        source["forecast_performance"] = {
            **manifest_forecast,
            **forecast_performance_review,
        }
    actions = list(source.get("automation_priority_actions", []) or [])
    if not actions:
        actions = [source.get("automation_recommended_action", "") or "continue_monitoring"]

    items = []
    for index, action_code in enumerate(actions, start=1):
        if action_code == "review_manual_review_backlog":
            history = _delivery_history(source)
            if _manual_review_count(source, history) <= 0:
                continue
        if action_code == "review_delivery_health_issues":
            history = _delivery_history(source)
            if not _delivery_health_issue_is_actionable(history):
                continue
        if action_code == "review_candidate_findings":
            if not _candidate_review_issue_is_actionable(
                source.get("candidate_findings_review", {})
            ):
                continue
        if action_code == "review_data_health":
            if not _data_health_issue_is_actionable(source.get("data_health_review", {})):
                continue
        if action_code in {"review_data_quality_score", "review_data_quality_trend"}:
            if not _data_health_issue_is_actionable(source.get("data_health_review", {})):
                continue
        if action_code == "review_backtest_evidence":
            if not _backtest_evidence_issue_is_actionable(
                source.get("backtest_evidence_review", {}),
                current_source_status,
            ):
                continue
        template = _action_template(action_code, source)
        items.append(
            {
                "priority": len(items) + 1,
                "status": "open",
                "action_code": action_code,
                "category": template["category"],
                "title": template["title"],
                "source": template["source"],
                "recommended_check": template["recommended_check"],
            }
        )

    membership_action = _membership_import_plan_action(import_plan)
    if membership_action and not any(
        item.get("action_code") == membership_action["action_code"] for item in items
    ):
        membership_action = dict(membership_action)
        membership_action["priority"] = len(items) + 1
        membership_action["status"] = "open"
        items.append(membership_action)

    current_source_action = _current_membership_source_action(
        current_source_status,
        current_source_review_status,
        current_source_inbox_status,
    )
    if current_source_action and not any(
        item.get("action_code") == current_source_action["action_code"] for item in items
    ):
        current_source_action = dict(current_source_action)
        current_source_action["priority"] = len(items) + 1
        current_source_action["status"] = "open"
        items.append(current_source_action)

    forecast_gap_action = _forecast_prediction_unavailable_action(forecast_performance_review)
    if forecast_gap_action and not any(
        item.get("action_code") == forecast_gap_action["action_code"] for item in items
    ):
        forecast_gap_action = dict(forecast_gap_action)
        forecast_gap_action["priority"] = len(items) + 1
        forecast_gap_action["status"] = "open"
        items.append(forecast_gap_action)

    backlog_reduction_action = _backlog_reduction_action(source)
    if backlog_reduction_action and not any(
        item.get("action_code") == backlog_reduction_action["action_code"] for item in items
    ):
        backlog_reduction_action = dict(backlog_reduction_action)
        backlog_reduction_action["priority"] = len(items) + 1
        backlog_reduction_action["status"] = "open"
        items.append(backlog_reduction_action)

    return {
        "action_items_schema": ACTION_ITEMS_SCHEMA,
        "action_items_version": ACTION_ITEMS_VERSION,
        "as_of_date": _latest_as_of_date(
            source,
            import_plan,
            current_source_status,
            current_source_review_status,
            current_source_inbox_status,
            forecast_performance_review,
            data_health_payload,
            candidate_findings_payload,
            backtest_evidence_payload,
            quote_retry_payload,
        ),
        "source_manifest": str(manifest_path),
        "automation_status": source.get("automation_status", "unknown"),
        "item_count": len(items),
        "backlog_reduction_plan": _backlog_reduction_plan(items),
        "items": items,
        "boundary": "只读取自我分析 manifest，不抓取行情，不重新评分，不修改正式模型参数。",
    }


def render_weekly_action_items(payload):
    lines = [
        "# 每周人工处理清单",
        "",
        f"- 日期：{payload.get('as_of_date', 'unknown')}",
        f"- 自动化状态：{payload.get('automation_status', 'unknown')}",
        f"- 事项数量：{payload.get('item_count', 0)}",
        f"- 来源：{payload.get('source_manifest', '')}",
        "",
        "## 处理事项",
    ]
    action_items_heading = lines.pop()
    plan = payload.get("backlog_reduction_plan", []) or []
    if plan:
        lines.extend(
            [
                "",
                "## 待办压降分流",
                "",
                "| category | count | first_action | target_count_after_close | actions | close_condition |",
                "|---|---:|---|---:|---|---|",
            ]
        )
        for entry in plan:
            lines.append(
                f"| {entry.get('category', 'unknown')} | {entry.get('count', 0)} | "
                f"{entry.get('first_action', '')} | "
                f"{entry.get('target_count_after_close', 0)} | "
                f"{', '.join(entry.get('actions', []) or [])} | "
                f"{entry.get('close_condition', '')} |"
            )
    lines.extend(["", action_items_heading])
    items = payload.get("items", []) or []
    if not items:
        lines.append("- 暂无待处理事项。")
    for item in items:
        lines.extend(
            [
                f"{item.get('priority', 0)}. {item.get('title', '')}",
                f"   - action_code：{item.get('action_code', '')}",
                f"   - category：{item.get('category', '')}",
                f"   - status：{item.get('status', '')}",
                f"   - source：{item.get('source', '')}",
                f"   - recommended_check：{item.get('recommended_check', '')}",
            ]
        )
    lines.extend(
        [
            "",
            "## 边界",
            f"- {payload.get('boundary', '')}",
            "- 该清单用于每周人工复核排序，不代表自动买入、卖出或模型参数调整。",
        ]
    )
    return "\n".join(lines) + "\n"


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
    parser = argparse.ArgumentParser(description="Build weekly manual action items from self-analysis manifest.")
    parser.add_argument("--manifest", default="outputs/automation/latest_self_analysis_manifest.json")
    parser.add_argument("--output", default="outputs/automation/latest_weekly_action_items.json")
    parser.add_argument("--report", default="outputs/automation/latest_weekly_action_items.md")
    parser.add_argument("--membership-import-plan", default=DEFAULT_MEMBERSHIP_IMPORT_PLAN)
    parser.add_argument("--current-membership-sources", default=DEFAULT_CURRENT_MEMBERSHIP_SOURCES)
    parser.add_argument(
        "--current-membership-source-review-status",
        default=DEFAULT_CURRENT_MEMBERSHIP_SOURCE_REVIEW_STATUS,
    )
    parser.add_argument(
        "--current-membership-source-inbox-status",
        default=DEFAULT_CURRENT_MEMBERSHIP_SOURCE_INBOX_STATUS,
    )
    parser.add_argument("--forecast-performance", default=DEFAULT_FORECAST_PERFORMANCE)
    parser.add_argument("--manual-review-queue", default=DEFAULT_MANUAL_REVIEW_QUEUE)
    parser.add_argument("--data-health-review", default=DEFAULT_DATA_HEALTH_REVIEW)
    parser.add_argument("--candidate-findings-review", default=DEFAULT_CANDIDATE_FINDINGS_REVIEW)
    parser.add_argument("--backtest-evidence-review", default=DEFAULT_BACKTEST_EVIDENCE_REVIEW)
    parser.add_argument("--quote-retry-results", default=DEFAULT_HK_QUOTE_RETRY_RESULTS)
    args = parser.parse_args()

    payload = build_weekly_action_items(
        args.manifest,
        membership_import_plan=args.membership_import_plan,
        current_membership_sources=args.current_membership_sources,
        current_membership_source_review_status=args.current_membership_source_review_status,
        current_membership_source_inbox_status=args.current_membership_source_inbox_status,
        forecast_performance=args.forecast_performance,
        manual_review_queue=args.manual_review_queue,
        data_health_review=args.data_health_review,
        candidate_findings_review=args.candidate_findings_review,
        backtest_evidence_review=args.backtest_evidence_review,
        quote_retry_results=args.quote_retry_results,
    )
    report = render_weekly_action_items(payload)
    if args.output:
        write_json(payload, args.output)
    if args.report:
        write_text(report, args.report)
    print(report, end="")


if __name__ == "__main__":
    main()
