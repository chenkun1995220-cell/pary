import argparse
import json
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path


REVIEW_SCHEMA = "weekly_delivery_streak_review"
REVIEW_VERSION = 1
ACCEPTANCE_START_DATE = date(2026, 7, 12)
REQUIRED_CONSECUTIVE_SUNDAYS = 3
HK_START_MIN = time(14, 15, 0)
HK_START_MAX = time(14, 30, 0)


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_history(path):
    rows = []
    try:
        for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    except (OSError, json.JSONDecodeError):
        return []
    return rows


def _iso_date(value):
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError:
        return None


def _timestamp(value):
    text = str(value or "").strip()
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            pass
    return None


def _int_value(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def update_history(rows, record):
    by_date = {}
    for row in rows or []:
        if isinstance(row, dict) and _iso_date(row.get("as_of_date")):
            by_date[row["as_of_date"]] = row
    if isinstance(record, dict) and _iso_date(record.get("as_of_date")):
        by_date[record["as_of_date"]] = record
    return [by_date[key] for key in sorted(by_date)]


def _consecutive_success_dates(rows):
    eligible = []
    for row in update_history(rows, None):
        row_date = _iso_date(row.get("as_of_date"))
        if row_date and row_date >= ACCEPTANCE_START_DATE:
            eligible.append((row_date, row))
    if not eligible or not eligible[-1][1].get("sunday_success"):
        return []
    result = [eligible[-1][0]]
    for index in range(len(eligible) - 2, -1, -1):
        row_date, row = eligible[index]
        if not row.get("sunday_success") or result[-1] - row_date != timedelta(days=7):
            break
        result.append(row_date)
    return [value.isoformat() for value in reversed(result)]


def _current_record(consistency, delivery, pre_submit, current_date):
    issues = []
    if consistency.get("status") != "ready" or consistency.get("issues"):
        issues.append("weekly_artifact_consistency_not_ready")
        for issue in consistency.get("issues", []) or []:
            issues.append(f"consistency:{issue}")
    if delivery.get("status") != "ready":
        issues.append("weekly_delivery_check_not_ready")
    if pre_submit.get("status") != "ready":
        issues.append("pre_submit_review_not_ready")
    for label, payload in (
        ("consistency", consistency),
        ("delivery", delivery),
        ("pre_submit", pre_submit),
    ):
        if payload.get("as_of_date") != current_date.isoformat():
            issues.append(f"{label}_as_of_date_mismatch")

    market_dates = sorted(set(consistency.get("market_run_dates", []) or []))
    if market_dates != [current_date.isoformat()]:
        issues.append("market_run_dates_not_current_sunday")
    counts = [
        _int_value(consistency.get("candidate_count_total"), -1),
        _int_value(consistency.get("conclusion_candidate_count_total"), -1),
        _int_value(consistency.get("delivery_candidate_count_total"), -1),
        _int_value(delivery.get("candidate_count_total"), -1),
    ]
    if min(counts) < 0 or len(set(counts)) != 1:
        issues.append("candidate_count_total_mismatch")

    markets = {}
    for row in consistency.get("markets", []) or []:
        if isinstance(row, dict) and row.get("market"):
            markets[row["market"]] = row
    if set(markets) != {"US", "CN", "HK"}:
        issues.append("market_timing_evidence_incomplete")
    for market in ("US", "CN", "HK"):
        row = markets.get(market, {})
        started = _timestamp(row.get("run_started_at"))
        completed = _timestamp(row.get("run_completed_at"))
        if not started or not completed:
            issues.append(f"{market.lower()}_run_timing_missing")
            continue
        if started.date() != current_date or completed.date() != current_date:
            issues.append(f"{market.lower()}_run_timing_date_mismatch")
        if started > completed:
            issues.append(f"{market.lower()}_run_timing_order_invalid")

    hk_started = _timestamp(markets.get("HK", {}).get("run_started_at"))
    hk_window_status = "needs_attention"
    if hk_started and hk_started.date() == current_date:
        if HK_START_MIN <= hk_started.time() <= HK_START_MAX:
            hk_window_status = "ready"
        else:
            issues.append("hk_run_start_outside_1415_window")
    elif "hk_run_timing_missing" not in issues:
        issues.append("hk_run_start_outside_1415_window")

    if consistency.get("formal_model_change_allowed") is not False:
        issues.append("consistency_formal_model_change_unsafe")
    return {
        "as_of_date": current_date.isoformat(),
        "sunday_success": not issues,
        "issues": list(dict.fromkeys(issues)),
        "candidate_count_total": counts[0] if counts[0] >= 0 else 0,
        "market_run_dates": market_dates,
        "market_timings": {
            market: {
                "run_started_at": markets.get(market, {}).get("run_started_at", ""),
                "run_completed_at": markets.get(market, {}).get("run_completed_at", ""),
            }
            for market in ("US", "CN", "HK")
        },
        "consistency_status": consistency.get("status", "missing"),
        "delivery_status": delivery.get("status", "missing"),
        "pre_submit_status": pre_submit.get("status", "missing"),
        "hk_start_window_status": hk_window_status,
        "formal_model_change_allowed": False,
    }


def build_weekly_delivery_streak_review(
    consistency, delivery, pre_submit, history_rows, as_of_date=None
):
    current_date = _iso_date(as_of_date or date.today().isoformat())
    if current_date is None:
        raise ValueError(f"invalid as_of_date: {as_of_date}")
    eligible_sunday = current_date >= ACCEPTANCE_START_DATE and current_date.weekday() == 6
    record = _current_record(consistency, delivery, pre_submit, current_date) if eligible_sunday else None
    logical_rows = update_history(history_rows, record)
    success_dates = _consecutive_success_dates(logical_rows)
    ready_count = len(success_dates)
    if not eligible_sunday:
        status = "not_scheduled_day"
        issues = []
    elif not record.get("sunday_success"):
        status = "needs_attention"
        issues = record.get("issues", [])
    elif ready_count >= REQUIRED_CONSECUTIVE_SUNDAYS:
        status = "ready"
        issues = []
    else:
        status = "accumulating"
        issues = []
    first_hk_status = "ready" if any(
        row.get("sunday_success") and row.get("hk_start_window_status") == "ready"
        for row in logical_rows
        if (_iso_date(row.get("as_of_date")) or date.min) >= ACCEPTANCE_START_DATE
    ) else "pending"
    return {
        "review_schema": REVIEW_SCHEMA,
        "review_version": REVIEW_VERSION,
        "as_of_date": current_date.isoformat(),
        "status": status,
        "acceptance_start_date": ACCEPTANCE_START_DATE.isoformat(),
        "required_consecutive_sundays": REQUIRED_CONSECUTIVE_SUNDAYS,
        "consecutive_sunday_ready_count": ready_count,
        "successful_sunday_dates": success_dates,
        "first_hk_1415_validation_status": first_hk_status,
        "history_record_count": len(logical_rows),
        "latest_record": record,
        "issues": issues,
        "formal_model_change_allowed": False,
        "boundary": "只读取当周交付证据并维护按周日去重的验收台账；不抓取行情、不重新评分、不修改正式模型参数。",
    }, record


def render_markdown(payload):
    latest = payload.get("latest_record") or {}
    lines = [
        "# 三市场连续周日交付验收",
        "",
        f"- 日期：{payload.get('as_of_date', '')}",
        f"- 状态：{payload.get('status', '')}",
        f"- 连续成功：{payload.get('consecutive_sunday_ready_count', 0)}/{payload.get('required_consecutive_sundays', 3)}",
        f"- 成功周日：{', '.join(payload.get('successful_sunday_dates', [])) or '无'}",
        f"- 港股 14:15 首次启动验收：{payload.get('first_hk_1415_validation_status', 'pending')}",
        f"- 当周候选总数：{latest.get('candidate_count_total', 0)}",
        "- 正式模型修改：不允许",
        "",
        "## 当周问题",
        "",
    ]
    issues = latest.get("issues", []) if latest else payload.get("issues", [])
    lines.extend(f"- {item}" for item in issues)
    if not issues:
        lines.append("- 无")
    lines.extend(["", "## 边界", "", f"- {payload.get('boundary', '')}", ""])
    return "\n".join(lines)


def _write_json(path, payload):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8-sig")


def _write_history(path, rows):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    destination.write_text(text, encoding="utf-8-sig")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="维护三市场连续周日交付验收台账。")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--as-of-date", default=date.today().isoformat())
    parser.add_argument("--output", default="outputs/automation/latest_weekly_delivery_streak_review.json")
    parser.add_argument("--report", default="outputs/automation/latest_weekly_delivery_streak_review.md")
    parser.add_argument("--history", default="outputs/automation/weekly_delivery_streak_history.jsonl")
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    automation = root / "outputs" / "automation"
    history_path = root / args.history if not Path(args.history).is_absolute() else Path(args.history)
    history_rows = _read_history(history_path)
    payload, record = build_weekly_delivery_streak_review(
        _read_json(automation / "latest_weekly_artifact_consistency.json"),
        _read_json(automation / "latest_weekly_delivery_check.json"),
        _read_json(automation / "latest_pre_submit_review.json"),
        history_rows,
        as_of_date=args.as_of_date,
    )
    if record is not None:
        _write_history(history_path, update_history(history_rows, record))
    output = Path(args.output) if Path(args.output).is_absolute() else root / args.output
    report = Path(args.report) if Path(args.report).is_absolute() else root / args.report
    _write_json(output, payload)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_markdown(payload), encoding="utf-8-sig")
    print(render_markdown(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
