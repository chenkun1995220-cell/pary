import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

from sp500_constituents import normalize_ticker


CONFIRMATION_SCHEMA = "membership_evidence_apply_confirmation_status"
CONFIRMATION_VERSION = 1
TEMPLATE_FIELDS = [
    "week",
    "ticker",
    "company_name",
    "current_evidence",
    "proposed_evidence",
    "proposed_membership_source_url",
    "source_as_of_date",
    "confirmation_decision",
    "reviewer",
    "decision_notes",
]
STATUS_FIELDS = TEMPLATE_FIELDS + [
    "validation_status",
    "validation_reason",
]
APPROVED_PACKAGE_FIELDS = [
    "week",
    "ticker",
    "company_name",
    "current_evidence",
    "current_membership_source_url",
    "proposed_evidence",
    "proposed_membership_source_url",
    "source_as_of_date",
    "upgrade_scope",
    "confirmation_decision",
    "reviewer",
    "decision_notes",
]


def _read_json(path):
    source = Path(path)
    if not source.exists():
        return {}
    return json.loads(source.read_text(encoding="utf-8-sig"))


def _read_csv(path):
    source = Path(path)
    if not source.exists():
        return []
    with source.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _preview_items(payload):
    items = []
    for item in payload.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        ticker = normalize_ticker(item.get("ticker"))
        week = str(item.get("week", "") or "").strip()
        if not ticker or not week:
            continue
        row = dict(item)
        row["ticker"] = ticker
        row["week"] = week
        items.append(row)
    return items


def _decision_key(row):
    return (
        str(row.get("week", "") or "").strip(),
        normalize_ticker(row.get("ticker")),
    )


