import argparse
import csv
import json
import sys
from datetime import date, timedelta
from pathlib import Path


REVIEW_SCHEMA = "forecast_performance_review"
REVIEW_VERSION = 1
FORECAST_MATURITY_DAYS = {"one_week": 7, "one_month": 28}
DEFAULT_MARKETS = [
    ("美股周筛", "outputs/us_universe/forecast_evaluations.csv"),
    ("A股周筛", "outputs/cn_universe/forecast_evaluations.csv"),
    ("港股周筛", "outputs/hk_universe/forecast_evaluations.csv"),
]


def _read_csv_rows(path):
    csv_path = Path(path)
    if not csv_path.exists():
        return None
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
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


def _is_true(value):
    return str(value or "").strip().lower() == "true"


def _unavailable_reason(row):
    if not row.get("prediction_signal"):
        return "missing_prediction_signal"
    if row.get("predicted_direction") in {"", "unknown"}:
        return "unknown_predicted_direction"
    return "prediction_unavailable"


def _count_by_reason(rows):
    counts = {}
    for row in rows:
        reason = _unavailable_reason(row)
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def _merge_reason_counts(markets):
    merged = {}
    for market in markets:
        for reason, count in (market.get("prediction_unavailable_reasons") or {}).items():
            merged[reason] = merged.get(reason, 0) + count
    return merged


def _merge_maturity_gap_reasons(markets):
    merged = {"prediction_unavailable": 0, "pending_maturity": 0, "other_not_evaluated": 0}
    for market in markets:
        for reason, count in (market.get("maturity_gap_reasons") or {}).items():
            merged[reason] = merged.get(reason, 0) + count
    return merged


def _maturity_gap_reasons(rows, mature, unavailable):
    pending_statuses = {"tracking", "pending", "not_due", "sample_accumulating"}
    mature_ids = {id(row) for row in mature}
    unavailable_ids = {id(row) for row in unavailable}
    pending = [
        row
        for row in rows
        if id(row) not in mature_ids
        and id(row) not in unavailable_ids
        and str(row.get("evaluation_status", "")).strip() in pending_statuses
    ]
    other = len(rows) - len(mature) - len(unavailable) - len(pending)
    return {
        "prediction_unavailable": len(unavailable),
        "pending_maturity": len(pending),
        "other_not_evaluated": max(other, 0),
    }


def _history_path(evaluation_path):
    return Path(evaluation_path).parent / "forecast_history.csv"


def _date_after(value, days):
    try:
        return (date.fromisoformat(str(value)) + timedelta(days=days)).isoformat()
    except (TypeError, ValueError):
        return "unknown"


def _earliest_known_date(values):
    known = [value for value in values if value and value != "unknown"]
    return min(known) if known else "unknown"


def _has_short_signals(row):
    return bool(row.get("one_week_expected_direction")) and bool(row.get("one_month_expected_direction"))


def _forecast_history_review(path):
    history_path = _history_path(path)
    rows = _read_csv_rows(history_path)
    if rows is None:
        return {
            "path": str(history_path),
            "status": "missing",
            "total_forecasts": 0,
            "short_signal_complete_count": 0,
            "short_signal_missing_count": 0,
            "latest_generated_date": "unknown",
            "latest_forecast_count": 0,
            "latest_short_signal_missing_count": 0,
            "legacy_short_signal_missing_count": 0,
            "latest_one_week_evaluation_date": "unknown",
            "latest_one_month_evaluation_date": "unknown",
            "latest_missing_samples": [],
            "legacy_missing_samples": [],
        }
    latest = max((row.get("generated_date", "") for row in rows if row.get("generated_date")), default="unknown")
    missing = [row for row in rows if not _has_short_signals(row)]
    latest_rows = [row for row in rows if row.get("generated_date", "") == latest] if latest != "unknown" else []
    latest_missing = [row for row in latest_rows if not _has_short_signals(row)]
    legacy_missing = [
        row for row in missing if latest == "unknown" or row.get("generated_date", "") != latest
    ]
    def sample(row):
        return {
            "ticker": row.get("ticker", ""),
            "company": row.get("company_name", ""),
            "generated_date": row.get("generated_date", ""),
            "missing_fields": ";".join(
                field
                for field in ("one_week_expected_direction", "one_month_expected_direction")
                if not row.get(field)
            ),
        }
    return {
        "path": str(history_path),
        "status": "ready",
        "total_forecasts": len(rows),
        "short_signal_complete_count": sum(1 for row in rows if _has_short_signals(row)),
        "short_signal_missing_count": len(missing),
        "latest_generated_date": latest,
        "latest_forecast_count": len(latest_rows),
        "latest_short_signal_missing_count": len(latest_missing),
        "legacy_short_signal_missing_count": len(legacy_missing),
        "latest_one_week_evaluation_date": _date_after(latest, FORECAST_MATURITY_DAYS["one_week"]),
        "latest_one_month_evaluation_date": _date_after(latest, FORECAST_MATURITY_DAYS["one_month"]),
        "latest_missing_samples": [sample(row) for row in latest_missing[:20]],
        "legacy_missing_samples": [sample(row) for row in legacy_missing[:5]],
    }


