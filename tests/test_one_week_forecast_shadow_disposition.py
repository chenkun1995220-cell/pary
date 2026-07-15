import errno
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


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


def wait_for_path(path, process, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise AssertionError(f"subprocess exited before signaling:\n{stdout}{stderr}")
        time.sleep(0.01)
    raise AssertionError(f"timed out waiting for subprocess signal: {path}")


def lock_contention_error():
    return OSError(errno.EACCES, "lock busy")


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

    def test_history_file_lock_times_out_then_can_be_reacquired(self):
        from one_week_forecast_shadow_disposition import history_file_lock

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            history = root / "history.jsonl"
            ready = root / "holder.ready"
            release = root / "holder.release"
            holder_script = """
import sys
import time
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from one_week_forecast_shadow_disposition import history_file_lock

history = Path(sys.argv[2])
ready = Path(sys.argv[3])
release = Path(sys.argv[4])
with history_file_lock(history, timeout_seconds=5.0, poll_interval=0.01):
    ready.write_text("ready", encoding="utf-8")
    deadline = time.monotonic() + 10.0
    while not release.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("holder release signal not received")
        time.sleep(0.01)
"""
            holder = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    holder_script,
                    str(PROJECT_ROOT),
                    str(history),
                    str(ready),
                    str(release),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                wait_for_path(ready, holder)
                started = time.monotonic()
                with self.assertRaises(TimeoutError):
                    with history_file_lock(history, timeout_seconds=0.15, poll_interval=0.01):
                        self.fail("contended lock must not be acquired")
                self.assertLess(time.monotonic() - started, 1.0)

                release.write_text("release", encoding="utf-8")
                stdout, stderr = holder.communicate(timeout=5)
                self.assertEqual(holder.returncode, 0, stdout + stderr)

                with history_file_lock(history, timeout_seconds=0.5, poll_interval=0.01):
                    pass
                self.assertTrue(Path(f"{history}.lock").exists())
            finally:
                release.touch(exist_ok=True)
                if holder.poll() is None:
                    holder.kill()
                    holder.communicate(timeout=5)

    def test_history_file_lock_checks_deadline_before_retry(self):
        import one_week_forecast_shadow_disposition as module

        attempts = 0

        if module.os.name == "nt":
            def fake_locking(_file_descriptor, mode, _byte_count):
                nonlocal attempts
                if mode == module.msvcrt.LK_NBLCK:
                    attempts += 1
                    if attempts == 1:
                        raise lock_contention_error()

            lock_patch = mock.patch.object(module.msvcrt, "locking", side_effect=fake_locking)
        else:
            def fake_flock(_file_descriptor, operation):
                nonlocal attempts
                if operation == module.fcntl.LOCK_EX | module.fcntl.LOCK_NB:
                    attempts += 1
                    if attempts == 1:
                        raise lock_contention_error()

            lock_patch = mock.patch.object(module.fcntl, "flock", side_effect=fake_flock)

        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp) / "history.jsonl"
            with (
                mock.patch.object(module.time, "monotonic", side_effect=[100.0, 100.1, 100.6]),
                mock.patch.object(module.time, "sleep"),
                lock_patch,
            ):
                with self.assertRaisesRegex(TimeoutError, "timed out acquiring history lock"):
                    with module.history_file_lock(
                        history,
                        timeout_seconds=0.5,
                        poll_interval=0.1,
                    ):
                        self.fail("expired retry must not acquire the lock")

        self.assertEqual(attempts, 1)

    def test_history_file_lock_propagates_permanent_acquire_errors(self):
        import one_week_forecast_shadow_disposition as module

        permanent_error = OSError(errno.EINVAL, "permanent lock failure")

        if module.os.name == "nt":
            lock_patch = mock.patch.object(module.msvcrt, "locking", side_effect=permanent_error)
        else:
            lock_patch = mock.patch.object(module.fcntl, "flock", side_effect=permanent_error)

        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp) / "history.jsonl"
            with lock_patch:
                with self.assertRaises(OSError) as caught:
                    with module.history_file_lock(
                        history,
                        timeout_seconds=0.0,
                        poll_interval=0.01,
                    ):
                        self.fail("permanent lock errors must not be converted to timeouts")

        self.assertIs(caught.exception, permanent_error)

    def test_history_file_lock_posix_propagates_non_contention_oserror(self):
        import one_week_forecast_shadow_disposition as module

        permanent_error = OSError(errno.EINVAL, "bad file descriptor")
        calls = []

        class FakeFcntl:
            LOCK_EX = 1
            LOCK_NB = 2
            LOCK_UN = 4

            def flock(self, _file_descriptor, operation):
                if operation == (self.LOCK_EX | self.LOCK_NB):
                    calls.append(operation)
                    raise permanent_error

        fake_fcntl = FakeFcntl()

        class FakeOs:
            name = "posix"

        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp) / "history.jsonl"
            with (
                mock.patch.object(module, "os", FakeOs()),
                mock.patch.object(module, "fcntl", fake_fcntl, create=True),
            ):
                with self.assertRaises(OSError) as caught:
                    with module.history_file_lock(
                        history,
                        timeout_seconds=0.0,
                        poll_interval=0.01,
                    ):
                        self.fail("POSIX permanent lock errors must not be retried")

        self.assertIs(caught.exception, permanent_error)
        self.assertEqual(len(calls), 1)

    def test_history_file_lock_windows_propagates_permanent_winerror(self):
        import one_week_forecast_shadow_disposition as module

        permanent_error = OSError(0, "access denied", None, 5)

        class FakeMsvcrt:
            LK_NBLCK = 1
            LK_UNLCK = 2

            def locking(self, _file_descriptor, mode, _byte_count):
                if mode == self.LK_NBLCK:
                    raise permanent_error

        class FakeOs:
            name = "nt"

        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp) / "history.jsonl"
            with (
                mock.patch.object(module, "os", FakeOs()),
                mock.patch.object(module, "msvcrt", FakeMsvcrt(), create=True),
            ):
                with self.assertRaises(OSError) as caught:
                    with module.history_file_lock(
                        history,
                        timeout_seconds=0.0,
                        poll_interval=0.01,
                    ):
                        self.fail("Windows permanent winerrors must not be retried")

        self.assertIs(caught.exception, permanent_error)

    def test_history_file_lock_windows_retries_lock_violation_winerror(self):
        import one_week_forecast_shadow_disposition as module

        lock_error = OSError(0, "lock violation", None, 33)
        attempts = 0

        class FakeMsvcrt:
            LK_NBLCK = 1
            LK_UNLCK = 2

            def locking(self, _file_descriptor, mode, _byte_count):
                nonlocal attempts
                if mode == self.LK_NBLCK:
                    attempts += 1
                    raise lock_error

        class FakeOs:
            name = "nt"

        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp) / "history.jsonl"
            with (
                mock.patch.object(module, "os", FakeOs()),
                mock.patch.object(module, "msvcrt", FakeMsvcrt(), create=True),
                mock.patch.object(module.time, "monotonic", side_effect=[100.0, 100.01, 100.2]),
                mock.patch.object(module.time, "sleep"),
            ):
                with self.assertRaisesRegex(TimeoutError, "timed out acquiring history lock"):
                    with module.history_file_lock(
                        history,
                        timeout_seconds=0.1,
                        poll_interval=0.01,
                    ):
                        self.fail("Windows lock violation should be retried until timeout")

        self.assertEqual(attempts, 1)

    def test_history_file_lock_raises_unlock_failure_without_active_exception(self):
        import one_week_forecast_shadow_disposition as module

        unlock_error = OSError("injected unlock failure")

        if module.os.name == "nt":
            def fake_locking(_file_descriptor, mode, _byte_count):
                if mode == module.msvcrt.LK_UNLCK:
                    raise unlock_error

            lock_patch = mock.patch.object(module.msvcrt, "locking", side_effect=fake_locking)
        else:
            def fake_flock(_file_descriptor, operation):
                if operation == module.fcntl.LOCK_UN:
                    raise unlock_error

            lock_patch = mock.patch.object(module.fcntl, "flock", side_effect=fake_flock)

        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp) / "history.jsonl"
            with lock_patch:
                with self.assertRaises(OSError) as caught:
                    with module.history_file_lock(history, timeout_seconds=0.5, poll_interval=0.01):
                        pass

        self.assertIs(caught.exception, unlock_error)

    def test_history_file_lock_preserves_body_exception_when_unlock_fails(self):
        import one_week_forecast_shadow_disposition as module

        unlock_error = OSError("injected unlock failure")

        if module.os.name == "nt":
            def fake_locking(_file_descriptor, mode, _byte_count):
                if mode == module.msvcrt.LK_UNLCK:
                    raise unlock_error

            lock_patch = mock.patch.object(module.msvcrt, "locking", side_effect=fake_locking)
        else:
            def fake_flock(_file_descriptor, operation):
                if operation == module.fcntl.LOCK_UN:
                    raise unlock_error

            lock_patch = mock.patch.object(module.fcntl, "flock", side_effect=fake_flock)

        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp) / "history.jsonl"
            with lock_patch:
                with self.assertRaisesRegex(RuntimeError, "body failure") as caught:
                    with module.history_file_lock(history, timeout_seconds=0.5, poll_interval=0.01):
                        raise RuntimeError("body failure")

        if hasattr(caught.exception, "__notes__"):
            self.assertTrue(
                any("injected unlock failure" in note for note in caught.exception.__notes__),
                caught.exception.__notes__,
            )

    def test_history_file_lock_timeout_zero_still_attempts_immediately(self):
        from one_week_forecast_shadow_disposition import history_file_lock

        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp) / "history.jsonl"
            with history_file_lock(history, timeout_seconds=0.0, poll_interval=0.01):
                pass

    def test_history_file_lock_rejects_invalid_timing_arguments(self):
        from one_week_forecast_shadow_disposition import history_file_lock

        invalid_arguments = [
            ("timeout_seconds", -0.01),
            ("timeout_seconds", float("nan")),
            ("timeout_seconds", float("inf")),
            ("timeout_seconds", float("-inf")),
            ("poll_interval", 0.0),
            ("poll_interval", -0.01),
            ("poll_interval", float("nan")),
            ("poll_interval", float("inf")),
            ("poll_interval", float("-inf")),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp) / "history.jsonl"
            for argument, value in invalid_arguments:
                with self.subTest(argument=argument, value=value):
                    kwargs = {"timeout_seconds": 0.0, "poll_interval": 0.01, argument: value}
                    with self.assertRaisesRegex(ValueError, argument):
                        with history_file_lock(history, **kwargs):
                            pass

    def test_writer_rolls_back_history_and_outputs_when_markdown_write_fails(self):
        import one_week_forecast_shadow_disposition as module

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "plan.json"
            validation = root / "validation.json"
            performance = root / "performance.json"
            history = root / "history.jsonl"
            output = root / "disposition.json"
            report = root / "disposition.md"
            original = history_row("2026-07-02", affected=4, markets=("US",))
            current = history_row("2026-07-09", affected=4, markets=("US",))
            original_history = (json.dumps(original, sort_keys=True) + "\n").encode("utf-8")
            original_output = b'{"status": "previous"}\n'
            plan.write_text(json.dumps(plan_payload()), encoding="utf-8")
            validation.write_text(json.dumps(validation_payload(current)), encoding="utf-8")
            performance.write_text(json.dumps(performance_payload()), encoding="utf-8")
            history.write_bytes(original_history)
            output.write_bytes(original_output)

            with mock.patch.object(
                module,
                "_write_text",
                side_effect=OSError("injected markdown failure"),
            ) as write_text:
                with self.assertRaisesRegex(OSError, "injected markdown failure"):
                    module.write_shadow_disposition_files(
                        plan,
                        validation,
                        history,
                        performance,
                        output,
                        report,
                        as_of_date="2026-07-10",
                    )

            self.assertEqual(write_text.call_count, 1)
            self.assertEqual(history.read_bytes(), original_history)
            self.assertEqual(output.read_bytes(), original_output)
            self.assertFalse(report.exists())
            with module.history_file_lock(history, timeout_seconds=0.5, poll_interval=0.01):
                pass

    def test_writer_waits_for_history_lock_before_writing_any_output(self):
        from one_week_forecast_shadow_disposition import (
            history_file_lock,
            write_shadow_disposition_files,
        )

        self.assertTrue(callable(history_file_lock))
        self.assertTrue(callable(write_shadow_disposition_files))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "plan.json"
            validation = root / "validation.json"
            performance = root / "performance.json"
            history = root / "history.jsonl"
            output = root / "disposition.json"
            report = root / "disposition.md"
            ready = root / "holder.ready"
            release = root / "holder.release"
            writer_ready = root / "writer.ready"
            row = history_row("2026-07-09", affected=4, markets=("US",), baseline_hits=2, shadow_hits=4)
            plan.write_text(json.dumps(plan_payload()), encoding="utf-8")
            validation.write_text(json.dumps(validation_payload(row)), encoding="utf-8")
            performance.write_text(json.dumps(performance_payload()), encoding="utf-8")

            holder_script = """
import sys
import time
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from one_week_forecast_shadow_disposition import history_file_lock

history = Path(sys.argv[2])
ready = Path(sys.argv[3])
release = Path(sys.argv[4])
with history_file_lock(history, timeout_seconds=5.0, poll_interval=0.01):
    ready.write_text("ready", encoding="utf-8")
    deadline = time.monotonic() + 10.0
    while not release.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("holder release signal not received")
        time.sleep(0.01)
"""
            writer_script = """
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from one_week_forecast_shadow_disposition import write_shadow_disposition_files

Path(sys.argv[8]).write_text("ready", encoding="utf-8")
write_shadow_disposition_files(
    sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7],
    as_of_date="2026-07-10", lock_timeout_seconds=5.0,
)
"""
            holder = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    holder_script,
                    str(PROJECT_ROOT),
                    str(history),
                    str(ready),
                    str(release),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            writer = None
            try:
                wait_for_path(ready, holder)
                writer = subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        writer_script,
                        str(PROJECT_ROOT),
                        str(plan),
                        str(validation),
                        str(history),
                        str(performance),
                        str(output),
                        str(report),
                        str(writer_ready),
                    ],
                    cwd=PROJECT_ROOT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                wait_for_path(writer_ready, writer)
                blocked_deadline = time.monotonic() + 0.25
                while time.monotonic() < blocked_deadline:
                    self.assertIsNone(holder.poll(), "holder exited during the blocked-write window")
                    self.assertIsNone(writer.poll(), "writer exited while the history lock was held")
                    self.assertFalse(history.exists())
                    self.assertFalse(output.exists())
                    self.assertFalse(report.exists())
                    time.sleep(0.01)

                release.write_text("release", encoding="utf-8")
                holder_stdout, holder_stderr = holder.communicate(timeout=5)
                self.assertEqual(holder.returncode, 0, holder_stdout + holder_stderr)
                writer_stdout, writer_stderr = writer.communicate(timeout=10)
                self.assertEqual(writer.returncode, 0, writer_stdout + writer_stderr)

                self.assertEqual(len(history.read_text(encoding="utf-8-sig").splitlines()), 1)
                payload = json.loads(output.read_text(encoding="utf-8-sig"))
                self.assertEqual(payload["history_records_added"], 1)
                self.assertIn("continue_observation", report.read_text(encoding="utf-8-sig"))
            finally:
                release.touch(exist_ok=True)
                for process in (writer, holder):
                    if process is not None and process.poll() is None:
                        process.kill()
                        process.communicate(timeout=5)

    def test_concurrent_transaction_writers_append_one_physical_history_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "plan.json"
            validation = root / "validation.json"
            performance = root / "performance.json"
            history = root / "history.jsonl"
            go = root / "writers.go"
            row = history_row("2026-07-09", affected=4, markets=("US",), baseline_hits=2, shadow_hits=4)
            plan.write_text(json.dumps(plan_payload()), encoding="utf-8")
            validation.write_text(json.dumps(validation_payload(row)), encoding="utf-8")
            performance.write_text(json.dumps(performance_payload()), encoding="utf-8")

            writer_script = """
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from one_week_forecast_shadow_disposition import write_shadow_disposition_files

plan = Path(sys.argv[2])
validation = Path(sys.argv[3])
history = Path(sys.argv[4])
performance = Path(sys.argv[5])
output = Path(sys.argv[6])
report = Path(sys.argv[7])
ready = Path(sys.argv[8])
go = Path(sys.argv[9])
result = Path(sys.argv[10])

ready.write_text("ready", encoding="utf-8")
deadline = time.monotonic() + 10.0
while not go.exists():
    if time.monotonic() >= deadline:
        raise TimeoutError("go signal not received")
    time.sleep(0.01)

payload = write_shadow_disposition_files(
    plan,
    validation,
    history,
    performance,
    output,
    report,
    as_of_date="2026-07-10",
    lock_timeout_seconds=5.0,
)
result.write_text(
    json.dumps({"history_records_added": payload["history_records_added"]}),
    encoding="utf-8",
)
"""
            processes = []
            try:
                for index in range(2):
                    ready = root / f"writer_{index}.ready"
                    result = root / f"writer_{index}.result.json"
                    process = subprocess.Popen(
                        [
                            sys.executable,
                            "-c",
                            writer_script,
                            str(PROJECT_ROOT),
                            str(plan),
                            str(validation),
                            str(history),
                            str(performance),
                            str(root / f"disposition_{index}.json"),
                            str(root / f"disposition_{index}.md"),
                            str(ready),
                            str(go),
                            str(result),
                        ],
                        cwd=PROJECT_ROOT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    processes.append((process, ready, result))

                for process, ready, _result in processes:
                    wait_for_path(ready, process)
                self.assertFalse(history.exists())

                go.write_text("go", encoding="utf-8")
                for process, _ready, _result in processes:
                    stdout, stderr = process.communicate(timeout=10)
                    self.assertEqual(process.returncode, 0, stdout + stderr)

                added_counts = sorted(
                    json.loads(result.read_text(encoding="utf-8"))["history_records_added"]
                    for _process, _ready, result in processes
                )
                self.assertEqual(added_counts, [0, 1])
                self.assertEqual(len(history.read_text(encoding="utf-8-sig").splitlines()), 1)
            finally:
                go.touch(exist_ok=True)
                for process, _ready, _result in processes:
                    if process.poll() is None:
                        process.kill()
                        process.communicate(timeout=5)

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
