import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = PROJECT_ROOT / "scripts" / "weekly_transient_step_retry.ps1"


class WeeklyTransientStepRetryTests(unittest.TestCase):
    def run_harness(self, body):
        with tempfile.TemporaryDirectory() as tmp:
            harness = Path(tmp) / "retry_harness.ps1"
            harness.write_text(
                f". '{HELPER_PATH}'\n{body}\n",
                encoding="utf-8-sig",
            )
            return subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(harness),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                errors="replace",
                capture_output=True,
                timeout=30,
            )

    def test_exit_120_is_retried_once_and_can_recover(self):
        result = self.run_harness(
            """
$script:attempts = 0
Invoke-WeeklyTransientStep -Label "snapshot" -RetryDelaySeconds 0 -Command {
  $script:attempts += 1
  if ($script:attempts -eq 1) {
    & powershell.exe -NoProfile -Command "exit 120"
  } else {
    & powershell.exe -NoProfile -Command "exit 0"
  }
}
Write-Output "attempts=$script:attempts"
"""
        )

        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("attempts=2", output)
        self.assertIn("exit code 120; retrying once", output)

    def test_non_retryable_exit_code_fails_without_second_attempt(self):
        result = self.run_harness(
            """
$script:attempts = 0
try {
  Invoke-WeeklyTransientStep -Label "snapshot" -RetryDelaySeconds 0 -Command {
    $script:attempts += 1
    & powershell.exe -NoProfile -Command "exit 2"
  }
} catch {
  Write-Output "caught=$($_.Exception.Message)"
}
Write-Output "attempts=$script:attempts"
"""
        )

        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("attempts=1", output)
        self.assertIn("caught=snapshot failed with exit code 2.", output)
        self.assertNotIn("retrying once", output)

    def test_second_exit_120_is_reported_after_exactly_two_attempts(self):
        result = self.run_harness(
            """
$script:attempts = 0
try {
  Invoke-WeeklyTransientStep -Label "quote diagnostics" -RetryDelaySeconds 0 -Command {
    $script:attempts += 1
    & powershell.exe -NoProfile -Command "exit 120"
  }
} catch {
  Write-Output "caught=$($_.Exception.Message)"
}
Write-Output "attempts=$script:attempts"
"""
        )

        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("attempts=2", output)
        self.assertIn(
            "caught=quote diagnostics failed with exit code 120.",
            output,
        )


if __name__ == "__main__":
    unittest.main()
