import tempfile
import unittest
from pathlib import Path

from automation_self_analysis import run_self_analysis


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig")


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


if __name__ == "__main__":
    unittest.main()
