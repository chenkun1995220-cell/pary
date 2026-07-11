import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path


REVIEW_SCHEMA = "first_one_month_forecast_evaluation_review"
REVIEW_VERSION = 1
COHORT_MARKET = "港股"
COHORT_GENERATED_DATE = "2026-07-06"
EXPECTED_SAMPLE_COUNT = 37
ONE_WEEK_MATURITY_DATE = "2026-07-13"
ONE_MONTH_MATURITY_DATE = "2026-08-03"

MARKET_PATHS = {
    "US": "outputs/us_universe/forecast_evaluations.csv",
    "CN": "outputs/cn_universe/forecast_evaluations.csv",
    "HK": "outputs/hk_universe/forecast_evaluations.csv",
}


def _read_csv_rows(path):
    csv_path = Path(path)
    if not csv_path.exists():
        return None
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
        ]


def _cohort_key(row):
    return (
        row.get("market", ""),
        row.get("ticker", ""),
        row.get("generated_date", ""),
        row.get("model_version", ""),
    )


def _evaluation_key(row):
    return _cohort_key(row) + (row.get("prediction_horizon", ""),)


def _float_value(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _average(values):
    cleaned = [value for value in values if value is not None]
    return sum(cleaned) / len(cleaned) if cleaned else None


def _is_true(value):
    return str(value or "").strip().lower() == "true"


def _failure_type(row):
    predicted = row.get("predicted_direction", "")
    actual = row.get("actual_direction", "")
    if not row.get("prediction_signal") or predicted not in {"up", "neutral", "down"}:
        return "missing_prediction_signal"
    if (
        _float_value(row.get("actual_return")) is None
        or _float_value(row.get("benchmark_return")) is None
        or _float_value(row.get("excess_return")) is None
    ):
        return "return_data_missing"
    if predicted == actual:
        return None
    if predicted == "neutral":
        return "predicted_neutral_but_moved"
    if actual == "neutral":
        return "predicted_move_but_actual_neutral"
    return "opposite_direction"


def _failure_sample(cohort_row, evaluation, horizon, failure_type):
    source = evaluation or cohort_row
    return {
        "market": source.get("market", ""),
        "ticker": source.get("ticker", ""),
        "company": source.get("company_name", ""),
        "generated_date": source.get("generated_date", ""),
        "horizon": horizon,
        "predicted_direction": (evaluation or {}).get("predicted_direction", ""),
        "actual_direction": (evaluation or {}).get("actual_direction", ""),
        "actual_return": (evaluation or {}).get("actual_return", ""),
        "excess_return": (evaluation or {}).get("excess_return", ""),
        "failure_type": failure_type,
    }


def _horizon_review(cohort, evaluations, horizon, as_of, maturity_date):
    matched = []
    failure_samples = []
    failure_type_counts = {}
    evaluation_due = as_of >= date.fromisoformat(maturity_date)
    for row in cohort:
        evaluation = evaluations.get(_cohort_key(row) + (horizon,))
        if evaluation is None:
            failure_type = "evaluation_missing" if evaluation_due else "evaluation_not_mature"
            failure_type_counts[failure_type] = failure_type_counts.get(failure_type, 0) + 1
            failure_samples.append(_failure_sample(row, None, horizon, failure_type))
            continue
        matched.append(evaluation)
        failure_type = _failure_type(evaluation)
        if failure_type:
            failure_type_counts[failure_type] = failure_type_counts.get(failure_type, 0) + 1
            failure_samples.append(_failure_sample(row, evaluation, horizon, failure_type))
    valid = [
        row
        for row in matched
        if _failure_type(row) not in {"missing_prediction_signal", "return_data_missing"}
        and row.get("actual_direction") in {"up", "neutral", "down"}
    ]
    return {
        "prediction_horizon": horizon,
        "maturity_date": maturity_date,
        "expected_sample_count": EXPECTED_SAMPLE_COUNT,
        "matched_evaluation_count": len(matched),
        "valid_evaluation_count": len(valid),
        "missing_evaluation_count": max(EXPECTED_SAMPLE_COUNT - len(valid), 0),
        "direction_hits": sum(1 for row in valid if _is_true(row.get("direction_hit"))),
        "direction_hit_rate": (
            sum(1 for row in valid if _is_true(row.get("direction_hit"))) / len(valid)
            if valid
            else None
        ),
        "average_return": _average(_float_value(row.get("actual_return")) for row in valid),
        "average_benchmark_return": _average(
            _float_value(row.get("benchmark_return")) for row in valid
        ),
        "average_excess_return": _average(_float_value(row.get("excess_return")) for row in valid),
        "positive_excess_return_count": sum(
            1 for row in valid if (_float_value(row.get("excess_return")) or 0) > 0
        ),
        "failure_type_counts": failure_type_counts,
        "failure_samples": failure_samples,
        "evaluation_due": evaluation_due,
    }


def _market_comparison(one_week, one_month):
    return {
        "status": "insufficient_market_coverage",
        "cross_market_comparison_allowed": False,
        "markets_with_cohort_samples": 1,
        "markets": {
            "US": {"status": "not_in_cohort", "cohort_sample_count": 0},
            "CN": {"status": "not_in_cohort", "cohort_sample_count": 0},
            "HK": {
                "status": "ready",
                "cohort_sample_count": EXPECTED_SAMPLE_COUNT,
                "one_week_valid_count": one_week.get("valid_evaluation_count", 0),
                "one_week_direction_hit_rate": one_week.get("direction_hit_rate"),
                "one_week_average_excess_return": one_week.get("average_excess_return"),
                "one_month_valid_count": one_month.get("valid_evaluation_count", 0),
                "one_month_direction_hit_rate": one_month.get("direction_hit_rate"),
                "one_month_average_excess_return": one_month.get("average_excess_return"),
            },
        },
    }


def build_review(project_root, as_of_date):
    root = Path(project_root)
    as_of = date.fromisoformat(str(as_of_date))
    history_path = root / "outputs/hk_universe/forecast_history.csv"
    history = _read_csv_rows(history_path)
    issues = []
    if history is None:
        history = []
        issues.append("cohort_history_missing")
    cohort = [
        row
        for row in history
        if row.get("market") == COHORT_MARKET
        and row.get("generated_date") == COHORT_GENERATED_DATE
    ]
    if len(cohort) != EXPECTED_SAMPLE_COUNT:
        issues.append("cohort_count_mismatch")
    cohort_keys = [_cohort_key(row) for row in cohort]
    duplicate_cohort_keys = sorted(
        {"|".join(key) for key in cohort_keys if cohort_keys.count(key) > 1}
    )
    if duplicate_cohort_keys:
        issues.append("duplicate_cohort_keys")

    evaluation_rows = []
    missing_market_files = []
    for market, relative_path in MARKET_PATHS.items():
        rows = _read_csv_rows(root / relative_path)
        if rows is None:
            missing_market_files.append(market)
        else:
            evaluation_rows.extend(rows)
    if missing_market_files:
        issues.append("evaluation_inputs_missing")
    evaluations = {}
    duplicate_evaluation_keys = []
    for row in evaluation_rows:
        key = _evaluation_key(row)
        if key in evaluations:
            duplicate_evaluation_keys.append("|".join(key))
        else:
            evaluations[key] = row
    if duplicate_evaluation_keys:
        issues.append("duplicate_evaluation_keys")

    one_week = _horizon_review(
        cohort, evaluations, "1w", as_of, ONE_WEEK_MATURITY_DATE
    )
    one_month = _horizon_review(
        cohort, evaluations, "1m", as_of, ONE_MONTH_MATURITY_DATE
    )

    if issues:
        status = "needs_attention"
        recommended_action = "repair_first_one_month_review_inputs"
    elif as_of < date.fromisoformat(ONE_MONTH_MATURITY_DATE):
        status = "awaiting_maturity"
        recommended_action = "wait_for_one_month_maturity"
    elif one_week["valid_evaluation_count"] < EXPECTED_SAMPLE_COUNT or one_month[
        "valid_evaluation_count"
    ] < EXPECTED_SAMPLE_COUNT:
        status = "sample_incomplete"
        recommended_action = "repair_first_cohort_evaluation_gaps"
    else:
        status = "review_ready"
        recommended_action = "review_first_one_month_results_manually"

    return {
        "review_schema": REVIEW_SCHEMA,
        "review_version": REVIEW_VERSION,
        "as_of_date": as_of.isoformat(),
        "status": status,
        "cohort": {
            "market": "HK",
            "generated_date": COHORT_GENERATED_DATE,
            "expected_sample_count": EXPECTED_SAMPLE_COUNT,
            "actual_sample_count": len(cohort),
            "one_week_maturity_date": ONE_WEEK_MATURITY_DATE,
            "one_month_maturity_date": ONE_MONTH_MATURITY_DATE,
            "sample_key": "market+ticker+generated_date+model_version",
            "evaluation_key": "market+ticker+generated_date+model_version+prediction_horizon",
        },
        "one_week": one_week,
        "one_month": one_month,
        "market_comparison": _market_comparison(one_week, one_month),
        "duplicate_cohort_key_count": len(duplicate_cohort_keys),
        "duplicate_cohort_key_samples": duplicate_cohort_keys[:20],
        "duplicate_evaluation_key_count": len(duplicate_evaluation_keys),
        "duplicate_evaluation_key_samples": duplicate_evaluation_keys[:20],
        "issues": issues,
        "recommended_action": recommended_action,
        "formal_model_change_allowed": False,
        "formal_model_conclusion_allowed": False,
        "boundary": (
            "Only evaluates the fixed first one-month forecast cohort from existing files; "
            "does not fetch data, rerun forecasts, rescore candidates, or change the formal model."
        ),
    }


def _percent(value):
    return "-" if value is None else f"{value:.2%}"


def _number(value):
    return "-" if value is None else f"{value:.4f}"


def render_report(payload):
    one_week = payload.get("one_week", {})
    one_month = payload.get("one_month", {})
    issues = payload.get("issues", [])
    lines = [
        "# 首批1个月预测评价",
        "",
        f"- 日期：{payload.get('as_of_date', '')}",
        f"- 状态：{payload.get('status', 'missing')}",
        f"- 固定队列：{payload.get('cohort', {}).get('actual_sample_count', 0)}/37",
        f"- 1周有效评价：{one_week.get('valid_evaluation_count', 0)}/37",
        f"- 1周方向命中率：{_percent(one_week.get('direction_hit_rate'))}",
        f"- 1周平均超额收益：{_number(one_week.get('average_excess_return'))}",
        f"- 1个月有效评价：{one_month.get('valid_evaluation_count', 0)}/37",
        f"- 1个月方向命中率：{_percent(one_month.get('direction_hit_rate'))}",
        f"- 1个月平均超额收益：{_number(one_month.get('average_excess_return'))}",
        f"- 市场比较：{payload.get('market_comparison', {}).get('status', 'missing')}",
        f"- 下一步：{payload.get('recommended_action', '')}",
        "- 正式模型修改：不允许",
        "- 正式模型优劣结论：不允许形成正式模型结论",
        "",
        "## 失败类型",
        "",
        f"- 1周：{json.dumps(one_week.get('failure_type_counts', {}), ensure_ascii=False, sort_keys=True)}",
        f"- 1个月：{json.dumps(one_month.get('failure_type_counts', {}), ensure_ascii=False, sort_keys=True)}",
        "",
        "## 问题",
        "",
    ]
    lines.extend(f"- {issue}" for issue in issues)
    if not issues:
        lines.append("- 无")
    lines.extend(["", "## 边界", "", f"- {payload.get('boundary', '')}"])
    return "\n".join(lines) + "\n"


def write_outputs(payload, output, report):
    output_path = Path(output)
    report_path = Path(report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(render_report(payload), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Review the fixed first one-month forecast cohort.")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--as-of-date", default=date.today().isoformat())
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    try:
        payload = build_review(args.project_root, args.as_of_date)
        write_outputs(payload, args.output, args.report)
    except Exception as exc:
        print(f"First one-month forecast evaluation review failed: {exc}", file=sys.stderr)
        return 1
    print(render_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
