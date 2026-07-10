import csv
import hashlib
import json
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


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_summary(path, candidate_count, extra=None, run_time="2026-07-11 14:05:00"):
    fields = {
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
        write_summary(market_dir / "latest_run_summary.md", candidate_counts[market])

    quote_path = root / "outputs" / "us_universe" / "market_quotes.csv"
    write_csv(
        quote_path,
        [
            {"ticker": "AAA", "price": "10", "quote_date": "2026-07-10"},
            {"ticker": "BBB", "price": "20", "quote_date": "2026-07-11"},
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
        },
    )

    automation = root / "outputs" / "automation"
    automation.mkdir(parents=True, exist_ok=True)
    (automation / "latest_weekly_conclusion.json").write_text(
        json.dumps(
            {
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
            self.assertEqual(payload["issues"], [])

    def test_blocks_summary_candidate_count_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            write_summary(root / "outputs" / "cn_universe" / "latest_run_summary.md", 3)

            from weekly_artifact_consistency import build_weekly_artifact_consistency

            payload = build_weekly_artifact_consistency(root, "2026-07-11")

            self.assertEqual(payload["status"], "needs_attention")
            self.assertIn("cn_summary_candidate_count_mismatch", payload["issues"])

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
