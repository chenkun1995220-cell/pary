import argparse
import csv
from datetime import date
from pathlib import Path

from sec_edgar_adapter import load_company_facts


FLOW_CONCEPTS = {
    "revenue_ttm": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ],
    "net_income_ttm": ["NetIncomeLoss", "ProfitLoss"],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "capex_positive": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ],
    "gross_profit": ["GrossProfit"],
    "cost_of_revenue": [
        "CostOfRevenue",
        "CostOfGoodsAndServicesSold",
        "CostOfGoodsSold",
    ],
    "operating_income": ["OperatingIncomeLoss"],
    "depreciation": [
        "DepreciationDepletionAndAmortization",
        "DepreciationDepletionAndAmortizationPropertyPlantAndEquipment",
        "Depreciation",
    ],
    "income_tax": ["IncomeTaxExpenseBenefit"],
    "pretax_income": [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxes",
    ],
}

INSTANT_CONCEPTS = {
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
}

DEBT_GROUPS = [
    ["LongTermDebtAndFinanceLeaseObligationsCurrent", "LongTermDebtAndFinanceLeaseObligationsNoncurrent"],
    ["LongTermDebtCurrent", "LongTermDebtNoncurrent"],
    ["ShortTermBorrowings", "LongTermDebt"],
    ["LongTermDebtAndFinanceLeaseObligations"],
    ["LongTermDebt"],
]

METRIC_FIELDS = [
    "revenue_ttm",
    "net_income_ttm",
    "operating_cash_flow",
    "capex",
    "ebitda",
    "gross_margin",
    "current_ratio",
    "roic",
    "net_debt_to_ebitda",
    "revenue_cagr_3y",
    "net_income_cagr_3y",
    "metrics_period_basis",
    "metrics_as_of",
]


def parse_date(value):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def duration_days(fact):
    start = parse_date(fact.get("start"))
    end = parse_date(fact.get("end"))
    if not start or not end:
        return None
    return (end - start).days + 1


def concept_entries(company_facts, concept_names, unit="USD"):
    us_gaap = company_facts.get("facts", {}).get("us-gaap", {})
    for concept in concept_names:
        entries = [
            dict(fact, concept=concept)
            for fact in us_gaap.get(concept, {}).get("units", {}).get(unit, [])
            if fact.get("val") is not None
        ]
        if entries:
            return entries
    return []


def annual_entries(company_facts, concept_names):
    candidates = []
    for fact in concept_entries(company_facts, concept_names):
        days = duration_days(fact)
        if fact.get("form") not in {"10-K", "20-F", "40-F"}:
            continue
        if fact.get("fp") not in {None, "FY"}:
            continue
        if days is not None and not 300 <= days <= 380:
            continue
        candidates.append(fact)

    by_end = {}
    for fact in candidates:
        end = fact.get("end") or ""
        previous = by_end.get(end)
        if previous is None or (fact.get("filed") or "") > (previous.get("filed") or ""):
            by_end[end] = fact
    return sorted(by_end.values(), key=lambda fact: fact.get("end") or "", reverse=True)


def latest_ttm_value(company_facts, concept_names):
    annuals = annual_entries(company_facts, concept_names)
    if not annuals:
        return None, "partial"
    annual = annuals[0]
    annual_end = parse_date(annual.get("end"))
    entries = concept_entries(company_facts, concept_names)
    ytd = []
    for fact in entries:
        end = parse_date(fact.get("end"))
        days = duration_days(fact)
        if not end or not annual_end or end <= annual_end:
            continue
        if fact.get("form") not in {"10-Q", "6-K"}:
            continue
        if days is None or not 60 <= days <= 300:
            continue
        ytd.append(fact)
    ytd.sort(key=lambda fact: (fact.get("end") or "", fact.get("filed") or ""), reverse=True)

    if ytd:
        current = ytd[0]
        current_end = parse_date(current.get("end"))
        current_days = duration_days(current)
        prior_candidates = []
        for fact in entries:
            end = parse_date(fact.get("end"))
            days = duration_days(fact)
            if not end or days is None or not current_end:
                continue
            day_gap = (current_end - end).days
            if not 330 <= day_gap <= 400:
                continue
            if abs(days - current_days) > 20:
                continue
            if current.get("fp") and fact.get("fp") and current.get("fp") != fact.get("fp"):
                continue
            prior_candidates.append(fact)
        prior_candidates.sort(
            key=lambda fact: (fact.get("end") or "", fact.get("filed") or ""), reverse=True
        )
        if prior_candidates:
            return annual["val"] + current["val"] - prior_candidates[0]["val"], "ttm"

    return annual["val"], "annual_fallback"


def latest_instant_value(company_facts, concept_names):
    entries = concept_entries(company_facts, concept_names)
    if not entries:
        return None
    entries.sort(key=lambda fact: (fact.get("end") or "", fact.get("filed") or ""), reverse=True)
    return entries[0]["val"]


def debt_value(company_facts):
    for group in DEBT_GROUPS:
        values = [latest_instant_value(company_facts, [concept]) for concept in group]
        if all(value is not None for value in values):
            return sum(values)
    return None


