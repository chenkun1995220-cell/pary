import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class WeeklyAutomationTests(unittest.TestCase):
    def test_orchestrator_summary_includes_universe_refresh_status(self):
        script = (PROJECT_ROOT / "scripts" / "run_us_universe_weekly.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("sp500_refresh_metadata.json", script)
        self.assertIn("Universe count", script)
        self.assertIn("Constituent refresh status", script)
        self.assertIn("candidate_price_history.py", script)
        self.assertIn("candidate_valuation.py", script)
        self.assertIn("valuation_targets.csv", script)
        self.assertIn("valuation_trend_v1", script)
        self.assertIn("forecast_tracker.py", script)
        self.assertIn("model_audit.py", script)
        self.assertIn("tracking_snapshot.csv", script)
        self.assertIn("forecast_evaluations.csv", script)
        self.assertIn("model_audit.md", script)
        self.assertIn('--candidates (Join-Path $OutputRoot "forecast_history.csv")', script)

    def test_orchestrator_dry_run_prints_ordered_pipeline_without_writing_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "weekly_output"
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "scripts\\run_us_universe_weekly.ps1",
                    "-SecUserAgent",
                    "Test test@example.com",
                    "-OutputRoot",
                    str(output_root),
                    "-DryRun",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            expected_steps = [
                "1/10 Refresh S&P 500 constituents",
                "2/10 Build US universe",
                "3/10 Fill market quotes",
                "4/10 Run screening",
                "5/10 Generate research packs",
                "6/10 Fetch candidate price history",
                "7/10 Generate valuation targets",
                "8/10 Fetch benchmark history",
                "9/10 Track forecast performance",
                "10/10 Audit forecast model",
            ]
            positions = [output.index(step) for step in expected_steps]
            self.assertEqual(positions, sorted(positions))
            self.assertIn(str(output_root), output)
            self.assertFalse(output_root.exists())

    def test_task_registration_what_if_prints_schedule_and_orchestrator(self):
        result = subprocess.run(
            [
                "powershell.exe",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                "scripts\\register_us_universe_weekly_task.ps1",
                "-TaskName",
                "StockScreeningTest",
                "-DayOfWeek",
                "Saturday",
                "-At",
                "09:00",
                "-SecUserAgent",
                "Test test@example.com",
                "-WhatIf",
            ],
            cwd=PROJECT_ROOT,
            text=True,
            errors="replace",
            capture_output=True,
            timeout=30,
        )

        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("StockScreeningTest", output)
        self.assertIn("Saturday", output)
        self.assertIn("09:00", output)
        self.assertIn("run_us_universe_weekly.ps1", output)


if __name__ == "__main__":
    unittest.main()