def _write_template(items, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TEMPLATE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for item in items:
            writer.writerow(
                {
                    "week": item.get("week", ""),
                    "ticker": item.get("ticker", ""),
                    "company_name": item.get("company_name", ""),
                    "current_evidence": item.get("current_evidence", ""),
                    "proposed_evidence": item.get("proposed_evidence", ""),
                    "proposed_membership_source_url": item.get("proposed_membership_source_url", ""),
                    "source_as_of_date": item.get("source_as_of_date", ""),
                    "confirmation_decision": "",
                    "reviewer": "",
                    "decision_notes": "",
                }
            )


def _status_for_decision(item, decision):
    if not decision:
        return {
            "confirmation_decision": "",
            "reviewer": "",
            "decision_notes": "",
            "validation_status": "pending_manual_confirmation",
            "validation_reason": "confirmation_decision_missing",
        }
    value = str(decision.get("confirmation_decision", "") or "").strip().lower()
    reviewer = str(decision.get("reviewer", "") or "").strip()
    notes = str(decision.get("decision_notes", "") or "").strip()
    if value in {"approve", "approved"}:
        return {
            "confirmation_decision": "approve",
            "reviewer": reviewer,
            "decision_notes": notes,
            "validation_status": "approved",
            "validation_reason": "manual_confirmation_approved",
        }
    if value in {"reject", "rejected"}:
        return {
            "confirmation_decision": "reject",
            "reviewer": reviewer,
            "decision_notes": notes,
            "validation_status": "rejected",
            "validation_reason": "manual_confirmation_rejected",
        }
    return {
        "confirmation_decision": value,
        "reviewer": reviewer,
        "decision_notes": notes,
        "validation_status": "invalid_decision",
        "validation_reason": "confirmation_decision_must_be_approve_or_reject",
    }


def _status_for_counts(approved_count, rejected_count, invalid_count, pending_count):
    if approved_count and (rejected_count or invalid_count):
        return "ready_with_rejections"
    if approved_count and not pending_count:
        return "ready_to_package"
    if invalid_count:
        return "needs_review"
    if pending_count:
        return "awaiting_manual_confirmation"
    return "clear"


def _write_csv(rows, path, fields):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_apply_confirmation_status(
    apply_preview,
    decisions_path,
    template_path,
    approved_package_path,
    as_of_date=None,
):
    preview = _read_json(apply_preview)
    preview_items = _preview_items(preview)
    template = Path(template_path)
    template_status = "existing" if template.exists() else "created"
    if not template.exists():
        _write_template(preview_items, template)
    decisions = {_decision_key(row): row for row in _read_csv(decisions_path)}
    items = []
    approved_package = []
    for item in preview_items:
        decision_status = _status_for_decision(item, decisions.get(_decision_key(item)))
        status_row = {
            **item,
            **decision_status,
        }
        items.append(status_row)
        if decision_status["validation_status"] == "approved":
            approved_package.append(status_row)
    approved_count = sum(1 for item in items if item["validation_status"] == "approved")
    rejected_count = sum(1 for item in items if item["validation_status"] == "rejected")
    invalid_count = sum(1 for item in items if item["validation_status"] == "invalid_decision")
    pending_count = sum(1 for item in items if item["validation_status"] == "pending_manual_confirmation")
    _write_csv(approved_package, approved_package_path, APPROVED_PACKAGE_FIELDS)
    return {
        "confirmation_schema": CONFIRMATION_SCHEMA,
        "confirmation_version": CONFIRMATION_VERSION,
        "as_of_date": as_of_date or date.today().isoformat(),
        "status": _status_for_counts(approved_count, rejected_count, invalid_count, pending_count),
        "apply_preview": str(Path(apply_preview)),
        "decisions_path": str(Path(decisions_path)),
        "template_path": str(template),
        "template_status": template_status,
        "approved_package_path": str(Path(approved_package_path)),
        "preview_row_count": len(preview_items),
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "invalid_count": invalid_count,
        "pending_count": pending_count,
        "approved_package_row_count": len(approved_package),
        "applied_to_historical_membership": False,
        "formal_backtest_upgrade_allowed": False,
        "items": items,
        "boundary": (
            "Only records manual confirmation of apply-preview rows and writes an approved package; "
            "does not modify historical_membership.csv or formal model parameters."
        ),
    }


def render_markdown(payload):
    lines = [
        "# membership_evidence_apply_confirmation_status",
        "",
        f"- as_of_date: {payload.get('as_of_date', '')}",
        f"- status: {payload.get('status', '')}",
        f"- preview_row_count: {payload.get('preview_row_count', 0)}",
        f"- approved_count: {payload.get('approved_count', 0)}",
        f"- rejected_count: {payload.get('rejected_count', 0)}",
        f"- invalid_count: {payload.get('invalid_count', 0)}",
        f"- pending_count: {payload.get('pending_count', 0)}",
        f"- approved_package_row_count: {payload.get('approved_package_row_count', 0)}",
        f"- applied_to_historical_membership: {str(payload.get('applied_to_historical_membership')).lower()}",
        f"- formal_backtest_upgrade_allowed: {str(payload.get('formal_backtest_upgrade_allowed')).lower()}",
        "",
        "| week | ticker | decision | status | reason |",
        "|---|---|---|---|---|",
    ]
    for item in payload.get("items", []) or []:
        lines.append(
            "| {week} | {ticker} | {confirmation_decision} | {validation_status} | {validation_reason} |".format(
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


def write_status_csv(payload, path):
    _write_csv(payload.get("items", []) or [], path, STATUS_FIELDS)


def write_text(text, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8-sig")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Validate manual confirmation for membership evidence apply preview.")
    parser.add_argument("--apply-preview", default="outputs/automation/latest_membership_evidence_apply_preview.json")
    parser.add_argument("--decisions", default="inputs/sp500_membership_evidence/apply_confirmation_decisions.csv")
    parser.add_argument("--template", default="outputs/automation/membership_evidence_apply_confirmation_decisions_template.csv")
    parser.add_argument("--approved-package", default="outputs/automation/latest_membership_evidence_approved_apply_package.csv")
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--output-json", default="outputs/automation/latest_membership_evidence_apply_confirmation_status.json")
    parser.add_argument("--output-csv", default="outputs/automation/latest_membership_evidence_apply_confirmation_status.csv")
    parser.add_argument("--output-md", default="outputs/automation/latest_membership_evidence_apply_confirmation_status.md")
    args = parser.parse_args()

    payload = build_apply_confirmation_status(
        args.apply_preview,
        decisions_path=args.decisions,
        template_path=args.template,
        approved_package_path=args.approved_package,
        as_of_date=args.as_of_date or None,
    )
    report = render_markdown(payload)
    write_json(payload, args.output_json)
    write_status_csv(payload, args.output_csv)
    write_text(report, args.output_md)
    print(report)


if __name__ == "__main__":
    main()
