import argparse
import json
import sys
from datetime import date
from pathlib import Path

from codex_automation_audit import audit_automations


CHECK_SCHEMA = "weekly_automation_check"
CHECK_VERSION = 1
OPS_CHECK_SCHEMA = "weekly_ops_check"
OPS_CHECK_VERSION = 1
HISTORY_SCHEMA = "weekly_ops_check_history"
HISTORY_VERSION = 1


def _load_weekly_check(path):
    check_path = Path(path)
    data = json.loads(check_path.read_text(encoding="utf-8-sig"))
    if data.get("check_schema") != CHECK_SCHEMA:
        raise ValueError(f"unexpected check_schema: {data.get('check_schema', '')}")
    if data.get("check_version") != CHECK_VERSION:
        raise ValueError(f"unexpected check_version: {data.get('check_version', '')}")
    return data


def _resolve_output_path(project_root, output_path):
    path = Path(output_path)
    if path.is_absolute():
        return path
    return Path(project_root) / path


def _missing_outputs(project_root, outputs):
    missing = []
    missing_paths = {}
    for key, raw_path in outputs.items():
        resolved = _resolve_output_path(project_root, raw_path)
        if not resolved.exists():
            missing.append(key)
            missing_paths[key] = str(resolved)
    return missing, missing_paths


def _automation_issues(audit_result):
    issues = []
    for check in audit_result.get("checks", []):
        for issue in check.get("issues", []):
            issues.append(f"{check.get('id', 'unknown')}: {issue}")
    return issues


def _parse_iso_date(value, field_name):
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"invalid {field_name}: {value}") from exc


def _freshness(as_of_date, today=None, max_age_days=8):
    check_date = _parse_iso_date(as_of_date, "as_of_date")
    current_date = _parse_iso_date(today, "today") if today else date.today()
    age_days = (current_date - check_date).days
    if age_days < 0:
        return "future", age_days
    if age_days > max_age_days:
        return "stale", age_days
    return "fresh", age_days


def run_weekly_ops_check(project_root, automation_root, check, today=None, max_age_days=8):
    project_root = Path(project_root)
    check_path = Path(check)
    weekly_check = _load_weekly_check(check_path)
    automation_audit = audit_automations(automation_root)
    missing, missing_paths = _missing_outputs(project_root, weekly_check.get("outputs", {}))

    market_count = int(weekly_check.get("market_count", 0) or 0)
    ready_count = int(weekly_check.get("markets_ready_count", 0) or 0)
    manifest_status = weekly_check.get("manifest_validation_status", "unknown")
    automation_status = automation_audit.get("status", "unknown")
    freshness_status, check_age_days = _freshness(
        weekly_check.get("as_of_date", "unknown"),
        today=today,
        max_age_days=max_age_days,
    )

    attention_reasons = []
    if automation_status != "ready":
        attention_reasons.append("automation_config_drift")
    if freshness_status == "stale":
        attention_reasons.append("stale_check_date")
    if freshness_status == "future":
        attention_reasons.append("future_check_date")
    if manifest_status != "valid":
        attention_reasons.append("manifest_validation_not_valid")
    if market_count == 0 or ready_count != market_count:
        attention_reasons.append("market_summary_not_ready")
    if missing:
        attention_reasons.append("missing_outputs")

    return {
        "ops_check_schema": OPS_CHECK_SCHEMA,
        "ops_check_version": OPS_CHECK_VERSION,
        "status": "ready" if not attention_reasons else "needs_attention",
        "project_root": str(project_root),
        "automation_root": str(Path(automation_root)),
        "check": str(check_path),
        "as_of_date": weekly_check.get("as_of_date", "unknown"),
        "freshness_status": freshness_status,
        "check_age_days": check_age_days,
        "max_age_days": max_age_days,
        "automation_audit_status": automation_status,
        "automation_check_status": weekly_check.get("status", "unknown"),
        "manifest_validation_status": manifest_status,
        "market_count": market_count,
        "markets_ready_count": ready_count,
        "candidate_count_total": int(weekly_check.get("candidate_count_total", 0) or 0),
        "manual_review_queue_count": int(weekly_check.get("manual_review_queue_count", 0) or 0),
        "manual_review_repeat_count": int(weekly_check.get("manual_review_repeat_count", 0) or 0),
        "forecast_next_one_week_evaluation_date": str(
            weekly_check.get("forecast_next_one_week_evaluation_date", "") or ""
        ),
        "forecast_next_one_month_evaluation_date": str(
            weekly_check.get("forecast_next_one_month_evaluation_date", "") or ""
        ),
        "recommended_action": weekly_check.get("recommended_action", "unknown"),
        "priority_actions": weekly_check.get("priority_actions", []),
        "missing_outputs": missing,
        "missing_output_paths": missing_paths,
        "automation_issues": _automation_issues(automation_audit),
        "attention_reasons": attention_reasons,
    }


