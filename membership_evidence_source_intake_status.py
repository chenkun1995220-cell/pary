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
    "batch_id",
    "batch_rank",
    "official_domain_search_query",
    "official_index_page_url",
    "manual_entry_instruction",
    "validation_command",
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
DEFAULT_VALIDATION_COMMAND = (
    "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
    "scripts\\run_membership_evidence_source_intake_status.ps1"
)
OFFICIAL_INDEX_PAGE_URL = "https://www.spglobal.com/spdji/en/indices/equity/sp-500/"


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


def _parse_iso_date(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _manual_entry_instruction(ticker, accepted_domains):
    return (
        f"Fill {ticker}: membership_evidence=verified; membership_source_url must be official S&P Global HTTPS "
        f"domain ({accepted_domains}); source_as_of_date must use YYYY-MM-DD and not be later than review date; "
        f"use official_domain_search_query to find official pages, but the search query is not evidence."
    )


def _official_domain_search_query(ticker, company_name):
    parts = [
        "site:spglobal.com/spdji",
        '"S&P 500"',
        f'"{ticker}"',
    ]
    if company_name:
        parts.append(f'"{company_name}"')
    return " ".join(parts)


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


def _validate_intake_row(queue_item, intake_row, review_date=None):
    ticker = queue_item.get("ticker", "")
    company_name = queue_item.get("company_name", "")
    accepted_domains = queue_item.get("accepted_source_domains", "spglobal.com,.spglobal.com")
    default_instruction = _manual_entry_instruction(ticker, accepted_domains)
    default_search_query = _official_domain_search_query(ticker, company_name)
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
            "batch_id": "",
            "batch_rank": 0,
            "official_domain_search_query": default_search_query,
            "official_index_page_url": OFFICIAL_INDEX_PAGE_URL,
            "manual_entry_instruction": default_instruction,
            "validation_command": DEFAULT_VALIDATION_COMMAND,
            "notes": "",
            "reviewer": "",
        }

    evidence = str(intake_row.get("membership_evidence", "") or "").strip().lower()
    source_url = str(intake_row.get("membership_source_url", "") or "").strip()
    source_as_of_date = str(intake_row.get("source_as_of_date", "") or "").strip()
    source_date = _parse_iso_date(source_as_of_date)
    evidence_kind = str(intake_row.get("evidence_kind", "") or "").strip() or "current_constituents"
    batch_id = str(intake_row.get("batch_id", "") or "").strip()
    batch_rank = _int_value(intake_row.get("batch_rank"), 0)
    official_domain_search_query = (
        str(intake_row.get("official_domain_search_query", "") or "").strip()
        or _official_domain_search_query(ticker, intake_row.get("company_name") or company_name)
    )
    official_index_page_url = (
        str(intake_row.get("official_index_page_url", "") or "").strip()
        or OFFICIAL_INDEX_PAGE_URL
    )
    manual_entry_instruction = str(intake_row.get("manual_entry_instruction", "") or "").strip() or default_instruction
    validation_command = str(intake_row.get("validation_command", "") or "").strip() or DEFAULT_VALIDATION_COMMAND
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
            "batch_id": batch_id,
            "batch_rank": batch_rank,
            "official_domain_search_query": official_domain_search_query,
            "official_index_page_url": official_index_page_url,
            "manual_entry_instruction": manual_entry_instruction,
            "validation_command": validation_command,
            "notes": intake_row.get("notes", ""),
            "reviewer": intake_row.get("reviewer", ""),
        }
    policy = classify_membership_source(source_url, evidence_kind=evidence_kind)
    review_date = review_date if isinstance(review_date, date) else None
    is_future_source_date = bool(source_date and review_date and source_date > review_date)
    is_ready = (
        evidence == "verified"
        and source_as_of_date
        and source_date
        and not is_future_source_date
        and policy["can_upgrade_membership"]
    )
    if is_ready:
        validation_status = "ready_current_source"
        validation_reason = policy["reason"]
    elif evidence != "verified":
        validation_status = "invalid_evidence_status"
        validation_reason = "membership_evidence_must_be_verified"
    elif not source_as_of_date:
        validation_status = "invalid_missing_source_date"
        validation_reason = "source_as_of_date_required"
    elif not source_date:
        validation_status = "invalid_source_date"
        validation_reason = "source_as_of_date_invalid"
    elif is_future_source_date:
        validation_status = "invalid_future_source_date"
        validation_reason = "source_as_of_date_after_review_date"
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
        "batch_id": batch_id,
        "batch_rank": batch_rank,
        "official_domain_search_query": official_domain_search_query,
        "official_index_page_url": official_index_page_url,
        "manual_entry_instruction": manual_entry_instruction,
        "validation_command": validation_command,
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


