import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path


QUEUE_SCHEMA = "membership_evidence_supplement_queue"
QUEUE_VERSION = 1
CSV_FIELDS = [
    "priority",
    "ticker",
    "company_name",
    "effective_date",
    "weeks_affected",
    "current_evidence",
    "import_status",
    "required_evidence_kind",
    "accepted_source_domains",
    "rejected_source_url",
    "rejected_source_trust_level",
    "rejection_reason",
    "recommended_action",
]


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


def _rejection_reason(item):
    status = str(item.get("import_status", "") or "").strip()
    trust = str(item.get("source_trust_level", "") or "").strip()
    if status == "missing_current_source":
        return "missing_current_source"
    if trust:
        return f"{trust}_cannot_upgrade_historical_membership"
    return "source_policy_cannot_upgrade_historical_membership"


def _queue_item(item, priority):
    return {
        "priority": priority,
        "ticker": item.get("ticker", ""),
        "company_name": item.get("company_name", ""),
        "effective_date": item.get("effective_date", ""),
        "weeks_affected": _int_value(item.get("weeks_affected"), 0),
        "current_evidence": item.get("current_evidence", ""),
        "import_status": item.get("import_status", ""),
        "required_evidence_kind": "official_spglobal_membership_evidence",
        "accepted_source_domains": "spglobal.com,.spglobal.com",
        "rejected_source_url": item.get("membership_source_url", ""),
        "rejected_source_trust_level": item.get("source_trust_level", ""),
        "rejection_reason": _rejection_reason(item),
        "recommended_action": "supplement_official_spglobal_source",
    }


def build_supplement_queue(import_plan, as_of_date=None):
    plan = _read_json(import_plan)
    candidates = [
        item
        for item in plan.get("items", []) or []
        if isinstance(item, dict) and item.get("import_status") != "ready_current_source"
    ]
    candidates = sorted(
        candidates,
        key=lambda item: (-_int_value(item.get("weeks_affected"), 0), str(item.get("ticker", ""))),
    )
    items = [_queue_item(item, index) for index, item in enumerate(candidates, start=1)]
    return {
        "queue_schema": QUEUE_SCHEMA,
        "queue_version": QUEUE_VERSION,
        "as_of_date": as_of_date or date.today().isoformat(),
        "status": "action_required" if items else "clear",
        "source_import_plan": str(Path(import_plan)),
        "queue_count": len(items),
        "ready_to_import_count": _int_value(plan.get("ready_to_import_count"), 0),
        "missing_source_count": _int_value(plan.get("missing_source_count"), 0),
        "invalid_source_count": _int_value(plan.get("invalid_source_count"), 0),
        "blocked_by_source_policy_count": _int_value(plan.get("blocked_by_source_policy_count"), 0),
        "official_evidence_required_count": len(items),
        "formal_backtest_upgrade_allowed": False,
        "items": items,
        "boundary": (
            "只生成 S&P 500 历史成分证据补强工作包；不抓取网页，不修改 historical_membership.csv，"
            "不把 crosscheck、ETF 或 secondary 来源升级为 verified。"
        ),
    }


def render_markdown(payload):
    lines = [
        "# membership_evidence_supplement_queue",
        "",
        f"- as_of_date: {payload.get('as_of_date', '')}",
        f"- status: {payload.get('status', '')}",
        f"- queue_count: {payload.get('queue_count', 0)}",
        f"- ready_to_import_count: {payload.get('ready_to_import_count', 0)}",
        f"- missing_source_count: {payload.get('missing_source_count', 0)}",
        f"- invalid_source_count: {payload.get('invalid_source_count', 0)}",
        f"- blocked_by_source_policy_count: {payload.get('blocked_by_source_policy_count', 0)}",
        f"- official_evidence_required_count: {payload.get('official_evidence_required_count', 0)}",
        f"- formal_backtest_upgrade_allowed: {str(payload.get('formal_backtest_upgrade_allowed')).lower()}",
        "",
        "| priority | ticker | company | weeks | required_evidence | rejected_source | reason |",
        "|---:|---|---|---:|---|---|---|",
    ]
    for item in payload.get("items", []) or []:
        lines.append(
            "| {priority} | {ticker} | {company_name} | {weeks_affected} | "
            "{required_evidence_kind} | {rejected_source_trust_level} | {rejection_reason} |".format(**item)
        )
    if not payload.get("items"):
        lines.append("| - | - | - | - | - | - | - |")
    lines.extend(["", "## boundary", "", f"- {payload.get('boundary', '')}", ""])
    return "\n".join(lines)


def write_json(payload, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8-sig",
    )


def write_csv(payload, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(payload.get("items", []) or [])


def write_text(text, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8-sig")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build S&P 500 verified membership evidence supplement queue.")
    parser.add_argument("--import-plan", default="outputs/automation/latest_membership_evidence_import_plan.json")
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--output-json", default="outputs/automation/latest_membership_evidence_supplement_queue.json")
    parser.add_argument("--output-csv", default="outputs/automation/latest_membership_evidence_supplement_queue.csv")
    parser.add_argument("--output-md", default="outputs/automation/latest_membership_evidence_supplement_queue.md")
    args = parser.parse_args()

    payload = build_supplement_queue(args.import_plan, as_of_date=args.as_of_date or None)
    report = render_markdown(payload)
    write_json(payload, args.output_json)
    write_csv(payload, args.output_csv)
    write_text(report, args.output_md)
    print(report)


if __name__ == "__main__":
    main()
