import csv
import tempfile
import unittest
from pathlib import Path

from data_quality_checks import check_rows, run_data_quality_checks


class DataQualityChecksTests(unittest.TestCase):
    def test_detects_missing_required_fields_and_unit_warnings(self):
        rows = [
            {
                "ticker": "",
                "company_name": "问题公司",
                "industry": "",
                "market_cap": "100",
                "net_income_ttm": "10",
                "gross_margin": "45",
                "industry_median_sample_count": "2",
                "industry_mapping_status": "unmapped",
            }
        ]

        issues = check_rows(rows)
        issue_codes = {issue["issue_code"] for issue in issues}

        self.assertIn("missing_required_field", issue_codes)
        self.assertIn("percentage_unit_suspect", issue_codes)
        self.assertIn("industry_unmapped", issue_codes)
        self.assertIn("industry_sample_too_small", issue_codes)

    def test_percent_unit_warnings_use_field_specific_thresholds(self):
        rows = [
            {
                "ticker": "OKRATIO",
                "company_name": "High But Plausible Co",
                "industry": "工业",
                "market_cap": "1000",
                "net_income_ttm": "100",
                "roe": "1.5",
                "roic": "1.6",
                "debt_to_assets": "1.2",
                "net_income_cagr_3y": "2.0",
                "audit_opinion": "标准无保留",
                "risk_flag": "无",
            },
            {
                "ticker": "BADUNIT",
                "company_name": "Bad Unit Co",
                "industry": "工业",
                "market_cap": "1000",
                "net_income_ttm": "100",
                "gross_margin": "45",
                "roe": "12",
                "roic": "12",
                "debt_to_assets": "3",
                "net_income_cagr_3y": "6",
                "audit_opinion": "标准无保留",
                "risk_flag": "无",
            },
        ]

        issues = check_rows(rows)
        by_ticker = {}
        for issue in issues:
            by_ticker.setdefault(issue["ticker"], set()).add((issue["issue_code"], issue["field"]))

        self.assertNotIn(("percentage_unit_suspect", "roe"), by_ticker.get("OKRATIO", set()))
        self.assertNotIn(("percentage_unit_suspect", "roic"), by_ticker.get("OKRATIO", set()))
        self.assertNotIn(("percentage_unit_suspect", "debt_to_assets"), by_ticker.get("OKRATIO", set()))
        self.assertNotIn(("percentage_unit_suspect", "net_income_cagr_3y"), by_ticker.get("OKRATIO", set()))
        self.assertIn(("percentage_unit_suspect", "gross_margin"), by_ticker.get("BADUNIT", set()))
        self.assertIn(("percentage_unit_suspect", "roe"), by_ticker.get("BADUNIT", set()))
        self.assertIn(("percentage_unit_suspect", "roic"), by_ticker.get("BADUNIT", set()))
        self.assertIn(("percentage_unit_suspect", "debt_to_assets"), by_ticker.get("BADUNIT", set()))
        self.assertIn(("percentage_unit_suspect", "net_income_cagr_3y"), by_ticker.get("BADUNIT", set()))

    def test_missing_income_and_revenue_is_reported_as_statement_gap(self):
        rows = [
            {
                "ticker": "FDXF",
                "company_name": "FedEx Freight Holding Company, Inc.",
                "industry": "工业",
                "market_cap": "22722555208",
                "net_income_ttm": "",
                "revenue_ttm": "",
                "audit_opinion": "标准无保留",
                "risk_flag": "无",
            }
        ]

        issues = check_rows(rows)
        issue_codes = {issue["issue_code"] for issue in issues}

        self.assertIn("missing_financial_statement_data", issue_codes)
        self.assertNotIn("missing_core_numeric_field", issue_codes)

    def test_quality_issues_include_actionable_handling_fields(self):
        rows = [
            {
                "ticker": "GMX",
                "company_name": "Gross Margin Extreme Co",
                "industry": "工业",
                "market_cap": "1000",
                "net_income_ttm": "100",
                "gross_margin": "45",
                "audit_opinion": "标准无保留",
                "risk_flag": "无",
            },
            {
                "ticker": "FDXF",
                "company_name": "FedEx Freight Holding Company, Inc.",
                "industry": "工业",
                "market_cap": "22722555208",
                "net_income_ttm": "",
                "revenue_ttm": "",
                "audit_opinion": "标准无保留",
                "risk_flag": "无",
            },
        ]

        issues = check_rows(rows)
        by_code = {issue["issue_code"]: issue for issue in issues}

        self.assertEqual(by_code["percentage_unit_suspect"]["review_action"], "复核源字段")
        self.assertEqual(by_code["percentage_unit_suspect"]["impact_on_score"], "可能影响盈利质量和估值倍数")
        self.assertIn("核对 gross_margin", by_code["percentage_unit_suspect"]["recommended_handling"])
        self.assertEqual(by_code["missing_financial_statement_data"]["review_action"], "补齐财报数据")
        self.assertEqual(by_code["missing_financial_statement_data"]["impact_on_score"], "可能降低估值置信度")
        self.assertIn("补齐 revenue_ttm", by_code["missing_financial_statement_data"]["recommended_handling"])

    def test_detects_financial_logic_issues(self):
        rows = [
            {
                "ticker": "BAD",
                "company_name": "逻辑异常公司",
                "industry": "科技软件",
                "market_cap": "1000",
                "enterprise_value": "900",
                "net_debt": "200",
                "net_income_ttm": "100",
                "operating_cash_flow": "120",
                "capex": "30",
                "audit_opinion": "",
                "risk_flag": "",
            }
        ]

        issues = check_rows(rows)
        issue_codes = {issue["issue_code"] for issue in issues}

        self.assertIn("enterprise_value_logic_error", issue_codes)
        self.assertIn("capex_sign_suspect", issue_codes)
        self.assertIn("risk_field_missing", issue_codes)

    def test_detects_market_cap_scale_and_cash_flow_outliers(self):
        rows = [
            {
                "ticker": "ERIE",
                "company_name": "ERIE INDEMNITY CO",
                "industry": "金融",
                "market_cap": "602741.2627563477",
                "revenue_ttm": "4089770000",
                "net_income_ttm": "571392000",
                "operating_cash_flow": "660431000",
                "capex": "-123432000",
                "audit_opinion": "标准无保留",
                "risk_flag": "无",
            }
        ]

        issues = check_rows(rows)
        issue_codes = {issue["issue_code"] for issue in issues}
        severe_codes = {issue["issue_code"] for issue in issues if issue["severity"] == "严重"}

        self.assertIn("market_cap_scale_suspect", issue_codes)
        self.assertIn("valuation_ratio_outlier", severe_codes)
        self.assertIn("fcf_yield_outlier", severe_codes)

    def test_run_checks_writes_csv_and_markdown_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "stocks.csv"
            issues_path = root / "issues.csv"
            report_path = root / "quality.md"

            rows = [
                {
                    "ticker": "",
                    "company_name": "问题公司",
                    "industry": "",
                    "market_cap": "100",
                    "gross_margin": "45",
                }
            ]
            with input_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)

            result = run_data_quality_checks(input_path, issues_path, report_path)
            issues_text = issues_path.read_text(encoding="utf-8-sig")
            report_text = report_path.read_text(encoding="utf-8-sig")

            self.assertGreater(result["issue_count"], 0)
            self.assertIn("missing_required_field", issues_text)
            self.assertIn("review_action", issues_text)
            self.assertIn("impact_on_score", issues_text)
            self.assertIn("recommended_handling", issues_text)
            self.assertIn("# 数据质量检查报告", report_text)
            self.assertIn("问题公司", report_text)
            self.assertIn("处置建议", report_text)


if __name__ == "__main__":
    unittest.main()
