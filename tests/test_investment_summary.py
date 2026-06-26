import csv
import tempfile
import unittest
from pathlib import Path

from investment_summary import generate_investment_summary


def write_csv(path, fieldnames, rows):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class InvestmentSummaryTests(unittest.TestCase):
    def test_generates_latest_investment_summary_with_lifecycle_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidate_pool.csv"
            valuations = root / "valuation_targets.csv"
            tracking = root / "tracking_snapshot.csv"
            forecast_history = root / "forecast_history.csv"
            model_audit = root / "model_audit.md"
            output = root / "latest_investment_summary.md"

            write_csv(
                candidates,
                [
                    "market",
                    "ticker",
                    "company_name",
                    "industry",
                    "total_score",
                    "grade",
                    "reason",
                    "risk_flag",
                    "data_quality_status",
                ],
                [
                    {
                        "market": "美股",
                        "ticker": "AAA",
                        "company_name": "Alpha Inc.",
                        "industry": "信息技术",
                        "total_score": "92",
                        "grade": "A",
                        "reason": "PE低于行业中位数；自由现金流为正",
                        "risk_flag": "无",
                        "data_quality_status": "ok",
                    },
                    {
                        "market": "美股",
                        "ticker": "BBB",
                        "company_name": "Beta Inc.",
                        "industry": "金融",
                        "total_score": "88",
                        "grade": "B",
                        "reason": "PB低于行业中位数",
                        "risk_flag": "无",
                        "data_quality_status": "ok",
                    },
                ],
            )
            write_csv(
                valuations,
                [
                    "market",
                    "ticker",
                    "company_name",
                    "currency",
                    "current_price",
                    "buy_price",
                    "target_price",
                    "expected_return",
                    "price_action",
                    "trend_label",
                    "valuation_confidence",
                    "reason",
                    "price_date",
                    "generated_date",
                    "model_version",
                ],
                [
                    {
                        "market": "美股",
                        "ticker": "AAA",
                        "company_name": "Alpha Inc.",
                        "currency": "USD",
                        "current_price": "100",
                        "buy_price": "112",
                        "target_price": "160",
                        "expected_return": "0.6",
                        "price_action": "达到建议买入区间",
                        "trend_label": "偏弱",
                        "valuation_confidence": "low",
                        "reason": "混合估值目标价 160",
                        "price_date": "2026-06-27",
                        "generated_date": "2026-06-27",
                        "model_version": "valuation_trend_v1",
                    },
                    {
                        "market": "美股",
                        "ticker": "BBB",
                        "company_name": "Beta Inc.",
                        "currency": "USD",
                        "current_price": "50",
                        "buy_price": "48",
                        "target_price": "65",
                        "expected_return": "0.3",
                        "price_action": "等待更好买点",
                        "trend_label": "中性",
                        "valuation_confidence": "low",
                        "reason": "混合估值目标价 65",
                        "price_date": "2026-06-27",
                        "generated_date": "2026-06-27",
                        "model_version": "valuation_trend_v1",
                    },
                ],
            )
            write_csv(
                tracking,
                ["ticker", "evaluation_status", "actual_return", "excess_return"],
                [
                    {
                        "ticker": "AAA",
                        "evaluation_status": "tracking",
                        "actual_return": "0.05",
                        "excess_return": "0.02",
                    }
                ],
            )
            write_csv(
                forecast_history,
                ["ticker", "generated_date", "model_version"],
                [
                    {"ticker": "AAA", "generated_date": "2026-06-20", "model_version": "valuation_trend_v1"},
                    {"ticker": "OLD", "generated_date": "2026-06-20", "model_version": "valuation_trend_v1"},
                    {"ticker": "AAA", "generated_date": "2026-06-27", "model_version": "valuation_trend_v1"},
                    {"ticker": "BBB", "generated_date": "2026-06-27", "model_version": "valuation_trend_v1"},
                ],
            )
            model_audit.write_text(
                "# 模型审计报告\n\n- 审计状态：sample_accumulating\n- 结论：样本积累中，不生成参数升级建议。\n",
                encoding="utf-8-sig",
            )

            result = generate_investment_summary(
                candidates,
                valuations,
                tracking,
                forecast_history,
                model_audit,
                output,
            )

            report = output.read_text(encoding="utf-8-sig")
            self.assertEqual(result["candidate_count"], 2)
            self.assertIn("# 每周低估公司结论", report)
            self.assertIn("- 候选公司数量：2", report)
            self.assertIn("- 模型审计状态：sample_accumulating", report)
            self.assertIn("| AAA | Alpha Inc. | A | 92.0 | USD 100.00 | USD 112.00 | USD 160.00 | 60.0% | 达到建议买入区间 |", report)
            self.assertIn("## 新入选", report)
            self.assertIn("BBB", report)
            self.assertIn("## 连续入选", report)
            self.assertIn("AAA", report)
            self.assertIn("## 本周剔除", report)
            self.assertIn("OLD", report)
            self.assertIn("仅供研究筛选，不构成投资建议。", report)


if __name__ == "__main__":
    unittest.main()
