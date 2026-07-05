import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

from sp500_current_membership_sources import (
    INTAKE_TEMPLATE_FIELDS,
    MINIMUM_OFFICIAL_TICKER_COUNT,
    OFFICIAL_EXPORT_URL,
    SOURCE_FILE_ACCEPTANCE_CRITERIA,
    SOURCE_FILE_INBOX,
    SOURCE_FILE_INBOX_DRY_RUN_COMMAND_TEMPLATE,
    SOURCE_FILE_INBOX_NEXT_COMMAND_TEMPLATE,
    SOURCE_FILE_REQUIRED_COLUMNS,
    SOURCE_FILE_USER_AGENT_HINT,
    _intake_expected_tickers,
    _source_file_available_columns,
    _source_file_fieldnames,
    _source_file_ticker_columns,
    _template_tickers,
    parse_official_current_tickers_from_source_file,
)


STATUS_SCHEMA = "sp500_current_membership_source_inbox_status"
STATUS_VERSION = 1


def _source_file_inbox_metadata(path):
    source = Path(path)
    if not source.exists():
        return {
            "source_file_inbox_size_bytes": 0,
            "source_file_inbox_sha256": "",
            "source_file_inbox_modified_at": "",
        }
    stat = source.stat()
    return {
        "source_file_inbox_size_bytes": stat.st_size,
        "source_file_inbox_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_file_inbox_modified_at": datetime.fromtimestamp(
            stat.st_mtime,
            tz=timezone.utc,
        ).isoformat(),
    }


def _status_for_source_file(tickers, intake_expected):
    if len(tickers) < MINIMUM_OFFICIAL_TICKER_COUNT:
        return "incomplete", "provide_complete_official_constituents_csv"
    return "ready_for_import_preview", "run_source_file_inbox_dry_run_then_import"


def _intake_coverage(tickers, intake_template):
    expected = _intake_expected_tickers(intake_template) if Path(intake_template).exists() else []
    missing = [ticker for ticker in expected if ticker not in tickers]
    if not expected:
        status = "not_available"
    elif not missing:
        status = "complete"
    elif len(missing) == len(expected):
        status = "none"
    else:
        status = "partial"
    return {
        "intake_template": str(intake_template),
        "intake_coverage_status": status,
        "intake_expected_count": len(expected),
        "intake_matched_count": len(expected) - len(missing),
        "intake_missing_count": len(missing),
        "intake_missing_tickers": missing,
    }


def _source_file_rejection_metadata(available_columns):
    available = {str(column or "").strip() for column in available_columns or []}
    is_intake_template = set(INTAKE_TEMPLATE_FIELDS).issubset(available)
    return {
        "source_file_is_intake_template": is_intake_template,
        "source_file_rejection_reason": "intake_template_submitted_as_official_csv"
        if is_intake_template
        else "missing_symbol_or_ticker_column",
    }


def build_inbox_status(
    template,
    source_file_inbox=SOURCE_FILE_INBOX,
    intake_template="outputs/automation/sp500_current_membership_source_intake_template.csv",
    source_url="https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
    as_of_date=None,
):
    requested = _template_tickers(template)
    inbox_path = Path(source_file_inbox)
    payload = {
        "status_schema": STATUS_SCHEMA,
        "status_version": STATUS_VERSION,
        "as_of_date": as_of_date or date.today().isoformat(),
        "source_url": source_url,
        "official_export_url": OFFICIAL_EXPORT_URL,
        "source_file_inbox": str(source_file_inbox),
        "source_file_inbox_exists": inbox_path.exists(),
        "source_file_required_columns": SOURCE_FILE_REQUIRED_COLUMNS,
        "source_file_acceptance_criteria": SOURCE_FILE_ACCEPTANCE_CRITERIA,
        "source_file_user_agent_hint": SOURCE_FILE_USER_AGENT_HINT,
        "minimum_official_ticker_count": MINIMUM_OFFICIAL_TICKER_COUNT,
        "requested_count": len(requested),
        "parsed_official_ticker_count": 0,
        "source_file_inbox_dry_run_command": SOURCE_FILE_INBOX_DRY_RUN_COMMAND_TEMPLATE.format(
            source_file_inbox=source_file_inbox
        ),
        "source_file_inbox_next_command": SOURCE_FILE_INBOX_NEXT_COMMAND_TEMPLATE.format(
            source_file_inbox=source_file_inbox
        ),
        "external_input_required": False,
        "blocking_reason": "",
        "blocking_input": "",
        "formal_backtest_upgrade_allowed": False,
        "formal_model_change_allowed": False,
        **_source_file_inbox_metadata(inbox_path),
    }
    if not inbox_path.exists():
        payload.update(
            {
                "status": "missing",
                "source_file_validation_status": "missing",
                "next_action": "place_official_constituents_csv",
                "external_input_required": True,
                "blocking_reason": "official_constituents_csv_missing",
                "blocking_input": str(source_file_inbox),
                **_intake_coverage(set(), intake_template),
            }
        )
        return payload
    try:
        source_file_ticker_columns = _source_file_ticker_columns(
            _source_file_fieldnames(inbox_path)
        )
        tickers = parse_official_current_tickers_from_source_file(inbox_path)
    except Exception as exc:
        available_columns = _source_file_available_columns(inbox_path)
        payload.update(
            {
                "status": "invalid",
                "source_file_validation_status": "invalid",
                "source_file_available_columns": available_columns,
                "validation_error": str(exc),
                "next_action": "provide_valid_official_constituents_csv",
                "external_input_required": True,
                "blocking_reason": "official_constituents_csv_invalid",
                "blocking_input": str(source_file_inbox),
                **_source_file_rejection_metadata(available_columns),
                **_intake_coverage(set(), intake_template),
            }
        )
        return payload
    coverage = _intake_coverage(tickers, intake_template)
    status, next_action = _status_for_source_file(tickers, coverage["intake_missing_tickers"])
    payload.update(
        {
            "status": status,
            "source_file_validation_status": "ready" if status.startswith("ready") else "incomplete",
            "next_action": next_action,
            "external_input_required": not status.startswith("ready"),
            "blocking_reason": "" if status.startswith("ready") else "official_constituents_csv_incomplete",
            "blocking_input": "" if status.startswith("ready") else str(source_file_inbox),
            "source_file_rejection_reason": ""
            if status.startswith("ready")
            else "official_ticker_count_below_minimum",
            "parsed_official_ticker_count": len(tickers),
            "source_file_ticker_columns": source_file_ticker_columns,
            "matched_requested_count": len([ticker for ticker in requested if ticker in tickers]),
            "missing_requested_count": len([ticker for ticker in requested if ticker not in tickers]),
            "missing_requested_tickers": [ticker for ticker in requested if ticker not in tickers],
            **coverage,
        }
    )
    return payload


