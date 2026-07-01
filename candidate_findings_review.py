import argparse
import csv
import json
import sys
from pathlib import Path


REVIEW_SCHEMA = "candidate_findings_review"
REVIEW_VERSION = 1
DEFAULT_MARKETS = [
    ("美股周筛", "outputs/us_universe"),
    ("A股周筛", "outputs/cn_universe"),
    ("港股周筛", "outputs/hk_universe"),
]
REQUIRED_FIELDS = [
    "ticker",
    "company_name",
    "current_price",
    "target_price",
    "buy_price",
    "expected_return",
    "trend_label",
    "one_week_trend_label",
    "one_month_trend_label",
    "valuation_confidence",
    "price_action",
    "reason",
]


def _read_csv_rows(path):
    csv_path = Path(path)
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
        ]


def _read_text(path):
    text_path = Path(path)
    if not text_path.exists():
        return ""
    return text_path.read_text(encoding="utf-8-sig")


def _section_lines(text, heading):
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == f"## {heading}":
            start = index + 1
            break
    if start is None:
        return []
    section = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        section.append(line)
    return section


def _markdown_table_rows(lines):
    rows = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells and all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        rows.append(cells)
    return rows[1:] if rows else []


def _risk_map(summary_path):
    rows = _markdown_table_rows(_section_lines(_read_text(summary_path), "候选风险说明"))
    risks = {}
    for cells in rows:
        if len(cells) >= 3:
            risks[cells[0]] = {"company": cells[1], "risk": cells[2]}
    return risks


def _float_value(value):
    try:
        return float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _missing_fields(row):
    return [field for field in REQUIRED_FIELDS if not str(row.get(field, "")).strip()]


def _is_weak_trend(row):
    return row.get("trend_label") == "偏弱"


def _is_low_confidence(row):
    return str(row.get("valuation_confidence", "")).lower() == "low"


def _is_negative_return(row):
    value = _float_value(row.get("expected_return"))
    return value is not None and value < 0


def _is_risk_review_needed(risk):
    text = str(risk or "").strip()
    return bool(text and text not in {"无", "未发现量化硬性风险，仍需复核行业周期和财报一次性项目"})


def _risk_categories(risk, row):
    text = str(risk or "").strip()
    categories = []
    if not text:
        return categories
    if "当前无安全边际" in text or "鏃犲畨鍏ㄨ竟" in text:
        categories.append("no_margin_of_safety")
    if "预期收益为负" in text or "棰勬湡鏀剁泭涓鸿礋" in text or _is_negative_return(row):
        categories.append("negative_expected_return")
    if "需等待更好买点" in text or "绛夊緟" in text:
        categories.append("wait_for_better_entry")
    if "走势偏弱" in text or "璧板娍鍋忓急" in text or _is_weak_trend(row):
        categories.append("weak_trend")
    if "估值置信度低" in text or "浼板€肩疆淇″害" in text or _is_low_confidence(row):
        categories.append("low_valuation_confidence")
    if any(token in text for token in ["收入增长为负", "净利润增长为负", "资产负债率偏高"]):
        categories.append("fundamental_risk")
    deduped = []
    for category in categories:
        if category not in deduped:
            deduped.append(category)
    return deduped


def _risk_recommended_action(categories):
    if {"no_margin_of_safety", "negative_expected_return"}.intersection(categories):
        return "deprioritize_or_wait"
    if "fundamental_risk" in categories:
        return "manual_fundamental_review"
    if categories and set(categories).issubset({"weak_trend", "low_valuation_confidence", "wait_for_better_entry"}):
        return "track_but_do_not_prioritize"
    return "manual_classification_required"


def _risk_queue_action(item):
    action = item.get("recommended_action", "")
    categories = set(item.get("risk_categories", []))
    if action == "deprioritize_or_wait":
        return "defer_research"
    if action == "manual_fundamental_review" or "fundamental_risk" in categories:
        return "manual_fundamental_review"
    if action == "manual_classification_required":
        return "classify_manually"
    return ""


def _risk_action_queue(items):
    queue = []
    for item in items:
        queue_action = _risk_queue_action(item)
        if not queue_action:
            continue
        queue.append(
            {
                "ticker": item.get("ticker", ""),
                "company": item.get("company", ""),
                "queue_action": queue_action,
                "recommended_action": item.get("recommended_action", ""),
                "risk_categories": item.get("risk_categories", []),
                "risk": item.get("risk", ""),
                "expected_return": item.get("expected_return", ""),
                "trend_label": item.get("trend_label", ""),
                "valuation_confidence": item.get("valuation_confidence", ""),
            }
        )
    return queue


def _category_counts(items):
    counts = {}
    for item in items:
        categories = item.get("risk_categories", [])
        if not categories:
            counts["unclassified"] = counts.get("unclassified", 0) + 1
        for category in categories:
            counts[category] = counts.get(category, 0) + 1
    return counts


