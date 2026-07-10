import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from automation_self_analysis import run_self_analysis


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig")


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class AutomationSelfAnalysisTests(unittest.TestCase):
    def test_automation_check_payload_exposes_sp500_external_input_blocker(self):
        from automation_self_analysis import _automation_check_payload

        payload = _automation_check_payload(
            {
                "as_of_date": "2026-07-04",
                "automation_status": "manual_review_needed",
                "automation_recommended_action": "review_backtest_evidence",
                "automation_priority_actions": ["review_backtest_evidence"],
                "market_count": 3,
                "markets": [],
                "sp500_current_source_inbox_external_input_required": True,
                "sp500_current_source_inbox_blocking_input": (
                    "inputs/sp500_current_membership/official_constituents.csv"
                ),
                "sp500_current_source_inbox_blocking_reason": "official_constituents_csv_missing",
                "sp500_current_source_inbox_dry_run_command": (
                    "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                    "scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> "
                    "-DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv"
                ),
                "sp500_current_source_inbox_import_command": (
                    "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                    "scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> "
                    "-SourceFileInbox inputs/sp500_current_membership/official_constituents.csv"
                ),
            },
            {"status": "valid", "markets_ready_count": 3, "errors": []},
        )

        self.assertEqual(payload["external_input_blocker_count"], 1)
        self.assertEqual(
            payload["external_input_blockers"][0]["action_code"],
            "provide_official_constituents_csv",
        )
        self.assertEqual(
            payload["external_input_blockers"][0]["blocking_reason"],
            "official_constituents_csv_missing",
        )
        self.assertIn(
            "official_constituents.csv",
            payload["external_input_blockers"][0]["blocking_input"],
        )
        self.assertEqual(
            payload["external_input_blockers"][0]["next_action"],
            "place_official_constituents_csv",
        )

    def test_self_analysis_manifest_reads_sp500_inbox_external_input_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for universe, title in (
                ("us_universe", "US Weekly Screening Run Summary"),
                ("cn_universe", "CN Weekly Data Summary"),
                ("hk_universe", "HK Weekly Data Summary"),
            ):
                write_text(root / "outputs" / universe / "latest_run_summary.md", f"# {title}\n")
                write_text(root / "outputs" / universe / "model_audit.md", "- audit status: sample_accumulating\n")
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")
            write_text(
                root / "outputs" / "automation" / "latest_sp500_current_membership_source_inbox_status.json",
                json.dumps(
                    {
                        "status_schema": "sp500_current_membership_source_inbox_status",
                        "status_version": 1,
                        "external_input_required": True,
                        "blocking_input": "inputs/sp500_current_membership/official_constituents.csv",
                        "blocking_reason": "official_constituents_csv_missing",
                        "source_file_inbox_size_bytes": 0,
                        "source_file_inbox_sha256": "",
                        "source_file_inbox_modified_at": "",
                        "source_file_inbox_dry_run_command": (
                            "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                            "scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> "
                            "-DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv"
                        ),
                        "source_file_inbox_next_command": (
                            "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                            "scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> "
                            "-SourceFileInbox inputs/sp500_current_membership/official_constituents.csv"
                        ),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )

            result = run_self_analysis(root, as_of_date="2026-07-04")
            manifest = json.loads(Path(result["manifest_output"]).read_text(encoding="utf-8-sig"))
            check = json.loads(Path(result["automation_check_output"]).read_text(encoding="utf-8-sig"))

            self.assertTrue(manifest["sp500_current_source_inbox_external_input_required"])
            self.assertEqual(
                manifest["sp500_current_source_inbox_blocking_reason"],
                "official_constituents_csv_missing",
            )
            self.assertIn(
                "official_constituents.csv",
                manifest["sp500_current_source_inbox_blocking_input"],
            )
            self.assertEqual(check["external_input_blocker_count"], 1)
            self.assertEqual(
                check["external_input_blockers"][0]["action_code"],
                "provide_official_constituents_csv",
            )

    def test_prefers_us_universe_summary_over_legacy_automation_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(
                root / "outputs" / "automation" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# Legacy US Weekly Screening Run Summary",
                        "- Candidate count: 1",
                        "- Candidate tickers: OLD",
                        "- Model audit: outputs/us_universe/model_audit.md",
                    ]
                ),
            )
            write_text(
                root / "outputs" / "us_universe" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# US Weekly Screening Run Summary",
                        "- Candidate count: 3",
                        "- Candidate tickers: NEW1, NEW2, NEW3",
                        "- Model audit: outputs/us_universe/model_audit.md",
                        "- Investment summary: outputs/us_universe/latest_investment_summary.md",
                    ]
                ),
            )
            write_text(root / "outputs" / "us_universe" / "model_audit.md", "- 审计状态：sample_accumulating\n")
            write_text(root / "outputs" / "cn_universe" / "latest_run_summary.md", "# CN Weekly Data Summary\n")
            write_text(root / "outputs" / "hk_universe" / "latest_run_summary.md", "# HK Weekly Data Summary\n")
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")

            result = run_self_analysis(root)

            self.assertEqual(result["markets"][0]["candidate_count"], "3")
            self.assertIn("outputs\\us_universe\\latest_run_summary.md", result["markets"][0]["summary_path"])

    def test_legacy_us_summary_prefers_new_universe_investment_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(
                root / "outputs" / "automation" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# Legacy US Weekly Screening Run Summary",
                        "- Candidate count: 1",
                        "- Candidate tickers: OLD",
                        "- Model audit: outputs/us_universe/model_audit.md",
                        "- Investment summary: outputs/automation/latest_investment_summary.md",
                    ]
                ),
            )
            write_text(root / "outputs" / "us_universe" / "model_audit.md", "- 审计状态：sample_accumulating\n")
            write_text(root / "outputs" / "cn_universe" / "latest_run_summary.md", "# CN Weekly Data Summary\n")
            write_text(root / "outputs" / "hk_universe" / "latest_run_summary.md", "# HK Weekly Data Summary\n")
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")
            write_text(root / "outputs" / "automation" / "latest_investment_summary.md", "# old\n")
            write_text(
                root / "outputs" / "us_universe" / "latest_investment_summary.md",
                "\n".join(
                    [
                        "# 每周低估公司结论",
                        "## 候选结论质量检查",
                        "- 字段完整：1/1",
                    ]
                ),
            )

            result = run_self_analysis(root)

            self.assertIn("outputs\\us_universe\\latest_investment_summary.md", result["candidate_reviews"][0]["path"])
            self.assertEqual(result["candidate_reviews"][0]["field_complete"], "1/1")

    def test_candidate_review_ignores_explicit_no_risk_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(
                root / "outputs" / "us_universe" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# US Weekly Screening Run Summary",
                        "- Candidate count: 2",
                        "- Candidate tickers: SAFE, RISK",
                        "- Model audit: outputs/us_universe/model_audit.md",
                        "- Investment summary: outputs/us_universe/latest_investment_summary.md",
                    ]
                ),
            )
            write_text(root / "outputs" / "us_universe" / "model_audit.md", "- 审计状态：sample_accumulating\n")
            write_text(root / "outputs" / "cn_universe" / "latest_run_summary.md", "# CN Weekly Data Summary\n")
            write_text(root / "outputs" / "hk_universe" / "latest_run_summary.md", "# HK Weekly Data Summary\n")
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")
            write_text(
                root / "outputs" / "us_universe" / "latest_investment_summary.md",
                "\n".join(
                    [
                        "# 每周低估公司结论",
                        "## 候选风险说明",
                        "| 股票 | 公司 | 风险说明 |",
                        "|---|---|---|",
                        "| SAFE | Safe Co | 无 |",
                        "| RISK | Risk Co | 走势偏弱 |",
                        "## 候选结论质量检查",
                        "- 字段完整：2/2",
                    ]
                ),
            )

            result = run_self_analysis(root)

            self.assertEqual(len(result["candidate_reviews"][0]["risk_items"]), 1)
            self.assertEqual(result["candidate_reviews"][0]["risk_items"][0]["ticker"], "RISK")

    def test_data_health_includes_quote_gap_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(
                root / "outputs" / "cn_universe" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# CN Weekly Data Summary",
                        "- Candidate count: 1",
                        "- Candidate tickers: AAA",
                        "- Model audit: outputs/cn_universe/model_audit.md",
                        "- Data health history: outputs/cn_universe/data_health_history.csv",
                        "- Quote gaps: outputs/cn_universe/quote_gaps.csv",
                    ]
                ),
            )
            write_text(root / "outputs" / "us_universe" / "latest_run_summary.md", "# US Weekly Screening Run Summary\n")
            write_text(root / "outputs" / "hk_universe" / "latest_run_summary.md", "# HK Weekly Data Summary\n")
            write_text(root / "outputs" / "cn_universe" / "model_audit.md", "- 审计状态：sample_accumulating\n")
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")
            write_csv(
                root / "outputs" / "cn_universe" / "data_health_history.csv",
                [
                    "run_time",
                    "refresh_status",
                    "quote_coverage_pct",
                    "financial_coverage_pct",
                    "candidate_count",
                    "data_quality_blocked",
                    "affected_candidate_count",
                    "share_override_review",
                ],
                [
                    {
                        "run_time": "2026-06-27 14:05:00",
                        "refresh_status": "online",
                        "quote_coverage_pct": "92.67",
                        "financial_coverage_pct": "100.00",
                        "candidate_count": "1",
                        "data_quality_blocked": "0",
                        "affected_candidate_count": "0",
                        "share_override_review": "0",
                    }
                ],
            )
            write_csv(
                root / "outputs" / "cn_universe" / "quote_gaps.csv",
                ["ticker", "issue_type"],
                [
                    {"ticker": "AAA", "issue_type": "partial_quote"},
                    {"ticker": "BBB", "issue_type": "partial_quote"},
                ],
            )

            result = run_self_analysis(root)
            report = Path(result["output"]).read_text(encoding="utf-8-sig")

            self.assertEqual(result["health"][1]["quote_gap_count"], "2")
            self.assertIn("| A股周筛 | ready | online | 92.67% | 100.00% | 2 | 2 | 0 | 1 |", report)
            self.assertNotIn("数据健康需关注：A股周筛 行情缺口 2", report)
            self.assertIn("数据健康需关注：A股周筛 行情可重抓缺口 2", report)

    def test_self_analysis_scores_cross_market_data_quality(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            market_configs = [
                ("us_universe", "US Weekly Screening Run Summary", "US1", "online", "100.00", "100.00", "0", "0", "0"),
                ("cn_universe", "CN Weekly Data Summary", "CN1", "online", "92.00", "100.00", "0", "0", "0"),
                ("hk_universe", "HK Weekly Data Summary", "HK1", "cache_fallback", "84.00", "90.00", "1", "2", "0"),
            ]
            for folder, title, ticker, refresh, quote, financial, blocked, affected, override in market_configs:
                write_text(
                    root / "outputs" / folder / "latest_run_summary.md",
                    "\n".join(
                        [
                            f"# {title}",
                            "- Candidate count: 1",
                            f"- Candidate tickers: {ticker}",
                            f"- Model audit: outputs/{folder}/model_audit.md",
                            f"- Data health history: outputs/{folder}/data_health_history.csv",
                            f"- Quote gaps: outputs/{folder}/quote_gaps.csv",
                        ]
                    ),
                )
                write_text(root / "outputs" / folder / "model_audit.md", "- Audit status: sample_accumulating\n")
                write_csv(
                    root / "outputs" / folder / "data_health_history.csv",
                    [
                        "run_time",
                        "refresh_status",
                        "quote_coverage_pct",
                        "financial_coverage_pct",
                        "candidate_count",
                        "data_quality_blocked",
                        "affected_candidate_count",
                        "share_override_review",
                    ],
                    [
                        {
                            "run_time": "2026-06-28 14:05:00",
                            "refresh_status": refresh,
                            "quote_coverage_pct": quote,
                            "financial_coverage_pct": financial,
                            "candidate_count": "1",
                            "data_quality_blocked": blocked,
                            "affected_candidate_count": affected,
                            "share_override_review": override,
                        }
                    ],
                )
            write_csv(
                root / "outputs" / "cn_universe" / "quote_gaps.csv",
                ["ticker", "issue_type"],
                [
                    {"ticker": "CN1", "issue_type": "partial_quote"},
                    {"ticker": "CN2", "issue_type": "missing_quote"},
                ],
            )
            write_csv(
                root / "outputs" / "hk_universe" / "quote_gaps.csv",
                ["ticker", "remediation_type", "review_category"],
                [
                    {
                        "ticker": "HK1",
                        "remediation_type": "manual_financial_review",
                        "review_category": "special_industry_valuation_review",
                    }
                ],
            )
            write_csv(
                root / "outputs" / "automation" / "data_quality_score_history.csv",
                ["as_of_date", "market", "quality_score", "quality_status", "reasons"],
                [
                    {
                        "as_of_date": "2026-06-21",
                        "market": "港股周筛",
                        "quality_score": "62",
                        "quality_status": "needs_review",
                        "reasons": "quote_coverage:86.00%",
                    },
                    {
                        "as_of_date": "2026-06-21",
                        "market": "美股周筛",
                        "quality_score": "100",
                        "quality_status": "ready",
                        "reasons": "clear",
                    },
                    {
                        "as_of_date": "2026-06-28",
                        "market": "港股周筛",
                        "quality_score": "99",
                        "quality_status": "ready",
                        "reasons": "stale_same_day_row_should_be_replaced",
                    },
                ],
            )
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")

            result = run_self_analysis(root, as_of_date="2026-06-28")

            report = Path(result["output"]).read_text(encoding="utf-8-sig")
            manifest = json.loads(Path(result["manifest_output"]).read_text(encoding="utf-8-sig"))
            automation_check = json.loads(
                Path(result["automation_check_output"]).read_text(encoding="utf-8-sig")
            )
            quality = result["data_quality_summary"]

            self.assertIn("## 数据质量评分", report)
            self.assertEqual(quality["status"], "needs_review")
            self.assertEqual(quality["recommended_action"], "review_data_quality_score")
            self.assertEqual([item["quality_status"] for item in quality["markets"]], ["ready", "watch", "needs_review"])
            self.assertEqual(quality["markets"][0]["quality_score"], 100)
            self.assertLess(quality["markets"][2]["quality_score"], 70)
            self.assertIn("data_quality_summary", manifest)
            self.assertEqual(manifest["data_quality_status"], "needs_review")
            self.assertEqual(manifest["data_quality_score"], quality["average_score"])
            self.assertIn("review_data_quality_score", manifest["automation_priority_actions"])
            self.assertIn("data_quality_history", manifest)
            self.assertEqual(manifest["data_quality_history"]["status"], "manual_review_needed")
            self.assertIn("港股周筛", manifest["data_quality_history"]["repeated_needs_review_markets"])
            self.assertIn("review_data_quality_trend", manifest["automation_priority_actions"])
            self.assertIn("## 数据质量历史", report)
            with Path(result["data_quality_history_output"]).open(
                encoding="utf-8-sig",
                newline="",
            ) as handle:
                history_rows = list(csv.DictReader(handle))
            self.assertEqual(
                [row["market"] for row in history_rows if row["as_of_date"] == "2026-06-28"],
                ["美股周筛", "A股周筛", "港股周筛"],
            )
            self.assertEqual(automation_check["data_quality_status"], "needs_review")
            self.assertEqual(automation_check["data_quality_score"], quality["average_score"])

    def test_quote_gap_count_ignores_ready_status_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(
                root / "outputs" / "us_universe" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# US Weekly Screening Run Summary",
                        "- Candidate count: 1",
                        "- Candidate tickers: AAA",
                        "- Model audit: outputs/us_universe/model_audit.md",
                        "- Data health history: outputs/us_universe/data_health_history.csv",
                        "- Quote gaps: outputs/us_universe/quote_gaps.csv",
                    ]
                ),
            )
            write_text(root / "outputs" / "cn_universe" / "latest_run_summary.md", "# CN Weekly Data Summary\n")
            write_text(root / "outputs" / "hk_universe" / "latest_run_summary.md", "# HK Weekly Data Summary\n")
            write_text(root / "outputs" / "us_universe" / "model_audit.md", "- 审计状态：sample_accumulating\n")
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")
            write_csv(
                root / "outputs" / "us_universe" / "data_health_history.csv",
                ["run_time", "refresh_status", "quote_coverage_pct", "candidate_count"],
                [
                    {
                        "run_time": "2026-06-27 14:05:00",
                        "refresh_status": "n/a",
                        "quote_coverage_pct": "100.00",
                        "candidate_count": "1",
                    }
                ],
            )
            write_csv(
                root / "outputs" / "us_universe" / "quote_gaps.csv",
                ["ticker", "status", "missing_fields"],
                [
                    {"ticker": "AAA", "status": "ready", "missing_fields": ""},
                    {"ticker": "BBB", "status": "missing", "missing_fields": "price"},
                ],
            )

            result = run_self_analysis(root)

            self.assertEqual(result["health"][0]["quote_gap_count"], "1")

    def test_data_health_summarizes_quote_gap_remediation_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(
                root / "outputs" / "hk_universe" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# HK Weekly Data Summary",
                        "- Candidate count: 2",
                        "- Candidate tickers: AAA, BBB",
                        "- Model audit: outputs/hk_universe/model_audit.md",
                        "- Data health history: outputs/hk_universe/data_health_history.csv",
                        "- Quote gaps: outputs/hk_universe/quote_gaps.csv",
                    ]
                ),
            )
            write_text(root / "outputs" / "us_universe" / "latest_run_summary.md", "# US Weekly Screening Run Summary\n")
            write_text(root / "outputs" / "cn_universe" / "latest_run_summary.md", "# CN Weekly Data Summary\n")
            write_text(root / "outputs" / "hk_universe" / "model_audit.md", "- 审计状态：sample_accumulating\n")
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")
            write_csv(
                root / "outputs" / "hk_universe" / "data_health_history.csv",
                ["run_time", "refresh_status", "quote_coverage_pct", "financial_coverage_pct", "candidate_count"],
                [
                    {
                        "run_time": "2026-06-27 14:05:00",
                        "refresh_status": "online",
                        "quote_coverage_pct": "84.10",
                        "financial_coverage_pct": "99.69",
                        "candidate_count": "2",
                    }
                ],
            )
            write_csv(
                root / "outputs" / "hk_universe" / "quote_gaps.csv",
                ["ticker", "issue_type", "remediation_type"],
                [
                    {
                        "ticker": "AAA",
                        "issue_type": "partial_quote",
                        "remediation_type": "refetch_or_supplement_quote",
                    },
                    {
                        "ticker": "BBB",
                        "issue_type": "non_positive_metric",
                        "remediation_type": "manual_financial_review",
                    },
                ],
            )

            result = run_self_analysis(root)
            report = Path(result["output"]).read_text(encoding="utf-8-sig")

            self.assertEqual(result["health"][2]["quote_gap_refetch_count"], "1")
            self.assertEqual(result["health"][2]["quote_gap_review_count"], "1")
            self.assertIn("| 港股周筛 | ready | online | 84.10% | 99.69% | 2 | 1 | 1 | 2 |", report)
            self.assertIn("数据健康需关注：港股周筛 行情可重抓缺口 1", report)
            self.assertNotIn("数据健康需关注：港股周筛 估值口径复核 1", report)

    def test_data_health_deduplicates_valuation_review_risk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(
                root / "outputs" / "hk_universe" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# HK Weekly Data Summary",
                        "- Candidate count: 1",
                        "- Candidate tickers: AAA",
                        "- Model audit: outputs/hk_universe/model_audit.md",
                        "- Data health history: outputs/hk_universe/data_health_history.csv",
                        "- Quote gaps: outputs/hk_universe/quote_gaps.csv",
                    ]
                ),
            )
            write_text(root / "outputs" / "us_universe" / "latest_run_summary.md", "# US Weekly Screening Run Summary\n")
            write_text(root / "outputs" / "cn_universe" / "latest_run_summary.md", "# CN Weekly Data Summary\n")
            write_text(root / "outputs" / "hk_universe" / "model_audit.md", "- 审计状态：sample_accumulating\n")
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")
            for universe in ["us_universe", "cn_universe"]:
                write_csv(
                    root / "outputs" / universe / "data_health_history.csv",
                    ["run_time", "refresh_status", "quote_coverage_pct", "financial_coverage_pct", "candidate_count"],
                    [
                        {
                            "run_time": "2026-06-27 14:05:00",
                            "refresh_status": "online",
                            "quote_coverage_pct": "100.00",
                            "financial_coverage_pct": "100.00",
                            "candidate_count": "0",
                        }
                    ],
                )
            write_csv(
                root / "outputs" / "hk_universe" / "data_health_history.csv",
                ["run_time", "refresh_status", "quote_coverage_pct", "financial_coverage_pct", "candidate_count"],
                [
                    {
                        "run_time": "2026-06-27 14:05:00",
                        "refresh_status": "online",
                        "quote_coverage_pct": "100.00",
                        "financial_coverage_pct": "99.69",
                        "candidate_count": "1",
                    }
                ],
            )
            write_csv(
                root / "outputs" / "hk_universe" / "quote_gaps.csv",
                ["ticker", "issue_type", "remediation_type", "review_category", "review_detail"],
                [
                    {
                        "ticker": "AAA",
                        "issue_type": "non_positive_metric",
                        "remediation_type": "manual_financial_review",
                        "review_category": "loss_making_or_negative_pe",
                        "review_detail": "pe=-3.5",
                    },
                ],
            )
            write_csv(
                root / "outputs" / "hk_universe" / "valuation_review_items.csv",
                ["ticker", "company_name", "valuation_review_category", "valuation_review_detail"],
                [
                    {
                        "ticker": "AAA",
                        "company_name": "Alpha",
                        "valuation_review_category": "loss_making_or_negative_pe",
                        "valuation_review_detail": "pe=-3.5",
                    },
                ],
            )

            result = run_self_analysis(root)
            report = Path(result["output"]).read_text(encoding="utf-8-sig")
            manifest = json.loads(Path(result["manifest_output"]).read_text(encoding="utf-8-sig"))

            self.assertEqual(manifest["data_health_status"], "clear")
            self.assertEqual(manifest["data_health_recommended_action"], "monitor_next_run")
            self.assertNotIn("review_data_health", manifest["automation_priority_actions"])
            self.assertIn("review_manual_queue", manifest["automation_priority_actions"])
            self.assertEqual(manifest["manual_review_queue_count"], 1)
            self.assertNotIn("数据健康需关注：港股周筛 估值口径复核 1", report)
            self.assertNotIn("估值复核待确认：港股周筛 1", report)
            self.assertIn("优先人工复核估值复核清单", report)

    def test_generates_summary_from_weekly_market_and_backtest_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(
                root / "outputs" / "automation" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# US Weekly Screening Run Summary",
                        "- Candidate count: 2",
                        "- Candidate tickers: ADBE, QCOM",
                        "- Model audit: outputs/us_universe/model_audit.md",
                    ]
                ),
            )
            write_text(
                root / "outputs" / "cn_universe" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# CN Weekly Data Summary",
                        "- Candidate count: 1",
                        "- Candidate tickers: 600519.SH",
                        "- Model audit: outputs/cn_universe/model_audit.md",
                    ]
                ),
            )
            write_text(
                root / "outputs" / "hk_universe" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# HK Weekly Data Summary",
                        "- Candidate count: 0",
                        "- Candidate tickers: None",
                        "- Model audit: outputs/hk_universe/model_audit.md",
                    ]
                ),
            )
            write_text(root / "outputs" / "us_universe" / "model_audit.md", "- 审计状态：sample_accumulating\n")
            write_text(root / "outputs" / "cn_universe" / "model_audit.md", "- 审计状态：shadow_analysis_ready\n")
            write_text(root / "outputs" / "hk_universe" / "model_audit.md", "- 审计状态：sample_accumulating\n")
            write_text(
                root / "outputs" / "automation" / "latest_backtest_summary.md",
                "\n".join(
                    [
                        "# US Point-in-Time Backtest Summary",
                        "- Weeks completed: 8",
                        "- Weeks failed: 0",
                        "- Membership evidence verified: 35/40 (87.5%)",
                        "- Weak evidence rows: 5",
                        "- Evidence status: evidence_review_needed",
                        "- Weak evidence weeks: 8",
                        "- Evidence next action: supplement_verified_membership_evidence",
                    ]
                ),
            )
            write_text(
                root / "outputs" / "automation" / "latest_backtest_evidence_review.json",
                json.dumps(
                    {
                        "status": "evidence_ceiling_confirmed",
                        "evidence_ceiling_status": "evidence_ceiling_confirmed",
                        "backtest_mode": "limited_verified_only",
                        "recommended_action": "maintain_limited_backtest",
                        "membership_evidence_unresolved_gap_count": 425,
                        "membership_evidence_action_required_count": 0,
                        "backtest_sample_expansion_allowed": False,
                        "historical_membership_auto_update_allowed": False,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )

            result = run_self_analysis(root, as_of_date="2026-06-25")

            output = Path(result["output"])
            text = output.read_text(encoding="utf-8-sig")
            manifest = json.loads(Path(result["manifest_output"]).read_text(encoding="utf-8-sig"))
            self.assertEqual(manifest["manifest_schema"], "self_analysis_manifest")
            self.assertEqual(manifest["manifest_version"], 1)
            self.assertEqual(len(manifest["markets"]), 3)
            self.assertEqual(manifest["markets"][0]["status"], "ready")
            self.assertEqual(manifest["markets"][0]["candidate_count"], "2")
            self.assertEqual(manifest["markets"][1]["candidate_count"], "1")
            self.assertEqual(manifest["markets"][2]["candidate_count"], "0")
            self.assertIn("summary_path", manifest["markets"][0])
            self.assertEqual(manifest["model_audit_status"], "sample_accumulating")
            self.assertEqual(manifest["model_audit_recommended_action"], "continue_sample_accumulation")
            self.assertEqual(manifest["model_audit_sample_accumulating_count"], 2)
            self.assertEqual(manifest["model_audit_shadow_ready_count"], 1)
            self.assertEqual(manifest["model_audit_statuses"]["A股周筛"], "shadow_analysis_ready")
            self.assertEqual(manifest["backtest_status"], "evidence_ceiling_confirmed")
            self.assertEqual(manifest["backtest_recommended_action"], "maintain_limited_backtest")
            self.assertEqual(manifest["backtest_mode"], "limited_verified_only")
            self.assertEqual(manifest["backtest_unresolved_gap_count"], 425)
            self.assertEqual(manifest["backtest_weeks_completed"], "8")
            self.assertEqual(manifest["backtest_weeks_failed"], "0")
            self.assertEqual(manifest["backtest_weak_rows"], "5")
            self.assertEqual(manifest["backtest_membership_verified"], "35/40 (87.5%)")
            self.assertEqual(manifest["backtest_evidence_status"], "evidence_ceiling_confirmed")
            self.assertEqual(manifest["backtest_weak_evidence_weeks"], "8")
            self.assertEqual(
                manifest["backtest_evidence_next_action"],
                "maintain_limited_backtest",
            )
            self.assertEqual(manifest["automation_status"], "manual_review_needed")
            self.assertEqual(manifest["automation_recommended_action"], "review_data_health")
            self.assertNotIn("review_backtest_evidence", manifest["automation_priority_actions"])
            self.assertNotIn("maintain_limited_backtest", manifest["automation_priority_actions"])
            self.assertIn("continue_sample_accumulation", manifest["automation_priority_actions"])
            check = json.loads(Path(result["automation_check_output"]).read_text(encoding="utf-8-sig"))
            self.assertEqual(check["check_schema"], "weekly_automation_check")
            self.assertEqual(check["check_version"], 1)
            self.assertEqual(check["as_of_date"], "2026-06-25")
            self.assertEqual(check["status"], "manual_review_needed")
            self.assertEqual(check["recommended_action"], "review_data_health")
            self.assertEqual(check["manifest_validation_status"], "valid")
            self.assertEqual(check["markets_ready_count"], 3)
            self.assertEqual(check["market_count"], 3)
            self.assertEqual(check["candidate_count_total"], 3)
            self.assertEqual(check["manual_review_queue_count"], manifest["manual_review_queue_count"])
            self.assertTrue(check["outputs"]["manifest"].endswith("latest_self_analysis_manifest.json"))
            self.assertTrue(output.exists())
            self.assertIn("每周自我分析摘要", text)
            self.assertIn("美股周筛", text)
            self.assertIn("候选数：2", text)
            self.assertIn("成员证据 verified：35/40 (87.5%)", text)
            self.assertIn("弱证据行：5", text)
            self.assertIn("证据状态：evidence_ceiling_confirmed", text)
            self.assertIn("弱证据周数：8", text)
            self.assertIn("证据上限已确认，维持受限回测", text)

    def test_self_analysis_summarizes_forecast_performance_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for universe, title in (
                ("us_universe", "US Weekly Screening Run Summary"),
                ("cn_universe", "CN Weekly Data Summary"),
                ("hk_universe", "HK Weekly Data Summary"),
            ):
                write_text(root / "outputs" / universe / "latest_run_summary.md", f"# {title}\n")
                write_text(root / "outputs" / universe / "model_audit.md", "- 审计状态：sample_accumulating\n")
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")
            fields = [
                "market",
                "ticker",
                "generated_date",
                "checkpoint_weeks",
                "prediction_horizon",
                "evaluation_status",
                "direction_hit",
                "actual_return",
                "excess_return",
            ]
            write_csv(
                root / "outputs" / "us_universe" / "forecast_evaluations.csv",
                fields,
                [
                    {
                        "market": "US",
                        "ticker": "AAA",
                        "generated_date": "2026-06-21",
                        "checkpoint_weeks": "1",
                        "prediction_horizon": "1w",
                        "evaluation_status": "evaluated",
                        "direction_hit": "True",
                        "actual_return": "0.08",
                        "excess_return": "0.03",
                    }
                ],
            )
            write_csv(
                root / "outputs" / "cn_universe" / "forecast_evaluations.csv",
                fields,
                [
                    {
                        "market": "CN",
                        "ticker": "BBB",
                        "generated_date": "2026-06-21",
                        "checkpoint_weeks": "1",
                        "prediction_horizon": "1w",
                        "evaluation_status": "prediction_unavailable",
                        "direction_hit": "",
                        "actual_return": "-0.02",
                        "excess_return": "-0.01",
                    }
                ],
            )
            write_text(
                root / "outputs" / "automation" / "latest_forecast_performance_review.json",
                json.dumps(
                    {
                        "next_one_week_evaluation_date": "2026-07-05",
                        "next_one_week_evaluation_count": 17,
                        "next_one_month_evaluation_date": "2026-07-26",
                        "next_one_month_evaluation_count": 19,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )

            result = run_self_analysis(root, as_of_date="2026-06-28")
            report = Path(result["output"]).read_text(encoding="utf-8-sig")
            manifest = json.loads(Path(result["manifest_output"]).read_text(encoding="utf-8-sig"))
            check = json.loads(Path(result["automation_check_output"]).read_text(encoding="utf-8-sig"))

            self.assertEqual(manifest["forecast_performance_status"], "partial_sample_accumulating")
            self.assertEqual(manifest["forecast_performance_recommended_action"], "continue_sample_accumulation")
            self.assertEqual(manifest["forecast_performance"]["total_evaluations"], 2)
            self.assertEqual(manifest["forecast_performance"]["mature_evaluations"], 1)
            self.assertEqual(manifest["forecast_performance"]["one_week_mature"], 1)
            self.assertEqual(manifest["forecast_performance"]["prediction_unavailable"], 1)
            self.assertEqual(manifest["forecast_performance"]["missing_market_count"], 1)
            self.assertAlmostEqual(manifest["forecast_performance"]["direction_hit_rate"], 1.0)
            self.assertEqual(
                manifest["forecast_performance"]["next_one_week_evaluation_date"],
                "2026-07-05",
            )
            self.assertEqual(
                manifest["forecast_performance"]["next_one_week_evaluation_count"],
                17,
            )
            self.assertEqual(
                manifest["forecast_performance"]["next_one_month_evaluation_date"],
                "2026-07-26",
            )
            self.assertEqual(
                manifest["forecast_performance"]["next_one_month_evaluation_count"],
                19,
            )
            self.assertEqual(check["forecast_performance_status"], "partial_sample_accumulating")
            self.assertEqual(check["forecast_next_one_week_evaluation_date"], "2026-07-05")
            self.assertEqual(check["forecast_next_one_week_evaluation_count"], 17)
            self.assertEqual(check["forecast_next_one_month_evaluation_date"], "2026-07-26")
            self.assertEqual(check["forecast_next_one_month_evaluation_count"], 19)
            self.assertIn("## 预测表现", report)
            self.assertIn("partial_sample_accumulating", report)
            self.assertIn("next_one_week_evaluation_date: 2026-07-05", report)
            self.assertIn("next_one_week_evaluation_count: 17", report)
            self.assertIn("next_one_month_evaluation_date: 2026-07-26", report)
            self.assertIn("next_one_month_evaluation_count: 19", report)
            self.assertIn("1w", report)
            self.assertIn("prediction_unavailable", report)

    def test_self_analysis_uses_structured_forecast_review_as_authoritative_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for universe, title in (
                ("us_universe", "US Weekly Screening Run Summary"),
                ("cn_universe", "CN Weekly Data Summary"),
                ("hk_universe", "HK Weekly Data Summary"),
            ):
                write_text(root / "outputs" / universe / "latest_run_summary.md", f"# {title}\n")
                write_text(root / "outputs" / universe / "model_audit.md", "- 瀹¤鐘舵€侊細sample_accumulating\n")
                write_csv(
                    root / "outputs" / universe / "forecast_evaluations.csv",
                    [
                        "market",
                        "ticker",
                        "generated_date",
                        "prediction_horizon",
                        "evaluation_status",
                        "direction_hit",
                        "actual_return",
                        "excess_return",
                    ],
                    [
                        {
                            "market": universe,
                            "ticker": "LEGACY",
                            "generated_date": "2026-06-01",
                            "prediction_horizon": "1w",
                            "evaluation_status": "evaluated",
                            "direction_hit": "True",
                            "actual_return": "0.05",
                            "excess_return": "0.01",
                        }
                    ],
                )
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")
            write_text(
                root / "outputs" / "automation" / "latest_forecast_performance_review.json",
                json.dumps(
                    {
                        "review_schema": "forecast_performance_review",
                        "status": "sample_accumulating",
                        "recommended_action": "continue_sample_accumulation",
                        "total_evaluations": 87,
                        "mature_evaluations": 0,
                        "one_week_mature": 0,
                        "one_month_mature": 0,
                        "prediction_unavailable": 87,
                        "latest_prediction_unavailable_count": 0,
                        "legacy_prediction_unavailable_count": 87,
                        "missing_market_count": 0,
                        "direction_hits": 0,
                        "direction_hit_rate": None,
                        "average_return": None,
                        "average_excess_return": None,
                        "model_audit_status_counts": {
                            "sample_accumulating": 2,
                            "validation_sample_insufficient": 1,
                        },
                        "shadow_model_proposal_count": 0,
                        "next_one_week_evaluation_date": "2026-07-07",
                        "next_one_week_evaluation_count": 42,
                        "next_one_month_evaluation_date": "2026-07-28",
                        "next_one_month_evaluation_count": 42,
                        "markets": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )

            result = run_self_analysis(root, as_of_date="2026-07-05")
            manifest = json.loads(Path(result["manifest_output"]).read_text(encoding="utf-8-sig"))
            check = json.loads(Path(result["automation_check_output"]).read_text(encoding="utf-8-sig"))

            self.assertEqual(manifest["forecast_performance_status"], "sample_accumulating")
            self.assertEqual(
                manifest["forecast_performance_recommended_action"],
                "continue_sample_accumulation",
            )
            self.assertEqual(manifest["forecast_performance"]["total_evaluations"], 87)
            self.assertEqual(manifest["forecast_performance"]["mature_evaluations"], 0)
            self.assertEqual(manifest["forecast_performance"]["prediction_unavailable"], 87)
            self.assertEqual(
                manifest["forecast_performance"]["latest_prediction_unavailable_count"],
                0,
            )
            self.assertEqual(
                manifest["forecast_performance"]["legacy_prediction_unavailable_count"],
                87,
            )
            self.assertEqual(
                manifest["forecast_performance"]["model_audit_status_counts"],
                {"sample_accumulating": 2, "validation_sample_insufficient": 1},
            )
            self.assertEqual(manifest["forecast_performance"]["shadow_model_proposal_count"], 0)
            self.assertEqual(check["forecast_performance_status"], "sample_accumulating")
            self.assertEqual(check["forecast_next_one_week_evaluation_date"], "2026-07-07")

    def test_mature_weak_forecast_performance_requests_review_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for universe, title in (
                ("us_universe", "US Weekly Screening Run Summary"),
                ("cn_universe", "CN Weekly Data Summary"),
                ("hk_universe", "HK Weekly Data Summary"),
            ):
                write_text(root / "outputs" / universe / "latest_run_summary.md", f"# {title}\n")
                write_text(root / "outputs" / universe / "model_audit.md", "- 审计状态：sample_accumulating\n")
                write_csv(
                    root / "outputs" / universe / "data_health_history.csv",
                    ["run_time", "refresh_status", "quote_coverage_pct", "financial_coverage_pct", "candidate_count"],
                    [
                        {
                            "run_time": "2026-06-28 14:00:00",
                            "refresh_status": "online",
                            "quote_coverage_pct": "100.00",
                            "financial_coverage_pct": "100.00",
                            "candidate_count": "0",
                        }
                    ],
                )
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")
            rows = []
            for index in range(30):
                rows.append(
                    {
                        "market": "US",
                        "ticker": f"AAA{index:02d}",
                        "generated_date": "2026-01-01",
                        "checkpoint_weeks": "4",
                        "prediction_horizon": "1m",
                        "evaluation_status": "evaluated",
                        "direction_hit": "False",
                        "actual_return": "-0.03",
                        "excess_return": "-0.04",
                    }
                )
            write_csv(
                root / "outputs" / "us_universe" / "forecast_evaluations.csv",
                [
                    "market",
                    "ticker",
                    "generated_date",
                    "checkpoint_weeks",
                    "prediction_horizon",
                    "evaluation_status",
                    "direction_hit",
                    "actual_return",
                    "excess_return",
                ],
                rows,
            )
            for universe in ("cn_universe", "hk_universe"):
                write_csv(
                    root / "outputs" / universe / "forecast_evaluations.csv",
                    [
                        "market",
                        "ticker",
                        "generated_date",
                        "checkpoint_weeks",
                        "prediction_horizon",
                        "evaluation_status",
                        "direction_hit",
                        "actual_return",
                        "excess_return",
                    ],
                    [],
                )
            write_text(
                root
                / "outputs"
                / "automation"
                / "latest_one_week_forecast_shadow_disposition.json",
                json.dumps(
                    {
                        "disposition_schema": "one_week_forecast_shadow_disposition",
                        "disposition_version": 1,
                        "as_of_date": "2026-06-28",
                        "status": "ready",
                        "recommended_action": "continue_shadow_validation",
                        "disposition_counts": {
                            "continue_observation": 3,
                            "rejected": 0,
                            "pending_human_approval": 0,
                        },
                        "candidate_dispositions": [],
                        "next_one_week_evaluation_date": "2026-07-05",
                        "next_one_week_evaluation_count": 30,
                        "formal_model_change_allowed": False,
                    },
                    ensure_ascii=False,
                ),
            )

            result = run_self_analysis(root, as_of_date="2026-06-28")
            manifest = json.loads(Path(result["manifest_output"]).read_text(encoding="utf-8-sig"))
            check = json.loads(Path(result["automation_check_output"]).read_text(encoding="utf-8-sig"))

            self.assertEqual(manifest["forecast_performance_status"], "performance_review_needed")
            self.assertEqual(manifest["forecast_performance_recommended_action"], "continue_shadow_validation")
            self.assertEqual(manifest["forecast_performance"]["mature_evaluations"], 30)
            self.assertEqual(manifest["forecast_performance"]["direction_hit_rate"], 0.0)
            self.assertAlmostEqual(manifest["forecast_performance"]["average_excess_return"], -0.04)
            self.assertEqual(
                manifest["one_week_forecast_shadow_disposition"]["recommended_action"],
                "continue_shadow_validation",
            )
            self.assertIn("continue_shadow_validation", manifest["automation_priority_actions"])
            self.assertNotIn("review_forecast_performance", manifest["automation_priority_actions"])
            self.assertEqual(check["forecast_performance_status"], "performance_review_needed")

    def test_missing_shadow_disposition_requests_input_repair(self):
        from automation_self_analysis import _one_week_forecast_shadow_disposition_snapshot

        with tempfile.TemporaryDirectory() as tmp:
            snapshot = _one_week_forecast_shadow_disposition_snapshot(Path(tmp))

        self.assertEqual(snapshot["status"], "missing")
        self.assertEqual(snapshot["recommended_action"], "repair_shadow_disposition_inputs")
        self.assertFalse(snapshot["formal_model_change_allowed"])

    def test_missing_inputs_are_reported_without_failing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_self_analysis(Path(tmp), as_of_date="2026-06-25")
            text = Path(result["output"]).read_text(encoding="utf-8-sig")

            self.assertIn("缺失摘要", text)
            self.assertIn("先补齐缺失的周筛或回测摘要", text)

    def test_self_analysis_uses_weekly_ops_history_as_stability_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(root / "outputs" / "us_universe" / "latest_run_summary.md", "# US Weekly Screening Run Summary\n")
            write_text(root / "outputs" / "cn_universe" / "latest_run_summary.md", "# CN Weekly Data Summary\n")
            write_text(root / "outputs" / "hk_universe" / "latest_run_summary.md", "# HK Weekly Data Summary\n")
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")
            write_text(
                root / "outputs" / "automation" / "weekly_ops_check_history.jsonl",
                "\n".join(
                    [
                        json.dumps(
                            {
                                "history_schema": "weekly_ops_check_history",
                                "history_version": 1,
                                "ops_check_schema": "weekly_ops_check",
                                "as_of_date": "2026-06-20",
                                "status": "needs_attention",
                                "freshness_status": "fresh",
                                "attention_reasons": ["automation_audit"],
                            }
                        ),
                        json.dumps(
                            {
                                "history_schema": "weekly_ops_check_history",
                                "history_version": 1,
                                "ops_check_schema": "weekly_ops_check",
                                "as_of_date": "2026-06-27",
                                "status": "needs_attention",
                                "freshness_status": "fresh",
                                "attention_reasons": ["automation_audit"],
                            }
                        ),
                    ]
                )
                + "\n",
            )

            result = run_self_analysis(root, as_of_date="2026-06-27")
            report = Path(result["output"]).read_text(encoding="utf-8-sig")
            manifest = json.loads(Path(result["manifest_output"]).read_text(encoding="utf-8-sig"))
            check = json.loads(Path(result["automation_check_output"]).read_text(encoding="utf-8-sig"))

            self.assertEqual(manifest["weekly_ops_history_status"], "manual_review_needed")
            self.assertEqual(manifest["weekly_ops_history_recommended_action"], "review_recurring_ops_issues")
            self.assertEqual(manifest["weekly_ops_history"]["needs_attention_count"], 2)
            self.assertEqual(
                manifest["weekly_ops_history"]["recurring_attention_reasons"],
                [{"reason": "automation_audit", "count": 2}],
            )
            self.assertIn("review_recurring_ops_issues", manifest["automation_priority_actions"])
            self.assertEqual(check["weekly_ops_history_status"], "manual_review_needed")
            self.assertIn("review_recurring_ops_issues", report)

    def test_self_analysis_uses_weekly_delivery_history_as_stability_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(root / "outputs" / "us_universe" / "latest_run_summary.md", "# US Weekly Screening Run Summary\n")
            write_text(root / "outputs" / "cn_universe" / "latest_run_summary.md", "# CN Weekly Data Summary\n")
            write_text(root / "outputs" / "hk_universe" / "latest_run_summary.md", "# HK Weekly Data Summary\n")
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")
            write_text(
                root / "outputs" / "automation" / "weekly_delivery_check_history.jsonl",
                "\n".join(
                    [
                        json.dumps(
                            {
                                "history_schema": "weekly_delivery_check_history",
                                "history_version": 1,
                                "delivery_check_schema": "weekly_delivery_check",
                                "as_of_date": "2026-06-20",
                                "status": "needs_attention",
                                "freshness_status": "fresh",
                                "attention_reasons": ["missing_outputs"],
                            }
                        ),
                        json.dumps(
                            {
                                "history_schema": "weekly_delivery_check_history",
                                "history_version": 1,
                                "delivery_check_schema": "weekly_delivery_check",
                                "as_of_date": "2026-06-27",
                                "status": "needs_attention",
                                "freshness_status": "fresh",
                                "attention_reasons": ["missing_outputs"],
                            }
                        ),
                    ]
                )
                + "\n",
            )

            result = run_self_analysis(root, as_of_date="2026-06-27")
            report = Path(result["output"]).read_text(encoding="utf-8-sig")
            manifest = json.loads(Path(result["manifest_output"]).read_text(encoding="utf-8-sig"))
            check = json.loads(Path(result["automation_check_output"]).read_text(encoding="utf-8-sig"))

            self.assertEqual(manifest["weekly_delivery_history_status"], "manual_review_needed")
            self.assertEqual(
                manifest["weekly_delivery_history_recommended_action"],
                "review_recurring_delivery_issues",
            )
            self.assertEqual(manifest["weekly_delivery_history"]["needs_attention_count"], 2)
            self.assertEqual(
                manifest["weekly_delivery_history"]["recurring_attention_reasons"],
                [{"reason": "missing_outputs", "count": 2}],
            )
            self.assertIn("review_recurring_delivery_issues", manifest["automation_priority_actions"])
            self.assertEqual(check["weekly_delivery_history_status"], "manual_review_needed")
            self.assertIn("review_recurring_delivery_issues", report)

    def test_self_analysis_exposes_delivery_action_items_actual_count_trend(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(root / "outputs" / "us_universe" / "latest_run_summary.md", "# US Weekly Screening Run Summary\n")
            write_text(root / "outputs" / "cn_universe" / "latest_run_summary.md", "# CN Weekly Data Summary\n")
            write_text(root / "outputs" / "hk_universe" / "latest_run_summary.md", "# HK Weekly Data Summary\n")
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")
            write_text(
                root / "outputs" / "automation" / "weekly_delivery_check_history.jsonl",
                "\n".join(
                    [
                        json.dumps(
                            {
                                "history_schema": "weekly_delivery_check_history",
                                "history_version": 1,
                                "delivery_check_schema": "weekly_delivery_check",
                                "as_of_date": "2026-06-13",
                                "status": "ready",
                                "freshness_status": "fresh",
                                "attention_reasons": [],
                                "action_items_status": "ready",
                                "action_items_count": 3,
                                "action_items_actual_count": 3,
                            }
                        ),
                        json.dumps(
                            {
                                "history_schema": "weekly_delivery_check_history",
                                "history_version": 1,
                                "delivery_check_schema": "weekly_delivery_check",
                                "as_of_date": "2026-06-20",
                                "status": "ready",
                                "freshness_status": "fresh",
                                "attention_reasons": [],
                                "action_items_status": "ready",
                                "action_items_count": 5,
                                "action_items_actual_count": 5,
                            }
                        ),
                        json.dumps(
                            {
                                "history_schema": "weekly_delivery_check_history",
                                "history_version": 1,
                                "delivery_check_schema": "weekly_delivery_check",
                                "as_of_date": "2026-06-27",
                                "status": "ready",
                                "freshness_status": "fresh",
                                "attention_reasons": [],
                                "action_items_status": "ready",
                                "action_items_count": 8,
                                "action_items_actual_count": 8,
                            }
                        ),
                    ]
                )
                + "\n",
            )

            result = run_self_analysis(root, as_of_date="2026-06-27")
            report = Path(result["output"]).read_text(encoding="utf-8-sig")
            manifest = json.loads(Path(result["manifest_output"]).read_text(encoding="utf-8-sig"))
            check = json.loads(Path(result["automation_check_output"]).read_text(encoding="utf-8-sig"))

            self.assertEqual(manifest["weekly_delivery_action_items_actual_count"], 8)
            self.assertEqual(manifest["weekly_delivery_action_items_actual_count_delta"], 5)
            self.assertEqual(manifest["weekly_delivery_action_items_actual_count_trend"], "increasing")
            self.assertEqual(check["weekly_delivery_action_items_actual_count"], 8)
            self.assertEqual(check["weekly_delivery_action_items_actual_count_delta"], 5)
            self.assertEqual(check["weekly_delivery_action_items_actual_count_trend"], "increasing")
            self.assertIn("reduce_weekly_action_backlog", manifest["automation_priority_actions"])
            self.assertIn("reduce_weekly_action_backlog", check["priority_actions"])
            self.assertIn("action_items_actual_count_trend: increasing", report)

    def test_self_analysis_maps_delivery_health_reasons_to_priority_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(root / "outputs" / "us_universe" / "latest_run_summary.md", "# US Weekly Screening Run Summary\n")
            write_text(root / "outputs" / "cn_universe" / "latest_run_summary.md", "# CN Weekly Data Summary\n")
            write_text(root / "outputs" / "hk_universe" / "latest_run_summary.md", "# HK Weekly Data Summary\n")
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")
            write_text(
                root / "outputs" / "automation" / "weekly_delivery_check_history.jsonl",
                "\n".join(
                    [
                        json.dumps(
                            {
                                "history_schema": "weekly_delivery_check_history",
                                "history_version": 1,
                                "delivery_check_schema": "weekly_delivery_check",
                                "as_of_date": "2026-06-20",
                                "status": "ready",
                                "freshness_status": "fresh",
                                "attention_reasons": [],
                                "conclusion_health_status": "needs_review",
                                "conclusion_health_score": 78,
                                "conclusion_health_reasons": ["manual_review_pending:8"],
                            }
                        ),
                        json.dumps(
                            {
                                "history_schema": "weekly_delivery_check_history",
                                "history_version": 1,
                                "delivery_check_schema": "weekly_delivery_check",
                                "as_of_date": "2026-06-27",
                                "status": "ready",
                                "freshness_status": "fresh",
                                "attention_reasons": [],
                                "conclusion_health_status": "needs_review",
                                "conclusion_health_score": 75,
                                "conclusion_health_reasons": ["manual_review_pending:8"],
                            }
                        ),
                    ]
                )
                + "\n",
            )

            result = run_self_analysis(root, as_of_date="2026-06-27")
            report = Path(result["output"]).read_text(encoding="utf-8-sig")
            manifest = json.loads(Path(result["manifest_output"]).read_text(encoding="utf-8-sig"))

            self.assertEqual(manifest["weekly_delivery_history_status"], "manual_review_needed")
            self.assertEqual(
                manifest["weekly_delivery_history_recommended_action"],
                "review_manual_review_backlog",
            )
            self.assertEqual(
                manifest["weekly_delivery_history"]["recurring_health_reasons"],
                [{"reason": "manual_review_pending:8", "count": 2}],
            )
            self.assertIn("review_manual_review_backlog", manifest["automation_priority_actions"])
            self.assertIn("manual_review_pending:8", report)
            self.assertIn("review_manual_review_backlog", report)

    def test_self_analysis_maps_missing_conclusion_signals_to_delivery_health_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(root / "outputs" / "us_universe" / "latest_run_summary.md", "# US Weekly Screening Run Summary\n")
            write_text(root / "outputs" / "cn_universe" / "latest_run_summary.md", "# CN Weekly Data Summary\n")
            write_text(root / "outputs" / "hk_universe" / "latest_run_summary.md", "# HK Weekly Data Summary\n")
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")
            write_text(
                root / "outputs" / "automation" / "weekly_delivery_check_history.jsonl",
                "\n".join(
                    [
                        json.dumps(
                            {
                                "history_schema": "weekly_delivery_check_history",
                                "history_version": 1,
                                "delivery_check_schema": "weekly_delivery_check",
                                "as_of_date": "2026-06-20",
                                "status": "needs_attention",
                                "freshness_status": "fresh",
                                "attention_reasons": ["missing_conclusion_signals"],
                                "conclusion_signal_status": "missing",
                                "missing_conclusion_signals": ["automation.forecast_performance"],
                            }
                        ),
                        json.dumps(
                            {
                                "history_schema": "weekly_delivery_check_history",
                                "history_version": 1,
                                "delivery_check_schema": "weekly_delivery_check",
                                "as_of_date": "2026-06-27",
                                "status": "needs_attention",
                                "freshness_status": "fresh",
                                "attention_reasons": ["missing_conclusion_signals"],
                                "conclusion_signal_status": "missing",
                                "missing_conclusion_signals": [
                                    "automation.data_quality_history",
                                    "automation.forecast_performance",
                                ],
                            }
                        ),
                    ]
                )
                + "\n",
            )

            result = run_self_analysis(root, as_of_date="2026-06-27")
            report = Path(result["output"]).read_text(encoding="utf-8-sig")
            manifest = json.loads(Path(result["manifest_output"]).read_text(encoding="utf-8-sig"))

            self.assertEqual(manifest["weekly_delivery_history_status"], "manual_review_needed")
            self.assertEqual(
                manifest["weekly_delivery_history_recommended_action"],
                "review_delivery_health_issues",
            )
            self.assertEqual(manifest["weekly_delivery_history"]["latest_conclusion_signal_status"], "missing")
            self.assertEqual(
                manifest["weekly_delivery_history"]["recurring_missing_conclusion_signals"],
                [{"signal": "automation.forecast_performance", "count": 2}],
            )
            self.assertIn("review_delivery_health_issues", manifest["automation_priority_actions"])
            self.assertIn("automation.forecast_performance", report)
            self.assertIn("review_delivery_health_issues", report)

    def test_cli_prints_self_analysis_and_manual_review_queue_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(PROJECT_ROOT / "automation_self_analysis.py"),
                    "--project-root",
                    str(root),
                    "--as-of-date",
                    "2026-06-28",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("Self-analysis summary:", output)
            self.assertIn("Manual review queue:", output)
            self.assertIn("latest_manual_review_queue.csv", output)
            self.assertIn("Manual review history:", output)
            self.assertIn("manual_review_queue_history.csv", output)
            self.assertIn("Manual review repeats:", output)
            self.assertIn("manual_review_repeats.csv", output)
            self.assertIn("Self-analysis manifest:", output)
            self.assertIn("latest_self_analysis_manifest.json", output)
            self.assertIn("Automation check:", output)
            self.assertIn("latest_automation_check.json", output)
            self.assertTrue((root / "outputs" / "automation" / "latest_automation_check.json").exists())
            self.assertTrue((root / "outputs" / "automation" / "latest_manual_review_queue.csv").exists())

    def test_validates_self_analysis_manifest_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_self_analysis(root, as_of_date="2026-06-27")

            from automation_self_analysis import validate_self_analysis_manifest

            validation = validate_self_analysis_manifest(result["manifest_output"])

            self.assertEqual(validation["status"], "valid")
            self.assertEqual(validation["schema"], "self_analysis_manifest")
            self.assertEqual(validation["version"], 1)
            self.assertEqual(validation["missing_fields"], [])

    def test_manifest_validator_reports_missing_required_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(
                json.dumps({"manifest_schema": "self_analysis_manifest", "manifest_version": 1}),
                encoding="utf-8-sig",
            )

            from automation_self_analysis import validate_self_analysis_manifest

            validation = validate_self_analysis_manifest(path)

            self.assertEqual(validation["status"], "invalid")
            self.assertIn("automation_status", validation["missing_fields"])

    def test_cli_can_validate_self_analysis_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_self_analysis(root, as_of_date="2026-06-27")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "automation_self_analysis.py"),
                    "--validate-manifest",
                    result["manifest_output"],
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(completed.returncode, 0)
            self.assertIn("Self-analysis manifest valid", completed.stdout)

    def test_manifest_completion_validator_reports_not_ready_markets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(root / "outputs" / "us_universe" / "latest_run_summary.md", "# US Weekly Screening Run Summary\n")
            write_text(root / "outputs" / "hk_universe" / "latest_run_summary.md", "# HK Weekly Data Summary\n")
            result = run_self_analysis(root, as_of_date="2026-06-27")

            from automation_self_analysis import validate_self_analysis_manifest

            validation = validate_self_analysis_manifest(
                result["manifest_output"],
                require_markets_ready=True,
            )

            self.assertEqual(validation["status"], "invalid")
            self.assertEqual(len(validation["not_ready_markets"]), 1)
            self.assertIn("market_not_ready", "; ".join(validation["errors"]))

    def test_cli_can_require_ready_market_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(root / "outputs" / "us_universe" / "latest_run_summary.md", "# US Weekly Screening Run Summary\n")
            write_text(root / "outputs" / "cn_universe" / "latest_run_summary.md", "# CN Weekly Data Summary\n")
            write_text(root / "outputs" / "hk_universe" / "latest_run_summary.md", "# HK Weekly Data Summary\n")
            result = run_self_analysis(root, as_of_date="2026-06-27")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "automation_self_analysis.py"),
                    "--validate-manifest",
                    result["manifest_output"],
                    "--require-market-ready",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(completed.returncode, 0)
            self.assertIn("markets_ready=3", completed.stdout)


    def test_includes_data_health_history_and_flags_attention_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(
                root / "outputs" / "automation" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# US Weekly Screening Run Summary",
                        "- Candidate count: 2",
                        "- Candidate tickers: ADBE, QCOM",
                        "- Model audit: outputs/us_universe/model_audit.md",
                        "- Data health history: outputs/us_universe/data_health_history.csv",
                    ]
                ),
            )
            write_text(
                root / "outputs" / "cn_universe" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# CN Weekly Data Summary",
                        "- Candidate count: 1",
                        "- Candidate tickers: 600519.SH",
                        "- Model audit: outputs/cn_universe/model_audit.md",
                        "- Data health history: outputs/cn_universe/data_health_history.csv",
                    ]
                ),
            )
            write_text(
                root / "outputs" / "hk_universe" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# HK Weekly Data Summary",
                        "- Candidate count: 3",
                        "- Candidate tickers: 00700.HK, 00005.HK, 00883.HK",
                        "- Model audit: outputs/hk_universe/model_audit.md",
                        "- Data health history: outputs/hk_universe/data_health_history.csv",
                    ]
                ),
            )
            write_text(root / "outputs" / "us_universe" / "model_audit.md", "- 审计状态：sample_accumulating\n")
            write_text(root / "outputs" / "cn_universe" / "model_audit.md", "- 审计状态：sample_accumulating\n")
            write_text(root / "outputs" / "hk_universe" / "model_audit.md", "- 审计状态：sample_accumulating\n")
            write_text(
                root / "outputs" / "automation" / "latest_backtest_summary.md",
                "\n".join(
                    [
                        "# US Point-in-Time Backtest Summary",
                        "- Weeks completed: 8",
                        "- Weeks failed: 0",
                        "- Membership evidence verified: 40/40 (100.0%)",
                        "- Weak evidence rows: 0",
                    ]
                ),
            )
            write_csv(
                root / "outputs" / "us_universe" / "data_health_history.csv",
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
                        "universe_count": "500",
                        "candidate_count": "3",
                        "quote_ready": "500",
                        "quote_total": "500",
                        "quote_coverage_pct": "100.00",
                        "data_quality_total": "1",
                        "data_quality_blocked": "0",
                        "data_quality_warnings": "1",
                        "affected_candidate_count": "0",
                        "share_override_total": "2",
                        "share_override_review": "0",
                    }
                ],
            )
            regional_fields = [
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
            ]
            write_csv(
                root / "outputs" / "cn_universe" / "data_health_history.csv",
                regional_fields,
                [
                    {
                        "run_time": "2026-06-27 14:05:00",
                        "market": "CN",
                        "universe": "CSI 300",
                        "refresh_status": "online",
                        "company_count": "300",
                        "quote_ready": "278",
                        "quote_total": "300",
                        "quote_coverage_pct": "92.67",
                        "financial_ready": "300",
                        "financial_total": "300",
                        "financial_coverage_pct": "100.00",
                        "candidate_count": "7",
                        "valuation_ready": "7",
                        "valuation_total": "7",
                        "tracking_count": "21",
                        "mature_evaluation_count": "0",
                    }
                ],
            )
            write_csv(
                root / "outputs" / "hk_universe" / "data_health_history.csv",
                regional_fields,
                [
                    {
                        "run_time": "2026-06-27 14:05:00",
                        "market": "HK",
                        "universe": "HSLI and HSMI",
                        "refresh_status": "cache_fallback",
                        "company_count": "327",
                        "quote_ready": "275",
                        "quote_total": "327",
                        "quote_coverage_pct": "84.10",
                        "financial_ready": "326",
                        "financial_total": "327",
                        "financial_coverage_pct": "99.69",
                        "candidate_count": "35",
                        "valuation_ready": "35",
                        "valuation_total": "35",
                        "tracking_count": "106",
                        "mature_evaluation_count": "0",
                    }
                ],
            )

            result = run_self_analysis(root, as_of_date="2026-06-27")

            manifest = json.loads(Path(result["manifest_output"]).read_text(encoding="utf-8-sig"))
            self.assertEqual(manifest["data_health_status"], "manual_review_needed")
            self.assertEqual(manifest["data_health_recommended_action"], "review_data_health")
            self.assertEqual(manifest["data_health_risk_count"], 3)
            self.assertEqual(len(manifest["data_health_risks"]), 3)
            self.assertEqual(len(manifest["health"]), 3)
            self.assertEqual(manifest["health"][1]["refresh_status"], "online")
            self.assertEqual(manifest["health"][1]["quote_coverage"], "92.67%")
            self.assertEqual(manifest["health"][2]["refresh_status"], "cache_fallback")
            self.assertEqual(manifest["health"][2]["quote_coverage"], "84.10%")
            self.assertEqual(manifest["health"][2]["candidate_count"], "35")

            text = Path(result["output"]).read_text(encoding="utf-8-sig")
            self.assertIn("## 数据健康", text)
            self.assertIn("| A股周筛 | ready | online | 92.67% | 100.00% | 0 | 0 | 0 | 7 |", text)
            self.assertIn("| 港股周筛 | ready | cache_fallback | 84.10% | 99.69% | 0 | 0 | 0 | 35 |", text)
            self.assertIn("数据健康需关注：A股周筛 行情覆盖 92.67%", text)
            self.assertIn("数据健康需关注：港股周筛 刷新状态 cache_fallback", text)
            self.assertIn("数据健康需关注：港股周筛 行情覆盖 84.10%", text)
            self.assertIn("数据健康异常先人工复核，不自动修改正式模型参数", text)


    def test_includes_candidate_review_priorities_from_investment_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(
                root / "outputs" / "automation" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# US Weekly Screening Run Summary",
                        "- Candidate count: 2",
                        "- Candidate tickers: AAA, BBB",
                        "- Model audit: outputs/us_universe/model_audit.md",
                        "- Investment summary: outputs/us_universe/latest_investment_summary.md",
                    ]
                ),
            )
            write_text(
                root / "outputs" / "cn_universe" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# CN Weekly Data Summary",
                        "- Candidate count: 0",
                        "- Candidate tickers: None",
                        "- Model audit: outputs/cn_universe/model_audit.md",
                    ]
                ),
            )
            write_text(
                root / "outputs" / "hk_universe" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# HK Weekly Data Summary",
                        "- Candidate count: 0",
                        "- Candidate tickers: None",
                        "- Model audit: outputs/hk_universe/model_audit.md",
                    ]
                ),
            )
            write_text(root / "outputs" / "us_universe" / "model_audit.md", "- 审计状态：sample_accumulating\n")
            write_text(root / "outputs" / "cn_universe" / "model_audit.md", "- 审计状态：sample_accumulating\n")
            write_text(root / "outputs" / "hk_universe" / "model_audit.md", "- 审计状态：sample_accumulating\n")
            write_text(
                root / "outputs" / "automation" / "latest_backtest_summary.md",
                "\n".join(
                    [
                        "# US Point-in-Time Backtest Summary",
                        "- Weeks completed: 8",
                        "- Weeks failed: 0",
                        "- Membership evidence verified: 40/40 (100.0%)",
                        "- Weak evidence rows: 0",
                    ]
                ),
            )
            write_text(
                root / "outputs" / "us_universe" / "latest_investment_summary.md",
                "\n".join(
                    [
                        "# 每周低估公司结论",
                        "",
                        "## 候选风险说明",
                        "",
                        "| 股票 | 公司 | 风险说明 |",
                        "|---|---|---|",
                        "| AAA | Alpha | 未发现量化硬性风险，仍需复核行业周期和财报一次性项目 |",
                        "| BBB | Beta | 当前无安全边际；预期收益为负 |",
                        "",
                        "## 候选结论质量检查",
                        "",
                        "- 字段完整：1/2",
                        "",
                        "| 股票 | 公司 | 缺口分类 | 具体缺口 |",
                        "|---|---|---|---|",
                        "| BBB | Beta | 数据不足 | 缺少跟踪状态 |",
                    ]
                ),
            )

            result = run_self_analysis(root, as_of_date="2026-06-27")

            manifest = json.loads(Path(result["manifest_output"]).read_text(encoding="utf-8-sig"))
            self.assertEqual(manifest["candidate_review_status"], "manual_review_needed")
            self.assertEqual(manifest["candidate_review_recommended_action"], "review_candidate_findings")
            self.assertEqual(manifest["candidate_review_quality_gap_count"], 1)
            self.assertEqual(manifest["candidate_review_risk_item_count"], 1)
            self.assertEqual(len(manifest["candidate_review_risks"]), 4)

            text = Path(result["output"]).read_text(encoding="utf-8-sig")
            self.assertIn("## 候选复核重点", text)
            self.assertIn("| 美股周筛 | ready | 1/2 | 1 |", text)
            self.assertIn("美股周筛 候选需复核：BBB Beta 数据不足：缺少跟踪状态", text)
            self.assertIn("美股周筛 风险需复核：BBB Beta 当前无安全边际；预期收益为负", text)
            self.assertIn("优先复核候选风险和结论缺口，不自动调整正式模型参数", text)


    def test_data_health_summarizes_quote_gap_review_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(root / "outputs" / "us_universe" / "latest_run_summary.md", "# US Weekly Screening Run Summary\n")
            write_text(root / "outputs" / "cn_universe" / "latest_run_summary.md", "# CN Weekly Data Summary\n")
            write_text(
                root / "outputs" / "hk_universe" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# HK Weekly Data Summary",
                        "- Candidate count: 2",
                        "- Candidate tickers: AAA, BBB",
                        "- Model audit: outputs/hk_universe/model_audit.md",
                        "- Data health history: outputs/hk_universe/data_health_history.csv",
                        "- Quote gaps: outputs/hk_universe/quote_gaps.csv",
                    ]
                ),
            )
            write_text(root / "outputs" / "hk_universe" / "model_audit.md", "- 审计状态：sample_accumulating\n")
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")
            write_csv(
                root / "outputs" / "hk_universe" / "data_health_history.csv",
                ["run_time", "refresh_status", "quote_coverage_pct", "financial_coverage_pct", "candidate_count"],
                [
                    {
                        "run_time": "2026-06-27 14:05:00",
                        "refresh_status": "online",
                        "quote_coverage_pct": "84.10",
                        "financial_coverage_pct": "99.69",
                        "candidate_count": "2",
                    }
                ],
            )
            write_csv(
                root / "outputs" / "hk_universe" / "quote_gaps.csv",
                ["ticker", "issue_type", "remediation_type", "review_category"],
                [
                    {
                        "ticker": "AAA",
                        "issue_type": "non_positive_metric",
                        "remediation_type": "manual_financial_review",
                        "review_category": "loss_making_or_negative_pe;non_positive_book_value_or_pb",
                    },
                    {
                        "ticker": "BBB",
                        "issue_type": "non_positive_metric",
                        "remediation_type": "manual_financial_review",
                        "review_category": "special_industry_valuation_review",
                    },
                ],
            )

            result = run_self_analysis(root, as_of_date="2026-06-27")
            report = Path(result["output"]).read_text(encoding="utf-8-sig")

            self.assertEqual(
                result["health"][2]["quote_gap_review_categories"],
                "loss_making_or_negative_pe=1;non_positive_book_value_or_pb=1;special_industry_valuation_review=1",
            )
            self.assertIn("loss_making_or_negative_pe=1", report)
            self.assertIn("special_industry_valuation_review=1", report)

    def test_data_health_summarizes_valuation_review_items_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(root / "outputs" / "us_universe" / "latest_run_summary.md", "# US Weekly Screening Run Summary\n")
            write_text(root / "outputs" / "cn_universe" / "latest_run_summary.md", "# CN Weekly Data Summary\n")
            write_text(
                root / "outputs" / "hk_universe" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# HK Weekly Data Summary",
                        "- Candidate count: 2",
                        "- Candidate tickers: AAA, BBB",
                        "- Data health history: outputs/hk_universe/data_health_history.csv",
                    ]
                ),
            )
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")
            write_csv(
                root / "outputs" / "hk_universe" / "data_health_history.csv",
                ["run_time", "refresh_status", "quote_coverage_pct", "financial_coverage_pct", "candidate_count"],
                [
                    {
                        "run_time": "2026-06-27 14:05:00",
                        "refresh_status": "online",
                        "quote_coverage_pct": "100.00",
                        "financial_coverage_pct": "99.69",
                        "candidate_count": "2",
                    }
                ],
            )
            write_csv(
                root / "outputs" / "hk_universe" / "valuation_review_items.csv",
                ["ticker", "company_name", "valuation_review_category", "valuation_review_detail"],
                [
                    {
                        "ticker": "AAA",
                        "company_name": "Alpha",
                        "valuation_review_category": "loss_making_or_negative_pe",
                        "valuation_review_detail": "pe=-3.5",
                    },
                    {
                        "ticker": "BBB",
                        "company_name": "Beta",
                        "valuation_review_category": "loss_making_or_negative_pe;non_positive_book_value_or_pb",
                        "valuation_review_detail": "pe=-1;pb=0",
                    },
                ],
            )

            result = run_self_analysis(root, as_of_date="2026-06-27")
            report = Path(result["output"]).read_text(encoding="utf-8-sig")
            with Path(result["manual_review_queue_output"]).open(
                "r", encoding="utf-8-sig", newline=""
            ) as handle:
                queue_rows = list(csv.DictReader(handle))
            self.assertEqual(queue_rows[0]["as_of_date"], "2026-06-27")

            self.assertEqual(result["health"][2]["valuation_review_item_count"], "2")
            self.assertEqual(
                result["health"][2]["valuation_review_categories"],
                "loss_making_or_negative_pe=2;non_positive_book_value_or_pb=1",
            )
            self.assertEqual(result["health"][2]["valuation_review_samples"][0]["ticker"], "AAA")
            self.assertIn("估值复核清单：2", report)
            self.assertIn("non_positive_book_value_or_pb=1", report)
            self.assertIn("AAA Alpha loss_making_or_negative_pe pe=-3.5", report)
            self.assertNotIn("估值复核待确认：港股周筛 2", report)
            self.assertIn("优先人工复核估值复核清单", report)
            self.assertIn("## 人工复核队列", report)
            self.assertIn("| 港股周筛 | 估值口径 | AAA | Alpha | loss_making_or_negative_pe；pe=-3.5 |", report)
            self.assertTrue(Path(result["manual_review_queue_output"]).exists())
            self.assertEqual(queue_rows[0]["rank"], "1")
            self.assertEqual(queue_rows[1]["rank"], "2")
            self.assertEqual(queue_rows[0]["market"], "港股周筛")
            self.assertEqual(queue_rows[0]["review_type"], "估值口径")
            self.assertEqual(queue_rows[0]["ticker"], "AAA")
            self.assertEqual(queue_rows[0]["review_detail"], "loss_making_or_negative_pe；pe=-3.5")


    def test_manual_review_queue_history_replaces_current_run_and_keeps_prior_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(root / "outputs" / "us_universe" / "latest_run_summary.md", "# US Weekly Screening Run Summary\n")
            write_text(root / "outputs" / "cn_universe" / "latest_run_summary.md", "# CN Weekly Data Summary\n")
            write_text(
                root / "outputs" / "hk_universe" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# HK Weekly Data Summary",
                        "- Candidate count: 2",
                        "- Candidate tickers: AAA, BBB",
                        "- Data health history: outputs/hk_universe/data_health_history.csv",
                    ]
                ),
            )
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")
            write_csv(
                root / "outputs" / "hk_universe" / "data_health_history.csv",
                ["run_time", "refresh_status", "quote_coverage_pct", "financial_coverage_pct", "candidate_count"],
                [
                    {
                        "run_time": "2026-06-27 14:05:00",
                        "refresh_status": "online",
                        "quote_coverage_pct": "100.00",
                        "financial_coverage_pct": "99.69",
                        "candidate_count": "2",
                    }
                ],
            )
            write_csv(
                root / "outputs" / "hk_universe" / "valuation_review_items.csv",
                ["ticker", "company_name", "valuation_review_category", "valuation_review_detail"],
                [
                    {
                        "ticker": "AAA",
                        "company_name": "Alpha",
                        "valuation_review_category": "loss_making_or_negative_pe",
                        "valuation_review_detail": "pe=-3.5",
                    },
                    {
                        "ticker": "BBB",
                        "company_name": "Beta",
                        "valuation_review_category": "non_positive_book_value_or_pb",
                        "valuation_review_detail": "pb=0",
                    },
                ],
            )
            write_csv(
                root / "outputs" / "automation" / "manual_review_queue_history.csv",
                ["as_of_date", "rank", "market", "review_type", "ticker", "company", "review_detail"],
                [
                    {
                        "as_of_date": "2026-06-20",
                        "rank": "1",
                        "market": "US",
                        "review_type": "risk",
                        "ticker": "OLD",
                        "company": "Old Co",
                        "review_detail": "keep older week",
                    },
                    {
                        "as_of_date": "2026-06-27",
                        "rank": "1",
                        "market": "HK",
                        "review_type": "stale",
                        "ticker": "STALE",
                        "company": "Stale Co",
                        "review_detail": "replace same date",
                    },
                ],
            )

            result = run_self_analysis(root, as_of_date="2026-06-27")
            with Path(result["manual_review_history_output"]).open(
                "r", encoding="utf-8-sig", newline=""
            ) as handle:
                history_rows = list(csv.DictReader(handle))

            self.assertEqual([row["as_of_date"] for row in history_rows], ["2026-06-20", "2026-06-27", "2026-06-27"])
            self.assertEqual([row["ticker"] for row in history_rows], ["OLD", "AAA", "BBB"])
            self.assertEqual(history_rows[1]["rank"], "1")
            self.assertEqual(history_rows[2]["rank"], "2")

    def test_self_analysis_skips_closed_manual_review_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(root / "outputs" / "us_universe" / "latest_run_summary.md", "# US Weekly Screening Run Summary\n")
            write_text(root / "outputs" / "cn_universe" / "latest_run_summary.md", "# CN Weekly Data Summary\n")
            write_text(
                root / "outputs" / "hk_universe" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# HK Weekly Data Summary",
                        "- Candidate count: 2",
                        "- Candidate tickers: AAA, BBB",
                        "- Data health history: outputs/hk_universe/data_health_history.csv",
                    ]
                ),
            )
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")
            write_csv(
                root / "outputs" / "hk_universe" / "data_health_history.csv",
                ["run_time", "refresh_status", "quote_coverage_pct", "financial_coverage_pct", "candidate_count"],
                [
                    {
                        "run_time": "2026-06-27 14:05:00",
                        "refresh_status": "online",
                        "quote_coverage_pct": "100.00",
                        "financial_coverage_pct": "99.69",
                        "candidate_count": "2",
                    }
                ],
            )
            write_csv(
                root / "outputs" / "hk_universe" / "valuation_review_items.csv",
                ["ticker", "company_name", "valuation_review_category", "valuation_review_detail"],
                [
                    {
                        "ticker": "AAA",
                        "company_name": "Alpha",
                        "valuation_review_category": "loss_making_or_negative_pe",
                        "valuation_review_detail": "pe=-3.5",
                    },
                    {
                        "ticker": "BBB",
                        "company_name": "Beta",
                        "valuation_review_category": "non_positive_book_value_or_pb",
                        "valuation_review_detail": "pb=0",
                    },
                ],
            )
            write_csv(
                root / "outputs" / "automation" / "manual_review_decisions.csv",
                [
                    "as_of_date",
                    "market",
                    "review_type",
                    "ticker",
                    "company",
                    "decision_status",
                    "decision_note",
                    "reviewer",
                    "decided_at",
                ],
                [
                    {
                        "as_of_date": "2026-06-20",
                        "market": "港股周筛",
                        "review_type": "估值口径",
                        "ticker": "AAA",
                        "company": "Alpha",
                        "decision_status": "accepted",
                        "decision_note": "口径已确认。",
                        "reviewer": "ck",
                        "decided_at": "2026-06-20T15:00:00",
                    },
                    {
                        "as_of_date": "2026-06-20",
                        "market": "港股周筛",
                        "review_type": "估值口径",
                        "ticker": "BBB",
                        "company": "Beta",
                        "decision_status": "needs_more_data",
                        "decision_note": "继续补证据。",
                        "reviewer": "ck",
                        "decided_at": "2026-06-20T15:05:00",
                    },
                ],
            )

            result = run_self_analysis(root, as_of_date="2026-06-27")
            with Path(result["manual_review_queue_output"]).open(
                "r", encoding="utf-8-sig", newline=""
            ) as handle:
                queue_rows = list(csv.DictReader(handle))
            with Path(result["manifest_output"]).open("r", encoding="utf-8-sig") as handle:
                manifest = json.load(handle)

            self.assertEqual([row["ticker"] for row in queue_rows], ["BBB"])
            self.assertEqual(queue_rows[0]["rank"], "1")
            self.assertEqual(manifest["manual_review_queue_count"], 1)

    def test_self_analysis_flags_manual_review_items_seen_in_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(root / "outputs" / "us_universe" / "latest_run_summary.md", "# US Weekly Screening Run Summary\n")
            write_text(root / "outputs" / "cn_universe" / "latest_run_summary.md", "# CN Weekly Data Summary\n")
            write_text(
                root / "outputs" / "hk_universe" / "latest_run_summary.md",
                "\n".join(
                    [
                        "# HK Weekly Data Summary",
                        "- Candidate count: 1",
                        "- Candidate tickers: AAA",
                        "- Data health history: outputs/hk_universe/data_health_history.csv",
                    ]
                ),
            )
            write_text(root / "outputs" / "automation" / "latest_backtest_summary.md", "# Backtest\n")
            write_csv(
                root / "outputs" / "hk_universe" / "data_health_history.csv",
                ["run_time", "refresh_status", "quote_coverage_pct", "financial_coverage_pct", "candidate_count"],
                [
                    {
                        "run_time": "2026-06-27 14:05:00",
                        "refresh_status": "online",
                        "quote_coverage_pct": "100.00",
                        "financial_coverage_pct": "99.69",
                        "candidate_count": "1",
                    }
                ],
            )
            write_csv(
                root / "outputs" / "hk_universe" / "valuation_review_items.csv",
                ["ticker", "company_name", "valuation_review_category", "valuation_review_detail"],
                [
                    {
                        "ticker": "AAA",
                        "company_name": "Alpha",
                        "valuation_review_category": "loss_making_or_negative_pe",
                        "valuation_review_detail": "pe=-3.5",
                    }
                ],
            )
            write_csv(
                root / "outputs" / "automation" / "manual_review_queue_history.csv",
                ["as_of_date", "rank", "market", "review_type", "ticker", "company", "review_detail"],
                [
                    {
                        "as_of_date": "2026-06-20",
                        "rank": "1",
                        "market": "HK",
                        "review_type": "valuation_review",
                        "ticker": "AAA",
                        "company": "Alpha",
                        "review_detail": "loss_making_or_negative_pe锛沺e=-4.0",
                    }
                ],
            )

            result = run_self_analysis(root, as_of_date="2026-06-27")
            report = Path(result["output"]).read_text(encoding="utf-8-sig")
            with Path(result["manual_review_repeats_output"]).open(
                "r", encoding="utf-8-sig", newline=""
            ) as handle:
                repeat_rows = list(csv.DictReader(handle))
            manifest = json.loads(Path(result["manifest_output"]).read_text(encoding="utf-8-sig"))

            self.assertEqual(result["manual_review_history_repeats"][0]["ticker"], "AAA")
            self.assertEqual(result["manual_review_history_repeats"][0]["previous_count"], 1)
            self.assertEqual(manifest["as_of_date"], "2026-06-27")
            self.assertEqual(manifest["review_status"], "recurring_manual_review")
            self.assertEqual(manifest["recommended_next_action"], "review_recurring_items")
            self.assertEqual(manifest["manual_review_queue_count"], 1)
            self.assertEqual(manifest["manual_review_repeat_count"], 1)
            self.assertTrue(manifest["outputs"]["manual_review_repeats"].endswith("manual_review_repeats.csv"))
            self.assertEqual(repeat_rows[0]["as_of_date"], "2026-06-27")
            self.assertEqual(repeat_rows[0]["ticker"], "AAA")
            self.assertEqual(repeat_rows[0]["previous_count"], "1")
            self.assertEqual(repeat_rows[0]["previous_dates"], "2026-06-20")
            self.assertIn("AAA", report)
            self.assertIn("2026-06-20", report)


if __name__ == "__main__":
    unittest.main()
