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
            self.assertIn("regional_market_snapshot.py", script)
            self.assertIn("regional_financials.py", script)
            self.assertIn("regional_value_screener.py", script)
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
            self.assertIn('--candidates (Join-Path $OutputRoot "forecast_history.csv")', script)
            self.assertIn("regional_fundamental_v2", script)
            self.assertIn("candidate_pool.csv", script)
            self.assertIn("--candidate-min-score 75", script)
            self.assertNotIn("pending adapter", script)

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
