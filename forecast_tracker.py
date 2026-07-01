import argparse
import csv
import math
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path


CHECKPOINTS = {1: 7, 4: 28, 12: 84, 26: 182, 52: 364}
EVALUATION_VERSION = "forecast_eval_v1"
TRACKING_FIELDS = [
    "market", "ticker", "company_name", "generated_date", "model_version",
    "as_of_date", "checkpoint_weeks", "prediction_horizon", "prediction_signal",
    "evaluation_status", "predicted_direction",
    "actual_direction", "direction_hit", "start_price", "actual_price",
    "target_price", "actual_return", "benchmark_return", "excess_return",
    "target_error", "target_error_pct", "max_favorable_excursion",
    "max_adverse_excursion", "valuation_confidence", "evaluation_version",
]


def _day(value):
    return date.fromisoformat(str(value))


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def due_checkpoints(generated_date, as_of_date):
    elapsed = (_day(as_of_date) - _day(generated_date)).days
    return [weeks for weeks, days in CHECKPOINTS.items() if elapsed >= days]


def latest_on_or_before(rows, target_date, tolerance_days=7):
    target = _day(target_date)
    eligible = []
    for row in rows:
        try:
            row_date = _day(row.get("date"))
        except (TypeError, ValueError):
            continue
        if row_date <= target:
            eligible.append((row_date, row))
    if not eligible:
        return None
    selected_date, selected = max(eligible, key=lambda item: item[0])
    return selected if (target - selected_date).days <= tolerance_days else None


def _direction(value):
    if value is None:
        return "unknown"
    if value > 0.05:
        return "up"
    if value < -0.05:
        return "down"
    return "neutral"


def _direction_from_signal(value):
    text = str(value or "").strip().lower()
    if not text:
        return "unknown"
    if text in {"up", "upward", "bullish"}:
        return "up"
    if text in {"down", "downward", "bearish"}:
        return "down"
    if text in {"neutral", "flat", "sideways"}:
        return "neutral"
    if "数据不足" in text or "insufficient" in text:
        return "unknown"
    if "上行" in text or "偏强" in text:
        return "up"
    if "下行" in text or "偏弱" in text:
        return "down"
    if "震荡" in text or "中性" in text:
        return "neutral"
    return "unknown"


def _prediction_direction(forecast, checkpoint_weeks):
    if checkpoint_weeks == 1:
        signal = forecast.get("one_week_expected_direction", "")
        return "1w", signal, _direction_from_signal(signal)
    if checkpoint_weeks == 4 and forecast.get("one_month_expected_direction"):
        signal = forecast.get("one_month_expected_direction", "")
        return "1m", signal, _direction_from_signal(signal)
    expected_return = _number(forecast.get("expected_return"))
    return "12m", "expected_return", _direction(expected_return)


def _adjusted(row):
    return _number(row.get("adjusted_close") or row.get("close")) if row else None


def evaluate_forecast(forecast, stock_prices, benchmark_prices, as_of_date, checkpoint_weeks=None):
    generated = _day(forecast.get("generated_date"))
    target_day = (
        generated + timedelta(days=CHECKPOINTS[checkpoint_weeks])
        if checkpoint_weeks else _day(as_of_date)
    )
    target_text = target_day.isoformat()
    start = latest_on_or_before(stock_prices, generated.isoformat())
    actual = latest_on_or_before(stock_prices, target_text)
    interval = [
        row for row in stock_prices
        if row.get("date") and generated <= _day(row["date"]) <= target_day
    ]
    base = {
        "market": forecast.get("market", ""),
        "ticker": forecast.get("ticker", ""),
        "company_name": forecast.get("company_name", ""),
        "generated_date": forecast.get("generated_date", ""),
        "model_version": forecast.get("model_version", ""),
        "as_of_date": as_of_date,
        "checkpoint_weeks": checkpoint_weeks or "",
        "valuation_confidence": forecast.get("valuation_confidence", ""),
        "evaluation_version": EVALUATION_VERSION,
    }
    prediction_horizon, prediction_signal, predicted_direction = _prediction_direction(
        forecast, checkpoint_weeks
    )
    base.update({
        "prediction_horizon": prediction_horizon,
        "prediction_signal": prediction_signal,
    })
    if any(row.get("data_status") == "corporate_action_review" for row in interval):
        return {**base, "evaluation_status": "corporate_action_review"}
    start_price, actual_price = _adjusted(start), _adjusted(actual)
    if not start_price or not actual_price:
        return {**base, "evaluation_status": "insufficient_data"}

    actual_return = actual_price / start_price - 1.0
    benchmark_start = latest_on_or_before(benchmark_prices, generated.isoformat())
    benchmark_actual = latest_on_or_before(benchmark_prices, target_text)
    benchmark_start_price = _adjusted(benchmark_start)
    benchmark_actual_price = _adjusted(benchmark_actual)
    benchmark_return = None
    if benchmark_start_price and benchmark_actual_price:
        benchmark_return = benchmark_actual_price / benchmark_start_price - 1.0
    expected_return = _number(forecast.get("expected_return"))
    target_price = _number(forecast.get("target_price"))
    prices = [_adjusted(row) for row in interval]
    prices = [value for value in prices if value is not None]
    actual_direction = _direction(actual_return)
    status = "evaluated" if checkpoint_weeks else "tracking"
    if checkpoint_weeks and predicted_direction == "unknown":
        status = "prediction_unavailable"
    result = {
        **base,
        "evaluation_status": status,
        "predicted_direction": predicted_direction,
        "actual_direction": actual_direction,
        "direction_hit": predicted_direction == actual_direction if predicted_direction != "unknown" else "",
        "start_price": start_price,
        "actual_price": actual_price,
        "target_price": target_price,
        "actual_return": actual_return,
        "benchmark_return": benchmark_return,
        "excess_return": actual_return - benchmark_return if benchmark_return is not None else None,
        "target_error": actual_price - target_price if target_price else None,
        "target_error_pct": abs(actual_price - target_price) / target_price if target_price else None,
        "max_favorable_excursion": max(prices) / start_price - 1.0 if prices else None,
        "max_adverse_excursion": min(prices) / start_price - 1.0 if prices else None,
    }
    return result


