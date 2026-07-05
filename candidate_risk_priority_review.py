import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path


REVIEW_SCHEMA = "candidate_risk_priority_review"
REVIEW_VERSION = 1


def _read_json(path):
    source = Path(path)
    if not source.exists():
        return {}
    return json.loads(source.read_text(encoding="utf-8-sig"))


def _read_csv_rows(path):
    source = Path(path)
    if not source.exists():
        return []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
        ]


def _float_value(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _candidate_pool_map(market_path):
    rows = _read_csv_rows(Path(market_path) / "candidate_pool.csv")
    return {row.get("ticker", ""): row for row in rows if row.get("ticker")}


def _priority_tier(item):
    expected_return = _float_value(item.get("expected_return"))
    confidence = str(item.get("valuation_confidence", "")).lower()
    categories = set(item.get("risk_categories") or [])
    queue_action = item.get("queue_action", "")
    if queue_action == "defer_research" or "negative_expected_return" in categories:
        return "defer_research"
    if (
        queue_action == "manual_fundamental_review"
        and expected_return is not None
        and expected_return >= 0.3
        and confidence != "low"
    ):
        return "priority_research"
    return "watchlist_review"


def _priority_score(row):
    tier_weight = {"priority_research": 0, "watchlist_review": 1, "defer_research": 2}
    expected_return = _float_value(row.get("expected_return"))
    total_score = _float_value(row.get("total_score"))
    return (
        tier_weight.get(row.get("priority_tier"), 9),
        -(expected_return if expected_return is not None else -999),
        -(total_score if total_score is not None else -999),
        row.get("ticker", ""),
    )


def _enrich_queue_item(market, item, candidate_pool):
    ticker = item.get("ticker", "")
    candidate = candidate_pool.get(ticker, {})
    expected_return = _float_value(item.get("expected_return"))
    total_score = _float_value(candidate.get("total_score"))
    enriched = {
        "market": market.get("name", ""),
        "ticker": ticker,
        "company": item.get("company", ""),
        "priority_tier": _priority_tier(item),
        "queue_action": item.get("queue_action", ""),
        "recommended_action": item.get("recommended_action", ""),
        "risk_categories": item.get("risk_categories", []),
        "risk": item.get("risk", ""),
        "expected_return": expected_return,
        "trend_label": item.get("trend_label", ""),
        "valuation_confidence": item.get("valuation_confidence", ""),
        "industry": candidate.get("industry", ""),
        "total_score": total_score,
        "grade": candidate.get("grade", ""),
        "candidate_status": candidate.get("candidate_status", ""),
        "market_cap": _float_value(candidate.get("market_cap")),
    }
    return enriched


def build_candidate_risk_priority_review(
    candidate_findings_review="outputs/automation/latest_candidate_findings_review.json",
    as_of_date=None,
):
    source = Path(candidate_findings_review)
    findings = _read_json(source)
    items = []
    for market in findings.get("markets", []) or []:
        candidate_pool = _candidate_pool_map(market.get("path", ""))
        for item in market.get("risk_action_queue", []) or []:
            items.append(_enrich_queue_item(market, item, candidate_pool))
    items = sorted(items, key=_priority_score)
    priority = sum(1 for item in items if item["priority_tier"] == "priority_research")
    watchlist = sum(1 for item in items if item["priority_tier"] == "watchlist_review")
    defer = sum(1 for item in items if item["priority_tier"] == "defer_research")
    return {
        "review_schema": REVIEW_SCHEMA,
        "review_version": REVIEW_VERSION,
        "as_of_date": as_of_date or findings.get("as_of_date") or date.today().isoformat(),
        "source_review": str(source),
        "status": "manual_review_needed" if items else "ready",
        "recommended_action": "review_candidate_risk_priority" if items else "continue_monitoring",
        "risk_queue_count": len(items),
        "priority_research_count": priority,
        "watchlist_count": watchlist,
        "defer_count": defer,
        "formal_model_change_allowed": False,
        "items": items,
        "boundary": "只读取候选风险复核队列并排序，不重新评分，不修改正式模型参数。",
    }


def _fmt(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def render_candidate_risk_priority_review(payload):
    lines = [
        "# 候选风险优先级复核",
        "",
        f"- 日期：{payload.get('as_of_date', '')}",
        f"- 状态：{payload.get('status', '')}",
        f"- 风险队列：{payload.get('risk_queue_count', 0)}",
        f"- priority_research：{payload.get('priority_research_count', 0)}",
        f"- watchlist_review：{payload.get('watchlist_count', 0)}",
        f"- defer_research：{payload.get('defer_count', 0)}",
        "- 正式模型修改：不允许",
        "",
        "## 处理队列",
        "",
        "| tier | 市场 | 股票 | 公司 | 动作 | 预期收益 | 分数 | 等级 | 趋势 | 置信度 | 风险 |",
        "|---|---|---|---|---|---:|---:|---|---|---|---|",
    ]
    if payload.get("items"):
        for item in payload["items"]:
            lines.append(
                f"| {item.get('priority_tier', '')} | {item.get('market', '')} | "
                f"{item.get('ticker', '')} | {item.get('company', '')} | "
                f"{item.get('queue_action', '')} | {_fmt(item.get('expected_return'))} | "
                f"{_fmt(item.get('total_score'))} | {item.get('grade', '')} | "
                f"{item.get('trend_label', '')} | {item.get('valuation_confidence', '')} | "
                f"{item.get('risk', '')} |"
            )
    else:
        lines.append("| - | - | - | - | - | - | - | - | - | - | - |")
    lines.extend(["", "## 边界", "", f"- {payload.get('boundary', '')}", ""])
    return "\n".join(lines)


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
    parser = argparse.ArgumentParser(description="Build candidate risk priority review.")
    parser.add_argument(
        "--candidate-findings-review",
        default="outputs/automation/latest_candidate_findings_review.json",
    )
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--output", default="outputs/automation/latest_candidate_risk_priority_review.json")
    parser.add_argument("--report", default="outputs/automation/latest_candidate_risk_priority_review.md")
    args = parser.parse_args()

    payload = build_candidate_risk_priority_review(
        args.candidate_findings_review,
        as_of_date=args.as_of_date or None,
    )
    report = render_candidate_risk_priority_review(payload)
    if args.output:
        write_json(payload, args.output)
    if args.report:
        write_text(report, args.report)
    print(report, end="")
    print(f"Candidate risk priority review: {args.report}")


if __name__ == "__main__":
    main()
