import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Sp500OfficialExportProbeTests(unittest.TestCase):
    def test_build_marks_403_as_forbidden_without_allowing_upgrade(self):
        from sp500_official_export_probe import build_sp500_official_export_probe

        def fetcher(url):
            raise HTTPError(url, 403, "Forbidden", hdrs=None, fp=None)

        payload = build_sp500_official_export_probe(
            official_export_url="https://www.spglobal.com/spdji/en/idsexport/file.xls?indexId=340",
            as_of_date="2026-07-07",
            fetcher=fetcher,
        )

        self.assertEqual(payload["probe_schema"], "sp500_official_export_probe")
        self.assertEqual(payload["status"], "forbidden")
        self.assertEqual(payload["http_status"], 403)
        self.assertEqual(payload["next_action"], "retry_with_logged_in_browser_or_manual_export")
        self.assertFalse(payload["formal_backtest_upgrade_allowed"])
        self.assertFalse(payload["downloaded"])
        self.assertEqual(
            payload["manual_export_target_file"],
            "inputs/sp500_current_membership/official_constituents.csv",
        )
        self.assertEqual(payload["minimum_official_ticker_count"], 400)
        self.assertIn("Symbol", payload["accepted_ticker_columns"])
        self.assertIn("Ticker", payload["accepted_ticker_columns"])
        self.assertIn("run_sp500_current_membership_sources.ps1", payload["manual_export_dry_run_command"])
        self.assertIn("-DryRun", payload["manual_export_dry_run_command"])
        self.assertIn("run_sp500_current_membership_sources.ps1", payload["manual_export_import_command"])

    def test_build_marks_network_failure_as_fetch_failed(self):
        from sp500_official_export_probe import build_sp500_official_export_probe

        def fetcher(url):
            raise URLError("connection refused")

        payload = build_sp500_official_export_probe(
            official_export_url="https://www.spglobal.com/spdji/en/idsexport/file.xls?indexId=340",
            as_of_date="2026-07-07",
            fetcher=fetcher,
        )

        self.assertEqual(payload["status"], "fetch_failed")
        self.assertEqual(payload["next_action"], "retry_official_export_probe")
        self.assertFalse(payload["formal_backtest_upgrade_allowed"])

    def test_cli_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "probe.json"
            report = root / "probe.md"

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_official_export_probe.py"),
                    "--official-export-url",
                    "http://127.0.0.1:9/file.xls",
                    "--as-of-date",
                    "2026-07-07",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["probe_schema"], "sp500_official_export_probe")
            self.assertIn(payload["status"], {"fetch_failed", "forbidden"})
            report_text = report.read_text(encoding="utf-8-sig")
            self.assertIn("sp500_official_export_probe", report_text)
            self.assertIn("manual_export_target_file", report_text)
            self.assertIn("manual_export_dry_run_command", report_text)

    def test_powershell_wrapper_and_weekly_bundle_include_probe_before_verified_plan(self):
        wrapper = (PROJECT_ROOT / "scripts" / "run_sp500_official_export_probe.ps1").read_text(
            encoding="utf-8-sig"
        )
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("sp500_official_export_probe.py", wrapper)
        self.assertIn("latest_sp500_official_export_probe.json", wrapper)
        self.assertIn("run_sp500_official_export_probe", bundle)
        self.assertLess(
            bundle.index("run_sp500_official_export_probe"),
            bundle.index("run_sp500_verified_source_plan"),
        )


if __name__ == "__main__":
    unittest.main()
