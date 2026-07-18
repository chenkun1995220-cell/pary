import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEEKLY_SCRIPTS = (
    "run_us_universe_weekly.ps1",
    "run_cn_weekly.ps1",
    "run_hk_weekly.ps1",
)


class WeeklyScriptEncodingTests(unittest.TestCase):
    def test_market_entry_scripts_declare_utf8_output_contract(self):
        for script_name in WEEKLY_SCRIPTS:
            with self.subTest(script=script_name):
                script = (PROJECT_ROOT / "scripts" / script_name).read_text(
                    encoding="utf-8-sig"
                )
                self.assertIn(
                    "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()",
                    script,
                )
                self.assertIn(
                    "$OutputEncoding = [System.Text.UTF8Encoding]::new()",
                    script,
                )
                self.assertIn('$env:PYTHONIOENCODING = "utf-8"', script)
