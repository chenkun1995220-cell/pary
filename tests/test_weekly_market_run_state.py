import json
import tempfile
import unittest
from pathlib import Path


class WeeklyMarketRunStateTests(unittest.TestCase):
    def test_writes_ready_state_with_hard_safety_boundary(self):
        from weekly_market_run_state import write_market_run_state

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "outputs" / "us_universe" / "latest_run_state.json"
            summary = root / "outputs" / "us_universe" / "latest_run_summary.md"
            candidates = root / "outputs" / "us_universe" / "candidate_pool.csv"
            log = root / "outputs" / "us_universe" / "run.log"

            payload = write_market_run_state(
                output,
                "US",
                "ready",
                "2026-07-18 14:05:00",
                run_completed_at="2026-07-18 14:08:00",
                summary_path=str(summary),
                candidate_path=str(candidates),
                log_path=str(log),
            )

            saved = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["run_state_schema"], "weekly_market_run_state")
            self.assertEqual(payload["run_state_version"], 1)
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["as_of_date"], "2026-07-18")
            self.assertFalse(payload["formal_model_change_allowed"])
            self.assertEqual(saved, payload)

    def test_running_state_allows_empty_completion_and_failure_fields(self):
        from weekly_market_run_state import write_market_run_state

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "latest_run_state.json"
            payload = write_market_run_state(
                output,
                "CN",
                "running",
                "2026-07-18 14:10:00",
            )

            self.assertEqual(payload["run_completed_at"], "")
            self.assertEqual(payload["failure_step"], "")
            self.assertEqual(payload["failure_message"], "")

    def test_failed_state_requires_failure_message(self):
        from weekly_market_run_state import write_market_run_state

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "latest_run_state.json"
            with self.assertRaisesRegex(ValueError, "failure_message_required"):
                write_market_run_state(
                    output,
                    "HK",
                    "failed",
                    "2026-07-18 14:30:00",
                )

    def test_rejects_invalid_market_status_or_timestamp(self):
        from weekly_market_run_state import write_market_run_state

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "latest_run_state.json"
            with self.assertRaisesRegex(ValueError, "market_invalid"):
                write_market_run_state(
                    output,
                    "EU",
                    "running",
                    "2026-07-18 14:05:00",
                )
            with self.assertRaisesRegex(ValueError, "status_invalid"):
                write_market_run_state(
                    output,
                    "US",
                    "complete",
                    "2026-07-18 14:05:00",
                )
            with self.assertRaisesRegex(ValueError, "run_started_at_invalid"):
                write_market_run_state(output, "US", "running", "not-a-time")

    def test_ready_state_requires_completion_timestamp(self):
        from weekly_market_run_state import write_market_run_state

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "latest_run_state.json"
            with self.assertRaisesRegex(ValueError, "run_completed_at_required"):
                write_market_run_state(
                    output,
                    "US",
                    "ready",
                    "2026-07-18 14:05:00",
                )


if __name__ == "__main__":
    unittest.main()
