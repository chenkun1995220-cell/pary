import csv
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from datetime import date
from unittest.mock import patch

from quote_auto_filler import (
    build_quote_row,
    extract_net_debt,
    extract_shares_outstanding,
    extract_shares_from_sec_filing_text,
    fetch_price_quote,
    parse_yahoo_chart_quote,
    load_share_overrides,
    load_fresh_quotes,
    run_auto_fill_quotes,
)


def sec_fact(value, fy=2024, filed="2025-02-01", form="10-K", fp="FY", unit="USD"):
    return {
        "val": value,
        "fy": fy,
        "fp": fp,
        "form": form,
        "filed": filed,
        "end": f"{fy}-12-31",
        "unit": unit,
    }


def company_facts(cik="320193"):
    return {
        "cik": int(cik),
        "entityName": "Fixture Inc.",
        "facts": {
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {
                        "shares": [
                            {
                                "val": 15_000_000_000,
                                "fy": 2024,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2025-02-01",
                                "end": "2024-12-31",
                            }
                        ]
                    }
                }
            },
            "us-gaap": {
                "LongTermDebtAndFinanceLeaseObligationsCurrent": {
                    "units": {"USD": [sec_fact(10_000_000_000)]}
                },
                "LongTermDebtAndFinanceLeaseObligationsNoncurrent": {
                    "units": {"USD": [sec_fact(80_000_000_000)]}
                },
                "CashAndCashEquivalentsAtCarryingValue": {
                    "units": {"USD": [sec_fact(140_000_000_000)]}
                },
            },
        },
    }


