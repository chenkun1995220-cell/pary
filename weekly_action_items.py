import argparse
import json
import sys
from pathlib import Path


ACTION_ITEMS_SCHEMA = "weekly_action_items"
ACTION_ITEMS_VERSION = 1
EXPECTED_MANIFEST_SCHEMA = "self_analysis_manifest"
EXPECTED_MANIFEST_VERSION = 1


def load_manifest(manifest):
    manifest_path = Path(manifest)
    payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if payload.get("manifest_schema") != EXPECTED_MANIFEST_SCHEMA:
        raise ValueError(f"unexpected manifest_schema: {payload.get('manifest_schema', '')}")
    if int(payload.get("manifest_version", 0) or 0) != EXPECTED_MANIFEST_VERSION:
        raise ValueError(f"unexpected manifest_version: {payload.get('manifest_version', '')}")
    return payload


def _delivery_history(manifest):
    history = manifest.get("weekly_delivery_history", {})
    return history if isinstance(history, dict) else {}


def _health_reason_text(history):
    reasons = list(history.get("latest_conclusion_health_reasons", []) or [])
    recurring = [
        f"{item.get('reason', 'unknown')} ({item.get('count', 0)})"
        for item in history.get("recurring_health_reasons", []) or []
        if isinstance(item, dict)
    ]
    parts = []
    if reasons:
        parts.append("latest=" + ", ".join(reasons))
    if recurring:
        parts.append("recurring=" + ", ".join(recurring))
    return "; ".join(parts) if parts else "无交付健康原因"


def _int_value(value, default=0):
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _manual_review_count(manifest, history):
    return _int_value(
        history.get("latest_manual_review_pending_count"),
        _int_value(manifest.get("manual_review_queue_count"), 0),
    )


def _action_template(action_code, manifest):
    history = _delivery_history(manifest)
    manual_review_count = _manual_review_count(manifest, history)
    health_text = _health_reason_text(history)
    templates = {
        "review_manual_queue": {
            "title": "检查本周人工复核队列",
            "category": "manual_review",
            "source": f"manual_review_queue_count:{manifest.get('manual_review_queue_count', 0)}",
            "recommended_check": f"按优先级处理 latest_manual_review_queue.csv 中的 {manifest.get('manual_review_queue_count', 0)} 条复核项。",
        },
        "review_manual_review_backlog": {
            "title": "处理人工复核积压",
            "category": "delivery_health",
            "source": health_text,
            "recommended_check": f"优先处理待复核 {manual_review_count} 条，确认是否需要合并 manual_review_decisions.csv。",
        },
        "review_delivery_health_issues": {
            "title": "复查最终交付健康提示",
            "category": "delivery_health",
            "source": health_text,
            "recommended_check": (
                "检查 weekly_delivery_history 中的健康状态 "
                f"{history.get('latest_conclusion_health_status', 'unknown')} / "
                f"{history.get('latest_conclusion_health_score', 0)}，区分人工积压和流程问题。"
            ),
        },
        "review_data_health": {
            "title": "复查数据健康异常",
            "category": "data_health",
            "source": f"data_health_status:{manifest.get('data_health_status', 'unknown')}",
            "recommended_check": "检查三市场 data_health_history.csv、quote_gaps.csv 和缺口分类，确认是否为可接受的数据缺口。",
        },
        "review_backtest_evidence": {
            "title": "复查回测证据质量",
            "category": "backtest",
            "source": f"backtest_status:{manifest.get('backtest_status', 'unknown')}",
            "recommended_check": "检查 latest_backtest_summary.md、成员证据等级和泄漏审计，再决定是否扩大回测样本。",
        },
        "review_candidate_findings": {
            "title": "复查候选结论质量",
            "category": "candidate_review",
            "source": f"candidate_review_status:{manifest.get('candidate_review_status', 'unknown')}",
            "recommended_check": "检查候选风险说明、目标价、建议买入价和数据质量说明是否完整。",
        },
        "continue_sample_accumulation": {
            "title": "继续积累模型跟踪样本",
            "category": "model_tracking",
            "source": f"model_audit_status:{manifest.get('model_audit_status', 'unknown')}",
            "recommended_check": f"当前模型审计为 {manifest.get('model_audit_status', 'unknown')}；继续保留跟踪，不自动升级正式参数。",
        },
        "continue_monitoring": {
            "title": "继续周度监控",
            "category": "monitoring",
            "source": f"automation_status:{manifest.get('automation_status', 'unknown')}",
            "recommended_check": "本周未识别出更高优先级处理项，继续保留周度监控。",
        },
    }
    return templates.get(
        action_code,
        {
            "title": f"复查动作码 {action_code}",
            "category": "monitoring",
            "source": f"automation_status:{manifest.get('automation_status', 'unknown')}",
            "recommended_check": "该动作码尚无专用模板，先查看 latest_self_analysis.md 中的上下文后人工判断。",
        },
    )


