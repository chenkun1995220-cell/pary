import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path


REVIEW_SCHEMA = "data_quality_manual_review_plan"
REVIEW_VERSION = 1


CATEGORY_ACTIONS = {
    "loss_making_or_negative_pe": {
        "priority": "monitor",
        "action": "treat_negative_pe_as_loss_case",
        "minimum_evidence": "保留亏损或负 PE 说明，确认不把 PE 缺失误判为行情缺口。",
    },
    "non_positive_book_value_or_pb": {
        "priority": "monitor",
        "action": "treat_pb_as_balance_sheet_case",
        "minimum_evidence": "保留负净资产或 PB 异常说明，确认估值置信度已反映该限制。",
    },
    "special_industry_valuation_review": {
        "priority": "watch",
        "action": "keep_industry_specific_valuation_note",
        "minimum_evidence": "保留行业估值口径说明，必要时在候选报告中提示估值不可直接横向比较。",
    },
    "unclassified": {
        "priority": "review",
        "action": "classify_remaining_manual_reviews",
        "minimum_evidence": "补充 review_category 和 review_detail，避免未分类项长期停留。",
    },
}


def _read_json(path):
    source = Path(path)
    if not source.exists():
        return {}
    return json.loads(source.read_text(encoding="utf-8-sig"))


def _int_value(value):
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _category_plan(category, count, market_breakdown):
    metadata = CATEGORY_ACTIONS.get(
        category,
        {
            "priority": "review",
            "action": "review_category_policy",
            "minimum_evidence": "确认该分类是否已有稳定解释口径，并补充人工判断说明。",
        },
    )
    return {
        "category": category,
        "item_count": count,
        "priority": metadata["priority"],
        "action": metadata["action"],
        "minimum_evidence": metadata["minimum_evidence"],
        "market_breakdown": market_breakdown,
        "manual_decision": "",
        "decision_reason": "",
    }


def _aggregate_categories(markets):
    totals = {}
    breakdown = {}
    for market in markets or []:
        market_name = market.get("name", "")
        categories = market.get("manual_financial_review_by_category") or {}
        if not isinstance(categories, dict):
            continue
        for category, raw_count in categories.items():
            count = _int_value(raw_count)
            if count <= 0:
                continue
            totals[category] = totals.get(category, 0) + count
            breakdown.setdefault(category, {})
            breakdown[category][market_name] = breakdown[category].get(market_name, 0) + count
    return [
        _category_plan(category, count, breakdown.get(category, {}))
        for category, count in sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    ]


def _market_summaries(markets):
    summaries = []
    for market in markets or []:
        summaries.append(
            {
                "name": market.get("name", ""),
                "manual_financial_review_count": _int_value(
                    market.get("manual_financial_review_count")
                ),
                "manual_financial_review_classified_count": _int_value(
                    market.get("manual_financial_review_classified_count")
                ),
                "manual_financial_review_unclassified_count": _int_value(
                    market.get("manual_financial_review_unclassified_count")
                ),
                "candidate_manual_financial_review_count": _int_value(
                    market.get("candidate_manual_financial_review_count")
                ),
                "active_manual_financial_review_count": _int_value(
                    market.get("active_manual_financial_review_count")
                ),
                "closed_manual_financial_review_count": _int_value(
                    market.get("closed_manual_financial_review_count")
                ),
            }
        )
    return summaries


def build_data_quality_manual_review_plan(
    data_health_review="outputs/automation/latest_data_health_review.json",
    as_of_date=None,
):
    source = Path(data_health_review)
    review = _read_json(source)
    markets = review.get("markets") if isinstance(review.get("markets"), list) else []

    manual_count = _int_value(review.get("manual_financial_review_count"))
    classified_count = _int_value(review.get("manual_financial_review_classified_count"))
    unclassified_count = _int_value(review.get("manual_financial_review_unclassified_count"))
    candidate_unclassified_count = _int_value(
        review.get("candidate_manual_financial_review_unclassified_count")
    )
    blocked_candidate_count = _int_value(review.get("blocked_candidate_count"))
    refetch_action_required_count = _int_value(review.get("refetch_gap_action_required_count"))
    classification_complete = manual_count == classified_count and unclassified_count == 0
    requires_weekly_blocker = (
        blocked_candidate_count > 0
        or refetch_action_required_count > 0
        or candidate_unclassified_count > 0
    )

    if not classification_complete:
        status = "manual_review_plan_needed"
        recommended_action = "classify_remaining_manual_financial_reviews"
    elif requires_weekly_blocker:
        status = "candidate_quality_review_needed"
        recommended_action = "resolve_candidate_level_data_quality_items"
    else:
        status = "classification_complete_monitoring"
        recommended_action = "continue_monitoring_classified_financial_reviews"

    review_groups = _aggregate_categories(markets)
    return {
        "review_schema": REVIEW_SCHEMA,
        "review_version": REVIEW_VERSION,
        "as_of_date": as_of_date or review.get("as_of_date") or date.today().isoformat(),
        "source_review": str(source),
        "source_status": review.get("status", ""),
        "status": status,
        "recommended_action": recommended_action,
        "manual_financial_review_count": manual_count,
        "manual_financial_review_classified_count": classified_count,
        "manual_financial_review_unclassified_count": unclassified_count,
        "candidate_manual_financial_review_count": _int_value(
            review.get("candidate_manual_financial_review_count")
        ),
        "candidate_manual_financial_review_unclassified_count": candidate_unclassified_count,
        "blocked_candidate_count": blocked_candidate_count,
        "refetch_gap_action_required_count": refetch_action_required_count,
        "classification_complete": classification_complete,
        "requires_weekly_blocker": requires_weekly_blocker,
        "review_group_count": len(review_groups),
        "review_groups": review_groups,
        "markets": _market_summaries(markets),
        "formal_model_change_allowed": False,
        "boundary": "只读取 latest_data_health_review，不抓取行情，不重新评分，不修改正式模型参数。",
    }


