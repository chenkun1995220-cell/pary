from __future__ import annotations

import csv
import math
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from candidate_valuation import MODEL_VERSION, TARGET_FIELDS, run_candidate_valuation
from forecast_tracker import CHECKPOINTS, evaluate_forecast
from historical_price_store import price_coverage, prices_available_as_of
from industry_medians import apply_industry_medians, calculate_industry_medians, median_rows
from sec_point_in_time import calculate_metrics_as_of
from stock_screener import apply_data_quality_block, score_stock, to_float


BACKTEST_FORECAST_FIELDS = TARGET_FIELDS + [
    "input_available_at_max",
    "week_eligible",
    "config_digest",
]

AUDIT_FIELDS = [
    "record_type",
    "source",
    "market",
    "ticker",
    "company_name",
    "industry",
    "cik",
    "available_at",
    "generated_date",
    "severity",
    "reason",
]


def assess_week_quality(
    membership_evidence,
    quote_coverage,
    financial_coverage,
    benchmark_ready,
    leakage_errors,
):
    reasons = []
    if membership_evidence != "verified":
        reasons.append("membership_not_verified")
    if quote_coverage < 0.95:
        reasons.append("quote_coverage_below_95pct")
    if financial_coverage < 0.80:
        reasons.append("financial_coverage_below_80pct")
    if not benchmark_ready:
        reasons.append("benchmark_missing")
    if leakage_errors:
        reasons.append("data_leakage_detected")
    return {"eligible": not reasons, "reasons": reasons}


def leakage_findings(records, generated_date):
    findings = []
    generated_text = str(generated_date)
    for row in records or []:
        if row.get("severity") not in ("", "severe", None):
            continue
        available_at = str(row.get("available_at", ""))
        if available_at and _is_after(available_at, generated_text):
            findings.append(
                {
                    "generated_date": generated_text,
                    "ticker": str(row.get("ticker", "")),
                    "severity": "severe",
                    "available_at": available_at,
                    "reason": "future_data_used",
                }
            )
    return findings


def evaluate_backtest_forecast(forecast, stock_rows, benchmark_rows):
    rows = []
    generated = date.fromisoformat(_as_text(forecast.get("generated_date")))
    for weeks, days in CHECKPOINTS.items():
        as_of_date = (generated + timedelta(days=days)).isoformat()
        row = evaluate_forecast(forecast, stock_rows, benchmark_rows, as_of_date, weeks)
        row["backtest_eligible"] = _as_text(forecast.get("week_eligible", "false"))
        rows.append(row)
    return rows


