import argparse
import json
import sys
from datetime import date
from pathlib import Path


DELIVERY_CHECK_SCHEMA = "weekly_delivery_check"
DELIVERY_CHECK_VERSION = 1
HISTORY_SCHEMA = "weekly_delivery_check_history"
HISTORY_VERSION = 1
DEFAULT_CONCLUSION_JSON = "outputs/automation/latest_weekly_conclusion.json"
DEFAULT_ACTION_ITEMS_JSON = "outputs/automation/latest_weekly_action_items.json"
DEFAULT_ACTION_ITEMS_MARKDOWN = "outputs/automation/latest_weekly_action_items.md"
DEFAULT_OUTPUT = "outputs/automation/latest_weekly_delivery_check.json"
DEFAULT_HISTORY = "outputs/automation/weekly_delivery_check_history.jsonl"
REQUIRED_CONCLUSION_SIGNALS = (
    "automation.data_quality",
    "automation.data_quality_history",
    "automation.forecast_performance",
)


def run_delivery_check(project_root, conclusion_json=None, today=None, max_age_days=8):
    project_root = Path(project_root)
    conclusion_path = _resolve_path(project_root, conclusion_json or DEFAULT_CONCLUSION_JSON)
    conclusion = _read_json(conclusion_path)

    missing_outputs = []
    missing_output_paths = {}
    attention_reasons = []
    freshness_status = "unknown"
    conclusion_age_days = None
    conclusion_health = {}
    action_items_status = "unknown"
    action_items_freshness_status = "unknown"
    action_items_age_days = None
    action_items_count = 0
    conclusion_signal_status = "unknown"
    missing_conclusion_signals = []

    if not conclusion:
        attention_reasons.append("missing_or_invalid_conclusion_json")
        _add_missing(missing_outputs, missing_output_paths, "weekly_conclusion_json", conclusion_path)
        conclusion = {}
    else:
        freshness_status, conclusion_age_days = _freshness(
            conclusion.get("as_of_date", "unknown"),
            today=today,
            max_age_days=max_age_days,
        )
        if freshness_status == "stale":
            attention_reasons.append("stale_conclusion_date")
        elif freshness_status == "future":
            attention_reasons.append("future_conclusion_date")
        if conclusion.get("conclusion_schema") != "weekly_conclusion":
            attention_reasons.append("unexpected_conclusion_schema")
        if int(conclusion.get("conclusion_version", 0) or 0) != 1:
            attention_reasons.append("unexpected_conclusion_version")
        conclusion_health = _conclusion_health(conclusion)
        if conclusion_health["status"] == "needs_fix":
            attention_reasons.append("conclusion_health_needs_fix")
        elif conclusion_health["status"] not in {"healthy", "needs_review"}:
            attention_reasons.append("invalid_conclusion_health")
        conclusion_signal_status, missing_conclusion_signals = _check_conclusion_signals(conclusion)
        if missing_conclusion_signals:
            attention_reasons.append("missing_conclusion_signals")

    for key, raw_path in _required_outputs(conclusion, conclusion_path).items():
        path = _resolve_path(project_root, raw_path)
        if not path.exists():
            _add_missing(missing_outputs, missing_output_paths, key, path)

    merge_summary = conclusion.get("manual_review_merge_summary", {})
    if merge_summary.get("exists") and merge_summary.get("path"):
        merge_path = _resolve_path(project_root, merge_summary["path"])
        if not merge_path.exists():
            _add_missing(missing_outputs, missing_output_paths, "manual_review_merge_summary", merge_path)

    if missing_outputs:
        attention_reasons.append("missing_outputs")

    action_items = _check_action_items(
        project_root,
        today=today,
        max_age_days=max_age_days,
        missing_outputs=missing_outputs,
        missing_output_paths=missing_output_paths,
    )
    action_items_status = action_items["status"]
    action_items_freshness_status = action_items["freshness_status"]
    action_items_age_days = action_items["age_days"]
    action_items_count = action_items["item_count"]
    if action_items["attention_reasons"]:
        for reason in action_items["attention_reasons"]:
            if reason not in attention_reasons:
                attention_reasons.append(reason)
    if action_items["missing"] and "missing_outputs" not in attention_reasons:
        attention_reasons.append("missing_outputs")

    return {
        "delivery_check_schema": DELIVERY_CHECK_SCHEMA,
        "delivery_check_version": DELIVERY_CHECK_VERSION,
        "status": "ready" if not attention_reasons else "needs_attention",
        "project_root": str(project_root),
        "conclusion_json": _relative_path(project_root, conclusion_path),
        "as_of_date": conclusion.get("as_of_date", "unknown"),
        "freshness_status": freshness_status,
        "conclusion_age_days": conclusion_age_days,
        "max_age_days": max_age_days,
        "conclusion_status": conclusion.get("status", "unknown"),
        "conclusion_health_status": conclusion_health.get("status", "unknown"),
        "conclusion_health_score": conclusion_health.get("score", 0),
        "conclusion_health_reasons": conclusion_health.get("reasons", []),
        "candidate_count_total": int(conclusion.get("candidate_count_total", 0) or 0),
        "manual_review_queue_count": int(conclusion.get("manual_review_queue", {}).get("count", 0) or 0),
        "manual_review_pending_count": int(conclusion.get("manual_review_decisions", {}).get("pending_count", 0) or 0),
        "manual_review_merge_summary_exists": bool(merge_summary.get("exists")),
        "conclusion_signal_status": conclusion_signal_status,
        "missing_conclusion_signals": missing_conclusion_signals,
        "action_items_status": action_items_status,
        "action_items_freshness_status": action_items_freshness_status,
        "action_items_age_days": action_items_age_days,
        "action_items_count": action_items_count,
        "missing_outputs": missing_outputs,
        "missing_output_paths": missing_output_paths,
        "attention_reasons": attention_reasons,
    }


