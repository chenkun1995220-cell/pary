import csv
import tempfile
import unittest
from pathlib import Path

from data_health_history import run_data_health_history


def write_csv(path, fieldnames, rows):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class DataHealthHistoryTests(unittest.TestCase):
    def test_appends_snapshot_and_reports_delta_from_previous_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_root = root / "us_universe"
            output_root.mkdir()
            history_path = output_root / "data_health_history.csv"
            report_path = output_root / "data_health_history.md"

            write_csv(
                output_root / "quote_gaps.csv",
                ["ticker", "status"],
                [
                    {"ticker": "AAA", "status": "ready"},
                    {"ticker": "BBB", "status": "manual_override_applied"},
                    {"ticker": "CCC", "status": "missing"},
                ],
            )
            write_csv(
                output_root / "data_quality_issues.csv",
                ["severity", "issue_code", "ticker"],
                [
                    {"severity": "警告", "issue_code": "percentage_unit_suspect", "ticker": "AAA"},
                    {"severity": "阻断", "issue_code": "missing_required_field", "ticker": "DDD"},
                ],
            )
            write_csv(
                output_root / "share_override_audit.csv",
                ["ticker", "status"],
                [
                    {"ticker": "BRK-B", "status": "current"},
                    {"ticker": "ERIE", "status": "review"},
                ],
            )
            write_csv(
                output_root / "candidate_pool.csv",
                ["ticker"],
                [{"ticker": "AAA"}, {"ticker": "BBB"}],
            )
            write_csv(
                history_path,
                [
                    "run_time",
                    "universe_count",
                    "candidate_count",
                    "quote_ready",
                    "quote_total",
                    "quote_coverage_pct",
                    "data_quality_total",
                    "data_quality_blocked",
                    "data_quality_warnings",
                    "affected_candidate_count",
                    "share_override_total",
                    "share_override_review",
                ],
                [
                    {
                        "run_time": "2026-06-20 14:05:00",
                        "universe_count": "3",
                        "candidate_count": "2",
                        "quote_ready": "2",
                        "quote_total": "3",
                        "quote_coverage_pct": "66.67",
                        "data_quality_total": "5",
                        "data_quality_blocked": "1",
                        "data_quality_warnings": "4",
                        "affected_candidate_count": "2",
                        "share_override_total": "2",
                        "share_override_review": "1",
                    }
                ],
            )

            result = run_data_health_history(
                output_root,
                history_path,
                report_path,
                run_time="2026-06-27 14:05:00",
            )

            with history_path.open("r", encoding="utf-8-sig", newline="") as handle:
                history_rows = list(csv.DictReader(handle))
            report = report_path.read_text(encoding="utf-8-sig")

            self.assertEqual(result["data_quality_total"], 2)
            self.assertEqual(len(history_rows), 2)
            self.assertEqual(history_rows[-1]["quote_coverage_pct"], "66.67")
            self.assertEqual(history_rows[-1]["affected_candidate_count"], "1")
            self.assertIn("# 数据健康历史", report)
            self.assertIn("- 数据质量问题：2（较上次 -3）", report)
            self.assertIn("- 受影响候选：1（较上次 -1）", report)


if __name__ == "__main__":
    unittest.main()
