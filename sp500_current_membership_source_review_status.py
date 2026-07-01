import argparse
import csv
import json
from datetime import date
from pathlib import Path


REVIEW_STATUS_SCHEMA = "sp500_current_membership_source_review_status"
REVIEW_STATUS_VERSION = 1
DEFAULT_QUEUE = "outputs/automation/sp500_current_membership_source_review_queue.csv"
DEFAULT_OUTPUT = "outputs/automation/latest_sp500_current_membership_source_review_status.json"
DEFAULT_REPORT = "outputs/automation/latest_sp500_current_membership_source_review_status.md"
DEFAULT_DECISIONS_TEMPLATE = (
    "outputs/automation/sp500_current_membership_source_review_decisions_template.csv"
)
DEFAULT_DECISIONS = "outputs/automation/sp500_current_membership_source_review_decisions.csv"
RESOLVED_STATUSES = {"resolved", "closed", "done", "accepted", "ignored"}
CLOSE_READY_DECISIONS = {"official_absent", "not_applicable", "ignored", "accepted"}
PENDING_DECISIONS = {"", "pending", "needs_more_data", "source_refresh_required", "keep_open"}
TRUE_VALUES = {"1", "true", "yes", "y", "checked"}
DECISION_TEMPLATE_FIELDS = [
    "ticker",
    "review_decision",
    "official_source_checked",
    "required_source_url",
    "issue_type",
    "recommended_check",
    "decision_notes",
]
DECISION_OPTIONS = [
    {
        "review_decision": "official_absent",
        "when_to_use": "Official current S&P source was checked and the ticker is absent.",
        "effect": "Ready to close the open queue item when official_source_checked=yes.",
    },
    {
        "review_decision": "source_refresh_required",
        "when_to_use": "The current official export appears stale or incomplete.",
        "effect": "Keeps the queue item open and asks for a fresher official source.",
    },
    {
        "review_decision": "keep_open",
        "when_to_use": "The item still needs more manual evidence before a decision.",
        "effect": "Keeps the queue item open.",
    },
    {
        "review_decision": "not_applicable",
        "when_to_use": "The ticker is not applicable to the current S&P 500 source review.",
        "effect": "Ready to close the open queue item when official_source_checked=yes.",
    },
]


def _decision_guidance():
    return {
        "decision_options": DECISION_OPTIONS,
        "decision_required_fields": DECISION_TEMPLATE_FIELDS,
        "manual_decision_instructions": (
            "Fill one row per open ticker in the decisions template. Set "
            "official_source_checked=yes when the official S&P source has been checked. "
            "Use official_absent or not_applicable only when the item is ready to close."
        ),
    }


def _read_csv(path):
    csv_path = Path(path)
    if not csv_path.exists():
        return None
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _normalized_row(row):
    return {
        "ticker": str(row.get("ticker", "")).strip().upper(),
        "review_status": str(row.get("review_status", "")).strip().lower() or "open",
        "issue_type": str(row.get("issue_type", "")).strip(),
        "recommended_check": str(row.get("recommended_check", "")).strip(),
        "required_source_url": str(row.get("required_source_url", "")).strip(),
        "source_status": str(row.get("source_status", "")).strip(),
    }


def _normalized_decision_row(row):
    return {
        "ticker": str(row.get("ticker", "")).strip().upper(),
        "review_decision": str(row.get("review_decision", "")).strip().lower(),
        "official_source_checked": str(row.get("official_source_checked", "")).strip().lower(),
        "required_source_url": str(row.get("required_source_url", "")).strip(),
        "issue_type": str(row.get("issue_type", "")).strip(),
        "recommended_check": str(row.get("recommended_check", "")).strip(),
        "decision_notes": str(row.get("decision_notes", "")).strip(),
    }


def _manual_decision_next_step(review_decision_status):
    if review_decision_status == "ready_to_apply":
        return "apply_review_decisions_to_queue"
    if review_decision_status == "invalid":
        return "fix_review_decisions"
    if review_decision_status in {"missing", "partial"}:
        return "fill_decisions_template"
    return "not_required"


