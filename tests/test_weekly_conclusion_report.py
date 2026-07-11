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

    def test_weekly_conclusion_shows_shadow_disposition_counts_and_next_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_ready_automation(root)
            write_json(
                root
                / "outputs"
                / "automation"
                / "latest_one_week_forecast_shadow_disposition.json",
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
                    "next_one_week_evaluation_date": "2026-07-13",
                    "next_one_week_evaluation_count": 37,
                    "formal_model_change_allowed": False,
                },
            )

            from weekly_conclusion_report import build_weekly_conclusion, render_markdown

            payload = build_weekly_conclusion(root, today="2026-06-28")
            markdown = render_markdown(payload)
            disposition = payload["automation"]["forecast_shadow_disposition"]

            self.assertEqual(disposition["continue_observation_count"], 3)
            self.assertEqual(disposition["pending_human_approval_count"], 0)
            self.assertIn("预测影子处置", markdown)
            self.assertIn("继续观察=3", markdown)
            self.assertIn("2026-07-13", markdown)

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

    def test_delivery_history_status_does_not_hard_block_current_conclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_ready_automation(root)
            write_json(
                root / "outputs" / "automation" / "latest_weekly_delivery_history_summary.json",
                {
                    "latest_as_of_date": "2026-06-28",
                    "latest_status": "needs_attention",
                    "recurring_attention_reasons": [
                        {"reason": "previous_delivery_check_failed", "count": 1}
                    ],
                },
            )

            from weekly_conclusion_report import build_weekly_conclusion

            payload = build_weekly_conclusion(root, today="2026-06-28")

            self.assertEqual(payload["status"], "ready")
            self.assertNotEqual(payload["health"]["status"], "needs_fix")
            self.assertEqual(
                payload["automation"]["weekly_delivery_history"]["status"],
                "needs_attention",
            )

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
                        "reduce_weekly_action_backlog",
                    ],
                },
            )

            from weekly_conclusion_report import build_weekly_conclusion, render_markdown

            payload = build_weekly_conclusion(root, today="2026-06-28")
            markdown = render_markdown(payload)
            self.assertIn("reduce_weekly_action_backlog", markdown)
            self.assertIn("manual_review_decisions.csv", markdown)

            labels = {
                item["action"]: item["label"]
                for item in payload["priority_action_details"]
            }
            self.assertEqual(labels["reduce_weekly_action_backlog"], "制定人工待办压降计划")
            self.assertEqual(labels["review_manual_review_backlog"], "处理人工复核积压")
            self.assertEqual(labels["review_delivery_health_issues"], "复查最终交付健康提示")
            self.assertNotIn("未分类动作", markdown)
            self.assertIn("| review_manual_review_backlog | 处理人工复核积压 |", markdown)
            self.assertIn("| review_delivery_health_issues | 复查最终交付健康提示 |", markdown)

    def test_includes_weekly_action_items_backlog_reduction_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_ready_automation(root)
            write_json(
                root / "outputs" / "automation" / "latest_weekly_action_items.json",
                {
                    "action_items_schema": "weekly_action_items",
                    "action_items_version": 1,
                    "as_of_date": "2026-06-28",
                    "item_count": 5,
                    "backlog_reduction_plan": [
                        {
                            "category": "delivery_health",
                            "count": 3,
                            "actions": [
                                "review_manual_review_backlog",
                                "review_delivery_health_issues",
                                "reduce_weekly_action_backlog",
                            ],
                        },
                        {
                            "category": "data_quality",
                            "count": 2,
                            "actions": [
                                "review_data_quality_score",
                                "review_data_quality_trend",
                            ],
                        },
                    ],
                },
            )

            from weekly_conclusion_report import build_weekly_conclusion, render_markdown

            payload = build_weekly_conclusion(root, today="2026-06-28")
            markdown = render_markdown(payload)

            plan = payload["automation"]["weekly_action_items"]["backlog_reduction_plan"]
            self.assertEqual(plan[0]["category"], "delivery_health")
            self.assertEqual(plan[0]["count"], 3)
            self.assertEqual(plan[1]["category"], "data_quality")
            self.assertIn("## 待办压降分流", markdown)
            self.assertIn("| delivery_health | 3 |", markdown)
            self.assertIn("| data_quality | 2 |", markdown)

    def test_merges_weekly_action_items_into_priority_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_manual_review_automation(root)
            write_json(
                root / "outputs" / "automation" / "latest_weekly_action_items.json",
                {
                    "action_items_schema": "weekly_action_items",
                    "action_items_version": 1,
                    "as_of_date": "2026-06-28",
                    "item_count": 1,
                    "backlog_reduction_plan": [],
                    "items": [
                        {
                            "action_code": "review_current_membership_source_status",
                            "category": "backtest",
                            "title": "核对当前 S&P 500 成分来源缺口",
                            "source": "decisions_template_status:ready; decisions_template_matched_open_count:1",
                            "recommended_check": (
                                "核对 S&P 当前成分来源复核队列；决策模板 status=ready, "
                                "matched_open=1, missing_open=0。"
                            ),
                            "status": "open",
                        }
                    ],
                },
            )

            from weekly_conclusion_report import build_weekly_conclusion, render_markdown

            payload = build_weekly_conclusion(root, today="2026-06-28")
            markdown = render_markdown(payload)
            details = {
                item["action"]: item for item in payload["priority_action_details"]
            }

            self.assertIn(
                "review_current_membership_source_status",
                payload["priority_actions"],
            )
            self.assertIn(
                "review_current_membership_source_status",
                details,
            )
            self.assertEqual(
                details["review_current_membership_source_status"]["label"],
                "核对当前 S&P 500 成分来源缺口",
            )
            self.assertIn(
                "决策模板 status=ready",
                details["review_current_membership_source_status"]["description"],
            )
            self.assertIn("review_current_membership_source_status", markdown)
            self.assertIn("决策模板 status=ready", markdown)

    def test_weekly_action_items_are_authoritative_for_priority_actions_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_json(
                root / "outputs" / "automation" / "latest_automation_check.json",
                {
                    "as_of_date": "2026-06-28",
                    "status": "manual_review_needed",
                    "recommended_action": "review_data_health",
                    "priority_actions": [
                        "review_manual_review_backlog",
                        "review_delivery_health_issues",
                        "review_data_health",
                    ],
                },
            )
            write_json(
                root / "outputs" / "automation" / "latest_weekly_ops_check.json",
                {"as_of_date": "2026-06-28", "status": "ready"},
            )
            write_json(
                root / "outputs" / "automation" / "latest_weekly_ops_history_summary.json",
                {"latest_as_of_date": "2026-06-28", "latest_status": "ready"},
            )
            write_json(
                root / "outputs" / "automation" / "latest_weekly_delivery_history_summary.json",
                {"latest_as_of_date": "2026-06-28", "latest_status": "ready"},
            )
            write_json(
                root / "outputs" / "automation" / "latest_weekly_action_items.json",
                {
                    "action_items_schema": "weekly_action_items",
                    "action_items_version": 1,
                    "as_of_date": "2026-06-28",
                    "item_count": 2,
                    "backlog_reduction_plan": [],
                    "items": [
                        {
                            "action_code": "review_delivery_health_issues",
                            "title": "复查最终交付健康提示",
                            "recommended_check": "复查数据质量导致的交付健康提示。",
                        },
                        {
                            "action_code": "review_data_health",
                            "title": "复查数据健康异常",
                            "recommended_check": "复查当前数据健康缺口。",
                        },
                    ],
                },
            )

            from weekly_conclusion_report import build_weekly_conclusion

            payload = build_weekly_conclusion(root, today="2026-06-28")

            self.assertEqual(
                payload["priority_actions"],
                ["review_delivery_health_issues", "review_data_health"],
            )
            self.assertEqual(payload["recommended_action"], "review_delivery_health_issues")
            self.assertNotIn("review_manual_review_backlog", payload["priority_actions"])

    def test_weekly_action_items_surface_external_input_gaps_in_risk_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_ready_automation(root)
            write_json(
                root / "outputs" / "automation" / "latest_weekly_action_items.json",
                {
                    "action_items_schema": "weekly_action_items",
                    "action_items_version": 1,
                    "as_of_date": "2026-06-28",
                    "item_count": 1,
                    "backlog_reduction_plan": [],
                    "items": [
                        {
                            "action_code": "provide_official_constituents_csv",
                            "category": "backtest",
                            "title": "核对当前 S&P 500 成分来源缺口",
                            "recommended_check": (
                                "source_file_inbox:inputs/sp500_current_membership/official_constituents.csv; "
                                "official_export_url=https://www.spglobal.com/spdji/en/idsexport/file.xls?redesignExport=true&languageId=1&selectedModule=Constituents&selectedSubModule=ConstituentsFullList&indexId=340; "
                                "source_file_user_agent_hint=Set SEC_USER_AGENT or pass -UserAgent <user_agent> when retrying official S&P Global fetches through PowerShell entrypoints.; "
                                "inbox_next_action=place_official_constituents_csv; "
                                "inbox_external_input_required=true; "
                                "inbox_blocking_reason=official_constituents_csv_missing; "
                                "dry_run_command:powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                                "scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> "
                                "-DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv; "
                                "import_command:powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                                "scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> "
                                "-SourceFileInbox inputs/sp500_current_membership/official_constituents.csv"
                            ),
                            "status": "open",
                        },
                    ],
                },
            )

            from weekly_conclusion_report import build_weekly_conclusion, render_markdown

            payload = build_weekly_conclusion(root, today="2026-06-28")
            markdown = render_markdown(payload)

            self.assertIn("priority_input_gaps", payload)
            self.assertEqual(payload["priority_input_gaps"][0]["action_code"], "provide_official_constituents_csv")
            self.assertEqual(
                payload["priority_input_gaps"][0]["blocking_input"],
                "inputs/sp500_current_membership/official_constituents.csv",
            )
            self.assertEqual(
                payload["priority_input_gaps"][0]["blocking_reason"],
                "official_constituents_csv_missing",
            )
            self.assertEqual(
                payload["priority_input_gaps"][0]["next_action"],
                "place_official_constituents_csv",
            )
            self.assertEqual(
                payload["priority_input_gaps"][0]["user_agent_hint"],
                "Set SEC_USER_AGENT or pass -UserAgent <user_agent> when retrying official S&P Global fetches through PowerShell entrypoints.",
            )
            self.assertEqual(
                payload["priority_input_gaps"][0]["official_export_url"],
                "https://www.spglobal.com/spdji/en/idsexport/file.xls?redesignExport=true&languageId=1&selectedModule=Constituents&selectedSubModule=ConstituentsFullList&indexId=340",
            )
            self.assertIn(
                "校验命令=",
                payload["priority_action_details"][0]["description"],
            )
            self.assertIn(
                "导入命令=",
                payload["priority_action_details"][0]["description"],
            )
            self.assertIn(
                "source_file_user_agent_hint=Set SEC_USER_AGENT",
                payload["priority_action_details"][0]["description"],
            )
            self.assertIn("-UserAgent <user_agent>", payload["priority_action_details"][0]["description"])
            self.assertIn("-DryRun -SourceFileInbox", payload["priority_input_gaps"][0]["dry_run_command"])
            self.assertIn("-SourceFileInbox", payload["priority_input_gaps"][0]["import_command"])
            self.assertIn("official_constituents.csv", markdown)
            self.assertIn("source_file_user_agent_hint=Set SEC_USER_AGENT", markdown)
            self.assertIn("official_export_url=https://www.spglobal.com/spdji/en/idsexport/file.xls", markdown)
            risk_gap_lines = [
                line
                for line in markdown.splitlines()
                if line.startswith("- 优先输入缺口：核对当前 S&P 500 成分来源缺口")
            ]
            self.assertEqual(len(risk_gap_lines), 1)
            self.assertIn("official_export_url=", risk_gap_lines[0])
            self.assertIn("-UserAgent <user_agent>", markdown)
            self.assertIn("投递入口", markdown)
            self.assertIn("阻塞原因", markdown)
            self.assertIn("导入命令", markdown)
            self.assertNotIn("dry_run_command:", markdown)
            self.assertNotIn("import_command:", markdown)
            self.assertNotIn("暂未发现需要优先人工复核的输入缺口", markdown)

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
                        "next_one_week_evaluation_date": "2026-07-05",
                        "next_one_month_evaluation_date": "2026-07-26",
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
            self.assertEqual(
                payload["automation"]["forecast_performance"]["next_one_week_evaluation_date"],
                "2026-07-05",
            )
            self.assertEqual(
                payload["automation"]["forecast_performance"]["next_one_month_evaluation_date"],
                "2026-07-26",
            )
            self.assertIn("forecast_performance:performance_review_needed", payload["health"]["reasons"])
            self.assertIn("next 1w 2026-07-05", markdown)
            self.assertIn("next 1m 2026-07-26", markdown)
            self.assertEqual(labels["review_forecast_performance"], "复核预测表现")
            self.assertEqual(labels["continue_sample_accumulation"], "继续积累样本")
            self.assertNotIn("未分类动作", markdown)
            self.assertIn("- forecast_performance：performance_review_needed / mature 32 / hit 41.0% / excess -2.5%", markdown)
            self.assertIn("| review_forecast_performance | 复核预测表现 |", markdown)

    def test_forecast_performance_dates_fall_back_to_review_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            automation = root / "outputs" / "automation"
            write_ready_automation(root)
            write_json(
                automation / "latest_self_analysis_manifest.json",
                {
                    "forecast_performance": {
                        "status": "sample_accumulating",
                        "total_evaluations": 80,
                        "mature_evaluations": 0,
                    }
                },
            )
            write_json(
                automation / "latest_forecast_performance_review.json",
                {
                    "status": "sample_accumulating",
                    "total_evaluations": 80,
                    "mature_evaluations": 0,
                    "next_one_week_evaluation_date": "2026-07-07",
                    "next_one_week_evaluation_count": 42,
                    "next_one_month_evaluation_date": "2026-07-28",
                    "next_one_month_evaluation_count": 43,
                },
            )
            write_json(
                automation / "latest_automation_check.json",
                {
                    "as_of_date": "2026-06-28",
                    "status": "manual_review_needed",
                    "forecast_performance_status": "sample_accumulating",
                    "outputs": {
                        "manifest": str(automation / "latest_self_analysis_manifest.json"),
                    },
                },
            )

            from weekly_conclusion_report import build_weekly_conclusion, render_markdown

            payload = build_weekly_conclusion(root, today="2026-06-28")
            markdown = render_markdown(payload)

            self.assertEqual(
                payload["automation"]["forecast_performance"]["next_one_week_evaluation_date"],
                "2026-07-07",
            )
            self.assertEqual(
                payload["automation"]["forecast_performance"]["next_one_week_evaluation_count"],
                42,
            )
            self.assertEqual(
                payload["automation"]["forecast_performance"]["next_one_month_evaluation_date"],
                "2026-07-28",
            )
            self.assertEqual(
                payload["automation"]["forecast_performance"]["next_one_month_evaluation_count"],
                43,
            )
            self.assertIn("next 1w 2026-07-07", markdown)
            self.assertIn("next 1w count 42", markdown)
            self.assertIn("next 1m 2026-07-28", markdown)
            self.assertIn("next 1m count 43", markdown)

    def test_includes_integrated_review_summary_from_current_week_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_ready_automation(root)
            automation = root / "outputs" / "automation"
            write_json(
                automation / "latest_candidate_findings_review.json",
                {
                    "status": "manual_review_needed",
                    "candidate_count_total": 63,
                    "risk_action_required_count": 15,
                    "risk_reduction_status": "action_required",
                    "risk_reduction_decision": "manual_review_queue_ready",
                    "priority_market": "港股周筛",
                    "formal_model_change_allowed": False,
                    "path": "outputs/automation/latest_candidate_findings_review.json",
                },
            )
            write_json(
                automation / "latest_candidate_risk_resolution_review.json",
                {
                    "status": "ready",
                    "as_of_date": "2026-06-28",
                    "risk_action_total_count": 15,
                    "resolved_or_routed_count": 10,
                    "auto_routed_count": 10,
                    "manual_pending_count": 5,
                    "manual_pending_limit": 5,
                    "cap_applied_count": 9,
                    "cap_applied_ratio": 0.6,
                    "formal_model_change_allowed": False,
                },
            )
            write_json(
                automation / "latest_one_week_forecast_shadow_review.json",
                {
                    "status": "shadow_review_needed",
                    "shadow_diagnosis_status": "review_needed",
                    "shadow_diagnosis_reasons": [
                        {"reason_code": "direction_mapping_issue"},
                        {"reason_code": "down_signal_reversal_risk"},
                    ],
                    "one_week_samples": 179,
                    "direction_hit_rate": 0.2179,
                    "priority_review_market": "港股周筛",
                    "formal_model_change_allowed": False,
                    "formal_model_change_decision": "keep_formal_model_unchanged",
                    "path": "outputs/automation/latest_one_week_forecast_shadow_review.json",
                },
            )
            write_json(
                automation / "latest_backtest_evidence_review.json",
                {
                    "status": "evidence_ceiling_confirmed",
                    "evidence_ceiling_status": "evidence_ceiling_confirmed",
                    "backtest_mode": "limited_verified_only",
                    "membership_evidence_unresolved_gap_count": 425,
                    "membership_evidence_gate_status": "blocked",
                    "membership_evidence_gate_decision": "verified_only_no_expansion",
                    "membership_evidence_blocking_tiers": ["secondary", "weak"],
                    "verified_membership_ratio": 0.156,
                    "backtest_sample_expansion_allowed": False,
                    "formal_model_change_allowed": False,
                    "path": "outputs/automation/latest_backtest_evidence_review.json",
                },
            )
            write_json(
                automation / "latest_data_health_review.json",
                {
                    "status": "acceptable_with_monitoring",
                    "data_health_triage_status": "monitor_only",
                    "data_health_triage_decision": "monitor_next_run",
                    "candidate_delivery_blocked": False,
                    "data_health_triage_counts": {
                        "candidate_blocking": 0,
                        "refetch_required": 0,
                        "monitor_only": 74,
                    },
                    "path": "outputs/automation/latest_data_health_review.json",
                },
            )
            write_json(
                automation / "latest_weekly_action_items.json",
                {
                    "action_items_schema": "weekly_action_items",
                    "as_of_date": "2026-06-28",
                    "item_count": 4,
                    "items": [
                        {"action_code": "review_backtest_evidence", "title": "复查回测证据质量"},
                        {"action_code": "review_forecast_performance", "title": "复核预测表现"},
                    ],
                    "backlog_reduction_plan": [
                        {
                            "category": "backtest",
                            "count": 2,
                            "actions": [
                                "review_backtest_evidence",
                                "supplement_verified_membership_evidence",
                            ],
                        }
                    ],
                },
            )

            from weekly_conclusion_report import build_weekly_conclusion, render_markdown

            payload = build_weekly_conclusion(root, today="2026-06-28")
            markdown = render_markdown(payload)

            summary = payload["integrated_review_summary"]
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["recommended_action"], "review_backtest_evidence")
            self.assertEqual(summary["candidate_risk_status"], "action_required")
            self.assertEqual(summary["candidate_risk_action_required_count"], 15)
            self.assertEqual(summary["candidate_risk_resolution_status"], "ready")
            self.assertEqual(summary["candidate_risk_auto_routed_count"], 10)
            self.assertEqual(summary["candidate_risk_manual_pending_count"], 5)
            self.assertEqual(summary["candidate_risk_cap_applied_count"], 9)
            self.assertEqual(summary["forecast_shadow_status"], "shadow_review_needed")
            self.assertEqual(summary["forecast_shadow_diagnosis_status"], "review_needed")
            self.assertIn("direction_mapping_issue", summary["forecast_shadow_diagnosis_reasons"])
            self.assertEqual(summary["backtest_evidence_gate_status"], "blocked")
            self.assertEqual(summary["backtest_evidence_gate_decision"], "verified_only_no_expansion")
            self.assertEqual(summary["backtest_evidence_ceiling_status"], "evidence_ceiling_confirmed")
            self.assertEqual(summary["backtest_mode"], "limited_verified_only")
            self.assertEqual(summary["backtest_unresolved_gap_count"], 425)
            self.assertEqual(summary["data_health_triage_status"], "monitor_only")
            self.assertEqual(summary["data_health_triage_counts"]["monitor_only"], 74)
            self.assertFalse(summary["formal_model_change_allowed"])

            self.assertIn("## 一屏结论", markdown)
            self.assertIn(
                "| 候选风险 | ready | raw_actions=15; auto_routed=10; manual_pending=5; cap_applied=9",
                markdown,
            )
            self.assertIn("| 预测影子诊断 | shadow_review_needed | samples=179; hit=21.8%; diagnosis=direction_mapping_issue, down_signal_reversal_risk", markdown)
            self.assertIn("| 回测证据边界 | evidence_ceiling_confirmed | mode=limited_verified_only; unresolved_gaps=425; decision=verified_only_no_expansion", markdown)
            self.assertIn("| 数据健康 | monitor_only | candidate_blocking=0; refetch_required=0; monitor_only=74", markdown)
            self.assertIn("| 正式模型 | protected | formal_model_change_allowed=false", markdown)

    def test_known_review_signals_keep_conclusion_health_at_review_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_manual_review_queue(root)
            automation = root / "outputs" / "automation"
            write_json(
                automation / "latest_automation_check.json",
                {
                    "as_of_date": "2026-06-28",
                    "status": "manual_review_needed",
                    "recommended_action": "review_manual_queue",
                    "priority_actions": [
                        "review_manual_queue",
                        "review_backtest_evidence",
                        "review_forecast_performance",
                    ],
                    "data_quality_history_status": "manual_review_needed",
                    "forecast_performance_status": "performance_review_needed",
                    "forecast_performance": {
                        "mature_evaluations": 179,
                        "direction_hit_rate": 0.2179,
                        "average_excess_return": 0.0249,
                    },
                },
            )
            write_json(
                automation / "latest_weekly_ops_check.json",
                {"as_of_date": "2026-06-28", "status": "ready"},
            )
            write_json(
                automation / "latest_weekly_ops_history_summary.json",
                {"latest_as_of_date": "2026-06-28", "latest_status": "ready"},
            )
            write_json(
                automation / "latest_weekly_delivery_history_summary.json",
                {"latest_as_of_date": "2026-06-28", "latest_status": "ready"},
            )
            write_json(
                automation / "latest_candidate_findings_review.json",
                {
                    "status": "manual_review_needed",
                    "risk_reduction_status": "action_required",
                    "risk_action_required_count": 15,
                    "formal_model_change_allowed": False,
                },
            )

            from weekly_conclusion_report import build_weekly_conclusion

            payload = build_weekly_conclusion(root, today="2026-06-28")

            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["health"]["status"], "needs_review")
            self.assertGreaterEqual(payload["health"]["score"], 60)
            self.assertIn("manual_review_pending:2", payload["health"]["reasons"])

    def test_first_one_month_awaiting_maturity_is_an_acceptable_lifecycle_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_three_markets(root)
            write_ready_automation(root)
            write_json(
                root
                / "outputs"
                / "automation"
                / "latest_first_one_month_forecast_evaluation_review.json",
                {
                    "as_of_date": "2026-06-28",
                    "status": "awaiting_maturity",
                    "recommended_action": "wait_for_one_month_maturity",
                },
            )

            from weekly_conclusion_report import build_weekly_conclusion

            payload = build_weekly_conclusion(root, today="2026-06-28")

            self.assertEqual(payload["status"], "ready")
            self.assertNotEqual(payload["health"]["status"], "needs_fix")

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

    def test_normalizes_first_one_month_evaluation_separately_by_horizon(self):
        from weekly_conclusion_report import normalize_first_one_month_forecast_evaluation

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "outputs/automation/latest_first_one_month_forecast_evaluation_review.json"
            payload = {
                "status": "review_ready",
                "as_of_date": "2026-08-03",
                "cohort": {"expected_sample_count": 37, "actual_sample_count": 37},
                "one_week": {"valid_evaluation_count": 37, "direction_hit_rate": 0.4, "average_excess_return": 0.01, "failure_type_counts": {"opposite_direction": 5}},
                "one_month": {"valid_evaluation_count": 37, "direction_hit_rate": 0.6, "average_excess_return": 0.03, "failure_type_counts": {"predicted_move_but_actual_neutral": 4}},
                "market_comparison": {"status": "insufficient_market_coverage"},
                "recommended_action": "review_first_one_month_results_manually",
                "formal_model_change_allowed": False,
                "formal_model_conclusion_allowed": False,
            }

            normalized = normalize_first_one_month_forecast_evaluation(root, payload, path)

            self.assertEqual(normalized["one_week_direction_hit_rate"], 0.4)
            self.assertEqual(normalized["one_month_direction_hit_rate"], 0.6)
            self.assertEqual(normalized["one_month_average_excess_return"], 0.03)
            self.assertEqual(normalized["market_comparison_status"], "insufficient_market_coverage")

    def test_integrated_summary_keeps_first_one_month_metrics_separate(self):
        from weekly_conclusion_report import build_integrated_review_summary

        automation = {
            "first_one_month_forecast_evaluation": {
                "status": "review_ready",
                "expected_sample_count": 37,
                "one_week_valid_count": 37,
                "one_week_direction_hit_rate": 0.4,
                "one_week_average_excess_return": 0.01,
                "one_month_valid_count": 37,
                "one_month_direction_hit_rate": 0.6,
                "one_month_average_excess_return": 0.03,
                "market_comparison_status": "insufficient_market_coverage",
                "formal_model_change_allowed": False,
                "formal_model_conclusion_allowed": False,
            }
        }

        summary = build_integrated_review_summary(automation, [], [], {"groups": []})

        self.assertEqual(summary["first_one_month_status"], "review_ready")
        self.assertEqual(summary["first_one_month_one_week_hit_rate"], 0.4)
        self.assertEqual(summary["first_one_month_one_month_hit_rate"], 0.6)
        self.assertEqual(summary["first_one_month_market_comparison_status"], "insufficient_market_coverage")


    def test_non_ready_conclusion_keeps_review_inputs_and_weekly_action_codes(self):
        from weekly_conclusion_report import choose_priority_actions

        automation = {
            "weekly_action_items": {
                "items": [
                    {"action_code": "continue_shadow_validation"},
                    {"action_code": "review_latest_ops_check"},
                    {"action_code": "continue_sample_accumulation"},
                    {"action_code": "review_delivery_health_issues"},
                    {"action_code": "review_inputs"},
                ]
            }
        }

        actions = choose_priority_actions("needs_attention", automation, "review_inputs")

        self.assertEqual(
            actions,
            [
                "review_inputs",
                "continue_shadow_validation",
                "review_latest_ops_check",
                "continue_sample_accumulation",
                "review_delivery_health_issues",
            ],
        )


if __name__ == "__main__":
    unittest.main()
