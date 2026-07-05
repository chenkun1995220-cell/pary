import argparse
import json
import sys
from datetime import date
from pathlib import Path


PLAN_SCHEMA = "one_week_forecast_shadow_parameter_plan"
PLAN_VERSION = 1
MIN_REVIEW_SAMPLES = 30


def _read_json(path):
    source = Path(path)
    if not source.exists():
        return {}
    return json.loads(source.read_text(encoding="utf-8-sig"))


def _float_value(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int_value(value, default=0):
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _direction_group(payload, direction):
    for item in payload.get("direction_groups", []) or []:
        if str(item.get("predicted_direction", "")).lower() == direction:
            return item
    return {}


def _candidate_changes(payload):
    changes = []
    down = _direction_group(payload, "down")
    down_samples = _int_value(down.get("sample_count"))
    down_hit_rate = _float_value(down.get("direction_hit_rate"))
    down_opposite = _int_value(down.get("opposite_miss_count"))
    down_avg_return = _float_value(down.get("average_actual_return"))
    if down_samples >= 10 and down_hit_rate < 0.20 and down_opposite >= 5 and down_avg_return > 0:
        changes.append(
            {
                "action_code": "shadow_demote_down_signal_to_neutral",
                "scope": "one_week_prediction",
                "target": "predicted_direction=down",
                "proposal": "In shadow backtest only, remap one-week down signals to neutral or set their weight to zero.",
                "evidence": (
                    f"down samples={down_samples}, hit_rate={down_hit_rate:.2%}, "
                    f"opposite_miss={down_opposite}, average_actual_return={down_avg_return:.2%}"
                ),
                "formal_model_change_allowed": False,
            }
        )

    neutral_pressure = sum(
        _int_value(item.get("neutral_miss_count")) for item in payload.get("direction_groups", []) or []
    )
    evaluated = _int_value(payload.get("one_week_evaluated_count"))
    if evaluated and neutral_pressure / evaluated >= 0.40:
        changes.append(
            {
                "action_code": "shadow_widen_neutral_band",
                "scope": "one_week_prediction",
                "target": "direction_thresholds",
                "proposal": "In shadow backtest only, widen the neutral band before emitting up/down labels.",
                "evidence": f"neutral_miss={neutral_pressure}, one_week_evaluated={evaluated}",
                "formal_model_change_allowed": False,
            }
        )

    for market in payload.get("market_groups", []) or []:
        market_hit_rate = _float_value(market.get("direction_hit_rate"))
        market_opposite = _int_value(market.get("opposite_miss_count"))
        market_samples = _int_value(market.get("sample_count"))
        if market_samples >= 20 and market_hit_rate < 0.10 and market_opposite >= 10:
            changes.append(
                {
                    "action_code": "shadow_review_hk_down_signal",
                    "scope": "market_specific_one_week_prediction",
                    "target": str(market.get("market", "")),
                    "proposal": "In shadow backtest only, evaluate a market-specific down-signal dampener.",
                    "evidence": (
                        f"market={market.get('market', '')}, samples={market_samples}, "
                        f"hit_rate={market_hit_rate:.2%}, opposite_miss={market_opposite}"
                    ),
                    "formal_model_change_allowed": False,
                }
            )
    return changes


def build_shadow_parameter_plan(calibration_review, as_of_date=None):
    payload = _read_json(calibration_review)
    evaluated = _int_value(payload.get("one_week_evaluated_count"))
    changes = _candidate_changes(payload) if evaluated >= MIN_REVIEW_SAMPLES else []
    status = "shadow_plan_ready" if changes else ("insufficient_samples" if evaluated < MIN_REVIEW_SAMPLES else "clear")
    return {
        "plan_schema": PLAN_SCHEMA,
        "plan_version": PLAN_VERSION,
        "as_of_date": as_of_date or payload.get("as_of_date") or date.today().isoformat(),
        "status": status,
        "source_calibration_review": str(Path(calibration_review)),
        "source_calibration_status": payload.get("status", ""),
        "one_week_evaluated_count": evaluated,
        "minimum_review_samples": MIN_REVIEW_SAMPLES,
        "execution_mode": "shadow_only",
        "candidate_shadow_changes": changes,
        "candidate_change_count": len(changes),
        "acceptance_gates": [
            "run_shadow_backtest_before_formal_change",
            "compare_against_current_model",
            "require_human_approval",
            "keep_formal_model_unchanged_until_approved",
        ],
        "formal_model_change_allowed": False,
        "boundary": (
            "Only prepares one-week forecast shadow parameter candidates; does not change formal model "
            "parameters, does not rerun scoring, and does not fetch market data."
        ),
    }


def render_shadow_parameter_plan(payload):
    lines = [
        "# 1周预测影子参数方案",
        "",
        f"- as_of_date: {payload.get('as_of_date', '')}",
        f"- status: {payload.get('status', '')}",
        f"- execution_mode: {payload.get('execution_mode', '')}",
        f"- one_week_evaluated_count: {payload.get('one_week_evaluated_count', 0)}",
        f"- candidate_change_count: {payload.get('candidate_change_count', 0)}",
        f"- formal_model_change_allowed: {str(payload.get('formal_model_change_allowed')).lower()}",
        "",
        "## candidate_shadow_changes",
        "",
        "| action_code | scope | target | proposal | evidence |",
        "|---|---|---|---|---|",
    ]
    for item in payload.get("candidate_shadow_changes", []) or []:
        lines.append(
            "| {action_code} | {scope} | {target} | {proposal} | {evidence} |".format(**item)
        )
    if not payload.get("candidate_shadow_changes"):
        lines.append("| - | - | - | - | - |")
    lines.extend(
        [
            "",
            "## acceptance_gates",
            "",
        ]
    )
    for gate in payload.get("acceptance_gates", []) or []:
        lines.append(f"- {gate}")
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
    parser = argparse.ArgumentParser(description="Build one-week forecast shadow parameter plan.")
    parser.add_argument(
        "--calibration-review",
        default="outputs/automation/latest_one_week_forecast_calibration_review.json",
    )
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--output", default="outputs/automation/latest_one_week_forecast_shadow_parameter_plan.json")
    parser.add_argument("--report", default="outputs/automation/latest_one_week_forecast_shadow_parameter_plan.md")
    args = parser.parse_args()

    payload = build_shadow_parameter_plan(args.calibration_review, as_of_date=args.as_of_date or None)
    report = render_shadow_parameter_plan(payload)
    write_json(payload, args.output)
    write_text(report, args.report)
    print(f"One-week forecast shadow parameter plan: {args.report}")


if __name__ == "__main__":
    main()
