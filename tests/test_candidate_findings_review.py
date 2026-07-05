import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# 每周低估公司结论",
                "",
                "- 生成日期：2026-06-28",
                "- 市场：测试市场",
                "- 候选公司数量：2",
                "",
                "## 候选风险说明",
                "",
                "| 股票 | 公司 | 风险说明 |",
                "|---|---|---|",
                "| AAA | Alpha Inc | 无 |",
                "| BBB | Beta Inc | 当前无安全边际；预期收益为负 |",
                "",
                "## 候选结论质量检查",
                "",
                "- 字段完整：2/2",
                "- 当前候选结论字段完整。",
                "",
            ]
        ),
        encoding="utf-8-sig",
    )


def write_fixture(root):
    market_dir = root / "outputs" / "test_universe"
    fields = [
        "market",
        "ticker",
        "company_name",
        "currency",
        "current_price",
        "target_price",
        "buy_price",
        "expected_return",
        "trend_label",
        "trend_confidence",
        "one_week_trend_label",
        "one_week_trend_confidence",
        "one_week_expected_direction",
        "one_month_trend_label",
        "one_month_trend_confidence",
        "one_month_expected_direction",
        "valuation_confidence",
        "valuation_status",
        "price_action",
        "reason",
        "price_date",
        "financial_report_date",
        "generated_date",
        "model_version",
    ]
    write_csv(
        market_dir / "valuation_targets.csv",
        [
            {
                "market": "测试市场",
                "ticker": "AAA",
                "company_name": "Alpha Inc",
                "currency": "USD",
                "current_price": "10",
                "target_price": "16",
                "buy_price": "12",
                "expected_return": "0.6",
                "trend_label": "中性",
                "trend_confidence": "high",
                "one_week_trend_label": "偏弱",
                "one_week_trend_confidence": "high",
                "one_week_expected_direction": "下行",
                "one_month_trend_label": "中性",
                "one_month_trend_confidence": "high",
                "one_month_expected_direction": "震荡",
                "valuation_confidence": "high",
                "valuation_status": "ready",
                "price_action": "达到建议买入区间",
                "reason": "混合估值目标价 16；安全边际 20%；走势 中性；估值置信度 high",
                "price_date": "2026-06-26",
                "financial_report_date": "2026-03-31",
                "generated_date": "2026-06-28",
                "model_version": "valuation_trend_v1",
            },
            {
                "market": "测试市场",
                "ticker": "BBB",
                "company_name": "Beta Inc",
                "currency": "USD",
                "current_price": "20",
                "target_price": "12",
                "buy_price": "10",
                "expected_return": "-0.4",
                "trend_label": "偏弱",
                "trend_confidence": "low",
                "one_week_trend_label": "偏弱",
                "one_week_trend_confidence": "low",
                "one_week_expected_direction": "下行",
                "one_month_trend_label": "偏弱",
                "one_month_trend_confidence": "low",
                "one_month_expected_direction": "下行",
                "valuation_confidence": "low",
                "valuation_status": "ready",
                "price_action": "等待回调/当前无安全边际",
                "reason": "混合估值目标价 12；安全边际 20%；走势 偏弱；估值置信度 low",
                "price_date": "2026-06-26",
                "financial_report_date": "2026-03-31",
                "generated_date": "2026-06-28",
                "model_version": "valuation_trend_v1",
            },
        ],
        fields,
    )
    write_summary(market_dir / "latest_investment_summary.md")
    return market_dir


