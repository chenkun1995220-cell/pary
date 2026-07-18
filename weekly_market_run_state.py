import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from atomic_artifact_io import write_json_atomic


RUN_STATE_SCHEMA = "weekly_market_run_state"
RUN_STATE_VERSION = 1
MARKETS = {"US", "CN", "HK"}
STATUSES = {"running", "ready", "failed"}


def _parse_timestamp(value, error_code):
    try:
        return datetime.fromisoformat(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(error_code) from exc


def _append_history(path, payload):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8-sig") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def write_market_run_state(
    output,
    market,
    status,
    run_started_at,
    run_completed_at="",
    summary_path="",
    candidate_path="",
    log_path="",
    failure_step="",
    failure_message="",
    history="",
):
    normalized_market = str(market).strip().upper()
    normalized_status = str(status).strip().lower()
    if normalized_market not in MARKETS:
        raise ValueError("market_invalid")
    if normalized_status not in STATUSES:
        raise ValueError("status_invalid")

    started = _parse_timestamp(run_started_at, "run_started_at_invalid")
    completed_text = str(run_completed_at or "").strip()
    if normalized_status == "ready" and not completed_text:
        raise ValueError("run_completed_at_required")
    if completed_text:
        _parse_timestamp(completed_text, "run_completed_at_invalid")

    failure_text = str(failure_message or "").strip()
    if normalized_status == "failed" and not failure_text:
        raise ValueError("failure_message_required")

    payload = {
        "run_state_schema": RUN_STATE_SCHEMA,
        "run_state_version": RUN_STATE_VERSION,
        "market": normalized_market,
        "status": normalized_status,
        "attempt_id": f"{normalized_market}:{str(run_started_at).strip()}",
        "as_of_date": started.date().isoformat(),
        "run_started_at": str(run_started_at).strip(),
        "run_completed_at": completed_text,
        "summary_path": str(summary_path or ""),
        "candidate_path": str(candidate_path or ""),
        "log_path": str(log_path or ""),
        "failure_step": str(failure_step or ""),
        "failure_message": failure_text,
        "formal_model_change_allowed": False,
    }
    write_json_atomic(output, payload)
    history_path = (
        Path(history)
        if str(history or "").strip()
        else Path(output).with_name("weekly_run_state_history.jsonl")
    )
    _append_history(history_path, payload)
    return payload


def main():
    parser = argparse.ArgumentParser(
        description="Write one market's weekly run state atomically."
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--market", required=True)
    parser.add_argument("--status", required=True)
    parser.add_argument("--run-started-at", required=True)
    parser.add_argument("--run-completed-at", default="")
    parser.add_argument("--summary-path", default="")
    parser.add_argument("--candidate-path", default="")
    parser.add_argument("--log-path", default="")
    parser.add_argument("--failure-step", default="")
    parser.add_argument("--failure-message", default="")
    parser.add_argument("--history", default="")
    args = parser.parse_args()

    payload = write_market_run_state(
        args.output,
        args.market,
        args.status,
        args.run_started_at,
        run_completed_at=args.run_completed_at,
        summary_path=args.summary_path,
        candidate_path=args.candidate_path,
        log_path=args.log_path,
        failure_step=args.failure_step,
        failure_message=args.failure_message,
        history=args.history,
    )
    print(
        f"Market run state: market={payload['market']} "
        f"status={payload['status']} output={args.output}"
    )


if __name__ == "__main__":
    main()
