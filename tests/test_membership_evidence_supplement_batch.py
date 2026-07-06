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
            self.assertIn("membership_evidence=verified", payload["items"][0]["manual_entry_instruction"])
            self.assertIn("YYYY-MM-DD", payload["items"][0]["manual_entry_instruction"])
            self.assertIn("site:spglobal.com/spdji", payload["items"][0]["official_domain_search_query"])
            self.assertIn("ABT", payload["items"][0]["official_domain_search_query"])
            self.assertIn("Abbott Laboratories", payload["items"][0]["official_domain_search_query"])
            self.assertIn("https://www.google.com/search?q=", payload["items"][0]["official_domain_search_url"])
            self.assertIn("site%3Aspglobal.com%2Fspdji", payload["items"][0]["official_domain_search_url"])
            self.assertIn("https://www.spglobal.com/spdji/en/indices/equity/sp-500/", payload["items"][0]["official_index_page_url"])
            self.assertIn("search query is not evidence", payload["items"][0]["manual_entry_instruction"])
            self.assertIn("run_membership_evidence_source_intake_status.ps1", payload["validation_command"])
            self.assertIn("run_membership_evidence_import_plan_from_verified_intake.ps1", payload["next_command_after_ready"])
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
            self.assertIn("membership_evidence=verified", rows[0]["manual_entry_instruction"])
            self.assertIn("run_membership_evidence_source_intake_status.ps1", rows[0]["validation_command"])
            self.assertIn("site:spglobal.com/spdji", rows[0]["official_domain_search_query"])
            self.assertIn("https://www.google.com/search?q=", rows[0]["official_domain_search_url"])
            self.assertIn("https://www.spglobal.com/spdji/en/indices/equity/sp-500/", rows[0]["official_index_page_url"])
            report = output_md.read_text(encoding="utf-8-sig")
            self.assertIn("membership_evidence_supplement_batch", report)
            self.assertIn("remaining_after_batch_count: 1", report)
            self.assertIn("## manual_entry_rules", report)
            self.assertIn("source_as_of_date must use YYYY-MM-DD", report)
            self.assertIn("## official_domain_search_guidance", report)
            self.assertIn("site:spglobal.com/spdji", report)
            self.assertIn("https://www.google.com/search?q=", report)
            self.assertIn("run_membership_evidence_source_intake_status.ps1", report)

    def test_cli_can_write_inputs_side_intake_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "queue.json"
            output_json = root / "batch.json"
            output_csv = root / "batch.csv"
            output_md = root / "batch.md"
            intake_draft = root / "inputs" / "sp500_membership_evidence" / "verified_membership_evidence_intake.csv"
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
                    "--intake-draft",
                    str(intake_draft),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with intake_draft.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["ticker"] for row in rows], ["ABT", "ADM"])
            self.assertEqual(rows[0]["membership_evidence"], "")
            self.assertEqual(rows[0]["membership_source_url"], "")
            self.assertEqual(rows[0]["source_as_of_date"], "")
            self.assertEqual(rows[0]["evidence_kind"], "current_constituents")
            self.assertIn("site:spglobal.com/spdji", rows[0]["official_domain_search_query"])
            self.assertIn("https://www.google.com/search?q=", rows[0]["official_domain_search_url"])
            self.assertIn("search query is not evidence", rows[0]["manual_entry_instruction"])
            self.assertIn("membership_evidence=verified", rows[0]["manual_entry_instruction"])
            payload = json.loads(output_json.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["intake_draft_path"], str(intake_draft))

    def test_cli_preserves_existing_manual_evidence_when_regenerating_intake_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "queue.json"
            output_json = root / "batch.json"
            output_csv = root / "batch.csv"
            output_md = root / "batch.md"
            intake_draft = root / "inputs" / "sp500_membership_evidence" / "verified_membership_evidence_intake.csv"
            write_queue(queue)
            intake_draft.parent.mkdir(parents=True, exist_ok=True)
            with intake_draft.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "ticker",
                        "company_name",
                        "membership_evidence",
                        "membership_source_url",
                        "source_as_of_date",
                        "evidence_kind",
                        "notes",
                        "reviewer",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "ticker": "ABT",
                        "company_name": "Abbott Laboratories",
                        "membership_evidence": "verified",
                        "membership_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                        "source_as_of_date": "2026-07-07",
                        "evidence_kind": "current_constituents",
                        "notes": "manual official page candidate",
                        "reviewer": "manual",
                    }
                )

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "membership_evidence_supplement_batch.py"),
                    "--queue",
                    str(queue),
                    "--batch-size",
                    "2",
                    "--as-of-date",
                    "2026-07-08",
                    "--output-json",
                    str(output_json),
                    "--output-csv",
                    str(output_csv),
                    "--output-md",
                    str(output_md),
                    "--intake-draft",
                    str(intake_draft),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with intake_draft.open(encoding="utf-8-sig", newline="") as handle:
                rows = {row["ticker"]: row for row in csv.DictReader(handle)}
            self.assertEqual(rows["ABT"]["batch_id"], "2026-07-08-p1")
            self.assertEqual(rows["ABT"]["membership_evidence"], "verified")
            self.assertEqual(
                rows["ABT"]["membership_source_url"],
                "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
            )
            self.assertEqual(rows["ABT"]["source_as_of_date"], "2026-07-07")
            self.assertEqual(rows["ABT"]["notes"], "manual official page candidate")
            self.assertEqual(rows["ABT"]["reviewer"], "manual")
            self.assertIn("official_domain_search_url", rows["ABT"])
            self.assertEqual(rows["ADM"]["membership_evidence"], "")
            payload = json.loads(output_json.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["preserved_manual_evidence_count"], 1)

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
        self.assertIn("verified_membership_evidence_intake.csv", wrapper)
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