def _merge_category_counts(markets):
    merged = {}
    for market in markets:
        for category, count in (market.get("risk_category_counts") or {}).items():
            merged[category] = merged.get(category, 0) + count
    return merged


def _market_review(name, path):
    market_path = Path(path)
    rows = _read_csv_rows(market_path / "valuation_targets.csv")
    risks = _risk_map(market_path / "latest_investment_summary.md")
    missing_items = []
    risk_items = []
    for row in rows:
        missing = _missing_fields(row)
        if missing:
            missing_items.append(
                {
                    "ticker": row.get("ticker", ""),
                    "company": row.get("company_name", ""),
                    "missing_fields": missing,
                }
            )
        risk = risks.get(row.get("ticker", ""), {}).get("risk", "")
        if _is_risk_review_needed(risk):
            categories = _risk_categories(risk, row)
            risk_items.append(
                {
                    "ticker": row.get("ticker", ""),
                    "company": row.get("company_name", ""),
                    "risk": risk,
                    "risk_categories": categories,
                    "recommended_action": _risk_recommended_action(categories),
                    "expected_return": row.get("expected_return", ""),
                    "trend_label": row.get("trend_label", ""),
                    "valuation_confidence": row.get("valuation_confidence", ""),
                }
            )
    generated_dates = [row.get("generated_date", "") for row in rows if row.get("generated_date")]
    risk_coverage = sum(1 for row in rows if row.get("ticker", "") in risks)
    risk_classified_count = sum(1 for item in risk_items if item["risk_categories"])
    risk_unclassified_count = sum(1 for item in risk_items if not item["risk_categories"])
    risk_action_required_count = sum(
        1
        for item in risk_items
        if item["recommended_action"]
        in {"deprioritize_or_wait", "manual_fundamental_review", "manual_classification_required"}
    )
    risk_action_queue = _risk_action_queue(risk_items)
    return {
        "name": name,
        "path": str(market_path),
        "as_of_date": generated_dates[0] if generated_dates else "unknown",
        "candidate_count": len(rows),
        "field_complete_count": len(rows) - len(missing_items),
        "missing_field_count": len(missing_items),
        "risk_coverage_count": risk_coverage,
        "risk_missing_count": max(len(rows) - risk_coverage, 0),
        "risk_review_count": len(risk_items),
        "risk_classified_count": risk_classified_count,
        "risk_unclassified_count": risk_unclassified_count,
        "risk_action_required_count": risk_action_required_count,
        "risk_action_queue_count": len(risk_action_queue),
        "risk_action_unqueued_count": max(risk_action_required_count - len(risk_action_queue), 0),
        "risk_category_counts": _category_counts(risk_items),
        "negative_return_count": sum(1 for row in rows if _is_negative_return(row)),
        "weak_trend_count": sum(1 for row in rows if _is_weak_trend(row)),
        "low_confidence_count": sum(1 for row in rows if _is_low_confidence(row)),
        "missing_items": missing_items[:20],
        "risk_items": risk_items[:20],
        "risk_action_queue": risk_action_queue[:50],
    }


def _overall_status(markets):
    if any(item["missing_field_count"] or item["risk_missing_count"] for item in markets):
        return "needs_attention"
    if any(
        item["risk_review_count"] or item["negative_return_count"] or item["weak_trend_count"] or item["low_confidence_count"]
        for item in markets
    ):
        return "manual_review_needed"
    return "ready"


def build_candidate_findings_review(markets=None):
    market_specs = markets or [{"name": name, "path": path} for name, path in DEFAULT_MARKETS]
    reviewed = [_market_review(item["name"], item["path"]) for item in market_specs]
    as_of_dates = [item["as_of_date"] for item in reviewed if item["as_of_date"] != "unknown"]
    status = _overall_status(reviewed)
    return {
        "review_schema": REVIEW_SCHEMA,
        "review_version": REVIEW_VERSION,
        "as_of_date": as_of_dates[0] if as_of_dates else "unknown",
        "status": status,
        "recommended_action": "review_candidate_findings" if status != "ready" else "continue_monitoring",
        "candidate_count": sum(item["candidate_count"] for item in reviewed),
        "field_complete_count": sum(item["field_complete_count"] for item in reviewed),
        "missing_field_count": sum(item["missing_field_count"] for item in reviewed),
        "risk_coverage_count": sum(item["risk_coverage_count"] for item in reviewed),
        "risk_missing_count": sum(item["risk_missing_count"] for item in reviewed),
        "risk_review_count": sum(item["risk_review_count"] for item in reviewed),
        "risk_classified_count": sum(item["risk_classified_count"] for item in reviewed),
        "risk_unclassified_count": sum(item["risk_unclassified_count"] for item in reviewed),
        "risk_action_required_count": sum(item["risk_action_required_count"] for item in reviewed),
        "risk_action_queue_count": sum(item["risk_action_queue_count"] for item in reviewed),
        "risk_action_unqueued_count": sum(item["risk_action_unqueued_count"] for item in reviewed),
        "risk_category_counts": _merge_category_counts(reviewed),
        "negative_return_count": sum(item["negative_return_count"] for item in reviewed),
        "weak_trend_count": sum(item["weak_trend_count"] for item in reviewed),
        "low_confidence_count": sum(item["low_confidence_count"] for item in reviewed),
        "markets": reviewed,
        "formal_model_change_allowed": False,
        "boundary": "只读取候选估值目标和投资摘要，不抓取行情，不重新评分，不修改正式模型参数。",
    }


