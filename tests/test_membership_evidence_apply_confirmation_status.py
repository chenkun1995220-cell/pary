import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_preview(path):
    payload = {
        "preview_schema": "membership_evidence_apply_preview",
        "preview_version": 1,
        "as_of_date": "2026-07-06",
        "status": "ready",
        "current_source_pack": "outputs/automation/latest_membership_evidence_verified_source_pack.csv",
        "preview_row_count": 2,
        "preview_weeks_affected": 2,
        "eligible_ticker_count": 1,
        "applied_to_historical_membership": False,
        "formal_backtest_upgrade_allowed": False,
        "items": [
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
            },
            {
                "week": "2026-06-26",
                "ticker": "ABT",
                "company_name": "Abbott Laboratories",
                "current_evidence": "secondary",
                "current_membership_source_url": "data/config/us_universe_symbols.csv",
                "proposed_evidence": "verified",
                "proposed_membership_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                "source_as_of_date": "2026-07-06",
                "upgrade_scope": "current_membership_only",
            },
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def write_decisions(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "week",
                "ticker",
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
                "confirmation_decision": "approve",
                "reviewer": "manual",
                "decision_notes": "checked",
            }
        )
        writer.writerow(
            {
                "week": "2026-06-26",
                "ticker": "ABT",
                "confirmation_decision": "reject",
                "reviewer": "manual",
                "decision_notes": "needs another source",
            }
        )


class MembershipEvidenceApplyConfirmationStatusTests(unittest.TestCase):
    def test_creates_confirmation_template_when_preview_has_rows_but_no_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preview = root / "preview.json"
            decisions = root / "missing_decisions.csv"
            template = root / "confirmation_template.csv"
            approved_package = root / "approved_package.csv"
            write_preview(preview)

            from membership_evidence_apply_confirmation_status import build_apply_confirmation_status

            payload = build_apply_confirmation_status(
                preview,
                decisions_path=decisions,
                template_path=template,
                approved_package_path=approved_package,
                as_of_date="2026-07-06",
            )

            self.assertEqual(payload["confirmation_schema"], "membership_evidence_apply_confirmation_status")
            self.assertEqual(payload["status"], "awaiting_manual_confirmation")
            self.assertEqual(payload["preview_row_count"], 2)
            self.assertEqual(payload["pending_count"], 2)
            self.assertEqual(payload["approved_count"], 0)
            self.assertEqual(payload["rejected_count"], 0)
            self.assertFalse(payload["applied_to_historical_membership"])
            self.assertFalse(payload["formal_backtest_upgrade_allowed"])
            self.assertTrue(template.exists())
            with template.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["confirmation_decision"], "")
            self.assertTrue(approved_package.exists())
            with approved_package.open(encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(list(csv.DictReader(handle)), [])

    def test_builds_approved_package_only_from_approved_confirmation_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preview = root / "preview.json"
            decisions = root / "decisions.csv"
            template = root / "confirmation_template.csv"
            approved_package = root / "approved_package.csv"
            write_preview(preview)
            write_decisions(decisions)

            from membership_evidence_apply_confirmation_status import build_apply_confirmation_status

            payload = build_apply_confirmation_status(
                preview,
                decisions_path=decisions,
                template_path=template,
                approved_package_path=approved_package,
                as_of_date="2026-07-06",
            )

            self.assertEqual(payload["status"], "ready_with_rejections")
            self.assertEqual(payload["approved_count"], 1)
            self.assertEqual(payload["rejected_count"], 1)
            self.assertEqual(payload["pending_count"], 0)
            self.assertEqual(payload["approved_package_row_count"], 1)
            self.assertFalse(payload["applied_to_historical_membership"])
            self.assertFalse(payload["formal_backtest_upgrade_allowed"])
            with approved_package.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["week"], "2026-06-19")
            self.assertEqual(rows[0]["ticker"], "ABT")
            self.assertEqual(rows[0]["proposed_evidence"], "verified")

    def test_cli_wrapper_bundle_and_pre_submit_include_confirmation_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preview = root / "preview.json"
            output_json = root / "confirmation.json"
            output_csv = root / "confirmation.csv"
            output_md = root / "confirmation.md"
            template = root / "confirmation_template.csv"
            approved_package = root / "approved_package.csv"
            write_preview(preview)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "membership_evidence_apply_confirmation_status.py"),
                    "--apply-preview",
                    str(preview),
                    "--decisions",
                    str(root / "missing_decisions.csv"),
                    "--template",
                    str(template),
                    "--approved-package",
                    str(approved_package),
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
            self.assertEqual(payload["status"], "awaiting_manual_confirmation")
            self.assertTrue(output_csv.exists())
            self.assertTrue(approved_package.exists())
            self.assertIn("membership_evidence_apply_confirmation_status", output_md.read_text(encoding="utf-8-sig"))

        wrapper = (PROJECT_ROOT / "scripts" / "run_membership_evidence_apply_confirmation_status.ps1").read_text(
            encoding="utf-8-sig"
        )
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(encoding="utf-8-sig")
        pre_submit = (PROJECT_ROOT / "pre_submit_review.py").read_text(encoding="utf-8-sig")

        self.assertIn("membership_evidence_apply_confirmation_status.py", wrapper)
        self.assertIn("latest_membership_evidence_apply_confirmation_status.json", wrapper)
        self.assertIn("membership_evidence_apply_confirmation_decisions_template.csv", wrapper)
        self.assertIn("latest_membership_evidence_approved_apply_package.csv", wrapper)
        self.assertIn("run_membership_evidence_apply_confirmation_status", bundle)
        self.assertLess(
            bundle.index("run_membership_evidence_apply_preview"),
            bundle.index("run_membership_evidence_apply_confirmation_status"),
        )
        self.assertLess(
            bundle.index("run_membership_evidence_apply_confirmation_status"),
            bundle.index("run_medium_term_goal_review"),
        )
        self.assertIn("membership_evidence_apply_confirmation_status", pre_submit)


if __name__ == "__main__":
    unittest.main()
