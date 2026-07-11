import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path


MARKETS = (
    {"market": "US", "label": "美股", "dir": "us_universe"},
    {"market": "CN", "label": "A股", "dir": "cn_universe"},
    {"market": "HK", "label": "港股", "dir": "hk_universe"},
)

REQUIRED_MARKET_FILES = (
    "latest_run_summary.md",
    "candidate_pool.csv",
    "valuation_targets.csv",
    "valuation_report.md",
    "latest_investment_summary.md",
)

AUTOMATION_FILES = {
    "automation_check": "latest_automation_check.json",
    "weekly_ops_check": "latest_weekly_ops_check.json",
    "weekly_ops_history": "latest_weekly_ops_history_summary.json",
    "weekly_delivery_history": "latest_weekly_delivery_history_summary.json",
}
NON_BLOCKING_AUTOMATION_STATUS_KEYS = {"weekly_delivery_history"}
LIGHT_REVIEW_AUTOMATION_STATUS_KEYS = {
    "data_quality_history",
    "forecast_performance",
    "candidate_findings_review",
    "candidate_risk_resolution_review",
}

DEFAULT_MARKDOWN_OUTPUT = "outputs/automation/latest_weekly_conclusion.md"
DEFAULT_JSON_OUTPUT = "outputs/automation/latest_weekly_conclusion.json"
MANUAL_REVIEW_QUEUE_PATH = "outputs/automation/latest_manual_review_queue.csv"
WEEKLY_ACTION_ITEMS_PATH = "outputs/automation/latest_weekly_action_items.json"
MANUAL_REVIEW_DECISIONS_PATH = "outputs/automation/manual_review_decisions.csv"
MANUAL_REVIEW_DECISIONS_TEMPLATE_OUTPUT = "outputs/automation/manual_review_decisions_template.csv"
MANUAL_REVIEW_MERGE_SUMMARY_PATH = "outputs/automation/latest_manual_review_decision_merge.json"
CANDIDATE_FINDINGS_REVIEW_PATH = "outputs/automation/latest_candidate_findings_review.json"
CANDIDATE_RISK_RESOLUTION_REVIEW_PATH = (
    "outputs/automation/latest_candidate_risk_resolution_review.json"
)
ONE_WEEK_FORECAST_SHADOW_REVIEW_PATH = "outputs/automation/latest_one_week_forecast_shadow_review.json"
ONE_WEEK_FORECAST_SHADOW_DISPOSITION_PATH = (
    "outputs/automation/latest_one_week_forecast_shadow_disposition.json"
)
FIRST_ONE_MONTH_FORECAST_EVALUATION_PATH = (
    "outputs/automation/latest_first_one_month_forecast_evaluation_review.json"
)
BACKTEST_EVIDENCE_REVIEW_PATH = "outputs/automation/latest_backtest_evidence_review.json"
DATA_HEALTH_REVIEW_PATH = "outputs/automation/latest_data_health_review.json"

ACTION_DETAILS = {
    "review_manual_queue": {
        "label": "复核人工队列",
        "description": "查看本周人工复核队列，优先处理估值口径、风险提示和候选结论缺口。",
    },
    "review_data_health": {
        "label": "复核数据健康",
        "description": "检查行情、财务字段、数据质量问题和人工覆盖项是否影响候选可信度。",
    },
    "review_data_quality_score": {
        "label": "复核三市场数据质量评分",
        "description": "检查三市场数据质量评分、最低分市场和评分原因，确认本周数据底座是否足以支撑候选结论。",
    },
    "review_data_quality_trend": {
        "label": "复核数据质量历史趋势",
        "description": "检查 data_quality_score_history.csv 中连续低分或评分下滑的市场，优先复核行情源、缺口分类和补数规则。",
    },
    "review_backtest_evidence": {
        "label": "复核回测证据",
        "description": "确认严格时点回测证据等级、弱证据周次和泄漏审计结果。",
    },
    "review_candidate_findings": {
        "label": "复核候选结论",
        "description": "检查候选公司的风险说明、建议买入价、目标价和跟踪状态是否完整。",
    },
    "review_manual_review_backlog": {
        "label": "处理人工复核积压",
        "description": "优先处理未完成的人工复核项，确认是否需要合并 manual_review_decisions.csv 并减少重复待办。",
    },
    "continue_sample_accumulation": {
        "label": "继续积累样本",
        "description": "维持正式模型不变，等待更多成熟跟踪样本后再评估参数优化。",
    },
    "review_forecast_performance": {
        "label": "复核预测表现",
        "description": "检查 forecast_evaluations.csv、performance_report.md 和预测方向阈值，确认成熟样本表现是否需要进入影子参数评估。",
    },
    "continue_shadow_validation": {
        "label": "继续影子验证",
        "description": "继续累计独立周批次、受影响样本和市场覆盖，正式模型保持不变。",
    },
    "review_shadow_candidate_approval": {
        "label": "审批影子候选",
        "description": "人工复核已达门槛的影子候选，只决定是否进入后续正式回测设计。",
    },
    "repair_shadow_disposition_inputs": {
        "label": "修复影子处置输入",
        "description": "修复影子计划、验证、历史或日期契约，再重新生成候选处置。",
    },
    "review_delivery_health_issues": {
        "label": "复查最终交付健康提示",
        "description": "检查最终交付健康分、周结论和人工处理清单，区分人工积压和流程修复问题。",
    },
    "reduce_weekly_action_backlog": {
        "label": "制定人工待办压降计划",
        "description": "按分类复核 latest_weekly_action_items.json，通过 manual_review_decisions.csv 关闭已处理项，合并重复交付健康提示；该动作只用于运营清理，不修改正式模型参数。",
    },
    "monitor_next_run": {
        "label": "继续观察下次运行",
        "description": "当前未发现优先处理项，下次自动运行后继续复核输出。",
    },
    "review_inputs": {
        "label": "复核输入文件",
        "description": "先处理缺失、过期或字段异常的输入文件，再使用本周结论。",
    },
}

REVIEW_TYPE_ACTIONS = {
    "估值口径": "用盈利质量、现金流、营收增速或净资产等替代口径复核，不把负 PE 直接视为低估。",
    "风险提示": "复核趋势、估值置信度和风险说明，确认是否需要降低候选优先级或补充人工备注。",
}

CANDIDATE_ACTION_TIERS = (
    "优先研究",
    "等待回调",
    "谨慎观察",
    "暂缓研究",
    "资料不足",
)

CANDIDATE_ACTION_GUIDANCE = {
    "优先研究": "评分、预期收益和置信度较好，优先进入人工深研。",
    "等待回调": "基本面仍可跟踪，但价格或安全边际需要继续等待。",
    "谨慎观察": "趋势、置信度或风险提示偏弱，先复核风险和数据质量。",
    "暂缓研究": "预期收益为负或缺少安全边际，本周暂不优先深研。",
    "资料不足": "关键估值或收益字段不足，先补数据再判断。",
}


def build_weekly_conclusion(project_root, today=None, max_age_days=8):
    project_root = Path(project_root)
    as_of_date = today or date.today().isoformat()
    missing_inputs = []
    warnings = []
    markets = []
    candidates = []

    automation = read_automation_state(project_root, as_of_date, max_age_days, warnings, missing_inputs)
    manual_review_queue = read_manual_review_queue(project_root)
    manual_review_decisions = read_manual_review_decisions(project_root, manual_review_queue)
    manual_review_merge_summary = read_manual_review_merge_summary(project_root)
    for market_config in MARKETS:
        market_result = read_market(project_root, market_config, missing_inputs, warnings)
        markets.append(market_result["summary"])
        candidates.extend(market_result["candidates"])

    status = decide_status(markets, candidates, automation, missing_inputs, warnings)
    return build_payload(
        as_of_date,
        status,
        automation,
        markets,
        candidates,
        missing_inputs,
        warnings,
        manual_review_queue,
        manual_review_decisions,
        manual_review_merge_summary,
    )


