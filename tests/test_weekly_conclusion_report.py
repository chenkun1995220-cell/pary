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
            self.assertIn("# 每周低估候选统一结论", markdown)
            self.assertIn("| US | MSFT | Microsoft | 82.5 | 120.00 | 96.00 |", markdown)
            self.assertIn("研究筛选和人工复核用途", markdown)

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
            self.assertEqual(payload["automation"]["automation_check"]["status"], "manual_review_needed")
            self.assertEqual(
                payload["automation"]["automation_check"]["priority_actions"],
                ["review_manual_queue", "review_candidate_findings"],
            )
            self.assertIn("- 优先动作：review_manual_queue", markdown)

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

    def test_powershell_wrapper_static_contract(self):
        script = (PROJECT_ROOT / "scripts" / "show_weekly_conclusion.ps1").read_text(encoding="utf-8-sig")

        self.assertIn("weekly_conclusion_report.py", script)
        self.assertIn("latest_weekly_conclusion.md", script)
        self.assertIn("latest_weekly_conclusion.json", script)
        self.assertIn("-NoProfile -ExecutionPolicy Bypass", script)
        self.assertIn("codex-primary-runtime", script)


if __name__ == "__main__":
    unittest.main()
