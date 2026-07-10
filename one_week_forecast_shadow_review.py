import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path


REVIEW_SCHEMA = "one_week_forecast_shadow_review"
REVIEW_VERSION = 1
DEFAULT_MARKETS = [
    ("美股周筛", "outputs/us_universe/forecast_evaluations.csv"),
    ("A股周筛", "outputs/cn_universe/forecast_evaluations.csv"),
    ("港股周筛", "outputs/hk_universe/forecast_evaluations.csv"),
]


def _read_csv_rows(path):
    source = Path(path)
    if not source.exists():
        return None
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


def _average(values):
    cleaned = [value for value in values if value is not None]
    return sum(cleaned) / len(cleaned) if cleaned else None


def _is_hit(row):
    return str(row.get("direction_hit", "")).strip().lower() == "true"


def _is_opposite_miss(row):
    predicted = row.get("predicted_direction", "")
    actual = row.get("actual_direction", "")
    return (predicted, actual) in {("up", "down"), ("down", "up")}


def _is_neutral_miss(row):
    return row.get("actual_direction", "") == "neutral" and not _is_hit(row)


def _one_week_evaluated(rows):
    return [
        row
        for row in rows or []
        if row.get("evaluation_status") == "evaluated" and row.get("prediction_horizon") == "1w"
    ]


def _sample(row, market_name):
    miss_type = "hit" if _is_hit(row) else "miss"
    if _is_opposite_miss(row):
        miss_type = "opposite_miss"
    elif _is_neutral_miss(row):
        miss_type = "neutral_miss"
    return {
        "market": market_name,
        "ticker": row.get("ticker", ""),
        "company": row.get("company_name", ""),
        "generated_date": row.get("generated_date", ""),
        "as_of_date": row.get("as_of_date", ""),
        "predicted_direction": row.get("predicted_direction", ""),
        "actual_direction": row.get("actual_direction", ""),
        "actual_return": row.get("actual_return", ""),
        "excess_return": row.get("excess_return", ""),
        "miss_type": miss_type,
    }


def _weak_sample_sort_key(item):
    priority = {"opposite_miss": 0, "neutral_miss": 1, "miss": 2, "hit": 3}
    excess = _float_value(item.get("excess_return"))
    if item.get("miss_type") == "opposite_miss" and excess is not None:
        magnitude_key = -abs(excess)
    else:
        magnitude_key = excess if excess is not None else 0
    return (
        priority.get(item.get("miss_type"), 9),
        excess is None,
        magnitude_key,
        item.get("ticker", ""),
    )


def _market_review(project_root, name, relative_path):
    path = Path(project_root) / relative_path
    rows = _read_csv_rows(path)
    if rows is None:
        return {
            "name": name,
            "path": str(path),
            "status": "missing",
            "one_week_evaluated_count": 0,
            "direction_hits": 0,
            "direction_hit_rate": None,
            "opposite_miss_count": 0,
            "neutral_miss_count": 0,
            "average_return": None,
            "average_excess_return": None,
            "weak_samples": [],
        }
    one_week = _one_week_evaluated(rows)
    hits = [row for row in one_week if _is_hit(row)]
    opposite = [row for row in one_week if _is_opposite_miss(row)]
    neutral = [row for row in one_week if _is_neutral_miss(row)]
    weak = [
        row
        for row in one_week
        if (not _is_hit(row)) or ((_float_value(row.get("excess_return")) or 0) < 0)
    ]
    weak_sorted = sorted((_sample(row, name) for row in weak), key=_weak_sample_sort_key)
    count = len(one_week)
    return {
        "name": name,
        "path": str(path),
        "status": "ready",
        "one_week_evaluated_count": count,
        "direction_hits": len(hits),
        "direction_hit_rate": len(hits) / count if count else None,
        "opposite_miss_count": len(opposite),
        "neutral_miss_count": len(neutral),
        "average_return": _average(_float_value(row.get("actual_return")) for row in one_week),
        "average_excess_return": _average(_float_value(row.get("excess_return")) for row in one_week),
        "weak_samples": weak_sorted[:10],
    }


