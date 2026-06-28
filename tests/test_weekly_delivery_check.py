import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig")


def write_ready_delivery_files(root, as_of_date="2026-06-28"):
    write_text(
        Path(root) / "outputs" / "automation" / "latest_weekly_conclusion.md",
        "# 每周低估候选统一结论\n\n## 人工复核合并摘要\n",
    )
    write_text(
        Path(root) / "outputs" / "automation" / "manual_review_decisions_template.csv",
        "as_of_date,market,review_type,ticker,company,review_detail,decision_status,decision_note,reviewer,decided_at\n",
    )
    write_text(
        Path(root) / "outputs" / "automation" / "latest_weekly_action_items.md",
        "# 每周人工处理清单\n\n- 事项数量：7\n",
    )
    write_json(
        Path(root) / "outputs" / "automation" / "latest_weekly_action_items.json",
        {
            "action_items_schema": "weekly_action_items",
            "action_items_version": 1,
            "as_of_date": as_of_date,
            "automation_status": "manual_review_needed",
            "item_count": 7,
            "items": [
                {
                    "priority": 1,
                    "status": "open",
                    "action_code": "review_manual_queue",
                    "category": "manual_review",
                    "title": "检查本周人工复核队列",
                    "source": "manual_review_queue_count:12",
                    "recommended_check": "按优先级处理 12 条复核项。",
                }
            ],
        },
    )
    write_json(
        Path(root) / "outputs" / "automation" / "latest_weekly_conclusion.json",
        {
            "conclusion_schema": "weekly_conclusion",
            "conclusion_version": 1,
            "as_of_date": as_of_date,
            "status": "ready",
            "health": {
                "status": "needs_review",
                "score": 75,
                "reasons": ["automation_check:manual_review_needed", "manual_review_pending:12"],
            },
            "candidate_count_total": 64,
            "manual_review_queue": {"count": 12},
            "manual_review_decisions": {"pending_count": 12},
            "manual_review_merge_summary": {
                "path": "outputs/automation/latest_manual_review_decision_merge.json",
                "exists": False,
            },
            "outputs": {
                "markdown": "outputs/automation/latest_weekly_conclusion.md",
                "json": "outputs/automation/latest_weekly_conclusion.json",
                "manual_review_decisions_template": "outputs/automation/manual_review_decisions_template.csv",
            },
        },
    )


