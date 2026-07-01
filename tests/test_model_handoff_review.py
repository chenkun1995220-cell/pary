import json
import tempfile
import unittest
from pathlib import Path


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


class ModelHandoffReviewTests(unittest.TestCase):
    def test_builds_handoff_from_medium_term_goal_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(
                root / "outputs" / "automation" / "latest_medium_term_goal_review.json",
                {
                    "review_schema": "medium_term_goal_review",
                    "review_version": 1,
                    "as_of_date": "2026-07-01",
                    "strategy_code": "steady_delivery_evidence_first",
                    "strategy_title": "稳交付 + 补证据 + 等预测样本成熟",
                    "overall_completion_percent": 61,
                    "automatic_multi_model_collaboration_enabled": False,
                    "collaboration_execution_mode": "single_codex_with_gpt55_review_checklist",
                    "collaboration_boundary_note": (
                        "当前未启用自动多模型协作；实际由单 Codex 执行并通过清单模拟复核。"
                    ),
                    "goals": [
                        {
                            "goal_code": "model_governance_handoff",
                            "module": "模型治理与多模型协作准备",
                            "completion_percent": 75,
                            "status": "on_track",
                            "next_action": "continue_governance_handoff",
                        }
                    ],
                },
            )

            from model_handoff_review import build_model_handoff_review, render_model_handoff_review

            result = build_model_handoff_review(
                root,
                today="2026-07-01",
                goal_code="model_governance_handoff",
                validation_commands=["python -m unittest discover -s tests"],
            )
            report = render_model_handoff_review(result)

            self.assertEqual(result["handoff_schema"], "model_handoff_review")
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["current_module"], "模型治理与多模型协作准备")
            self.assertEqual(result["module_completion_percent"], 75)
            self.assertEqual(result["medium_term_overall_completion_percent"], 61)
            self.assertFalse(result["automatic_multi_model_collaboration_enabled"])
            self.assertEqual(
                result["collaboration_execution_mode"],
                "single_codex_with_gpt55_review_checklist",
            )
            self.assertIn("gpt5.5", " ".join(result["gpt55_review_checklist"]))
            self.assertIn("未启用自动双模型协作", report)

    def test_defaults_to_medium_term_closeout_goal_when_goal_code_is_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(
                root / "outputs" / "automation" / "latest_medium_term_goal_review.json",
                {
                    "review_schema": "medium_term_goal_review",
                    "review_version": 1,
                    "as_of_date": "2026-07-02",
                    "strategy_code": "steady_delivery_evidence_first",
                    "strategy_title": "稳交付 + 补证据 + 等预测样本成熟",
                    "overall_completion_percent": 61,
                    "automatic_multi_model_collaboration_enabled": False,
                    "collaboration_execution_mode": "single_codex_with_gpt55_review_checklist",
                    "collaboration_boundary_note": "当前未启用自动多模型协作；实际由单 Codex 执行并通过清单模拟复核。",
                    "task_closeout_snapshot": {
                        "goal_code": "backtest_evidence_quality",
                        "current_module": "S&P 500 成分证据补强",
                        "module_completion_percent": 30,
                        "medium_term_overall_completion_percent": 61,
                    },
                    "goals": [
                        {
                            "goal_code": "model_governance_handoff",
                            "module": "模型治理与多模型协作准备",
                            "completion_percent": 75,
                            "status": "on_track",
                        },
                        {
                            "goal_code": "backtest_evidence_quality",
                            "module": "S&P 500 成分证据补强",
                            "completion_percent": 30,
                            "status": "needs_work",
                        },
                    ],
                },
            )

            from model_handoff_review import build_model_handoff_review

            result = build_model_handoff_review(root, today="2026-07-02")

            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["goal_code"], "backtest_evidence_quality")
            self.assertEqual(result["current_module"], "S&P 500 成分证据补强")
            self.assertEqual(result["module_completion_percent"], 30)
            self.assertEqual(result["medium_term_overall_completion_percent"], 61)

    def test_weekly_bundle_runs_handoff_before_pre_submit_review(self):
        project_root = Path(__file__).resolve().parents[1]
        bundle = (project_root / "scripts" / "run_weekly_reporting_bundle.ps1").read_text(
            encoding="utf-8-sig"
        )
        wrapper = (project_root / "scripts" / "run_model_handoff_review.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("run_model_handoff_review.ps1", bundle)
        self.assertLess(
            bundle.index("run_model_handoff_review.ps1"),
            bundle.index("run_pre_submit_review.ps1"),
        )
        self.assertIn("if ($GoalCode)", wrapper)


if __name__ == "__main__":
    unittest.main()
