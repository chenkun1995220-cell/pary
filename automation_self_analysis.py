import argparse
import csv
import json
from datetime import date
from pathlib import Path

from weekly_delivery_history_report import summarize_weekly_delivery_history
from weekly_ops_history_report import summarize_weekly_ops_history


MARKETS = [
    {
        "name": "美股周筛",
        "summary": Path("outputs/us_universe/latest_run_summary.md"),
        "legacy_summary": Path("outputs/automation/latest_run_summary.md"),
        "default_audit": Path("outputs/us_universe/model_audit.md"),
        "default_health": Path("outputs/us_universe/data_health_history.csv"),
        "default_investment": Path("outputs/us_universe/latest_investment_summary.md"),
        "default_quote_gaps": Path("outputs/us_universe/quote_gaps.csv"),
        "default_valuation_review": Path("outputs/us_universe/valuation_review_items.csv"),
    },
    {
        "name": "A股周筛",
        "summary": Path("outputs/cn_universe/latest_run_summary.md"),
        "default_audit": Path("outputs/cn_universe/model_audit.md"),
        "default_health": Path("outputs/cn_universe/data_health_history.csv"),
        "default_investment": Path("outputs/cn_universe/latest_investment_summary.md"),
        "default_quote_gaps": Path("outputs/cn_universe/quote_gaps.csv"),
        "default_valuation_review": Path("outputs/cn_universe/valuation_review_items.csv"),
    },
    {
        "name": "港股周筛",
        "summary": Path("outputs/hk_universe/latest_run_summary.md"),
        "default_audit": Path("outputs/hk_universe/model_audit.md"),
        "default_health": Path("outputs/hk_universe/data_health_history.csv"),
        "default_investment": Path("outputs/hk_universe/latest_investment_summary.md"),
        "default_quote_gaps": Path("outputs/hk_universe/quote_gaps.csv"),
        "default_valuation_review": Path("outputs/hk_universe/valuation_review_items.csv"),
    },
]


def _read_text(path):
    path = Path(path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig")


def _read_csv_rows(path):
    csv_path = Path(path)
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
        ]


def _summary_fields(text):
    fields = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        body = line[2:]
        separator = "：" if "：" in body else ":"
        if separator not in body:
            continue
        key, value = body.split(separator, 1)
        fields[key.strip()] = value.strip()
    return fields


def _resolve_path(project_root, text):
    if not text:
        return None
    path = Path(text)
    if path.is_absolute():
        return path
    return Path(project_root) / path


def _audit_status(path):
    text = _read_text(path)
    fields = _summary_fields(text)
    return fields.get("审计状态") or fields.get("Audit status") or "unknown"


def _market_snapshot(project_root, config):
    path = Path(project_root) / config["summary"]
    legacy_used = False
    if not path.exists() and config.get("legacy_summary"):
        path = Path(project_root) / config["legacy_summary"]
        legacy_used = True
    text = _read_text(path)
    if not text:
        return {
            "name": config["name"],
            "status": "missing",
            "candidate_count": "unknown",
            "candidate_tickers": "unknown",
            "audit_status": "unknown",
            "summary_path": str(path),
            "health_path": str(Path(project_root) / config["default_health"]),
            "investment_path": str(Path(project_root) / config["default_investment"]),
            "quote_gaps_path": str(Path(project_root) / config["default_quote_gaps"]),
            "valuation_review_path": str(Path(project_root) / config["default_valuation_review"]),
        }
    fields = _summary_fields(text)
    audit_path = _resolve_path(project_root, fields.get("Model audit")) or (
        Path(project_root) / config["default_audit"]
    )
    health_path = _resolve_path(project_root, fields.get("Data health history")) or (
        Path(project_root) / config["default_health"]
    )
    quote_gaps_path = _resolve_path(project_root, fields.get("Quote gaps")) or (
        Path(project_root) / config["default_quote_gaps"]
    )
    valuation_review_path = _resolve_path(project_root, fields.get("Valuation review items")) or (
        Path(project_root) / config["default_valuation_review"]
    )
    default_investment_path = Path(project_root) / config["default_investment"]
    investment_path = _resolve_path(project_root, fields.get("Investment summary")) or (
        default_investment_path
    )
    if legacy_used and default_investment_path.exists():
        investment_path = default_investment_path
    return {
        "name": config["name"],
        "status": "ready",
        "candidate_count": fields.get("Candidate count", "unknown"),
        "candidate_tickers": fields.get("Candidate tickers", "unknown"),
        "audit_status": _audit_status(audit_path),
        "summary_path": str(path),
        "health_path": str(health_path),
        "investment_path": str(investment_path),
        "quote_gaps_path": str(quote_gaps_path),
        "valuation_review_path": str(valuation_review_path),
    }


def _backtest_snapshot(project_root):
    path = Path(project_root) / "outputs" / "automation" / "latest_backtest_summary.md"
    text = _read_text(path)
    if not text:
        return {
            "status": "missing",
            "weeks_completed": "unknown",
            "weeks_failed": "unknown",
            "verified": "unknown",
            "weak_rows": "unknown",
            "evidence_status": "unknown",
            "weak_evidence_weeks": "unknown",
            "evidence_next_action": "unknown",
            "summary_path": str(path),
        }
    fields = _summary_fields(text)
    return {
        "status": "ready",
        "weeks_completed": fields.get("Weeks completed", "unknown"),
        "weeks_failed": fields.get("Weeks failed", "unknown"),
        "verified": fields.get("Membership evidence verified", "unknown"),
        "weak_rows": fields.get("Weak evidence rows", "unknown"),
        "evidence_status": fields.get("Evidence status", "unknown"),
        "weak_evidence_weeks": fields.get("Weak evidence weeks", "unknown"),
        "evidence_next_action": fields.get("Evidence next action", "unknown"),
        "summary_path": str(path),
    }


def _weekly_ops_history_snapshot(project_root):
    path = Path(project_root) / "outputs" / "automation" / "weekly_ops_check_history.jsonl"
    if not path.exists():
        return {
            "history_summary_schema": "weekly_ops_history_summary",
            "history_summary_version": 1,
            "history_count": 0,
            "window_size": 0,
            "latest_as_of_date": "unknown",
            "latest_status": "missing",
            "latest_freshness_status": "unknown",
            "ready_count": 0,
            "needs_attention_count": 0,
            "stale_count": 0,
            "recurring_attention_reasons": [],
            "recommended_action": "collect_weekly_ops_history",
            "path": str(path),
        }
    try:
        summary = summarize_weekly_ops_history(path)
    except (ValueError, json.JSONDecodeError) as exc:
        return {
            "history_summary_schema": "weekly_ops_history_summary",
            "history_summary_version": 1,
            "history_count": 0,
            "window_size": 0,
            "latest_as_of_date": "unknown",
            "latest_status": "invalid",
            "latest_freshness_status": "unknown",
            "ready_count": 0,
            "needs_attention_count": 0,
            "stale_count": 0,
            "recurring_attention_reasons": [],
            "recommended_action": "review_weekly_ops_history_file",
            "error": str(exc),
            "path": str(path),
        }
    summary["path"] = str(path)
    return summary


