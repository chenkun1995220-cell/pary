import argparse
import csv
import statistics
from datetime import date
from pathlib import Path


MODEL_VERSION = "regional_fundamental_v2"


def to_float(value):
    try:
        text = str(value).strip().replace(",", "")
        return float(text) if text else None
    except (TypeError, ValueError):
        return None


def load_rows(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _positive_median(values):
    clean = [value for value in values if value is not None and value > 0]
    return round(float(statistics.median(clean)), 4) if clean else ""


def calculate_industry_medians(rows):
    grouped = {}
    for item in rows:
        key = (item.get("market", "").strip(), item.get("industry", "").strip())
        if not all(key):
            continue
        group = grouped.setdefault(key, {"pe": [], "pb": [], "sample_count": 0})
        group["sample_count"] += 1
        group["pe"].append(to_float(item.get("pe")))
        group["pb"].append(to_float(item.get("pb")))
    return {
        key: {
            "pe_median": _positive_median(group["pe"]),
            "pb_median": _positive_median(group["pb"]),
            "sample_count": group["sample_count"],
        }
        for key, group in grouped.items()
    }


def _discount_score(value, median, levels):
    if value is None or median in (None, "", 0) or value <= 0:
        return 0
    ratio = value / float(median)
    for maximum, points in levels:
        if ratio <= maximum:
            return points
    return 0


def _valuation_review_fields(pe, pb):
    categories = []
    details = []
    if pe is None or pe <= 0:
        categories.append("loss_making_or_negative_pe")
        details.append("pe=" if pe is None else f"pe={pe:g}")
    if pb is None or pb <= 0:
        categories.append("non_positive_book_value_or_pb")
        details.append("pb=" if pb is None else f"pb={pb:g}")
    return ";".join(categories), ";".join(details)


def score_row(item, median, candidate_min_score=65):
    pe = to_float(item.get("pe"))
    pb = to_float(item.get("pb"))
    roe = to_float(item.get("roe"))
    market_cap = to_float(item.get("market_cap"))
    price = to_float(item.get("price"))
    roic = to_float(item.get("roic"))
    gross_margin = to_float(item.get("gross_margin"))
    current_ratio = to_float(item.get("current_ratio"))
    debt_to_assets = to_float(item.get("debt_to_assets"))
    operating_cash_flow = to_float(item.get("operating_cash_flow"))
    revenue_growth = to_float(item.get("revenue_growth"))
    net_income_growth = to_float(item.get("net_income_growth"))
    pe_median = to_float(median.get("pe_median"))
    pb_median = to_float(median.get("pb_median"))
    sample_count = int(median.get("sample_count") or 0)

    pe_score = _discount_score(pe, pe_median, [(0.7, 25), (0.85, 20), (1, 14), (1.15, 7)])
    pb_score = _discount_score(pb, pb_median, [(0.7, 15), (0.85, 12), (1, 9), (1.15, 4)])
    if roe is None or roe <= 0:
        roe_score = 0
    elif roe >= 0.15:
        roe_score = 10
    elif roe >= 0.10:
        roe_score = 8
    elif roe >= 0.05:
        roe_score = 5
    else:
        roe_score = 2
    roic_score = 10 if roic is not None and roic >= 0.12 else 7 if roic is not None and roic >= 0.08 else 3 if roic is not None and roic > 0 else 0
    gross_margin_score = 5 if gross_margin is not None and gross_margin >= 0.40 else 3 if gross_margin is not None and gross_margin >= 0.20 else 1 if gross_margin is not None and gross_margin > 0 else 0
    profitability_score = roe_score + roic_score + gross_margin_score

    debt_score = 8 if debt_to_assets is not None and debt_to_assets <= 0.40 else 5 if debt_to_assets is not None and debt_to_assets <= 0.60 else 1 if debt_to_assets is not None else 0
    current_score = 7 if current_ratio is not None and current_ratio >= 1.5 else 5 if current_ratio is not None and current_ratio >= 1 else 2 if current_ratio is not None and current_ratio > 0 else 0
    balance_sheet_score = debt_score + current_score
    cash_flow_score = 10 if operating_cash_flow is not None and operating_cash_flow > 0 else 0

    def growth_points(value):
        if value is None or value <= 0:
            return 0
        if value >= 0.10:
            return 5
        if value >= 0.03:
            return 3
        return 1

    growth_score = growth_points(revenue_growth) + growth_points(net_income_growth)
    valuation_score = pe_score + pb_score
    total_score = valuation_score + profitability_score + balance_sheet_score + cash_flow_score + growth_score
    valuation_review_category, valuation_review_detail = _valuation_review_fields(pe, pb)

    financial_values = [roic, gross_margin, current_ratio, debt_to_assets, operating_cash_flow, revenue_growth, net_income_growth]
    financial_field_count = sum(value is not None for value in financial_values)
    financial_ready = item.get("financial_data_status") == "ready"
    confidence = "high" if financial_ready and financial_field_count >= 7 else "medium" if financial_ready and financial_field_count >= 4 else "low"

    reasons = []
    if pe is None or pe <= 0:
        reasons.append("PE非正，无法作为盈利估值候选")
    elif pe_median:
        reasons.append(f"PE低于行业中位数：{pe:.2f}x vs {pe_median:.2f}x" if pe <= pe_median else f"PE高于行业中位数：{pe:.2f}x")
    if pb is not None and pb_median and pb <= pb_median:
        reasons.append(f"PB低于行业中位数：{pb:.2f}x vs {pb_median:.2f}x")
    if roe is not None:
        reasons.append(f"ROE {roe * 100:.2f}%")
        if roe < 0.05:
            reasons.append("ROE低于5%，不满足候选盈利质量门槛")
    if sample_count < 5:
        reasons.append(f"行业样本仅{sample_count}家，低于最低要求")
    if not financial_ready:
        reasons.append("财务数据缺失，不进入正式候选")
    else:
        if roic is not None:
            reasons.append(f"ROIC {roic * 100:.2f}%")
        if operating_cash_flow is not None:
            reasons.append("经营现金流为正" if operating_cash_flow > 0 else "经营现金流为负")
        if debt_to_assets is not None:
            reasons.append(f"资产负债率 {debt_to_assets * 100:.2f}%")

    eligible = (
        pe is not None
        and pe > 0
        and pb is not None
        and pb > 0
        and roe is not None
        and roe >= 0.05
        and sample_count >= 5
        and financial_ready
        and total_score >= candidate_min_score
    )
    grade = "A" if total_score >= 85 else "B" if total_score >= 75 else "C" if total_score >= 65 else "D"
    result = dict(item)
    result.update(
        {
            "industry_pe_median": pe_median if pe_median is not None else "",
            "industry_pb_median": pb_median if pb_median is not None else "",
            "industry_median_sample_count": sample_count,
            "pe_score": pe_score,
            "pb_score": pb_score,
            "valuation_score": valuation_score,
            "profitability_score": profitability_score,
            "balance_sheet_score": balance_sheet_score,
            "cash_flow_score": cash_flow_score,
            "growth_score": growth_score,
            "total_score": total_score,
            "grade": grade,
            "candidate_status": "candidate" if eligible else "excluded",
            "valuation_review_category": valuation_review_category,
            "valuation_review_detail": valuation_review_detail,
            "reason": "；".join(reasons),
            "model_version": MODEL_VERSION,
            "model_scope": "估值、盈利质量、资产负债、现金流和增长综合初筛",
            "confidence": confidence,
            "financial_field_count": financial_field_count,
        }
    )
    return result


def write_csv(path, rows):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = []
    for item in rows:
        for key in item:
            if key not in fields:
                fields.append(key)
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        if fields:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)