class CandidateFindingsReviewTests(unittest.TestCase):
    def test_builds_review_from_valuation_targets_and_risk_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            market_dir = write_fixture(Path(tmp))

            from candidate_findings_review import (
                build_candidate_findings_review,
                render_candidate_findings_review,
            )

            payload = build_candidate_findings_review(
                [{"name": "测试市场", "path": market_dir}]
            )
            report = render_candidate_findings_review(payload)

            self.assertEqual(payload["review_schema"], "candidate_findings_review")
            self.assertEqual(payload["review_version"], 1)
            self.assertEqual(payload["as_of_date"], "2026-06-28")
            self.assertEqual(payload["status"], "manual_review_needed")
            self.assertEqual(payload["candidate_count"], 2)
            self.assertEqual(payload["field_complete_count"], 2)
            self.assertEqual(payload["missing_field_count"], 0)
            self.assertEqual(payload["risk_coverage_count"], 2)
            self.assertEqual(payload["risk_review_count"], 1)
            self.assertEqual(payload["risk_classified_count"], 1)
            self.assertEqual(payload["risk_unclassified_count"], 0)
            self.assertEqual(payload["risk_action_required_count"], 1)
            self.assertEqual(payload["risk_action_queue_count"], 1)
            self.assertEqual(payload["risk_action_unqueued_count"], 0)
            self.assertEqual(payload["risk_action_queue_by_action"], {"defer_research": 1})
            self.assertEqual(payload["risk_category_counts"]["negative_expected_return"], 1)
            self.assertEqual(payload["risk_category_counts"]["no_margin_of_safety"], 1)
            self.assertEqual(payload["negative_return_count"], 1)
            self.assertEqual(payload["weak_trend_count"], 1)
            self.assertEqual(payload["low_confidence_count"], 1)
            self.assertFalse(payload["formal_model_change_allowed"])
            market = payload["markets"][0]
            self.assertEqual(market["risk_classified_count"], 1)
            self.assertEqual(market["risk_unclassified_count"], 0)
            self.assertEqual(market["risk_action_required_count"], 1)
            self.assertEqual(market["risk_action_queue_count"], 1)
            self.assertEqual(market["risk_action_unqueued_count"], 0)
            self.assertEqual(market["risk_action_queue"][0]["ticker"], "BBB")
            self.assertEqual(market["risk_action_queue"][0]["queue_action"], "defer_research")
            self.assertEqual(
                market["risk_items"][0]["risk_categories"],
                [
                    "no_margin_of_safety",
                    "negative_expected_return",
                    "weak_trend",
                    "low_valuation_confidence",
                ],
            )
            self.assertEqual(market["risk_items"][0]["recommended_action"], "deprioritize_or_wait")

            self.assertIn("# 候选解释复核结论", report)
            self.assertIn("manual_review_needed", report)
            self.assertIn("BBB", report)
            self.assertIn("risk_action_required_count", report)
            self.assertIn("risk_action_queue_count", report)
            self.assertIn("risk_action_queue_by_action", report)
            self.assertIn("当前无安全边际", report)
            self.assertIn("不重新评分", report)
            self.assertIn("不修改正式模型参数", report)

    def test_cli_writes_json_and_markdown_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            market_dir = write_fixture(root)
            output = root / "outputs" / "automation" / "latest_candidate_findings_review.json"
            report = root / "outputs" / "automation" / "latest_candidate_findings_review.md"

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "candidate_findings_review.py"),
                    "--market",
                    f"测试市场={market_dir}",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            combined = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, combined)
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["status"], "manual_review_needed")
            self.assertFalse(payload["formal_model_change_allowed"])
            self.assertIn("候选解释复核结论", report.read_text(encoding="utf-8-sig"))
            self.assertIn("latest_candidate_findings_review.md", combined)

    def test_powershell_wrapper_and_bundle_include_candidate_findings_review(self):
        wrapper = (PROJECT_ROOT / "scripts" / "run_candidate_findings_review.ps1").read_text(
            encoding="utf-8-sig"
        )
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("candidate_findings_review.py", wrapper)
        self.assertIn("latest_candidate_findings_review.json", wrapper)
        self.assertIn("latest_candidate_findings_review.md", wrapper)
        self.assertIn("run_candidate_findings_review", bundle)
        self.assertLess(
            bundle.index("run_backtest_evidence_review"),
            bundle.index("run_candidate_findings_review"),
        )
        self.assertLess(
            bundle.index("run_candidate_findings_review"),
            bundle.index("show_weekly_action_items"),
        )


if __name__ == "__main__":
    unittest.main()