def _weekly_delivery_history_snapshot(project_root):
    path = Path(project_root) / "outputs" / "automation" / "weekly_delivery_check_history.jsonl"
    if not path.exists():
        return {
            "history_summary_schema": "weekly_delivery_history_summary",
            "history_summary_version": 1,
            "history_count": 0,
            "window_size": 0,
            "latest_as_of_date": "unknown",
            "latest_status": "missing",
            "latest_freshness_status": "unknown",
            "ready_count": 0,
            "needs_attention_count": 0,
            "stale_count": 0,
            "recurring_attention_reasons": [],
            "recommended_action": "collect_weekly_delivery_history",
            "path": str(path),
        }
    try:
        summary = summarize_weekly_delivery_history(path)
    except (ValueError, json.JSONDecodeError) as exc:
        return {
            "history_summary_schema": "weekly_delivery_history_summary",
            "history_summary_version": 1,
            "history_count": 0,
            "window_size": 0,
            "latest_as_of_date": "unknown",
            "latest_status": "invalid",
            "latest_freshness_status": "unknown",
            "ready_count": 0,
            "needs_attention_count": 0,
            "stale_count": 0,
            "recurring_attention_reasons": [],
            "recommended_action": "review_weekly_delivery_history_file",
            "error": str(exc),
            "path": str(path),
        }
    summary["path"] = str(path)
    return summary


