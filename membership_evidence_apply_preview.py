import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

from historical_sp500 import _is_official_spglobal_source
from sp500_constituents import normalize_ticker


PREVIEW_SCHEMA = "membership_evidence_apply_preview"
PREVIEW_VERSION = 1
CSV_FIELDS = [
    "week",
    "ticker",
    "company_name",
    "current_evidence",
    "current_membership_source_url",
    "proposed_evidence",
    "proposed_membership_source_url",
    "source_as_of_date",
    "upgrade_scope",
]


def _read_csv(path):
    source = Path(path)
    if not source.exists():
        return []
    with source.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _current_source_maps(path):
    valid = {}
    invalid = {}
    for row in _read_csv(path):
        ticker = normalize_ticker(row.get("ticker"))
        if not ticker:
            continue
        evidence = str(row.get("membership_evidence", "") or "").strip().lower()
        source_url = str(row.get("membership_source_url", "") or "").strip()
        if evidence == "verified" and _is_official_spglobal_source(source_url):
            valid[ticker] = row
        else:
            invalid[ticker] = row
    return valid, invalid


def _preview_item(row, source_row):
    return {
        "week": row.get("week", ""),
        "ticker": normalize_ticker(row.get("ticker")),
        "company_name": row.get("company_name", ""),
        "current_evidence": str(row.get("membership_evidence", "") or "").strip().lower(),
        "current_membership_source_url": row.get("membership_source_url", ""),
        "proposed_evidence": "verified",
        "proposed_membership_source_url": source_row.get("membership_source_url", ""),
        "source_as_of_date": source_row.get("source_as_of_date", ""),
        "upgrade_scope": "current_membership_only",
    }


def build_apply_preview(membership_path, current_source_pack, as_of_date=None):
    valid_sources, invalid_sources = _current_source_maps(current_source_pack)
    items = []
    already_verified = 0
    membership_rows = _read_csv(membership_path)
    for row in membership_rows:
        ticker = normalize_ticker(row.get("ticker"))
        evidence = str(row.get("membership_evidence", "") or "").strip().lower()
        if evidence == "verified":
            already_verified += 1
            continue
        source_row = valid_sources.get(ticker)
        if source_row:
            items.append(_preview_item(row, source_row))
    eligible_tickers = sorted({item["ticker"] for item in items})
    return {
        "preview_schema": PREVIEW_SCHEMA,
        "preview_version": PREVIEW_VERSION,
        "as_of_date": as_of_date or date.today().isoformat(),
        "status": "ready",
        "membership_path": str(Path(membership_path)),
        "current_source_pack": str(Path(current_source_pack)),
        "applied_to_historical_membership": False,
        "membership_row_count": len(membership_rows),
        "eligible_ticker_count": len(eligible_tickers),
        "preview_row_count": len(items),
        "preview_weeks_affected": len({item["week"] for item in items}),
        "invalid_source_ticker_count": len(invalid_sources),
        "already_verified_row_count": already_verified,
        "formal_backtest_upgrade_allowed": False,
        "items": items,
        "boundary": "Only previews rows that could be upgraded by verified official current S&P Global membership sources; does not modify historical_membership.csv.",
    }


def render_markdown(payload):
    lines = [
        "# membership_evidence_apply_preview",
        "",
        f"- as_of_date: {payload.get('as_of_date', '')}",
        f"- status: {payload.get('status', '')}",
        f"- membership_row_count: {payload.get('membership_row_count', 0)}",
        f"- eligible_ticker_count: {payload.get('eligible_ticker_count', 0)}",
        f"- preview_row_count: {payload.get('preview_row_count', 0)}",
        f"- preview_weeks_affected: {payload.get('preview_weeks_affected', 0)}",
        f"- invalid_source_ticker_count: {payload.get('invalid_source_ticker_count', 0)}",
        f"- already_verified_row_count: {payload.get('already_verified_row_count', 0)}",
        f"- applied_to_historical_membership: {str(payload.get('applied_to_historical_membership')).lower()}",
        f"- formal_backtest_upgrade_allowed: {str(payload.get('formal_backtest_upgrade_allowed')).lower()}",
        "",
        "| week | ticker | current | proposed | source |",
        "|---|---|---|---|---|",
    ]
    for item in payload.get("items", []):
        lines.append(
            "| {week} | {ticker} | {current_evidence} | {proposed_evidence} | {proposed_membership_source_url} |".format(
                **item
            )
        )
    if not payload.get("items"):
        lines.append("| - | - | - | - | - |")
    lines.extend(["", "## boundary", "", f"- {payload.get('boundary', '')}", ""])
    return "\n".join(lines)


def write_json(payload, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8-sig")


def write_csv(payload, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(payload.get("items", []))


def write_text(text, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8-sig")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Preview current S&P 500 membership source application without modifying historical membership.")
    parser.add_argument("--membership", default="outputs/backtests/us_3y_weekly/historical_membership.csv")
    parser.add_argument("--current-source-pack", default="data/config/us_sp500_current_membership_sources.csv")
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--output-json", default="outputs/automation/latest_membership_evidence_apply_preview.json")
    parser.add_argument("--output-csv", default="outputs/automation/latest_membership_evidence_apply_preview.csv")
    parser.add_argument("--output-md", default="outputs/automation/latest_membership_evidence_apply_preview.md")
    args = parser.parse_args()

    payload = build_apply_preview(
        args.membership,
        args.current_source_pack,
        as_of_date=args.as_of_date or None,
    )
    report = render_markdown(payload)
    write_json(payload, args.output_json)
    write_csv(payload, args.output_csv)
    write_text(report, args.output_md)
    print(report)


if __name__ == "__main__":
    main()
