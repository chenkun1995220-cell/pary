import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path


REVIEW_SCHEMA = "backtest_evidence_review"
REVIEW_VERSION = 1


def _read_text(path):
    text_path = Path(path)
    if not text_path.exists():
        return ""
    return text_path.read_text(encoding="utf-8-sig")


def _summary_fields(text):
    fields = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        body = stripped[2:]
        if ":" not in body:
            continue
        key, value = body.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def _int_value(value, default=0):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _verified_ratio(value):
    text = str(value or "")
    match = re.search(r"\(([-+]?\d+(?:\.\d+)?)%\)", text)
    if match:
        return round(float(match.group(1)) / 100, 4)
    fraction = re.search(r"(\d+)\s*/\s*(\d+)", text)
    if fraction and int(fraction.group(2)):
        return round(int(fraction.group(1)) / int(fraction.group(2)), 4)
    return None


def _as_of_date(fields):
    raw = fields.get("Run time", "")
    if not raw:
        return "unknown"
    try:
        return datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S").date().isoformat()
    except ValueError:
        return raw[:10] if len(raw) >= 10 else "unknown"


def _gap_report_path(summary_path):
    return Path(summary_path).parent / "latest_membership_evidence_gaps.json"


def _load_gap_report(path):
    gap_path = Path(path)
    if not gap_path.exists():
        return {
            "status": "missing",
            "gap_count": 0,
            "weak_rows": 0,
            "verified_rows": 0,
            "total_rows": 0,
            "top_gaps": [],
            "_queue_source_gaps": [],
            "path": str(gap_path),
        }
    payload = json.loads(gap_path.read_text(encoding="utf-8-sig"))
    gaps = list(payload.get("gaps", []) or [])
    return {
        "status": "ready",
        "schema": payload.get("schema", ""),
        "version": payload.get("version", ""),
        "gap_count": _int_value(payload.get("gap_count")),
        "returned_gap_count": _int_value(payload.get("returned_gap_count")),
        "weak_rows": _int_value(payload.get("weak_rows")),
        "verified_rows": _int_value(payload.get("verified_rows")),
        "total_rows": _int_value(payload.get("total_rows")),
        "membership_path": payload.get("membership_path", ""),
        "top_gaps": gaps[:10],
        "_queue_source_gaps": gaps[:50],
        "path": str(gap_path),
    }


def _action_type(gap):
    recommended = str(gap.get("recommended_action", ""))
    current_evidence = str(gap.get("current_evidence", ""))
    if recommended == "supplement_official_spglobal_source" or current_evidence in {"secondary", "weak", ""}:
        return "supplement_official_membership_source"
    return "review_membership_evidence"


def _membership_evidence_action_queue(gap_report):
    queue = []
    for gap in gap_report.get("_queue_source_gaps", []) or []:
        queue.append(
            {
                "rank": _int_value(gap.get("rank")),
                "ticker": gap.get("ticker", ""),
                "company_name": gap.get("company_name", ""),
                "action_type": _action_type(gap),
                "current_evidence": gap.get("current_evidence", ""),
                "weeks_affected": _int_value(gap.get("weeks_affected")),
                "first_week": gap.get("first_week", ""),
                "last_week": gap.get("last_week", ""),
                "recommended_action": gap.get("recommended_action", ""),
                "recommended_source": "official_spglobal_membership_evidence",
            }
        )
    return queue


def _decision(fields, gap_report):
    evidence_status = fields.get("Evidence status", "unknown")
    weak_rows = _int_value(fields.get("Weak evidence rows"))
    weak_weeks = _int_value(fields.get("Weak evidence weeks"))
    weeks_failed = _int_value(fields.get("Weeks failed"))
    ratio = _verified_ratio(fields.get("Membership evidence verified"))
    if weeks_failed:
        return "backtest_run_failed", "rerun_or_debug_backtest", False
    if evidence_status == "ready" and weak_rows == 0 and (ratio is None or ratio >= 0.8):
        return "ready", "continue_monitoring", True
    if evidence_status in {"evidence_review_needed", "unknown"} or weak_rows or weak_weeks:
        return "evidence_review_needed", fields.get("Evidence next action", "supplement_verified_membership_evidence"), False
    if gap_report.get("status") != "ready":
        return "evidence_review_needed", "regenerate_membership_evidence_gaps", False
    return evidence_status, fields.get("Evidence next action", "review_backtest_evidence"), False