def _market_review(project_root, name, path):
    csv_path = Path(project_root) / path
    rows = _read_csv_rows(csv_path)
    history_review = _forecast_history_review(csv_path)
    if rows is None:
        return {
            "name": name,
            "path": str(csv_path),
            "status": "missing",
            "total_evaluations": 0,
            "mature_evaluations": 0,
            "one_week_mature": 0,
            "one_month_mature": 0,
            "prediction_unavailable": 0,
            "direction_hits": 0,
            "direction_hit_rate": None,
            "average_return": None,
            "average_excess_return": None,
            "prediction_unavailable_reasons": {},
            "prediction_unavailable_samples": [],
            "forecast_history": history_review,
            "weak_sample_count": 0,
            "weak_samples": [],
        }
    mature = [row for row in rows if row.get("evaluation_status") == "evaluated"]
    unavailable = [row for row in rows if row.get("evaluation_status") == "prediction_unavailable"]
    maturity_gap_reasons = _maturity_gap_reasons(rows, mature, unavailable)
    latest_generated_date = history_review.get("latest_generated_date", "unknown")
    latest_unavailable = [
        row for row in unavailable if latest_generated_date != "unknown" and row.get("generated_date", "") == latest_generated_date
    ]
    legacy_unavailable = [
        row for row in unavailable if latest_generated_date == "unknown" or row.get("generated_date", "") != latest_generated_date
    ]
    hits = [row for row in mature if _is_true(row.get("direction_hit"))]
    def unavailable_sample(row):
        return {
            "ticker": row.get("ticker", ""),
            "company": row.get("company_name", ""),
            "horizon": row.get("prediction_horizon", ""),
            "reason": _unavailable_reason(row),
            "prediction_signal": row.get("prediction_signal", ""),
            "predicted_direction": row.get("predicted_direction", ""),
            "generated_date": row.get("generated_date", ""),
            "as_of_date": row.get("as_of_date", ""),
        }
    weak_samples = [
        {
            "ticker": row.get("ticker", ""),
            "company": row.get("company_name", ""),
            "horizon": row.get("prediction_horizon", ""),
            "predicted_direction": row.get("predicted_direction", ""),
            "actual_direction": row.get("actual_direction", ""),
            "actual_return": row.get("actual_return", ""),
            "excess_return": row.get("excess_return", ""),
        }
        for row in mature
        if not _is_true(row.get("direction_hit")) or (_float_value(row.get("excess_return")) or 0) < 0
    ]
    return {
        "name": name,
        "path": str(csv_path),
        "status": "ready",
        "total_evaluations": len(rows),
        "mature_evaluations": len(mature),
        "one_week_mature": sum(1 for row in mature if row.get("prediction_horizon") == "1w"),
        "one_month_mature": sum(1 for row in mature if row.get("prediction_horizon") == "1m"),
        "prediction_unavailable": len(unavailable),
        "prediction_unavailable_reasons": _count_by_reason(unavailable),
        "maturity_gap_reasons": maturity_gap_reasons,
        "latest_prediction_unavailable_count": len(latest_unavailable),
        "legacy_prediction_unavailable_count": len(legacy_unavailable),
        "latest_prediction_unavailable_samples": [unavailable_sample(row) for row in latest_unavailable[:20]],
        "legacy_prediction_unavailable_samples": [unavailable_sample(row) for row in legacy_unavailable[:5]],
        "forecast_history": history_review,
        "direction_hits": len(hits),
        "direction_hit_rate": len(hits) / len(mature) if mature else None,
        "average_return": _average(_float_value(row.get("actual_return")) for row in mature),
        "average_excess_return": _average(_float_value(row.get("excess_return")) for row in mature),
        "weak_sample_count": len(weak_samples),
        "weak_samples": weak_samples[:20],
    }


