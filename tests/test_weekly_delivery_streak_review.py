import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def consistency_payload(day="2026-07-12", hk_start="2026-07-12 14:30:05"):
    starts = {
        "US": f"{day} 14:05:10",
        "CN": f"{day} 14:10:10",
        "HK": hk_start,
    }
    completed = {
        "US": f"{day} 14:12:00",
        "CN": f"{day} 14:18:00",
        "HK": f"{day} 14:50:00",
    }
    counts = {"US": 20, "CN": 6, "HK": 37}
    return {
        "as_of_date": day,
        "status": "ready",
        "issues": [],
        "market_run_dates": [day],
        "candidate_count_total": 63,
        "conclusion_candidate_count_total": 63,
        "delivery_candidate_count_total": 63,
        "markets": [
            {
                "market": market,
                "run_date": day,
                "run_started_at": starts[market],
                "run_completed_at": completed[market],
                "summary_candidate_count": counts[market],
                "candidate_file_count": counts[market],
            }
            for market in ("US", "CN", "HK")
        ],
        "formal_model_change_allowed": False,
    }


def delivery_payload(day="2026-07-12"):
    return {"as_of_date": day, "status": "ready", "candidate_count_total": 63}


def pre_submit_payload(day="2026-07-12"):
    return {"as_of_date": day, "status": "ready"}


def success_record(day):
    return {
        "as_of_date": day,
        "sunday_success": True,
        "issues": [],
        "hk_start_window_status": "ready",
    }


class WeeklyDeliveryStreakReviewTests(unittest.TestCase):
    def test_non_sunday_does_not_create_history_record(self):
        from weekly_delivery_streak_review import build_weekly_delivery_streak_review

        payload, record = build_weekly_delivery_streak_review(
            consistency_payload("2026-07-11", "2026-07-11 14:30:05"),
            delivery_payload("2026-07-11"),
            pre_submit_payload("2026-07-11"),
            [],
            as_of_date="2026-07-11",
        )

        self.assertEqual(payload["status"], "not_scheduled_day")
        self.assertIsNone(record)
        self.assertEqual(payload["consecutive_sunday_ready_count"], 0)

    def test_same_sunday_replaces_existing_record(self):
        from weekly_delivery_streak_review import update_history

        old = {**success_record("2026-07-12"), "candidate_count_total": 60}
        new = {**success_record("2026-07-12"), "candidate_count_total": 63}
        rows = update_history([old], new)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["candidate_count_total"], 63)

    def test_three_consecutive_successful_sundays_are_ready(self):
        from weekly_delivery_streak_review import build_weekly_delivery_streak_review

        payload, record = build_weekly_delivery_streak_review(
            consistency_payload("2026-07-26", "2026-07-26 14:30:05"),
            delivery_payload("2026-07-26"),
            pre_submit_payload("2026-07-26"),
            [success_record("2026-07-12"), success_record("2026-07-19")],
            as_of_date="2026-07-26",
        )

        self.assertTrue(record["sunday_success"])
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["consecutive_sunday_ready_count"], 3)
        self.assertEqual(payload["successful_sunday_dates"], [
            "2026-07-12", "2026-07-19", "2026-07-26"
        ])
        self.assertEqual(payload["first_hk_1430_validation_status"], "ready")
        self.assertFalse(payload["formal_model_change_allowed"])

    def test_date_gap_breaks_consecutive_streak(self):
        from weekly_delivery_streak_review import build_weekly_delivery_streak_review

        payload, _ = build_weekly_delivery_streak_review(
            consistency_payload("2026-08-02", "2026-08-02 14:30:05"),
            delivery_payload("2026-08-02"),
            pre_submit_payload("2026-08-02"),
            [success_record("2026-07-12"), success_record("2026-07-19")],
            as_of_date="2026-08-02",
        )

        self.assertEqual(payload["status"], "accumulating")
        self.assertEqual(payload["consecutive_sunday_ready_count"], 1)
        self.assertEqual(payload["successful_sunday_dates"], ["2026-08-02"])

    def test_candidate_count_mismatch_fails_current_sunday(self):
        from weekly_delivery_streak_review import build_weekly_delivery_streak_review

        consistency = consistency_payload()
        consistency["delivery_candidate_count_total"] = 62
        payload, record = build_weekly_delivery_streak_review(
            consistency, delivery_payload(), pre_submit_payload(), [], as_of_date="2026-07-12"
        )

        self.assertEqual(payload["status"], "needs_attention")
        self.assertFalse(record["sunday_success"])
        self.assertIn("candidate_count_total_mismatch", record["issues"])

    def test_hk_start_outside_window_fails_current_sunday(self):
        from weekly_delivery_streak_review import build_weekly_delivery_streak_review

        payload, record = build_weekly_delivery_streak_review(
            consistency_payload(hk_start="2026-07-12 14:45:01"),
            delivery_payload(),
            pre_submit_payload(),
            [],
            as_of_date="2026-07-12",
        )

        self.assertEqual(payload["status"], "needs_attention")
        self.assertEqual(record["hk_start_window_status"], "needs_attention")
        self.assertIn("hk_run_start_outside_1430_window", record["issues"])

    def test_hk_start_a_few_seconds_after_1430_is_accepted(self):
        from weekly_delivery_streak_review import build_weekly_delivery_streak_review

        payload, record = build_weekly_delivery_streak_review(
            consistency_payload(hk_start="2026-07-12 14:30:05"),
            delivery_payload(),
            pre_submit_payload(),
            [],
            as_of_date="2026-07-12",
        )

        self.assertEqual(payload["status"], "accumulating")
        self.assertTrue(record["sunday_success"])
        self.assertEqual(payload["first_hk_1430_validation_status"], "ready")

    def test_cli_writes_outputs_but_not_history_on_saturday(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            automation = root / "outputs" / "automation"
            automation.mkdir(parents=True)
            for name, payload in (
                ("latest_weekly_artifact_consistency.json", consistency_payload("2026-07-11", "2026-07-11 14:30:05")),
                ("latest_weekly_delivery_check.json", delivery_payload("2026-07-11")),
                ("latest_pre_submit_review.json", pre_submit_payload("2026-07-11")),
            ):
                (automation / name).write_text(json.dumps(payload), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable, str(PROJECT_ROOT / "weekly_delivery_streak_review.py"),
                    "--project-root", str(root), "--as-of-date", "2026-07-11",
                ],
                text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((automation / "latest_weekly_delivery_streak_review.json").exists())
            self.assertFalse((automation / "weekly_delivery_streak_history.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
