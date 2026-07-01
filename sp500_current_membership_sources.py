import argparse
import csv
import json
import re
import sys
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

from historical_sp500 import _is_official_spglobal_source
from sp500_constituents import normalize_ticker


SOURCE_SCHEMA = "sp500_current_membership_sources"
SOURCE_VERSION = 1
SOURCE_FILE_REQUIRED_COLUMNS = ["Symbol", "Ticker"]
INTAKE_TEMPLATE_FIELDS = [
    "expected_ticker",
    "intake_status",
    "required_source_url",
    "required_source_columns",
    "notes",
]
REVIEW_QUEUE_FIELDS = [
    "ticker",
    "review_status",
    "issue_type",
    "recommended_check",
    "required_source_url",
    "source_status",
]
OUTPUT_FIELDS = [
    "ticker",
    "membership_evidence",
    "membership_source_url",
    "source_as_of_date",
    "notes",
]
SOURCE_FILE_TICKER_COLUMNS = {"symbol", "ticker"}
OFFICIAL_TABLE_LABELS = {
    "COMPANY",
    "DATE",
    "GICS",
    "INDUSTRY",
    "NAME",
    "SECTOR",
    "SECURITY",
    "SYMBOL",
    "TICKER",
}


class _TableTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._in_cell = False
        self._cell = []
        self.cells = []

    def handle_starttag(self, tag, attrs):
        if tag in {"td", "th"}:
            self._in_cell = True
            self._cell = []

    def handle_data(self, data):
        if self._in_cell:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self._in_cell:
            value = re.sub(r"\s+", " ", "".join(self._cell)).strip()
            if value:
                self.cells.append(value)
            self._in_cell = False
            self._cell = []


def _read_csv(path):
    source = Path(path)
    if not source.exists():
        return []
    with source.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _template_tickers(template_path):
    tickers = []
    for row in _read_csv(template_path):
        ticker = normalize_ticker(row.get("ticker"))
        if ticker and ticker not in tickers:
            tickers.append(ticker)
    return tickers


def _intake_expected_tickers(path):
    expected = []
    for row in _read_csv(path):
        ticker = normalize_ticker(row.get("expected_ticker"))
        if ticker and ticker not in expected:
            expected.append(ticker)
    return expected


def parse_official_current_tickers(html_text):
    parser = _TableTextParser()
    parser.feed(html_text)
    tickers = set()
    for cell in parser.cells:
        ticker = normalize_ticker(cell)
        if ticker not in OFFICIAL_TABLE_LABELS and re.fullmatch(r"[A-Z][A-Z0-9-]{0,9}", ticker):
            tickers.add(ticker)
    return tickers


def parse_official_current_tickers_from_source_file(source_file):
    source = Path(source_file)
    if not source.exists():
        raise FileNotFoundError(source)
    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        ticker_columns = [
            name
            for name in fieldnames
            if name and name.strip().lower() in SOURCE_FILE_TICKER_COLUMNS
        ]
        if not ticker_columns:
            raise ValueError("source_file must contain a Symbol or Ticker column")
        tickers = set()
        for row in reader:
            for column in ticker_columns:
                ticker = normalize_ticker(row.get(column))
                if ticker and re.fullmatch(r"[A-Z][A-Z0-9-]{0,9}", ticker):
                    tickers.add(ticker)
                    break
        return tickers