def _overall_status(mature, missing_market_count, latest_short_missing, direction_hit_rate, average_excess_return):
    if missing_market_count:
        return "needs_attention", "collect_forecast_evaluations"
    if latest_short_missing:
        return "needs_attention", "fix_latest_short_prediction_fields"
    if mature < 30:
        return "sample_accumulating", "continue_sample_accumulation"
    weak = (
        (direction_hit_rate is not None and direction_hit_rate < 0.45)
        or (average_excess_return is not None and average_excess_return < 0)
    )
    if weak:
        return "performance_review_needed", "review_forecast_performance"
    return "ready", "review_forecast_performance"


def build_forecast_performance_review(project_root=".", markets=None, today=None):
    root = Path(project_root)
    market_specs = markets or [{"name": name, "path": path} for name, path in DEFAULT_MARKETS]
    reviewed = [_market_review(root, item["name"], item["path"]) for item in market_specs]
    total = sum(item["total_evaluations"] for item in reviewed)
    mature = sum(item["mature_evaluations"] for item in reviewed)
    hits = sum(item["direction_hits"] for item in reviewed)
    one_week = sum(item["one_week_mature"] for item in reviewed)
    one_month = sum(item["one_month_mature"] for item in reviewed)
    unavailable = sum(item["prediction_unavailable"] for item in reviewed)
    missing_market_count = sum(1 for item in reviewed if item["status"] == "missing")
    direction_hit_rate = hits / mature if mature else None
    average_return = _average(item.get("average_return") for item in reviewed if item.get("average_return") is not None)
    average_excess_return = _average(
        item.get("average_excess_return") for item in reviewed if item.get("average_excess_return") is not None
    )
    status, recommended_action = _overall_status(
        mature,
        missing_market_count,
        sum(item.get("forecast_history", {}).get("latest_short_signal_missing_count", 0) for item in reviewed),
        direction_hit_rate,
        average_excess_return,
    )
    return {
        "review_schema": REVIEW_SCHEMA,
        "review_version": REVIEW_VERSION,
        "as_of_date": today or date.today().isoformat(),
        "status": status,
        "recommended_action": recommended_action,
        "total_evaluations": total,
        "mature_evaluations": mature,
        "one_week_mature": one_week,
        "one_month_mature": one_month,
        "prediction_unavailable": unavailable,
        "latest_prediction_unavailable_count": sum(
            item.get("latest_prediction_unavailable_count", 0) for item in reviewed
        ),
        "legacy_prediction_unavailable_count": sum(
            item.get("legacy_prediction_unavailable_count", 0) for item in reviewed
        ),
        "prediction_unavailable_reasons": _merge_reason_counts(reviewed),
        "maturity_gap_reasons": _merge_maturity_gap_reasons(reviewed),
        "forecast_history_short_signal_missing_count": sum(
            item.get("forecast_history", {}).get("short_signal_missing_count", 0) for item in reviewed
        ),
        "latest_short_signal_missing_count": sum(
            item.get("forecast_history", {}).get("latest_short_signal_missing_count", 0) for item in reviewed
        ),
        "legacy_short_signal_missing_count": sum(
            item.get("forecast_history", {}).get("legacy_short_signal_missing_count", 0) for item in reviewed
        ),
        "next_one_week_evaluation_date": _earliest_known_date(
            item.get("forecast_history", {}).get("latest_one_week_evaluation_date") for item in reviewed
        ),
        "next_one_month_evaluation_date": _earliest_known_date(
            item.get("forecast_history", {}).get("latest_one_month_evaluation_date") for item in reviewed
        ),
        "missing_market_count": missing_market_count,
        "direction_hits": hits,
        "direction_hit_rate": direction_hit_rate,
        "average_return": average_return,
        "average_excess_return": average_excess_return,
        "weak_sample_count": sum(item["weak_sample_count"] for item in reviewed),
        "markets": reviewed,
        "formal_model_change_allowed": False,
        "boundary": "只读取现有 forecast_evaluations.csv 和 forecast_history.csv，不抓取行情，不重新预测，不修改正式模型参数。",
    }


def _pct(value):
    return "unknown" if value is None else f"{float(value):.2%}"


def _status_label(status):
    labels = {
        "ready": "可进入人工复核",
        "sample_accumulating": "样本积累中",
        "performance_review_needed": "需复核预测表现",
        "needs_attention": "需补齐预测评估文件",
    }
    return labels.get(status, status)


