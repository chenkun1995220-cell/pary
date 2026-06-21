import argparse
import csv
import json
import os
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen


STANDARD_FIELDS = [
    "market",
    "ticker",
    "company_name",
    "industry",
    "market_cap",
    "enterprise_value",
    "net_assets",
    "revenue_ttm",
    "net_income_ttm",
    "ebitda",
    "operating_cash_flow",
    "capex",
    "dividend_yield",
    "industry_pe_median",
    "industry_pb_median",
    "industry_ev_ebitda_median",
    "roe",
    "roic",
    "gross_margin",
    "debt_to_assets",
    "net_debt_to_ebitda",
    "current_ratio",
    "revenue_cagr_3y",
    "net_income_cagr_3y",
    "audit_opinion",
    "risk_flag",
    "source",
    "source_cik",
    "source_filed",
]


CONCEPTS = {
    "revenue_ttm": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
    ],
    "net_income_ttm": ["NetIncomeLoss", "ProfitLoss"],
    "net_assets": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "capex_positive": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ],
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
}


def cik_to_10_digits(cik):
    return str(cik).strip().zfill(10)


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


def latest_annual_usd_fact(company_facts, concept_names):
    us_gaap = company_facts.get("facts", {}).get("us-gaap", {})
    candidates = []
    for concept in concept_names:
        units = us_gaap.get(concept, {}).get("units", {})
        for fact in units.get("USD", []):
            if fact.get("form") not in {"10-K", "20-F", "40-F"}:
                continue
            if fact.get("fp") not in {None, "FY"}:
                continue
            if fact.get("val") is None:
                continue
            candidates.append(
                {
                    "concept": concept,
                    "value": fact.get("val"),
                    "filed": fact.get("filed") or "",
                    "fy": fact.get("fy") or 0,
                    "end": fact.get("end") or "",
                }
            )
    if not candidates:
        return None, None
    candidates.sort(key=lambda item: (item["fy"], item["filed"], item["end"]), reverse=True)
    picked = candidates[0]
    return picked["value"], picked


def load_sec_config(config_path):
    rows = []
    with Path(config_path).open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            clean = {key.strip(): value for key, value in row.items() if key is not None}
            if clean.get("ticker") and clean.get("cik"):
                rows.append(clean)
    return rows


