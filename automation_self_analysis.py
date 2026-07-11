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
        "default_forecast_evaluations": Path("outputs/us_universe/forecast_evaluations.csv"),
    },
    {
        "name": "A股周筛",
        "summary": Path("outputs/cn_universe/latest_run_summary.md"),
        "default_audit": Path("outputs/cn_universe/model_audit.md"),
        "default_health": Path("outputs/cn_universe/data_health_history.csv"),
        "default_investment": Path("outputs/cn_universe/latest_investment_summary.md"),
        "default_quote_gaps": Path("outputs/cn_universe/quote_gaps.csv"),
        "default_valuation_review": Path("outputs/cn_universe/valuation_review_items.csv"),
        "default_forecast_evaluations": Path("outputs/cn_universe/forecast_evaluations.csv"),
    },
    {
        "name": "港股周筛",
        "summary": Path("outputs/hk_universe/latest_run_summary.md"),
        "default_audit": Path("outputs/hk_universe/model_audit.md"),
        "default_health": Path("outputs/hk_universe/data_health_history.csv"),
        "default_investment": Path("outputs/hk_universe/latest_investment_summary.md"),
        "default_quote_gaps": Path("outputs/hk_universe/quote_gaps.csv"),
        "default_valuation_review": Path("outputs/hk_universe/valuation_review_items.csv"),
        "default_forecast_evaluations": Path("outputs/hk_universe/forecast_evaluations.csv"),
    },
]

MANUAL_REVIEW_DECISIONS_PATH = Path("outputs/automation/manual_review_decisions.csv")
CLOSED_MANUAL_REVIEW_STATUSES = {"accepted", "rejected"}
SP500_CURRENT_MEMBERSHIP_SOURCE_INBOX_STATUS_PATH = Path(
    "outputs/automation/latest_sp500_current_membership_source_inbox_status.json"
)


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


