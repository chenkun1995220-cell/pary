import csv
import json
import tempfile
import unittest
from pathlib import Path

from regional_data_health_history import run_regional_data_health_history


def write_csv(path, fieldnames, rows):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class RegionalDataHealthHistoryTests(unittest.TestCase):
    def test_appends_snapshot_and_reports_regional_health_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_root = root / "cn_universe"
            cache_dir = root / "cache"
            output_root.mkdir()
            cache_dir.mkdir()
            history_path = output_root / "data_health_history.csv"
            report_path = output_root / "data_health_history.md"

            write_csv(
                output_root / "market_snapshot.csv",
                ["ticker", "data_quality_status"],
                [
                    {"ticker": "AAA", "data_quality_status": "ready"},
                    {"ticker": "BBB", "data_quality_status": "stale"},
                    {"ticker": "CCC", "data_quality_status": "ready"},
                ],
            )
            write_csv(
                output_root / "financial_snapshot.csv",
                ["ticker", "financial_data_status"],
                [
                    {"ticker": "AAA", "financial_data_status": "ready"},
                    {"ticker": "BBB", "financial_data_status": "missing"},
                    {"ticker": "CCC", "financial_data_status": "ready"},
                ],
            )
            write_csv(
                output_root / "candidate_pool.csv",
                ["ticker"],
                [{"ticker": "AAA"}, {"ticker": "CCC"}],
            )
            write_csv(
                output_root / "valuation_targets.csv",
                ["ticker", "valuation_status"],
                [
                    {"ticker": "AAA", "valuation_status": "ready"},
                    {"ticker": "CCC", "valuation_status": "blocked"},
                ],
            )
            write_csv(
                output_root / "tracking_snapshot.csv",
                ["ticker", "evaluation_status"],
                [
                    {"ticker": "AAA", "evaluation_status": "tracking"},
                    {"ticker": "CCC", "evaluation_status": "mature"},
                ],
            )
            (cache_dir / "refresh_metadata.json").write_text(
                json.dumps({"status": "online"}), encoding="utf-8"
            )
            write_csv(
                history_path,
                [
                    "run_time",
                    "market",
                    "universe",
                    "refresh_status",
                    "company_count",
                    "quote_ready",
                    "quote_total",
                    "quote_coverage_pct",
                    "financial_ready",
                    "financial_total",
                    "financial_coverage_pct",
                    "candidate_count",
                    "valuation_ready",
                    "valuation_total",
                    "tracking_count",
                    "mature_evaluation_count",
                ],
                [
                    {
                        "run_time": "2026-06-20 14:05:00",
                        "market": "CN",
                        "universe": "CSI 300",
                        "refresh_status": "cache_fallback",
                        "company_count": "3",
                        "quote_ready": "1",
                        "quote_total": "3",
                        "quote_coverage_pct": "33.33",
                        "financial_ready": "1",
                        "financial_total": "3",
                        "financial_coverage_pct": "33.33",
                        "candidate_count": "1",
                        "valuation_ready": "1",
                        "valuation_total": "1",
                        "tracking_count": "1",
                        "mature_evaluation_count": "0",
                    }
                ],
            )

            result = run_regional_data_health_history(
                market="CN",
                universe_label="CSI 300",
                output_root=output_root,
                cache_dir=cache_dir,
                history_path=history_path,
                report_path=report_path,
                run_time="2026-06-27 14:05:00",
            )

            with history_path.open("r", encoding="utf-8-sig", newline="") as handle:
                history_rows = list(csv.DictReader(handle))
            report = report_path.read_text(encoding="utf-8-sig")

            self.assertEqual(result["quote_ready"], 2)
            self.assertEqual(result["financial_ready"], 2)
            self.assertEqual(result["candidate_count"], 2)
            self.assertEqual(result["valuation_ready"], 1)
            self.assertEqual(result["mature_evaluation_count"], 1)
            self.assertEqual(len(history_rows), 2)
            self.assertEqual(history_rows[-1]["quote_coverage_pct"], "66.67")
            self.assertEqual(history_rows[-1]["financial_coverage_pct"], "66.67")
            self.assertIn("# 区域数据健康历史", report)
            self.assertIn("- 市场：CN", report)
            self.assertIn("- 股票池：CSI 300", report)
            self.assertIn("- 刷新状态：online", report)
            self.assertIn("- 候选数量：2（较上次 +1）", report)
            self.assertIn("- 成熟评价样本：1（较上次 +1）", report)
            self.assertIn("不代表模型参数已经自动调整", report)


if __name__ == "__main__":
    unittest.main()
