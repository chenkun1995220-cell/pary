import argparse
import csv
import json
from pathlib import Path


APPLY_SCHEMA = "sp500_current_membership_source_review_decision_apply"
APPLY_VERSION = 1
DEFAULT_QUEUE = "outputs/automation/sp500_current_membership_source_review_queue.csv"
DEFAULT_DECISIONS = "outputs/automation/sp500_current_membership_source_review_decisions.csv"
DEFAULT_SUMMARY_JSON = (
    "outputs/automation/latest_sp500_current_membership_source_review_decision_apply.json"
)
DEFAULT_SUMMARY_MD = (
    "outputs/automation/latest_sp500_current_membership_source_review_decision_apply.md"
)
READY_DECISIONS = {"official_absent", "not_applicable", "ignored", "accepted"}
PENDING_DECISIONS = {"", "pending", "needs_more_data", "source_refresh_required", "keep_open"}
TRUE_VALUES = {"1", "true", "yes", "y", "checked"}


def read_csv(path):
    path = Path(path)
    if not path.exists():
        return None, []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def write_csv(path, fieldnames, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_ticker(value):
    return str(value or "").strip().upper()


def normalize_decision(row):
    return {
        "ticker": normalize_ticker(row.get("ticker")),
        "review_decision": str(row.get("review_decision", "") or "").strip().lower(),
        "official_source_checked": str(row.get("official_source_checked", "") or "").strip().lower(),
        "decision_notes": str(row.get("decision_notes", "") or "").strip(),
    }


def decision_is_ready(decision):
    return (
        decision["review_decision"] in READY_DECISIONS
        and decision["official_source_checked"] in TRUE_VALUES
    )


def apply_review_decisions(queue_path, decisions_path, dry_run=False):
    queue_fields, queue_rows = read_csv(queue_path)
    decision_fields, decision_rows = read_csv(decisions_path)
    if not queue_fields:
        return {
            "status": "missing_queue",
            "queue": str(queue_path),
            "decisions": str(decisions_path),
            "queue_exists": False,
            "decision_file_exists": bool(decision_fields),
            "queue_total_count": 0,
            "decision_total_count": len(decision_rows),
            "applied_count": 0,
            "skipped_pending_count": 0,
            "skipped_invalid_count": 0,
            "applied_items": [],
            "formal_backtest_upgrade_allowed": False,
        }
    if not decision_fields:
        return {
            "status": "missing_decisions",
            "queue": str(queue_path),
            "decisions": str(decisions_path),
            "queue_exists": True,
            "decision_file_exists": False,
            "queue_total_count": len(queue_rows),
            "decision_total_count": 0,
            "applied_count": 0,
            "skipped_pending_count": 0,
            "skipped_invalid_count": 0,
            "applied_items": [],
            "formal_backtest_upgrade_allowed": False,
        }

    decisions_by_ticker = {}
    skipped_invalid = 0
    for raw in decision_rows:
        decision = normalize_decision(raw)
        if not decision["ticker"]:
            skipped_invalid += 1
            continue
        decisions_by_ticker[decision["ticker"]] = decision

    applied_items = []
    skipped_pending = 0
    for row in queue_rows:
        ticker = normalize_ticker(row.get("ticker"))
        current_status = str(row.get("review_status", "") or "").strip().lower()
        if current_status in {"resolved", "closed", "done", "accepted", "ignored"}:
            continue
        decision = decisions_by_ticker.get(ticker)
        if not decision:
            skipped_pending += 1
            continue
        if decision_is_ready(decision):
            applied_items.append(
                {
                    "ticker": ticker,
                    "review_decision": decision["review_decision"],
                    "decision_notes": decision["decision_notes"],
                }
            )
            if not dry_run:
                row["review_status"] = "resolved"
        elif decision["review_decision"] in PENDING_DECISIONS:
            skipped_pending += 1
        else:
            skipped_invalid += 1

    if applied_items:
        status = "dry_run" if dry_run else "applied"
    elif skipped_invalid:
        status = "invalid_decisions"
    else:
        status = "no_changes"

    if applied_items and not dry_run:
        write_csv(queue_path, queue_fields, queue_rows)

    return {
        "apply_schema": APPLY_SCHEMA,
        "apply_version": APPLY_VERSION,
        "status": status,
        "queue": str(queue_path),
        "decisions": str(decisions_path),
        "queue_exists": True,
        "decision_file_exists": True,
        "queue_total_count": len(queue_rows),
        "decision_total_count": len(decision_rows),
        "applied_count": len(applied_items),
        "skipped_pending_count": skipped_pending,
        "skipped_invalid_count": skipped_invalid,
        "applied_items": applied_items,
        "dry_run": dry_run,
        "formal_backtest_upgrade_allowed": False,
        "boundary": "只根据人工决策文件更新 S&P 500 当前来源复核队列，不修改 historical_membership.csv 或正式模型参数。",
    }


def render_summary(summary):
    lines = [
        "# S&P 500 当前成分来源复核决策应用摘要",
        "",
        f"- 状态：{summary.get('status', 'unknown')}",
        f"- 队列文件：{summary.get('queue', '')}",
        f"- 决策文件：{summary.get('decisions', '')}",
        f"- applied_count={summary.get('applied_count', 0)}",
        f"- skipped_pending_count={summary.get('skipped_pending_count', 0)}",
        f"- skipped_invalid_count={summary.get('skipped_invalid_count', 0)}",
        "",
        "## 已应用条目",
        "",
    ]
    items = summary.get("applied_items", []) or []
    if not items:
        lines.append("- 无")
    else:
        for item in items:
            lines.append(
                "- {ticker}: {review_decision}; {decision_notes}".format(
                    ticker=item.get("ticker", ""),
                    review_decision=item.get("review_decision", ""),
                    decision_notes=item.get("decision_notes", ""),
                )
            )
    lines.extend(["", "## 边界", "", f"- {summary.get('boundary', '')}", ""])
    return "\n".join(lines)


def write_outputs(summary, summary_json=None, summary_md=None):
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
        description="Apply S&P 500 current membership source review decisions to the review queue."
    )
    parser.add_argument("--queue", default=DEFAULT_QUEUE)
    parser.add_argument("--decisions", default=DEFAULT_DECISIONS)
    parser.add_argument("--summary-json", default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--summary-md", default=DEFAULT_SUMMARY_MD)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    summary = apply_review_decisions(
        args.queue,
        args.decisions,
        dry_run=args.dry_run,
    )
    write_outputs(summary, summary_json=args.summary_json, summary_md=args.summary_md)
    print(
        "status={status} applied={applied} skipped_pending={pending} skipped_invalid={invalid}".format(
            status=summary["status"],
            applied=summary["applied_count"],
            pending=summary["skipped_pending_count"],
            invalid=summary["skipped_invalid_count"],
        )
    )
    return 1 if summary["status"] == "missing_queue" else 0


if __name__ == "__main__":
    raise SystemExit(main())
