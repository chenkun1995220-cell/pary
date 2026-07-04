import argparse
import json
import sys
from pathlib import Path


DEFAULT_REVIEW = Path("outputs") / "automation" / "latest_medium_term_goal_review.json"


def _load_json(path):
    json_path = Path(path)
    return json.loads(json_path.read_text(encoding="utf-8-sig"))


def _find_goal(review, goal_code="", module=""):
    goals = review.get("goals", []) or []
    if goal_code:
        for goal in goals:
            if goal.get("goal_code") == goal_code:
                return goal
    if module:
        for goal in goals:
            if goal.get("module") == module:
                return goal
    return {}


def build_development_closeout_summary(review_path, goal_code="", module=""):
    review = _load_json(review_path)
    snapshot = review.get("task_closeout_snapshot", {}) or {}
    if not goal_code and not module:
        goal_code = snapshot.get("goal_code", "")
    goal = _find_goal(review, goal_code=goal_code, module=module)
    current_module = goal.get("module") or module or snapshot.get("current_module", "unknown")
    module_completion = goal.get(
        "completion_percent",
        snapshot.get("module_completion_percent", 0),
    )
    current = goal.get("current", {}) if isinstance(goal, dict) else {}
    if not isinstance(current, dict):
        current = {}
    return {
        "current_module": current_module,
        "goal_code": goal.get("goal_code", goal_code or "unknown"),
        "module_completion_percent": int(module_completion or 0),
        "medium_term_overall_completion_percent": int(
            review.get(
                "overall_completion_percent",
                snapshot.get("medium_term_overall_completion_percent", 0),
            )
            or 0
        ),
        "current_target_total_completion_percent": int(
            review.get(
                "current_target_total_completion_percent",
                review.get(
                    "overall_completion_percent",
                    snapshot.get("current_target_total_completion_percent", 0),
                ),
            )
            or 0
        ),
        "medium_term_status": review.get("status", "unknown"),
        "strategy_code": review.get("strategy_code", "unknown"),
        "strategy_title": review.get("strategy_title", "unknown"),
        "automatic_multi_model_collaboration_enabled": bool(
            review.get("automatic_multi_model_collaboration_enabled")
        ),
        "collaboration_execution_mode": review.get(
            "collaboration_execution_mode",
            "unknown",
        ),
        "sp500_current_source_inbox_external_input_required": bool(
            current.get("sp500_current_source_inbox_external_input_required")
        ),
        "sp500_current_source_inbox_size_bytes": int(
            current.get("sp500_current_source_inbox_size_bytes") or 0
        ),
        "sp500_current_source_inbox_sha256": current.get(
            "sp500_current_source_inbox_sha256",
            "",
        ),
        "sp500_current_source_inbox_modified_at": current.get(
            "sp500_current_source_inbox_modified_at",
            "",
        ),
        "sp500_current_source_inbox_blocking_reason": current.get(
            "sp500_current_source_inbox_blocking_reason",
            "",
        ),
        "sp500_current_source_inbox_blocking_input": current.get(
            "sp500_current_source_inbox_blocking_input",
            "",
        ),
        "collaboration_boundary_note": review.get(
            "collaboration_boundary_note",
            "unknown",
        ),
        "boundary": "只读取最新中期目标看板，不抓取行情，不重新评分，不修改正式模型参数。",
    }


def render_development_closeout_summary(summary):
    collaboration = (
        "已启用"
        if summary.get("automatic_multi_model_collaboration_enabled")
        else "未启用，当前为单 Codex 执行 + gpt5.5 复核清单模拟"
    )
    lines = [
        "# 开发收尾摘要",
        "",
        f"- 当前开发内容所属模块：{summary.get('current_module', 'unknown')}",
        f"- 该模块完成度：{summary.get('module_completion_percent', 0)}%",
        f"- 中期目标整体完成度：{summary.get('medium_term_overall_completion_percent', 0)}%",
        f"- 当前目标总完成度：{summary.get('current_target_total_completion_percent', 0)}%",
        f"- 中期目标方案：{summary.get('strategy_title', 'unknown')}",
        f"- 中期目标状态：{summary.get('medium_term_status', 'unknown')}",
        f"- 自动双模型协作：{collaboration}",
        f"- 真实执行模式：{summary.get('collaboration_execution_mode', 'unknown')}",
        f"- 协作边界：{summary.get('collaboration_boundary_note', 'unknown')}",
        "",
        "## 边界",
        f"- {summary.get('boundary', '')}",
        "",
    ]
    lines.insert(
        -3,
        f"- sp500_current_source_inbox_external_input_required={summary.get('sp500_current_source_inbox_external_input_required', False)}",
    )
    lines.insert(
        -3,
        f"- sp500_current_source_inbox_size_bytes={summary.get('sp500_current_source_inbox_size_bytes', 0)}",
    )
    lines.insert(
        -3,
        f"- sp500_current_source_inbox_sha256={summary.get('sp500_current_source_inbox_sha256', '')}",
    )
    lines.insert(
        -3,
        f"- sp500_current_source_inbox_modified_at={summary.get('sp500_current_source_inbox_modified_at', '')}",
    )
    lines.insert(
        -3,
        f"- sp500_current_source_inbox_blocking_reason={summary.get('sp500_current_source_inbox_blocking_reason', '')}",
    )
    lines.insert(
        -3,
        f"- sp500_current_source_inbox_blocking_input={summary.get('sp500_current_source_inbox_blocking_input', '')}",
    )
    return "\n".join(lines)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Show development closeout progress from the medium-term goal review.")
    parser.add_argument("--review", default=str(DEFAULT_REVIEW))
    parser.add_argument("--goal-code", default="")
    parser.add_argument("--module", default="")
    args = parser.parse_args()

    summary = build_development_closeout_summary(
        args.review,
        goal_code=args.goal_code,
        module=args.module,
    )
    print(render_development_closeout_summary(summary), end="")


if __name__ == "__main__":
    main()