def _as_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _as_float(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _percent(value):
    number = _as_float(value)
    if number is None:
        return "unknown"
    return f"{number:.2f}%"


def _latest_health_row(path):
    rows = _read_csv_rows(path)
    return rows[-1] if rows else None


def _quote_gap_summary(path):
    rows = _read_csv_rows(path)
    summary = {"total": 0, "refetch": 0, "review": 0, "review_categories": {}}
    ready_statuses = {"", "ready", "current", "manual_override_applied"}
    for row in rows:
        if "status" in row:
            if row.get("status", "").strip().lower() in ready_statuses:
                continue
        summary["total"] += 1
        remediation = row.get("remediation_type", "").strip().lower()
        if remediation in {"refetch_quote", "refetch_or_supplement_quote"}:
            summary["refetch"] += 1
        elif remediation == "manual_financial_review":
            summary["review"] += 1
            for category in row.get("review_category", "").split(";"):
                category = category.strip()
                if category:
                    summary["review_categories"][category] = summary["review_categories"].get(category, 0) + 1
        else:
            issue_type = row.get("issue_type", "").strip().lower()
            if issue_type in {"missing_quote", "partial_quote"}:
                summary["refetch"] += 1
            elif issue_type == "non_positive_metric":
                summary["review"] += 1
                for category in row.get("review_category", "").split(";"):
                    category = category.strip()
                    if category:
                        summary["review_categories"][category] = summary["review_categories"].get(category, 0) + 1
    return summary


def _valuation_review_summary(path):
    rows = _read_csv_rows(path)
    summary = {"total": 0, "categories": {}, "samples": []}
    for row in rows:
        summary["total"] += 1
        category_text = row.get("valuation_review_category") or row.get("review_category") or ""
        for category in category_text.split(";"):
            category = category.strip()
            if category:
                summary["categories"][category] = summary["categories"].get(category, 0) + 1
        if len(summary["samples"]) < 5:
            summary["samples"].append(
                {
                    "ticker": row.get("ticker", ""),
                    "company": row.get("company_name") or row.get("company", ""),
                    "category": category_text,
                    "detail": row.get("valuation_review_detail") or row.get("review_detail") or "",
                }
            )
    return summary


def _format_count_map(counts):
    if not counts:
        return "none"
    return ";".join(f"{key}={counts[key]}" for key in sorted(counts))


def _section_lines(text, heading):
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == f"## {heading}":
            start = index + 1
            break
    if start is None:
        return []
    section = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        section.append(line)
    return section


def _markdown_table_rows(lines):
    rows = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        rows.append(cells)
    if rows and all(cell in {"股票", "公司", "风险说明", "缺口分类", "具体缺口"} for cell in rows[0]):
        return rows[1:]
    return rows


def _is_no_risk_text(text):
    normalized = str(text or "").strip().lower()
    return (
        normalized in {"无", "none", "no", "n/a", "na", "未发现"}
        or normalized.startswith("未发现量化硬性风险")
    )


def _investment_review_snapshot(market):
    path = Path(market["investment_path"])
    text = _read_text(path)
    if not text:
        return {
            "name": market["name"],
            "status": "missing",
            "field_complete": "unknown",
            "quality_gap_count": 0,
            "quality_gaps": [],
            "risk_items": [],
            "path": str(path),
        }

    quality_lines = _section_lines(text, "候选结论质量检查")
    field_complete = "unknown"
    for line in quality_lines:
        stripped = line.strip()
        if stripped.startswith("- 字段完整"):
            separator = "：" if "：" in stripped else ":"
            field_complete = stripped.split(separator, 1)[1].strip() if separator in stripped else "unknown"
            break

    quality_gaps = []
    for cells in _markdown_table_rows(quality_lines):
        if len(cells) >= 4:
            quality_gaps.append(
                {
                    "ticker": cells[0],
                    "company": cells[1],
                    "category": cells[2],
                    "details": cells[3],
                }
            )

    risk_items = []
    for cells in _markdown_table_rows(_section_lines(text, "候选风险说明")):
        if len(cells) >= 3 and not _is_no_risk_text(cells[2]):
            risk_items.append(
                {
                    "ticker": cells[0],
                    "company": cells[1],
                    "risk": cells[2],
                }
            )

    return {
        "name": market["name"],
        "status": "ready",
        "field_complete": field_complete,
        "quality_gap_count": len(quality_gaps),
        "quality_gaps": quality_gaps,
        "risk_items": risk_items,
        "path": str(path),
    }


def _health_snapshot(market):
    path = Path(market["health_path"])
    row = _latest_health_row(path)
    quote_gap_summary = _quote_gap_summary(market["quote_gaps_path"])
    valuation_review_summary = _valuation_review_summary(market["valuation_review_path"])
    if row is None:
        return {
            "name": market["name"],
            "status": "missing",
            "refresh_status": "unknown",
            "quote_coverage": "unknown",
            "financial_coverage": "unknown",
            "candidate_count": "unknown",
            "data_quality_blocked": "unknown",
            "affected_candidate_count": "unknown",
            "share_override_review": "unknown",
            "quote_gap_count": str(quote_gap_summary["total"]),
            "quote_gap_refetch_count": str(quote_gap_summary["refetch"]),
            "quote_gap_review_count": str(quote_gap_summary["review"]),
            "quote_gap_review_categories": _format_count_map(quote_gap_summary["review_categories"]),
            "valuation_review_item_count": str(valuation_review_summary["total"]),
            "valuation_review_categories": _format_count_map(valuation_review_summary["categories"]),
            "valuation_review_samples": valuation_review_summary["samples"],
            "path": str(path),
        }
    financial_value = row.get("financial_coverage_pct")
    return {
        "name": market["name"],
        "status": "ready",
        "refresh_status": row.get("refresh_status") or "n/a",
        "quote_coverage": _percent(row.get("quote_coverage_pct")),
        "quote_coverage_number": _as_float(row.get("quote_coverage_pct")),
        "financial_coverage": _percent(financial_value) if financial_value is not None else "n/a",
        "financial_coverage_number": _as_float(financial_value),
        "candidate_count": row.get("candidate_count", "unknown"),
        "quote_gap_count": str(quote_gap_summary["total"]),
        "quote_gap_refetch_count": str(quote_gap_summary["refetch"]),
        "quote_gap_review_count": str(quote_gap_summary["review"]),
        "quote_gap_review_categories": _format_count_map(quote_gap_summary["review_categories"]),
        "valuation_review_item_count": str(valuation_review_summary["total"]),
        "valuation_review_categories": _format_count_map(valuation_review_summary["categories"]),
        "valuation_review_samples": valuation_review_summary["samples"],
        "data_quality_blocked": row.get("data_quality_blocked", "0"),
        "affected_candidate_count": row.get("affected_candidate_count", "0"),
        "share_override_review": row.get("share_override_review", "0"),
        "path": str(path),
    }


def _health_risks(health):
    risks = []
    for item in health:
        name = item["name"]
        if item["status"] != "ready":
            risks.append(f"数据健康缺失：{name}")
            continue
        refresh_status = item.get("refresh_status", "unknown")
        if refresh_status not in {"online", "n/a", "unknown"}:
            risks.append(f"数据健康需关注：{name} 刷新状态 {refresh_status}")
        quote_coverage = item.get("quote_coverage_number")
        if quote_coverage is not None and quote_coverage < 95:
            risks.append(f"数据健康需关注：{name} 行情覆盖 {quote_coverage:.2f}%")
        financial_coverage = item.get("financial_coverage_number")
        if financial_coverage is not None and financial_coverage < 95:
            risks.append(f"数据健康需关注：{name} 财务覆盖 {financial_coverage:.2f}%")
        blocked = _as_int(item.get("data_quality_blocked"))
        if blocked and blocked > 0:
            risks.append(f"数据健康需关注：{name} 数据质量阻断 {blocked}")
        affected = _as_int(item.get("affected_candidate_count"))
        if affected and affected > 0:
            risks.append(f"数据健康需关注：{name} 受影响候选 {affected}")
        refetch = _as_int(item.get("quote_gap_refetch_count"))
        review_gaps = _as_int(item.get("quote_gap_review_count"))
        quote_gaps = _as_int(item.get("quote_gap_count"))
        unclassified_gaps = max((quote_gaps or 0) - (refetch or 0) - (review_gaps or 0), 0)
        if unclassified_gaps > 0:
            risks.append(f"数据健康需关注：{name} 行情缺口 {unclassified_gaps}")
        if refetch and refetch > 0:
            risks.append(f"数据健康需关注：{name} 行情可重抓缺口 {refetch}")
        if review_gaps and review_gaps > 0:
            risks.append(f"数据健康需关注：{name} 估值口径复核 {review_gaps}")
        valuation_reviews = _as_int(item.get("valuation_review_item_count"))
        uncovered_valuation_reviews = max((valuation_reviews or 0) - (review_gaps or 0), 0)
        if uncovered_valuation_reviews > 0:
            risks.append(f"估值复核待确认：{name} {uncovered_valuation_reviews}")
        review = _as_int(item.get("share_override_review"))
        if review and review > 0:
            risks.append(f"数据健康需关注：{name} 人工覆盖需复核 {review}")
    return risks


def _risks(markets, backtest, health):
    risks = []
    missing = [market["name"] for market in markets if market["status"] != "ready"]
    if missing:
        risks.append("缺失摘要：" + "、".join(missing))
    sample_markets = [
        market["name"] for market in markets if market["audit_status"] == "sample_accumulating"
    ]
    if sample_markets:
        risks.append("模型审计仍在样本积累：" + "、".join(sample_markets))
    risks.extend(_health_risks(health))
    if backtest["status"] != "ready":
        risks.append("缺失严格时点回测摘要")
    failed_weeks = _as_int(backtest.get("weeks_failed"))
    if failed_weeks and failed_weeks > 0:
        risks.append(f"严格时点回测失败周数：{failed_weeks}")
    weak_rows = _as_int(backtest.get("weak_rows"))
    if weak_rows and weak_rows > 0:
        risks.append(f"历史成分仍有弱证据行：{weak_rows}")
    return risks or ["未发现新的自动化阻断项"]


def _candidate_review_risks(candidate_reviews):
    risks = []
    for review in candidate_reviews:
        if review["status"] != "ready":
            risks.append(f"候选复核缺失：{review['name']}")
            continue
        for gap in review["quality_gaps"][:5]:
            risks.append(
                f"{review['name']} 候选需复核：{gap['ticker']} {gap['company']} {gap['category']}：{gap['details']}"
            )
        for item in review["risk_items"][:5]:
            risks.append(
                f"{review['name']} 风险需复核：{item['ticker']} {item['company']} {item['risk']}"
            )
    return risks


def _manual_review_queue(health, candidate_reviews, limit=12):
    queue = []

    def add_item(name, review_type, ticker, company, detail):
        queue.append(
            {
                "rank": len(queue) + 1,
                "name": name,
                "type": review_type,
                "ticker": ticker,
                "company": company,
                "detail": detail,
            }
        )

    for item in health:
        for sample in item.get("valuation_review_samples", []):
            detail = "；".join(
                part
                for part in [sample.get("category", ""), sample.get("detail", "")]
                if part
            )
            add_item(
                item["name"],
                "估值口径",
                sample.get("ticker", ""),
                sample.get("company", ""),
                detail,
            )
            if len(queue) >= limit:
                return queue
    for review in candidate_reviews:
        if review["status"] != "ready":
            continue
        for gap in review["quality_gaps"]:
            add_item(
                review["name"],
                "结论缺口",
                gap["ticker"],
                gap["company"],
                f"{gap['category']}；{gap['details']}",
            )
            if len(queue) >= limit:
                return queue
        for item in review["risk_items"]:
            add_item(
                review["name"],
                "风险提示",
                item["ticker"],
                item["company"],
                item["risk"],
            )
            if len(queue) >= limit:
                return queue
    return queue


MANUAL_REVIEW_QUEUE_FIELDNAMES = [
    "as_of_date",
    "rank",
    "market",
    "review_type",
    "ticker",
    "company",
    "review_detail",
]

MANUAL_REVIEW_REPEAT_FIELDNAMES = [
    "as_of_date",
    "ticker",
    "company",
    "review_type",
    "previous_count",
    "previous_dates",
]


def _manual_review_queue_rows(queue, as_of_date):
    rows = []
    for item in queue:
        rows.append(
            {
                "as_of_date": as_of_date,
                "rank": item.get("rank", ""),
                "market": item.get("name", ""),
                "review_type": item.get("type", ""),
                "ticker": item.get("ticker", ""),
                "company": item.get("company", ""),
                "review_detail": item.get("detail", ""),
            }
        )
    return rows


def _write_manual_review_rows(path, rows):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=MANUAL_REVIEW_QUEUE_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in MANUAL_REVIEW_QUEUE_FIELDNAMES})


