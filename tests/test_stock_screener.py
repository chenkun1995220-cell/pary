import csv
import tempfile
import unittest
from pathlib import Path

from stock_screener import load_stocks, score_stock, run_screening, run_weekly_report


class StockScreenerTests(unittest.TestCase):
    def test_score_stock_accepts_blank_debt_to_assets(self):
        stock = {
            "market": "美股",
            "ticker": "BLANK",
            "company_name": "Blank Debt Ratio Inc.",
            "industry": "科技软件",
            "market_cap": "1000",
            "enterprise_value": "900",
            "net_assets": "500",
            "revenue_ttm": "800",
            "net_income_ttm": "100",
            "operating_cash_flow": "120",
            "capex": "-20",
            "debt_to_assets": "",
            "audit_opinion": "标准无保留",
            "risk_flag": "无",
        }

        scored = score_stock(stock)

        self.assertEqual(scored["ticker"], "BLANK")
        self.assertNotIn("资产负债率较低", scored["reason"])

    def test_scores_quality_value_company_as_priority_candidate(self):
        stock = {
            "market": "A股",
            "ticker": "600000",
            "company_name": "样本消费公司",
            "industry": "消费",
            "market_cap": "50000",
            "enterprise_value": "48000",
            "net_assets": "25000",
            "revenue_ttm": "30000",
            "net_income_ttm": "3500",
            "ebitda": "5000",
            "operating_cash_flow": "4200",
            "capex": "-1200",
            "dividend_yield": "0.025",
            "industry_pe_median": "22",
            "industry_pb_median": "3",
            "industry_ev_ebitda_median": "12",
            "roe": "0.14",
            "roic": "0.12",
            "gross_margin": "0.42",
            "debt_to_assets": "0.38",
            "net_debt_to_ebitda": "1.2",
            "current_ratio": "1.8",
            "revenue_cagr_3y": "0.08",
            "net_income_cagr_3y": "0.10",
            "audit_opinion": "标准无保留",
            "risk_flag": "无",
        }

        scored = score_stock(stock)

        self.assertEqual(scored["free_cash_flow"], 3000.0)
        self.assertEqual(scored["grade"], "B")
        self.assertGreaterEqual(scored["total_score"], 80)

    def test_run_screening_merges_csv_files_and_exports_candidate_pool(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_dir = root / "data" / "raw"
            out_dir = root / "outputs"
            raw_dir.mkdir(parents=True)

            rows = [
                {
                    "market": "A股",
                    "ticker": "600000",
                    "company_name": "优质低估样本",
                    "industry": "消费",
                    "market_cap": "50000",
                    "enterprise_value": "48000",
                    "net_assets": "25000",
                    "revenue_ttm": "30000",
                    "net_income_ttm": "3500",
                    "ebitda": "5000",
                    "operating_cash_flow": "4200",
                    "capex": "-1200",
                    "dividend_yield": "0.025",
                    "industry_pe_median": "22",
                    "industry_pb_median": "3",
                    "industry_ev_ebitda_median": "12",
                    "roe": "0.14",
                    "roic": "0.12",
                    "gross_margin": "0.42",
                    "debt_to_assets": "0.38",
                    "net_debt_to_ebitda": "1.2",
                    "current_ratio": "1.8",
                    "revenue_cagr_3y": "0.08",
                    "net_income_cagr_3y": "0.10",
                    "audit_opinion": "标准无保留",
                    "risk_flag": "无",
                },
                {
                    "market": "美股",
                    "ticker": "RISK",
                    "company_name": "高风险样本",
                    "industry": "科技软件",
                    "market_cap": "90000",
                    "enterprise_value": "85000",
                    "net_assets": "12000",
                    "revenue_ttm": "18000",
                    "net_income_ttm": "1500",
                    "ebitda": "2500",
                    "operating_cash_flow": "2800",
                    "capex": "-500",
                    "dividend_yield": "0",
                    "industry_pe_median": "35",
                    "industry_pb_median": "7",
                    "industry_ev_ebitda_median": "22",
                    "roe": "0.11",
                    "roic": "0.09",
                    "gross_margin": "0.72",
                    "debt_to_assets": "0.28",
                    "net_debt_to_ebitda": "0.5",
                    "current_ratio": "2.5",
                    "revenue_cagr_3y": "0.18",
                    "net_income_cagr_3y": "0.15",
                    "audit_opinion": "标准无保留",
                    "risk_flag": "重大",
                },
            ]

            with (raw_dir / "sample.csv").open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)

            loaded = load_stocks(raw_dir)
            result = run_screening(raw_dir, out_dir, candidate_min_score=80)

            self.assertEqual(len(loaded), 2)
            self.assertEqual(result["total_rows"], 2)
            self.assertEqual(result["candidate_rows"], 1)
            self.assertTrue((out_dir / "screening_results.csv").exists())
            self.assertTrue((out_dir / "candidate_pool.csv").exists())

    def test_score_includes_readable_reason_for_candidate(self):
        stock = {
            "market": "A股",
            "ticker": "600000",
            "company_name": "样本消费公司",
            "industry": "消费",
            "market_cap": "50000",
            "enterprise_value": "48000",
            "net_assets": "25000",
            "revenue_ttm": "30000",
            "net_income_ttm": "3500",
            "ebitda": "5000",
            "operating_cash_flow": "4200",
            "capex": "-1200",
            "industry_pe_median": "22",
            "industry_pb_median": "3",
            "industry_ev_ebitda_median": "12",
            "roe": "0.14",
            "roic": "0.12",
            "gross_margin": "0.42",
            "debt_to_assets": "0.38",
            "net_debt_to_ebitda": "1.2",
            "current_ratio": "1.8",
            "revenue_cagr_3y": "0.08",
            "net_income_cagr_3y": "0.10",
            "audit_opinion": "标准无保留",
            "risk_flag": "无",
        }

        scored = score_stock(stock)

        self.assertIn("PE低于行业中位数", scored["reason"])
        self.assertIn("自由现金流为正", scored["reason"])
        self.assertIn("审计意见标准且无重大风险", scored["reason"])

    def test_weekly_report_exports_dated_markdown_with_reasons(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_dir = root / "data" / "raw"
            out_dir = root / "outputs"
            raw_dir.mkdir(parents=True)

            row = {
                "market": "A股",
                "ticker": "600000",
                "company_name": "优质低估样本",
                "industry": "消费",
                "market_cap": "50000",
                "enterprise_value": "48000",
                "net_assets": "25000",
                "revenue_ttm": "30000",
                "net_income_ttm": "3500",
                "ebitda": "5000",
                "operating_cash_flow": "4200",
                "capex": "-1200",
                "industry_pe_median": "22",
                "industry_pb_median": "3",
                "industry_ev_ebitda_median": "12",
                "roe": "0.14",
                "roic": "0.12",
                "gross_margin": "0.42",
                "debt_to_assets": "0.38",
                "net_debt_to_ebitda": "1.2",
                "current_ratio": "1.8",
                "revenue_cagr_3y": "0.08",
                "net_income_cagr_3y": "0.10",
                "audit_opinion": "标准无保留",
                "risk_flag": "无",
            }
            with (raw_dir / "sample.csv").open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(row.keys()))
                writer.writeheader()
                writer.writerow(row)

            result = run_weekly_report(raw_dir, out_dir, report_date="2026-06-16")
            report_text = result["report_path"].read_text(encoding="utf-8-sig")

            self.assertEqual(result["candidate_rows"], 1)
            self.assertIn("# 低估公司每周筛选报告（2026-06-16）", report_text)
            self.assertIn("优质低估样本", report_text)
            self.assertIn("PE低于行业中位数", report_text)

    def test_severe_data_quality_issue_blocks_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_dir = root / "data" / "raw"
            out_dir = root / "outputs"
            raw_dir.mkdir(parents=True)

            row = {
                "market": "A股",
                "ticker": "",
                "company_name": "缺代码高分样本",
                "industry": "消费",
                "market_cap": "50000",
                "enterprise_value": "48000",
                "net_assets": "25000",
                "revenue_ttm": "30000",
                "net_income_ttm": "3500",
                "ebitda": "5000",
                "operating_cash_flow": "4200",
                "capex": "-1200",
                "industry_pe_median": "22",
                "industry_pb_median": "3",
                "industry_ev_ebitda_median": "12",
                "roe": "0.14",
                "roic": "0.12",
                "gross_margin": "0.42",
                "debt_to_assets": "0.38",
                "net_debt_to_ebitda": "1.2",
                "current_ratio": "1.8",
                "revenue_cagr_3y": "0.08",
                "net_income_cagr_3y": "0.10",
                "audit_opinion": "标准无保留",
                "risk_flag": "无",
            }
            with (raw_dir / "bad.csv").open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(row.keys()))
                writer.writeheader()
                writer.writerow(row)

            result = run_screening(raw_dir, out_dir, candidate_min_score=80)

            self.assertEqual(result["candidate_rows"], 0)
            self.assertEqual(result["scored"][0]["data_quality_status"], "blocked")
            self.assertEqual(result["scored"][0]["total_score"], 0)
            self.assertIn("missing_required_field", result["scored"][0]["data_quality_block_reason"])

    def test_weekly_report_lists_data_quality_blocked_stock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_dir = root / "data" / "raw"
            out_dir = root / "outputs"
            raw_dir.mkdir(parents=True)

            row = {
                "market": "A股",
                "ticker": "",
                "company_name": "缺代码样本",
                "industry": "消费",
                "market_cap": "50000",
                "net_income_ttm": "3500",
                "audit_opinion": "标准无保留",
                "risk_flag": "无",
            }
            with (raw_dir / "bad.csv").open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(row.keys()))
                writer.writeheader()
                writer.writerow(row)

            result = run_weekly_report(raw_dir, out_dir, report_date="2026-06-17")
            report_text = result["report_path"].read_text(encoding="utf-8-sig")

            self.assertIn("缺代码样本", report_text)
            self.assertIn("数据质量", report_text)

    def test_weekly_report_includes_data_quality_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_dir = root / "data" / "raw"
            out_dir = root / "outputs"
            raw_dir.mkdir(parents=True)

            row = {
                "market": "A股",
                "ticker": "600000",
                "company_name": "单位异常样本",
                "industry": "消费",
                "market_cap": "50000",
                "net_income_ttm": "3500",
                "gross_margin": "45",
                "audit_opinion": "标准无保留",
                "risk_flag": "无",
            }
            with (raw_dir / "warn.csv").open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(row.keys()))
                writer.writeheader()
                writer.writerow(row)

            result = run_weekly_report(raw_dir, out_dir, report_date="2026-06-17")
            report_text = result["report_path"].read_text(encoding="utf-8-sig")

            self.assertIn("## 数据质量摘要", report_text)
            self.assertIn("警告：1", report_text)
            self.assertIn("percentage_unit_suspect", report_text)


if __name__ == "__main__":
    unittest.main()