def run_regional_screening(input_path, output_root, candidate_min_score=75):
    rows = load_rows(input_path)
    medians = calculate_industry_medians(rows)
    scored = [
        score_row(
            item,
            medians.get((item.get("market", "").strip(), item.get("industry", "").strip()), {}),
            candidate_min_score=candidate_min_score,
        )
        for item in rows
    ]
    scored.sort(key=lambda item: (-item["total_score"], item.get("ticker", "")))
    candidates = [item for item in scored if item["candidate_status"] == "candidate"]
    valuation_review_items = [
        item for item in scored if item.get("valuation_review_category")
    ]
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "screening_results.csv", scored)
    write_csv(output / "candidate_pool.csv", candidates)
    write_csv(output / "valuation_review_items.csv", valuation_review_items)
    median_rows = [
        {
            "market": key[0],
            "industry": key[1],
            "sample_count": value["sample_count"],
            "industry_pe_median": value["pe_median"],
            "industry_pb_median": value["pb_median"],
        }
        for key, value in sorted(medians.items())
    ]
    write_csv(output / "industry_medians.csv", median_rows)

    report_lines = [
        f"# {date.today().isoformat()} 区域市场相对估值初筛",
        "",
        f"- 模型版本：{MODEL_VERSION}",
        f"- 股票数量：{len(scored)}",
        f"- 候选数量：{len(candidates)}",
        "- 适用范围：PE/PB相对估值、ROE/ROIC、资产负债、经营现金流和增长综合初筛。",
        "",
        "| 股票 | 公司 | 行业 | 总分 | 等级 | 理由 |",
        "|---|---|---|---:|---|---|",
    ]
    for item in candidates:
        report_lines.append(
            f"| {item.get('ticker', '')} | {item.get('company_name', '')} | {item.get('industry', '')} | {item['total_score']} | {item['grade']} | {item['reason']} |"
        )
    if not candidates:
        report_lines.append("| - | 本期无满足门槛的候选 | - | - | - | - |")
    if valuation_review_items:
        report_lines.extend(
            [
                "",
                "## 估值口径复核",
                "",
                "| 股票 | 公司 | 行业 | 复核分类 | 细节 | 排除理由 |",
                "|---|---|---|---|---|---|",
            ]
        )
        for item in valuation_review_items[:20]:
            report_lines.append(
                f"| {item.get('ticker', '')} | {item.get('company_name', '')} | {item.get('industry', '')} | {item.get('valuation_review_category', '')} | {item.get('valuation_review_detail', '')} | {item['reason']} |"
            )
    (output / "weekly_report.md").write_text(
        "\n".join(report_lines) + "\n", encoding="utf-8-sig"
    )
    return {
        "rows": len(scored),
        "candidates": len(candidates),
        "valuation_review_items": len(valuation_review_items),
        "output_root": output,
    }


def main():
    parser = argparse.ArgumentParser(description="Regional PE/PB/ROE value screening")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--candidate-min-score", type=int, default=75)
    args = parser.parse_args()
    result = run_regional_screening(
        args.input, args.output_root, candidate_min_score=args.candidate_min_score
    )
    print(f"Screening rows: {result['rows']}")
    print(f"Candidates: {result['candidates']}")


if __name__ == "__main__":
    main()
