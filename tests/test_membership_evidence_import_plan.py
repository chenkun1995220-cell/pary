import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_gap_report(path):
    payload = {
        "schema": "membership_evidence_gap_report",
        "version": 1,
        "gap_count": 2,
        "returned_gap_count": 2,
        "gaps": [
            {
                "rank": 1,
                "ticker": "ABT",
                "company_name": "Abbott Laboratories",
                "effective_date": "1957-03-04",
                "current_evidence": "secondary",
                "membership_source_url": "data/config/us_universe_symbols.csv",
                "weeks_affected": 156,
                "first_week": "2023-07-07",
                "last_week": "2026-06-26",
                "recommended_action": "supplement_official_spglobal_source",
            },
            {
                "rank": 2,
                "ticker": "ADM",
                "company_name": "Archer Daniels Midland",
                "effective_date": "1957-03-04",
                "current_evidence": "secondary",
                "membership_source_url": "data/config/us_universe_symbols.csv",
                "weeks_affected": 156,
                "first_week": "2023-07-07",
                "last_week": "2026-06-26",
                "recommended_action": "supplement_official_spglobal_source",
            },
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def write_priority_gap_report(path):
    payload = {
        "schema": "membership_evidence_gap_report",
        "version": 1,
        "gap_count": 3,
        "returned_gap_count": 3,
        "gaps": [
            {
                "rank": 1,
                "ticker": "LOW",
                "company_name": "Low Impact",
                "effective_date": "2024-01-01",
                "current_evidence": "secondary",
                "membership_source_url": "",
                "weeks_affected": 10,
                "recommended_action": "supplement_official_spglobal_source",
            },
            {
                "rank": 2,
                "ticker": "HIGH",
                "company_name": "High Impact",
                "effective_date": "2024-01-01",
                "current_evidence": "secondary",
                "membership_source_url": "",
                "weeks_affected": 200,
                "recommended_action": "supplement_official_spglobal_source",
            },
            {
                "rank": 3,
                "ticker": "MISS",
                "company_name": "Missing Source",
                "effective_date": "2024-01-01",
                "current_evidence": "secondary",
                "membership_source_url": "",
                "weeks_affected": 300,
                "recommended_action": "supplement_official_spglobal_source",
            },
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


class MembershipEvidenceImportPlanTests(unittest.TestCase):
    def test_builds_import_plan_from_gap_report_and_current_source_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gaps = root / "latest_membership_evidence_gaps.json"
            source_pack = root / "current_membership_sources.csv"
            write_gap_report(gaps)
            write_csv(
                source_pack,
                [
                    {
                        "ticker": "ABT",
                        "membership_evidence": "verified",
                        "membership_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                        "source_as_of_date": "2026-06-30",
                        "notes": "Official S&P DJI index page checked manually.",
                    },
                    {
                        "ticker": "ADM",
                        "membership_evidence": "verified",
                        "membership_source_url": "https://spglobal.com.example.test/sp-500/",
                        "source_as_of_date": "2026-06-30",
                        "notes": "Invalid lookalike host.",
                    },
                ],
                [
                    "ticker",
                    "membership_evidence",
                    "membership_source_url",
                    "source_as_of_date",
                    "notes",
                ],
            )

            from membership_evidence_import_plan import build_membership_evidence_import_plan

            payload = build_membership_evidence_import_plan(gaps, source_pack, as_of_date="2026-06-30")

            self.assertEqual(payload["review_schema"], "membership_evidence_import_plan")
            self.assertEqual(payload["as_of_date"], "2026-06-30")
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["gap_count"], 2)
            self.assertEqual(payload["ready_to_import_count"], 1)
            self.assertEqual(payload["invalid_source_count"], 1)
            self.assertEqual(payload["missing_source_count"], 0)
            self.assertEqual(payload["ready_to_import_weeks_affected"], 156)
            self.assertEqual(payload["invalid_source_weeks_affected"], 156)
            self.assertEqual(payload["missing_source_weeks_affected"], 0)
            self.assertFalse(payload["formal_backtest_upgrade_allowed"])
            by_ticker = {item["ticker"]: item for item in payload["items"]}
            self.assertEqual(by_ticker["ABT"]["import_status"], "ready_current_source")
            self.assertEqual(by_ticker["ABT"]["upgrade_scope"], "current_membership_only")
            self.assertEqual(by_ticker["ADM"]["import_status"], "invalid_current_source")

    def test_import_plan_prioritizes_ready_sources_by_impact_weeks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gaps = root / "latest_membership_evidence_gaps.json"
            source_pack = root / "current_membership_sources.csv"
            write_priority_gap_report(gaps)
            write_csv(
                source_pack,
                [
                    {
                        "ticker": "LOW",
                        "membership_evidence": "verified",
                        "membership_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                        "source_as_of_date": "2026-06-30",
                        "notes": "",
                    },
                    {
                        "ticker": "HIGH",
                        "membership_evidence": "verified",
                        "membership_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                        "source_as_of_date": "2026-06-30",
                        "notes": "",
                    },
                ],
                [
                    "ticker",
                    "membership_evidence",
                    "membership_source_url",
                    "source_as_of_date",
                    "notes",
                ],
            )

            from membership_evidence_import_plan import build_membership_evidence_import_plan

            payload = build_membership_evidence_import_plan(gaps, source_pack, as_of_date="2026-06-30")

            self.assertEqual(
                [item["ticker"] for item in payload["items"]],
                ["HIGH", "LOW", "MISS"],
            )
            self.assertEqual(payload["next_action"], "run_membership_evidence_apply_preview")
            self.assertEqual(payload["ready_to_import_count"], 2)
            self.assertEqual(payload["ready_to_import_weeks_affected"], 210)

    def test_cli_writes_json_csv_and_markdown_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gaps = root / "latest_membership_evidence_gaps.json"
            source_pack = root / "missing_current_sources.csv"
            output_json = root / "plan.json"
            output_csv = root / "plan.csv"
            output_md = root / "plan.md"
            source_template = root / "current_sources_template.csv"
            write_gap_report(gaps)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "membership_evidence_import_plan.py"),
                    "--gaps",
                    str(gaps),
                    "--current-source-pack",
                    str(source_pack),
                    "--output-json",
                    str(output_json),
                    "--output-csv",
                    str(output_csv),
                    "--output-md",
                    str(output_md),
                    "--source-template",
                    str(source_template),
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
            self.assertEqual(payload["missing_source_count"], 2)
            self.assertEqual(payload["ready_to_import_count"], 0)
            self.assertEqual(payload["missing_source_weeks_affected"], 312)
            self.assertEqual(payload["next_action"], "provide_current_membership_sources")
            self.assertIn("membership_evidence_import_plan", output_md.read_text(encoding="utf-8-sig"))
            self.assertIn("missing_source_weeks_affected: 312", output_md.read_text(encoding="utf-8-sig"))
            self.assertIn("next_action: provide_current_membership_sources", output_md.read_text(encoding="utf-8-sig"))
            self.assertIn("ABT", output_csv.read_text(encoding="utf-8-sig"))
            template_text = source_template.read_text(encoding="utf-8-sig")
            self.assertIn("ticker,membership_evidence,membership_source_url,source_as_of_date,notes", template_text)
            self.assertIn("ABT,verified,,", template_text)

    def test_powershell_wrapper_and_reporting_bundle_include_import_plan(self):
        wrapper = (PROJECT_ROOT / "scripts" / "run_membership_evidence_import_plan.ps1").read_text(
            encoding="utf-8-sig"
        )
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("membership_evidence_import_plan.py", wrapper)
        self.assertIn("latest_membership_evidence_gaps.json", wrapper)
        self.assertIn("us_sp500_current_membership_sources.csv", wrapper)
        self.assertIn("latest_membership_evidence_import_plan.json", wrapper)
        self.assertIn("latest_membership_evidence_import_plan.csv", wrapper)
        self.assertIn("latest_membership_evidence_import_plan.md", wrapper)
        self.assertIn("us_sp500_current_membership_sources_template.csv", wrapper)
        self.assertIn("run_sp500_current_membership_sources", bundle)
        self.assertIn("run_membership_evidence_import_plan", bundle)
        self.assertLess(
            bundle.index("run_sp500_current_membership_sources"),
            bundle.index("run_membership_evidence_import_plan"),
        )
        self.assertLess(
            bundle.index("run_backtest_evidence_review"),
            bundle.index("run_membership_evidence_import_plan"),
        )
        self.assertLess(
            bundle.index("run_membership_evidence_import_plan"),
            bundle.index("run_medium_term_goal_review"),
        )


if __name__ == "__main__":
    unittest.main()
