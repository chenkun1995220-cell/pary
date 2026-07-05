import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path


VALIDATION_SCHEMA = "one_week_forecast_shadow_parameter_validation"
VALIDATION_VERSION = 1
MARKET_FILES = [
    ("美股周筛", "outputs/us_universe/forecast_evaluations.csv"),
    ("A股周筛", "outputs/cn_universe/forecast_evaluations.csv"),
    ("港股周筛", "outputs/hk_universe/forecast_evaluations.csv"),
]


def _read_json(path):
    source = Path(path)
    if not source.exists():
        return {}
    return json.loads(source.read_text(encoding="utf-8-sig"))


def _read_csv(path):
    source = Path(path)
    if not source.exists():
        return []
    with source.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _evaluated_one_week_rows(project_root):
    root = Path(project_root)
    rows = []
    for market_label, relative_path in MARKET_FILES:
        for row in _read_csv(root / relative_path):
            if str(row.get("evaluation_status", "")).lower() != "evaluated":
                continue
            if str(row.get("prediction_horizon", "")).lower() not in {"1w", "one_week"}:
                continue
            enriched = dict(row)
            enriched["_market_label"] = market_label
            rows.append(enriched)
    return rows


def _latest_as_of_date(rows):
    dates = sorted({str(row.get("as_of_date", "") or "") for row in rows if row.get("as_of_date")})
    return dates[-1] if dates else ""