def _recommended_actions(total, hit_rate, opposite_misses, neutral_misses):
    actions = []
    if total and hit_rate is not None and hit_rate < 0.35 and opposite_misses > 0:
        actions.append("review_direction_mapping")
    if total and neutral_misses / total >= 0.25:
        actions.append("review_neutral_band")
    if total < 30:
        actions.append("continue_sample_accumulation")
    actions.append("keep_formal_model_unchanged")
    return actions


def _priority_review_market(markets):
    candidates = [
        item
        for item in markets
        if item.get("status") == "ready" and item.get("one_week_evaluated_count", 0) > 0
    ]
    if not candidates:
        return ""
    ranked = sorted(
        candidates,
        key=lambda item: (
            item.get("direction_hit_rate") is None,
            item.get("direction_hit_rate") if item.get("direction_hit_rate") is not None else 1,
            -item.get("opposite_miss_count", 0),
            -item.get("neutral_miss_count", 0),
            item.get("name", ""),
        ),
    )
    return ranked[0].get("name", "")


def _formal_model_blockers(total, hit_rate, opposite_misses, neutral_misses):
    blockers = ["shadow_review_only"]
    if total < 30:
        blockers.append("sample_count_below_minimum")
    if hit_rate is None:
        blockers.append("direction_hit_rate_unknown")
    elif hit_rate < 0.35:
        blockers.append("direction_hit_rate_below_threshold")
    if opposite_misses > 0:
        blockers.append("opposite_miss_count_positive")
    if total and neutral_misses / total >= 0.25:
        blockers.append("neutral_miss_rate_high")
    return blockers


def build_one_week_forecast_shadow_review(project_root=".", markets=None, as_of_date=None):
    market_specs = markets or DEFAULT_MARKETS
    reviewed = sorted(
        (_market_review(project_root, name, path) for name, path in market_specs),
        key=lambda item: (item["status"] != "ready", item["name"]),
    )
    available = [item for item in reviewed if item["status"] == "ready"]
    total = sum(item["one_week_evaluated_count"] for item in reviewed)
    hits = sum(item["direction_hits"] for item in reviewed)
    opposite = sum(item["opposite_miss_count"] for item in reviewed)
    neutral = sum(item["neutral_miss_count"] for item in reviewed)
    hit_rate = hits / total if total else None
    average_return = _average(item.get("average_return") for item in reviewed)
    average_excess = _average(item.get("average_excess_return") for item in reviewed)
    recommended_actions = _recommended_actions(total, hit_rate, opposite, neutral)
    formal_model_blockers = _formal_model_blockers(total, hit_rate, opposite, neutral)
    status = (
        "shadow_review_needed"
        if any(action.startswith("review_") for action in recommended_actions)
        else "sample_accumulating"
    )
    weak_samples = []
    for market in reviewed:
        weak_samples.extend(market.get("weak_samples", []))
    weak_samples = sorted(weak_samples, key=_weak_sample_sort_key)[:20]
    return {
        "review_schema": REVIEW_SCHEMA,
        "review_version": REVIEW_VERSION,
        "as_of_date": as_of_date or date.today().isoformat(),
        "status": status,
        "market_count": len(reviewed),
        "available_market_count": len(available),
        "missing_market_count": len(reviewed) - len(available),
        "one_week_evaluated_count": total,
        "direction_hits": hits,
        "direction_hit_rate": hit_rate,
        "opposite_miss_count": opposite,
        "neutral_miss_count": neutral,
        "average_return": average_return,
        "average_excess_return": average_excess,
        "recommended_shadow_actions": recommended_actions,
        "formal_model_change_allowed": False,
        "formal_model_change_decision": "keep_formal_model_unchanged",
        "shadow_review_decision": "shadow_review_only",
        "priority_review_market": _priority_review_market(reviewed),
        "formal_model_change_blockers": formal_model_blockers,
        "markets": reviewed,
        "weak_samples": weak_samples,
        "boundary": "只做1周预测表现影子分析，不重新评分，不修改正式模型参数。",
    }