def _join_or_none(values):
    if not values:
        return "无"
    return ", ".join(str(value) for value in values)


def render_weekly_ops_check(result):
    lines = [
        "# 周度运维总检查",
        "",
        f"- 日期：{result.get('as_of_date', 'unknown')}",
        f"- 验收日期新鲜度：{result.get('freshness_status', 'unknown')} ({result.get('check_age_days', 'unknown')}天/{result.get('max_age_days', 'unknown')}天)",
        f"- 总体状态：{result.get('status', 'unknown')}",
        f"- 自动任务配置：{result.get('automation_audit_status', 'unknown')}",
        f"- 验收结论：{result.get('automation_check_status', 'unknown')}",
        f"- manifest 校验：{result.get('manifest_validation_status', 'unknown')}",
        f"- 三市场 ready：{result.get('markets_ready_count', 0)}/{result.get('market_count', 0)}",
        f"- 候选总数：{result.get('candidate_count_total', 0)}",
        f"- 人工复核队列：{result.get('manual_review_queue_count', 0)}",
        f"- 历史重复复核：{result.get('manual_review_repeat_count', 0)}",
        f"- forecast_next_one_week_evaluation_date={result.get('forecast_next_one_week_evaluation_date', '')}",
        f"- forecast_next_one_month_evaluation_date={result.get('forecast_next_one_month_evaluation_date', '')}",
        f"- 缺失输出：{_join_or_none(result.get('missing_outputs', []))}",
        f"- 建议动作：{result.get('recommended_action', 'unknown')}",
        f"- 重点动作：{_join_or_none(result.get('priority_actions', []))}",
    ]
    if result.get("automation_issues"):
        lines.extend(["", "## 自动任务问题"])
        for issue in result["automation_issues"]:
            lines.append(f"- {issue}")
    if result.get("freshness_status") in {"stale", "future"}:
        lines.extend(["", "## 验收日期问题"])
        if result["freshness_status"] == "stale":
            lines.append("- 验收文件过期：请重新运行本周三市场周筛和自我分析，不要复用旧结论。")
        else:
            lines.append("- 验收日期晚于当前日期：请检查系统日期或验收文件来源。")
    if result.get("missing_output_paths"):
        lines.extend(["", "## 缺失输出路径"])
        for key, path in result["missing_output_paths"].items():
            lines.append(f"- {key}: {path}")
    lines.extend(
        [
            "",
            "## 边界",
            "- 该检查只读取现有验收文件、关键输出路径和 Codex 自动任务配置。",
            "- 该检查不抓取行情，不重新评分，也不修改模型参数。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_weekly_ops_check(result, output):
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8-sig",
    )
    return output_path


def append_weekly_ops_history(result, history):
    history_path = Path(history)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "history_schema": HISTORY_SCHEMA,
        "history_version": HISTORY_VERSION,
        **result,
    }
    with history_path.open("a", encoding="utf-8-sig") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return history_path


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run the weekly operations check.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--automation-root", default=str(Path.home() / ".codex" / "automations"))
    parser.add_argument("--check", default="outputs/automation/latest_automation_check.json")
    parser.add_argument("--today", default="")
    parser.add_argument("--max-age-days", type=int, default=8)
    parser.add_argument("--output", default="")
    parser.add_argument("--history", default="")
    args = parser.parse_args()
    result = run_weekly_ops_check(
        args.project_root,
        args.automation_root,
        args.check,
        today=args.today or None,
        max_age_days=args.max_age_days,
    )
    if args.output:
        write_weekly_ops_check(result, args.output)
    if args.history:
        append_weekly_ops_history(result, args.history)
    print(render_weekly_ops_check(result), end="")
    if result["status"] != "ready":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
