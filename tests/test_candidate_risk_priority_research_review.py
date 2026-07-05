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


def manual_review_plan_payload():
    return {
        "review_schema": "candidate_risk_manual_review_plan",
        "review_version": 1,
        "as_of_date": "2026-07-05",
        "status": "manual_review_plan_ready",
        "manual_review_item_count": 3,
        "priority_research_count": 2,
        "watchlist_count": 1,
        "defer_count": 0,
        "formal_model_change_allowed": False,
        "items": [
            {
                "review_id": "risk-001",
                "priority_tier": "priority_research",
                "market": "港股周筛",
                "ticker": "02367.HK",
                "company": "GIANT BIOGENE",
                "review_focus": "fundamental_and_trend_review",
                "queue_action": "manual_fundamental_review",
                "risk_categories": ["weak_trend", "fundamental_risk"],
                "risk": "走势偏弱；收入增长为负；净利润增长为负",
                "expected_return": 0.59985,
                "total_score": 90.0,
                "research_questions": ["核对收入变化", "检查现金流", "比较走势"],
                "minimum_evidence": ["weekly_report 对应条目", "最近一期财报", "近1个月走势"],
                "decision_options": [
                    "approve_priority_research",
                    "continue_tracking",
                    "downgrade_to_watchlist",
                ],
                "manual_decision": "",
                "decision_reason": "",
            },
            {
                "review_id": "risk-002",
                "priority_tier": "priority_research",
                "market": "港股周筛",
                "ticker": "09698.HK",
                "company": "GDS - SW",
                "review_focus": "fundamental_review",
                "queue_action": "manual_fundamental_review",
                "risk_categories": ["fundamental_risk"],
                "risk": "资产负债率偏高",
                "expected_return": 0.599724,
                "total_score": 80.0,
                "research_questions": ["检查资产负债率"],
                "minimum_evidence": ["最近一期财报"],
                "decision_options": ["approve_priority_research", "continue_tracking"],
                "manual_decision": "",
                "decision_reason": "",
            },
            {
                "review_id": "risk-003",
                "priority_tier": "watchlist_review",
                "market": "港股周筛",
                "ticker": "00013.HK",
                "company": "HUTCHMED",
                "review_focus": "valuation_input_review",
                "queue_action": "manual_fundamental_review",
                "risk_categories": ["low_valuation_confidence"],
                "risk": "估值置信度低",
                "expected_return": 0.6,
                "total_score": 91.0,
                "research_questions": ["复核估值输入"],
                "minimum_evidence": ["估值输入字段"],
                "decision_options": ["continue_tracking"],
                "manual_decision": "",
                "decision_reason": "",
            },
        ],
    }


class CandidateRiskPriorityResearchReviewTests(unittest.TestCase):
    def test_builds_priority_research_review_from_manual_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "latest_candidate_risk_manual_review_plan.json"
            write_json(source, manual_review_plan_payload())

            from candidate_risk_priority_research_review import (
                build_candidate_risk_priority_research_review,
                render_candidate_risk_priority_research_review,
            )

            payload = build_candidate_risk_priority_research_review(source, as_of_date="2026-07-05")
            report = render_candidate_risk_priority_research_review(payload)

            self.assertEqual(payload["review_schema"], "candidate_risk_priority_research_review")
            self.assertEqual(payload["status"], "priority_research_pending")
            self.assertEqual(payload["recommended_action"], "complete_priority_research_reviews")
            self.assertEqual(payload["priority_research_count"], 2)
            self.assertEqual(payload["pending_decision_count"], 2)
            self.assertFalse(payload["formal_model_change_allowed"])
            self.assertEqual(payload["focus_counts"]["fundamental_and_trend_review"], 1)
            self.assertEqual(payload["items"][0]["ticker"], "02367.HK")
            self.assertEqual(payload["items"][0]["suggested_disposition"], "priority_research_with_trend_caution")
            self.assertIn("候选风险优先研究复核", report)
            self.assertIn("02367.HK", report)
            self.assertIn("不修改正式模型", report)

    def test_cli_writes_json_markdown_and_csv_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "latest_candidate_risk_manual_review_plan.json"
            output = root / "latest_candidate_risk_priority_research_review.json"
            report = root / "latest_candidate_risk_priority_research_review.md"
            csv_output = root / "candidate_risk_priority_research_review.csv"
            write_json(source, manual_review_plan_payload())

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "candidate_risk_priority_research_review.py"),
                    "--candidate-risk-manual-review-plan",
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
            self.assertEqual(payload["priority_research_count"], 2)
            self.assertIn("候选风险优先研究复核", report.read_text(encoding="utf-8-sig"))
            with csv_output.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["ticker"], "02367.HK")
            self.assertEqual(rows[0]["suggested_disposition"], "priority_research_with_trend_caution")

    def test_powershell_wrapper_and_weekly_bundle_include_priority_research_review(self):
        wrapper = (
            PROJECT_ROOT / "scripts" / "run_candidate_risk_priority_research_review.ps1"
        ).read_text(encoding="utf-8-sig")
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("candidate_risk_priority_research_review.py", wrapper)
        self.assertIn("latest_candidate_risk_manual_review_plan.json", wrapper)
        self.assertIn("latest_candidate_risk_priority_research_review.json", wrapper)
        self.assertIn("candidate_risk_priority_research_review.csv", wrapper)
        self.assertIn("run_candidate_risk_priority_research_review", bundle)
        self.assertLess(
            bundle.index("run_candidate_risk_manual_review_plan"),
            bundle.index("run_candidate_risk_priority_research_review"),
        )
        self.assertLess(
            bundle.index("run_candidate_risk_priority_research_review"),
            bundle.index("run_forecast_performance_review"),
        )


if __name__ == "__main__":
    unittest.main()
