import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_import_plan(path):
    payload = {
        "review_schema": "membership_evidence_import_plan",
        "review_version": 1,
        "as_of_date": "2026-07-05",
        "status": "ready",
        "ready_to_import_count": 1,
        "missing_source_count": 1,
        "invalid_source_count": 1,
        "blocked_by_source_policy_count": 1,
        "next_action": "supplement_verified_membership_evidence",
        "formal_backtest_upgrade_allowed": False,
        "items": [
            {
                "rank": 1,
                "ticker": "ABT",
                "company_name": "Abbott Laboratories",
                "effective_date": "1957-03-04",
                "weeks_affected": 156,
                "current_evidence": "secondary",
                "import_status": "invalid_current_source",
                "proposed_action": "fix_current_membership_source",
                "membership_source_url": "local://sp500_crosscheck_substitute",
                "source_as_of_date": "2026-07-05",
                "source_trust_level": "crosscheck_substitute",
                "notes": "crosscheck substitute",
            },
            {
                "rank": 2,
                "ticker": "MISS",
                "company_name": "Missing Source",
                "effective_date": "2024-01-01",
                "weeks_affected": 20,
                "current_evidence": "secondary",
                "import_status": "missing_current_source",
                "proposed_action": "add_current_membership_source",
                "membership_source_url": "",
                "source_as_of_date": "",
                "source_trust_level": "missing",
                "notes": "",
            },
            {
                "rank": 3,
                "ticker": "VER",
                "company_name": "Verified Source",
                "effective_date": "2024-01-01",
                "weeks_affected": 10,
                "current_evidence": "secondary",
                "import_status": "ready_current_source",
                "proposed_action": "prepare_current_membership_import",
                "membership_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                "source_as_of_date": "2026-07-05",
                "source_trust_level": "verified",
                "notes": "",
            },
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


class MembershipEvidenceSupplementQueueTests(unittest.TestCase):
    def test_builds_official_evidence_work_package_from_blocked_import_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "latest_membership_evidence_import_plan.json"
            write_import_plan(plan)

            from membership_evidence_supplement_queue import build_supplement_queue

            payload = build_supplement_queue(plan, as_of_date="2026-07-05")

            self.assertEqual(payload["queue_schema"], "membership_evidence_supplement_queue")
            self.assertEqual(payload["status"], "action_required")
            self.assertEqual(payload["queue_count"], 2)
            self.assertEqual(payload["ready_to_import_count"], 1)
            self.assertEqual(payload["blocked_by_source_policy_count"], 1)
            self.assertFalse(payload["formal_backtest_upgrade_allowed"])
            self.assertEqual(payload["items"][0]["ticker"], "ABT")
            self.assertEqual(payload["items"][0]["required_evidence_kind"], "official_spglobal_membership_evidence")
            self.assertEqual(payload["items"][0]["accepted_source_domains"], "spglobal.com,.spglobal.com")
            self.assertEqual(payload["items"][0]["rejected_source_trust_level"], "crosscheck_substitute")
            self.assertIn("cannot_upgrade_historical_membership", payload["items"][0]["rejection_reason"])
            self.assertEqual(payload["items"][1]["ticker"], "MISS")
            self.assertEqual(payload["items"][1]["rejection_reason"], "missing_current_source")

    def test_cli_writes_json_csv_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "latest_membership_evidence_import_plan.json"
            output_json = root / "queue.json"
            output_csv = root / "queue.csv"
            output_md = root / "queue.md"
            write_import_plan(plan)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "membership_evidence_supplement_queue.py"),
                    "--import-plan",
                    str(plan),
                    "--as-of-date",
                    "2026-07-05",
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
            self.assertEqual(payload["queue_count"], 2)
            with output_csv.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["ticker"], "ABT")
            report = output_md.read_text(encoding="utf-8-sig")
            self.assertIn("membership_evidence_supplement_queue", report)
            self.assertIn("official_spglobal_membership_evidence", report)

    def test_powershell_wrapper_remains_manual_and_bundle_excludes_supplement_queue(self):
        wrapper = (PROJECT_ROOT / "scripts" / "run_membership_evidence_supplement_queue.ps1").read_text(
            encoding="utf-8-sig"
        )
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("membership_evidence_supplement_queue.py", wrapper)
        self.assertIn("latest_membership_evidence_supplement_queue.json", wrapper)
        self.assertIn("latest_membership_evidence_supplement_queue.csv", wrapper)
        self.assertIn("latest_membership_evidence_supplement_queue.md", wrapper)
        self.assertNotIn("run_membership_evidence_supplement_queue", bundle)


if __name__ == "__main__":
    unittest.main()
