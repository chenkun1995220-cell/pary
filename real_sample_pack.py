import argparse
import csv
from pathlib import Path


REQUIRED_COMPANY_FIELDS = ["ticker", "cik", "company_name", "industry"]
REQUIRED_QUOTE_FIELDS = [
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
ALLOWED_PRICE_UNITS = {"USD/share"}
ALLOWED_SHARE_UNITS = {"shares", "thousand_shares", "million_shares"}
ALLOWED_DEBT_UNITS = {"USD", "USD_thousand", "USD_million"}
QUOTE_VALUE_FIELDS = ["price", "shares_outstanding", "net_debt"]
QUOTE_METADATA_FIELDS = ["quote_source", "updated_at", "quote_date"]
REQUIRED_SAMPLE_TICKERS = {
    "AAPL": "320193",
    "MSFT": "789019",
    "GOOGL": "1652044",
}


def load_csv_rows(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return [
            {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(f)
        ]


def load_sample_companies(path):
    rows = []
    for row in load_csv_rows(path):
        ticker = row.get("ticker", "").upper()
        if ticker:
            clean = dict(row)
            clean["ticker"] = ticker
            rows.append(clean)
    return rows


def duplicate_values(rows, field):
    seen = set()
    duplicates = set()
    for row in rows:
        value = row.get(field, "").strip().upper()
        if not value:
            continue
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def conflicting_duplicate_ciks(rows):
    names_by_cik = {}
    for row in rows:
        cik = row.get("cik", "").strip()
        name = " ".join(row.get("company_name", "").upper().split())
        if cik:
            names_by_cik.setdefault(cik, set()).add(name)
    return {cik for cik, names in names_by_cik.items() if len(names) > 1}


def row_has_quote_values(row):
    return any(str(row.get(field, "")).strip() for field in QUOTE_VALUE_FIELDS)


def validate_quote_metadata(quotes):
    errors = []
    if not quotes:
        return errors, "missing_quotes"

    quote_fields = set(quotes[0].keys())
    missing_fields = [field for field in REQUIRED_QUOTE_FIELDS if field not in quote_fields]
    if missing_fields:
        errors.append("missing_quote_fields")
        return errors, "missing_fields"

    for row in quotes:
        price_unit = row.get("price_unit", "")
        shares_unit = row.get("shares_unit", "")
        debt_unit = row.get("debt_unit", "")
        if price_unit and price_unit not in ALLOWED_PRICE_UNITS:
            errors.append("invalid_quote_unit")
        if shares_unit and shares_unit not in ALLOWED_SHARE_UNITS:
            errors.append("invalid_quote_unit")
        if debt_unit and debt_unit not in ALLOWED_DEBT_UNITS:
            errors.append("invalid_quote_unit")
        if row_has_quote_values(row) and any(not row.get(field, "") for field in QUOTE_METADATA_FIELDS):
            errors.append("missing_quote_metadata")

    unique_errors = list(dict.fromkeys(errors))
    return unique_errors, "template_ready" if not unique_errors else "has_errors"


def validate_real_sample_pack(companies_path, quotes_path=None):
    errors = []
    companies = load_sample_companies(companies_path)
    company_fields = set(companies[0].keys()) if companies else set()
    missing_fields = [field for field in REQUIRED_COMPANY_FIELDS if field not in company_fields]
    if missing_fields:
        errors.append("missing_company_fields")

    tickers = sorted({row.get("ticker", "").upper() for row in companies if row.get("ticker")})
    by_ticker = {row.get("ticker", "").upper(): row for row in companies}
    for ticker, cik in REQUIRED_SAMPLE_TICKERS.items():
        if ticker not in by_ticker:
            errors.append(f"missing_required_ticker:{ticker}")
        elif by_ticker[ticker].get("cik") != cik:
            errors.append(f"wrong_cik:{ticker}")

    if duplicate_values(companies, "ticker"):
        errors.append("duplicate_ticker")
    if conflicting_duplicate_ciks(companies):
        errors.append("duplicate_cik")

    quote_tickers = []
    quote_metadata_status = "not_checked"
    if quotes_path:
        quotes = load_csv_rows(quotes_path)
        quote_errors, quote_metadata_status = validate_quote_metadata(quotes)
        errors.extend(quote_errors)
        quote_tickers = sorted(
            {row.get("ticker", "").strip().upper() for row in quotes if row.get("ticker")}
        )
        extra_quotes = sorted(set(quote_tickers) - set(tickers))
        missing_quotes = sorted(set(tickers) - set(quote_tickers))
        if extra_quotes:
            errors.append("extra_quote_ticker")
        if missing_quotes:
            errors.append("missing_quote_ticker")

    return {
        "ok": not errors,
        "errors": errors,
        "tickers": tickers,
        "quote_tickers": quote_tickers,
        "quote_metadata_status": quote_metadata_status,
    }


def main():
    parser = argparse.ArgumentParser(description="校验真实美股样本跑通包配置。")
    parser.add_argument("--companies", default="data/samples/us_real_sample_companies.csv")
    parser.add_argument("--quotes", default=None)
    args = parser.parse_args()

    result = validate_real_sample_pack(args.companies, args.quotes)
    if not result["ok"]:
        print("真实美股样本包校验失败：" + ", ".join(result["errors"]))
        raise SystemExit(1)
    print("真实美股样本包校验通过：" + ", ".join(result["tickers"]))


if __name__ == "__main__":
    main()
