import argparse
import json
import sys
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sp500_current_membership_sources import OFFICIAL_EXPORT_URL


PROBE_SCHEMA = "sp500_official_export_probe"
PROBE_VERSION = 1
MANUAL_EXPORT_TARGET_FILE = "inputs/sp500_current_membership/official_constituents.csv"
MINIMUM_OFFICIAL_TICKER_COUNT = 400
ACCEPTED_TICKER_COLUMNS = [
    "Symbol",
    "Ticker",
    "Ticker Symbol",
    "Constituent Ticker",
    "Constituent Symbol",
]
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
)


def _manual_export_fields():
    dry_run = (
        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
        "scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> "
        "-DryRun -SourceFileInbox inputs\\sp500_current_membership\\official_constituents.csv"
    )
    import_command = (
        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
        "scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> "
        "-SourceFileInbox inputs\\sp500_current_membership\\official_constituents.csv"
    )
    return {
        "manual_export_target_file": MANUAL_EXPORT_TARGET_FILE,
        "manual_export_dry_run_command": dry_run,
        "manual_export_import_command": import_command,
        "minimum_official_ticker_count": MINIMUM_OFFICIAL_TICKER_COUNT,
        "accepted_ticker_columns": list(ACCEPTED_TICKER_COLUMNS),
    }


def _default_fetcher(url, timeout=30, user_agent=""):
    request = Request(
        url,
        headers={
            "User-Agent": user_agent or DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return {
            "status_code": getattr(response, "status", 200),
            "content_type": response.headers.get("Content-Type", ""),
            "content": response.read(),
        }


def _failure_payload(status, url, as_of_date, error, http_status=0, next_action="retry_official_export_probe"):
    return {
        "probe_schema": PROBE_SCHEMA,
        "probe_version": PROBE_VERSION,
        "as_of_date": as_of_date or date.today().isoformat(),
        "status": status,
        "http_status": http_status,
        "official_export_url": url,
        "downloaded": False,
        "download_size_bytes": 0,
        "content_type": "",
        "next_action": next_action,
        "error": str(error or ""),
        "formal_backtest_upgrade_allowed": False,
        "boundary": (
            "Only probes the official S&P Global full constituents export URL. "
            "It does not import sources, modify historical_membership.csv, or upgrade formal backtest evidence."
        ),
        **_manual_export_fields(),
    }


def build_sp500_official_export_probe(
    official_export_url=OFFICIAL_EXPORT_URL,
    as_of_date=None,
    timeout=30,
    user_agent="",
    fetcher=None,
):
    url = official_export_url or OFFICIAL_EXPORT_URL
    fetch = fetcher or (lambda probe_url: _default_fetcher(probe_url, timeout=timeout, user_agent=user_agent))
    try:
        result = fetch(url)
    except HTTPError as error:
        status_code = int(getattr(error, "code", 0) or 0)
        if status_code == 403:
            return _failure_payload(
                "forbidden",
                url,
                as_of_date,
                error,
                http_status=403,
                next_action="retry_with_logged_in_browser_or_manual_export",
            )
        return _failure_payload("http_error", url, as_of_date, error, http_status=status_code)
    except URLError as error:
        return _failure_payload("fetch_failed", url, as_of_date, error)
    except TimeoutError as error:
        return _failure_payload("timeout", url, as_of_date, error)
    except OSError as error:
        return _failure_payload("fetch_failed", url, as_of_date, error)

    content = result.get("content", b"") if isinstance(result, dict) else bytes(result or b"")
    status_code = int(result.get("status_code", 200) if isinstance(result, dict) else 200)
    content_type = str(result.get("content_type", "") if isinstance(result, dict) else "")
    return {
        "probe_schema": PROBE_SCHEMA,
        "probe_version": PROBE_VERSION,
        "as_of_date": as_of_date or date.today().isoformat(),
        "status": "downloaded",
        "http_status": status_code,
        "official_export_url": url,
        "downloaded": True,
        "download_size_bytes": len(content),
        "content_type": content_type,
        "next_action": "save_as_official_constituents_csv_then_dry_run",
        "error": "",
        "formal_backtest_upgrade_allowed": False,
        "boundary": (
            "Only confirms the official export URL responded. The downloaded content still must be saved "
            "to inputs/sp500_current_membership/official_constituents.csv and pass dry-run validation before import."
        ),
        **_manual_export_fields(),
    }


def render_markdown(payload):
    return "\n".join(
        [
            "# sp500_official_export_probe",
            "",
            f"- as_of_date: {payload.get('as_of_date', '')}",
            f"- status: {payload.get('status', '')}",
            f"- http_status: {payload.get('http_status', 0)}",
            f"- official_export_url: {payload.get('official_export_url', '')}",
            f"- downloaded: {str(payload.get('downloaded')).lower()}",
            f"- download_size_bytes: {payload.get('download_size_bytes', 0)}",
            f"- content_type: {payload.get('content_type', '')}",
            f"- next_action: {payload.get('next_action', '')}",
            f"- formal_backtest_upgrade_allowed: {str(payload.get('formal_backtest_upgrade_allowed')).lower()}",
            f"- error: {payload.get('error', '')}",
            "",
            "## manual_export_handoff",
            "",
            f"- manual_export_target_file: {payload.get('manual_export_target_file', '')}",
            f"- minimum_official_ticker_count: {payload.get('minimum_official_ticker_count', 0)}",
            f"- accepted_ticker_columns: {', '.join(payload.get('accepted_ticker_columns') or [])}",
            f"- manual_export_dry_run_command: {payload.get('manual_export_dry_run_command', '')}",
            f"- manual_export_import_command: {payload.get('manual_export_import_command', '')}",
            "",
            "## boundary",
            "",
            f"- {payload.get('boundary', '')}",
            "",
        ]
    )


def write_json(payload, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8-sig")


def write_text(text, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8-sig")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Probe S&P Global official S&P 500 full constituents export URL.")
    parser.add_argument("--official-export-url", default=OFFICIAL_EXPORT_URL)
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--user-agent", default="")
    parser.add_argument("--output", default="outputs/automation/latest_sp500_official_export_probe.json")
    parser.add_argument("--report", default="outputs/automation/latest_sp500_official_export_probe.md")
    args = parser.parse_args()

    payload = build_sp500_official_export_probe(
        official_export_url=args.official_export_url,
        as_of_date=args.as_of_date or None,
        timeout=args.timeout,
        user_agent=args.user_agent,
    )
    report = render_markdown(payload)
    if args.output:
        write_json(payload, args.output)
    if args.report:
        write_text(report, args.report)
    print(report, end="")


if __name__ == "__main__":
    main()
