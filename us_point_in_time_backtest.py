import argparse
import csv
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from backtest_manifest import config_digest as build_config_digest
from backtest_manifest import upsert_manifest_row, write_checkpoint
from forecast_tracker import TRACKING_FIELDS
from historical_price_store import prices_available_as_of
from shadow_backtest import run_shadow_backtest
from us_weekly_replay import AUDIT_FIELDS, evaluate_backtest_forecast, replay_week


EVALUATION_FIELDS = TRACKING_FIELDS + ["backtest_eligible"]


def _read_csv(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _atomic_csv(path, rows, fieldnames):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", newline="", delete=False, dir=path.parent) as handle:
            temporary = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def _cik_cache_path(cache_dir, cik):
    normalized = str(cik or "").strip().zfill(10)
    return Path(cache_dir) / f"CIK{normalized}.json"


def _load_company_facts(cache_dir, membership_rows):
    facts = {}
    for row in membership_rows:
        cik = str(row.get("cik", "")).strip()
        if not cik or cik in facts:
            continue
        path = _cik_cache_path(cache_dir, cik)
        if path.exists():
            facts[cik] = json.loads(path.read_text(encoding="utf-8-sig"))
    return facts


def _facts_cache_files(cache_dir):
    cache = Path(cache_dir)
    if not cache.exists():
        return []
    return list(cache.glob("CIK*.json"))


def _group_membership_by_week(rows):
    grouped = {}
    for row in rows:
        week = str(row.get("week", "")).strip()
        if week:
            grouped.setdefault(week, []).append(row)
    return grouped


def _validate_prepared_inputs(membership_rows, price_rows, benchmark_rows, grouped, selected_weeks, company_facts_cache):
    problems = []
    if not membership_rows:
        problems.append("historical_membership.csv has no rows")
    if not grouped:
        problems.append("historical_membership.csv has no usable week rows")
    if not selected_weeks:
        problems.append("no replay weeks selected")
    if not price_rows:
        problems.append("price_history.csv has no rows")
    if not benchmark_rows:
        problems.append("benchmark_history.csv has no rows")
    if not _facts_cache_files(company_facts_cache):
        problems.append("SEC company facts cache has no CIK*.json files")
    if problems:
        raise ValueError("Prepared backtest inputs are required before execution: " + "; ".join(problems))


def _evaluation_key(row):
    return (
        row.get("market", ""),
        row.get("ticker", ""),
        row.get("generated_date", ""),
        row.get("model_version", ""),
        str(row.get("checkpoint_weeks", "")),
        row.get("evaluation_version", ""),
    )


def _dedupe_evaluations(rows):
    keyed = {}
    for row in rows:
        keyed[_evaluation_key(row)] = dict(row)
    return sorted(
        keyed.values(),
        key=lambda row: (
            row.get("generated_date", ""),
            row.get("ticker", ""),
            str(row.get("checkpoint_weeks", "")),
            row.get("model_version", ""),
        ),
    )


def _write_backtest_report(output_root, result):
    text = "\n".join(
        [
            "# 美股严格时点回测报告",
            "",
            f"- 完成周数：{result['weeks_completed']}",
            f"- 失败周数：{result['weeks_failed']}",
            f"- 预测记录：{result['forecast_rows']}",
            f"- 评价记录：{result['evaluation_rows']}",
            "- 结论：样本或证据积累中，不得自动升级正式模型。",
            "",
        ]
    )
    (Path(output_root) / "backtest_report.md").write_text(text, encoding="utf-8-sig")


def _write_leakage_audit_report(output_root, audit_rows):
    output = Path(output_root)
    severe_count = sum(1 for row in audit_rows if row.get("severity") == "severe")
    weeks = sorted({str(row.get("generated_date", "")).strip() for row in audit_rows if row.get("generated_date")})
    lines = [
        "# 数据泄漏审计",
        "",
        f"- 覆盖回放周数：{len(weeks)}",
        f"- 严重泄漏数：{severe_count}",
        f"- 审计记录数：{len(audit_rows)}",
        "",
        "| 回放日期 | 记录类型 | 来源 | 代码 | 可用时间 | 严重程度 | 原因 |",
        "|---|---|---|---|---|---|---|",
    ]
    if audit_rows:
        for row in audit_rows:
            lines.append(
                f"| {row.get('generated_date', '')} | {row.get('record_type', '')} | {row.get('source', '')} | "
                f"{row.get('ticker', '')} | {row.get('available_at', '')} | {row.get('severity', '')} | "
                f"{row.get('reason', '')} |"
            )
    else:
        lines.append("| - | - | - | - | - | - | - |")
    (output / "data_leakage_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def run_point_in_time_backtest(
    membership_path,
    company_facts_cache,
    price_history_path,
    benchmark_history_path,
    output_root,
    pilot_weeks=8,
    full_run=False,
    config_digest=None,
):
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    membership_rows = _read_csv(membership_path)
    price_rows = _read_csv(price_history_path)
    benchmark_rows = _read_csv(benchmark_history_path)
    grouped = _group_membership_by_week(membership_rows)
    weeks = sorted(grouped)
    selected_weeks = weeks if full_run else weeks[: int(pilot_weeks)]
    _validate_prepared_inputs(
        membership_rows,
        price_rows,
        benchmark_rows,
        grouped,
        selected_weeks,
        company_facts_cache,
    )
    digest = config_digest or build_config_digest(
        {
            "membership": str(membership_path),
            "price_history": str(price_history_path),
            "benchmark_history": str(benchmark_history_path),
            "pilot_weeks": int(pilot_weeks),
            "full_run": bool(full_run),
        }
    )
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest_path = output / "replay_manifest.csv"
    evaluation_rows = _read_csv(output / "backtest_evaluations.csv")
    batch_audit_rows = []
    completed = 0
    failed = 0
    last_week = ""

    for week in selected_weeks:
        week_rows = grouped[week]
        facts = _load_company_facts(company_facts_cache, week_rows)
        try:
            replay_price_rows = prices_available_as_of(price_rows, week)
            replay_benchmark_rows = prices_available_as_of(benchmark_rows, week)
            replay_result = replay_week(week, week_rows, facts, replay_price_rows, replay_benchmark_rows, output, digest)
            batch_audit_rows.extend(_read_csv(output / "data_leakage_audit.csv"))
            completed += 1
            last_week = week
            upsert_manifest_row(
                manifest_path,
                {
                    "batch_id": batch_id,
                    "week": week,
                    "status": "completed",
                    "config_digest": digest,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "eligible": str(replay_result.get("eligible", "")).lower(),
                    "quality_reasons": ";".join(replay_result.get("quality_reasons", [])),
                },
            )
        except Exception as exc:
            failed += 1
            upsert_manifest_row(
                manifest_path,
                {
                    "batch_id": batch_id,
                    "week": week,
                    "status": "failed",
                    "config_digest": digest,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "error": str(exc),
                },
            )
            continue

    _atomic_csv(output / "data_leakage_audit.csv", batch_audit_rows, AUDIT_FIELDS)
    _write_leakage_audit_report(output, batch_audit_rows)

    for forecast in _read_csv(output / "backtest_forecasts.csv"):
        ticker = str(forecast.get("ticker", "")).upper()
        stock_rows = [row for row in price_rows if str(row.get("ticker", "")).upper() == ticker]
        evaluation_rows.extend(evaluate_backtest_forecast(forecast, stock_rows, benchmark_rows))
    evaluation_rows = _dedupe_evaluations(evaluation_rows)
    _atomic_csv(output / "backtest_evaluations.csv", evaluation_rows, EVALUATION_FIELDS)

    if evaluation_rows:
        run_shadow_backtest(output / "backtest_evaluations.csv", output)

    result = {
        "weeks_completed": completed,
        "weeks_failed": failed,
        "forecast_rows": len(_read_csv(output / "backtest_forecasts.csv")),
        "evaluation_rows": len(evaluation_rows),
    }
    write_checkpoint(
        output / "checkpoint.json",
        {
            "batch_id": batch_id,
            "config_digest": digest,
            "last_completed_week": last_week,
            "success_count": completed,
            "failure_count": failed,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    _write_backtest_report(output, result)
    return result


def main():
    parser = argparse.ArgumentParser(description="Run US point-in-time weekly backtest from prepared inputs.")
    parser.add_argument("--membership", required=True)
    parser.add_argument("--company-facts-cache", required=True)
    parser.add_argument("--price-history", required=True)
    parser.add_argument("--benchmark-history", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--pilot-weeks", type=int, default=8)
    parser.add_argument("--full-run", action="store_true")
    parser.add_argument("--config-digest")
    args = parser.parse_args()
    result = run_point_in_time_backtest(
        args.membership,
        args.company_facts_cache,
        args.price_history,
        args.benchmark_history,
        args.output_root,
        pilot_weeks=args.pilot_weeks,
        full_run=args.full_run,
        config_digest=args.config_digest,
    )
    print(f"Weeks completed: {result['weeks_completed']}")
    print(f"Weeks failed: {result['weeks_failed']}")
    print(f"Forecast rows: {result['forecast_rows']}")
    print(f"Evaluation rows: {result['evaluation_rows']}")


if __name__ == "__main__":
    main()