def three_year_cagr(company_facts, concept_names):
    annuals = annual_entries(company_facts, concept_names)
    if not annuals:
        return None
    by_year = {}
    for fact in annuals:
        end = parse_date(fact.get("end"))
        if end:
            by_year[end.year] = fact["val"]
    latest_year = max(by_year, default=None)
    if latest_year is None or latest_year - 3 not in by_year:
        return None
    latest = by_year[latest_year]
    base = by_year[latest_year - 3]
    if latest <= 0 or base <= 0:
        return None
    return (latest / base) ** (1 / 3) - 1


def safe_ratio(numerator, denominator):
    if numerator is None or denominator in {None, 0}:
        return None
    return numerator / denominator


def calculate_financial_metrics(company_facts):
    flow_values = {}
    bases = {}
    for field, concepts in FLOW_CONCEPTS.items():
        flow_values[field], bases[field] = latest_ttm_value(company_facts, concepts)

    revenue = flow_values["revenue_ttm"]
    gross_profit = flow_values["gross_profit"]
    if gross_profit is None and revenue is not None and flow_values["cost_of_revenue"] is not None:
        gross_profit = revenue - flow_values["cost_of_revenue"]

    operating_income = flow_values["operating_income"]
    depreciation = flow_values["depreciation"]
    ebitda = (
        operating_income + depreciation
        if operating_income is not None and depreciation is not None
        else None
    )

    current_assets = latest_instant_value(company_facts, INSTANT_CONCEPTS["current_assets"])
    current_liabilities = latest_instant_value(company_facts, INSTANT_CONCEPTS["current_liabilities"])
    equity = latest_instant_value(company_facts, INSTANT_CONCEPTS["equity"])
    cash = latest_instant_value(company_facts, INSTANT_CONCEPTS["cash"])
    debt = debt_value(company_facts)
    net_debt = debt - cash if debt is not None and cash is not None else None

    tax_expense = flow_values["income_tax"]
    pretax_income = flow_values["pretax_income"]
    tax_rate = safe_ratio(tax_expense, pretax_income)
    if tax_rate is not None:
        tax_rate = min(0.35, max(0, tax_rate))
    invested_capital = (
        equity + debt - cash
        if equity is not None and debt is not None and cash is not None
        else None
    )
    nopat = (
        operating_income * (1 - tax_rate)
        if operating_income is not None and tax_rate is not None
        else None
    )

    core_bases = {bases.get("revenue_ttm"), bases.get("net_income_ttm")}
    if core_bases == {"ttm"}:
        period_basis = "ttm"
    elif "partial" in core_bases or len(core_bases) > 1:
        period_basis = "partial"
    else:
        period_basis = "annual_fallback"

    all_entries = [
        fact
        for concepts in list(FLOW_CONCEPTS.values()) + list(INSTANT_CONCEPTS.values())
        for fact in concept_entries(company_facts, concepts)
        if fact.get("end")
    ]
    metrics_as_of = max((fact.get("end") for fact in all_entries), default="")

    return {
        "revenue_ttm": revenue,
        "net_income_ttm": flow_values["net_income_ttm"],
        "operating_cash_flow": flow_values["operating_cash_flow"],
        "capex": -abs(flow_values["capex_positive"]) if flow_values["capex_positive"] is not None else None,
        "ebitda": ebitda,
        "gross_margin": safe_ratio(gross_profit, revenue),
        "current_ratio": safe_ratio(current_assets, current_liabilities),
        "roic": safe_ratio(nopat, invested_capital),
        "net_debt_to_ebitda": safe_ratio(net_debt, ebitda),
        "revenue_cagr_3y": three_year_cagr(company_facts, FLOW_CONCEPTS["revenue_ttm"]),
        "net_income_cagr_3y": three_year_cagr(company_facts, FLOW_CONCEPTS["net_income_ttm"]),
        "metrics_period_basis": period_basis,
        "metrics_as_of": metrics_as_of,
    }


def load_csv_rows(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def write_enhanced_csv(path, rows):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    for field in METRIC_FIELDS:
        if field not in fields:
            fields.append(field)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_financial_metrics_enhancement(
    input_path, output_path, user_agent=None, fixture_dir=None, cache_dir=None
):
    output_rows = []
    for row in load_csv_rows(input_path):
        cik = row.get("source_cik") or row.get("cik")
        out = dict(row)
        if cik:
            facts = load_company_facts(
                cik,
                user_agent=user_agent,
                fixture_dir=fixture_dir,
                cache_dir=cache_dir,
            )
            metrics = calculate_financial_metrics(facts)
            for field, value in metrics.items():
                if value is not None:
                    out[field] = value
        output_rows.append(out)
    write_enhanced_csv(output_path, output_rows)
    return {"rows": len(output_rows), "output_path": Path(output_path)}


def main():
    parser = argparse.ArgumentParser(description="用 SEC Company Facts 增强 TTM 和财务质量指标。")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--user-agent", default=None)
    parser.add_argument("--fixture-dir", default=None)
    parser.add_argument("--cache-dir", default=None)
    args = parser.parse_args()

    result = run_financial_metrics_enhancement(
        args.input,
        args.output,
        user_agent=args.user_agent,
        fixture_dir=args.fixture_dir,
        cache_dir=args.cache_dir,
    )
    print(f"已增强 SEC 财务指标行数：{result['rows']}")
    print(f"输出文件：{result['output_path']}")


if __name__ == "__main__":
    main()
