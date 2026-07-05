import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

from historical_sp500 import _is_official_spglobal_source
from sp500_constituents import normalize_ticker


SOURCE_SCHEMA = "sp500_current_membership_sources"
SOURCE_VERSION = 1
MINIMUM_OFFICIAL_TICKER_COUNT = 400
SOURCE_FILE_REQUIRED_COLUMNS = ["Symbol", "Ticker"]
SOURCE_FILE_ACCEPTED_TICKER_COLUMNS = [
    "Symbol",
    "Ticker",
    "Ticker Symbol",
    "Constituent Ticker",
    "Constituent Symbol",
]
SOURCE_FILE_NEXT_COMMAND = (
    "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
    "scripts\\run_sp500_current_membership_sources.ps1 "
    "-ProjectRoot <project_root> -SourceFile <official_constituents.csv>"
)
SOURCE_FILE_DRY_RUN_COMMAND = (
    "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
    "scripts\\run_sp500_current_membership_sources.ps1 "
    "-ProjectRoot <project_root> -DryRun -SourceFile <official_constituents.csv>"
)
SOURCE_FILE_INBOX = "inputs/sp500_current_membership/official_constituents.csv"
OFFICIAL_EXPORT_URL = (
    "https://www.spglobal.com/spdji/en/idsexport/file.xls?"
    "redesignExport=true&languageId=1&selectedModule=Constituents&"
    "selectedSubModule=ConstituentsFullList&indexId=340"
)
SOURCE_FILE_INBOX_NEXT_COMMAND_TEMPLATE = (
    "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
    "scripts\\run_sp500_current_membership_sources.ps1 "
    "-ProjectRoot <project_root> -SourceFileInbox {source_file_inbox}"
)
SOURCE_FILE_INBOX_DRY_RUN_COMMAND_TEMPLATE = (
    "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
    "scripts\\run_sp500_current_membership_sources.ps1 "
    "-ProjectRoot <project_root> -DryRun -SourceFileInbox {source_file_inbox}"
)
SOURCE_FILE_ACCEPTANCE_CRITERIA = [
    "has_symbol_or_ticker_column",
    "at_least_400_tickers",
    "official_spglobal_constituents_export",
]
SOURCE_FILE_USER_AGENT_HINT = (
    "Set SEC_USER_AGENT or pass -UserAgent <user_agent> when retrying official "
    "S&P Global fetches through PowerShell entrypoints."
)
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
SOURCE_FILE_TICKER_COLUMN_KEYS = {
    "symbol",
    "ticker",
    "tickersymbol",
    "constituentsymbol",
    "constituentticker",
}
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


def _source_file_column_key(name):
    return re.sub(r"[^a-z0-9]+", "", str(name or "").strip().lower())


def _source_file_ticker_columns(fieldnames):
    return [
        name
        for name in fieldnames or []
        if name and _source_file_column_key(name) in SOURCE_FILE_TICKER_COLUMN_KEYS
    ]


def _read_source_file_rows(source_file):
    source = Path(source_file)
    if not source.exists():
        raise FileNotFoundError(source)
    with source.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle))


def _source_file_header_and_data_rows(source_file):
    rows = _read_source_file_rows(source_file)
    first_non_empty = []
    for index, row in enumerate(rows):
        normalized_row = [str(cell or "").strip() for cell in row]
        if not any(normalized_row):
            continue
        if not first_non_empty:
            first_non_empty = normalized_row
        if _source_file_ticker_columns(normalized_row):
            return normalized_row, rows[index + 1 :]
    return first_non_empty, []


def _source_file_fieldnames(source_file):
    fieldnames, _rows = _source_file_header_and_data_rows(source_file)
    return [name for name in fieldnames or [] if name]


def _source_file_available_columns(source_file):
    source = Path(source_file)
    if not source.exists():
        return []
    try:
        return _source_file_fieldnames(source)
    except OSError:
        return []


def parse_official_current_tickers_from_source_file(source_file):
    source = Path(source_file)
    if not source.exists():
        raise FileNotFoundError(source)
    fieldnames, data_rows = _source_file_header_and_data_rows(source)
    ticker_columns = _source_file_ticker_columns(fieldnames)
    if not ticker_columns:
        raise ValueError("source_file must contain a Symbol or Ticker column")
    tickers = set()
    for values in data_rows:
        row = dict(zip(fieldnames, values))
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


