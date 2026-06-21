import argparse
import csv
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sec_edgar_adapter import load_company_facts, load_sec_config
from us_market_data_enricher import fetch_stooq_quote


QUOTE_FIELDS = [
    "ticker",
    "price",
    "shares_outstanding",
    "net_debt",
    "currency",
    "quote_date",
    "price_unit",
    "shares_unit",
    "debt_unit",
    "quote_source",
    "updated_at",
]

SHARES_CONCEPTS = ["EntityCommonStockSharesOutstanding"]
US_GAAP_SHARES_CONCEPTS = [
    "CommonStockSharesOutstanding",
    "WeightedAverageNumberOfDilutedSharesOutstanding",
    "WeightedAverageNumberOfSharesOutstandingBasic",
]
DEBT_CONCEPT_GROUPS = [
    [
        "LongTermDebtAndFinanceLeaseObligationsCurrent",
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
    ],
    ["LongTermDebtCurrent", "LongTermDebtNoncurrent"],
    ["ShortTermBorrowings", "LongTermDebt"],
    ["LongTermDebtAndFinanceLeaseObligations"],
    ["LongTermDebt"],
]
CASH_CONCEPTS = [
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
]


def latest_fact_value(company_facts, taxonomy, concept_names, unit):
    facts = company_facts.get("facts", {}).get(taxonomy, {})
    candidates = []
    for concept in concept_names:
        for fact in facts.get(concept, {}).get("units", {}).get(unit, []):
            if fact.get("val") is None:
                continue
            candidates.append(
                {
                    "value": fact.get("val"),
                    "filed": fact.get("filed") or "",
                    "fy": fact.get("fy") or 0,
                    "end": fact.get("end") or "",
                }
            )
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item["fy"], item["filed"], item["end"]), reverse=True)
    return candidates[0]["value"]


def extract_shares_outstanding(company_facts):
    return latest_fact_value(
        company_facts, "dei", SHARES_CONCEPTS, "shares"
    ) or latest_fact_value(
        company_facts, "us-gaap", US_GAAP_SHARES_CONCEPTS, "shares"
    )


def extract_debt(company_facts):
    for concept_group in DEBT_CONCEPT_GROUPS:
        values = [
            latest_fact_value(company_facts, "us-gaap", [concept], "USD")
            for concept in concept_group
        ]
        if all(value is not None for value in values):
            return sum(values)
    return None


def extract_cash(company_facts):
    return latest_fact_value(company_facts, "us-gaap", CASH_CONCEPTS, "USD")


def extract_net_debt(company_facts):
    debt = extract_debt(company_facts)
    cash = extract_cash(company_facts)
    if debt is None or cash is None:
        return None
    return debt - cash


def read_price_fixture(price_fixture_dir, ticker):
    if not price_fixture_dir:
        return None
    fixture_path = Path(price_fixture_dir) / f"{ticker.upper()}.csv"
    return fixture_path.read_text(encoding="utf-8-sig")


def load_fresh_quotes(path, as_of_date=None, max_age_days=7):
    output = Path(path)
    if not output.exists():
        return {}
    as_of_date = as_of_date or date.today()
    fresh = {}
    with output.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                quote_date = date.fromisoformat(row.get("quote_date", ""))
                age = (as_of_date - quote_date).days
            except (TypeError, ValueError):
                continue
            if 0 <= age <= max_age_days and row.get("price"):
                fresh[row.get("ticker", "").upper()] = row
    return fresh


def parse_yahoo_chart_quote(ticker, payload):
    result = payload.get("chart", {}).get("result", [None])[0]
    if not result:
        raise ValueError(f"Yahoo Finance chart 未返回 {ticker} 的价格。")
    timestamps = result.get("timestamp", [])
    closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
    candidates = [
        (timestamp, close)
        for timestamp, close in zip(timestamps, closes)
        if timestamp is not None and close is not None
    ]
    if not candidates:
        raise ValueError(f"Yahoo Finance chart 缺少 {ticker} 的有效收盘价。")
    timestamp, close = candidates[-1]
    quote_date = date.fromtimestamp(timestamp).isoformat()
    return {
        "ticker": ticker.upper(),
        "price": float(close),
        "quote_date": quote_date,
        "quote_source": "Yahoo Finance chart",
    }


