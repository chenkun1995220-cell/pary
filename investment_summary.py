import argparse
import csv
import re
from pathlib import Path


def load_csv_rows(path):
    csv_path = Path(path)
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
        ]


def to_float(value):
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def format_money(currency, value):
    number = to_float(value)
    if number is None:
        return ""
    return f"{currency or 'USD'} {number:.2f}"


def format_pct(value):
    number = to_float(value)
    if number is None:
        return ""
    return f"{number * 100:.1f}%"


def compact_list(values, limit=20):
    items = [value for value in values if value]
    if not items:
        return "无"
    head = items[:limit]
    suffix = f" 等 {len(items)} 只" if len(items) > limit else ""
    return "、".join(head) + suffix


def summarize_data_quality_groups(data_quality_rows, issue_limit=3, ticker_limit=5):
    severity_groups = {
        "阻断": {"阻断", "严重", "错误", "error", "blocked", "blocker"},
        "需复核": {"警告", "warning", "warn"},
        "可接受": {"提示", "info", "notice"},
    }
    severity_order = ["阻断", "需复核", "可接受"]
    grouped = {}

    for row in data_quality_rows:
        code = row.get("issue_code", "").strip() or "unknown_issue"
        severity_text = row.get("severity", "").strip().lower()
        group = "可接受"
        for candidate_group, labels in severity_groups.items():
            if severity_text in {label.lower() for label in labels}:
                group = candidate_group
                break
        key = (group, code)
        if key not in grouped:
            grouped[key] = {"count": 0, "tickers": set()}
        grouped[key]["count"] += 1
        ticker = row.get("ticker", "").strip().upper()
        if ticker:
            grouped[key]["tickers"].add(ticker)

    lines = []
    for severity in severity_order:
        issues = [
            (code, data)
            for (group, code), data in grouped.items()
            if group == severity
        ]
        issues.sort(key=lambda item: (-item[1]["count"], item[0]))
        for code, data in issues[:issue_limit]:
            tickers = sorted(data["tickers"])
            ticker_text = compact_list(tickers, limit=ticker_limit)
            lines.append(
                f"- {severity}：{code} {data['count']} 项，影响 {len(tickers)} 只（{ticker_text}）"
            )
    return lines


def summarize_data_quality_actions(data_quality_rows, action_limit=5, ticker_limit=5):
    grouped = {}
    for row in data_quality_rows:
        code = row.get("issue_code", "").strip() or "unknown_issue"
        action = row.get("review_action", "").strip()
        impact = row.get("impact_on_score", "").strip()
        handling = row.get("recommended_handling", "").strip()
        if not action and not impact and not handling:
            continue
        key = (code, action, impact, handling)
        if key not in grouped:
            grouped[key] = {"count": 0, "tickers": set()}
        grouped[key]["count"] += 1
        ticker = row.get("ticker", "").strip().upper()
        if ticker:
            grouped[key]["tickers"].add(ticker)

    if not grouped:
        return []

    lines = ["", "## 数据风险处置建议", ""]
    items = sorted(
        grouped.items(),
        key=lambda item: (-item[1]["count"], item[0][0], item[0][1]),
    )
    for (code, action, impact, handling), data in items[:action_limit]:
        tickers = sorted(data["tickers"])
        ticker_text = compact_list(tickers, limit=ticker_limit)
        suffix = f"（{data['count']} 项，{ticker_text}）" if tickers else f"（{data['count']} 项）"
        lines.append(f"- {code}：{action}；{impact}；{handling}{suffix}")
    return lines


def summarize_candidate_quality_exposure(candidate_rows, data_quality_rows, row_limit=10):
    candidate_tickers = [row.get("ticker", "").strip().upper() for row in candidate_rows if row.get("ticker")]
    candidate_set = set(candidate_tickers)
    if not candidate_set:
        return []

    affected = [
        row
        for row in data_quality_rows
        if row.get("ticker", "").strip().upper() in candidate_set
    ]
    affected_tickers = {row.get("ticker", "").strip().upper() for row in affected if row.get("ticker")}
    lines = [
        "",
        "## 候选公司数据质量影响",
        "",
        f"- 受影响候选：{len(affected_tickers)}/{len(candidate_set)}",
    ]
    if not affected:
        lines.append("- 当前候选公司未命中数据质量问题。")
        return lines

    lines.extend(
        [
            "",
            "| 股票 | 问题代码 | 处置动作 | 评分影响 |",
            "|---|---|---|---|",
        ]
    )
    for row in sorted(affected, key=lambda item: (item.get("ticker", ""), item.get("issue_code", "")))[:row_limit]:
        lines.append(
            "| {ticker} | {code} | {action} | {impact} |".format(
                ticker=row.get("ticker", "").strip().upper(),
                code=row.get("issue_code", ""),
                action=row.get("review_action", ""),
                impact=row.get("impact_on_score", ""),
            )
        )
    return lines