def _source_file_guidance(source_file_inbox=SOURCE_FILE_INBOX):
    return {
        "source_file_inbox": source_file_inbox,
        "source_file_next_command": SOURCE_FILE_NEXT_COMMAND,
        "source_file_dry_run_command": SOURCE_FILE_DRY_RUN_COMMAND,
        "official_export_url": OFFICIAL_EXPORT_URL,
        "source_file_acceptance_criteria": SOURCE_FILE_ACCEPTANCE_CRITERIA,
        "source_file_user_agent_hint": SOURCE_FILE_USER_AGENT_HINT,
    }


def _fetch_error_classification(error):
    text = str(error or "")
    lowered = text.lower()
    if "winerror 10013" in lowered or "permission" in lowered:
        return {
            "fetch_error_type": "network_permission_denied",
            "fetch_retryable_without_environment_change": False,
            "fetch_error_next_action": "provide_official_constituents_csv_or_fix_network_permission",
            "source_quality_flag": "official_source_fetch_blocked_by_permission",
        }
    if "timed out" in lowered or "timeout" in lowered:
        return {
            "fetch_error_type": "network_timeout",
            "fetch_retryable_without_environment_change": True,
            "fetch_error_next_action": "retry_official_source_or_provide_official_constituents_csv",
            "source_quality_flag": "official_source_fetch_timeout",
        }
    if "http error 403" in lowered or "forbidden" in lowered:
        return {
            "fetch_error_type": "official_source_access_denied",
            "fetch_retryable_without_environment_change": False,
            "fetch_error_next_action": "provide_official_constituents_csv",
            "source_quality_flag": "official_source_fetch_blocked_by_remote_access_policy",
        }
    return {
        "fetch_error_type": "official_source_fetch_error",
        "fetch_retryable_without_environment_change": True,
        "fetch_error_next_action": "retry_official_source_or_provide_official_constituents_csv",
        "source_quality_flag": "official_source_fetch_failed",
    }


def build_current_membership_sources_from_tickers(template_path, official_tickers, source_url, as_of_date=None):
    if not _is_official_spglobal_source(source_url):
        raise ValueError("source_url must be an official S&P Global HTTPS URL")
    requested = _template_tickers(template_path)
    official = set(official_tickers)
    source_quality_flags = []
    if len(official) < MINIMUM_OFFICIAL_TICKER_COUNT:
        source_quality_flags.append("official_ticker_count_below_minimum")
    official_for_matching = official if not source_quality_flags else set()
    matched = [ticker for ticker in requested if ticker in official_for_matching]
    missing = [ticker for ticker in requested if ticker not in official_for_matching]
    status = "ready"
    next_action = "import_current_membership_sources"
    source_file_required_columns = []
    if source_quality_flags:
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
    payload = {
        "source_schema": SOURCE_SCHEMA,
        "source_version": SOURCE_VERSION,
        "status": status,
        "as_of_date": as_of_date or date.today().isoformat(),
        "source_url": source_url,
        "requested_count": len(requested),
        "parsed_official_ticker_count": len(official),
        "minimum_official_ticker_count": MINIMUM_OFFICIAL_TICKER_COUNT,
        "source_quality_flags": source_quality_flags,
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
    if status == "source_file_required":
        payload.update(_source_file_guidance())
    return payload


def build_current_membership_sources(template_path, html_text, source_url, as_of_date=None):
    return build_current_membership_sources_from_tickers(
        template_path,
        parse_official_current_tickers(html_text),
        source_url,
        as_of_date=as_of_date,
    )


def build_fetch_failed_payload(template_path, source_url, error, as_of_date=None):
    requested = _template_tickers(template_path)
    classification = _fetch_error_classification(error)
    source_quality_flags = ["official_source_fetch_failed"]
    if classification["source_quality_flag"] not in source_quality_flags:
        source_quality_flags.append(classification["source_quality_flag"])
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
        "next_action": classification["fetch_error_next_action"],
        "source_file_required_columns": SOURCE_FILE_REQUIRED_COLUMNS,
        "minimum_official_ticker_count": MINIMUM_OFFICIAL_TICKER_COUNT,
        "source_quality_flags": source_quality_flags,
        "fetch_error_type": classification["fetch_error_type"],
        "fetch_retryable_without_environment_change": classification[
            "fetch_retryable_without_environment_change"
        ],
        "fetch_error_next_action": classification["fetch_error_next_action"],
        **_source_file_guidance(),
        "formal_backtest_upgrade_allowed": False,
        "rows": [],
        "error": str(error),
        "boundary": "官方来源未能读取或解析时只输出空来源包和失败报告，不生成 verified 当前成分来源。",
    }


