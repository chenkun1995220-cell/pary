import csv
import os
import re
import tempfile
from copy import deepcopy
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from sp500_constituents import normalize_ticker


EVIDENCE_LEVELS = {"verified", "secondary", "insufficient"}
MEMBERSHIP_FIELDS = [
    "week",
    "ticker",
    "company_name",
    "effective_date",
    "membership_evidence",
    "membership_source_url",
]


def _iso_date(value, field_name):
    text = str(value or "").strip()
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid ISO date (YYYY-MM-DD): {text}") from exc
    if parsed.isoformat() != text:
        raise ValueError(f"{field_name} must be a valid ISO date (YYYY-MM-DD): {text}")
    return text


def _evidence(value, field_name):
    level = str(value or "").strip().lower()
    if level not in EVIDENCE_LEVELS:
        raise ValueError(f"{field_name} has invalid evidence level: {value}")
    return level


def _is_official_spglobal_source(url):
    try:
        parsed = urlparse(str(url or "").strip())
        hostname = (parsed.hostname or "").lower()
        return (
            parsed.scheme.lower() == "https"
            and parsed.username is None
            and parsed.password is None
            and parsed.port in {None, 443}
            and (hostname == "spglobal.com" or hostname.endswith(".spglobal.com"))
        )
    except ValueError:
        return False


def _trusted_evidence(level, source_url):
    if level == "verified" and not _is_official_spglobal_source(source_url):
        return "secondary"
    return level


def _event_value(event, primary, alias, default=""):
    if primary in event:
        return event.get(primary, default)
    return event.get(alias, default)


def _normalize_event(raw_event, position):
    event = deepcopy(raw_event)
    source_url = str(
        _event_value(event, "membership_source_url", "source_url") or ""
    ).strip()
    evidence = _evidence(
        _event_value(event, "membership_evidence", "evidence", "insufficient"),
        f"event {position} membership_evidence",
    )
    normalized = {
        "effective_date": _iso_date(event.get("effective_date"), f"event {position} effective_date"),
        "added_ticker": normalize_ticker(event.get("added_ticker")),
        "added_company_name": str(
            _event_value(event, "added_company_name", "added_company") or ""
        ).strip(),
        "removed_ticker": normalize_ticker(event.get("removed_ticker")),
        "removed_company_name": str(
            _event_value(event, "removed_company_name", "removed_company") or ""
        ).strip(),
        "membership_evidence": _trusted_evidence(evidence, source_url),
        "membership_source_url": source_url,
        "reason": str(event.get("reason", "") or "").strip(),
    }
    if not normalized["added_ticker"] and not normalized["removed_ticker"]:
        raise ValueError(f"event {position} has no membership transition")
    if normalized["added_ticker"] == normalized["removed_ticker"]:
        raise ValueError(f"event {position} adds and removes the same ticker")
    return normalized


def _event_sort_key(event):
    return (
        event["removed_ticker"],
        event["added_ticker"],
        event["removed_company_name"],
        event["added_company_name"],
        event["membership_evidence"],
        event["membership_source_url"],
        event["reason"],
    )


def _reverse_order(events):
    by_date = {}
    seen_transitions = set()
    for event in events:
        transition = (
            event["effective_date"],
            event["added_ticker"],
            event["removed_ticker"],
        )
        if transition in seen_transitions:
            raise ValueError(f"duplicate membership transition: {transition}")
        seen_transitions.add(transition)
        by_date.setdefault(event["effective_date"], []).append(event)

    ordered = []
    for effective_date in sorted(by_date, reverse=True):
        group = by_date[effective_date]
        added = {}
        removed = {}
        for event in group:
            if event["added_ticker"]:
                if event["added_ticker"] in added:
                    raise ValueError(
                        f"conflicting additions on {effective_date}: {event['added_ticker']}"
                    )
                added[event["added_ticker"]] = event
            if event["removed_ticker"]:
                if event["removed_ticker"] in removed:
                    raise ValueError(
                        f"conflicting removals on {effective_date}: {event['removed_ticker']}"
                    )
                removed[event["removed_ticker"]] = event

        dependencies = {id(event): set() for event in group}
        dependents = {id(event): set() for event in group}
        by_id = {id(event): event for event in group}
        for first in group:
            successor = removed.get(first["added_ticker"])
            if successor is not None and successor is not first:
                dependencies[id(successor)].add(id(first))
                dependents[id(first)].add(id(successor))

        ready = sorted(
            (event for event in group if not dependencies[id(event)]),
            key=_event_sort_key,
        )
        forward = []
        while ready:
            event = ready.pop(0)
            forward.append(event)
            for dependent_id in sorted(
                dependents[id(event)], key=lambda item: _event_sort_key(by_id[item])
            ):
                dependencies[dependent_id].remove(id(event))
                if not dependencies[dependent_id]:
                    ready.append(by_id[dependent_id])
                    ready.sort(key=_event_sort_key)
        if len(forward) != len(group):
            raise ValueError(f"cyclic membership transitions on {effective_date}")
        ordered.extend(reversed(forward))
    return ordered


