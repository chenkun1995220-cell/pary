import argparse
import csv
import json
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


HISTORY_FIELDS = [
    "market", "ticker", "date", "close", "adjusted_close", "dividend",
    "split_ratio", "source", "data_status",
]
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
HSI_CHART_URL = "https://www.hsi.com.hk/data/eng/indexes"
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def provider_symbol(market, ticker):
    market = str(market).upper()
    ticker = str(ticker).upper()
    if ticker.startswith("^"):
        return ticker
    if market == "HK" and ticker == "00011.00":
        return ticker
    if market == "US":
        return ticker.replace(".", "-")
    if market == "CN" and ticker.endswith(".SS"):
        return ticker
    if market == "CN" and ticker.endswith(".SH"):
        return ticker[:-3] + ".SS"
    if market == "CN" and ticker.endswith(".SZ"):
        return ticker
    if market == "HK" and ticker.endswith(".HK"):
        code = ticker[:-3]
        if code.isdigit():
            return f"{int(code):04d}.HK"
    raise ValueError(f"Unsupported ticker: {market} {ticker}")


def build_history_url(market, ticker):
    symbol_value = provider_symbol(market, ticker)
    if str(market).upper() == "HK" and symbol_value == "00011.00":
        return f"{HSI_CHART_URL}/{symbol_value}/chart.json"
    symbol = quote(symbol_value, safe=".-")
    query = urlencode({"range": "1y", "interval": "1d", "events": "history"})
    return f"{YAHOO_CHART_URL}/{symbol}?{query}"


def fetch_yahoo_history(url):
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_yahoo_history(market, ticker, payload):
    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise ValueError(f"Yahoo Chart error: {chart['error']}")
    results = chart.get("result") or []
    if not results:
        return []
    result = results[0]
    timestamps = result.get("timestamp") or []
    quotes = (result.get("indicators") or {}).get("quote") or []
    closes = quotes[0].get("close", []) if quotes else []
    adjusted_sets = (result.get("indicators") or {}).get("adjclose") or []
    adjusted_closes = adjusted_sets[0].get("adjclose", []) if adjusted_sets else []
    events = result.get("events") or {}
    dividends = events.get("dividends") or {}
    splits = events.get("splits") or {}
    rows = []
    for index, (timestamp, close) in enumerate(zip(timestamps, closes)):
        if close is None:
            continue
        adjusted = adjusted_closes[index] if index < len(adjusted_closes) else None
        status = "ready" if adjusted is not None else "unadjusted_fallback"
        adjusted = close if adjusted is None else adjusted
        dividend = (dividends.get(str(timestamp)) or {}).get("amount", 0.0)
        split = splits.get(str(timestamp)) or {}
        numerator = split.get("numerator", 1)
        denominator = split.get("denominator", 1)
        try:
            split_ratio = float(numerator) / float(denominator)
            if split_ratio <= 0:
                raise ValueError("invalid split")
        except (TypeError, ValueError, ZeroDivisionError):
            split_ratio = 1.0
            status = "corporate_action_review"
        rows.append(
            {
                "market": str(market).upper(),
                "ticker": str(ticker).upper(),
                "date": datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat(),
                "close": close,
                "adjusted_close": adjusted,
                "dividend": dividend,
                "split_ratio": split_ratio,
                "source": "Yahoo Chart",
                "data_status": status,
            }
        )
    return rows


def parse_hsi_official_history(market, ticker, payload):
    rows = []
    for timestamp_ms, close in payload.get("indexLevels-1y") or []:
        if close is None:
            continue
        rows.append(
            {
                "market": str(market).upper(),
                "ticker": str(ticker).upper(),
                "date": datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).date().isoformat(),
                "close": close,
                "adjusted_close": close,
                "dividend": 0.0,
                "split_ratio": 1.0,
                "source": "Hang Seng Indexes official",
                "data_status": "ready",
            }
        )
    return rows


def parse_history_payload(market, ticker, payload):
    if str(market).upper() == "HK" and provider_symbol(market, ticker) == "00011.00":
        return parse_hsi_official_history(market, ticker, payload)
    return parse_yahoo_history(market, ticker, payload)


def _load_candidates(path, market=None):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    tickers = []
    seen = set()
    for row in rows:
        provider = str(row.get("provider_symbol") or "").strip().upper()
        if provider and market and str(row.get("market") or "").strip().upper() != str(market).upper():
            continue
        ticker = str(row.get("ticker") or provider).strip().upper()
        if ticker and ticker not in seen:
            seen.add(ticker)
            tickers.append(ticker)
    return tickers


