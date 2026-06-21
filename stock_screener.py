import argparse
import csv
from collections import Counter
from datetime import date
from pathlib import Path

from data_quality_checks import check_rows


OUTPUT_FIELDS = [
    "market",
    "ticker",
    "company_name",
    "industry",
    "market_cap",
    "enterprise_value",
    "revenue_ttm",
    "net_income_ttm",
    "free_cash_flow",
    "pe",
    "pb",
    "ps",
    "ev_ebitda",
    "fcf_yield",
    "valuation_score",
    "profitability_score",
    "balance_sheet_score",
    "cash_flow_score",
    "growth_score",
    "governance_score",
    "total_score",
    "grade",
    "action",
    "risk_flag",
    "data_quality_status",
    "data_quality_block_reason",
    "reason",
    "notes",
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


def ratio(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def points_for_threshold(value, thresholds):
    if value is None:
        return 0
    for threshold, points in thresholds:
        if value >= threshold:
            return points
    return 0


def discount_points(value, median, full, partial, small):
    if value is None or median in (None, 0) or value <= 0:
        return 0
    if value <= median * 0.7:
        return full
    if value <= median * 0.85:
        return partial
    if value <= median:
        return small
    return 0


def grade_for_score(score):
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "E"


def action_for_grade(grade):
    return {
        "A": "进入年报/行业/估值模型深研",
        "B": "加入重点跟踪池",
        "C": "普通观察，等待确认",
        "D": "暂不深研，仅复看",
        "E": "剔除",
    }[grade]


def format_pct(value):
    if value is None:
        return "无数据"
    return f"{value * 100:.1f}%"


def load_stocks(raw_dir):
    raw_path = Path(raw_dir)
    rows = []
    for file_path in sorted(raw_path.glob("*.csv")):
        with file_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row = {key.strip(): value for key, value in row.items() if key is not None}
                row["_source_file"] = file_path.name
                rows.append(row)
    return rows


def build_reason(stock):
    reasons = []
    debt_to_assets = to_float(stock.get("debt_to_assets"))
    if stock.get("pe") is not None and stock.get("industry_pe_median"):
        reasons.append(
            f"PE低于行业中位数：{stock['pe']:.1f}x vs {to_float(stock.get('industry_pe_median')):.1f}x"
            if stock["pe"] <= to_float(stock.get("industry_pe_median"))
            else f"PE高于行业中位数：{stock['pe']:.1f}x"
        )
    if stock.get("pb") is not None and stock.get("industry_pb_median"):
        if stock["pb"] <= to_float(stock.get("industry_pb_median")):
            reasons.append(
                f"PB低于行业中位数：{stock['pb']:.1f}x vs {to_float(stock.get('industry_pb_median')):.1f}x"
            )
    if stock.get("free_cash_flow") is not None and stock["free_cash_flow"] > 0:
        reasons.append(f"自由现金流为正，FCF收益率 {format_pct(stock.get('fcf_yield'))}")
    if stock.get("roe") is not None:
        reasons.append(f"ROE {format_pct(to_float(stock.get('roe')))}")
    if debt_to_assets is not None and debt_to_assets <= 0.4:
        reasons.append("资产负债率较低")
    if stock.get("audit_opinion") == "标准无保留" and stock.get("risk_flag") == "无":
        reasons.append("审计意见标准且无重大风险")
    if stock.get("risk_flag") == "重大":
        reasons.append("存在重大风险标记，已从候选池排除")
    return "；".join(reasons)


def score_stock(stock):
    market_cap = to_float(stock.get("market_cap"))
    enterprise_value = to_float(stock.get("enterprise_value"))
    net_assets = to_float(stock.get("net_assets"))
    revenue = to_float(stock.get("revenue_ttm"))
    net_income = to_float(stock.get("net_income_ttm"))
    ebitda = to_float(stock.get("ebitda"))
    operating_cash_flow = to_float(stock.get("operating_cash_flow"))
    capex = to_float(stock.get("capex"))
    free_cash_flow = to_float(stock.get("free_cash_flow"))
    if free_cash_flow is None and operating_cash_flow is not None and capex is not None:
        free_cash_flow = operating_cash_flow + capex

    pe = ratio(market_cap, net_income) if net_income and net_income > 0 else None
    pb = ratio(market_cap, net_assets) if net_assets and net_assets > 0 else None
    ps = ratio(market_cap, revenue) if revenue and revenue > 0 else None
    ev_ebitda = ratio(enterprise_value, ebitda) if ebitda and ebitda > 0 else None
    fcf_yield = ratio(free_cash_flow, market_cap) if market_cap and market_cap > 0 else None
    net_margin = ratio(net_income, revenue) if revenue and revenue > 0 else None
    cash_conversion = ratio(operating_cash_flow, net_income) if net_income and net_income > 0 else None

    industry_pe = to_float(stock.get("industry_pe_median"))
    industry_pb = to_float(stock.get("industry_pb_median"))
    industry_ev = to_float(stock.get("industry_ev_ebitda_median"))
    roe = to_float(stock.get("roe"))
    roic = to_float(stock.get("roic"))
    gross_margin = to_float(stock.get("gross_margin"))
    debt_to_assets = to_float(stock.get("debt_to_assets"))
    net_debt_to_ebitda = to_float(stock.get("net_debt_to_ebitda"))
    current_ratio = to_float(stock.get("current_ratio"))
    revenue_cagr = to_float(stock.get("revenue_cagr_3y"))
    income_cagr = to_float(stock.get("net_income_cagr_3y"))
    audit_opinion = str(stock.get("audit_opinion", "")).strip()
    risk_flag = str(stock.get("risk_flag", "")).strip()

    valuation_score = min(
        30,
        discount_points(pe, industry_pe, 9, 6, 3)
        + discount_points(pb, industry_pb, 7, 5, 2)
        + discount_points(ev_ebitda, industry_ev, 7, 5, 2)
        + points_for_threshold(fcf_yield, [(0.08, 7), (0.05, 5), (0.03, 2)]),
    )

    profitability_score = min(
        25,
        points_for_threshold(roe, [(0.15, 7), (0.10, 5), (0.000001, 2)])
        + points_for_threshold(roic, [(0.12, 7), (0.08, 5), (0.000001, 2)])
        + points_for_threshold(gross_margin, [(0.40, 6), (0.25, 4), (0.000001, 1)])
        + points_for_threshold(net_margin, [(0.15, 5), (0.08, 3), (0.000001, 1)]),
    )

    balance_sheet_score = min(
        15,
        (5 if debt_to_assets is not None and debt_to_assets <= 0.4 else 3 if debt_to_assets is not None and debt_to_assets <= 0.6 else 1 if debt_to_assets is not None else 0)
        + (5 if net_debt_to_ebitda is not None and net_debt_to_ebitda <= 1 else 3 if net_debt_to_ebitda is not None and net_debt_to_ebitda <= 2.5 else 1 if net_debt_to_ebitda is not None else 0)
        + (5 if current_ratio is not None and current_ratio >= 1.5 else 3 if current_ratio is not None and current_ratio >= 1 else 1 if current_ratio is not None else 0),
    )

    cash_flow_score = min(
        15,
        (4 if free_cash_flow is not None and free_cash_flow > 0 else 0)
        + points_for_threshold(fcf_yield, [(0.08, 5), (0.05, 3), (0.03, 1)])
        + points_for_threshold(cash_conversion, [(1.0, 6), (0.7, 3)]),
    )

    growth_score = min(
        10,
        points_for_threshold(revenue_cagr, [(0.10, 5), (0.03, 3), (0.000001, 1)])
        + points_for_threshold(income_cagr, [(0.10, 5), (0.03, 3), (0.000001, 1)]),
    )

    if audit_opinion == "标准无保留" and risk_flag == "无":
        governance_score = 5
    elif audit_opinion == "标准无保留" and risk_flag != "重大":
        governance_score = 3
    else:
        governance_score = 1

    total_score = (
        valuation_score
        + profitability_score
        + balance_sheet_score
        + cash_flow_score
        + growth_score
        + governance_score
    )
    grade = grade_for_score(total_score)

    scored = dict(stock)
    scored.update(
        {
            "free_cash_flow": free_cash_flow,
            "pe": pe,
            "pb": pb,
            "ps": ps,
            "ev_ebitda": ev_ebitda,
            "fcf_yield": fcf_yield,
            "valuation_score": valuation_score,
            "profitability_score": profitability_score,
            "balance_sheet_score": balance_sheet_score,
            "cash_flow_score": cash_flow_score,
            "growth_score": growth_score,
            "governance_score": governance_score,
            "total_score": total_score,
            "grade": grade,
            "action": action_for_grade(grade),
        }
    )
    scored["reason"] = build_reason(scored)
    scored["notes"] = build_notes(scored, risk_flag)
    return scored


def build_notes(stock, risk_flag):
    notes = []
    if risk_flag == "重大":
        notes.append("重大风险标记，候选池自动排除")
    if stock.get("pe") is None:
        notes.append("PE无法计算或净利润为负")
    if stock.get("fcf_yield") is not None and stock["fcf_yield"] < 0.03:
        notes.append("FCF收益率偏低")
    return "；".join(notes)


def severe_quality_issues(stock):
    return [issue for issue in check_rows([stock]) if issue.get("severity") == "严重"]


def apply_data_quality_block(scored):
    issues = severe_quality_issues(scored)
    if not issues:
        scored["data_quality_status"] = "ok"
        scored["data_quality_block_reason"] = ""
        return scored

    issue_codes = sorted({issue["issue_code"] for issue in issues})
    messages = "；".join(issue["message"] for issue in issues)
    scored["data_quality_status"] = "blocked"
    scored["data_quality_block_reason"] = ";".join(issue_codes)
    scored["total_score"] = 0
    scored["grade"] = "E"
    scored["action"] = "数据质量阻断，暂不评分"
    scored["reason"] = "数据质量存在严重问题，暂不进入候选池"
    existing_notes = scored.get("notes", "")
    scored["notes"] = "；".join(part for part in [existing_notes, f"数据质量阻断：{messages}"] if part)
    return scored


def summarize_quality_issues(stocks):
    issues = check_rows(stocks)
    severity_counts = Counter(issue["severity"] for issue in issues)
    code_counts = Counter(issue["issue_code"] for issue in issues)
    return {
        "issue_count": len(issues),
        "severity_counts": dict(severity_counts),
        "code_counts": dict(code_counts),
    }


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_screening(raw_dir, output_dir, candidate_min_score=80):
    stocks = load_stocks(raw_dir)
    quality_summary = summarize_quality_issues(stocks)
    scored = [apply_data_quality_block(score_stock(stock)) for stock in stocks]
    scored.sort(key=lambda row: row["total_score"], reverse=True)
    candidates = [
        row
        for row in scored
        if row["total_score"] >= candidate_min_score and row.get("risk_flag") != "重大"
        and row.get("data_quality_status") != "blocked"
    ]

    output_path = Path(output_dir)
    write_csv(output_path / "screening_results.csv", scored)
    write_csv(output_path / "candidate_pool.csv", candidates)
    return {
        "total_rows": len(scored),
        "candidate_rows": len(candidates),
        "screening_results": output_path / "screening_results.csv",
        "candidate_pool": output_path / "candidate_pool.csv",
        "scored": scored,
        "candidates": candidates,
        "quality_summary": quality_summary,
    }


def write_weekly_report(path, report_date, result):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# 低估公司每周筛选报告（{report_date}）",
        "",
        "## 摘要",
        "",
        f"- 本周处理股票数：{result['total_rows']}",
        f"- 入选候选池：{result['candidate_rows']}",
        "- 候选池规则：总分不低于阈值，且无重大风险标记",
        "",
        "## 数据质量摘要",
        "",
        f"- 问题总数：{result['quality_summary']['issue_count']}",
        f"- 严重：{result['quality_summary']['severity_counts'].get('严重', 0)}",
        f"- 警告：{result['quality_summary']['severity_counts'].get('警告', 0)}",
        f"- 提示：{result['quality_summary']['severity_counts'].get('提示', 0)}",
        "",
        "| 问题代码 | 数量 |",
        "|---|---:|",
    ]
    if result["quality_summary"]["code_counts"]:
        for code, count in sorted(result["quality_summary"]["code_counts"].items()):
            lines.append(f"| {code} | {count} |")
    else:
        lines.append("| 无 | 0 |")
    lines.extend([
        "",
        "## 候选公司",
        "",
    ])
    if not result["candidates"]:
        lines.append("本周没有符合条件的候选公司。")
    else:
        lines.extend(
            [
                "| 市场 | 代码 | 公司 | 行业 | 总分 | 等级 | 理由 |",
                "|---|---|---|---|---:|---|---|",
            ]
        )
        for row in result["candidates"]:
            lines.append(
                "| {market} | {ticker} | {company_name} | {industry} | {total_score:.0f} | {grade} | {reason} |".format(
                    **row
                )
            )
    lines.extend(
        [
            "",
            "## 高风险或剔除提示",
            "",
            "| 市场 | 代码 | 公司 | 总分 | 等级 | 备注 |",
            "|---|---|---|---:|---|---|",
        ]
    )
    excluded = [row for row in result["scored"] if row.get("risk_flag") == "重大" or row.get("grade") == "E"]
    if excluded:
        for row in excluded[:20]:
            lines.append(
                "| {market} | {ticker} | {company_name} | {total_score:.0f} | {grade} | {notes} |".format(
                    **row
                )
            )
    else:
        lines.append("| - | - | - | - | - | 无 |")
    lines.extend(
        [
            "",
            "## 输出文件",
            "",
            f"- 完整结果：`{result['screening_results']}`",
            f"- 候选池：`{result['candidate_pool']}`",
            "",
            "## 使用提醒",
            "",
            "本报告用于初筛，不构成买卖建议。入选公司仍需进一步核验年报、行业周期、管理层、现金流质量和估值模型。",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8-sig")


def run_weekly_report(raw_dir, output_dir, candidate_min_score=80, report_date=None):
    report_date = report_date or date.today().isoformat()
    result = run_screening(raw_dir, output_dir, candidate_min_score)
    report_path = Path(output_dir) / "reports" / f"{report_date}_低估公司每周筛选报告.md"
    write_weekly_report(report_path, report_date, result)
    result["report_path"] = report_path
    return result


def main():
    parser = argparse.ArgumentParser(description="整合股票 CSV 并按低估筛选标准打分。")
    parser.add_argument("--raw-dir", default="data/raw", help="原始 CSV 文件目录")
    parser.add_argument("--output-dir", default="outputs", help="输出目录")
    parser.add_argument("--candidate-min-score", type=float, default=80, help="候选池最低总分")
    parser.add_argument("--weekly-report", action="store_true", help="同时生成每周 Markdown 报告")
    parser.add_argument("--report-date", default=None, help="报告日期，默认使用今天")
    args = parser.parse_args()

    if args.weekly_report:
        result = run_weekly_report(
            args.raw_dir,
            args.output_dir,
            args.candidate_min_score,
            args.report_date,
        )
    else:
        result = run_screening(args.raw_dir, args.output_dir, args.candidate_min_score)
    print(f"已处理 {result['total_rows']} 行股票数据")
    print(f"候选池 {result['candidate_rows']} 行")
    print(f"完整结果：{result['screening_results']}")
    print(f"候选池：{result['candidate_pool']}")
    if "report_path" in result:
        print(f"每周报告：{result['report_path']}")


if __name__ == "__main__":
    main()