def render_data_quality_manual_review_plan(payload):
    lines = [
        "# 数据质量人工复核计划",
        "",
        f"- 日期：{payload.get('as_of_date', '')}",
        f"- 状态：{payload.get('status', '')}",
        f"- 建议动作：{payload.get('recommended_action', '')}",
        f"- 财务/估值人工复核总数：{payload.get('manual_financial_review_count', 0)}",
        f"- 已分类：{payload.get('manual_financial_review_classified_count', 0)}",
        f"- 未分类：{payload.get('manual_financial_review_unclassified_count', 0)}",
        f"- 候选池未分类：{payload.get('candidate_manual_financial_review_unclassified_count', 0)}",
        f"- 是否阻断周交付：{'是' if payload.get('requires_weekly_blocker') else '否'}",
        "- 正式模型修改：不允许",
        "",
        "## 分类计划",
        "",
        "| 分类 | 数量 | 优先级 | 动作 | 最低证据 |",
        "|---|---:|---|---|---|",
    ]
    if payload.get("review_groups"):
        for item in payload["review_groups"]:
            lines.append(
                f"| {item.get('category', '')} | {item.get('item_count', 0)} | "
                f"{item.get('priority', '')} | {item.get('action', '')} | "
                f"{item.get('minimum_evidence', '')} |"
            )
    else:
        lines.append("| - | 0 | monitor | continue_monitoring | 当前无人工复核项 |")

    lines.extend(
        [
            "",
            "## 市场分布",
            "",
            "| 市场 | 总数 | 已分类 | 未分类 | 候选池复核 | active | closed |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for market in payload.get("markets", []):
        lines.append(
            f"| {market.get('name', '')} | {market.get('manual_financial_review_count', 0)} | "
            f"{market.get('manual_financial_review_classified_count', 0)} | "
            f"{market.get('manual_financial_review_unclassified_count', 0)} | "
            f"{market.get('candidate_manual_financial_review_count', 0)} | "
            f"{market.get('active_manual_financial_review_count', 0)} | "
            f"{market.get('closed_manual_financial_review_count', 0)} |"
        )
    lines.extend(["", "## 边界", "", f"- {payload.get('boundary', '')}", ""])
    return "\n".join(lines)


CSV_FIELDS = [
    "category",
    "item_count",
    "priority",
    "action",
    "minimum_evidence",
    "market_breakdown",
    "manual_decision",
    "decision_reason",
]


def write_csv(payload, output):
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for item in payload.get("review_groups", []):
            row = dict(item)
            row["market_breakdown"] = ";".join(
                f"{market}:{count}" for market, count in item.get("market_breakdown", {}).items()
            )
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
    parser = argparse.ArgumentParser(description="Build data quality manual review plan.")
    parser.add_argument(
        "--data-health-review",
        default="outputs/automation/latest_data_health_review.json",
    )
    parser.add_argument("--as-of-date", default="")
    parser.add_argument(
        "--output",
        default="outputs/automation/latest_data_quality_manual_review_plan.json",
    )
    parser.add_argument(
        "--report",
        default="outputs/automation/latest_data_quality_manual_review_plan.md",
    )
    parser.add_argument(
        "--csv-output",
        default="outputs/automation/data_quality_manual_review_plan.csv",
    )
    args = parser.parse_args()

    payload = build_data_quality_manual_review_plan(
        args.data_health_review,
        as_of_date=args.as_of_date or None,
    )
    report = render_data_quality_manual_review_plan(payload)
    if args.output:
        write_json(payload, args.output)
    if args.report:
        write_text(report, args.report)
    if args.csv_output:
        write_csv(payload, args.csv_output)
    print(report, end="")
    print(f"Data quality manual review plan: {args.report}")


if __name__ == "__main__":
    main()
