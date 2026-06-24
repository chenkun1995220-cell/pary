import argparse
import csv
import tempfile
from pathlib import Path

from candidate_price_history import HISTORY_FIELDS
from historical_price_store import load_historical_prices


BACKTEST_HISTORY_FIELDS = HISTORY_FIELDS + ["available_at"]


def _read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _atomic_history_csv(path, rows):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8-sig",
            newline="",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=BACKTEST_HISTORY_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            temporary = Path(handle.name)
        temporary.replace(output)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _membership_tickers(membership_rows, market):
    requested_market = str(market).upper()
    seen = set()
    tickers = []
    for row in membership_rows:
        row_market = str(row.get("market", "")).strip().upper()
        if row_market and row_market != requested_market:
            continue
        ticker = str(row.get("ticker", "")).strip().upper()
        if ticker and ticker not in seen:
            seen.add(ticker)
            tickers.append(ticker)
    return sorted(tickers)


def _benchmark_symbol(config_path, market):
    requested_market = str(market).upper()
    for row in _read_csv(config_path):
        if str(row.get("market", "")).strip().upper() == requested_market:
            symbol = str(row.get("provider_symbol", "")).strip()
            if symbol:
                return symbol
    raise ValueError(f"benchmark provider_symbol not configured for market {requested_market}")


def _with_available_at(rows):
    normalized = []
    for row in rows:
        copy = dict(row)
        copy["available_at"] = str(copy.get("available_at") or copy.get("date") or "")
        normalized.append(copy)
    return normalized


def _sort_history(rows):
    return sorted(rows, key=lambda row: (str(row.get("ticker", "")), str(row.get("date", ""))))


def prepare_historical_price_inputs(
    membership_path,
    output_root,
    cache_dir,
    benchmark_config_path,
    market="US",
    range_name="5y",
    minimum_coverage=0.80,
    cache_max_age_days=30,
    fetcher=None,
):
    market = str(market).upper()
    output = Path(output_root)
    cache = Path(cache_dir)
    tickers = _membership_tickers(_read_csv(membership_path), market)
    benchmark = _benchmark_symbol(benchmark_config_path, market)

    all_price_rows = []
    failures = []
    covered_count = 0
    cache_fallbacks = 0
    for ticker in tickers:
        try:
            result = load_historical_prices(
                ticker,
                cache / "price_history",
                range_name=range_name,
                cache_max_age_days=cache_max_age_days,
                fetcher=fetcher,
                market=market,
            )
        except Exception as exc:
            failures.append({"ticker": ticker, "error": str(exc)})
            continue
        covered_count += 1
        if result["source"] == "cache_fallback":
            cache_fallbacks += 1
        all_price_rows.extend(_with_available_at(result["rows"]))

    candidate_count = len(tickers)
    coverage = covered_count / candidate_count if candidate_count else 1.0
    if coverage < minimum_coverage:
        raise RuntimeError(f"price history coverage {coverage:.2%} below required {minimum_coverage:.2%}")

    benchmark_result = load_historical_prices(
        benchmark,
        cache / "benchmark_history",
        range_name=range_name,
        cache_max_age_days=cache_max_age_days,
        fetcher=fetcher,
        market=market,
    )
    benchmark_rows = _with_available_at(benchmark_result["rows"])

    _atomic_history_csv(output / "price_history.csv", _sort_history(all_price_rows))
    _atomic_history_csv(output / "benchmark_history.csv", _sort_history(benchmark_rows))
    return {
        "candidate_count": candidate_count,
        "covered_count": covered_count,
        "coverage": coverage,
        "row_count": len(all_price_rows),
        "benchmark": benchmark,
        "benchmark_rows": len(benchmark_rows),
        "cache_fallbacks": cache_fallbacks,
        "failures": failures,
        "output_root": output,
    }


def main():
    parser = argparse.ArgumentParser(description="Prepare historical price inputs for US point-in-time backtests.")
    parser.add_argument("--membership", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--benchmark-config", required=True)
    parser.add_argument("--market", default="US")
    parser.add_argument("--range", dest="range_name", default="5y")
    parser.add_argument("--minimum-coverage", type=float, default=0.80)
    parser.add_argument("--cache-max-age-days", type=float, default=30)
    args = parser.parse_args()
    result = prepare_historical_price_inputs(
        args.membership,
        args.output_root,
        args.cache_dir,
        args.benchmark_config,
        market=args.market,
        range_name=args.range_name,
        minimum_coverage=args.minimum_coverage,
        cache_max_age_days=args.cache_max_age_days,
    )
    print(f"Backtest price coverage: {result['covered_count']}/{result['candidate_count']}")
    print(f"Backtest price rows: {result['row_count']}")
    print(f"Benchmark rows: {result['benchmark_rows']}")
    print(f"Cache fallbacks: {result['cache_fallbacks']}")


if __name__ == "__main__":
    main()
