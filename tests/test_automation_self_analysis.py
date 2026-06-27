import csv
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
            self.assertIn("数据健康需关注：A股周筛 行情缺口 2", report)

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
            self.assertIn("数据健康需关注：港股周筛 估值口径复核 1", report)

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
                    ]
                ),
            )

            result = run_self_analysis(root, as_of_date="2026-06-25")

            output = Path(result["output"])
            text = output.read_text(encoding="utf-8-sig")
            self.assertTrue(output.exists())
            self.assertIn("每周自我分析摘要", text)
            self.assertIn("美股周筛", text)
            self.assertIn("候选数：2", text)
            self.assertIn("成员证据 verified：35/40 (87.5%)", text)
            self.assertIn("弱证据行：5", text)
            self.assertIn("继续补充历史成分 verified 证据", text)

    def test_missing_inputs_are_reported_without_failing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_self_analysis(Path(tmp), as_of_date="2026-06-25")
            text = Path(result["output"]).read_text(encoding="utf-8-sig")

            self.assertIn("缺失摘要", text)
            self.assertIn("先补齐缺失的周筛或回测摘要", text)

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
            self.assertTrue((root / "outputs" / "automation" / "latest_manual_review_queue.csv").exists())


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
            self.assertIn("估值复核待确认：港股周筛 2", report)
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

            self.assertEqual(result["manual_review_history_repeats"][0]["ticker"], "AAA")
            self.assertEqual(result["manual_review_history_repeats"][0]["previous_count"], 1)
            self.assertEqual(repeat_rows[0]["as_of_date"], "2026-06-27")
            self.assertEqual(repeat_rows[0]["ticker"], "AAA")
            self.assertEqual(repeat_rows[0]["previous_count"], "1")
            self.assertEqual(repeat_rows[0]["previous_dates"], "2026-06-20")
            self.assertIn("AAA", report)
            self.assertIn("2026-06-20", report)


if __name__ == "__main__":
    unittest.main()
