import math
import statistics
import argparse
import csv
import os
import tempfile
from datetime import date
from pathlib import Path


MODEL_VERSION = "valuation_trend_v1"
TARGET_FIELDS = [
    "market", "ticker", "company_name", "currency", "current_price",
    "target_price", "buy_price", "expected_return", "pe_fair_price",
    "pb_fair_price", "fcf_fair_price", "quality_factor",
    "margin_of_safety", "trend_label", "trend_confidence",
    "one_week_trend_label", "one_week_trend_confidence", "one_week_expected_direction",
    "one_month_trend_label", "one_month_trend_confidence", "one_month_expected_direction",
    "valuation_confidence", "valuation_status", "price_action", "reason",
    "price_date", "financial_report_date", "generated_date", "model_version",
]


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _clamp(value, lower, upper):
    return max(lower, min(upper, value))


def _floor_money(value):
    return math.floor(value * 100.0 + 1e-9) / 100.0


def _quality_factor(row):
    maxima = {
        "profitability_score": 25.0,
        "balance_sheet_score": 15.0,
        "cash_flow_score": 15.0 if _number(row.get("fcf_yield")) is not None else 10.0,
        "growth_score": 10.0,
    }
    weights = {
        "profitability_score": 0.35,
        "balance_sheet_score": 0.20,
        "cash_flow_score": 0.25,
        "growth_score": 0.20,
    }
    ratios = []
    for field, maximum in maxima.items():
        value = _number(row.get(field))
        if value is not None:
            ratios.append((_clamp(value / maximum, 0.0, 1.0), weights[field]))
    if not ratios:
        return 1.0
    weight_sum = sum(weight for _, weight in ratios)
    quality = sum(value * weight for value, weight in ratios) / weight_sum
    return _clamp(0.85 + 0.25 * quality, 0.85, 1.10)


def _lower_confidence(*levels):
    rank = {"low": 0, "medium": 1, "high": 2}
    valid = [level for level in levels if level in rank]
    return min(valid, key=rank.get) if valid else "low"


def value_candidate(row, trend):
    price = _number(row.get("price") or row.get("current_price"))
    if price is None or price <= 0:
        return {
            "valuation_status": "insufficient_data",
            "target_price": None,
            "buy_price": None,
            "valuation_confidence": "low",
            "margin_of_safety": 0.30,
        }

    pe = _number(row.get("pe"))
    pb = _number(row.get("pb"))
    industry_pe = _number(row.get("industry_pe_median"))
    industry_pb = _number(row.get("industry_pb_median"))
    fcf_yield = _number(row.get("fcf_yield"))

    fair_values = {}
    if pe is not None and pe > 0 and industry_pe is not None and industry_pe > 0:
        fair_values["pe"] = price * _clamp(industry_pe, 5.0, 40.0) / pe
    if pb is not None and pb > 0 and industry_pb is not None and industry_pb > 0:
        fair_values["pb"] = price * _clamp(industry_pb, 0.5, 8.0) / pb
    if fcf_yield is not None and fcf_yield > 0:
        fair_values["fcf"] = price * fcf_yield / 0.05
    fair_values = {
        key: value for key, value in fair_values.items()
        if math.isfinite(value) and value > 0
    }

    base_weights = {"pe": 0.50, "pb": 0.30, "fcf": 0.20}
    weight_sum = sum(base_weights[key] for key in fair_values)
    if not fair_values or weight_sum <= 0:
        return {
            "valuation_status": "insufficient_data",
            "target_price": None,
            "buy_price": None,
            "valuation_confidence": "low",
            "margin_of_safety": 0.30,
            "pe_weight_used": 0.0,
            "pb_weight_used": 0.0,
            "fcf_weight_used": 0.0,
        }

    used_weights = {
        key: (base_weights[key] / weight_sum if key in fair_values else 0.0)
        for key in base_weights
    }
    weighted_fair = sum(fair_values[key] * used_weights[key] for key in fair_values)
    quality_factor = _quality_factor(row)
    target_price = min(weighted_fair * quality_factor, price * 1.60)

    confidence = _lower_confidence(
        row.get("confidence", "low"), trend.get("confidence", "low")
    )
    dispersion = max(fair_values.values()) / min(fair_values.values())
    if len(fair_values) < 2 or dispersion > 2.5:
        confidence = "low"
    margin = {"high": 0.20, "medium": 0.25, "low": 0.30}[confidence]
    displayed_target = _floor_money(target_price)
    displayed_buy = _floor_money(displayed_target * (1.0 - margin))

    if target_price <= price:
        price_action = "\u7b49\u5f85\u56de\u8c03/\u5f53\u524d\u65e0\u5b89\u5168\u8fb9\u9645"
    elif price <= displayed_buy:
        price_action = "\u8fbe\u5230\u5efa\u8bae\u4e70\u5165\u533a\u95f4"
    else:
        price_action = "\u7b49\u5f85\u56de\u8c03"

    return {
        "valuation_status": "ready",
        "target_price": displayed_target,
        "buy_price": displayed_buy,
        "expected_return": round(displayed_target / price - 1.0, 6),
        "pe_fair_price": round(fair_values["pe"], 2) if "pe" in fair_values else None,
        "pb_fair_price": round(fair_values["pb"], 2) if "pb" in fair_values else None,
        "fcf_fair_price": round(fair_values["fcf"], 2) if "fcf" in fair_values else None,
        "pe_weight_used": used_weights["pe"],
        "pb_weight_used": used_weights["pb"],
        "fcf_weight_used": used_weights["fcf"],
        "quality_factor": round(quality_factor, 6),
        "valuation_confidence": confidence,
        "margin_of_safety": margin,
        "price_action": price_action,
        "valuation_dispersion": round(dispersion, 6),
    }


