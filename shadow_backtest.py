import argparse
import csv
import os
import re
import statistics
import tempfile
from pathlib import Path


DEFAULT_PROPOSALS = [
    {
        "proposal_name": "direction_threshold_3pct",
        "parameter": "direction_threshold",
        "candidate_value": "0.03",
        "excess_return_delta": "0.01",
        "adverse_excursion_delta": "0.00",
    },
    {
        "proposal_name": "direction_threshold_8pct",
        "parameter": "direction_threshold",
        "candidate_value": "0.08",
        "excess_return_delta": "0.005",
        "adverse_excursion_delta": "0.00",
    },
    {
        "proposal_name": "target_price_cap_140pct",
        "parameter": "target_price_cap",
        "candidate_value": "1.40",
        "excess_return_delta": "0.004",
        "adverse_excursion_delta": "0.00",
    },
    {
        "proposal_name": "target_price_cap_150pct",
        "parameter": "target_price_cap",
        "candidate_value": "1.50",
        "excess_return_delta": "0.006",
        "adverse_excursion_delta": "0.00",
    },
    {
        "proposal_name": "uniform_safety_margin_25pct",
        "parameter": "uniform_safety_margin",
        "candidate_value": "0.25",
        "excess_return_delta": "0.008",
        "adverse_excursion_delta": "0.00",
    },
]

COMPARISON_FIELDS = [
    "proposal_name",
    "parameter",
    "candidate_value",
    "status",
    "rejection_reason",
    "training_start",
    "training_end",
    "validation_start",
    "validation_end",
    "training_samples",
    "validation_samples",
    "market_count",
    "industry_count",
    "markets",
    "industries",
    "direction_hit_rate",
    "average_excess_return",
    "average_target_error",
    "max_adverse_excursion",
    "tail_target_error_p95",
    "validation_window",
]


def rolling_windows(weeks, train_size=104, validation_size=26, step=13):
    ordered = sorted(dict.fromkeys(weeks), key=_week_sort_key)
    windows = []
    start = 0
    while start + train_size + validation_size <= len(ordered):
        split = start + train_size
        windows.append((ordered[start:split], ordered[split:split + validation_size]))
        start += step
    return windows


def _week_sort_key(value):
    text = str(value)
    numbers = tuple(int(part) for part in re.findall(r"\d+", text))
    return (numbers, text)


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _mean(rows, field):
    values = [_number(row.get(field)) for row in rows]
    values = [value for value in values if value is not None]
    return statistics.fmean(values) if values else None


def _p95_abs(rows, field):
    values = [_number(row.get(field)) for row in rows]
    values = sorted(abs(value) for value in values if value is not None)
    if not values:
        return None
    index = min(len(values) - 1, int(round((len(values) - 1) * 0.95)))
    return values[index]


def _metrics(rows):
    hits = [str(row.get("direction_hit", "")).lower() == "true" for row in rows]
    adverse = [_number(row.get("max_adverse_excursion")) for row in rows]
    adverse = [value for value in adverse if value is not None]
    return {
        "direction_hit_rate": sum(hits) / len(hits) if hits else None,
        "average_excess_return": _mean(rows, "excess_return"),
        "average_target_error": _mean(rows, "target_error_pct"),
        "max_adverse_excursion": min(adverse) if adverse else None,
        "tail_target_error_p95": _p95_abs(rows, "target_error_pct"),
    }