def restore_membership(current_rows, events, as_of_date):
    cutoff = _iso_date(as_of_date, "as_of_date")
    membership = {}
    for source_key, source_row in deepcopy(current_rows).items():
        row = dict(source_row)
        ticker = normalize_ticker(row.get("ticker", source_key))
        if not ticker:
            raise ValueError("current membership contains an empty ticker")
        if ticker in membership:
            raise ValueError(f"duplicate normalized current ticker: {ticker}")
        evidence = row.get("membership_evidence", "insufficient")
        effective_date = str(row.get("effective_date", "") or "").strip()
        if effective_date:
            effective_date = _iso_date(
                effective_date, f"current ticker {ticker} effective_date"
            )
        source_url = str(
            row.get("membership_source_url", row.get("source_url", "")) or ""
        ).strip()
        evidence = _evidence(
            evidence, f"current ticker {ticker} membership_evidence"
        )
        row.update(
            {
                "ticker": ticker,
                "company_name": str(row.get("company_name", "") or "").strip(),
                "effective_date": effective_date,
                "membership_evidence": _trusted_evidence(evidence, source_url),
                "membership_source_url": source_url,
            }
        )
        membership[ticker] = row

    normalized_events = [
        _normalize_event(event, position)
        for position, event in enumerate(events, start=1)
    ]
    ordered_events = _reverse_order(normalized_events)
    for event in ordered_events:
        if event["effective_date"] <= cutoff:
            continue
        added = event["added_ticker"]
        removed = event["removed_ticker"]
        if added:
            if added not in membership:
                raise ValueError(
                    f"cannot reverse {event['effective_date']}: added ticker {added} is absent"
                )
            del membership[added]
        if removed:
            if removed in membership:
                raise ValueError(
                    f"cannot reverse {event['effective_date']}: removed ticker {removed} already exists"
                )
            membership[removed] = {
                "ticker": removed,
                "company_name": event["removed_company_name"],
                "effective_date": event["effective_date"],
                "membership_evidence": event["membership_evidence"],
                "membership_source_url": event["membership_source_url"],
            }
    return membership


class _ChangesTableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self._table = None
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table" and self._table is None:
            self._table = []
        elif self._table is not None and tag == "tr":
            self._row = []
        elif self._row is not None and tag in {"th", "td"}:
            self._cell = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"th", "td"} and self._cell is not None:
            value = re.sub(r"\s+", " ", "".join(self._cell)).strip()
            self._row.append(value)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None