def read_automation_state(project_root, as_of_date, max_age_days, warnings, missing_inputs):
    automation_dir = project_root / "outputs" / "automation"
    state = {}
    for key, filename in AUTOMATION_FILES.items():
        path = automation_dir / filename
        payload = read_json(path)
        if payload is None:
            missing_inputs.append(relative_path(project_root, path))
            state[key] = {"status": "missing", "path": relative_path(project_root, path)}
            continue
        state[key] = {
            "status": payload.get("status") or payload.get("latest_status") or "unknown",
            "as_of_date": payload.get("as_of_date") or payload.get("latest_as_of_date"),
            "recommended_action": payload.get("recommended_action"),
            "priority_actions": payload.get("priority_actions", []),
            "path": relative_path(project_root, path),
        }
        if key == "automation_check":
            if "data_quality_status" in payload or "data_quality_score" in payload:
                state["data_quality"] = {
                    "status": payload.get("data_quality_status", "unknown"),
                    "score": payload.get("data_quality_score"),
                    "path": relative_path(project_root, path),
                }
            if "data_quality_history_status" in payload:
                state["data_quality_history"] = {
                    "status": payload.get("data_quality_history_status", "unknown"),
                    "path": relative_path(project_root, path),
                }
            forecast_state = read_forecast_performance_state(project_root, payload, path)
            if forecast_state:
                state["forecast_performance"] = forecast_state

    weekly_action_items_path = project_root / WEEKLY_ACTION_ITEMS_PATH
    weekly_action_items = read_json(weekly_action_items_path)
    if isinstance(weekly_action_items, dict):
        state["weekly_action_items"] = {
            "status": "ready",
            "as_of_date": weekly_action_items.get("as_of_date"),
            "item_count": weekly_action_items.get("item_count", 0),
            "items": weekly_action_items.get("items", []),
            "backlog_reduction_plan": weekly_action_items.get("backlog_reduction_plan", []),
            "path": relative_path(project_root, weekly_action_items_path),
        }

    candidate_review = read_json(project_root / CANDIDATE_FINDINGS_REVIEW_PATH)
    if isinstance(candidate_review, dict):
        state["candidate_findings_review"] = normalize_candidate_findings_review(
            project_root,
            candidate_review,
            project_root / CANDIDATE_FINDINGS_REVIEW_PATH,
        )

    candidate_risk_resolution = read_json(
        project_root / CANDIDATE_RISK_RESOLUTION_REVIEW_PATH
    )
    if isinstance(candidate_risk_resolution, dict):
        state["candidate_risk_resolution_review"] = normalize_candidate_risk_resolution_review(
            project_root,
            candidate_risk_resolution,
            project_root / CANDIDATE_RISK_RESOLUTION_REVIEW_PATH,
        )

    forecast_shadow_review = read_json(project_root / ONE_WEEK_FORECAST_SHADOW_REVIEW_PATH)
    if isinstance(forecast_shadow_review, dict):
        state["one_week_forecast_shadow_review"] = normalize_forecast_shadow_review(
            project_root,
            forecast_shadow_review,
            project_root / ONE_WEEK_FORECAST_SHADOW_REVIEW_PATH,
        )

    first_one_month_evaluation = read_json(
        project_root / FIRST_ONE_MONTH_FORECAST_EVALUATION_PATH
    )
    if isinstance(first_one_month_evaluation, dict):
        state["first_one_month_forecast_evaluation"] = (
            normalize_first_one_month_forecast_evaluation(
                project_root,
                first_one_month_evaluation,
                project_root / FIRST_ONE_MONTH_FORECAST_EVALUATION_PATH,
            )
        )

    forecast_shadow_disposition = read_json(
        project_root / ONE_WEEK_FORECAST_SHADOW_DISPOSITION_PATH
    )
    if isinstance(forecast_shadow_disposition, dict):
        state["forecast_shadow_disposition"] = normalize_forecast_shadow_disposition(
            project_root,
            forecast_shadow_disposition,
            project_root / ONE_WEEK_FORECAST_SHADOW_DISPOSITION_PATH,
        )

    backtest_review = read_json(project_root / BACKTEST_EVIDENCE_REVIEW_PATH)
    if isinstance(backtest_review, dict):
        state["backtest_evidence_review"] = normalize_backtest_evidence_review(
            project_root,
            backtest_review,
            project_root / BACKTEST_EVIDENCE_REVIEW_PATH,
        )

    data_health_review = read_json(project_root / DATA_HEALTH_REVIEW_PATH)
    if isinstance(data_health_review, dict):
        state["data_health_review"] = normalize_data_health_review(
            project_root,
            data_health_review,
            project_root / DATA_HEALTH_REVIEW_PATH,
        )

    check = state.get("automation_check", {})
    check_date = parse_iso_date(check.get("as_of_date"))
    current_date = parse_iso_date(as_of_date)
    if check_date and current_date:
        if check_date > current_date:
            warnings.append("latest_automation_check.json is later than today")
        elif (current_date - check_date).days > max_age_days:
            warnings.append(f"latest_automation_check.json is older than {max_age_days} days")
    elif check.get("status") != "missing":
        warnings.append("latest_automation_check.json has invalid as_of_date")
    return state


def read_market(project_root, market_config, missing_inputs, warnings):
    market_dir = project_root / "outputs" / market_config["dir"]
    required_missing = []
    source_files = []
    for filename in REQUIRED_MARKET_FILES:
        resolved = resolve_required_market_file(project_root, market_config, market_dir, filename)
        source_files.append(relative_path(project_root, resolved["path"]))
        if not resolved["exists"]:
            missing = relative_path(project_root, resolved["path"])
            missing_inputs.append(missing)
            required_missing.append(missing)

    candidate_rows = read_csv_rows(market_dir / "candidate_pool.csv")
    target_rows = index_by_ticker(read_csv_rows(market_dir / "valuation_targets.csv"))
    risk_by_ticker = extract_risks(market_dir / "latest_investment_summary.md")

    candidates = []
    for row in candidate_rows:
        ticker = pick(row, "ticker", "symbol", "code", "股票代码", "证券代码")
        if not ticker:
            warnings.append(f"{market_config['market']} candidate row missing ticker")
            continue
        target = target_rows.get(ticker, {})
        candidates.append(
            {
                "market": market_config["market"],
                "market_label": market_config["label"],
                "ticker": ticker,
                "company": pick(row, "company", "company_name", "name", "股票名称", "证券简称"),
                "score": pick(row, "total_score", "score", "评分"),
                "target_price": pick(target, "target_price", "target", "目标价"),
                "buy_price": pick(target, "buy_price", "suggested_buy_price", "建议买入价"),
                "expected_return": pick(target, "expected_return", "expected_return_pct", "预期收益率"),
                "trend_label": pick(target, "trend_label", "trend", "趋势分类"),
                "trend_confidence": pick(target, "trend_confidence", "趋势置信度"),
                "one_week_trend_label": pick(target, "one_week_trend_label", "1周走势"),
                "one_week_trend_confidence": pick(target, "one_week_trend_confidence", "1周置信度"),
                "one_week_expected_direction": pick(target, "one_week_expected_direction", "1周方向"),
                "one_month_trend_label": pick(target, "one_month_trend_label", "1个月走势"),
                "one_month_trend_confidence": pick(target, "one_month_trend_confidence", "1个月置信度"),
                "one_month_expected_direction": pick(target, "one_month_expected_direction", "1个月方向"),
                "valuation_confidence": pick(target, "valuation_confidence", "估值置信度"),
                "reason": pick(target, "reason", "valuation_reason", "候选理由"),
                "risk_reason": risk_by_ticker.get(ticker) or risk_by_ticker.get("*", ""),
                "source_paths": {
                    "candidate_pool": relative_path(project_root, market_dir / "candidate_pool.csv"),
                    "valuation_targets": relative_path(project_root, market_dir / "valuation_targets.csv"),
                    "investment_summary": relative_path(project_root, market_dir / "latest_investment_summary.md"),
                },
            }
        )

    status = "ready" if not required_missing else "missing"
    summary = {
        "market": market_config["market"],
        "label": market_config["label"],
        "status": status,
        "candidate_count": len(candidates),
        "missing_inputs": required_missing,
        "source_dir": relative_path(project_root, market_dir),
        "source_files": source_files,
    }
    return {"summary": summary, "candidates": candidates}


def resolve_required_market_file(project_root, market_config, market_dir, filename):
    default_path = market_dir / filename
    if default_path.exists():
        return {"path": default_path, "exists": True}
    if market_config["market"] == "US" and filename == "latest_run_summary.md":
        fallback = project_root / "outputs" / "automation" / "latest_run_summary.md"
        if fallback.exists():
            return {"path": fallback, "exists": True}
    return {"path": default_path, "exists": False}


def decide_status(markets, candidates, automation, missing_inputs, warnings):
    if not candidates and automation.get("automation_check", {}).get("status") == "missing":
        return "missing"
    automation_bad = any(
        not is_acceptable_status(entry.get("status"))
        for key, entry in automation.items()
        if key not in NON_BLOCKING_AUTOMATION_STATUS_KEYS
    )
    market_bad = any(market.get("status") != "ready" for market in markets)
    candidate_bad = any(not candidate.get("ticker") for candidate in candidates)
    if missing_inputs or warnings or automation_bad or market_bad or candidate_bad:
        return "needs_attention"
    return "ready"


def summarize_health(status, automation, missing_inputs, warnings, manual_review_decisions):
    score = 100
    reasons = []
    if status != "ready":
        score -= 40
        reasons.append(f"conclusion_status:{status}")
    if missing_inputs:
        score -= 20
        reasons.append(f"missing_inputs:{len(set(missing_inputs))}")
    if warnings:
        score -= 20
        reasons.append(f"warnings:{len(set(warnings))}")
    for key, entry in automation.items():
        if key in NON_BLOCKING_AUTOMATION_STATUS_KEYS:
            continue
        entry_status = entry.get("status", "unknown")
        if entry_status in {"manual_review_needed", "performance_review_needed"}:
            score -= 5 if key in LIGHT_REVIEW_AUTOMATION_STATUS_KEYS else 10
            reasons.append(f"{key}:{entry_status}")
        elif not is_acceptable_status(entry_status):
            score -= 25
            reasons.append(f"{key}:{entry_status}")
    pending_count = int(manual_review_decisions.get("pending_count", 0) or 0)
    if pending_count:
        score -= 15
        reasons.append(f"manual_review_pending:{pending_count}")
    score = max(0, min(100, score))
    if score >= 95:
        health_status = "healthy"
    elif score >= 60:
        health_status = "needs_review"
    else:
        health_status = "needs_fix"
    return {
        "score": score,
        "status": health_status,
        "reasons": reasons,
    }


