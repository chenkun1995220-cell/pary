import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path


REVIEW_SCHEMA = "backtest_evidence_review"
REVIEW_VERSION = 1
MIN_VERIFIED_RATIO_FOR_SAMPLE_EXPANSION = 0.5
DEFAULT_POLICY = "data/config/sp500_historical_evidence_policy.json"
MEMBERSHIP_EVIDENCE_TIER_POLICY = {
    "verified": {
        "expansion_eligible": True,
        "use": "eligible_for_sample_expansion_after_other_gates_clear",
        "required_source": "official_s_and_p_global_membership_evidence",
    },
    "secondary": {
        "expansion_eligible": False,
        "use": "crosscheck_only_not_formal_expansion_evidence",
        "required_source": "replace_with_official_s_and_p_global_source",
    },
    "insufficient": {
        "expansion_eligible": False,
        "use": "blocked_until_source_supplied",
        "required_source": "supply_verified_membership_evidence",
    },
}


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


def _load_policy(path):
    if not path:
        return {}
    policy_path = Path(path)
    if not policy_path.exists():
        return {}
    payload = json.loads(policy_path.read_text(encoding="utf-8-sig"))
    payload["_path"] = str(policy_path)
    return payload


def _evidence_ceiling_active(policy):
    return bool(
        policy.get("policy_schema") == "sp500_historical_evidence_policy"
        and policy.get("policy_version") == 1
        and policy.get("status") == "evidence_ceiling_confirmed"
        and policy.get("official_source_acquisition_closed") is True
        and policy.get("limited_backtest_only") is True
        and policy.get("recurring_supplement_request_enabled") is False
        and policy.get("formal_backtest_expansion_allowed") is False
        and policy.get("historical_membership_auto_update_allowed") is False
        and policy.get("formal_model_change_allowed") is False
    )


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


def _membership_evidence_tier_counts(gap_report):
    counts = {
        "verified_rows": _int_value(gap_report.get("verified_rows")),
        "weak_rows": _int_value(gap_report.get("weak_rows")),
        "total_rows": _int_value(gap_report.get("total_rows")),
    }
    gap_counts = {}
    for gap in gap_report.get("_queue_source_gaps", []) or []:
        tier = str(gap.get("current_evidence", "") or "insufficient")
        gap_counts[tier] = gap_counts.get(tier, 0) + 1
    for tier, count in gap_counts.items():
        counts[f"{tier}_gap_tickers"] = count
    return counts


def _membership_evidence_gate(fields, gap_report, sample_expansion):
    weak_rows = _int_value(fields.get("Weak evidence rows"))
    blocking_tiers = []
    for gap in gap_report.get("_queue_source_gaps", []) or []:
        tier = str(gap.get("current_evidence", "") or "insufficient")
        if not MEMBERSHIP_EVIDENCE_TIER_POLICY.get(tier, {}).get("expansion_eligible", False):
            if tier not in blocking_tiers:
                blocking_tiers.append(tier)
    if weak_rows and "weak" not in blocking_tiers:
        blocking_tiers.append("weak")
    allowed = bool(sample_expansion.get("backtest_sample_expansion_allowed")) and not blocking_tiers
    return {
        "membership_evidence_gate_status": "clear" if allowed else "blocked",
        "membership_evidence_gate_decision": (
            "verified_only_expansion_review_allowed"
            if allowed
            else "verified_only_no_expansion"
        ),
        "membership_evidence_tier_policy": MEMBERSHIP_EVIDENCE_TIER_POLICY,
        "membership_evidence_blocking_tiers": blocking_tiers,
        "membership_evidence_tier_counts": _membership_evidence_tier_counts(gap_report),
        "historical_membership_auto_update_allowed": False,
    }


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


def _sample_expansion_decision(fields, gap_report, action_required_count):
    weeks_failed = _int_value(fields.get("Weeks failed"))
    weak_rows = _int_value(fields.get("Weak evidence rows"))
    weak_weeks = _int_value(fields.get("Weak evidence weeks"))
    ratio = _verified_ratio(fields.get("Membership evidence verified"))
    reasons = []
    if weeks_failed:
        reasons.append("backtest_weeks_failed")
    if gap_report.get("status") != "ready":
        reasons.append("membership_gap_report_not_ready")
    if ratio is None:
        reasons.append("verified_membership_ratio_unknown")
    elif ratio < MIN_VERIFIED_RATIO_FOR_SAMPLE_EXPANSION:
        reasons.append("verified_membership_ratio_below_threshold")
    if weak_rows:
        reasons.append("weak_evidence_rows_present")
    if weak_weeks:
        reasons.append("weak_evidence_weeks_present")
    if action_required_count:
        reasons.append("membership_evidence_actions_open")

    allowed = not reasons
    return {
        "backtest_sample_expansion_allowed": allowed,
        "backtest_sample_expansion_decision": (
            "expand_backtest_sample_after_manual_review"
            if allowed
            else "do_not_expand_backtest_sample"
        ),
        "backtest_sample_expansion_reason": reasons or ["verified_membership_evidence_sufficient"],
        "required_verified_membership_ratio_for_expansion": MIN_VERIFIED_RATIO_FOR_SAMPLE_EXPANSION,
    }


