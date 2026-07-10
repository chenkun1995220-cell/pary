import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_fixture(root):
    automation_dir = root / "outputs" / "automation"
    automation_dir.mkdir(parents=True, exist_ok=True)
    summary = "\n".join(
        [
            "# US Point-in-Time Backtest Summary",
            "",
            "- Run time: 2026-06-28 16:34:11",
            "- OutputRoot: F:\\chatgptssd\\project2\\outputs\\backtests\\us_3y_weekly",
            "- Weeks completed: 8",
            "- Weeks failed: 0",
            "- Membership evidence verified: 624/4006 (15.6%)",
            "- Weak evidence rows: 3382",
            "- Evidence status: evidence_review_needed",
            "- Weak evidence weeks: 8",
            "- Evidence next action: supplement_verified_membership_evidence",
            "- Backtest report: F:\\chatgptssd\\project2\\outputs\\backtests\\us_3y_weekly\\backtest_report.md",
            "- Data leakage audit: F:\\chatgptssd\\project2\\outputs\\backtests\\us_3y_weekly\\data_leakage_audit.md",
            "- Model comparison: F:\\chatgptssd\\project2\\outputs\\backtests\\us_3y_weekly\\model_comparison.csv",
            "- Log: F:\\chatgptssd\\project2\\outputs\\automation\\us_point_in_time_backtest_20260626_233041.log",
            "",
        ]
    )
    (automation_dir / "latest_backtest_summary.md").write_text(summary, encoding="utf-8-sig")
    gaps = {
        "schema": "membership_evidence_gap_report",
        "version": 1,
        "membership_path": "outputs\\backtests\\us_3y_weekly\\historical_membership.csv",
        "total_rows": 73971,
        "verified_rows": 8328,
        "weak_rows": 65643,
        "gap_count": 425,
        "returned_gap_count": 2,
        "gaps": [
            {
                "rank": 1,
                "ticker": "ABT",
                "company_name": "Abbott Laboratories",
                "effective_date": "1957-03-04",
                "current_evidence": "secondary",
                "weeks_affected": 156,
                "first_week": "2023-07-07",
                "last_week": "2026-06-26",
                "recommended_action": "supplement_official_spglobal_source",
            },
            {
                "rank": 2,
                "ticker": "ADM",
                "company_name": "Archer Daniels Midland",
                "effective_date": "1957-03-04",
                "current_evidence": "secondary",
                "weeks_affected": 156,
                "first_week": "2023-07-07",
                "last_week": "2026-06-26",
                "recommended_action": "supplement_official_spglobal_source",
            },
        ],
    }
    (automation_dir / "latest_membership_evidence_gaps.json").write_text(
        json.dumps(gaps, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )
    return automation_dir / "latest_backtest_summary.md"


def write_policy(root):
    policy = root / "data" / "config" / "sp500_historical_evidence_policy.json"
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text(
        json.dumps(
            {
                "policy_schema": "sp500_historical_evidence_policy",
                "policy_version": 1,
                "status": "evidence_ceiling_confirmed",
                "effective_date": "2026-07-11",
                "official_source_acquisition_closed": True,
                "limited_backtest_only": True,
                "recurring_supplement_request_enabled": False,
                "formal_backtest_expansion_allowed": False,
                "historical_membership_auto_update_allowed": False,
                "formal_model_change_allowed": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8-sig",
    )
    return policy


class BacktestEvidenceReviewTests(unittest.TestCase):
    def test_builds_review_from_summary_and_membership_gap_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = write_fixture(root)
            policy = write_policy(root)

            from backtest_evidence_review import (
                build_backtest_evidence_review,
                render_backtest_evidence_review,
            )

            payload = build_backtest_evidence_review(
                summary,
                as_of_date="2026-07-11",
                policy=policy,
            )
            report = render_backtest_evidence_review(payload)

            self.assertEqual(payload["review_schema"], "backtest_evidence_review")
            self.assertEqual(payload["review_version"], 1)
            self.assertEqual(payload["as_of_date"], "2026-07-11")
            self.assertEqual(payload["backtest_as_of_date"], "2026-06-28")
            self.assertEqual(payload["status"], "evidence_ceiling_confirmed")
            self.assertEqual(payload["evidence_ceiling_status"], "evidence_ceiling_confirmed")
            self.assertEqual(payload["evidence_ceiling_effective_date"], "2026-07-11")
            self.assertEqual(payload["backtest_mode"], "limited_verified_only")
            self.assertTrue(payload["official_source_acquisition_closed"])
            self.assertTrue(payload["limited_backtest_only"])
            self.assertFalse(payload["recurring_supplement_request_enabled"])
            self.assertEqual(payload["weeks_completed"], 8)
            self.assertEqual(payload["weeks_failed"], 0)
            self.assertEqual(payload["weak_evidence_rows"], 3382)
            self.assertEqual(payload["weak_evidence_weeks"], 8)
            self.assertEqual(payload["verified_membership_ratio"], 0.156)
            self.assertFalse(payload["formal_model_upgrade_allowed"])
            self.assertEqual(payload["recommended_action"], "maintain_limited_backtest")
            self.assertEqual(payload["source_evidence_next_action"], "supplement_verified_membership_evidence")
            self.assertEqual(payload["gap_report"]["gap_count"], 425)
            self.assertEqual(payload["gap_report"]["top_gaps"][0]["ticker"], "ABT")
            self.assertEqual(payload["membership_evidence_unresolved_gap_count"], 425)
            self.assertEqual(payload["membership_evidence_action_required_count"], 0)
            self.assertEqual(payload["membership_evidence_action_queue_count"], 0)
            self.assertEqual(payload["membership_evidence_action_unqueued_count"], 0)
            self.assertEqual(payload["membership_evidence_action_queue"], [])
            self.assertFalse(payload["backtest_sample_expansion_allowed"])
            self.assertEqual(
                payload["backtest_sample_expansion_decision"],
                "do_not_expand_backtest_sample",
            )
            self.assertEqual(payload["required_verified_membership_ratio_for_expansion"], 0.5)
            self.assertIn("verified_membership_ratio_below_threshold", payload["backtest_sample_expansion_reason"])
            self.assertIn("weak_evidence_rows_present", payload["backtest_sample_expansion_reason"])
            self.assertIn("evidence_ceiling_confirmed_limited_backtest_only", payload["backtest_sample_expansion_reason"])
            self.assertNotIn("membership_evidence_actions_open", payload["backtest_sample_expansion_reason"])
            self.assertEqual(payload["membership_evidence_gate_status"], "blocked")
            self.assertEqual(payload["membership_evidence_gate_decision"], "verified_only_no_expansion")
            self.assertFalse(payload["historical_membership_auto_update_allowed"])
            self.assertTrue(payload["membership_evidence_tier_policy"]["verified"]["expansion_eligible"])
            self.assertFalse(payload["membership_evidence_tier_policy"]["secondary"]["expansion_eligible"])
            self.assertFalse(payload["membership_evidence_tier_policy"]["insufficient"]["expansion_eligible"])
            self.assertIn("secondary", payload["membership_evidence_blocking_tiers"])
            self.assertEqual(payload["membership_evidence_tier_counts"]["secondary_gap_tickers"], 2)
            self.assertEqual(payload["membership_evidence_tier_counts"]["verified_rows"], 8328)
            self.assertEqual(payload["membership_evidence_tier_counts"]["weak_rows"], 65643)

            self.assertIn("# 回测证据复核结论", report)
            self.assertIn("## 回测样本扩展决策", report)
            self.assertIn("## 成员证据分层闸门", report)
            self.assertIn("verified_only_no_expansion", report)
            self.assertIn("secondary", report)
            self.assertIn("不得自动更新 historical_membership.csv", report)
            self.assertIn("扩样决策：do_not_expand_backtest_sample", report)
            self.assertIn("扩样允许：false", report)
            self.assertIn("evidence_ceiling_confirmed", report)
            self.assertIn("limited_verified_only", report)
            self.assertIn("证据上限已确认", report)
            self.assertIn("15.60%", report)
            self.assertIn("ABT", report)
            self.assertIn("不得自动升级正式模型", report)
            self.assertIn("不抓取行情", report)
            self.assertIn("不重新回测", report)

    def test_cli_writes_json_and_markdown_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = write_fixture(root)
            policy = write_policy(root)
            output = root / "outputs" / "automation" / "latest_backtest_evidence_review.json"
            report = root / "outputs" / "automation" / "latest_backtest_evidence_review.md"

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "backtest_evidence_review.py"),
                    "--summary",
                    str(summary),
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--policy",
                    str(policy),
                    "--as-of-date",
                    "2026-07-11",
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
            self.assertEqual(payload["as_of_date"], "2026-07-11")
            self.assertEqual(payload["backtest_as_of_date"], "2026-06-28")
            self.assertEqual(payload["status"], "evidence_ceiling_confirmed")
            self.assertFalse(payload["formal_model_upgrade_allowed"])
            self.assertIn("回测证据复核结论", report.read_text(encoding="utf-8-sig"))
            self.assertIn("latest_backtest_evidence_review.md", combined)

    def test_powershell_wrapper_and_bundle_include_backtest_evidence_review(self):
        wrapper = (PROJECT_ROOT / "scripts" / "run_backtest_evidence_review.ps1").read_text(
            encoding="utf-8-sig"
        )
        bundle = (PROJECT_ROOT / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("backtest_evidence_review.py", wrapper)
        self.assertIn("latest_backtest_summary.md", wrapper)
        self.assertIn("latest_backtest_evidence_review.json", wrapper)
        self.assertIn("latest_backtest_evidence_review.md", wrapper)
        self.assertIn("sp500_historical_evidence_policy.json", wrapper)
        self.assertIn("run_backtest_evidence_review", bundle)
        self.assertLess(
            bundle.index("run_data_health_review"),
            bundle.index("run_backtest_evidence_review"),
        )
        self.assertLess(
            bundle.index("run_backtest_evidence_review"),
            bundle.index("show_weekly_action_items"),
        )


if __name__ == "__main__":
    unittest.main()
