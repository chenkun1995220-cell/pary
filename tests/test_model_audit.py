import csv
import tempfile
import unittest
from pathlib import Path

from model_audit import audit_model, run_model_audit


def evaluations(count, markets=("US", "CN")):
    rows = []
    for index in range(count):
        rows.append({
            "market": markets[index % len(markets)],
            "ticker": f"T{index}",
            "generated_date": f"2025-{(index % 12) + 1:02d}-{(index % 27) + 1:02d}",
            "checkpoint_weeks": "4",
            "evaluation_status": "evaluated",
            "direction_hit": "true" if index % 2 == 0 else "false",
            "actual_return": "0.10",
            "excess_return": "0.03",
            "target_error_pct": "0.20",
            "max_adverse_excursion": "-0.08",
            "valuation_confidence": "high",
            "model_version": "valuation_trend_v1",
        })
    return rows


class ModelAuditTests(unittest.TestCase):
    def test_less_than_thirty_mature_samples_only_accumulates(self):
        result = audit_model(evaluations(29))
        self.assertEqual(result["audit_status"], "sample_accumulating")
        self.assertEqual(result["proposals"], [])

    def test_less_than_fifteen_validation_samples_blocks_proposals(self):
        result = audit_model(evaluations(49))
        self.assertEqual(result["audit_status"], "validation_sample_insufficient")
        self.assertEqual(result["proposals"], [])

    def test_two_markets_and_fifteen_validation_samples_create_analysis_candidates(self):
        result = audit_model(evaluations(50))
        self.assertEqual(result["audit_status"], "shadow_analysis_ready")
        self.assertGreater(len(result["proposals"]), 0)
        self.assertTrue(all(row["status"] == "analysis_candidate" for row in result["proposals"]))

    def test_single_market_never_creates_review_candidate(self):
        result = audit_model(evaluations(50, markets=("US",)))
        self.assertNotEqual(result["audit_status"], "shadow_analysis_ready")
        self.assertEqual(result["proposals"], [])

    def test_run_writes_accumulating_report_and_empty_proposals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); eval_path = root / "evaluations.csv"; tracking = root / "tracking.csv"
            with eval_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(evaluations(2)[0])); writer.writeheader(); writer.writerows(evaluations(2))
            tracking.write_text("ticker,evaluation_status\nT0,tracking\n", encoding="utf-8-sig")

            result = run_model_audit(eval_path, tracking, root / "out", "2026-06-21")

            self.assertEqual(result["audit_status"], "sample_accumulating")
            self.assertIn("样本积累中", (root / "out" / "model_audit.md").read_text(encoding="utf-8-sig"))
            with (root / "out" / "shadow_model_proposals.csv").open(encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(list(csv.DictReader(handle)), [])


if __name__ == "__main__":
    unittest.main()