def render_candidate_findings_review(payload):
    lines = [
        "# 候选解释复核结论",
        "",
        f"- 日期：{payload.get('as_of_date', 'unknown')}",
        f"- 状态：{payload.get('status', 'unknown')}",
        f"- 建议动作：{payload.get('recommended_action', 'unknown')}",
        f"- 候选总数：{payload.get('candidate_count', 0)}",
        f"- 字段完整：{payload.get('field_complete_count', 0)}/{payload.get('candidate_count', 0)}",
        f"- 风险说明覆盖：{payload.get('risk_coverage_count', 0)}/{payload.get('candidate_count', 0)}",
        f"- 需人工复核风险：{payload.get('risk_review_count', 0)}",
        f"- 预期收益为负：{payload.get('negative_return_count', 0)}",
        f"- 走势偏弱：{payload.get('weak_trend_count', 0)}",
        f"- 估值置信度 low：{payload.get('low_confidence_count', 0)}",
        f"- 正式模型修改：{'允许' if payload.get('formal_model_change_allowed') else '不允许'}",
        "",
        "## 市场概览",
        "",
        "| 市场 | 候选数 | 字段完整 | 风险覆盖 | 风险复核 | 负收益 | 弱走势 | low置信度 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    lines.insert(5, f"- risk_classified_count: {payload.get('risk_classified_count', 0)}")
    lines.insert(6, f"- risk_unclassified_count: {payload.get('risk_unclassified_count', 0)}")
    lines.insert(7, f"- risk_action_required_count: {payload.get('risk_action_required_count', 0)}")
    lines.insert(8, f"- risk_action_queue_count: {payload.get('risk_action_queue_count', 0)}")
    lines.insert(9, f"- risk_action_unqueued_count: {payload.get('risk_action_unqueued_count', 0)}")
    for item in payload.get("markets", []) or []:
        lines.append(
            f"| {item.get('name', '')} | {item.get('candidate_count', 0)} | "
            f"{item.get('field_complete_count', 0)} | {item.get('risk_coverage_count', 0)} | "
            f"{item.get('risk_review_count', 0)} | {item.get('negative_return_count', 0)} | "
            f"{item.get('weak_trend_count', 0)} | {item.get('low_confidence_count', 0)} |"
        )
    lines.extend(
        [
            "",
            "## 风险复核样例",
            "",
            "| 市场 | 股票 | 公司 | 风险说明 | 预期收益 | 趋势 | 估值置信度 |",
            "|---|---|---|---|---:|---|---|",
        ]
    )
    any_risk = False
    for market in payload.get("markets", []) or []:
        for item in market.get("risk_items", []) or []:
            any_risk = True
            lines.append(
                f"| {market.get('name', '')} | {item.get('ticker', '')} | {item.get('company', '')} | "
                f"{item.get('risk', '')} | {item.get('expected_return', '')} | "
                f"{item.get('trend_label', '')} | {item.get('valuation_confidence', '')} |"
            )
    if not any_risk:
        lines.append("| - | - | - | 无需人工复核风险样例 | - | - | - |")
    lines.extend(
        [
            "",
            "## 边界",
            f"- {payload.get('boundary', '')}",
            "- 该复核只用于安排候选解释人工复核顺序，不构成投资建议。",
            "",
        ]
    )
    return "\n".join(lines)


def _parse_market(value):
    if "=" not in value:
        raise ValueError(f"market must be NAME=PATH: {value}")
    name, path = value.split("=", 1)
    return {"name": name, "path": path}


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
    parser = argparse.ArgumentParser(description="Build candidate findings review from valuation outputs.")
    parser.add_argument("--market", action="append", default=[])
    parser.add_argument("--output", default="outputs/automation/latest_candidate_findings_review.json")
    parser.add_argument("--report", default="outputs/automation/latest_candidate_findings_review.md")
    args = parser.parse_args()

    markets = [_parse_market(item) for item in args.market] if args.market else None
    payload = build_candidate_findings_review(markets)
    report = render_candidate_findings_review(payload)
    if args.output:
        write_json(payload, args.output)
    if args.report:
        write_text(report, args.report)
    print(report, end="")
    print(f"Candidate findings review: {args.report}")


if __name__ == "__main__":
    main()