def _write_manual_review_queue(path, queue, as_of_date):
    _write_manual_review_rows(path, _manual_review_queue_rows(queue, as_of_date))


def _write_manual_review_history(path, queue, as_of_date):
    current_rows = _manual_review_queue_rows(queue, as_of_date)
    existing_rows = [
        row for row in _read_csv_rows(path)
        if row.get("as_of_date") != as_of_date
    ]
    _write_manual_review_rows(path, existing_rows + current_rows)


def _manual_review_history_repeats(path, queue, as_of_date, limit=10):
    history_by_ticker = {}
    for row in _read_csv_rows(path):
        if row.get("as_of_date") == as_of_date:
            continue
        ticker = row.get("ticker", "")
        if not ticker:
            continue
        entry = history_by_ticker.setdefault(ticker, {"count": 0, "dates": set()})
        entry["count"] += 1
        if row.get("as_of_date"):
            entry["dates"].add(row["as_of_date"])

    repeats = []
    for item in queue:
        ticker = item.get("ticker", "")
        history = history_by_ticker.get(ticker)
        if not history:
            continue
        repeats.append(
            {
                "ticker": ticker,
                "company": item.get("company", ""),
                "review_type": item.get("type", ""),
                "previous_count": history["count"],
                "previous_dates": sorted(history["dates"]),
            }
        )
        if len(repeats) >= limit:
            break
    return repeats


def _write_manual_review_repeats(path, repeats, as_of_date):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=MANUAL_REVIEW_REPEAT_FIELDNAMES)
        writer.writeheader()
        for item in repeats:
            writer.writerow(
                {
                    "as_of_date": as_of_date,
                    "ticker": item.get("ticker", ""),
                    "company": item.get("company", ""),
                    "review_type": item.get("review_type", ""),
                    "previous_count": item.get("previous_count", ""),
                    "previous_dates": ";".join(item.get("previous_dates", [])),
                }
            )


def _write_self_analysis_manifest(path, payload):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8-sig",
    )


def _candidate_count_total(markets):
    total = 0
    for market in markets:
        count = _as_int(market.get("candidate_count"))
        if count is not None:
            total += count
    return total


def _automation_check_payload(manifest, manifest_validation):
    return {
        "check_schema": "weekly_automation_check",
        "check_version": 1,
        "as_of_date": manifest.get("as_of_date", ""),
        "status": manifest.get("automation_status", "unknown"),
        "recommended_action": manifest.get("automation_recommended_action", "unknown"),
        "priority_actions": manifest.get("automation_priority_actions", []),
        "manifest_validation_status": manifest_validation.get("status", "invalid"),
        "manifest_validation_errors": manifest_validation.get("errors", []),
        "market_count": manifest.get("market_count", 0),
        "markets_ready_count": manifest_validation.get("markets_ready_count", 0),
        "not_ready_markets": manifest_validation.get("not_ready_markets", []),
        "candidate_count_total": _candidate_count_total(manifest.get("markets", [])),
        "market_candidate_counts": [
            {
                "name": market.get("name", ""),
                "status": market.get("status", ""),
                "candidate_count": market.get("candidate_count", ""),
            }
            for market in manifest.get("markets", [])
        ],
        "manual_review_queue_count": manifest.get("manual_review_queue_count", 0),
        "manual_review_repeat_count": manifest.get("manual_review_repeat_count", 0),
        "data_health_status": manifest.get("data_health_status", "unknown"),
        "candidate_review_status": manifest.get("candidate_review_status", "unknown"),
        "weekly_ops_history_status": manifest.get("weekly_ops_history_status", "unknown"),
        "weekly_delivery_history_status": manifest.get("weekly_delivery_history_status", "unknown"),
        "model_audit_status": manifest.get("model_audit_status", "unknown"),
        "backtest_status": manifest.get("backtest_status", "unknown"),
        "outputs": manifest.get("outputs", {}),
    }


def _manual_review_status(queue_count, repeat_count):
    if repeat_count > 0:
        return "recurring_manual_review", "review_recurring_items"
    if queue_count > 0:
        return "manual_review_needed", "review_manual_queue"
    return "clear", "monitor_next_run"


def _manifest_markets(markets):
    return [
        {
            "name": market.get("name", ""),
            "status": market.get("status", ""),
            "candidate_count": market.get("candidate_count", ""),
            "candidate_tickers": market.get("candidate_tickers", ""),
            "audit_status": market.get("audit_status", ""),
            "summary_path": market.get("summary_path", ""),
        }
        for market in markets
    ]


