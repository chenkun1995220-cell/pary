import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote_plus

from sp500_constituents import normalize_ticker


BATCH_SCHEMA = "membership_evidence_supplement_batch"
BATCH_VERSION = 1
BATCH_FIELDS = [
    "batch_id",
    "batch_rank",
    "queue_priority",
    "ticker",
    "company_name",
    "effective_date",
    "weeks_affected",
    "current_evidence",
    "required_evidence_kind",
    "accepted_source_domains",
    "rejection_reason",
    "membership_evidence",
    "membership_source_url",
    "source_as_of_date",
    "evidence_kind",
    "notes",
    "reviewer",
    "official_domain_search_query",
    "official_domain_search_url",
    "official_index_page_url",
    "manual_entry_instruction",
    "validation_command",
]
OFFICIAL_INDEX_PAGE_URL = "https://www.spglobal.com/spdji/en/indices/equity/sp-500/"


def _read_json(path):
    source = Path(path)
    if not source.exists():
        return {}
    return json.loads(source.read_text(encoding="utf-8-sig"))


def _int_value(value, default=0):
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _queue_items(payload):
    items = []
    for item in payload.get("items", []) or []:
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


def _official_domain_search_query(ticker, company_name):
    parts = [
        "site:spglobal.com/spdji",
        '"S&P 500"',
        f'"{ticker}"',
    ]
    if company_name:
        parts.append(f'"{company_name}"')
    return " ".join(parts)


def _official_domain_search_url(query):
    return f"https://www.google.com/search?q={quote_plus(query)}"


def _batch_item(item, batch_id, batch_rank):
    ticker = item.get("ticker", "")
    company_name = item.get("company_name", "")
    accepted_domains = item.get("accepted_source_domains", "spglobal.com,.spglobal.com")
    validation_command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_membership_evidence_source_intake_status.ps1"
    search_query = _official_domain_search_query(ticker, company_name)
    return {
        "batch_id": batch_id,
        "batch_rank": batch_rank,
        "queue_priority": item.get("priority", 0),
        "ticker": ticker,
        "company_name": company_name,
        "effective_date": item.get("effective_date", ""),
        "weeks_affected": _int_value(item.get("weeks_affected"), 0),
        "current_evidence": item.get("current_evidence", ""),
        "required_evidence_kind": item.get("required_evidence_kind", "official_spglobal_membership_evidence"),
        "accepted_source_domains": accepted_domains,
        "rejection_reason": item.get("rejection_reason", ""),
        "membership_evidence": "",
        "membership_source_url": "",
        "source_as_of_date": "",
        "evidence_kind": "current_constituents",
        "notes": "",
        "reviewer": "",
        "official_domain_search_query": search_query,
        "official_domain_search_url": _official_domain_search_url(search_query),
        "official_index_page_url": OFFICIAL_INDEX_PAGE_URL,
        "manual_entry_instruction": (
            f"Fill {ticker}: membership_evidence=verified; membership_source_url must be official S&P Global HTTPS "
            f"domain ({accepted_domains}); source_as_of_date must use YYYY-MM-DD and not be later than review date; "
            f"use official_domain_search_query to find official pages, but the search query is not evidence."
        ),
        "validation_command": validation_command,
    }


def build_supplement_batch(queue, batch_size=10, as_of_date=None):
    queue_payload = _read_json(queue)
    items = _queue_items(queue_payload)
    size = max(1, _int_value(batch_size, 10))
    selected = items[:size]
    current_date = as_of_date or date.today().isoformat()
    batch_id = f"{current_date}-p1"
    batch_items = [_batch_item(item, batch_id, index) for index, item in enumerate(selected, start=1)]
    return {
        "batch_schema": BATCH_SCHEMA,
        "batch_version": BATCH_VERSION,
        "as_of_date": current_date,
        "status": "batch_ready" if batch_items else "clear",
        "source_queue": str(Path(queue)),
        "batch_id": batch_id,
        "batch_size": size,
        "queue_count": len(items),
        "selected_count": len(batch_items),
        "remaining_after_batch_count": max(len(items) - len(batch_items), 0),
        "batch_tickers": [item["ticker"] for item in batch_items],
        "batch_weeks_affected": sum(_int_value(item.get("weeks_affected"), 0) for item in batch_items),
        "completion_condition": (
            "Fill these tickers in inputs/sp500_membership_evidence/verified_membership_evidence_intake.csv "
            "with verified S&P Global source URLs, then rerun run_membership_evidence_source_intake_status.ps1."
        ),
        "manual_entry_rules": [
            "membership_evidence must be verified.",
            "membership_source_url must be an official S&P Global HTTPS URL under spglobal.com.",
            "source_as_of_date must use YYYY-MM-DD and must not be later than the review date.",
            "official_domain_search_query is only a manual lookup aid; do not paste search results as evidence.",
            "ETF holdings, Wikipedia, GitHub, Kaggle, crosscheck, or secondary sources remain reference-only.",
        ],
        "validation_command": "powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_membership_evidence_source_intake_status.ps1",
        "next_command_after_ready": "powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_membership_evidence_import_plan_from_verified_intake.ps1",
        "intake_draft_path": "",
        "applied_to_historical_membership": False,
        "formal_backtest_upgrade_allowed": False,
        "items": batch_items,
        "boundary": (
            "只生成本批次人工补证工作包；不抓取网页，不修改 historical_membership.csv，"
            "不把 crosscheck、ETF 或 secondary 来源升级为 verified。"
        ),
    }


