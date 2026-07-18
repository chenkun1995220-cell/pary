import csv
import json
import tempfile
import unittest
from pathlib import Path

from weekly_market_run_state import write_market_run_state


MARKETS = {
    "US": "us_universe",
    "CN": "cn_universe",
    "HK": "hk_universe",
}


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ticker", "company"])
        writer.writeheader()
        writer.writerows(rows)


def make_market(root, market, status="ready", run_date="2026-07-18", count=2):
    directory = root / "outputs" / MARKETS[market]
    directory.mkdir(parents=True, exist_ok=True)
    summary = directory / "latest_run_summary.md"
    candidates = directory / "candidate_pool.csv"
    state = directory / "latest_run_state.json"
    started = f"{run_date} 14:05:00"
    completed = f"{run_date} 14:08:00" if status == "ready" else ""
    summary.write_text(
        "\n".join(
            [
                f"# {market} Weekly Summary",
                f"- Run start time: {started}",
                f"- Run time: {run_date} 14:08:00",
                f"- Candidate count: {count}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    write_csv(
        candidates,
        [
            {"ticker": f"{market}{index}", "company": f"Company {index}"}
            for index in range(count)
        ],
    )
    write_market_run_state(
        state,
        market,
        status,
        started,
        run_completed_at=completed,
        summary_path=str(summary),
        candidate_path=str(candidates),
        log_path=str(directory / "run.log"),
        failure_step="market_pipeline" if status == "failed" else "",
        failure_message="pipeline failed" if status == "failed" else "",
    )
    return {
        "directory": directory,
        "summary": summary,
        "candidates": candidates,
        "state": state,
    }


def make_project(root, statuses=None, dates=None, counts=None):
    statuses = statuses or {}
    dates = dates or {}
    counts = counts or {}
    return {
        market: make_market(
            root,
            market,
            status=statuses.get(market, "ready"),
            run_date=dates.get(market, "2026-07-18"),
            count=counts.get(market, 2),
        )
        for market in MARKETS
    }


class WeeklyMarketCompletionGateTests(unittest.TestCase):
    def test_ready_requires_three_same_day_completed_markets(self):
        from weekly_market_completion_gate import (
            build_weekly_market_completion_gate,
            render_weekly_market_completion_gate,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_project(root)

            payload = build_weekly_market_completion_gate(root, "2026-07-18")

            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["market_count"], 3)
            self.assertEqual(payload["ready_market_count"], 3)
            self.assertEqual(payload["candidate_count_total"], 6)
            self.assertEqual(payload["issues"], [])
            self.assertFalse(payload["formal_model_change_allowed"])
            self.assertIn("6", render_weekly_market_completion_gate(payload))

    def test_running_or_failed_market_blocks_with_stable_issues(self):
        from weekly_market_completion_gate import build_weekly_market_completion_gate

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_project(root, statuses={"US": "failed", "HK": "running"})

            payload = build_weekly_market_completion_gate(root, "2026-07-18")

            self.assertEqual(payload["status"], "blocked")
            self.assertIn("us_run_status_failed", payload["issues"])
            self.assertIn("hk_run_status_running", payload["issues"])
            self.assertEqual(payload["ready_market_count"], 1)

    def test_missing_or_invalid_state_blocks(self):
        from weekly_market_completion_gate import build_weekly_market_completion_gate

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = make_project(root)
            paths["US"]["state"].unlink()
            paths["CN"]["state"].write_text("{not-json}\n", encoding="utf-8")

            payload = build_weekly_market_completion_gate(root, "2026-07-18")

            self.assertIn("us_run_state_missing", payload["issues"])
            self.assertIn("cn_run_state_invalid", payload["issues"])

    def test_stale_future_and_mismatched_market_dates_block(self):
        from weekly_market_completion_gate import build_weekly_market_completion_gate

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_project(
                root,
                dates={
                    "US": "2026-07-17",
                    "CN": "2026-07-18",
                    "HK": "2026-07-19",
                },
            )

            payload = build_weekly_market_completion_gate(root, "2026-07-18")

            self.assertIn("us_run_state_stale", payload["issues"])
            self.assertIn("hk_run_state_future", payload["issues"])
            self.assertIn("market_run_date_mismatch", payload["issues"])

    def test_market_and_fixed_paths_must_match(self):
        from weekly_market_completion_gate import build_weekly_market_completion_gate

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = make_project(root)
            state = json.loads(paths["US"]["state"].read_text(encoding="utf-8"))
            state["market"] = "CN"
            state["summary_path"] = str(root / "elsewhere" / "summary.md")
            paths["US"]["state"].write_text(json.dumps(state), encoding="utf-8")

            payload = build_weekly_market_completion_gate(root, "2026-07-18")

            self.assertIn("us_run_state_market_mismatch", payload["issues"])
            self.assertIn("us_run_state_path_mismatch", payload["issues"])

    def test_summary_and_candidate_evidence_must_match_state(self):
        from weekly_market_completion_gate import build_weekly_market_completion_gate

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = make_project(root)
            paths["US"]["summary"].write_text(
                "\n".join(
                    [
                        "# US Weekly Summary",
                        "- Run time: 2026-07-17 14:08:00",
                        "- Candidate count: 9",
                    ]
                ),
                encoding="utf-8",
            )
            paths["CN"]["candidates"].unlink()
            paths["HK"]["summary"].unlink()

            payload = build_weekly_market_completion_gate(root, "2026-07-18")

            self.assertIn("us_summary_date_mismatch", payload["issues"])
            self.assertIn("us_candidate_count_mismatch", payload["issues"])
            self.assertIn("cn_candidate_pool_missing", payload["issues"])
            self.assertIn("hk_summary_missing", payload["issues"])


if __name__ == "__main__":
    unittest.main()
