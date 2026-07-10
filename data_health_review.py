import argparse
import csv
import json
import sys
from pathlib import Path


REVIEW_SCHEMA = "data_health_review"
REVIEW_VERSION = 1
EXPECTED_MANIFEST_SCHEMA = "self_analysis_manifest"
EXPECTED_MANIFEST_VERSION = 1
READY_GAP_STATUSES = {"", "ready", "current", "manual_override_applied"}
REFETCH_REMEDIATIONS = {"refetch_quote", "refetch_or_supplement_quote"}


def _read_csv_rows(path):
    csv_path = Path(path)
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
        ]


def _load_manifest(path):
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if payload.get("manifest_schema") != EXPECTED_MANIFEST_SCHEMA:
        raise ValueError(f"unexpected manifest_schema: {payload.get('manifest_schema', '')}")
    if int(payload.get("manifest_version", 0) or 0) != EXPECTED_MANIFEST_VERSION:
        raise ValueError(f"unexpected manifest_version: {payload.get('manifest_version', '')}")
    return payload


def _split_tickers(value):
    return {
        part.strip()
        for part in str(value or "").replace(";", ",").split(",")
        if part.strip()
    }


def _candidate_tickers_by_market(manifest):
    markets = manifest.get("markets", [])
    if not isinstance(markets, list):
        return {}
    return {
        item.get("name", ""): _split_tickers(item.get("candidate_tickers", ""))
        for item in markets
        if isinstance(item, dict)
    }


def _quote_gaps_path(health_row):
    health_path = Path(health_row.get("path", ""))
    if not str(health_path):
        return None
    return health_path.parent / "quote_gaps.csv"


def _quote_retry_results_path(health_row):
    quote_gaps_path = _quote_gaps_path(health_row)
    if quote_gaps_path is None:
        return None
    return quote_gaps_path.parent / "quote_retry_results.json"


def _load_quote_retry_results(health_row):
    path = _quote_retry_results_path(health_row)
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    if payload.get("retry_schema") != "regional_quote_retry":
        return {}
    results = payload.get("results", [])
    if not isinstance(results, list):
        return {}
    return {
        str(item.get("ticker", "")).strip().upper(): item
        for item in results
        if isinstance(item, dict) and item.get("ticker")
    }


def _is_active_gap(row):
    if "status" not in row:
        return True
    return row.get("status", "").strip().lower() not in READY_GAP_STATUSES


def _is_refetch_gap(row):
    remediation = row.get("remediation_type", "").strip().lower()
    issue_type = row.get("issue_type", "").strip().lower()
    return remediation in REFETCH_REMEDIATIONS or issue_type in {"missing_quote", "partial_quote"}


def _is_manual_financial_review(row):
    remediation = row.get("remediation_type", "").strip().lower()
    issue_type = row.get("issue_type", "").strip().lower()
    return remediation == "manual_financial_review" or issue_type == "non_positive_metric"


def _manual_review_categories(row):
    return [
        part.strip()
        for part in str(row.get("review_category", "") or "").replace(",", ";").split(";")
        if part.strip()
    ]


def _manual_review_is_classified(row):
    return bool(_manual_review_categories(row))


def _manual_review_is_active(row):
    return row.get("in_candidate_pool") or not _manual_review_is_classified(row)


def _manual_review_category_counts(rows):
    counts = {}
    for row in rows:
        categories = _manual_review_categories(row)
        if not categories:
            counts["unclassified"] = counts.get("unclassified", 0) + 1
        for category in categories:
            counts[category] = counts.get(category, 0) + 1
    return counts


def _triage_counts(
    blocked_candidate_count,
    refetch_gap_action_required_count,
    refetch_gap_unresolved_non_candidate_count,
    active_manual_financial_review_count,
    closed_manual_financial_review_count,
):
    candidate_blocking = int(blocked_candidate_count or 0)
    refetch_required = max(int(refetch_gap_action_required_count or 0) - candidate_blocking, 0)
    monitor_only = (
        int(refetch_gap_unresolved_non_candidate_count or 0)
        + int(active_manual_financial_review_count or 0)
        + int(closed_manual_financial_review_count or 0)
    )
    return {
        "candidate_blocking": candidate_blocking,
        "refetch_required": refetch_required,
        "monitor_only": monitor_only,
    }