def _format(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _status(proposal, validation_rows, valid_window_count):
    markets = {row.get("market", "") for row in validation_rows if row.get("market")}
    industries = {row.get("industry", "") for row in validation_rows if row.get("industry")}
    if len(markets) < 2 or len(industries) < 2:
        return "rejected", "market_or_industry_diversity_insufficient"
    if _number(proposal.get("adverse_excursion_delta")) is not None and _number(proposal.get("adverse_excursion_delta")) < 0:
        return "rejected", "risk_worse"
    if valid_window_count < 2:
        return "analysis_candidate", "validation_windows_insufficient"
    if (_number(proposal.get("excess_return_delta")) or 0) > 0:
        return "review_candidate", ""
    return "analysis_candidate", "improvement_insufficient"


def _is_valid_validation_window(rows):
    markets = {row.get("market", "") for row in rows if row.get("market")}
    industries = {row.get("industry", "") for row in rows if row.get("industry")}
    return len(markets) >= 2 and len(industries) >= 2


def _rows_for_weeks(rows, weeks):
    selected = set(weeks)
    return [row for row in rows if row.get("generated_date") in selected]


def summarize_shadow_windows(evaluations, proposals=None, train_size=104, validation_size=26, step=13):
    mature = [row for row in evaluations or [] if row.get("evaluation_status") == "evaluated"]
    weeks = [row.get("generated_date") for row in mature if row.get("generated_date")]
    windows = rolling_windows(weeks, train_size, validation_size, step)
    proposals = list(proposals or DEFAULT_PROPOSALS)
    valid_window_count = sum(
        1
        for _, validation_weeks in windows
        if _is_valid_validation_window(_rows_for_weeks(mature, validation_weeks))
    )
    output = []
    for index, (training_weeks, validation_weeks) in enumerate(windows, start=1):
        training_rows = _rows_for_weeks(mature, training_weeks)
        validation_rows = _rows_for_weeks(mature, validation_weeks)
        markets = sorted({row.get("market", "") for row in validation_rows if row.get("market")})
        industries = sorted({row.get("industry", "") for row in validation_rows if row.get("industry")})
        common = {
            "training_start": training_weeks[0],
            "training_end": training_weeks[-1],
            "validation_start": validation_weeks[0],
            "validation_end": validation_weeks[-1],
            "training_samples": len(training_rows),
            "validation_samples": len(validation_rows),
            "market_count": len(markets),
            "industry_count": len(industries),
            "markets": ",".join(markets),
            "industries": ",".join(industries),
            "validation_window": index,
        }
        metrics = _metrics(validation_rows)
        output.append(
            {
                **common,
                **{key: _format(value) for key, value in metrics.items()},
                "proposal_name": "formal_model",
                "parameter": "current",
                "candidate_value": "current",
                "status": "formal_baseline",
                "rejection_reason": "",
            }
        )
        for proposal in proposals:
            status, reason = _status(proposal, validation_rows, valid_window_count)
            adjusted = dict(metrics)
            adjusted["average_excess_return"] = (
                (adjusted["average_excess_return"] or 0) + (_number(proposal.get("excess_return_delta")) or 0)
            )
            adjusted["max_adverse_excursion"] = (
                (adjusted["max_adverse_excursion"] or 0) + (_number(proposal.get("adverse_excursion_delta")) or 0)
            )
            output.append(
                {
                    **common,
                    **{key: _format(value) for key, value in adjusted.items()},
                    "proposal_name": proposal.get("proposal_name", ""),
                    "parameter": proposal.get("parameter", ""),
                    "candidate_value": proposal.get("candidate_value", ""),
                    "status": status,
                    "rejection_reason": reason,
                }
            )
    return output


def _read_csv(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _atomic_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", newline="", delete=False, dir=path.parent) as handle:
            temporary = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=COMPARISON_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def _atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig") as handle:
            handle.write(text)
        Path(name).replace(path)
    finally:
        Path(name).unlink(missing_ok=True)


def _report(rows):
    review_candidates = [row for row in rows if row.get("status") == "review_candidate"]
    rejected = [row for row in rows if row.get("status") == "rejected"]
    lines = [
        "# 美股严格时点回测报告",
        "",
        f"- 比较记录数：{len(rows)}",
        f"- 复核候选数：{len(review_candidates)}",
        f"- 拒绝方案数：{len(rejected)}",
        "- 结论：样本或证据积累中，不得自动升级正式模型。",
        "",
        "| 方案 | 状态 | 验证窗口 | 验证样本 | 平均超额收益 | 最大不利波动 | 拒绝原因 |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| {proposal_name} | {status} | {validation_window} | {validation_samples} | "
            "{average_excess_return} | {max_adverse_excursion} | {rejection_reason} |".format(**row)
        )
    return "\n".join(lines) + "\n"


def run_shadow_backtest(evaluations_path, output_root):
    rows = summarize_shadow_windows(_read_csv(evaluations_path))
    output = Path(output_root)
    _atomic_csv(output / "model_comparison.csv", rows)
    _atomic_text(output / "backtest_report.md", _report(rows))
    return {"comparison_rows": len(rows)}


def main():
    parser = argparse.ArgumentParser(description="Run rolling shadow backtest")
    parser.add_argument("--evaluations", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()
    result = run_shadow_backtest(args.evaluations, args.output_root)
    print(f"Comparison rows: {result['comparison_rows']}")


if __name__ == "__main__":
    main()
