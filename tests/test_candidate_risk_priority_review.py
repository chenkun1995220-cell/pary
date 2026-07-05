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


def write_candidate_pool(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["ticker", "industry", "total_score", "grade", "candidate_status", "market_cap"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def candidate_findings_payload(root):
    return {
        "review_schema": "candidate_findings_review",
        "review_version": 1,
        "as_of_date": "2026-07-05",
        "status": "manual_review_needed",
        "candidate_count": 3,
        "risk_action_required_count": 3,
        "risk_action_queue_count": 3,
        "formal_model_change_allowed": False,
        "markets": [
            {
                "name": "港股周筛",
                "path": str(root / "outputs" / "hk_universe"),
                "risk_action_queue": [
                    {
                        "ticker": "02367.HK",
                        "company": "GIANT BIOGENE",
                        "queue_action": "manual_fundamental_review",
                        "recommended_action": "manual_fundamental_review",
                        "risk_categories": ["weak_trend", "fundamental_risk"],
                        "risk": "走势偏弱；收入增长为负；净利润增长为负",
                        "expected_return": "0.59985",
                        "trend_label": "偏弱",
                        "valuation_confidence": "high",
                    },
                    {
                        "ticker": "00013.HK",
                        "company": "HUTCHMED",
                        "queue_action": "manual_fundamental_review",
                        "recommended_action": "manual_fundamental_review",
                        "risk_categories": ["weak_trend", "low_valuation_confidence", "fundamental_risk"],
                        "risk": "估值置信度低；走势偏弱；收入增长为负",
                        "expected_return": "0.6",
                        "trend_label": "偏弱",
                        "valuation_confidence": "low",
                    },
                ],
            },
            {
                "name": "A股周筛",
                "path": str(root / "outputs" / "cn_universe"),
                "risk_action_queue": [
                    {
                        "ticker": "603893.SH",
                        "company": "瑞芯微",
                        "queue_action": "defer_research",
                        "recommended_action": "deprioritize_or_wait",
                        "risk_categories": ["no_margin_of_safety", "negative_expected_return"],
                        "risk": "当前无安全边际；预期收益为负",
                        "expected_return": "-0.345776",
                        "trend_label": "温和偏强",
                        "valuation_confidence": "high",
                    }
                ],
            },
        ],
    }


class CandidateRiskPriorityReviewTests(unittest.TestCase):
    def test_builds_priority_queue_from_candidate_findings_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review = root / "outputs" / "automation" / "latest_candidate_findings_review.json"
            write_json(review, candidate_findings_payload(root))
            write_candidate_pool(
                root / "outputs" / "hk_universe" / "candidate_pool.csv",
                [
                    {
                        "ticker": "02367.HK",
                        "industry": "个人护理",
                        "total_score": "96",
                        "grade": "A",
                        "candidate_status": "candidate",
                        "market_cap": "63000000000",
                    },
                    {
                        "ticker": "00013.HK",
                        "industry": "药品及生物科技",
                        "total_score": "91",
                        "grade": "A",
                        "candidate_status": "candidate",
                        "market_cap": "28000000000",
                    },
                ],
            )
            write_candidate_pool(
                root / "outputs" / "cn_universe" / "candidate_pool.csv",
                [
                    {
                        "ticker": "603893.SH",
                        "industry": "半导体",
                        "total_score": "90",
                        "grade": "A",
                        "candidate_status": "candidate",
                        "market_cap": "80000000000",
                    }
                ],
            )

            from candidate_risk_priority_review import (
                build_candidate_risk_priority_review,
                render_candidate_risk_priority_review,
            )

            payload = build_candidate_risk_priority_review(review, as_of_date="2026-07-05")
            report = render_candidate_risk_priority_review(payload)

            self.assertEqual(payload["review_schema"], "candidate_risk_priority_review")
            self.assertEqual(payload["status"], "manual_review_needed")
            self.assertEqual(payload["risk_queue_count"], 3)
            self.assertEqual(payload["priority_research_count"], 1)
            self.assertEqual(payload["watchlist_count"], 1)
            self.assertEqual(payload["defer_count"], 1)
            self.assertFalse(payload["formal_model_change_allowed"])
            self.assertEqual(payload["items"][0]["ticker"], "02367.HK")
            self.assertEqual(payload["items"][0]["priority_tier"], "priority_research")
            self.assertEqual(payload["items"][0]["total_score"], 96.0)
            self.assertEqual(payload["items"][-1]["priority_tier"], "defer_research")
            self.assertIn("候选风险优先级复核", report)
            self.assertIn("priority_research", report)

    def test_cli_writes_json_and_markdown_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review = root / "outputs" / "automation" / "latest_candidate_findings_review.json"
            output = root / "priority.json"
            report = root / "priority.md"
            write_json(review, candidate_findings_payload(root))

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "candidate_risk_priority_review.py"),
                    "--candidate-findings-review",
                    str(review),
                    "--as-of-date",
                    "2026-07-05",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["risk_queue_count"], 3)
            self.assertFalse(payload["formal_model_change_allowed"])
            self.assertIn("候选风险优先级复核", report.read_text(encoding="utf-8-sig"))

    def test_powershell_wrapper_and_weekly_bundle_include_priority_review(self):
        wrapper = (PROJECT_ROOT / "scripts" / "run_candidate_risk_priority_review.ps1").read_text(
            encoding="utf-8-sig"
        )
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("candidate_risk_priority_review.py", wrapper)
        self.assertIn("latest_candidate_risk_priority_review.json", wrapper)
        self.assertIn("run_candidate_risk_priority_review", bundle)
        self.assertLess(
            bundle.index("run_candidate_findings_review"),
            bundle.index("run_candidate_risk_priority_review"),
        )
        self.assertLess(
            bundle.index("run_candidate_risk_priority_review"),
            bundle.index("run_forecast_performance_review"),
        )


if __name__ == "__main__":
    unittest.main()