def _triage_status(counts):
    if counts.get("candidate_blocking", 0):
        return "candidate_blocking"
    if counts.get("refetch_required", 0):
        return "refetch_required"
    if counts.get("monitor_only", 0):
        return "monitor_only"
    return "clear"


def _triage_decision(status):
    return {
        "candidate_blocking": "block_candidate_delivery_until_refetch",
        "refetch_required": "refetch_or_supplement_quote",
        "monitor_only": "monitor_next_run",
        "clear": "continue_monitoring",
    }.get(status, "review_data_health")


def _gap_payload(row, candidate_tickers, retry_results=None):
    ticker = row.get("ticker", "")
    retry = (retry_results or {}).get(ticker.strip().upper(), {})
    return {
        "ticker": ticker,
        "company": row.get("company_name") or row.get("company", ""),
        "issue_type": row.get("issue_type", ""),
        "missing_fields": row.get("missing_fields", ""),
        "remediation_type": row.get("remediation_type", ""),
        "review_category": row.get("review_category", ""),
        "review_detail": row.get("review_detail", ""),
        "in_candidate_pool": ticker in candidate_tickers,
        "refetch_attempted": bool(retry),
        "retry_status": retry.get("status", ""),
        "retry_message": retry.get("message", ""),
    }


def _market_review(health_row, candidate_tickers):
    quote_gaps = _read_csv_rows(_quote_gaps_path(health_row))
    retry_results = _load_quote_retry_results(health_row)
    active_gaps = [row for row in quote_gaps if _is_active_gap(row)]
    refetch_gaps = [
        _gap_payload(row, candidate_tickers, retry_results)
        for row in active_gaps
        if _is_refetch_gap(row)
    ]
    manual_financial = [
        _gap_payload(row, candidate_tickers, retry_results)
        for row in active_gaps
        if _is_manual_financial_review(row) and not _is_refetch_gap(row)
    ]
    candidate_refetch = [row for row in refetch_gaps if row["in_candidate_pool"]]
    action_required_refetch = [
        row for row in refetch_gaps if row["in_candidate_pool"] or not row["refetch_attempted"]
    ]
    unresolved_non_candidate_refetch = [
        row
        for row in refetch_gaps
        if not row["in_candidate_pool"] and row["refetch_attempted"] and row.get("retry_status") != "updated"
    ]
    current_refetch_gaps = action_required_refetch
    attempted_refetch = [row for row in current_refetch_gaps if row["refetch_attempted"]]
    candidate_manual = [row for row in manual_financial if row["in_candidate_pool"]]
    classified_manual = [row for row in manual_financial if _manual_review_is_classified(row)]
    unclassified_manual = [row for row in manual_financial if not _manual_review_is_classified(row)]
    active_manual = [row for row in manual_financial if _manual_review_is_active(row)]
    closed_manual = [row for row in manual_financial if not _manual_review_is_active(row)]
    blocked_count = len(candidate_refetch)
    triage_counts = _triage_counts(
        blocked_count,
        len(action_required_refetch),
        len(unresolved_non_candidate_refetch),
        len(active_manual),
        len(closed_manual),
    )
    triage_status = _triage_status(triage_counts)
    return {
        "name": health_row.get("name", "unknown"),
        "status": health_row.get("status", "unknown"),
        "quote_coverage": health_row.get("quote_coverage", "unknown"),
        "financial_coverage": health_row.get("financial_coverage", "unknown"),
        "quote_gap_count": len(active_gaps),
        "refetch_gap_count": len(current_refetch_gaps),
        "candidate_refetch_gap_count": len(candidate_refetch),
        "refetch_gap_attempted_count": len(attempted_refetch),
        "refetch_gap_action_required_count": len(action_required_refetch),
        "refetch_gap_unresolved_non_candidate_count": len(unresolved_non_candidate_refetch),
        "manual_financial_review_count": len(manual_financial),
        "active_manual_financial_review_count": len(active_manual),
        "closed_manual_financial_review_count": len(closed_manual),
        "candidate_manual_financial_review_count": len(candidate_manual),
        "manual_financial_review_classified_count": len(classified_manual),
        "manual_financial_review_unclassified_count": len(unclassified_manual),
        "candidate_manual_financial_review_unclassified_count": sum(
            1 for row in candidate_manual if not _manual_review_is_classified(row)
        ),
        "manual_financial_review_by_category": _manual_review_category_counts(manual_financial),
        "blocked_candidate_count": blocked_count,
        "candidate_delivery_blocked": blocked_count > 0,
        "data_health_triage_status": triage_status,
        "data_health_triage_decision": _triage_decision(triage_status),
        "data_health_triage_counts": triage_counts,
        "refetch_gaps": current_refetch_gaps,
        "refetch_gap_unresolved_non_candidate_samples": unresolved_non_candidate_refetch[:5],
        "manual_financial_review_samples": manual_financial[:5],
        "quote_gaps_path": str(_quote_gaps_path(health_row) or ""),
        "quote_retry_results_path": str(_quote_retry_results_path(health_row) or ""),
    }


