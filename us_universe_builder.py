import argparse
import csv
import json
from pathlib import Path
from urllib.request import Request, urlopen


SEC_TICKER_EXCHANGE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"

OUTPUT_FIELDS = [
    "ticker",
    "cik",
    "company_name",
    "exchange",
    "industry",
    "market_cap",
    "enterprise_value",
    "ebitda",
    "industry_pe_median",
    "industry_pb_median",
    "industry_ev_ebitda_median",
    "roic",
    "gross_margin",
    "current_ratio",
    "revenue_cagr_3y",
    "net_income_cagr_3y",
    "dividend_yield",
    "audit_opinion",
    "risk_flag",
]

IDENTITY_AUDIT_FIELDS = [
    "ticker",
    "configured_cik",
    "sec_candidate_ciks",
    "selected_cik",
    "configured_company_name",
    "sec_candidate_names",
    "resolution",
]


def load_csv_rows(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return [
            {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(f)
        ]


def load_symbol_config(path):
    enabled_values = {"1", "true", "yes", "y"}
    return [
        row
        for row in load_csv_rows(path)
        if row.get("enabled", "1").strip().lower() in enabled_values
    ]


def fetch_sec_ticker_exchange(user_agent):
    if not user_agent:
        raise ValueError("SEC ticker 清单请求必须提供 User-Agent。")
    request = Request(
        SEC_TICKER_EXCHANGE_URL,
        headers={"User-Agent": user_agent, "Accept-Encoding": "identity"},
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def ticker_index(payload):
    fields = payload.get("fields", [])
    index = {}
    for values in payload.get("data", []):
        row = dict(zip(fields, values))
        ticker = str(row.get("ticker", "")).strip().upper()
        if ticker:
            index.setdefault(ticker, []).append(row)
    return index


def _normalized_cik(value):
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return str(int(text))
    except ValueError:
        return text.lstrip("0") or "0"


def build_universe_rows(symbols, payload):
    sec_by_ticker = ticker_index(payload)
    rows = []
    missing = []
    for symbol in symbols:
        ticker = symbol.get("ticker", "").strip().upper()
        if not ticker:
            continue
        sec_candidates = sec_by_ticker.get(ticker, [])
        if not sec_candidates:
            missing.append(ticker)
            continue
        configured_cik = _normalized_cik(symbol.get("cik"))
        exact_sec = next(
            (
                candidate
                for candidate in sec_candidates
                if configured_cik
                and _normalized_cik(candidate.get("cik")) == configured_cik
            ),
            None,
        )
        sec = exact_sec or sec_candidates[-1]
        selected_cik = configured_cik or _normalized_cik(sec.get("cik"))
        selected_name = str(sec.get("name", "")).strip()
        if configured_cik and exact_sec is None:
            selected_name = symbol.get("company_name", "").strip() or selected_name
        row = {field: "" for field in OUTPUT_FIELDS}
        row.update(
            {
                "ticker": ticker,
                "cik": selected_cik,
                "company_name": selected_name,
                "exchange": str(sec.get("exchange", "")).strip(),
                "industry": symbol.get("industry", "").strip(),
                "audit_opinion": "标准无保留",
                "risk_flag": "无",
            }
        )
        rows.append(row)
    return rows, sorted(missing)


def build_identity_audit_rows(symbols, payload, universe_rows):
    sec_by_ticker = ticker_index(payload)
    selected_by_ticker = {row.get("ticker", ""): row for row in universe_rows}
    audit_rows = []
    for symbol in symbols:
        ticker = symbol.get("ticker", "").strip().upper()
        configured_cik = _normalized_cik(symbol.get("cik"))
        candidates = sec_by_ticker.get(ticker, [])
        if not ticker or not configured_cik or not candidates:
            continue
        if any(_normalized_cik(candidate.get("cik")) == configured_cik for candidate in candidates):
            continue
        selected = selected_by_ticker.get(ticker, {})
        audit_rows.append(
            {
                "ticker": ticker,
                "configured_cik": configured_cik,
                "sec_candidate_ciks": ";".join(
                    sorted({_normalized_cik(candidate.get("cik")) for candidate in candidates})
                ),
                "selected_cik": _normalized_cik(selected.get("cik")),
                "configured_company_name": symbol.get("company_name", "").strip(),
                "sec_candidate_names": ";".join(
                    sorted({str(candidate.get("name", "")).strip() for candidate in candidates})
                ),
                "resolution": "configured_identity_preserved",
            }
        )
    return audit_rows


def write_identity_audit_csv(path, rows):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=IDENTITY_AUDIT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_company_csv(path, rows):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_universe_build(
    symbols_path,
    output_path,
    user_agent=None,
    fixture_path=None,
    minimum_match_rate=0,
    identity_audit_path=None,
):
    symbols = load_symbol_config(symbols_path)
    if fixture_path:
        payload = json.loads(Path(fixture_path).read_text(encoding="utf-8-sig"))
    else:
        payload = fetch_sec_ticker_exchange(user_agent)
    rows, missing = build_universe_rows(symbols, payload)
    identity_audit_rows = build_identity_audit_rows(symbols, payload, rows)
    configured = len([row for row in symbols if row.get("ticker", "").strip()])
    match_rate = len(rows) / configured if configured else 0
    if match_rate < minimum_match_rate:
        raise ValueError(
            f"SEC ticker match rate {match_rate:.2%} below required {minimum_match_rate:.2%}"
        )
    write_company_csv(output_path, rows)
    if identity_audit_path:
        write_identity_audit_csv(identity_audit_path, identity_audit_rows)
    return {
        "rows": len(rows),
        "missing": missing,
        "match_rate": match_rate,
        "output_path": Path(output_path),
        "identity_conflict_count": len(identity_audit_rows),
        "identity_audit_path": Path(identity_audit_path) if identity_audit_path else None,
    }


def main():
    parser = argparse.ArgumentParser(description="从 SEC 官方 ticker 清单构建美股样本池。")
    parser.add_argument("--symbols", default="data/config/us_universe_symbols.csv")
    parser.add_argument("--output", default="data/samples/us_universe_companies.csv")
    parser.add_argument("--user-agent", default=None)
    parser.add_argument("--fixture", default=None)
    parser.add_argument("--minimum-match-rate", type=float, default=0.98)
    parser.add_argument("--identity-audit", default=None)
    args = parser.parse_args()

    result = run_universe_build(
        args.symbols,
        args.output,
        user_agent=args.user_agent,
        fixture_path=args.fixture,
        minimum_match_rate=args.minimum_match_rate,
        identity_audit_path=args.identity_audit,
    )
    print(f"已构建美股公司数：{result['rows']}")
    print(f"SEC 清单未命中：{', '.join(result['missing']) or '无'}")
    print(f"输出文件：{result['output_path']}")


if __name__ == "__main__":
    main()