def parse_number(value):
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def parse_return(value):
    number = parse_number(value)
    if number is None:
        return None
    if "%" in str(value):
        return number / 100
    return number


def read_forecast_performance_state(project_root, check_payload, check_path):
    forecast = check_payload.get("forecast_performance")
    source_path = check_path
    if not isinstance(forecast, dict):
        manifest_path = (check_payload.get("outputs") or {}).get("manifest")
        if manifest_path:
            resolved_manifest_path = resolve_optional_path(project_root, manifest_path)
            manifest = read_json(resolved_manifest_path)
            if isinstance(manifest, dict):
                forecast = manifest.get("forecast_performance")
                source_path = resolved_manifest_path
    if not isinstance(forecast, dict) and "forecast_performance_status" not in check_payload:
        return None
    forecast = forecast if isinstance(forecast, dict) else {}
    fallback_review_path = Path(check_path).parent / "latest_forecast_performance_review.json"
    fallback_forecast = read_json(fallback_review_path)
    if isinstance(fallback_forecast, dict):
        for key in (
            "next_one_week_evaluation_date",
            "next_one_week_evaluation_count",
            "next_one_month_evaluation_date",
            "next_one_month_evaluation_count",
        ):
            if not forecast.get(key) and fallback_forecast.get(key):
                forecast[key] = fallback_forecast.get(key)
    return {
        "status": check_payload.get("forecast_performance_status") or forecast.get("status") or "unknown",
        "total_evaluations": forecast.get("total_evaluations", 0),
        "mature_evaluations": forecast.get("mature_evaluations", 0),
        "one_week_mature": forecast.get("one_week_mature", 0),
        "one_month_mature": forecast.get("one_month_mature", 0),
        "prediction_unavailable": forecast.get("prediction_unavailable", 0),
        "direction_hit_rate": forecast.get("direction_hit_rate"),
        "average_excess_return": forecast.get("average_excess_return"),
        "next_one_week_evaluation_date": forecast.get("next_one_week_evaluation_date", ""),
        "next_one_week_evaluation_count": forecast.get("next_one_week_evaluation_count", 0),
        "next_one_month_evaluation_date": forecast.get("next_one_month_evaluation_date", ""),
        "next_one_month_evaluation_count": forecast.get("next_one_month_evaluation_count", 0),
        "path": relative_path(project_root, source_path),
    }


def normalize_candidate_findings_review(project_root, payload, path):
    return {
        "status": payload.get("status", "unknown"),
        "as_of_date": payload.get("as_of_date"),
        "candidate_count": to_int(first_present(payload, "candidate_count_total", "candidate_count")),
        "risk_action_required_count": to_int(payload.get("risk_action_required_count")),
        "risk_action_queue_count": to_int(payload.get("risk_action_queue_count")),
        "risk_reduction_status": payload.get("risk_reduction_status") or payload.get("status", "unknown"),
        "risk_reduction_decision": payload.get("risk_reduction_decision", ""),
        "priority_market": first_present(payload, "priority_market", "risk_reduction_priority_market"),
        "formal_model_change_allowed": bool(payload.get("formal_model_change_allowed")),
        "path": relative_path(project_root, path),
    }


def normalize_candidate_risk_resolution_review(project_root, payload, path):
    return {
        "status": payload.get("status", "unknown"),
        "as_of_date": payload.get("as_of_date"),
        "risk_action_total_count": to_int(payload.get("risk_action_total_count")),
        "auto_routed_count": to_int(payload.get("auto_routed_count")),
        "manual_pending_count": to_int(payload.get("manual_pending_count")),
        "manual_pending_limit": to_int(payload.get("manual_pending_limit")),
        "cap_applied_count": to_int(payload.get("cap_applied_count")),
        "cap_applied_ratio": payload.get("cap_applied_ratio"),
        "formal_model_change_allowed": bool(payload.get("formal_model_change_allowed")),
        "path": relative_path(project_root, path),
    }


def normalize_forecast_shadow_review(project_root, payload, path):
    return {
        "status": payload.get("status", "unknown"),
        "as_of_date": payload.get("as_of_date"),
        "one_week_samples": to_int(first_present(payload, "one_week_samples", "one_week_evaluated_count")),
        "direction_hit_rate": payload.get("direction_hit_rate"),
        "shadow_diagnosis_status": payload.get("shadow_diagnosis_status", "unknown"),
        "shadow_diagnosis_reasons": normalize_reason_list(payload.get("shadow_diagnosis_reasons", [])),
        "priority_review_market": payload.get("priority_review_market", ""),
        "formal_model_change_allowed": bool(payload.get("formal_model_change_allowed")),
        "formal_model_change_decision": payload.get("formal_model_change_decision", ""),
        "path": relative_path(project_root, path),
    }


def normalize_first_one_month_forecast_evaluation(project_root, payload, path):
    cohort = payload.get("cohort", {}) or {}
    one_week = payload.get("one_week", {}) or {}
    one_month = payload.get("one_month", {}) or {}
    comparison = payload.get("market_comparison", {}) or {}
    return {
        "status": payload.get("status", "missing"),
        "as_of_date": payload.get("as_of_date", ""),
        "expected_sample_count": to_int(cohort.get("expected_sample_count")),
        "actual_sample_count": to_int(cohort.get("actual_sample_count")),
        "one_week_valid_count": to_int(one_week.get("valid_evaluation_count")),
        "one_week_direction_hit_rate": one_week.get("direction_hit_rate"),
        "one_week_average_excess_return": one_week.get("average_excess_return"),
        "one_week_failure_type_counts": one_week.get("failure_type_counts", {}),
        "one_month_valid_count": to_int(one_month.get("valid_evaluation_count")),
        "one_month_direction_hit_rate": one_month.get("direction_hit_rate"),
        "one_month_average_excess_return": one_month.get("average_excess_return"),
        "one_month_failure_type_counts": one_month.get("failure_type_counts", {}),
        "market_comparison_status": comparison.get("status", "missing"),
        "recommended_action": payload.get("recommended_action", ""),
        "formal_model_change_allowed": bool(payload.get("formal_model_change_allowed")),
        "formal_model_conclusion_allowed": bool(
            payload.get("formal_model_conclusion_allowed")
        ),
        "path": relative_path(project_root, path),
    }


def normalize_forecast_shadow_disposition(project_root, payload, path):
    counts = payload.get("disposition_counts", {}) or {}
    return {
        "status": payload.get("status", "unknown"),
        "as_of_date": payload.get("as_of_date"),
        "recommended_action": payload.get("recommended_action", ""),
        "continue_observation_count": to_int(counts.get("continue_observation")),
        "rejected_count": to_int(counts.get("rejected")),
        "pending_human_approval_count": to_int(counts.get("pending_human_approval")),
        "next_one_week_evaluation_date": payload.get("next_one_week_evaluation_date", ""),
        "next_one_week_evaluation_count": to_int(payload.get("next_one_week_evaluation_count")),
        "formal_model_change_allowed": bool(payload.get("formal_model_change_allowed")),
        "path": relative_path(project_root, path),
    }


def normalize_backtest_evidence_review(project_root, payload, path):
    return {
        "status": payload.get("status") or payload.get("evidence_status") or "unknown",
        "as_of_date": payload.get("as_of_date"),
        "membership_evidence_gate_status": payload.get("membership_evidence_gate_status", "unknown"),
        "membership_evidence_gate_decision": payload.get("membership_evidence_gate_decision", ""),
        "membership_evidence_blocking_tiers": normalize_reason_list(payload.get("membership_evidence_blocking_tiers", [])),
        "verified_membership_ratio": payload.get("verified_membership_ratio"),
        "backtest_sample_expansion_allowed": bool(payload.get("backtest_sample_expansion_allowed")),
        "evidence_ceiling_status": payload.get("evidence_ceiling_status", "not_confirmed"),
        "backtest_mode": payload.get("backtest_mode", "unknown"),
        "membership_evidence_unresolved_gap_count": to_int(
            payload.get("membership_evidence_unresolved_gap_count")
        ),
        "formal_model_change_allowed": bool(
            payload.get("formal_model_change_allowed") or payload.get("formal_model_upgrade_allowed")
        ),
        "path": relative_path(project_root, path),
    }


def normalize_data_health_review(project_root, payload, path):
    counts = payload.get("data_health_triage_counts") if isinstance(payload.get("data_health_triage_counts"), dict) else {}
    return {
        "status": payload.get("status", "unknown"),
        "as_of_date": payload.get("as_of_date"),
        "data_health_triage_status": payload.get("data_health_triage_status", "unknown"),
        "data_health_triage_decision": payload.get("data_health_triage_decision", ""),
        "candidate_delivery_blocked": bool(payload.get("candidate_delivery_blocked")),
        "data_health_triage_counts": {
            "candidate_blocking": to_int(counts.get("candidate_blocking")),
            "refetch_required": to_int(counts.get("refetch_required")),
            "monitor_only": to_int(counts.get("monitor_only")),
        },
        "path": relative_path(project_root, path),
    }