def fetch_company_facts(cik, user_agent):
    if not user_agent:
        raise ValueError("SEC 请求必须提供 User-Agent，例如姓名/邮箱或项目联系方式。")
    padded = cik_to_10_digits(cik)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{padded}.json"
    request = Request(url, headers={"User-Agent": user_agent, "Accept-Encoding": "identity"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _read_company_facts_file(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _write_company_facts_cache(path, payload):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False)
        os.replace(temporary_name, destination)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def load_company_facts(
    cik,
    user_agent=None,
    fixture_dir=None,
    cache_dir=None,
    max_age_hours=168,
    fetcher=None,
):
    padded = cik_to_10_digits(cik)
    if fixture_dir:
        fixture_path = Path(fixture_dir) / f"CIK{padded}.json"
        return _read_company_facts_file(fixture_path)

    cache_path = Path(cache_dir) / f"CIK{padded}.json" if cache_dir else None
    if cache_path and cache_path.exists():
        age_hours = (time.time() - cache_path.stat().st_mtime) / 3600
        if age_hours <= max_age_hours:
            return _read_company_facts_file(cache_path)

    fetch = fetcher or fetch_company_facts
    try:
        payload = fetch(padded, user_agent)
    except Exception:
        if cache_path and cache_path.exists():
            return _read_company_facts_file(cache_path)
        raise

    if cache_path:
        _write_company_facts_cache(cache_path, payload)
    return payload


def normalize_company_facts(company_facts, metadata):
    extracted = {}
    picked_facts = []
    for output_field, concepts in CONCEPTS.items():
        value, picked = latest_annual_usd_fact(company_facts, concepts)
        extracted[output_field] = value
        if picked:
            picked_facts.append(picked)

    capex_positive = extracted.get("capex_positive")
    capex = -abs(capex_positive) if capex_positive is not None else None
    assets = to_float(extracted.get("assets"))
    liabilities = to_float(extracted.get("liabilities"))
    debt_to_assets = liabilities / assets if assets not in (None, 0) and liabilities is not None else None
    net_assets = extracted.get("net_assets")
    net_income = extracted.get("net_income_ttm")
    roe = to_float(metadata.get("roe"))
    if roe is None and net_assets not in (None, 0) and net_income is not None:
        roe = net_income / net_assets

    latest_file_date = ""
    if picked_facts:
        latest_file_date = sorted(
            [item.get("filed", "") for item in picked_facts if item.get("filed")],
            reverse=True,
        )[0]

    row = {
        "market": metadata.get("market") or "美股",
        "ticker": metadata.get("ticker", ""),
        "company_name": metadata.get("company_name")
        or company_facts.get("entityName")
        or metadata.get("ticker", ""),
        "industry": metadata.get("industry", ""),
        "market_cap": metadata.get("market_cap", ""),
        "enterprise_value": metadata.get("enterprise_value", ""),
        "net_assets": net_assets,
        "revenue_ttm": extracted.get("revenue_ttm"),
        "net_income_ttm": net_income,
        "ebitda": metadata.get("ebitda", ""),
        "operating_cash_flow": extracted.get("operating_cash_flow"),
        "capex": capex,
        "dividend_yield": metadata.get("dividend_yield", ""),
        "industry_pe_median": metadata.get("industry_pe_median", ""),
        "industry_pb_median": metadata.get("industry_pb_median", ""),
        "industry_ev_ebitda_median": metadata.get("industry_ev_ebitda_median", ""),
        "roe": roe,
        "roic": metadata.get("roic", ""),
        "gross_margin": metadata.get("gross_margin", ""),
        "debt_to_assets": debt_to_assets,
        "net_debt_to_ebitda": metadata.get("net_debt_to_ebitda", ""),
        "current_ratio": metadata.get("current_ratio", ""),
        "revenue_cagr_3y": metadata.get("revenue_cagr_3y", ""),
        "net_income_cagr_3y": metadata.get("net_income_cagr_3y", ""),
        "audit_opinion": metadata.get("audit_opinion") or "标准无保留",
        "risk_flag": metadata.get("risk_flag") or "无",
        "source": "SEC Company Facts",
        "source_cik": cik_to_10_digits(company_facts.get("cik") or metadata.get("cik")),
        "source_filed": latest_file_date,
    }
    return row


def write_standard_csv(output_path, rows):
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=STANDARD_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_sec_import(
    config_path, output_path, user_agent=None, fixture_dir=None, cache_dir=None
):
    config_rows = load_sec_config(config_path)
    output_rows = []
    for metadata in config_rows:
        facts = load_company_facts(
            metadata["cik"],
            user_agent=user_agent,
            fixture_dir=fixture_dir,
            cache_dir=cache_dir,
        )
        output_rows.append(normalize_company_facts(facts, metadata))
    write_standard_csv(output_path, output_rows)
    return {"rows": len(output_rows), "output_path": Path(output_path)}


def main():
    parser = argparse.ArgumentParser(description="从 SEC Company Facts 导入美股财务数据。")
    parser.add_argument("--config", default="data/config/sec_us_companies.csv", help="SEC 公司配置 CSV")
    parser.add_argument("--output", default="data/raw/sec_us_stocks.csv", help="标准化输出 CSV")
    parser.add_argument("--user-agent", default=None, help="SEC 请求 User-Agent，建议包含邮箱")
    parser.add_argument("--fixture-dir", default=None, help="本地 Company Facts JSON 目录，用于离线测试")
    parser.add_argument("--cache-dir", default=None)
    args = parser.parse_args()

    result = run_sec_import(
        args.config,
        args.output,
        user_agent=args.user_agent,
        fixture_dir=args.fixture_dir,
        cache_dir=args.cache_dir,
    )
    print(f"已导入 SEC 公司数：{result['rows']}")
    print(f"输出文件：{result['output_path']}")


if __name__ == "__main__":
    main()
