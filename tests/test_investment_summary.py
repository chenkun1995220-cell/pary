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
    def test_generates_candidate_risk_explanations_when_risk_flag_is_missing(self):
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
                    "total_score",
                    "grade",
                    "reason",
                    "data_quality_status",
                    "financial_data_status",
                    "debt_to_assets",
                    "current_ratio",
                    "revenue_growth",
                    "net_income_growth",
                ],
                [
                    {
                        "market": "A股",
                        "ticker": "AAA",
                        "company_name": "Alpha",
                        "total_score": "90",
                        "grade": "A",
                        "reason": "PE低于行业中位数；ROE稳健；经营现金流为正",
                        "data_quality_status": "ready",
                        "financial_data_status": "ready",
                        "debt_to_assets": "0.20",
                        "current_ratio": "2.5",
                        "revenue_growth": "0.12",
                        "net_income_growth": "0.18",
                    },
                    {
                        "market": "A股",
                        "ticker": "BBB",
                        "company_name": "Beta",
                        "total_score": "82",
                        "grade": "B",
                        "reason": "PB低于行业中位数；资产负债率可控",
                        "data_quality_status": "ready",
                        "financial_data_status": "ready",
                        "debt_to_assets": "0.72",
                        "current_ratio": "0.80",
                        "revenue_growth": "-0.10",
                        "net_income_growth": "-0.22",
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
                    "generated_date",
                    "model_version",
                ],
                [
                    {
                        "market": "A股",
                        "ticker": "AAA",
                        "company_name": "Alpha",
                        "currency": "CNY",
                        "current_price": "10",
                        "buy_price": "9",
                        "target_price": "14",
                        "expected_return": "0.4",
                        "price_action": "达到建议买入区间",
                        "trend_label": "中性",
                        "valuation_confidence": "high",
                        "reason": "混合估值目标价 14",
                        "generated_date": "2026-06-27",
                        "model_version": "valuation_trend_v1",
                    },
                    {
                        "market": "A股",
                        "ticker": "BBB",
                        "company_name": "Beta",
                        "currency": "CNY",
                        "current_price": "30",
                        "buy_price": "22",
                        "target_price": "28",
                        "expected_return": "-0.05",
                        "price_action": "等待回调/当前无安全边际",
                        "trend_label": "偏弱",
                        "valuation_confidence": "low",
                        "reason": "混合估值目标价 28",
                        "generated_date": "2026-06-27",
                        "model_version": "valuation_trend_v1",
                    },
                ],
            )
            write_csv(
                tracking,
                ["ticker", "evaluation_status"],
                [
                    {"ticker": "AAA", "evaluation_status": "tracking"},
                    {"ticker": "BBB", "evaluation_status": "tracking"},
                ],
            )
            write_csv(forecast_history, ["ticker", "generated_date", "model_version"], [])
            model_audit.write_text("- 审计状态：sample_accumulating\n- 结论：样本积累中\n", encoding="utf-8-sig")

            generate_investment_summary(
                candidates,
                valuations,
                tracking,
                forecast_history,
                model_audit,
                output,
            )

            report = output.read_text(encoding="utf-8-sig")
            self.assertIn("## 候选风险说明", report)
            self.assertIn("| AAA | Alpha | 未发现量化硬性风险", report)
            self.assertIn("| BBB | Beta | 估值置信度低", report)
            self.assertIn("当前无安全边际", report)
            self.assertIn("走势偏弱", report)
            self.assertIn("资产负债率偏高", report)
            self.assertIn("流动比率低于1", report)
            self.assertIn("收入增长为负", report)
            self.assertIn("净利润增长为负", report)
            self.assertIn("- 字段完整：2/2", report)

    def test_flags_candidate_conclusion_quality_gaps(self):
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
                    "total_score",
                    "grade",
                    "reason",
                    "risk_flag",
                    "data_quality_status",
                    "financial_data_status",
                ],
                [
                    {
                        "market": "A股",
                        "ticker": "AAA",
                        "company_name": "Alpha",
                        "total_score": "90",
                        "grade": "A",
                        "reason": "PE低于行业中位数；ROE稳健；经营现金流为正",
                        "risk_flag": "无重大风险",
                        "data_quality_status": "ready",
                        "financial_data_status": "ready",
                    },
                    {
                        "market": "A股",
                        "ticker": "BBB",
                        "company_name": "Beta",
                        "total_score": "85",
                        "grade": "A",
                        "reason": "",
                        "risk_flag": "",
                        "data_quality_status": "ready",
                        "financial_data_status": "ready",
                    },
                    {
                        "market": "A股",
                        "ticker": "CCC",
                        "company_name": "Gamma",
                        "total_score": "80",
                        "grade": "B",
                        "reason": "PB低于行业中位数；资产负债率可控",
                        "risk_flag": "周期波动",
                        "data_quality_status": "",
                        "financial_data_status": "missing",
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
                    "generated_date",
                    "model_version",
                ],
                [
                    {
                        "market": "A股",
                        "ticker": "AAA",
                        "company_name": "Alpha",
                        "currency": "CNY",
                        "current_price": "10",
                        "buy_price": "9",
                        "target_price": "14",
                        "expected_return": "0.4",
                        "price_action": "达到建议买入区间",
                        "trend_label": "中性",
                        "valuation_confidence": "high",
                        "reason": "混合估值目标价 14",
                        "generated_date": "2026-06-27",
                        "model_version": "valuation_trend_v1",
                    },
                    {
                        "market": "A股",
                        "ticker": "BBB",
                        "company_name": "Beta",
                        "currency": "CNY",
                        "current_price": "20",
                        "buy_price": "18",
                        "target_price": "28",
                        "expected_return": "0.4",
                        "price_action": "达到建议买入区间",
                        "trend_label": "中性",
                        "valuation_confidence": "high",
                        "reason": "",
                        "generated_date": "2026-06-27",
                        "model_version": "valuation_trend_v1",
                    },
                    {
                        "market": "A股",
                        "ticker": "CCC",
                        "company_name": "Gamma",
                        "currency": "CNY",
                        "current_price": "30",
                        "buy_price": "",
                        "target_price": "",
                        "expected_return": "",
                        "price_action": "数据不足",
                        "trend_label": "",
                        "valuation_confidence": "low",
                        "reason": "缺少估值目标价",
                        "generated_date": "2026-06-27",
                        "model_version": "valuation_trend_v1",
                    },
                ],
            )
            write_csv(
                tracking,
                ["ticker", "evaluation_status"],
                [{"ticker": "AAA", "evaluation_status": "tracking"}],
            )
            write_csv(forecast_history, ["ticker", "generated_date", "model_version"], [])
            model_audit.write_text("- 审计状态：sample_accumulating\n- 结论：样本积累中\n", encoding="utf-8-sig")

            generate_investment_summary(
                candidates,
                valuations,
                tracking,
                forecast_history,
                model_audit,
                output,
            )

            report = output.read_text(encoding="utf-8-sig")
            self.assertIn("## 候选结论质量检查", report)
            self.assertIn("- 字段完整：1/3", report)
            self.assertIn("| BBB | Beta | 理由不足、数据不足 |", report)
            self.assertIn("| CCC | Gamma | 数据不足 |", report)
            self.assertIn("缺少低估依据", report)
            self.assertIn("缺少跟踪状态", report)
            self.assertIn("缺少数据质量说明", report)
            self.assertIn("缺少建议买入价", report)
            self.assertIn("缺少目标价", report)

    def test_includes_data_health_summary_when_inputs_are_provided(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidate_pool.csv"
            valuations = root / "valuation_targets.csv"
            tracking = root / "tracking_snapshot.csv"
            forecast_history = root / "forecast_history.csv"
            model_audit = root / "model_audit.md"
            quote_gaps = root / "quote_gaps.csv"
            data_quality_issues = root / "data_quality_issues.csv"
            share_override_audit = root / "share_override_audit.csv"
            output = root / "latest_investment_summary.md"

            write_csv(
                candidates,
                ["market", "ticker", "company_name", "total_score", "grade", "reason"],
                [{"market": "美股", "ticker": "AAA", "company_name": "Alpha", "total_score": "90", "grade": "A", "reason": "低估"}],
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
                    "generated_date",
                    "model_version",
                ],
                [
                    {
                        "market": "美股",
                        "ticker": "AAA",
                        "company_name": "Alpha",
                        "currency": "USD",
                        "current_price": "100",
                        "buy_price": "90",
                        "target_price": "130",
                        "expected_return": "0.3",
                        "price_action": "达到建议买入区间",
                        "trend_label": "中性",
                        "valuation_confidence": "low",
                        "reason": "估值低",
                        "generated_date": "2026-06-27",
                        "model_version": "valuation_trend_v1",
                    }
                ],
            )
            write_csv(tracking, ["ticker", "evaluation_status"], [])
            write_csv(forecast_history, ["ticker", "generated_date", "model_version"], [])
            model_audit.write_text("- 审计状态：sample_accumulating\n- 结论：样本积累中\n", encoding="utf-8-sig")
            write_csv(
                quote_gaps,
                ["ticker", "status", "missing_fields", "ready_field_count", "total_required_field_count"],
                [
                    {"ticker": "AAA", "status": "ready", "missing_fields": "", "ready_field_count": "9", "total_required_field_count": "9"},
                    {"ticker": "BRK-B", "status": "manual_override_applied", "missing_fields": "", "ready_field_count": "9", "total_required_field_count": "9"},
                ],
            )
            write_csv(
                data_quality_issues,
                ["severity", "issue_code", "ticker", "review_action", "impact_on_score", "recommended_handling"],
                [
                    {
                        "severity": "警告",
                        "issue_code": "percentage_unit_suspect",
                        "ticker": "AAA",
                        "review_action": "复核源字段",
                        "impact_on_score": "可能影响盈利质量和估值倍数",
                        "recommended_handling": "核对 gross_margin 原始口径，确认后再参与估值",
                    },
                    {
                        "severity": "警告",
                        "issue_code": "percentage_unit_suspect",
                        "ticker": "BBB",
                        "review_action": "复核源字段",
                        "impact_on_score": "可能影响盈利质量和估值倍数",
                        "recommended_handling": "核对 gross_margin 原始口径，确认后再参与估值",
                    },
                    {
                        "severity": "阻断",
                        "issue_code": "missing_required_field",
                        "ticker": "BAD",
                        "review_action": "补齐必填字段",
                        "impact_on_score": "阻断评分",
                        "recommended_handling": "补齐必填字段后重新筛选",
                    },
                    {
                        "severity": "提示",
                        "issue_code": "industry_sample_too_small",
                        "ticker": "CCC",
                        "review_action": "观察",
                        "impact_on_score": "不直接影响评分",
                        "recommended_handling": "继续积累行业样本",
                    },
                ],
            )
            write_csv(
                share_override_audit,
                ["ticker", "status", "age_days"],
                [{"ticker": "BRK-B", "status": "current", "age_days": "74"}],
            )

            generate_investment_summary(
                candidates,
                valuations,
                tracking,
                forecast_history,
                model_audit,
                output,
                quote_gaps_path=quote_gaps,
                data_quality_issues_path=data_quality_issues,
                share_override_audit_path=share_override_audit,
            )

            report = output.read_text(encoding="utf-8-sig")
            self.assertIn("## 数据健康", report)
            self.assertIn("行情覆盖：2/2 (100.00%)", report)
            self.assertIn("人工覆盖：1 项，需复核 0 项", report)
            self.assertIn("数据质量问题：4 项（阻断 1，警告 2）", report)
            self.assertIn("阻断：missing_required_field 1 项，影响 1 只（BAD）", report)
            self.assertIn("需复核：percentage_unit_suspect 2 项，影响 2 只（AAA、BBB）", report)
            self.assertIn("可接受：industry_sample_too_small 1 项，影响 1 只（CCC）", report)
            self.assertIn("## 数据风险处置建议", report)
            self.assertIn("percentage_unit_suspect：复核源字段；可能影响盈利质量和估值倍数；核对 gross_margin 原始口径，确认后再参与估值", report)
            self.assertIn("missing_required_field：补齐必填字段；阻断评分；补齐必填字段后重新筛选", report)
            self.assertIn("## 候选公司数据质量影响", report)
            self.assertIn("- 受影响候选：1/1", report)
            self.assertIn("| AAA | percentage_unit_suspect | 复核源字段 | 可能影响盈利质量和估值倍数 |", report)

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
