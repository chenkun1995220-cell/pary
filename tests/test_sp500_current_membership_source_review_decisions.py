import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_csv(path, fieldnames, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


QUEUE_FIELDS = [
    "ticker",
    "review_status",
    "issue_type",
    "recommended_check",
    "required_source_url",
    "source_status",
]

DECISION_FIELDS = [
    "ticker",
    "review_decision",
    "official_source_checked",
    "required_source_url",
    "issue_type",
    "recommended_check",
    "decision_notes",
]


class Sp500CurrentMembershipSourceReviewDecisionTests(unittest.TestCase):
    def test_merges_filled_template_rows_into_decision_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.csv"
            decisions = root / "decisions.csv"
            summary_json = root / "merge.json"
            summary_md = root / "merge.md"
            write_csv(
                decisions,
                DECISION_FIELDS,
                [
                    {
                        "ticker": "OLD",
                        "review_decision": "official_absent",
                        "official_source_checked": "yes",
                        "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                        "issue_type": "missing_from_official_current_source",
                        "recommended_check": "Previously confirmed.",
                        "decision_notes": "Keep existing decision.",
                    }
                ],
            )
            write_csv(
                template,
                DECISION_FIELDS,
                [
                    {
                        "ticker": "ZZZ",
                        "review_decision": "official_absent",
                        "official_source_checked": "yes",
                        "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                        "issue_type": "missing_from_official_current_source",
                        "recommended_check": "Confirmed official coverage.",
                        "decision_notes": "Official current source does not include ZZZ.",
                    },
                    {
                        "ticker": "PENDING",
                        "review_decision": "",
                        "official_source_checked": "",
                        "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                        "issue_type": "missing_from_official_current_source",
                        "recommended_check": "Still pending.",
                        "decision_notes": "",
                    },
                ],
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_source_review_decision_merge.py"),
                    "--template",
                    str(template),
                    "--decisions",
                    str(decisions),
                    "--summary-json",
                    str(summary_json),
                    "--summary-md",
                    str(summary_md),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with decisions.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["ticker"] for row in rows], ["OLD", "ZZZ"])
            self.assertEqual(rows[1]["review_decision"], "official_absent")
            self.assertEqual(rows[1]["official_source_checked"], "yes")
            payload = json.loads(summary_json.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["merge_schema"], "sp500_current_membership_source_review_decision_merge")
            self.assertEqual(payload["merged"], 1)
            self.assertEqual(payload["skipped_pending"], 1)
            self.assertEqual(payload["skipped_invalid"], 0)
            self.assertEqual(payload["row_count"], 2)
            self.assertIn("ZZZ", summary_md.read_text(encoding="utf-8-sig"))

    def test_applies_ready_decisions_to_queue_and_writes_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "queue.csv"
            decisions = root / "decisions.csv"
            summary_json = root / "summary.json"
            summary_md = root / "summary.md"
            write_csv(
                queue,
                QUEUE_FIELDS,
                [
                    {
                        "ticker": "ZZZ",
                        "review_status": "open",
                        "issue_type": "missing_from_official_current_source",
                        "recommended_check": "Confirm official coverage.",
                        "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                        "source_status": "ready",
                    },
                    {
                        "ticker": "OLD",
                        "review_status": "resolved",
                        "issue_type": "missing_from_official_current_source",
                        "recommended_check": "Already confirmed.",
                        "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                        "source_status": "ready",
                    },
                ],
            )
            write_csv(
                decisions,
                DECISION_FIELDS,
                [
                    {
                        "ticker": "ZZZ",
                        "review_decision": "official_absent",
                        "official_source_checked": "yes",
                        "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                        "issue_type": "missing_from_official_current_source",
                        "recommended_check": "Confirmed official coverage.",
                        "decision_notes": "Official current source does not include ZZZ.",
                    }
                ],
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_source_review_decisions.py"),
                    "--queue",
                    str(queue),
                    "--decisions",
                    str(decisions),
                    "--summary-json",
                    str(summary_json),
                    "--summary-md",
                    str(summary_md),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with queue.open(encoding="utf-8-sig", newline="") as handle:
                queue_rows = list(csv.DictReader(handle))
            self.assertEqual(queue_rows[0]["ticker"], "ZZZ")
            self.assertEqual(queue_rows[0]["review_status"], "resolved")
            self.assertEqual(queue_rows[1]["review_status"], "resolved")

            payload = json.loads(summary_json.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["status"], "applied")
            self.assertEqual(payload["applied_count"], 1)
            self.assertEqual(payload["skipped_pending_count"], 0)
            self.assertEqual(payload["skipped_invalid_count"], 0)
            self.assertFalse(payload["formal_backtest_upgrade_allowed"])
            self.assertIn("ZZZ", summary_md.read_text(encoding="utf-8-sig"))

    def test_dry_run_does_not_modify_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "queue.csv"
            decisions = root / "decisions.csv"
            summary_json = root / "summary.json"
            write_csv(
                queue,
                QUEUE_FIELDS,
                [
                    {
                        "ticker": "ZZZ",
                        "review_status": "open",
                        "issue_type": "missing_from_official_current_source",
                        "recommended_check": "Confirm official coverage.",
                        "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                        "source_status": "ready",
                    }
                ],
            )
            write_csv(
                decisions,
                DECISION_FIELDS,
                [
                    {
                        "ticker": "ZZZ",
                        "review_decision": "official_absent",
                        "official_source_checked": "yes",
                        "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                        "issue_type": "missing_from_official_current_source",
                        "recommended_check": "Confirmed official coverage.",
                        "decision_notes": "Dry run only.",
                    }
                ],
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_source_review_decisions.py"),
                    "--queue",
                    str(queue),
                    "--decisions",
                    str(decisions),
                    "--summary-json",
                    str(summary_json),
                    "--dry-run",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with queue.open(encoding="utf-8-sig", newline="") as handle:
                queue_rows = list(csv.DictReader(handle))
            self.assertEqual(queue_rows[0]["review_status"], "open")
            payload = json.loads(summary_json.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["status"], "dry_run")
            self.assertEqual(payload["applied_count"], 1)

    def test_powershell_wrapper_static_contract(self):
        apply_script = (
            PROJECT_ROOT
            / "scripts"
            / "apply_sp500_current_membership_source_review_decisions.ps1"
        ).read_text(encoding="utf-8-sig")
        merge_script = (
            PROJECT_ROOT
            / "scripts"
            / "merge_sp500_current_membership_source_review_decisions.ps1"
        ).read_text(encoding="utf-8-sig")

        self.assertIn("sp500_current_membership_source_review_decisions.py", apply_script)
        self.assertIn("sp500_current_membership_source_review_queue.csv", apply_script)
        self.assertIn("sp500_current_membership_source_review_decisions.csv", apply_script)
        self.assertIn("latest_sp500_current_membership_source_review_decision_apply.json", apply_script)
        self.assertIn("--summary-json", apply_script)
        self.assertIn("--dry-run", apply_script)
        self.assertIn("sp500_current_membership_source_review_decision_merge.py", merge_script)
        self.assertIn("sp500_current_membership_source_review_decisions_template.csv", merge_script)
        self.assertIn("sp500_current_membership_source_review_decisions.csv", merge_script)
        self.assertIn("latest_sp500_current_membership_source_review_decision_merge.json", merge_script)
        self.assertIn("--template", merge_script)
        self.assertIn("--decisions", merge_script)


if __name__ == "__main__":
    unittest.main()
