import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path


REVIEW_SCHEMA = "candidate_risk_manual_review_plan"
REVIEW_VERSION = 1


def _read_json(path):
    source = Path(path)
    if not source.exists():
        return {}
    return json.loads(source.read_text(encoding="utf-8-sig"))


def _float_value(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _review_focus(item):
    categories = set(item.get("risk_categories") or [])
    if "negative_expected_return" in categories or "no_margin_of_safety" in categories:
        return "defer_until_margin_returns"
    if "fundamental_risk" in categories and "weak_trend" in categories:
        return "fundamental_and_trend_review"
    if "fundamental_risk" in categories:
        return "fundamental_review"
    if "low_valuation_confidence" in categories:
        return "valuation_input_review"
    if "weak_trend" in categories:
        return "trend_review"
    return "manual_classification_review"


def _research_questions(item):
    categories = set(item.get("risk_categories") or [])
    questions = []
    if "fundamental_risk" in categories:
        questions.extend(
            [
                "核对最新收入和净利润变化是否为一次性因素",
                "检查资产负债率、现金流和利润率是否支持当前估值",
            ]
        )
    if "weak_trend" in categories:
        questions.append("比较近1个月和近3个月走势是否持续弱于本地基准")
    if "low_valuation_confidence" in categories:
        questions.append("复核PE、PB、ROE、行业中位数和缺失财务字段是否导致估值置信度偏低")
    if "no_margin_of_safety" in categories:
        questions.append("确认当前价是否仍高于建议买入价或缺少安全边际")
    if "negative_expected_return" in categories:
        questions.append("确认目标价和当前价关系是否仍显示负预期收益")
    if not questions:
        questions.append("补充人工判断该风险项是否需要继续跟踪")
    return questions


def _minimum_evidence(item):
    categories = set(item.get("risk_categories") or [])
    evidence = ["候选公司本期 valuation_report 或 weekly_report 对应条目"]
    if "fundamental_risk" in categories:
        evidence.append("最近一期年报或中报中的收入、净利润、资产负债率和现金流")
    if "weak_trend" in categories:
        evidence.append("近1个月和近3个月价格走势及相对基准表现")
    if "low_valuation_confidence" in categories:
        evidence.append("估值输入字段、行业样本数量和缺失字段说明")
    if "no_margin_of_safety" in categories or "negative_expected_return" in categories:
        evidence.append("当前价格、建议买入价、目标价和预期收益率")
    return evidence


def _decision_options(item):
    tier = item.get("priority_tier", "")
    if tier == "defer_research":
        return ["defer_until_better_entry", "remove_from_research_queue", "watch_price_only"]
    options = ["continue_tracking", "downgrade_to_watchlist", "defer_until_better_entry"]
    if tier == "priority_research":
        options.insert(0, "approve_priority_research")
    return options


def _priority_sort_key(item):
    tier_weight = {"priority_research": 0, "watchlist_review": 1, "defer_research": 2}
    expected_return = _float_value(item.get("expected_return"))
    total_score = _float_value(item.get("total_score"))
    return (
        tier_weight.get(item.get("priority_tier", ""), 9),
        -(expected_return if expected_return is not None else -999),
        -(total_score if total_score is not None else -999),
        item.get("ticker", ""),
    )


def _plan_item(item, index):
    focus = _review_focus(item)
    return {
        "review_id": f"risk-{index:03d}",
        "market": item.get("market", ""),
        "ticker": item.get("ticker", ""),
        "company": item.get("company", ""),
        "priority_tier": item.get("priority_tier", ""),
        "review_focus": focus,
        "queue_action": item.get("queue_action", ""),
        "recommended_action": item.get("recommended_action", ""),
        "risk_categories": item.get("risk_categories") or [],
        "risk": item.get("risk", ""),
        "expected_return": _float_value(item.get("expected_return")),
        "total_score": _float_value(item.get("total_score")),
        "grade": item.get("grade", ""),
        "trend_label": item.get("trend_label", ""),
        "valuation_confidence": item.get("valuation_confidence", ""),
        "industry": item.get("industry", ""),
        "research_questions": _research_questions(item),
        "minimum_evidence": _minimum_evidence(item),
        "decision_options": _decision_options(item),
        "manual_decision": "",
        "decision_reason": "",
    }


def build_candidate_risk_manual_review_plan(
    candidate_risk_priority_review="outputs/automation/latest_candidate_risk_priority_review.json",
    as_of_date=None,
):
    source = Path(candidate_risk_priority_review)
    priority_review = _read_json(source)
    source_items = sorted(priority_review.get("items") or [], key=_priority_sort_key)
    items = [_plan_item(item, index + 1) for index, item in enumerate(source_items)]
    priority_count = sum(1 for item in items if item["priority_tier"] == "priority_research")
    watchlist_count = sum(1 for item in items if item["priority_tier"] == "watchlist_review")
    defer_count = sum(1 for item in items if item["priority_tier"] == "defer_research")
    return {
        "review_schema": REVIEW_SCHEMA,
        "review_version": REVIEW_VERSION,
        "as_of_date": as_of_date or priority_review.get("as_of_date") or date.today().isoformat(),
        "source_review": str(source),
        "status": "manual_review_plan_ready" if items else "ready",
        "recommended_action": "complete_priority_research_reviews" if priority_count else "continue_monitoring",
        "manual_review_item_count": len(items),
        "priority_research_count": priority_count,
        "watchlist_count": watchlist_count,
        "defer_count": defer_count,
        "formal_model_change_allowed": False,
        "items": items,
        "boundary": "只把候选风险队列转成人工复核清单，不抓取行情，不重新评分，不修改正式模型参数。",
    }


def _fmt(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def render_candidate_risk_manual_review_plan(payload):
    lines = [
        "# 候选风险人工复核清单",
        "",
        f"- 日期：{payload.get('as_of_date', '')}",
        f"- 状态：{payload.get('status', '')}",
        f"- 复核项：{payload.get('manual_review_item_count', 0)}",
        f"- priority_research：{payload.get('priority_research_count', 0)}",
        f"- watchlist_review：{payload.get('watchlist_count', 0)}",
        f"- defer_research：{payload.get('defer_count', 0)}",
        "- 正式模型修改：不允许",
        "",
        "## 复核清单",
        "",
        "| ID | tier | 市场 | 股票 | 公司 | 焦点 | 决策选项 | 风险 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    if payload.get("items"):
        for item in payload["items"]:
            lines.append(
                f"| {item.get('review_id', '')} | {item.get('priority_tier', '')} | "
                f"{item.get('market', '')} | {item.get('ticker', '')} | {item.get('company', '')} | "
                f"{item.get('review_focus', '')} | {';'.join(item.get('decision_options', []))} | "
                f"{item.get('risk', '')} |"
            )
    else:
        lines.append("| - | - | - | - | - | - | - | - |")
    lines.extend(["", "## 复核问题", ""])
    for item in payload.get("items", []):
        lines.append(f"### {item.get('review_id', '')} {item.get('ticker', '')} {item.get('company', '')}")
        lines.append("")
        lines.append("问题：")
        for question in item.get("research_questions", []):
            lines.append(f"- {question}")
        lines.append("最低证据：")
        for evidence in item.get("minimum_evidence", []):
            lines.append(f"- {evidence}")
        lines.append("")
    lines.extend(["## 边界", "", f"- {payload.get('boundary', '')}", ""])
    return "\n".join(lines)


CSV_FIELDS = [
    "review_id",
    "priority_tier",
    "market",
    "ticker",
    "company",
    "review_focus",
    "queue_action",
    "risk_categories",
    "risk",
    "expected_return",
    "total_score",
    "research_questions",
    "minimum_evidence",
    "decision_options",
    "manual_decision",
    "decision_reason",
]


def write_csv(payload, output):
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for item in payload.get("items", []):
            row = dict(item)
            row["risk_categories"] = ";".join(item.get("risk_categories", []))
            row["research_questions"] = ";".join(item.get("research_questions", []))
            row["minimum_evidence"] = ";".join(item.get("minimum_evidence", []))
            row["decision_options"] = ";".join(item.get("decision_options", []))
            writer.writerow(row)


def write_json(payload, output):
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8-sig",
    )


def write_text(text, output):
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8-sig")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build candidate risk manual review plan.")
    parser.add_argument(
        "--candidate-risk-priority-review",
        default="outputs/automation/latest_candidate_risk_priority_review.json",
    )
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--output", default="outputs/automation/latest_candidate_risk_manual_review_plan.json")
    parser.add_argument("--report", default="outputs/automation/latest_candidate_risk_manual_review_plan.md")
    parser.add_argument("--csv-output", default="outputs/automation/candidate_risk_manual_review_plan.csv")
    args = parser.parse_args()

    payload = build_candidate_risk_manual_review_plan(
        args.candidate_risk_priority_review,
        as_of_date=args.as_of_date or None,
    )
    report = render_candidate_risk_manual_review_plan(payload)
    if args.output:
        write_json(payload, args.output)
    if args.report:
        write_text(report, args.report)
    if args.csv_output:
        write_csv(payload, args.csv_output)
    print(report, end="")
    print(f"Candidate risk manual review plan: {args.report}")


if __name__ == "__main__":
    main()
