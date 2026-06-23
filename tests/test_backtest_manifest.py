import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from backtest_manifest import (
    config_digest,
    load_checkpoint,
    load_manifest_rows,
    should_run_week,
    upsert_manifest_row,
    write_checkpoint,
)


class BacktestManifestTests(unittest.TestCase):

    def test_completed_week_is_reused_only_for_same_config(self):
        digest = config_digest({"model": "valuation_trend_v1", "start": "2023-06-01"})
        row = {"week": "2025-01-05", "status": "completed", "config_digest": digest}

        self.assertFalse(should_run_week(row, digest))
        self.assertTrue(should_run_week(row, "different"))

    def test_config_digest_is_stable_for_key_order_and_sensitive_to_change(self):
        digest_a = config_digest({"model": "valuation_trend_v1", "start": "2023-06-01", "depth": 12})
        digest_b = config_digest({"depth": 12, "start": "2023-06-01", "model": "valuation_trend_v1"})
        digest_changed = config_digest({"model": "valuation_trend_v2", "start": "2023-06-01", "depth": 12})

        self.assertEqual(digest_a, digest_b)
        self.assertNotEqual(digest_a, digest_changed)

    def test_should_run_week_for_empty_or_incomplete_rows(self):
        digest = config_digest({"model": "valuation_trend_v1", "start": "2023-06-01"})

        self.assertTrue(should_run_week(None, digest))
        self.assertTrue(should_run_week({}, digest))
        self.assertTrue(should_run_week({"status": "pending", "config_digest": digest}, digest))
        self.assertTrue(
            should_run_week({"status": "failed", "config_digest": digest}, digest)
        )
        self.assertTrue(
            should_run_week(
                {"status": "completed", "config_digest": "different"},
                digest,
            )
        )

    def test_checkpoint_missing_file_returns_none(self):
        with TemporaryDirectory() as root:
            checkpoint = Path(root) / "nested" / "checkpoint.json"

            self.assertIsNone(load_checkpoint(checkpoint))

    def test_checkpoint_roundtrip_and_atomic_write_parent_auto_created(self):
        with TemporaryDirectory() as root:
            checkpoint_path = Path(root) / "output" / "checkpoint.json"
            data = {
                "batch_id": "batch_a",
                "config_digest": "abc123",
                "last_completed_week": "2026-01-01",
                "success_count": 10,
                "failure_count": 2,
                "updated_at": "2026-01-02T00:00:00Z",
            }

            write_checkpoint(checkpoint_path, data)
            loaded = load_checkpoint(checkpoint_path)

            self.assertTrue(checkpoint_path.exists())
            self.assertTrue(checkpoint_path.parent.exists())
            self.assertEqual(loaded, data)
            self.assertEqual(checkpoint_path.parent.name, "output")

    def test_checkpoint_rejects_missing_required_fields(self):
        with TemporaryDirectory() as root:
            checkpoint_path = Path(root) / "checkpoint.json"
            partial = {"batch_id": "batch_a", "config_digest": "abc123"}
            with self.assertRaises(ValueError):
                write_checkpoint(checkpoint_path, partial)

    def test_manifest_rows_load_empty_when_missing(self):
        with TemporaryDirectory() as root:
            manifest_path = Path(root) / "replay_manifest.csv"
            self.assertEqual(load_manifest_rows(manifest_path), [])

    def test_replay_manifest_overwrites_same_batch_week_only(self):
        with TemporaryDirectory() as root:
            manifest_path = Path(root) / "replay_manifest.csv"
            initial = {
                "batch_id": "batch_a",
                "week": "2026-01-01",
                "status": "failed",
                "config_digest": "digest_old",
                "coverage": "0.82",
                "quality_gate": "retry",
                "failure_reason": "timeout",
                "updated_at": "2026-01-01T00:00:00Z",
            }
            upsert_manifest_row(manifest_path, initial)

            retry = {
                "batch_id": "batch_a",
                "week": "2026-01-01",
                "status": "completed",
                "config_digest": "digest_new",
                "coverage": "0.95",
                "quality_gate": "pass",
                "failure_reason": "",
                "updated_at": "2026-01-02T00:00:00Z",
            }
            upsert_manifest_row(manifest_path, retry)

            rows = load_manifest_rows(manifest_path)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "completed")
            self.assertEqual(rows[0]["week"], "2026-01-01")
            self.assertEqual(rows[0]["batch_id"], "batch_a")

    def test_replay_manifest_keeps_distinct_batch_or_week_records(self):
        with TemporaryDirectory() as root:
            manifest_path = Path(root) / "replay_manifest.csv"
            rows = [
                {
                    "batch_id": "batch_a",
                    "week": "2026-01-01",
                    "status": "completed",
                    "config_digest": "digest_a",
                    "coverage": "0.80",
                    "quality_gate": "pass",
                    "failure_reason": "",
                    "updated_at": "2026-01-01T00:00:00Z",
                },
                {
                    "batch_id": "batch_a",
                    "week": "2026-01-08",
                    "status": "completed",
                    "config_digest": "digest_a",
                    "coverage": "0.90",
                    "quality_gate": "pass",
                    "failure_reason": "",
                    "updated_at": "2026-01-08T00:00:00Z",
                },
                {
                    "batch_id": "batch_b",
                    "week": "2026-01-01",
                    "status": "failed",
                    "config_digest": "digest_b",
                    "coverage": "0.77",
                    "quality_gate": "retry",
                    "failure_reason": "network",
                    "updated_at": "2026-01-01T06:00:00Z",
                },
            ]
            for row in rows:
                upsert_manifest_row(manifest_path, row)

            rows_back = load_manifest_rows(manifest_path)
            self.assertEqual(len(rows_back), 3)

            keyset = {(row["batch_id"], row["week"]) for row in rows_back}
            self.assertIn(("batch_a", "2026-01-01"), keyset)
            self.assertIn(("batch_a", "2026-01-08"), keyset)
            self.assertIn(("batch_b", "2026-01-01"), keyset)

    def test_replay_manifest_outputs_utf8_bom(self):
        with TemporaryDirectory() as root:
            manifest_path = Path(root) / "replay_manifest.csv"
            upsert_manifest_row(
                manifest_path,
                {
                    "batch_id": "batch_a",
                    "week": "2026-01-01",
                    "status": "completed",
                    "config_digest": "digest_new",
                    "coverage": "0.99",
                    "quality_gate": "pass",
                    "failure_reason": "",
                    "updated_at": "2026-01-01T00:00:00Z",
                },
            )

            raw = manifest_path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))

    def test_failed_retry_keeps_completed_single_record(self):
        with TemporaryDirectory() as root:
            manifest_path = Path(root) / "replay_manifest.csv"
            rows = [
                {
                    "batch_id": "batch_a",
                    "week": "2026-01-01",
                    "status": "failed",
                    "config_digest": "digest_a",
                    "coverage": "0.45",
                    "quality_gate": "retry",
                    "failure_reason": "temporary network",
                    "updated_at": "2026-01-01T00:00:00Z",
                },
                {
                    "batch_id": "batch_a",
                    "week": "2026-01-01",
                    "status": "completed",
                    "config_digest": "digest_b",
                    "coverage": "0.78",
                    "quality_gate": "pass",
                    "failure_reason": "",
                    "updated_at": "2026-01-02T00:00:00Z",
                },
            ]

            for row in rows:
                upsert_manifest_row(manifest_path, row)

            rows_back = load_manifest_rows(manifest_path)
            self.assertEqual(len(rows_back), 1)
            self.assertEqual(rows_back[0]["status"], "completed")
            self.assertEqual(rows_back[0]["config_digest"], "digest_b")


if __name__ == "__main__":
    unittest.main()