def _current_batch_summary(items):
    batch_items = [item for item in items if item.get("batch_id")]
    if not batch_items:
        return {
            "current_batch_id": "",
            "current_batch_count": 0,
            "current_batch_ready_count": 0,
            "current_batch_pending_count": 0,
            "current_batch_invalid_count": 0,
            "current_batch_completion_ratio": 0.0,
            "current_batch_tickers": [],
            "current_batch_manual_checklist": [],
        }
    latest_batch_id = sorted(
        {str(item.get("batch_id", "")) for item in batch_items if item.get("batch_id")}
    )[-1]
    current_items = [item for item in batch_items if item.get("batch_id") == latest_batch_id]
    ready_count = sum(1 for item in current_items if item["validation_status"] == "ready_current_source")
    pending_count = sum(1 for item in current_items if item["validation_status"] == "pending_manual_evidence")
    invalid_count = len(current_items) - ready_count - pending_count
    sorted_items = sorted(
        current_items,
        key=lambda row: (_int_value(row.get("batch_rank"), 0), row.get("ticker", "")),
    )
    return {
        "current_batch_id": latest_batch_id,
        "current_batch_count": len(current_items),
        "current_batch_ready_count": ready_count,
        "current_batch_pending_count": pending_count,
        "current_batch_invalid_count": invalid_count,
        "current_batch_completion_ratio": round(ready_count / len(current_items), 4) if current_items else 0.0,
        "current_batch_tickers": [
            item.get("ticker", "")
            for item in sorted_items
            if item.get("ticker")
        ],
        "current_batch_manual_checklist": [
            {
                "batch_rank": _int_value(item.get("batch_rank"), 0),
                "ticker": item.get("ticker", ""),
                "company_name": item.get("company_name", ""),
                "validation_status": item.get("validation_status", ""),
                "validation_reason": item.get("validation_reason", ""),
                "official_domain_search_query": item.get("official_domain_search_query", ""),
                "official_index_page_url": item.get("official_index_page_url", ""),
                "manual_entry_instruction": item.get("manual_entry_instruction", ""),
                "validation_command": item.get("validation_command", ""),
            }
            for item in sorted_items
            if item.get("validation_status") != "ready_current_source"
        ],
    }


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
    review_date = _parse_iso_date(as_of_date) if as_of_date else date.today()
    items = [_validate_intake_row(item, intake_lookup.get(item["ticker"]), review_date) for item in queue_items]
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
        **_current_batch_summary(items),
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
        f"- current_batch_id: {payload.get('current_batch_id', '')}",
        f"- current_batch_count: {payload.get('current_batch_count', 0)}",
        f"- current_batch_ready_count: {payload.get('current_batch_ready_count', 0)}",
        f"- current_batch_pending_count: {payload.get('current_batch_pending_count', 0)}",
        f"- current_batch_invalid_count: {payload.get('current_batch_invalid_count', 0)}",
        f"- current_batch_completion_ratio: {payload.get('current_batch_completion_ratio', 0)}",
        f"- current_batch_tickers: {', '.join(payload.get('current_batch_tickers') or [])}",
        f"- template_status: {payload.get('template_status', '')}",
        f"- formal_backtest_upgrade_allowed: {str(payload.get('formal_backtest_upgrade_allowed')).lower()}",
        "",
        "## current_batch_manual_checklist",
        "",
        "| batch_rank | ticker | company | status | reason | official_domain_search_query | official_index_page_url | instruction | validation_command |",
        "|---:|---|---|---|---|---|---|---|---|",
    ]
    for item in payload.get("current_batch_manual_checklist", []) or []:
        lines.append(
            "| {batch_rank} | {ticker} | {company_name} | {validation_status} | "
            "{validation_reason} | {official_domain_search_query} | {official_index_page_url} | "
            "{manual_entry_instruction} | {validation_command} |".format(**item)
        )
    if not payload.get("current_batch_manual_checklist"):
        lines.append("| - | - | - | - | - | - | - | - | - |")
    lines.extend([
        "",
        "| priority | ticker | company | status | trust | source_date | reason |",
        "|---:|---|---|---|---|---|---|",
    ])
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
