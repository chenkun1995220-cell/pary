import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_manifest(path):
    manifest = {
        "manifest_schema": "self_analysis_manifest",
        "manifest_version": 1,
        "as_of_date": "2026-06-28",
        "automation_status": "manual_review_needed",
        "automation_priority_actions": [
            "review_manual_queue",
            "review_data_health",
            "review_manual_review_backlog",
            "review_delivery_health_issues",
            "review_data_quality_score",
            "review_data_quality_trend",
            "review_forecast_performance",
            "continue_sample_accumulation",
        ],
        "manual_review_queue_count": 12,
        "weekly_delivery_history": {
            "latest_manual_review_pending_count": 12,
            "latest_conclusion_health_status": "needs_review",
            "latest_conclusion_health_score": 75,
            "latest_conclusion_health_reasons": [
                "automation_check:manual_review_needed",
                "manual_review_pending:12",
            ],
            "recurring_health_reasons": [
                {"reason": "manual_review_pending:12", "count": 2}
            ],
            "latest_conclusion_signal_status": "missing",
            "latest_missing_conclusion_signals": [
                "automation.data_quality_history",
                "automation.forecast_performance",
            ],
            "latest_missing_conclusion_signal_fixes": {
                "automation.data_quality_history": (
                    "rerun_self_analysis_and_weekly_conclusion: ensure latest_self_analysis_manifest.json "
                    "contains data_quality_history before show_weekly_conclusion.ps1"
                ),
                "automation.forecast_performance": (
                    "rerun_self_analysis_and_weekly_conclusion: ensure latest_self_analysis_manifest.json "
                    "contains forecast_performance before show_weekly_conclusion.ps1"
                ),
            },
            "recurring_missing_conclusion_signals": [
                {"signal": "automation.forecast_performance", "count": 2}
            ],
            "recurring_missing_conclusion_signal_fixes": [
                {
                    "signal": "automation.forecast_performance",
                    "fix": (
                        "rerun_self_analysis_and_weekly_conclusion: ensure latest_self_analysis_manifest.json "
                        "contains forecast_performance before show_weekly_conclusion.ps1"
                    ),
                    "count": 2,
                }
            ],
        },
        "data_quality_status": "needs_review",
        "data_quality_score": 79.0,
        "data_quality_summary": {
            "status": "needs_review",
            "average_score": 79.0,
            "markets": [
                {
                    "name": "美股周筛",
                    "quality_score": 100,
                    "quality_status": "ready",
                    "reasons": ["clear"],
                },
                {
                    "name": "港股周筛",
                    "quality_score": 57,
                    "quality_status": "needs_review",
                    "reasons": ["quote_coverage:84.10%", "quote_review_gap:50"],
                },
            ],
        },
        "data_quality_history": {
            "status": "manual_review_needed",
            "recommended_action": "review_data_quality_trend",
            "repeated_needs_review_markets": ["港股周筛"],
            "score_decline_markets": ["A股周筛"],
        },
        "data_health_status": "ready",
        "backtest_status": "sample_accumulating",
        "candidate_review_status": "needs_review",
        "model_audit_status": "sample_accumulating",
        "forecast_performance_status": "performance_review_needed",
        "forecast_performance": {
            "mature_evaluations": 30,
            "direction_hit_rate": 0.32,
            "average_excess_return": -0.04,
            "next_one_week_evaluation_date": "2026-07-07",
            "next_one_month_evaluation_date": "2026-07-28",
        },
    }
    Path(path).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_membership_import_plan(path, ready_count=2):
    payload = {
        "review_schema": "membership_evidence_import_plan",
        "review_version": 1,
        "as_of_date": "2026-06-28",
        "status": "ready",
        "ready_to_import_count": ready_count,
        "ready_to_import_weeks_affected": 210,
        "missing_source_count": 1,
        "missing_source_weeks_affected": 300,
        "invalid_source_count": 0,
        "invalid_source_weeks_affected": 0,
        "next_action": "run_membership_evidence_apply_preview",
        "items": [
            {
                "ticker": "HIGH",
                "company_name": "High Impact",
                "import_status": "ready_current_source",
                "weeks_affected": 200,
            },
            {
                "ticker": "LOW",
                "company_name": "Low Impact",
                "import_status": "ready_current_source",
                "weeks_affected": 10,
            },
        ],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_current_membership_sources(path):
    payload = {
        "source_schema": "sp500_current_membership_sources",
        "source_version": 1,
        "as_of_date": "2026-06-28",
        "status": "ready",
        "matched_count": 1,
        "missing_count": 1,
        "missing_tickers": ["ZZZ"],
        "missing_ticker_review_queue": [
            {
                "ticker": "ZZZ",
                "review_status": "open",
                "issue_type": "missing_from_official_current_source",
                "recommended_check": "Confirm official source coverage.",
            }
        ],
        "missing_ticker_review_queue_file": "outputs/automation/sp500_current_membership_source_review_queue.csv",
        "intake_coverage_status": "none",
        "intake_expected_count": 1,
        "intake_matched_count": 0,
        "intake_missing_count": 1,
        "intake_missing_tickers": ["ZZZ"],
        "next_action": "review_missing_tickers",
        "recommended_followup": "review_current_membership_source_status",
        "formal_backtest_upgrade_allowed": False,
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_current_membership_source_review_status(path):
    payload = {
        "review_status_schema": "sp500_current_membership_source_review_status",
        "review_status_version": 1,
        "as_of_date": "2026-06-28",
        "status": "review_needed",
        "queue_file": "outputs/automation/sp500_current_membership_source_review_queue.csv",
        "queue_exists": True,
        "queue_total_count": 1,
        "open_count": 1,
        "resolved_count": 0,
        "open_items": [{"ticker": "ZZZ", "review_status": "open"}],
        "resolved_items": [],
        "next_action": "review_open_queue_items",
        "review_decision_status": "missing",
        "manual_decision_next_step": "fill_decisions_template",
        "decision_pending_count": 1,
        "decision_pending_tickers": ["ZZZ"],
        "decision_ready_to_apply_count": 0,
        "decision_ready_to_apply_tickers": [],
        "decisions_template_file": "outputs/automation/sp500_current_membership_source_review_decisions_template.csv",
        "decisions_template_exists": True,
        "decisions_template_status": "ready",
        "decisions_template_total_count": 1,
        "decisions_template_matched_open_count": 1,
        "decisions_template_missing_open_tickers": [],
        "decisions_template_extra_tickers": [],
        "decisions_template_missing_fields": [],
        "formal_backtest_upgrade_allowed": False,
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_current_membership_source_inbox_status(path):
    payload = {
        "status_schema": "sp500_current_membership_source_inbox_status",
        "status_version": 1,
        "as_of_date": "2026-06-28",
        "status": "missing",
        "source_file_inbox": "inputs/sp500_current_membership/official_constituents.csv",
        "source_file_inbox_exists": False,
        "source_file_validation_status": "missing",
        "parsed_official_ticker_count": 0,
        "minimum_official_ticker_count": 400,
        "intake_coverage_status": "none",
        "intake_expected_count": 50,
        "intake_matched_count": 0,
        "intake_missing_count": 50,
        "next_action": "place_official_constituents_csv",
        "formal_backtest_upgrade_allowed": False,
        "formal_model_change_allowed": False,
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_forecast_performance_review(
    path,
    prediction_unavailable=87,
    pending_maturity=0,
    mature_evaluations=0,
    latest_prediction_unavailable=87,
    legacy_prediction_unavailable=0,
    next_one_week_evaluation_date="2026-07-07",
    next_one_month_evaluation_date="2026-07-28",
):
    payload = {
        "review_schema": "forecast_performance_review",
        "review_version": 1,
        "as_of_date": "2026-06-28",
        "status": "sample_accumulating",
        "total_evaluations": 87,
        "mature_evaluations": mature_evaluations,
        "one_week_mature": 0,
        "one_month_mature": 0,
        "latest_short_signal_missing_count": 0,
        "latest_prediction_unavailable_count": latest_prediction_unavailable,
        "legacy_prediction_unavailable_count": legacy_prediction_unavailable,
        "next_one_week_evaluation_date": next_one_week_evaluation_date,
        "next_one_month_evaluation_date": next_one_month_evaluation_date,
        "maturity_gap_reasons": {
            "prediction_unavailable": prediction_unavailable,
            "pending_maturity": pending_maturity,
            "other_not_evaluated": 0,
        },
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def write_manual_review_queue(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "as_of_date",
                "rank",
                "market",
                "review_type",
                "ticker",
                "company",
                "review_detail",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "as_of_date": "2026-06-28",
                "rank": "1",
                "market": "A股周筛",
                "review_type": "估值口径",
                "ticker": "300433.SZ",
                "company": "蓝思科技",
                "review_detail": "loss_making_or_negative_pe；pe=-457.21",
            }
        )


def write_data_health_review(path):
    payload = {
        "review_schema": "data_health_review",
        "as_of_date": "2026-06-29",
        "status": "acceptable_with_monitoring",
        "refetch_gap_count": 2,
        "markets": [
            {
                "name": "港股周筛",
                "refetch_gaps": [
                    {
                        "ticker": "00754.HK",
                        "company": "HOPSON DEV HOLD",
                        "missing_fields": "price;pe",
                        "in_candidate_pool": False,
                    },
                    {
                        "ticker": "00823.HK",
                        "company": "LINK REIT",
                        "missing_fields": "pe;pb",
                        "in_candidate_pool": False,
                    },
                ],
            }
        ],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


class WeeklyActionItemsTests(unittest.TestCase):
    def test_builds_action_items_from_self_analysis_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "latest_self_analysis_manifest.json"
            manual_queue_path = Path(tmp) / "latest_manual_review_queue.csv"
            data_health_path = Path(tmp) / "latest_data_health_review.json"
            write_manifest(manifest_path)
            write_manual_review_queue(manual_queue_path)
            write_data_health_review(data_health_path)

            from weekly_action_items import build_weekly_action_items, render_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                manual_review_queue=manual_queue_path,
                data_health_review=data_health_path,
            )
            report = render_weekly_action_items(payload)

            self.assertEqual(payload["action_items_schema"], "weekly_action_items")
            self.assertEqual(payload["action_items_version"], 1)
            self.assertEqual(payload["as_of_date"], "2026-06-28")
            self.assertEqual(payload["source_manifest"], str(manifest_path))
            self.assertEqual(payload["automation_status"], "manual_review_needed")
            self.assertEqual(payload["item_count"], 8)

            backlog = next(
                item
                for item in payload["items"]
                if item["action_code"] == "review_manual_review_backlog"
            )
            self.assertEqual(backlog["category"], "delivery_health")
            self.assertEqual(backlog["status"], "open")
            self.assertIn("人工复核积压", backlog["title"])
            self.assertIn("12", backlog["recommended_check"])
            self.assertIn("manual_review_pending:12", backlog["source"])

            delivery = next(
                item
                for item in payload["items"]
                if item["action_code"] == "review_delivery_health_issues"
            )
            self.assertIn("automation_check:manual_review_needed", delivery["source"])
            self.assertIn("automation.forecast_performance", delivery["source"])
            self.assertIn("latest_self_analysis_manifest.json", delivery["source"])
            self.assertIn("automation.data_quality_history", delivery["recommended_check"])
            self.assertIn("automation.forecast_performance", delivery["recommended_check"])
            self.assertIn("latest_self_analysis_manifest.json", delivery["recommended_check"])
            self.assertIn("show_weekly_conclusion.ps1", delivery["recommended_check"])
            self.assertIn("needs_review", delivery["recommended_check"])

            manual_queue = next(
                item
                for item in payload["items"]
                if item["action_code"] == "review_manual_queue"
            )
            self.assertIn("300433.SZ", manual_queue["recommended_check"])
            self.assertIn("蓝思科技", manual_queue["recommended_check"])
            self.assertIn("loss_making_or_negative_pe", manual_queue["recommended_check"])

            data_health = next(
                item
                for item in payload["items"]
                if item["action_code"] == "review_data_health"
            )
            self.assertIn("00754.HK", data_health["recommended_check"])
            self.assertIn("HOPSON DEV HOLD", data_health["recommended_check"])
            self.assertIn("price;pe", data_health["recommended_check"])
            self.assertIn("00823.HK", data_health["recommended_check"])
            self.assertIn("LINK REIT", data_health["recommended_check"])
            self.assertIn("pe;pb", data_health["recommended_check"])

            data_quality = next(
                item
                for item in payload["items"]
                if item["action_code"] == "review_data_quality_score"
            )
            self.assertEqual(data_quality["category"], "data_quality")
            self.assertIn("needs_review", data_quality["source"])
            self.assertIn("79", data_quality["source"])
            self.assertIn("港股周筛", data_quality["recommended_check"])
            self.assertIn("57", data_quality["recommended_check"])

            data_quality_trend = next(
                item
                for item in payload["items"]
                if item["action_code"] == "review_data_quality_trend"
            )
            self.assertEqual(data_quality_trend["category"], "data_quality")
            self.assertIn("manual_review_needed", data_quality_trend["source"])
            self.assertIn("港股周筛", data_quality_trend["recommended_check"])
            self.assertIn("A股周筛", data_quality_trend["recommended_check"])

            sample = next(
                item
                for item in payload["items"]
                if item["action_code"] == "continue_sample_accumulation"
            )
            self.assertEqual(sample["category"], "model_tracking")
            self.assertIn("sample_accumulating", sample["recommended_check"])
            self.assertIn("2026-07-07", sample["recommended_check"])
            self.assertIn("2026-07-28", sample["recommended_check"])

            forecast = next(
                item
                for item in payload["items"]
                if item["action_code"] == "review_forecast_performance"
            )
            self.assertEqual(forecast["category"], "forecast_performance")
            self.assertIn("预测表现", forecast["title"])
            self.assertIn("30", forecast["source"])
            self.assertIn("32.00%", forecast["recommended_check"])
            self.assertIn("-4.00%", forecast["recommended_check"])

            self.assertIn("# 每周人工处理清单", report)
            self.assertIn("review_manual_review_backlog", report)
            self.assertIn("automation.forecast_performance", report)
            self.assertIn("show_weekly_conclusion.ps1", report)
            self.assertIn("review_data_quality_score", report)
            self.assertIn("review_forecast_performance", report)
            self.assertIn("人工复核积压", report)
            self.assertIn("不抓取行情", report)

    def test_adds_apply_preview_action_when_membership_sources_are_ready_to_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            import_plan_path = root / "latest_membership_evidence_import_plan.json"
            write_manifest(manifest_path)
            write_membership_import_plan(import_plan_path)

            from weekly_action_items import build_weekly_action_items, render_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                membership_import_plan=import_plan_path,
            )
            report = render_weekly_action_items(payload)

            apply_item = next(
                item
                for item in payload["items"]
                if item["action_code"] == "run_membership_evidence_apply_preview"
            )
            self.assertEqual(payload["item_count"], 9)
            self.assertEqual(apply_item["category"], "backtest")
            self.assertIn("ready_to_import_count:2", apply_item["source"])
            self.assertIn("weeks_affected:210", apply_item["source"])
            self.assertIn("HIGH", apply_item["recommended_check"])
            self.assertIn("run_membership_evidence_apply_preview.ps1", apply_item["recommended_check"])
            self.assertIn("run_membership_evidence_apply_preview", report)

    def test_adds_current_membership_source_review_action_when_missing_tickers_remain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            source_path = root / "latest_sp500_current_membership_sources.json"
            review_status_path = root / "latest_sp500_current_membership_source_review_status.json"
            write_manifest(manifest_path)
            write_current_membership_sources(source_path)
            write_current_membership_source_review_status(review_status_path)

            from weekly_action_items import build_weekly_action_items, render_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                current_membership_sources=source_path,
                current_membership_source_review_status=review_status_path,
            )
            report = render_weekly_action_items(payload)

            source_item = next(
                item
                for item in payload["items"]
                if item["action_code"] == "review_current_membership_source_status"
            )
            self.assertEqual(payload["item_count"], 9)
            self.assertEqual(source_item["category"], "backtest")
            self.assertIn("matched_count:1", source_item["source"])
            self.assertIn("missing_count:1", source_item["source"])
            self.assertIn("missing_ticker_review_queue_count:1", source_item["source"])
            self.assertIn("ZZZ", source_item["recommended_check"])
            self.assertIn("缺失复核队列 1 条", source_item["recommended_check"])
            self.assertIn("sp500_current_membership_source_review_queue.csv", source_item["recommended_check"])
            self.assertIn("latest_sp500_current_membership_source_review_status.json", source_item["recommended_check"])
            self.assertIn("sp500_current_membership_source_review_decisions_template.csv", source_item["recommended_check"])
            self.assertIn("决策模板 status=ready, matched_open=1, missing_open=0", source_item["recommended_check"])
            self.assertIn("review_status:review_needed", source_item["source"])
            self.assertIn("review_open_count:1", source_item["source"])
            self.assertIn("review_resolved_count:0", source_item["source"])
            self.assertIn("decisions_template_status:ready", source_item["source"])
            self.assertIn("decisions_template_matched_open_count:1", source_item["source"])
            self.assertIn("decisions_template_missing_open_count:0", source_item["source"])
            self.assertIn("review_decision_status:missing", source_item["source"])
            self.assertIn("manual_decision_next_step:fill_decisions_template", source_item["source"])
            self.assertIn("decision_pending_tickers:ZZZ", source_item["source"])
            self.assertIn("状态报告 open=1, resolved=0", source_item["recommended_check"])
            self.assertIn("手工决策下一步=fill_decisions_template", source_item["recommended_check"])
            self.assertIn("待决策 ticker=ZZZ", source_item["recommended_check"])
            self.assertIn("latest_sp500_current_membership_sources.json", source_item["recommended_check"])
            self.assertIn("sp500_current_membership_source_intake_template.csv", source_item["recommended_check"])
            self.assertIn("review_current_membership_source_status", report)

    def test_adds_current_membership_source_file_action_when_official_csv_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            source_path = root / "latest_sp500_current_membership_sources.json"
            inbox_status_path = root / "latest_sp500_current_membership_source_inbox_status.json"
            write_manifest(manifest_path)
            write_current_membership_sources(source_path)
            write_current_membership_source_inbox_status(inbox_status_path)
            inbox_status = json.loads(inbox_status_path.read_text(encoding="utf-8-sig"))
            inbox_status.update(
                {
                    "status": "invalid",
                    "source_file_validation_status": "invalid",
                    "source_file_available_columns": [
                        "expected_ticker",
                        "intake_status",
                        "required_source_url",
                    ],
                    "next_action": "provide_valid_official_constituents_csv",
                }
            )
            inbox_status_path.write_text(
                json.dumps(inbox_status, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            source.update(
                {
                    "status": "fetch_failed",
                    "matched_count": 0,
                    "missing_count": 50,
                    "missing_tickers": ["ABT", "ADM", "AEP"],
                    "intake_expected_count": 50,
                    "intake_matched_count": 0,
                    "intake_missing_count": 50,
                    "intake_missing_tickers": ["ABT", "ADM", "AEP"],
                    "next_action": "retry_official_source_or_provide_official_constituents_csv",
                    "recommended_followup": "provide_official_constituents_csv",
                    "source_file_required_columns": ["Symbol", "Ticker"],
                    "source_file_next_command": (
                        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                        "scripts\\run_sp500_current_membership_sources.ps1 "
                        "-ProjectRoot <project_root> -SourceFile <official_constituents.csv>"
                    ),
                    "source_file_dry_run_command": (
                        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                        "scripts\\run_sp500_current_membership_sources.ps1 "
                        "-ProjectRoot <project_root> -DryRun -SourceFile <official_constituents.csv>"
                    ),
                    "source_file_request_file": "outputs/automation/sp500_current_membership_source_file_request.md",
                    "source_file_inbox": "inputs/sp500_current_membership/official_constituents.csv",
                    "source_file_inbox_next_command": (
                        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                        "scripts\\run_sp500_current_membership_sources.ps1 "
                        "-ProjectRoot <project_root> -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv"
                    ),
                    "source_file_inbox_dry_run_command": (
                        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                        "scripts\\run_sp500_current_membership_sources.ps1 "
                        "-ProjectRoot <project_root> -DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv"
                    ),
                    "source_file_inbox_exists": False,
                    "source_file_validation_status": "missing",
                    "source_file_acceptance_criteria": [
                        "has_symbol_or_ticker_column",
                        "at_least_400_tickers",
                    ],
                    "source_quality_flags": ["official_ticker_count_below_minimum"],
                    "fetch_error_type": "network_permission_denied",
                    "fetch_retryable_without_environment_change": False,
                    "fetch_error_next_action": "provide_official_constituents_csv_or_fix_network_permission",
                }
            )
            source_path.write_text(
                json.dumps(source, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items, render_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                current_membership_sources=source_path,
                current_membership_source_inbox_status=inbox_status_path,
            )
            report = render_weekly_action_items(payload)

            source_item = next(
                item
                for item in payload["items"]
                if item["action_code"] == "provide_official_constituents_csv"
            )
            self.assertEqual(source_item["category"], "backtest")
            self.assertIn("recommended_followup:provide_official_constituents_csv", source_item["source"])
            self.assertIn("source_file_required_columns:Symbol, Ticker", source_item["source"])
            self.assertIn(
                "source_file_accepted_ticker_columns:Symbol, Ticker, Ticker Symbol, Constituent Ticker, Constituent Symbol",
                source_item["source"],
            )
            self.assertIn("source_file_request_file:outputs/automation/sp500_current_membership_source_file_request.md", source_item["source"])
            self.assertIn("source_file_inbox:inputs/sp500_current_membership/official_constituents.csv", source_item["source"])
            self.assertIn("source_file_inbox_exists:false", source_item["source"])
            self.assertIn("source_file_validation_status:missing", source_item["source"])
            self.assertIn("source_file_inbox_status:invalid", source_item["source"])
            self.assertIn("source_file_inbox_next_action:provide_valid_official_constituents_csv", source_item["source"])
            self.assertIn(
                "source_file_inbox_available_columns:expected_ticker, intake_status, required_source_url",
                source_item["source"],
            )
            self.assertIn("fetch_error_type:network_permission_denied", source_item["source"])
            self.assertIn("fetch_retryable_without_environment_change:false", source_item["source"])
            self.assertIn(
                "fetch_error_next_action:provide_official_constituents_csv_or_fix_network_permission",
                source_item["source"],
            )
            self.assertIn("latest_sp500_current_membership_sources.json", source_item["recommended_check"])
            self.assertIn("sp500_current_membership_source_intake_template.csv", source_item["recommended_check"])
            self.assertIn("sp500_current_membership_source_file_request.md", source_item["recommended_check"])
            self.assertIn("inputs/sp500_current_membership/official_constituents.csv", source_item["recommended_check"])
            self.assertIn("inbox_status=invalid", source_item["recommended_check"])
            self.assertIn("fetch_error_type=network_permission_denied", source_item["recommended_check"])
            self.assertIn("fetch_retryable_without_environment_change=false", source_item["recommended_check"])
            self.assertIn(
                "fetch_error_next_action=provide_official_constituents_csv_or_fix_network_permission",
                source_item["recommended_check"],
            )
            self.assertIn(
                "inbox_available_columns=expected_ticker, intake_status, required_source_url",
                source_item["recommended_check"],
            )
            self.assertIn("提供官方 S&P Global constituents CSV", source_item["recommended_check"])
            self.assertIn("Symbol, Ticker", source_item["recommended_check"])
            self.assertIn("Ticker Symbol, Constituent Ticker, Constituent Symbol", source_item["recommended_check"])
            self.assertIn("-DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv", source_item["recommended_check"])
            self.assertIn("run_sp500_current_membership_sources.ps1", source_item["recommended_check"])
            self.assertIn("-SourceFileInbox inputs/sp500_current_membership/official_constituents.csv", source_item["recommended_check"])
            self.assertIn("latest_sp500_current_membership_source_inbox_status.json", source_item["recommended_check"])
            self.assertIn("inbox_next_action=provide_valid_official_constituents_csv", source_item["recommended_check"])
            self.assertIn("parsed_official_ticker_count=0", source_item["recommended_check"])
            self.assertIn("inbox_intake_missing_count=50", source_item["recommended_check"])
            self.assertIn("at_least_400_tickers", source_item["recommended_check"])
            self.assertIn("provide_official_constituents_csv", report)

    def test_current_membership_source_action_defaults_to_inbox_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            source_path = root / "latest_sp500_current_membership_sources.json"
            write_manifest(manifest_path)
            write_current_membership_sources(source_path)
            source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            source.update(
                {
                    "status": "fetch_failed",
                    "matched_count": 0,
                    "missing_count": 50,
                    "missing_tickers": ["ABT", "ADM"],
                    "intake_missing_count": 50,
                    "intake_missing_tickers": ["ABT", "ADM"],
                    "next_action": "retry_official_source_or_provide_official_constituents_csv",
                    "recommended_followup": "provide_official_constituents_csv",
                    "source_file_required_columns": ["Symbol", "Ticker"],
                    "source_file_request_file": "outputs/automation/sp500_current_membership_source_file_request.md",
                    "source_file_inbox": "inputs/sp500_current_membership/official_constituents.csv",
                    "source_file_inbox_exists": False,
                    "source_file_validation_status": "missing",
                    "source_file_acceptance_criteria": [
                        "has_symbol_or_ticker_column",
                        "at_least_400_tickers",
                    ],
                }
            )
            source.pop("source_file_next_command", None)
            source.pop("source_file_dry_run_command", None)
            source.pop("source_file_inbox_next_command", None)
            source.pop("source_file_inbox_dry_run_command", None)
            source_path.write_text(
                json.dumps(source, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                current_membership_sources=source_path,
            )

            source_item = next(
                item
                for item in payload["items"]
                if item["action_code"] == "provide_official_constituents_csv"
            )
            self.assertIn(
                "-DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv",
                source_item["recommended_check"],
            )
            self.assertIn(
                "-SourceFileInbox inputs/sp500_current_membership/official_constituents.csv",
                source_item["recommended_check"],
            )
            self.assertNotIn("-SourceFile <official_constituents.csv>", source_item["recommended_check"])

    def test_adds_backlog_reduction_action_when_weekly_action_items_are_increasing(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "latest_self_analysis_manifest.json"
            write_manifest(manifest_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            manifest["weekly_delivery_action_items_actual_count"] = 9
            manifest["weekly_delivery_action_items_actual_count_delta"] = 3
            manifest["weekly_delivery_action_items_actual_count_trend"] = "increasing"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items, render_weekly_action_items

            payload = build_weekly_action_items(manifest_path)
            report = render_weekly_action_items(payload)

            reduction = payload["items"][-1]
            self.assertEqual(payload["item_count"], 9)
            self.assertEqual(reduction["action_code"], "reduce_weekly_action_backlog")
            self.assertEqual(reduction["category"], "delivery_health")
            self.assertIn("actual_count:9", reduction["source"])
            self.assertIn("delta:3", reduction["source"])
            self.assertIn("trend:increasing", reduction["source"])
            self.assertIn("latest_weekly_action_items.json", reduction["recommended_check"])
            self.assertIn("manual_review_decisions.csv", reduction["recommended_check"])
            self.assertIn("人工待办压降", reduction["title"])
            self.assertIn("不修改正式模型参数", reduction["recommended_check"])
            self.assertIn("reduce_weekly_action_backlog", report)
            self.assertEqual(payload["backlog_reduction_plan"][0]["category"], "delivery_health")
            self.assertEqual(payload["backlog_reduction_plan"][0]["count"], 3)
            self.assertEqual(
                payload["backlog_reduction_plan"][0]["first_action"],
                "review_manual_review_backlog",
            )
            self.assertEqual(payload["backlog_reduction_plan"][0]["target_count_after_close"], 0)
            self.assertIn("manual_review_decisions.csv", payload["backlog_reduction_plan"][0]["close_condition"])
            self.assertEqual(
                payload["backlog_reduction_plan"][0]["actions"],
                [
                    "review_manual_review_backlog",
                    "review_delivery_health_issues",
                    "reduce_weekly_action_backlog",
                ],
            )
            self.assertEqual(payload["backlog_reduction_plan"][1]["category"], "data_quality")
            self.assertEqual(payload["backlog_reduction_plan"][1]["count"], 2)
            self.assertEqual(payload["backlog_reduction_plan"][1]["first_action"], "review_data_quality_score")
            self.assertEqual(payload["backlog_reduction_plan"][1]["target_count_after_close"], 0)
            self.assertIn("## 待办压降分流", report)
            self.assertIn("| delivery_health | 3 |", report)
            self.assertIn("| data_quality | 2 |", report)
            self.assertLess(report.index("## 待办压降分流"), report.index("## 处理事项"))
            self.assertLess(report.index("## 待办压降分流"), report.index("action_code"))

    def test_uses_backlog_reduction_template_when_action_comes_from_manifest_priority_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "latest_self_analysis_manifest.json"
            write_manifest(manifest_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            manifest["automation_priority_actions"].append("reduce_weekly_action_backlog")
            manifest["weekly_delivery_action_items_actual_count"] = 10
            manifest["weekly_delivery_action_items_actual_count_delta"] = 4
            manifest["weekly_delivery_action_items_actual_count_trend"] = "increasing"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8-sig",
            )

            from weekly_action_items import build_weekly_action_items

            payload = build_weekly_action_items(manifest_path)

            reduction = next(
                item
                for item in payload["items"]
                if item["action_code"] == "reduce_weekly_action_backlog"
            )
            self.assertEqual(reduction["category"], "delivery_health")
            self.assertIn("人工待办压降", reduction["title"])
            self.assertIn("actual_count:10", reduction["source"])
            self.assertIn("delta:4", reduction["source"])
            self.assertNotIn("复查动作码", reduction["title"])
            self.assertEqual(payload["backlog_reduction_plan"][0]["category"], "delivery_health")
            self.assertEqual(payload["backlog_reduction_plan"][0]["count"], 3)

    def test_adds_prediction_unavailable_action_when_forecast_gap_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            forecast_path = root / "latest_forecast_performance_review.json"
            write_manifest(manifest_path)
            write_forecast_performance_review(forecast_path)

            from weekly_action_items import build_weekly_action_items, render_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                forecast_performance=forecast_path,
            )
            report = render_weekly_action_items(payload)

            action = next(
                item
                for item in payload["items"]
                if item["action_code"] == "review_prediction_unavailable_signals"
            )
            self.assertEqual(action["category"], "model_tracking")
            self.assertIn("prediction_unavailable:87", action["source"])
            self.assertIn("pending_maturity:0", action["source"])
            self.assertIn("mature_evaluations:0", action["source"])
            self.assertIn("latest_forecast_performance_review.json", action["recommended_check"])
            self.assertIn("formal model parameters", action["recommended_check"])
            self.assertIn("review_prediction_unavailable_signals", report)

    def test_ignores_legacy_only_prediction_unavailable_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            forecast_path = root / "latest_forecast_performance_review.json"
            write_manifest(manifest_path)
            write_forecast_performance_review(
                forecast_path,
                prediction_unavailable=87,
                latest_prediction_unavailable=0,
                legacy_prediction_unavailable=87,
            )

            from weekly_action_items import build_weekly_action_items, render_weekly_action_items

            payload = build_weekly_action_items(
                manifest_path,
                forecast_performance=forecast_path,
            )
            report = render_weekly_action_items(payload)

            self.assertNotIn(
                "review_prediction_unavailable_signals",
                [item["action_code"] for item in payload["items"]],
            )
            self.assertNotIn("review_prediction_unavailable_signals", report)

    def test_cli_writes_json_and_markdown_action_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            output_path = root / "latest_weekly_action_items.json"
            report_path = root / "latest_weekly_action_items.md"
            write_manifest(manifest_path)
            write_data_health_review(root / "latest_data_health_review.json")
            write_current_membership_source_inbox_status(
                root / "latest_sp500_current_membership_source_inbox_status.json"
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "weekly_action_items.py"),
                    "--manifest",
                    str(manifest_path),
                    "--output",
                    str(output_path),
                    "--report",
                    str(report_path),
                    "--membership-import-plan",
                    str(root / "latest_membership_evidence_import_plan.json"),
                    "--current-membership-sources",
                    str(root / "latest_sp500_current_membership_sources.json"),
                    "--forecast-performance",
                    str(root / "latest_forecast_performance_review.json"),
                    "--manual-review-queue",
                    str(root / "latest_manual_review_queue.csv"),
                    "--data-health-review",
                    str(root / "latest_data_health_review.json"),
                    "--current-membership-source-inbox-status",
                    str(root / "latest_sp500_current_membership_source_inbox_status.json"),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            payload = json.loads(output_path.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["action_items_schema"], "weekly_action_items")
            self.assertEqual(payload["item_count"], 8)
            self.assertIn("review_delivery_health_issues", output)
            self.assertIn("每周人工处理清单", report_path.read_text(encoding="utf-8-sig"))

    def test_powershell_wrapper_static_contract(self):
        script = (PROJECT_ROOT / "scripts" / "show_weekly_action_items.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("weekly_action_items.py", script)
        self.assertIn("latest_self_analysis_manifest.json", script)
        self.assertIn("latest_weekly_action_items.json", script)
        self.assertIn("latest_weekly_action_items.md", script)
        self.assertIn("--manifest", script)
        self.assertIn("--output", script)
        self.assertIn("--report", script)
        self.assertIn("--membership-import-plan", script)
        self.assertIn("--current-membership-sources", script)
        self.assertIn("--current-membership-source-review-status", script)
        self.assertIn("--forecast-performance", script)
        self.assertIn("latest_sp500_current_membership_sources.json", script)
        self.assertIn("latest_sp500_current_membership_source_review_status.json", script)
        self.assertIn("latest_sp500_current_membership_source_inbox_status.json", script)
        self.assertIn("--current-membership-source-inbox-status", script)
        self.assertIn("latest_forecast_performance_review.json", script)
        self.assertIn("latest_manual_review_queue.csv", script)
        self.assertIn("--manual-review-queue", script)
        self.assertIn("latest_data_health_review.json", script)
        self.assertIn("--data-health-review", script)
        self.assertIn("codex-primary-runtime", script)


if __name__ == "__main__":
    unittest.main()
