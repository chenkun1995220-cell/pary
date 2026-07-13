import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path


TRACKER_SCHEMA = "extended_shadow_validation_tracker"
TRACKER_VERSION = 1
APPROVAL_DECISION = "approve_for_extended_shadow_validation"
BOUNDARY = "human_decision_only_no_trade_or_model_change"
REQUIRED_BATCHES = 3

DEFAULT_DECISION_HISTORY = "outputs/automation/human_decision_history.csv"
DEFAULT_VALIDATION_HISTORY = (
    "outputs/automation/one_week_forecast_shadow_parameter_validation_history.jsonl"
)
DEFAULT_DECISION_INBOX = "outputs/automation/latest_human_decision_inbox.json"
DEFAULT_SHADOW_DISPOSITION = "outputs/automation/latest_one_week_forecast_shadow_disposition.json"

HISTORY_FIELDS = {
    "decision_key",
    "item_type",
    "source_as_of_date",
    "decision",
    "decided_by",
    "decided_at",
    "boundary_acknowledgement",
}


def _path(root, value):
    candidate = Path(value)
    return candidate if candidate.is_absolute() else Path(root) / candidate


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _read_jsonl(path):
    rows = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError("validation_history_json_invalid") from exc
        if not isinstance(value, dict):
            raise ValueError(f"validation_history_row_not_object:{line_number}")
        rows.append(value)
    return rows