class QuoteAutoFillerTests(unittest.TestCase):
    def test_live_price_prefers_yahoo_and_uses_stooq_only_as_fallback(self):
        yahoo_quote = {"ticker": "AAPL", "price": 10, "quote_date": "2026-06-21", "quote_source": "Yahoo"}
        with patch("quote_auto_filler.fetch_yahoo_chart_quote", return_value=yahoo_quote) as yahoo, patch("quote_auto_filler.fetch_stooq_quote") as stooq:
            result = fetch_price_quote("AAPL")
        self.assertEqual(result, yahoo_quote)
        yahoo.assert_called_once_with("AAPL")
        stooq.assert_not_called()
    def test_quote_rows_are_built_with_bounded_concurrency(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            companies = root / "companies.csv"
            output = root / "quotes.csv"
            with companies.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["ticker", "cik", "company_name", "industry"])
                writer.writeheader()
                for index in range(4):
                    writer.writerow({"ticker": f"T{index}", "cik": str(index + 1), "company_name": "Test", "industry": "Tech"})

            state = {"active": 0, "maximum": 0}
            lock = threading.Lock()

            def fake_build(company, facts, price_csv_text=None, quote_override=None, **kwargs):
                with lock:
                    state["active"] += 1
                    state["maximum"] = max(state["maximum"], state["active"])
                time.sleep(0.05)
                with lock:
                    state["active"] -= 1
                return {"ticker": company["ticker"], "price": "10", "quote_date": "2026-06-21"}

            with patch("quote_auto_filler.load_company_facts", return_value=company_facts()), patch("quote_auto_filler.build_quote_row", side_effect=fake_build):
                run_auto_fill_quotes(companies, output, fixture_dir=root, max_workers=4)

            self.assertGreater(state["maximum"], 1)
    def test_existing_quotes_are_reused_only_within_seven_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quotes.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["ticker", "price", "shares_outstanding", "quote_date", "quote_source"])
                writer.writeheader()
                writer.writerow({"ticker": "FRESH", "price": "10", "shares_outstanding": "100", "quote_date": "2026-06-18", "quote_source": "cached"})
                writer.writerow({"ticker": "STALE", "price": "20", "shares_outstanding": "200", "quote_date": "2026-06-10", "quote_source": "cached"})
                writer.writerow({"ticker": "PARTIAL", "price": "30", "shares_outstanding": "", "quote_date": "2026-06-18", "quote_source": "cached"})
                writer.writerow({"ticker": "TINY", "price": "40", "shares_outstanding": "0.002542", "quote_date": "2026-06-18", "quote_source": "cached"})

            rows = load_fresh_quotes(path, date(2026, 6, 21), max_age_days=7)

            self.assertEqual(set(rows), {"FRESH"})
            self.assertEqual(rows["FRESH"]["price"], "10")

    def test_existing_manual_override_quotes_reuse_requires_current_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quotes.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["ticker", "price", "shares_outstanding", "quote_date", "quote_source"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "ticker": "KEEP",
                        "price": "10",
                        "shares_outstanding": "100",
                        "quote_date": "2026-06-18",
                        "quote_source": "Yahoo; Manual share override (still configured)",
                    }
                )
                writer.writerow(
                    {
                        "ticker": "DROP",
                        "price": "20",
                        "shares_outstanding": "200",
                        "quote_date": "2026-06-18",
                        "quote_source": "Yahoo; Manual share override (removed)",
                    }
                )

            rows = load_fresh_quotes(
                path,
                date(2026, 6, 21),
                max_age_days=7,
                manual_override_tickers={"KEEP"},
            )

            self.assertEqual(set(rows), {"KEEP"})

    def test_build_quote_row_rejects_implausibly_tiny_sec_share_count(self):
        facts = company_facts()
        facts["facts"].pop("dei")
        facts["facts"]["us-gaap"]["WeightedAverageNumberOfDilutedSharesOutstanding"] = {
            "units": {
                "shares": [
                    {
                        "val": 2_542,
                        "fy": 2026,
                        "fp": "Q1",
                        "form": "10-Q",
                        "filed": "2026-04-23",
                        "end": "2026-03-31",
                    }
                ]
            }
        }
        facts["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"] = {
            "units": {"USD": [sec_fact(4_089_770_000)]}
        }
        facts["facts"]["us-gaap"]["NetIncomeLoss"] = {
            "units": {"USD": [sec_fact(571_392_000)]}
        }

        row = build_quote_row(
            {"ticker": "ERIE"},
            facts,
            quote_override={
                "ticker": "ERIE",
                "price": 237.11300659179688,
                "quote_date": "2026-06-26",
                "quote_source": "Yahoo Finance chart",
            },
        )

        self.assertEqual(row["shares_outstanding"], "")
        self.assertIn("share sanity failed", row["quote_source"])

    def test_load_share_overrides_converts_million_share_units(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "overrides.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "ticker",
                        "shares_outstanding",
                        "shares_unit",
                        "as_of_date",
                        "source",
                        "source_url",
                        "note",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "ticker": "erie",
                        "shares_outstanding": "52.3",
                        "shares_unit": "million_shares",
                        "as_of_date": "2026-06-26",
                        "source": "manual review",
                        "source_url": "https://example.com",
                        "note": "class-adjusted shares",
                    }
                )

            overrides = load_share_overrides(path)

        self.assertEqual(overrides["ERIE"]["shares"], 52_300_000)
        self.assertEqual(overrides["ERIE"]["source"], "manual review")

    def test_build_quote_row_uses_manual_share_override_after_sec_sanity_failure(self):
        facts = company_facts()
        facts["facts"].pop("dei")
        facts["facts"]["us-gaap"]["WeightedAverageNumberOfDilutedSharesOutstanding"] = {
            "units": {"shares": [sec_fact(2_542, unit="shares")]}
        }
        facts["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"] = {
            "units": {"USD": [sec_fact(4_089_770_000)]}
        }

        row = build_quote_row(
            {"ticker": "ERIE"},
            facts,
            quote_override={
                "ticker": "ERIE",
                "price": 237.11,
                "quote_date": "2026-06-26",
                "quote_source": "Yahoo Finance chart",
            },
            share_override={
                "shares": 52_300_000,
                "source": "manual review",
            },
        )

        self.assertEqual(row["shares_outstanding"], 52.3)
        self.assertIn("Manual share override", row["quote_source"])
        self.assertIn("manual review", row["quote_source"])

    def test_extracts_shares_from_sec_filing_text(self):
        proxy_text = "Shares of common stock outstanding as of the Record Date 171,466,896"
        spin_text = (
            "converted the total number of shares of the Common Stock issued and "
            "outstanding into a number of validly issued shares equal to 149,505,248."
        )

        self.assertEqual(extract_shares_from_sec_filing_text(proxy_text), 171_466_896)
        self.assertEqual(extract_shares_from_sec_filing_text(spin_text), 149_505_248)

    def test_build_quote_row_uses_sec_filing_share_fallback(self):
        facts = company_facts()
        facts["facts"].pop("dei")

        row = build_quote_row(
            {"ticker": "FDXF"},
            facts,
            quote_override={
                "ticker": "FDXF",
                "price": 150,
                "quote_date": "2026-06-26",
                "quote_source": "Yahoo Finance chart",
            },
            fallback_shares=149_505_248,
            fallback_share_source="SEC filing text",
        )

        self.assertEqual(row["shares_outstanding"], 149.505248)
        self.assertIn("SEC filing text", row["quote_source"])
    def test_parse_yahoo_chart_quote_uses_latest_close(self):
        payload = {
            "chart": {
                "result": [
                    {
                        "timestamp": [1781616600, 1781703000],
                        "indicators": {
                            "quote": [
                                {"close": [295.0, 296.69]},
                            ]
                        },
                    }
                ],
                "error": None,
            }
        }

        quote = parse_yahoo_chart_quote("AAPL", payload)

        self.assertEqual(quote["ticker"], "AAPL")
        self.assertEqual(quote["price"], 296.69)
        self.assertEqual(quote["quote_date"], "2026-06-17")
        self.assertEqual(quote["quote_source"], "Yahoo Finance chart")

    def test_extracts_shares_and_net_debt_from_company_facts(self):
        facts = company_facts()

        self.assertEqual(extract_shares_outstanding(facts), 15_000_000_000)
        self.assertEqual(extract_net_debt(facts), -50_000_000_000)

    def test_extracts_shares_from_us_gaap_common_stock_when_dei_is_missing(self):
        facts = company_facts()
        facts["facts"].pop("dei")
        facts["facts"]["us-gaap"]["CommonStockSharesOutstanding"] = {
            "units": {
                "shares": [
                    {
                        "val": 12_345_000_000,
                        "fy": 2024,
                        "fp": "FY",
                        "form": "10-K",
                        "filed": "2025-02-01",
                        "end": "2024-12-31",
                    }
                ]
            }
        }

        self.assertEqual(extract_shares_outstanding(facts), 12_345_000_000)

    def test_extracts_newer_us_gaap_shares_instead_of_stale_dei_value(self):
        facts = company_facts()
        facts["facts"]["dei"]["EntityCommonStockSharesOutstanding"] = {
            "units": {
                "shares": [
                    {
                        "val": 1,
                        "fy": 2019,
                        "fp": "Q2",
                        "form": "10-Q",
                        "filed": "2019-03-18",
                        "end": "2019-03-18",
                    }
                ]
            }
        }
        facts["facts"]["us-gaap"]["WeightedAverageNumberOfDilutedSharesOutstanding"] = {
            "units": {
                "shares": [
                    {
                        "val": 443_000_000,
                        "fy": 2026,
                        "fp": "Q3",
                        "form": "10-Q",
                        "filed": "2026-05-11",
                        "end": "2026-03-31",
                    }
                ]
            }
        }

        self.assertEqual(extract_shares_outstanding(facts), 443_000_000)

    def test_build_quote_row_uses_newer_us_gaap_shares_without_manual_override(self):
        facts = company_facts()
        facts["facts"]["dei"]["EntityCommonStockSharesOutstanding"] = {
            "units": {
                "shares": [
                    {
                        "val": 1,
                        "fy": 2019,
                        "fp": "Q2",
                        "form": "10-Q",
                        "filed": "2019-03-18",
                        "end": "2019-03-18",
                    }
                ]
            }
        }
        facts["facts"]["us-gaap"]["WeightedAverageNumberOfDilutedSharesOutstanding"] = {
            "units": {"shares": [sec_fact(443_000_000, fy=2026, filed="2026-05-11", fp="Q3", unit="shares")]}
        }
        facts["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"] = {
            "units": {"USD": [sec_fact(16_480_000_000, fy=2026, filed="2026-05-11")]}
        }

        row = build_quote_row(
            {"ticker": "FOXA"},
            facts,
            quote_override={
                "ticker": "FOXA",
                "price": 50,
                "quote_date": "2026-06-26",
                "quote_source": "Yahoo Finance chart",
            },
        )

        self.assertEqual(row["shares_outstanding"], 443.0)
        self.assertNotIn("Manual share override", row["quote_source"])
        self.assertNotIn("share sanity failed", row["quote_source"])

    def test_run_auto_fill_quotes_writes_standard_quote_csv_from_fixtures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            companies_path = root / "companies.csv"
            output_path = root / "quotes.csv"
            sec_fixture_dir = root / "sec"
            price_fixture_dir = root / "prices"
            sec_fixture_dir.mkdir()
            price_fixture_dir.mkdir()

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

            (sec_fixture_dir / "CIK0000320193.json").write_text(
                json.dumps(company_facts("320193")), encoding="utf-8"
            )
            (price_fixture_dir / "AAPL.csv").write_text(
                "Symbol,Date,Time,Open,High,Low,Close,Volume\n"
                "AAPL.US,2026-06-18,22:00:08,190,201,188,200.5,123456\n",
                encoding="utf-8",
            )

            result = run_auto_fill_quotes(
                companies_path,
                output_path,
                fixture_dir=sec_fixture_dir,
                price_fixture_dir=price_fixture_dir,
            )
            with output_path.open("r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))

            self.assertEqual(result["rows"], 1)
            self.assertEqual(rows[0]["ticker"], "AAPL")
            self.assertEqual(rows[0]["price"], "200.5")
            self.assertEqual(rows[0]["shares_outstanding"], "15000.0")
            self.assertEqual(rows[0]["net_debt"], "-50000.0")
            self.assertEqual(rows[0]["price_unit"], "USD/share")
            self.assertEqual(rows[0]["shares_unit"], "million_shares")
            self.assertEqual(rows[0]["debt_unit"], "USD_million")
            self.assertEqual(rows[0]["quote_date"], "2026-06-18")
            self.assertIn("SEC Company Facts", rows[0]["quote_source"])


if __name__ == "__main__":
    unittest.main()