def _manifest_health(health):
    return [
        {
            "name": item.get("name", ""),
            "status": item.get("status", ""),
            "refresh_status": item.get("refresh_status", ""),
            "quote_coverage": item.get("quote_coverage", ""),
            "financial_coverage": item.get("financial_coverage", ""),
            "quote_gap_count": item.get("quote_gap_count", ""),
            "quote_gap_refetch_count": item.get("quote_gap_refetch_count", ""),
            "quote_gap_review_count": item.get("quote_gap_review_count", ""),
            "quote_gap_review_categories": item.get("quote_gap_review_categories", ""),
            "valuation_review_item_count": item.get("valuation_review_item_count", ""),
            "valuation_review_categories": item.get("valuation_review_categories", ""),
            "candidate_count": item.get("candidate_count", ""),
            "data_quality_blocked": item.get("data_quality_blocked", ""),
            "affected_candidate_count": item.get("affected_candidate_count", ""),
            "share_override_review": item.get("share_override_review", ""),
            "path": item.get("path", ""),
        }
        for item in health
    ]


def _manifest_model_audit_status(markets):
    statuses = {market.get("name", ""): market.get("audit_status", "unknown") for market in markets}
    sample_count = sum(1 for status in statuses.values() if status == "sample_accumulating")
    shadow_ready_count = sum(1 for status in statuses.values() if status == "shadow_analysis_ready")
    unknown_count = sum(1 for status in statuses.values() if status == "unknown")
    if sample_count:
        status = "sample_accumulating"
        action = "continue_sample_accumulation"
    elif shadow_ready_count:
        status = "shadow_analysis_ready"
        action = "review_shadow_analysis"
    elif unknown_count:
        status = "unknown"
        action = "review_model_audit_inputs"
    else:
        status = "clear"
        action = "monitor_next_run"
    return {
        "model_audit_status": status,
        "model_audit_recommended_action": action,
        "model_audit_sample_accumulating_count": sample_count,
        "model_audit_shadow_ready_count": shadow_ready_count,
        "model_audit_unknown_count": unknown_count,
        "model_audit_statuses": statuses,
    }


def _manifest_data_health_status(health):
    risks = _health_risks(health)
    if risks:
        return {
            "data_health_status": "manual_review_needed",
            "data_health_recommended_action": "review_data_health",
            "data_health_risk_count": len(risks),
            "data_health_risks": risks,
        }
    return {
        "data_health_status": "clear",
        "data_health_recommended_action": "monitor_next_run",
        "data_health_risk_count": 0,
        "data_health_risks": [],
    }


def _manifest_candidate_review_status(candidate_reviews):
    risks = _candidate_review_risks(candidate_reviews)
    quality_gap_count = sum(_as_int(item.get("quality_gap_count")) or 0 for item in candidate_reviews)
    risk_item_count = sum(len(item.get("risk_items", [])) for item in candidate_reviews)
    if risks:
        return {
            "candidate_review_status": "manual_review_needed",
            "candidate_review_recommended_action": "review_candidate_findings",
            "candidate_review_quality_gap_count": quality_gap_count,
            "candidate_review_risk_item_count": risk_item_count,
            "candidate_review_risks": risks,
        }
    return {
        "candidate_review_status": "clear",
        "candidate_review_recommended_action": "monitor_next_run",
        "candidate_review_quality_gap_count": quality_gap_count,
        "candidate_review_risk_item_count": risk_item_count,
        "candidate_review_risks": [],
    }


def _manifest_backtest_status(backtest):
    failed_weeks = _as_int(backtest.get("weeks_failed"))
    weak_rows = _as_int(backtest.get("weak_rows"))
    if backtest.get("status") != "ready":
        status = "missing"
        action = "run_point_in_time_backtest"
    elif failed_weeks and failed_weeks > 0:
        status = "failed_weeks"
        action = "review_backtest_failures"
    elif weak_rows and weak_rows > 0:
        status = "evidence_review_needed"
        action = "review_backtest_evidence"
    else:
        status = "clear"
        action = "monitor_next_run"
    return {
        "backtest_status": status,
        "backtest_recommended_action": action,
        "backtest_weeks_completed": backtest.get("weeks_completed", ""),
        "backtest_weeks_failed": backtest.get("weeks_failed", ""),
        "backtest_membership_verified": backtest.get("verified", ""),
        "backtest_weak_rows": backtest.get("weak_rows", ""),
        "backtest_evidence_status": backtest.get("evidence_status", ""),
        "backtest_weak_evidence_weeks": backtest.get("weak_evidence_weeks", ""),
        "backtest_evidence_next_action": backtest.get("evidence_next_action", ""),
        "backtest_summary_path": backtest.get("summary_path", ""),
    }


def _manifest_weekly_ops_history_status(weekly_ops_history):
    action = weekly_ops_history.get("recommended_action", "collect_weekly_ops_history")
    if action == "continue_monitoring":
        status = "clear"
        recommended_action = "monitor_next_run"
    elif action == "collect_weekly_ops_history":
        status = "missing"
        recommended_action = action
    else:
        status = "manual_review_needed"
        recommended_action = action
    return {
        "weekly_ops_history_status": status,
        "weekly_ops_history_recommended_action": recommended_action,
    }


def _weekly_delivery_health_priority_actions(weekly_delivery_history):
    reasons = []
    for item in weekly_delivery_history.get("recurring_health_reasons", []):
        reason = item.get("reason", "")
        if reason:
            reasons.append(reason)
    reasons.extend(weekly_delivery_history.get("latest_conclusion_health_reasons", []))
    priority_actions = []
    if any(str(reason).startswith("manual_review_pending:") for reason in reasons):
        priority_actions.append("review_manual_review_backlog")
    if any(not str(reason).startswith("manual_review_pending:") for reason in reasons):
        priority_actions.append("review_delivery_health_issues")
    return priority_actions


def _manifest_weekly_delivery_history_status(weekly_delivery_history):
    action = weekly_delivery_history.get("recommended_action", "collect_weekly_delivery_history")
    health_actions = _weekly_delivery_health_priority_actions(weekly_delivery_history)
    if action == "continue_monitoring" and health_actions:
        status = "manual_review_needed"
        recommended_action = health_actions[0]
    elif action == "continue_monitoring":
        status = "clear"
        recommended_action = "monitor_next_run"
    elif action == "collect_weekly_delivery_history":
        status = "missing"
        recommended_action = action
    else:
        status = "manual_review_needed"
        recommended_action = action
    return {
        "weekly_delivery_history_status": status,
        "weekly_delivery_history_recommended_action": recommended_action,
        "weekly_delivery_history_priority_actions": health_actions,
    }