class WeeklyDeliveryCheckTests(unittest.TestCase):
    def test_delivery_check_is_ready_when_final_outputs_exist_and_are_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root)

            from weekly_delivery_check import render_delivery_check, run_delivery_check

            result = run_delivery_check(root, today="2026-06-28", max_age_days=8)
            report = render_delivery_check(result)

            self.assertEqual(result["delivery_check_schema"], "weekly_delivery_check")
            self.assertEqual(result["delivery_check_version"], 1)
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["freshness_status"], "fresh")
            self.assertEqual(result["candidate_count_total"], 64)
            self.assertEqual(result["conclusion_health_status"], "needs_review")
            self.assertEqual(result["conclusion_health_score"], 75)
            self.assertEqual(result["action_items_status"], "ready")
            self.assertEqual(result["action_items_freshness_status"], "fresh")
            self.assertEqual(result["action_items_count"], 7)
            self.assertEqual(
                result["conclusion_health_reasons"],
                ["automation_check:manual_review_needed", "manual_review_pending:12"],
            )
            self.assertEqual(result["manual_review_queue_count"], 12)
            self.assertEqual(result["manual_review_pending_count"], 12)
            self.assertEqual(result["missing_outputs"], [])
            self.assertIn("# 每周最终交付验收", report)
            self.assertIn("- 总体状态：ready", report)
            self.assertIn("needs_review / 75", report)
            self.assertIn("每周人工处理清单：ready / 7", report)
            self.assertIn("- 候选总数：64", report)

    def test_delivery_check_needs_attention_when_conclusion_health_needs_fix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root)
            conclusion_path = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            conclusion = json.loads(conclusion_path.read_text(encoding="utf-8-sig"))
            conclusion["health"] = {
                "status": "needs_fix",
                "score": 40,
                "reasons": ["missing_inputs:2"],
            }
            write_json(conclusion_path, conclusion)

            from weekly_delivery_check import render_delivery_check, run_delivery_check

            result = run_delivery_check(root, today="2026-06-28", max_age_days=8)
            report = render_delivery_check(result)

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["conclusion_health_status"], "needs_fix")
            self.assertEqual(result["conclusion_health_score"], 40)
            self.assertIn("conclusion_health_needs_fix", result["attention_reasons"])
            self.assertIn("needs_fix / 40", report)

    def test_delivery_check_needs_attention_when_required_final_output_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root)
            (root / "outputs" / "automation" / "manual_review_decisions_template.csv").unlink()

            from weekly_delivery_check import render_delivery_check, run_delivery_check

            result = run_delivery_check(root, today="2026-06-28", max_age_days=8)
            report = render_delivery_check(result)

            self.assertEqual(result["status"], "needs_attention")
            self.assertIn("missing_outputs", result["attention_reasons"])
            self.assertEqual(result["missing_outputs"], ["manual_review_decisions_template"])
            self.assertIn("manual_review_decisions_template", report)

    def test_delivery_check_needs_attention_when_weekly_action_items_are_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root)
            (root / "outputs" / "automation" / "latest_weekly_action_items.json").unlink()
            (root / "outputs" / "automation" / "latest_weekly_action_items.md").unlink()

            from weekly_delivery_check import render_delivery_check, run_delivery_check

            result = run_delivery_check(root, today="2026-06-28", max_age_days=8)
            report = render_delivery_check(result)

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["action_items_status"], "missing")
            self.assertIn("missing_outputs", result["attention_reasons"])
            self.assertEqual(
                result["missing_outputs"],
                ["weekly_action_items_json", "weekly_action_items_markdown"],
            )
            self.assertIn("weekly_action_items_json", report)

    def test_delivery_check_needs_attention_when_weekly_action_items_are_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root, as_of_date="2026-06-10")
            conclusion_path = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            conclusion = json.loads(conclusion_path.read_text(encoding="utf-8-sig"))
            conclusion["as_of_date"] = "2026-06-28"
            write_json(conclusion_path, conclusion)

            from weekly_delivery_check import run_delivery_check

            result = run_delivery_check(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["action_items_status"], "stale")
            self.assertEqual(result["action_items_freshness_status"], "stale")
            self.assertIn("stale_action_items_date", result["attention_reasons"])

    def test_delivery_check_needs_attention_when_conclusion_json_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root, as_of_date="2026-06-01")

            from weekly_delivery_check import run_delivery_check

            result = run_delivery_check(root, today="2026-06-28", max_age_days=8)

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["freshness_status"], "stale")
            self.assertIn("stale_conclusion_date", result["attention_reasons"])

    def test_cli_writes_delivery_check_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_delivery_files(root)
            output = root / "outputs" / "automation" / "latest_weekly_delivery_check.json"
            history = root / "outputs" / "automation" / "weekly_delivery_check_history.jsonl"

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "weekly_delivery_check.py"),
                    "--project-root",
                    str(root),
                    "--today",
                    "2026-06-28",
                    "--output",
                    str(output),
                    "--history",
                    str(history),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["delivery_check_schema"], "weekly_delivery_check")
            self.assertEqual(payload["status"], "ready")
            self.assertIn("每周最终交付验收", result.stdout)
            history_rows = [
                json.loads(line)
                for line in history.read_text(encoding="utf-8-sig").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(history_rows), 1)
            self.assertEqual(history_rows[0]["history_schema"], "weekly_delivery_check_history")
            self.assertEqual(history_rows[0]["history_version"], 1)
            self.assertEqual(history_rows[0]["delivery_check_schema"], "weekly_delivery_check")
            self.assertEqual(history_rows[0]["status"], "ready")

    def test_powershell_wrapper_static_contract(self):
        script = (PROJECT_ROOT / "scripts" / "run_weekly_delivery_check.ps1").read_text(encoding="utf-8-sig")

        self.assertIn("weekly_delivery_check.py", script)
        self.assertIn("latest_weekly_delivery_check.json", script)
        self.assertIn("weekly_delivery_check_history.jsonl", script)
        self.assertIn("--history", script)
        self.assertIn("-NoProfile -ExecutionPolicy Bypass", script)
        self.assertIn("codex-primary-runtime", script)


if __name__ == "__main__":
    unittest.main()
