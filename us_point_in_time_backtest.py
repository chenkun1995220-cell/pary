import argparse
import csv
import json
import tempfile
from bisect import bisect_right
from collections import OrderedDict
from datetime import date, datetime, timezone
from pathlib import Path

from backtest_manifest import config_digest as build_config_digest
from backtest_manifest import upsert_manifest_row, write_checkpoint
from forecast_tracker import TRACKING_FIELDS
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


def _normalize_cik(cik):
    text = str(cik or "").strip()
    if not text:
        return ""
    return text.zfill(10)


class _LazyCompanyFactsCache:
    def __init__(self, cache_dir, allowed_ciks, max_entries=64):
        self.cache_dir = Path(cache_dir)
        self.allowed_ciks = {_normalize_cik(cik) for cik in allowed_ciks if _normalize_cik(cik)}
        self.max_entries = max(1, int(max_entries or 1))
        self._cache = OrderedDict()

    def get(self, cik, default=None):
        normalized = _normalize_cik(cik)
        if not normalized or normalized not in self.allowed_ciks:
            return default
        if normalized in self._cache:
            self._cache.move_to_end(normalized)
            return self._cache[normalized]

        path = _cik_cache_path(self.cache_dir, normalized)
        if not path.exists():
            return default

        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        self._cache[normalized] = payload
        self._cache.move_to_end(normalized)
        while len(self._cache) > self.max_entries:
            self._cache.popitem(last=False)
        return payload


def _load_company_facts(cache_dir, membership_rows, max_entries=64):
    return _LazyCompanyFactsCache(
        cache_dir,
        [row.get("cik", "") for row in membership_rows or []],
        max_entries=max_entries,
    )


def _facts_cache_files(cache_dir):
    cache = Path(cache_dir)
    if not cache.exists():
        return []
    return list(cache.glob("CIK*.json"))


def _price_row_date(row):
    value = row.get("date") if isinstance(row, dict) else None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None
    return None


class _PriceTimeline:
    def __init__(self, rows):
        dated_rows = []
        for row in rows or []:
            row_date = _price_row_date(row)
            if row_date is not None:
                dated_rows.append((row_date, row))
        dated_rows.sort(key=lambda item: item[0])
        self._dates = [item[0] for item in dated_rows]
        self._rows = [item[1] for item in dated_rows]

    def as_of(self, as_of_date):
        cutoff = _price_row_date({"date": as_of_date})
        if cutoff is None:
            raise ValueError(f"Invalid as_of_date: {as_of_date!r}")
        end = bisect_right(self._dates, cutoff)
        return self._rows[:end]


def _group_membership_by_week(rows):
    grouped = {}
    for row in rows:
        week = str(row.get("week", "")).strip()
        if week:
            grouped.setdefault(week, []).append(row)
    return grouped


def _select_replay_weeks(weeks, pilot_weeks=8, full_run=False, pilot_window="latest"):
    ordered = sorted(weeks or [])
    if full_run:
        return ordered
    count = int(pilot_weeks)
    if count <= 0:
        raise ValueError("pilot_weeks must be positive")
    window = str(pilot_window or "latest").strip().lower()
    if window == "latest":
        return ordered[-count:]
    if window == "earliest":
        return ordered[:count]
    raise ValueError(f"pilot_window must be latest or earliest: {pilot_window}")


def _membership_evidence_summary(grouped_membership_rows, selected_weeks):
    counts = {"verified": 0, "secondary": 0, "insufficient": 0}
    total = 0
    weak_weeks = set()
    for week in selected_weeks or []:
        week_has_weak_evidence = False
        for row in grouped_membership_rows.get(week, []):
            label = str(row.get("membership_evidence") or row.get("evidence_level") or "secondary").strip().lower()
            if label not in counts:
                label = "insufficient"
            counts[label] += 1
            total += 1
            if label != "verified":
                week_has_weak_evidence = True
        if week_has_weak_evidence:
            weak_weeks.add(week)
    weak_rows = counts["secondary"] + counts["insufficient"]
    verified_ratio = counts["verified"] / total if total else 0.0
    return {
        "total_rows": total,
        "verified_rows": counts["verified"],
        "secondary_rows": counts["secondary"],
        "insufficient_rows": counts["insufficient"],
        "weak_evidence_rows": weak_rows,
        "weeks_with_weak_evidence": len(weak_weeks),
        "verified_ratio": verified_ratio,
    }


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


def _screening_diagnostics(rows):
    total = len(rows or [])
    candidates = 0
    blocked = 0
    risk_excluded = 0
    low_score = 0
    for row in rows or []:
        score_text = row.get("total_score")
        try:
            score = float(score_text) if score_text not in (None, "") else None
        except (TypeError, ValueError):
            score = None
        is_blocked = row.get("data_quality_status") == "blocked"
        is_major_risk = row.get("risk_flag") == "重大"
        is_candidate = score is not None and score >= 80 and not is_blocked and not is_major_risk
        if is_candidate:
            candidates += 1
        if is_blocked:
            blocked += 1
        if is_major_risk:
            risk_excluded += 1
        if score is None or score < 80:
            low_score += 1
    return {
        "screened_rows": total,
        "candidate_rows": candidates,
        "data_quality_blocked": blocked,
        "major_risk_excluded": risk_excluded,
        "below_score_threshold": low_score,
    }


