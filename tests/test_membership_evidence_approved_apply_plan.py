import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_approved_package(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "week",
                "ticker",
                "company_name",
                "current_evidence",
                "current_membership_source_url",
                "proposed_evidence",
                "proposed_membership_source_url",
                "source_as_of_date",
                "upgrade_scope",
                "confirmation_decision",
                "reviewer",
                "decision_notes",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "week": "2026-06-19",
                "ticker": "ABT",
                "company_name": "Abbott Laboratories",
                "current_evidence": "secondary",
                "current_membership_source_url": "data/config/us_universe_symbols.csv",
                "proposed_evidence": "verified",
                "proposed_membership_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                "source_as_of_date": "2026-07-06",
                "upgrade_scope": "current_membership_only",
                "confirmation_decision": "approve",
                "reviewer": "manual",
                "decision_notes": "checked",
            }
        )
        writer.writerow(
            {
                "week": "2026-06-26",
                "ticker": "AEP",
                "company_name": "American Electric Power",
                "current_evidence": "secondary",
                "current_membership_source_url": "data/config/us_universe_symbols.csv",
                "proposed_evidence": "verified",
                "proposed_membership_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                "source_as_of_date": "2026-07-06",
                "upgrade_scope": "current_membership_only",
                "confirmation_decision": "approve",
                "reviewer": "manual",
                "decision_notes": "checked",
            }
        )
        writer.writerow(
            {
                "week": "2026-06-26",
                "ticker": "BA",
                "company_name": "Boeing",
                "current_evidence": "secondary",
                "current_membership_source_url": "data/config/us_universe_symbols.csv",
                "proposed_evidence": "verified",
                "proposed_membership_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                "source_as_of_date": "2026-07-06",
                "upgrade_scope": "current_membership_only",
                "confirmation_decision": "approve",
                "reviewer": "manual",
                "decision_notes": "checked",
            }
        )


def write_historical_membership(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "week",
                "ticker",
                "company_name",
                "membership_evidence",
                "membership_source_url",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "week": "2026-06-19",
                "ticker": "ABT",
                "company_name": "Abbott Laboratories",
                "membership_evidence": "secondary",
                "membership_source_url": "data/config/us_universe_symbols.csv",
            }
        )
        writer.writerow(
            {
                "week": "2026-06-26",
                "ticker": "AEP",
                "company_name": "American Electric Power",
                "membership_evidence": "verified",
                "membership_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
            }
        )


class MembershipEvidenceApprovedApplyPlanTests(unittest.TestCase):
    def test_builds_read_only_apply_plan_without_modifying_historical_membership(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            approved_package = root / "approved_package.csv"
            membership = root / "historical_membership.csv"
            write_approved_package(approved_package)
            write_historical_membership(membership)
            before = membership.read_text(encoding="utf-8-sig")

            from membership_evidence_approved_apply_plan import build_approved_apply_plan

            payload = build_approved_apply_plan(
                approved_package,
                membership,
                as_of_date="2026-07-06",
            )

            self.assertEqual(payload["plan_schema"], "membership_evidence_approved_apply_plan")
            self.assertEqual(payload["status"], "ready_for_manual_apply_review")
            self.assertEqual(payload["approved_package_row_count"], 3)
            self.assertEqual(payload["ready_to_apply_count"], 1)
            self.assertEqual(payload["already_verified_count"], 1)
            self.assertEqual(payload["missing_historical_row_count"], 1)
            self.assertTrue(payload["requires_manual_apply"])
            self.assertFalse(payload["would_modify_historical_membership"])
            self.assertFalse(payload["applied_to_historical_membership"])
            self.assertFalse(payload["formal_backtest_upgrade_allowed"])
            self.assertEqual(membership.read_text(encoding="utf-8-sig"), before)

            statuses = {item["ticker"]: item["validation_status"] for item in payload["items"]}
            self.assertEqual(statuses["ABT"], "ready_to_apply_manually")
            self.assertEqual(statuses["AEP"], "already_verified")
            self.assertEqual(statuses["BA"], "missing_historical_row")

    def test_cli_wrapper_bundle_and_pre_submit_include_approved_apply_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            approved_package = root / "approved_package.csv"
            membership = root / "historical_membership.csv"
            output_json = root / "plan.json"
            output_csv = root / "plan.csv"
            output_md = root / "plan.md"
            write_approved_package(approved_package)
            write_historical_membership(membership)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "membership_evidence_approved_apply_plan.py"),
                    "--approved-package",
                    str(approved_package),
                    "--membership",
                    str(membership),
                    "--as-of-date",
                    "2026-07-06",
                    "--output-json",
                    str(output_json),
                    "--output-csv",
                    str(output_csv),
                    "--output-md",
                    str(output_md),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output_json.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["status"], "ready_for_manual_apply_review")
            self.assertTrue(output_csv.exists())
            self.assertIn("membership_evidence_approved_apply_plan", output_md.read_text(encoding="utf-8-sig"))

        wrapper = (PROJECT_ROOT / "scripts" / "run_membership_evidence_approved_apply_plan.ps1").read_text(
            encoding="utf-8-sig"
        )
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(encoding="utf-8-sig")
        pre_submit = (PROJECT_ROOT / "pre_submit_review.py").read_text(encoding="utf-8-sig")

        self.assertIn("membership_evidence_approved_apply_plan.py", wrapper)
        self.assertIn("latest_membership_evidence_approved_apply_plan.json", wrapper)
        self.assertIn("latest_membership_evidence_approved_apply_plan.md", wrapper)
        self.assertNotIn("run_membership_evidence_approved_apply_plan", bundle)
        self.assertIn("membership_evidence_approved_apply_plan", pre_submit)


if __name__ == "__main__":
    unittest.main()