def _cache_path(cache_dir, market, ticker):
    symbol = provider_symbol(market, ticker)
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", symbol).rstrip(" .")
    if not safe_name:
        safe_name = "_"
    if safe_name.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
        safe_name = "_" + safe_name
    return Path(cache_dir) / f"{safe_name}.json"


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            json.dump(payload, stream, ensure_ascii=False)
            temporary = Path(stream.name)
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _load_fresh_cache(path, max_age_days):
    if not path.exists() or max_age_days < 0:
        return None
    now = time.time()
    modified_time = path.stat().st_mtime
    if modified_time > now + 300:
        return None
    age_seconds = max(0.0, now - modified_time)
    if age_seconds > max_age_days * 86400:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_history_csv(path, rows):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8-sig",
            newline="",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=HISTORY_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
            temporary = Path(stream.name)
        temporary.replace(output)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _fetch_with_retry(fetcher, url, max_attempts, retry_delay_seconds, sleeper):
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    for attempt in range(1, max_attempts + 1):
        try:
            return fetcher(url), attempt - 1
        except Exception:
            if attempt >= max_attempts:
                raise
            sleeper(retry_delay_seconds * attempt)


def run_price_history(
    candidates_path,
    output_path,
    cache_dir,
    market,
    minimum_coverage=0.80,
    cache_max_age_days=10,
    fail_on_cache_fallback=False,
    max_attempts=1,
    retry_delay_seconds=2,
    sleeper=None,
    fetcher=None,
):
    market = str(market).upper()
    tickers = _load_candidates(candidates_path, market)
    fetch = fetcher or fetch_yahoo_history
    all_rows = []
    covered_count = 0
    cache_fallbacks = 0
    network_retries = 0
    sleep = sleeper or time.sleep

    for ticker in tickers:
        rows = []
        used_cache = False
        try:
            cache_path = _cache_path(cache_dir, market, ticker)
            try:
                payload, ticker_retries = _fetch_with_retry(
                    fetch,
                    build_history_url(market, ticker),
                    max_attempts,
                    retry_delay_seconds,
                    sleep,
                )
                network_retries += ticker_retries
            except Exception:
                cached_payload = _load_fresh_cache(cache_path, cache_max_age_days)
                if cached_payload is not None:
                    rows = parse_history_payload(market, ticker, cached_payload)
                    used_cache = bool(rows)
            else:
                rows = parse_history_payload(market, ticker, payload)
                _write_json(cache_path, payload)
        except Exception:
            rows = []
            used_cache = False
        if used_cache:
            cache_fallbacks += 1
        if rows:
            covered_count += 1
            all_rows.extend(rows)

    candidate_count = len(tickers)
    coverage = covered_count / candidate_count if candidate_count else 1.0
    if coverage < minimum_coverage:
        raise RuntimeError(
            f"price history coverage {coverage:.2%} below required {minimum_coverage:.2%}"
        )
    if fail_on_cache_fallback and cache_fallbacks:
        raise RuntimeError(
            f"price history cache fallback used for {cache_fallbacks} ticker(s)"
        )

    _write_history_csv(output_path, all_rows)
    return {
        "candidates": candidate_count,
        "ready": covered_count,
        "output": Path(output_path),
        "cache_fallbacks": cache_fallbacks,
        "network_retries": network_retries,
        "candidate_count": candidate_count,
        "covered_count": covered_count,
        "coverage": coverage,
        "row_count": len(all_rows),
        "output_path": Path(output_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch candidate one-year price history")
    parser.add_argument("--market", required=True, choices=["US", "CN", "HK"])
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--minimum-coverage", type=float, default=0.80)
    parser.add_argument("--cache-max-age-days", type=float, default=10)
    parser.add_argument("--fail-on-cache-fallback", action="store_true")
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-delay-seconds", type=float, default=2)
    args = parser.parse_args()
    result = run_price_history(
        args.candidates,
        args.output,
        args.cache_dir,
        args.market,
        minimum_coverage=args.minimum_coverage,
        cache_max_age_days=args.cache_max_age_days,
        fail_on_cache_fallback=args.fail_on_cache_fallback,
        max_attempts=args.max_attempts,
        retry_delay_seconds=args.retry_delay_seconds,
    )
    print(f"Price history coverage: {result['ready']}/{result['candidates']}")
    print(f"Cache fallbacks: {result['cache_fallbacks']}")
    print(f"Network retries: {result['network_retries']}")
    print(f"Price history rows: {result['row_count']}")


if __name__ == "__main__":
    main()