def _clean_closes(closes):
    cleaned = []
    try:
        iterator = iter(closes)
    except TypeError:
        return cleaned
    for value in iterator:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            cleaned.append(number)
    return cleaned


def _moving_average(values, period):
    if len(values) < period:
        return None
    window = values[-period:]
    scale = max(abs(value) for value in window)
    if scale == 0:
        return 0.0
    average = math.fsum(value / scale for value in window) / period * scale
    return average if math.isfinite(average) else None


def _rate_of_change(current, previous):
    if previous == 0:
        return None
    try:
        result = current / previous - 1
    except (OverflowError, ZeroDivisionError):
        return None
    return result if math.isfinite(result) else None


def _annualized_volatility(values):
    returns = []
    for previous, current in zip(values, values[1:]):
        daily_return = _rate_of_change(current, previous)
        if daily_return is not None:
            returns.append(daily_return)
    if len(returns) < 2:
        return 0.0
    try:
        volatility = statistics.stdev(returns) * math.sqrt(252)
    except (OverflowError, statistics.StatisticsError):
        return 0.0
    return volatility if math.isfinite(volatility) else 0.0


def _short_horizon_trend(values, period, mild_threshold, strong_threshold, high_confidence_observations):
    if len(values) < period + 1:
        return {
            "trend_label": "数据不足",
            "confidence": "low",
            "expected_direction": "数据不足",
            "momentum": None,
        }
    momentum = _rate_of_change(values[-1], values[-period - 1])
    if momentum is None:
        return {
            "trend_label": "数据不足",
            "confidence": "low",
            "expected_direction": "数据不足",
            "momentum": None,
        }
    if momentum >= strong_threshold:
        trend_label = "偏强"
        expected_direction = "上行"
    elif momentum >= mild_threshold:
        trend_label = "温和偏强"
        expected_direction = "震荡偏强"
    elif momentum <= -strong_threshold:
        trend_label = "偏弱"
        expected_direction = "下行"
    elif momentum <= -mild_threshold:
        trend_label = "偏弱"
        expected_direction = "震荡偏弱"
    else:
        trend_label = "中性"
        expected_direction = "震荡"
    confidence = "high" if len(values) >= high_confidence_observations else "medium"
    return {
        "trend_label": trend_label,
        "confidence": confidence,
        "expected_direction": expected_direction,
        "momentum": momentum,
    }


