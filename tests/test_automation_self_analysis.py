import csv
import tempfile
import unittest
from pathlib import Path

from automation_self_analysis import run_self_analysis


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
            self.assertIn("| A股周筛 | ready | online | 92.67% | 100.00% | 7 |", text)
            self.assertIn("| 港股周筛 | ready | cache_fallback | 84.10% | 99.69% | 35 |", text)
            self.assertIn("数据健康需关注：A股周筛 行情覆盖 92.67%", text)
            self.assertIn("数据健康需关注：港股周筛 刷新状态 cache_fallback", text)
            self.assertIn("数据健康需关注：港股周筛 行情覆盖 84.10%", text)
            self.assertIn("数据健康异常先人工复核，不自动修改正式模型参数", text)


if __name__ == "__main__":
    unittest.main()
