import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path


REVIEW_SCHEMA = "candidate_risk_priority_research_review"
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


def _suggested_disposition(item):
    categories = set(item.get("risk_categories") or [])
    focus = item.get("review_focus", "")
    if "weak_trend" in categories and "fundamental_risk" in categories:
        return "priority_research_with_trend_caution"
    if "fundamental_risk" in categories:
        return "priority_research_fundamental_check"
    if focus == "valuation_input_review":
        return "priority_research_valuation_input_check"
    return "priority_research_manual_decision"


def _sort_key(item):
    expected_return = _float_value(item.get("expected_return"))
    total_score = _float_value(item.get("total_score"))
    return (
        -(expected_return if expected_return is not None else -999),
        -(total_score if total_score is not None else -999),
        item.get("ticker", ""),
    )


def _priority_item(item, rank):
    return {
        "rank": rank,
        "review_id": item.get("review_id", ""),
        "market": item.get("market", ""),
        "ticker": item.get("ticker", ""),
        "company": item.get("company", ""),
        "review_focus": item.get("review_focus", ""),
        "queue_action": item.get("queue_action", ""),
        "risk_categories": item.get("risk_categories") or [],
        "risk": item.get("risk", ""),
        "expected_return": _float_value(item.get("expected_return")),
        "total_score": _float_value(item.get("total_score")),
        "research_questions": item.get("research_questions") or [],
        "minimum_evidence": item.get("minimum_evidence") or [],
        "decision_options": item.get("decision_options") or [],
        "suggested_disposition": _suggested_disposition(item),
        "manual_decision": item.get("manual_decision", ""),
        "decision_reason": item.get("decision_reason", ""),
    }


def _focus_counts(items):
    counts = {}
    for item in items:
        focus = item.get("review_focus") or "unknown"
        counts[focus] = counts.get(focus, 0) + 1
    return dict(sorted(counts.items(), key=lambda entry: (-entry[1], entry[0])))


def build_candidate_risk_priority_research_review(
    candidate_risk_manual_review_plan="outputs/automation/latest_candidate_risk_manual_review_plan.json",
    as_of_date=None,
):
    source = Path(candidate_risk_manual_review_plan)
    plan = _read_json(source)
    priority_items = [
        item
        for item in plan.get("items", []) or []
        if item.get("priority_tier") == "priority_research"
    ]
    items = [
        _priority_item(item, index + 1)
        for index, item in enumerate(sorted(priority_items, key=_sort_key))
    ]
    pending_decision_count = sum(1 for item in items if not item.get("manual_decision"))
    return {
        "review_schema": REVIEW_SCHEMA,
        "review_version": REVIEW_VERSION,
        "as_of_date": as_of_date or plan.get("as_of_date") or date.today().isoformat(),
        "source_review": str(source),
        "source_status": plan.get("status", ""),
        "status": "priority_research_pending" if pending_decision_count else "ready",
        "recommended_action": (
            "complete_priority_research_reviews"
            if pending_decision_count
            else "continue_monitoring"
        ),
        "priority_research_count": len(items),
        "pending_decision_count": pending_decision_count,
        "focus_counts": _focus_counts(items),
        "formal_model_change_allowed": False,
        "items": items,
        "boundary": "只读取候选风险人工复核计划，不抓取行情，不重新评分，不删除候选，不修改正式模型参数。",
    }


def _join(values):
    return ";".join(str(value) for value in values if value is not None)


def render_candidate_risk_priority_research_review(payload):
    lines = [
        "# 候选风险优先研究复核",
        "",
        f"- 日期：{payload.get('as_of_date', '')}",
        f"- 状态：{payload.get('status', '')}",
        f"- 建议动作：{payload.get('recommended_action', '')}",
        f"- priority_research：{payload.get('priority_research_count', 0)}",
        f"- 待人工决策：{payload.get('pending_decision_count', 0)}",
        "- 正式模型修改：不允许",
        "",
        "## 焦点分布",
        "",
    ]
    if payload.get("focus_counts"):
        for focus, count in payload["focus_counts"].items():
            lines.append(f"- {focus}: {count}")
    else:
        lines.append("- 无")
    lines.extend(
        [
            "",
            "## 优先研究顺序",
            "",
            "| 排名 | 市场 | 股票 | 公司 | 焦点 | 建议处置 | 风险 |",
            "|---:|---|---|---|---|---|---|",
        ]
    )
    if payload.get("items"):
        for item in payload["items"]:
            lines.append(
                f"| {item.get('rank', '')} | {item.get('market', '')} | "
                f"{item.get('ticker', '')} | {item.get('company', '')} | "
                f"{item.get('review_focus', '')} | {item.get('suggested_disposition', '')} | "
                f"{item.get('risk', '')} |"
            )
    else:
        lines.append("| - | - | - | - | - | - | - |")
    lines.extend(["", "## 边界", "", f"- {payload.get('boundary', '')}", ""])
    return "\n".join(lines)


CSV_FIELDS = [
    "rank",
    "review_id",
    "market",
    "ticker",
    "company",
    "review_focus",
    "suggested_disposition",
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
            row["risk_categories"] = _join(item.get("risk_categories", []))
            row["research_questions"] = _join(item.get("research_questions", []))
            row["minimum_evidence"] = _join(item.get("minimum_evidence", []))
            row["decision_options"] = _join(item.get("decision_options", []))
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
    parser = argparse.ArgumentParser(description="Build candidate risk priority research review.")
    parser.add_argument(
        "--candidate-risk-manual-review-plan",
        default="outputs/automation/latest_candidate_risk_manual_review_plan.json",
    )
    parser.add_argument("--as-of-date", default="")
    parser.add_argument(
        "--output",
        default="outputs/automation/latest_candidate_risk_priority_research_review.json",
    )
    parser.add_argument(
        "--report",
        default="outputs/automation/latest_candidate_risk_priority_research_review.md",
    )
    parser.add_argument(
        "--csv-output",
        default="outputs/automation/candidate_risk_priority_research_review.csv",
    )
    args = parser.parse_args()

    payload = build_candidate_risk_priority_research_review(
        args.candidate_risk_manual_review_plan,
        as_of_date=args.as_of_date or None,
    )
    report = render_candidate_risk_priority_research_review(payload)
    if args.output:
        write_json(payload, args.output)
    if args.report:
        write_text(report, args.report)
    if args.csv_output:
        write_csv(payload, args.csv_output)
    print(report, end="")
    print(f"Candidate risk priority research review: {args.report}")


if __name__ == "__main__":
    main()
