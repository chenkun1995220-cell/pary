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


def priority_review_payload():
    return {
        "review_schema": "candidate_risk_priority_review",
        "review_version": 1,
        "as_of_date": "2026-07-05",
        "status": "manual_review_needed",
        "risk_queue_count": 3,
        "priority_research_count": 1,
        "watchlist_count": 1,
        "defer_count": 1,
        "formal_model_change_allowed": False,
        "items": [
            {
                "market": "港股周筛",
                "ticker": "02367.HK",
                "company": "GIANT BIOGENE",
                "priority_tier": "priority_research",
                "queue_action": "manual_fundamental_review",
                "recommended_action": "manual_fundamental_review",
                "risk_categories": ["weak_trend", "fundamental_risk"],
                "risk": "走势偏弱；收入增长为负；净利润增长为负",
                "expected_return": 0.59985,
                "trend_label": "偏弱",
                "valuation_confidence": "high",
                "industry": "其他医疗保健",
                "total_score": 90.0,
                "grade": "A",
            },
            {
                "market": "港股周筛",
                "ticker": "00013.HK",
                "company": "HUTCHMED",
                "priority_tier": "watchlist_review",
                "queue_action": "manual_fundamental_review",
                "recommended_action": "manual_fundamental_review",
                "risk_categories": ["low_valuation_confidence", "fundamental_risk"],
                "risk": "估值置信度低；收入增长为负",
                "expected_return": 0.6,
                "trend_label": "偏弱",
                "valuation_confidence": "low",
                "industry": "药品及生物科技",
                "total_score": 91.0,
                "grade": "A",
            },
            {
                "market": "A股周筛",
                "ticker": "603893.SH",
                "company": "瑞芯微",
                "priority_tier": "defer_research",
                "queue_action": "defer_research",
                "recommended_action": "deprioritize_or_wait",
                "risk_categories": ["no_margin_of_safety", "negative_expected_return"],
                "risk": "当前无安全边际；预期收益为负",
                "expected_return": -0.34,
                "trend_label": "温和偏强",
                "valuation_confidence": "high",
                "industry": "半导体",
                "total_score": 90.0,
                "grade": "A",
            },
        ],
    }


class CandidateRiskManualReviewPlanTests(unittest.TestCase):
    def test_builds_actionable_manual_review_plan_from_priority_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "latest_candidate_risk_priority_review.json"
            write_json(source, priority_review_payload())

            from candidate_risk_manual_review_plan import (
                build_candidate_risk_manual_review_plan,
                render_candidate_risk_manual_review_plan,
            )

            payload = build_candidate_risk_manual_review_plan(source, as_of_date="2026-07-05")
            report = render_candidate_risk_manual_review_plan(payload)

            self.assertEqual(payload["review_schema"], "candidate_risk_manual_review_plan")
            self.assertEqual(payload["status"], "manual_review_plan_ready")
            self.assertEqual(payload["manual_review_item_count"], 3)
            self.assertEqual(payload["priority_research_count"], 1)
            self.assertFalse(payload["formal_model_change_allowed"])
            self.assertEqual(payload["items"][0]["ticker"], "02367.HK")
            self.assertEqual(payload["items"][0]["review_focus"], "fundamental_and_trend_review")
            self.assertTrue(
                any("核对最新收入和净利润变化" in question for question in payload["items"][0]["research_questions"])
            )
            self.assertIn("continue_tracking", payload["items"][0]["decision_options"])
            self.assertEqual(payload["items"][-1]["review_focus"], "defer_until_margin_returns")
            self.assertIn("候选风险人工复核清单", report)
            self.assertIn("fundamental_and_trend_review", report)

    def test_cli_writes_json_markdown_and_csv_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "latest_candidate_risk_priority_review.json"
            output = root / "plan.json"
            report = root / "plan.md"
            csv_output = root / "plan.csv"
            write_json(source, priority_review_payload())

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "candidate_risk_manual_review_plan.py"),
                    "--candidate-risk-priority-review",
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
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["manual_review_item_count"], 3)
            self.assertFalse(payload["formal_model_change_allowed"])
            self.assertIn("候选风险人工复核清单", report.read_text(encoding="utf-8-sig"))
            csv_text = csv_output.read_text(encoding="utf-8-sig")
            self.assertIn("review_id", csv_text)
            self.assertIn("02367.HK", csv_text)

    def test_powershell_wrapper_and_weekly_bundle_include_manual_review_plan(self):
        wrapper = (PROJECT_ROOT / "scripts" / "run_candidate_risk_manual_review_plan.ps1").read_text(
            encoding="utf-8-sig"
        )
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("candidate_risk_manual_review_plan.py", wrapper)
        self.assertIn("latest_candidate_risk_manual_review_plan.json", wrapper)
        self.assertIn("candidate_risk_manual_review_plan.csv", wrapper)
        self.assertIn("run_candidate_risk_manual_review_plan", bundle)
        self.assertLess(
            bundle.index("run_candidate_risk_priority_review"),
            bundle.index("run_candidate_risk_manual_review_plan"),
        )
        self.assertLess(
            bundle.index("run_candidate_risk_manual_review_plan"),
            bundle.index("run_forecast_performance_review"),
        )


if __name__ == "__main__":
    unittest.main()
