import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig")


def write_json(path, payload):
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_manual_review_queue(root):
    write_csv(
        Path(root) / "outputs" / "automation" / "latest_manual_review_queue.csv",
        [
            {
                "as_of_date": "2026-06-28",
                "rank": "1",
                "market": "A股周筛",
                "review_type": "估值口径",
                "ticker": "300122.SZ",
                "company": "智飞生物",
                "review_detail": "loss_making_or_negative_pe；pe=-17.54",
            },
            {
                "as_of_date": "2026-06-28",
                "rank": "2",
                "market": "港股周筛",
                "review_type": "风险提示",
                "ticker": "01548.HK",
                "company": "GENSCRIPT BIO",
                "review_detail": "估值置信度低；走势偏弱",
            },
        ],
    )


def write_manual_review_decisions(root):
    write_csv(
        Path(root) / "outputs" / "automation" / "manual_review_decisions.csv",
        [
            {
                "as_of_date": "2026-06-28",
                "market": "A股周筛",
                "review_type": "估值口径",
                "ticker": "300122.SZ",
                "company": "智飞生物",
                "decision_status": "accepted",
                "decision_note": "现金流和行业周期仍可解释，保留跟踪。",
                "reviewer": "ck",
                "decided_at": "2026-06-28",
            },
            {
                "as_of_date": "2026-06-28",
                "market": "港股周筛",
                "review_type": "估值口径",
                "ticker": "00000.HK",
                "company": "历史样例",
                "decision_status": "rejected",
                "decision_note": "不属于本周队列，保留历史记录但不计入本周匹配。",
                "reviewer": "ck",
                "decided_at": "2026-06-28",
            },
        ],
    )


def write_manual_review_merge_summary(root):
    write_json(
        Path(root) / "outputs" / "automation" / "latest_manual_review_decision_merge.json",
        {
            "merge_schema": "manual_review_decision_merge",
            "merge_version": 1,
            "template": "outputs/automation/manual_review_decisions_template.csv",
            "decisions": "outputs/automation/manual_review_decisions.csv",
            "merged": 2,
            "skipped_pending": 1,
            "skipped_invalid": 0,
            "row_count": 2,
            "by_status": [
                {"decision_status": "accepted", "count": 1},
                {"decision_status": "rejected", "count": 1},
            ],
        },
    )


def write_market(root, market_dir, ticker, company):
    base = Path(root) / "outputs" / market_dir
    write_text(base / "latest_run_summary.md", "# summary\nCandidate count: 1\n")
    write_csv(
        base / "candidate_pool.csv",
        [{"ticker": ticker, "company": company, "total_score": "82.5"}],
    )
    write_csv(
        base / "valuation_targets.csv",
        [
            {
                "ticker": ticker,
                "target_price": "120.00",
                "buy_price": "96.00",
                "expected_return": "24.5%",
                "trend_label": "uptrend_watch",
                "trend_confidence": "medium",
                "one_week_trend_label": "偏强",
                "one_week_expected_direction": "上行",
                "one_week_trend_confidence": "high",
                "one_month_trend_label": "温和偏强",
                "one_month_expected_direction": "震荡偏强",
                "one_month_trend_confidence": "medium",
                "valuation_confidence": "high",
                "reason": "估值折价且质量分稳定",
            }
        ],
    )
    write_text(base / "valuation_report.md", f"# valuation\n## {ticker}\n估值折价且质量分稳定\n")
    write_text(base / "latest_investment_summary.md", f"# investment\n## {ticker}\n风险：行业景气回落\n")


def write_ready_automation(root, as_of_date="2026-06-28"):
    write_json(
        Path(root) / "outputs" / "automation" / "latest_automation_check.json",
        {"as_of_date": as_of_date, "status": "ready"},
    )
    write_json(
        Path(root) / "outputs" / "automation" / "latest_weekly_ops_check.json",
        {"as_of_date": as_of_date, "status": "ready"},
    )
    write_json(
        Path(root) / "outputs" / "automation" / "latest_weekly_ops_history_summary.json",
        {"latest_as_of_date": as_of_date, "latest_status": "ready"},
    )
    write_json(
        Path(root) / "outputs" / "automation" / "latest_weekly_delivery_history_summary.json",
        {"latest_as_of_date": as_of_date, "latest_status": "ready"},
    )