def resolve_optional_path(project_root, path):
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = project_root / resolved
    return resolved


def format_percent(value):
    if value is None or value == "":
        return "n/a"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "n/a"


def format_forecast_performance_status(entry):
    status = (
        f"{entry.get('status', 'missing')} / mature {entry.get('mature_evaluations', 0)}"
        f" / hit {format_percent(entry.get('direction_hit_rate'))}"
        f" / excess {format_percent(entry.get('average_excess_return'))}"
    )
    if entry.get("next_one_week_evaluation_date"):
        status += f" / next 1w {entry.get('next_one_week_evaluation_date')}"
    if entry.get("next_one_week_evaluation_count"):
        status += f" / next 1w count {entry.get('next_one_week_evaluation_count')}"
    if entry.get("next_one_month_evaluation_date"):
        status += f" / next 1m {entry.get('next_one_month_evaluation_date')}"
    if entry.get("next_one_month_evaluation_count"):
        status += f" / next 1m count {entry.get('next_one_month_evaluation_count')}"
    return status


def classify_candidate_action(candidate):
    expected_return = parse_return(candidate.get("expected_return"))
    score = parse_number(candidate.get("score"))
    risk_reason = str(candidate.get("risk_reason") or "")
    trend_label = str(candidate.get("trend_label") or "")
    trend_confidence = str(candidate.get("trend_confidence") or "").lower()
    valuation_confidence = str(candidate.get("valuation_confidence") or "").lower()

    if expected_return is None:
        return "资料不足", "缺少预期收益率，先补齐目标价或收益字段。"
    if expected_return < 0 or "当前无安全边际" in risk_reason or "预期收益为负" in risk_reason:
        return "暂缓研究", "预期收益为负或缺少安全边际，本周暂不优先深研。"
    if (
        "low" in {trend_confidence, valuation_confidence}
        or "偏弱" in trend_label
        or "走势偏弱" in risk_reason
        or "置信度低" in risk_reason
    ):
        return "谨慎观察", "趋势、估值置信度或风险提示偏弱，先复核风险。"
    if expected_return >= 0.20 and (score is None or score >= 80):
        return "优先研究", "评分和预期收益较高，优先进入人工深研。"
    return "等待回调", "仍可跟踪，但收益空间或安全边际需要继续等待。"


def annotate_candidate_actions(candidates):
    annotated = []
    for candidate in candidates:
        tier, reason = classify_candidate_action(candidate)
        next_candidate = dict(candidate)
        next_candidate["action_tier"] = tier
        next_candidate["action_reason"] = reason
        annotated.append(next_candidate)
    return annotated


def summarize_candidate_actions(candidates):
    by_tier = {tier: 0 for tier in CANDIDATE_ACTION_TIERS}
    examples = {tier: [] for tier in CANDIDATE_ACTION_TIERS}
    for candidate in candidates:
        tier = candidate.get("action_tier") or "资料不足"
        if tier not in by_tier:
            by_tier[tier] = 0
            examples[tier] = []
        by_tier[tier] += 1
        if len(examples[tier]) < 5:
            examples[tier].append(candidate.get("ticker", ""))
    groups = []
    for tier in CANDIDATE_ACTION_TIERS:
        count = by_tier.get(tier, 0)
        if count:
            groups.append(
                {
                    "tier": tier,
                    "count": count,
                    "examples": [ticker for ticker in examples.get(tier, []) if ticker],
                    "guidance": CANDIDATE_ACTION_GUIDANCE.get(tier, ""),
                }
            )
    return {"by_tier": by_tier, "groups": groups}


def build_payload(
    as_of_date,
    status,
    automation,
    markets,
    candidates,
    missing_inputs,
    warnings,
    manual_review_queue,
    manual_review_decisions,
    manual_review_merge_summary,
):
    recommended_action = choose_recommended_action(status, automation)
    priority_actions = choose_priority_actions(status, automation, recommended_action)
    priority_action_details = describe_priority_actions(
        priority_actions,
        automation.get("weekly_action_items", {}).get("items", []),
    )
    priority_input_gaps = summarize_priority_input_gaps(priority_action_details)
    health = summarize_health(status, automation, missing_inputs, warnings, manual_review_decisions)
    candidates = annotate_candidate_actions(candidates)
    candidate_action_summary = summarize_candidate_actions(candidates)
    integrated_review_summary = build_integrated_review_summary(
        automation,
        candidates,
        priority_actions,
        candidate_action_summary,
    )
    return {
        "conclusion_schema": "weekly_conclusion",
        "conclusion_version": 1,
        "as_of_date": as_of_date,
        "status": status,
        "recommended_action": recommended_action,
        "priority_actions": priority_actions,
        "priority_action_details": priority_action_details,
        "priority_input_gaps": priority_input_gaps,
        "health": health,
        "automation": automation,
        "markets": markets,
        "manual_review_queue": manual_review_queue,
        "manual_review_decisions": manual_review_decisions,
        "manual_review_merge_summary": manual_review_merge_summary,
        "candidate_count_total": len(candidates),
        "candidate_action_summary": candidate_action_summary,
        "integrated_review_summary": integrated_review_summary,
        "candidates": candidates,
        "missing_inputs": sorted(set(missing_inputs)),
        "warnings": sorted(set(warnings)),
        "outputs": {
            "markdown": DEFAULT_MARKDOWN_OUTPUT,
            "json": DEFAULT_JSON_OUTPUT,
            "manual_review_decisions_template": MANUAL_REVIEW_DECISIONS_TEMPLATE_OUTPUT,
        },
    }


def render_markdown(payload, per_market_limit=10):
    lines = ["# 每周低估候选统一结论", ""]
    lines.extend(render_automation_section(payload))
    lines.extend(render_integrated_review_summary_section(payload))
    lines.extend(render_priority_actions_section(payload))
    lines.extend(render_backlog_reduction_section(payload))
    lines.extend(render_market_section(payload))
    lines.extend(render_candidate_action_section(payload))
    lines.extend(render_candidate_section(payload, per_market_limit=per_market_limit))
    lines.extend(render_manual_review_queue_section(payload))
    lines.extend(render_manual_review_decisions_section(payload))
    lines.extend(render_manual_review_merge_summary_section(payload))
    lines.extend(render_risk_section(payload))
    lines.extend(render_output_section(payload))
    lines.extend(render_boundary_section())
    return "\n".join(lines).rstrip() + "\n"


def render_automation_section(payload):
    automation = payload["automation"]
    health = payload.get("health", {})
    lines = [
        "## 自动化状态",
        "",
        f"- 本周日期：{payload['as_of_date']}",
        f"- 结论状态：{payload['status']}",
        f"- overall_health：{health.get('status', 'unknown')} / {health.get('score', 0)}",
        f"- 优先动作：{payload['recommended_action']}",
    ]
    for key in (
        "automation_check",
        "data_quality",
        "data_quality_history",
        "forecast_performance",
        "first_one_month_forecast_evaluation",
        "forecast_shadow_disposition",
        "weekly_action_items",
        "weekly_ops_check",
        "weekly_ops_history",
        "weekly_delivery_history",
    ):
        entry = automation.get(key, {})
        status = entry.get("status", "missing")
        if key == "data_quality" and entry.get("score") is not None:
            status = f"{status} / {entry.get('score')}"
        if key == "forecast_performance" and entry:
            status = format_forecast_performance_status(entry)
        lines.append(f"- {key}：{status} ({entry.get('path', '')})")
    lines.append("")
    return lines


