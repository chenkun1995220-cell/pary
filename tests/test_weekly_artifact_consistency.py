import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MARKETS = {
    "US": "us_universe",
    "CN": "cn_universe",
    "HK": "hk_universe",
}
ACTION_POLICY_ARTIFACTS = {
    "manifest": "latest_self_analysis_manifest.json",
    "automation_check": "latest_automation_check.json",
    "action_items": "latest_weekly_action_items.json",
    "ops_check": "latest_weekly_ops_check.json",
    "conclusion": "latest_weekly_conclusion.json",
    "delivery": "latest_weekly_delivery_check.json",
}


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_summary(
    path,
    candidate_count,
    extra=None,
    run_time="2026-07-11 14:25:00",
    run_start_time="2026-07-11 14:05:00",
):
    fields = {
        "Run start time": run_start_time,
        "Run time": run_time,
        "Candidate count": str(candidate_count),
    }
    fields.update(extra or {})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Weekly Summary\n\n" + "\n".join(f"- {key}: {value}" for key, value in fields.items()) + "\n",
        encoding="utf-8-sig",
    )


def write_fixture(root):
    candidate_counts = {"US": 2, "CN": 2, "HK": 2}
    for market, directory in MARKETS.items():
        market_dir = root / "outputs" / directory
        rows = [
            {"ticker": f"{market}1", "score": "90"},
            {"ticker": f"{market}2", "score": "85"},
        ]
        write_csv(market_dir / "candidate_pool.csv", rows)
        write_csv(
            market_dir / "forecast_evaluations.csv",
            [
                {"ticker": f"{market}1", "evaluation_status": "evaluated"},
                {"ticker": f"{market}2", "evaluation_status": "prediction_unavailable"},
            ],
        )
        (market_dir / "latest_investment_summary.md").write_text(
            "# Investment summary\n\n- \u6210\u719f\u8bc4\u4ef7\u6837\u672c\uff1a1\n",
            encoding="utf-8-sig",
        )
        (market_dir / "performance_report.md").write_text(
            "# Performance report\n\n- \u6210\u719f\u8bc4\u4ef7\uff1a1\n",
            encoding="utf-8-sig",
        )
        (market_dir / "model_audit.md").write_text(
            "# Model audit\n\n- \u6210\u719f\u8bc4\u4ef7\u6837\u672c\uff1a1\n",
            encoding="utf-8-sig",
        )
        write_summary(market_dir / "latest_run_summary.md", candidate_counts[market])

    quote_path = root / "outputs" / "us_universe" / "market_quotes.csv"
    write_csv(
        quote_path,
        [
            {"ticker": "AAA", "price": "10", "quote_date": "2026-07-10"},
            {"ticker": "BBB", "price": "20", "quote_date": "2026-07-11"},
        ],
    )
    identity_audit_path = root / "outputs" / "us_universe" / "sec_identity_audit.csv"
    write_csv(
        identity_audit_path,
        [
            {
                "ticker": "XOM",
                "configured_cik": "34088",
                "sec_candidate_ciks": "2115436",
                "selected_cik": "34088",
                "configured_company_name": "ExxonMobil",
                "sec_candidate_names": "ExxonMobil Holdings Corp",
                "resolution": "configured_identity_preserved",
            }
        ],
    )
    write_summary(
        root / "outputs" / "us_universe" / "latest_run_summary.md",
        2,
        {
            "Quote snapshot policy": "runtime_output_only",
            "Quote snapshot file": str(quote_path),
            "Quote snapshot rows": "2",
            "Quote date min": "2026-07-10",
            "Quote date max": "2026-07-11",
            "Quote snapshot sha256": sha256(quote_path),
            "SEC identity conflict count": "1",
            "SEC identity audit": str(identity_audit_path),
        },
    )

    automation = root / "outputs" / "automation"
    automation.mkdir(parents=True, exist_ok=True)
    for filename in ACTION_POLICY_ARTIFACTS.values():
        (automation / filename).write_text(
            json.dumps({"action_policy_version": 1}),
            encoding="utf-8",
        )
    (automation / "latest_weekly_conclusion.json").write_text(
        json.dumps(
            {
                "action_policy_version": 1,
                "as_of_date": "2026-07-11",
                "candidate_count_total": 6,
                "markets": [
                    {"market": market, "candidate_count": count}
                    for market, count in candidate_counts.items()
                ],
            }
        ),
        encoding="utf-8",
    )
    (automation / "latest_weekly_delivery_check.json").write_text(
        json.dumps(
            {
                "action_policy_version": 1,
                "as_of_date": "2026-07-11",
                "candidate_count_total": 6,
                "conclusion_status": "ready",
            }
        ),
        encoding="utf-8",
    )
    return quote_path


