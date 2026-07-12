import json
import csv
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


def write_authorizations(root, rows):
    path = root / "data" / "manual" / "human_decision_authorizations.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "decision_key",
        "decision",
        "decided_by",
        "decided_at",
        "decision_reason",
        "boundary_acknowledgement",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


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

    def test_validates_type_specific_decisions(self):
        from human_decision_inbox import build_human_decision_inbox

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_sources(root)
            write_authorizations(
                root,
                [
                    {
                        "decision_key": "candidate_risk|港股周筛|06110.HK|2026-07-12",
                        "decision": "approve_for_continued_research",
                        "decided_by": "user",
                        "decided_at": "2026-07-12T15:30:00+08:00",
                        "decision_reason": "研究底稿完整，继续观察基本面",
                        "boundary_acknowledgement": "human_decision_only_no_trade_or_model_change",
                    },
                    {
                        "decision_key": "forecast_shadow|shadow_demote_down_signal_to_neutral|2026-07-12",
                        "decision": "approve_for_extended_shadow_validation",
                        "decided_by": "user",
                        "decided_at": "2026-07-12T15:31:00+08:00",
                        "decision_reason": "允许积累更多影子样本",
                        "boundary_acknowledgement": "human_decision_only_no_trade_or_model_change",
                    },
                ],
            )

            payload = build_human_decision_inbox(root, as_of_date="2026-07-12")

            self.assertEqual(payload["decided_count"], 2)
            self.assertEqual(payload["pending_count"], 4)
            self.assertEqual(payload["invalid_decision_count"], 0)
            decided = {
                item["decision_key"]: item
                for item in payload["items"]
                if item["decision_status"] == "decided"
            }
            self.assertEqual(
                decided["candidate_risk|港股周筛|06110.HK|2026-07-12"]["decision"],
                "approve_for_continued_research",
            )
            self.assertEqual(
                decided[
                    "forecast_shadow|shadow_demote_down_signal_to_neutral|2026-07-12"
                ]["decision"],
                "approve_for_extended_shadow_validation",
            )

    def test_rejects_conflicts_invalid_fields_and_old_batch_decisions(self):
        from human_decision_inbox import build_human_decision_inbox

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_sources(root)
            write_authorizations(
                root,
                [
                    {
                        "decision_key": "candidate_risk|港股周筛|06110.HK|2026-07-12",
                        "decision": "approve_for_extended_shadow_validation",
                        "decided_by": "user",
                        "decided_at": "2026-07-12T15:30:00+08:00",
                        "decision_reason": "错误类型决定",
                        "boundary_acknowledgement": "human_decision_only_no_trade_or_model_change",
                    },
                    {
                        "decision_key": "candidate_risk|港股周筛|09698.HK|2026-07-12",
                        "decision": "continue_observation",
                        "decided_by": "user",
                        "decided_at": "2026-07-12T15:31:00+08:00",
                        "decision_reason": "",
                        "boundary_acknowledgement": "human_decision_only_no_trade_or_model_change",
                    },
                    {
                        "decision_key": "candidate_risk|港股周筛|02367.HK|2026-07-12",
                        "decision": "continue_observation",
                        "decided_by": "user",
                        "decided_at": "2026-07-12T15:32:00+08:00",
                        "decision_reason": "先观察",
                        "boundary_acknowledgement": "wrong_boundary",
                    },
                    {
                        "decision_key": "candidate_risk|港股周筛|00512.HK|2026-07-12",
                        "decision": "continue_observation",
                        "decided_by": "user",
                        "decided_at": "2026-07-12T15:33:00+08:00",
                        "decision_reason": "先观察",
                        "boundary_acknowledgement": "human_decision_only_no_trade_or_model_change",
                    },
                    {
                        "decision_key": "candidate_risk|港股周筛|00512.HK|2026-07-12",
                        "decision": "reject_candidate_research",
                        "decided_by": "user",
                        "decided_at": "2026-07-12T15:34:00+08:00",
                        "decision_reason": "冲突决定",
                        "boundary_acknowledgement": "human_decision_only_no_trade_or_model_change",
                    },
                    {
                        "decision_key": "candidate_risk|港股周筛|00288.HK|2026-07-05",
                        "decision": "continue_observation",
                        "decided_by": "user",
                        "decided_at": "2026-07-05T15:30:00+08:00",
                        "decision_reason": "旧批次",
                        "boundary_acknowledgement": "human_decision_only_no_trade_or_model_change",
                    },
                ],
            )

            payload = build_human_decision_inbox(root, as_of_date="2026-07-12")

            self.assertEqual(payload["decided_count"], 0)
            self.assertEqual(payload["pending_count"], 6)
            self.assertEqual(payload["invalid_decision_count"], 4)
            self.assertIn(
                "conflicting_authorizations:candidate_risk|港股周筛|00512.HK|2026-07-12",
                payload["issues"],
            )
            self.assertTrue(
                all(item["decision_status"] == "pending" for item in payload["items"])
            )

    def test_decision_history_is_idempotent(self):
        from human_decision_inbox import (
            append_decision_history,
            build_human_decision_inbox,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_sources(root)
            write_authorizations(
                root,
                [
                    {
                        "decision_key": "candidate_risk|港股周筛|06110.HK|2026-07-12",
                        "decision": "approve_for_continued_research",
                        "decided_by": "user",
                        "decided_at": "2026-07-12T15:30:00+08:00",
                        "decision_reason": "继续研究",
                        "boundary_acknowledgement": "human_decision_only_no_trade_or_model_change",
                    },
                    {
                        "decision_key": "forecast_shadow|shadow_demote_down_signal_to_neutral|2026-07-12",
                        "decision": "approve_for_extended_shadow_validation",
                        "decided_by": "user",
                        "decided_at": "2026-07-12T15:31:00+08:00",
                        "decision_reason": "继续影子验证",
                        "boundary_acknowledgement": "human_decision_only_no_trade_or_model_change",
                    },
                ],
            )
            payload = build_human_decision_inbox(root, as_of_date="2026-07-12")
            history = root / "outputs" / "automation" / "human_decision_history.csv"

            self.assertEqual(append_decision_history(payload, history), 2)
            self.assertEqual(append_decision_history(payload, history), 0)
            with history.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual(
                len({(row["decision_key"], row["decision"], row["decided_at"]) for row in rows}),
                2,
            )


if __name__ == "__main__":
    unittest.main()
