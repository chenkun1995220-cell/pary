import csv
import tempfile
import unittest
from pathlib import Path

from real_sample_pack import load_sample_companies, validate_real_sample_pack


class RealSamplePackTests(unittest.TestCase):
    def test_sample_company_file_contains_required_us_tickers(self):
        rows = load_sample_companies("data/samples/us_real_sample_companies.csv")

        by_ticker = {row["ticker"]: row for row in rows}

        self.assertEqual(by_ticker["AAPL"]["cik"], "320193")
        self.assertEqual(by_ticker["MSFT"]["cik"], "789019")
        self.assertEqual(by_ticker["GOOGL"]["cik"], "1652044")

    def test_validation_rejects_duplicate_cik(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            companies_path = root / "companies.csv"
            with companies_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["ticker", "cik", "company_name", "industry"]
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "ticker": "AAPL",
                        "cik": "320193",
                        "company_name": "Apple Inc.",
                        "industry": "科技硬件",
                    }
                )
                writer.writerow(
                    {
                        "ticker": "MSFT",
                        "cik": "320193",
                        "company_name": "Microsoft Corporation",
                        "industry": "科技软件",
                    }
                )

            result = validate_real_sample_pack(companies_path)

            self.assertFalse(result["ok"])
            self.assertIn("duplicate_cik", result["errors"])

    def test_validation_allows_share_classes_of_same_company_to_share_cik(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "companies.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["ticker", "cik", "company_name", "industry"])
                writer.writeheader()
                writer.writerow({"ticker": "GOOGL", "cik": "1652044", "company_name": "Alphabet Inc.", "industry": "Software"})
                writer.writerow({"ticker": "GOOG", "cik": "1652044", "company_name": "Alphabet Inc.", "industry": "Software"})

            result = validate_real_sample_pack(path)

            self.assertNotIn("duplicate_cik", result["errors"])

    def test_validation_checks_quote_tickers_match_companies(self):
        result = validate_real_sample_pack(
            "data/samples/us_real_sample_companies.csv",
            "data/samples/us_real_sample_quotes.csv",
        )

        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["tickers"], ["AAPL", "GOOGL", "MSFT"])
        self.assertEqual(result["quote_tickers"], ["AAPL", "GOOGL", "MSFT"])

    def test_sample_quote_template_requires_metadata_columns(self):
        result = validate_real_sample_pack(
            "data/samples/us_real_sample_companies.csv",
            "data/samples/us_real_sample_quotes.csv",
        )

        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["quote_metadata_status"], "template_ready")

    def test_validation_rejects_invalid_quote_units(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            companies_path = root / "companies.csv"
            quotes_path = root / "quotes.csv"
            with companies_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["ticker", "cik", "company_name", "industry"]
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "ticker": "AAPL",
                        "cik": "320193",
                        "company_name": "Apple Inc.",
                        "industry": "Technology Hardware",
                    }
                )
                writer.writerow(
                    {
                        "ticker": "MSFT",
                        "cik": "789019",
                        "company_name": "Microsoft Corporation",
                        "industry": "Software",
                    }
                )
                writer.writerow(
                    {
                        "ticker": "GOOGL",
                        "cik": "1652044",
                        "company_name": "Alphabet Inc.",
                        "industry": "Software",
                    }
                )
            with quotes_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
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
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "ticker": "AAPL",
                        "price": "100",
                        "shares_outstanding": "15000",
                        "net_debt": "-50000",
                        "currency": "USD",
                        "quote_date": "2026-06-18",
                        "price_unit": "USD/share",
                        "shares_unit": "billions",
                        "debt_unit": "USD_million",
                        "quote_source": "manual",
                        "updated_at": "2026-06-18",
                    }
                )
                writer.writerow(
                    {
                        "ticker": "MSFT",
                        "price_unit": "USD/share",
                        "shares_unit": "shares",
                        "debt_unit": "USD",
                    }
                )
                writer.writerow(
                    {
                        "ticker": "GOOGL",
                        "price_unit": "USD/share",
                        "shares_unit": "shares",
                        "debt_unit": "USD",
                    }
                )

            result = validate_real_sample_pack(companies_path, quotes_path)

            self.assertFalse(result["ok"])
            self.assertIn("invalid_quote_unit", result["errors"])

    def test_validation_rejects_populated_quote_without_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            companies_path = root / "companies.csv"
            quotes_path = root / "quotes.csv"
            with companies_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["ticker", "cik", "company_name", "industry"]
                )
                writer.writeheader()
                for ticker, cik in [("AAPL", "320193"), ("MSFT", "789019"), ("GOOGL", "1652044")]:
                    writer.writerow(
                        {
                            "ticker": ticker,
                            "cik": cik,
                            "company_name": ticker,
                            "industry": "Software",
                        }
                    )
            with quotes_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
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
                    ],
                )
                writer.writeheader()
                for ticker in ["AAPL", "MSFT", "GOOGL"]:
                    writer.writerow(
                        {
                            "ticker": ticker,
                            "price": "100",
                            "shares_outstanding": "1000",
                            "net_debt": "0",
                            "currency": "USD",
                            "quote_date": "2026-06-18",
                            "price_unit": "USD/share",
                            "shares_unit": "shares",
                            "debt_unit": "USD",
                            "quote_source": "",
                            "updated_at": "2026-06-18",
                        }
                    )

            result = validate_real_sample_pack(companies_path, quotes_path)

            self.assertFalse(result["ok"])
            self.assertIn("missing_quote_metadata", result["errors"])


if __name__ == "__main__":
    unittest.main()