def _pct(value):
    return "unknown" if value is None else f"{value:.2%}"


def render_one_week_forecast_shadow_review(payload):
    lines = [
        "# 1周预测影子分析",
        "",
        f"- 日期：{payload.get('as_of_date', 'unknown')}",
        f"- 状态：{payload.get('status', 'unknown')}",
        f"- 1周成熟样本：{payload.get('one_week_evaluated_count', 0)}",
        f"- 方向命中率：{_pct(payload.get('direction_hit_rate'))}",
        f"- 反向误差：{payload.get('opposite_miss_count', 0)}",
        f"- neutral误差：{payload.get('neutral_miss_count', 0)}",
        f"- 平均超额收益：{_pct(payload.get('average_excess_return'))}",
        f"- shadow_actions：{', '.join(payload.get('recommended_shadow_actions', []))}",
        "- 正式模型修改：不允许",
        "",
        "## 正式模型保护结论",
        "",
        f"- formal_model_change_decision：{payload.get('formal_model_change_decision', 'unknown')}",
        f"- shadow_review_decision：{payload.get('shadow_review_decision', 'unknown')}",
        f"- priority_review_market：{payload.get('priority_review_market', '')}",
        f"- formal_model_change_blockers：{', '.join(payload.get('formal_model_change_blockers', []))}",
        "",
        "## 市场分布",
        "",
        "| 市场 | 状态 | 1周样本 | 命中 | 命中率 | 反向误差 | neutral误差 | 平均超额 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in payload.get("markets", []):
        lines.append(
            f"| {item.get('name', '')} | {item.get('status', '')} | "
            f"{item.get('one_week_evaluated_count', 0)} | {item.get('direction_hits', 0)} | "
            f"{_pct(item.get('direction_hit_rate'))} | {item.get('opposite_miss_count', 0)} | "
            f"{item.get('neutral_miss_count', 0)} | {_pct(item.get('average_excess_return'))} |"
        )
    lines.extend(
        [
            "",
            "## 弱样本",
            "",
            "| 市场 | 股票 | 公司 | 类型 | 预测 | 实际 | 实际收益 | 超额收益 |",
            "|---|---|---|---|---|---|---:|---:|",
        ]
    )
    if payload.get("weak_samples"):
        for item in payload.get("weak_samples", []):
            lines.append(
                f"| {item.get('market', '')} | {item.get('ticker', '')} | {item.get('company', '')} | "
                f"{item.get('miss_type', '')} | "
                f"{item.get('predicted_direction', '')} | {item.get('actual_direction', '')} | "
                f"{item.get('actual_return', '')} | {item.get('excess_return', '')} |"
            )
    else:
        lines.append("| - | - | - | - | - | - | - | - |")
    lines.extend(["", "## 边界", "", f"- {payload.get('boundary', '')}", ""])
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


def _parse_market(value):
    if "=" not in value:
        raise ValueError(f"market must be NAME=PATH: {value}")
    name, path = value.split("=", 1)
    return name, path


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build one-week forecast shadow review.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--market", action="append", default=[])
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--output", default="outputs/automation/latest_one_week_forecast_shadow_review.json")
    parser.add_argument("--report", default="outputs/automation/latest_one_week_forecast_shadow_review.md")
    args = parser.parse_args()

    markets = [_parse_market(item) for item in args.market] if args.market else None
    payload = build_one_week_forecast_shadow_review(
        args.project_root,
        markets=markets,
        as_of_date=args.as_of_date or None,
    )
    report = render_one_week_forecast_shadow_review(payload)
    if args.output:
        write_json(payload, args.output)
    if args.report:
        write_text(report, args.report)
    print(report, end="")
    print(f"One-week forecast shadow review: {args.report}")


if __name__ == "__main__":
    main()
