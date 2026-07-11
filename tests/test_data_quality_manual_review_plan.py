import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def data_health_payload():
    return {
        "review_schema": "data_health_review",
        "review_version": 1,
        "as_of_date": "2026-07-05",
        "status": "acceptable_with_monitoring",
        "recommended_action": "monitor_next_run",
        "blocked_candidate_count": 0,
        "refetch_gap_count": 0,
        "refetch_gap_action_required_count": 0,
        "manual_financial_review_count": 73,
        "active_manual_financial_review_count": 0,
        "closed_manual_financial_review_count": 73,
        "candidate_manual_financial_review_count": 0,
        "manual_financial_review_classified_count": 73,
        "manual_financial_review_unclassified_count": 0,
        "candidate_manual_financial_review_unclassified_count": 0,
        "markets": [
            {
                "name": "美股周筛",
                "manual_financial_review_count": 0,
                "manual_financial_review_classified_count": 0,
                "manual_financial_review_unclassified_count": 0,
                "candidate_manual_financial_review_count": 0,
                "active_manual_financial_review_count": 0,
                "closed_manual_financial_review_count": 0,
                "manual_financial_review_by_category": {},
            },
            {
                "name": "A股周筛",
                "manual_financial_review_count": 22,
                "manual_financial_review_classified_count": 22,
                "manual_financial_review_unclassified_count": 0,
                "candidate_manual_financial_review_count": 0,
                "active_manual_financial_review_count": 0,
                "closed_manual_financial_review_count": 22,
                "manual_financial_review_by_category": {
                    "loss_making_or_negative_pe": 22,
                },
            },
            {
                "name": "港股周筛",
                "manual_financial_review_count": 51,
                "manual_financial_review_classified_count": 51,
                "manual_financial_review_unclassified_count": 0,
                "candidate_manual_financial_review_count": 0,
                "active_manual_financial_review_count": 0,
                "closed_manual_financial_review_count": 51,
                "manual_financial_review_by_category": {
                    "loss_making_or_negative_pe": 49,
                    "non_positive_book_value_or_pb": 7,
                    "special_industry_valuation_review": 1,
                },
            },
        ],
    }


class DataQualityManualReviewPlanTests(unittest.TestCase):
    def test_pending_official_share_fact_uses_monitoring_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "latest_data_health_review.json"
            payload = data_health_payload()
            payload["manual_financial_review_count"] = 2
            payload["manual_financial_review_classified_count"] = 2
            payload["closed_manual_financial_review_count"] = 2
            payload["markets"] = [
                {
                    "name": "美股周筛",
                    "manual_financial_review_count": 2,
                    "manual_financial_review_classified_count": 2,
                    "manual_financial_review_unclassified_count": 0,
                    "candidate_manual_financial_review_count": 0,
                    "active_manual_financial_review_count": 0,
                    "closed_manual_financial_review_count": 2,
                    "manual_financial_review_by_category": {
                        "official_share_fact_pending": 2,
                    },
                }
            ]
            write_json(source, payload)

            from data_quality_manual_review_plan import build_data_quality_manual_review_plan

            result = build_data_quality_manual_review_plan(source, as_of_date="2026-07-11")
            group = result["review_groups"][0]

            self.assertEqual(group["category"], "official_share_fact_pending")
            self.assertEqual(group["priority"], "monitor")
            self.assertEqual(group["action"], "monitor_official_share_fact_availability")
            self.assertIn("SEC", group["minimum_evidence"])

    def test_builds_classification_complete_monitoring_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "latest_data_health_review.json"
            write_json(source, data_health_payload())

            from data_quality_manual_review_plan import (
                build_data_quality_manual_review_plan,
                render_data_quality_manual_review_plan,
            )

            payload = build_data_quality_manual_review_plan(source, as_of_date="2026-07-05")
            report = render_data_quality_manual_review_plan(payload)

            self.assertEqual(payload["review_schema"], "data_quality_manual_review_plan")
            self.assertEqual(payload["status"], "classification_complete_monitoring")
            self.assertEqual(payload["recommended_action"], "continue_monitoring_classified_financial_reviews")
            self.assertEqual(payload["manual_financial_review_count"], 73)
            self.assertEqual(payload["manual_financial_review_classified_count"], 73)
            self.assertEqual(payload["manual_financial_review_unclassified_count"], 0)
            self.assertTrue(payload["classification_complete"])
            self.assertFalse(payload["requires_weekly_blocker"])
            self.assertFalse(payload["formal_model_change_allowed"])
            self.assertEqual(payload["review_group_count"], 3)
            self.assertEqual(payload["review_groups"][0]["category"], "loss_making_or_negative_pe")
            self.assertEqual(payload["review_groups"][0]["item_count"], 71)
            self.assertEqual(payload["review_groups"][0]["priority"], "monitor")
            self.assertIn("数据质量人工复核计划", report)
            self.assertIn("classification_complete_monitoring", report)
            self.assertIn("不修改正式模型", report)

    def test_cli_writes_json_markdown_and_csv_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "latest_data_health_review.json"
            output = root / "latest_data_quality_manual_review_plan.json"
            report = root / "latest_data_quality_manual_review_plan.md"
            csv_output = root / "data_quality_manual_review_plan.csv"
            write_json(source, data_health_payload())

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "data_quality_manual_review_plan.py"),
                    "--data-health-review",
                    str(source),
                    "--as-of-date",
                    "2026-07-05",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--csv-output",
                    str(csv_output),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["status"], "classification_complete_monitoring")
            self.assertEqual(payload["review_group_count"], 3)
            self.assertIn("数据质量人工复核计划", report.read_text(encoding="utf-8-sig"))
            with csv_output.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["category"], "loss_making_or_negative_pe")
            self.assertEqual(rows[0]["item_count"], "71")

    def test_powershell_wrapper_and_weekly_bundle_include_data_quality_plan(self):
        wrapper = (PROJECT_ROOT / "scripts" / "run_data_quality_manual_review_plan.ps1").read_text(
            encoding="utf-8-sig"
        )
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("data_quality_manual_review_plan.py", wrapper)
        self.assertIn("latest_data_health_review.json", wrapper)
        self.assertIn("latest_data_quality_manual_review_plan.json", wrapper)
        self.assertIn("data_quality_manual_review_plan.csv", wrapper)
        self.assertIn("run_data_quality_manual_review_plan", bundle)
        self.assertLess(
            bundle.index("run_data_health_review"),
            bundle.index("run_data_quality_manual_review_plan"),
        )
        self.assertLess(
            bundle.index("run_data_quality_manual_review_plan"),
            bundle.index("run_backtest_evidence_review"),
        )


if __name__ == "__main__":
    unittest.main()
