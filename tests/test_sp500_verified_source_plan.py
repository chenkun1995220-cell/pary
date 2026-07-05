import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


class Sp500VerifiedSourcePlanTests(unittest.TestCase):
    def test_builds_verified_source_plan_from_current_gap_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            automation = root / "outputs" / "automation"
            import_plan = automation / "latest_membership_evidence_import_plan.json"
            current_sources = automation / "latest_sp500_current_membership_sources.json"
            inbox_status = automation / "latest_sp500_current_membership_source_inbox_status.json"
            backtest_review = automation / "latest_backtest_evidence_review.json"
            write_json(
                import_plan,
                {
                    "review_schema": "membership_evidence_import_plan",
                    "status": "ready",
                    "ready_to_import_count": 0,
                    "verified_candidate_count": 0,
                    "invalid_source_count": 50,
                    "blocked_by_source_policy_count": 50,
                    "formal_backtest_upgrade_allowed": False,
                },
            )
            write_json(
                current_sources,
                {
                    "source_schema": "sp500_current_membership_sources",
                    "status": "secondary_ready",
                    "recommended_followup": "obtain_official_spglobal_constituents_csv",
                    "official_export_url": "https://www.spglobal.com/spdji/en/idsexport/file.xls?indexId=340",
                    "parsed_official_ticker_count": 0,
                    "parsed_secondary_ticker_count": 503,
                },
            )
            write_json(
                inbox_status,
                {
                    "status_schema": "sp500_current_membership_source_inbox_status",
                    "status": "secondary_fallback_available",
                    "source_file_inbox": "inputs/sp500_current_membership/official_constituents.csv",
                    "parsed_official_ticker_count": 0,
                    "minimum_official_ticker_count": 400,
                    "formal_backtest_upgrade_allowed": False,
                },
            )
            write_json(
                backtest_review,
                {
                    "review_schema": "backtest_evidence_review",
                    "status": "evidence_review_needed",
                    "verified_membership_ratio": 0.156,
                    "weak_evidence_rows": 3382,
                    "formal_model_upgrade_allowed": False,
                },
            )

            from sp500_verified_source_plan import (
                build_sp500_verified_source_plan,
                render_sp500_verified_source_plan,
            )

            payload = build_sp500_verified_source_plan(
                import_plan=import_plan,
                current_sources=current_sources,
                inbox_status=inbox_status,
                backtest_review=backtest_review,
                as_of_date="2026-07-05",
            )
            report = render_sp500_verified_source_plan(payload)

            self.assertEqual(payload["review_schema"], "sp500_verified_source_plan")
            self.assertEqual(payload["status"], "verified_source_required")
            self.assertEqual(payload["ready_to_import_count"], 0)
            self.assertEqual(payload["verified_candidate_count"], 0)
            self.assertEqual(payload["blocked_by_source_policy_count"], 50)
            self.assertFalse(payload["formal_backtest_upgrade_allowed"])
            self.assertEqual(payload["next_actions"][0]["action"], "obtain_official_spglobal_full_constituents_file")
            by_id = {item["source_id"]: item for item in payload["source_matrix"]}
            self.assertEqual(by_id["spglobal_full_constituents_export"]["trust_level"], "verified")
            self.assertTrue(by_id["spglobal_full_constituents_export"]["can_upgrade_membership"])
            self.assertEqual(by_id["ishares_ivv_holdings"]["trust_level"], "cross_check")
            self.assertFalse(by_id["ishares_ivv_holdings"]["can_upgrade_membership"])
            self.assertEqual(by_id["ssga_spy_holdings"]["trust_level"], "cross_check")
            self.assertEqual(by_id["vanguard_voo_holdings"]["trust_level"], "cross_check")
            self.assertIn("S&P 500 verified 来源补强计划", report)
            self.assertIn("obtain_official_spglobal_full_constituents_file", report)

    def test_crosscheck_substitute_state_does_not_require_official_full_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            automation = root / "outputs" / "automation"
            import_plan = automation / "latest_membership_evidence_import_plan.json"
            current_sources = automation / "latest_sp500_current_membership_sources.json"
            inbox_status = automation / "latest_sp500_current_membership_source_inbox_status.json"
            backtest_review = automation / "latest_backtest_evidence_review.json"
            write_json(
                import_plan,
                {
                    "review_schema": "membership_evidence_import_plan",
                    "status": "ready",
                    "ready_to_import_count": 0,
                    "verified_candidate_count": 0,
                    "invalid_source_count": 50,
                    "blocked_by_source_policy_count": 50,
                    "formal_backtest_upgrade_allowed": False,
                },
            )
            write_json(
                current_sources,
                {
                    "source_schema": "sp500_current_membership_sources",
                    "status": "crosscheck_substitute_ready",
                    "recommended_followup": "refresh_crosscheck_substitute_weekly",
                    "source_trust_level": "crosscheck_substitute",
                    "crosscheck_constituents_file": (
                        "outputs/sp500_crosscheck_20260705/"
                        "sp500_full_constituents_crosscheck_20260705.xlsx"
                    ),
                    "parsed_crosscheck_ticker_count": 503,
                    "formal_backtest_upgrade_allowed": False,
                },
            )
            write_json(
                inbox_status,
                {
                    "status_schema": "sp500_current_membership_source_inbox_status",
                    "status": "missing",
                    "source_file_inbox": "inputs/sp500_current_membership/official_constituents.csv",
                    "formal_backtest_upgrade_allowed": False,
                },
            )
            write_json(
                backtest_review,
                {
                    "review_schema": "backtest_evidence_review",
                    "status": "evidence_review_needed",
                    "verified_membership_ratio": 0.156,
                    "weak_evidence_rows": 3382,
                    "formal_model_upgrade_allowed": False,
                },
            )

            from sp500_verified_source_plan import build_sp500_verified_source_plan

            payload = build_sp500_verified_source_plan(
                import_plan=import_plan,
                current_sources=current_sources,
                inbox_status=inbox_status,
                backtest_review=backtest_review,
                as_of_date="2026-07-05",
            )

            self.assertEqual(payload["status"], "crosscheck_substitute_active")
            self.assertFalse(payload["official_full_file_required"])
            actions = [item["action"] for item in payload["next_actions"]]
            self.assertIn("refresh_crosscheck_substitute_weekly", actions)
            self.assertIn("rerun_us_weekly_screening_with_crosscheck_substitute", actions)
            self.assertNotIn("obtain_official_spglobal_full_constituents_file", actions)
            self.assertFalse(payload["formal_backtest_upgrade_allowed"])

    def test_cli_writes_json_and_markdown_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "plan.json"
            report = root / "plan.md"

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_verified_source_plan.py"),
                    "--project-root",
                    str(root),
                    "--as-of-date",
                    "2026-07-05",
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
            self.assertEqual(payload["review_schema"], "sp500_verified_source_plan")
            self.assertFalse(payload["formal_backtest_upgrade_allowed"])
            self.assertIn("S&P 500 verified 来源补强计划", report.read_text(encoding="utf-8-sig"))

    def test_powershell_wrapper_and_weekly_bundle_include_verified_source_plan(self):
        wrapper = (PROJECT_ROOT / "scripts" / "run_sp500_verified_source_plan.ps1").read_text(
            encoding="utf-8-sig"
        )
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("sp500_verified_source_plan.py", wrapper)
        self.assertIn("latest_sp500_verified_source_plan.json", wrapper)
        self.assertIn("run_sp500_verified_source_plan", bundle)
        self.assertLess(
            bundle.index("run_membership_evidence_import_plan"),
            bundle.index("run_sp500_verified_source_plan"),
        )
        self.assertLess(
            bundle.index("run_sp500_verified_source_plan"),
            bundle.index("run_membership_evidence_apply_preview"),
        )


if __name__ == "__main__":
    unittest.main()