def _manifest_automation_decision(
    model_audit_status,
    backtest_status,
    data_health_status,
    candidate_review_status,
    weekly_ops_history_status,
    weekly_delivery_history_status,
    review_status,
    recommended_next_action,
):
    action_candidates = [
        (review_status, recommended_next_action),
        (data_health_status["data_health_status"], data_health_status["data_health_recommended_action"]),
        (backtest_status["backtest_status"], backtest_status["backtest_recommended_action"]),
        (
            candidate_review_status["candidate_review_status"],
            candidate_review_status["candidate_review_recommended_action"],
        ),
        (
            weekly_ops_history_status["weekly_ops_history_status"],
            weekly_ops_history_status["weekly_ops_history_recommended_action"],
        ),
        (
            weekly_delivery_history_status["weekly_delivery_history_status"],
            weekly_delivery_history_status["weekly_delivery_history_recommended_action"],
        ),
        (model_audit_status["model_audit_status"], model_audit_status["model_audit_recommended_action"]),
    ]
    for action in weekly_delivery_history_status.get("weekly_delivery_history_priority_actions", []):
        action_candidates.append(("manual_review_needed", action))
    priority_actions = []
    for status, action in action_candidates:
        if status in {"clear", "missing"} or action == "monitor_next_run" or action in priority_actions:
            continue
        priority_actions.append(action)
    if not priority_actions:
        return {
            "automation_status": "clear",
            "automation_recommended_action": "monitor_next_run",
            "automation_priority_actions": [],
        }
    if review_status == "recurring_manual_review":
        status = "recurring_manual_review"
    elif any(action != "continue_sample_accumulation" for action in priority_actions):
        status = "manual_review_needed"
    else:
        status = "sample_accumulating"
    return {
        "automation_status": status,
        "automation_recommended_action": priority_actions[0],
        "automation_priority_actions": priority_actions,
    }


def _recommendations(risks, backtest):
    recommendations = []
    if any(risk.startswith("缺失摘要") for risk in risks) or "缺失严格时点回测摘要" in risks:
        recommendations.append("先补齐缺失的周筛或回测摘要，再做模型参数判断。")
    if any(risk.startswith("数据健康") for risk in risks):
        recommendations.append("数据健康异常先人工复核，不自动修改正式模型参数。")
    if any("候选需复核" in risk or "风险需复核" in risk for risk in risks):
        recommendations.append("优先复核候选风险和结论缺口，不自动调整正式模型参数。")
    if any(risk.startswith("估值复核待确认") or "估值口径复核" in risk for risk in risks):
        recommendations.append("优先人工复核估值复核清单，确认亏损、非正净资产或特殊行业估值口径后再解读候选缺口。")
    if _as_int(backtest.get("weak_rows")):
        recommendations.append("继续补充历史成分 verified 证据，降低严格时点回测的数据质量风险。")
    if any("样本积累" in risk for risk in risks):
        recommendations.append("继续积累 4/12/26/52 周评价样本，暂不升级正式模型。")
    if not recommendations:
        recommendations.append("保持现有模型，只做人工复核和样本外观察。")
    return recommendations