def build_integrated_review_summary(automation, candidates, priority_actions, candidate_action_summary):
    candidate_review = automation.get("candidate_findings_review", {})
    candidate_risk_resolution = automation.get("candidate_risk_resolution_review", {})
    forecast_shadow = automation.get("one_week_forecast_shadow_review", {})
    forecast_disposition = automation.get("forecast_shadow_disposition", {})
    first_one_month = automation.get("first_one_month_forecast_evaluation", {})
    backtest_review = automation.get("backtest_evidence_review", {})
    data_health = automation.get("data_health_review", {})
    data_health_counts = data_health.get("data_health_triage_counts", {}) or {}
    formal_flags = [
        candidate_review.get("formal_model_change_allowed"),
        candidate_risk_resolution.get("formal_model_change_allowed"),
        forecast_shadow.get("formal_model_change_allowed"),
        forecast_disposition.get("formal_model_change_allowed"),
        first_one_month.get("formal_model_change_allowed"),
        first_one_month.get("formal_model_conclusion_allowed"),
        backtest_review.get("formal_model_change_allowed"),
    ]
    return {
        "candidate_count_total": to_int(candidate_review.get("candidate_count")) or len(candidates),
        "candidate_action_tiers": {
            group.get("tier"): group.get("count", 0)
            for group in candidate_action_summary.get("groups", [])
            if group.get("tier")
        },
        "candidate_risk_status": candidate_review.get("risk_reduction_status") or candidate_review.get("status", "unknown"),
        "candidate_risk_decision": candidate_review.get("risk_reduction_decision", ""),
        "candidate_risk_action_required_count": to_int(candidate_review.get("risk_action_required_count")),
        "candidate_risk_priority_market": candidate_review.get("priority_market", ""),
        "candidate_risk_resolution_status": candidate_risk_resolution.get("status", "missing"),
        "candidate_risk_auto_routed_count": to_int(candidate_risk_resolution.get("auto_routed_count")),
        "candidate_risk_manual_pending_count": to_int(candidate_risk_resolution.get("manual_pending_count")),
        "candidate_risk_manual_pending_limit": to_int(candidate_risk_resolution.get("manual_pending_limit")),
        "candidate_risk_cap_applied_count": to_int(candidate_risk_resolution.get("cap_applied_count")),
        "candidate_risk_cap_applied_ratio": candidate_risk_resolution.get("cap_applied_ratio"),
        "forecast_shadow_status": forecast_shadow.get("status", "unknown"),
        "forecast_shadow_diagnosis_status": forecast_shadow.get("shadow_diagnosis_status", "unknown"),
        "forecast_shadow_diagnosis_reasons": forecast_shadow.get("shadow_diagnosis_reasons", []),
        "forecast_shadow_samples": to_int(forecast_shadow.get("one_week_samples")),
        "forecast_shadow_direction_hit_rate": forecast_shadow.get("direction_hit_rate"),
        "forecast_shadow_priority_market": forecast_shadow.get("priority_review_market", ""),
        "forecast_disposition_status": forecast_disposition.get("status", "unknown"),
        "forecast_disposition_continue_observation_count": to_int(
            forecast_disposition.get("continue_observation_count")
        ),
        "forecast_disposition_rejected_count": to_int(forecast_disposition.get("rejected_count")),
        "forecast_disposition_pending_human_approval_count": to_int(
            forecast_disposition.get("pending_human_approval_count")
        ),
        "forecast_disposition_next_one_week_evaluation_date": forecast_disposition.get(
            "next_one_week_evaluation_date", ""
        ),
        "first_one_month_status": first_one_month.get("status", "missing"),
        "first_one_month_expected_count": to_int(first_one_month.get("expected_sample_count")),
        "first_one_month_one_week_valid_count": to_int(first_one_month.get("one_week_valid_count")),
        "first_one_month_one_week_hit_rate": first_one_month.get("one_week_direction_hit_rate"),
        "first_one_month_one_week_average_excess_return": first_one_month.get(
            "one_week_average_excess_return"
        ),
        "first_one_month_one_month_valid_count": to_int(first_one_month.get("one_month_valid_count")),
        "first_one_month_one_month_hit_rate": first_one_month.get("one_month_direction_hit_rate"),
        "first_one_month_one_month_average_excess_return": first_one_month.get(
            "one_month_average_excess_return"
        ),
        "first_one_month_market_comparison_status": first_one_month.get(
            "market_comparison_status", "missing"
        ),
        "backtest_evidence_gate_status": backtest_review.get("membership_evidence_gate_status", "unknown"),
        "backtest_evidence_gate_decision": backtest_review.get("membership_evidence_gate_decision", ""),
        "backtest_evidence_blocking_tiers": backtest_review.get("membership_evidence_blocking_tiers", []),
        "verified_membership_ratio": backtest_review.get("verified_membership_ratio"),
        "backtest_sample_expansion_allowed": bool(backtest_review.get("backtest_sample_expansion_allowed")),
        "backtest_evidence_ceiling_status": backtest_review.get(
            "evidence_ceiling_status", "not_confirmed"
        ),
        "backtest_mode": backtest_review.get("backtest_mode", "unknown"),
        "backtest_unresolved_gap_count": to_int(
            backtest_review.get("membership_evidence_unresolved_gap_count")
        ),
        "data_health_triage_status": data_health.get("data_health_triage_status", "unknown"),
        "data_health_triage_decision": data_health.get("data_health_triage_decision", ""),
        "candidate_delivery_blocked": bool(data_health.get("candidate_delivery_blocked")),
        "data_health_triage_counts": {
            "candidate_blocking": to_int(data_health_counts.get("candidate_blocking")),
            "refetch_required": to_int(data_health_counts.get("refetch_required")),
            "monitor_only": to_int(data_health_counts.get("monitor_only")),
        },
        "weekly_action_item_count": to_int(automation.get("weekly_action_items", {}).get("item_count")),
        "priority_action_count": len(priority_actions or []),
        "formal_model_change_allowed": any(flag is True for flag in formal_flags),
    }


def render_integrated_review_summary_section(payload):
    summary = payload.get("integrated_review_summary", {})
    counts = summary.get("data_health_triage_counts", {}) or {}
    lines = [
        "## 一屏结论",
        "",
        "| 模块 | 状态 | 关键数字 | 处理边界 |",
        "|---|---|---|---|",
    ]
    lines.append(
        "| 候选风险 | {status} | raw_actions={required}; auto_routed={routed}; manual_pending={pending}; cap_applied={cap} | {decision} |".format(
            status=escape_cell(summary.get("candidate_risk_resolution_status", "missing")),
            required=escape_cell(summary.get("candidate_risk_action_required_count", 0)),
            routed=escape_cell(summary.get("candidate_risk_auto_routed_count", 0)),
            pending=escape_cell(summary.get("candidate_risk_manual_pending_count", 0)),
            cap=escape_cell(summary.get("candidate_risk_cap_applied_count", 0)),
            decision=escape_cell(summary.get("candidate_risk_decision") or "按风险压降队列处理"),
        )
    )
    lines.append(
        "| 预测影子诊断 | {status} | samples={samples}; hit={hit}; diagnosis={diagnosis} | shadow_only; formal_model_unchanged |".format(
            status=escape_cell(summary.get("forecast_shadow_status", "unknown")),
            samples=escape_cell(summary.get("forecast_shadow_samples", 0)),
            hit=escape_cell(format_percent(summary.get("forecast_shadow_direction_hit_rate"))),
            diagnosis=escape_cell(", ".join(summary.get("forecast_shadow_diagnosis_reasons", []) or []) or "-"),
        )
    )
    lines.append(
        "| 预测影子处置 | {status} | 继续观察={observing}; 已驳回={rejected}; 待人工审批={approval}; 下一批={next_date} | shadow_only; formal_model_unchanged |".format(
            status=escape_cell(summary.get("forecast_disposition_status", "unknown")),
            observing=escape_cell(summary.get("forecast_disposition_continue_observation_count", 0)),
            rejected=escape_cell(summary.get("forecast_disposition_rejected_count", 0)),
            approval=escape_cell(summary.get("forecast_disposition_pending_human_approval_count", 0)),
            next_date=escape_cell(summary.get("forecast_disposition_next_one_week_evaluation_date") or "-"),
        )
    )
    lines.append(
        "| 首批1个月评价 | {status} | 1周={week_count}/{expected}, 命中={week_hit}, 超额={week_excess}; 1个月={month_count}/{expected}, 命中={month_hit}, 超额={month_excess}; 市场比较={market_status} | review_only; no_formal_model_conclusion |".format(
            status=escape_cell(summary.get("first_one_month_status", "missing")),
            week_count=summary.get("first_one_month_one_week_valid_count", 0),
            expected=summary.get("first_one_month_expected_count", 0),
            week_hit=escape_cell(format_percent(summary.get("first_one_month_one_week_hit_rate"))),
            week_excess=escape_cell(
                format_percent(summary.get("first_one_month_one_week_average_excess_return"))
            ),
            month_count=summary.get("first_one_month_one_month_valid_count", 0),
            month_hit=escape_cell(format_percent(summary.get("first_one_month_one_month_hit_rate"))),
            month_excess=escape_cell(
                format_percent(summary.get("first_one_month_one_month_average_excess_return"))
            ),
            market_status=escape_cell(
                summary.get("first_one_month_market_comparison_status", "missing")
            ),
        )
    )
    if summary.get("backtest_evidence_ceiling_status") == "evidence_ceiling_confirmed":
        lines.append(
            "| 回测证据边界 | {status} | mode={mode}; unresolved_gaps={gaps}; decision={decision} | no_sample_expansion |".format(
                status=escape_cell(summary.get("backtest_evidence_ceiling_status")),
                mode=escape_cell(summary.get("backtest_mode", "unknown")),
                gaps=summary.get("backtest_unresolved_gap_count", 0),
                decision=escape_cell(summary.get("backtest_evidence_gate_decision") or "-"),
            )
        )
    else:
        lines.append(
            "| 回测证据闸门 | {status} | decision={decision}; blocking={blocking}; verified_ratio={ratio} | no_sample_expansion |".format(
                status=escape_cell(summary.get("backtest_evidence_gate_status", "unknown")),
                decision=escape_cell(summary.get("backtest_evidence_gate_decision") or "-"),
                blocking=escape_cell(", ".join(summary.get("backtest_evidence_blocking_tiers", []) or []) or "-"),
                ratio=escape_cell(format_percent(summary.get("verified_membership_ratio"))),
            )
        )
    lines.append(
        "| 数据健康 | {status} | candidate_blocking={candidate_blocking}; refetch_required={refetch_required}; monitor_only={monitor_only} | candidate_delivery_blocked={blocked} |".format(
            status=escape_cell(summary.get("data_health_triage_status", "unknown")),
            candidate_blocking=escape_cell(counts.get("candidate_blocking", 0)),
            refetch_required=escape_cell(counts.get("refetch_required", 0)),
            monitor_only=escape_cell(counts.get("monitor_only", 0)),
            blocked=str(bool(summary.get("candidate_delivery_blocked"))).lower(),
        )
    )
    lines.append(
        "| 每周待办 | open | action_items={items}; priority_actions={actions} | 先处理最高风险待办 |".format(
            items=escape_cell(summary.get("weekly_action_item_count", 0)),
            actions=escape_cell(summary.get("priority_action_count", 0)),
        )
    )
    lines.append(
        "| 正式模型 | protected | formal_model_change_allowed={allowed} | 不抓取行情、不重新评分、不自动改参数 |".format(
            allowed=str(bool(summary.get("formal_model_change_allowed"))).lower(),
        )
    )
    lines.append("")
    return lines


