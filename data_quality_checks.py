import argparse
import csv
from collections import Counter
from pathlib import Path


ISSUE_FIELDS = [
    "severity",
    "issue_code",
    "market",
    "ticker",
    "company_name",
    "field",
    "value",
    "message",
]

REQUIRED_FIELDS = ["ticker", "company_name", "industry"]
CORE_NUMERIC_FIELDS = ["market_cap", "net_income_ttm"]
PERCENT_FIELDS = [
    "dividend_yield",
    "roe",
    "roic",
    "gross_margin",
    "debt_to_assets",
    "revenue_cagr_3y",
    "net_income_cagr_3y",
    "fcf_yield",
]

PERCENT_UNIT_SUSPECT_THRESHOLDS = {
    "dividend_yield": 1,
    "fcf_yield": 1,
    "gross_margin": 1,
    "debt_to_assets": 2,
    "roe": 10,
    "roic": 10,
    "revenue_cagr_3y": 5,
    "net_income_cagr_3y": 5,
}


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


def is_blank(value):
    return value is None or str(value).strip() == ""


def load_csv_rows(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return [{key.strip(): value for key, value in row.items() if key is not None} for row in csv.DictReader(f)]


def make_issue(row, severity, issue_code, field, value, message):
    return {
        "severity": severity,
        "issue_code": issue_code,
        "market": row.get("market", ""),
        "ticker": row.get("ticker", ""),
        "company_name": row.get("company_name", ""),
        "field": field,
        "value": value,
        "message": message,
    }


def check_required_fields(row):
    issues = []
    for field in REQUIRED_FIELDS:
        if is_blank(row.get(field)):
            issues.append(
                make_issue(row, "严重", "missing_required_field", field, row.get(field, ""), f"必填字段 {field} 缺失")
            )
    for field in CORE_NUMERIC_FIELDS:
        if is_blank(row.get(field)):
            if field == "net_income_ttm" and is_blank(row.get("revenue_ttm")):
                issues.append(
                    make_issue(
                        row,
                        "警告",
                        "missing_financial_statement_data",
                        field,
                        row.get(field, ""),
                        "营收和净利润字段同时缺失，可能是特殊上市主体或财务报表尚未覆盖",
                    )
                )
                continue
            issues.append(
                make_issue(row, "警告", "missing_core_numeric_field", field, row.get(field, ""), f"核心数值字段 {field} 缺失，可能影响估值评分")
            )
    return issues


def check_percentage_units(row):
    issues = []
    for field in PERCENT_FIELDS:
        value = to_float(row.get(field))
        threshold = PERCENT_UNIT_SUSPECT_THRESHOLDS.get(field, 1)
        if value is not None and value > threshold:
            issues.append(
                make_issue(row, "警告", "percentage_unit_suspect", field, row.get(field), f"{field} 高于字段阈值 {threshold}，疑似单位、口径或分母异常")
            )
    return issues


def check_mapping_and_samples(row, min_industry_sample):
    issues = []
    if row.get("industry_mapping_status") == "unmapped":
        issues.append(
            make_issue(row, "警告", "industry_unmapped", "industry", row.get("industry", ""), "行业未被别名表映射，可能影响行业中位数分组")
        )
    sample_count = to_float(row.get("industry_median_sample_count"))
    if sample_count is not None and sample_count < min_industry_sample:
        issues.append(
            make_issue(row, "提示", "industry_sample_too_small", "industry_median_sample_count", row.get("industry_median_sample_count"), f"行业中位数样本数小于 {min_industry_sample}，代表性不足")
        )
    return issues


def check_financial_logic(row):
    issues = []
    market_cap = to_float(row.get("market_cap"))
    enterprise_value = to_float(row.get("enterprise_value"))
    net_debt = to_float(row.get("net_debt"))
    if (
        market_cap is not None
        and enterprise_value is not None
        and net_debt is not None
        and net_debt > 0
        and enterprise_value < market_cap
    ):
        issues.append(
            make_issue(row, "严重", "enterprise_value_logic_error", "enterprise_value", row.get("enterprise_value"), "净债务为正但企业价值小于市值，EV 逻辑异常")
        )

    capex = to_float(row.get("capex"))
    if capex is not None and capex > 0:
        issues.append(
            make_issue(row, "警告", "capex_sign_suspect", "capex", row.get("capex"), "资本开支通常按现金流出录入为负数，当前为正数")
        )

    net_income = to_float(row.get("net_income_ttm"))
    market_cap = to_float(row.get("market_cap"))
    if net_income is not None and net_income > 0 and (market_cap is None or market_cap <= 0):
        issues.append(
            make_issue(row, "警告", "pe_unavailable_with_positive_income", "market_cap", row.get("market_cap", ""), "净利润为正但市值缺失或无效，PE 无法可靠计算")
        )
    revenue = to_float(row.get("revenue_ttm"))
    operating_cash_flow = to_float(row.get("operating_cash_flow"))
    free_cash_flow = to_float(row.get("free_cash_flow"))
    if free_cash_flow is None and operating_cash_flow is not None and capex is not None:
        free_cash_flow = operating_cash_flow + capex
    if market_cap is not None and market_cap > 0:
        if revenue is not None and revenue > 0 and market_cap / revenue < 0.02:
            issues.append(
                make_issue(row, "警告", "market_cap_scale_suspect", "market_cap", row.get("market_cap", ""), "市值相对收入低于 2%，疑似股本、价格或金额单位不一致")
            )
        if (
            net_income is not None
            and net_income > 0
            and revenue is not None
            and revenue > 0
            and market_cap / net_income < 1
            and market_cap / revenue < 0.02
        ):
            issues.append(
                make_issue(row, "严重", "valuation_ratio_outlier", "market_cap", row.get("market_cap", ""), "净利润为正但 PE 低于 1，疑似市值或财务金额单位异常")
            )
        if free_cash_flow is not None and free_cash_flow > 0 and free_cash_flow / market_cap > 1:
            issues.append(
                make_issue(row, "严重", "fcf_yield_outlier", "free_cash_flow", free_cash_flow, "自由现金流收益率高于 100%，疑似市值、股本或现金流单位异常")
            )
    return issues


def check_risk_fields(row):
    issues = []
    for field in ["audit_opinion", "risk_flag"]:
        if is_blank(row.get(field)):
            issues.append(
                make_issue(row, "提示", "risk_field_missing", field, row.get(field, ""), f"风险字段 {field} 缺失，建议补充")
            )
    return issues


def check_rows(rows, min_industry_sample=5):
    issues = []
    for row in rows:
        issues.extend(check_required_fields(row))
        issues.extend(check_percentage_units(row))
        issues.extend(check_mapping_and_samples(row, min_industry_sample))
        issues.extend(check_financial_logic(row))
        issues.extend(check_risk_fields(row))
    return issues


def write_issues_csv(path, issues):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ISSUE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(issues)


def write_markdown_report(path, input_path, row_count, issues):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    by_severity = Counter(issue["severity"] for issue in issues)
    by_code = Counter(issue["issue_code"] for issue in issues)
    lines = [
        "# 数据质量检查报告",
        "",
        "## 摘要",
        "",
        f"- 输入文件：`{input_path}`",
        f"- 股票行数：{row_count}",
        f"- 问题总数：{len(issues)}",
        f"- 严重：{by_severity.get('严重', 0)}",
        f"- 警告：{by_severity.get('警告', 0)}",
        f"- 提示：{by_severity.get('提示', 0)}",
        "",
        "## 问题类型",
        "",
        "| 问题代码 | 数量 |",
        "|---|---:|",
    ]
    if by_code:
        for code, count in sorted(by_code.items()):
            lines.append(f"| {code} | {count} |")
    else:
        lines.append("| 无 | 0 |")
    lines.extend(["", "## 明细（前 50 条）", "", "| 级别 | 代码 | 股票 | 字段 | 值 | 说明 |", "|---|---|---|---|---|---|"])
    for issue in issues[:50]:
        stock = issue.get("ticker") or issue.get("company_name") or "-"
        lines.append(
            f"| {issue['severity']} | {issue['issue_code']} | {stock} | {issue['field']} | {issue['value']} | {issue['message']} |"
        )
    if not issues:
        lines.append("| - | - | - | - | - | 未发现问题 |")
    output.write_text("\n".join(lines), encoding="utf-8-sig")


def run_data_quality_checks(input_path, issues_path, report_path, min_industry_sample=5):
    rows = load_csv_rows(input_path)
    issues = check_rows(rows, min_industry_sample=min_industry_sample)
    write_issues_csv(issues_path, issues)
    write_markdown_report(report_path, input_path, len(rows), issues)
    return {
        "rows": len(rows),
        "issue_count": len(issues),
        "issues_path": Path(issues_path),
        "report_path": Path(report_path),
    }


def main():
    parser = argparse.ArgumentParser(description="检查股票筛选输入数据质量。")
    parser.add_argument("--input", required=True, help="待检查 CSV")
    parser.add_argument("--issues", default="outputs/data_quality_issues.csv", help="问题明细 CSV")
    parser.add_argument("--report", default="outputs/data_quality_report.md", help="中文质检报告")
    parser.add_argument("--min-industry-sample", type=int, default=5, help="行业中位数最低样本数提示阈值")
    args = parser.parse_args()

    result = run_data_quality_checks(
        args.input,
        args.issues,
        args.report,
        min_industry_sample=args.min_industry_sample,
    )
    print(f"已检查股票行数：{result['rows']}")
    print(f"发现问题数：{result['issue_count']}")
    print(f"问题明细：{result['issues_path']}")
    print(f"质检报告：{result['report_path']}")


if __name__ == "__main__":
    main()
