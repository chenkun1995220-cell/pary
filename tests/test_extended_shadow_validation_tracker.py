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


if __name__ == "__main__":
    unittest.main()
