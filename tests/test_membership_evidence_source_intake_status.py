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
                        "notes": "official page shows ABT as current constituent",
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

    def test_rejects_generic_official_index_page_without_ticker_observation_note(self):
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

            from membership_evidence_source_intake_status import build_source_intake_status

            payload = build_source_intake_status(
                queue_path,
                intake_path=intake_path,
                template_path=template_path,
                source_pack_path=root / "verified_source_pack.csv",
                as_of_date="2026-07-06",
            )

            by_ticker = {row["ticker"]: row for row in payload["items"]}
            self.assertEqual(payload["ready_to_import_count"], 0)
            self.assertEqual(payload["invalid_count"], 1)
            self.assertEqual(by_ticker["ABT"]["validation_status"], "invalid_generic_official_source")
            self.assertEqual(by_ticker["ABT"]["validation_reason"], "generic_official_page_requires_ticker_observation_note")
            with (root / "verified_source_pack.csv").open(encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(list(csv.DictReader(handle)), [])

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

    def test_blank_intake_draft_rows_remain_pending_manual_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue.json"
            intake_path = root / "verified_membership_evidence_intake.csv"
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
                        "membership_evidence": "",
                        "membership_source_url": "",
                        "source_as_of_date": "",
                        "evidence_kind": "current_constituents",
                        "notes": "",
                        "reviewer": "",
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

            self.assertEqual(payload["status"], "awaiting_manual_evidence")
            self.assertEqual(payload["ready_to_import_count"], 0)
            self.assertEqual(payload["invalid_count"], 0)
            self.assertEqual(payload["pending_count"], 2)
            by_ticker = {row["ticker"]: row for row in payload["items"]}
            self.assertEqual(by_ticker["ABT"]["validation_status"], "pending_manual_evidence")
            self.assertEqual(by_ticker["ABT"]["validation_reason"], "manual_evidence_missing")

    def test_summarizes_current_batch_completion_from_intake_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue.json"
            intake_path = root / "verified_membership_evidence_intake.csv"
            template_path = root / "template.csv"
            write_queue(queue_path)
            with intake_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "batch_id",
                        "batch_rank",
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
                        "batch_id": "2026-07-06-p1",
                        "batch_rank": "1",
                        "ticker": "ABT",
                        "company_name": "Abbott Laboratories",
                        "membership_evidence": "verified",
                        "membership_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                        "source_as_of_date": "2026-07-06",
                        "evidence_kind": "current_constituents",
                        "notes": "official page shows ABT as current constituent",
                        "reviewer": "manual",
                    }
                )
                writer.writerow(
                    {
                        "batch_id": "2026-07-06-p1",
                        "batch_rank": "2",
                        "ticker": "ADM",
                        "company_name": "Archer Daniels Midland",
                        "membership_evidence": "",
                        "membership_source_url": "",
                        "source_as_of_date": "",
                        "evidence_kind": "current_constituents",
                        "notes": "",
                        "reviewer": "",
                    }
                )

            from membership_evidence_source_intake_status import (
                build_source_intake_status,
                render_markdown,
            )

            payload = build_source_intake_status(
                queue_path,
                intake_path=intake_path,
                template_path=template_path,
                source_pack_path=root / "verified_source_pack.csv",
                as_of_date="2026-07-06",
            )
            markdown = render_markdown(payload)

            self.assertEqual(payload["current_batch_id"], "2026-07-06-p1")
            self.assertEqual(payload["current_batch_count"], 2)
            self.assertEqual(payload["current_batch_ready_count"], 1)
            self.assertEqual(payload["current_batch_pending_count"], 1)
            self.assertEqual(payload["current_batch_invalid_count"], 0)
            self.assertEqual(payload["current_batch_tickers"], ["ABT", "ADM"])
            self.assertEqual(payload["current_batch_completion_ratio"], 0.5)
            self.assertIn("current_batch_manual_checklist", payload)
            self.assertEqual(len(payload["current_batch_manual_checklist"]), 1)
            self.assertEqual(payload["current_batch_manual_checklist"][0]["ticker"], "ADM")
            self.assertEqual(
                payload["current_batch_manual_checklist"][0]["validation_reason"],
                "manual_evidence_missing",
            )
            self.assertIn(
                "site:spglobal.com/spdji",
                payload["current_batch_manual_checklist"][0]["official_domain_search_query"],
            )
            self.assertIn(
                "https://www.google.com/search?q=",
                payload["current_batch_manual_checklist"][0]["official_domain_search_url"],
            )
            self.assertIn(
                "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                payload["current_batch_manual_checklist"][0]["official_index_page_url"],
            )
            self.assertIn(
                "membership_evidence=verified",
                payload["current_batch_manual_checklist"][0]["manual_entry_instruction"],
            )
            self.assertIn(
                "run_membership_evidence_source_intake_status.ps1",
                payload["current_batch_manual_checklist"][0]["validation_command"],
            )
            by_ticker = {row["ticker"]: row for row in payload["items"]}
            self.assertEqual(by_ticker["ABT"]["batch_id"], "2026-07-06-p1")
            self.assertEqual(by_ticker["ADM"]["batch_rank"], 2)
            self.assertIn("current_batch_id: 2026-07-06-p1", markdown)
            self.assertIn("current_batch_ready_count: 1", markdown)
            self.assertIn("## current_batch_manual_checklist", markdown)
            self.assertIn("site:spglobal.com/spdji", markdown)
            self.assertIn("https://www.google.com/search?q=", markdown)
            self.assertIn("ADM", markdown)

    def test_builds_current_batch_manual_work_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue.json"
            intake_path = root / "missing_intake.csv"
            template_path = root / "template.csv"
            write_queue(queue_path)

            from membership_evidence_source_intake_status import (
                build_source_intake_status,
                render_manual_work_package_markdown,
                write_manual_work_package_csv,
            )

            payload = build_source_intake_status(
                queue_path,
                intake_path=intake_path,
                template_path=template_path,
                source_pack_path=root / "verified_source_pack.csv",
                as_of_date="2026-07-06",
            )
            work_package = payload["current_batch_manual_work_package"]

            self.assertEqual(len(work_package), 2)
            self.assertEqual(work_package[0]["ticker"], "ABT")
            self.assertEqual(work_package[0]["membership_evidence"], "verified")
            self.assertEqual(work_package[0]["evidence_kind"], "current_constituents")
            self.assertEqual(
                work_package[0]["notes_example"],
                "official page shows ABT or Abbott Laboratories as current constituent",
            )
            self.assertIn("site:spglobal.com/spdji", work_package[0]["official_domain_search_query"])
            self.assertIn("https://www.google.com/search?q=", work_package[0]["official_domain_search_url"])
            self.assertIn("spglobal.com,.spglobal.com", work_package[0]["accepted_source_domains"])
            self.assertIn("crosscheck", work_package[0]["rejected_source_examples"])
            self.assertIn("run_membership_evidence_source_intake_status.ps1", work_package[0]["validation_command"])

            work_package_csv = root / "manual_work_package.csv"
            write_manual_work_package_csv(payload, work_package_csv)
            with work_package_csv.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["ticker"], "ABT")
            self.assertEqual(rows[0]["membership_evidence"], "verified")
            self.assertEqual(rows[0]["membership_source_url"], "")
            self.assertEqual(rows[0]["source_as_of_date"], "")

            markdown = render_manual_work_package_markdown(payload)
            self.assertIn("# S&P 500 verified evidence manual work package", markdown)
            self.assertIn("current_batch_id", markdown)
            self.assertIn("ABT", markdown)
            self.assertIn("notes_example", markdown)
            self.assertIn("crosscheck substitute is not verified evidence", markdown)

    def test_rejects_invalid_or_future_source_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue.json"
            intake_path = root / "verified_membership_evidence_intake.csv"
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
                        "source_as_of_date": "not-a-date",
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
                        "membership_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                        "source_as_of_date": "2026-07-07",
                        "evidence_kind": "current_constituents",
                        "notes": "official page",
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

            self.assertEqual(payload["status"], "needs_review")
            self.assertEqual(payload["ready_to_import_count"], 0)
            self.assertEqual(payload["invalid_count"], 2)
            by_ticker = {row["ticker"]: row for row in payload["items"]}
            self.assertEqual(by_ticker["ABT"]["validation_status"], "invalid_source_date")
            self.assertEqual(by_ticker["ABT"]["validation_reason"], "source_as_of_date_invalid")
            self.assertEqual(by_ticker["ADM"]["validation_status"], "invalid_future_source_date")
            self.assertEqual(by_ticker["ADM"]["validation_reason"], "source_as_of_date_after_review_date")
            with (root / "verified_source_pack.csv").open(encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(list(csv.DictReader(handle)), [])

    def test_cli_wrapper_bundle_and_pre_submit_include_source_intake_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue.json"
            output_json = root / "status.json"
            output_csv = root / "status.csv"
            output_md = root / "status.md"
            work_package_csv = root / "manual_work_package.csv"
            work_package_md = root / "manual_work_package.md"
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
                    "--manual-work-package-csv",
                    str(work_package_csv),
                    "--manual-work-package-md",
                    str(work_package_md),
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
            self.assertTrue(work_package_csv.exists())
            self.assertTrue(work_package_md.exists())
            self.assertIn("manual work package", work_package_md.read_text(encoding="utf-8-sig"))

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
        self.assertIn("latest_membership_evidence_manual_work_package.csv", wrapper)
        self.assertIn("latest_membership_evidence_verified_source_pack.csv", apply_wrapper)
        refresh_wrapper = (
            PROJECT_ROOT / "scripts" / "run_membership_evidence_import_plan_from_verified_intake.ps1"
        ).read_text(encoding="utf-8-sig")
        self.assertIn("run_membership_evidence_import_plan.ps1", refresh_wrapper)
        self.assertIn("latest_membership_evidence_verified_source_pack.csv", refresh_wrapper)
        self.assertIn("run_membership_evidence_source_intake_status", bundle)
        self.assertIn("run_membership_evidence_import_plan_from_verified_intake", bundle)
        self.assertLess(
            bundle.index("run_membership_evidence_supplement_queue"),
            bundle.index("run_membership_evidence_source_intake_status"),
        )
        self.assertLess(
            bundle.index("run_membership_evidence_source_intake_status"),
            bundle.index("run_membership_evidence_import_plan_from_verified_intake"),
        )
        self.assertLess(
            bundle.index("run_membership_evidence_import_plan_from_verified_intake"),
            bundle.index("run_sp500_verified_source_plan"),
        )
        self.assertIn("membership_evidence_source_intake_status", pre_submit)


if __name__ == "__main__":
    unittest.main()
