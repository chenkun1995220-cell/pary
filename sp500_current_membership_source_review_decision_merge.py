import argparse
import csv
import json
from pathlib import Path


MERGE_SCHEMA = "sp500_current_membership_source_review_decision_merge"
MERGE_VERSION = 1
DEFAULT_TEMPLATE = (
    "outputs/automation/sp500_current_membership_source_review_decisions_template.csv"
)
DEFAULT_DECISIONS = "outputs/automation/sp500_current_membership_source_review_decisions.csv"
DEFAULT_SUMMARY_JSON = (
    "outputs/automation/latest_sp500_current_membership_source_review_decision_merge.json"
)
DEFAULT_SUMMARY_MD = (
    "outputs/automation/latest_sp500_current_membership_source_review_decision_merge.md"
)
FIELDNAMES = [
    "ticker",
    "review_decision",
    "official_source_checked",
    "required_source_url",
    "issue_type",
    "recommended_check",
    "decision_notes",
]
FINAL_DECISIONS = {"official_absent", "not_applicable", "ignored", "accepted"}
PENDING_DECISIONS = {"", "pending", "needs_more_data", "source_refresh_required", "keep_open"}


def read_rows(path):
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except FileNotFoundError:
        return []


def write_rows(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def normalize_row(row):
    return {
        "ticker": str(row.get("ticker", "") or "").strip().upper(),
        "review_decision": str(row.get("review_decision", "") or "").strip().lower(),
        "official_source_checked": str(row.get("official_source_checked", "") or "").strip().lower(),
        "required_source_url": str(row.get("required_source_url", "") or "").strip(),
        "issue_type": str(row.get("issue_type", "") or "").strip(),
        "recommended_check": str(row.get("recommended_check", "") or "").strip(),
        "decision_notes": str(row.get("decision_notes", "") or "").strip(),
    }


def merge_decisions(template_rows, existing_rows):
    merged = {}
    order = []
    for row in existing_rows:
        normalized = normalize_row(row)
        ticker = normalized["ticker"]
        if not ticker:
            continue
        if ticker not in merged:
            order.append(ticker)
        merged[ticker] = normalized

    merged_count = 0
    skipped_pending = 0
    skipped_invalid = 0
    merged_tickers = []
    for row in template_rows:
        normalized = normalize_row(row)
        ticker = normalized["ticker"]
        decision = normalized["review_decision"]
        if not ticker:
            skipped_invalid += 1
            continue
        if decision in PENDING_DECISIONS:
            skipped_pending += 1
            continue
        if decision not in FINAL_DECISIONS:
            skipped_invalid += 1
            continue
        if ticker not in merged:
            order.append(ticker)
        merged[ticker] = normalized
        merged_count += 1
        merged_tickers.append(ticker)

    rows = [merged[ticker] for ticker in order]
    return {
        "rows": rows,
        "merged": merged_count,
        "skipped_pending": skipped_pending,
        "skipped_invalid": skipped_invalid,
        "merged_tickers": merged_tickers,
        "by_decision": count_by_decision(rows),
    }


def count_by_decision(rows):
    counts = {}
    for row in rows:
        decision = row.get("review_decision") or ""
        if decision:
            counts[decision] = counts.get(decision, 0) + 1
    return [
        {"review_decision": decision, "count": count}
        for decision, count in counts.items()
    ]


def build_summary(result, template_path, decisions_path):
    return {
        "merge_schema": MERGE_SCHEMA,
        "merge_version": MERGE_VERSION,
        "template": str(template_path),
        "decisions": str(decisions_path),
        "merged": result["merged"],
        "merged_tickers": result["merged_tickers"],
        "skipped_pending": result["skipped_pending"],
        "skipped_invalid": result["skipped_invalid"],
        "row_count": len(result["rows"]),
        "by_decision": result["by_decision"],
        "formal_backtest_upgrade_allowed": False,
    }


def render_summary(summary):
    lines = [
        "# S&P 500 当前成分来源复核决策合并摘要",
        "",
        f"- 模板文件：{summary['template']}",
        f"- 正式决策文件：{summary['decisions']}",
        f"- 合并/更新：{summary['merged']}",
        f"- 本次合并 ticker：{', '.join(summary['merged_tickers']) if summary['merged_tickers'] else '无'}",
        f"- 跳过 pending：{summary['skipped_pending']}",
        f"- 跳过无效：{summary['skipped_invalid']}",
        f"- 当前正式决策行数：{summary['row_count']}",
        "",
        "| 决策 | 数量 |",
        "|---|---:|",
    ]
    for item in summary["by_decision"]:
        lines.append(f"| {item['review_decision']} | {item['count']} |")
    return "\n".join(lines).rstrip() + "\n"


def write_summary(summary, summary_json=None, summary_md=None):
    if summary_json:
        path = Path(summary_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8-sig",
        )
    if summary_md:
        path = Path(summary_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_summary(summary), encoding="utf-8-sig")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Merge filled S&P 500 current membership source review decision template rows."
    )
    parser.add_argument("--template", default=DEFAULT_TEMPLATE)
    parser.add_argument("--decisions", default=DEFAULT_DECISIONS)
    parser.add_argument("--summary-json", default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--summary-md", default=DEFAULT_SUMMARY_MD)
    args = parser.parse_args(argv)

    template_rows = read_rows(args.template)
    existing_rows = read_rows(args.decisions)
    result = merge_decisions(template_rows, existing_rows)
    write_rows(args.decisions, result["rows"])
    summary = build_summary(result, args.template, args.decisions)
    write_summary(summary, summary_json=args.summary_json, summary_md=args.summary_md)
    print(
        "merged={merged} skipped_pending={pending} skipped_invalid={invalid} output={output}".format(
            merged=result["merged"],
            pending=result["skipped_pending"],
            invalid=result["skipped_invalid"],
            output=args.decisions,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
