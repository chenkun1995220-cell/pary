import argparse
import csv
from datetime import datetime
from pathlib import Path


HISTORY_FIELDS = [
    "run_time",
    "universe_count",
    "candidate_count",
    "quote_ready",
    "quote_total",
    "quote_coverage_pct",
    "data_quality_total",
    "data_quality_blocked",
    "data_quality_warnings",
    "affected_candidate_count",
    "share_override_total",
    "share_override_review",
]


def load_csv_rows(path):
    csv_path = Path(path)
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
        ]


def write_csv_rows(path, rows):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HISTORY_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def to_int(value):
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def delta_text(current, previous):
    if previous is None:
        return "无上次记录"
    delta = current - previous
    if delta > 0:
        return f"较上次 +{delta}"
    return f"较上次 {delta}"


def build_snapshot(output_root, run_time):
    root = Path(output_root)
    quote_rows = load_csv_rows(root / "quote_gaps.csv")
    quality_rows = load_csv_rows(root / "data_quality_issues.csv")
    override_rows = load_csv_rows(root / "share_override_audit.csv")
    candidate_rows = load_csv_rows(root / "candidate_pool.csv")

    usable_quote_statuses = {"ready", "manual_override_applied"}
    quote_ready = sum(1 for row in quote_rows if row.get("status") in usable_quote_statuses)
    quote_total = len(quote_rows)
    quote_coverage = (quote_ready / quote_total * 100) if quote_total else 0

    blocked_labels = {"阻断", "严重", "错误", "error", "blocked", "blocker"}
    warning_labels = {"警告", "warning", "warn"}
    data_quality_blocked = sum(
        1 for row in quality_rows if row.get("severity", "").strip().lower() in {label.lower() for label in blocked_labels}
    )
    data_quality_warnings = sum(
        1 for row in quality_rows if row.get("severity", "").strip().lower() in {label.lower() for label in warning_labels}
    )

    candidate_tickers = {row.get("ticker", "").strip().upper() for row in candidate_rows if row.get("ticker")}
    affected_candidate_tickers = {
        row.get("ticker", "").strip().upper()
        for row in quality_rows
        if row.get("ticker", "").strip().upper() in candidate_tickers
    }

    override_review = sum(1 for row in override_rows if row.get("status") not in ("", "current"))

    return {
        "run_time": run_time,
        "universe_count": quote_total,
        "candidate_count": len(candidate_rows),
        "quote_ready": quote_ready,
        "quote_total": quote_total,
        "quote_coverage_pct": f"{quote_coverage:.2f}",
        "data_quality_total": len(quality_rows),
        "data_quality_blocked": data_quality_blocked,
        "data_quality_warnings": data_quality_warnings,
        "affected_candidate_count": len(affected_candidate_tickers),
        "share_override_total": len(override_rows),
        "share_override_review": override_review,
    }


def write_markdown_report(path, snapshot, previous):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    previous_quality = to_int(previous.get("data_quality_total")) if previous else None
    previous_affected = to_int(previous.get("affected_candidate_count")) if previous else None
    previous_review = to_int(previous.get("share_override_review")) if previous else None

    lines = [
        "# 数据健康历史",
        "",
        f"- 本次运行：{snapshot['run_time']}",
        f"- 行情覆盖：{snapshot['quote_ready']}/{snapshot['quote_total']} ({snapshot['quote_coverage_pct']}%)",
        f"- 数据质量问题：{snapshot['data_quality_total']}（{delta_text(to_int(snapshot['data_quality_total']), previous_quality)}）",
        f"- 数据质量阻断：{snapshot['data_quality_blocked']}",
        f"- 数据质量警告：{snapshot['data_quality_warnings']}",
        f"- 受影响候选：{snapshot['affected_candidate_count']}（{delta_text(to_int(snapshot['affected_candidate_count']), previous_affected)}）",
        f"- 人工覆盖需复核：{snapshot['share_override_review']}（{delta_text(to_int(snapshot['share_override_review']), previous_review)}）",
        "",
        "仅用于每周自动化数据健康追踪，不代表模型参数已经自动调整。",
    ]
    output.write_text("\n".join(lines), encoding="utf-8-sig")


def run_data_health_history(output_root, history_path, report_path, run_time=None):
    current_run_time = run_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    history_file = Path(history_path)
    existing_rows = load_csv_rows(history_file)
    previous = existing_rows[-1] if existing_rows else None
    snapshot = build_snapshot(output_root, current_run_time)
    rows = existing_rows + [snapshot]
    write_csv_rows(history_file, rows)
    write_markdown_report(report_path, snapshot, previous)
    return snapshot


def main():
    parser = argparse.ArgumentParser(description="记录每周数据健康历史。")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--history", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--run-time", default=None)
    args = parser.parse_args()

    result = run_data_health_history(
        args.output_root,
        args.history,
        args.report,
        run_time=args.run_time,
    )
    print(f"Data health history updated: {args.history}")
    print(f"Data quality issues: {result['data_quality_total']}")
    print(f"Affected candidates: {result['affected_candidate_count']}")


if __name__ == "__main__":
    main()