def _render(
    as_of_date,
    markets,
    backtest,
    health,
    candidate_reviews,
    manual_review_history_repeats=None,
    weekly_ops_history=None,
    weekly_delivery_history=None,
):
    risks = _risks(markets, backtest, health) + _candidate_review_risks(candidate_reviews)
    recommendations = _recommendations(risks, backtest)
    manual_queue = _manual_review_queue(health, candidate_reviews)
    manual_review_history_repeats = manual_review_history_repeats or []
    weekly_ops_history = weekly_ops_history or {}
    weekly_delivery_history = weekly_delivery_history or {}
    lines = [
        f"# 每周自我分析摘要（{as_of_date}）",
        "",
        "## 运行覆盖",
        "",
        "| 模块 | 状态 | 候选数 | 候选代码 | 模型审计 | 摘要 |",
        "|---|---|---:|---|---|---|",
    ]
    for market in markets:
        lines.append(
            f"| {market['name']} | {market['status']} | {market['candidate_count']} | "
            f"{market['candidate_tickers']} | {market['audit_status']} | {market['summary_path']} |"
        )
        lines.append(f"- {market['name']} 候选数：{market['candidate_count']}")
    lines.extend(
        [
            "",
            "## 数据健康",
            "",
            "| 模块 | 状态 | 刷新状态 | 行情覆盖 | 财务覆盖 | 行情缺口 | 可重抓 | 需复核 | 候选数 |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in health:
        lines.append(
            f"| {item['name']} | {item['status']} | {item['refresh_status']} | "
            f"{item['quote_coverage']} | {item['financial_coverage']} | "
            f"{item['quote_gap_count']} | {item['quote_gap_refetch_count']} | "
            f"{item['quote_gap_review_count']} | {item['candidate_count']} |"
        )
    for item in health:
        categories = item.get("quote_gap_review_categories", "none")
        if categories != "none":
            lines.append(f"- {item['name']} 估值复核分类：{categories}")
        review_count = _as_int(item.get("valuation_review_item_count"))
        review_categories = item.get("valuation_review_categories", "none")
        if review_count and review_count > 0:
            lines.append(f"- {item['name']} 估值复核清单：{review_count}；{review_categories}")
            samples = []
            for sample in item.get("valuation_review_samples", []):
                samples.append(
                    " ".join(
                        part
                        for part in [
                            sample.get("ticker", ""),
                            sample.get("company", ""),
                            sample.get("category", ""),
                            sample.get("detail", ""),
                        ]
                        if part
                    )
                )
            if samples:
                lines.append(f"- {item['name']} 估值复核样例：" + "; ".join(samples))
    lines.extend(
        [
            "",
            "## 候选复核重点",
            "",
            "| 模块 | 状态 | 字段完整 | 结论缺口 | 风险提示 |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for item in candidate_reviews:
        lines.append(
            f"| {item['name']} | {item['status']} | {item['field_complete']} | "
            f"{item['quality_gap_count']} | {len(item['risk_items'])} |"
        )
    recurring_reasons = weekly_ops_history.get("recurring_attention_reasons", [])
    recurring_text = (
        ", ".join(f"{item.get('reason', '')} ({item.get('count', 0)})" for item in recurring_reasons)
        if recurring_reasons
        else "none"
    )
    lines.extend(
        [
            "",
            "## 周度运维历史",
            "",
            f"- history_count: {weekly_ops_history.get('history_count', 0)}",
            f"- latest_status: {weekly_ops_history.get('latest_status', 'unknown')}",
            f"- latest_freshness_status: {weekly_ops_history.get('latest_freshness_status', 'unknown')}",
            f"- needs_attention_count: {weekly_ops_history.get('needs_attention_count', 0)}",
            f"- recurring_attention_reasons: {recurring_text}",
            f"- recommended_action: {weekly_ops_history.get('recommended_action', 'unknown')}",
            f"- history_path: {weekly_ops_history.get('path', '')}",
        ]
    )
    delivery_recurring_reasons = weekly_delivery_history.get("recurring_attention_reasons", [])
    delivery_recurring_text = (
        ", ".join(f"{item.get('reason', '')} ({item.get('count', 0)})" for item in delivery_recurring_reasons)
        if delivery_recurring_reasons
        else "none"
    )
    delivery_health_reasons = weekly_delivery_history.get("recurring_health_reasons", [])
    delivery_health_text = (
        ", ".join(f"{item.get('reason', '')} ({item.get('count', 0)})" for item in delivery_health_reasons)
        if delivery_health_reasons
        else "none"
    )
    delivery_health_actions = _weekly_delivery_health_priority_actions(weekly_delivery_history)
    delivery_health_action_text = ", ".join(delivery_health_actions) if delivery_health_actions else "none"
    lines.extend(
        [
            "",
            "## 最终交付历史",
            "",
            f"- history_count: {weekly_delivery_history.get('history_count', 0)}",
            f"- latest_status: {weekly_delivery_history.get('latest_status', 'unknown')}",
            f"- latest_freshness_status: {weekly_delivery_history.get('latest_freshness_status', 'unknown')}",
            f"- needs_attention_count: {weekly_delivery_history.get('needs_attention_count', 0)}",
            f"- recurring_attention_reasons: {delivery_recurring_text}",
            f"- latest_conclusion_health: {weekly_delivery_history.get('latest_conclusion_health_status', 'unknown')} / {weekly_delivery_history.get('latest_conclusion_health_score', 0)}",
            f"- recurring_health_reasons: {delivery_health_text}",
            f"- health_priority_actions: {delivery_health_action_text}",
            f"- recommended_action: {weekly_delivery_history.get('recommended_action', 'unknown')}",
            f"- history_path: {weekly_delivery_history.get('path', '')}",
        ]
    )
    lines.extend(
        [
            "",
            "## 人工复核队列",
            "",
            "| 模块 | 类型 | 股票 | 公司 | 复核要点 |",
            "|---|---|---|---|---|",
        ]
    )
    if manual_queue:
        for item in manual_queue:
            lines.append(
                f"| {item['name']} | {item['type']} | {item['ticker']} | {item['company']} | {item['detail']} |"
            )
    else:
        lines.append("| - | - | - | - | 本周未发现需优先人工复核的队列项 |")
    lines.extend(
        [
            "",
            "## 严格时点回测",
            "",
            f"- 状态：{backtest['status']}",
            f"- 完成周数：{backtest['weeks_completed']}",
            f"- 失败周数：{backtest['weeks_failed']}",
            f"- 成员证据 verified：{backtest['verified']}",
            f"- 弱证据行：{backtest['weak_rows']}",
            f"- 证据状态：{backtest.get('evidence_status', 'unknown')}",
            f"- 弱证据周数：{backtest.get('weak_evidence_weeks', 'unknown')}",
            f"- 证据下一步：{backtest.get('evidence_next_action', 'unknown')}",
            f"- 摘要：{backtest['summary_path']}",
            "",
            "## 风险与缺口",
            "",
        ]
    )
    lines.extend(f"- {risk}" for risk in risks)
    lines.extend(["", "## 下周优化建议", ""])
    lines.extend(f"- {item}" for item in recommendations)
    if manual_review_history_repeats:
        lines.extend(
            [
                "",
                "## 人工复核历史重复项",
                "",
                "| 股票 | 公司 | 本周类型 | 历史出现次数 | 历史日期 |",
                "|---|---|---|---:|---|",
            ]
        )
        for item in manual_review_history_repeats:
            lines.append(
                f"| {item['ticker']} | {item['company']} | {item['review_type']} | "
                f"{item['previous_count']} | {', '.join(item['previous_dates'])} |"
            )
    lines.append("")
    return "\n".join(lines)


def run_self_analysis(project_root, output=None, as_of_date=None):
    project_root = Path(project_root)
    as_of_date = as_of_date or date.today().isoformat()
    output = Path(output) if output else project_root / "outputs" / "automation" / "latest_self_analysis.md"
    if not output.is_absolute():
        output = project_root / output
    markets = [_market_snapshot(project_root, config) for config in MARKETS]
    health = [_health_snapshot(market) for market in markets]
    candidate_reviews = [_investment_review_snapshot(market) for market in markets]
    backtest = _backtest_snapshot(project_root)
    weekly_ops_history = _weekly_ops_history_snapshot(project_root)
    weekly_delivery_history = _weekly_delivery_history_snapshot(project_root)
    manual_review_queue = _manual_review_queue(health, candidate_reviews)
    manual_review_queue_output = output.parent / "latest_manual_review_queue.csv"
    manual_review_history_output = output.parent / "manual_review_queue_history.csv"
    manual_review_repeats_output = output.parent / "manual_review_repeats.csv"
    manifest_output = output.parent / "latest_self_analysis_manifest.json"
    automation_check_output = output.parent / "latest_automation_check.json"
    manual_review_history_repeats = _manual_review_history_repeats(
        manual_review_history_output, manual_review_queue, as_of_date
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        _render(
            as_of_date,
            markets,
            backtest,
            health,
            candidate_reviews,
            manual_review_history_repeats,
            weekly_ops_history,
            weekly_delivery_history,
        ),
        encoding="utf-8-sig",
    )
    _write_manual_review_queue(manual_review_queue_output, manual_review_queue, as_of_date)
    _write_manual_review_repeats(manual_review_repeats_output, manual_review_history_repeats, as_of_date)
    _write_manual_review_history(manual_review_history_output, manual_review_queue, as_of_date)
    review_status, recommended_next_action = _manual_review_status(
        len(manual_review_queue), len(manual_review_history_repeats)
    )
    model_audit_status = _manifest_model_audit_status(markets)
    backtest_status = _manifest_backtest_status(backtest)
    data_health_status = _manifest_data_health_status(health)
    candidate_review_status = _manifest_candidate_review_status(candidate_reviews)
    weekly_ops_history_status = _manifest_weekly_ops_history_status(weekly_ops_history)
    weekly_delivery_history_status = _manifest_weekly_delivery_history_status(weekly_delivery_history)
    manifest = {
        "manifest_schema": "self_analysis_manifest",
        "manifest_version": 1,
        "as_of_date": as_of_date,
        "market_count": len(markets),
        "markets": _manifest_markets(markets),
        **model_audit_status,
        **backtest_status,
        "health": _manifest_health(health),
        **data_health_status,
        **candidate_review_status,
        "weekly_ops_history": weekly_ops_history,
        **weekly_ops_history_status,
        "weekly_delivery_history": weekly_delivery_history,
        **weekly_delivery_history_status,
        "manual_review_queue_count": len(manual_review_queue),
        "manual_review_repeat_count": len(manual_review_history_repeats),
        "review_status": review_status,
        "recommended_next_action": recommended_next_action,
        **_manifest_automation_decision(
            model_audit_status,
            backtest_status,
            data_health_status,
            candidate_review_status,
            weekly_ops_history_status,
            weekly_delivery_history_status,
            review_status,
            recommended_next_action,
        ),
        "outputs": {
            "self_analysis": str(output),
            "manifest": str(manifest_output),
            "automation_check": str(automation_check_output),
            "manual_review_queue": str(manual_review_queue_output),
            "manual_review_history": str(manual_review_history_output),
            "manual_review_repeats": str(manual_review_repeats_output),
        },
    }
    _write_self_analysis_manifest(manifest_output, manifest)
    manifest_validation = validate_self_analysis_manifest(manifest_output, require_markets_ready=True)
    _write_self_analysis_manifest(
        automation_check_output,
        _automation_check_payload(manifest, manifest_validation),
    )
    return {
        "output": str(output),
        "manual_review_queue_output": str(manual_review_queue_output),
        "manual_review_history_output": str(manual_review_history_output),
        "manual_review_repeats_output": str(manual_review_repeats_output),
        "manifest_output": str(manifest_output),
        "automation_check_output": str(automation_check_output),
        "markets": markets,
        "backtest": backtest,
        "health": health,
        "candidate_reviews": candidate_reviews,
        "weekly_ops_history": weekly_ops_history,
        "weekly_delivery_history": weekly_delivery_history,
        "manual_review_queue": manual_review_queue,
        "manual_review_history_repeats": manual_review_history_repeats,
    }


REQUIRED_SELF_ANALYSIS_MANIFEST_FIELDS = [
    "manifest_schema",
    "manifest_version",
    "as_of_date",
    "automation_status",
    "automation_recommended_action",
    "automation_priority_actions",
    "markets",
    "model_audit_status",
    "model_audit_recommended_action",
    "backtest_status",
    "backtest_recommended_action",
    "health",
    "data_health_status",
    "data_health_recommended_action",
    "candidate_review_status",
    "candidate_review_recommended_action",
    "weekly_ops_history",
    "weekly_ops_history_status",
    "weekly_ops_history_recommended_action",
    "weekly_delivery_history",
    "weekly_delivery_history_status",
    "weekly_delivery_history_recommended_action",
    "manual_review_queue_count",
    "manual_review_repeat_count",
    "review_status",
    "recommended_next_action",
    "outputs",
]


def validate_self_analysis_manifest(path, require_markets_ready=False):
    manifest_path = Path(path)
    if not manifest_path.exists():
        return {
            "status": "invalid",
            "schema": "",
            "version": "",
            "missing_fields": REQUIRED_SELF_ANALYSIS_MANIFEST_FIELDS[:],
            "market_statuses": [],
            "not_ready_markets": [],
            "markets_ready_count": 0,
            "errors": [f"missing_manifest: {manifest_path}"],
        }
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return {
            "status": "invalid",
            "schema": "",
            "version": "",
            "missing_fields": REQUIRED_SELF_ANALYSIS_MANIFEST_FIELDS[:],
            "market_statuses": [],
            "not_ready_markets": [],
            "markets_ready_count": 0,
            "errors": [f"invalid_json: {exc}"],
        }
    missing = [field for field in REQUIRED_SELF_ANALYSIS_MANIFEST_FIELDS if field not in data]
    errors = []
    market_statuses = []
    not_ready_markets = []
    markets_ready_count = 0
    schema = data.get("manifest_schema", "")
    version = data.get("manifest_version", "")
    if schema != "self_analysis_manifest":
        errors.append(f"unexpected_schema: {schema}")
    if version != 1:
        errors.append(f"unexpected_version: {version}")
    if missing:
        errors.append("missing_fields: " + ", ".join(missing))
    if require_markets_ready:
        markets = data.get("markets", [])
        if not isinstance(markets, list):
            errors.append("markets_not_list")
            markets = []
        expected_market_count = len(MARKETS)
        if len(markets) != expected_market_count:
            errors.append(f"market_count: expected {expected_market_count} got {len(markets)}")
        for index, market in enumerate(markets):
            if isinstance(market, dict):
                name = market.get("name") or f"market_{index + 1}"
                status = market.get("status") or "missing"
            else:
                name = f"market_{index + 1}"
                status = "invalid"
            status_row = {"name": name, "status": status}
            market_statuses.append(status_row)
            if status == "ready":
                markets_ready_count += 1
            else:
                not_ready_markets.append(status_row)
        if not_ready_markets:
            errors.append(
                "market_not_ready: "
                + ", ".join(f"{market['name']}={market['status']}" for market in not_ready_markets)
            )
    return {
        "status": "invalid" if errors else "valid",
        "schema": schema,
        "version": version,
        "missing_fields": missing,
        "market_statuses": market_statuses,
        "not_ready_markets": not_ready_markets,
        "markets_ready_count": markets_ready_count,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate weekly automation self-analysis summary.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--output")
    parser.add_argument("--as-of-date")
    parser.add_argument("--validate-manifest")
    parser.add_argument("--require-market-ready", action="store_true")
    args = parser.parse_args()
    if args.validate_manifest:
        validation = validate_self_analysis_manifest(
            args.validate_manifest,
            require_markets_ready=args.require_market_ready,
        )
        if validation["status"] == "valid":
            message = f"Self-analysis manifest valid: schema={validation['schema']} version={validation['version']}"
            if args.require_market_ready:
                message += f" markets_ready={validation['markets_ready_count']}"
            print(message)
            return
        print("Self-analysis manifest invalid: " + "; ".join(validation["errors"]))
        raise SystemExit(1)
    result = run_self_analysis(args.project_root, args.output, args.as_of_date)
    print(f"Self-analysis summary: {result['output']}")
    print(f"Manual review queue: {result['manual_review_queue_output']}")
    print(f"Manual review history: {result['manual_review_history_output']}")
    print(f"Manual review repeats: {result['manual_review_repeats_output']}")
    print(f"Self-analysis manifest: {result['manifest_output']}")
    print(f"Automation check: {result['automation_check_output']}")


if __name__ == "__main__":
    main()