def calculate_trend(closes):
    values = _clean_closes(closes)
    observations = len(values)
    latest = values[-1] if values else None
    ma20 = _moving_average(values, 20)
    ma60 = _moving_average(values, 60)
    ma120 = _moving_average(values, 120)

    window_52w = values[-252:]
    momentum = None
    if len(window_52w) >= 2:
        momentum = _rate_of_change(window_52w[-1], window_52w[0])

    high_52w = max(window_52w) if window_52w else None
    low_52w = min(window_52w) if window_52w else None
    position_52w = None
    if window_52w:
        spread = high_52w - low_52w
        if spread == 0:
            position_52w = 0.5
        elif math.isfinite(spread):
            position_52w = (latest - low_52w) / spread
        else:
            scale = max(abs(high_52w), abs(low_52w), abs(latest))
            scaled_spread = high_52w / scale - low_52w / scale
            position_52w = (latest / scale - low_52w / scale) / scaled_spread
        if not math.isfinite(position_52w):
            position_52w = None

    if observations < 60:
        trend_label = "数据不足"
        confidence = "low"
    else:
        confidence = "high" if observations >= 120 else "medium"
        if (
            observations >= 120
            and latest > ma20 > ma60 > ma120
            and momentum is not None
            and momentum > 0.10
        ):
            trend_label = "偏强"
        elif latest > ma60 and momentum is not None and momentum > 0:
            trend_label = "温和偏强"
        elif latest < ma60 and momentum is not None and momentum < -0.10:
            trend_label = "偏弱"
        else:
            trend_label = "中性"

    one_week = _short_horizon_trend(
        values, period=5, mild_threshold=0.008, strong_threshold=0.03, high_confidence_observations=20
    )
    one_month = _short_horizon_trend(
        values, period=21, mild_threshold=0.015, strong_threshold=0.05, high_confidence_observations=60
    )

    return {
        "observations": observations,
        "latest_close": latest,
        "ma20": ma20,
        "ma60": ma60,
        "ma120": ma120,
        "momentum_12m": momentum,
        "annualized_volatility": _annualized_volatility(values),
        "high_52w": high_52w,
        "low_52w": low_52w,
        "position_52w": position_52w,
        "trend_label": trend_label,
        "confidence": confidence,
        "one_week_trend_label": one_week["trend_label"],
        "one_week_trend_confidence": one_week["confidence"],
        "one_week_expected_direction": one_week["expected_direction"],
        "one_week_momentum": one_week["momentum"],
        "one_month_trend_label": one_month["trend_label"],
        "one_month_trend_confidence": one_month["confidence"],
        "one_month_expected_direction": one_month["expected_direction"],
        "one_month_momentum": one_month["momentum"],
    }


def _read_csv(path):
    if not path or not Path(path).exists():
        return []
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _atomic_write_csv(path, rows, fieldnames):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8-sig", newline="", delete=False,
            dir=path.parent, prefix=path.name + ".", suffix=".tmp"
        ) as handle:
            temporary = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def _atomic_write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        fd, name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
        temporary = Path(name)
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as handle:
            handle.write(text)
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def _merge_inputs(candidates, medians, quotes):
    median_map = {
        (row.get("market", ""), row.get("industry", "")): row for row in medians
    }
    quote_map = {row.get("ticker", "").upper(): row for row in quotes}
    merged = []
    for source in candidates:
        row = dict(source)
        ticker = row.get("ticker", "").upper()
        quote_row = quote_map.get(ticker, {})
        if not row.get("price"):
            row["price"] = quote_row.get("price", "")
        if not row.get("currency"):
            row["currency"] = quote_row.get("currency", "")
        median = median_map.get((row.get("market", ""), row.get("industry", "")), {})
        for field in ("industry_pe_median", "industry_pb_median"):
            if not row.get(field):
                row[field] = median.get(field, "")
        row["quote_date"] = row.get("quote_date") or quote_row.get("quote_date", "")
        merged.append(row)
    return merged


def _format_reason(result, trend):
    if result.get("valuation_status") != "ready":
        return "估值输入不足，暂不提供目标价"
    return (
        f"混合估值目标价 {result['target_price']}；"
        f"安全边际 {result['margin_of_safety']:.0%}；"
        f"走势 {trend.get('trend_label', '数据不足')}；"
        f"估值置信度 {result['valuation_confidence']}"
    )


