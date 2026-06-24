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

    def test_point_in_time_backtest_script_static_contract(self):
        script = (PROJECT_ROOT / "scripts" / "run_us_point_in_time_backtest.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("historical_sp500.py", script)
        self.assertIn("us_weekly_replay.py", script)
        self.assertIn("shadow_backtest.py", script)
        self.assertIn("-PilotWeeks 8", script)
        self.assertIn("historical_membership.csv", script)
        self.assertIn("replay_manifest.csv", script)
        self.assertIn("backtest_forecasts.csv", script)
        self.assertIn("backtest_evaluations.csv", script)
        self.assertIn("model_comparison.csv", script)
        self.assertIn("backtest_report.md", script)
        self.assertIn("data_leakage_audit.md", script)
        self.assertIn("checkpoint.json", script)
        self.assertIn("FullRun", script)

    def test_point_in_time_backtest_dry_run_prints_ordered_pipeline_without_writing_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "backtest_output"
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "scripts\\run_us_point_in_time_backtest.ps1",
                    "-SecUserAgent",
                    "Test test@example.com",
                    "-OutputRoot",
                    str(output_root),
                    "-PilotWeeks",
                    "8",
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
                "1/8 Build historical S&P 500 membership",
                "2/8 Load point-in-time SEC facts",
                "3/8 Load historical prices",
                "4/8 Replay weekly screening",
                "5/8 Write replay manifest and checkpoint",
                "6/8 Evaluate backtest forecasts",
                "7/8 Run rolling shadow comparison",
                "8/8 Write backtest report",
            ]
            positions = [output.index(step) for step in expected_steps]
            self.assertEqual(positions, sorted(positions))
            self.assertIn(str(output_root), output)
            self.assertIn("PilotWeeks: 8", output)
            self.assertFalse(output_root.exists())

    def test_point_in_time_backtest_non_dry_run_blocks_until_batch_replay_is_wired(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "backtest_output"
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "scripts\\run_us_point_in_time_backtest.ps1",
                    "-SecUserAgent",
                    "Test test@example.com",
                    "-OutputRoot",
                    str(output_root),
                    "-PilotWeeks",
                    "8",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            output = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn("Batch weekly replay runner is not wired yet", output)
            self.assertNotIn("Point-in-time backtest completed", output)

    def test_point_in_time_backtest_docs_describe_run_modes_and_limits(self):
        doc = (PROJECT_ROOT / "docs" / "美股每周自动运行说明.md").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("run_us_point_in_time_backtest.ps1", doc)
        self.assertIn("-PilotWeeks 8", doc)
        self.assertIn("-FullRun", doc)
        self.assertIn("outputs/backtests/us_3y_weekly", doc)
        self.assertIn("data_leakage_audit.md", doc)
        self.assertIn("不得自动升级正式模型", doc)


if __name__ == "__main__":
    unittest.main()
