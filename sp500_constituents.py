import argparse
import csv
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


MEDIAWIKI_API_URL = "https://en.wikipedia.org/w/api.php"
MEDIAWIKI_PAGE = "List of S&P 500 companies"
OUTPUT_FIELDS = [
    "source_ticker",
    "ticker",
    "company_name",
    "industry",
    "gics_sub_industry",
    "cik",
    "date_added",
    "enabled",
]


class ConstituentsTableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_table = False
        self.in_cell = False
        self.current_cell = []
        self.current_row = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "table" and attributes.get("id") == "constituents":
            self.in_table = True
        elif self.in_table and tag in {"th", "td"}:
            self.in_cell = True
            self.current_cell = []

    def handle_data(self, data):
        if self.in_table and self.in_cell:
            self.current_cell.append(data)

    def handle_endtag(self, tag):
        if not self.in_table:
            return
        if tag in {"th", "td"} and self.in_cell:
            value = re.sub(r"\s+", " ", "".join(self.current_cell)).strip()
            self.current_row.append(value)
            self.current_cell = []
            self.in_cell = False
        elif tag == "tr":
            if self.current_row:
                self.rows.append(self.current_row)
            self.current_row = []
        elif tag == "table":
            self.in_table = False


def normalize_ticker(value):
    return str(value or "").strip().upper().replace(".", "-")


def parse_constituents_html(html_text):
    parser = ConstituentsTableParser()
    parser.feed(html_text)
    if not parser.rows:
        raise ValueError("S&P 500 constituents table was not found")

    headers = parser.rows[0]
    header_index = {name: index for index, name in enumerate(headers)}
    required_headers = {
        "Symbol",
        "Security",
        "GICS Sector",
        "GICS Sub-Industry",
        "Date added",
        "CIK",
    }
    missing_headers = sorted(required_headers - set(header_index))
    if missing_headers:
        raise ValueError(f"missing S&P 500 table headers: {', '.join(missing_headers)}")

    rows = []
    for values in parser.rows[1:]:
        if len(values) < len(headers):
            continue

        def cell(name):
            return values[header_index[name]].strip()

        source_ticker = cell("Symbol").upper()
        cik_text = re.sub(r"\D", "", cell("CIK"))
        cik = str(int(cik_text)) if cik_text else ""
        rows.append(
            {
                "source_ticker": source_ticker,
                "ticker": normalize_ticker(source_ticker),
                "company_name": cell("Security"),
                "industry": cell("GICS Sector"),
                "gics_sub_industry": cell("GICS Sub-Industry"),
                "cik": cik,
                "date_added": cell("Date added"),
                "enabled": "1",
            }
        )
    return rows


def validate_constituents(rows, minimum=450, maximum=550):
    if not minimum <= len(rows) <= maximum:
        raise ValueError(
            f"constituent row count {len(rows)} outside safety range {minimum}-{maximum}"
        )

    required = ("source_ticker", "ticker", "company_name", "industry", "cik")
    seen = set()
    for row_number, row in enumerate(rows, start=1):
        missing = [field for field in required if not str(row.get(field, "")).strip()]
        if missing:
            raise ValueError(
                f"constituent row {row_number} missing required fields: {', '.join(missing)}"
            )
        if not str(row["cik"]).isdigit():
            raise ValueError(f"constituent row {row_number} has non-numeric CIK")
        ticker = row["ticker"]
        if ticker in seen:
            raise ValueError(f"duplicate normalized ticker: {ticker}")
        seen.add(ticker)
    return rows


def fetch_constituents_html(user_agent=None):
    query = urlencode(
        {
            "action": "parse",
            "page": MEDIAWIKI_PAGE,
            "prop": "text",
            "format": "json",
            "formatversion": "2",
        }
    )
    request = Request(
        f"{MEDIAWIKI_API_URL}?{query}",
        headers={"User-Agent": user_agent or "stock-undervaluation-screen/1.0"},
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    html_text = payload.get("parse", {}).get("text", "")
    if not html_text:
        raise ValueError("MediaWiki response did not contain parsed HTML")
    return html_text


def _atomic_write_text(path, text, encoding="utf-8"):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(handle, "w", encoding=encoding, newline="") as stream:
            stream.write(text)
        os.replace(temporary_name, destination)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def write_constituents_csv(path, rows):
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


def load_constituents_csv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def refresh_constituents(
    output_path,
    cache_dir,
    fetcher=None,
    minimum=450,
    maximum=550,
    user_agent=None,
):
    cache_root = Path(cache_dir)
    cache_csv = cache_root / "sp500_constituents.csv"
    source_json = cache_root / "sp500_source.json"
    metadata_json = cache_root / "sp500_refresh_metadata.json"
    fetched_at = datetime.now(timezone.utc).isoformat()
    fetch = fetcher or (lambda: fetch_constituents_html(user_agent=user_agent))

    try:
        html_text = fetch()
        rows = parse_constituents_html(html_text)
        validate_constituents(rows, minimum=minimum, maximum=maximum)
        write_constituents_csv(cache_csv, rows)
        write_constituents_csv(output_path, rows)
        _atomic_write_text(
            source_json,
            json.dumps(
                {
                    "source": MEDIAWIKI_PAGE,
                    "source_url": MEDIAWIKI_API_URL,
                    "fetched_at": fetched_at,
                    "html": html_text,
                },
                ensure_ascii=False,
            ),
        )
        result = {"status": "online", "rows": len(rows), "warning": ""}
    except Exception as exc:
        if not cache_csv.exists():
            raise RuntimeError(
                f"S&P 500 refresh failed and no valid cache is available: {exc}"
            ) from exc
        rows = load_constituents_csv(cache_csv)
        validate_constituents(rows, minimum=minimum, maximum=maximum)
        write_constituents_csv(output_path, rows)
        result = {
            "status": "cache_fallback",
            "rows": len(rows),
            "warning": str(exc),
        }

    metadata = {
        "status": result["status"],
        "rows": result["rows"],
        "refreshed_at": fetched_at,
        "warning": result["warning"],
    }
    _atomic_write_text(metadata_json, json.dumps(metadata, ensure_ascii=False, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description="Refresh the S&P 500 constituent universe")
    parser.add_argument("--output", default="data/config/us_universe_symbols.csv")
    parser.add_argument("--cache-dir", default="data/cache/sp500")
    parser.add_argument("--user-agent", default=None)
    args = parser.parse_args()

    result = refresh_constituents(
        args.output,
        args.cache_dir,
        user_agent=args.user_agent,
    )
    print(f"S&P 500 universe rows: {result['rows']}")
    print(f"Refresh status: {result['status']}")
    if result["warning"]:
        print(f"Warning: {result['warning']}")


if __name__ == "__main__":
    main()