def read_model_audit_status(path):
    audit_path = Path(path)
    if not audit_path.exists():
        return "unknown", "未找到模型审计报告。"
    text = audit_path.read_text(encoding="utf-8-sig")
    status_match = re.search(r"审计状态[:：]\s*([^\n\r]+)", text)
    conclusion_match = re.search(r"结论[:：]\s*([^\n\r]+)", text)
    status = status_match.group(1).strip() if status_match else "unknown"
    conclusion = conclusion_match.group(1).strip() if conclusion_match else ""
    return status, conclusion


def build_data_health_summary(quote_gap_rows, data_quality_rows, share_override_rows, candidate_rows=None):
    quote_total = len(quote_gap_rows)
    usable_statuses = {"ready", "manual_override_applied"}
    quote_ready = sum(1 for row in quote_gap_rows if row.get("status") in usable_statuses)
    quote_pending = quote_total - quote_ready
    quote_coverage = (quote_ready / quote_total) if quote_total else None

    override_total = len(share_override_rows)
    override_review = sum(1 for row in share_override_rows if row.get("status") not in ("", "current"))

    quality_total = len(data_quality_rows)
    blocked_labels = {"阻断", "错误", "error", "blocked", "blocker"}
    warning_labels = {"警告", "warning", "warn"}
    quality_blocked = sum(
        1 for row in data_quality_rows if row.get("severity", "").strip().lower() in blocked_labels
    )
    quality_warnings = sum(
        1 for row in data_quality_rows if row.get("severity", "").strip().lower() in warning_labels
    )

    if quote_total == 0 and override_total == 0 and quality_total == 0:
        return []

    lines = ["", "## 数据健康", ""]
    if quote_total:
        lines.append(
            f"- 行情覆盖：{quote_ready}/{quote_total} ({quote_coverage * 100:.2f}%)；待补 {quote_pending}"
        )
    if override_total:
        lines.append(f"- 人工覆盖：{override_total} 项，需复核 {override_review} 项")
    if quality_total:
        lines.append(
            f"- 数据质量问题：{quality_total} 项（阻断 {quality_blocked}，警告 {quality_warnings}）"
        )
        lines.extend(summarize_data_quality_groups(data_quality_rows))
        lines.extend(summarize_data_quality_actions(data_quality_rows))
    if candidate_rows:
        lines.extend(summarize_candidate_quality_exposure(candidate_rows, data_quality_rows))
    return lines


def latest_prior_forecast_tickers(forecast_rows, current_generated_date):
    prior_dates = sorted(
        {
            row.get("generated_date", "")
            for row in forecast_rows
            if row.get("generated_date", "") and row.get("generated_date", "") < current_generated_date
        }
    )
    if not prior_dates:
        return set()
    latest_prior_date = prior_dates[-1]
    return {
        row.get("ticker", "").upper()
        for row in forecast_rows
        if row.get("generated_date") == latest_prior_date and row.get("ticker")
    }


def merge_candidate_rows(candidate_rows, valuation_rows):
    valuations_by_ticker = {row.get("ticker", "").upper(): row for row in valuation_rows}
    merged = []
    for candidate in candidate_rows:
        ticker = candidate.get("ticker", "").upper()
        valuation = valuations_by_ticker.get(ticker, {})
        row = dict(candidate)
        row.update({f"valuation_{key}": value for key, value in valuation.items()})
        row["ticker"] = ticker
        row["company_name"] = valuation.get("company_name") or candidate.get("company_name", "")
        row["currency"] = valuation.get("currency") or "USD"
        row["current_price"] = valuation.get("current_price", "")
        row["buy_price"] = valuation.get("buy_price", "")
        row["target_price"] = valuation.get("target_price", "")
        row["expected_return"] = valuation.get("expected_return", "")
        row["price_action"] = valuation.get("price_action", "")
        row["trend_label"] = valuation.get("trend_label", "")
        row["valuation_confidence"] = valuation.get("valuation_confidence", "")
        row["valuation_reason"] = valuation.get("reason", "")
        row["price_date"] = valuation.get("price_date", "")
        row["generated_date"] = valuation.get("generated_date", "")
        row["model_version"] = valuation.get("model_version", "")
        row["risk_summary"] = row.get("risk_summary") or row.get("risk_note") or row.get("risk_flag") or build_candidate_risk_summary(row)
        merged.append(row)
    return sorted(
        merged,
        key=lambda row: (
            to_float(row.get("total_score")) or 0,
            to_float(row.get("expected_return")) or 0,
        ),
        reverse=True,
    )


