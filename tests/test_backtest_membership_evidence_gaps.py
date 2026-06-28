import csv
import json
import tempfile
import unittest
from pathlib import Path

from backtest_membership_evidence_gaps import build_evidence_gap_report, write_gap_outputs


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class BacktestMembershipEvidenceGapTests(unittest.TestCase):
    def test_builds_ranked_gap_report_from_weak_membership_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            membership = root / "historical_membership.csv"
            write_csv(
                membership,
                [
                    "week",
                    "ticker",
                    "company_name",
                    "effective_date",
                    "membership_evidence",
                    "membership_source_url",
                ],
                [
                    {
                        "week": "2026-06-05",
                        "ticker": "AAA",
                        "company_name": "Alpha",
                        "effective_date": "2024-01-02",
                        "membership_evidence": "secondary",
                        "membership_source_url": "local.csv",
                    },
                    {
                        "week": "2026-06-12",
                        "ticker": "AAA",
                        "company_name": "Alpha",
                        "effective_date": "2024-01-02",
                        "membership_evidence": "secondary",
                        "membership_source_url": "local.csv",
                    },
                    {
                        "week": "2026-06-12",
                        "ticker": "BBB",
                        "company_name": "Beta",
                        "effective_date": "2025-03-03",
                        "membership_evidence": "insufficient",
                        "membership_source_url": "",
                    },
                    {
                        "week": "2026-06-12",
                        "ticker": "CCC",
                        "company_name": "Gamma",
                        "effective_date": "2025-04-04",
                        "membership_evidence": "verified",
                        "membership_source_url": "https://www.spglobal.com/example.pdf",
                    },
                ],
            )

            report = build_evidence_gap_report(membership, limit=10)

            self.assertEqual(report["total_rows"], 4)
            self.assertEqual(report["weak_rows"], 3)
            self.assertEqual(report["verified_rows"], 1)
            self.assertEqual(report["gap_count"], 2)
            self.assertEqual(report["gaps"][0]["ticker"], "AAA")
            self.assertEqual(report["gaps"][0]["weeks_affected"], 2)
            self.assertEqual(report["gaps"][0]["recommended_action"], "supplement_official_spglobal_source")
            self.assertEqual(report["gaps"][1]["ticker"], "BBB")

    def test_writes_json_csv_and_markdown_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = {
                "schema": "membership_evidence_gap_report",
                "version": 1,
                "membership_path": "historical_membership.csv",
                "total_rows": 2,
                "verified_rows": 0,
                "weak_rows": 2,
                "gap_count": 1,
                "gaps": [
                    {
                        "rank": 1,
                        "ticker": "AAA",
                        "company_name": "Alpha",
                        "effective_date": "2024-01-02",
                        "current_evidence": "secondary",
                        "membership_source_url": "local.csv",
                        "weeks_affected": 2,
                        "first_week": "2026-06-05",
                        "last_week": "2026-06-12",
                        "recommended_action": "supplement_official_spglobal_source",
                    }
                ],
            }

            outputs = write_gap_outputs(
                report,
                root / "latest_membership_evidence_gaps.json",
                root / "latest_membership_evidence_gaps.csv",
                root / "latest_membership_evidence_gaps.md",
            )

            payload = json.loads(Path(outputs["json"]).read_text(encoding="utf-8-sig"))
            markdown = Path(outputs["markdown"]).read_text(encoding="utf-8-sig")
            with Path(outputs["csv"]).open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(payload["gap_count"], 1)
            self.assertEqual(rows[0]["ticker"], "AAA")
            self.assertIn("membership_evidence_gap_report", markdown)
            self.assertIn("AAA", markdown)


if __name__ == "__main__":
    unittest.main()
