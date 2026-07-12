import json
import tempfile
import unittest
from pathlib import Path


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8-sig")


def write_sources(root, as_of_date="2026-07-12"):
    automation = root / "outputs" / "automation"
    write_json(
        automation / "latest_candidate_risk_resolution_review.json",
        {
            "review_schema": "candidate_risk_resolution_review",
            "review_version": 1,
            "as_of_date": as_of_date,
            "status": "ready",
            "items": [
                {
                    "market": "港股周筛",
                    "ticker": ticker,
                    "company": company,
                    "manual_decision_required": True,
                    "total_score": 80 + index,
                    "current_price": 10 + index,
                    "buy_price": 8 + index,
                    "target_price": 12 + index,
                    "expected_return": 0.5,
                    "sensitivity": {"status": "capped"},
                    "core_risks": ["估值上限需要人工复核"],
                    "buy_conditions": ["安全边际满足"],
                    "abandon_conditions": ["基本面恶化"],
                    "deep_dive_review": {
                        "status": "completed",
                        "research_recommendation": "continue_tracking",
                    },
                }
                for index, (ticker, company) in enumerate(
                    [
                        ("06110.HK", "TOPSPORTS"),
                        ("09698.HK", "GDS - SW"),
                        ("02367.HK", "GIANT BIOGENE"),
                        ("00512.HK", "GRAND PHARMA"),
                        ("00288.HK", "WH GROUP"),
                    ]
                )
            ],
            "formal_model_change_allowed": False,
        },
    )
    write_json(
        automation / "latest_one_week_forecast_shadow_disposition.json",
        {
            "disposition_schema": "one_week_forecast_shadow_disposition",
            "disposition_version": 1,
            "as_of_date": as_of_date,
            "evaluation_as_of_date": as_of_date,
            "status": "ready",
            "candidate_dispositions": [
                {
                    "action_code": "shadow_demote_down_signal_to_neutral",
                    "disposition": "pending_human_approval",
                    "independent_batch_count": 3,
                    "evaluation_sample_count": 122,
                    "comparable_sample_count": 122,
                    "affected_count": 40,
                    "affected_market_count": 3,
                    "affected_markets": ["A股周筛", "港股周筛", "美股周筛"],
                    "baseline_hit_rate": 0.1639,
                    "shadow_hit_rate": 0.3852,
                    "aggregate_hit_rate_delta": 0.2213,
                    "severe_market_deterioration": [],
                },
                {
                    "action_code": "shadow_widen_neutral_band",
                    "disposition": "rejected",
                },
            ],
            "formal_model_change_allowed": False,
        },
    )


class HumanDecisionInboxTests(unittest.TestCase):
    def test_builds_six_item_pending_inbox_from_current_sources(self):
        from human_decision_inbox import build_human_decision_inbox

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_sources(root)

            payload = build_human_decision_inbox(root, as_of_date="2026-07-12")

            self.assertEqual(payload["inbox_schema"], "human_decision_inbox")
            self.assertEqual(payload["item_count"], 6)
            self.assertEqual(payload["pending_count"], 6)
            self.assertEqual(payload["decided_count"], 0)
            self.assertEqual(payload["invalid_decision_count"], 0)
            self.assertEqual(payload["status"], "manual_review_needed")
            self.assertEqual(
                {item["item_type"] for item in payload["items"]},
                {"candidate_risk", "forecast_shadow"},
            )
            keys = {item["decision_key"] for item in payload["items"]}
            self.assertIn("candidate_risk|港股周筛|06110.HK|2026-07-12", keys)
            self.assertIn(
                "forecast_shadow|shadow_demote_down_signal_to_neutral|2026-07-12",
                keys,
            )
            self.assertFalse(payload["trade_execution_allowed"])
            self.assertFalse(payload["formal_model_change_allowed"])
            self.assertFalse(payload["formal_model_conclusion_allowed"])

    def test_empty_valid_sources_are_ready(self):
        from human_decision_inbox import build_human_decision_inbox

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_sources(root)
            risk_path = root / "outputs" / "automation" / "latest_candidate_risk_resolution_review.json"
            risk = json.loads(risk_path.read_text(encoding="utf-8-sig"))
            risk["items"] = []
            write_json(risk_path, risk)
            shadow_path = root / "outputs" / "automation" / "latest_one_week_forecast_shadow_disposition.json"
            shadow = json.loads(shadow_path.read_text(encoding="utf-8-sig"))
            shadow["candidate_dispositions"] = []
            write_json(shadow_path, shadow)

            payload = build_human_decision_inbox(root, as_of_date="2026-07-12")

            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["recommended_action"], "monitor_next_run")
            self.assertEqual(payload["item_count"], 0)


if __name__ == "__main__":
    unittest.main()