def _overall_decision(markets):
    blocked = sum(item["blocked_candidate_count"] for item in markets)
    refetch = sum(item["refetch_gap_count"] for item in markets)
    manual = sum(item["manual_financial_review_count"] for item in markets)
    if blocked:
        return "blocks_candidate_delivery", "refetch_candidate_quotes"
    if refetch or manual:
        return "acceptable_with_monitoring", "monitor_next_run"
    return "clear", "continue_monitoring"


def build_data_health_review(manifest):
    manifest_path = Path(manifest)
    source = _load_manifest(manifest_path)
    candidate_tickers = _candidate_tickers_by_market(source)
    health_rows = source.get("health", [])
    if not isinstance(health_rows, list):
        health_rows = []
    markets = [
        _market_review(row, candidate_tickers.get(row.get("name", ""), set()))
        for row in health_rows
        if isinstance(row, dict)
    ]
    status, recommended_action = _overall_decision(markets)
    blocked_candidate_count = sum(item["blocked_candidate_count"] for item in markets)
    refetch_gap_count = sum(item["refetch_gap_count"] for item in markets)
    refetch_gap_attempted_count = sum(item["refetch_gap_attempted_count"] for item in markets)
    refetch_gap_action_required_count = sum(item["refetch_gap_action_required_count"] for item in markets)
    refetch_gap_unresolved_non_candidate_count = sum(
        item["refetch_gap_unresolved_non_candidate_count"] for item in markets
    )
    manual_financial_review_count = sum(item["manual_financial_review_count"] for item in markets)
    active_manual_financial_review_count = sum(
        item["active_manual_financial_review_count"] for item in markets
    )
    closed_manual_financial_review_count = sum(
        item["closed_manual_financial_review_count"] for item in markets
    )
    candidate_manual_financial_review_count = sum(
        item["candidate_manual_financial_review_count"] for item in markets
    )
    manual_financial_review_classified_count = sum(
        item["manual_financial_review_classified_count"] for item in markets
    )
    manual_financial_review_unclassified_count = sum(
        item["manual_financial_review_unclassified_count"] for item in markets
    )
    candidate_manual_financial_review_unclassified_count = sum(
        item["candidate_manual_financial_review_unclassified_count"] for item in markets
    )
    triage_counts = _triage_counts(
        blocked_candidate_count,
        refetch_gap_action_required_count,
        refetch_gap_unresolved_non_candidate_count,
        active_manual_financial_review_count,
        closed_manual_financial_review_count,
    )
    triage_status = _triage_status(triage_counts)
    return {
        "review_schema": REVIEW_SCHEMA,
        "review_version": REVIEW_VERSION,
        "as_of_date": source.get("as_of_date", "unknown"),
        "source_manifest": str(manifest_path),
        "source_data_health_status": source.get("data_health_status", "unknown"),
        "status": status,
        "recommended_action": recommended_action,
        "blocked_candidate_count": blocked_candidate_count,
        "candidate_delivery_blocked": blocked_candidate_count > 0,
        "data_health_triage_status": triage_status,
        "data_health_triage_decision": _triage_decision(triage_status),
        "data_health_triage_counts": triage_counts,
        "refetch_gap_count": refetch_gap_count,
        "refetch_gap_attempted_count": refetch_gap_attempted_count,
        "refetch_gap_action_required_count": refetch_gap_action_required_count,
        "refetch_gap_unresolved_non_candidate_count": refetch_gap_unresolved_non_candidate_count,
        "manual_financial_review_count": manual_financial_review_count,
        "active_manual_financial_review_count": active_manual_financial_review_count,
        "closed_manual_financial_review_count": closed_manual_financial_review_count,
        "candidate_manual_financial_review_count": candidate_manual_financial_review_count,
        "manual_financial_review_classified_count": manual_financial_review_classified_count,
        "manual_financial_review_unclassified_count": manual_financial_review_unclassified_count,
        "candidate_manual_financial_review_unclassified_count": candidate_manual_financial_review_unclassified_count,
        "markets": markets,
        "boundary": "只读取现有自我分析和 quote_gaps.csv，不抓取行情，不重新评分，不修改正式模型参数。",
    }


