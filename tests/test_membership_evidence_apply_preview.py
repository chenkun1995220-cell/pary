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


def write_historical_membership(path):
    write_csv(
        path,
        [
            {
                "week": "2026-06-19",
                "market": "US",
                "ticker": "ABT",
                "cik": "0000001800",
                "company_name": "Abbott Laboratories",
                "industry": "Health Care",
                "gics_sub_industry": "Health Care Equipment",
                "date_added": "1957-03-04",
                "effective_date": "1957-03-04",
                "membership_evidence": "secondary",
                "membership_source_url": "data/config/us_universe_symbols.csv",
                "available_at": "2026-06-19",
            },
            {
                "week": "2026-06-26",
                "market": "US",
                "ticker": "ABT",
                "cik": "0000001800",
                "company_name": "Abbott Laboratories",
                "industry": "Health Care",
                "gics_sub_industry": "Health Care Equipment",
                "date_added": "1957-03-04",
                "effective_date": "1957-03-04",
                "membership_evidence": "secondary",
                "membership_source_url": "data/config/us_universe_symbols.csv",
                "available_at": "2026-06-26",
            },
            {
                "week": "2026-06-26",
                "market": "US",
                "ticker": "ADM",
                "cik": "0000007084",
                "company_name": "Archer Daniels Midland",
                "industry": "Consumer Staples",
                "gics_sub_industry": "Agricultural Products",
                "date_added": "1957-03-04",
                "effective_date": "1957-03-04",
                "membership_evidence": "secondary",
                "membership_source_url": "data/config/us_universe_symbols.csv",
                "available_at": "2026-06-26",
            },
            {
                "week": "2026-06-26",
                "market": "US",
                "ticker": "AEP",
                "cik": "0000004904",
                "company_name": "American Electric Power",
                "industry": "Utilities",
                "gics_sub_industry": "Electric Utilities",
                "date_added": "1957-03-04",
                "effective_date": "1957-03-04",
                "membership_evidence": "verified",
                "membership_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                "available_at": "2026-06-26",
            },
        ],
        [
            "week",
            "market",
            "ticker",
            "cik",
            "company_name",
            "industry",
            "gics_sub_industry",
            "date_added",
            "effective_date",
            "membership_evidence",
            "membership_source_url",
            "available_at",
        ],
    )


def write_current_sources(path):
    write_csv(
        path,
        [
            {
                "ticker": "ABT",
                "membership_evidence": "verified",
                "membership_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                "source_as_of_date": "2026-06-30",
                "notes": "Official current membership source.",
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


class MembershipEvidenceApplyPreviewTests(unittest.TestCase):
    def test_builds_read_only_preview_for_rows_upgradable_by_current_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            membership = root / "historical_membership.csv"
            sources = root / "current_sources.csv"
            write_historical_membership(membership)
            write_current_sources(sources)
            before = membership.read_text(encoding="utf-8-sig")

            from membership_evidence_apply_preview import build_apply_preview

            payload = build_apply_preview(
                membership,
                sources,
                as_of_date="2026-06-30",
            )

            self.assertEqual(payload["preview_schema"], "membership_evidence_apply_preview")
            self.assertEqual(payload["preview_version"], 1)
            self.assertEqual(payload["status"], "ready")
            self.assertFalse(payload["applied_to_historical_membership"])
            self.assertEqual(payload["eligible_ticker_count"], 1)
            self.assertEqual(payload["preview_row_count"], 2)
            self.assertEqual(payload["preview_weeks_affected"], 2)
            self.assertEqual(payload["invalid_source_ticker_count"], 1)
            self.assertEqual(payload["already_verified_row_count"], 1)
            self.assertEqual(membership.read_text(encoding="utf-8-sig"), before)
            tickers = {item["ticker"] for item in payload["items"]}
            self.assertEqual(tickers, {"ABT"})
            self.assertEqual(payload["items"][0]["proposed_evidence"], "verified")
            self.assertEqual(
                payload["items"][0]["proposed_membership_source_url"],
                "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
            )

    def test_cli_writes_json_csv_and_markdown_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            membership = root / "historical_membership.csv"
            sources = root / "current_sources.csv"
            output_json = root / "preview.json"
            output_csv = root / "preview.csv"
            output_md = root / "preview.md"
            write_historical_membership(membership)
            write_current_sources(sources)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "membership_evidence_apply_preview.py"),
                    "--membership",
                    str(membership),
                    "--current-source-pack",
                    str(sources),
                    "--as-of-date",
                    "2026-06-30",
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
            self.assertEqual(payload["preview_row_count"], 2)
            self.assertIn("ABT", output_csv.read_text(encoding="utf-8-sig"))
            report = output_md.read_text(encoding="utf-8-sig")
            self.assertIn("membership_evidence_apply_preview", report)
            self.assertIn("preview_row_count: 2", report)

    def test_powershell_wrapper_remains_manual_and_bundle_excludes_apply_preview(self):
        wrapper = (PROJECT_ROOT / "scripts" / "run_membership_evidence_apply_preview.ps1").read_text(
            encoding="utf-8-sig"
        )
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("membership_evidence_apply_preview.py", wrapper)
        self.assertIn("historical_membership.csv", wrapper)
        self.assertIn("us_sp500_current_membership_sources.csv", wrapper)
        self.assertIn("latest_membership_evidence_apply_preview.json", wrapper)
        self.assertIn("latest_membership_evidence_apply_preview.csv", wrapper)
        self.assertIn("latest_membership_evidence_apply_preview.md", wrapper)
        self.assertNotIn("run_membership_evidence_apply_preview", bundle)


if __name__ == "__main__":
    unittest.main()