def _as_text(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def _temporal_key(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        current = value.astimezone(timezone.utc) if value.tzinfo else value
        return current.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00") if text.endswith("Z") else text
    try:
        if "T" not in text and " " not in text:
            parsed_date = date.fromisoformat(text)
            return datetime(parsed_date.year, parsed_date.month, parsed_date.day)
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    except ValueError:
        return None


def _is_after(value, cutoff):
    value_key = _temporal_key(value)
    cutoff_key = _temporal_key(cutoff)
    if value_key is None or cutoff_key is None:
        return False
    return value_key.date() > cutoff_key.date()


def _max_temporal_value(values):
    best_value = ""
    best_key = None
    for value in values:
        text = _as_text(value)
        if not text:
            continue
        key = _temporal_key(text)
        if key is None:
            continue
        if best_key is None or key > best_key:
            best_value = text
            best_key = key
    return best_value


def _read_csv(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _atomic_write_csv(path, rows, fieldnames=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    inferred = list(fieldnames or [])
    if not inferred:
        for row in rows:
            for key in row:
                if key not in inferred:
                    inferred.append(key)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8-sig",
            newline="",
            delete=False,
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
        ) as handle:
            temporary = Path(handle.name)
            if inferred:
                writer = csv.DictWriter(handle, fieldnames=inferred, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
            else:
                handle.write("")
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def _atomic_write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            delete=False,
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
        ) as handle:
            temporary = Path(handle.name)
            handle.write(text)
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def _market_key(row):
    return (str(row.get("market", "")).strip(), str(row.get("ticker", "")).strip().upper())


def _available_membership_rows(membership_rows, backtest_date_text):
    available = []
    future_rows = []
    for row in membership_rows or []:
        available_at = _as_text(row.get("available_at"))
        if available_at and _is_after(available_at, backtest_date_text):
            future_rows.append(dict(row, available_at=available_at))
            continue
        available.append(dict(row, available_at=available_at))

    deduped = {}
    for row in available:
        key = _market_key(row)
        current = deduped.get(key)
        row_key = _temporal_key(row.get("available_at"))
        current_key = _temporal_key(current.get("available_at")) if current else None
        if current is None or (row_key is not None and (current_key is None or row_key >= current_key)):
            deduped[key] = row
    return list(deduped.values()), future_rows


def _normalize_price_rows(rows):
    normalized = []
    for row in rows or []:
        price = to_float(row.get("close"))
        if price is None:
            price = to_float(row.get("adjusted_close"))
        if price is None:
            price = to_float(row.get("price"))
        out = dict(row)
        if price is not None:
            out["price"] = price
            if not str(out.get("data_status", "")).strip():
                out["data_status"] = "ready"
        normalized.append(out)
    return normalized


def _latest_rows_by_ticker(rows):
    latest = {}
    for row in rows or []:
        ticker = str(row.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        row_date = _temporal_key(row.get("date") or row.get("quote_date"))
        if row_date is None:
            continue
        current = latest.get(ticker)
        current_date = _temporal_key(current.get("date") or current.get("quote_date")) if current else None
        if current is None or row_date >= current_date:
            latest[ticker] = dict(row)
    return latest


def _availability_text(row):
    return _as_text(row.get("available_at") or row.get("quote_date") or row.get("date"))


def _split_rows_by_availability(rows, backtest_date_text):
    available_rows = []
    late_rows = []
    for row in rows or []:
        available_at = _availability_text(row)
        normalized = dict(row)
        if available_at and not _as_text(normalized.get("available_at")):
            normalized["available_at"] = available_at
        if available_at and _is_after(available_at, backtest_date_text):
            late_rows.append(normalized)
        else:
            available_rows.append(normalized)
    return available_rows, late_rows


def _normalize_quote_row(row, backtest_date_text):
    quote = dict(row)
    price = to_float(quote.get("price"))
    if price is None:
        price = to_float(quote.get("close"))
    if price is None:
        price = to_float(quote.get("adjusted_close"))
    if price is None:
        return None
    quote["price"] = price
    quote["quote_date"] = _as_text(quote.get("quote_date") or quote.get("date") or backtest_date_text)
    quote["available_at"] = _as_text(quote.get("available_at") or quote["quote_date"])
    if not str(quote.get("data_status", "")).strip():
        quote["data_status"] = "ready"
    return quote


def _company_facts_payload_for_row(row, company_facts_by_cik):
    cik = str(row.get("cik", "")).strip()
    payload = company_facts_by_cik.get(cik)
    if payload is None and cik:
        payload = company_facts_by_cik.get(cik.lstrip("0"))
    return cik, payload


def _membership_evidence_label(rows):
    labels = []
    for row in rows or []:
        label = _as_text(row.get("membership_evidence") or row.get("evidence_level") or "").lower()
        labels.append(label or "secondary")
    if not labels:
        return "secondary"
    return "verified" if all(label == "verified" for label in labels) else "secondary"


def _financial_metrics_for_row(row, company_facts_by_cik, backtest_date_text):
    cik, payload = _company_facts_payload_for_row(row, company_facts_by_cik)
    if payload is None:
        return None, "", ""
    try:
        metrics = calculate_metrics_as_of(payload, backtest_date_text)
    except Exception:
        return None, "", ""
    return (
        metrics,
        _as_text(metrics.get("latest_source_filed")),
        _as_text(metrics.get("earliest_future_filed")),
    )


def _financial_leakage_audit_rows(row, company_facts_by_cik, backtest_date_text):
    cik, payload = _company_facts_payload_for_row(row, company_facts_by_cik)
    if not isinstance(payload, dict):
        return []

    future_filed_dates = set()
    facts = payload.get("facts", {})
    if not isinstance(facts, dict):
        return []

    for taxonomy in facts.values():
        if not isinstance(taxonomy, dict):
            continue
        for concept in taxonomy.values():
            if not isinstance(concept, dict):
                continue
            units = concept.get("units")
            if not isinstance(units, dict):
                continue
            for unit_entries in units.values():
                if not isinstance(unit_entries, list):
                    continue
                for entry in unit_entries:
                    if not isinstance(entry, dict):
                        continue
                    filed = _as_text(entry.get("filed"))
                    if filed and _is_after(filed, backtest_date_text):
                        future_filed_dates.add(filed)
    if not future_filed_dates:
        return []
    earliest_future = min(future_filed_dates, key=lambda value: _temporal_key(value) or datetime.max)
    return [
        _audit_record(
            "financial",
            {
                **row,
                "cik": cik,
                "available_at": earliest_future,
            },
            backtest_date_text,
            "company_facts_by_cik",
            severity="audit",
            reason="future_data_excluded",
        )
    ]


def _build_weekly_input_row(
    membership_row,
    metrics,
    quote_row,
    backtest_date_text,
    config_digest,
):
    row = dict(membership_row)
    row.setdefault("market", membership_row.get("market", "US"))
    row.setdefault("ticker", membership_row.get("ticker", ""))
    row.setdefault("company_name", membership_row.get("company_name", ""))
    row.setdefault("industry", membership_row.get("industry", ""))
    row["membership_evidence"] = _membership_evidence_label([membership_row])
    row["available_at"] = _as_text(membership_row.get("available_at"))
    row["config_digest"] = config_digest
    row["backtest_date"] = backtest_date_text

    if metrics:
        row.update(metrics)
        row["financial_report_date"] = _as_text(metrics.get("latest_source_filed"))
    else:
        row["financial_report_date"] = ""

    if quote_row:
        row["price"] = quote_row.get("price")
        row["currency"] = quote_row.get("currency") or row.get("currency", "USD")
        row["quote_date"] = quote_row.get("quote_date") or quote_row.get("date", "")
        row["quote_available_at"] = _as_text(quote_row.get("available_at") or quote_row.get("quote_date"))
    else:
        row["quote_date"] = ""
        row["quote_available_at"] = ""

    input_available_values = [
        row.get("available_at"),
        row.get("quote_available_at"),
        row.get("financial_report_date"),
        row.get("latest_source_filed"),
    ]
    row["input_available_at_max"] = _max_temporal_value(input_available_values)

    payload = row.get("_financial_payload")
    if payload is not None:
        row.pop("_financial_payload", None)
    return row


def _audit_record(record_type, row, generated_date_text, source, severity="ok", reason=""):
    return {
        "record_type": record_type,
        "source": source,
        "market": _as_text(row.get("market")),
        "ticker": _as_text(row.get("ticker")),
        "company_name": _as_text(row.get("company_name")),
        "industry": _as_text(row.get("industry")),
        "cik": _as_text(row.get("cik")),
        "available_at": _as_text(row.get("available_at") or row.get("date") or row.get("quote_date")),
        "generated_date": generated_date_text,
        "severity": severity,
        "reason": reason,
    }


def _dedupe_forecasts(rows):
    keyed = {}
    for row in rows or []:
        key = (
            _as_text(row.get("market")),
            _as_text(row.get("ticker")).upper(),
            _as_text(row.get("generated_date")),
            _as_text(row.get("model_version")),
        )
        keyed[key] = dict(row)
    return sorted(
        keyed.values(),
        key=lambda row: (
            _as_text(row.get("generated_date")),
            _as_text(row.get("market")),
            _as_text(row.get("ticker")).upper(),
            _as_text(row.get("model_version")),
        ),
    )


def replay_week(
    backtest_date,
    membership_rows,
    company_facts_by_cik,
    price_rows,
    benchmark_rows,
    output_root,
    config_digest,
    price_rows_as_of=False,
    benchmark_rows_as_of=False,
    preserve_price_history=False,
):
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    backtest_date_text = _as_text(backtest_date)

    available_memberships, future_memberships = _available_membership_rows(
        membership_rows, backtest_date_text
    )
    normalized_price_rows = _normalize_price_rows(price_rows)
    if price_rows_as_of:
        available_price_rows = normalized_price_rows
        late_price_rows = []
        filtered_price_rows = normalized_price_rows
    else:
        available_price_rows, late_price_rows = _split_rows_by_availability(
            normalized_price_rows, backtest_date_text
        )
        filtered_price_rows = prices_available_as_of(available_price_rows, backtest_date_text)

    normalized_benchmark_rows = _normalize_price_rows(benchmark_rows)
    if benchmark_rows_as_of:
        available_benchmark_rows = normalized_benchmark_rows
        late_benchmark_rows = []
        filtered_benchmark_rows = normalized_benchmark_rows
    else:
        available_benchmark_rows, late_benchmark_rows = _split_rows_by_availability(
            normalized_benchmark_rows, backtest_date_text
        )
        filtered_benchmark_rows = prices_available_as_of(available_benchmark_rows, backtest_date_text)

    membership_tickers = [str(row.get("ticker", "")).strip() for row in available_memberships if row.get("ticker")]
    quote_map = _latest_rows_by_ticker(filtered_price_rows)

    weekly_inputs = []
    audit_rows = []
    financial_success_count = 0
    for row in available_memberships:
        quote_row = _normalize_quote_row(quote_map.get(str(row.get("ticker", "")).strip().upper(), {}), backtest_date_text)
        metrics, financial_available_at, future_financial_available_at = _financial_metrics_for_row(
            row, company_facts_by_cik or {}, backtest_date_text
        )
        if future_financial_available_at:
            audit_rows.append(
                _audit_record(
                    "financial",
                    {
                        **row,
                        "available_at": future_financial_available_at,
                    },
                    backtest_date_text,
                    "company_facts_by_cik",
                    severity="audit",
                    reason="future_data_excluded",
                )
            )
        elif metrics is None:
            audit_rows.extend(
                _financial_leakage_audit_rows(row, company_facts_by_cik or {}, backtest_date_text)
            )
        if metrics is not None:
            financial_success_count += 1
        weekly_row = _build_weekly_input_row(row, metrics, quote_row, backtest_date_text, config_digest)
        if metrics is not None:
            weekly_row["financial_available_at"] = financial_available_at
        else:
            weekly_row["financial_available_at"] = ""
        if quote_row:
            weekly_row["price"] = quote_row.get("price")
            weekly_row["currency"] = quote_row.get("currency")
            weekly_row["quote_date"] = quote_row.get("quote_date")
        weekly_inputs.append(weekly_row)

        audit_rows.append(
            _audit_record(
                "membership",
                row,
                backtest_date_text,
                "membership_rows",
                severity="severe" if _is_after(_as_text(row.get("available_at")), backtest_date_text) else "ok",
                reason="future_data_used" if _is_after(_as_text(row.get("available_at")), backtest_date_text) else "",
            )
        )
        if quote_row:
            audit_rows.append(
                _audit_record(
                    "price",
                    quote_row,
                    backtest_date_text,
                    "price_rows",
                    severity="ok",
                    reason="",
                )
            )
        if metrics is not None and not any(
            entry["record_type"] == "financial" and entry["ticker"] == _as_text(row.get("ticker"))
            and entry["severity"] == "severe"
            for entry in audit_rows
        ):
            audit_rows.append(
                _audit_record(
                    "financial",
                    {
                        **row,
                        "available_at": financial_available_at,
                    },
                    backtest_date_text,
                    "company_facts_by_cik",
                    severity="ok",
                    reason="",
                )
            )

    for row in future_memberships:
        audit_rows.append(
            _audit_record(
                "membership",
                row,
                backtest_date_text,
                "membership_rows",
                severity="severe",
                reason="future_data_used",
            )
        )

    for row in late_price_rows:
        audit_rows.append(
            _audit_record(
                "price",
                row,
                backtest_date_text,
                "price_rows",
                severity="severe",
                reason="future_data_used",
            )
        )

    for row in late_benchmark_rows:
        audit_rows.append(
            _audit_record(
                "benchmark",
                row,
                backtest_date_text,
                "benchmark_rows",
                severity="severe",
                reason="future_data_used",
            )
        )
    for row in available_benchmark_rows:
        audit_rows.append(
            _audit_record(
                "benchmark",
                row,
                backtest_date_text,
                "benchmark_rows",
                severity="ok",
                reason="",
            )
        )

    weekly_inputs = [row for row in weekly_inputs if row.get("ticker")]
    _atomic_write_csv(output / "weekly_inputs.csv", weekly_inputs)

    median_source_rows = []
    for row in weekly_inputs:
        median_source_rows.append(
            {
                "market": row.get("market", ""),
                "industry": row.get("industry", ""),
                "market_cap": row.get("market_cap", ""),
                "net_income_ttm": row.get("net_income_ttm", ""),
                "net_assets": row.get("net_assets", ""),
                "enterprise_value": row.get("enterprise_value", ""),
                "ebitda": row.get("ebitda", ""),
            }
        )
    medians = calculate_industry_medians(median_source_rows)
    enriched_inputs = apply_industry_medians(weekly_inputs, medians, overwrite=True)
    _atomic_write_csv(output / "industry_medians.csv", median_rows(medians))

    scored_rows = []
    for row in enriched_inputs:
        scored = apply_data_quality_block(score_stock(row))
        scored["config_digest"] = config_digest
        scored["input_available_at_max"] = row.get("input_available_at_max", "")
        scored["financial_report_date"] = row.get("financial_report_date", "")
        scored["quote_date"] = row.get("quote_date", "")
        scored["week_backtest_date"] = backtest_date_text
        scored_rows.append(scored)
    scored_rows.sort(key=lambda row: float(row.get("total_score", 0) or 0), reverse=True)
    candidate_rows = [
        row
        for row in scored_rows
        if to_float(row.get("total_score")) is not None
        and to_float(row.get("total_score")) >= 80
        and row.get("risk_flag") != "重大"
        and row.get("data_quality_status") != "blocked"
    ]

    _atomic_write_csv(output / "screening_results.csv", scored_rows)
    _atomic_write_csv(output / "candidate_pool.csv", candidate_rows)

    candidate_tickers = {_as_text(row.get("ticker")).upper() for row in candidate_rows}
    valuation_price_rows = [
        row for row in filtered_price_rows if _as_text(row.get("ticker")).upper() in candidate_tickers
    ]
    valuation_quote_rows = [
        row for ticker, row in quote_map.items() if _as_text(ticker).upper() in candidate_tickers
    ]
    price_fields = list(filtered_price_rows[0]) if filtered_price_rows else None
    quote_fields = list(next(iter(quote_map.values()))) if quote_map else None
    valuation_price_history_path = (
        output / "valuation_price_history.csv" if preserve_price_history else output / "price_history.csv"
    )
    _atomic_write_csv(valuation_price_history_path, valuation_price_rows, price_fields)
    _atomic_write_csv(output / "quotes.csv", valuation_quote_rows, quote_fields)

    candidate_path = output / "candidate_pool.csv"
    price_history_path = valuation_price_history_path
    medians_path = output / "industry_medians.csv"
    quotes_path = output / "quotes.csv"
    run_candidate_valuation(
        candidate_path,
        price_history_path,
        output,
        _as_text(available_memberships[0].get("market", "US")) if available_memberships else "US",
        medians_path,
        quotes_path,
        generated_date=backtest_date_text,
    )

    current_candidate_keys = {
        (
            _as_text(row.get("market")),
            _as_text(row.get("ticker")).upper(),
        )
        for row in candidate_rows
    }
    current_forecast_rows = []
    for row in _read_csv(output / "forecast_history.csv"):
        key = (
            _as_text(row.get("market")),
            _as_text(row.get("ticker")).upper(),
        )
        if (
            _as_text(row.get("generated_date")) == backtest_date_text
            and _as_text(row.get("model_version")) == MODEL_VERSION
            and key in current_candidate_keys
        ):
            current_forecast_rows.append(row)

    available_by_key = {}
    for row in weekly_inputs:
        key = (
            _as_text(row.get("market")),
            _as_text(row.get("ticker")).upper(),
        )
        available_by_key[key] = row

    augmented_forecasts = []
    for row in current_forecast_rows:
        key = (
            _as_text(row.get("market")),
            _as_text(row.get("ticker")).upper(),
        )
        source = available_by_key.get(key, {})
        augmented = dict(row)
        augmented["config_digest"] = config_digest
        week_quality = assess_week_quality(
            _membership_evidence_label(available_memberships),
            price_coverage(membership_tickers, _normalize_price_rows(filtered_price_rows)),
            (financial_success_count / len(available_memberships)) if available_memberships else 0.0,
            bool(filtered_benchmark_rows),
            len(leakage_findings(audit_rows, backtest_date_text)),
        )
        augmented["week_eligible"] = "true" if week_quality["eligible"] else "false"
        augmented["input_available_at_max"] = _max_temporal_value(
            [
                source.get("input_available_at_max"),
                source.get("available_at"),
                source.get("financial_report_date"),
                source.get("quote_date"),
                row.get("price_date"),
            ]
        )
        augmented_forecasts.append(augmented)

    existing_backtest_forecasts = [
        row
        for row in _read_csv(output / "backtest_forecasts.csv")
        if not (
            _as_text(row.get("generated_date")) == backtest_date_text
            and _as_text(row.get("model_version")) in {"", MODEL_VERSION}
        )
    ]
    combined_forecasts = _dedupe_forecasts(existing_backtest_forecasts + augmented_forecasts)
    _atomic_write_csv(output / "backtest_forecasts.csv", combined_forecasts, BACKTEST_FORECAST_FIELDS)

    findings = leakage_findings(audit_rows, backtest_date_text)
    for row in audit_rows:
        if row.get("severity") == "severe":
            row.setdefault("reason", "future_data_used")
        else:
            row.setdefault("severity", "ok")
            row.setdefault("reason", "")

    _atomic_write_csv(output / "data_leakage_audit.csv", audit_rows, AUDIT_FIELDS)

    audit_lines = [
        f"# 数据泄漏审计",
        "",
        f"- 回放日期：{backtest_date_text}",
        f"- 严重泄漏数：{len(findings)}",
        f"- 审计记录数：{len(audit_rows)}",
        "",
        "| 记录类型 | 代码 | 证券 | 可用时间 | 严重程度 | 原因 |",
        "|---|---|---|---|---|---|",
    ]
    if audit_rows:
        for row in audit_rows:
            audit_lines.append(
                f"| {row.get('record_type', '')} | {row.get('source', '')} | {row.get('ticker', '')} | "
                f"{row.get('available_at', '')} | {row.get('severity', '')} | {row.get('reason', '')} |"
            )
    else:
        audit_lines.append("| - | - | - | - | - | - |")
    _atomic_write_text(output / "data_leakage_audit.md", "\n".join(audit_lines) + "\n")

    quality = assess_week_quality(
        _membership_evidence_label(available_memberships),
        price_coverage(membership_tickers, _normalize_price_rows(filtered_price_rows)),
        (financial_success_count / len(available_memberships)) if available_memberships else 0.0,
        bool(filtered_benchmark_rows),
        len(findings),
    )

    return {
        "eligible": quality["eligible"],
        "quality_reasons": quality["reasons"],
        "quote_coverage": price_coverage(membership_tickers, _normalize_price_rows(filtered_price_rows)),
        "financial_coverage": (financial_success_count / len(available_memberships)) if available_memberships else 0.0,
        "benchmark_ready": bool(filtered_benchmark_rows),
        "candidate_rows": len(candidate_rows),
        "forecast_rows": len(combined_forecasts),
        "output_root": output,
    }
