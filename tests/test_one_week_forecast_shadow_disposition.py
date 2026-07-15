import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ACTION = "shadow_demote_down_signal_to_neutral"
WIDEN_ACTION = "shadow_widen_neutral_band"


def history_row(
    batch_date,
    action=ACTION,
    affected=10,
    markets=("US", "HK"),
    baseline_hits=4,
    shadow_hits=6,
    status="validated",
    reason="",
):
    market_results = []
    market_count = len(markets)
    for market in markets:
        market_results.append(
            {
                "market": market,
                "sample_count": 5,
                "affected_count": affected // market_count if market_count else 0,
                "baseline_hit_count": baseline_hits // market_count if market_count else 0,
                "shadow_hit_count": shadow_hits // market_count if market_count else 0,
                "baseline_opposite_miss_count": 2,
                "shadow_opposite_miss_count": 1,
                "baseline_neutral_miss_count": 2,
                "shadow_neutral_miss_count": 2,
            }
        )
    return {
        "evaluation_as_of_date": batch_date,
        "action_code": action,
        "validation_status": status,
        "reason": reason,
        "evaluation_sample_count": 10,
        "affected_count": affected,
        "baseline_hit_count": baseline_hits,
        "shadow_hit_count": shadow_hits if status == "validated" else None,
        "baseline_opposite_miss_count": 4,
        "shadow_opposite_miss_count": 2 if status == "validated" else None,
        "baseline_neutral_miss_count": 4,
        "shadow_neutral_miss_count": 4 if status == "validated" else None,
        "market_results": market_results,
        "formal_model_change_allowed": False,
    }


def plan_payload(action=ACTION):
    return {
        "plan_schema": "one_week_forecast_shadow_parameter_plan",
        "plan_version": 1,
        "status": "shadow_plan_ready",
        "candidate_shadow_changes": [{"action_code": action}],
        "formal_model_change_allowed": False,
    }


def validation_payload(row):
    return {
        "validation_schema": "one_week_forecast_shadow_parameter_validation",
        "validation_version": 1,
        "as_of_date": row.get("evaluation_as_of_date", ""),
        "status": "shadow_validation_ready",
        "evaluation_as_of_date": row.get("evaluation_as_of_date", ""),
        "candidate_results": [{key: value for key, value in row.items() if key != "evaluation_as_of_date"}],
        "formal_model_change_allowed": False,
    }


def performance_payload():
    return {
        "review_schema": "forecast_performance_review",
        "status": "performance_review_needed",
        "next_one_week_evaluation_date": "2026-07-26",
        "next_one_week_evaluation_count": 20,
    }


def by_action(payload, action):
    return next(item for item in payload["candidate_dispositions"] if item["action_code"] == action)


def build_from_rows(rows, action=ACTION, as_of_date="2026-07-20"):
    from one_week_forecast_shadow_disposition import build_shadow_disposition

    latest = rows[-1]
    return build_shadow_disposition(
        plan_payload(action),
        validation_payload(latest),
        rows,
        performance_payload(),
        as_of_date=as_of_date,
    )