def render_delivery_check(result):
    lines = [
        "# 每周最终交付验收",
        "",
        f"- 日期：{result.get('as_of_date', 'unknown')}",
        f"- 总体状态：{result.get('status', 'unknown')}",
        f"- 周结论状态：{result.get('conclusion_status', 'unknown')}",
        f"- 周结论健康：{result.get('conclusion_health_status', 'unknown')} / {result.get('conclusion_health_score', 0)}",
        f"- 周结论新鲜度：{result.get('freshness_status', 'unknown')}",
        f"- 候选总数：{result.get('candidate_count_total', 0)}",
        f"- 人工复核队列：{result.get('manual_review_queue_count', 0)}",
        f"- 待处理复核：{result.get('manual_review_pending_count', 0)}",
        f"- 合并摘要存在：{result.get('manual_review_merge_summary_exists', False)}",
        f"- 周结论关键信号：{result.get('conclusion_signal_status', 'unknown')}",
        f"- 每周人工处理清单：{result.get('action_items_status', 'unknown')} / {result.get('action_items_count', 0)}",
        f"- 缺失输出：{_join_or_none(result.get('missing_outputs', []))}",
    ]
    if result.get("attention_reasons"):
        lines.extend(["", "## 需要处理"])
        for reason in result["attention_reasons"]:
            lines.append(f"- {reason}")
    if result.get("missing_conclusion_signals"):
        lines.extend(["", "## 缺失周结论信号"])
        for signal in result["missing_conclusion_signals"]:
            lines.append(f"- {signal}")
    if result.get("missing_output_paths"):
        lines.extend(["", "## 缺失路径"])
        for key, path in result["missing_output_paths"].items():
            lines.append(f"- {key}: {path}")
    lines.extend(
        [
            "",
            "## 边界",
            "- 本验收只读取最终周报、JSON、每周人工处理清单、人工复核模板和可选合并摘要。",
            "- 本验收不抓取行情、不重新评分、不修改正式模型参数。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_delivery_check(result, output):
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8-sig")
    return output_path


def append_delivery_check_history(result, history):
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


def _required_outputs(conclusion, conclusion_path):
    outputs = conclusion.get("outputs", {}) if conclusion else {}
    return {
        "weekly_conclusion_markdown": outputs.get("markdown", "outputs/automation/latest_weekly_conclusion.md"),
        "weekly_conclusion_json": outputs.get("json", conclusion_path),
        "manual_review_decisions_template": outputs.get(
            "manual_review_decisions_template",
            "outputs/automation/manual_review_decisions_template.csv",
        ),
    }


def _check_action_items(project_root, today=None, max_age_days=8, missing_outputs=None, missing_output_paths=None):
    missing_outputs = missing_outputs if missing_outputs is not None else []
    missing_output_paths = missing_output_paths if missing_output_paths is not None else {}
    json_path = _resolve_path(project_root, DEFAULT_ACTION_ITEMS_JSON)
    markdown_path = _resolve_path(project_root, DEFAULT_ACTION_ITEMS_MARKDOWN)
    attention_reasons = []
    missing = False

    if not json_path.exists():
        _add_missing(missing_outputs, missing_output_paths, "weekly_action_items_json", json_path)
        missing = True
    if not markdown_path.exists():
        _add_missing(missing_outputs, missing_output_paths, "weekly_action_items_markdown", markdown_path)
        missing = True
    if missing:
        return {
            "status": "missing",
            "freshness_status": "unknown",
            "age_days": None,
            "item_count": 0,
            "attention_reasons": [],
            "missing": True,
        }

    payload = _read_json(json_path)
    if not payload:
        return {
            "status": "invalid",
            "freshness_status": "unknown",
            "age_days": None,
            "item_count": 0,
            "attention_reasons": ["invalid_action_items_json"],
            "missing": False,
        }

    status = "ready"
    if payload.get("action_items_schema") != "weekly_action_items":
        status = "invalid"
        attention_reasons.append("unexpected_action_items_schema")
    if int(payload.get("action_items_version", 0) or 0) != 1:
        status = "invalid"
        attention_reasons.append("unexpected_action_items_version")

    item_count = int(payload.get("item_count", 0) or 0)
    freshness_status, age_days = _freshness(
        payload.get("as_of_date", "unknown"),
        today=today,
        max_age_days=max_age_days,
    )
    if freshness_status == "stale":
        status = "stale"
        attention_reasons.append("stale_action_items_date")
    elif freshness_status == "future":
        status = "future"
        attention_reasons.append("future_action_items_date")

    return {
        "status": status,
        "freshness_status": freshness_status,
        "age_days": age_days,
        "item_count": item_count,
        "attention_reasons": attention_reasons,
        "missing": False,
    }


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _conclusion_health(conclusion):
    health = conclusion.get("health", {})
    if not isinstance(health, dict):
        return {"status": "invalid", "score": 0, "reasons": ["health_not_object"]}
    status = str(health.get("status", "unknown") or "unknown")
    try:
        score = int(health.get("score", 0) or 0)
    except (TypeError, ValueError):
        score = 0
        status = "invalid"
    reasons = health.get("reasons", [])
    if not isinstance(reasons, list):
        reasons = [str(reasons)]
    return {
        "status": status,
        "score": max(0, min(100, score)),
        "reasons": [str(reason) for reason in reasons],
    }


def _check_conclusion_signals(conclusion):
    missing = []
    for signal in REQUIRED_CONCLUSION_SIGNALS:
        if _nested_value(conclusion, signal) in (None, ""):
            missing.append(signal)
    return ("ready" if not missing else "missing"), missing


def _nested_value(payload, dotted_key):
    current = payload
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _resolve_path(project_root, raw_path):
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return Path(project_root) / path


def _relative_path(project_root, path):
    try:
        return Path(path).relative_to(project_root).as_posix()
    except ValueError:
        return str(path)


def _add_missing(missing_outputs, missing_output_paths, key, path):
    if key not in missing_outputs:
        missing_outputs.append(key)
    missing_output_paths[key] = str(path)


def _freshness(as_of_date, today=None, max_age_days=8):
    check_date = _parse_iso_date(as_of_date, "as_of_date")
    current_date = _parse_iso_date(today, "today") if today else date.today()
    age_days = (current_date - check_date).days
    if age_days < 0:
        return "future", age_days
    if age_days > max_age_days:
        return "stale", age_days
    return "fresh", age_days


def _parse_iso_date(value, field_name):
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise ValueError(f"invalid {field_name}: {value}") from exc


def _join_or_none(values):
    if not values:
        return "无"
    return ", ".join(str(value) for value in values)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Validate final weekly delivery outputs.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--conclusion-json", default="")
    parser.add_argument("--today", default="")
    parser.add_argument("--max-age-days", type=int, default=8)
    parser.add_argument("--output", default="")
    parser.add_argument("--history", default="")
    args = parser.parse_args(argv)

    project_root = Path(args.project_root)
    result = run_delivery_check(
        project_root,
        conclusion_json=args.conclusion_json or None,
        today=args.today or None,
        max_age_days=args.max_age_days,
    )
    if args.output:
        write_delivery_check(result, args.output)
    if args.history:
        append_delivery_check_history(result, args.history)
    print(render_delivery_check(result), end="")
    if result["status"] != "ready":
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