def fetch_source_html(source_url, user_agent=None):
    request = Request(
        source_url,
        headers={"User-Agent": user_agent or "stock-undervaluation-screen/1.0"},
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _missing_ticker_review_queue(missing_tickers, source_url, status):
    return [
        {
            "ticker": ticker,
            "review_status": "open",
            "issue_type": "missing_from_official_current_source",
            "recommended_check": (
                "Confirm whether the ticker is absent from the official S&P Global current membership source "
                "or whether a fresher official export is required."
            ),
            "required_source_url": source_url,
            "source_status": status,
        }
        for ticker in missing_tickers or []
    ]


def build_current_membership_sources_from_tickers(template_path, official_tickers, source_url, as_of_date=None):
    if not _is_official_spglobal_source(source_url):
        raise ValueError("source_url must be an official S&P Global HTTPS URL")
    requested = _template_tickers(template_path)
    official = set(official_tickers)
    matched = [ticker for ticker in requested if ticker in official]
    missing = [ticker for ticker in requested if ticker not in official]
    status = "ready"
    next_action = "import_current_membership_sources"
    source_file_required_columns = []
    if not official:
        status = "source_file_required"
        next_action = "provide_official_constituents_csv"
        source_file_required_columns = SOURCE_FILE_REQUIRED_COLUMNS
    elif missing:
        next_action = "review_missing_tickers"
    rows = [
        {
            "ticker": ticker,
            "membership_evidence": "verified",
            "membership_source_url": source_url,
            "source_as_of_date": as_of_date or date.today().isoformat(),
            "notes": "Matched ticker in official S&P Global current membership source.",
        }
        for ticker in matched
    ]
    return {
        "source_schema": SOURCE_SCHEMA,
        "source_version": SOURCE_VERSION,
        "status": status,
        "as_of_date": as_of_date or date.today().isoformat(),
        "source_url": source_url,
        "requested_count": len(requested),
        "parsed_official_ticker_count": len(official),
        "matched_count": len(rows),
        "missing_count": len(missing),
        "missing_tickers": missing,
        "missing_ticker_review_queue": _missing_ticker_review_queue(missing, source_url, status),
        "next_action": next_action,
        "source_file_required_columns": source_file_required_columns,
        "formal_backtest_upgrade_allowed": False,
        "rows": rows,
        "boundary": "只在官方 S&P Global 来源中解析到 ticker 时生成 verified 当前成分来源；不推断、不补全、不修改回测输入。",
    }


def build_current_membership_sources(template_path, html_text, source_url, as_of_date=None):
    return build_current_membership_sources_from_tickers(
        template_path,
        parse_official_current_tickers(html_text),
        source_url,
        as_of_date=as_of_date,
    )


def build_fetch_failed_payload(template_path, source_url, error, as_of_date=None):
    requested = _template_tickers(template_path)
    return {
        "source_schema": SOURCE_SCHEMA,
        "source_version": SOURCE_VERSION,
        "status": "fetch_failed",
        "as_of_date": as_of_date or date.today().isoformat(),
        "source_url": source_url,
        "requested_count": len(requested),
        "parsed_official_ticker_count": 0,
        "matched_count": 0,
        "missing_count": len(requested),
        "missing_tickers": requested,
        "missing_ticker_review_queue": _missing_ticker_review_queue(
            requested,
            source_url,
            "fetch_failed",
        ),
        "next_action": "retry_official_source_or_provide_official_constituents_csv",
        "source_file_required_columns": SOURCE_FILE_REQUIRED_COLUMNS,
        "formal_backtest_upgrade_allowed": False,
        "rows": [],
        "error": str(error),
        "boundary": "官方来源未能读取或解析时只输出空来源包和失败报告，不生成 verified 当前成分来源。",
    }


def write_sources_csv(payload, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(payload.get("rows", []))


def write_intake_template(payload, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INTAKE_TEMPLATE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for ticker in payload.get("missing_tickers", []) or []:
            writer.writerow(
                {
                    "expected_ticker": ticker,
                    "intake_status": "official_export_required",
                    "required_source_url": payload.get("source_url", ""),
                    "required_source_columns": "Symbol or Ticker",
                    "notes": "Download the official S&P Global constituents export, then run with --source-file. Do not import this checklist as the source file.",
                }
            )


def write_review_queue_csv(payload, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_QUEUE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(payload.get("missing_ticker_review_queue", []) or [])


def add_intake_coverage(payload, intake_template):
    intake_path = Path(intake_template)
    expected = _intake_expected_tickers(intake_path) if intake_path.exists() else []
    matched = {row.get("ticker", "") for row in payload.get("rows", []) or []}
    missing = [ticker for ticker in expected if ticker not in matched]
    if not expected:
        status = "not_available"
    elif not missing:
        status = "complete"
    elif len(missing) == len(expected):
        status = "none"
    else:
        status = "partial"
    payload["source_file_intake_template"] = str(intake_path)
    payload["intake_coverage_status"] = status
    payload["intake_expected_count"] = len(expected)
    payload["intake_matched_count"] = len(expected) - len(missing)
    payload["intake_missing_count"] = len(missing)
    payload["intake_missing_tickers"] = missing
    if status in {"complete", "partial"}:
        payload["recommended_followup"] = "run_membership_evidence_import_plan_then_apply_preview"
    elif payload.get("status") in {"fetch_failed", "source_file_required"}:
        payload["recommended_followup"] = "provide_official_constituents_csv"
    else:
        payload["recommended_followup"] = "review_current_membership_source_status"
    return payload


def render_report(payload):
    lines = [
        "# sp500_current_membership_sources",
        "",
        f"- as_of_date: {payload.get('as_of_date', '')}",
        f"- source_url: {payload.get('source_url', '')}",
        f"- status: {payload.get('status', 'unknown')}",
        f"- requested_count: {payload.get('requested_count', 0)}",
        f"- parsed_official_ticker_count: {payload.get('parsed_official_ticker_count', 0)}",
        f"- matched_count: {payload.get('matched_count', 0)}",
        f"- missing_count: {payload.get('missing_count', 0)}",
        f"- next_action: {payload.get('next_action', '')}",
        f"- source_file_required_columns: {', '.join(payload.get('source_file_required_columns') or [])}",
        f"- intake_coverage_status: {payload.get('intake_coverage_status', '')}",
        f"- intake_expected_count: {payload.get('intake_expected_count', 0)}",
        f"- intake_matched_count: {payload.get('intake_matched_count', 0)}",
        f"- intake_missing_count: {payload.get('intake_missing_count', 0)}",
        f"- recommended_followup: {payload.get('recommended_followup', '')}",
        f"- formal_backtest_upgrade_allowed: {str(payload.get('formal_backtest_upgrade_allowed')).lower()}",
    ]
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error', '')}")
    lines.extend(["", "| ticker | evidence | source |", "|---|---|---|"])
    for row in payload.get("rows", []):
        lines.append(
            f"| {row.get('ticker', '')} | {row.get('membership_evidence', '')} | {row.get('membership_source_url', '')} |"
        )
    if not payload.get("rows"):
        lines.append("| - | - | - |")
    lines.extend(
        [
            "",
            "## Missing ticker review queue",
            "",
            "| ticker | review_status | issue_type | recommended_check |",
            "|---|---|---|---|",
        ]
    )
    for item in payload.get("missing_ticker_review_queue", []) or []:
        lines.append(
            f"| {item.get('ticker', '')} | {item.get('review_status', '')} | "
            f"{item.get('issue_type', '')} | {item.get('recommended_check', '')} |"
        )
    if not payload.get("missing_ticker_review_queue"):
        lines.append("| - | - | - | - |")
    lines.extend(["", "## boundary", "", f"- {payload.get('boundary', '')}", ""])
    return "\n".join(lines)


def write_text(text, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8-sig")


def write_json(payload, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8-sig",
    )


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build verified current S&P 500 membership source rows from an official source.")
    parser.add_argument("--template", default="outputs/automation/us_sp500_current_membership_sources_template.csv")
    parser.add_argument("--source-url", default="https://www.spglobal.com/spdji/en/indices/equity/sp-500/")
    parser.add_argument("--source-html", default="")
    parser.add_argument("--source-file", default="")
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--output", default="data/config/us_sp500_current_membership_sources.csv")
    parser.add_argument("--report", default="outputs/automation/latest_sp500_current_membership_sources.md")
    parser.add_argument("--json-output", default="outputs/automation/latest_sp500_current_membership_sources.json")
    parser.add_argument("--intake-template", default="outputs/automation/sp500_current_membership_source_intake_template.csv")
    parser.add_argument("--review-queue-output", default="")
    parser.add_argument("--user-agent", default="")
    parser.add_argument("--allow-empty-on-fetch-error", action="store_true")
    args = parser.parse_args()

    try:
        if args.source_file:
            payload = build_current_membership_sources_from_tickers(
                args.template,
                parse_official_current_tickers_from_source_file(args.source_file),
                args.source_url,
                as_of_date=args.as_of_date or None,
            )
        else:
            html_text = Path(args.source_html).read_text(encoding="utf-8-sig") if args.source_html else fetch_source_html(
                args.source_url,
                user_agent=args.user_agent or None,
            )
            payload = build_current_membership_sources(
                args.template,
                html_text,
                args.source_url,
                as_of_date=args.as_of_date or None,
            )
    except Exception as exc:
        if not args.allow_empty_on_fetch_error:
            raise
        payload = build_fetch_failed_payload(
            args.template,
            args.source_url,
            exc,
            as_of_date=args.as_of_date or None,
        )
    if args.intake_template:
        add_intake_coverage(payload, args.intake_template)
    write_sources_csv(payload, args.output)
    if args.intake_template:
        write_intake_template(payload, args.intake_template)
    if args.review_queue_output:
        payload["missing_ticker_review_queue_file"] = args.review_queue_output
        write_review_queue_csv(payload, args.review_queue_output)
    report = render_report(payload)
    write_text(report, args.report)
    if args.json_output:
        write_json(payload, args.json_output)
    print(report)


if __name__ == "__main__":
    main()
