import argparse
import csv
import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

from historical_sp500 import restore_membership


BACKTEST_MEMBERSHIP_FIELDS = [
    "week",
    "market",
    "ticker",
    "cik",
    "company_name",
    "industry",
    "gics_sub_industry",
    "date_added",
    "effective_date",
    "membership_evidence",
    "membership_source_url",
    "available_at",
]


def _read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_optional_csv(path):
    if not path:
        return []
    evidence_path = Path(path)
    if not evidence_path.exists():
        return []
    return _read_csv(evidence_path)


def _iso_date(value, field_name):
    text = str(value or "").strip()
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{field_name} must be YYYY-MM-DD: {text}") from exc
    if parsed.isoformat() != text:
        raise ValueError(f"{field_name} must be YYYY-MM-DD: {text}")
    return parsed


def _enabled(row):
    return str(row.get("enabled", "1")).strip().lower() not in {"0", "false", "no", "n"}


def _weekly_dates(weeks, end_date=None):
    count = int(weeks)
    if count <= 0:
        raise ValueError("weeks must be positive")
    end = _iso_date(end_date, "end_date") if end_date else date.today()
    return [(end - timedelta(days=7 * offset)).isoformat() for offset in range(count - 1, -1, -1)]


def _active_universe_rows(universe_rows):
    rows = []
    for row in universe_rows:
        ticker = str(row.get("ticker", "")).strip().upper()
        cik = str(row.get("cik", "")).strip()
        date_added = str(row.get("date_added", "")).strip()
        if not ticker or not cik or not date_added or not _enabled(row):
            continue
        rows.append(dict(row, ticker=ticker, cik=cik, date_added=date_added))
    if not rows:
        raise ValueError("enabled universe rows with ticker, cik and date_added are required")
    return rows


def _current_membership_map(active_rows, evidence, source_url, evidence_rows=None):
    added_events = {}
    removed_tickers = set()
    for event in evidence_rows or []:
        added_ticker = str(event.get("added_ticker", "") or "").strip().upper()
        removed_ticker = str(event.get("removed_ticker", "") or "").strip().upper()
        if added_ticker:
            added_events[added_ticker] = event
        if removed_ticker:
            removed_tickers.add(removed_ticker)

    current = {}
    for row in active_rows:
        ticker = row["ticker"]
        if ticker in removed_tickers and ticker not in added_events:
            continue
        event = added_events.get(ticker, {})
        current[ticker] = {
            "ticker": ticker,
            "company_name": row.get("company_name", ""),
            "effective_date": event.get("effective_date", row.get("date_added", "")),
            "membership_evidence": event.get("membership_evidence", evidence),
            "membership_source_url": event.get("membership_source_url", source_url),
            "_source_row": row,
        }
    return current


def _applicable_evidence_rows(evidence_rows, active_rows):
    active_tickers = {row["ticker"] for row in active_rows}
    applicable = []
    for event in evidence_rows or []:
        added_ticker = str(event.get("added_ticker", "") or "").strip().upper()
        removed_ticker = str(event.get("removed_ticker", "") or "").strip().upper()
        if added_ticker in active_tickers or (not added_ticker and removed_ticker in active_tickers):
            applicable.append(event)
    return applicable


def build_backtest_membership(
    universe_rows,
    weeks=156,
    end_date=None,
    market="US",
    evidence="secondary",
    source_url="data/config/us_universe_symbols.csv",
    company_limit=0,
    evidence_rows=None,
):
    active_rows = _active_universe_rows(universe_rows)
    limit = int(company_limit or 0)
    if limit > 0:
        active_rows = sorted(active_rows, key=lambda item: item["ticker"])[:limit]
    applicable_evidence_rows = _applicable_evidence_rows(evidence_rows, active_rows)
    week_dates = _weekly_dates(weeks, end_date=end_date)
    output = []
    for week in week_dates:
        week_date = _iso_date(week, "week")
        if applicable_evidence_rows:
            current = _current_membership_map(active_rows, evidence, source_url, applicable_evidence_rows)
            week_members = restore_membership(current, applicable_evidence_rows, week)
            active_by_ticker = {row["ticker"]: row for row in active_rows}
            week_rows = []
            for ticker, restored in sorted(week_members.items()):
                source = restored.get("_source_row") or active_by_ticker.get(ticker, {})
                if not source:
                    continue
                added = _iso_date(source.get("date_added"), "date_added")
                if added <= week_date:
                    week_rows.append((source, restored))
        else:
            week_rows = []
            for row in sorted(active_rows, key=lambda item: item["ticker"]):
                added = _iso_date(row.get("date_added"), "date_added")
                if added <= week_date:
                    week_rows.append(
                        (
                            row,
                            {
                                "effective_date": row.get("date_added", ""),
                                "membership_evidence": evidence,
                                "membership_source_url": source_url,
                            },
                        )
                    )
        for row, restored in week_rows:
            output.append(
                {
                    "week": week,
                    "market": str(market).upper(),
                    "ticker": row["ticker"],
                    "cik": row["cik"],
                    "company_name": row.get("company_name", ""),
                    "industry": row.get("industry", ""),
                    "gics_sub_industry": row.get("gics_sub_industry", ""),
                    "date_added": row.get("date_added", ""),
                    "effective_date": restored.get("effective_date", row.get("date_added", "")),
                    "membership_evidence": restored.get("membership_evidence", evidence),
                    "membership_source_url": restored.get("membership_source_url", source_url),
                    "available_at": week,
                }
            )
    if not output:
        raise ValueError("backtest membership output is empty")
    return output


def write_backtest_membership_csv(path, rows):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    raw_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    descriptor_owned = True
    try:
        stream = os.fdopen(raw_descriptor, "w", encoding="utf-8-sig", newline="")
        descriptor_owned = False
        with stream:
            writer = csv.DictWriter(stream, fieldnames=BACKTEST_MEMBERSHIP_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary_name, destination)
    except Exception:
        if descriptor_owned:
            try:
                os.close(raw_descriptor)
            except OSError:
                pass
        Path(temporary_name).unlink(missing_ok=True)
        raise


def prepare_backtest_membership(
    universe_config,
    output,
    weeks=156,
    end_date=None,
    market="US",
    company_limit=0,
    evidence_pack=None,
):
    rows = build_backtest_membership(
        _read_csv(universe_config),
        weeks=weeks,
        end_date=end_date,
        market=market,
        source_url=str(universe_config),
        company_limit=company_limit,
        evidence_rows=_read_optional_csv(evidence_pack),
    )
    write_backtest_membership_csv(output, rows)
    return {"rows": len(rows), "weeks": len({row["week"] for row in rows}), "output": Path(output)}


def main():
    parser = argparse.ArgumentParser(description="Prepare conservative weekly S&P 500 membership inputs for backtests.")
    parser.add_argument("--universe-config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--weeks", type=int, default=156)
    parser.add_argument("--end-date")
    parser.add_argument("--market", default="US")
    parser.add_argument("--max-companies", type=int, default=0)
    parser.add_argument("--evidence-pack")
    args = parser.parse_args()
    result = prepare_backtest_membership(
        args.universe_config,
        args.output,
        weeks=args.weeks,
        end_date=args.end_date,
        market=args.market,
        company_limit=args.max_companies,
        evidence_pack=args.evidence_pack,
    )
    print(f"Backtest membership weeks: {result['weeks']}")
    print(f"Backtest membership rows: {result['rows']}")
    print(f"Output: {result['output']}")


if __name__ == "__main__":
    main()