def _float_value(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _mean(rows, field):
    values = [_float_value(row.get(field)) for row in rows]
    values = [value for value in values if value is not None]
    return sum(values) / len(values) if values else None


def _direction(row, field):
    return str(row.get(field, "") or "").strip().lower()


def _hit_rate(rows, direction_field="predicted_direction"):
    if not rows:
        return None
    hits = 0
    for row in rows:
        if _direction(row, direction_field) == _direction(row, "actual_direction"):
            hits += 1
    return hits / len(rows)


def _baseline(rows):
    return {
        "sample_count": len(rows),
        "direction_hit_rate": _hit_rate(rows),
        "average_actual_return": _mean(rows, "actual_return"),
        "average_excess_return": _mean(rows, "excess_return"),
    }


def _target_is_hk(target):
    text = str(target or "").lower()
    return "港股" in text or "hk" in text


def _apply_candidate(row, action_code, target):
    adjusted = dict(row)
    current = _direction(row, "predicted_direction")
    if action_code == "shadow_demote_down_signal_to_neutral" and current == "down":
        adjusted["shadow_predicted_direction"] = "neutral"
        return adjusted, True
    if action_code == "shadow_review_hk_down_signal" and current == "down":
        market_text = f"{row.get('_market_label', '')} {row.get('market', '')}"
        if _target_is_hk(target) and ("港股" in market_text or "HK" in market_text.upper()):
            adjusted["shadow_predicted_direction"] = "neutral"
            return adjusted, True
    adjusted["shadow_predicted_direction"] = current
    return adjusted, False


def _validate_candidate(rows, candidate, baseline_hit_rate):
    action_code = candidate.get("action_code", "")
    if action_code == "shadow_widen_neutral_band":
        return {
            "action_code": action_code,
            "validation_status": "not_evaluable_current_fields",
            "reason": "prediction_score_or_threshold_distance_missing",
            "affected_count": 0,
            "baseline_hit_rate": baseline_hit_rate,
            "shadow_hit_rate": None,
            "hit_rate_delta": None,
            "formal_model_change_allowed": False,
        }

    adjusted_rows = []
    affected_count = 0
    for row in rows:
        adjusted, affected = _apply_candidate(row, action_code, candidate.get("target", ""))
        adjusted_rows.append(adjusted)
        if affected:
            affected_count += 1
    shadow_hit_rate = _hit_rate(adjusted_rows, direction_field="shadow_predicted_direction")
    delta = None if baseline_hit_rate is None or shadow_hit_rate is None else shadow_hit_rate - baseline_hit_rate
    status = "validated" if affected_count else "not_applicable"
    return {
        "action_code": action_code,
        "validation_status": status,
        "reason": "" if affected_count else "no_matching_rows",
        "affected_count": affected_count,
        "baseline_hit_rate": baseline_hit_rate,
        "shadow_hit_rate": shadow_hit_rate,
        "hit_rate_delta": delta,
        "formal_model_change_allowed": False,
    }


def build_shadow_parameter_validation(project_root=".", plan_path="", as_of_date=None):
    all_rows = _evaluated_one_week_rows(project_root)
    evaluation_as_of_date = _latest_as_of_date(all_rows)
    rows = [row for row in all_rows if row.get("as_of_date") == evaluation_as_of_date] if evaluation_as_of_date else all_rows
    plan = _read_json(plan_path)
    baseline = _baseline(rows)
    baseline_hit_rate = baseline.get("direction_hit_rate")
    candidate_results = [
        _validate_candidate(rows, candidate, baseline_hit_rate)
        for candidate in plan.get("candidate_shadow_changes", []) or []
    ]
    validated_count = sum(1 for item in candidate_results if item.get("validation_status") == "validated")
    if not rows:
        status = "no_evaluable_samples"
    elif validated_count:
        status = "shadow_validation_ready"
    else:
        status = "no_validated_shadow_changes"
    return {
        "validation_schema": VALIDATION_SCHEMA,
        "validation_version": VALIDATION_VERSION,
        "as_of_date": as_of_date or date.today().isoformat(),
        "status": status,
        "source_plan": str(Path(plan_path)),
        "source_plan_status": plan.get("status", ""),
        "evaluation_as_of_date": evaluation_as_of_date,
        "baseline": baseline,
        "candidate_results": candidate_results,
        "validated_candidate_count": validated_count,
        "formal_model_change_allowed": False,
        "acceptance_gates": [
            "compare_hit_rate_delta_before_any_manual_approval",
            "require_shadow_validation_on_next_mature_batch",
            "keep_formal_model_unchanged_until_approved",
        ],
        "boundary": (
            "Only validates one-week forecast shadow parameter candidates from existing forecast_evaluations.csv; "
            "does not change formal model parameters, rerun scoring, or fetch market data."
        ),
    }


def _format_rate(value):
    if value is None:
        return "unknown"
    return f"{value:.2%}"


def _format_delta(value):
    if value is None:
        return "unknown"
    return f"{value:+.2%}"


def render_shadow_parameter_validation(payload):
    baseline = payload.get("baseline", {}) or {}
    lines = [
        "# 1周预测影子参数验证",
        "",
        f"- as_of_date: {payload.get('as_of_date', '')}",
        f"- status: {payload.get('status', '')}",
        f"- baseline_sample_count: {baseline.get('sample_count', 0)}",
        f"- baseline_direction_hit_rate: {_format_rate(baseline.get('direction_hit_rate'))}",
        f"- validated_candidate_count: {payload.get('validated_candidate_count', 0)}",
        f"- formal_model_change_allowed: {str(payload.get('formal_model_change_allowed')).lower()}",
        "",
        "## candidate_results",
        "",
        "| action_code | status | affected | baseline_hit | shadow_hit | delta | reason |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for item in payload.get("candidate_results", []) or []:
        lines.append(
            "| {action_code} | {validation_status} | {affected_count} | {baseline} | {shadow} | {delta} | {reason} |".format(
                action_code=item.get("action_code", ""),
                validation_status=item.get("validation_status", ""),
                affected_count=item.get("affected_count", 0),
                baseline=_format_rate(item.get("baseline_hit_rate")),
                shadow=_format_rate(item.get("shadow_hit_rate")),
                delta=_format_delta(item.get("hit_rate_delta")),
                reason=item.get("reason", ""),
            )
        )
    if not payload.get("candidate_results"):
        lines.append("| - | - | 0 | unknown | unknown | unknown | - |")
    lines.extend(["", "## boundary", "", f"- {payload.get('boundary', '')}", ""])
    return "\n".join(lines)


def write_json(payload, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8-sig")


def write_text(text, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8-sig")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Validate one-week forecast shadow parameter candidates.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--plan", default="outputs/automation/latest_one_week_forecast_shadow_parameter_plan.json")
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--output", default="outputs/automation/latest_one_week_forecast_shadow_parameter_validation.json")
    parser.add_argument("--report", default="outputs/automation/latest_one_week_forecast_shadow_parameter_validation.md")
    args = parser.parse_args()

    payload = build_shadow_parameter_validation(args.project_root, args.plan, as_of_date=args.as_of_date or None)
    report = render_shadow_parameter_validation(payload)
    write_json(payload, args.output)
    write_text(report, args.report)
    print(f"One-week forecast shadow parameter validation: {args.report}")


if __name__ == "__main__":
    main()