def build_source_file_invalid_payload(template_path, source_url, source_file, error, as_of_date=None):
    requested = _template_tickers(template_path)
    return {
        "source_schema": SOURCE_SCHEMA,
        "source_version": SOURCE_VERSION,
        "status": "source_file_invalid",
        "as_of_date": as_of_date or date.today().isoformat(),
        "source_url": source_url,
        "source_file": str(source_file),
        "source_file_available_columns": _source_file_available_columns(source_file),
        "requested_count": len(requested),
        "parsed_official_ticker_count": 0,
        "matched_count": 0,
        "missing_count": len(requested),
        "missing_tickers": requested,
        "missing_ticker_review_queue": _missing_ticker_review_queue(
            requested,
            source_url,
            "source_file_invalid",
        ),
        "next_action": "provide_valid_official_constituents_csv",
        "source_file_required_columns": SOURCE_FILE_REQUIRED_COLUMNS,
        "minimum_official_ticker_count": MINIMUM_OFFICIAL_TICKER_COUNT,
        "source_quality_flags": ["source_file_invalid"],
        **_source_file_guidance(),
        "formal_backtest_upgrade_allowed": False,
        "rows": [],
        "error": str(error),
        "boundary": "只验证本地官方 CSV 是否可导入，不写入当前成分来源包，不修改回测输入或正式模型参数。",
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


def add_source_file_inbox_status(payload, source_file_inbox):
    if not source_file_inbox:
        return payload
    inbox_path = Path(source_file_inbox)
    inbox_exists = inbox_path.exists()
    payload["source_file_inbox"] = source_file_inbox
    payload["source_file_inbox_next_command"] = SOURCE_FILE_INBOX_NEXT_COMMAND_TEMPLATE.format(
        source_file_inbox=source_file_inbox
    )
    payload["source_file_inbox_dry_run_command"] = SOURCE_FILE_INBOX_DRY_RUN_COMMAND_TEMPLATE.format(
        source_file_inbox=source_file_inbox
    )
    payload["source_file_inbox_exists"] = inbox_exists
    if inbox_exists:
        stat = inbox_path.stat()
        payload["source_file_inbox_size_bytes"] = stat.st_size
        payload["source_file_inbox_sha256"] = hashlib.sha256(inbox_path.read_bytes()).hexdigest()
        payload["source_file_inbox_modified_at"] = datetime.fromtimestamp(
            stat.st_mtime,
            tz=timezone.utc,
        ).isoformat()
    else:
        payload["source_file_inbox_size_bytes"] = 0
        payload["source_file_inbox_sha256"] = ""
        payload["source_file_inbox_modified_at"] = ""
    if not inbox_exists:
        payload["source_file_validation_status"] = "missing"
    elif payload.get("status") == "source_file_invalid":
        payload["source_file_validation_status"] = "invalid"
    else:
        payload["source_file_validation_status"] = "present_unvalidated"
    return payload


def render_report(payload):
    lines = [
        "# sp500_current_membership_sources",
        "",
        f"- as_of_date: {payload.get('as_of_date', '')}",
        f"- source_url: {payload.get('source_url', '')}",
        f"- official_export_url: {payload.get('official_export_url', '')}",
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
    if payload.get("validation_only") is not None:
        lines.append(f"- validation_only: {str(payload.get('validation_only')).lower()}")
    if payload.get("source_file_next_command"):
        lines.append(f"- source_file_next_command: {payload.get('source_file_next_command', '')}")
    if payload.get("source_file_dry_run_command"):
        lines.append(f"- source_file_dry_run_command: {payload.get('source_file_dry_run_command', '')}")
    if payload.get("source_file_inbox_next_command"):
        lines.append(f"- source_file_inbox_next_command: {payload.get('source_file_inbox_next_command', '')}")
    if payload.get("source_file_inbox_dry_run_command"):
        lines.append(f"- source_file_inbox_dry_run_command: {payload.get('source_file_inbox_dry_run_command', '')}")
    if payload.get("source_file_request_file"):
        lines.append(f"- source_file_request_file: {payload.get('source_file_request_file', '')}")
    if payload.get("source_file_inbox"):
        lines.append(f"- source_file_inbox: {payload.get('source_file_inbox', '')}")
    if payload.get("source_file_inbox_exists") is not None:
        lines.append(f"- source_file_inbox_exists: {str(payload.get('source_file_inbox_exists')).lower()}")
    if payload.get("source_file_validation_status"):
        lines.append(f"- source_file_validation_status: {payload.get('source_file_validation_status', '')}")
    if "source_file_inbox_size_bytes" in payload:
        lines.append(f"- source_file_inbox_size_bytes: {payload.get('source_file_inbox_size_bytes', 0) or 0}")
    if "source_file_inbox_sha256" in payload:
        lines.append(f"- source_file_inbox_sha256: {payload.get('source_file_inbox_sha256') or 'none'}")
    if "source_file_inbox_modified_at" in payload:
        lines.append(f"- source_file_inbox_modified_at: {payload.get('source_file_inbox_modified_at') or 'none'}")
    if payload.get("source_file_acceptance_criteria"):
        lines.append(
            "- source_file_acceptance_criteria: "
            + ", ".join(payload.get("source_file_acceptance_criteria") or [])
        )
    if payload.get("source_file_user_agent_hint"):
        lines.append(f"- source_file_user_agent_hint: {payload.get('source_file_user_agent_hint', '')}")
    if payload.get("source_file_ticker_columns"):
        lines.append(
            "- source_file_ticker_columns: " + ", ".join(payload.get("source_file_ticker_columns") or [])
        )
    if payload.get("source_file_available_columns"):
        lines.append(
            "- source_file_available_columns: " + ", ".join(payload.get("source_file_available_columns") or [])
        )
    if payload.get("fetch_error_type"):
        lines.append(f"- fetch_error_type: {payload.get('fetch_error_type', '')}")
    if payload.get("fetch_retryable_without_environment_change") is not None:
        lines.append(
            "- fetch_retryable_without_environment_change: "
            + str(payload.get("fetch_retryable_without_environment_change")).lower()
        )
    if payload.get("fetch_error_next_action"):
        lines.append(f"- fetch_error_next_action: {payload.get('fetch_error_next_action', '')}")
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


def render_source_file_request(payload, missing_limit=20):
    missing = payload.get("missing_tickers", []) or []
    displayed_missing = missing[:missing_limit]
    required_columns = " or ".join(payload.get("source_file_required_columns") or [])
    lines = [
        "# S&P 500 official constituents CSV request",
        "",
        "- request_manifest_schema: sp500_current_membership_source_file_request",
        "- request_manifest_version: 1",
        f"- as_of_date: {payload.get('as_of_date', '')}",
        f"- status: {payload.get('status', 'unknown')}",
        f"- source_url: {payload.get('source_url', '')}",
        f"- official_export_url: {payload.get('official_export_url', '')}",
        f"- required_columns: {required_columns}",
        "- accepted_ticker_columns: " + ", ".join(SOURCE_FILE_ACCEPTED_TICKER_COLUMNS),
        "- acceptance_criteria: " + ", ".join(payload.get("source_file_acceptance_criteria") or []),
        f"- source_file_user_agent_hint: {payload.get('source_file_user_agent_hint', '')}",
        f"- minimum_official_ticker_count: {payload.get('minimum_official_ticker_count', 0)}",
        f"- requested_count: {payload.get('requested_count', 0)}",
        f"- missing_count: {payload.get('missing_count', 0)}",
        f"- intake_template: {payload.get('source_file_intake_template', '')}",
        f"- source_file_inbox: {payload.get('source_file_inbox', SOURCE_FILE_INBOX)}",
        f"- source_file_inbox_exists: {str(payload.get('source_file_inbox_exists')).lower()}",
        f"- source_file_validation_status: {payload.get('source_file_validation_status', '')}",
        f"- fetch_error_type: {payload.get('fetch_error_type', '')}",
        "- fetch_retryable_without_environment_change: "
        + str(payload.get("fetch_retryable_without_environment_change")).lower(),
        f"- fetch_error_next_action: {payload.get('fetch_error_next_action', '')}",
        f"- dry_run_command: {payload.get('source_file_dry_run_command', '')}",
        f"- inbox_dry_run_command: {payload.get('source_file_inbox_dry_run_command', '')}",
        "- validation_mode: --validate-source-file-only",
        f"- import_command: {payload.get('source_file_next_command', '')}",
        f"- inbox_import_command: {payload.get('source_file_inbox_next_command', '')}",
        "- formal_backtest_upgrade_allowed: false",
        "- formal_model_change_allowed: false",
        "",
        "## Acceptance criteria",
        "",
    ]
    for item in payload.get("source_file_acceptance_criteria") or []:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Current source file inbox fingerprint",
            "",
            f"- source_file_inbox_size_bytes: {payload.get('source_file_inbox_size_bytes', 0) or 0}",
            f"- source_file_inbox_sha256: {payload.get('source_file_inbox_sha256') or 'none'}",
            f"- source_file_inbox_modified_at: {payload.get('source_file_inbox_modified_at') or 'none'}",
            "",
            "## Missing ticker sample",
            "",
            "| ticker |",
            "|---|",
        ]
    )
    for ticker in displayed_missing:
        lines.append(f"| {ticker} |")
    if not displayed_missing:
        lines.append("| - |")
    if len(missing) > missing_limit:
        lines.append(f"| ... {len(missing) - missing_limit} more |")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Use only the official S&P Global constituents export. Do not import the intake template as the source CSV.",
            "- Run the dry-run command before the import command.",
            "",
        ]
    )
    return "\n".join(lines)


