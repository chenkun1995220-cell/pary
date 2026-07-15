import argparse
import errno
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path


if os.name == "nt":
    import msvcrt
else:
    import fcntl


DISPOSITION_SCHEMA = "one_week_forecast_shadow_disposition"
DISPOSITION_VERSION = 1
PLAN_SCHEMA = "one_week_forecast_shadow_parameter_plan"
VALIDATION_SCHEMA = "one_week_forecast_shadow_parameter_validation"
MIN_BATCHES = 3
MIN_AFFECTED = 30
MIN_MARKETS = 2
MIN_POSITIVE_BATCHES = 2
SEVERE_MARKET_MIN_AFFECTED = 10
SEVERE_MARKET_DELTA = -0.05
MAX_SOURCE_AGE_DAYS = 8
VALID_DISPOSITIONS = {"continue_observation", "rejected", "pending_human_approval"}


def _is_lock_contention_error(error):
    error_number = getattr(error, "errno", None)
    if os.name == "nt":
        winerror = getattr(error, "winerror", None)
        if winerror is not None:
            return winerror in {32, 33}
        return error_number in {errno.EACCES, errno.EAGAIN}
    return error_number in {errno.EACCES, errno.EAGAIN}


@contextmanager
def history_file_lock(history_path, timeout_seconds=30.0, poll_interval=0.05):
    try:
        timeout_seconds = float(timeout_seconds)
    except (TypeError, ValueError):
        raise ValueError("timeout_seconds must be a finite non-negative number") from None
    if not math.isfinite(timeout_seconds) or timeout_seconds < 0:
        raise ValueError("timeout_seconds must be a finite non-negative number")

    try:
        poll_interval = float(poll_interval)
    except (TypeError, ValueError):
        raise ValueError("poll_interval must be a finite positive number") from None
    if not math.isfinite(poll_interval) or poll_interval <= 0:
        raise ValueError("poll_interval must be a finite positive number")

    lock_path = Path(f"{Path(history_path)}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    acquired = False
    first_attempt = True
    last_error = None

    with lock_path.open("a+b") as lock_file:
        if lock_path.stat().st_size == 0:
            lock_file.write(b"\0")
            lock_file.flush()

        while True:
            if not first_attempt and time.monotonic() >= deadline:
                raise TimeoutError(f"timed out acquiring history lock: {lock_path}") from last_error
            try:
                lock_file.seek(0)
                if os.name == "nt":
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError as error:
                if not _is_lock_contention_error(error):
                    raise
                last_error = error
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"timed out acquiring history lock: {lock_path}") from error
                time.sleep(min(poll_interval, remaining))
                first_attempt = False

        try:
            yield
        finally:
            if acquired:
                active_error = sys.exc_info()[1]
                try:
                    lock_file.seek(0)
                    if os.name == "nt":
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                except OSError as unlock_error:
                    if active_error is None:
                        raise
                    if hasattr(active_error, "add_note"):
                        active_error.add_note(f"history lock release failed: {unlock_error}")


def _read_json(path):
    source = Path(path)
    if not source.exists():
        return {}
    try:
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path):
    source = Path(path)
    if not source.exists():
        return []
    rows = []
    for line in source.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _int_value(value, default=0):
    try:
        return int(value if value is not None else default)
    except (TypeError, ValueError):
        return default