def _is_present(value):
    return str(value or "").strip() not in {"", "None", "none", "nan", "NaN"}


def build_candidate_risk_summary(row):
    risks = []
    confidence = str(row.get("valuation_confidence", "")).strip().lower()
    if confidence == "low":
        risks.append("估值置信度低")

    price_action = str(row.get("price_action", "")).strip()
    if "无安全边际" in price_action:
        risks.append("当前无安全边际")
    elif "等待回调" in price_action:
        risks.append("需等待更好买点")

    expected_return = to_float(row.get("expected_return"))
    if expected_return is not None and expected_return < 0:
        risks.append("预期收益为负")

    trend = str(row.get("trend_label", "")).strip()
    if trend in {"偏弱", "弱势"}:
        risks.append("走势偏弱")

    debt_to_assets = to_float(row.get("debt_to_assets"))
    if debt_to_assets is not None and debt_to_assets >= 0.60:
        risks.append("资产负债率偏高")

    current_ratio = to_float(row.get("current_ratio"))
    if current_ratio is not None and current_ratio < 1:
        risks.append("流动比率低于1")

    revenue_growth = to_float(row.get("revenue_growth"))
    if revenue_growth is not None and revenue_growth < 0:
        risks.append("收入增长为负")

    net_income_growth = to_float(row.get("net_income_growth"))
    if net_income_growth is not None and net_income_growth < 0:
        risks.append("净利润增长为负")

    data_quality_statuses = [
        row.get("data_quality_status"),
        row.get("financial_data_status"),
        row.get("valuation_valuation_status"),
    ]
    weak_quality = [
        str(status).strip()
        for status in data_quality_statuses
        if _is_present(status) and str(status).strip().lower() not in {"ready", "ok", "current", "manual_override_applied"}
    ]
    if weak_quality:
        risks.append("数据质量需复核")

    if not risks:
        risks.append("未发现量化硬性风险，仍需复核行业周期和财报一次性项目")
    return "；".join(risks)


def build_candidate_risk_lines(rows, row_limit=None):
    if not rows:
        return []
    lines = [
        "",
        "## 候选风险说明",
        "",
        "| 股票 | 公司 | 风险说明 |",
        "|---|---|---|",
    ]
    visible_rows = rows if row_limit is None else rows[:row_limit]
    for row in visible_rows:
        lines.append(
            "| {ticker} | {company} | {risk} |".format(
                ticker=row.get("ticker", ""),
                company=row.get("company_name", ""),
                risk=row.get("risk_summary") or build_candidate_risk_summary(row),
            )
        )
    return lines


def build_candidate_explanation_summary_lines(rows):
    if not rows:
        return []

    total = len(rows)
    buy_zone_count = sum(
        1 for row in rows if "达到建议买入区间" in str(row.get("price_action", ""))
    )
    wait_count = sum(
        1
        for row in rows
        if "等待" in str(row.get("price_action", ""))
        or "安全边际" in str(row.get("price_action", ""))
    )
    low_confidence_count = sum(
        1
        for row in rows
        if str(row.get("valuation_confidence", "")).strip().lower() == "low"
    )
    weak_trend_count = sum(
        1 for row in rows if str(row.get("trend_label", "")).strip() in {"偏弱", "弱势"}
    )
    negative_return_count = sum(
        1
        for row in rows
        if (to_float(row.get("expected_return")) is not None and to_float(row.get("expected_return")) < 0)
    )

    return [
        "",
        "## 候选解释摘要",
        "",
        f"- 达到建议买入区间：{buy_zone_count}/{total}",
        f"- 等待回调或安全边际不足：{wait_count}/{total}",
        f"- 估值置信度 low：{low_confidence_count}/{total}",
        f"- 走势偏弱：{weak_trend_count}/{total}",
        f"- 预期收益为负：{negative_return_count}/{total}",
    ]


def _tracking_status_by_ticker(tracking_rows):
    status_by_ticker = {}
    for row in tracking_rows:
        ticker = row.get("ticker", "").strip().upper()
        if ticker:
            status_by_ticker[ticker] = row.get("evaluation_status", "").strip()
    return status_by_ticker