class WeeklyArtifactConsistencyTests(unittest.TestCase):
    def test_ready_when_dates_counts_delivery_and_runtime_snapshot_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)

            from weekly_artifact_consistency import build_weekly_artifact_consistency

            payload = build_weekly_artifact_consistency(root, "2026-07-11", max_age_days=8)

            self.assertEqual(payload["consistency_schema"], "weekly_artifact_consistency")
            self.assertEqual(payload["consistency_version"], 1)
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["candidate_count_total"], 6)
            self.assertEqual(payload["runtime_quote_snapshot"]["git_policy"], "runtime_output_only")
            self.assertEqual(payload["runtime_quote_snapshot"]["row_count"], 2)
            self.assertEqual(payload["sec_identity_audit"]["row_count"], 1)
            self.assertEqual(payload["sec_identity_audit"]["summary_row_count"], 1)
            self.assertEqual(payload["sec_identity_audit"]["unresolved_count"], 0)
            market_rows = {row["market"]: row for row in payload["markets"]}
            self.assertEqual(market_rows["US"]["run_started_at"], "2026-07-11 14:05:00")
            self.assertEqual(market_rows["US"]["run_completed_at"], "2026-07-11 14:25:00")
            self.assertEqual(payload["issues"], [])

    def test_consistency_reports_complete_action_policy_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)

            from weekly_artifact_consistency import build_weekly_artifact_consistency

            payload = build_weekly_artifact_consistency(root, "2026-07-11")

            self.assertEqual(payload["action_policy_contract_status"], "valid")
            self.assertEqual(payload["action_policy_version"], 1)
            self.assertEqual(
                payload["action_policy_versions"],
                {key: 1 for key in ACTION_POLICY_ARTIFACTS},
            )

    def test_consistency_reports_missing_action_policy_version_across_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload.pop("action_policy_version")
            path.write_text(json.dumps(payload), encoding="utf-8")

            from weekly_artifact_consistency import build_weekly_artifact_consistency

            result = build_weekly_artifact_consistency(root, "2026-07-11")

            self.assertEqual(result["action_policy_contract_status"], "missing")
            self.assertEqual(result["status"], "needs_attention")
            self.assertIsNone(result["action_policy_version"])
            self.assertEqual(
                result["issues"],
                [
                    "action_items_action_policy_version_missing",
                    "action_policy_version_inconsistent",
                ],
            )

    def test_consistency_rejects_consistently_old_action_policy_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            automation = root / "outputs" / "automation"
            for filename in ACTION_POLICY_ARTIFACTS.values():
                path = automation / filename
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["action_policy_version"] = 0
                path.write_text(json.dumps(payload), encoding="utf-8")

            from weekly_artifact_consistency import build_weekly_artifact_consistency

            result = build_weekly_artifact_consistency(root, "2026-07-11")

            self.assertEqual(result["action_policy_contract_status"], "mismatch")
            self.assertEqual(result["status"], "needs_attention")
            self.assertIsNone(result["action_policy_version"])
            self.assertEqual(
                result["action_policy_versions"],
                {key: 0 for key in ACTION_POLICY_ARTIFACTS},
            )
            self.assertEqual(
                set(result["issues"]),
                {
                    f"{key}_action_policy_version_mismatch"
                    for key in ACTION_POLICY_ARTIFACTS
                },
            )
            self.assertNotIn("action_policy_version_inconsistent", result["issues"])

    def test_consistency_rejects_mixed_action_policy_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            path = root / "outputs" / "automation" / "latest_weekly_delivery_check.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["action_policy_version"] = 0
            path.write_text(json.dumps(payload), encoding="utf-8")

            from weekly_artifact_consistency import build_weekly_artifact_consistency

            result = build_weekly_artifact_consistency(root, "2026-07-11")

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["action_policy_contract_status"], "mismatch")
            self.assertIn("delivery_action_policy_version_mismatch", result["issues"])
            self.assertIn("action_policy_version_inconsistent", result["issues"])

    def test_consistency_treats_unparseable_action_policy_version_as_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            path = root / "outputs" / "automation" / "latest_weekly_ops_check.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["action_policy_version"] = "not-a-version"
            path.write_text(json.dumps(payload), encoding="utf-8")

            from weekly_artifact_consistency import build_weekly_artifact_consistency

            result = build_weekly_artifact_consistency(root, "2026-07-11")

            self.assertEqual(result["status"], "needs_attention")
            self.assertEqual(result["action_policy_contract_status"], "mismatch")
            self.assertIsNone(result["action_policy_versions"]["ops_check"])
            self.assertIn("ops_check_action_policy_version_mismatch", result["issues"])
            self.assertNotIn("ops_check_action_policy_version_missing", result["issues"])
            self.assertIn("action_policy_version_inconsistent", result["issues"])

    def test_blocks_missing_or_unresolved_sec_identity_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            audit_path = root / "outputs" / "us_universe" / "sec_identity_audit.csv"
            audit_path.unlink()

            from weekly_artifact_consistency import build_weekly_artifact_consistency

            missing = build_weekly_artifact_consistency(root, "2026-07-11")
            self.assertIn("sec_identity_audit_missing", missing["issues"])

            write_csv(
                audit_path,
                [
                    {
                        "ticker": "XOM",
                        "configured_cik": "34088",
                        "sec_candidate_ciks": "2115436",
                        "selected_cik": "2115436",
                        "configured_company_name": "ExxonMobil",
                        "sec_candidate_names": "ExxonMobil Holdings Corp",
                        "resolution": "unresolved",
                    }
                ],
            )
            unresolved = build_weekly_artifact_consistency(root, "2026-07-11")
            self.assertIn("sec_identity_audit_unresolved_conflicts", unresolved["issues"])
            self.assertEqual(unresolved["sec_identity_audit"]["unresolved_count"], 1)

    def test_blocks_sec_identity_audit_summary_count_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            summary_path = root / "outputs" / "us_universe" / "latest_run_summary.md"
            text = summary_path.read_text(encoding="utf-8-sig")
            summary_path.write_text(
                text.replace("- SEC identity conflict count: 1", "- SEC identity conflict count: 0"),
                encoding="utf-8-sig",
            )

            from weekly_artifact_consistency import build_weekly_artifact_consistency

            payload = build_weekly_artifact_consistency(root, "2026-07-11")
            self.assertIn("sec_identity_audit_row_count_mismatch", payload["issues"])

    def test_blocks_closure_outputs_older_than_market_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            market_summaries = [
                root / "outputs" / directory / "latest_run_summary.md"
                for directory in MARKETS.values()
            ]
            conclusion = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            delivery = root / "outputs" / "automation" / "latest_weekly_delivery_check.json"
            for summary in market_summaries:
                os.utime(summary, (1_700_000_300, 1_700_000_300))
            os.utime(conclusion, (1_700_000_200, 1_700_000_200))
            os.utime(delivery, (1_700_000_100, 1_700_000_100))

            from weekly_artifact_consistency import build_weekly_artifact_consistency

            payload = build_weekly_artifact_consistency(root, "2026-07-11")

            self.assertIn("conclusion_older_than_market_outputs", payload["issues"])
            self.assertIn("delivery_older_than_conclusion", payload["issues"])
            self.assertFalse(payload["closure_order"]["conclusion_after_markets"])
            self.assertFalse(payload["closure_order"]["delivery_after_conclusion"])

    def test_blocks_summary_candidate_count_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            write_summary(root / "outputs" / "cn_universe" / "latest_run_summary.md", 3)

            from weekly_artifact_consistency import build_weekly_artifact_consistency

            payload = build_weekly_artifact_consistency(root, "2026-07-11")

            self.assertEqual(payload["status"], "needs_attention")
            self.assertIn("cn_summary_candidate_count_mismatch", payload["issues"])

    def test_blocks_mature_evaluation_count_mismatch_across_market_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            (root / "outputs" / "us_universe" / "latest_investment_summary.md").write_text(
                "# Investment summary\n\n- \u6210\u719f\u8bc4\u4ef7\u6837\u672c\uff1a0\n",
                encoding="utf-8-sig",
            )

            from weekly_artifact_consistency import build_weekly_artifact_consistency

            payload = build_weekly_artifact_consistency(root, "2026-07-11")

            self.assertEqual(payload["status"], "needs_attention")
            self.assertIn("us_mature_evaluation_count_mismatch", payload["issues"])
            market_rows = {row["market"]: row for row in payload["markets"]}
            self.assertEqual(market_rows["US"]["mature_evaluation_counts"]["evaluations"], 1)
            self.assertEqual(market_rows["US"]["mature_evaluation_counts"]["investment_summary"], 0)

    def test_blocks_stale_market_and_closure_date_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            write_summary(root / "outputs" / "hk_universe" / "latest_run_summary.md", 2, run_time="2026-06-30 14:15:00")
            delivery_path = root / "outputs" / "automation" / "latest_weekly_delivery_check.json"
            delivery = json.loads(delivery_path.read_text(encoding="utf-8"))
            delivery["as_of_date"] = "2026-07-10"
            delivery_path.write_text(json.dumps(delivery), encoding="utf-8")

            from weekly_artifact_consistency import build_weekly_artifact_consistency

            payload = build_weekly_artifact_consistency(root, "2026-07-11", max_age_days=8)

            self.assertIn("hk_run_summary_stale", payload["issues"])
            self.assertIn("closure_as_of_date_mismatch", payload["issues"])

    def test_blocks_fresh_market_summaries_from_different_batch_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            write_summary(
                root / "outputs" / "hk_universe" / "latest_run_summary.md",
                2,
                run_time="2026-07-10 14:15:00",
            )

            from weekly_artifact_consistency import build_weekly_artifact_consistency

            payload = build_weekly_artifact_consistency(root, "2026-07-11", max_age_days=8)

            self.assertEqual(payload["status"], "needs_attention")
            self.assertIn("market_run_date_mismatch", payload["issues"])
            self.assertEqual(payload["market_run_dates"], ["2026-07-10", "2026-07-11"])

    def test_blocks_conclusion_delivery_and_market_count_mismatches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            conclusion_path = root / "outputs" / "automation" / "latest_weekly_conclusion.json"
            conclusion = json.loads(conclusion_path.read_text(encoding="utf-8"))
            conclusion["markets"][0]["candidate_count"] = 1
            conclusion["candidate_count_total"] = 5
            conclusion_path.write_text(json.dumps(conclusion), encoding="utf-8")

            from weekly_artifact_consistency import build_weekly_artifact_consistency

            payload = build_weekly_artifact_consistency(root, "2026-07-11")

            self.assertIn("us_conclusion_candidate_count_mismatch", payload["issues"])
            self.assertIn("conclusion_candidate_count_total_mismatch", payload["issues"])
            self.assertIn("delivery_candidate_count_total_mismatch", payload["issues"])

    def test_blocks_snapshot_metadata_or_legacy_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            quote_path = write_fixture(root)
            quote_path.write_text(quote_path.read_text(encoding="utf-8-sig") + "BROKEN\n", encoding="utf-8-sig")
            legacy = root / "data" / "samples" / "us_universe_quotes.csv"
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_text("ticker,price\nAAA,10\n", encoding="utf-8")

            from weekly_artifact_consistency import build_weekly_artifact_consistency

            payload = build_weekly_artifact_consistency(root, "2026-07-11")

            self.assertIn("runtime_quote_snapshot_sha256_mismatch", payload["issues"])
            self.assertIn("legacy_tracked_quote_snapshot_present", payload["issues"])

    def test_cli_and_wrapper_write_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            output = root / "review.json"
            report = root / "review.md"

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "weekly_artifact_consistency.py"),
                    "--project-root",
                    str(root),
                    "--as-of-date",
                    "2026-07-11",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "ready")
            self.assertIn("周产物一致性复核", report.read_text(encoding="utf-8-sig"))

        wrapper = (PROJECT_ROOT / "scripts" / "run_weekly_artifact_consistency.ps1").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("weekly_artifact_consistency.py", wrapper)
        self.assertIn("latest_weekly_artifact_consistency.json", wrapper)
        self.assertIn("latest_weekly_artifact_consistency.md", wrapper)


if __name__ == "__main__":
    unittest.main()
