import argparse
import csv
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ENRICHED_FIELDS = [
    "market",
    "ticker",
    "company_name",
    "industry",
    "currency",
    "quote_date",
    "price",
    "shares_outstanding",
    "price_unit",
    "shares_unit",
    "market_cap",
    "net_debt",
    "debt_unit",
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
    "quote_source",
    "updated_at",
]


SHARE_UNIT_MULTIPLIERS = {
    "shares": 1,
    "thousand_shares": 1_000,
    "million_shares": 1_000_000,
}
DEBT_UNIT_MULTIPLIERS = {
    "USD": 1,
    "USD_thousand": 1_000,
    "USD_million": 1_000_000,
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


def load_csv_rows(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return [{key.strip(): value for key, value in row.items() if key is not None} for row in csv.DictReader(f)]


def load_quotes(path):
    quotes = {}
    for row in load_csv_rows(path):
        ticker = row.get("ticker", "").strip().upper()
        if ticker:
            quotes[ticker] = row
    return quotes


def normalize_by_unit(value, unit, multipliers):
    number = to_float(value)
    if number is None:
        return None
    multiplier = multipliers.get(str(unit or "").strip(), 1)
    return number * multiplier


def fetch_stooq_quote(ticker, csv_text=None):
    symbol = f"{ticker.lower()}.us"
    if csv_text is None:
        query = urlencode({"s": symbol, "i": "d"})
        url = f"https://stooq.com/q/l/?{query}"
        request = Request(url, headers={"User-Agent": "stock-screening-tool/0.1"})
        with urlopen(request, timeout=30) as response:
            csv_text = response.read().decode("utf-8")

    rows = list(csv.DictReader(csv_text.splitlines()))
    if not rows:
        raise ValueError(f"未获得 {ticker} 的 Stooq 行情。")
    row = rows[0]
    close = to_float(row.get("Close"))
    if close is None:
        raise ValueError(f"Stooq 行情缺少 {ticker} 的 Close 字段。")
    return {
        "ticker": ticker.upper(),
        "price": close,
        "quote_date": row.get("Date", ""),
        "quote_source": "Stooq delayed CSV",
    }


def enrich_rows(rows, quotes):
    enriched = []
    for row in rows:
        out = dict(row)
        ticker = out.get("ticker", "").strip().upper()
        quote = quotes.get(ticker, {})
        price = to_float(quote.get("price") if quote else out.get("price"))
        shares = normalize_by_unit(
            quote.get("shares_outstanding") if quote else out.get("shares_outstanding"),
            quote.get("shares_unit") if quote else out.get("shares_unit"),
            SHARE_UNIT_MULTIPLIERS,
        )
        net_debt = normalize_by_unit(
            quote.get("net_debt") if quote else out.get("net_debt"),
            quote.get("debt_unit") if quote else out.get("debt_unit"),
            DEBT_UNIT_MULTIPLIERS,
        )
        existing_market_cap = to_float(out.get("market_cap"))
        market_cap = price * shares if price is not None and shares is not None else existing_market_cap
        existing_ev = to_float(out.get("enterprise_value"))
        enterprise_value = (
            market_cap + net_debt
            if market_cap is not None and net_debt is not None
            else existing_ev
        )

        if quote:
            out["price"] = price
            out["shares_outstanding"] = shares
            out["net_debt"] = net_debt
            out["currency"] = quote.get("currency") or out.get("currency") or "USD"
            out["quote_date"] = quote.get("quote_date", "")
            out["quote_source"] = quote.get("quote_source") or "local quotes CSV"
            out["updated_at"] = quote.get("updated_at", "")
            out["price_unit"] = quote.get("price_unit", "")
            out["shares_unit"] = quote.get("shares_unit", "")
            out["debt_unit"] = quote.get("debt_unit", "")
        if market_cap is not None:
            out["market_cap"] = market_cap
        if enterprise_value is not None:
            out["enterprise_value"] = enterprise_value
        enriched.append(out)
    return enriched


def write_enriched_csv(path, rows):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    all_fields = list(ENRICHED_FIELDS)
    for row in rows:
        for key in row:
            if key not in all_fields:
                all_fields.append(key)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_market_enrichment(input_path, quote_path, output_path):
    rows = load_csv_rows(input_path)
    quotes = load_quotes(quote_path)
    enriched = enrich_rows(rows, quotes)
    write_enriched_csv(output_path, enriched)
    return {"rows": len(enriched), "output_path": Path(output_path)}


def main():
    parser = argparse.ArgumentParser(description="用美股行情/股本数据补齐市值和企业价值。")
    parser.add_argument("--input", default="data/raw/sec_us_stocks.csv", help="待补充的标准 CSV")
    parser.add_argument("--quotes", default="data/config/us_market_quotes.csv", help="行情/股本补充 CSV")
    parser.add_argument("--output", default="data/raw/us_stocks_enriched.csv", help="补充后输出 CSV")
    args = parser.parse_args()

    result = run_market_enrichment(args.input, args.quotes, args.output)
    print(f"已补充美股行情/市值行数：{result['rows']}")
    print(f"输出文件：{result['output_path']}")


if __name__ == "__main__":
    main()