def _read_json(path):
    json_path = Path(path)
    if not json_path.exists():
        return {}
    try:
        return json.loads(json_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


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
    review_path = (
        Path(project_root)
        / "outputs"
        / "automation"
        / "latest_backtest_evidence_review.json"
    )
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
    snapshot = {
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
    if review_path.exists():
        try:
            review = json.loads(review_path.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError):
            review = {}
        if review.get("evidence_ceiling_status") == "evidence_ceiling_confirmed":
            snapshot.update(
                {
                    "evidence_status": "evidence_ceiling_confirmed",
                    "evidence_next_action": "maintain_limited_backtest",
                    "backtest_mode": review.get("backtest_mode", "limited_verified_only"),
                    "unresolved_gap_count": _as_int(
                        review.get("membership_evidence_unresolved_gap_count")
                    ),
                    "evidence_review_path": str(review_path),
                }
            )
    return snapshot


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
            "latest_action_items_actual_count": 0,
            "max_action_items_actual_count": 0,
            "action_items_actual_count_delta": 0,
            "action_items_actual_count_trend": "insufficient",
            "latest_conclusion_signal_status": "unknown",
            "latest_missing_conclusion_signals": [],
            "conclusion_signal_ready_count": 0,
            "conclusion_signal_problem_count": 0,
            "recurring_missing_conclusion_signals": [],
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
            "latest_action_items_actual_count": 0,
            "max_action_items_actual_count": 0,
            "action_items_actual_count_delta": 0,
            "action_items_actual_count_trend": "insufficient",
            "latest_conclusion_signal_status": "unknown",
            "latest_missing_conclusion_signals": [],
            "conclusion_signal_ready_count": 0,
            "conclusion_signal_problem_count": 0,
            "recurring_missing_conclusion_signals": [],
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
            elif (
                row.get("status", "").strip().lower()
                in {"needs_fill", "missing", "partial"}
                and row.get("missing_fields", "").strip()
            ):
                summary["refetch"] += 1
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


def _average(values):
    cleaned = [value for value in values if value is not None]
    return sum(cleaned) / len(cleaned) if cleaned else None


def _forecast_market_snapshot(project_root, config):
    path = Path(project_root) / config["default_forecast_evaluations"]
    if not path.exists():
        return {
            "name": config["name"],
            "status": "missing",
            "total_evaluations": 0,
            "mature_evaluations": 0,
            "one_week_mature": 0,
            "one_month_mature": 0,
            "prediction_unavailable": 0,
            "direction_hits": 0,
            "direction_hit_rate": None,
            "average_return": None,
            "average_excess_return": None,
            "path": str(path),
        }
    rows = _read_csv_rows(path)
    mature = [row for row in rows if row.get("evaluation_status") == "evaluated"]
    hits = [row for row in mature if str(row.get("direction_hit", "")).lower() == "true"]
    return {
        "name": config["name"],
        "status": "ready",
        "total_evaluations": len(rows),
        "mature_evaluations": len(mature),
        "one_week_mature": sum(1 for row in mature if row.get("prediction_horizon") == "1w"),
        "one_month_mature": sum(1 for row in mature if row.get("prediction_horizon") == "1m"),
        "prediction_unavailable": sum(1 for row in rows if row.get("evaluation_status") == "prediction_unavailable"),
        "direction_hits": len(hits),
        "direction_hit_rate": len(hits) / len(mature) if mature else None,
        "average_return": _average(_as_float(row.get("actual_return")) for row in mature),
        "average_excess_return": _average(_as_float(row.get("excess_return")) for row in mature),
        "path": str(path),
    }


def _forecast_performance_snapshot(project_root):
    markets = [_forecast_market_snapshot(project_root, config) for config in MARKETS]
    review = _read_json(Path(project_root) / "outputs" / "automation" / "latest_forecast_performance_review.json")
    total = sum(item["total_evaluations"] for item in markets)
    mature = sum(item["mature_evaluations"] for item in markets)
    hits = sum(item["direction_hits"] for item in markets)
    one_week = sum(item["one_week_mature"] for item in markets)
    one_month = sum(item["one_month_mature"] for item in markets)
    prediction_unavailable = sum(item["prediction_unavailable"] for item in markets)
    missing_market_count = sum(1 for item in markets if item["status"] == "missing")
    average_return = _average(item.get("average_return") for item in markets if item.get("average_return") is not None)
    average_excess_return = _average(
        item.get("average_excess_return") for item in markets if item.get("average_excess_return") is not None
    )
    direction_hit_rate = hits / mature if mature else None
    if review.get("review_schema") == "forecast_performance_review":
        review_markets = review.get("markets") if isinstance(review.get("markets"), list) else markets
        return {
            "forecast_performance_schema": "forecast_performance_summary",
            "forecast_performance_version": 1,
            "status": review.get("status", "unknown"),
            "recommended_action": review.get("recommended_action", "review_forecast_performance"),
            "total_evaluations": _as_int(review.get("total_evaluations")) or 0,
            "mature_evaluations": _as_int(review.get("mature_evaluations")) or 0,
            "one_week_mature": _as_int(review.get("one_week_mature")) or 0,
            "one_month_mature": _as_int(review.get("one_month_mature")) or 0,
            "prediction_unavailable": _as_int(review.get("prediction_unavailable")) or 0,
            "latest_prediction_unavailable_count": _as_int(
                review.get("latest_prediction_unavailable_count")
            )
            or 0,
            "legacy_prediction_unavailable_count": _as_int(
                review.get("legacy_prediction_unavailable_count")
            )
            or 0,
            "missing_market_count": _as_int(review.get("missing_market_count")) or 0,
            "direction_hits": _as_int(review.get("direction_hits")) or 0,
            "direction_hit_rate": review.get("direction_hit_rate"),
            "average_return": review.get("average_return"),
            "average_excess_return": review.get("average_excess_return"),
            "model_audit_status_counts": review.get("model_audit_status_counts", {}),
            "shadow_model_proposal_count": _as_int(review.get("shadow_model_proposal_count")) or 0,
            "next_one_week_evaluation_date": review.get("next_one_week_evaluation_date", ""),
            "next_one_week_evaluation_count": _as_int(review.get("next_one_week_evaluation_count")) or 0,
            "next_one_month_evaluation_date": review.get("next_one_month_evaluation_date", ""),
            "next_one_month_evaluation_count": _as_int(review.get("next_one_month_evaluation_count")) or 0,
            "markets": review_markets,
        }
    weak_performance = (
        mature >= 30
        and (
            (direction_hit_rate is not None and direction_hit_rate < 0.45)
            or (average_excess_return is not None and average_excess_return < 0)
        )
    )
    if missing_market_count and total == 0:
        status = "missing"
        action = "collect_forecast_evaluations"
    elif missing_market_count:
        status = "partial_sample_accumulating" if mature < 30 else "partial_ready"
        action = "continue_sample_accumulation" if mature < 30 else "review_forecast_performance"
    elif mature < 30:
        status = "sample_accumulating"
        action = "continue_sample_accumulation"
    elif weak_performance:
        status = "performance_review_needed"
        action = "review_forecast_performance"
    else:
        status = "ready"
        action = "review_forecast_performance"
    return {
        "forecast_performance_schema": "forecast_performance_summary",
        "forecast_performance_version": 1,
        "status": status,
        "recommended_action": action,
        "total_evaluations": total,
        "mature_evaluations": mature,
        "one_week_mature": one_week,
        "one_month_mature": one_month,
        "prediction_unavailable": prediction_unavailable,
        "missing_market_count": missing_market_count,
        "direction_hits": hits,
        "direction_hit_rate": direction_hit_rate,
        "average_return": average_return,
        "average_excess_return": average_excess_return,
        "next_one_week_evaluation_date": review.get("next_one_week_evaluation_date", ""),
        "next_one_week_evaluation_count": _as_int(
            review.get("next_one_week_evaluation_count"),
        )
        or 0,
        "next_one_month_evaluation_date": review.get("next_one_month_evaluation_date", ""),
        "next_one_month_evaluation_count": _as_int(
            review.get("next_one_month_evaluation_count"),
        )
        or 0,
        "markets": markets,
    }


def _one_week_forecast_shadow_disposition_snapshot(project_root):
    path = (
        Path(project_root)
        / "outputs"
        / "automation"
        / "latest_one_week_forecast_shadow_disposition.json"
    )
    payload = _read_json(path)
    if payload.get("disposition_schema") != "one_week_forecast_shadow_disposition":
        return {
            "status": "missing",
            "recommended_action": "repair_shadow_disposition_inputs",
            "disposition_counts": {
                "continue_observation": 0,
                "rejected": 0,
                "pending_human_approval": 0,
            },
            "candidate_dispositions": [],
            "next_one_week_evaluation_date": "",
            "next_one_week_evaluation_count": 0,
            "formal_model_change_allowed": False,
            "path": str(path),
        }
    snapshot = dict(payload)
    snapshot["path"] = str(path)
    if payload.get("formal_model_change_allowed") is True or payload.get("status") != "ready":
        snapshot["status"] = "needs_attention"
        snapshot["recommended_action"] = "repair_shadow_disposition_inputs"
    snapshot.setdefault("disposition_counts", {})
    snapshot.setdefault("candidate_dispositions", [])
    snapshot.setdefault("next_one_week_evaluation_date", "")
    snapshot.setdefault("next_one_week_evaluation_count", 0)
    snapshot.setdefault("formal_model_change_allowed", False)
    return snapshot


def _first_one_month_forecast_evaluation_snapshot(project_root):
    path = (
        Path(project_root)
        / "outputs"
        / "automation"
        / "latest_first_one_month_forecast_evaluation_review.json"
    )
    payload = _read_json(path)
    if payload.get("review_schema") != "first_one_month_forecast_evaluation_review":
        return {
            "status": "missing",
            "expected_sample_count": 37,
            "actual_sample_count": 0,
            "one_week_valid_count": 0,
            "one_month_valid_count": 0,
            "recommended_action": "repair_first_one_month_review_inputs",
            "formal_model_change_allowed": False,
            "formal_model_conclusion_allowed": False,
            "path": str(path),
        }
    cohort = payload.get("cohort", {}) or {}
    one_week = payload.get("one_week", {}) or {}
    one_month = payload.get("one_month", {}) or {}
    comparison = payload.get("market_comparison", {}) or {}
    return {
        "status": payload.get("status", "missing"),
        "as_of_date": payload.get("as_of_date", ""),
        "expected_sample_count": _as_int(cohort.get("expected_sample_count")) or 37,
        "actual_sample_count": _as_int(cohort.get("actual_sample_count")) or 0,
        "one_week_valid_count": _as_int(one_week.get("valid_evaluation_count")) or 0,
        "one_week_direction_hit_rate": one_week.get("direction_hit_rate"),
        "one_week_average_excess_return": one_week.get("average_excess_return"),
        "one_week_failure_type_counts": one_week.get("failure_type_counts", {}),
        "one_month_valid_count": _as_int(one_month.get("valid_evaluation_count")) or 0,
        "one_month_direction_hit_rate": one_month.get("direction_hit_rate"),
        "one_month_average_excess_return": one_month.get("average_excess_return"),
        "one_month_failure_type_counts": one_month.get("failure_type_counts", {}),
        "market_comparison_status": comparison.get("status", "missing"),
        "recommended_action": payload.get(
            "recommended_action", "repair_first_one_month_review_inputs"
        ),
        "formal_model_change_allowed": bool(payload.get("formal_model_change_allowed")),
        "formal_model_conclusion_allowed": bool(
            payload.get("formal_model_conclusion_allowed")
        ),
        "path": str(path),
    }


def _first_one_month_priority_action(snapshot):
    if snapshot.get("status") == "awaiting_maturity":
        return ""
    if snapshot.get("status") in {"sample_incomplete", "needs_attention", "review_ready"}:
        return snapshot.get("recommended_action", "")
    return ""


def _format_rate(value):
    return "unknown" if value is None else f"{value:.2%}"


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
            "quote_data_coverage": "unknown",
            "quote_data_coverage_number": None,
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
    quote_coverage_number = _as_float(row.get("quote_coverage_pct"))
    quote_total = _as_int(row.get("quote_total")) or 0
    if quote_coverage_number is None:
        quote_data_coverage_number = None
    elif quote_total > 0:
        review_coverage = quote_gap_summary["review"] / quote_total * 100
        quote_data_coverage_number = min(100.0, quote_coverage_number + review_coverage)
    else:
        quote_data_coverage_number = quote_coverage_number
    return {
        "name": market["name"],
        "status": "ready",
        "refresh_status": row.get("refresh_status") or "n/a",
        "quote_coverage": _percent(row.get("quote_coverage_pct")),
        "quote_coverage_number": quote_coverage_number,
        "quote_data_coverage": _percent(quote_data_coverage_number),
        "quote_data_coverage_number": quote_data_coverage_number,
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
        quote_coverage = item.get("quote_data_coverage_number")
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

DATA_QUALITY_HISTORY_FIELDNAMES = [
    "as_of_date",
    "market",
    "quality_score",
    "quality_status",
    "reasons",
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


def _manual_review_decision_key(market, review_type, ticker):
    market = (market or "").strip()
    review_type = (review_type or "").strip()
    ticker = (ticker or "").strip().upper()
    if not (market and review_type and ticker):
        return None
    return (market, review_type, ticker)


def _closed_manual_review_decision_keys(path):
    closed = set()
    for row in _read_csv_rows(path):
        status = (row.get("decision_status") or "").strip().lower()
        if status not in CLOSED_MANUAL_REVIEW_STATUSES:
            continue
        key = _manual_review_decision_key(
            row.get("market"),
            row.get("review_type"),
            row.get("ticker"),
        )
        if key:
            closed.add(key)
    return closed


def _filter_closed_manual_review_queue(queue, closed_keys):
    if not closed_keys:
        return queue
    filtered = []
    for item in queue:
        key = _manual_review_decision_key(
            item.get("name"),
            item.get("type"),
            item.get("ticker"),
        )
        if key in closed_keys:
            continue
        next_item = dict(item)
        next_item["rank"] = len(filtered) + 1
        filtered.append(next_item)
    return filtered


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


def _data_quality_history_rows(data_quality_summary, as_of_date):
    rows = []
    for item in data_quality_summary.get("markets", []) or []:
        rows.append(
            {
                "as_of_date": as_of_date,
                "market": item.get("name", ""),
                "quality_score": item.get("quality_score", 0),
                "quality_status": item.get("quality_status", "unknown"),
                "reasons": ";".join(item.get("reasons", []) or []),
            }
        )
    return rows


def _write_data_quality_history(path, data_quality_summary, as_of_date):
    current_rows = _data_quality_history_rows(data_quality_summary, as_of_date)
    existing_rows = [
        row for row in _read_csv_rows(path)
        if row.get("as_of_date") != as_of_date
    ]
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=DATA_QUALITY_HISTORY_FIELDNAMES)
        writer.writeheader()
        for row in existing_rows + current_rows:
            writer.writerow({field: row.get(field, "") for field in DATA_QUALITY_HISTORY_FIELDNAMES})


def _data_quality_history_summary(path, data_quality_summary, as_of_date, window=4):
    rows = [
        row for row in _read_csv_rows(path)
        if row.get("as_of_date") != as_of_date
    ] + _data_quality_history_rows(data_quality_summary, as_of_date)
    if not rows:
        return {
            "history_schema": "data_quality_history_summary",
            "history_version": 1,
            "status": "missing",
            "recommended_action": "collect_data_quality_history",
            "history_count": 0,
            "window_size": 0,
            "repeated_needs_review_markets": [],
            "score_decline_markets": [],
            "recovered_markets": [],
            "markets": [],
            "path": str(path),
        }
    by_market = {}
    for row in rows:
        market = row.get("market", "")
        if not market:
            continue
        by_market.setdefault(market, []).append(row)
    market_summaries = []
    repeated = []
    declining = []
    recovered = []
    for market, market_rows in sorted(by_market.items()):
        market_rows = sorted(market_rows, key=lambda row: row.get("as_of_date", ""))[-window:]
        current = market_rows[-1]
        previous = market_rows[-2] if len(market_rows) >= 2 else None
        current_score = _as_float(current.get("quality_score")) or 0
        previous_score = _as_float(previous.get("quality_score")) if previous else None
        delta = None if previous_score is None else round(current_score - previous_score, 2)
        needs_review_count = sum(
            1 for row in market_rows
            if row.get("quality_status") == "needs_review"
        )
        current_status = current.get("quality_status", "unknown")
        if needs_review_count >= 2 and current_status == "needs_review":
            repeated.append(market)
        elif needs_review_count >= 2 and current_status == "ready":
            recovered.append(market)
        if delta is not None and delta <= -10:
            declining.append(market)
        market_summaries.append(
            {
                "market": market,
                "latest_score": current_score,
                "latest_status": current_status,
                "previous_score": previous_score,
                "score_delta": delta,
                "needs_review_count": needs_review_count,
                "window_count": len(market_rows),
            }
        )
    if repeated or declining:
        status = "manual_review_needed"
        action = "review_data_quality_trend"
    elif len({row.get("as_of_date", "") for row in rows}) < 2:
        status = "collecting"
        action = "collect_data_quality_history"
    else:
        status = "clear"
        action = "monitor_next_run"
    return {
        "history_schema": "data_quality_history_summary",
        "history_version": 1,
        "status": status,
        "recommended_action": action,
        "history_count": len(rows),
        "window_size": window,
        "repeated_needs_review_markets": repeated,
        "score_decline_markets": declining,
        "recovered_markets": recovered,
        "markets": market_summaries,
        "path": str(path),
    }


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


def _automation_external_input_blockers(manifest):
    if not manifest.get("sp500_current_source_inbox_external_input_required"):
        return []
    blocking_input = str(manifest.get("sp500_current_source_inbox_blocking_input", "") or "")
    blocking_reason = str(manifest.get("sp500_current_source_inbox_blocking_reason", "") or "")
    if not blocking_input and not blocking_reason:
        return []
    return [
        {
            "action_code": "provide_official_constituents_csv",
            "blocking_input": blocking_input,
            "blocking_reason": blocking_reason,
            "next_action": "place_official_constituents_csv",
            "dry_run_command": str(manifest.get("sp500_current_source_inbox_dry_run_command", "") or ""),
            "import_command": str(manifest.get("sp500_current_source_inbox_import_command", "") or ""),
        }
    ]


def _sp500_current_source_inbox_status_summary(project_root):
    status = _read_json(Path(project_root) / SP500_CURRENT_MEMBERSHIP_SOURCE_INBOX_STATUS_PATH)
    if not status:
        return {}
    return {
        "sp500_current_source_inbox_external_input_required": bool(
            status.get("external_input_required")
        ),
        "sp500_current_source_inbox_size_bytes": int(
            status.get("source_file_inbox_size_bytes") or 0
        ),
        "sp500_current_source_inbox_sha256": status.get("source_file_inbox_sha256", ""),
        "sp500_current_source_inbox_modified_at": status.get("source_file_inbox_modified_at", ""),
        "sp500_current_source_inbox_blocking_reason": status.get("blocking_reason", ""),
        "sp500_current_source_inbox_blocking_input": status.get("blocking_input", ""),
        "sp500_current_source_inbox_dry_run_command": status.get(
            "source_file_inbox_dry_run_command",
            "",
        ),
        "sp500_current_source_inbox_import_command": status.get(
            "source_file_inbox_next_command",
            "",
        ),
    }


def _automation_check_payload(manifest, manifest_validation):
    external_input_blockers = _automation_external_input_blockers(manifest)
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
        "data_quality_status": manifest.get("data_quality_status", "unknown"),
        "data_quality_score": manifest.get("data_quality_score", 0),
        "data_quality_history_status": manifest.get("data_quality_history_status", "unknown"),
        "candidate_review_status": manifest.get("candidate_review_status", "unknown"),
        "weekly_ops_history_status": manifest.get("weekly_ops_history_status", "unknown"),
        "weekly_delivery_history_status": manifest.get("weekly_delivery_history_status", "unknown"),
        "weekly_delivery_action_items_actual_count": manifest.get(
            "weekly_delivery_action_items_actual_count", 0
        ),
        "weekly_delivery_action_items_actual_count_delta": manifest.get(
            "weekly_delivery_action_items_actual_count_delta", 0
        ),
        "weekly_delivery_action_items_actual_count_trend": manifest.get(
            "weekly_delivery_action_items_actual_count_trend", "unknown"
        ),
        "model_audit_status": manifest.get("model_audit_status", "unknown"),
        "forecast_performance_status": manifest.get("forecast_performance_status", "unknown"),
        "forecast_next_one_week_evaluation_date": (
            manifest.get("forecast_performance", {}).get("next_one_week_evaluation_date", "")
        ),
        "forecast_next_one_week_evaluation_count": (
            manifest.get("forecast_performance", {}).get("next_one_week_evaluation_count", 0)
        ),
        "forecast_next_one_month_evaluation_date": (
            manifest.get("forecast_performance", {}).get("next_one_month_evaluation_date", "")
        ),
        "forecast_next_one_month_evaluation_count": (
            manifest.get("forecast_performance", {}).get("next_one_month_evaluation_count", 0)
        ),
        "external_input_blocker_count": len(external_input_blockers),
        "external_input_blockers": external_input_blockers,
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
            "quote_data_coverage": item.get("quote_data_coverage", ""),
            "quote_data_coverage_number": item.get("quote_data_coverage_number"),
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


def _coverage_penalty(value, threshold=95.0, multiplier=2.0, cap=30):
    if value is None:
        return 0
    if value >= threshold:
        return 0
    return min(cap, int(round((threshold - value) * multiplier)))


def _quality_status(score):
    if score >= 90:
        return "ready"
    if score >= 70:
        return "watch"
    return "needs_review"


def _market_data_quality(item):
    score = 100
    reasons = []
    if item.get("status") != "ready":
        return {
            "name": item.get("name", ""),
            "quality_score": 0,
            "quality_status": "needs_review",
            "recommended_action": "restore_data_health_snapshot",
            "reasons": ["data_health_missing"],
            "path": item.get("path", ""),
        }

    refresh_status = item.get("refresh_status", "unknown")
    if refresh_status not in {"online", "n/a", "unknown"}:
        score -= 15
        reasons.append(f"refresh_status:{refresh_status}")

    quote_penalty = _coverage_penalty(item.get("quote_data_coverage_number"))
    if quote_penalty:
        score -= quote_penalty
        reasons.append(f"quote_data_coverage:{item.get('quote_data_coverage', 'unknown')}")

    financial_penalty = _coverage_penalty(item.get("financial_coverage_number"))
    if financial_penalty:
        score -= financial_penalty
        reasons.append(f"financial_coverage:{item.get('financial_coverage', 'unknown')}")

    refetch = _as_int(item.get("quote_gap_refetch_count")) or 0
    if refetch > 0:
        score -= min(15, refetch * 3)
        reasons.append(f"quote_refetch_gap:{refetch}")

    blocked = _as_int(item.get("data_quality_blocked")) or 0
    if blocked > 0:
        score -= 20
        reasons.append(f"data_quality_blocked:{blocked}")

    affected = _as_int(item.get("affected_candidate_count")) or 0
    if affected > 0:
        score -= min(20, affected * 5)
        reasons.append(f"affected_candidate_count:{affected}")

    override_review = _as_int(item.get("share_override_review")) or 0
    if override_review > 0:
        score -= min(10, override_review * 5)
        reasons.append(f"share_override_review:{override_review}")

    score = max(0, min(100, score))
    status = _quality_status(score)
    if status == "needs_review":
        action = "review_data_quality_score"
    elif status == "watch":
        action = "monitor_data_quality_drift"
    else:
        action = "monitor_next_run"
    return {
        "name": item.get("name", ""),
        "quality_score": score,
        "quality_status": status,
        "recommended_action": action,
        "reasons": reasons or ["clear"],
        "path": item.get("path", ""),
    }


def _data_quality_summary(health):
    markets = [_market_data_quality(item) for item in health]
    if not markets:
        return {
            "summary_schema": "data_quality_summary",
            "summary_version": 1,
            "status": "missing",
            "average_score": 0,
            "recommended_action": "collect_data_quality_inputs",
            "markets": [],
        }
    average_score = round(sum(item["quality_score"] for item in markets) / len(markets), 2)
    statuses = [item["quality_status"] for item in markets]
    if "needs_review" in statuses:
        status = "needs_review"
        action = "review_data_quality_score"
    elif "watch" in statuses:
        status = "watch"
        action = "monitor_data_quality_drift"
    else:
        status = "ready"
        action = "monitor_next_run"
    return {
        "summary_schema": "data_quality_summary",
        "summary_version": 1,
        "status": status,
        "average_score": average_score,
        "recommended_action": action,
        "markets": markets,
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
    if backtest.get("evidence_status") == "evidence_ceiling_confirmed":
        status = "evidence_ceiling_confirmed"
        action = "maintain_limited_backtest"
    elif backtest.get("status") != "ready":
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
        "backtest_mode": backtest.get("backtest_mode", ""),
        "backtest_unresolved_gap_count": _as_int(backtest.get("unresolved_gap_count")),
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
    missing_signals = list(weekly_delivery_history.get("latest_missing_conclusion_signals", []))
    missing_signals.extend(
        item.get("signal", "")
        for item in weekly_delivery_history.get("recurring_missing_conclusion_signals", [])
        if item.get("signal", "")
    )
    priority_actions = []
    if any(str(reason).startswith("manual_review_pending:") for reason in reasons):
        priority_actions.append("review_manual_review_backlog")
    if any(not str(reason).startswith("manual_review_pending:") for reason in reasons) or missing_signals:
        priority_actions.append("review_delivery_health_issues")
    if (
        weekly_delivery_history.get("action_items_actual_count_trend") == "increasing"
        and (_as_int(weekly_delivery_history.get("action_items_actual_count_delta")) or 0) > 0
    ):
        priority_actions.append("reduce_weekly_action_backlog")
    return priority_actions


def _manifest_weekly_delivery_history_status(weekly_delivery_history):
    action = weekly_delivery_history.get("recommended_action", "collect_weekly_delivery_history")
    health_actions = _weekly_delivery_health_priority_actions(weekly_delivery_history)
    if health_actions:
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
    forecast_performance,
    data_health_status,
    data_quality_summary,
    data_quality_history,
    candidate_review_status,
    weekly_ops_history_status,
    weekly_delivery_history_status,
    review_status,
    recommended_next_action,
):
    action_candidates = [
        (review_status, recommended_next_action),
        (data_health_status["data_health_status"], data_health_status["data_health_recommended_action"]),
    ]
    data_quality_status = data_quality_summary.get("status", "unknown")
    if data_quality_status not in {"ready", "watch"}:
        action_candidates.append(
            (
                data_quality_status,
                data_quality_summary.get("recommended_action", "review_data_quality_score"),
            )
        )
    if data_quality_history.get("status") == "manual_review_needed":
        action_candidates.append(
            (
                data_quality_history.get("status", "unknown"),
                data_quality_history.get("recommended_action", "review_data_quality_trend"),
            )
        )
    action_candidates.extend(
        [
            (backtest_status["backtest_status"], backtest_status["backtest_recommended_action"]),
            (forecast_performance["status"], forecast_performance["recommended_action"]),
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
    )
    for action in weekly_delivery_history_status.get("weekly_delivery_history_priority_actions", []):
        action_candidates.append(("manual_review_needed", action))
    priority_actions = []
    for status, action in action_candidates:
        if (
            status in {"clear", "missing", "ready", "evidence_ceiling_confirmed"}
            or action in {"", "none", "monitor_next_run", "maintain_limited_backtest"}
            or action in priority_actions
        ):
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


def _recommendations(risks, backtest, manual_queue=None):
    recommendations = []
    manual_queue = manual_queue or []
    if any(risk.startswith("缺失摘要") for risk in risks) or "缺失严格时点回测摘要" in risks:
        recommendations.append("先补齐缺失的周筛或回测摘要，再做模型参数判断。")
    if any(risk.startswith("数据健康") for risk in risks):
        recommendations.append("数据健康异常先人工复核，不自动修改正式模型参数。")
    if any("候选需复核" in risk or "风险需复核" in risk for risk in risks):
        recommendations.append("优先复核候选风险和结论缺口，不自动调整正式模型参数。")
    if any(risk.startswith("估值复核待确认") or "估值口径复核" in risk for risk in risks) or any(
        item.get("type") == "估值口径" for item in manual_queue
    ):
        recommendations.append("优先人工复核估值复核清单，确认亏损、非正净资产或特殊行业估值口径后再解读候选缺口。")
    if (
        _as_int(backtest.get("weak_rows"))
        and backtest.get("evidence_status") != "evidence_ceiling_confirmed"
    ):
        recommendations.append("继续补充历史成分 verified 证据，降低严格时点回测的数据质量风险。")
    if backtest.get("evidence_status") == "evidence_ceiling_confirmed":
        recommendations.append("证据上限已确认，维持受限回测且不得扩大正式回测样本。")
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
    forecast_performance=None,
    data_quality_summary=None,
    data_quality_history=None,
    manual_review_history_repeats=None,
    manual_review_queue=None,
    weekly_ops_history=None,
    weekly_delivery_history=None,
):
    risks = _risks(markets, backtest, health) + _candidate_review_risks(candidate_reviews)
    manual_queue = manual_review_queue if manual_review_queue is not None else _manual_review_queue(health, candidate_reviews)
    recommendations = _recommendations(risks, backtest, manual_queue)
    manual_review_history_repeats = manual_review_history_repeats or []
    weekly_ops_history = weekly_ops_history or {}
    weekly_delivery_history = weekly_delivery_history or {}
    data_quality_summary = data_quality_summary or _data_quality_summary(health)
    data_quality_history = data_quality_history or {}
    forecast_performance = forecast_performance or {
        "status": "unknown",
        "recommended_action": "collect_forecast_evaluations",
        "total_evaluations": 0,
        "mature_evaluations": 0,
        "one_week_mature": 0,
        "one_month_mature": 0,
        "prediction_unavailable": 0,
        "missing_market_count": 0,
        "direction_hit_rate": None,
        "markets": [],
    }
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
            "| 模块 | 状态 | 刷新状态 | 行情字段完整率 | 估值质量门通过率 | 财务覆盖 | 行情缺口 | 可重抓 | 需复核 | 候选数 |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in health:
        lines.append(
            f"| {item['name']} | {item['status']} | {item['refresh_status']} | "
            f"{item['quote_data_coverage']} | {item['quote_coverage']} | "
            f"{item['financial_coverage']} | "
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
            "## 数据质量评分",
            "",
            f"- status: {data_quality_summary.get('status', 'unknown')}",
            f"- average_score: {data_quality_summary.get('average_score', 0)}",
            f"- recommended_action: {data_quality_summary.get('recommended_action', 'unknown')}",
            "",
            "| 模块 | 评分 | 状态 | 原因 |",
            "|---|---:|---|---|",
        ]
    )
    for item in data_quality_summary.get("markets", []):
        reasons = "; ".join(item.get("reasons", [])) or "clear"
        lines.append(
            f"| {item.get('name', '')} | {item.get('quality_score', 0)} | "
            f"{item.get('quality_status', '')} | {reasons} |"
        )
    repeated_text = "、".join(data_quality_history.get("repeated_needs_review_markets", [])) or "none"
    declining_text = "、".join(data_quality_history.get("score_decline_markets", [])) or "none"
    recovered_text = "、".join(data_quality_history.get("recovered_markets", [])) or "none"
    lines.extend(
        [
            "",
            "## 数据质量历史",
            "",
            f"- status: {data_quality_history.get('status', 'unknown')}",
            f"- recommended_action: {data_quality_history.get('recommended_action', 'unknown')}",
            f"- repeated_needs_review_markets: {repeated_text}",
            f"- score_decline_markets: {declining_text}",
            f"- recovered_markets: {recovered_text}",
            f"- history_path: {data_quality_history.get('path', '')}",
            "",
            "| 模块 | 最新评分 | 最新状态 | 上次评分 | 变化 | needs_review次数 |",
            "|---|---:|---|---:|---:|---:|",
        ]
    )
    for item in data_quality_history.get("markets", []):
        previous = item.get("previous_score")
        delta = item.get("score_delta")
        lines.append(
            f"| {item.get('market', '')} | {item.get('latest_score', 0)} | "
            f"{item.get('latest_status', '')} | {previous if previous is not None else 'n/a'} | "
            f"{delta if delta is not None else 'n/a'} | {item.get('needs_review_count', 0)} |"
        )
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
    lines.extend(
        [
            "",
            "## 预测表现",
            "",
            f"- status: {forecast_performance.get('status', 'unknown')}",
            f"- recommended_action: {forecast_performance.get('recommended_action', 'unknown')}",
            f"- total_evaluations: {forecast_performance.get('total_evaluations', 0)}",
            f"- mature_evaluations: {forecast_performance.get('mature_evaluations', 0)}",
            f"- one_week_mature: {forecast_performance.get('one_week_mature', 0)}",
            f"- one_month_mature: {forecast_performance.get('one_month_mature', 0)}",
            f"- prediction_unavailable: {forecast_performance.get('prediction_unavailable', 0)}",
            f"- missing_market_count: {forecast_performance.get('missing_market_count', 0)}",
            f"- direction_hit_rate: {_format_rate(forecast_performance.get('direction_hit_rate'))}",
            f"- next_one_week_evaluation_date: {forecast_performance.get('next_one_week_evaluation_date', '') or 'unknown'}",
            f"- next_one_week_evaluation_count: {forecast_performance.get('next_one_week_evaluation_count', 0)}",
            f"- next_one_month_evaluation_date: {forecast_performance.get('next_one_month_evaluation_date', '') or 'unknown'}",
            f"- next_one_month_evaluation_count: {forecast_performance.get('next_one_month_evaluation_count', 0)}",
            "",
            "| 模块 | 状态 | 总评估 | 成熟评估 | 1w | 1m | prediction_unavailable | 方向命中率 |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in forecast_performance.get("markets", []):
        lines.append(
            f"| {item.get('name', '')} | {item.get('status', '')} | "
            f"{item.get('total_evaluations', 0)} | {item.get('mature_evaluations', 0)} | "
            f"{item.get('one_week_mature', 0)} | {item.get('one_month_mature', 0)} | "
            f"{item.get('prediction_unavailable', 0)} | {_format_rate(item.get('direction_hit_rate'))} |"
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
    delivery_latest_missing_signals = weekly_delivery_history.get("latest_missing_conclusion_signals", [])
    delivery_latest_missing_signal_text = (
        ", ".join(str(signal) for signal in delivery_latest_missing_signals)
        if delivery_latest_missing_signals
        else "none"
    )
    delivery_recurring_missing_signals = weekly_delivery_history.get("recurring_missing_conclusion_signals", [])
    delivery_recurring_missing_signal_text = (
        ", ".join(
            f"{item.get('signal', '')} ({item.get('count', 0)})"
            for item in delivery_recurring_missing_signals
        )
        if delivery_recurring_missing_signals
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
            f"- latest_action_items_actual_count: {weekly_delivery_history.get('latest_action_items_actual_count', 0)}",
            f"- max_action_items_actual_count: {weekly_delivery_history.get('max_action_items_actual_count', 0)}",
            f"- action_items_actual_count_delta: {weekly_delivery_history.get('action_items_actual_count_delta', 0)}",
            f"- action_items_actual_count_trend: {weekly_delivery_history.get('action_items_actual_count_trend', 'unknown')}",
            f"- latest_conclusion_health: {weekly_delivery_history.get('latest_conclusion_health_status', 'unknown')} / {weekly_delivery_history.get('latest_conclusion_health_score', 0)}",
            f"- recurring_health_reasons: {delivery_health_text}",
            f"- latest_conclusion_signal_status: {weekly_delivery_history.get('latest_conclusion_signal_status', 'unknown')}",
            f"- latest_missing_conclusion_signals: {delivery_latest_missing_signal_text}",
            f"- recurring_missing_conclusion_signals: {delivery_recurring_missing_signal_text}",
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
    forecast_performance = _forecast_performance_snapshot(project_root)
    first_one_month_evaluation = _first_one_month_forecast_evaluation_snapshot(project_root)
    shadow_disposition = _one_week_forecast_shadow_disposition_snapshot(project_root)
    if forecast_performance.get("status") == "performance_review_needed":
        forecast_performance = dict(forecast_performance)
        forecast_performance["recommended_action"] = shadow_disposition.get(
            "recommended_action",
            "repair_shadow_disposition_inputs",
        )
    sp500_current_source_inbox_status = _sp500_current_source_inbox_status_summary(project_root)
    data_quality_summary = _data_quality_summary(health)
    weekly_ops_history = _weekly_ops_history_snapshot(project_root)
    weekly_delivery_history = _weekly_delivery_history_snapshot(project_root)
    manual_review_queue = _manual_review_queue(health, candidate_reviews)
    closed_manual_review_keys = _closed_manual_review_decision_keys(
        project_root / MANUAL_REVIEW_DECISIONS_PATH
    )
    manual_review_queue = _filter_closed_manual_review_queue(
        manual_review_queue,
        closed_manual_review_keys,
    )
    manual_review_queue_output = output.parent / "latest_manual_review_queue.csv"
    manual_review_history_output = output.parent / "manual_review_queue_history.csv"
    manual_review_repeats_output = output.parent / "manual_review_repeats.csv"
    data_quality_history_output = output.parent / "data_quality_score_history.csv"
    manifest_output = output.parent / "latest_self_analysis_manifest.json"
    automation_check_output = output.parent / "latest_automation_check.json"
    data_quality_history = _data_quality_history_summary(
        data_quality_history_output,
        data_quality_summary,
        as_of_date,
    )
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
            forecast_performance,
            data_quality_summary,
            data_quality_history,
            manual_review_history_repeats,
            manual_review_queue,
            weekly_ops_history,
            weekly_delivery_history,
        ),
        encoding="utf-8-sig",
    )
    _write_manual_review_queue(manual_review_queue_output, manual_review_queue, as_of_date)
    _write_manual_review_repeats(manual_review_repeats_output, manual_review_history_repeats, as_of_date)
    _write_manual_review_history(manual_review_history_output, manual_review_queue, as_of_date)
    _write_data_quality_history(data_quality_history_output, data_quality_summary, as_of_date)
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
        "forecast_performance": forecast_performance,
        "forecast_performance_status": forecast_performance.get("status", "unknown"),
        "forecast_performance_recommended_action": forecast_performance.get("recommended_action", "unknown"),
        "first_one_month_forecast_evaluation": first_one_month_evaluation,
        "one_week_forecast_shadow_disposition": shadow_disposition,
        "health": _manifest_health(health),
        **data_health_status,
        "data_quality_summary": data_quality_summary,
        "data_quality_status": data_quality_summary.get("status", "unknown"),
        "data_quality_score": data_quality_summary.get("average_score", 0),
        "data_quality_recommended_action": data_quality_summary.get("recommended_action", "unknown"),
        "data_quality_history": data_quality_history,
        "data_quality_history_status": data_quality_history.get("status", "unknown"),
        "data_quality_history_recommended_action": data_quality_history.get("recommended_action", "unknown"),
        **candidate_review_status,
        **sp500_current_source_inbox_status,
        "weekly_ops_history": weekly_ops_history,
        **weekly_ops_history_status,
        "weekly_delivery_history": weekly_delivery_history,
        **weekly_delivery_history_status,
        "weekly_delivery_action_items_actual_count": weekly_delivery_history.get(
            "latest_action_items_actual_count", 0
        ),
        "weekly_delivery_action_items_actual_count_delta": weekly_delivery_history.get(
            "action_items_actual_count_delta", 0
        ),
        "weekly_delivery_action_items_actual_count_trend": weekly_delivery_history.get(
            "action_items_actual_count_trend", "unknown"
        ),
        "manual_review_queue_count": len(manual_review_queue),
        "manual_review_repeat_count": len(manual_review_history_repeats),
        "review_status": review_status,
        "recommended_next_action": recommended_next_action,
        **_manifest_automation_decision(
            model_audit_status,
            backtest_status,
            forecast_performance,
            data_health_status,
            data_quality_summary,
            data_quality_history,
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
            "data_quality_history": str(data_quality_history_output),
            "one_week_forecast_shadow_disposition": shadow_disposition.get("path", ""),
            "first_one_month_forecast_evaluation": first_one_month_evaluation.get("path", ""),
        },
    }
    first_month_action = _first_one_month_priority_action(first_one_month_evaluation)
    if first_month_action:
        priority_actions = manifest.setdefault("automation_priority_actions", [])
        if first_month_action not in priority_actions:
            priority_actions.append(first_month_action)
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
        "data_quality_history_output": str(data_quality_history_output),
        "manifest_output": str(manifest_output),
        "automation_check_output": str(automation_check_output),
        "markets": markets,
        "backtest": backtest,
        "forecast_performance": forecast_performance,
        "first_one_month_forecast_evaluation": first_one_month_evaluation,
        "one_week_forecast_shadow_disposition": shadow_disposition,
        "data_quality_summary": data_quality_summary,
        "data_quality_history": data_quality_history,
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
    "forecast_performance",
    "forecast_performance_status",
    "forecast_performance_recommended_action",
    "one_week_forecast_shadow_disposition",
    "health",
    "data_health_status",
    "data_health_recommended_action",
    "data_quality_summary",
    "data_quality_status",
    "data_quality_score",
    "data_quality_recommended_action",
    "data_quality_history",
    "data_quality_history_status",
    "data_quality_history_recommended_action",
    "candidate_review_status",
    "candidate_review_recommended_action",
    "weekly_ops_history",
    "weekly_ops_history_status",
    "weekly_ops_history_recommended_action",
    "weekly_delivery_history",
    "weekly_delivery_history_status",
    "weekly_delivery_history_recommended_action",
    "weekly_delivery_action_items_actual_count",
    "weekly_delivery_action_items_actual_count_delta",
    "weekly_delivery_action_items_actual_count_trend",
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
