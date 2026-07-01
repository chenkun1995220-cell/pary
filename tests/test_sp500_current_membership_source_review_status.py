import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_review_queue(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "ticker",
                "review_status",
                "issue_type",
                "recommended_check",
                "required_source_url",
                "source_status",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "ticker": "ZZZ",
                "review_status": "open",
                "issue_type": "missing_from_official_current_source",
                "recommended_check": "Confirm official coverage.",
                "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                "source_status": "ready",
            }
        )
        writer.writerow(
            {
                "ticker": "OLD",
                "review_status": "resolved",
                "issue_type": "missing_from_official_current_source",
                "recommended_check": "Already confirmed.",
                "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                "source_status": "ready",
            }
        )


def write_review_decisions(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "ticker",
                "review_decision",
                "official_source_checked",
                "required_source_url",
                "issue_type",
                "recommended_check",
                "decision_notes",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "ticker": "ZZZ",
                "review_decision": "official_absent",
                "official_source_checked": "yes",
                "required_source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
                "issue_type": "missing_from_official_current_source",
                "recommended_check": "Confirmed from official source.",
                "decision_notes": "Official current source does not include this ticker.",
            }
        )


class Sp500CurrentMembershipSourceReviewStatusTests(unittest.TestCase):
    def test_builds_review_status_from_queue_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "sp500_current_membership_source_review_queue.csv"
            write_review_queue(queue)

            from sp500_current_membership_source_review_status import (
                build_review_status,
                render_review_status,
            )

            payload = build_review_status(queue, as_of_date="2026-07-01")
            report = render_review_status(payload)

            self.assertEqual(
                payload["review_status_schema"],
                "sp500_current_membership_source_review_status",
            )
            self.assertEqual(payload["status"], "review_needed")
            self.assertEqual(payload["queue_total_count"], 2)
            self.assertEqual(payload["open_count"], 1)
            self.assertEqual(payload["resolved_count"], 1)
            self.assertEqual(payload["open_items"][0]["ticker"], "ZZZ")
            self.assertEqual(payload["next_action"], "review_open_queue_items")
            self.assertEqual(payload["manual_decision_next_step"], "fill_decisions_template")
            self.assertEqual(payload["decision_pending_tickers"], ["ZZZ"])
            self.assertEqual(payload["decision_ready_to_apply_tickers"], [])
            self.assertFalse(payload["formal_backtest_upgrade_allowed"])
            self.assertIn("decision_options", payload)
            self.assertIn("decision_required_fields", payload)
            self.assertIn(
                "official_absent",
                [item["review_decision"] for item in payload["decision_options"]],
            )
            self.assertIn("review_decision", payload["decision_required_fields"])
            self.assertIn("decision_notes", payload["decision_required_fields"])
            self.assertIn("ZZZ", report)
            self.assertIn("open_count=1", report)
            self.assertIn("manual_decision_next_step=fill_decisions_template", report)
            self.assertIn("decision_pending_tickers=ZZZ", report)
            self.assertIn("人工决策指引", report)
            self.assertIn("official_absent", report)
            self.assertIn("decision_notes", report)

    def test_marks_open_queue_ready_to_apply_when_decision_file_confirms_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "sp500_current_membership_source_review_queue.csv"
            decisions = root / "sp500_current_membership_source_review_decisions.csv"
            write_review_queue(queue)
            write_review_decisions(decisions)

            from sp500_current_membership_source_review_status import (
                build_review_status,
                render_review_status,
            )

            payload = build_review_status(
                queue,
                as_of_date="2026-07-01",
                decisions_path=decisions,
            )
            report = render_review_status(payload)

            self.assertEqual(payload["status"], "review_needed")
            self.assertEqual(payload["review_decision_status"], "ready_to_apply")
            self.assertEqual(payload["decision_file"], str(decisions))
            self.assertTrue(payload["decision_file_exists"])
            self.assertEqual(payload["decision_total_count"], 1)
            self.assertEqual(payload["decision_matched_open_count"], 1)
            self.assertEqual(payload["decision_ready_to_apply_count"], 1)
            self.assertEqual(payload["decision_pending_count"], 0)
            self.assertEqual(payload["manual_decision_next_step"], "apply_review_decisions_to_queue")
            self.assertEqual(payload["decision_pending_tickers"], [])
            self.assertEqual(payload["decision_ready_to_apply_tickers"], ["ZZZ"])
            self.assertEqual(payload["decision_invalid_count"], 0)
            self.assertEqual(payload["decision_items"][0]["ticker"], "ZZZ")
            self.assertEqual(payload["next_action"], "apply_review_decisions_to_queue")
            self.assertFalse(payload["formal_backtest_upgrade_allowed"])
            self.assertIn("ready_to_apply", report)

    def test_cli_writes_json_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "queue.csv"
            output = root / "status.json"
            report = root / "status.md"
            decisions = root / "decisions_template.csv"
            decision_file = root / "decisions.csv"
            write_review_queue(queue)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "sp500_current_membership_source_review_status.py"),
                    "--queue",
                    str(queue),
                    "--as-of-date",
                    "2026-07-01",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--decisions-template",
                    str(decisions),
                    "--decisions",
                    str(decision_file),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            combined = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, combined)
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["open_count"], 1)
            self.assertEqual(payload["decisions_template_file"], str(decisions))
            self.assertTrue(payload["decisions_template_exists"])
            self.assertEqual(payload["decisions_template_status"], "ready")
            self.assertEqual(payload["decisions_template_total_count"], 1)
            self.assertEqual(payload["decisions_template_matched_open_count"], 1)
            self.assertEqual(payload["decisions_template_missing_open_tickers"], [])
            self.assertEqual(payload["decision_file"], str(decision_file))
            self.assertFalse(payload["decision_file_exists"])
            report_text = report.read_text(encoding="utf-8-sig")
            self.assertIn("ZZZ", report_text)
            self.assertIn("decisions_template_status=ready", report_text)
            with decisions.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["ticker"], "ZZZ")
            self.assertEqual(rows[0]["review_decision"], "")
            self.assertEqual(rows[0]["official_source_checked"], "")
            self.assertEqual(rows[0]["decision_notes"], "")

    def test_weekly_bundle_generates_review_status_after_current_source_queue(self):
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )
        wrapper = (
            PROJECT_ROOT / "scripts" / "run_sp500_current_membership_source_review_status.ps1"
        ).read_text(encoding="utf-8-sig")

        self.assertIn("run_sp500_current_membership_source_review_status.ps1", bundle)
        self.assertIn("merge_sp500_current_membership_source_review_decisions.ps1", bundle)
        self.assertIn("apply_sp500_current_membership_source_review_decisions.ps1", bundle)
        self.assertLess(
            bundle.index("run_sp500_current_membership_sources.ps1"),
            bundle.index("merge_sp500_current_membership_source_review_decisions.ps1"),
        )
        self.assertLess(
            bundle.index("merge_sp500_current_membership_source_review_decisions.ps1"),
            bundle.index("apply_sp500_current_membership_source_review_decisions.ps1"),
        )
        self.assertLess(
            bundle.index("apply_sp500_current_membership_source_review_decisions.ps1"),
            bundle.index("run_sp500_current_membership_source_review_status.ps1"),
        )
        self.assertIn("DecisionsTemplate", wrapper)
        self.assertIn("Decisions", wrapper)
        self.assertIn("--decisions-template", wrapper)
        self.assertIn("--decisions", wrapper)
        self.assertIn("sp500_current_membership_source_review_decisions_template.csv", wrapper)
        self.assertIn("sp500_current_membership_source_review_decisions.csv", wrapper)


if __name__ == "__main__":
    unittest.main()
