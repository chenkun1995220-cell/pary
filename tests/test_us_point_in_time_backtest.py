import csv
import json
import tempfile
import unittest
from pathlib import Path

from tests.test_sec_financial_metrics import metric_facts
from us_point_in_time_backtest import (
    _load_company_facts,
    _PriceTimeline,
    _select_replay_weeks,
    _write_leakage_audit_report,
    run_point_in_time_backtest,
)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_empty_csv(path, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()


class UsPointInTimeBacktestTests(unittest.TestCase):
    def test_price_timeline_returns_sorted_as_of_rows(self):
        rows = [
            {"ticker": "AAPL", "date": "2025-01-03", "close": "3"},
            {"ticker": "AAPL", "date": "bad-date", "close": "bad"},
            {"ticker": "MSFT", "date": "2025-01-01", "close": "1"},
            {"ticker": "AAPL", "date": "2025-01-02", "close": "2"},
        ]

        timeline = _PriceTimeline(rows)

        self.assertEqual(
            [row["close"] for row in timeline.as_of("2025-01-02")],
            ["1", "2"],
        )
        self.assertEqual(
            [row["close"] for row in timeline.as_of("2025-01-03")],
            ["1", "2", "3"],
        )

    def test_company_facts_loader_is_lazy_and_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / "CIK0000000001.json").write_text(
                json.dumps({"entityName": "One", "facts": {}}),
                encoding="utf-8",
            )
            (cache / "CIK0000000002.json").write_text(
                json.dumps({"entityName": "Two", "facts": {}}),
                encoding="utf-8",
            )
            (cache / "CIK0000000003.json").write_text("{not-json", encoding="utf-8")

            facts = _load_company_facts(
                cache,
                [{"cik": "1"}, {"cik": "2"}, {"cik": "3"}],
                max_entries=1,
            )

            self.assertEqual(facts.get("1")["entityName"], "One")
            self.assertLessEqual(len(facts._cache), 1)
            self.assertEqual(facts.get("0000000002")["entityName"], "Two")
            self.assertLessEqual(len(facts._cache), 1)
            with self.assertRaises(json.JSONDecodeError):
                facts.get("3")

    def test_default_pilot_selects_latest_weeks(self):
        weeks = ["2024-01-05", "2024-01-12", "2024-01-19"]

        self.assertEqual(_select_replay_weeks(weeks, pilot_weeks=2), ["2024-01-12", "2024-01-19"])
        self.assertEqual(
            _select_replay_weeks(weeks, pilot_weeks=2, pilot_window="earliest"),
            ["2024-01-05", "2024-01-12"],
        )
        self.assertEqual(_select_replay_weeks(weeks, pilot_weeks=2, full_run=True), weeks)

    def test_leakage_audit_report_limits_markdown_detail_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = [
                {
                    "record_type": "financial",
                    "source": "company_facts_by_cik",
                    "market": "US",
                    "ticker": f"T{index:04d}",
                    "company_name": "",
                    "industry": "",
                    "cik": "",
                    "available_at": "2025-01-15",
                    "generated_date": "2024-06-01",
                    "severity": "audit",
                    "reason": "future_data_excluded",
                }
                for index in range(1005)
            ]

            _write_leakage_audit_report(root, rows)

            report = (root / "data_leakage_audit.md").read_text(encoding="utf-8-sig")
            self.assertIn("Markdown 明细行：1000/1005", report)
            self.assertIn("T0999", report)
            self.assertNotIn("T1000", report)

    def test_rejects_empty_prepared_inputs_before_reporting_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            membership = root / "historical_membership.csv"
            facts_cache = root / "facts"
            price_history = root / "price_history.csv"
            benchmark = root / "benchmark_history.csv"
            output = root / "out"

            write_empty_csv(membership, ["week", "market", "ticker", "cik"])
            write_empty_csv(price_history, ["market", "ticker", "date", "adjusted_close", "available_at"])
            write_empty_csv(benchmark, ["market", "ticker", "date", "adjusted_close", "available_at"])
            facts_cache.mkdir()

            with self.assertRaisesRegex(ValueError, "Prepared backtest inputs are required"):
                run_point_in_time_backtest(
                    membership,
                    facts_cache,
                    price_history,
                    benchmark,
                    output,
                    pilot_weeks=2,
                    config_digest="digest-test",
                )

    def test_runs_pilot_weeks_and_writes_manifest_checkpoint_forecasts_and_evaluations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            membership = root / "historical_membership.csv"
            facts_cache = root / "facts"
            price_history = root / "price_history.csv"
            benchmark = root / "benchmark_history.csv"
            output = root / "out"
            weeks = ["2025-07-25", "2025-08-01"]

            write_csv(
                membership,
                [
                    row
                    for week in weeks
                    for row in [
                        {
                            "week": week,
                            "market": "US",
                            "ticker": "AAPL",
                            "cik": "320193",
                            "company_name": "Apple Inc.",
                            "industry": "Technology",
                            "membership_evidence": "verified",
                            "available_at": "2025-07-20",
                            "market_cap": "100",
                            "enterprise_value": "110",
                            "net_assets": "50",
                            "revenue_ttm": "100",
                            "net_income_ttm": "20",
                            "ebitda": "20",
                            "free_cash_flow": "10",
                            "roe": "0.20",
                            "roic": "0.15",
                            "gross_margin": "0.50",
                            "debt_to_assets": "0.30",
                            "net_debt_to_ebitda": "0.50",
                            "current_ratio": "2.0",
                            "revenue_cagr_3y": "0.20",
                            "net_income_cagr_3y": "0.20",
                            "audit_opinion": "standard",
                            "risk_flag": "",
                        },
                        {
                            "week": week,
                            "market": "US",
                            "ticker": "MSFT",
                            "cik": "789019",
                            "company_name": "Microsoft Corp.",
                            "industry": "Technology",
                            "membership_evidence": "secondary",
                            "available_at": "2025-07-20",
                            "market_cap": "10000",
                            "enterprise_value": "12000",
                            "net_assets": "20",
                            "revenue_ttm": "100",
                            "net_income_ttm": "5",
                            "ebitda": "5",
                            "free_cash_flow": "1",
                            "roe": "0.02",
                            "roic": "0.02",
                            "gross_margin": "0.20",
                            "debt_to_assets": "0.80",
                            "net_debt_to_ebitda": "3.0",
                            "current_ratio": "0.8",
                            "revenue_cagr_3y": "0.01",
                            "net_income_cagr_3y": "0.01",
                            "audit_opinion": "standard",
                            "risk_flag": "重大",
                        },
                    ]
                ],
            )
            facts_cache.mkdir()
            (facts_cache / "CIK0000320193.json").write_text(json.dumps(metric_facts()), encoding="utf-8")
            (facts_cache / "CIK0000789019.json").write_text(json.dumps(metric_facts()), encoding="utf-8")
            write_csv(
                price_history,
                [
                    {"market": "US", "ticker": "AAPL", "date": "2025-07-24", "close": "10", "adjusted_close": "10", "data_status": "ready", "available_at": "2025-07-24"},
                    {"market": "US", "ticker": "MSFT", "date": "2025-07-24", "close": "100", "adjusted_close": "100", "data_status": "ready", "available_at": "2025-07-24"},
                    {"market": "US", "ticker": "AAPL", "date": "2025-08-01", "close": "11", "adjusted_close": "11", "data_status": "ready", "available_at": "2025-08-01"},
                    {"market": "US", "ticker": "MSFT", "date": "2025-08-01", "close": "101", "adjusted_close": "101", "data_status": "ready", "available_at": "2025-08-01"},
                    {"market": "US", "ticker": "AAPL", "date": "2025-08-22", "close": "12", "adjusted_close": "12", "data_status": "ready", "available_at": "2025-08-22"},
                    {"market": "US", "ticker": "AAPL", "date": "2025-10-24", "close": "13", "adjusted_close": "13", "data_status": "ready", "available_at": "2025-10-24"},
                    {"market": "US", "ticker": "AAPL", "date": "2026-01-23", "close": "14", "adjusted_close": "14", "data_status": "ready", "available_at": "2026-01-23"},
                    {"market": "US", "ticker": "AAPL", "date": "2026-07-24", "close": "15", "adjusted_close": "15", "data_status": "ready", "available_at": "2026-07-24"},
                ],
            )
            write_csv(
                benchmark,
                [
                    {"market": "US", "ticker": "^GSPC", "date": "2025-07-24", "close": "100", "adjusted_close": "100", "data_status": "ready", "available_at": "2025-07-24"},
                    {"market": "US", "ticker": "^GSPC", "date": "2025-08-01", "close": "101", "adjusted_close": "101", "data_status": "ready", "available_at": "2025-08-01"},
                    {"market": "US", "ticker": "^GSPC", "date": "2025-08-22", "close": "102", "adjusted_close": "102", "data_status": "ready", "available_at": "2025-08-22"},
                    {"market": "US", "ticker": "^GSPC", "date": "2025-10-24", "close": "103", "adjusted_close": "103", "data_status": "ready", "available_at": "2025-10-24"},
                    {"market": "US", "ticker": "^GSPC", "date": "2026-01-23", "close": "104", "adjusted_close": "104", "data_status": "ready", "available_at": "2026-01-23"},
                    {"market": "US", "ticker": "^GSPC", "date": "2026-07-24", "close": "105", "adjusted_close": "105", "data_status": "ready", "available_at": "2026-07-24"},
                ],
            )

            result = run_point_in_time_backtest(
                membership,
                facts_cache,
                price_history,
                benchmark,
                output,
                pilot_weeks=2,
                config_digest="digest-test",
            )

            self.assertEqual(result["weeks_completed"], 2)
            self.assertEqual(result["membership_evidence_summary"]["total_rows"], 4)
            self.assertEqual(result["membership_evidence_summary"]["verified_rows"], 2)
            self.assertEqual(result["membership_evidence_summary"]["secondary_rows"], 2)
            self.assertAlmostEqual(result["membership_evidence_summary"]["verified_ratio"], 0.5)
            self.assertTrue((output / "replay_manifest.csv").exists())
            self.assertTrue((output / "checkpoint.json").exists())
            self.assertTrue((output / "backtest_forecasts.csv").exists())
            self.assertTrue((output / "backtest_evaluations.csv").exists())
            with (output / "replay_manifest.csv").open(encoding="utf-8-sig", newline="") as handle:
                manifest = list(csv.DictReader(handle))
            with (output / "backtest_evaluations.csv").open(encoding="utf-8-sig", newline="") as handle:
                evaluations = list(csv.DictReader(handle))
            with (output / "data_leakage_audit.csv").open(encoding="utf-8-sig", newline="") as handle:
                audit_rows = list(csv.DictReader(handle))
            backtest_report = (output / "backtest_report.md").read_text(encoding="utf-8-sig")
            leakage_report = (output / "data_leakage_audit.md").read_text(encoding="utf-8-sig")
            self.assertEqual([row["status"] for row in manifest], ["completed", "completed"])
            self.assertEqual({row["checkpoint_weeks"] for row in evaluations}, {"1", "4", "12", "26", "52"})
            self.assertEqual({row["generated_date"] for row in audit_rows}, {"2025-07-25", "2025-08-01"})
            self.assertIn("\u7f8e\u80a1\u4e25\u683c\u65f6\u70b9\u56de\u6d4b\u62a5\u544a", backtest_report)
            self.assertIn("成员证据覆盖", backtest_report)
            self.assertIn("已验证证据：2/4 (50.0%)", backtest_report)
            self.assertIn("弱证据行：2", backtest_report)
            self.assertIn("最后一周筛选诊断", backtest_report)
            self.assertIn("进入候选池：1", backtest_report)
            self.assertIn("重大风险标记排除：1", backtest_report)
            self.assertIn("\u6570\u636e\u6cc4\u6f0f\u5ba1\u8ba1", leakage_report)


if __name__ == "__main__":
    unittest.main()
