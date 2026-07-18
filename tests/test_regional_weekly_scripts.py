import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RegionalWeeklyScriptTests(unittest.TestCase):
    def test_weekly_scripts_include_snapshot_and_screening_steps(self):
        for script_name in ("run_cn_weekly.ps1", "run_hk_weekly.ps1"):
            script = (PROJECT_ROOT / "scripts" / script_name).read_text(
                encoding="utf-8-sig"
            )
            self.assertIn("weekly_transient_step_retry.ps1", script)
            self.assertIn("Invoke-WeeklyTransientStep", script)
            self.assertIn("regional_market_snapshot.py", script)
            self.assertIn("regional_quote_gaps.py", script)
            self.assertIn("regional_quote_retry.py", script)
            self.assertIn("quote_gaps.csv", script)
            self.assertIn("quote_gaps.md", script)
            self.assertIn("quote_retry.md", script)
            self.assertIn("regional_financials.py", script)
            self.assertIn("regional_value_screener.py", script)
            self.assertIn("valuation_review_items.csv", script)
            self.assertIn("candidate_price_history.py", script)
            self.assertIn("candidate_valuation.py", script)
            self.assertIn("valuation_targets.csv", script)
            self.assertIn("valuation_trend_v1", script)
            self.assertIn("forecast_tracker.py", script)
            self.assertIn("model_audit.py", script)
            self.assertIn("tracking_snapshot.csv", script)
            self.assertIn("forecast_evaluations.csv", script)
            self.assertIn("model_audit.md", script)
            self.assertIn("investment_summary.py", script)
            self.assertIn("latest_investment_summary.md", script)
            self.assertIn("regional_data_health_history.py", script)
            self.assertIn("data_health_history.csv", script)
            self.assertIn("data_health_history.md", script)
            self.assertIn("Quote gaps", script)
            self.assertIn("Quote gap report", script)
            self.assertIn("Quote retry report", script)
            self.assertIn("Valuation review items", script)
            self.assertIn('--candidates (Join-Path $OutputRoot "forecast_history.csv")', script)
            self.assertIn("regional_fundamental_v2", script)
            self.assertIn("candidate_pool.csv", script)
            self.assertIn("--candidate-min-score 75", script)
            self.assertNotIn("pending adapter", script)

    def test_weekly_scripts_limit_process_retry_to_observed_exit_120_steps(self):
        for script_name in ("run_cn_weekly.ps1", "run_hk_weekly.ps1"):
            script = (PROJECT_ROOT / "scripts" / script_name).read_text(
                encoding="utf-8-sig"
            )

            self.assertIn(
                'Invoke-WeeklyTransientStep -Label "market snapshot"',
                script,
            )
            self.assertIn(
                'Invoke-WeeklyTransientStep -Label "quote gap diagnostics"',
                script,
            )
            self.assertIn(
                'Invoke-WeeklyTransientStep -Label "final quote gap diagnostics"',
                script,
            )
            self.assertNotIn(
                'Invoke-WeeklyTransientStep -Label "regional screening"',
                script,
            )
            self.assertNotIn(
                'Invoke-WeeklyTransientStep -Label "candidate valuation"',
                script,
            )
            self.assertNotIn(
                'Invoke-WeeklyTransientStep -Label "forecast tracking"',
                script,
            )

    def run_dry(self, script_name, output_root):
        return subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                f"scripts\\{script_name}",
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

    def test_cn_weekly_dry_run_is_side_effect_free(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "cn"
            result = self.run_dry("run_cn_weekly.ps1", output_root)
            output = result.stdout + result.stderr

            self.assertEqual(result.returncode, 0, output)
            self.assertIn("Market: CN", output)
            self.assertIn("data\\cache\\csi300", output)
            self.assertIn(str(output_root), output)
            self.assertFalse(output_root.exists())

    def test_cn_weekly_checks_python_requirements_without_installing_at_runtime(self):
        script = (PROJECT_ROOT / "scripts" / "run_cn_weekly.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertNotIn("-m pip install", script)
        self.assertNotIn("--disable-pip-version-check", script)
        self.assertIn("import pandas, openpyxl, xlrd", script)
        self.assertIn("CN Python dependency check failed", script)

        requirements_position = script.index("import pandas, openpyxl, xlrd")
        universe_position = script.index("regional_universe.py")
        self.assertLess(requirements_position, universe_position)

    def test_hk_weekly_dry_run_is_side_effect_free(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "hk"
            result = self.run_dry("run_hk_weekly.ps1", output_root)
            output = result.stdout + result.stderr

            self.assertEqual(result.returncode, 0, output)
            self.assertIn("Market: HK", output)
            self.assertIn("data\\cache\\hk_large_mid", output)
            self.assertIn(str(output_root), output)
            self.assertFalse(output_root.exists())


if __name__ == "__main__":
    unittest.main()