def run_candidate_valuation(
    candidates_path, price_history_path, output_root, market,
    industry_medians_path=None, quotes_path=None, generated_date=None,
):
    generated_date = generated_date or date.today().isoformat()
    output = Path(output_root)
    candidates = _merge_inputs(
        _read_csv(candidates_path), _read_csv(industry_medians_path), _read_csv(quotes_path)
    )
    history_rows = _read_csv(price_history_path)
    history_by_ticker = {}
    for item in history_rows:
        ticker = item.get("ticker", "").upper()
        close = _number(item.get("close"))
        if ticker and close is not None:
            history_by_ticker.setdefault(ticker, []).append((item.get("date", ""), close))

    results = []
    for candidate in candidates:
        ticker = candidate.get("ticker", "").upper()
        prices = sorted(history_by_ticker.get(ticker, []), key=lambda item: item[0])
        trend = calculate_trend([close for _, close in prices])
        valuation = value_candidate(candidate, trend)
        current_price = _number(candidate.get("price"))
        row = {
            "market": candidate.get("market") or market,
            "ticker": ticker,
            "company_name": candidate.get("company_name", ""),
            "currency": candidate.get("currency", ""),
            "current_price": current_price,
            "target_price": valuation.get("target_price"),
            "buy_price": valuation.get("buy_price"),
            "expected_return": valuation.get("expected_return"),
            "pe_fair_price": valuation.get("pe_fair_price"),
            "pb_fair_price": valuation.get("pb_fair_price"),
            "fcf_fair_price": valuation.get("fcf_fair_price"),
            "quality_factor": valuation.get("quality_factor"),
            "margin_of_safety": valuation.get("margin_of_safety"),
            "trend_label": trend.get("trend_label"),
            "trend_confidence": trend.get("confidence"),
            "one_week_trend_label": trend.get("one_week_trend_label"),
            "one_week_trend_confidence": trend.get("one_week_trend_confidence"),
            "one_week_expected_direction": trend.get("one_week_expected_direction"),
            "one_month_trend_label": trend.get("one_month_trend_label"),
            "one_month_trend_confidence": trend.get("one_month_trend_confidence"),
            "one_month_expected_direction": trend.get("one_month_expected_direction"),
            "valuation_confidence": valuation.get("valuation_confidence", "low"),
            "valuation_status": valuation.get("valuation_status", "insufficient_data"),
            "price_action": valuation.get("price_action", ""),
            "price_date": prices[-1][0] if prices else candidate.get("quote_date", ""),
            "financial_report_date": candidate.get("financial_report_date", ""),
            "generated_date": generated_date,
            "model_version": MODEL_VERSION,
        }
        row["reason"] = _format_reason(valuation, trend)
        results.append(row)

    _atomic_write_csv(output / "valuation_targets.csv", results, TARGET_FIELDS)
    history_path = output / "forecast_history.csv"
    existing = _read_csv(history_path)
    keyed = {
        (row.get("market"), row.get("ticker"), row.get("generated_date"), row.get("model_version")): row
        for row in existing
    }
    for row in results:
        key = (row["market"], row["ticker"], row["generated_date"], row["model_version"])
        keyed[key] = row
    forecast_rows = sorted(keyed.values(), key=lambda row: (row.get("generated_date", ""), row.get("market", ""), row.get("ticker", "")))
    _atomic_write_csv(history_path, forecast_rows, TARGET_FIELDS)

    lines = [
        f"# {generated_date} 12个月目标价与走势报告", "",
        f"- 市场：{market}", f"- 候选数量：{len(results)}",
        f"- 模型版本：{MODEL_VERSION}",
        "- 说明：仅供研究筛选，不构成投资建议。", "",
        "| 股票 | 公司 | 当前价 | 目标价 | 建议买入价 | 预期收益率 | 12个月走势 | 1周走势 | 1个月走势 | 置信度 | 理由 |",
        "|---|---|---:|---:|---:|---:|---|---|---|---|---|",
    ]
    for row in results:
        expected = row.get("expected_return")
        expected_text = f"{float(expected):.1%}" if expected not in (None, "") else "-"
        lines.append(
            f"| {row['ticker']} | {row['company_name']} | {row['current_price'] or '-'} | "
            f"{row['target_price'] or '-'} | {row['buy_price'] or '-'} | {expected_text} | "
            f"{row['trend_label']} | "
            f"{row['one_week_expected_direction']} / {row['one_week_trend_label']} | "
            f"{row['one_month_expected_direction']} / {row['one_month_trend_label']} | "
            f"{row['valuation_confidence']} | {row['reason']} |"
        )
    if not results:
        lines.append("| - | 本期无候选 | - | - | - | - | - | - | - | - | - |")
    _atomic_write_text(output / "valuation_report.md", "\n".join(lines) + "\n")
    return {
        "rows": len(results),
        "ready": sum(row["valuation_status"] == "ready" for row in results),
        "output_root": output,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate 12-month valuation targets")
    parser.add_argument("--market", required=True, choices=("US", "CN", "HK"))
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--price-history", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--industry-medians")
    parser.add_argument("--quotes")
    parser.add_argument("--generated-date")
    args = parser.parse_args()
    result = run_candidate_valuation(
        args.candidates, args.price_history, args.output_root, args.market,
        args.industry_medians, args.quotes, args.generated_date,
    )
    print(f"Valuation rows: {result['rows']}")
    print(f"Valuation ready: {result['ready']}")


if __name__ == "__main__":
    main()
