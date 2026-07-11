import argparse
import csv
import io
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


CSI300_URL = "https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/cons/000300cons.xls"
HK_SIZE_URL = "https://www.hsi.com.hk/data/eng/rt/index-series/sizeindexes/constituents.do"

# HKEX temporary counter used during Hesai's July-August 2026 share subdivision.
HK_TEMPORARY_COUNTER_ALIASES = {("02983", "HESAI - W"): "02525"}

OUTPUT_FIELDS = [
    "market",
    "ticker",
    "raw_ticker",
    "company_name",
    "industry",
    "index_name",
    "currency",
    "exchange",
    "enabled",
]


def _clean(value):
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _normalize_hk_counter(constituent):
    code = re.sub(r"\D", "", str(constituent.get("code", ""))).zfill(5)
    company_name = _clean(constituent.get("constituentName"))
    return HK_TEMPORARY_COUNTER_ALIASES.get((code, company_name.upper()), code)


def _find_value(record, candidates):
    for key, value in record.items():
        normalized = re.sub(r"\s+", "", str(key)).lower()
        if any(candidate.lower() in normalized for candidate in candidates):
            return _clean(value)
    return ""


def normalize_csi300_records(records):
    rows = []
    for record in records:
        code = _find_value(record, ["成分券代码", "constituentcode", "证券代码"])
        code = re.sub(r"\.0$", "", code).zfill(6)
        if not re.fullmatch(r"\d{6}", code):
            continue
        name = _find_value(record, ["成分券名称", "constituentname", "证券简称"])
        industry = _find_value(record, ["中证一级行业", "industry"])
        is_shanghai = code.startswith(("5", "6", "9"))
        rows.append(
            {
                "market": "A股",
                "ticker": f"{code}.{'SH' if is_shanghai else 'SZ'}",
                "raw_ticker": code,
                "company_name": name,
                "industry": industry,
                "index_name": "沪深300",
                "currency": "CNY",
                "exchange": "SSE" if is_shanghai else "SZSE",
                "enabled": "1",
            }
        )
    return rows


def parse_csi300_excel(content):
    import pandas as pd

    frame = pd.read_excel(io.BytesIO(content), dtype=str)
    return normalize_csi300_records(frame.to_dict(orient="records"))


def parse_hk_size_payload(payload):
    selected = {
        "Hang Seng Composite LargeCap Index": "HSLI",
        "Hang Seng Composite MidCap Index": "HSMI",
    }
    by_ticker = {}
    for series in payload.get("indexSeriesList", []):
        for index in series.get("indexList", []):
            short_name = selected.get(index.get("indexName"))
            if not short_name:
                continue
            constituents = sorted(
                index.get("constituentContent", []),
                key=_normalize_hk_counter,
            )
            for constituent in constituents:
                code = _normalize_hk_counter(constituent)
                company_name = _clean(constituent.get("constituentName"))
                if not code.strip("0"):
                    continue
                ticker = f"{code}.HK"
                if ticker in by_ticker:
                    names = by_ticker[ticker]["index_name"].split(",")
                    if short_name not in names:
                        by_ticker[ticker]["index_name"] += f",{short_name}"
                    continue
                by_ticker[ticker] = {
                    "market": "港股",
                    "ticker": ticker,
                    "raw_ticker": code,
                    "company_name": company_name,
                    "industry": _clean(constituent.get("industry")),
                    "index_name": short_name,
                    "currency": "HKD",
                    "exchange": "HKEX",
                    "enabled": "1",
                }
    return list(by_ticker.values())


def validate_market_rows(rows, minimum, maximum):
    if not minimum <= len(rows) <= maximum:
        raise ValueError(f"row count {len(rows)} outside safety range {minimum}-{maximum}")
    seen = set()
    for number, row in enumerate(rows, start=1):
        for field in ("market", "ticker", "raw_ticker", "company_name", "index_name"):
            if not _clean(row.get(field)):
                raise ValueError(f"row {number} missing required field: {field}")
        ticker = row["ticker"]
        if ticker in seen:
            raise ValueError(f"duplicate ticker: {ticker}")
        seen.add(ticker)
    return rows


def fetch_csi300():
    request = Request(CSI300_URL, headers={"User-Agent": "stock-undervaluation-screen/1.0"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def fetch_hk_size():
    request = Request(HK_SIZE_URL, headers={"User-Agent": "stock-undervaluation-screen/1.0"})
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _atomic_write_bytes(path, content):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
        os.replace(temporary_name, destination)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _atomic_write_json(path, payload):
    _atomic_write_bytes(
        path, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    )


def write_rows(path, rows):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary_name, destination)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def load_rows(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def refresh_market_universe(
    market,
    output_path,
    cache_dir,
    fetcher=None,
    parser=None,
    minimum=None,
    maximum=None,
):
    market = market.upper()
    if market not in {"CN", "HK"}:
        raise ValueError("market must be CN or HK")
    defaults = {
        "CN": (fetch_csi300, parse_csi300_excel, 280, 320),
        "HK": (fetch_hk_size, parse_hk_size_payload, 180, 450),
    }
    default_fetcher, default_parser, default_minimum, default_maximum = defaults[market]
    fetch = fetcher or default_fetcher
    parse = parser or default_parser
    minimum = default_minimum if minimum is None else minimum
    maximum = default_maximum if maximum is None else maximum

    cache_root = Path(cache_dir)
    cache_csv = cache_root / "constituents.csv"
    source_path = cache_root / ("source.xls" if market == "CN" else "source.json")
    metadata_path = cache_root / "refresh_metadata.json"
    refreshed_at = datetime.now(timezone.utc).isoformat()

    try:
        source = fetch()
        rows = parse(source)
        validate_market_rows(rows, minimum, maximum)
        write_rows(cache_csv, rows)
        write_rows(output_path, rows)
        if isinstance(source, bytes):
            _atomic_write_bytes(source_path, source)
        else:
            _atomic_write_json(source_path, source)
        result = {"status": "online", "rows": len(rows), "warning": ""}
    except Exception as exc:
        if not cache_csv.exists():
            raise RuntimeError(
                f"{market} universe refresh failed and no valid cache is available: {exc}"
            ) from exc
        rows = load_rows(cache_csv)
        validate_market_rows(rows, minimum, maximum)
        write_rows(output_path, rows)
        result = {"status": "cache_fallback", "rows": len(rows), "warning": str(exc)}

    _atomic_write_json(
        metadata_path,
        {
            "market": market,
            "status": result["status"],
            "rows": result["rows"],
            "refreshed_at": refreshed_at,
            "warning": result["warning"],
        },
    )
    return result


def main():
    parser = argparse.ArgumentParser(description="Refresh CN or HK index constituents")
    parser.add_argument("--market", required=True, choices=["CN", "HK"])
    parser.add_argument("--output", required=True)
    parser.add_argument("--cache-dir", required=True)
    args = parser.parse_args()

    result = refresh_market_universe(args.market, args.output, args.cache_dir)
    print(f"Market: {args.market}")
    print(f"Universe rows: {result['rows']}")
    print(f"Refresh status: {result['status']}")
    if result["warning"]:
        print(f"Warning: {result['warning']}")


if __name__ == "__main__":
    main()
