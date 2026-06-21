import csv
import json
import tempfile
import unittest
from pathlib import Path

from candidate_research_pack import (
    build_filing_url,
    latest_filings,
    run_candidate_research_packs,
)


def submissions_fixture():
    return {
        "cik": "0001652044",
        "name": "Example Inc.",
        "filings": {
            "recent": {
                "accessionNumber": ["0001652044-26-000010", "0001652044-25-000099"],
                "filingDate": ["2026-05-01", "2025-12-01"],
                "reportDate": ["2026-03-31", "2025-09-30"],
                "form": ["10-Q", "10-K"],
                "primaryDocument": ["example-20260331.htm", "example-20250930.htm"],
            }
        },
    }


class CandidateResearchPackTests(unittest.TestCase):
    def test_builds_sec_archive_filing_url(self):
        url = build_filing_url(
            "0001652044",
            "0001652044-26-000010",
            "example-20260331.htm",
        )

        self.assertEqual(
            url,
            "https://www.sec.gov/Archives/edgar/data/1652044/000165204426000010/example-20260331.htm",
        )

    def test_selects_latest_10k_and_10q(self):
        filings = latest_filings(submissions_fixture())

        self.assertEqual(filings["10-Q"]["filing_date"], "2026-05-01")
        self.assertEqual(filings["10-K"]["filing_date"], "2025-12-01")
        self.assertIn("Archives/edgar/data/1652044", filings["10-K"]["url"])

    def test_generates_candidate_index_and_company_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate_path = root / "candidate_pool.csv"
            metrics_path = root / "metrics.csv"
            issues_path = root / "issues.csv"
            companies_path = root / "companies.csv"
            fixture_dir = root / "submissions"
            output_dir = root / "research"
            fixture_dir.mkdir()

            with candidate_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "ticker",
                        "company_name",
                        "industry",
                        "total_score",
                        "grade",
                        "action",
                        "pe",
                        "pb",
                        "ps",
                        "ev_ebitda",
                        "fcf_yield",
                        "reason",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "ticker": "EXMPL",
                        "company_name": "Example Inc.",
                        "industry": "科技软件",
                        "total_score": "90",
                        "grade": "A",
                        "action": "进入深研",
                        "pe": "12",
                        "pb": "5",
                        "ps": "3",
                        "ev_ebitda": "8",
                        "fcf_yield": "0.10",
                        "reason": "估值低于行业中位数",
                    }
                )
            with metrics_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "ticker",
                        "roic",
                        "gross_margin",
                        "current_ratio",
                        "debt_to_assets",
                        "net_debt_to_ebitda",
                        "revenue_cagr_3y",
                        "net_income_cagr_3y",
                        "metrics_period_basis",
                        "metrics_as_of",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "ticker": "EXMPL",
                        "roic": "0.15",
                        "gross_margin": "0.60",
                        "current_ratio": "1.5",
                        "debt_to_assets": "0.30",
                        "net_debt_to_ebitda": "0.5",
                        "revenue_cagr_3y": "0.08",
                        "net_income_cagr_3y": "0.10",
                        "metrics_period_basis": "ttm",
                        "metrics_as_of": "2026-03-31",
                    }
                )
            issues_path.write_text(
                "severity,issue_code,ticker,message\n",
                encoding="utf-8-sig",
            )
            companies_path.write_text(
                "ticker,cik,company_name,industry\nEXMPL,1652044,Example Inc.,科技软件\n",
                encoding="utf-8-sig",
            )
            (fixture_dir / "CIK0001652044.json").write_text(
                json.dumps(submissions_fixture()), encoding="utf-8"
            )

            result = run_candidate_research_packs(
                candidate_path,
                metrics_path,
                issues_path,
                companies_path,
                output_dir,
                fixture_dir=fixture_dir,
            )
            report = (output_dir / "EXMPL_深研包.md").read_text(encoding="utf-8-sig")
            index = (output_dir / "候选公司深研索引.md").read_text(encoding="utf-8-sig")

            self.assertEqual(result["rows"], 1)
            self.assertIn("Example Inc.", report)
            self.assertIn("## 估值快照", report)
            self.assertIn("## SEC 官方申报", report)
            self.assertIn("10-K", report)
            self.assertIn("价值陷阱检查", report)
            self.assertIn("EXMPL", index)


if __name__ == "__main__":
    unittest.main()