def _float_value(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _rate(hit_count, sample_count):
    return hit_count / sample_count if sample_count else None


def _delta(baseline_rate, shadow_rate):
    if baseline_rate is None or shadow_rate is None:
        return None
    return shadow_rate - baseline_rate


def _parse_date(value):
    try:
        return datetime.strptime(str(value or ""), "%Y-%m-%d").date()
    except ValueError:
        return None


def _source_is_fresh(validation, as_of_date):
    current = _parse_date(as_of_date)
    source = _parse_date(validation.get("as_of_date") or validation.get("evaluation_as_of_date"))
    if current is None or source is None:
        return False
    return 0 <= (current - source).days <= MAX_SOURCE_AGE_DAYS


def validation_history_records(validation):
    if validation.get("validation_schema") != VALIDATION_SCHEMA:
        return []
    evaluation_as_of_date = str(validation.get("evaluation_as_of_date", "") or "")
    if not evaluation_as_of_date:
        return []
    rows = []
    for candidate in validation.get("candidate_results", []) or []:
        if not isinstance(candidate, dict) or not candidate.get("action_code"):
            continue
        row = dict(candidate)
        row["evaluation_as_of_date"] = evaluation_as_of_date
        row["formal_model_change_allowed"] = False
        rows.append(row)
    return rows


def _history_key(row):
    key = (
        str(row.get("evaluation_as_of_date", "") or ""),
        str(row.get("action_code", "") or ""),
    )
    return key if all(key) else None


def _canonical_history_row(row):
    return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def history_rows_to_append(history_rows, new_rows):
    latest = {}
    for row in history_rows or []:
        if isinstance(row, dict) and (key := _history_key(row)):
            latest[key] = _canonical_history_row(row)
    pending = []
    for row in new_rows or []:
        if not isinstance(row, dict) or not (key := _history_key(row)):
            continue
        canonical = _canonical_history_row(row)
        if latest.get(key) == canonical:
            continue
        pending.append(row)
        latest[key] = canonical
    return pending


def logical_history(rows):
    by_key = {}
    duplicate_count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = (
            str(row.get("evaluation_as_of_date", "") or ""),
            str(row.get("action_code", "") or ""),
        )
        if not all(key):
            continue
        if key in by_key:
            duplicate_count += 1
        by_key[key] = row
    ordered = sorted(by_key.values(), key=lambda row: (row["evaluation_as_of_date"], row["action_code"]))
    return ordered, duplicate_count


def _batch_delta(row):
    sample_count = _int_value(row.get("evaluation_sample_count"))
    baseline_rate = _rate(_int_value(row.get("baseline_hit_count")), sample_count)
    shadow_hits = row.get("shadow_hit_count")
    shadow_rate = None if shadow_hits is None else _rate(_int_value(shadow_hits), sample_count)
    return _delta(baseline_rate, shadow_rate)


def _market_summary(rows):
    totals = defaultdict(
        lambda: {
            "sample_count": 0,
            "affected_count": 0,
            "baseline_hit_count": 0,
            "shadow_hit_count": 0,
        }
    )
    for row in rows:
        for market in row.get("market_results", []) or []:
            name = str(market.get("market", "") or "").strip()
            if not name:
                continue
            item = totals[name]
            item["sample_count"] += _int_value(market.get("sample_count"))
            item["affected_count"] += _int_value(market.get("affected_count"))
            item["baseline_hit_count"] += _int_value(market.get("baseline_hit_count"))
            item["shadow_hit_count"] += _int_value(market.get("shadow_hit_count"))
    results = []
    for name in sorted(totals):
        item = totals[name]
        baseline_rate = _rate(item["baseline_hit_count"], item["sample_count"])
        shadow_rate = _rate(item["shadow_hit_count"], item["sample_count"])
        item = dict(item)
        item.update(
            {
                "market": name,
                "baseline_hit_rate": baseline_rate,
                "shadow_hit_rate": shadow_rate,
                "hit_rate_delta": _delta(baseline_rate, shadow_rate),
            }
        )
        results.append(item)
    return results


def _candidate_summary(action_code, rows, sources_fresh):
    batch_count = len(rows)
    affected_count = sum(_int_value(row.get("affected_count")) for row in rows)
    evaluation_sample_count = sum(_int_value(row.get("evaluation_sample_count")) for row in rows)
    baseline_hit_count = sum(_int_value(row.get("baseline_hit_count")) for row in rows)
    shadow_rows = [row for row in rows if row.get("shadow_hit_count") is not None]
    shadow_sample_count = sum(_int_value(row.get("evaluation_sample_count")) for row in shadow_rows)
    shadow_hit_count = sum(_int_value(row.get("shadow_hit_count")) for row in shadow_rows)
    baseline_comparable_hits = sum(_int_value(row.get("baseline_hit_count")) for row in shadow_rows)
    baseline_rate = _rate(baseline_comparable_hits, shadow_sample_count)
    shadow_rate = _rate(shadow_hit_count, shadow_sample_count)
    aggregate_delta = _delta(baseline_rate, shadow_rate)
    deltas = [_batch_delta(row) for row in rows]
    positive_count = sum(delta is not None and delta > 0 for delta in deltas)
    negative_count = sum(delta is not None and delta < 0 for delta in deltas)
    not_evaluable_reasons = Counter(
        str(row.get("reason", "") or "")
        for row in rows
        if str(row.get("validation_status", "")).startswith("not_evaluable")
    )
    market_results = _market_summary(rows)
    affected_markets = [item for item in market_results if item["affected_count"] > 0]
    severe_markets = [
        item["market"]
        for item in market_results
        if item["affected_count"] >= SEVERE_MARKET_MIN_AFFECTED
        and item["hit_rate_delta"] is not None
        and item["hit_rate_delta"] <= SEVERE_MARKET_DELTA
    ]
    return {
        "action_code": action_code,
        "independent_batch_count": batch_count,
        "affected_count": affected_count,
        "affected_market_count": len(affected_markets),
        "affected_markets": [item["market"] for item in affected_markets],
        "evaluation_sample_count": evaluation_sample_count,
        "comparable_sample_count": shadow_sample_count,
        "baseline_hit_count": baseline_hit_count,
        "comparable_baseline_hit_count": baseline_comparable_hits,
        "shadow_hit_count": shadow_hit_count,
        "baseline_hit_rate": baseline_rate,
        "shadow_hit_rate": shadow_rate,
        "aggregate_hit_rate_delta": aggregate_delta,
        "positive_batch_count": positive_count,
        "negative_batch_count": negative_count,
        "not_evaluable_batch_count": sum(not_evaluable_reasons.values()),
        "same_not_evaluable_reason_count": max(not_evaluable_reasons.values(), default=0),
        "market_results": market_results,
        "severe_market_deterioration": severe_markets,
        "sources_fresh": bool(sources_fresh),
    }


def classify_candidate(summary):
    if summary["independent_batch_count"] >= MIN_BATCHES and summary["same_not_evaluable_reason_count"] >= MIN_BATCHES:
        return "rejected", ["repeated_not_evaluable"], "close_rejected_shadow_candidate"
    if summary["independent_batch_count"] >= MIN_BATCHES and summary["affected_count"] == 0:
        return "rejected", ["no_applicable_samples"], "close_rejected_shadow_candidate"
    if summary["severe_market_deterioration"]:
        return "rejected", ["severe_market_deterioration"], "close_rejected_shadow_candidate"
    aggregate_delta = summary.get("aggregate_hit_rate_delta")
    if summary["independent_batch_count"] >= MIN_BATCHES and aggregate_delta is not None and aggregate_delta <= 0:
        return "rejected", ["non_positive_aggregate_delta"], "close_rejected_shadow_candidate"

    gates = {
        "independent_batches": summary["independent_batch_count"] >= MIN_BATCHES,
        "affected_samples": summary["affected_count"] >= MIN_AFFECTED,
        "market_coverage": summary["affected_market_count"] >= MIN_MARKETS,
        "positive_aggregate_delta": aggregate_delta is not None and aggregate_delta > 0,
        "positive_batches": summary["positive_batch_count"] >= MIN_POSITIVE_BATCHES,
        "sources_fresh": summary["sources_fresh"],
    }
    if all(gates.values()):
        return "pending_human_approval", ["minimum_evidence_gates_met"], "review_shadow_candidate_approval"
    reasons = [f"{name}_pending" for name, passed in gates.items() if not passed]
    return "continue_observation", reasons, "continue_shadow_validation"


def _recommended_action(status, candidates):
    if status != "ready":
        return "repair_shadow_disposition_inputs"
    dispositions = {item.get("disposition") for item in candidates}
    if "pending_human_approval" in dispositions:
        return "review_shadow_candidate_approval"
    if "continue_observation" in dispositions:
        return "continue_shadow_validation"
    return "none"


def build_shadow_disposition(plan, validation, history_rows, performance, as_of_date=None):
    as_of_date = as_of_date or date.today().isoformat()
    attention_reasons = []
    if plan.get("plan_schema") != PLAN_SCHEMA:
        attention_reasons.append("invalid_source_plan")
    if validation.get("validation_schema") != VALIDATION_SCHEMA:
        attention_reasons.append("invalid_source_validation")
    if not validation.get("evaluation_as_of_date"):
        attention_reasons.append("missing_evaluation_as_of_date")
    if plan.get("formal_model_change_allowed") is True or validation.get("formal_model_change_allowed") is True:
        attention_reasons.append("formal_model_change_unsafe")

    plan_actions = {
        str(item.get("action_code", "") or "")
        for item in plan.get("candidate_shadow_changes", []) or []
        if isinstance(item, dict) and item.get("action_code")
    }
    validation_actions = {
        str(item.get("action_code", "") or "")
        for item in validation.get("candidate_results", []) or []
        if isinstance(item, dict) and item.get("action_code")
    }
    if plan_actions and validation_actions != plan_actions:
        attention_reasons.append("candidate_action_contract_mismatch")

    new_rows = validation_history_records(validation)
    pending_rows = history_rows_to_append(history_rows, new_rows)
    combined_rows = list(history_rows or []) + pending_rows
    logical_rows, duplicate_count = logical_history(combined_rows)
    sources_fresh = _source_is_fresh(validation, as_of_date)
    if not sources_fresh:
        attention_reasons.append("source_validation_stale_or_invalid")

    status = "needs_attention" if attention_reasons else "ready"
    candidates = []
    for action_code in sorted(plan_actions):
        action_rows = [row for row in logical_rows if row.get("action_code") == action_code]
        summary = _candidate_summary(action_code, action_rows, sources_fresh)
        disposition, reason_codes, next_action = classify_candidate(summary)
        summary.update(
            {
                "disposition": disposition,
                "reason_codes": reason_codes,
                "next_action": next_action,
                "formal_model_change_allowed": False,
            }
        )
        candidates.append(summary)

    counts = {value: 0 for value in sorted(VALID_DISPOSITIONS)}
    for candidate in candidates:
        counts[candidate["disposition"]] += 1
    recommended_action = _recommended_action(status, candidates)
    return {
        "disposition_schema": DISPOSITION_SCHEMA,
        "disposition_version": DISPOSITION_VERSION,
        "as_of_date": as_of_date,
        "status": status,
        "attention_reasons": attention_reasons,
        "source_plan_status": plan.get("status", ""),
        "source_validation_status": validation.get("status", ""),
        "evaluation_as_of_date": validation.get("evaluation_as_of_date", ""),
        "history_records_added": len(pending_rows),
        "logical_history_record_count": len(logical_rows),
        "duplicate_history_key_count": duplicate_count,
        "candidate_dispositions": candidates,
        "disposition_counts": counts,
        "recommended_action": recommended_action,
        "next_one_week_evaluation_date": performance.get("next_one_week_evaluation_date", ""),
        "next_one_week_evaluation_count": _int_value(performance.get("next_one_week_evaluation_count")),
        "formal_model_change_allowed": False,
        "acceptance_gates": {
            "minimum_independent_batches": MIN_BATCHES,
            "minimum_affected_samples": MIN_AFFECTED,
            "minimum_affected_markets": MIN_MARKETS,
            "minimum_positive_batches": MIN_POSITIVE_BATCHES,
            "maximum_source_age_days": MAX_SOURCE_AGE_DAYS,
        },
        "boundary": (
            "Shadow disposition only; does not fetch data, rerun scoring, apply candidate parameters, "
            "or modify the formal model."
        ),
    }


def _format_rate(value):
    return "unknown" if value is None else f"{value:.2%}"


def render_shadow_disposition(payload):
    counts = payload.get("disposition_counts", {}) or {}
    lines = [
        "# 1周预测影子候选处置",
        "",
        f"- 日期：{payload.get('as_of_date', '')}",
        f"- 状态：{payload.get('status', '')}",
        f"- 推荐动作：{payload.get('recommended_action', '')}",
        f"- continue_observation：{counts.get('continue_observation', 0)}",
        f"- rejected：{counts.get('rejected', 0)}",
        f"- pending_human_approval：{counts.get('pending_human_approval', 0)}",
        f"- 下一批1周评价：{payload.get('next_one_week_evaluation_date', '')} ({payload.get('next_one_week_evaluation_count', 0)})",
        f"- 正式模型修改允许：{str(payload.get('formal_model_change_allowed')).lower()}",
        "",
        "## 候选处置",
        "",
        "| 候选 | 批次 | 影响样本 | 市场 | 基准命中 | 影子命中 | 变化 | 处置 | 下一步 |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for item in payload.get("candidate_dispositions", []) or []:
        lines.append(
            "| {action} | {batches} | {affected} | {markets} | {baseline} | {shadow} | {delta} | {disposition} | {next_action} |".format(
                action=item.get("action_code", ""),
                batches=item.get("independent_batch_count", 0),
                affected=item.get("affected_count", 0),
                markets=item.get("affected_market_count", 0),
                baseline=_format_rate(item.get("baseline_hit_rate")),
                shadow=_format_rate(item.get("shadow_hit_rate")),
                delta=_format_rate(item.get("aggregate_hit_rate_delta")),
                disposition=item.get("disposition", ""),
                next_action=item.get("next_action", ""),
            )
        )
    if not payload.get("candidate_dispositions"):
        lines.append("| - | 0 | 0 | 0 | unknown | unknown | unknown | - | - |")
    lines.extend(["", "## 边界", "", f"- {payload.get('boundary', '')}", ""])
    return "\n".join(lines)


def _append_jsonl(rows, path):
    if not rows:
        return
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    prefix = ""
    if destination.exists() and destination.stat().st_size:
        prefix = "\n" if not destination.read_text(encoding="utf-8-sig").endswith("\n") else ""
    with destination.open("a", encoding="utf-8-sig", newline="") as handle:
        if prefix:
            handle.write(prefix)
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(payload, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8-sig",
    )


def _write_text(content, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8-sig")


def _capture_file_state(path):
    source = Path(path)
    if not source.exists():
        return False, b""
    return True, source.read_bytes()


def _restore_file_state(path, state):
    destination = Path(path)
    existed, content = state
    if existed:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    elif destination.exists():
        destination.unlink()


def write_shadow_disposition_files(
    plan_path,
    validation_path,
    history_path,
    performance_path,
    output_path,
    report_path,
    as_of_date=None,
    lock_timeout_seconds=30.0,
):
    with history_file_lock(history_path, timeout_seconds=lock_timeout_seconds):
        managed_paths = [Path(history_path), Path(output_path), Path(report_path)]
        original_states = [_capture_file_state(path) for path in managed_paths]
        try:
            plan = _read_json(plan_path)
            validation = _read_json(validation_path)
            history_rows = _read_jsonl(history_path)
            performance = _read_json(performance_path)
            payload = build_shadow_disposition(
                plan,
                validation,
                history_rows,
                performance,
                as_of_date=as_of_date,
            )
            pending_rows = history_rows_to_append(
                history_rows,
                validation_history_records(validation),
            )
            if payload.get("history_records_added", 0) > 0:
                _append_jsonl(pending_rows, history_path)
            _write_json(payload, output_path)
            _write_text(render_shadow_disposition(payload), report_path)
            return payload
        except BaseException as error:
            rollback_errors = []
            for path, state in reversed(list(zip(managed_paths, original_states))):
                try:
                    _restore_file_state(path, state)
                except OSError as rollback_error:
                    rollback_errors.append(f"{path}: {rollback_error}")
            if rollback_errors and hasattr(error, "add_note"):
                error.add_note("rollback failures: " + "; ".join(rollback_errors))
            raise


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build one-week forecast shadow candidate dispositions.")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--validation", required=True)
    parser.add_argument("--history", required=True)
    parser.add_argument("--performance", required=True)
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    write_shadow_disposition_files(
        args.plan,
        args.validation,
        args.history,
        args.performance,
        args.output,
        args.report,
        as_of_date=args.as_of_date or None,
    )
    print(f"One-week forecast shadow disposition: {args.report}")


if __name__ == "__main__":
    main()