def _historical_date(value):
    text = re.sub(r"\[[^]]*]", "", str(value or "")).strip()
    for date_format in ("%Y-%m-%d", "%B %d, %Y", "%B %d %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"unrecognized historical change date: {value}")


def _configured_evidence(config, event):
    if not config:
        return "secondary", ""
    key = (
        event["effective_date"],
        event["added_ticker"],
        event["removed_ticker"],
    )
    entry = config.get(key, config.get("|".join(key), {}))
    if isinstance(entry, str):
        source_url = entry.strip()
    else:
        source_url = str((entry or {}).get("source_url", "") or "").strip()
    if not source_url:
        return "secondary", ""
    return _trusted_evidence("verified", source_url), source_url


def parse_change_events_html(html_text, evidence_config=None):
    parser = _ChangesTableParser()
    parser.feed(html_text)
    table = None
    for candidate in parser.tables:
        header_text = " ".join(" ".join(row) for row in candidate[:2]).lower()
        if all(label in header_text for label in ("date", "added", "removed", "reason")):
            table = candidate
            break
    if table is None:
        raise ValueError("S&P 500 historical changes table was not found")

    events = []
    previous_date = ""
    data_started = False
    for row_number, row in enumerate(table, start=1):
        values = list(row)
        try:
            effective_date = _historical_date(values[0])
            previous_date = effective_date
        except (ValueError, IndexError):
            if previous_date and len(values) == 5:
                effective_date = previous_date
                values.insert(0, "")
            elif data_started:
                raise ValueError(
                    f"malformed historical changes row {row_number}: {row!r}"
                )
            else:
                continue
        if len(values) < 6:
            if data_started:
                raise ValueError(
                    f"malformed historical changes row {row_number}: {row!r}"
                )
            continue
        data_started = True
        event = {
            "effective_date": effective_date,
            "added_ticker": normalize_ticker(values[1]),
            "added_company_name": values[2].strip(),
            "removed_ticker": normalize_ticker(values[3]),
            "removed_company_name": values[4].strip(),
            "reason": values[5].strip(),
            "membership_evidence": "secondary",
            "membership_source_url": "",
        }
        if not event["added_ticker"] and not event["removed_ticker"]:
            continue
        evidence, source_url = _configured_evidence(evidence_config, event)
        event["membership_evidence"] = evidence
        event["membership_source_url"] = source_url
        events.append(event)
    if not events:
        raise ValueError("S&P 500 historical changes table contained no events")
    return events


def load_change_events_csv(path):
    source = Path(path)
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        header = None
        header_line = 0
        for line_number, row in enumerate(reader, start=1):
            if not row or not any(str(value).strip() for value in row):
                continue
            header = [str(value or "").strip() for value in row]
            header_line = line_number
            break
        if header is None:
            raise ValueError(f"{source} contained no CSV header")
        if len(set(header)) != len(header):
            raise ValueError(f"{source} CSV header contains duplicate fields")

        events = []
        data_started = False
        for line_number, row in enumerate(reader, start=header_line + 1):
            is_blank = not row or not any(str(value).strip() for value in row)
            if is_blank and not data_started:
                continue
            if is_blank or len(row) != len(header):
                raise ValueError(
                    f"malformed historical changes CSV line {line_number}: {row!r}"
                )
            data_started = True
            raw_event = dict(zip(header, row))
            try:
                events.append(_normalize_event(raw_event, line_number))
            except ValueError as exc:
                raise ValueError(
                    f"malformed historical changes CSV line {line_number}: {row!r}"
                ) from exc
    if not events:
        raise ValueError(f"{source} contained no historical change events")
    return events


def _validate_history_coverage(events, weeks):
    if len(weeks) < 156:
        return
    if not events:
        raise ValueError(
            "insufficient historical coverage: no history events for 156+ weeks"
        )
    normalized_events = [
        _normalize_event(event, position)
        for position, event in enumerate(events, start=1)
    ]
    earliest_event = min(event["effective_date"] for event in normalized_events)
    earliest_week = min(weeks)
    if earliest_event > earliest_week:
        raise ValueError(
            "insufficient historical coverage: earliest history event "
            f"{earliest_event} is later than earliest week {earliest_week}"
        )


def build_weekly_membership(current_rows, events, weeks):
    output = []
    normalized_weeks = [
        _iso_date(week, "week") for week in deepcopy(weeks)
    ]
    seen_weeks = set()
    for week in normalized_weeks:
        if week in seen_weeks:
            raise ValueError(f"duplicate week: {week}")
        seen_weeks.add(week)
    normalized_weeks.sort()
    _validate_history_coverage(events, normalized_weeks)
    for week in normalized_weeks:
        membership = restore_membership(current_rows, events, week)
        for ticker in sorted(membership):
            row = membership[ticker]
            output.append(
                {
                    "week": week,
                    "ticker": ticker,
                    "company_name": row.get("company_name", ""),
                    "effective_date": row.get("effective_date", ""),
                    "membership_evidence": row.get("membership_evidence", "insufficient"),
                    "membership_source_url": row.get("membership_source_url", ""),
                }
            )
    return output


def write_historical_membership_csv(path, rows):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    raw_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    descriptor_owned = True
    try:
        stream = os.fdopen(
            raw_descriptor, "w", encoding="utf-8-sig", newline=""
        )
        descriptor_owned = False
        with stream:
            writer = csv.DictWriter(
                stream, fieldnames=MEMBERSHIP_FIELDS, extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary_name, destination)
    except Exception:
        if descriptor_owned:
            try:
                os.close(raw_descriptor)
            except OSError:
                pass
        try:
            Path(temporary_name).unlink(missing_ok=True)
        except OSError:
            pass
        raise
