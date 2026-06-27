import argparse
import csv
import json
from datetime import datetime
from pathlib import Path


HISTORY_FIELDS = [
    "run_time",
    "market",
    "universe",
    "refresh_status",
    "company_count",
    "quote_ready",
    "quote_total",
    "quote_coverage_pct",
    "financial_ready",
    "financial_total",
    "financial_coverage_pct",
    "candidate_count",
    "valuation_ready",
    "valuation_total",
    "tracking_count",
    "mature_evaluation_count",
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


def status_is_ready(row, field):
    return row.get(field, "").strip().lower() in {"ready", "manual_override_applied"}


def read_refresh_status(cache_dir):
    metadata_path = Path(cache_dir) / "refresh_metadata.json"
    if not metadata_path.exists():
        return "unknown"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return "unknown"
    return str(metadata.get("status") or "unknown")


def build_snapshot(market, universe_label, output_root, cache_dir, run_time):
    root = Path(output_root)
    quote_rows = load_csv_rows(root / "market_snapshot.csv")
    financial_rows = load_csv_rows(root / "financial_snapshot.csv")
    candidate_rows = load_csv_rows(root / "candidate_pool.csv")
    valuation_rows = load_csv_rows(root / "valuation_targets.csv")
    tracking_rows = load_csv_rows(root / "tracking_snapshot.csv")

    quote_ready = sum(1 for row in quote_rows if status_is_ready(row, "data_quality_status"))
    quote_total = len(quote_rows)
    financial_ready = sum(1 for row in financial_rows if status_is_ready(row, "financial_data_status"))
    financial_total = len(financial_rows)
    valuation_ready = sum(1 for row in valuation_rows if status_is_ready(row, "valuation_status"))
    valuation_total = len(valuation_rows)

    mature_evaluations = sum(
        1
        for row in tracking_rows
        if row.get("evaluation_status", "").strip().lower()
        not in {"", "tracking", "pending", "sample_accumulating"}
    )

    quote_coverage = (quote_ready / quote_total * 100) if quote_total else 0
    financial_coverage = (financial_ready / financial_total * 100) if financial_total else 0

    return {
        "run_time": run_time,
        "market": market,
        "universe": universe_label,
        "refresh_status": read_refresh_status(cache_dir),
        "company_count": quote_total,
        "quote_ready": quote_ready,
        "quote_total": quote_total,
        "quote_coverage_pct": f"{quote_coverage:.2f}",
        "financial_ready": financial_ready,
        "financial_total": financial_total,
        "financial_coverage_pct": f"{financial_coverage:.2f}",
        "candidate_count": len(candidate_rows),
        "valuation_ready": valuation_ready,
        "valuation_total": valuation_total,
        "tracking_count": len(tracking_rows),
        "mature_evaluation_count": mature_evaluations,
    }


def write_markdown_report(path, snapshot, previous):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    previous_candidates = to_int(previous.get("candidate_count")) if previous else None
    previous_mature = to_int(previous.get("mature_evaluation_count")) if previous else None

    lines = [
        "# 区域数据健康历史",
        "",
        f"- 本次运行：{snapshot['run_time']}",
        f"- 市场：{snapshot['market']}",
        f"- 股票池：{snapshot['universe']}",
        f"- 刷新状态：{snapshot['refresh_status']}",
        f"- 行情覆盖：{snapshot['quote_ready']}/{snapshot['quote_total']} ({snapshot['quote_coverage_pct']}%)",
        f"- 财务覆盖：{snapshot['financial_ready']}/{snapshot['financial_total']} ({snapshot['financial_coverage_pct']}%)",
        f"- 候选数量：{snapshot['candidate_count']}（{delta_text(to_int(snapshot['candidate_count']), previous_candidates)}）",
        f"- 估值就绪：{snapshot['valuation_ready']}/{snapshot['valuation_total']}",
        f"- 跟踪中样本：{snapshot['tracking_count']}",
        f"- 成熟评价样本：{snapshot['mature_evaluation_count']}（{delta_text(to_int(snapshot['mature_evaluation_count']), previous_mature)}）",
        "",
        "仅用于每周自动化数据健康追踪，不代表模型参数已经自动调整。",
    ]
    output.write_text("\n".join(lines), encoding="utf-8-sig")


def run_regional_data_health_history(
    market,
    universe_label,
    output_root,
    cache_dir,
    history_path,
    report_path,
    run_time=None,
):
    current_run_time = run_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    history_file = Path(history_path)
    existing_rows = load_csv_rows(history_file)
    previous = existing_rows[-1] if existing_rows else None
    snapshot = build_snapshot(market, universe_label, output_root, cache_dir, current_run_time)
    write_csv_rows(history_file, existing_rows + [snapshot])
    write_markdown_report(report_path, snapshot, previous)
    return snapshot


def main():
    parser = argparse.ArgumentParser(description="记录区域每周数据健康历史。")
    parser.add_argument("--market", required=True)
    parser.add_argument("--universe-label", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--history", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--run-time", default=None)
    args = parser.parse_args()

    result = run_regional_data_health_history(
        market=args.market,
        universe_label=args.universe_label,
        output_root=args.output_root,
        cache_dir=args.cache_dir,
        history_path=args.history,
        report_path=args.report,
        run_time=args.run_time,
    )
    print(f"Regional data health history updated: {args.history}")
    print(f"Quote coverage: {result['quote_coverage_pct']}%")
    print(f"Financial coverage: {result['financial_coverage_pct']}%")


if __name__ == "__main__":
    main()
