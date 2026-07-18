import csv
import json
import tempfile
import unittest
from pathlib import Path


ACTION = "shadow_demote_down_signal_to_neutral"
BOUNDARY = "human_decision_only_no_trade_or_model_change"


def validation_row(batch_date, action=ACTION, baseline_hits=4, shadow_hits=6):
    return {
        "action_code": action,
        "evaluation_as_of_date": batch_date,
        "validation_status": "validated",
        "evaluation_sample_count": 10,
        "affected_count": 4,
        "baseline_hit_count": baseline_hits,
        "shadow_hit_count": shadow_hits,
        "market_results": [
            {
                "market": "美股周筛",
                "sample_count": 10,
                "affected_count": 4,
                "baseline_hit_count": baseline_hits,
                "shadow_hit_count": shadow_hits,
            }
        ],
        "formal_model_change_allowed": False,
    }


class ExtendedShadowValidationTrackerTests(unittest.TestCase):
    def make_project(self, rows, authorization_date="2026-07-12"):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        output = root / "outputs" / "automation"
        output.mkdir(parents=True)

        decision_key = f"forecast_shadow|{ACTION}|{authorization_date}"
        history_fields = [
            "history_key",
            "decision_key",
            "item_type",
            "source_as_of_date",
            "decision",
            "decided_by",
            "decided_at",
            "decision_reason",
            "boundary_acknowledgement",
        ]
        history_row = {
            "history_key": f"{decision_key}|approve_for_extended_shadow_validation|2026-07-12T18:48:55+08:00",
            "decision_key": decision_key,
            "item_type": "forecast_shadow",
            "source_as_of_date": authorization_date,
            "decision": "approve_for_extended_shadow_validation",
            "decided_by": "user",
            "decided_at": "2026-07-12T18:48:55+08:00",
            "decision_reason": "允许继续积累三批影子验证样本",
            "boundary_acknowledgement": BOUNDARY,
        }
        with (output / "human_decision_history.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=history_fields)
            writer.writeheader()
            writer.writerow(history_row)

        with (output / "one_week_forecast_shadow_parameter_validation_history.jsonl").open(
            "w", encoding="utf-8"
        ) as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

        inbox = {
            "inbox_schema": "human_decision_inbox",
            "inbox_version": 1,
            "as_of_date": authorization_date,
            "status": "ready",
            "items": [
                {
                    "item_type": "forecast_shadow",
                    "decision_key": decision_key,
                    "source_as_of_date": authorization_date,
                    "action_code": ACTION,
                    "decision_status": "decided",
                    "decision": "approve_for_extended_shadow_validation",
                    "boundary_acknowledgement": BOUNDARY,
                    "trade_execution_allowed": False,
                    "formal_model_change_allowed": False,
                    "formal_model_conclusion_allowed": False,
                }
            ],
            "trade_execution_allowed": False,
            "formal_model_change_allowed": False,
            "formal_model_conclusion_allowed": False,
        }
        (output / "latest_human_decision_inbox.json").write_text(
            json.dumps(inbox, ensure_ascii=False), encoding="utf-8"
        )

        disposition = {
            "disposition_schema": "one_week_forecast_shadow_disposition",
            "disposition_version": 1,
            "as_of_date": authorization_date,
            "status": "ready",
            "candidate_dispositions": [
                {
                    "action_code": ACTION,
                    "disposition": "pending_human_approval",
                    "formal_model_change_allowed": False,
                }
            ],
            "formal_model_change_allowed": False,
        }
        (output / "latest_one_week_forecast_shadow_disposition.json").write_text(
            json.dumps(disposition, ensure_ascii=False), encoding="utf-8"
        )
        return temporary, root

    def test_preapproval_batches_do_not_consume_extended_allowance(self):
        from extended_shadow_validation_tracker import (
            build_extended_shadow_validation_tracker,
            render_extended_shadow_validation_tracker,
        )

        rows = [validation_row(day) for day in ("2026-07-09", "2026-07-11", "2026-07-12")]
        temporary, root = self.make_project(rows)
        self.addCleanup(temporary.cleanup)

        payload = build_extended_shadow_validation_tracker(root, as_of_date="2026-07-12")
        item = payload["items"][0]

        self.assertEqual(payload["status"], "active")
        self.assertEqual(item["post_approval_history_batch_count"], 0)
        self.assertEqual(item["evaluable_batch_count"], 0)
        self.assertEqual(item["remaining_evaluable_batch_count"], 3)
        self.assertEqual(item["status"], "active")
        self.assertEqual(item["recommended_action"], "continue_extended_shadow_validation")
        self.assertIn("0/3", render_extended_shadow_validation_tracker(payload))
        self.assertFalse(payload["trade_execution_allowed"])
        self.assertFalse(payload["formal_model_change_allowed"])
        self.assertFalse(payload["formal_model_conclusion_allowed"])

    def test_reapproval_supersedes_older_authorization_for_same_action(self):
        from extended_shadow_validation_tracker import build_extended_shadow_validation_tracker

        temporary, root = self.make_project([validation_row("2026-07-13")])
        self.addCleanup(temporary.cleanup)
        output = root / "outputs" / "automation"
        history_path = output / "human_decision_history.csv"
        with history_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
            fields = list(rows[0])

        new_date = "2026-07-18"
        new_key = f"forecast_shadow|{ACTION}|{new_date}"
        new_authorization = dict(rows[0])
        new_authorization.update(
            {
                "history_key": (
                    f"{new_key}|approve_for_extended_shadow_validation|"
                    "2026-07-18T16:21:54+08:00"
                ),
                "decision_key": new_key,
                "source_as_of_date": new_date,
                "decided_at": "2026-07-18T16:21:54+08:00",
                "decision_reason": "approve a new three-batch validation cycle",
            }
        )
        with history_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows([rows[0], new_authorization])

        inbox_path = output / "latest_human_decision_inbox.json"
        inbox = json.loads(inbox_path.read_text(encoding="utf-8"))
        inbox["as_of_date"] = new_date
        inbox["items"][0].update(
            {
                "decision_key": new_key,
                "source_as_of_date": new_date,
            }
        )
        inbox_path.write_text(json.dumps(inbox), encoding="utf-8")

        payload = build_extended_shadow_validation_tracker(root, as_of_date=new_date)

        self.assertEqual(payload["status"], "active")
        self.assertEqual(payload["authorization_count"], 1)
        self.assertEqual(payload["items"][0]["authorization_date"], new_date)
        self.assertEqual(payload["items"][0]["post_approval_history_batch_count"], 0)
        self.assertEqual(payload["items"][0]["remaining_evaluable_batch_count"], 3)

    def test_classifies_post_approval_batches(self):
        from extended_shadow_validation_tracker import classify_batch

        positive = classify_batch([validation_row("2026-07-19", baseline_hits=4, shadow_hits=6)])
        negative = classify_batch([validation_row("2026-07-26", baseline_hits=6, shadow_hits=4)])
        not_evaluable_row = validation_row("2026-08-02")
        not_evaluable_row.update(
            {
                "validation_status": "not_evaluable_current_fields",
                "evaluation_sample_count": 0,
                "baseline_hit_count": 0,
                "shadow_hit_count": None,
                "market_results": [],
            }
        )
        not_evaluable = classify_batch([not_evaluable_row])
        severe_row = validation_row("2026-08-09", baseline_hits=4, shadow_hits=7)
        severe_row["market_results"][0]["severe_deterioration"] = True
        severe = classify_batch([severe_row])

        self.assertEqual(positive["classification"], "positive")
        self.assertEqual(positive["comparable_sample_count"], 10)
        self.assertAlmostEqual(positive["aggregate_hit_rate_delta"], 0.2)
        self.assertEqual(negative["classification"], "negative")
        self.assertLessEqual(negative["aggregate_hit_rate_delta"], 0)
        self.assertEqual(not_evaluable["classification"], "not_evaluable")
        self.assertEqual(not_evaluable["comparable_sample_count"], 0)
        self.assertEqual(severe["classification"], "severe_deterioration")
        self.assertEqual(severe["severe_markets"], ["美股周筛"])

    def test_three_evaluable_batches_require_reapproval(self):
        from extended_shadow_validation_tracker import build_extended_shadow_validation_tracker

        rows = [validation_row(day) for day in ("2026-07-19", "2026-07-26", "2026-08-02")]
        temporary, root = self.make_project(rows)
        self.addCleanup(temporary.cleanup)

        payload = build_extended_shadow_validation_tracker(root, as_of_date="2026-08-02")
        item = payload["items"][0]

        self.assertEqual(payload["status"], "ready_for_reapproval")
        self.assertEqual(item["evaluable_batch_count"], 3)
        self.assertEqual(item["remaining_evaluable_batch_count"], 0)
        self.assertEqual(item["status"], "ready_for_reapproval")
        self.assertEqual(item["recommended_action"], "review_extended_shadow_validation_results")

    def test_severe_batch_pauses_immediately(self):
        from extended_shadow_validation_tracker import build_extended_shadow_validation_tracker

        row = validation_row("2026-07-19")
        row["market_results"][0]["severe_deterioration"] = True
        temporary, root = self.make_project([row])
        self.addCleanup(temporary.cleanup)

        payload = build_extended_shadow_validation_tracker(root, as_of_date="2026-07-19")
        item = payload["items"][0]

        self.assertEqual(payload["status"], "paused_severe_deterioration")
        self.assertEqual(item["severe_deterioration_batch_count"], 1)
        self.assertEqual(item["status"], "paused_severe_deterioration")
        self.assertEqual(item["recommended_action"], "request_shadow_safety_reapproval")

    def test_not_evaluable_batch_does_not_break_consecutive_negative_sequence(self):
        from extended_shadow_validation_tracker import build_extended_shadow_validation_tracker

        first_negative = validation_row("2026-07-19", baseline_hits=6, shadow_hits=4)
        not_evaluable = validation_row("2026-07-26")
        not_evaluable.update(
            {
                "validation_status": "not_evaluable_current_fields",
                "evaluation_sample_count": 0,
                "baseline_hit_count": 0,
                "shadow_hit_count": None,
                "market_results": [],
            }
        )
        second_negative = validation_row("2026-08-02", baseline_hits=5, shadow_hits=5)
        temporary, root = self.make_project(
            [first_negative, not_evaluable, second_negative]
        )
        self.addCleanup(temporary.cleanup)

        payload = build_extended_shadow_validation_tracker(root, as_of_date="2026-08-02")
        item = payload["items"][0]

        self.assertEqual(payload["status"], "paused_two_consecutive_negative_batches")
        self.assertEqual(item["post_approval_history_batch_count"], 3)
        self.assertEqual(item["evaluable_batch_count"], 2)
        self.assertEqual(item["not_evaluable_batch_count"], 1)
        self.assertEqual(item["consecutive_negative_batch_count"], 2)
        self.assertEqual(item["remaining_evaluable_batch_count"], 1)

    def assert_blocked(self, root, reason_code):
        from extended_shadow_validation_tracker import build_extended_shadow_validation_tracker

        payload = build_extended_shadow_validation_tracker(root, as_of_date="2026-07-19")
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["recommended_action"], "repair_extended_shadow_validation_inputs")
        self.assertIn(reason_code, payload["issues"])
        self.assertFalse(payload["formal_model_change_allowed"])

    def test_duplicate_batch_key_counts_once(self):
        from extended_shadow_validation_tracker import build_extended_shadow_validation_tracker

        row = validation_row("2026-07-19")
        temporary, root = self.make_project([row, dict(row)])
        self.addCleanup(temporary.cleanup)

        payload = build_extended_shadow_validation_tracker(root, as_of_date="2026-07-19")

        self.assertEqual(payload["items"][0]["post_approval_history_batch_count"], 1)
        self.assertEqual(payload["items"][0]["evaluable_batch_count"], 1)

    def test_malformed_decision_history_blocks(self):
        temporary, root = self.make_project([validation_row("2026-07-19")])
        self.addCleanup(temporary.cleanup)
        (root / "outputs" / "automation" / "human_decision_history.csv").write_text(
            "unexpected\nvalue\n", encoding="utf-8"
        )

        self.assert_blocked(root, "decision_history_columns_invalid")

    def test_conflicting_authorization_rows_block(self):
        temporary, root = self.make_project([validation_row("2026-07-19")])
        self.addCleanup(temporary.cleanup)
        history_path = root / "outputs" / "automation" / "human_decision_history.csv"
        with history_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
            fields = list(rows[0])
        conflict = dict(rows[0])
        conflict["history_key"] = conflict["history_key"].replace(
            "2026-07-12T18:48:55+08:00", "2026-07-12T19:00:00+08:00"
        )
        conflict["decided_at"] = "2026-07-12T19:00:00+08:00"
        conflict["decision_reason"] = "冲突的重复授权"
        with history_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows([rows[0], conflict])

        self.assert_blocked(root, "authorization_decision_key_conflict")

    def test_approval_and_rejection_for_same_decision_key_block(self):
        temporary, root = self.make_project([validation_row("2026-07-19")])
        self.addCleanup(temporary.cleanup)
        history_path = root / "outputs" / "automation" / "human_decision_history.csv"
        with history_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
            fields = list(rows[0])
        rejection = dict(rows[0])
        rejection["history_key"] = rejection["history_key"].replace(
            "approve_for_extended_shadow_validation", "reject_shadow_candidate"
        )
        rejection["decision"] = "reject_shadow_candidate"
        rejection["decision_reason"] = "拒绝同一影子方案"
        with history_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows([rows[0], rejection])

        self.assert_blocked(root, "authorization_decision_key_conflict")

    def test_future_validation_batch_blocks_instead_of_consuming_allowance(self):
        temporary, root = self.make_project([validation_row("2026-07-26")])
        self.addCleanup(temporary.cleanup)

        self.assert_blocked(root, "validation_history_batch_in_future")

    def test_invalid_authorization_boundary_blocks(self):
        temporary, root = self.make_project([validation_row("2026-07-19")])
        self.addCleanup(temporary.cleanup)
        history_path = root / "outputs" / "automation" / "human_decision_history.csv"
        content = history_path.read_text(encoding="utf-8-sig").replace(
            BOUNDARY, "unsafe_boundary"
        )
        history_path.write_text(content, encoding="utf-8-sig")

        self.assert_blocked(root, "authorization_boundary_invalid")

    def test_malformed_validation_history_blocks_with_stable_code(self):
        temporary, root = self.make_project([validation_row("2026-07-19")])
        self.addCleanup(temporary.cleanup)
        history_path = (
            root
            / "outputs"
            / "automation"
            / "one_week_forecast_shadow_parameter_validation_history.jsonl"
        )
        history_path.write_text("{not-json}\n", encoding="utf-8")

        self.assert_blocked(root, "validation_history_json_invalid")

    def test_disposition_action_mismatch_blocks(self):
        temporary, root = self.make_project([validation_row("2026-07-19")])
        self.addCleanup(temporary.cleanup)
        disposition_path = (
            root / "outputs" / "automation" / "latest_one_week_forecast_shadow_disposition.json"
        )
        disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
        disposition["candidate_dispositions"][0]["action_code"] = "different_action"
        disposition_path.write_text(json.dumps(disposition), encoding="utf-8")

        self.assert_blocked(root, "authorization_action_missing_from_disposition")


if __name__ == "__main__":
    unittest.main()
