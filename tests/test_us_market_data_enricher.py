import csv
import tempfile
import unittest
from pathlib import Path

from us_market_data_enricher import (
    enrich_rows,
    fetch_stooq_quote,
    load_quotes,
    run_market_enrichment,
)


class UsMarketDataEnricherTests(unittest.TestCase):
    def test_enrich_rows_calculates_market_cap_and_enterprise_value(self):
        rows = [
            {
                "market": "美股",
                "ticker": "EXMPL",
                "company_name": "Example Inc.",
                "revenue_ttm": "1200",
                "net_income_ttm": "120",
                "net_assets": "500",
            }
        ]
        quotes = {
            "EXMPL": {
                "price": "25",
                "shares_outstanding": "100",
                "net_debt": "300",
                "currency": "USD",
                "quote_date": "2026-06-16",
            }
        }

        enriched = enrich_rows(rows, quotes)

        self.assertEqual(enriched[0]["market_cap"], 2500.0)
        self.assertEqual(enriched[0]["enterprise_value"], 2800.0)
        self.assertEqual(enriched[0]["price"], 25.0)
        self.assertEqual(enriched[0]["quote_date"], "2026-06-16")
        self.assertEqual(enriched[0]["revenue_ttm"], "1200")

    def test_enrich_rows_normalizes_quote_units_before_calculating_value(self):
        rows = [
            {
                "market": "美股",
                "ticker": "EXMPL",
                "company_name": "Example Inc.",
            }
        ]
        quotes = {
            "EXMPL": {
                "price": "25",
                "shares_outstanding": "100",
                "net_debt": "300",
                "currency": "USD",
                "quote_date": "2026-06-18",
                "price_unit": "USD/share",
                "shares_unit": "million_shares",
                "debt_unit": "USD_million",
                "quote_source": "manual test",
                "updated_at": "2026-06-18",
            }
        }

        enriched = enrich_rows(rows, quotes)

        self.assertEqual(enriched[0]["shares_outstanding"], 100_000_000.0)
        self.assertEqual(enriched[0]["net_debt"], 300_000_000.0)
        self.assertEqual(enriched[0]["market_cap"], 2_500_000_000.0)
        self.assertEqual(enriched[0]["enterprise_value"], 2_800_000_000.0)
        self.assertEqual(enriched[0]["shares_unit"], "million_shares")
        self.assertEqual(enriched[0]["debt_unit"], "USD_million")

    def test_run_market_enrichment_writes_enriched_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "sec_us_stocks.csv"
            quote_path = root / "us_quotes.csv"
            output_path = root / "us_stocks_enriched.csv"

            with input_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["market", "ticker", "company_name", "revenue_ttm"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "market": "美股",
                        "ticker": "EXMPL",
                        "company_name": "Example Inc.",
                        "revenue_ttm": "1200",
                    }
                )
            with quote_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "ticker",
                        "price",
                        "shares_outstanding",
                        "net_debt",
                        "currency",
                        "quote_date",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "ticker": "EXMPL",
                        "price": "25",
                        "shares_outstanding": "100",
                        "net_debt": "300",
                        "currency": "USD",
                        "quote_date": "2026-06-16",
                    }
                )

            result = run_market_enrichment(input_path, quote_path, output_path)
            output = output_path.read_text(encoding="utf-8-sig")

            self.assertEqual(result["rows"], 1)
            self.assertIn("market_cap", output)
            self.assertIn("2800.0", output)

    def test_load_quotes_normalizes_ticker_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            quote_path = Path(tmp) / "quotes.csv"
            quote_path.write_text(
                "ticker,price,shares_outstanding\nexmpl,25,100\n",
                encoding="utf-8-sig",
            )

            quotes = load_quotes(quote_path)

            self.assertIn("EXMPL", quotes)

    def test_fetch_stooq_quote_parses_csv_text(self):
        csv_text = (
            "Symbol,Date,Time,Open,High,Low,Close,Volume\n"
            "AAPL.US,2026-06-16,22:00:08,100,110,99,108.5,123456\n"
        )

        quote = fetch_stooq_quote("AAPL", csv_text=csv_text)

        self.assertEqual(quote["ticker"], "AAPL")
        self.assertEqual(quote["price"], 108.5)
        self.assertEqual(quote["quote_date"], "2026-06-16")


if __name__ == "__main__":
    unittest.main()
