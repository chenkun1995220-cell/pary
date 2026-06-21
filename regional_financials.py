import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


FINANCIAL_URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
REPORT_NAMES = {
    "CN": "RPT_F10_FINANCE_MAINFINADATA",
    "HK": "RPT_HKF10_FN_MAININDICATOR",
}


def build_financial_url(market, tickers, periods_per_company=8):
    market = market.upper()
    if market not in REPORT_NAMES:
        raise ValueError("market must be CN or HK")
    quoted = ",".join(f'"{ticker}"' for ticker in tickers)
    query = urlencode(
        {
            "reportName": REPORT_NAMES[market],
            "columns": "ALL",
            "filter": f"(SECUCODE in ({quoted}))",
            "pageNumber": 1,
            "pageSize": max(20, len(tickers) * periods_per_company),
            "sortTypes": -1,
            "sortColumns": "REPORT_DATE",
            "source": "HSF10" if market == "CN" else "F10",
            "client": "PC",
        }
    )
    return f"{FINANCIAL_URL}?{query}"


def fetch_financial_batch(market, tickers):
    request = Request(
        build_financial_url(market, tickers),
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://emweb.securities.eastmoney.com/",
        },
    )
    with urlopen(request, timeout=45) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("success") or not payload.get("result"):
        raise ValueError(f"financial batch request failed: {payload.get('message')}")
    return payload


def _number(value):
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ratio(value):
    number = _number(value)
    return number / 100 if number is not None else None


def normalize_financial_records(market, records):
    market = market.upper()
    latest = {}
    for record in records:
        ticker = str(record.get("SECUCODE", "")).upper()
        report_date = str(record.get("REPORT_DATE") or record.get("STD_REPORT_DATE") or "")
        if not ticker:
            continue
        previous = latest.get(ticker)
        if previous is None or report_date > str(
            previous.get("REPORT_DATE") or previous.get("STD_REPORT_DATE") or ""
        ):
            latest[ticker] = record

    rows = []
    for ticker, record in latest.items():
        if market == "CN":
            mapped = {
                "revenue": _number(record.get("TOTALOPERATEREVE")),
                "net_income": _number(record.get("PARENTNETPROFIT")),
                "operating_cash_flow": _number(record.get("NETCASH_OPERATE_PK")),
                "roe": _ratio(record.get("ROEJQ")),
                "roic": _ratio(record.get("ROIC")),
                "gross_margin": _ratio(record.get("XSMLL")),
                "current_ratio": _number(record.get("LD")),
                "debt_to_assets": _ratio(record.get("ZCFZL")),
                "revenue_growth": _ratio(record.get("TOTALOPERATEREVETZ")),
                "net_income_growth": _ratio(record.get("PARENTNETPROFITTZ")),
            }
        else:
            mapped = {
                "revenue": _number(record.get("OPERATE_INCOME")),
                "net_income": _number(record.get("HOLDER_PROFIT")),
                "operating_cash_flow": _number(record.get("NETCASH_OPERATE")),
                "roe": _ratio(record.get("ROE_YEARLY")),
                "roic": _ratio(record.get("ROIC_YEARLY")),
                "gross_margin": _ratio(record.get("GROSS_PROFIT_RATIO")),
                "current_ratio": _number(record.get("CURRENT_RATIO")),
                "debt_to_assets": _ratio(record.get("DEBT_ASSET_RATIO")),
                "revenue_growth": _ratio(record.get("OPERATE_INCOME_YOY")),
                "net_income_growth": _ratio(record.get("HOLDER_PROFIT_YOY")),
            }
        row = {
            "ticker": ticker,
            "financial_report_date": str(
                record.get("REPORT_DATE") or record.get("STD_REPORT_DATE") or ""
            )[:10],
            "financial_period_basis": record.get("REPORT_TYPE", ""),
            "financial_source": "Eastmoney financial indicators",
        }
        row.update({key: value if value is not None else "" for key, value in mapped.items()})
        rows.append(row)
    return rows


def load_csv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_regional_financials(
    market,
    snapshot_path,
    output_path,
    raw_cache_path,
    fetcher=None,
    batch_size=20,
    minimum_coverage=0.8,
):
    snapshot_rows = load_csv(snapshot_path)
    fetch = fetcher or fetch_financial_batch
    financial_rows = []
    payloads = []
    for start in range(0, len(snapshot_rows), batch_size):
        tickers = [row["ticker"] for row in snapshot_rows[start : start + batch_size]]
        payload = fetch(market, tickers)
        payloads.append(payload)
        records = (payload.get("result") or {}).get("data") or []
        financial_rows.extend(normalize_financial_records(market, records))

    by_ticker = {row["ticker"]: row for row in financial_rows}
    merged = []
    ready = 0
    for snapshot in snapshot_rows:
        row = dict(snapshot)
        financial = by_ticker.get(snapshot.get("ticker"))
        if financial:
            row.update(financial)
            row["financial_data_status"] = "ready"
            ready += 1
        else:
            row["financial_data_status"] = "missing"
        merged.append(row)

    coverage = ready / len(snapshot_rows) if snapshot_rows else 0
    if coverage < minimum_coverage:
        raise ValueError(
            f"regional financial coverage {coverage:.2%} below required {minimum_coverage:.2%}"
        )
    write_csv(output_path, merged)
    raw_cache = Path(raw_cache_path)
    raw_cache.parent.mkdir(parents=True, exist_ok=True)
    raw_cache.write_text(
        json.dumps(payloads, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {
        "rows": len(merged),
        "financial_rows": ready,
        "coverage": coverage,
        "output_path": Path(output_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Build regional financial quality snapshot")
    parser.add_argument("--market", required=True, choices=["CN", "HK"])
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--raw-cache", required=True)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--minimum-coverage", type=float, default=0.8)
    args = parser.parse_args()
    result = run_regional_financials(
        args.market,
        args.snapshot,
        args.output,
        args.raw_cache,
        batch_size=args.batch_size,
        minimum_coverage=args.minimum_coverage,
    )
    print(f"Financial rows: {result['financial_rows']}/{result['rows']}")
    print(f"Financial coverage: {result['coverage']:.2%}")


if __name__ == "__main__":
    main()