def write_manual_review_automation(root, as_of_date="2026-06-28"):
    write_json(
        Path(root) / "outputs" / "automation" / "latest_automation_check.json",
        {
            "as_of_date": as_of_date,
            "status": "manual_review_needed",
            "recommended_action": "review_manual_queue",
            "priority_actions": ["review_manual_queue", "review_candidate_findings"],
        },
    )
    write_json(
        Path(root) / "outputs" / "automation" / "latest_weekly_ops_check.json",
        {"as_of_date": as_of_date, "status": "ready"},
    )
    write_json(
        Path(root) / "outputs" / "automation" / "latest_weekly_ops_history_summary.json",
        {"latest_as_of_date": as_of_date, "latest_status": "ready"},
    )
    write_json(
        Path(root) / "outputs" / "automation" / "latest_weekly_delivery_history_summary.json",
        {"latest_as_of_date": as_of_date, "latest_status": "ready"},
    )


def write_three_markets(root):
    write_market(root, "us_universe", "MSFT", "Microsoft")
    write_market(root, "cn_universe", "000300.SZ", "沪深样本")
    write_market(root, "hk_universe", "0700.HK", "腾讯控股")


class WeeklyConclusionReportTests(unittest.TestCase):
    def test_builds_ready_markdown_and_json_from_three_markets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_ready_automation(root)

            from weekly_conclusion_report import build_weekly_conclusion, render_markdown

            payload = build_weekly_conclusion(root, today="2026-06-28")
            markdown = render_markdown(payload)

            self.assertEqual(payload["conclusion_schema"], "weekly_conclusion")
            self.assertEqual(payload["conclusion_version"], 1)
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["recommended_action"], "monitor_next_run")
            self.assertEqual(payload["candidate_count_total"], 3)
            self.assertEqual([market["market"] for market in payload["markets"]], ["US", "CN", "HK"])
            self.assertEqual(payload["candidates"][0]["ticker"], "MSFT")
            self.assertEqual(payload["candidates"][0]["target_price"], "120.00")
            self.assertEqual(payload["candidates"][0]["buy_price"], "96.00")
            self.assertEqual(payload["candidates"][0]["risk_reason"], "行业景气回落")
            self.assertEqual(payload["candidates"][0]["one_week_expected_direction"], "上行")
            self.assertEqual(payload["candidates"][0]["one_month_expected_direction"], "震荡偏强")
            self.assertIn("# 每周低估候选统一结论", markdown)
            self.assertIn("| US | MSFT | Microsoft | 82.5 | 120.00 | 96.00 | 24.5% | uptrend_watch | 上行 / 偏强 | 震荡偏强 / 温和偏强 |", markdown)
            self.assertIn("研究筛选和人工复核用途", markdown)

    def test_adds_candidate_action_tiers_to_weekly_conclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_csv(
                root / "outputs" / "cn_universe" / "valuation_targets.csv",
                [
                    {
                        "ticker": "000300.SZ",
                        "target_price": "90.00",
                        "buy_price": "72.00",
                        "expected_return": "-8.0%",
                        "trend_label": "中性",
                        "trend_confidence": "high",
                        "valuation_confidence": "high",
                        "reason": "安全边际不足",
                    }
                ],
            )
            write_text(
                root / "outputs" / "cn_universe" / "latest_investment_summary.md",
                "# investment\n## 000300.SZ\n风险：当前无安全边际；预期收益为负\n",
            )
            write_csv(
                root / "outputs" / "hk_universe" / "valuation_targets.csv",
                [
                    {
                        "ticker": "0700.HK",
                        "target_price": "520.00",
                        "buy_price": "390.00",
                        "expected_return": "18.0%",
                        "trend_label": "偏弱",
                        "trend_confidence": "low",
                        "valuation_confidence": "low",
                        "reason": "估值有折价但证据弱",
                    }
                ],
            )
            write_text(
                root / "outputs" / "hk_universe" / "latest_investment_summary.md",
                "# investment\n## 0700.HK\n风险：走势偏弱；估值置信度低\n",
            )
            write_ready_automation(root)

            from weekly_conclusion_report import build_weekly_conclusion, render_markdown

            payload = build_weekly_conclusion(root, today="2026-06-28")
            markdown = render_markdown(payload)
            tiers = {candidate["ticker"]: candidate["action_tier"] for candidate in payload["candidates"]}

            self.assertEqual(tiers["MSFT"], "优先研究")
            self.assertEqual(tiers["000300.SZ"], "暂缓研究")
            self.assertEqual(tiers["0700.HK"], "谨慎观察")
            self.assertEqual(payload["candidate_action_summary"]["by_tier"]["优先研究"], 1)
            self.assertEqual(payload["candidate_action_summary"]["by_tier"]["暂缓研究"], 1)
            self.assertEqual(payload["candidate_action_summary"]["by_tier"]["谨慎观察"], 1)
            self.assertIn("## 候选行动分层", markdown)
            self.assertIn("| 优先研究 | 1 | MSFT |", markdown)
            self.assertIn("| 暂缓研究 | 1 | 000300.SZ |", markdown)
            self.assertIn("| 谨慎观察 | 1 | 0700.HK |", markdown)

    def test_missing_required_market_file_marks_needs_attention(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            (root / "outputs" / "hk_universe" / "valuation_targets.csv").unlink()
            write_ready_automation(root)

            from weekly_conclusion_report import build_weekly_conclusion

            payload = build_weekly_conclusion(root, today="2026-06-28")

            self.assertEqual(payload["status"], "needs_attention")
            self.assertIn("outputs/hk_universe/valuation_targets.csv", payload["missing_inputs"])

    def test_us_summary_can_fall_back_to_automation_summary_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            (root / "outputs" / "us_universe" / "latest_run_summary.md").unlink()
            write_text(
                root / "outputs" / "automation" / "latest_run_summary.md",
                "# US Weekly Screening Run Summary\n\n- Candidate count: 1\n",
            )
            write_ready_automation(root)

            from weekly_conclusion_report import build_weekly_conclusion

            payload = build_weekly_conclusion(root, today="2026-06-28")
            us_market = payload["markets"][0]

            self.assertEqual(payload["status"], "ready")
            self.assertEqual(us_market["status"], "ready")
            self.assertNotIn("outputs/us_universe/latest_run_summary.md", payload["missing_inputs"])
            self.assertIn("outputs/automation/latest_run_summary.md", us_market["source_files"])

    def test_manual_review_automation_check_keeps_conclusion_ready_with_review_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_manual_review_automation(root)

            from weekly_conclusion_report import build_weekly_conclusion, render_markdown

            payload = build_weekly_conclusion(root, today="2026-06-28")
            markdown = render_markdown(payload)

            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["recommended_action"], "review_manual_queue")
            self.assertEqual(payload["priority_actions"], ["review_manual_queue", "review_candidate_findings"])
            self.assertEqual(payload["health"]["status"], "needs_review")
            self.assertEqual(payload["health"]["score"], 90)
            self.assertIn("automation_check:manual_review_needed", payload["health"]["reasons"])
            self.assertEqual(payload["priority_action_details"][0]["action"], "review_manual_queue")
            self.assertEqual(payload["priority_action_details"][0]["label"], "复核人工队列")
            self.assertIn("查看本周人工复核队列", payload["priority_action_details"][0]["description"])
            self.assertEqual(payload["automation"]["automation_check"]["status"], "manual_review_needed")
            self.assertEqual(
                payload["automation"]["automation_check"]["priority_actions"],
                ["review_manual_queue", "review_candidate_findings"],
            )
            self.assertEqual(payload["automation"]["weekly_delivery_history"]["status"], "ready")
            self.assertIn("overall_health", markdown)
            self.assertIn("needs_review / 90", markdown)
            self.assertIn("## 优先动作", markdown)
            self.assertIn("weekly_delivery_history", markdown)
            self.assertIn("| review_manual_queue | 复核人工队列 | 查看本周人工复核队列", markdown)
            self.assertIn("| review_candidate_findings | 复核候选结论 | 检查候选公司的风险说明", markdown)
            self.assertIn("- 优先动作：review_manual_queue", markdown)

    def test_delivery_health_actions_have_chinese_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_ready_automation(root)
            write_json(
                root / "outputs" / "automation" / "latest_automation_check.json",
                {
                    "as_of_date": "2026-06-28",
                    "status": "manual_review_needed",
                    "recommended_action": "review_manual_review_backlog",
                    "priority_actions": [
                        "review_manual_review_backlog",
                        "review_delivery_health_issues",
                    ],
                },
            )

            from weekly_conclusion_report import build_weekly_conclusion, render_markdown

            payload = build_weekly_conclusion(root, today="2026-06-28")
            markdown = render_markdown(payload)

            labels = {
                item["action"]: item["label"]
                for item in payload["priority_action_details"]
            }
            self.assertEqual(labels["review_manual_review_backlog"], "处理人工复核积压")
            self.assertEqual(labels["review_delivery_health_issues"], "复查最终交付健康提示")
            self.assertNotIn("未分类动作", markdown)
            self.assertIn("| review_manual_review_backlog | 处理人工复核积压 |", markdown)
            self.assertIn("| review_delivery_health_issues | 复查最终交付健康提示 |", markdown)

    def test_data_quality_trend_signal_reaches_weekly_conclusion_health(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_ready_automation(root)
            write_json(
                root / "outputs" / "automation" / "latest_automation_check.json",
                {
                    "as_of_date": "2026-06-28",
                    "status": "manual_review_needed",
                    "recommended_action": "review_data_quality_trend",
                    "priority_actions": [
                        "review_data_quality_trend",
                        "review_data_quality_score",
                    ],
                    "data_quality_status": "needs_review",
                    "data_quality_score": 79.0,
                    "data_quality_history_status": "manual_review_needed",
                },
            )

            from weekly_conclusion_report import build_weekly_conclusion, render_markdown

            payload = build_weekly_conclusion(root, today="2026-06-28")
            markdown = render_markdown(payload)
            labels = {
                item["action"]: item["label"]
                for item in payload["priority_action_details"]
            }

            self.assertEqual(payload["recommended_action"], "review_data_quality_trend")
            self.assertEqual(
                payload["priority_actions"],
                ["review_data_quality_trend", "review_data_quality_score"],
            )
            self.assertEqual(payload["automation"]["data_quality_history"]["status"], "manual_review_needed")
            self.assertIn("data_quality_history:manual_review_needed", payload["health"]["reasons"])
            self.assertIn("automation_check:manual_review_needed", payload["health"]["reasons"])
            self.assertEqual(labels["review_data_quality_trend"], "复核数据质量历史趋势")
            self.assertEqual(labels["review_data_quality_score"], "复核三市场数据质量评分")
            self.assertNotIn("未分类动作", markdown)
            self.assertIn("| review_data_quality_trend | 复核数据质量历史趋势 |", markdown)
            self.assertIn("| review_data_quality_score | 复核三市场数据质量评分 |", markdown)

    def test_forecast_performance_signal_reaches_weekly_conclusion_health(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_ready_automation(root)
            write_json(
                root / "outputs" / "automation" / "latest_automation_check.json",
                {
                    "as_of_date": "2026-06-28",
                    "status": "manual_review_needed",
                    "recommended_action": "review_forecast_performance",
                    "priority_actions": [
                        "review_forecast_performance",
                        "continue_sample_accumulation",
                    ],
                    "forecast_performance_status": "performance_review_needed",
                    "forecast_performance": {
                        "total_evaluations": 80,
                        "mature_evaluations": 32,
                        "one_week_mature": 18,
                        "one_month_mature": 14,
                        "prediction_unavailable": 3,
                        "direction_hit_rate": 0.41,
                        "average_excess_return": -0.025,
                    },
                },
            )

            from weekly_conclusion_report import build_weekly_conclusion, render_markdown

            payload = build_weekly_conclusion(root, today="2026-06-28")
            markdown = render_markdown(payload)
            labels = {
                item["action"]: item["label"]
                for item in payload["priority_action_details"]
            }

            self.assertEqual(payload["recommended_action"], "review_forecast_performance")
            self.assertEqual(
                payload["automation"]["forecast_performance"]["status"],
                "performance_review_needed",
            )
            self.assertEqual(payload["automation"]["forecast_performance"]["mature_evaluations"], 32)
            self.assertEqual(payload["automation"]["forecast_performance"]["direction_hit_rate"], 0.41)
            self.assertIn("forecast_performance:performance_review_needed", payload["health"]["reasons"])
            self.assertEqual(labels["review_forecast_performance"], "复核预测表现")
            self.assertEqual(labels["continue_sample_accumulation"], "继续积累样本")
            self.assertNotIn("未分类动作", markdown)
            self.assertIn("- forecast_performance：performance_review_needed / mature 32 / hit 41.0% / excess -2.5%", markdown)
            self.assertIn("| review_forecast_performance | 复核预测表现 |", markdown)

    def test_includes_manual_review_queue_items_when_action_requests_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_manual_review_automation(root)
            write_manual_review_queue(root)

            from weekly_conclusion_report import build_weekly_conclusion, render_markdown

            payload = build_weekly_conclusion(root, today="2026-06-28")
            markdown = render_markdown(payload)

            self.assertEqual(payload["manual_review_queue"]["count"], 2)
            self.assertEqual(
                payload["manual_review_queue"]["by_market"],
                [{"market": "A股周筛", "count": 1}, {"market": "港股周筛", "count": 1}],
            )
            self.assertEqual(
                payload["manual_review_queue"]["by_review_type"],
                [{"review_type": "估值口径", "count": 1}, {"review_type": "风险提示", "count": 1}],
            )
            self.assertEqual(
                payload["manual_review_queue"]["action_guidance"],
                [
                    {
                        "review_type": "估值口径",
                        "count": 1,
                        "recommended_action": "用盈利质量、现金流、营收增速或净资产等替代口径复核，不把负 PE 直接视为低估。",
                    },
                    {
                        "review_type": "风险提示",
                        "count": 1,
                        "recommended_action": "复核趋势、估值置信度和风险说明，确认是否需要降低候选优先级或补充人工备注。",
                    },
                ],
            )
            self.assertEqual(payload["manual_review_queue"]["items"][0]["ticker"], "300122.SZ")
            self.assertEqual(payload["manual_review_queue"]["items"][0]["review_detail"], "loss_making_or_negative_pe；pe=-17.54")
            self.assertIn("## 人工复核队列", markdown)
            self.assertIn("- 按市场：A股周筛 1；港股周筛 1", markdown)
            self.assertIn("- 按类型：估值口径 1；风险提示 1", markdown)
            self.assertIn("### 人工复核建议", markdown)
            self.assertIn("| 估值口径 | 1 | 用盈利质量、现金流、营收增速或净资产等替代口径复核，不把负 PE 直接视为低估。 |", markdown)
            self.assertIn("| 风险提示 | 1 | 复核趋势、估值置信度和风险说明，确认是否需要降低候选优先级或补充人工备注。 |", markdown)
            self.assertIn("| 1 | A股周筛 | 估值口径 | 300122.SZ | 智飞生物 | loss_making_or_negative_pe；pe=-17.54 |", markdown)

    def test_summarizes_manual_review_decisions_against_current_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_manual_review_automation(root)
            write_manual_review_queue(root)
            write_manual_review_decisions(root)

            from weekly_conclusion_report import build_weekly_conclusion, render_markdown

            payload = build_weekly_conclusion(root, today="2026-06-28")
            markdown = render_markdown(payload)

            self.assertEqual(payload["manual_review_decisions"]["decision_count"], 2)
            self.assertEqual(payload["manual_review_decisions"]["matched_count"], 1)
            self.assertEqual(payload["manual_review_decisions"]["pending_count"], 1)
            self.assertEqual(
                payload["manual_review_decisions"]["by_status"],
                [{"decision_status": "accepted", "count": 1}, {"decision_status": "pending", "count": 1}],
            )
            self.assertEqual(payload["manual_review_decisions"]["items"][0]["decision_status"], "accepted")
            self.assertEqual(payload["manual_review_decisions"]["items"][0]["decision_note"], "现金流和行业周期仍可解释，保留跟踪。")
            self.assertEqual(payload["manual_review_decisions"]["items"][1]["decision_status"], "pending")
            self.assertIn("## 人工复核结果", markdown)
            self.assertIn("- 结果文件：outputs/automation/manual_review_decisions.csv", markdown)
            self.assertIn("- 已匹配本周队列：1", markdown)
            self.assertIn("- 待处理：1", markdown)
            self.assertIn("| accepted | 1 |", markdown)
            self.assertIn("| pending | 1 |", markdown)
            self.assertIn("| 300122.SZ | A股周筛 | 估值口径 | accepted | 现金流和行业周期仍可解释，保留跟踪。 | ck |", markdown)

    def test_includes_manual_review_merge_summary_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_manual_review_automation(root)
            write_manual_review_queue(root)
            write_manual_review_decisions(root)
            write_manual_review_merge_summary(root)

            from weekly_conclusion_report import build_weekly_conclusion, render_markdown

            payload = build_weekly_conclusion(root, today="2026-06-28")
            markdown = render_markdown(payload)

            self.assertTrue(payload["manual_review_merge_summary"]["exists"])
            self.assertEqual(payload["manual_review_merge_summary"]["path"], "outputs/automation/latest_manual_review_decision_merge.json")
            self.assertEqual(payload["manual_review_merge_summary"]["merged"], 2)
            self.assertEqual(payload["manual_review_merge_summary"]["skipped_pending"], 1)
            self.assertEqual(payload["manual_review_merge_summary"]["skipped_invalid"], 0)
            self.assertEqual(payload["manual_review_merge_summary"]["row_count"], 2)
            self.assertEqual(
                payload["manual_review_merge_summary"]["by_status"],
                [{"decision_status": "accepted", "count": 1}, {"decision_status": "rejected", "count": 1}],
            )
            self.assertIn("latest_manual_review_decision_merge.json", markdown)
            self.assertIn("- 合并/更新：2", markdown)
            self.assertIn("- 跳过 pending：1", markdown)
            self.assertIn("| accepted | 1 |", markdown)
            self.assertIn("| rejected | 1 |", markdown)

    def test_extracts_risk_reason_from_investment_summary_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_text(
                root / "outputs" / "hk_universe" / "latest_investment_summary.md",
                "\n".join(
                    [
                        "# 每周低估公司结论",
                        "",
                        "## 候选风险说明",
                        "",
                        "| 股票 | 公司 | 风险说明 |",
                        "|---|---|---|",
                        "| 0700.HK | 腾讯控股 | 走势偏弱；收入增长放缓 |",
                    ]
                ),
            )
            write_ready_automation(root)

            from weekly_conclusion_report import build_weekly_conclusion

            payload = build_weekly_conclusion(root, today="2026-06-28")
            hk = [candidate for candidate in payload["candidates"] if candidate["market"] == "HK"][0]

            self.assertEqual(hk["risk_reason"], "走势偏弱；收入增长放缓")

    def test_stale_or_future_automation_check_marks_needs_attention(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_ready_automation(root, as_of_date="2026-06-01")

            from weekly_conclusion_report import build_weekly_conclusion

            stale = build_weekly_conclusion(root, today="2026-06-28", max_age_days=8)
            self.assertEqual(stale["status"], "needs_attention")
            self.assertIn("latest_automation_check.json is older than 8 days", stale["warnings"])

            write_ready_automation(root, as_of_date="2026-07-01")
            future = build_weekly_conclusion(root, today="2026-06-28", max_age_days=8)
            self.assertEqual(future["status"], "needs_attention")
            self.assertIn("latest_automation_check.json is later than today", future["warnings"])

    def test_cli_writes_markdown_and_json_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_ready_automation(root)

            md = root / "outputs" / "automation" / "latest_weekly_conclusion.md"
            js = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "weekly_conclusion_report.py"),
                    "--project-root",
                    str(root),
                    "--today",
                    "2026-06-28",
                    "--output",
                    str(md),
                    "--json-output",
                    str(js),
                ],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("每周低估候选统一结论", result.stdout)
            self.assertTrue(md.exists())
            self.assertTrue(js.exists())
            self.assertEqual(json.loads(js.read_text(encoding="utf-8-sig"))["status"], "ready")

    def test_cli_writes_manual_review_decisions_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_manual_review_automation(root)
            write_manual_review_queue(root)
            write_manual_review_decisions(root)

            template = root / "outputs" / "automation" / "manual_review_decisions_template.csv"
            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "weekly_conclusion_report.py"),
                    "--project-root",
                    str(root),
                    "--today",
                    "2026-06-28",
                ],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(template.exists())
            with template.open("r", newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["ticker"], "300122.SZ")
            self.assertEqual(rows[0]["decision_status"], "accepted")
            self.assertEqual(rows[0]["decision_note"], "现金流和行业周期仍可解释，保留跟踪。")
            self.assertEqual(rows[1]["ticker"], "01548.HK")
            self.assertEqual(rows[1]["decision_status"], "pending")
            self.assertEqual(rows[1]["decision_note"], "")
            self.assertEqual(rows[1]["suggested_decision_status"], "needs_more_data")
            self.assertIn("风险提示", rows[1]["suggested_decision_note"])

    def test_powershell_wrapper_static_contract(self):
        script = (PROJECT_ROOT / "scripts" / "show_weekly_conclusion.ps1").read_text(encoding="utf-8-sig")

        self.assertIn("weekly_conclusion_report.py", script)
        self.assertIn("latest_weekly_conclusion.md", script)
        self.assertIn("latest_weekly_conclusion.json", script)
        self.assertIn("manual_review_decisions_template.csv", script)
        self.assertIn("--decisions-template-output", script)
        self.assertIn("-NoProfile -ExecutionPolicy Bypass", script)
        self.assertIn("codex-primary-runtime", script)


if __name__ == "__main__":
    unittest.main()
