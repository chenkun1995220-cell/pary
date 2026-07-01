import argparse
import csv
import json
from pathlib import Path


FIELDNAMES = [
    "as_of_date",
    "market",
    "review_type",
    "ticker",
    "company",
    "decision_status",
    "decision_note",
    "reviewer",
    "decided_at",
]

FINAL_STATUSES = {"accepted", "rejected", "needs_more_data"}


def read_rows(path):
    try:
        with Path(path).open("r", newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    except FileNotFoundError:
        return []


def write_rows(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def decision_key(row):
    market = (row.get("market") or "").strip()
    review_type = (row.get("review_type") or "").strip()
    ticker = (row.get("ticker") or "").strip()
    if not (market and review_type and ticker):
        return None
    return (market, review_type, ticker)


def normalize_decision_row(row):
    return {field: (row.get(field) or "").strip() for field in FIELDNAMES}


def merge_decisions(template_rows, existing_rows):
    merged = {}
    order = []
    for row in existing_rows:
        key = decision_key(row)
        if not key:
            continue
        if key not in merged:
            order.append(key)
        merged[key] = normalize_decision_row(row)

    skipped_pending = 0
    skipped_invalid = 0
    merged_count = 0
    for row in template_rows:
        status = (row.get("decision_status") or "").strip()
        if status in {"", "pending"}:
            skipped_pending += 1
            continue
        if status not in FINAL_STATUSES:
            skipped_invalid += 1
            continue
        key = decision_key(row)
        if not key:
            skipped_invalid += 1
            continue
        if key not in merged:
            order.append(key)
        merged[key] = normalize_decision_row(row)
        merged_count += 1

    return {
        "rows": [merged[key] for key in order],
        "merged": merged_count,
        "skipped_pending": skipped_pending,
        "skipped_invalid": skipped_invalid,
        "by_status": count_by_status([merged[key] for key in order]),
    }


def count_by_status(rows):
    counts = {}
    for row in rows:
        status = row.get("decision_status") or ""
        if not status:
            continue
        counts[status] = counts.get(status, 0) + 1
    return [{"decision_status": status, "count": count} for status, count in counts.items()]


def build_summary(result, template_path, decisions_path):
    return {
        "merge_schema": "manual_review_decision_merge",
        "merge_version": 1,
        "template": str(template_path),
        "decisions": str(decisions_path),
        "merged": result["merged"],
        "skipped_pending": result["skipped_pending"],
        "skipped_invalid": result["skipped_invalid"],
        "row_count": len(result["rows"]),
        "by_status": result["by_status"],
    }


def render_summary_markdown(summary):
    lines = [
        "# 人工复核结果合并摘要",
        "",
        f"- 模板文件：{summary['template']}",
        f"- 结果文件：{summary['decisions']}",
        f"- 合并/更新：{summary['merged']}",
        f"- 跳过 pending：{summary['skipped_pending']}",
        f"- 跳过无效：{summary['skipped_invalid']}",
        f"- 当前正式结果行数：{summary['row_count']}",
        "",
        "| 状态 | 数量 |",
        "|---|---:|",
    ]
    for item in summary["by_status"]:
        lines.append(f"| {item['decision_status']} | {item['count']} |")
    return "\n".join(lines).rstrip() + "\n"


def write_summary_outputs(summary, json_path=None, markdown_path=None):
    if json_path:
        path = Path(json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    if markdown_path:
        path = Path(markdown_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_summary_markdown(summary), encoding="utf-8-sig")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", required=True)
    parser.add_argument("--decisions", required=True)
    parser.add_argument("--summary-json", default=None)
    parser.add_argument("--summary-md", default=None)
    args = parser.parse_args(argv)

    template_rows = read_rows(args.template)
    existing_rows = read_rows(args.decisions)
    result = merge_decisions(template_rows, existing_rows)
    write_rows(args.decisions, result["rows"])
    summary = build_summary(result, args.template, args.decisions)
    write_summary_outputs(summary, json_path=args.summary_json, markdown_path=args.summary_md)
    print(
        "merged={merged} skipped_pending={skipped_pending} skipped_invalid={skipped_invalid} output={output}".format(
            merged=result["merged"],
            skipped_pending=result["skipped_pending"],
            skipped_invalid=result["skipped_invalid"],
            output=args.decisions,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