def _write_backtest_report(output_root, result):
    diagnostics = result.get("screening_diagnostics") or {}
    evidence = result.get("membership_evidence_summary") or {}
    evidence_total = evidence.get("total_rows", 0)
    evidence_verified = evidence.get("verified_rows", 0)
    evidence_ratio = evidence.get("verified_ratio", 0.0) * 100
    text = "\n".join(
        [
            "# 美股严格时点回测报告",
            "",
            f"- 完成周数：{result['weeks_completed']}",
            f"- 失败周数：{result['weeks_failed']}",
            f"- 预测记录：{result['forecast_rows']}",
            f"- 评价记录：{result['evaluation_rows']}",
            "",
            "## 成员证据覆盖",
            "",
            f"- 已验证证据：{evidence_verified}/{evidence_total} ({evidence_ratio:.1f}%)",
            f"- secondary 证据：{evidence.get('secondary_rows', 0)}",
            f"- insufficient 证据：{evidence.get('insufficient_rows', 0)}",
            f"- 弱证据行：{evidence.get('weak_evidence_rows', 0)}",
            f"- 存在弱证据的回放周：{evidence.get('weeks_with_weak_evidence', 0)}",
            "",
            "## 最后一周筛选诊断",
            "",
            f"- 参与筛选：{diagnostics.get('screened_rows', 0)}",
            f"- 进入候选池：{diagnostics.get('candidate_rows', 0)}",
            f"- 低于评分门槛：{diagnostics.get('below_score_threshold', 0)}",
            f"- 数据质量阻断：{diagnostics.get('data_quality_blocked', 0)}",
            f"- 重大风险标记排除：{diagnostics.get('major_risk_excluded', 0)}",
            "",
            "- 结论：样本或证据积累中，不得自动升级正式模型。",
            "",
        ]
    )
    (Path(output_root) / "backtest_report.md").write_text(text, encoding="utf-8-sig")


def _write_leakage_audit_report(output_root, audit_rows, detail_limit=1000):
    output = Path(output_root)
    severe_count = sum(1 for row in audit_rows if row.get("severity") == "severe")
    weeks = sorted({str(row.get("generated_date", "")).strip() for row in audit_rows if row.get("generated_date")})
    detail_rows = audit_rows[:detail_limit]
    lines = [
        "# 数据泄漏审计",
        "",
        f"- 覆盖回放周数：{len(weeks)}",
        f"- 严重泄漏数：{severe_count}",
        f"- 审计记录数：{len(audit_rows)}",
        f"- Markdown 明细行：{len(detail_rows)}/{len(audit_rows)}",
        "",
        "| 回放日期 | 记录类型 | 来源 | 代码 | 可用时间 | 严重程度 | 原因 |",
        "|---|---|---|---|---|---|---|",
    ]
    if detail_rows:
        for row in detail_rows:
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
    pilot_window="latest",
):
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    membership_rows = _read_csv(membership_path)
    price_rows = _read_csv(price_history_path)
    benchmark_rows = _read_csv(benchmark_history_path)
    price_timeline = _PriceTimeline(price_rows)
    benchmark_timeline = _PriceTimeline(benchmark_rows)
    grouped = _group_membership_by_week(membership_rows)
    weeks = sorted(grouped)
    selected_weeks = _select_replay_weeks(
        weeks,
        pilot_weeks=pilot_weeks,
        full_run=full_run,
        pilot_window=pilot_window,
    )
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
            "pilot_window": str(pilot_window or "latest"),
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
            replay_price_rows = price_timeline.as_of(week)
            replay_benchmark_rows = benchmark_timeline.as_of(week)
            replay_result = replay_week(
                week,
                week_rows,
                facts,
                replay_price_rows,
                replay_benchmark_rows,
                output,
                digest,
                price_rows_as_of=True,
                benchmark_rows_as_of=True,
                preserve_price_history=True,
            )
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
        "screening_diagnostics": _screening_diagnostics(_read_csv(output / "screening_results.csv")),
        "membership_evidence_summary": _membership_evidence_summary(grouped, selected_weeks),
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
    parser.add_argument("--pilot-window", choices=["latest", "earliest"], default="latest")
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
        pilot_window=args.pilot_window,
        full_run=args.full_run,
        config_digest=args.config_digest,
    )
    print(f"Weeks completed: {result['weeks_completed']}")
    print(f"Weeks failed: {result['weeks_failed']}")
    print(f"Forecast rows: {result['forecast_rows']}")
    print(f"Evaluation rows: {result['evaluation_rows']}")


if __name__ == "__main__":
    main()
