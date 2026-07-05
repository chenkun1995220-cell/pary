import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_queue(path):
    payload = {
        "queue_schema": "membership_evidence_supplement_queue",
        "queue_version": 1,
        "as_of_date": "2026-07-06",
        "status": "action_required",
        "queue_count": 3,
        "formal_backtest_upgrade_allowed": False,
        "items": [
            {
                "priority": 1,
                "ticker": "ABT",
                "company_name": "Abbott Laboratories",
                "effective_date": "1957-03-04",
                "weeks_affected": 156,
                "current_evidence": "secondary",
                "required_evidence_kind": "official_spglobal_membership_evidence",
                "accepted_source_domains": "spglobal.com,.spglobal.com",
                "rejection_reason": "crosscheck_substitute_cannot_upgrade_historical_membership",
            },
            {
                "priority": 2,
                "ticker": "ADM",
                "company_name": "Archer Daniels Midland",
                "effective_date": "1957-03-04",
                "weeks_affected": 120,
                "current_evidence": "secondary",
                "required_evidence_kind": "official_spglobal_membership_evidence",
                "accepted_source_domains": "spglobal.com,.spglobal.com",
                "rejection_reason": "crosscheck_substitute_cannot_upgrade_historical_membership",
            },
            {
                "priority": 3,
                "ticker": "AEP",
                "company_name": "American Electric Power",
                "effective_date": "1957-03-04",
                "weeks_affected": 80,
                "current_evidence": "secondary",
                "required_evidence_kind": "official_spglobal_membership_evidence",
                "accepted_source_domains": "spglobal.com,.spglobal.com",
                "rejection_reason": "crosscheck_substitute_cannot_upgrade_historical_membership",
            },
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


class MembershipEvidenceSupplementBatchTests(unittest.TestCase):
    def test_builds_top_priority_manual_batch_from_supplement_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "queue.json"
            write_queue(queue)

            from membership_evidence_supplement_batch import build_supplement_batch

            payload = build_supplement_batch(queue, batch_size=2, as_of_date="2026-07-06")

            self.assertEqual(payload["batch_schema"], "membership_evidence_supplement_batch")
            self.assertEqual(payload["status"], "batch_ready")
            self.assertEqual(payload["queue_count"], 3)
            self.assertEqual(payload["batch_size"], 2)
            self.assertEqual(payload["selected_count"], 2)
            self.assertEqual(payload["remaining_after_batch_count"], 1)
            self.assertEqual(payload["batch_tickers"], ["ABT", "ADM"])
            self.assertEqual(payload["batch_weeks_affected"], 276)
            self.assertFalse(payload["applied_to_historical_membership"])
            self.assertFalse(payload["formal_backtest_upgrade_allowed"])
            self.assertEqual(payload["items"][0]["batch_rank"], 1)
            self.assertEqual(payload["items"][0]["membership_evidence"], "")
            self.assertEqual(payload["items"][0]["evidence_kind"], "current_constituents")
            self.assertIn("verified_membership_evidence_intake.csv", payload["completion_condition"])

    def test_cli_writes_batch_json_csv_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "queue.json"
            output_json = root / "batch.json"
            output_csv = root / "batch.csv"
            output_md = root / "batch.md"
            write_queue(queue)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "membership_evidence_supplement_batch.py"),
                    "--queue",
                    str(queue),
                    "--batch-size",
                    "2",
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
            self.assertEqual(payload["batch_tickers"], ["ABT", "ADM"])
            with output_csv.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["ticker"] for row in rows], ["ABT", "ADM"])
            report = output_md.read_text(encoding="utf-8-sig")
            self.assertIn("membership_evidence_supplement_batch", report)
            self.assertIn("remaining_after_batch_count: 1", report)

    def test_wrapper_bundle_and_pre_submit_include_supplement_batch(self):
        wrapper = (PROJECT_ROOT / "scripts" / "run_membership_evidence_supplement_batch.ps1").read_text(
            encoding="utf-8-sig"
        )
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )
        pre_submit = (PROJECT_ROOT / "pre_submit_review.py").read_text(encoding="utf-8-sig")

        self.assertIn("membership_evidence_supplement_batch.py", wrapper)
        self.assertIn("latest_membership_evidence_supplement_batch.json", wrapper)
        self.assertIn("latest_membership_evidence_supplement_batch.csv", wrapper)
        self.assertIn("latest_membership_evidence_supplement_batch.md", wrapper)
        self.assertIn("run_membership_evidence_supplement_batch", bundle)
        self.assertLess(
            bundle.index("run_membership_evidence_supplement_queue"),
            bundle.index("run_membership_evidence_supplement_batch"),
        )
        self.assertLess(
            bundle.index("run_membership_evidence_supplement_batch"),
            bundle.index("run_membership_evidence_source_intake_status"),
        )
        self.assertIn("membership_evidence_supplement_batch", pre_submit)


if __name__ == "__main__":
    unittest.main()
