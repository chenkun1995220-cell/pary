import argparse
import json
import tempfile
from datetime import datetime
from pathlib import Path


RUN_STATE_SCHEMA = "weekly_market_run_state"
RUN_STATE_VERSION = 1
MARKETS = {"US", "CN", "HK"}
STATUSES = {"running", "ready", "failed"}


def _parse_timestamp(value, error_code):
    try:
        return datetime.fromisoformat(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(error_code) from exc


def _atomic_write_json(path, payload):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temporary_path.replace(output)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


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
    _atomic_write_json(output, payload)
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
    )
    print(
        f"Market run state: market={payload['market']} "
        f"status={payload['status']} output={args.output}"
    )


if __name__ == "__main__":
    main()
