import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

from sp500_constituents import normalize_ticker
from sp500_membership_source_policy import classify_membership_source


STATUS_SCHEMA = "membership_evidence_source_intake_status"
STATUS_VERSION = 1
TEMPLATE_FIELDS = [
    "ticker",
    "company_name",
    "membership_evidence",
    "membership_source_url",
    "source_as_of_date",
    "evidence_kind",
    "notes",
    "reviewer",
]
STATUS_FIELDS = [
    "priority",
    "ticker",
    "company_name",
    "effective_date",
    "weeks_affected",
    "membership_evidence",
    "membership_source_url",
    "source_as_of_date",
    "evidence_kind",
    "source_trust_level",
    "can_upgrade_membership",
    "validation_status",
    "validation_reason",
    "notes",
    "reviewer",
]
SOURCE_PACK_FIELDS = [
    "ticker",
    "membership_evidence",
    "membership_source_url",
    "source_as_of_date",
    "notes",
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


def _int_value(value, default=0):
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _queue_items(queue_payload):
    items = []
    for item in queue_payload.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        ticker = normalize_ticker(item.get("ticker"))
        if not ticker:
            continue
        row = dict(item)
        row["ticker"] = ticker
        row["priority"] = _int_value(row.get("priority"), len(items) + 1)
        row["weeks_affected"] = _int_value(row.get("weeks_affected"), 0)
        items.append(row)
    return sorted(items, key=lambda row: (_int_value(row.get("priority"), 0), row.get("ticker", "")))


def _write_template(queue_items, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TEMPLATE_FIELDS)
        writer.writeheader()
        for item in queue_items:
            writer.writerow(
                {
                    "ticker": item.get("ticker", ""),
                    "company_name": item.get("company_name", ""),
                    "membership_evidence": "",
                    "membership_source_url": "",
                    "source_as_of_date": "",
                    "evidence_kind": "current_constituents",
                    "notes": "",
                    "reviewer": "",
                }
            )


def _intake_by_ticker(rows):
    by_ticker = {}
    for row in rows:
        ticker = normalize_ticker(row.get("ticker"))
        if ticker:
            by_ticker[ticker] = row
    return by_ticker


def _validate_intake_row(queue_item, intake_row):
    ticker = queue_item.get("ticker", "")
    if not intake_row:
        return {
            "priority": queue_item.get("priority", 0),
            "ticker": ticker,
            "company_name": queue_item.get("company_name", ""),
            "effective_date": queue_item.get("effective_date", ""),
            "weeks_affected": queue_item.get("weeks_affected", 0),
            "membership_evidence": "",
            "membership_source_url": "",
            "source_as_of_date": "",
            "evidence_kind": "current_constituents",
            "source_trust_level": "missing",
            "can_upgrade_membership": False,
            "validation_status": "pending_manual_evidence",
            "validation_reason": "manual_evidence_missing",
            "notes": "",
            "reviewer": "",
        }

    evidence = str(intake_row.get("membership_evidence", "") or "").strip().lower()
    source_url = str(intake_row.get("membership_source_url", "") or "").strip()
    source_as_of_date = str(intake_row.get("source_as_of_date", "") or "").strip()
    evidence_kind = str(intake_row.get("evidence_kind", "") or "").strip() or "current_constituents"
    if not evidence and not source_url and not source_as_of_date:
        return {
            "priority": queue_item.get("priority", 0),
            "ticker": ticker,
            "company_name": intake_row.get("company_name") or queue_item.get("company_name", ""),
            "effective_date": queue_item.get("effective_date", ""),
            "weeks_affected": queue_item.get("weeks_affected", 0),
            "membership_evidence": "",
            "membership_source_url": "",
            "source_as_of_date": "",
            "evidence_kind": evidence_kind,
            "source_trust_level": "missing",
            "can_upgrade_membership": False,
            "validation_status": "pending_manual_evidence",
            "validation_reason": "manual_evidence_missing",
            "notes": intake_row.get("notes", ""),
            "reviewer": intake_row.get("reviewer", ""),
        }
    policy = classify_membership_source(source_url, evidence_kind=evidence_kind)
    is_ready = evidence == "verified" and source_as_of_date and policy["can_upgrade_membership"]
    if is_ready:
        validation_status = "ready_current_source"
        validation_reason = policy["reason"]
    elif evidence != "verified":
        validation_status = "invalid_evidence_status"
        validation_reason = "membership_evidence_must_be_verified"
    elif not source_as_of_date:
        validation_status = "invalid_missing_source_date"
        validation_reason = "source_as_of_date_required"
    else:
        validation_status = "invalid_source_policy"
        validation_reason = f"{policy['reason']}_cannot_upgrade"

    return {
        "priority": queue_item.get("priority", 0),
        "ticker": ticker,
        "company_name": intake_row.get("company_name") or queue_item.get("company_name", ""),
        "effective_date": queue_item.get("effective_date", ""),
        "weeks_affected": queue_item.get("weeks_affected", 0),
        "membership_evidence": evidence,
        "membership_source_url": source_url,
        "source_as_of_date": source_as_of_date,
        "evidence_kind": evidence_kind,
        "source_trust_level": policy["trust_level"],
        "can_upgrade_membership": bool(policy["can_upgrade_membership"]),
        "validation_status": validation_status,
        "validation_reason": validation_reason,
        "notes": intake_row.get("notes", ""),
        "reviewer": intake_row.get("reviewer", ""),
    }


def _status_for_counts(ready_count, invalid_count, pending_count):
    if ready_count and invalid_count:
        return "ready_with_rejections"
    if ready_count:
        return "ready_to_preview"
    if invalid_count:
        return "needs_review"
    if pending_count:
        return "awaiting_manual_evidence"
    return "clear"


def _write_source_pack(items, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SOURCE_PACK_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for item in items:
            if item.get("validation_status") != "ready_current_source":
                continue
            writer.writerow(
                {
                    "ticker": item.get("ticker", ""),
                    "membership_evidence": "verified",
                    "membership_source_url": item.get("membership_source_url", ""),
                    "source_as_of_date": item.get("source_as_of_date", ""),
                    "notes": item.get("notes", ""),
                }
            )


def build_source_intake_status(queue, intake_path, template_path, source_pack_path="", as_of_date=None):
    queue_payload = _read_json(queue)
    queue_items = _queue_items(queue_payload)
    intake = Path(intake_path)
    template = Path(template_path)
    template_status = "existing" if template.exists() else "created"
    if not template.exists():
        _write_template(queue_items, template)

    intake_rows = _read_csv(intake)
    intake_lookup = _intake_by_ticker(intake_rows)
    items = [_validate_intake_row(item, intake_lookup.get(item["ticker"])) for item in queue_items]
    ready_count = sum(1 for item in items if item["validation_status"] == "ready_current_source")
    pending_count = sum(1 for item in items if item["validation_status"] == "pending_manual_evidence")
    invalid_count = len(items) - ready_count - pending_count
    ready_weeks = sum(_int_value(item.get("weeks_affected"), 0) for item in items if item["validation_status"] == "ready_current_source")
    invalid_weeks = sum(
        _int_value(item.get("weeks_affected"), 0)
        for item in items
        if item["validation_status"] not in {"ready_current_source", "pending_manual_evidence"}
    )
    source_pack = Path(source_pack_path) if source_pack_path else Path("outputs/automation/latest_membership_evidence_verified_source_pack.csv")
    _write_source_pack(items, source_pack)
    return {
        "status_schema": STATUS_SCHEMA,
        "status_version": STATUS_VERSION,
        "as_of_date": as_of_date or date.today().isoformat(),
        "status": _status_for_counts(ready_count, invalid_count, pending_count),
        "source_queue": str(Path(queue)),
        "intake_path": str(intake),
        "template_path": str(template),
        "template_status": template_status,
        "source_pack_path": str(source_pack),
        "source_pack_ready_count": ready_count,
        "queue_count": len(queue_items),
        "ready_to_import_count": ready_count,
        "ready_to_import_weeks_affected": ready_weeks,
        "invalid_count": invalid_count,
        "invalid_weeks_affected": invalid_weeks,
        "pending_count": pending_count,
        "formal_backtest_upgrade_allowed": False,
        "items": items,
        "boundary": (
            "只校验人工录入的 S&P 500 verified 成分证据；不抓取网页，不修改 historical_membership.csv，"
            "不把 crosscheck、ETF holdings、Wikipedia、GitHub、Kaggle 或 secondary 来源升级为 verified。"
        ),
    }


def render_markdown(payload):
    lines = [
        "# membership_evidence_source_intake_status",
        "",
        f"- as_of_date: {payload.get('as_of_date', '')}",
        f"- status: {payload.get('status', '')}",
        f"- queue_count: {payload.get('queue_count', 0)}",
        f"- ready_to_import_count: {payload.get('ready_to_import_count', 0)}",
        f"- invalid_count: {payload.get('invalid_count', 0)}",
        f"- pending_count: {payload.get('pending_count', 0)}",
        f"- template_status: {payload.get('template_status', '')}",
        f"- formal_backtest_upgrade_allowed: {str(payload.get('formal_backtest_upgrade_allowed')).lower()}",
        "",
        "| priority | ticker | company | status | trust | source_date | reason |",
        "|---:|---|---|---|---|---|---|",
    ]
    for item in payload.get("items", []) or []:
        lines.append(
            "| {priority} | {ticker} | {company_name} | {validation_status} | "
            "{source_trust_level} | {source_as_of_date} | {validation_reason} |".format(**item)
        )
    if not payload.get("items"):
        lines.append("| - | - | - | - | - | - | - |")
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
        writer = csv.DictWriter(handle, fieldnames=STATUS_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(payload.get("items", []) or [])


def write_text(text, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8-sig")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Validate manual S&P 500 membership evidence intake.")
    parser.add_argument("--queue", default="outputs/automation/latest_membership_evidence_supplement_queue.json")
    parser.add_argument("--intake", default="inputs/sp500_membership_evidence/verified_membership_evidence_intake.csv")
    parser.add_argument("--template", default="outputs/automation/us_sp500_verified_membership_evidence_intake_template.csv")
    parser.add_argument("--source-pack", default="outputs/automation/latest_membership_evidence_verified_source_pack.csv")
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--output-json", default="outputs/automation/latest_membership_evidence_source_intake_status.json")
    parser.add_argument("--output-csv", default="outputs/automation/latest_membership_evidence_source_intake_status.csv")
    parser.add_argument("--output-md", default="outputs/automation/latest_membership_evidence_source_intake_status.md")
    args = parser.parse_args()

    payload = build_source_intake_status(
        args.queue,
        intake_path=args.intake,
        template_path=args.template,
        source_pack_path=args.source_pack,
        as_of_date=args.as_of_date or None,
    )
    report = render_markdown(payload)
    write_json(payload, args.output_json)
    write_csv(payload, args.output_csv)
    write_text(report, args.output_md)
    print(report)


if __name__ == "__main__":
    main()
