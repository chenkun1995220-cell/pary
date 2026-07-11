import argparse
import csv
import hashlib
import json
from datetime import date, datetime
from pathlib import Path


CONSISTENCY_SCHEMA = "weekly_artifact_consistency"
CONSISTENCY_VERSION = 1
MARKETS = {
    "US": "us_universe",
    "CN": "cn_universe",
    "HK": "hk_universe",
}


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def _summary_fields(path):
    fields = {}
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return fields
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("- ") or ":" not in stripped:
            continue
        key, value = stripped[2:].split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def _report_metric(path, label):
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return -1
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        content = stripped[2:]
        for separator in ("：", ":"):
            if separator in content:
                key, value = content.split(separator, 1)
                if key.strip() == label:
                    return _int_value(value)
    return -1


def _csv_rows(path):
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError:
        return []


def _int_value(value, default=-1):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _iso_date(value):
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def _sha256(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return ""


def _mtime_ns(path):
    try:
        return Path(path).stat().st_mtime_ns
    except OSError:
        return 0


def _mtime_text(value):
    if not value:
        return ""
    return datetime.fromtimestamp(value / 1_000_000_000).astimezone().isoformat(timespec="seconds")


def _unique(items):
    result = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def _market_evidence(project_root, market, directory, current_date, max_age_days, issues):
    market_dir = project_root / "outputs" / directory
    summary_path = market_dir / "latest_run_summary.md"
    candidate_path = market_dir / "candidate_pool.csv"
    fields = _summary_fields(summary_path)
    candidate_rows = _csv_rows(candidate_path)
    evaluations_path = market_dir / "forecast_evaluations.csv"
    investment_summary_path = market_dir / "latest_investment_summary.md"
    performance_report_path = market_dir / "performance_report.md"
    model_audit_path = market_dir / "model_audit.md"
    mature_counts = {
        "evaluations": (
            sum(
                1
                for row in _csv_rows(evaluations_path)
                if row.get("evaluation_status") == "evaluated"
            )
            if evaluations_path.exists()
            else -1
        ),
        "investment_summary": _report_metric(
            investment_summary_path, "成熟评价样本"
        ),
        "performance_report": _report_metric(performance_report_path, "成熟评价"),
        "model_audit": _report_metric(model_audit_path, "成熟评价样本"),
    }
    summary_count = _int_value(fields.get("Candidate count"))
    run_date = _iso_date(fields.get("Run time", ""))
    age_days = (current_date - run_date).days if run_date else None
    prefix = market.lower()

    if not summary_path.exists():
        issues.append(f"{prefix}_run_summary_missing")
    elif run_date is None:
        issues.append(f"{prefix}_run_summary_date_invalid")
    elif age_days < 0:
        issues.append(f"{prefix}_run_summary_future")
    elif age_days > max_age_days:
        issues.append(f"{prefix}_run_summary_stale")

    if not candidate_path.exists():
        issues.append(f"{prefix}_candidate_pool_missing")
    if summary_count != len(candidate_rows):
        issues.append(f"{prefix}_summary_candidate_count_mismatch")
    if min(mature_counts.values()) < 0:
        issues.append(f"{prefix}_mature_evaluation_evidence_missing")
    elif len(set(mature_counts.values())) != 1:
        issues.append(f"{prefix}_mature_evaluation_count_mismatch")

    return {
        "market": market,
        "run_date": run_date.isoformat() if run_date else "",
        "run_started_at": fields.get("Run start time", ""),
        "run_completed_at": fields.get("Run time", ""),
        "age_days": age_days,
        "summary_candidate_count": summary_count,
        "candidate_file_count": len(candidate_rows),
        "mature_evaluation_counts": mature_counts,
        "summary_file": str(summary_path),
        "candidate_file": str(candidate_path),
    }, fields


def _runtime_quote_snapshot(project_root, fields, current_date, max_age_days, issues):
    expected_path = (project_root / "outputs" / "us_universe" / "market_quotes.csv").resolve()
    raw_path = fields.get("Quote snapshot file", "")
    snapshot_path = Path(raw_path) if raw_path else expected_path
    if not snapshot_path.is_absolute():
        snapshot_path = project_root / snapshot_path
    snapshot_path = snapshot_path.resolve()
    policy = fields.get("Quote snapshot policy", "")
    rows = _csv_rows(snapshot_path)
    quote_dates = sorted(
        value
        for value in (str(row.get("quote_date", "")).strip() for row in rows)
        if _iso_date(value)
    )
    actual_min = quote_dates[0] if quote_dates else ""
    actual_max = quote_dates[-1] if quote_dates else ""
    actual_sha = _sha256(snapshot_path)
    summary_rows = _int_value(fields.get("Quote snapshot rows"))

    if policy != "runtime_output_only":
        issues.append("runtime_quote_snapshot_policy_invalid")
    if snapshot_path != expected_path:
        issues.append("runtime_quote_snapshot_path_invalid")
    if not snapshot_path.exists():
        issues.append("runtime_quote_snapshot_missing")
    if summary_rows != len(rows):
        issues.append("runtime_quote_snapshot_row_count_mismatch")
    if fields.get("Quote date min", "") != actual_min:
        issues.append("runtime_quote_snapshot_min_date_mismatch")
    if fields.get("Quote date max", "") != actual_max:
        issues.append("runtime_quote_snapshot_max_date_mismatch")
    if fields.get("Quote snapshot sha256", "").lower() != actual_sha:
        issues.append("runtime_quote_snapshot_sha256_mismatch")

    latest_date = _iso_date(actual_max)
    quote_age_days = (current_date - latest_date).days if latest_date else None
    if latest_date and quote_age_days < 0:
        issues.append("runtime_quote_snapshot_future")
    elif latest_date and quote_age_days > max_age_days:
        issues.append("runtime_quote_snapshot_stale")

    legacy_path = project_root / "data" / "samples" / "us_universe_quotes.csv"
    if legacy_path.exists():
        issues.append("legacy_tracked_quote_snapshot_present")

    return {
        "git_policy": policy,
        "path": str(snapshot_path),
        "row_count": len(rows),
        "summary_row_count": summary_rows,
        "quote_date_min": actual_min,
        "quote_date_max": actual_max,
        "quote_age_days": quote_age_days,
        "sha256": actual_sha,
        "legacy_path_present": legacy_path.exists(),
    }


def _sec_identity_audit(project_root, fields, issues):
    expected_path = (
        project_root / "outputs" / "us_universe" / "sec_identity_audit.csv"
    ).resolve()
    raw_path = fields.get("SEC identity audit", "")
    summary_path = Path(raw_path) if raw_path else expected_path
    if not summary_path.is_absolute():
        summary_path = project_root / summary_path
    summary_path = summary_path.resolve()
    rows = _csv_rows(expected_path)
    summary_rows = _int_value(fields.get("SEC identity conflict count"))
    unresolved = [
        row
        for row in rows
        if row.get("configured_cik", "").strip() != row.get("selected_cik", "").strip()
        or row.get("resolution", "").strip() != "configured_identity_preserved"
    ]

    if summary_path != expected_path:
        issues.append("sec_identity_audit_path_invalid")
    if not expected_path.exists():
        issues.append("sec_identity_audit_missing")
    if summary_rows != len(rows):
        issues.append("sec_identity_audit_row_count_mismatch")
    if unresolved:
        issues.append("sec_identity_audit_unresolved_conflicts")

    return {
        "path": str(expected_path),
        "summary_path": str(summary_path),
        "row_count": len(rows),
        "summary_row_count": summary_rows,
        "unresolved_count": len(unresolved),
        "unresolved_tickers": [row.get("ticker", "") for row in unresolved],
    }


def build_weekly_artifact_consistency(project_root, as_of_date=None, max_age_days=8):
    project_root = Path(project_root)
    current_date = _iso_date(as_of_date or date.today().isoformat())
    if current_date is None:
        raise ValueError(f"invalid as_of_date: {as_of_date}")
    issues = []
    markets = []
    summary_fields = {}
    for market, directory in MARKETS.items():
        evidence, fields = _market_evidence(
            project_root,
            market,
            directory,
            current_date,
            max_age_days,
            issues,
        )
        markets.append(evidence)
        summary_fields[market] = fields

    market_run_dates = sorted(
        {row["run_date"] for row in markets if row.get("run_date")}
    )
    if len(market_run_dates) > 1:
        issues.append("market_run_date_mismatch")

    candidate_counts = {row["market"]: row["candidate_file_count"] for row in markets}
    candidate_count_total = sum(candidate_counts.values())
    conclusion = _read_json(project_root / "outputs" / "automation" / "latest_weekly_conclusion.json")
    delivery = _read_json(project_root / "outputs" / "automation" / "latest_weekly_delivery_check.json")
    conclusion_markets = {
        str(row.get("market", "")): _int_value(row.get("candidate_count"))
        for row in conclusion.get("markets", [])
        if isinstance(row, dict)
    }
    for market, count in candidate_counts.items():
        if conclusion_markets.get(market) != count:
            issues.append(f"{market.lower()}_conclusion_candidate_count_mismatch")

    conclusion_total = _int_value(conclusion.get("candidate_count_total"))
    delivery_total = _int_value(delivery.get("candidate_count_total"))
    if conclusion_total != candidate_count_total:
        issues.append("conclusion_candidate_count_total_mismatch")
    if delivery_total != conclusion_total:
        issues.append("delivery_candidate_count_total_mismatch")
    conclusion_date = str(conclusion.get("as_of_date", ""))
    delivery_date = str(delivery.get("as_of_date", ""))
    if not conclusion_date or conclusion_date != delivery_date:
        issues.append("closure_as_of_date_mismatch")

    market_summary_mtimes = [
        _mtime_ns(row.get("summary_file", "")) for row in markets
    ]
    latest_market_summary_mtime = max(market_summary_mtimes, default=0)
    conclusion_mtime = _mtime_ns(
        project_root / "outputs" / "automation" / "latest_weekly_conclusion.json"
    )
    delivery_mtime = _mtime_ns(
        project_root / "outputs" / "automation" / "latest_weekly_delivery_check.json"
    )
    conclusion_after_markets = bool(
        latest_market_summary_mtime
        and conclusion_mtime
        and conclusion_mtime >= latest_market_summary_mtime
    )
    delivery_after_conclusion = bool(
        conclusion_mtime and delivery_mtime and delivery_mtime >= conclusion_mtime
    )
    if latest_market_summary_mtime and conclusion_mtime and not conclusion_after_markets:
        issues.append("conclusion_older_than_market_outputs")
    if conclusion_mtime and delivery_mtime and not delivery_after_conclusion:
        issues.append("delivery_older_than_conclusion")
    closure_order = {
        "latest_market_summary_modified_at": _mtime_text(latest_market_summary_mtime),
        "conclusion_modified_at": _mtime_text(conclusion_mtime),
        "delivery_modified_at": _mtime_text(delivery_mtime),
        "conclusion_after_markets": conclusion_after_markets,
        "delivery_after_conclusion": delivery_after_conclusion,
    }

    runtime_snapshot = _runtime_quote_snapshot(
        project_root,
        summary_fields.get("US", {}),
        current_date,
        max_age_days,
        issues,
    )
    identity_audit = _sec_identity_audit(
        project_root,
        summary_fields.get("US", {}),
        issues,
    )
    issues = _unique(issues)
    return {
        "consistency_schema": CONSISTENCY_SCHEMA,
        "consistency_version": CONSISTENCY_VERSION,
        "as_of_date": current_date.isoformat(),
        "status": "ready" if not issues else "needs_attention",
        "max_age_days": max_age_days,
        "markets": markets,
        "market_run_dates": market_run_dates,
        "candidate_count_total": candidate_count_total,
        "conclusion_candidate_count_total": conclusion_total,
        "delivery_candidate_count_total": delivery_total,
        "conclusion_as_of_date": conclusion_date,
        "delivery_as_of_date": delivery_date,
        "closure_order": closure_order,
        "runtime_quote_snapshot": runtime_snapshot,
        "sec_identity_audit": identity_audit,
        "issues": issues,
        "formal_model_change_allowed": False,
        "boundary": "只读取现有运行产物，不抓取行情、不重新评分、不修改正式模型参数。",
    }


def render_weekly_artifact_consistency(payload):
    lines = [
        "# 周产物一致性复核",
        "",
        f"- 日期：{payload.get('as_of_date', '')}",
        f"- 状态：{payload.get('status', '')}",
        f"- 候选总数：{payload.get('candidate_count_total', 0)}",
        f"- 统一结论候选数：{payload.get('conclusion_candidate_count_total', 0)}",
        f"- 交付验收候选数：{payload.get('delivery_candidate_count_total', 0)}",
        "",
        "## 三市场",
        "",
        "| 市场 | 运行日期 | 新鲜度天数 | 摘要候选数 | 文件候选数 |",
        "|---|---|---:|---:|---:|",
    ]
    for row in payload.get("markets", []):
        lines.append(
            f"| {row.get('market', '')} | {row.get('run_date', '')} | "
            f"{row.get('age_days', '')} | {row.get('summary_candidate_count', '')} | "
            f"{row.get('candidate_file_count', '')} |"
        )
    snapshot = payload.get("runtime_quote_snapshot", {})
    lines.extend(
        [
            "",
            "## 美股行情快照",
            "",
            f"- Git 策略：{snapshot.get('git_policy', '')}",
            f"- 路径：{snapshot.get('path', '')}",
            f"- 行数：{snapshot.get('row_count', 0)}",
            f"- 行情日期：{snapshot.get('quote_date_min', '')} 至 {snapshot.get('quote_date_max', '')}",
            f"- SHA-256：{snapshot.get('sha256', '')}",
        ]
    )
    identity_audit = payload.get("sec_identity_audit", {})
    lines.extend(
        [
            "",
            "## 美股 SEC 身份审计",
            "",
            f"- 路径：{identity_audit.get('path', '')}",
            f"- 冲突数：{identity_audit.get('row_count', 0)}",
            f"- 摘要冲突数：{identity_audit.get('summary_row_count', -1)}",
            f"- 未解决冲突：{identity_audit.get('unresolved_count', 0)}",
        ]
    )
    closure_order = payload.get("closure_order", {})
    lines.extend(
        [
            "",
            "## 收口顺序",
            "",
            f"- 最新市场摘要：{closure_order.get('latest_market_summary_modified_at', '')}",
            f"- 统一结论：{closure_order.get('conclusion_modified_at', '')}",
            f"- 交付验收：{closure_order.get('delivery_modified_at', '')}",
            f"- 结论晚于市场：{closure_order.get('conclusion_after_markets', False)}",
            f"- 交付晚于结论：{closure_order.get('delivery_after_conclusion', False)}",
        ]
    )
    issues = payload.get("issues", [])
    lines.extend(["", "## 问题", ""])
    lines.extend([f"- {issue}" for issue in issues] or ["- 无"])
    lines.extend(["", "## 边界", "", f"- {payload.get('boundary', '')}"])
    return "\n".join(lines).rstrip() + "\n"


def _write_json(path, payload):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="复核三市场周产物、候选数量和运行行情快照的一致性。")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--as-of-date", default=date.today().isoformat())
    parser.add_argument("--max-age-days", type=int, default=8)
    parser.add_argument("--output", default="outputs/automation/latest_weekly_artifact_consistency.json")
    parser.add_argument("--report", default="outputs/automation/latest_weekly_artifact_consistency.md")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    output = Path(args.output)
    report = Path(args.report)
    if not output.is_absolute():
        output = root / output
    if not report.is_absolute():
        report = root / report
    payload = build_weekly_artifact_consistency(root, args.as_of_date, args.max_age_days)
    _write_json(output, payload)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_weekly_artifact_consistency(payload), encoding="utf-8-sig")
    print(render_weekly_artifact_consistency(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
