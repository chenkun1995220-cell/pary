import argparse
import json
from pathlib import Path


STATUS_LABELS = {
    "clear": "通过",
    "manual_review_needed": "需要人工复核",
    "recurring_manual_review": "存在重复复核项",
    "sample_accumulating": "样本积累中",
}


def _load_check(path):
    check_path = Path(path)
    data = json.loads(check_path.read_text(encoding="utf-8-sig"))
    if data.get("check_schema") != "weekly_automation_check":
        raise ValueError(f"unexpected check_schema: {data.get('check_schema', '')}")
    if data.get("check_version") != 1:
        raise ValueError(f"unexpected check_version: {data.get('check_version', '')}")
    return data


def _status_label(status):
    return STATUS_LABELS.get(status, status or "unknown")


def _join_actions(actions):
    if not actions:
        return "无"
    return ", ".join(str(action) for action in actions)


def render_automation_check(path):
    data = _load_check(path)
    market_count = data.get("market_count", 0)
    ready_count = data.get("markets_ready_count", 0)
    lines = [
        "# 每周自动化验收结论",
        "",
        f"- 日期：{data.get('as_of_date', 'unknown')}",
        f"- 状态：{_status_label(data.get('status'))} ({data.get('status', 'unknown')})",
        f"- 下一步：{data.get('recommended_action', 'unknown')}",
        f"- 三市场：{ready_count}/{market_count} ready",
        f"- 候选总数：{data.get('candidate_count_total', 0)}",
        f"- 人工复核队列：{data.get('manual_review_queue_count', 0)}",
        f"- 历史重复复核：{data.get('manual_review_repeat_count', 0)}",
        f"- weekly_ops_history_status: {data.get('weekly_ops_history_status', 'unknown')}",
        f"- weekly_delivery_history_status: {data.get('weekly_delivery_history_status', 'unknown')}",
        f"- weekly_delivery_action_items_actual_count: {data.get('weekly_delivery_action_items_actual_count', 0)}",
        f"- weekly_delivery_action_items_actual_count_delta: {data.get('weekly_delivery_action_items_actual_count_delta', 0)}",
        f"- weekly_delivery_action_items_actual_count_trend: {data.get('weekly_delivery_action_items_actual_count_trend', 'unknown')}",
        f"- forecast_next_one_week_evaluation_date={data.get('forecast_next_one_week_evaluation_date', '')}",
        f"- forecast_next_one_month_evaluation_date={data.get('forecast_next_one_month_evaluation_date', '')}",
        f"- manifest 校验：{data.get('manifest_validation_status', 'unknown')}",
        f"- 重点动作：{_join_actions(data.get('priority_actions', []))}",
        "",
        "## 市场概览",
    ]
    market_rows = data.get("market_candidate_counts", [])
    if market_rows:
        for market in market_rows:
            lines.append(
                f"- {market.get('name', 'unknown')}：{market.get('status', 'unknown')}，"
                f"候选 {market.get('candidate_count', 'unknown')}"
            )
    else:
        lines.append("- 无市场明细")
    outputs = data.get("outputs", {})
    if outputs:
        lines.extend(["", "## 关键输出"])
        for key in ["self_analysis", "manifest", "manual_review_queue", "automation_check"]:
            if key in outputs:
                lines.append(f"- {key}: {outputs[key]}")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Render the weekly automation check as a Chinese summary.")
    parser.add_argument("--check", default="outputs/automation/latest_automation_check.json")
    args = parser.parse_args()
    print(render_automation_check(args.check), end="")


if __name__ == "__main__":
    main()
