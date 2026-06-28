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
        },
    }
    Path(path).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


class WeeklyActionItemsTests(unittest.TestCase):
    def test_builds_action_items_from_self_analysis_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "latest_self_analysis_manifest.json"
            write_manifest(manifest_path)

            from weekly_action_items import build_weekly_action_items, render_weekly_action_items

            payload = build_weekly_action_items(manifest_path)
            report = render_weekly_action_items(payload)

            self.assertEqual(payload["action_items_schema"], "weekly_action_items")
            self.assertEqual(payload["action_items_version"], 1)
            self.assertEqual(payload["as_of_date"], "2026-06-28")
            self.assertEqual(payload["source_manifest"], str(manifest_path))
            self.assertEqual(payload["automation_status"], "manual_review_needed")
            self.assertEqual(payload["item_count"], 7)

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
            self.assertIn("needs_review", delivery["recommended_check"])

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
            self.assertIn("review_data_quality_score", report)
            self.assertIn("review_forecast_performance", report)
            self.assertIn("人工复核积压", report)
            self.assertIn("不抓取行情", report)

    def test_cli_writes_json_and_markdown_action_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "latest_self_analysis_manifest.json"
            output_path = root / "latest_weekly_action_items.json"
            report_path = root / "latest_weekly_action_items.md"
            write_manifest(manifest_path)

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
            self.assertEqual(payload["item_count"], 7)
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
        self.assertIn("codex-primary-runtime", script)


if __name__ == "__main__":
    unittest.main()
