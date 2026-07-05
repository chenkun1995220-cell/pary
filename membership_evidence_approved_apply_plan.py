import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

from sp500_constituents import normalize_ticker


PLAN_SCHEMA = "membership_evidence_approved_apply_plan"
PLAN_VERSION = 1
PLAN_FIELDS = [
    "week",
    "ticker",
    "company_name",
    "historical_current_evidence",
    "historical_current_membership_source_url",
    "proposed_evidence",
    "proposed_membership_source_url",
    "source_as_of_date",
    "upgrade_scope",
    "confirmation_decision",
    "reviewer",
    "decision_notes",
    "validation_status",
    "validation_reason",
]


def _read_csv(path):
    source = Path(path)
    if not source.exists():
        return []
    with source.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _row_key(row):
    return (
        str(row.get("week", "") or "").strip(),
        normalize_ticker(row.get("ticker")),
    )


def _historical_index(rows):
    index = {}
    for row in rows:
        week, ticker = _row_key(row)
        if week and ticker:
            index[(week, ticker)] = row
    return index


def _status_for_package_row(package_row, historical_row):
    proposed_evidence = str(package_row.get("proposed_evidence", "") or "").strip().lower()
    proposed_source = str(package_row.get("proposed_membership_source_url", "") or "").strip()
    decision = str(package_row.get("confirmation_decision", "") or "").strip().lower()
    if decision not in {"approve", "approved"}:
        return "invalid_approved_package_row", "confirmation_decision_not_approved"
    if proposed_evidence != "verified" or not proposed_source:
        return "invalid_approved_package_row", "verified_source_required"
    if not historical_row:
        return "missing_historical_row", "week_ticker_not_found_in_historical_membership"
    current_evidence = str(historical_row.get("membership_evidence", "") or "").strip().lower()
    if current_evidence == "verified":
        return "already_verified", "historical_membership_already_verified"
    return "ready_to_apply_manually", "approved_verified_source_can_upgrade_historical_row"


def _plan_item(package_row, historical_row):
    status, reason = _status_for_package_row(package_row, historical_row)
    return {
        "week": str(package_row.get("week", "") or "").strip(),
        "ticker": normalize_ticker(package_row.get("ticker")),
        "company_name": package_row.get("company_name", "") or (historical_row or {}).get("company_name", ""),
        "historical_current_evidence": (historical_row or {}).get("membership_evidence", ""),
        "historical_current_membership_source_url": (historical_row or {}).get("membership_source_url", ""),
        "proposed_evidence": str(package_row.get("proposed_evidence", "") or "").strip().lower(),
        "proposed_membership_source_url": package_row.get("proposed_membership_source_url", ""),
        "source_as_of_date": package_row.get("source_as_of_date", ""),
        "upgrade_scope": package_row.get("upgrade_scope", ""),
        "confirmation_decision": package_row.get("confirmation_decision", ""),
        "reviewer": package_row.get("reviewer", ""),
        "decision_notes": package_row.get("decision_notes", ""),
        "validation_status": status,
        "validation_reason": reason,
    }


def _overall_status(ready_count, invalid_count, missing_count, package_count):
    if ready_count:
        return "ready_for_manual_apply_review"
    if invalid_count or missing_count:
        return "needs_review"
    if package_count:
        return "clear"
    return "clear"


def build_approved_apply_plan(approved_package, membership_path, as_of_date=None):
    package_rows = _read_csv(approved_package)
    membership_rows = _read_csv(membership_path)
    historical = _historical_index(membership_rows)
    items = []
    for row in package_rows:
        week, ticker = _row_key(row)
        if not week or not ticker:
            continue
        items.append(_plan_item(row, historical.get((week, ticker))))

    ready_count = sum(1 for item in items if item["validation_status"] == "ready_to_apply_manually")
    already_verified_count = sum(1 for item in items if item["validation_status"] == "already_verified")
    missing_count = sum(1 for item in items if item["validation_status"] == "missing_historical_row")
    invalid_count = sum(1 for item in items if item["validation_status"] == "invalid_approved_package_row")
    return {
        "plan_schema": PLAN_SCHEMA,
        "plan_version": PLAN_VERSION,
        "as_of_date": as_of_date or date.today().isoformat(),
        "status": _overall_status(ready_count, invalid_count, missing_count, len(items)),
        "approved_package_path": str(Path(approved_package)),
        "membership_path": str(Path(membership_path)),
        "approved_package_row_count": len(items),
        "membership_row_count": len(membership_rows),
        "ready_to_apply_count": ready_count,
        "already_verified_count": already_verified_count,
        "missing_historical_row_count": missing_count,
        "invalid_approved_package_row_count": invalid_count,
        "requires_manual_apply": ready_count > 0,
        "would_modify_historical_membership": False,
        "applied_to_historical_membership": False,
        "formal_backtest_upgrade_allowed": False,
        "items": items,
        "boundary": (
            "Only prepares a read-only manual apply plan from approved evidence rows; "
            "does not modify historical_membership.csv or formal model parameters."
        ),
    }


def render_markdown(payload):
    lines = [
        "# membership_evidence_approved_apply_plan",
        "",
        f"- as_of_date: {payload.get('as_of_date', '')}",
        f"- status: {payload.get('status', '')}",
        f"- approved_package_row_count: {payload.get('approved_package_row_count', 0)}",
        f"- ready_to_apply_count: {payload.get('ready_to_apply_count', 0)}",
        f"- already_verified_count: {payload.get('already_verified_count', 0)}",
        f"- missing_historical_row_count: {payload.get('missing_historical_row_count', 0)}",
        f"- invalid_approved_package_row_count: {payload.get('invalid_approved_package_row_count', 0)}",
        f"- requires_manual_apply: {str(payload.get('requires_manual_apply')).lower()}",
        f"- would_modify_historical_membership: {str(payload.get('would_modify_historical_membership')).lower()}",
        f"- applied_to_historical_membership: {str(payload.get('applied_to_historical_membership')).lower()}",
        f"- formal_backtest_upgrade_allowed: {str(payload.get('formal_backtest_upgrade_allowed')).lower()}",
        "",
        "| week | ticker | current | proposed | status | reason |",
        "|---|---|---|---|---|---|",
    ]
    for item in payload.get("items", []) or []:
        lines.append(
            "| {week} | {ticker} | {historical_current_evidence} | {proposed_evidence} | {validation_status} | {validation_reason} |".format(
                **item
            )
        )
    if not payload.get("items"):
        lines.append("| - | - | - | - | - | - |")
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
        writer = csv.DictWriter(handle, fieldnames=PLAN_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(payload.get("items", []) or [])


def write_text(text, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8-sig")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build a read-only approved membership evidence apply plan.")
    parser.add_argument("--approved-package", default="outputs/automation/latest_membership_evidence_approved_apply_package.csv")
    parser.add_argument("--membership", default="outputs/backtests/us_3y_weekly/historical_membership.csv")
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--output-json", default="outputs/automation/latest_membership_evidence_approved_apply_plan.json")
    parser.add_argument("--output-csv", default="outputs/automation/latest_membership_evidence_approved_apply_plan.csv")
    parser.add_argument("--output-md", default="outputs/automation/latest_membership_evidence_approved_apply_plan.md")
    args = parser.parse_args()

    payload = build_approved_apply_plan(
        args.approved_package,
        args.membership,
        as_of_date=args.as_of_date or None,
    )
    report = render_markdown(payload)
    write_json(payload, args.output_json)
    write_csv(payload, args.output_csv)
    write_text(report, args.output_md)
    print(report)


if __name__ == "__main__":
    main()
