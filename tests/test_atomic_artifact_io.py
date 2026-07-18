import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AtomicArtifactIoTests(unittest.TestCase):
    def test_atomic_json_is_utf8_bom_and_powershell_compatible(self):
        from atomic_artifact_io import write_json_atomic

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "latest.json"
            write_json_atomic(output, {"status": "就绪"})

            self.assertTrue(output.read_bytes().startswith(b"\xef\xbb\xbf"))
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8-sig")),
                {"status": "就绪"},
            )
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-Command",
                    (
                        f"$actual=(Get-Content -Raw -LiteralPath '{output}' | "
                        "ConvertFrom-Json).status; "
                        "$expected=([string][char]0x5C31)+([char]0x7EEA); "
                        "if ($actual -ne $expected) { exit 1 }"
                    ),
                ],
                text=True,
                errors="replace",
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_replace_failure_preserves_previous_file_and_cleans_temp_file(self):
        from atomic_artifact_io import write_json_atomic

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "latest.json"
            output.write_text('{"status":"old"}\n', encoding="utf-8-sig")

            with mock.patch(
                "atomic_artifact_io.os.replace",
                side_effect=OSError("replace blocked"),
            ):
                with self.assertRaisesRegex(OSError, "replace blocked"):
                    write_json_atomic(output, {"status": "new"})

            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8-sig")),
                {"status": "old"},
            )
            self.assertEqual(list(Path(tmp).glob(".latest.json.*.tmp")), [])

    def test_critical_weekly_json_writers_use_shared_atomic_writer(self):
        modules = (
            "weekly_market_completion_gate.py",
            "weekly_artifact_consistency.py",
            "weekly_delivery_check.py",
            "pre_submit_review.py",
            "weekly_action_items.py",
        )

        for module in modules:
            source = (PROJECT_ROOT / module).read_text(encoding="utf-8-sig")
            self.assertIn(
                "write_json_atomic",
                source,
                f"{module} must use the shared atomic JSON writer",
            )


if __name__ == "__main__":
    unittest.main()
