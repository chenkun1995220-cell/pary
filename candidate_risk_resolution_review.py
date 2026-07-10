import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path


REVIEW_SCHEMA = "candidate_risk_resolution_review"
REVIEW_VERSION = 1
DEFAULT_VALUATION_FILES = [
    "outputs/us_universe/valuation_targets.csv",
    "outputs/cn_universe/valuation_targets.csv",
    "outputs/hk_universe/valuation_targets.csv",
]


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_csv(path):
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError:
        return []


def _number(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _boolean(value):
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _valuation_map(project_root, valuation_files=None):
    result = {}
    for raw_path in valuation_files or DEFAULT_VALUATION_FILES:
        path = Path(raw_path)
        if not path.is_absolute():
            path = Path(project_root) / path
        for row in _read_csv(path):
            ticker = str(row.get("ticker", "")).strip().upper()
            if ticker:
                result[ticker] = row
    return result


def _core_risks(item):
    risks = []
    raw_risk = str(item.get("risk", "")).strip()
    if raw_risk:
        risks.append(raw_risk)
    labels = {
        "fundamental_risk": "基本面增长、现金流或负债风险需要核实",
        "weak_trend": "价格及相对基准走势偏弱",
        "low_valuation_confidence": "估值输入或方法分散导致置信度偏低",
        "no_margin_of_safety": "当前价格缺少安全边际",
        "negative_expected_return": "正式目标价对应预期收益为负",
        "wait_for_better_entry": "尚未达到更有利的买入区间",
    }
    for category in item.get("risk_categories", []) or []:
        label = labels.get(category)
        if label and label not in risks:
            risks.append(label)
    return risks or ["风险分类需要人工补充"]


def _buy_conditions(item, valuation):
    categories = set(item.get("risk_categories", []) or [])
    buy_price = _number(valuation.get("buy_price"))
    conditions = [
        (
            f"当前价格不高于正式建议买入价 {buy_price:.2f}"
            if buy_price is not None
            else "补齐正式建议买入价后再讨论买入"
        ),
        "估值置信度不得为 low",
    ]
    if _boolean(valuation.get("target_cap_applied")):
        conditions.append("目标价触及60%保护上限，必须复核未封顶估值和三档敏感性；上限不是精确收益预测")
    if "fundamental_risk" in categories:
        conditions.append("最新财报确认收入、利润、现金流或负债风险停止恶化，或可由一次性因素解释")
    if "weak_trend" in categories:
        conditions.append("价格及相对基准走势企稳后再进入买入讨论")
    if "no_margin_of_safety" in categories or "negative_expected_return" in categories:
        conditions.append("正式目标价重新高于当前价并恢复安全边际")
    return conditions


def _abandon_conditions(item, valuation):
    categories = set(item.get("risk_categories", []) or [])
    conditions = [
        "正式目标价降至当前价以下，或当前价长期高于建议买入价且安全边际无法恢复",
        "关键事实与候选论文相反",
    ]
    if "fundamental_risk" in categories:
        conditions.append("收入、净利润或自由现金流恶化持续，或负债风险继续上升")
    if "low_valuation_confidence" in categories:
        conditions.append("估值方法高度分散且关键输入无法补证")
    if _boolean(valuation.get("target_cap_applied")):
        conditions.append("去除60%保护上限后，敏感性低值仍不能提供合理安全边际")
    return conditions


def _reopen_conditions(disposition, valuation):
    buy_price = _number(valuation.get("buy_price"))
    if disposition == "manual_deep_dive_required":
        return ["补齐最低证据并记录人工处置结论后关闭", "新财报或估值输入发生重大变化时重新复核"]
    if disposition == "defer_until_margin_returns":
        return [
            (
                f"当前价格回落至建议买入价 {buy_price:.2f} 附近"
                if buy_price is not None
                else "建议买入价恢复可用"
            ),
            "正式预期收益重新转正且安全边际恢复",
        ]
    return ["价格进入建议买入区间且核心风险停止恶化", "新财报、目标价或估值置信度发生重大变化"]


def _disposition(item, manual_slots_used, manual_limit):
    tier = item.get("priority_tier", "")
    if tier == "defer_research" or item.get("queue_action") == "defer_research":
        return "defer_until_margin_returns", manual_slots_used
    if tier == "priority_research" and manual_slots_used < manual_limit:
        return "manual_deep_dive_required", manual_slots_used + 1
    return "continue_tracking", manual_slots_used


def _disposition_reason(disposition, item):
    if disposition == "manual_deep_dive_required":
        return "位于风险优先级前五，保留人工深研；不得因高预期收益或触顶目标价自动批准买入"
    if disposition == "defer_until_margin_returns":
        return "当前缺少安全边际或预期收益为负，暂缓研究直到估值条件恢复"
    return "未进入前五人工深研预算，保守转为继续跟踪；风险或估值条件改善后可重新进入"


def _resolved_item(item, valuation, disposition):
    return {
        "market": item.get("market", ""),
        "ticker": str(item.get("ticker", "")).upper(),
        "company": item.get("company", ""),
        "priority_tier": item.get("priority_tier", ""),
        "queue_action": item.get("queue_action", ""),
        "risk_categories": item.get("risk_categories", []) or [],
        "risk": item.get("risk", ""),
        "expected_return": _number(item.get("expected_return")),
        "total_score": _number(item.get("total_score")),
        "valuation_confidence": valuation.get("valuation_confidence", item.get("valuation_confidence", "")),
        "current_price": _number(valuation.get("current_price")),
        "target_price": _number(valuation.get("target_price")),
        "buy_price": _number(valuation.get("buy_price")),
        "target_cap_applied": _boolean(valuation.get("target_cap_applied")),
        "uncapped_target_price": _number(valuation.get("uncapped_target_price")),
        "target_cap_price": _number(valuation.get("target_cap_price")),
        "target_cap_ratio": _number(valuation.get("target_cap_ratio")),
        "sensitivity": {
            "low": _number(valuation.get("sensitivity_low_price")),
            "base": _number(valuation.get("sensitivity_base_price")),
            "high": _number(valuation.get("sensitivity_high_price")),
        },
        "core_risks": _core_risks(item),
        "buy_conditions": _buy_conditions(item, valuation),
        "abandon_conditions": _abandon_conditions(item, valuation),
        "reopen_conditions": _reopen_conditions(disposition, valuation),
        "disposition": disposition,
        "disposition_reason": _disposition_reason(disposition, item),
        "manual_decision_required": disposition == "manual_deep_dive_required",
    }


def build_candidate_risk_resolution_review(
    project_root,
    candidate_risk_priority_review="outputs/automation/latest_candidate_risk_priority_review.json",
    as_of_date=None,
    manual_limit=5,
    valuation_files=None,
):
    root = Path(project_root)
    source = Path(candidate_risk_priority_review)
    if not source.is_absolute():
        source = root / source
    priority = _read_json(source)
    valuations = _valuation_map(root, valuation_files)
    resolved = []
    manual_slots = 0
    for item in priority.get("items", []) or []:
        disposition, manual_slots = _disposition(item, manual_slots, manual_limit)
        ticker = str(item.get("ticker", "")).strip().upper()
        resolved.append(_resolved_item(item, valuations.get(ticker, {}), disposition))

    manual_pending = sum(item["manual_decision_required"] for item in resolved)
    auto_routed = len(resolved) - manual_pending
    cap_count = sum(item["target_cap_applied"] for item in resolved)
    source_count = int(priority.get("risk_queue_count", len(resolved)) or 0)
    issues = []
    if source_count != len(resolved):
        issues.append("source_risk_queue_count_mismatch")
    if manual_pending > manual_limit:
        issues.append("manual_pending_count_above_limit")
    if any(not item["core_risks"] or not item["buy_conditions"] or not item["abandon_conditions"] for item in resolved):
        issues.append("research_conditions_incomplete")
    return {
        "review_schema": REVIEW_SCHEMA,
        "review_version": REVIEW_VERSION,
        "as_of_date": as_of_date or priority.get("as_of_date") or date.today().isoformat(),
        "source_review": str(source),
        "status": "ready" if not issues else "needs_attention",
        "recommended_action": "complete_top_manual_deep_dives" if manual_pending else "continue_monitoring",
        "risk_action_total_count": len(resolved),
        "resolved_or_routed_count": auto_routed,
        "auto_routed_count": auto_routed,
        "manual_pending_count": manual_pending,
        "manual_pending_limit": manual_limit,
        "cap_applied_count": cap_count,
        "cap_applied_ratio": round(cap_count / len(resolved), 6) if resolved else 0.0,
        "issues": issues,
        "formal_model_change_allowed": False,
        "items": resolved,
        "boundary": "自动分流不构成买入批准；不抓取行情、不重新评分、不修改正式模型参数。",
    }


def render_candidate_risk_resolution_review(payload):
    lines = [
        "# 候选风险处置与研究条件",
        "",
        f"- 日期：{payload.get('as_of_date', '')}",
        f"- 状态：{payload.get('status', '')}",
        f"- 风险行动总数：{payload.get('risk_action_total_count', 0)}",
        f"- 自动分流：{payload.get('auto_routed_count', 0)}",
        f"- 待人工深研：{payload.get('manual_pending_count', 0)}/{payload.get('manual_pending_limit', 5)}",
        f"- 目标价触顶：{payload.get('cap_applied_count', 0)} ({payload.get('cap_applied_ratio', 0):.1%})",
        "- 正式模型修改：不允许",
        "",
        "| 市场 | 股票 | 公司 | 处置 | 触顶 | 敏感性低/基准/高 | 核心风险 |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in payload.get("items", []):
        sensitivity = item.get("sensitivity", {})
        lines.append(
            f"| {item.get('market', '')} | {item.get('ticker', '')} | {item.get('company', '')} | "
            f"{item.get('disposition', '')} | {str(item.get('target_cap_applied', False)).lower()} | "
            f"{sensitivity.get('low', '')}/{sensitivity.get('base', '')}/{sensitivity.get('high', '')} | "
            f"{';'.join(item.get('core_risks', []))} |"
        )
    if not payload.get("items"):
        lines.append("| - | - | - | - | - | - | - |")
    lines.extend(["", "## 人工深研条件", ""])
    for item in payload.get("items", []):
        if not item.get("manual_decision_required"):
            continue
        lines.extend([f"### {item.get('ticker', '')} {item.get('company', '')}", "", "买入条件："])
        lines.extend(f"- {value}" for value in item.get("buy_conditions", []))
        lines.append("放弃条件：")
        lines.extend(f"- {value}" for value in item.get("abandon_conditions", []))
        lines.append("")
    lines.extend(["## 边界", "", f"- {payload.get('boundary', '')}", ""])
    return "\n".join(lines)


CSV_FIELDS = [
    "market", "ticker", "company", "priority_tier", "disposition",
    "manual_decision_required", "disposition_reason", "risk_categories", "risk",
    "expected_return", "total_score", "current_price", "target_price", "buy_price",
    "target_cap_applied", "uncapped_target_price", "target_cap_price", "target_cap_ratio",
    "sensitivity", "core_risks", "buy_conditions", "abandon_conditions", "reopen_conditions",
]


def write_csv(payload, output):
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for item in payload.get("items", []):
            row = dict(item)
            for field in ("risk_categories", "core_risks", "buy_conditions", "abandon_conditions", "reopen_conditions"):
                row[field] = ";".join(str(value) for value in item.get(field, []))
            row["sensitivity"] = json.dumps(item.get("sensitivity", {}), ensure_ascii=False, sort_keys=True)
            writer.writerow(row)


def write_json(payload, output):
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8-sig")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Resolve candidate risk backlog into research dispositions.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--candidate-risk-priority-review", default="outputs/automation/latest_candidate_risk_priority_review.json")
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--manual-limit", type=int, default=5)
    parser.add_argument("--output", default="outputs/automation/latest_candidate_risk_resolution_review.json")
    parser.add_argument("--report", default="outputs/automation/latest_candidate_risk_resolution_review.md")
    parser.add_argument("--csv-output", default="outputs/automation/candidate_risk_resolution_review.csv")
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    payload = build_candidate_risk_resolution_review(
        root,
        args.candidate_risk_priority_review,
        as_of_date=args.as_of_date or None,
        manual_limit=args.manual_limit,
    )
    output = Path(args.output) if Path(args.output).is_absolute() else root / args.output
    report = Path(args.report) if Path(args.report).is_absolute() else root / args.report
    csv_output = Path(args.csv_output) if Path(args.csv_output).is_absolute() else root / args.csv_output
    write_json(payload, output)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_candidate_risk_resolution_review(payload), encoding="utf-8-sig")
    write_csv(payload, csv_output)
    print(render_candidate_risk_resolution_review(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
