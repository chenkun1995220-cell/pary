import argparse
import csv
import html
import json
import re
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
REVENUE_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
]
NET_INCOME_CONCEPTS = ["NetIncomeLoss", "ProfitLoss"]
MIN_REUSABLE_SHARES_MILLIONS = 0.01
MIN_MARKET_CAP_TO_REVENUE = 0.02
MIN_MARKET_CAP_TO_NET_INCOME = 1.0
DEFAULT_SHARE_OVERRIDES_PATH = "data/manual/us_share_overrides.csv"
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
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
SEC_DEFAULT_USER_AGENT = "stock-screening-tool/0.1"
SEC_SHARE_TEXT_PATTERNS = [
    re.compile(
        r"shares of common stock outstanding as of (?:the )?(?:record date|[a-z0-9,\s]+?)\s+([0-9][0-9,]*)",
        re.IGNORECASE,
    ),
    re.compile(
        r"shares of (?:the )?common stock issued and outstanding.{0,220}?equal to\s+([0-9][0-9,]*)",
        re.IGNORECASE,
    ),
]
SEC_SHARE_FORM_SKIP_PREFIXES = ("3", "4", "5", "144", "SC ", "SCHEDULE")


def latest_fact_candidate(company_facts, taxonomy, concept_names, unit, taxonomy_priority=0):
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
                    "taxonomy_priority": taxonomy_priority,
                }
            )
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (item["fy"], item["filed"], item["end"], item["taxonomy_priority"]),
        reverse=True,
    )
    return candidates[0]


def latest_fact_value(company_facts, taxonomy, concept_names, unit):
    candidate = latest_fact_candidate(company_facts, taxonomy, concept_names, unit)
    if candidate is None:
        return None
    return candidate["value"]


def latest_share_fact_value(company_facts):
    candidates = [
        latest_fact_candidate(company_facts, "dei", SHARES_CONCEPTS, "shares", taxonomy_priority=1),
        latest_fact_candidate(company_facts, "us-gaap", US_GAAP_SHARES_CONCEPTS, "shares", taxonomy_priority=0),
    ]
    candidates = [candidate for candidate in candidates if candidate is not None]
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (item["fy"], item["filed"], item["end"], item["taxonomy_priority"]),
        reverse=True,
    )
    return candidates[0]["value"]


def extract_shares_outstanding(company_facts):
    return latest_share_fact_value(company_facts)


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


def numeric(value):
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def latest_usd_value(company_facts, concept_names):
    return latest_fact_value(company_facts, "us-gaap", concept_names, "USD")


def shares_pass_sanity_check(price, shares, company_facts):
    price_value = numeric(price)
    shares_value = numeric(shares)
    if price_value is None or shares_value is None or shares_value <= 0:
        return True
    implied_market_cap = price_value * shares_value
    revenue = latest_usd_value(company_facts, REVENUE_CONCEPTS)
    net_income = latest_usd_value(company_facts, NET_INCOME_CONCEPTS)
    if revenue is not None and revenue > 0 and implied_market_cap / revenue < MIN_MARKET_CAP_TO_REVENUE:
        return False
    if net_income is not None and net_income > 0 and implied_market_cap / net_income < MIN_MARKET_CAP_TO_NET_INCOME:
        return False
    return True


def read_price_fixture(price_fixture_dir, ticker):
    if not price_fixture_dir:
        return None
    fixture_path = Path(price_fixture_dir) / f"{ticker.upper()}.csv"
    return fixture_path.read_text(encoding="utf-8-sig")


def load_fresh_quotes(path, as_of_date=None, max_age_days=7, manual_override_tickers=None):
    output = Path(path)
    if not output.exists():
        return {}
    as_of_date = as_of_date or date.today()
    manual_override_tickers = {ticker.upper() for ticker in (manual_override_tickers or set())}
    fresh = {}
    with output.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            ticker = row.get("ticker", "").upper()
            if "Manual share override" in row.get("quote_source", "") and ticker not in manual_override_tickers:
                continue
            try:
                quote_date = date.fromisoformat(row.get("quote_date", ""))
                age = (as_of_date - quote_date).days
            except (TypeError, ValueError):
                continue
            shares = numeric(row.get("shares_outstanding"))
            if (
                0 <= age <= max_age_days
                and row.get("price")
                and shares is not None
                and shares >= MIN_REUSABLE_SHARES_MILLIONS
            ):
                fresh[ticker] = row
    return fresh


def load_share_overrides(path):
    override_path = Path(path)
    if not path or not override_path.exists():
        return {}
    overrides = {}
    with override_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            ticker = row.get("ticker", "").strip().upper()
            shares = numeric(row.get("shares_outstanding"))
            if not ticker or shares is None or shares <= 0:
                continue
            unit = row.get("shares_unit", "million_shares").strip().lower()
            if unit in ("shares", "share"):
                raw_shares = shares
            else:
                raw_shares = shares * 1_000_000
            if raw_shares / 1_000_000 < MIN_REUSABLE_SHARES_MILLIONS:
                continue
            overrides[ticker] = {
                "shares": raw_shares,
                "source": row.get("source", "").strip() or "manual review",
                "source_url": row.get("source_url", "").strip(),
                "as_of_date": row.get("as_of_date", "").strip(),
                "note": row.get("note", "").strip(),
            }
    return overrides


