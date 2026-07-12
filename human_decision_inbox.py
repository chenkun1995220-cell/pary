import argparse
import csv
import json
from datetime import date
from pathlib import Path


INBOX_SCHEMA = "human_decision_inbox"
INBOX_VERSION = 1
BOUNDARY = "human_decision_only_no_trade_or_model_change"
RISK_SCHEMA = "candidate_risk_resolution_review"
SHADOW_SCHEMA = "one_week_forecast_shadow_disposition"
DEFAULT_RISK_REVIEW = "outputs/automation/latest_candidate_risk_resolution_review.json"
DEFAULT_SHADOW_DISPOSITION = (
    "outputs/automation/latest_one_week_forecast_shadow_disposition.json"
)
DEFAULT_AUTHORIZATIONS = "data/manual/human_decision_authorizations.csv"
AUTHORIZATION_FIELDS = [
    "decision_key",
    "decision",
    "decided_by",
    "decided_at",
    "decision_reason",
    "boundary_acknowledgement",
]
CANDIDATE_DECISIONS = [
    "approve_for_continued_research",
    "downgrade_to_watchlist",
    "reject_candidate_research",
    "continue_observation",
]
SHADOW_DECISIONS = [
    "approve_for_extended_shadow_validation",
    "reject_shadow_candidate",
    "continue_observation",
]


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_csv(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _safe_list(value):
    return value if isinstance(value, list) else []


def _candidate_items(payload):
    source_date = str(payload.get("as_of_date", ""))
    result = []
    for source in _safe_list(payload.get("items")):
        if not source.get("manual_decision_required"):
            continue
        market = str(source.get("market", "")).strip()
        ticker = str(source.get("ticker", "")).strip()
        decision_key = f"candidate_risk|{market}|{ticker}|{source_date}"
        result.append(
            {
                "item_type": "candidate_risk",
                "decision_key": decision_key,
                "source_as_of_date": source_date,
                "market": market,
                "ticker": ticker,
                "company": source.get("company", ""),
                "action_code": "",
                "evidence": {
                    "total_score": source.get("total_score"),
                    "current_price": source.get("current_price"),
                    "buy_price": source.get("buy_price"),
                    "target_price": source.get("target_price"),
                    "expected_return": source.get("expected_return"),
                    "sensitivity": source.get("sensitivity", {}),
                    "core_risks": _safe_list(source.get("core_risks")),
                    "buy_conditions": _safe_list(source.get("buy_conditions")),
                    "abandon_conditions": _safe_list(source.get("abandon_conditions")),
                    "deep_dive_review": source.get("deep_dive_review", {}),
                },
                "allowed_decisions": list(CANDIDATE_DECISIONS),
            }
        )
    return result


def _shadow_items(payload):
    source_date = str(payload.get("evaluation_as_of_date") or payload.get("as_of_date") or "")
    result = []
    for source in _safe_list(payload.get("candidate_dispositions")):
        if source.get("disposition") != "pending_human_approval":
            continue
        action_code = str(source.get("action_code", "")).strip()
        decision_key = f"forecast_shadow|{action_code}|{source_date}"
        result.append(
            {
                "item_type": "forecast_shadow",
                "decision_key": decision_key,
                "source_as_of_date": source_date,
                "market": "",
                "ticker": "",
                "company": "",
                "action_code": action_code,
                "evidence": {
                    "independent_batch_count": source.get("independent_batch_count", 0),
                    "evaluation_sample_count": source.get("evaluation_sample_count", 0),
                    "comparable_sample_count": source.get("comparable_sample_count", 0),
                    "affected_count": source.get("affected_count", 0),
                    "affected_market_count": source.get("affected_market_count", 0),
                    "affected_markets": _safe_list(source.get("affected_markets")),
                    "baseline_hit_rate": source.get("baseline_hit_rate"),
                    "shadow_hit_rate": source.get("shadow_hit_rate"),
                    "hit_rate_delta": source.get("aggregate_hit_rate_delta"),
                    "severe_market_deterioration": _safe_list(
                        source.get("severe_market_deterioration")
                    ),
                },
                "allowed_decisions": list(SHADOW_DECISIONS),
            }
        )
    return result


def _source_issues(risk_payload, shadow_payload, as_of_date):
    issues = []
    if not isinstance(risk_payload, dict):
        issues.append("candidate_risk_source_missing_or_invalid")
    elif risk_payload.get("review_schema") != RISK_SCHEMA:
        issues.append("candidate_risk_source_schema_invalid")
    elif risk_payload.get("status") != "ready":
        issues.append("candidate_risk_source_not_ready")
    if not isinstance(shadow_payload, dict):
        issues.append("forecast_shadow_source_missing_or_invalid")
    elif shadow_payload.get("disposition_schema") != SHADOW_SCHEMA:
        issues.append("forecast_shadow_source_schema_invalid")
    elif shadow_payload.get("status") != "ready":
        issues.append("forecast_shadow_source_not_ready")
    for label, payload, field in (
        ("candidate_risk", risk_payload, "as_of_date"),
        ("forecast_shadow", shadow_payload, "evaluation_as_of_date"),
    ):
        if isinstance(payload, dict):
            source_date = str(payload.get(field) or payload.get("as_of_date") or "")
            if as_of_date and source_date != as_of_date:
                issues.append(f"{label}_source_date_mismatch")
    return issues


def build_human_decision_inbox(
    project_root=".",
    candidate_risk_review=DEFAULT_RISK_REVIEW,
    shadow_disposition=DEFAULT_SHADOW_DISPOSITION,
    authorizations=DEFAULT_AUTHORIZATIONS,
    as_of_date=None,
):
    root = Path(project_root)
    effective_date = str(as_of_date or date.today().isoformat())
    risk_payload = _read_json(root / candidate_risk_review)
    shadow_payload = _read_json(root / shadow_disposition)
    issues = _source_issues(risk_payload, shadow_payload, effective_date)
    items = []
    if isinstance(risk_payload, dict):
        items.extend(_candidate_items(risk_payload))
    if isinstance(shadow_payload, dict):
        items.extend(_shadow_items(shadow_payload))
    for item in items:
        item.update(
            {
                "decision_status": "pending",
                "decision": "",
                "decided_by": "",
                "decided_at": "",
                "decision_reason": "",
                "boundary_acknowledgement": "",
                "trade_execution_allowed": False,
                "formal_model_change_allowed": False,
                "formal_model_conclusion_allowed": False,
            }
        )
    pending_count = len(items)
    status = "blocked" if issues else ("manual_review_needed" if pending_count else "ready")
    recommended_action = (
        "repair_human_decision_inbox_sources"
        if issues
        else ("review_human_decision_inbox" if pending_count else "monitor_next_run")
    )
    return {
        "inbox_schema": INBOX_SCHEMA,
        "inbox_version": INBOX_VERSION,
        "as_of_date": effective_date,
        "status": status,
        "recommended_action": recommended_action,
        "item_count": len(items),
        "pending_count": pending_count,
        "decided_count": 0,
        "invalid_decision_count": 0,
        "items": items,
        "issues": issues,
        "authorization_source": str(authorizations),
        "boundary": BOUNDARY,
        "trade_execution_allowed": False,
        "formal_model_change_allowed": False,
        "formal_model_conclusion_allowed": False,
    }


def render_human_decision_inbox(payload):
    lines = [
        "# 统一人工决策收件箱",
        "",
        f"- 日期：{payload.get('as_of_date', '')}",
        f"- 状态：{payload.get('status', 'unknown')}",
        f"- 总事项：{payload.get('item_count', 0)}",
        f"- 待决定：{payload.get('pending_count', 0)}",
        f"- 已决定：{payload.get('decided_count', 0)}",
        f"- 非法决定：{payload.get('invalid_decision_count', 0)}",
        "- 边界：只允许人工研究或影子验证决定，不允许交易或正式模型变更。",
        "",
        "| 类型 | 标识 | 公司/方案 | 状态 |",
        "|---|---|---|---|",
    ]
    for item in payload.get("items", []):
        subject = item.get("company") or item.get("action_code") or item.get("ticker")
        lines.append(
            f"| {item.get('item_type', '')} | {item.get('decision_key', '')} | "
            f"{subject} | {item.get('decision_status', '')} |"
        )
    if payload.get("issues"):
        lines.extend(["", "## 问题", ""])
        lines.extend(f"- {issue}" for issue in payload["issues"])
    return "\n".join(lines) + "\n"


def write_json(payload, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig"
    )


def write_text(text, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig")


def write_inbox_csv(payload, path):
    fields = [
        "item_type",
        "decision_key",
        "market",
        "ticker",
        "company",
        "action_code",
        "source_as_of_date",
        "decision_status",
        "decision",
    ]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(payload.get("items", []))


def write_authorization_template(path):
    path = Path(path)
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        csv.DictWriter(handle, fieldnames=AUTHORIZATION_FIELDS).writeheader()
    return True


def main():
    parser = argparse.ArgumentParser(description="Build the unified human decision inbox.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--candidate-risk-review", default=DEFAULT_RISK_REVIEW)
    parser.add_argument("--shadow-disposition", default=DEFAULT_SHADOW_DISPOSITION)
    parser.add_argument("--authorizations", default=DEFAULT_AUTHORIZATIONS)
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--output", default="outputs/automation/latest_human_decision_inbox.json")
    parser.add_argument("--report", default="outputs/automation/latest_human_decision_inbox.md")
    parser.add_argument("--csv-output", default="outputs/automation/human_decision_inbox.csv")
    parser.add_argument("--authorization-template", default=DEFAULT_AUTHORIZATIONS)
    parser.add_argument("--history", default="outputs/automation/human_decision_history.csv")
    args = parser.parse_args()
    root = Path(args.project_root)
    payload = build_human_decision_inbox(
        root,
        candidate_risk_review=args.candidate_risk_review,
        shadow_disposition=args.shadow_disposition,
        authorizations=args.authorizations,
        as_of_date=args.as_of_date or None,
    )
    write_json(payload, root / args.output)
    write_text(render_human_decision_inbox(payload), root / args.report)
    write_inbox_csv(payload, root / args.csv_output)
    write_authorization_template(root / args.authorization_template)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
