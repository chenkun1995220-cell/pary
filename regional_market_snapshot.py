import argparse
import csv
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


EASTMONEY_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
EASTMONEY_UT = "f057cbcbce2a86e2866ab8877db1d059"
FIELDS = "f2,f9,f12,f14,f20,f23,f37,f100"
OUTPUT_FIELDS = [
    "market",
    "ticker",
    "company_name",
    "industry",
    "index_name",
    "currency",
    "price",
    "market_cap",
    "pe",
    "pb",
    "roe",
    "quote_date",
    "source",
    "data_quality_status",
]


def ticker_to_secid(ticker):
    ticker = str(ticker).strip().upper()
    if ticker.endswith(".SH"):
        return f"1.{ticker[:-3]}"
    if ticker.endswith(".SZ"):
        return f"0.{ticker[:-3]}"
    if ticker.endswith(".HK"):
        return f"116.{ticker[:-3].zfill(5)}"
    raise ValueError(f"unsupported regional ticker: {ticker}")


def _number(value):
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_eastmoney_snapshot(payload, companies, quote_date=None):
    quotes = {
        str(item.get("f12", "")).zfill(5 if len(str(item.get("f12", ""))) <= 5 else 6): item
        for item in (payload.get("data") or {}).get("diff", [])
        if item.get("f12") is not None
    }
    rows = []
    missing = []
    for company in companies:
        raw_ticker = str(company.get("raw_ticker", "")).strip()
        quote = quotes.get(raw_ticker)
        if not quote:
            missing.append(company.get("ticker", ""))
            continue
        price = _number(quote.get("f2"))
        market_cap = _number(quote.get("f20"))
        pe = _number(quote.get("f9"))
        pb = _number(quote.get("f23"))
        roe_percent = _number(quote.get("f37"))
        rows.append(
            {
                "market": company.get("market", ""),
                "ticker": company.get("ticker", ""),
                "company_name": company.get("company_name") or quote.get("f14", ""),
                "industry": company.get("industry") or quote.get("f100", ""),
                "index_name": company.get("index_name", ""),
                "currency": company.get("currency", ""),
                "price": price if price is not None else "",
                "market_cap": market_cap if market_cap is not None else "",
                "pe": pe if pe is not None else "",
                "pb": pb if pb is not None else "",
                "roe": roe_percent / 100 if roe_percent is not None else "",
                "quote_date": quote_date or date.today().isoformat(),
                "source": "Eastmoney batch quote",
                "data_quality_status": "ready"
                if all(value is not None and value > 0 for value in (price, market_cap, pe, pb))
                else "partial",
            }
        )
    return rows, missing


def fetch_eastmoney_batch(secids):
    query = urlencode(
        {
            "fltt": "2",
            "invt": "2",
            "ut": EASTMONEY_UT,
            "secids": ",".join(secids),
            "fields": FIELDS,
        }
    )
    request = Request(
        f"{EASTMONEY_URL}?{query}",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://quote.eastmoney.com/",
        },
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("rc") != 0 or not payload.get("data"):
        raise ValueError(f"Eastmoney batch request failed: rc={payload.get('rc')}")
    return payload


def load_companies(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_snapshot(path, rows):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_market_snapshot(
    companies_path,
    output_path,
    raw_cache_path,
    fetcher=None,
    batch_size=50,
    quote_date=None,
    minimum_coverage=0,
):
    companies = load_companies(companies_path)
    fetch = fetcher or fetch_eastmoney_batch
    rows = []
    missing = []
    payloads = []
    for start in range(0, len(companies), batch_size):
        batch = companies[start : start + batch_size]
        payload = fetch([ticker_to_secid(row["ticker"]) for row in batch])
        payloads.append(payload)
        parsed, batch_missing = parse_eastmoney_snapshot(
            payload, batch, quote_date=quote_date
        )
        rows.extend(parsed)
        missing.extend(batch_missing)

    coverage = len(rows) / len(companies) if companies else 0
    if coverage < minimum_coverage:
        raise ValueError(
            f"regional market snapshot coverage {coverage:.2%} below required {minimum_coverage:.2%}"
        )
    write_snapshot(output_path, rows)
    raw_cache = Path(raw_cache_path)
    raw_cache.parent.mkdir(parents=True, exist_ok=True)
    raw_cache.write_text(
        json.dumps(payloads, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {
        "rows": len(rows),
        "missing": missing,
        "coverage": coverage,
        "output_path": Path(output_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Build CN or HK market valuation snapshot")
    parser.add_argument("--companies", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--raw-cache", required=True)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--minimum-coverage", type=float, default=0.95)
    args = parser.parse_args()

    result = run_market_snapshot(
        args.companies,
        args.output,
        args.raw_cache,
        batch_size=args.batch_size,
        minimum_coverage=args.minimum_coverage,
    )
    print(f"Snapshot rows: {result['rows']}")
    print(f"Coverage: {result['coverage']:.2%}")
    print(f"Missing tickers: {', '.join(result['missing']) or 'None'}")


if __name__ == "__main__":
    main()