def build_weekly_action_items(manifest):
    manifest_path = Path(manifest)
    source = load_manifest(manifest_path)
    actions = list(source.get("automation_priority_actions", []) or [])
    if not actions:
        actions = [source.get("automation_recommended_action", "") or "continue_monitoring"]

    items = []
    for index, action_code in enumerate(actions, start=1):
        template = _action_template(action_code, source)
        items.append(
            {
                "priority": index,
                "status": "open",
                "action_code": action_code,
                "category": template["category"],
                "title": template["title"],
                "source": template["source"],
                "recommended_check": template["recommended_check"],
            }
        )

    return {
        "action_items_schema": ACTION_ITEMS_SCHEMA,
        "action_items_version": ACTION_ITEMS_VERSION,
        "as_of_date": source.get("as_of_date", "unknown"),
        "source_manifest": str(manifest_path),
        "automation_status": source.get("automation_status", "unknown"),
        "item_count": len(items),
        "items": items,
        "boundary": "只读取自我分析 manifest，不抓取行情，不重新评分，不修改正式模型参数。",
    }


def render_weekly_action_items(payload):
    lines = [
        "# 每周人工处理清单",
        "",
        f"- 日期：{payload.get('as_of_date', 'unknown')}",
        f"- 自动化状态：{payload.get('automation_status', 'unknown')}",
        f"- 事项数量：{payload.get('item_count', 0)}",
        f"- 来源：{payload.get('source_manifest', '')}",
        "",
        "## 处理事项",
    ]
    items = payload.get("items", []) or []
    if not items:
        lines.append("- 暂无待处理事项。")
    for item in items:
        lines.extend(
            [
                f"{item.get('priority', 0)}. {item.get('title', '')}",
                f"   - action_code：{item.get('action_code', '')}",
                f"   - category：{item.get('category', '')}",
                f"   - status：{item.get('status', '')}",
                f"   - source：{item.get('source', '')}",
                f"   - recommended_check：{item.get('recommended_check', '')}",
            ]
        )
    lines.extend(
        [
            "",
            "## 边界",
            f"- {payload.get('boundary', '')}",
            "- 该清单用于每周人工复核排序，不代表自动买入、卖出或模型参数调整。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_json(payload, output):
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8-sig",
    )
    return output_path


def write_text(text, output):
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8-sig")
    return output_path


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build weekly manual action items from self-analysis manifest.")
    parser.add_argument("--manifest", default="outputs/automation/latest_self_analysis_manifest.json")
    parser.add_argument("--output", default="outputs/automation/latest_weekly_action_items.json")
    parser.add_argument("--report", default="outputs/automation/latest_weekly_action_items.md")
    args = parser.parse_args()

    payload = build_weekly_action_items(args.manifest)
    report = render_weekly_action_items(payload)
    if args.output:
        write_json(payload, args.output)
    if args.report:
        write_text(report, args.report)
    print(report, end="")


if __name__ == "__main__":
    main()