def build_backtest_evidence_review(summary, as_of_date=None, policy=None):
    summary_path = Path(summary)
    text = _read_text(summary_path)
    fields = _summary_fields(text)
    gap_report = _load_gap_report(_gap_report_path(summary_path))
    evidence_policy = _load_policy(policy)
    evidence_ceiling_active = _evidence_ceiling_active(evidence_policy)
    unresolved_gap_count = _int_value(gap_report.get("gap_count"))
    action_queue = (
        []
        if evidence_ceiling_active
        else _membership_evidence_action_queue(gap_report)
    )
    action_required_count = 0 if evidence_ceiling_active else unresolved_gap_count
    action_queue_count = len(action_queue)
    action_unqueued_count = max(action_required_count - action_queue_count, 0)
    public_gap_report = dict(gap_report)
    public_gap_report.pop("_queue_source_gaps", None)
    status, recommended_action, upgrade_allowed = _decision(fields, gap_report)
    sample_expansion = _sample_expansion_decision(fields, gap_report, action_required_count)
    if evidence_ceiling_active:
        status = "evidence_ceiling_confirmed"
        recommended_action = "maintain_limited_backtest"
        upgrade_allowed = False
        sample_expansion["backtest_sample_expansion_allowed"] = False
        sample_expansion["backtest_sample_expansion_decision"] = (
            "do_not_expand_backtest_sample"
        )
        reasons = list(sample_expansion.get("backtest_sample_expansion_reason", []))
        if "evidence_ceiling_confirmed_limited_backtest_only" not in reasons:
            reasons.append("evidence_ceiling_confirmed_limited_backtest_only")
        sample_expansion["backtest_sample_expansion_reason"] = reasons
    evidence_gate = _membership_evidence_gate(fields, gap_report, sample_expansion)
    backtest_as_of_date = _as_of_date(fields)
    return {
        "review_schema": REVIEW_SCHEMA,
        "review_version": REVIEW_VERSION,
        "as_of_date": as_of_date or date.today().isoformat(),
        "backtest_as_of_date": backtest_as_of_date,
        "source_summary": str(summary_path),
        "status": status,
        "recommended_action": recommended_action,
        "evidence_ceiling_status": (
            "evidence_ceiling_confirmed" if evidence_ceiling_active else "not_confirmed"
        ),
        "evidence_ceiling_effective_date": evidence_policy.get("effective_date", ""),
        "backtest_mode": (
            "limited_verified_only" if evidence_ceiling_active else "evidence_improvement_open"
        ),
        "official_source_acquisition_closed": bool(
            evidence_policy.get("official_source_acquisition_closed")
        ),
        "limited_backtest_only": bool(evidence_policy.get("limited_backtest_only")),
        "recurring_supplement_request_enabled": evidence_policy.get(
            "recurring_supplement_request_enabled"
        ),
        "evidence_policy_path": evidence_policy.get("_path", ""),
        "evidence_policy_closure_reasons": evidence_policy.get("closure_reasons", []),
        "weeks_completed": _int_value(fields.get("Weeks completed")),
        "weeks_failed": _int_value(fields.get("Weeks failed")),
        "membership_evidence_verified": fields.get("Membership evidence verified", "unknown"),
        "verified_membership_ratio": _verified_ratio(fields.get("Membership evidence verified")),
        "weak_evidence_rows": _int_value(fields.get("Weak evidence rows")),
        "weak_evidence_weeks": _int_value(fields.get("Weak evidence weeks")),
        "evidence_status": fields.get("Evidence status", "unknown"),
        "evidence_next_action": recommended_action,
        "source_evidence_next_action": fields.get("Evidence next action", "unknown"),
        "backtest_report": fields.get("Backtest report", ""),
        "data_leakage_audit": fields.get("Data leakage audit", ""),
        "model_comparison": fields.get("Model comparison", ""),
        "log": fields.get("Log", ""),
        "gap_report": public_gap_report,
        "membership_evidence_unresolved_gap_count": unresolved_gap_count,
        "membership_evidence_action_required_count": action_required_count,
        "membership_evidence_action_queue_count": action_queue_count,
        "membership_evidence_action_unqueued_count": action_unqueued_count,
        "membership_evidence_action_queue": action_queue,
        **sample_expansion,
        **evidence_gate,
        "formal_model_upgrade_allowed": upgrade_allowed,
        "formal_model_change_allowed": False,
        "boundary": "只读取现有严格时点回测摘要和成员证据缺口报告，不抓取行情，不重新回测，不修改正式模型参数。",
    }