def render_forecast_performance_review(payload):
    lines = [
        "# 预测表现复核结论",
        "",
        f"- 日期：{payload.get('as_of_date', 'unknown')}",
        f"- 状态：{payload.get('status', 'unknown')}（{_status_label(payload.get('status', 'unknown'))}）",
        f"- 建议动作：{payload.get('recommended_action', 'unknown')}",
        f"- 总评估数：{payload.get('total_evaluations', 0)}",
        f"- 成熟评估：{payload.get('mature_evaluations', 0)}",
        f"- 1周成熟评估：{payload.get('one_week_mature', 0)}",
        f"- 1个月成熟评估：{payload.get('one_month_mature', 0)}",
        f"- next_one_week_evaluation_date: {payload.get('next_one_week_evaluation_date', 'unknown')}",
        f"- next_one_month_evaluation_date: {payload.get('next_one_month_evaluation_date', 'unknown')}",
        f"- 预测字段缺失未评估：{payload.get('prediction_unavailable', 0)}",
        f"- 缺失市场文件：{payload.get('missing_market_count', 0)}",
        f"- 方向命中率：{_pct(payload.get('direction_hit_rate'))}",
        f"- 平均超额收益：{_pct(payload.get('average_excess_return'))}",
        f"- 弱样本数量：{payload.get('weak_sample_count', 0)}",
        f"- 正式模型修改：{'允许' if payload.get('formal_model_change_allowed') else '不允许'}",
        "",
        "## 市场概览",
        "",
        "| 市场 | 状态 | 总评估 | 成熟 | 1周 | 1个月 | 缺预测字段 | 命中率 | 平均超额 | 弱样本 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in payload.get("markets", []) or []:
        lines.append(
            f"| {item.get('name', '')} | {item.get('status', '')} | {item.get('total_evaluations', 0)} | "
            f"{item.get('mature_evaluations', 0)} | {item.get('one_week_mature', 0)} | "
            f"{item.get('one_month_mature', 0)} | {item.get('prediction_unavailable', 0)} | "
            f"{_pct(item.get('direction_hit_rate'))} | {_pct(item.get('average_excess_return'))} | "
            f"{item.get('weak_sample_count', 0)} |"
        )
    lines.extend(
        [
            "",
            "## 弱样本样例",
            "",
            "| 市场 | 股票 | 公司 | 周期 | 预测方向 | 实际方向 | 实际收益 | 超额收益 |",
            "|---|---|---|---|---|---|---:|---:|",
        ]
    )
    any_sample = False
    for market in payload.get("markets", []) or []:
        for item in market.get("weak_samples", []) or []:
            any_sample = True
            lines.append(
                f"| {market.get('name', '')} | {item.get('ticker', '')} | {item.get('company', '')} | "
                f"{item.get('horizon', '')} | {item.get('predicted_direction', '')} | "
                f"{item.get('actual_direction', '')} | {item.get('actual_return', '')} | "
                f"{item.get('excess_return', '')} |"
            )
    if not any_sample:
        lines.append("| - | - | - | - | - | - | - | - |")
    lines.extend(
        [
            "",
            "## 预测字段缺失原因",
            "",
            "| 原因 | 数量 |",
            "|---|---:|",
        ]
    )
    reasons = payload.get("prediction_unavailable_reasons", {}) or {}
    if reasons:
        for reason, count in sorted(reasons.items()):
            lines.append(f"| {reason} | {count} |")
    else:
        lines.append("| - | 0 |")
    lines.extend(
        [
            "",
            "## maturity_gap_reasons",
            "",
            "| reason | count |",
            "|---|---:|",
        ]
    )
    maturity_reasons = payload.get("maturity_gap_reasons", {}) or {}
    if maturity_reasons:
        for reason, count in sorted(maturity_reasons.items()):
            lines.append(f"| {reason} | {count} |")
    else:
        lines.append("| - | 0 |")
    lines.extend(
        [
            "",
            "## 最新批次预测不可评估样例",
            "",
            "| 市场 | 股票 | 公司 | 周期 | 原因 | 预测信号 | 预测方向 | 生成日期 | 评价日期 |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    any_latest_unavailable = False
    for market in payload.get("markets", []) or []:
        for item in market.get("latest_prediction_unavailable_samples", []) or []:
            any_latest_unavailable = True
            lines.append(
                f"| {market.get('name', '')} | {item.get('ticker', '')} | {item.get('company', '')} | "
                f"{item.get('horizon', '')} | {item.get('reason', '')} | "
                f"{item.get('prediction_signal', '')} | {item.get('predicted_direction', '')} | "
                f"{item.get('generated_date', '')} | {item.get('as_of_date', '')} |"
            )
    if not any_latest_unavailable:
        lines.append("| - | - | - | - | 最新批次无预测不可评估样例 | - | - | - | - |")
    lines.extend(
        [
            "",
            "## legacy预测不可评估样例",
            "",
            "| 市场 | 股票 | 公司 | 周期 | 原因 | 预测信号 | 预测方向 | 生成日期 | 评价日期 |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    any_legacy_unavailable = False
    for market in payload.get("markets", []) or []:
        for item in market.get("legacy_prediction_unavailable_samples", []) or []:
            any_legacy_unavailable = True
            lines.append(
                f"| {market.get('name', '')} | {item.get('ticker', '')} | {item.get('company', '')} | "
                f"{item.get('horizon', '')} | {item.get('reason', '')} | "
                f"{item.get('prediction_signal', '')} | {item.get('predicted_direction', '')} | "
                f"{item.get('generated_date', '')} | {item.get('as_of_date', '')} |"
            )
    if not any_legacy_unavailable:
        lines.append("| - | - | - | - | - | - | - | - | - |")
    lines.extend(
        [
            "",
            "## 短周期预测字段覆盖",
            "",
            "| 市场 | 状态 | 历史预测 | 短周期字段缺失 | 最新批次日期 | next_one_week_evaluation_date | next_one_month_evaluation_date | 最新批次缺失 | legacy缺失 |",
            "|---|---|---:|---:|---|---|---|---:|---:|",
        ]
    )
    for market in payload.get("markets", []) or []:
        history = market.get("forecast_history", {}) or {}
        lines.append(
            f"| {market.get('name', '')} | {history.get('status', 'unknown')} | "
            f"{history.get('total_forecasts', 0)} | {history.get('short_signal_missing_count', 0)} | "
            f"{history.get('latest_generated_date', 'unknown')} | "
            f"{history.get('latest_one_week_evaluation_date', 'unknown')} | "
            f"{history.get('latest_one_month_evaluation_date', 'unknown')} | "
            f"{history.get('latest_short_signal_missing_count', 0)} | "
            f"{history.get('legacy_short_signal_missing_count', 0)} |"
        )
    lines.extend(
        [
            "",
            "## 最新批次短周期字段缺失样例",
            "",
            "| 市场 | 股票 | 公司 | 生成日期 | 缺失字段 |",
            "|---|---|---|---|---|",
        ]
    )
    any_latest_gap = False
    for market in payload.get("markets", []) or []:
        history = market.get("forecast_history", {}) or {}
        for item in history.get("latest_missing_samples", []) or []:
            any_latest_gap = True
            lines.append(
                f"| {market.get('name', '')} | {item.get('ticker', '')} | {item.get('company', '')} | "
                f"{item.get('generated_date', '')} | {item.get('missing_fields', '')} |"
            )
    if not any_latest_gap:
        lines.append("| - | - | - | - | 最新批次无短周期字段缺失 |")
    lines.extend(
        [
            "",
            "## legacy短周期字段缺失样例",
            "",
            "| 市场 | 股票 | 公司 | 生成日期 | 缺失字段 |",
            "|---|---|---|---|---|",
        ]
    )
    any_legacy_gap = False
    for market in payload.get("markets", []) or []:
        history = market.get("forecast_history", {}) or {}
        for item in history.get("legacy_missing_samples", []) or []:
            any_legacy_gap = True
            lines.append(
                f"| {market.get('name', '')} | {item.get('ticker', '')} | {item.get('company', '')} | "
                f"{item.get('generated_date', '')} | {item.get('missing_fields', '')} |"
            )
    if not any_legacy_gap:
        lines.append("| - | - | - | - | - |")
    lines.extend(
        [
            "",
            "## 边界",
            f"- {payload.get('boundary', '')}",
            "- 该复核只用于判断预测跟踪样本是否足以进入人工复核，不构成投资建议。",
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
    parser = argparse.ArgumentParser(description="Build forecast performance review from forecast evaluations.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--market", action="append", default=[])
    parser.add_argument("--today")
    parser.add_argument("--output", default="outputs/automation/latest_forecast_performance_review.json")
    parser.add_argument("--report", default="outputs/automation/latest_forecast_performance_review.md")
    args = parser.parse_args()

    markets = [_parse_market(item) for item in args.market] if args.market else None
    payload = build_forecast_performance_review(args.project_root, markets, args.today)
    report = render_forecast_performance_review(payload)
    if args.output:
        write_json(payload, args.output)
    if args.report:
        write_text(report, args.report)
    print(report, end="")
    print(f"Forecast performance review: {args.report}")


if __name__ == "__main__":
    main()
