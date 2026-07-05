import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_fixture(root):
    manifest_path = root / "outputs" / "automation" / "latest_self_analysis_manifest.json"
    hk_dir = root / "outputs" / "hk_universe"
    cn_dir = root / "outputs" / "cn_universe"
    us_dir = root / "outputs" / "us_universe"
    for directory in (hk_dir, cn_dir, us_dir):
        directory.mkdir(parents=True, exist_ok=True)
        write_csv(
            directory / "data_health_history.csv",
            [
                {
                    "run_time": "2026-06-28 14:05:00",
                    "market": directory.name,
                    "quote_coverage_pct": "100.00",
                }
            ],
            ["run_time", "market", "quote_coverage_pct"],
        )
    write_csv(
        hk_dir / "quote_gaps.csv",
        [
            {
                "market": "HK",
                "ticker": "00754.HK",
                "company_name": "HOPSON DEV HOLD",
                "issue_type": "partial_quote",
                "missing_fields": "price;pe",
                "remediation_type": "refetch_or_supplement_quote",
                "review_category": "",
                "review_detail": "",
            },
            {
                "market": "HK",
                "ticker": "00823.HK",
                "company_name": "LINK REIT",
                "issue_type": "partial_quote",
                "missing_fields": "pe;pb",
                "remediation_type": "refetch_or_supplement_quote",
                "review_category": "",
                "review_detail": "",
            },
            {
                "market": "HK",
                "ticker": "01548.HK",
                "company_name": "GENSCRIPT BIO",
                "issue_type": "non_positive_metric",
                "missing_fields": "pe",
                "remediation_type": "manual_financial_review",
                "review_category": "loss_making_or_negative_pe",
                "review_detail": "pe=-6.22",
            },
        ],
        [
            "market",
            "ticker",
            "company_name",
            "issue_type",
            "missing_fields",
            "remediation_type",
            "review_category",
            "review_detail",
        ],
    )
    (hk_dir / "quote_retry_results.json").write_text(
        json.dumps(
            {
                "retry_schema": "regional_quote_retry",
                "retry_version": 1,
                "attempted": 2,
                "updated": 0,
                "errors": 0,
                "results": [
                    {
                        "ticker": "00754.HK",
                        "status": "partial",
                        "message": "still partial after retry",
                    },
                    {
                        "ticker": "00823.HK",
                        "status": "partial",
                        "message": "still partial after retry",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8-sig",
    )
    for directory in (cn_dir, us_dir):
        write_csv(
            directory / "quote_gaps.csv",
            [],
            [
                "market",
                "ticker",
                "company_name",
                "issue_type",
                "missing_fields",
                "remediation_type",
                "review_category",
                "review_detail",
            ],
        )
    manifest = {
        "manifest_schema": "self_analysis_manifest",
        "manifest_version": 1,
        "as_of_date": "2026-06-28",
        "data_health_status": "manual_review_needed",
        "data_health_recommended_action": "review_data_health",
        "markets": [
            {
                "name": "美股周筛",
                "candidate_tickers": "ADBE, MSFT",
                "status": "ready",
            },
            {
                "name": "A股周筛",
                "candidate_tickers": "300628.SZ",
                "status": "ready",
            },
            {
                "name": "港股周筛",
                "candidate_tickers": "01530.HK, 03888.HK, 03918.HK",
                "status": "ready",
            },
        ],
        "health": [
            {
                "name": "美股周筛",
                "path": str(us_dir / "data_health_history.csv"),
                "quote_coverage": "100.00%",
                "financial_coverage": "n/a",
                "quote_gap_count": "0",
                "quote_gap_refetch_count": "0",
                "quote_gap_review_count": "0",
                "affected_candidate_count": "0",
                "status": "ready",
            },
            {
                "name": "A股周筛",
                "path": str(cn_dir / "data_health_history.csv"),
                "quote_coverage": "92.67%",
                "financial_coverage": "100.00%",
                "quote_gap_count": "0",
                "quote_gap_refetch_count": "0",
                "quote_gap_review_count": "0",
                "affected_candidate_count": "0",
                "status": "ready",
            },
            {
                "name": "港股周筛",
                "path": str(hk_dir / "data_health_history.csv"),
                "quote_coverage": "84.10%",
                "financial_coverage": "99.69%",
                "quote_gap_count": "3",
                "quote_gap_refetch_count": "2",
                "quote_gap_review_count": "1",
                "affected_candidate_count": "0",
                "status": "ready",
            },
        ],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )
    return manifest_path


class DataHealthReviewTests(unittest.TestCase):
    def test_builds_review_with_refetch_gap_candidate_impact_and_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = write_fixture(Path(tmp))

            from data_health_review import build_data_health_review, render_data_health_review

            payload = build_data_health_review(manifest_path)
            report = render_data_health_review(payload)

            self.assertEqual(payload["review_schema"], "data_health_review")
            self.assertEqual(payload["review_version"], 1)
            self.assertEqual(payload["as_of_date"], "2026-06-28")
            self.assertEqual(payload["status"], "acceptable_with_monitoring")
            self.assertEqual(payload["blocked_candidate_count"], 0)
            self.assertEqual(payload["refetch_gap_count"], 0)
            self.assertEqual(payload["manual_financial_review_count"], 1)
            self.assertEqual(payload["active_manual_financial_review_count"], 0)
            self.assertEqual(payload["closed_manual_financial_review_count"], 1)
            self.assertEqual(payload["candidate_manual_financial_review_count"], 0)
            self.assertEqual(payload["manual_financial_review_classified_count"], 1)
            self.assertEqual(payload["manual_financial_review_unclassified_count"], 0)
            self.assertEqual(payload["candidate_manual_financial_review_unclassified_count"], 0)
            self.assertEqual(payload["refetch_gap_attempted_count"], 0)
            self.assertEqual(payload["refetch_gap_action_required_count"], 0)
            self.assertEqual(payload["refetch_gap_unresolved_non_candidate_count"], 2)
            self.assertEqual(payload["recommended_action"], "monitor_next_run")

            hk = next(item for item in payload["markets"] if item["name"] == "港股周筛")
            self.assertEqual(hk["refetch_gap_count"], 0)
            self.assertEqual(hk["candidate_refetch_gap_count"], 0)
            self.assertEqual(hk["manual_financial_review_count"], 1)
            self.assertEqual(hk["active_manual_financial_review_count"], 0)
            self.assertEqual(hk["closed_manual_financial_review_count"], 1)
            self.assertEqual(hk["manual_financial_review_classified_count"], 1)
            self.assertEqual(hk["manual_financial_review_unclassified_count"], 0)
            self.assertEqual(hk["manual_financial_review_by_category"]["loss_making_or_negative_pe"], 1)
            self.assertEqual(hk["refetch_gap_attempted_count"], 0)
            self.assertEqual(hk["refetch_gap_action_required_count"], 0)
            self.assertEqual(hk["refetch_gap_unresolved_non_candidate_count"], 2)
            self.assertEqual(hk["refetch_gaps"], [])

            self.assertIn("# 数据健康复核结论", report)
            self.assertIn("当前数据健康缺口不直接阻断本周候选", report)
            self.assertIn("00754.HK", report)
            self.assertIn("00823.HK", report)
            self.assertIn("refetch_gap_attempted_count", report)
            self.assertIn("refetch_gap_action_required_count", report)
            self.assertIn("candidate_manual_financial_review_count", report)
            self.assertIn("不抓取行情", report)
            self.assertIn("不重新评分", report)
            self.assertIn("不修改正式模型参数", report)

    def test_excludes_exhausted_non_candidate_retry_gaps_from_refetch_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = write_fixture(Path(tmp))

            from data_health_review import build_data_health_review

            payload = build_data_health_review(manifest_path)
            hk = payload["markets"][2]

            self.assertEqual(payload["refetch_gap_count"], 0)
            self.assertEqual(payload["refetch_gap_attempted_count"], 0)
            self.assertEqual(payload["refetch_gap_action_required_count"], 0)
            self.assertEqual(payload["refetch_gap_unresolved_non_candidate_count"], 2)
            self.assertEqual(hk["refetch_gap_count"], 0)
            self.assertEqual(hk["refetch_gap_unresolved_non_candidate_count"], 2)

    def test_cli_writes_json_and_markdown_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = write_fixture(root)
            output = root / "outputs" / "automation" / "latest_data_health_review.json"
            report = root / "outputs" / "automation" / "latest_data_health_review.md"

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "data_health_review.py"),
                    "--manifest",
                    str(manifest_path),
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            combined = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, combined)
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["status"], "acceptable_with_monitoring")
            self.assertIn("数据健康复核结论", report.read_text(encoding="utf-8-sig"))
            self.assertIn("latest_data_health_review.md", combined)

    def test_powershell_wrapper_and_bundle_include_data_health_review(self):
        wrapper = (PROJECT_ROOT / "scripts" / "run_data_health_review.ps1").read_text(
            encoding="utf-8-sig"
        )
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("data_health_review.py", wrapper)
        self.assertIn("latest_self_analysis_manifest.json", wrapper)
        self.assertIn("latest_data_health_review.json", wrapper)
        self.assertIn("latest_data_health_review.md", wrapper)
        self.assertIn("run_data_health_review", bundle)
        self.assertLess(
            bundle.index("run_self_analysis"),
            bundle.index("run_data_health_review"),
        )
        self.assertLess(
            bundle.index("run_data_health_review"),
            bundle.index("show_weekly_action_items"),
        )


if __name__ == "__main__":
    unittest.main()