def _pct(value):
    if value is None:
        return "unknown"
    return f"{float(value):.2%}"


def render_backtest_evidence_review(payload):
    upgrade_text = "允许进入正式升级复核" if payload.get("formal_model_upgrade_allowed") else "不得自动升级正式模型"
    expansion_allowed = bool(payload.get("backtest_sample_expansion_allowed", False))
    expansion_reasons = ", ".join(payload.get("backtest_sample_expansion_reason", []) or ["unknown"])
    lines = [
        "# 回测证据复核结论",
        f"- evidence_ceiling_status: {payload.get('evidence_ceiling_status', 'not_confirmed')}",
        f"- backtest_mode: {payload.get('backtest_mode', 'unknown')}",
        f"- membership_evidence_unresolved_gap_count: {payload.get('membership_evidence_unresolved_gap_count', 0)}",
        f"- membership_evidence_action_required_count: {payload.get('membership_evidence_action_required_count', 0)}",
        f"- membership_evidence_action_queue_count: {payload.get('membership_evidence_action_queue_count', 0)}",
        f"- membership_evidence_action_unqueued_count: {payload.get('membership_evidence_action_unqueued_count', 0)}",
        "",
        f"- 复核日期：{payload.get('as_of_date', 'unknown')}",
        f"- 回测日期：{payload.get('backtest_as_of_date', 'unknown')}",
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
        "## 回测样本扩展决策",
        "",
        f"- 扩样允许：{str(expansion_allowed).lower()}",
        f"- 扩样决策：{payload.get('backtest_sample_expansion_decision', 'unknown')}",
        f"- 扩样证据门槛：verified ratio >= {_pct(payload.get('required_verified_membership_ratio_for_expansion'))}",
        f"- 当前 verified ratio：{_pct(payload.get('verified_membership_ratio'))}",
        f"- 决策原因：{expansion_reasons}",
        (
            "- 执行动作：证据上限已确认，仅保留受限回测；不得重复生成官方历史来源补充任务。"
            if payload.get("evidence_ceiling_status") == "evidence_ceiling_confirmed"
            else "- 执行动作：先补充 verified S&P Global 历史成分证据，再考虑扩大回测样本。"
        ),
        "",
        "## 成员证据分层闸门",
        "",
        f"- gate_status：{payload.get('membership_evidence_gate_status', 'unknown')}",
        f"- gate_decision：{payload.get('membership_evidence_gate_decision', 'unknown')}",
        f"- blocking_tiers：{', '.join(payload.get('membership_evidence_blocking_tiers', []) or []) or 'none'}",
        f"- historical_membership_auto_update_allowed：{str(bool(payload.get('historical_membership_auto_update_allowed', False))).lower()}",
        "- 执行边界：不得自动更新 historical_membership.csv；secondary 只作为交叉校验，不得作为正式扩样证据。",
        "",
        "| 证据等级 | 可用于扩样 | 用途 | 需要来源 |",
        "|---|---|---|---|",
    ]
    for tier, policy in (payload.get("membership_evidence_tier_policy", {}) or {}).items():
        lines.append(
            f"| {tier} | {str(bool(policy.get('expansion_eligible'))).lower()} | "
            f"{policy.get('use', '')} | {policy.get('required_source', '')} |"
        )
    counts = payload.get("membership_evidence_tier_counts", {}) or {}
    lines.extend(
        [
            "",
            f"- verified_rows：{counts.get('verified_rows', 0)}",
            f"- weak_rows：{counts.get('weak_rows', 0)}",
            f"- total_rows：{counts.get('total_rows', 0)}",
            f"- secondary_gap_tickers：{counts.get('secondary_gap_tickers', 0)}",
            "",
        "## 证据缺口样例",
        "",
        "| 排名 | 股票 | 公司 | 证据等级 | 影响周数 | 建议动作 |",
        "|---:|---|---|---|---:|---|",
        ]
    )
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
    parser.add_argument("--policy", default=DEFAULT_POLICY)
    parser.add_argument("--output", default="outputs/automation/latest_backtest_evidence_review.json")
    parser.add_argument("--report", default="outputs/automation/latest_backtest_evidence_review.md")
    parser.add_argument("--as-of-date", default="")
    args = parser.parse_args()

    payload = build_backtest_evidence_review(
        args.summary,
        as_of_date=args.as_of_date or None,
        policy=args.policy,
    )
    report = render_backtest_evidence_review(payload)
    if args.output:
        write_json(payload, args.output)
    if args.report:
        write_text(report, args.report)
    print(report, end="")
    print(f"Backtest evidence review: {args.report}")


if __name__ == "__main__":
    main()
