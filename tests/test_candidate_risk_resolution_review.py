import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def risk_item(index, tier="priority_research", categories=None):
    categories = categories or ["weak_trend", "fundamental_risk"]
    return {
        "market": "港股周筛" if index <= 12 else "A股周筛",
        "ticker": f"T{index:02d}",
        "company": f"Company {index}",
        "priority_tier": tier,
        "queue_action": "defer_research" if tier == "defer_research" else "manual_fundamental_review",
        "recommended_action": "deprioritize_or_wait" if tier == "defer_research" else "manual_fundamental_review",
        "risk_categories": categories,
        "risk": "走势偏弱；净利润增长为负" if tier != "defer_research" else "当前无安全边际；预期收益为负",
        "expected_return": 0.60 - index * 0.01,
        "trend_label": "偏弱",
        "valuation_confidence": "high",
        "industry": "测试行业",
        "total_score": 100 - index,
        "grade": "A" if index <= 8 else "B",
    }


def write_fixture(root):
    items = [risk_item(index) for index in range(1, 8)]
    items.extend(risk_item(index, tier="watchlist_review") for index in range(8, 15))
    items.append(
        risk_item(
            15,
            tier="defer_research",
            categories=["no_margin_of_safety", "negative_expected_return"],
        )
    )
    source = root / "outputs" / "automation" / "latest_candidate_risk_priority_review.json"
    write_json(
        source,
        {
            "review_schema": "candidate_risk_priority_review",
            "review_version": 1,
            "as_of_date": "2026-07-11",
            "status": "manual_review_needed",
            "risk_queue_count": 15,
            "formal_model_change_allowed": False,
            "items": items,
        },
    )
    valuation_rows = []
    for index in range(1, 16):
        capped = index <= 9
        valuation_rows.append(
            {
                "ticker": f"T{index:02d}",
                "current_price": "100",
                "target_price": "160" if capped else "130",
                "buy_price": "128" if capped else "104",
                "expected_return": "0.6" if capped else "0.3",
                "valuation_confidence": "high",
                "target_cap_applied": str(capped),
                "uncapped_target_price": "220" if capped else "130",
                "target_cap_price": "160",
                "target_cap_ratio": "1.375" if capped else "0.8125",
                "sensitivity_low_price": "120",
                "sensitivity_base_price": "220" if capped else "130",
                "sensitivity_high_price": "280" if capped else "145",
                "target_cap_note": "目标价触及60%保护上限；不是精确收益预测" if capped else "",
            }
        )
    write_csv(root / "outputs" / "hk_universe" / "valuation_targets.csv", valuation_rows[:12])
    write_csv(root / "outputs" / "cn_universe" / "valuation_targets.csv", valuation_rows[12:])
    write_csv(root / "outputs" / "us_universe" / "valuation_targets.csv", [valuation_rows[0]])
    return source


class CandidateRiskResolutionReviewTests(unittest.TestCase):
    def test_routes_fifteen_items_and_limits_manual_deep_dives_to_five(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = write_fixture(root)

            from candidate_risk_resolution_review import build_candidate_risk_resolution_review

            payload = build_candidate_risk_resolution_review(root, source, as_of_date="2026-07-11")

            self.assertEqual(payload["review_schema"], "candidate_risk_resolution_review")
            self.assertEqual(payload["review_version"], 1)
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["risk_action_total_count"], 15)
            self.assertEqual(payload["manual_pending_count"], 5)
            self.assertEqual(payload["auto_routed_count"], 10)
            self.assertEqual(payload["resolved_or_routed_count"], 10)
            self.assertEqual(payload["cap_applied_count"], 9)
            self.assertFalse(payload["formal_model_change_allowed"])
            self.assertEqual(
                sum(item["disposition"] == "manual_deep_dive_required" for item in payload["items"]),
                5,
            )
            self.assertEqual(payload["items"][-1]["disposition"], "defer_until_margin_returns")

    def test_every_item_has_research_conditions_and_cap_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = write_fixture(root)

            from candidate_risk_resolution_review import build_candidate_risk_resolution_review

            payload = build_candidate_risk_resolution_review(root, source)

            for item in payload["items"]:
                with self.subTest(ticker=item["ticker"]):
                    self.assertTrue(item["core_risks"])
                    self.assertTrue(item["buy_conditions"])
                    self.assertTrue(item["abandon_conditions"])
                    self.assertTrue(item["reopen_conditions"])
                    self.assertTrue(item["disposition_reason"])
                    self.assertIn("sensitivity", item)
            capped = payload["items"][0]
            self.assertTrue(capped["target_cap_applied"])
            self.assertEqual(capped["sensitivity"]["base"], 220.0)
            self.assertTrue(any("保护上限" in condition for condition in capped["buy_conditions"]))

    def test_cli_and_wrapper_write_json_markdown_and_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = write_fixture(root)
            output = root / "resolution.json"
            report = root / "resolution.md"
            csv_output = root / "resolution.csv"

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "candidate_risk_resolution_review.py"),
                    "--project-root",
                    str(root),
                    "--candidate-risk-priority-review",
                    str(source),
                    "--as-of-date",
                    "2026-07-11",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    "--csv-output",
                    str(csv_output),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8-sig"))["manual_pending_count"], 5)
            self.assertIn("候选风险处置与研究条件", report.read_text(encoding="utf-8-sig"))
            with csv_output.open(encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 15)

        wrapper = (PROJECT_ROOT / "scripts" / "run_candidate_risk_resolution_review.ps1").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("candidate_risk_resolution_review.py", wrapper)
        self.assertIn("latest_candidate_risk_resolution_review.json", wrapper)
        self.assertIn("candidate_risk_resolution_review.csv", wrapper)


if __name__ == "__main__":
    unittest.main()
