import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

from sp500_membership_source_policy import classify_membership_source
from sp500_constituents import normalize_ticker


REVIEW_SCHEMA = "membership_evidence_import_plan"
REVIEW_VERSION = 1
CSV_FIELDS = [
    "rank",
    "ticker",
    "company_name",
    "effective_date",
    "weeks_affected",
    "current_evidence",
    "import_status",
    "proposed_action",
    "upgrade_scope",
    "membership_source_url",
    "source_as_of_date",
    "source_trust_level",
]
SOURCE_TEMPLATE_FIELDS = [
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


def _current_source_map(path):
    rows = {}
    for row in _read_csv(path):
        ticker = normalize_ticker(row.get("ticker"))
        if ticker:
            rows[ticker] = row
    return rows


def _source_status(row):
    if not row:
        return "missing_current_source", "add_current_membership_source", "missing"
    evidence = str(row.get("membership_evidence", "")).strip().lower()
    source_url = str(row.get("membership_source_url", "")).strip()
    explicit_trust_level = str(row.get("source_trust_level", "")).strip().lower()
    policy = classify_membership_source(source_url, evidence_kind="current_constituents")
    trust_level = explicit_trust_level or policy["trust_level"]
    if evidence != "verified" or not policy["can_upgrade_membership"] or trust_level != "verified":
        return "invalid_current_source", "fix_current_membership_source", trust_level
    return "ready_current_source", "prepare_current_membership_import", trust_level


def _plan_item(gap, current_source):
    ticker = normalize_ticker(gap.get("ticker"))
    source_row = current_source.get(ticker, {})
    import_status, proposed_action, source_trust_level = _source_status(source_row)
    return {
        "rank": int(gap.get("rank") or 0),
        "ticker": ticker,
        "company_name": gap.get("company_name", ""),
        "effective_date": gap.get("effective_date", ""),
        "weeks_affected": int(gap.get("weeks_affected") or 0),
        "current_evidence": gap.get("current_evidence", ""),
        "import_status": import_status,
        "proposed_action": proposed_action,
        "upgrade_scope": "current_membership_only",
        "membership_source_url": source_row.get("membership_source_url", ""),
        "source_as_of_date": source_row.get("source_as_of_date", ""),
        "source_trust_level": source_trust_level,
        "notes": source_row.get("notes", ""),
    }


def _item_sort_key(item):
    status_order = {
        "ready_current_source": 0,
        "missing_current_source": 1,
        "invalid_current_source": 2,
    }
    return (
        status_order.get(item.get("import_status"), 9),
        -int(item.get("weeks_affected") or 0),
        item.get("ticker", ""),
    )


def build_membership_evidence_import_plan(gaps_path, current_source_pack=None, as_of_date=None):
    gap_report = _read_json(gaps_path)
    current_source = _current_source_map(current_source_pack) if current_source_pack else {}
    gaps = list(gap_report.get("gaps", []) or [])
    items = sorted((_plan_item(gap, current_source) for gap in gaps), key=_item_sort_key)
    ready = sum(1 for item in items if item["import_status"] == "ready_current_source")
    missing = sum(1 for item in items if item["import_status"] == "missing_current_source")
    invalid = sum(1 for item in items if item["import_status"] == "invalid_current_source")
    ready_weeks = sum(item["weeks_affected"] for item in items if item["import_status"] == "ready_current_source")
    missing_weeks = sum(item["weeks_affected"] for item in items if item["import_status"] == "missing_current_source")
    invalid_weeks = sum(item["weeks_affected"] for item in items if item["import_status"] == "invalid_current_source")
    verified_candidates = sum(1 for item in items if item["source_trust_level"] == "verified")
    cross_checks = sum(1 for item in items if item["source_trust_level"] == "cross_check")
    blocked_by_source_policy = sum(
        1
        for item in items
        if item["source_trust_level"] in {"cross_check", "crosscheck_substitute", "secondary"}
        and item["import_status"] != "ready_current_source"
    )
    if ready:
        next_action = "run_membership_evidence_apply_preview"
    elif missing:
        next_action = "provide_current_membership_sources"
    else:
        next_action = "supplement_verified_membership_evidence"
    return {
        "review_schema": REVIEW_SCHEMA,
        "review_version": REVIEW_VERSION,
        "as_of_date": as_of_date or date.today().isoformat(),
        "status": "ready",
        "source_gap_report": str(Path(gaps_path)),
        "current_source_pack": str(Path(current_source_pack)) if current_source_pack else "",
        "gap_count": int(gap_report.get("gap_count") or len(gaps)),
        "queue_count": len(items),
        "ready_to_import_count": ready,
        "missing_source_count": missing,
        "invalid_source_count": invalid,
        "verified_candidate_count": verified_candidates,
        "cross_check_count": cross_checks,
        "blocked_by_source_policy_count": blocked_by_source_policy,
        "ready_to_import_weeks_affected": ready_weeks,
        "missing_source_weeks_affected": missing_weeks,
        "invalid_source_weeks_affected": invalid_weeks,
        "next_action": next_action,
        "formal_backtest_upgrade_allowed": False,
        "items": items,
        "boundary": "只生成成分证据导入计划，不抓取网页，不修改 historical_membership.csv，不把当前成分来源直接升级为完整历史证据。",
    }


def render_markdown(payload):
    lines = [
        "# membership_evidence_import_plan",
        "",
        f"- gap_count: {payload.get('gap_count', 0)}",
        f"- queue_count: {payload.get('queue_count', 0)}",
        f"- ready_to_import_count: {payload.get('ready_to_import_count', 0)}",
        f"- missing_source_count: {payload.get('missing_source_count', 0)}",
        f"- invalid_source_count: {payload.get('invalid_source_count', 0)}",
        f"- verified_candidate_count: {payload.get('verified_candidate_count', 0)}",
        f"- cross_check_count: {payload.get('cross_check_count', 0)}",
        f"- blocked_by_source_policy_count: {payload.get('blocked_by_source_policy_count', 0)}",
        f"- ready_to_import_weeks_affected: {payload.get('ready_to_import_weeks_affected', 0)}",
        f"- missing_source_weeks_affected: {payload.get('missing_source_weeks_affected', 0)}",
        f"- invalid_source_weeks_affected: {payload.get('invalid_source_weeks_affected', 0)}",
        f"- next_action: {payload.get('next_action', '')}",
        f"- formal_backtest_upgrade_allowed: {str(payload.get('formal_backtest_upgrade_allowed')).lower()}",
        "",
        "| rank | ticker | company | status | action | scope |",
        "|---:|---|---|---|---|---|",
    ]
    for item in payload.get("items", []):
        lines.append(
            "| {rank} | {ticker} | {company_name} | {import_status} | {proposed_action} | {upgrade_scope} |".format(
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
        writer.writerows(payload.get("items", []))


def write_source_template(payload, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SOURCE_TEMPLATE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for item in payload.get("items", []):
            if item.get("import_status") == "ready_current_source":
                continue
            writer.writerow(
                {
                    "ticker": item.get("ticker", ""),
                    "membership_evidence": "verified",
                    "membership_source_url": item.get("membership_source_url", ""),
                    "source_as_of_date": item.get("source_as_of_date", ""),
                    "notes": "Fill with official S&P Global current membership source.",
                }
            )


def write_text(text, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8-sig")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build an import plan for S&P 500 membership evidence gaps.")
    parser.add_argument("--gaps", default="outputs/automation/latest_membership_evidence_gaps.json")
    parser.add_argument("--current-source-pack", default="data/config/us_sp500_current_membership_sources.csv")
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--output-json", default="outputs/automation/latest_membership_evidence_import_plan.json")
    parser.add_argument("--output-csv", default="outputs/automation/latest_membership_evidence_import_plan.csv")
    parser.add_argument("--output-md", default="outputs/automation/latest_membership_evidence_import_plan.md")
    parser.add_argument("--source-template", default="outputs/automation/us_sp500_current_membership_sources_template.csv")
    args = parser.parse_args()

    payload = build_membership_evidence_import_plan(args.gaps, args.current_source_pack, args.as_of_date or None)
    report = render_markdown(payload)
    write_json(payload, args.output_json)
    write_csv(payload, args.output_csv)
    write_text(report, args.output_md)
    write_source_template(payload, args.source_template)
    print(report)


if __name__ == "__main__":
    main()