def candidate_conclusion_quality(rows, tracking_rows):
    tracking_status = _tracking_status_by_ticker(tracking_rows)
    results = []
    for row in rows:
        ticker = row.get("ticker", "").strip().upper()
        categories = []
        details = []

        reason = row.get("reason") or row.get("valuation_reason")
        if len(str(reason or "").strip()) < 8:
            categories.append("理由不足")
            details.append("缺少低估依据")

        buy_price = row.get("buy_price")
        target_price = row.get("target_price")
        if not _is_present(buy_price):
            categories.append("数据不足")
            details.append("缺少建议买入价")
        if not _is_present(target_price):
            categories.append("数据不足")
            details.append("缺少目标价")
        if not _is_present(tracking_status.get(ticker)):
            categories.append("数据不足")
            details.append("缺少跟踪状态")

        data_quality_values = [
            row.get("data_quality_status"),
            row.get("financial_data_status"),
            row.get("valuation_valuation_status"),
        ]
        usable_quality_statuses = {"ready", "ok", "current", "manual_override_applied"}
        has_usable_quality_status = any(
            str(value or "").strip().lower() in usable_quality_statuses
            for value in data_quality_values
        )
        if not has_usable_quality_status:
            categories.append("数据不足")
            details.append("缺少数据质量说明")

        risk_text = row.get("risk_flag") or row.get("risk_note") or row.get("risk_summary")
        if not _is_present(risk_text):
            categories.append("可读性不足")
            details.append("缺少风险说明")

        category_order = ["理由不足", "数据不足", "可读性不足"]
        unique_categories = [category for category in category_order if category in categories]
        results.append(
            {
                "ticker": ticker,
                "company_name": row.get("company_name", ""),
                "status": "complete" if not unique_categories else "needs_review",
                "categories": unique_categories,
                "details": details,
            }
        )
    return results


def build_conclusion_quality_lines(rows, tracking_rows, row_limit=20):
    quality_rows = candidate_conclusion_quality(rows, tracking_rows)
    if not quality_rows:
        return []
    complete_count = sum(1 for row in quality_rows if row["status"] == "complete")
    lines = [
        "",
        "## 候选结论质量检查",
        "",
        f"- 字段完整：{complete_count}/{len(quality_rows)}",
    ]
    review_rows = [row for row in quality_rows if row["status"] != "complete"]
    if not review_rows:
        lines.append("- 当前候选结论字段完整。")
        return lines

    lines.extend(
        [
            "",
            "| 股票 | 公司 | 缺口分类 | 具体缺口 |",
            "|---|---|---|---|",
        ]
    )
    for row in review_rows[:row_limit]:
        lines.append(
            "| {ticker} | {company} | {categories} | {details} |".format(
                ticker=row["ticker"],
                company=row["company_name"],
                categories="、".join(row["categories"]),
                details="；".join(row["details"]),
            )
        )
    return lines


def build_summary_lines(
    rows,
    tracking_rows,
    previous_tickers,
    audit_status,
    audit_conclusion,
    top_limit,
    data_health_lines=None,
):
    current_tickers = {row.get("ticker", "") for row in rows if row.get("ticker")}
    current_generated_date = next((row.get("generated_date", "") for row in rows if row.get("generated_date")), "")
    model_version = next((row.get("model_version", "") for row in rows if row.get("model_version")), "")
    market = next((row.get("market", "") or row.get("valuation_market", "") for row in rows), "")
    new_tickers = sorted(current_tickers - previous_tickers)
    continuous_tickers = sorted(current_tickers & previous_tickers)
    removed_tickers = sorted(previous_tickers - current_tickers)
    tracking_count = sum(1 for row in tracking_rows if row.get("evaluation_status") == "tracking")
    mature_count = sum(1 for row in tracking_rows if row.get("evaluation_status") not in ("", "tracking"))

    lines = [
        "# 每周低估公司结论",
        "",
        f"- 生成日期：{current_generated_date or '未知'}",
        f"- 市场：{market or '未知'}",
        f"- 候选公司数量：{len(rows)}",
        f"- 模型版本：{model_version or '未知'}",
        f"- 模型审计状态：{audit_status}",
        f"- 跟踪中样本：{tracking_count}",
        f"- 成熟评价样本：{mature_count}",
    ]
    if audit_conclusion:
        lines.append(f"- 审计结论：{audit_conclusion}")
    if data_health_lines:
        lines.extend(data_health_lines)
    lines.extend(
        [
            "",
            "## 本周优先关注",
            "",
            "| 股票 | 公司 | 评级 | 评分 | 当前价 | 建议买入价 | 目标价 | 预期收益 | 操作判断 | 趋势 | 估值置信度 | 低估理由 |",
            "|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|",
        ]
    )
    for row in rows[:top_limit]:
        currency = row.get("currency") or "USD"
        reason = row.get("reason") or row.get("valuation_reason") or ""
        lines.append(
            "| {ticker} | {company} | {grade} | {score:.1f} | {current_price} | {buy_price} | {target_price} | {expected_return} | {action} | {trend} | {confidence} | {reason} |".format(
                ticker=row.get("ticker", ""),
                company=row.get("company_name", ""),
                grade=row.get("grade", ""),
                score=to_float(row.get("total_score")) or 0,
                current_price=format_money(currency, row.get("current_price")),
                buy_price=format_money(currency, row.get("buy_price")),
                target_price=format_money(currency, row.get("target_price")),
                expected_return=format_pct(row.get("expected_return")),
                action=row.get("price_action", ""),
                trend=row.get("trend_label", ""),
                confidence=row.get("valuation_confidence", ""),
                reason=reason,
            )
        )
    lines.extend(build_candidate_risk_lines(rows))
    lines.extend(build_candidate_explanation_summary_lines(rows))
    lines.extend(build_conclusion_quality_lines(rows, tracking_rows))
    lines.extend(
        [
            "",
            "## 新入选",
            "",
            compact_list(new_tickers),
            "",
            "## 连续入选",
            "",
            compact_list(continuous_tickers),
            "",
            "## 本周剔除",
            "",
            compact_list(removed_tickers),
            "",
            "## 使用提示",
            "",
            "优先查看评分高、已达到建议买入区间、且风险标记为无的公司；估值置信度为 low 时，买入价和目标价只作为研究锚点，需要结合后续跟踪样本继续校准。",
            "",
            "仅供研究筛选，不构成投资建议。",
        ]
    )
    return lines