def _read_decision_history(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not HISTORY_FIELDS.issubset(reader.fieldnames):
            raise ValueError("decision_history_columns_invalid")
        return list(reader)


def _authorization_identity(row):
    parts = str(row.get("decision_key", "") or "").split("|")
    if len(parts) != 3 or parts[0] != "forecast_shadow" or not parts[1] or not parts[2]:
        raise ValueError("authorization_decision_key_invalid")
    if row.get("source_as_of_date") != parts[2]:
        raise ValueError("authorization_source_date_mismatch")
    date.fromisoformat(parts[2])
    return parts[1], parts[2]


def _approved_authorizations(rows):
    approved_by_key = {}
    for row in rows:
        if row.get("item_type") != "forecast_shadow" or row.get("decision") != APPROVAL_DECISION:
            continue
        if row.get("boundary_acknowledgement") != BOUNDARY:
            raise ValueError("authorization_boundary_invalid")
        action_code, authorization_date = _authorization_identity(row)
        authorization = {
            "decision_key": row["decision_key"],
            "action_code": action_code,
            "authorization_date": authorization_date,
            "decided_by": row.get("decided_by", ""),
            "decided_at": row.get("decided_at", ""),
            "decision_reason": row.get("decision_reason", ""),
            "boundary_acknowledgement": row.get("boundary_acknowledgement", ""),
        }
        existing = approved_by_key.get(row["decision_key"])
        if existing is not None and existing != authorization:
            raise ValueError("authorization_decision_key_conflict")
        approved_by_key[row["decision_key"]] = authorization
    return list(approved_by_key.values())


def _validate_decision_history_conflicts(rows):
    decisions_by_key = {}
    for row in rows:
        if row.get("item_type") != "forecast_shadow":
            continue
        decision_key = str(row.get("decision_key", "") or "")
        if not decision_key:
            raise ValueError("authorization_decision_key_invalid")
        decision = (
            row.get("source_as_of_date", ""),
            row.get("decision", ""),
            row.get("boundary_acknowledgement", ""),
        )
        existing = decisions_by_key.get(decision_key)
        if existing is not None and existing != decision:
            raise ValueError("authorization_decision_key_conflict")
        decisions_by_key[decision_key] = decision


def _validate_sources(authorizations, inbox, disposition):
    if inbox.get("inbox_schema") != "human_decision_inbox" or inbox.get("status") != "ready":
        raise ValueError("decision_inbox_not_ready")
    for field in (
        "trade_execution_allowed",
        "formal_model_change_allowed",
        "formal_model_conclusion_allowed",
    ):
        if inbox.get(field) is not False:
            raise ValueError(f"decision_inbox_{field}_unsafe")

    inbox_items = {
        item.get("decision_key"): item
        for item in inbox.get("items", []) or []
        if isinstance(item, dict)
    }
    disposition_actions = {
        item.get("action_code")
        for item in disposition.get("candidate_dispositions", []) or []
        if isinstance(item, dict)
    }
    if disposition.get("formal_model_change_allowed") is not False:
        raise ValueError("shadow_disposition_formal_model_change_unsafe")

    for authorization in authorizations:
        item = inbox_items.get(authorization["decision_key"])
        if not item or item.get("decision") != APPROVAL_DECISION:
            raise ValueError("authorization_missing_from_decision_inbox")
        if item.get("action_code") != authorization["action_code"]:
            raise ValueError("authorization_inbox_action_mismatch")
        if authorization["action_code"] not in disposition_actions:
            raise ValueError("authorization_action_missing_from_disposition")


def _logical_history(rows):
    logical = {}
    for row in rows:
        action_code = str(row.get("action_code", "") or "")
        evaluation_date = str(row.get("evaluation_as_of_date", "") or "")
        if not action_code or not evaluation_date:
            raise ValueError("validation_history_identity_missing")
        date.fromisoformat(evaluation_date)
        key = f"{action_code}|{evaluation_date}"
        if key in logical and logical[key] != row:
            raise ValueError(f"validation_history_batch_conflict:{key}")
        logical[key] = row
    return logical


def classify_batch(rows):
    severe_markets = sorted(
        {
            str(market.get("market", "") or "")
            for row in rows
            for market in row.get("market_results", []) or []
            if isinstance(market, dict)
            and (
                market.get("severe_deterioration") is True
                or market.get("severe_market_deterioration") is True
            )
            and market.get("market")
        }
    )
    comparable_rows = [
        row
        for row in rows
        if row.get("validation_status") == "validated"
        and int(row.get("evaluation_sample_count") or 0) > 0
        and row.get("shadow_hit_count") is not None
    ]
    comparable_sample_count = sum(
        int(row.get("evaluation_sample_count") or 0) for row in comparable_rows
    )
    baseline_hit_count = sum(int(row.get("baseline_hit_count") or 0) for row in comparable_rows)
    shadow_hit_count = sum(int(row.get("shadow_hit_count") or 0) for row in comparable_rows)
    baseline_hit_rate = (
        baseline_hit_count / comparable_sample_count if comparable_sample_count else None
    )
    shadow_hit_rate = shadow_hit_count / comparable_sample_count if comparable_sample_count else None
    aggregate_delta = (
        shadow_hit_rate - baseline_hit_rate if comparable_sample_count else None
    )
    if severe_markets:
        classification = "severe_deterioration"
    elif not comparable_sample_count:
        classification = "not_evaluable"
    elif aggregate_delta > 0:
        classification = "positive"
    else:
        classification = "negative"
    return {
        "classification": classification,
        "source_row_count": len(rows),
        "comparable_sample_count": comparable_sample_count,
        "baseline_hit_count": baseline_hit_count,
        "shadow_hit_count": shadow_hit_count if comparable_sample_count else None,
        "baseline_hit_rate": baseline_hit_rate,
        "shadow_hit_rate": shadow_hit_rate,
        "aggregate_hit_rate_delta": aggregate_delta,
        "severe_markets": severe_markets,
    }


def classify_tracker_state(batches):
    classifications = [batch.get("classification") for batch in batches]
    if "severe_deterioration" in classifications:
        return "paused_severe_deterioration", "request_shadow_safety_reapproval"
    evaluable = [value for value in classifications if value in {"positive", "negative"}]
    if len(evaluable) >= 2 and evaluable[-2:] == ["negative", "negative"]:
        return "paused_two_consecutive_negative_batches", "request_shadow_safety_reapproval"
    if len(evaluable) >= REQUIRED_BATCHES:
        return "ready_for_reapproval", "review_extended_shadow_validation_results"
    return "active", "continue_extended_shadow_validation"


def _initial_item(authorization, history):
    action_code = authorization["action_code"]
    authorization_date = authorization["authorization_date"]
    action_rows = [
        row
        for key, row in history.items()
        if key.startswith(f"{action_code}|")
        and str(row.get("evaluation_as_of_date", "")) > authorization_date
    ]
    action_rows.sort(key=lambda row: row["evaluation_as_of_date"])
    batches = []
    for row in action_rows:
        batch = classify_batch([row])
        batch.update(
            {
                "batch_key": f"{action_code}|{row['evaluation_as_of_date']}",
                "action_code": action_code,
                "evaluation_as_of_date": row["evaluation_as_of_date"],
            }
        )
        batches.append(batch)
    classifications = [batch["classification"] for batch in batches]
    evaluable = [value for value in classifications if value in {"positive", "negative"}]
    consecutive_negative_count = 0
    for value in reversed(evaluable):
        if value != "negative":
            break
        consecutive_negative_count += 1
    status, recommended_action = classify_tracker_state(batches)
    return {
        **authorization,
        "post_approval_history_batch_count": len(batches),
        "evaluable_batch_count": len(evaluable),
        "positive_batch_count": classifications.count("positive"),
        "negative_batch_count": classifications.count("negative"),
        "not_evaluable_batch_count": classifications.count("not_evaluable"),
        "severe_deterioration_batch_count": classifications.count("severe_deterioration"),
        "consecutive_negative_batch_count": consecutive_negative_count,
        "remaining_evaluable_batch_count": max(REQUIRED_BATCHES - len(evaluable), 0),
        "status": status,
        "recommended_action": recommended_action,
        "batches": batches,
        "trade_execution_allowed": False,
        "formal_model_change_allowed": False,
        "formal_model_conclusion_allowed": False,
    }


def _blocked_payload(as_of_date, issues):
    return {
        "tracker_schema": TRACKER_SCHEMA,
        "tracker_version": TRACKER_VERSION,
        "as_of_date": as_of_date,
        "status": "blocked",
        "recommended_action": "repair_extended_shadow_validation_inputs",
        "authorization_count": 0,
        "active_authorization_count": 0,
        "ready_for_reapproval_count": 0,
        "paused_count": 0,
        "items": [],
        "issues": issues,
        "boundary": BOUNDARY,
        "trade_execution_allowed": False,
        "formal_model_change_allowed": False,
        "formal_model_conclusion_allowed": False,
    }


def build_extended_shadow_validation_tracker(
    project_root=".",
    decision_history=DEFAULT_DECISION_HISTORY,
    validation_history=DEFAULT_VALIDATION_HISTORY,
    decision_inbox=DEFAULT_DECISION_INBOX,
    shadow_disposition=DEFAULT_SHADOW_DISPOSITION,
    as_of_date=None,
):
    root = Path(project_root)
    effective_date = str(as_of_date or date.today().isoformat())
    try:
        date.fromisoformat(effective_date)
        decisions = _read_decision_history(_path(root, decision_history))
        history_rows = _read_jsonl(_path(root, validation_history))
        inbox = _read_json(_path(root, decision_inbox))
        disposition = _read_json(_path(root, shadow_disposition))
        _validate_decision_history_conflicts(decisions)
        authorizations = _approved_authorizations(decisions)
        _validate_sources(authorizations, inbox, disposition)
        logical_history = _logical_history(history_rows)
        approved_actions = {authorization["action_code"] for authorization in authorizations}
        if any(
            row.get("action_code") in approved_actions
            and str(row.get("evaluation_as_of_date", "")) > effective_date
            for row in logical_history.values()
        ):
            raise ValueError("validation_history_batch_in_future")
        if any(
            authorization["authorization_date"] > effective_date
            for authorization in authorizations
        ):
            raise ValueError("authorization_date_in_future")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _blocked_payload(effective_date, [str(exc)])

    items = [_initial_item(authorization, logical_history) for authorization in authorizations]
    status_priority = [
        "paused_severe_deterioration",
        "paused_two_consecutive_negative_batches",
        "ready_for_reapproval",
        "active",
    ]
    status = next(
        (value for value in status_priority if any(item["status"] == value for item in items)),
        "inactive",
    )
    action_by_status = {
        "paused_severe_deterioration": "request_shadow_safety_reapproval",
        "paused_two_consecutive_negative_batches": "request_shadow_safety_reapproval",
        "ready_for_reapproval": "review_extended_shadow_validation_results",
        "active": "continue_extended_shadow_validation",
        "inactive": "monitor_shadow_authorizations",
    }
    recommended_action = action_by_status[status]
    return {
        "tracker_schema": TRACKER_SCHEMA,
        "tracker_version": TRACKER_VERSION,
        "as_of_date": effective_date,
        "status": status,
        "recommended_action": recommended_action,
        "authorization_count": len(items),
        "active_authorization_count": sum(item["status"] == "active" for item in items),
        "ready_for_reapproval_count": sum(
            item["status"] == "ready_for_reapproval" for item in items
        ),
        "paused_count": sum(item["status"].startswith("paused_") for item in items),
        "items": items,
        "issues": [],
        "boundary": BOUNDARY,
        "trade_execution_allowed": False,
        "formal_model_change_allowed": False,
        "formal_model_conclusion_allowed": False,
    }


def render_extended_shadow_validation_tracker(payload):
    lines = [
        "# 扩展影子验证追踪器",
        "",
        f"- 日期：{payload.get('as_of_date', '')}",
        f"- 状态：{payload.get('status', '')}",
        f"- 建议动作：{payload.get('recommended_action', '')}",
        f"- 授权数：{payload.get('authorization_count', 0)}",
        f"- 交易执行允许：{str(payload.get('trade_execution_allowed')).lower()}",
        f"- 正式模型修改允许：{str(payload.get('formal_model_change_allowed')).lower()}",
        f"- 正式模型结论允许：{str(payload.get('formal_model_conclusion_allowed')).lower()}",
        "",
        "## 授权进度",
        "",
        "| 动作代码 | 审批日期 | 有效进度 | 剩余批次 | 状态 | 下一步 |",
        "|---|---|---:|---:|---|---|",
    ]
    for item in payload.get("items", []) or []:
        lines.append(
            "| {action} | {date} | {done}/{required} | {remaining} | {status} | {action_next} |".format(
                action=item.get("action_code", ""),
                date=item.get("authorization_date", ""),
                done=item.get("evaluable_batch_count", 0),
                required=REQUIRED_BATCHES,
                remaining=item.get("remaining_evaluable_batch_count", REQUIRED_BATCHES),
                status=item.get("status", ""),
                action_next=item.get("recommended_action", ""),
            )
        )
    if not payload.get("items"):
        lines.append("| - | - | 0/3 | 3 | - | - |")
    if payload.get("issues"):
        lines.extend(["", "## 问题", ""])
        lines.extend(f"- {issue}" for issue in payload["issues"])
    lines.extend(["", "## 边界", "", "- 仅用于人工审批后的影子验证，不允许交易或正式模型变更。", ""])
    return "\n".join(lines)


def write_batch_csv(payload, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "decision_key",
        "action_code",
        "authorization_date",
        "batch_key",
        "evaluation_as_of_date",
        "classification",
        "evaluation_sample_count",
        "baseline_hit_count",
        "shadow_hit_count",
    ]
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in payload.get("items", []) or []:
            for batch in item.get("batches", []) or []:
                writer.writerow(
                    {
                        "decision_key": item.get("decision_key", ""),
                        "action_code": item.get("action_code", ""),
                        "authorization_date": item.get("authorization_date", ""),
                        **{field: batch.get(field, "") for field in fields[3:]},
                    }
                )


def _write_text(path, content):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8-sig")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build the extended shadow validation tracker.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--decision-history", default=DEFAULT_DECISION_HISTORY)
    parser.add_argument("--validation-history", default=DEFAULT_VALIDATION_HISTORY)
    parser.add_argument("--decision-inbox", default=DEFAULT_DECISION_INBOX)
    parser.add_argument("--shadow-disposition", default=DEFAULT_SHADOW_DISPOSITION)
    parser.add_argument("--as-of-date", default="")
    parser.add_argument(
        "--output", default="outputs/automation/latest_extended_shadow_validation_tracker.json"
    )
    parser.add_argument(
        "--report", default="outputs/automation/latest_extended_shadow_validation_tracker.md"
    )
    parser.add_argument(
        "--batch-csv", default="outputs/automation/extended_shadow_validation_batches.csv"
    )
    args = parser.parse_args()

    payload = build_extended_shadow_validation_tracker(
        project_root=args.project_root,
        decision_history=args.decision_history,
        validation_history=args.validation_history,
        decision_inbox=args.decision_inbox,
        shadow_disposition=args.shadow_disposition,
        as_of_date=args.as_of_date or None,
    )
    root = Path(args.project_root)
    _write_text(
        _path(root, args.output),
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _write_text(_path(root, args.report), render_extended_shadow_validation_tracker(payload))
    write_batch_csv(payload, _path(root, args.batch_csv))
    print(f"Extended shadow validation tracker: {_path(root, args.report)}")


if __name__ == "__main__":
    main()