def render_priority_actions_section(payload):
    lines = ["## 优先动作", ""]
    details = payload.get("priority_action_details") or describe_priority_actions(payload.get("priority_actions") or [])
    lines.extend(["| 动作码 | 中文动作 | 说明 |", "|---|---|---|"])
    for item in details:
        lines.append(
            "| {action} | {label} | {description} |".format(
                action=escape_cell(item.get("action")),
                label=escape_cell(item.get("label")),
                description=escape_cell(item.get("description")),
            )
        )
    lines.append("")
    return lines


def render_backlog_reduction_section(payload):
    weekly_action_items = payload.get("automation", {}).get("weekly_action_items", {})
    plan = weekly_action_items.get("backlog_reduction_plan", []) or []
    if not plan:
        return []
    lines = [
        "## 待办压降分流",
        "",
        "| category | count | actions |",
        "|---|---:|---|",
    ]
    for entry in plan:
        lines.append(
            "| {category} | {count} | {actions} |".format(
                category=escape_cell(entry.get("category", "unknown")),
                count=escape_cell(entry.get("count", 0)),
                actions=escape_cell(", ".join(entry.get("actions", []) or [])),
            )
        )
    lines.append("")
    return lines


def render_market_section(payload):
    lines = ["## 三市场候选概览", "", "| 市场 | 状态 | 候选数 | 来源 |", "|---|---:|---:|---|"]
    for market in payload["markets"]:
        lines.append(
            f"| {market['market']} | {market['status']} | {market['candidate_count']} | {escape_cell(market['source_dir'])} |"
        )
    lines.append("")
    return lines


def render_candidate_action_section(payload):
    summary = payload.get("candidate_action_summary", {})
    groups = summary.get("groups", [])
    lines = [
        "## 候选行动分层",
        "",
        "| 层级 | 数量 | 代表股票 | 处理建议 |",
        "|---|---:|---|---|",
    ]
    if not groups:
        lines.append("| 资料不足 | 0 | - | 暂无可分层候选。 |")
        lines.append("")
        return lines
    for group in groups:
        lines.append(
            "| {tier} | {count} | {examples} | {guidance} |".format(
                tier=escape_cell(group.get("tier")),
                count=escape_cell(group.get("count")),
                examples=escape_cell(", ".join(group.get("examples", [])) or "-"),
                guidance=escape_cell(group.get("guidance")),
            )
        )
    lines.append("")
    return lines


def format_short_trend(candidate, prefix):
    direction = candidate.get(f"{prefix}_expected_direction")
    label = candidate.get(f"{prefix}_trend_label")
    if direction and label:
        return f"{direction} / {label}"
    return direction or label or "-"


def render_candidate_section(payload, per_market_limit=10):
    lines = [
        "## 候选公司摘要",
        "",
        "| 市场 | 股票 | 公司 | 评分 | 目标价 | 建议买入价 | 预期收益率 | 12个月趋势 | 1周走势 | 1个月走势 | 置信度 | 风险理由 |",
        "|---|---|---|---:|---:|---:|---:|---|---|---|---|---|",
    ]
    for market in ("US", "CN", "HK"):
        market_candidates = [candidate for candidate in payload["candidates"] if candidate["market"] == market]
        for candidate in market_candidates[:per_market_limit]:
            confidence = " / ".join(
                value for value in (candidate.get("trend_confidence"), candidate.get("valuation_confidence")) if value
            )
            lines.append(
                "| {market} | {ticker} | {company} | {score} | {target_price} | {buy_price} | "
                "{expected_return} | {trend_label} | {one_week} | {one_month} | {confidence} | {risk_reason} |".format(
                    market=candidate["market"],
                    ticker=escape_cell(candidate.get("ticker")),
                    company=escape_cell(candidate.get("company")),
                    score=escape_cell(candidate.get("score")),
                    target_price=escape_cell(candidate.get("target_price")),
                    buy_price=escape_cell(candidate.get("buy_price")),
                    expected_return=escape_cell(candidate.get("expected_return")),
                    trend_label=escape_cell(candidate.get("trend_label")),
                    one_week=escape_cell(format_short_trend(candidate, "one_week")),
                    one_month=escape_cell(format_short_trend(candidate, "one_month")),
                    confidence=escape_cell(confidence),
                    risk_reason=escape_cell(candidate.get("risk_reason")),
                )
            )
    if not payload["candidates"]:
        lines.append("| - | - | - | - | - | - | - | - | - | - | - | 无可读候选 |")
    lines.append("")
    return lines


def render_manual_review_queue_section(payload):
    queue = payload.get("manual_review_queue", {})
    lines = ["## 人工复核队列", ""]
    if not queue.get("items"):
        lines.append("- 当前没有人工复核队列记录。")
        lines.append("")
        return lines

    lines.extend(
        [
            f"- 队列数量：{queue.get('count', 0)}",
            f"- 来源：{queue.get('path', '')}",
            f"- 按市场：{format_queue_counts(queue.get('by_market', []), 'market')}",
            f"- 按类型：{format_queue_counts(queue.get('by_review_type', []), 'review_type')}",
            "",
            "### 人工复核建议",
            "",
            "| 类型 | 数量 | 建议处置 |",
            "|---|---:|---|",
        ]
    )
    for guidance in queue.get("action_guidance", []):
        lines.append(
            "| {review_type} | {count} | {recommended_action} |".format(
                review_type=escape_cell(guidance.get("review_type")),
                count=escape_cell(guidance.get("count")),
                recommended_action=escape_cell(guidance.get("recommended_action")),
            )
        )
    lines.extend(
        [
            "",
            "| 序号 | 市场 | 类型 | 股票 | 公司 | 复核要点 |",
            "|---:|---|---|---|---|---|",
        ]
    )
    for item in queue["items"]:
        lines.append(
            "| {rank} | {market} | {review_type} | {ticker} | {company} | {review_detail} |".format(
                rank=escape_cell(item.get("rank")),
                market=escape_cell(item.get("market")),
                review_type=escape_cell(item.get("review_type")),
                ticker=escape_cell(item.get("ticker")),
                company=escape_cell(item.get("company")),
                review_detail=escape_cell(item.get("review_detail")),
            )
        )
    lines.append("")
    return lines


def render_manual_review_decisions_section(payload):
    decisions = payload.get("manual_review_decisions", {})
    lines = [
        "## 人工复核结果",
        "",
        f"- 结果文件：{decisions.get('path', '')}",
        f"- 已记录结果：{decisions.get('decision_count', 0)}",
        f"- 已匹配本周队列：{decisions.get('matched_count', 0)}",
        f"- 待处理：{decisions.get('pending_count', 0)}",
        "",
        "| 状态 | 数量 |",
        "|---|---:|",
    ]
    for item in decisions.get("by_status", []):
        lines.append(f"| {escape_cell(item.get('decision_status'))} | {escape_cell(item.get('count'))} |")
    lines.extend(
        [
            "",
            "| 股票 | 市场 | 类型 | 状态 | 备注 | 复核人 |",
            "|---|---|---|---|---|---|",
        ]
    )
    for item in decisions.get("items", [])[:10]:
        lines.append(
            "| {ticker} | {market} | {review_type} | {decision_status} | {decision_note} | {reviewer} |".format(
                ticker=escape_cell(item.get("ticker")),
                market=escape_cell(item.get("market")),
                review_type=escape_cell(item.get("review_type")),
                decision_status=escape_cell(item.get("decision_status")),
                decision_note=escape_cell(item.get("decision_note")),
                reviewer=escape_cell(item.get("reviewer")),
            )
        )
    lines.append("")
    return lines


def render_manual_review_merge_summary_section(payload):
    summary = payload.get("manual_review_merge_summary", {})
    lines = ["## 人工复核合并摘要", ""]
    lines.append(f"- 合并摘要：{summary.get('path', '')}")
    if not summary.get("exists"):
        lines.append("- 暂未发现人工复核结果合并摘要。")
        lines.append("")
        return lines

    lines.extend(
        [
            f"- 合并/更新：{summary.get('merged', 0)}",
            f"- 跳过 pending：{summary.get('skipped_pending', 0)}",
            f"- 跳过无效：{summary.get('skipped_invalid', 0)}",
            f"- 正式结果行数：{summary.get('row_count', 0)}",
            "",
            "| 状态 | 数量 |",
            "|---|---:|",
        ]
    )
    for item in summary.get("by_status", []):
        lines.append(f"| {escape_cell(item.get('decision_status'))} | {escape_cell(item.get('count'))} |")
    lines.append("")
    return lines


