import csv
import tempfile
import unittest
from pathlib import Path

from shadow_backtest import rolling_windows, run_shadow_backtest, summarize_shadow_windows


def evaluation_rows(weeks, markets=("US", "CN"), industries=("Technology", "Financials")):
    rows = []
    for index, week in enumerate(weeks):
        rows.append(
            {
                "market": markets[index % len(markets)],
                "industry": industries[index % len(industries)],
                "ticker": f"T{index:03d}",
                "generated_date": week,
                "checkpoint_weeks": "52",
                "evaluation_status": "evaluated",
                "direction_hit": "true",
                "actual_return": "0.10",
                "excess_return": "0.03",
                "target_error_pct": "0.12",
                "max_adverse_excursion": "-0.08",
                "model_version": "valuation_trend_v1",
            }
        )
    return rows


class ShadowBacktestTests(unittest.TestCase):
    def test_rolling_windows_use_time_order(self):
        weeks = [f"W{i:03d}" for i in range(156)]
        windows = rolling_windows(weeks, train_size=104, validation_size=26, step=13)

        self.assertEqual(windows[0], (weeks[:104], weeks[104:130]))
        self.assertEqual(windows[1], (weeks[13:117], weeks[117:143]))
        self.assertEqual(len(windows), 3)

    def test_summary_requires_multiple_validation_windows_for_review_candidate(self):
        weeks = [f"2024-W{i:03d}" for i in range(156)]
        result = summarize_shadow_windows(evaluation_rows(weeks))

        formal = [row for row in result if row["proposal_name"] == "formal_model"]
        candidates = [row for row in result if row["proposal_name"] != "formal_model"]

        self.assertEqual(len(formal), 3)
        self.assertTrue(all(row["status"] == "formal_baseline" for row in formal))
        self.assertTrue(any(row["status"] == "review_candidate" for row in candidates))
        self.assertTrue(all(int(row["validation_samples"]) >= 26 for row in result))
        self.assertTrue(all(row["market_count"] == 2 for row in result))
        self.assertTrue(all(row["industry_count"] == 2 for row in result))

    def test_review_candidate_requires_two_valid_validation_windows(self):
        weeks = [f"2024-W{i:03d}" for i in range(156)]
        rows = evaluation_rows(weeks)
        for row in rows:
            if row["generated_date"] >= "2024-W117":
                row["market"] = "US"

        result = summarize_shadow_windows(rows)
        candidates = [row for row in result if row["proposal_name"] != "formal_model"]

        self.assertTrue(candidates)
        self.assertFalse(any(row["status"] == "review_candidate" for row in candidates))
        self.assertTrue(any(row["rejection_reason"] == "validation_windows_insufficient" for row in candidates))

    def test_single_market_shadow_candidate_is_rejected(self):
        weeks = [f"2024-W{i:03d}" for i in range(156)]
        result = summarize_shadow_windows(evaluation_rows(weeks, markets=("US",)))
        candidates = [row for row in result if row["proposal_name"] != "formal_model"]

        self.assertTrue(candidates)
        self.assertTrue(all(row["status"] == "rejected" for row in candidates))
        self.assertTrue(all(row["rejection_reason"] == "market_or_industry_diversity_insufficient" for row in candidates))

    def test_worse_drawdown_shadow_candidate_is_rejected(self):
        weeks = [f"2024-W{i:03d}" for i in range(156)]
        rows = evaluation_rows(weeks)
        result = summarize_shadow_windows(
            rows,
            proposals=[
                {
                    "proposal_name": "higher_return_higher_risk",
                    "parameter": "direction_threshold",
                    "candidate_value": "0.03",
                    "excess_return_delta": "0.02",
                    "adverse_excursion_delta": "-0.10",
                }
            ],
        )
        candidate = [row for row in result if row["proposal_name"] == "higher_return_higher_risk"][0]

        self.assertEqual(candidate["status"], "rejected")
        self.assertEqual(candidate["rejection_reason"], "risk_worse")

    def test_run_shadow_backtest_writes_comparison_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evaluations_path = root / "backtest_evaluations.csv"
            rows = evaluation_rows([f"2024-W{i:03d}" for i in range(156)])
            with evaluations_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)

            result = run_shadow_backtest(evaluations_path, root / "out")

            self.assertGreater(result["comparison_rows"], 0)
            self.assertTrue((root / "out" / "model_comparison.csv").exists())
            report = (root / "out" / "backtest_report.md").read_text(encoding="utf-8-sig")
            self.assertIn("样本或证据积累中", report)
            self.assertIn("不得自动升级正式模型", report)


if __name__ == "__main__":
    unittest.main()
