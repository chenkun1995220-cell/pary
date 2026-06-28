import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


class ManualReviewDecisionTests(unittest.TestCase):
    def test_merges_template_into_decisions_and_skips_pending_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            decisions = root / "outputs" / "automation" / "manual_review_decisions.csv"
            template = root / "outputs" / "automation" / "manual_review_decisions_template.csv"

            write_csv(
                decisions,
                [
                    {
                        "as_of_date": "2026-06-21",
                        "market": "A股周筛",
                        "review_type": "估值口径",
                        "ticker": "300122.SZ",
                        "company": "智飞生物",
                        "decision_status": "needs_more_data",
                        "decision_note": "旧备注",
                        "reviewer": "ck",
                        "decided_at": "2026-06-21",
                    }
                ],
            )
            write_csv(
                template,
                [
                    {
                        "as_of_date": "2026-06-28",
                        "market": "A股周筛",
                        "review_type": "估值口径",
                        "ticker": "300122.SZ",
                        "company": "智飞生物",
                        "review_detail": "loss_making_or_negative_pe；pe=-17.54",
                        "decision_status": "accepted",
                        "decision_note": "现金流复核通过",
                        "reviewer": "ck",
                        "decided_at": "2026-06-28",
                    },
                    {
                        "as_of_date": "2026-06-28",
                        "market": "港股周筛",
                        "review_type": "风险提示",
                        "ticker": "01548.HK",
                        "company": "GENSCRIPT BIO",
                        "review_detail": "估值置信度低",
                        "decision_status": "rejected",
                        "decision_note": "风险过高，本周剔除观察",
                        "reviewer": "ck",
                        "decided_at": "2026-06-28",
                    },
                    {
                        "as_of_date": "2026-06-28",
                        "market": "港股周筛",
                        "review_type": "估值口径",
                        "ticker": "00017.HK",
                        "company": "NEW WORLD DEV",
                        "review_detail": "loss_making_or_negative_pe；pe=-1.27",
                        "decision_status": "pending",
                        "decision_note": "",
                        "reviewer": "",
                        "decided_at": "",
                    },
                ],
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "manual_review_decisions.py"),
                    "--template",
                    str(template),
                    "--decisions",
                    str(decisions),
                ],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("merged=2", result.stdout)
            self.assertIn("skipped_pending=1", result.stdout)
            with decisions.open("r", newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["ticker"], "300122.SZ")
            self.assertEqual(rows[0]["decision_status"], "accepted")
            self.assertEqual(rows[0]["decision_note"], "现金流复核通过")
            self.assertEqual(rows[1]["ticker"], "01548.HK")
            self.assertEqual(rows[1]["decision_status"], "rejected")

    def test_powershell_wrapper_static_contract(self):
        script = (PROJECT_ROOT / "scripts" / "merge_manual_review_decisions.ps1").read_text(encoding="utf-8-sig")

        self.assertIn("manual_review_decisions.py", script)
        self.assertIn("manual_review_decisions_template.csv", script)
        self.assertIn("manual_review_decisions.csv", script)
        self.assertIn("--template", script)
        self.assertIn("--decisions", script)
        self.assertIn("codex-primary-runtime", script)

    def test_powershell_wrapper_can_merge_external_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            decisions = root / "outputs" / "automation" / "manual_review_decisions.csv"
            template = root / "outputs" / "automation" / "manual_review_decisions_template.csv"
            write_csv(
                decisions,
                [
                    {
                        "as_of_date": "2026-06-21",
                        "market": "A股周筛",
                        "review_type": "估值口径",
                        "ticker": "300122.SZ",
                        "company": "智飞生物",
                        "decision_status": "needs_more_data",
                        "decision_note": "旧备注",
                        "reviewer": "ck",
                        "decided_at": "2026-06-21",
                    }
                ],
            )
            write_csv(
                template,
                [
                    {
                        "as_of_date": "2026-06-28",
                        "market": "A股周筛",
                        "review_type": "估值口径",
                        "ticker": "300122.SZ",
                        "company": "智飞生物",
                        "review_detail": "loss_making_or_negative_pe；pe=-17.54",
                        "decision_status": "accepted",
                        "decision_note": "现金流复核通过",
                        "reviewer": "ck",
                        "decided_at": "2026-06-28",
                    }
                ],
            )

            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(PROJECT_ROOT / "scripts" / "merge_manual_review_decisions.ps1"),
                    "-ProjectRoot",
                    str(root),
                ],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("merged=1", result.stdout)
            with decisions.open("r", newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["decision_status"], "accepted")


if __name__ == "__main__":
    unittest.main()