def _decision_summary(decisions_path, open_items):
    decision_file = str(Path(decisions_path)) if decisions_path else ""
    rows = _read_csv(decisions_path) if decisions_path else None
    open_tickers = {item.get("ticker", "") for item in open_items if item.get("ticker")}
    initial_status = "not_required" if not open_tickers else "missing"
    summary = {
        "decision_file": decision_file,
        "decision_file_exists": rows is not None,
        "decision_total_count": 0,
        "decision_matched_open_count": 0,
        "decision_ready_to_apply_count": 0,
        "decision_pending_count": len(open_tickers),
        "decision_pending_tickers": sorted(open_tickers),
        "decision_ready_to_apply_tickers": [],
        "decision_invalid_count": 0,
        "decision_items": [],
        "review_decision_status": initial_status,
        "manual_decision_next_step": _manual_decision_next_step(initial_status),
    }
    if rows is None:
        return summary

    normalized = [_normalized_decision_row(row) for row in rows]
    decisions_by_ticker = {}
    invalid_count = 0
    for row in normalized:
        ticker = row["ticker"]
        if not ticker:
            invalid_count += 1
            continue
        decisions_by_ticker[ticker] = row

    matched = []
    ready_to_apply = []
    ready_to_apply_tickers = []
    pending_tickers = []
    pending_count = 0
    for ticker in sorted(open_tickers):
        decision = decisions_by_ticker.get(ticker)
        if not decision:
            pending_count += 1
            pending_tickers.append(ticker)
            continue
        matched.append(decision)
        review_decision = decision["review_decision"]
        checked = decision["official_source_checked"] in TRUE_VALUES
        if review_decision in CLOSE_READY_DECISIONS and checked:
            ready_to_apply.append(decision)
            ready_to_apply_tickers.append(ticker)
        elif review_decision in PENDING_DECISIONS:
            pending_count += 1
            pending_tickers.append(ticker)
        else:
            invalid_count += 1
            pending_tickers.append(ticker)

    if open_tickers and len(ready_to_apply) == len(open_tickers):
        status = "ready_to_apply"
    elif invalid_count:
        status = "invalid"
    elif matched:
        status = "partial"
    elif open_tickers:
        status = "missing"
    else:
        status = "not_required"

    summary.update(
        {
            "decision_total_count": len(normalized),
            "decision_matched_open_count": len(matched),
            "decision_ready_to_apply_count": len(ready_to_apply),
            "decision_pending_count": pending_count,
            "decision_pending_tickers": pending_tickers,
            "decision_ready_to_apply_tickers": ready_to_apply_tickers,
            "decision_invalid_count": invalid_count,
            "decision_items": matched,
            "review_decision_status": status,
            "manual_decision_next_step": _manual_decision_next_step(status),
        }
    )
    return summary


def _decision_template_summary(template_path, open_items):
    template_file = str(Path(template_path)) if template_path else ""
    open_tickers = {item.get("ticker", "") for item in open_items if item.get("ticker")}
    summary = {
        "decisions_template_file": template_file,
        "decisions_template_exists": False,
        "decisions_template_status": "not_required" if not open_tickers else "missing",
        "decisions_template_total_count": 0,
        "decisions_template_matched_open_count": 0,
        "decisions_template_missing_open_tickers": sorted(open_tickers),
        "decisions_template_extra_tickers": [],
        "decisions_template_missing_fields": [],
    }
    if not template_path:
        return summary

    csv_path = Path(template_path)
    if not csv_path.exists():
        return summary

    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        rows = list(reader)

    missing_fields = sorted(set(DECISION_TEMPLATE_FIELDS) - fields)
    template_tickers = {
        str(row.get("ticker", "")).strip().upper()
        for row in rows
        if str(row.get("ticker", "")).strip()
    }
    matched = sorted(open_tickers & template_tickers)
    missing_open = sorted(open_tickers - template_tickers)
    extra_tickers = sorted(template_tickers - open_tickers)
    if missing_fields:
        status = "invalid"
    elif not open_tickers:
        status = "not_required" if not extra_tickers else "mismatch"
    elif missing_open or extra_tickers:
        status = "mismatch"
    else:
        status = "ready"

    summary.update(
        {
            "decisions_template_exists": True,
            "decisions_template_status": status,
            "decisions_template_total_count": len(rows),
            "decisions_template_matched_open_count": len(matched),
            "decisions_template_missing_open_tickers": missing_open,
            "decisions_template_extra_tickers": extra_tickers,
            "decisions_template_missing_fields": missing_fields,
        }
    )
    return summary


def build_review_status(queue_path=DEFAULT_QUEUE, as_of_date=None, decisions_path=None):
    queue_path = Path(queue_path)
    rows = _read_csv(queue_path)
    current_date = as_of_date or date.today().isoformat()
    if rows is None:
        return {
            "review_status_schema": REVIEW_STATUS_SCHEMA,
            "review_status_version": REVIEW_STATUS_VERSION,
            "as_of_date": current_date,
            "status": "missing",
            "queue_file": str(queue_path),
            "queue_exists": False,
            "queue_total_count": 0,
            "open_count": 0,
            "resolved_count": 0,
            "open_items": [],
            "resolved_items": [],
            "next_action": "regenerate_sp500_current_membership_source_queue",
            "formal_backtest_upgrade_allowed": False,
            "boundary": "只读取 S&P 500 当前来源复核队列，不修改 historical_membership.csv 或正式模型参数。",
            **_decision_guidance(),
            **_decision_summary(decisions_path, []),
        }

    normalized = [_normalized_row(row) for row in rows]
    resolved_items = [
        row for row in normalized if row["review_status"] in RESOLVED_STATUSES
    ]
    open_items = [
        row for row in normalized if row["review_status"] not in RESOLVED_STATUSES
    ]
    status = "clear" if not open_items else "review_needed"
    decision_payload = _decision_summary(decisions_path, open_items)
    next_action = (
        "continue_membership_evidence_import_plan"
        if status == "clear"
        else "review_open_queue_items"
    )
    if status == "review_needed" and decision_payload["review_decision_status"] == "ready_to_apply":
        next_action = "apply_review_decisions_to_queue"

    return {
        "review_status_schema": REVIEW_STATUS_SCHEMA,
        "review_status_version": REVIEW_STATUS_VERSION,
        "as_of_date": current_date,
        "status": status,
        "queue_file": str(queue_path),
        "queue_exists": True,
        "queue_total_count": len(normalized),
        "open_count": len(open_items),
        "resolved_count": len(resolved_items),
        "open_items": open_items,
        "resolved_items": resolved_items,
        "next_action": next_action,
        "formal_backtest_upgrade_allowed": False,
        "boundary": "只读取 S&P 500 当前来源复核队列，不修改 historical_membership.csv 或正式模型参数。",
        **_decision_guidance(),
        **decision_payload,
    }


