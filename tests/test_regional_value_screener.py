import csv
import tempfile
import unittest
from pathlib import Path

from regional_value_screener import (
    calculate_industry_medians,
    run_regional_screening,
    score_row,
)


def row(ticker, pe, pb, roe, industry="银行", market="A股"):
    return {
        "market": market,
        "ticker": ticker,
        "company_name": ticker,
        "industry": industry,
        "currency": "CNY",
        "price": "10",
        "market_cap": "100000000000",
        "pe": str(pe),
        "pb": str(pb),
        "roe": str(roe),
        "roic": "0.12",
        "gross_margin": "0.40",
        "current_ratio": "1.5",
        "debt_to_assets": "0.40",
        "operating_cash_flow": "1000000000",
        "revenue_growth": "0.08",
        "net_income_growth": "0.10",
        "financial_data_status": "ready",
        "quote_date": "2026-06-19",
        "source": "fixture",
        "data_quality_status": "ready",
    }


class RegionalValueScreenerTests(unittest.TestCase):
    def test_calculates_medians_by_market_and_industry(self):
        rows = [row("A", 5, 0.5, 0.15), row("B", 15, 1.5, 0.08)]
        rows.append(row("HK", 30, 3, 0.05, market="港股"))

        medians = calculate_industry_medians(rows)

        self.assertEqual(medians[("A股", "银行")]["pe_median"], 10)
        self.assertEqual(medians[("A股", "银行")]["pb_median"], 1)
        self.assertEqual(medians[("港股", "银行")]["pe_median"], 30)

    def test_scores_discounted_profitable_company_as_candidate(self):
        median = {"pe_median": 10, "pb_median": 1, "sample_count": 8}

        scored = score_row(row("VALUE", 6, 0.6, 0.16), median, candidate_min_score=65)

        self.assertGreaterEqual(scored["total_score"], 65)
        self.assertEqual(scored["candidate_status"], "candidate")
        self.assertIn("PE低于行业中位数", scored["reason"])
        self.assertIn("ROE", scored["reason"])
        self.assertEqual(scored["model_version"], "regional_fundamental_v2")
        self.assertGreater(scored["profitability_score"], 0)
        self.assertGreater(scored["balance_sheet_score"], 0)
        self.assertGreater(scored["cash_flow_score"], 0)
        self.assertGreater(scored["growth_score"], 0)

    def test_missing_financials_are_low_confidence_and_not_candidate(self):
        item = row("MISSING", 5, 0.5, 0.15)
        for field in (
            "roic",
            "gross_margin",
            "current_ratio",
            "debt_to_assets",
            "operating_cash_flow",
            "revenue_growth",
            "net_income_growth",
        ):
            item[field] = ""
        item["financial_data_status"] = "missing"
        median = {"pe_median": 20, "pb_median": 2, "sample_count": 8}

        scored = score_row(item, median, candidate_min_score=1)

        self.assertEqual(scored["candidate_status"], "excluded")
        self.assertEqual(scored["confidence"], "low")
        self.assertIn("财务数据缺失", scored["reason"])

    def test_negative_pe_is_never_candidate(self):
        median = {"pe_median": 10, "pb_median": 1, "sample_count": 8}

        scored = score_row(row("LOSS", -3, 0.5, 0.1), median, candidate_min_score=1)

        self.assertEqual(scored["candidate_status"], "excluded")
        self.assertIn("PE非正", scored["reason"])

    def test_roe_below_five_percent_is_never_candidate(self):
        median = {"pe_median": 20, "pb_median": 2, "sample_count": 8}

        scored = score_row(row("LOWROE", 5, 0.5, 0.02), median, candidate_min_score=1)

        self.assertEqual(scored["candidate_status"], "excluded")
        self.assertIn("ROE低于5%", scored["reason"])

    def test_run_screening_writes_results_candidates_medians_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "snapshot.csv"
            output_root = root / "output"
            rows = [
                row("VALUE", 5, 0.5, 0.16),
                row("B", 10, 1.0, 0.12),
                row("C", 11, 1.1, 0.10),
                row("D", 12, 1.2, 0.08),
                row("E", 13, 1.3, 0.07),
                row("F", 14, 1.4, 0.06),
            ]
            with input_path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            result = run_regional_screening(input_path, output_root, candidate_min_score=65)

            self.assertEqual(result["rows"], 6)
            self.assertGreaterEqual(result["candidates"], 1)
            self.assertTrue((output_root / "screening_results.csv").exists())
            self.assertTrue((output_root / "candidate_pool.csv").exists())
            self.assertTrue((output_root / "industry_medians.csv").exists())
            report = (output_root / "weekly_report.md").read_text(encoding="utf-8-sig")
            self.assertIn("区域市场相对估值初筛", report)
            self.assertIn("VALUE", report)


    def test_screening_report_lists_non_positive_valuation_review_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "snapshot.csv"
            output_root = root / "output"
            rows = [
                row("VALUE", 5, 0.5, 0.16),
                row("EMPTY", "", 0.4, 0.11),
                row("LOSS", -3, 0.5, 0.10),
                row("BOOK", 6, 0, 0.12),
                row("B", 10, 1.0, 0.12),
                row("C", 11, 1.1, 0.10),
                row("D", 12, 1.2, 0.08),
                row("E", 13, 1.3, 0.07),
                row("F", 14, 1.4, 0.06),
            ]
            with input_path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            run_regional_screening(input_path, output_root, candidate_min_score=65)

            with (output_root / "screening_results.csv").open("r", encoding="utf-8-sig", newline="") as stream:
                result_rows = {item["ticker"]: item for item in csv.DictReader(stream)}
            report = (output_root / "weekly_report.md").read_text(encoding="utf-8-sig")

            self.assertEqual(result_rows["LOSS"]["valuation_review_category"], "loss_making_or_negative_pe")
            self.assertEqual(result_rows["BOOK"]["valuation_review_category"], "non_positive_book_value_or_pb")
            self.assertEqual(result_rows["EMPTY"]["valuation_review_category"], "loss_making_or_negative_pe")
            self.assertIn("loss_making_or_negative_pe", report)
            self.assertIn("non_positive_book_value_or_pb", report)
            self.assertIn("LOSS", report)
            self.assertIn("BOOK", report)


if __name__ == "__main__":
    unittest.main()