def _read_csv(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _atomic_csv(path, rows):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", newline="", delete=False, dir=path.parent) as handle:
            temp = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=TRACKING_FIELDS, extrasaction="ignore")
            writer.writeheader(); writer.writerows(rows)
        temp.replace(path)
    finally:
        if temp and temp.exists(): temp.unlink()


def _atomic_text(path, text):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig") as handle: handle.write(text)
        Path(name).replace(path)
    finally:
        Path(name).unlink(missing_ok=True)


def run_forecast_tracking(forecasts_path, stock_history_path, benchmark_history_path,
                          output_root, market, as_of_date=None):
    as_of_date = as_of_date or date.today().isoformat()
    forecasts = _read_csv(forecasts_path)
    stock_rows = _read_csv(stock_history_path)
    benchmark_rows = _read_csv(benchmark_history_path)
    by_ticker = {}
    for row in stock_rows:
        by_ticker.setdefault(row.get("ticker", "").upper(), []).append(row)
    tracking, new_evaluations = [], []
    for forecast in forecasts:
        prices = by_ticker.get(forecast.get("ticker", "").upper(), [])
        tracking.append(evaluate_forecast(forecast, prices, benchmark_rows, as_of_date))
        for weeks in due_checkpoints(forecast.get("generated_date"), as_of_date):
            new_evaluations.append(evaluate_forecast(forecast, prices, benchmark_rows, as_of_date, weeks))
    output = Path(output_root)
    _atomic_csv(output / "tracking_snapshot.csv", tracking)
    existing = _read_csv(output / "forecast_evaluations.csv")
    def key(row):
        return (row.get("market"), row.get("ticker"), row.get("generated_date"),
                row.get("model_version"), str(row.get("checkpoint_weeks")), row.get("evaluation_version"))
    merged = {key(row): row for row in existing}
    for row in new_evaluations: merged.setdefault(key(row), row)
    evaluations = sorted(merged.values(), key=lambda row: (row.get("generated_date", ""), row.get("ticker", ""), str(row.get("checkpoint_weeks", ""))))
    _atomic_csv(output / "forecast_evaluations.csv", evaluations)
    mature = [row for row in evaluations if row.get("evaluation_status") == "evaluated"]
    hits = [row for row in mature if str(row.get("direction_hit")).lower() == "true"]
    one_week = [row for row in mature if row.get("prediction_horizon") == "1w"]
    one_month = [row for row in mature if row.get("prediction_horizon") == "1m"]
    unavailable = [row for row in evaluations if row.get("evaluation_status") == "prediction_unavailable"]
    lines = [
        f"# {as_of_date} 预测表现跟踪报告",
        "",
        f"- 市场：{market}",
        f"- 跟踪预测：{len(tracking)}",
        f"- 成熟评价：{len(mature)}",
        f"- 1周成熟评估：{len(one_week)}",
        f"- 1个月成熟评估：{len(one_month)}",
        f"- 预测字段缺失未评估：{len(unavailable)}",
    ]
    if mature:
        lines.append(f"- 方向命中率：{len(hits) / len(mature):.2%}")
    else:
        lines.append("- 评价状态：样本积累中")
    for label, rows in (("1周", one_week), ("1个月", one_month)):
        if rows:
            row_hits = [row for row in rows if str(row.get("direction_hit")).lower() == "true"]
            lines.append(f"- {label}方向命中率：{len(row_hits) / len(rows):.2%}")
    _atomic_text(output / "performance_report.md", "\n".join(lines) + "\n")
    return {"tracking": len(tracking), "evaluations": len(evaluations), "mature": len(mature)}


def main():
    parser = argparse.ArgumentParser(description="Track forecast performance")
    parser.add_argument("--market", required=True)
    parser.add_argument("--forecasts", required=True)
    parser.add_argument("--stock-history", required=True)
    parser.add_argument("--benchmark-history", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--as-of-date")
    args = parser.parse_args()
    result = run_forecast_tracking(args.forecasts, args.stock_history, args.benchmark_history,
                                   args.output_root, args.market, args.as_of_date)
    print(f"Tracking rows: {result['tracking']}")
    print(f"Mature evaluations: {result['mature']}")


if __name__ == "__main__":
    main()