def should_write_source_file_request(payload):
    return payload.get("recommended_followup") == "provide_official_constituents_csv" or payload.get("next_action") in {
        "provide_official_constituents_csv",
        "retry_official_source_or_provide_official_constituents_csv",
        "provide_official_constituents_csv_or_fix_network_permission",
        "provide_valid_official_constituents_csv",
    }


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
    parser.add_argument("--source-file-request", default="outputs/automation/sp500_current_membership_source_file_request.md")
    parser.add_argument("--source-file-inbox", default=SOURCE_FILE_INBOX)
    parser.add_argument("--user-agent", default="")
    parser.add_argument("--allow-empty-on-fetch-error", action="store_true")
    parser.add_argument("--validate-source-file-only", action="store_true")
    args = parser.parse_args()
    if args.validate_source_file_only and not args.source_file:
        parser.error("--validate-source-file-only requires --source-file")

    try:
        if args.source_file:
            source_file_ticker_columns = _source_file_ticker_columns(
                _source_file_fieldnames(args.source_file)
            )
            payload = build_current_membership_sources_from_tickers(
                args.template,
                parse_official_current_tickers_from_source_file(args.source_file),
                args.source_url,
                as_of_date=args.as_of_date or None,
            )
            payload["source_file_ticker_columns"] = source_file_ticker_columns
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
        if args.validate_source_file_only:
            payload = build_source_file_invalid_payload(
                args.template,
                args.source_url,
                args.source_file,
                exc,
                as_of_date=args.as_of_date or None,
            )
            payload["validation_only"] = True
            if args.source_file_inbox and should_write_source_file_request(payload):
                add_source_file_inbox_status(payload, args.source_file_inbox)
            print(render_report(payload))
            sys.exit(1)
        if not args.allow_empty_on_fetch_error:
            raise
        payload = build_fetch_failed_payload(
            args.template,
            args.source_url,
            exc,
            as_of_date=args.as_of_date or None,
        )
    if args.source_file_inbox and should_write_source_file_request(payload):
        add_source_file_inbox_status(payload, args.source_file_inbox)
    if args.intake_template and not args.source_file and payload.get("status") in {
        "fetch_failed",
        "source_file_required",
    }:
        write_intake_template(payload, args.intake_template)
    if args.intake_template:
        add_intake_coverage(payload, args.intake_template)
    if args.validate_source_file_only:
        payload["validation_only"] = True
        print(render_report(payload))
        return
    write_sources_csv(payload, args.output)
    if args.intake_template:
        write_intake_template(payload, args.intake_template)
    if args.review_queue_output:
        payload["missing_ticker_review_queue_file"] = args.review_queue_output
        write_review_queue_csv(payload, args.review_queue_output)
    if args.source_file_request and should_write_source_file_request(payload):
        payload["source_file_request_file"] = args.source_file_request
        write_text(render_source_file_request(payload), args.source_file_request)
    report = render_report(payload)
    write_text(report, args.report)
    if args.json_output:
        write_json(payload, args.json_output)
    print(report)


if __name__ == "__main__":
    main()