def render_markdown(payload):
    lines = [
        "# membership_evidence_supplement_batch",
        "",
        f"- as_of_date: {payload.get('as_of_date', '')}",
        f"- status: {payload.get('status', '')}",
        f"- batch_id: {payload.get('batch_id', '')}",
        f"- queue_count: {payload.get('queue_count', 0)}",
        f"- batch_size: {payload.get('batch_size', 0)}",
        f"- selected_count: {payload.get('selected_count', 0)}",
        f"- remaining_after_batch_count: {payload.get('remaining_after_batch_count', 0)}",
        f"- batch_tickers: {', '.join(payload.get('batch_tickers') or [])}",
        f"- batch_weeks_affected: {payload.get('batch_weeks_affected', 0)}",
        f"- intake_draft_path: {payload.get('intake_draft_path', '')}",
        f"- validation_command: {payload.get('validation_command', '')}",
        f"- next_command_after_ready: {payload.get('next_command_after_ready', '')}",
        f"- applied_to_historical_membership: {str(payload.get('applied_to_historical_membership')).lower()}",
        f"- formal_backtest_upgrade_allowed: {str(payload.get('formal_backtest_upgrade_allowed')).lower()}",
        "",
        "## manual_entry_rules",
        "",
    ]
    for rule in payload.get("manual_entry_rules", []) or []:
        lines.append(f"- {rule}")
    lines.extend([
        "",
        "## completion_condition",
        "",
        f"- {payload.get('completion_condition', '')}",
        "",
        "## official_domain_search_guidance",
        "",
        f"- official_index_page_url: {OFFICIAL_INDEX_PAGE_URL}",
        "- Use official_domain_search_query or official_domain_search_url only to locate S&P Global pages or announcements; it is not evidence.",
        "",
        "| batch_rank | ticker | company | weeks | official_domain_search_query | official_domain_search_url | required_evidence | reason |",
        "|---:|---|---|---:|---|---|---|---|",
    ])
    for item in payload.get("items", []) or []:
        lines.append(
            "| {batch_rank} | {ticker} | {company_name} | {weeks_affected} | "
            "{official_domain_search_query} | {official_domain_search_url} | "
            "{required_evidence_kind} | {rejection_reason} |".format(**item)
        )
    if not payload.get("items"):
        lines.append("| - | - | - | - | - | - | - | - |")
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
        writer = csv.DictWriter(handle, fieldnames=BATCH_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(payload.get("items", []) or [])


def write_text(text, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8-sig")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build a focused manual batch from the S&P 500 verified evidence supplement queue.")
    parser.add_argument("--queue", default="outputs/automation/latest_membership_evidence_supplement_queue.json")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--output-json", default="outputs/automation/latest_membership_evidence_supplement_batch.json")
    parser.add_argument("--output-csv", default="outputs/automation/latest_membership_evidence_supplement_batch.csv")
    parser.add_argument("--output-md", default="outputs/automation/latest_membership_evidence_supplement_batch.md")
    parser.add_argument("--intake-draft", default="")
    args = parser.parse_args()

    payload = build_supplement_batch(args.queue, batch_size=args.batch_size, as_of_date=args.as_of_date or None)
    if args.intake_draft:
        payload["intake_draft_path"] = str(Path(args.intake_draft))
    report = render_markdown(payload)
    write_json(payload, args.output_json)
    write_csv(payload, args.output_csv)
    if args.intake_draft:
        write_csv(payload, args.intake_draft)
    write_text(report, args.output_md)
    print(report)


if __name__ == "__main__":
    main()
