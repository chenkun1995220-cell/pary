import argparse
import csv
import json
from pathlib import Path
from urllib.request import Request, urlopen


def cik_to_10_digits(cik):
    return str(cik or "").strip().zfill(10)


def load_csv_rows(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def build_filing_url(cik, accession_number, primary_document):
    cik_number = str(int(str(cik).strip()))
    accession = str(accession_number).replace("-", "")
    return (
        f"https://www.sec.gov/Archives/edgar/data/{cik_number}/"
        f"{accession}/{primary_document}"
    )


def latest_filings(submissions):
    recent = submissions.get("filings", {}).get("recent", {})
    keys = ["accessionNumber", "filingDate", "reportDate", "form", "primaryDocument"]
    count = min((len(recent.get(key, [])) for key in keys), default=0)
    cik = submissions.get("cik", "")
    result = {}
    for index in range(count):
        form = recent["form"][index]
        if form not in {"10-K", "10-Q"} or form in result:
            continue
        accession = recent["accessionNumber"][index]
        document = recent["primaryDocument"][index]
        result[form] = {
            "form": form,
            "filing_date": recent["filingDate"][index],
            "report_date": recent["reportDate"][index],
            "accession_number": accession,
            "primary_document": document,
            "url": build_filing_url(cik, accession, document),
        }
    return result


def fetch_submissions(cik, user_agent):
    if not user_agent:
        raise ValueError("SEC submissions 请求必须提供 User-Agent。")
    padded = cik_to_10_digits(cik)
    url = f"https://data.sec.gov/submissions/CIK{padded}.json"
    request = Request(url, headers={"User-Agent": user_agent, "Accept-Encoding": "identity"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def load_submissions(cik, user_agent=None, fixture_dir=None):
    padded = cik_to_10_digits(cik)
    if fixture_dir:
        path = Path(fixture_dir) / f"CIK{padded}.json"
        return json.loads(path.read_text(encoding="utf-8-sig"))
    return fetch_submissions(cik, user_agent)


def to_float(value):
    try:
        text = str(value or "").strip().replace(",", "")
        return float(text) if text else None
    except ValueError:
        return None


def fmt_number(value, decimals=2):
    number = to_float(value)
    return "-" if number is None else f"{number:.{decimals}f}"


def fmt_pct(value):
    number = to_float(value)
    return "-" if number is None else f"{number * 100:.1f}%"


def value_trap_checks(candidate, metrics, issues):
    checks = []
    fcf_yield = to_float(candidate.get("fcf_yield"))
    revenue_growth = to_float(metrics.get("revenue_cagr_3y"))
    income_growth = to_float(metrics.get("net_income_cagr_3y"))
    leverage = to_float(metrics.get("net_debt_to_ebitda"))
    basis = metrics.get("metrics_period_basis", "")

    if fcf_yield is not None and fcf_yield < 0.03:
        checks.append("自由现金流收益率低于 3%，估值安全垫有限。")
    if revenue_growth is not None and revenue_growth < 0:
        checks.append("三年收入 CAGR 为负，需要核验业务收缩是否结构性。")
    if income_growth is not None and income_growth < 0:
        checks.append("三年净利润 CAGR 为负，需要核验利润下降原因。")
    if leverage is not None and leverage > 2.5:
        checks.append("净负债/EBITDA 高于 2.5，需要核验偿债压力。")
    if basis and basis != "ttm":
        checks.append(f"核心财务期间口径为 {basis}，不是完整 TTM。")
    for issue in issues:
        checks.append(
            f"数据质量{issue.get('severity', '')}：{issue.get('issue_code', '')}，"
            f"{issue.get('message', '')}"
        )
    if not checks:
        checks.append("自动规则未发现明显价值陷阱，但仍需人工核验一次性项目和会计口径。")
    return checks


def filing_lines(filings):
    lines = ["| 表格 | 申报日期 | 报告期 | 官方链接 |", "|---|---|---|---|"]
    for form in ["10-K", "10-Q"]:
        filing = filings.get(form)
        if filing:
            lines.append(
                f"| {form} | {filing['filing_date']} | {filing['report_date']} | "
                f"[打开 SEC 文件]({filing['url']}) |"
            )
        else:
            lines.append(f"| {form} | - | - | 未找到 |")
    return lines


def render_company_report(candidate, metrics, issues, filings):
    checks = value_trap_checks(candidate, metrics, issues)
    lines = [
        f"# {candidate.get('ticker')} {candidate.get('company_name')} 深研包",
        "",
        "## 初筛结论",
        "",
        f"- 行业：{candidate.get('industry', '-')}",
        f"- 总分：{candidate.get('total_score', '-')} / 100",
        f"- 等级：{candidate.get('grade', '-')}",
        f"- 动作：{candidate.get('action', '-')}",
        f"- 初筛理由：{candidate.get('reason', '-')}",
        "",
        "## 估值快照",
        "",
        "| 指标 | 当前值 |",
        "|---|---:|",
        f"| PE | {fmt_number(candidate.get('pe'))}x |",
        f"| PB | {fmt_number(candidate.get('pb'))}x |",
        f"| PS | {fmt_number(candidate.get('ps'))}x |",
        f"| EV/EBITDA | {fmt_number(candidate.get('ev_ebitda'))}x |",
        f"| FCF 收益率 | {fmt_pct(candidate.get('fcf_yield'))} |",
        "",
        "## 财务质量",
        "",
        "| 指标 | 当前值 |",
        "|---|---:|",
        f"| ROIC | {fmt_pct(metrics.get('roic'))} |",
        f"| 毛利率 | {fmt_pct(metrics.get('gross_margin'))} |",
        f"| 流动比率 | {fmt_number(metrics.get('current_ratio'))} |",
        f"| 资产负债率 | {fmt_pct(metrics.get('debt_to_assets'))} |",
        f"| 净负债/EBITDA | {fmt_number(metrics.get('net_debt_to_ebitda'))}x |",
        f"| 收入三年 CAGR | {fmt_pct(metrics.get('revenue_cagr_3y'))} |",
        f"| 净利润三年 CAGR | {fmt_pct(metrics.get('net_income_cagr_3y'))} |",
        f"| 财务期间口径 | {metrics.get('metrics_period_basis', '-')} |",
        f"| 指标截至 | {metrics.get('metrics_as_of', '-')} |",
        "",
        "## SEC 官方申报",
        "",
        *filing_lines(filings),
        "",
        "## 价值陷阱检查",
        "",
        *[f"- {check}" for check in checks],
        "",
        "## 人工核验清单",
        "",
        "- 阅读最新 10-K/10-Q 的业务、风险因素和管理层讨论。",
        "- 核验自由现金流是否包含营运资本或一次性税费影响。",
        "- 核验回购、股权激励和稀释股本变化。",
        "- 检查收入增长、利润率和客户集中度是否可持续。",
        "- 使用悲观、基准、乐观三种情景单独建立估值模型。",
        "",
        "> 本文档用于研究流程，不构成投资建议。",
        "",
    ]
    return "\n".join(lines)


def render_index(candidates):
    lines = [
        "# 候选公司深研索引",
        "",
        "| 股票 | 公司 | 行业 | 分数 | 等级 | 深研包 |",
        "|---|---|---|---:|---|---|",
    ]
    for candidate in candidates:
        ticker = candidate.get("ticker", "")
        lines.append(
            f"| {ticker} | {candidate.get('company_name', '')} | "
            f"{candidate.get('industry', '')} | {candidate.get('total_score', '')} | "
            f"{candidate.get('grade', '')} | [{ticker}_深研包.md]({ticker}_深研包.md) |"
        )
    lines.extend(["", "> 初筛结果不构成投资建议。", ""])
    return "\n".join(lines)


def run_candidate_research_packs(
    candidate_path,
    metrics_path,
    issues_path,
    companies_path,
    output_dir,
    user_agent=None,
    fixture_dir=None,
):
    candidates = load_csv_rows(candidate_path)
    metrics_by_ticker = {
        row.get("ticker", "").upper(): row for row in load_csv_rows(metrics_path)
    }
    companies_by_ticker = {
        row.get("ticker", "").upper(): row for row in load_csv_rows(companies_path)
    }
    issues_by_ticker = {}
    for issue in load_csv_rows(issues_path):
        issues_by_ticker.setdefault(issue.get("ticker", "").upper(), []).append(issue)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    generated = []
    for candidate in candidates:
        ticker = candidate.get("ticker", "").upper()
        company = companies_by_ticker.get(ticker, {})
        cik = company.get("cik") or candidate.get("source_cik")
        submissions = load_submissions(cik, user_agent=user_agent, fixture_dir=fixture_dir)
        filings = latest_filings(submissions)
        report = render_company_report(
            candidate,
            metrics_by_ticker.get(ticker, {}),
            issues_by_ticker.get(ticker, []),
            filings,
        )
        report_path = output / f"{ticker}_深研包.md"
        report_path.write_text(report, encoding="utf-8-sig")
        generated.append(report_path)

    index_path = output / "候选公司深研索引.md"
    index_path.write_text(render_index(candidates), encoding="utf-8-sig")
    return {
        "rows": len(candidates),
        "output_dir": output,
        "index_path": index_path,
        "reports": generated,
    }


def main():
    parser = argparse.ArgumentParser(description="为候选股票生成 SEC 官方链接和量化深研包。")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--metrics", required=True)
    parser.add_argument("--issues", required=True)
    parser.add_argument("--companies", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--user-agent", default=None)
    parser.add_argument("--fixture-dir", default=None)
    args = parser.parse_args()

    result = run_candidate_research_packs(
        args.candidates,
        args.metrics,
        args.issues,
        args.companies,
        args.output_dir,
        user_agent=args.user_agent,
        fixture_dir=args.fixture_dir,
    )
    print(f"已生成候选深研包：{result['rows']}")
    print(f"索引：{result['index_path']}")


if __name__ == "__main__":
    main()
