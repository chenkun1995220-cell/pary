import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path


REVIEW_SCHEMA = "one_week_forecast_calibration_review"
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


def _is_one_week_evaluated(row):
    return row.get("evaluation_status") == "evaluated" and row.get("prediction_horizon") == "1w"


def _is_opposite_miss(row):
    predicted = row.get("predicted_direction", "")
    actual = row.get("actual_direction", "")
    return (predicted, actual) in {("up", "down"), ("down", "up")}


def _is_neutral_miss(row):
    predicted = row.get("predicted_direction", "")
    actual = row.get("actual_direction", "")
    return (predicted != actual) and ("neutral" in {predicted, actual})


def _sample(row, market_name, miss_type):
    return {
        "market": market_name or row.get("_market_name", "") or row.get("market", ""),
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


def _empty_group(key, group_type):
    return {
        group_type: key,
        "sample_count": 0,
        "hit_count": 0,
        "direction_hit_rate": None,
        "opposite_miss_count": 0,
        "neutral_miss_count": 0,
        "other_miss_count": 0,
        "average_actual_return": None,
        "average_excess_return": None,
        "weak_samples": [],
    }


def _group_rows(rows, key_func, group_type, market_name=None):
    grouped = {}
    returns = {}
    excess_returns = {}
    for row in rows:
        key = key_func(row) or "unknown"
        if key not in grouped:
            grouped[key] = _empty_group(key, group_type)
            returns[key] = []
            excess_returns[key] = []
        group = grouped[key]
        group["sample_count"] += 1
        if _is_hit(row):
            group["hit_count"] += 1
        elif _is_opposite_miss(row):
            group["opposite_miss_count"] += 1
            group["weak_samples"].append(_sample(row, market_name or row.get("_market_name", ""), "opposite_miss"))
        elif _is_neutral_miss(row):
            group["neutral_miss_count"] += 1
            group["weak_samples"].append(_sample(row, market_name or row.get("_market_name", ""), "neutral_miss"))
        else:
            group["other_miss_count"] += 1
            group["weak_samples"].append(_sample(row, market_name or row.get("_market_name", ""), "miss"))
        returns[key].append(_float_value(row.get("actual_return")))
        excess_returns[key].append(_float_value(row.get("excess_return")))
    for key, group in grouped.items():
        count = group["sample_count"]
        group["direction_hit_rate"] = group["hit_count"] / count if count else None
        group["average_actual_return"] = _average(returns[key])
        group["average_excess_return"] = _average(excess_returns[key])
        group["weak_samples"] = sorted(group["weak_samples"], key=_weak_sample_sort_key)[:10]
    return sorted(grouped.values(), key=_group_sort_key)


def _weak_sample_sort_key(item):
    priority = {"opposite_miss": 0, "neutral_miss": 1, "miss": 2}
    excess = _float_value(item.get("excess_return"))
    magnitude = -abs(excess) if excess is not None else 0
    return (priority.get(item.get("miss_type"), 9), magnitude, item.get("ticker", ""))


def _group_sort_key(item):
    hit_rate = item.get("direction_hit_rate")
    hit_rate_sort = hit_rate if hit_rate is not None else 2
    return (hit_rate_sort, -item.get("sample_count", 0), str(item.get("predicted_direction") or item.get("market")))


def _market_rows(project_root, market_name, relative_path):
    path = Path(project_root) / relative_path
    rows = _read_csv_rows(path)
    if rows is None:
        return {
            "name": market_name,
            "path": str(path),
            "status": "missing",
            "one_week_evaluated_count": 0,
            "direction_groups": [],
            "rows": [],
        }
    one_week = [row for row in rows if _is_one_week_evaluated(row)]
    return {
        "name": market_name,
        "path": str(path),
        "status": "ready",
        "one_week_evaluated_count": len(one_week),
        "direction_groups": _group_rows(
            one_week,
            lambda row: row.get("predicted_direction", ""),
            "predicted_direction",
            market_name=market_name,
        ),
        "rows": [{**row, "_market_name": market_name} for row in one_week],
    }


def _recommended_actions(total, direction_groups):
    actions = []
    down_group = next((item for item in direction_groups if item.get("predicted_direction") == "down"), None)
    neutral_misses = sum(item.get("neutral_miss_count", 0) for item in direction_groups)
    if down_group and down_group.get("opposite_miss_count", 0) > 0 and (down_group.get("direction_hit_rate") or 0) < 0.25:
        actions.append("review_down_signal_mapping_shadow_only")
    if total and neutral_misses / total >= 0.25:
        actions.append("review_neutral_band_shadow_only")
    if total < 30:
        actions.append("continue_sample_accumulation")
    actions.append("keep_formal_model_unchanged")
    return actions


def build_one_week_forecast_calibration_review(project_root=".", markets=None, as_of_date=None):
    market_specs = markets or DEFAULT_MARKETS
    markets_reviewed = [_market_rows(project_root, name, path) for name, path in market_specs]
    rows = []
    for market in markets_reviewed:
        rows.extend(market.pop("rows"))
    total = len(rows)
    direction_groups = _group_rows(
        rows,
        lambda row: row.get("predicted_direction", ""),
        "predicted_direction",
    )
    market_groups = _group_rows(rows, lambda row: row.get("_market_name", ""), "market")
    actions = _recommended_actions(total, direction_groups)
    status = "calibration_review_needed" if any(action.startswith("review_") for action in actions) else "insufficient_samples"
    if total >= 30 and status == "insufficient_samples":
        status = "monitoring"
    weak_samples = []
    for group in direction_groups:
        weak_samples.extend(group.get("weak_samples", []))
    return {
        "review_schema": REVIEW_SCHEMA,
        "review_version": REVIEW_VERSION,
        "as_of_date": as_of_date or date.today().isoformat(),
        "status": status,
        "one_week_evaluated_count": total,
        "available_market_count": sum(1 for market in markets_reviewed if market["status"] == "ready"),
        "missing_market_count": sum(1 for market in markets_reviewed if market["status"] != "ready"),
        "direction_groups": direction_groups,
        "market_groups": market_groups,
        "markets": markets_reviewed,
        "weak_samples": sorted(weak_samples, key=_weak_sample_sort_key)[:20],
        "recommended_shadow_actions": actions,
        "formal_model_change_allowed": False,
        "boundary": "只做1周预测校准影子复盘；不重新评分，不抓取行情，不修改正式模型参数。",
    }


def _pct(value):
    return "unknown" if value is None else f"{value:.2%}"


def render_one_week_forecast_calibration_review(payload):
    lines = [
        "# 1周预测校准影子复盘",
        "",
        f"- 日期：{payload.get('as_of_date', 'unknown')}",
        f"- 状态：{payload.get('status', 'unknown')}",
        f"- 1周成熟样本：{payload.get('one_week_evaluated_count', 0)}",
        f"- shadow_actions：{', '.join(payload.get('recommended_shadow_actions', []))}",
        "- 正式模型修改：不允许",
        "",
        "## 预测方向分组",
        "",
        "| 预测方向 | 样本 | 命中 | 命中率 | 反向错误 | neutral错误 | 其他错误 | 平均实际收益 | 平均超额收益 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in payload.get("direction_groups", []):
        lines.append(
            f"| {item.get('predicted_direction', '')} | {item.get('sample_count', 0)} | "
            f"{item.get('hit_count', 0)} | {_pct(item.get('direction_hit_rate'))} | "
            f"{item.get('opposite_miss_count', 0)} | {item.get('neutral_miss_count', 0)} | "
            f"{item.get('other_miss_count', 0)} | {_pct(item.get('average_actual_return'))} | "
            f"{_pct(item.get('average_excess_return'))} |"
        )
    lines.extend(
        [
            "",
            "## 市场分组",
            "",
            "| 市场 | 样本 | 命中 | 命中率 | 反向错误 | neutral错误 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for item in payload.get("market_groups", []):
        lines.append(
            f"| {item.get('market', '')} | {item.get('sample_count', 0)} | "
            f"{item.get('hit_count', 0)} | {_pct(item.get('direction_hit_rate'))} | "
            f"{item.get('opposite_miss_count', 0)} | {item.get('neutral_miss_count', 0)} |"
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
                f"{item.get('miss_type', '')} | {item.get('predicted_direction', '')} | "
                f"{item.get('actual_direction', '')} | {item.get('actual_return', '')} | "
                f"{item.get('excess_return', '')} |"
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
    parser = argparse.ArgumentParser(description="Build one-week forecast calibration shadow review.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--market", action="append", default=[])
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--output", default="outputs/automation/latest_one_week_forecast_calibration_review.json")
    parser.add_argument("--report", default="outputs/automation/latest_one_week_forecast_calibration_review.md")
    args = parser.parse_args()

    markets = [_parse_market(item) for item in args.market] if args.market else None
    payload = build_one_week_forecast_calibration_review(
        args.project_root,
        markets=markets,
        as_of_date=args.as_of_date or None,
    )
    report = render_one_week_forecast_calibration_review(payload)
    if args.output:
        write_json(payload, args.output)
    if args.report:
        write_text(report, args.report)
    print(report, end="")
    print(f"One-week forecast calibration review: {args.report}")


if __name__ == "__main__":
    main()
