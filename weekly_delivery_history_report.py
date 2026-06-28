import argparse
import json
import sys
from collections import Counter
from pathlib import Path


SUMMARY_SCHEMA = "weekly_delivery_history_summary"
SUMMARY_VERSION = 1
EXPECTED_HISTORY_SCHEMA = "weekly_delivery_check_history"
EXPECTED_DELIVERY_SCHEMA = "weekly_delivery_check"


def load_weekly_delivery_history(history):
    history_path = Path(history)
    if not history_path.exists():
        return []
    rows = []
    for line_number, line in enumerate(history_path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("history_schema") != EXPECTED_HISTORY_SCHEMA:
            raise ValueError(f"unexpected history_schema at line {line_number}: {row.get('history_schema', '')}")
        if row.get("delivery_check_schema") != EXPECTED_DELIVERY_SCHEMA:
            raise ValueError(
                f"unexpected delivery_check_schema at line {line_number}: {row.get('delivery_check_schema', '')}"
            )
        rows.append(row)
    return rows


def _latest_record_per_as_of_date(rows):
    latest_by_date = {}
    undated_rows = []
    for row in rows:
        as_of_date = row.get("as_of_date", "")
        if as_of_date:
            latest_by_date[as_of_date] = row
        else:
            undated_rows.append(row)
    deduped = sorted(latest_by_date.values(), key=lambda row: row.get("as_of_date", ""))
    deduped.extend(undated_rows)
    return deduped


def summarize_weekly_delivery_history(history, window=8):
    rows = load_weekly_delivery_history(history)
    trend_rows = _latest_record_per_as_of_date(rows)
    recent = trend_rows[-window:] if window > 0 else trend_rows
    reason_counts = Counter(
        reason
        for row in recent
        for reason in row.get("attention_reasons", [])
    )
    health_reason_counts = Counter(
        reason
        for row in recent
        for reason in row.get("conclusion_health_reasons", [])
    )
    recurring = [
        {"reason": reason, "count": count}
        for reason, count in sorted(reason_counts.items())
        if count >= 2
    ]
    recurring_health = [
        {"reason": reason, "count": count}
        for reason, count in sorted(health_reason_counts.items())
        if count >= 2
    ]
    latest = recent[-1] if recent else {}
    needs_attention_count = sum(1 for row in recent if row.get("status") == "needs_attention")
    ready_count = sum(1 for row in recent if row.get("status") == "ready")
    stale_count = sum(1 for row in recent if row.get("freshness_status") == "stale")
    if recurring:
        recommended_action = "review_recurring_delivery_issues"
    elif latest.get("status") == "needs_attention":
        recommended_action = "review_latest_delivery_check"
    else:
        recommended_action = "continue_monitoring"
    return {
        "history_summary_schema": SUMMARY_SCHEMA,
        "history_summary_version": SUMMARY_VERSION,
        "raw_history_count": len(rows),
        "history_count": len(trend_rows),
        "window_size": len(recent),
        "configured_window": window,
        "latest_as_of_date": latest.get("as_of_date", "unknown"),
        "latest_status": latest.get("status", "unknown"),
        "latest_freshness_status": latest.get("freshness_status", "unknown"),
        "latest_conclusion_health_status": latest.get("conclusion_health_status", "unknown"),
        "latest_conclusion_health_score": int(latest.get("conclusion_health_score", 0) or 0),
        "latest_conclusion_health_reasons": latest.get("conclusion_health_reasons", []),
        "latest_candidate_count_total": int(latest.get("candidate_count_total", 0) or 0),
        "latest_manual_review_pending_count": int(latest.get("manual_review_pending_count", 0) or 0),
        "ready_count": ready_count,
        "needs_attention_count": needs_attention_count,
        "stale_count": stale_count,
        "recurring_attention_reasons": recurring,
        "recurring_health_reasons": recurring_health,
        "recommended_action": recommended_action,
    }


def _join_recurring(reasons):
    if not reasons:
        return "无"
    return ", ".join(f"{item['reason']} ({item['count']})" for item in reasons)


def render_weekly_delivery_history_report(summary):
    lines = [
        "# 每周最终交付历史摘要",
        "",
        f"- raw_history_count: {summary.get('raw_history_count', summary.get('history_count', 0))}",
        f"- 历史总数：{summary.get('history_count', 0)}",
        f"- 最近记录：{summary.get('window_size', 0)}",
        f"- 最新日期：{summary.get('latest_as_of_date', 'unknown')}",
        f"- 最新状态：{summary.get('latest_status', 'unknown')}",
        f"- 最新新鲜度：{summary.get('latest_freshness_status', 'unknown')}",
        f"- 最新周结论健康：{summary.get('latest_conclusion_health_status', 'unknown')} / {summary.get('latest_conclusion_health_score', 0)}",
        f"- 最新候选总数：{summary.get('latest_candidate_count_total', 0)}",
        f"- 最新待处理复核：{summary.get('latest_manual_review_pending_count', 0)}",
        f"- ready 次数：{summary.get('ready_count', 0)}",
        f"- needs_attention 次数：{summary.get('needs_attention_count', 0)}",
        f"- stale 次数：{summary.get('stale_count', 0)}",
        f"- 重复问题：{_join_recurring(summary.get('recurring_attention_reasons', []))}",
        f"- 重复健康原因：{_join_recurring(summary.get('recurring_health_reasons', []))}",
        f"- 建议动作：{summary.get('recommended_action', 'unknown')}",
        "",
        "## 边界",
        "- 该摘要按 as_of_date 取最后一条记录统计趋势；同一天手动重跑不会被当成多周重复问题。",
        "- 该摘要只读取最终交付验收历史，不抓取行情，不重新评分，也不修改模型参数。",
    ]
    return "\n".join(lines) + "\n"


def write_json(payload, output):
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8-sig",
    )
    return output_path


def write_text(text, output):
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8-sig")
    return output_path


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Summarize weekly delivery check history.")
    parser.add_argument("--history", default="outputs/automation/weekly_delivery_check_history.jsonl")
    parser.add_argument("--window", type=int, default=8)
    parser.add_argument("--output", default="")
    parser.add_argument("--report", default="")
    args = parser.parse_args()
    summary = summarize_weekly_delivery_history(args.history, window=args.window)
    report = render_weekly_delivery_history_report(summary)
    if args.output:
        write_json(summary, args.output)
    if args.report:
        write_text(report, args.report)
    print(report, end="")


if __name__ == "__main__":
    main()