def build_backtest_evidence_review(summary):
    summary_path = Path(summary)
    text = _read_text(summary_path)
    fields = _summary_fields(text)
    gap_report = _load_gap_report(_gap_report_path(summary_path))
    action_queue = _membership_evidence_action_queue(gap_report)
    action_required_count = _int_value(gap_report.get("gap_count"))
    action_queue_count = len(action_queue)
    action_unqueued_count = max(action_required_count - action_queue_count, 0)
    public_gap_report = dict(gap_report)
    public_gap_report.pop("_queue_source_gaps", None)
    status, recommended_action, upgrade_allowed = _decision(fields, gap_report)
    return {
        "review_schema": REVIEW_SCHEMA,
        "review_version": REVIEW_VERSION,
        "as_of_date": _as_of_date(fields),
        "source_summary": str(summary_path),
        "status": status,
        "recommended_action": recommended_action,
        "weeks_completed": _int_value(fields.get("Weeks completed")),
        "weeks_failed": _int_value(fields.get("Weeks failed")),
        "membership_evidence_verified": fields.get("Membership evidence verified", "unknown"),
        "verified_membership_ratio": _verified_ratio(fields.get("Membership evidence verified")),
        "weak_evidence_rows": _int_value(fields.get("Weak evidence rows")),
        "weak_evidence_weeks": _int_value(fields.get("Weak evidence weeks")),
        "evidence_status": fields.get("Evidence status", "unknown"),
        "evidence_next_action": fields.get("Evidence next action", "unknown"),
        "backtest_report": fields.get("Backtest report", ""),
        "data_leakage_audit": fields.get("Data leakage audit", ""),
        "model_comparison": fields.get("Model comparison", ""),
        "log": fields.get("Log", ""),
        "gap_report": public_gap_report,
        "membership_evidence_action_required_count": action_required_count,
        "membership_evidence_action_queue_count": action_queue_count,
        "membership_evidence_action_unqueued_count": action_unqueued_count,
        "membership_evidence_action_queue": action_queue,
        "formal_model_upgrade_allowed": upgrade_allowed,
        "boundary": "只读取现有严格时点回测摘要和成员证据缺口报告，不抓取行情，不重新回测，不修改正式模型参数。",
    }


def _pct(value):
    if value is None:
        return "unknown"
    return f"{float(value):.2%}"


def render_backtest_evidence_review(payload):
    upgrade_text = "允许进入正式升级复核" if payload.get("formal_model_upgrade_allowed") else "不得自动升级正式模型"
    lines = [
        "# 回测证据复核结论",
        f"- membership_evidence_action_required_count: {payload.get('membership_evidence_action_required_count', 0)}",
        f"- membership_evidence_action_queue_count: {payload.get('membership_evidence_action_queue_count', 0)}",
        f"- membership_evidence_action_unqueued_count: {payload.get('membership_evidence_action_unqueued_count', 0)}",
        "",
        f"- 日期：{payload.get('as_of_date', 'unknown')}",
        f"- 状态：{payload.get('status', 'unknown')}",
        f"- 建议动作：{payload.get('recommended_action', 'unknown')}",
        f"- 完成周数：{payload.get('weeks_completed', 0)}",
        f"- 失败周数：{payload.get('weeks_failed', 0)}",
        f"- 成员证据 verified：{payload.get('membership_evidence_verified', 'unknown')}",
        f"- verified 比例：{_pct(payload.get('verified_membership_ratio'))}",
        f"- 弱证据行：{payload.get('weak_evidence_rows', 0)}",
        f"- 弱证据周数：{payload.get('weak_evidence_weeks', 0)}",
        f"- 正式模型升级：{upgrade_text}",
        "",
        "## 证据缺口样例",
        "",
        "| 排名 | 股票 | 公司 | 证据等级 | 影响周数 | 建议动作 |",
        "|---:|---|---|---|---:|---|",
    ]
    gaps = payload.get("gap_report", {}).get("top_gaps", []) or []
    if not gaps:
        lines.append("| - | - | - | - | - | 无证据缺口样例 |")
    else:
        for item in gaps[:10]:
            lines.append(
                f"| {item.get('rank', '')} | {item.get('ticker', '')} | {item.get('company_name', '')} | "
                f"{item.get('current_evidence', '')} | {item.get('weeks_affected', 0)} | "
                f"{item.get('recommended_action', '')} |"
            )
    lines.extend(
        [
            "",
            "## 关键路径",
            f"- backtest_report: {payload.get('backtest_report', '')}",
            f"- data_leakage_audit: {payload.get('data_leakage_audit', '')}",
            f"- model_comparison: {payload.get('model_comparison', '')}",
            f"- gap_report: {payload.get('gap_report', {}).get('path', '')}",
            "",
            "## 边界",
            f"- {payload.get('boundary', '')}",
            "- 该复核只用于判断回测证据是否足以支撑发布或模型升级建议，不构成投资建议。",
            "",
        ]
    )
    return "\n".join(lines)


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
    parser = argparse.ArgumentParser(description="Build backtest evidence review from automation summary.")
    parser.add_argument("--summary", default="outputs/automation/latest_backtest_summary.md")
    parser.add_argument("--output", default="outputs/automation/latest_backtest_evidence_review.json")
    parser.add_argument("--report", default="outputs/automation/latest_backtest_evidence_review.md")
    args = parser.parse_args()

    payload = build_backtest_evidence_review(args.summary)
    report = render_backtest_evidence_review(payload)
    if args.output:
        write_json(payload, args.output)
    if args.report:
        write_text(report, args.report)
    print(report, end="")
    print(f"Backtest evidence review: {args.report}")


if __name__ == "__main__":
    main()