def _yes_no(value):
    return "是" if value else "否"


def render_data_health_review(payload):
    status = payload.get("status", "unknown")
    conclusion = (
        "当前数据健康缺口不直接阻断本周候选"
        if status == "acceptable_with_monitoring"
        else "当前数据健康缺口需要处理后再进入候选交付"
        if status == "blocks_candidate_delivery"
        else "当前未发现数据健康缺口"
    )
    lines = [
        "# 数据健康复核结论",
        "",
        f"- 日期：{payload.get('as_of_date', 'unknown')}",
        f"- 状态：{status}",
        f"- 建议动作：{payload.get('recommended_action', 'unknown')}",
        f"- 结论：{conclusion}。",
        f"- 候选受阻数量：{payload.get('blocked_candidate_count', 0)}",
        f"- 可重抓缺口：{payload.get('refetch_gap_count', 0)}",
        f"- refetch_gap_attempted_count：{payload.get('refetch_gap_attempted_count', 0)}",
        f"- refetch_gap_action_required_count：{payload.get('refetch_gap_action_required_count', payload.get('refetch_gap_count', 0))}",
        f"- refetch_gap_unresolved_non_candidate_count：{payload.get('refetch_gap_unresolved_non_candidate_count', 0)}",
        f"- 财务/估值口径复核：{payload.get('manual_financial_review_count', 0)}",
        f"- active_manual_financial_review_count：{payload.get('active_manual_financial_review_count', payload.get('manual_financial_review_count', 0))}",
        f"- closed_manual_financial_review_count：{payload.get('closed_manual_financial_review_count', 0)}",
        "",
        "## 数据健康三层分流",
        "",
        f"- data_health_triage_status：{payload.get('data_health_triage_status', 'unknown')}",
        f"- data_health_triage_decision：{payload.get('data_health_triage_decision', 'unknown')}",
        f"- candidate_delivery_blocked：{str(bool(payload.get('candidate_delivery_blocked', False))).lower()}",
        "",
        "| 层级 | 数量 | 处理方式 |",
        "|---|---:|---|",
        f"| candidate_blocking | {(payload.get('data_health_triage_counts', {}) or {}).get('candidate_blocking', 0)} | 先补齐候选相关行情，再进入交付 |",
        f"| refetch_required | {(payload.get('data_health_triage_counts', {}) or {}).get('refetch_required', 0)} | 补抓或补充行情源 |",
        f"| monitor_only | {(payload.get('data_health_triage_counts', {}) or {}).get('monitor_only', 0)} | 保留下周监控，不阻断本周候选 |",
        "",
        "## 市场概览",
        "",
        "| 市场 | 行情覆盖 | 财务覆盖 | 可重抓 | 候选可重抓 | 估值口径复核 | 候选受阻 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for market in payload.get("markets", []) or []:
        lines.append(
            f"| {market.get('name', '')} | {market.get('quote_coverage', 'unknown')} | "
            f"{market.get('financial_coverage', 'unknown')} | {market.get('refetch_gap_count', 0)} | "
            f"{market.get('candidate_refetch_gap_count', 0)} | "
            f"{market.get('active_manual_financial_review_count', market.get('manual_financial_review_count', 0))} | "
            f"{market.get('blocked_candidate_count', 0)} |"
        )
    lines.extend(["", "## 可重抓缺口", "", "| 市场 | 股票 | 公司 | 缺失字段 | 候选池内 | 判断 |", "|---|---|---|---|---|---|"])
    any_refetch = False
    for market in payload.get("markets", []) or []:
        for gap in market.get("refetch_gaps", []) or []:
            any_refetch = True
            judgment = "需先补齐再交付" if gap.get("in_candidate_pool") else "不在本周候选池，保留下周观察"
            lines.append(
                f"| {market.get('name', '')} | {gap.get('ticker', '')} | {gap.get('company', '')} | "
                f"{gap.get('missing_fields', '')} | {_yes_no(gap.get('in_candidate_pool'))} | {judgment} |"
            )
    if not any_refetch:
        lines.append("| - | - | - | - | - | 无可重抓缺口 |")
    lines.extend(
        [
            "",
            "## 估值口径复核样例",
            "",
            "| 市场 | 股票 | 公司 | 分类 | 详情 |",
            "|---|---|---|---|---|",
        ]
    )
    any_manual = False
    for market in payload.get("markets", []) or []:
        for gap in market.get("manual_financial_review_samples", []) or []:
            any_manual = True
            lines.append(
                f"| {market.get('name', '')} | {gap.get('ticker', '')} | {gap.get('company', '')} | "
                f"{gap.get('review_category', '')} | {gap.get('review_detail', '')} |"
            )
    if not any_manual:
        lines.append("| - | - | - | - | 无估值口径复核样例 |")
    lines.extend(
        [
            "",
            "## 边界",
            f"- {payload.get('boundary', '')}",
            "- 该复核只用于判断数据底座是否影响本周交付，不构成投资建议。",
            "",
        ]
    )
    lines.extend(["", "## 已重抓仍残留的非候选观察项", "", "| 市场 | 股票 | 公司 | 缺失字段 | 重抓状态 | 说明 |", "|---|---|---|---|---|---|"])
    any_residual = False
    for market in payload.get("markets", []) or []:
        for gap in market.get("refetch_gap_unresolved_non_candidate_samples", []) or []:
            any_residual = True
            lines.append(
                f"| {market.get('name', '')} | {gap.get('ticker', '')} | {gap.get('company', '')} | "
                f"{gap.get('missing_fields', '')} | {gap.get('retry_status', '')} | {gap.get('retry_message', '')} |"
            )
    if not any_residual:
        lines.append("| - | - | - | - | - | 无残留观察项 |")
    lines.extend(
        [
            "",
            f"- candidate_manual_financial_review_count: {payload.get('candidate_manual_financial_review_count', 0)}",
            f"- candidate_manual_financial_review_unclassified_count: {payload.get('candidate_manual_financial_review_unclassified_count', 0)}",
        ]
    )
    return "\n".join(lines)


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
    parser = argparse.ArgumentParser(description="Build data health review from self-analysis manifest.")
    parser.add_argument("--manifest", default="outputs/automation/latest_self_analysis_manifest.json")
    parser.add_argument("--output", default="outputs/automation/latest_data_health_review.json")
    parser.add_argument("--report", default="outputs/automation/latest_data_health_review.md")
    args = parser.parse_args()

    payload = build_data_health_review(args.manifest)
    report = render_data_health_review(payload)
    if args.output:
        write_json(payload, args.output)
    if args.report:
        write_text(report, args.report)
    print(report, end="")
    print(f"Data health review: {args.report}")


if __name__ == "__main__":
    main()