def fetch_yahoo_chart_quote(ticker):
    query = urlencode({"range": "5d", "interval": "1d"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker.upper()}?{query}"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return parse_yahoo_chart_quote(ticker, payload)


def fetch_price_quote(ticker, price_csv_text=None):
    if price_csv_text is not None:
        return fetch_stooq_quote(ticker, csv_text=price_csv_text)
    try:
        return fetch_yahoo_chart_quote(ticker)
    except Exception:
        return fetch_stooq_quote(ticker)


def millions(value):
    if value is None:
        return ""
    return round(float(value) / 1_000_000, 6)


def build_quote_row(company, company_facts, price_csv_text=None, quote_override=None):
    ticker = company.get("ticker", "").strip().upper()
    quote = quote_override or fetch_price_quote(ticker, price_csv_text=price_csv_text)
    shares = extract_shares_outstanding(company_facts)
    net_debt = extract_net_debt(company_facts)
    return {
        "ticker": ticker,
        "price": quote.get("price", ""),
        "shares_outstanding": millions(shares),
        "net_debt": millions(net_debt),
        "currency": "USD",
        "quote_date": quote.get("quote_date", ""),
        "price_unit": "USD/share",
        "shares_unit": "million_shares",
        "debt_unit": "USD_million",
        "quote_source": f"{quote.get('quote_source', 'price source')}; SEC Company Facts",
        "updated_at": date.today().isoformat(),
    }


def write_quote_csv(path, rows):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=QUOTE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_auto_fill_quotes(
    companies_path,
    output_path,
    user_agent=None,
    fixture_dir=None,
    price_fixture_dir=None,
    cache_dir=None,
    as_of_date=None,
    quote_max_age_days=7,
    max_workers=12,
):
    companies = load_sec_config(companies_path)
    cached_quotes = (
        {} if price_fixture_dir else load_fresh_quotes(output_path, as_of_date, quote_max_age_days)
    )
    prepared = []
    for company in companies:
        facts = load_company_facts(
            company["cik"],
            user_agent=user_agent,
            fixture_dir=fixture_dir,
            cache_dir=cache_dir,
        )
        price_csv_text = read_price_fixture(price_fixture_dir, company["ticker"])
        prepared.append(
            (company, facts, price_csv_text, cached_quotes.get(company["ticker"].strip().upper()))
        )

    def build(prepared_row):
        company, facts, price_csv_text, quote_override = prepared_row
        return build_quote_row(
            company,
            facts,
            price_csv_text=price_csv_text,
            quote_override=quote_override,
        )

    worker_count = max(1, min(int(max_workers), 32))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        rows = list(executor.map(build, prepared))
    write_quote_csv(output_path, rows)
    return {"rows": len(rows), "output_path": Path(output_path)}


def main():
    parser = argparse.ArgumentParser(description="自动补齐美股样本行情、股本和净债务。")
    parser.add_argument("--companies", default="data/samples/us_real_sample_companies.csv")
    parser.add_argument("--output", default="data/samples/us_real_sample_quotes.csv")
    parser.add_argument("--user-agent", default=None)
    parser.add_argument("--fixture-dir", default=None)
    parser.add_argument("--price-fixture-dir", default=None)
    parser.add_argument("--cache-dir", default=None)
    parser.add_argument("--max-workers", type=int, default=12)
    args = parser.parse_args()

    result = run_auto_fill_quotes(
        args.companies,
        args.output,
        user_agent=args.user_agent,
        fixture_dir=args.fixture_dir,
        price_fixture_dir=args.price_fixture_dir,
        cache_dir=args.cache_dir,
        max_workers=args.max_workers,
    )
    print(f"已自动补齐行情行数：{result['rows']}")
    print(f"输出文件：{result['output_path']}")


if __name__ == "__main__":
    main()
