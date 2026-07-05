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
        "queue_count": 2,
        "formal_backtest_upgrade_allowed": False,
        "items": [
            {
                "priority": 1,
                "ticker": "ABT",
                "company_name": "Abbott Laboratories",
                "effective_date": "1957-03-04",
                "weeks_affected": 156,
                "current_evidence": "secondary",
                "import_status": "invalid_current_source",
                "required_evidence_kind": "official_spglobal_membership_evidence",
                "accepted_source_domains": "spglobal.com,.spglobal.com",
                "recommended_action": "supplement_official_spglobal_source",
            },
            {
                "priority": 2,
                "ticker": "ADM",
                "company_name": "Archer Daniels Midland",
                "effective_date": "1957-03-04",
                "weeks_affected": 156,
                "current_evidence": "secondary",
                "import_status": "invalid_current_source",
                "required_evidence_kind": "official_spglobal_membership_evidence",
                "accepted_source_domains": "spglobal.com,.spglobal.com",
                "recommended_action": "supplement_official_spglobal_source",
            },
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


class MembershipEvidenceSourceIntakeStatusTests(unittest.TestCase):
    def test_validates_manual_evidence_against_official_source_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue.json"
            intake_path = root / "intake.csv"
            template_path = root / "template.csv"
            write_queue(queue_path)
            with intake_path.open("w", encoding="utf-8-sig", newline="") as handle:
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
                        "source_as_of_date": "2026-07-06",
                        "evidence_kind": "current_constituents",
                        "notes": "official page",
                        "reviewer": "manual",
                    }
                )
                writer.writerow(
                    {
                        "ticker": "ADM",
                        "company_name": "Archer Daniels Midland",
                        "membership_evidence": "verified",
                        "membership_source_url": "local://sp500_crosscheck_substitute",
                        "source_as_of_date": "2026-07-06",
                        "evidence_kind": "current_constituents",
                        "notes": "crosscheck only",
                        "reviewer": "manual",
                    }
                )

            from membership_evidence_source_intake_status import build_source_intake_status

            payload = build_source_intake_status(
                queue_path,
                intake_path=intake_path,
                template_path=template_path,
                source_pack_path=root / "verified_source_pack.csv",
                as_of_date="2026-07-06",
            )

            self.assertEqual(payload["status_schema"], "membership_evidence_source_intake_status")
            self.assertEqual(payload["status"], "ready_with_rejections")
            self.assertEqual(payload["queue_count"], 2)
            self.assertEqual(payload["ready_to_import_count"], 1)
            self.assertEqual(payload["invalid_count"], 1)
            self.assertEqual(payload["pending_count"], 0)
            self.assertFalse(payload["formal_backtest_upgrade_allowed"])
            by_ticker = {row["ticker"]: row for row in payload["items"]}
            self.assertEqual(by_ticker["ABT"]["validation_status"], "ready_current_source")
            self.assertEqual(by_ticker["ABT"]["source_trust_level"], "verified")
            self.assertEqual(by_ticker["ADM"]["validation_status"], "invalid_source_policy")
            self.assertEqual(by_ticker["ADM"]["source_trust_level"], "crosscheck_substitute")
            self.assertIn("cannot_upgrade", by_ticker["ADM"]["validation_reason"])
            self.assertEqual(payload["source_pack_ready_count"], 1)
            self.assertEqual(payload["source_pack_path"], str(root / "verified_source_pack.csv"))
            with (root / "verified_source_pack.csv").open(encoding="utf-8-sig", newline="") as handle:
                source_rows = list(csv.DictReader(handle))
            self.assertEqual(len(source_rows), 1)
            self.assertEqual(source_rows[0]["ticker"], "ABT")
            self.assertEqual(source_rows[0]["membership_evidence"], "verified")
            self.assertEqual(
                source_rows[0]["membership_source_url"],
                "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
            )

    def test_missing_intake_creates_template_and_waits_for_manual_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue.json"
            intake_path = root / "missing_intake.csv"
            template_path = root / "template.csv"
            write_queue(queue_path)

            from membership_evidence_source_intake_status import build_source_intake_status

            payload = build_source_intake_status(
                queue_path,
                intake_path=intake_path,
                template_path=template_path,
                source_pack_path=root / "verified_source_pack.csv",
                as_of_date="2026-07-06",
            )

            self.assertEqual(payload["status"], "awaiting_manual_evidence")
            self.assertEqual(payload["template_status"], "created")
            self.assertEqual(payload["ready_to_import_count"], 0)
            self.assertEqual(payload["pending_count"], 2)
            self.assertTrue(template_path.exists())
            with template_path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["ticker"] for row in rows], ["ABT", "ADM"])
            self.assertEqual(rows[0]["evidence_kind"], "current_constituents")
            with (root / "verified_source_pack.csv").open(encoding="utf-8-sig", newline="") as handle:
                source_rows = list(csv.DictReader(handle))
            self.assertEqual(source_rows, [])

    def test_cli_wrapper_bundle_and_pre_submit_include_source_intake_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue.json"
            output_json = root / "status.json"
            output_csv = root / "status.csv"
            output_md = root / "status.md"
            template_path = root / "template.csv"
            source_pack_path = root / "verified_source_pack.csv"
            write_queue(queue_path)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "membership_evidence_source_intake_status.py"),
                    "--queue",
                    str(queue_path),
                    "--intake",
                    str(root / "missing_intake.csv"),
                    "--template",
                    str(template_path),
                    "--source-pack",
                    str(source_pack_path),
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
            self.assertEqual(payload["status"], "awaiting_manual_evidence")
            self.assertTrue(output_csv.exists())
            self.assertTrue(source_pack_path.exists())
            self.assertIn("membership_evidence_source_intake_status", output_md.read_text(encoding="utf-8-sig"))

        wrapper = (PROJECT_ROOT / "scripts" / "run_membership_evidence_source_intake_status.ps1").read_text(
            encoding="utf-8-sig"
        )
        apply_wrapper = (PROJECT_ROOT / "scripts" / "run_membership_evidence_apply_preview.ps1").read_text(
            encoding="utf-8-sig"
        )
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(encoding="utf-8-sig")
        pre_submit = (PROJECT_ROOT / "pre_submit_review.py").read_text(encoding="utf-8-sig")

        self.assertIn("membership_evidence_source_intake_status.py", wrapper)
        self.assertIn("latest_membership_evidence_source_intake_status.json", wrapper)
        self.assertIn("latest_membership_evidence_verified_source_pack.csv", wrapper)
        self.assertIn("latest_membership_evidence_verified_source_pack.csv", apply_wrapper)
        self.assertIn("run_membership_evidence_source_intake_status", bundle)
        self.assertLess(
            bundle.index("run_membership_evidence_supplement_queue"),
            bundle.index("run_membership_evidence_source_intake_status"),
        )
        self.assertLess(
            bundle.index("run_membership_evidence_source_intake_status"),
            bundle.index("run_sp500_verified_source_plan"),
        )
        self.assertIn("membership_evidence_source_intake_status", pre_submit)


if __name__ == "__main__":
    unittest.main()