def normalize_sec_text(text):
    plain = html.unescape(str(text or ""))
    plain = re.sub(r"<[^>]+>", " ", plain)
    return re.sub(r"\s+", " ", plain)


def extract_shares_from_sec_filing_text(text):
    plain = normalize_sec_text(text)
    for pattern in SEC_SHARE_TEXT_PATTERNS:
        match = pattern.search(plain)
        if match:
            return int(match.group(1).replace(",", ""))
    return None


def sec_request(url, user_agent=None):
    return Request(url, headers={"User-Agent": user_agent or SEC_DEFAULT_USER_AGENT})


def fetch_sec_submission_shares(cik, user_agent=None, max_filings=40):
    cik_text = str(cik).strip().zfill(10)
    with urlopen(sec_request(SEC_SUBMISSIONS_URL.format(cik=cik_text), user_agent), timeout=30) as response:
        submission = json.loads(response.read().decode("utf-8"))

    recent = submission.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accession_numbers = recent.get("accessionNumber", [])
    primary_documents = recent.get("primaryDocument", [])
    filing_dates = recent.get("filingDate", [])

    for index, form in enumerate(forms[:max_filings]):
        form_text = str(form or "").upper()
        if form_text.startswith(SEC_SHARE_FORM_SKIP_PREFIXES):
            continue
        accession = accession_numbers[index].replace("-", "")
        document = primary_documents[index]
        if not accession or not document:
            continue
        url = SEC_ARCHIVE_URL.format(cik=int(cik_text), accession=accession, document=document)
        with urlopen(sec_request(url, user_agent), timeout=30) as response:
            text = response.read().decode("utf-8", "replace")
        shares = extract_shares_from_sec_filing_text(text)
        if shares is not None:
            filing_date = filing_dates[index] if index < len(filing_dates) else ""
            return {
                "shares": shares,
                "source": f"SEC filing text ({form_text} {filing_date})",
                "url": url,
            }
    return {}


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


def combine_sources(*sources):
    combined = []
    seen = set()
    for source in sources:
        for part in str(source or "").split(";"):
            text = part.strip()
            if not text or text in seen:
                continue
            combined.append(text)
            seen.add(text)
    return "; ".join(combined)


def build_quote_row(
    company,
    company_facts,
    price_csv_text=None,
    quote_override=None,
    fallback_shares=None,
    fallback_share_source=None,
    share_override=None,
):
    ticker = company.get("ticker", "").strip().upper()
    quote = quote_override or fetch_price_quote(ticker, price_csv_text=price_csv_text)
    shares = extract_shares_outstanding(company_facts)
    share_source = "SEC Company Facts"
    if shares is None and fallback_shares is not None:
        shares = fallback_shares
        share_source = fallback_share_source or "SEC filing text"
    if shares is not None and not shares_pass_sanity_check(quote.get("price", ""), shares, company_facts):
        shares = None
        share_source = f"{share_source} share sanity failed"
    if share_override:
        shares = share_override.get("shares")
        override_source = share_override.get("source") or "manual review"
        share_source = f"Manual share override ({override_source})"
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
        "quote_source": combine_sources(quote.get("quote_source", "price source"), "SEC Company Facts", share_source),
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
    share_overrides_path=DEFAULT_SHARE_OVERRIDES_PATH,
):
    companies = load_sec_config(companies_path)
    share_overrides = load_share_overrides(share_overrides_path)
    cached_quotes = (
        {}
        if price_fixture_dir
        else load_fresh_quotes(
            output_path,
            as_of_date,
            quote_max_age_days,
            manual_override_tickers=set(share_overrides),
        )
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
        fallback = {}
        if not fixture_dir and extract_shares_outstanding(facts) is None:
            try:
                fallback = fetch_sec_submission_shares(company["cik"], user_agent=user_agent)
            except Exception:
                fallback = {}
        prepared.append(
            (
                company,
                facts,
                price_csv_text,
                cached_quotes.get(company["ticker"].strip().upper()),
                fallback.get("shares"),
                fallback.get("source"),
                share_overrides.get(company["ticker"].strip().upper()),
            )
        )

    def build(prepared_row):
        (
            company,
            facts,
            price_csv_text,
            quote_override,
            fallback_shares,
            fallback_share_source,
            share_override,
        ) = prepared_row
        return build_quote_row(
            company,
            facts,
            price_csv_text=price_csv_text,
            quote_override=quote_override,
            fallback_shares=fallback_shares,
            fallback_share_source=fallback_share_source,
            share_override=share_override,
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
    parser.add_argument("--share-overrides", default=DEFAULT_SHARE_OVERRIDES_PATH)
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
        share_overrides_path=args.share_overrides,
    )
    print(f"已自动补齐行情行数：{result['rows']}")
    print(f"输出文件：{result['output_path']}")


if __name__ == "__main__":
    main()