def render_review_status(payload):
    lines = [
        "# S&P 500 当前成分来源复核队列状态",
        "",
        f"- 状态：{payload.get('status', 'unknown')}",
        f"- 队列文件：{payload.get('queue_file', '')}",
        f"- queue_total_count={payload.get('queue_total_count', 0)}",
        f"- open_count={payload.get('open_count', 0)}",
        f"- resolved_count={payload.get('resolved_count', 0)}",
        f"- review_decision_status={payload.get('review_decision_status', 'unknown')}",
        f"- manual_decision_next_step={payload.get('manual_decision_next_step', 'unknown')}",
        f"- decision_ready_to_apply_count={payload.get('decision_ready_to_apply_count', 0)}",
        "- decision_ready_to_apply_tickers="
        + ", ".join(payload.get("decision_ready_to_apply_tickers", []) or []),
        "- decision_pending_tickers="
        + ", ".join(payload.get("decision_pending_tickers", []) or []),
        f"- 下一步：{payload.get('next_action', 'unknown')}",
        "",
        "## 未处理条目",
        "",
    ]
    open_items = payload.get("open_items", []) or []
    if not open_items:
        lines.append("- 无")
    else:
        for item in open_items:
            lines.append(
                "- {ticker}: {issue_type}; {recommended_check}".format(
                    ticker=item.get("ticker", ""),
                    issue_type=item.get("issue_type", ""),
                    recommended_check=item.get("recommended_check", ""),
                )
            )
    lines.extend(["", "## 边界", "", f"- {payload.get('boundary', '')}", ""])
    lines.extend(["## 人工决策指引", ""])
    lines.append(f"- 决策文件：{payload.get('decision_file', '')}")
    if payload.get("decisions_template_file"):
        lines.append(f"- 决策模板：{payload.get('decisions_template_file', '')}")
    if "decisions_template_status" in payload:
        lines.append(
            f"- decisions_template_status={payload.get('decisions_template_status', 'unknown')}"
        )
        lines.append(
            "- decisions_template_missing_open_tickers="
            + ", ".join(payload.get("decisions_template_missing_open_tickers", []) or [])
        )
    lines.append(f"- 填写说明：{payload.get('manual_decision_instructions', '')}")
    lines.append("- 必填字段：" + ", ".join(payload.get("decision_required_fields", []) or []))
    lines.append("")
    for option in payload.get("decision_options", []) or []:
        lines.append(
            "- {decision}: {when_to_use} Effect: {effect}".format(
                decision=option.get("review_decision", ""),
                when_to_use=option.get("when_to_use", ""),
                effect=option.get("effect", ""),
            )
        )
    lines.append("")
    return "\n".join(lines)


def write_json(payload, output):
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8-sig",
    )
    return output_path


def write_report(payload, report):
    report_path = Path(report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_review_status(payload), encoding="utf-8-sig")
    return report_path


def write_decisions_template(payload, output):
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DECISION_TEMPLATE_FIELDS)
        writer.writeheader()
        for item in payload.get("open_items", []) or []:
            writer.writerow(
                {
                    "ticker": item.get("ticker", ""),
                    "review_decision": "",
                    "official_source_checked": "",
                    "required_source_url": item.get("required_source_url", ""),
                    "issue_type": item.get("issue_type", ""),
                    "recommended_check": item.get("recommended_check", ""),
                    "decision_notes": "",
                }
            )
    return output_path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build S&P 500 current membership source review queue status."
    )
    parser.add_argument("--queue", default=DEFAULT_QUEUE)
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--decisions-template", default=DEFAULT_DECISIONS_TEMPLATE)
    parser.add_argument("--decisions", default=DEFAULT_DECISIONS)
    args = parser.parse_args(argv)

    payload = build_review_status(
        args.queue,
        as_of_date=args.as_of_date,
        decisions_path=args.decisions,
    )
    payload["decisions_template_file"] = str(Path(args.decisions_template))
    write_decisions_template(payload, args.decisions_template)
    payload.update(_decision_template_summary(args.decisions_template, payload.get("open_items", [])))
    write_json(payload, args.output)
    write_report(payload, args.report)
    print(f"S&P 500 current membership source review status: {payload['status']}")
    print(f"Writes: {args.output}, {args.report}, {args.decisions_template}")
    return 0 if payload["status"] != "missing" else 1


if __name__ == "__main__":
    raise SystemExit(main())