def render_risk_section(payload):
    lines = ["## 风险与人工复核", ""]
    if payload["missing_inputs"]:
        lines.append("- 缺失输入：" + "；".join(payload["missing_inputs"]))
    if payload["warnings"]:
        lines.append("- 警告：" + "；".join(payload["warnings"]))
    priority_input_gaps = payload.get("priority_input_gaps", [])
    for gap in priority_input_gaps:
        parts = [f"- 优先输入缺口：{gap.get('label') or gap.get('action_code')}"]
        if gap.get("blocking_input"):
            parts.append(f"投递入口={gap.get('blocking_input')}")
        if gap.get("official_export_url"):
            parts.append(f"official_export_url={gap.get('official_export_url')}")
        if gap.get("blocking_reason"):
            parts.append(f"阻塞原因={gap.get('blocking_reason')}")
        if gap.get("next_action"):
            parts.append(f"下一步={gap.get('next_action')}")
        if gap.get("dry_run_command"):
            parts.append(f"校验命令={gap.get('dry_run_command')}")
        if gap.get("import_command"):
            parts.append(f"导入命令={gap.get('import_command')}")
        if len(parts) == 1:
            parts.append(gap.get("description", ""))
        lines.append("；".join(parts))
    missing_risks = [
        f"{candidate['market']} {candidate['ticker']}"
        for candidate in payload["candidates"]
        if not candidate.get("risk_reason")
    ]
    if missing_risks:
        lines.append("- 风险理由缺口：" + "；".join(missing_risks[:20]))
    if not payload["missing_inputs"] and not payload["warnings"] and not priority_input_gaps and not missing_risks:
        lines.append("- 暂未发现需要优先人工复核的输入缺口。")
    lines.append("")
    return lines


def render_output_section(payload):
    outputs = payload["outputs"]
    return [
        "## 输出路径",
        "",
        f"- Markdown：{outputs['markdown']}",
        f"- JSON：{outputs['json']}",
        "",
    ]


def render_boundary_section():
    return [
        "## 边界",
        "",
        "- 本报告只汇总当前文件系统中已经生成的结果，不重新抓取行情，不重新评分，不修改正式模型参数。",
        "- 内容用于研究筛选和人工复核用途，不构成投资建议。",
        "",
    ]


def write_outputs(payload, markdown, output=None, json_output=None, decisions_template_output=None):
    output_path = Path(output or DEFAULT_MARKDOWN_OUTPUT)
    json_path = Path(json_output or DEFAULT_JSON_OUTPUT)
    template_path = Path(decisions_template_output or MANUAL_REVIEW_DECISIONS_TEMPLATE_OUTPUT)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8-sig")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    write_manual_review_decisions_template(payload, template_path)
    return {"markdown": str(output_path), "json": str(json_path), "manual_review_decisions_template": str(template_path)}


def write_manual_review_decisions_template(payload, path):
    fieldnames = [
        "as_of_date",
        "market",
        "review_type",
        "ticker",
        "company",
        "review_detail",
        "suggested_decision_status",
        "suggested_decision_note",
        "decision_status",
        "decision_note",
        "reviewer",
        "decided_at",
    ]
    decisions = {decision_key(item): item for item in payload.get("manual_review_decisions", {}).get("items", [])}
    rows = []
    for item in payload.get("manual_review_queue", {}).get("all_items", []):
        decision = decisions.get(decision_key(item), {})
        suggestion = suggest_manual_review_decision(item)
        rows.append(
            {
                "as_of_date": payload.get("as_of_date", ""),
                "market": item.get("market", ""),
                "review_type": item.get("review_type", ""),
                "ticker": item.get("ticker", ""),
                "company": item.get("company", ""),
                "review_detail": item.get("review_detail", ""),
                "suggested_decision_status": suggestion["status"],
                "suggested_decision_note": suggestion["note"],
                "decision_status": decision.get("decision_status") or "pending",
                "decision_note": decision.get("decision_note", ""),
                "reviewer": decision.get("reviewer", ""),
                "decided_at": decision.get("decided_at", ""),
            }
        )
    with Path(path).open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def suggest_manual_review_decision(item):
    review_type = item.get("review_type", "")
    review_detail = item.get("review_detail", "")
    if "风险" in review_type or "risk" in review_type.lower():
        return {
            "status": "needs_more_data",
            "note": f"风险提示复核：{review_detail}；确认是否需要降低候选优先级或补充人工备注。",
        }
    if "估值" in review_type or "valuation" in review_type.lower():
        return {
            "status": "needs_more_data",
            "note": f"估值口径复核：{review_detail}；用现金流、盈利质量、收入增长或净资产口径补充判断。",
        }
    return {
        "status": "needs_more_data",
        "note": f"人工复核：{review_detail}；确认后填写 accepted、rejected 或 needs_more_data。",
    }


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def read_csv_rows(path):
    try:
        with Path(path).open("r", newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    except FileNotFoundError:
        return []


def read_manual_review_queue(project_root, item_limit=10):
    path = project_root / MANUAL_REVIEW_QUEUE_PATH
    rows = read_csv_rows(path)
    by_review_type = count_queue_rows(rows, "review_type", "review_type")
    all_items = [normalize_manual_review_row(row) for row in rows]
    return {
        "path": relative_path(project_root, path),
        "count": len(rows),
        "by_market": count_queue_rows(rows, "market", "market"),
        "by_review_type": by_review_type,
        "action_guidance": build_queue_action_guidance(by_review_type),
        "all_items": all_items,
        "items": all_items[:item_limit],
    }


def normalize_manual_review_row(row):
    return {
        "rank": pick(row, "rank", "priority", "优先级序号"),
        "market": pick(row, "market", "市场"),
        "review_type": pick(row, "review_type", "复核类型"),
        "ticker": pick(row, "ticker", "股票"),
        "company": pick(row, "company", "公司"),
        "review_detail": pick(row, "review_detail", "复核要点"),
    }


def read_manual_review_decisions(project_root, manual_review_queue):
    path = project_root / MANUAL_REVIEW_DECISIONS_PATH
    rows = read_csv_rows(path)
    decisions = {decision_key(row): row for row in rows if decision_key(row)}
    items = []
    for queue_item in manual_review_queue.get("all_items", []):
        decision = decisions.get(decision_key(queue_item), {})
        status = pick(decision, "decision_status", "处理状态") or "pending"
        items.append(
            {
                "market": queue_item.get("market", ""),
                "review_type": queue_item.get("review_type", ""),
                "ticker": queue_item.get("ticker", ""),
                "company": queue_item.get("company", ""),
                "decision_status": status,
                "decision_note": pick(decision, "decision_note", "复核备注"),
                "reviewer": pick(decision, "reviewer", "复核人"),
                "decided_at": pick(decision, "decided_at", "复核时间"),
            }
        )
    return {
        "path": relative_path(project_root, path),
        "decision_count": len(rows),
        "matched_count": sum(1 for item in items if item["decision_status"] != "pending"),
        "pending_count": sum(1 for item in items if item["decision_status"] == "pending"),
        "by_status": count_decision_items(items),
        "items": items,
    }


def read_manual_review_merge_summary(project_root):
    path = project_root / MANUAL_REVIEW_MERGE_SUMMARY_PATH
    payload = read_json(path)
    summary = {
        "path": relative_path(project_root, path),
        "exists": payload is not None,
        "merged": 0,
        "skipped_pending": 0,
        "skipped_invalid": 0,
        "row_count": 0,
        "by_status": [],
    }
    if not payload:
        return summary
    summary.update(
        {
            "merged": to_int(payload.get("merged")),
            "skipped_pending": to_int(payload.get("skipped_pending")),
            "skipped_invalid": to_int(payload.get("skipped_invalid")),
            "row_count": to_int(payload.get("row_count")),
            "by_status": normalize_status_counts(payload.get("by_status", [])),
        }
    )
    return summary


def decision_key(row):
    market = pick(row, "market", "市场")
    review_type = pick(row, "review_type", "复核类型")
    ticker = pick(row, "ticker", "股票")
    if not (market and review_type and ticker):
        return None
    return (market, review_type, ticker)


def count_decision_items(items):
    counts = {}
    for item in items:
        status = item.get("decision_status") or "pending"
        counts[status] = counts.get(status, 0) + 1
    return [{"decision_status": key, "count": count} for key, count in counts.items()]


def normalize_status_counts(items):
    normalized = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "decision_status": pick(item, "decision_status", "status"),
                "count": to_int(item.get("count")),
            }
        )
    return normalized


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def normalize_reason_list(value):
    if not isinstance(value, list):
        return []
    reasons = []
    for item in value:
        if isinstance(item, dict):
            reason = first_present(item, "reason_code", "reason", "code", "name")
        else:
            reason = str(item or "")
        if reason:
            reasons.append(reason)
    return reasons


def build_queue_action_guidance(by_review_type):
    guidance = []
    for item in by_review_type:
        review_type = item.get("review_type", "")
        guidance.append(
            {
                "review_type": review_type,
                "count": item.get("count", 0),
                "recommended_action": REVIEW_TYPE_ACTIONS.get(
                    review_type,
                    "保留原始复核类型并补充人工判断，确认是否影响候选评分、风险说明或后续跟踪状态。",
                ),
            }
        )
    return guidance


