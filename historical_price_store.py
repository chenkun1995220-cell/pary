from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote, urlencode
from typing import Iterable, Mapping, Sequence

from candidate_price_history import (
    provider_symbol,
    YAHOO_CHART_URL,
    _cache_path,
    _load_fresh_cache,
    _write_json,
    fetch_yahoo_history,
    parse_history_payload,
)

HISTORICAL_RANGE = "5y"
HISTORICAL_INTERVAL = "1d"
HISTORICAL_EVENTS = "history"


def prices_available_as_of(rows, as_of_date):
    if rows is None:
        return []

    as_of = _to_date(as_of_date)
    if as_of is None:
        raise ValueError(f"Invalid as_of_date: {as_of_date!r}")

    parsed_rows = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        row_date = _to_date(row.get("date"), allow_none=True)
        if row_date is None or row_date > as_of:
            continue
        parsed_rows.append((row_date, row))

    return [row for _, row in sorted(parsed_rows, key=lambda item: item[0])]


def price_coverage(tickers: Iterable[str], rows: Sequence[Mapping]):
    tickers = list(tickers or [])
    if not tickers:
        return 1.0

    requested = {str(ticker).upper() for ticker in tickers}
    ready_tickers = {
        str(row.get("ticker", "")).upper()
        for row in rows
        if isinstance(row, Mapping) and str(row.get("data_status", "")) == "ready"
    }
    return len(requested.intersection(ready_tickers)) / len(requested)


def build_historical_url(ticker, range_name=HISTORICAL_RANGE):
    provider = quote(provider_symbol("US", ticker), safe=".-")
    query = urlencode(
        {"range": range_name, "interval": HISTORICAL_INTERVAL, "events": HISTORICAL_EVENTS}
    )
    return f"{YAHOO_CHART_URL}/{provider}?{query}"


def load_historical_prices(
    ticker,
    cache_dir,
    range_name=HISTORICAL_RANGE,
    cache_max_age_days=30,
    fetcher=None,
    market="US",
):
    if cache_max_age_days < 0:
        raise ValueError("cache_max_age_days must be >= 0")

    effective_fetcher = fetcher or fetch_yahoo_history
    cache_path = _cache_path(cache_dir, market, ticker)
    cache_path = Path(cache_path)
    url = build_historical_url(ticker, range_name=range_name)

    try:
        payload = effective_fetcher(url)
        rows = parse_history_payload(market, ticker, payload)
        if not rows:
            raise ValueError("No price rows from network payload")
        _write_json(cache_path, payload)
        source = "network"
    except Exception as error:
        cached_payload = _load_fresh_cache(cache_path, cache_max_age_days)
        if cached_payload is None:
            raise error

        rows = parse_history_payload(market, ticker, cached_payload)
        if not rows:
            raise error
        source = "cache_fallback"

    return {
        "ticker": str(ticker),
        "rows": rows,
        "source": source,
        "cache_path": cache_path,
    }


def _to_date(value, allow_none=False):
    if value is None:
        return None if allow_none else None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None if allow_none else None
    return None if allow_none else None