def generate_investment_summary(
    candidates_path,
    valuations_path,
    tracking_path,
    forecast_history_path,
    model_audit_path,
    output_path,
    top_limit=20,
    quote_gaps_path=None,
    data_quality_issues_path=None,
    share_override_audit_path=None,
):
    candidate_rows = load_csv_rows(candidates_path)
    valuation_rows = load_csv_rows(valuations_path)
    tracking_rows = load_csv_rows(tracking_path)
    forecast_rows = load_csv_rows(forecast_history_path)
    current_generated_date = max((row.get("generated_date", "") for row in valuation_rows), default="")
    previous_tickers = latest_prior_forecast_tickers(forecast_rows, current_generated_date)
    audit_status, audit_conclusion = read_model_audit_status(model_audit_path)
    rows = merge_candidate_rows(candidate_rows, valuation_rows)
    data_health_lines = build_data_health_summary(
        load_csv_rows(quote_gaps_path) if quote_gaps_path else [],
        load_csv_rows(data_quality_issues_path) if data_quality_issues_path else [],
        load_csv_rows(share_override_audit_path) if share_override_audit_path else [],
        candidate_rows=rows,
    )
    lines = build_summary_lines(
        rows,
        tracking_rows,
        previous_tickers,
        audit_status,
        audit_conclusion,
        int(top_limit),
        data_health_lines=data_health_lines,
    )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return {
        "candidate_count": len(rows),
        "output_path": output,
        "audit_status": audit_status,
    }


def main():
    parser = argparse.ArgumentParser(description="生成每周低估公司最终结论报告。")
    parser.add_argument("--candidates", default="outputs/us_universe/candidate_pool.csv")
    parser.add_argument("--valuations", default="outputs/us_universe/valuation_targets.csv")
    parser.add_argument("--tracking", default="outputs/us_universe/tracking_snapshot.csv")
    parser.add_argument("--forecast-history", default="outputs/us_universe/forecast_history.csv")
    parser.add_argument("--model-audit", default="outputs/us_universe/model_audit.md")
    parser.add_argument("--quote-gaps", default=None)
    parser.add_argument("--data-quality-issues", default=None)
    parser.add_argument("--share-override-audit", default=None)
    parser.add_argument("--output", default="outputs/automation/latest_investment_summary.md")
    parser.add_argument("--top-limit", type=int, default=20)
    args = parser.parse_args()

    result = generate_investment_summary(
        args.candidates,
        args.valuations,
        args.tracking,
        args.forecast_history,
        args.model_audit,
        args.output,
        top_limit=args.top_limit,
        quote_gaps_path=args.quote_gaps,
        data_quality_issues_path=args.data_quality_issues,
        share_override_audit_path=args.share_override_audit,
    )
    print(f"已生成低估公司结论报告：{result['output_path']}")
    print(f"候选公司数量：{result['candidate_count']}")
    print(f"模型审计状态：{result['audit_status']}")


if __name__ == "__main__":
    main()