class OneWeekForecastShadowDispositionTests(unittest.TestCase):
    def test_duplicate_batch_key_counts_once_and_current_data_continues_observation(self):
        row = history_row("2026-07-09", affected=4, markets=("US",), baseline_hits=2, shadow_hits=4)

        payload = build_from_rows([row, dict(row)], as_of_date="2026-07-10")
        candidate = by_action(payload, ACTION)

        self.assertEqual(candidate["independent_batch_count"], 1)
        self.assertEqual(candidate["affected_count"], 4)
        self.assertEqual(candidate["disposition"], "continue_observation")
        self.assertEqual(candidate["next_action"], "continue_shadow_validation")
        self.assertEqual(payload["duplicate_history_key_count"], 1)
        self.assertFalse(payload["formal_model_change_allowed"])

    def test_three_positive_batches_meeting_all_gates_are_pending_human_approval(self):
        rows = [history_row(day) for day in ("2026-07-05", "2026-07-12", "2026-07-19")]

        candidate = by_action(build_from_rows(rows), ACTION)

        self.assertEqual(candidate["independent_batch_count"], 3)
        self.assertEqual(candidate["affected_count"], 30)
        self.assertEqual(candidate["affected_market_count"], 2)
        self.assertEqual(candidate["disposition"], "pending_human_approval")
        self.assertEqual(candidate["next_action"], "review_shadow_candidate_approval")

    def test_non_positive_aggregate_after_three_batches_is_rejected(self):
        rows = [
            history_row(day, markets=(), baseline_hits=6, shadow_hits=4)
            for day in ("2026-07-05", "2026-07-12", "2026-07-19")
        ]

        candidate = by_action(build_from_rows(rows), ACTION)

        self.assertEqual(candidate["disposition"], "rejected")
        self.assertIn("non_positive_aggregate_delta", candidate["reason_codes"])
        self.assertEqual(candidate["next_action"], "close_rejected_shadow_candidate")

    def test_three_same_non_evaluable_batches_are_rejected(self):
        rows = [
            history_row(
                day,
                action=WIDEN_ACTION,
                affected=0,
                markets=(),
                baseline_hits=0,
                shadow_hits=0,
                status="not_evaluable_current_fields",
                reason="prediction_score_missing",
            )
            for day in ("2026-07-05", "2026-07-12", "2026-07-19")
        ]

        candidate = by_action(build_from_rows(rows, action=WIDEN_ACTION), WIDEN_ACTION)

        self.assertEqual(candidate["disposition"], "rejected")
        self.assertIn("repeated_not_evaluable", candidate["reason_codes"])

    def test_missing_evaluation_date_needs_attention_and_adds_no_history(self):
        row = history_row("")

        payload = build_from_rows([row])

        self.assertEqual(payload["status"], "needs_attention")
        self.assertEqual(payload["history_records_added"], 0)
        self.assertEqual(payload["recommended_action"], "repair_shadow_disposition_inputs")
        self.assertFalse(payload["formal_model_change_allowed"])

    def test_plan_and_validation_action_mismatch_needs_attention(self):
        from one_week_forecast_shadow_disposition import build_shadow_disposition

        row = history_row("2026-07-19", action=WIDEN_ACTION)
        payload = build_shadow_disposition(
            plan_payload(ACTION),
            validation_payload(row),
            [],
            performance_payload(),
            as_of_date="2026-07-20",
        )

        self.assertEqual(payload["status"], "needs_attention")
        self.assertIn("candidate_action_contract_mismatch", payload["attention_reasons"])

    def test_missing_market_does_not_count_toward_market_gate(self):
        rows = [
            history_row(day, affected=10, markets=())
            for day in ("2026-07-05", "2026-07-12", "2026-07-19")
        ]

        candidate = by_action(build_from_rows(rows), ACTION)

        self.assertEqual(candidate["independent_batch_count"], 3)
        self.assertEqual(candidate["affected_market_count"], 0)
        self.assertEqual(candidate["disposition"], "continue_observation")

    def test_revised_history_row_with_same_key_is_appended_and_becomes_latest(self):
        from one_week_forecast_shadow_disposition import history_rows_to_append, logical_history

        original = history_row("2026-07-09", shadow_hits=4)
        revised = history_row("2026-07-09", shadow_hits=5)

        pending = history_rows_to_append([original], [revised])

        self.assertEqual(pending, [revised])
        self.assertEqual(logical_history([original, *pending])[0], [revised])

    def test_cli_repeated_identical_input_does_not_append_duplicate_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "plan.json"
            validation = root / "validation.json"
            performance = root / "performance.json"
            history = root / "history.jsonl"
            output = root / "disposition.json"
            report = root / "disposition.md"
            row = history_row("2026-07-09", affected=4, markets=("US",), baseline_hits=2, shadow_hits=4)
            plan.write_text(json.dumps(plan_payload()), encoding="utf-8")
            validation.write_text(json.dumps(validation_payload(row)), encoding="utf-8")
            performance.write_text(json.dumps(performance_payload()), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "one_week_forecast_shadow_disposition.py"),
                    "--plan",
                    str(plan),
                    "--validation",
                    str(validation),
                    "--history",
                    str(history),
                    "--performance",
                    str(performance),
                    "--as-of-date",
                    "2026-07-10",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["recommended_action"], "continue_shadow_validation")
            self.assertEqual(len(history.read_text(encoding="utf-8-sig").splitlines()), 1)
            self.assertIn("continue_observation", report.read_text(encoding="utf-8-sig"))
            self.assertFalse(payload["formal_model_change_allowed"])

            second = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "one_week_forecast_shadow_disposition.py"),
                    "--plan",
                    str(plan),
                    "--validation",
                    str(validation),
                    "--history",
                    str(history),
                    "--performance",
                    str(performance),
                    "--as-of-date",
                    "2026-07-10",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            second_payload = json.loads(output.read_text(encoding="utf-8-sig"))
            self.assertEqual(len(history.read_text(encoding="utf-8-sig").splitlines()), 1)
            self.assertEqual(second_payload["history_records_added"], 0)

    def test_wrapper_and_reporting_bundle_order_shadow_disposition_before_refresh(self):
        wrapper = (
            PROJECT_ROOT / "scripts" / "run_one_week_forecast_shadow_disposition.ps1"
        ).read_text(encoding="utf-8-sig")
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("one_week_forecast_shadow_disposition.py", wrapper)
        self.assertLess(
            bundle.index("run_one_week_forecast_shadow_parameter_validation"),
            bundle.index("run_one_week_forecast_shadow_disposition"),
        )
        self.assertLess(
            bundle.index("run_one_week_forecast_shadow_disposition"),
            bundle.index("refresh_self_analysis_after_shadow_disposition"),
        )


if __name__ == "__main__":
    unittest.main()
