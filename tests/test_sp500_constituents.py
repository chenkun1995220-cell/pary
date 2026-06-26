import csv
import tempfile
import unittest
from pathlib import Path

from sp500_constituents import (
    parse_constituents_html,
    refresh_constituents,
    reconcile_with_sec_tickers,
    validate_constituents,
)


FIXTURE_HTML = """
<html><body>
<table class="wikitable sortable" id="constituents">
  <tr>
    <th>Symbol</th><th>Security</th><th>GICS Sector</th>
    <th>GICS Sub-Industry</th><th>Headquarters Location</th>
    <th>Date added</th><th>CIK</th><th>Founded</th>
  </tr>
  <tr>
    <td><a>BRK.B</a></td><td>Berkshire Hathaway</td><td>Financials</td>
    <td>Multi-Sector Holdings</td><td>Omaha, Nebraska</td>
    <td>2010-02-16</td><td>0001067983</td><td>1839</td>
  </tr>
  <tr>
    <td>MSFT</td><td>Microsoft</td><td>Information Technology</td>
    <td>Systems Software</td><td>Redmond, Washington</td>
    <td>1994-06-01</td><td>0000789019</td><td>1975</td>
  </tr>
</table>
</body></html>
"""


def sec_ticker_payload():
    return {
        "fields": ["cik", "name", "ticker", "exchange"],
        "data": [
            [1067983, "Berkshire Hathaway Inc.", "BRK-B", "NYSE"],
            [789019, "Microsoft Corporation", "MSFT", "Nasdaq"],
        ],
    }


class Sp500ConstituentTests(unittest.TestCase):
    def test_parse_constituents_normalizes_share_class_tickers(self):
        rows = parse_constituents_html(FIXTURE_HTML)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["source_ticker"], "BRK.B")
        self.assertEqual(rows[0]["ticker"], "BRK-B")
        self.assertEqual(rows[0]["company_name"], "Berkshire Hathaway")
        self.assertEqual(rows[0]["industry"], "Financials")
        self.assertEqual(rows[0]["gics_sub_industry"], "Multi-Sector Holdings")
        self.assertEqual(rows[0]["cik"], "1067983")
        self.assertEqual(rows[0]["enabled"], "1")

    def test_validate_rejects_unsafe_row_count(self):
        rows = parse_constituents_html(FIXTURE_HTML)

        with self.assertRaisesRegex(ValueError, "row count"):
            validate_constituents(rows)

    def test_validate_rejects_duplicate_normalized_tickers(self):
        rows = parse_constituents_html(FIXTURE_HTML)
        rows.append(dict(rows[0], source_ticker="BRK-B"))

        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_constituents(rows, minimum=2, maximum=5)

    def test_reconcile_uses_sec_ticker_when_source_symbol_disagrees_for_unique_cik(self):
        rows = [
            {
                "source_ticker": "ECHO",
                "ticker": "ECHO",
                "company_name": "EchoStar",
                "industry": "Communication Services",
                "gics_sub_industry": "Wireless Telecommunication Services",
                "cik": "1415404",
                "date_added": "2026-03-23",
                "enabled": "1",
            }
        ]
        sec_payload = {
            "fields": ["cik", "name", "ticker", "exchange"],
            "data": [[1415404, "EchoStar CORP", "SATS", "Nasdaq"]],
        }

        reconciled, corrections = reconcile_with_sec_tickers(rows, sec_payload)

        self.assertEqual(reconciled[0]["source_ticker"], "SATS")
        self.assertEqual(reconciled[0]["ticker"], "SATS")
        self.assertEqual(corrections, [{"cik": "1415404", "from": "ECHO", "to": "SATS"}])

    def test_refresh_writes_last_good_cache_and_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "symbols.csv"
            cache_dir = root / "cache"

            result = refresh_constituents(
                output,
                cache_dir,
                fetcher=lambda: FIXTURE_HTML,
                sec_ticker_fetcher=sec_ticker_payload,
                minimum=2,
                maximum=5,
            )

            self.assertEqual(result["status"], "online")
            self.assertEqual(result["rows"], 2)
            self.assertTrue((cache_dir / "sp500_constituents.csv").exists())
            self.assertTrue((cache_dir / "sp500_source.json").exists())
            self.assertTrue((cache_dir / "sp500_refresh_metadata.json").exists())
            with output.open("r", encoding="utf-8-sig", newline="") as f:
                saved = list(csv.DictReader(f))
            self.assertEqual(saved[0]["ticker"], "BRK-B")

    def test_refresh_falls_back_to_last_good_cache_when_fetch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "symbols.csv"
            cache_dir = root / "cache"
            refresh_constituents(
                output,
                cache_dir,
                fetcher=lambda: FIXTURE_HTML,
                sec_ticker_fetcher=sec_ticker_payload,
                minimum=2,
                maximum=5,
            )
            output.unlink()

            def fail_fetch():
                raise OSError("network unavailable")

            result = refresh_constituents(
                output,
                cache_dir,
                fetcher=fail_fetch,
                minimum=2,
                maximum=5,
            )

            self.assertEqual(result["status"], "cache_fallback")
            self.assertEqual(result["rows"], 2)
            self.assertTrue(output.exists())
            self.assertIn("network unavailable", result["warning"])

    def test_refresh_raises_when_fetch_fails_without_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            with self.assertRaisesRegex(RuntimeError, "no valid cache"):
                refresh_constituents(
                    root / "symbols.csv",
                    root / "cache",
                    fetcher=lambda: (_ for _ in ()).throw(OSError("offline")),
                    sec_ticker_fetcher=sec_ticker_payload,
                    minimum=2,
                    maximum=5,
                )


if __name__ == "__main__":
    unittest.main()
