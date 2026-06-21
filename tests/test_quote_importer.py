import csv
import tempfile
import unittest
from pathlib import Path

from quote_importer import import_quote_csv, load_quote_aliases, map_quote_row


class QuoteImporterTests(unittest.TestCase):
    def test_maps_external_quote_fields_and_applies_default_units(self):
        aliases = {
            "ticker": "ticker",
            "close": "price",
            "shares(m)": "shares_outstanding",
            "net debt(m)": "net_debt",
            "date": "quote_date",
            "source": "quote_source",
        }
        row = {
            "Ticker": "aapl",
            "Close": "200",
            "Shares(M)": "15000",
            "Net Debt(M)": "-50000",
            "Date": "2026-06-18",
            "Source": "broker export",
        }

        mapped = map_quote_row(row, aliases)

        self.assertEqual(mapped["ticker"], "AAPL")
        self.assertEqual(mapped["price"], "200")
        self.assertEqual(mapped["shares_outstanding"], "15000")
        self.assertEqual(mapped["net_debt"], "-50000")
        self.assertEqual(mapped["currency"], "USD")
        self.assertEqual(mapped["price_unit"], "USD/share")
        self.assertEqual(mapped["shares_unit"], "million_shares")
        self.assertEqual(mapped["debt_unit"], "USD_million")
        self.assertEqual(mapped["quote_source"], "broker export")
        self.assertEqual(mapped["updated_at"], "2026-06-18")

    def test_import_quote_csv_writes_standard_quote_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "broker_quotes.csv"
            output_path = root / "mapped_quotes.csv"
            aliases_path = root / "aliases.csv"
            with input_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["Ticker", "Close", "Shares(M)", "Net Debt(M)", "Date", "Source"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "Ticker": "MSFT",
                        "Close": "450",
                        "Shares(M)": "7400",
                        "Net Debt(M)": "-30000",
                        "Date": "2026-06-18",
                        "Source": "manual sample",
                    }
                )
            aliases_path.write_text(
                "\n".join(
                    [
                        "alias,standard_field",
                        "Ticker,ticker",
                        "Close,price",
                        "Shares(M),shares_outstanding",
                        "Net Debt(M),net_debt",
                        "Date,quote_date",
                        "Source,quote_source",
                    ]
                )
                + "\n",
                encoding="utf-8-sig",
            )

            result = import_quote_csv(input_path, output_path, aliases_path)
            output = output_path.read_text(encoding="utf-8-sig")

            self.assertEqual(result["rows"], 1)
            self.assertIn("price_unit", output)
            self.assertIn("million_shares", output)
            self.assertIn("USD_million", output)

    def test_load_quote_aliases_reads_config(self):
        aliases = load_quote_aliases("data/config/quote_field_aliases.csv")

        self.assertEqual(aliases["ticker"], "ticker")
        self.assertEqual(aliases["close"], "price")


if __name__ == "__main__":
    unittest.main()