def count_queue_rows(rows, source_key, output_key):
    counts = {}
    for row in rows:
        value = pick(row, source_key)
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return [{output_key: key, "count": count} for key, count in counts.items()]


def format_queue_counts(items, label_key):
    if not items:
        return "无"
    return "；".join(f"{item.get(label_key, '')} {item.get('count', 0)}" for item in items)


def index_by_ticker(rows):
    result = {}
    for row in rows:
        ticker = pick(row, "ticker", "symbol", "code", "股票代码", "证券代码")
        if ticker:
            result[ticker] = row
    return result


def extract_risks(path):
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return {}
    risks = {}
    current_ticker = "*"
    for line in text.splitlines():
        heading = re.match(r"^#+\s+(.+?)\s*$", line)
        if heading:
            current_ticker = heading.group(1).split()[0]
        risk = re.search(r"风险[：:]\s*(.+)", line)
        if risk:
            risks[current_ticker] = risk.group(1).strip()
            risks.setdefault("*", risk.group(1).strip())
        table_risk = parse_risk_table_row(line)
        if table_risk:
            risks[table_risk["ticker"]] = table_risk["risk_reason"]
    return risks


def parse_risk_table_row(line):
    if not line.lstrip().startswith("|"):
        return None
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    if len(cells) < 3:
        return None
    ticker, _company, risk_reason = cells[:3]
    if ticker in {"股票", "---", ""} or set(ticker) <= {"-"}:
        return None
    if risk_reason in {"风险说明", "---", ""} or set(risk_reason) <= {"-"}:
        return None
    return {"ticker": ticker, "risk_reason": risk_reason}


def pick(row, *names):
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return str(value)
    return ""


def is_acceptable_status(status):
    normalized = str(status or "").strip().lower()
    return normalized in {
        "ready",
        "ok",
        "success",
        "completed",
        "fresh",
        "needs_review",
        "collecting",
        "sample_accumulating",
        "partial_sample_accumulating",
        "performance_review_needed",
        "manual_review_needed",
        "action_required",
        "shadow_review_needed",
        "evidence_review_needed",
        "evidence_ceiling_confirmed",
        "acceptable_with_monitoring",
        "monitor_only",
        "blocked",
    }


def choose_recommended_action(status, automation):
    if status != "ready":
        return "review_inputs"
    weekly_items = automation.get("weekly_action_items", {}).get("items", []) or []
    for item in weekly_items:
        if not isinstance(item, dict):
            continue
        action_code = str(item.get("action_code", "")).strip()
        if action_code:
            return action_code
    automation_action = automation.get("automation_check", {}).get("recommended_action")
    return automation_action or "monitor_next_run"


def choose_priority_actions(status, automation, recommended_action):
    if status != "ready":
        return [recommended_action]
    actions = automation.get("automation_check", {}).get("priority_actions") or []
    weekly_items = automation.get("weekly_action_items", {}).get("items", []) or []
    weekly_actions = [
        str(item.get("action_code", "")).strip()
        for item in weekly_items
        if isinstance(item, dict) and str(item.get("action_code", "")).strip()
    ]
    if weekly_actions:
        return list(weekly_actions)
    return list(actions or [recommended_action])


def describe_priority_actions(actions, weekly_action_items=None):
    dynamic_templates = {
        str(item.get("action_code", "")).strip(): item
        for item in weekly_action_items or []
        if isinstance(item, dict) and str(item.get("action_code", "")).strip()
    }
    details = []
    for action in actions or ["monitor_next_run"]:
        if action in ACTION_DETAILS:
            template = ACTION_DETAILS[action]
            label = template["label"]
            description = template["description"]
            raw_description = description
        elif action in dynamic_templates:
            template = dynamic_templates[action]
            label = template.get("title") or "未分类动作"
            description = template.get("recommended_check") or "保留原始动作码，等待后续补充中文说明。"
            raw_description = description
            if is_external_input_action(action, description):
                description = format_priority_input_gap_description(
                    parse_inline_action_metadata(description),
                    description,
                )
        else:
            label = "未分类动作"
            description = "保留原始动作码，等待后续补充中文说明。"
            raw_description = description
        details.append(
            {
                "action": action,
                "label": label,
                "description": description,
                "raw_description": raw_description,
            }
        )
    return details


def summarize_priority_input_gaps(priority_action_details):
    gaps = []
    for detail in priority_action_details or []:
        action = str(detail.get("action", "")).strip()
        description = str(detail.get("raw_description") or detail.get("description", "")).strip()
        if not is_external_input_action(action, description):
            continue
        metadata = parse_inline_action_metadata(description)
        gaps.append(
            {
                "action_code": action,
                "label": detail.get("label", ""),
                "description": description,
                "blocking_input": first_present(
                    metadata,
                    "source_file_inbox",
                    "inbox_blocking_input",
                    "source_file_inbox_blocking_input",
                    "blocking_input",
                ),
                "blocking_reason": first_present(
                    metadata,
                    "inbox_blocking_reason",
                    "source_file_inbox_blocking_reason",
                    "blocking_reason",
                ),
                "next_action": first_present(
                    metadata,
                    "inbox_next_action",
                    "source_file_inbox_next_action",
                    "next_action",
                ),
                "dry_run_command": first_present(
                    metadata,
                    "dry_run_command",
                    "source_file_inbox_dry_run_command",
                ),
                "import_command": first_present(
                    metadata,
                    "import_command",
                    "source_file_inbox_import_command",
                    "source_file_inbox_next_command",
                ),
                "official_export_url": first_present(metadata, "official_export_url"),
                "user_agent_hint": first_present(metadata, "source_file_user_agent_hint"),
            }
        )
    return gaps


def is_external_input_action(action, description):
    external_input_actions = {"provide_official_constituents_csv"}
    external_input_markers = (
        "external_input_required=true",
        "inbox_external_input_required=true",
        "source_file_inbox",
        "blocking_input=",
        "official_constituents_csv_missing",
    )
    description_lower = str(description or "").lower()
    return action in external_input_actions or any(marker in description_lower for marker in external_input_markers)


def format_priority_input_gap_description(metadata, fallback):
    parts = []
    blocking_input = first_present(
        metadata,
        "source_file_inbox",
        "inbox_blocking_input",
        "source_file_inbox_blocking_input",
        "blocking_input",
    )
    blocking_reason = first_present(
        metadata,
        "inbox_blocking_reason",
        "source_file_inbox_blocking_reason",
        "blocking_reason",
    )
    next_action = first_present(metadata, "inbox_next_action", "source_file_inbox_next_action", "next_action")
    dry_run_command = first_present(
        metadata,
        "dry_run_command",
        "source_file_inbox_dry_run_command",
    )
    import_command = first_present(
        metadata,
        "import_command",
        "source_file_inbox_import_command",
        "source_file_inbox_next_command",
    )
    user_agent_hint = first_present(metadata, "source_file_user_agent_hint")
    official_export_url = first_present(metadata, "official_export_url")
    if blocking_input:
        parts.append(f"投递入口={blocking_input}")
    if official_export_url:
        parts.append(f"official_export_url={official_export_url}")
    if blocking_reason:
        parts.append(f"阻塞原因={blocking_reason}")
    if next_action:
        parts.append(f"下一步={next_action}")
    if dry_run_command:
        parts.append(f"校验命令={dry_run_command}")
    if import_command:
        parts.append(f"导入命令={import_command}")
    if user_agent_hint:
        parts.append(f"source_file_user_agent_hint={user_agent_hint}")
    return "；".join(parts) or fallback


def parse_inline_action_metadata(text):
    metadata = {}
    for raw_part in str(text or "").split(";"):
        part = raw_part.strip()
        if not part:
            continue
        if "=" in part:
            key, value = part.split("=", 1)
        elif ":" in part:
            key, value = part.split(":", 1)
        else:
            continue
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z0-9_]+", key):
            continue
        metadata[key] = value.strip()
    return metadata


def first_present(mapping, *keys):
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return ""


def parse_iso_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def relative_path(project_root, path):
    try:
        return Path(path).relative_to(project_root).as_posix()
    except ValueError:
        return Path(path).as_posix()


def escape_cell(value):
    if value is None:
        return ""
    return str(value).replace("|", "\\|")


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--today", default=None)
    parser.add_argument("--max-age-days", type=int, default=8)
    parser.add_argument("--output", default=None)
    parser.add_argument("--json-output", default=None)
    parser.add_argument("--decisions-template-output", default=None)
    args = parser.parse_args(argv)

    project_root = Path(args.project_root)
    payload = build_weekly_conclusion(project_root, today=args.today, max_age_days=args.max_age_days)
    markdown = render_markdown(payload)
    default_output = project_root / DEFAULT_MARKDOWN_OUTPUT
    default_json_output = project_root / DEFAULT_JSON_OUTPUT
    write_outputs(
        payload,
        markdown,
        output=args.output or default_output,
        json_output=args.json_output or default_json_output,
        decisions_template_output=args.decisions_template_output or project_root / MANUAL_REVIEW_DECISIONS_TEMPLATE_OUTPUT,
    )
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