def render_status(payload):
    lines = [
        "# S&P 500 official constituents inbox status",
        "",
        f"- as_of_date: {payload.get('as_of_date', '')}",
        f"- status: {payload.get('status', 'unknown')}",
        f"- official_export_url: {payload.get('official_export_url', '')}",
        f"- source_file_inbox: {payload.get('source_file_inbox', '')}",
        f"- source_file_inbox_exists: {str(payload.get('source_file_inbox_exists')).lower()}",
        f"- source_file_inbox_size_bytes: {payload.get('source_file_inbox_size_bytes', 0)}",
        f"- source_file_inbox_sha256: {payload.get('source_file_inbox_sha256', '')}",
        f"- source_file_inbox_modified_at: {payload.get('source_file_inbox_modified_at', '')}",
        f"- source_file_validation_status: {payload.get('source_file_validation_status', '')}",
        f"- parsed_official_ticker_count: {payload.get('parsed_official_ticker_count', 0)}",
        f"- source_file_ticker_columns: {', '.join(payload.get('source_file_ticker_columns') or [])}",
        f"- source_file_available_columns: {', '.join(payload.get('source_file_available_columns') or [])}",
        f"- source_file_rejection_reason: {payload.get('source_file_rejection_reason', '')}",
        f"- source_file_user_agent_hint: {payload.get('source_file_user_agent_hint', '')}",
        f"- minimum_official_ticker_count: {payload.get('minimum_official_ticker_count', 0)}",
        f"- intake_coverage_status: {payload.get('intake_coverage_status', '')}",
        f"- intake_expected_count: {payload.get('intake_expected_count', 0)}",
        f"- intake_matched_count: {payload.get('intake_matched_count', 0)}",
        f"- intake_missing_count: {payload.get('intake_missing_count', 0)}",
        f"- external_input_required: {str(payload.get('external_input_required', False)).lower()}",
        f"- blocking_reason: {payload.get('blocking_reason', '')}",
        f"- blocking_input: {payload.get('blocking_input', '')}",
        f"- next_action: {payload.get('next_action', '')}",
        f"- dry_run_command: {payload.get('source_file_inbox_dry_run_command', '')}",
        f"- import_command: {payload.get('source_file_inbox_next_command', '')}",
        "",
        "## Boundary",
        "",
        "- This check is read-only and does not write current membership sources.",
        "- Passing this check does not modify historical membership or formal model parameters.",
        "",
    ]
    missing = payload.get("intake_missing_tickers", []) or []
    if missing:
        lines.extend(["## Intake Missing Tickers", "", ", ".join(missing[:20]), ""])
    if payload.get("validation_error"):
        lines.extend(["## Validation Error", "", str(payload.get("validation_error")), ""])
    return "\n".join(lines)


def write_json(payload, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8-sig",
    )


def write_text(text, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8-sig")


def main():
    parser = argparse.ArgumentParser(description="Check the S&P 500 official constituents CSV inbox.")
    parser.add_argument("--template", default="outputs/automation/us_sp500_current_membership_sources_template.csv")
    parser.add_argument("--source-file-inbox", default=SOURCE_FILE_INBOX)
    parser.add_argument("--intake-template", default="outputs/automation/sp500_current_membership_source_intake_template.csv")
    parser.add_argument("--source-url", default="https://www.spglobal.com/spdji/en/indices/equity/sp-500/")
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--output", default="outputs/automation/latest_sp500_current_membership_source_inbox_status.json")
    parser.add_argument("--report", default="outputs/automation/latest_sp500_current_membership_source_inbox_status.md")
    args = parser.parse_args()

    payload = build_inbox_status(
        args.template,
        source_file_inbox=args.source_file_inbox,
        intake_template=args.intake_template,
        source_url=args.source_url,
        as_of_date=args.as_of_date or None,
    )
    report = render_status(payload)
    if args.output:
        write_json(payload, args.output)
    if args.report:
        write_text(report, args.report)
    print(report)


if __name__ == "__main__":
    main()
