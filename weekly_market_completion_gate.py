import argparse
import csv
import json
import os
from datetime import date
from pathlib import Path

from atomic_artifact_io import write_json_atomic, write_text_atomic


GATE_SCHEMA = "weekly_market_completion_gate"
GATE_VERSION = 1
RUN_STATE_SCHEMA = "weekly_market_run_state"
RUN_STATE_VERSION = 1
MARKETS = {
    "US": "us_universe",
    "CN": "cn_universe",
    "HK": "hk_universe",
}


def _unique(values):
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None


def _summary_fields(path):
    fields = {}
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return fields
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("- ") or ":" not in stripped:
            continue
        key, value = stripped[2:].split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def _csv_count(path):
    try:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            return sum(1 for _ in csv.DictReader(handle))
    except (OSError, csv.Error):
        return None


def _int_value(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _iso_date(value):
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except (TypeError, ValueError):
        return None


def _same_path(left, right):
    if not left or not right:
        return False
    left_path = os.path.normcase(str(Path(left).resolve(strict=False)))
    right_path = os.path.normcase(str(Path(right).resolve(strict=False)))
    return left_path == right_path


def _market_evidence(root, market, directory, current_date):
    prefix = market.lower()
    market_dir = root / "outputs" / directory
    state_path = market_dir / "latest_run_state.json"
    expected_summary = market_dir / "latest_run_summary.md"
    expected_candidates = market_dir / "candidate_pool.csv"
    issues = []
    state = None

    if not state_path.exists():
        issues.append(f"{prefix}_run_state_missing")
    else:
        state = _read_json(state_path)
        if (
            not isinstance(state, dict)
            or state.get("run_state_schema") != RUN_STATE_SCHEMA
            or state.get("run_state_version") != RUN_STATE_VERSION
        ):
            issues.append(f"{prefix}_run_state_invalid")
            state = None

    status = str((state or {}).get("status", "") or "")
    state_date_text = str((state or {}).get("as_of_date", "") or "")
    state_date = _iso_date(state_date_text)
    if state is not None:
        if state.get("market") != market:
            issues.append(f"{prefix}_run_state_market_mismatch")
        if status != "ready":
            issues.append(f"{prefix}_run_status_{status or 'invalid'}")
        if state_date is None:
            issues.append(f"{prefix}_run_state_date_invalid")
        elif state_date < current_date:
            issues.append(f"{prefix}_run_state_stale")
        elif state_date > current_date:
            issues.append(f"{prefix}_run_state_future")
        if not (
            _same_path(state.get("summary_path"), expected_summary)
            and _same_path(state.get("candidate_path"), expected_candidates)
        ):
            issues.append(f"{prefix}_run_state_path_mismatch")

    fields = {}
    if not expected_summary.exists():
        issues.append(f"{prefix}_summary_missing")
    else:
        fields = _summary_fields(expected_summary)
        summary_date = _iso_date(fields.get("Run time"))
        if summary_date is None:
            issues.append(f"{prefix}_summary_date_invalid")
        elif state_date is not None and summary_date != state_date:
            issues.append(f"{prefix}_summary_date_mismatch")

    candidate_count = None
    if not expected_candidates.exists():
        issues.append(f"{prefix}_candidate_pool_missing")
    else:
        candidate_count = _csv_count(expected_candidates)
        if candidate_count is None:
            issues.append(f"{prefix}_candidate_pool_invalid")

    summary_count = _int_value(fields.get("Candidate count"))
    if fields and summary_count is None:
        issues.append(f"{prefix}_summary_candidate_count_invalid")
    elif candidate_count is not None and summary_count != candidate_count:
        issues.append(f"{prefix}_candidate_count_mismatch")

    issues = _unique(issues)
    return {
        "market": market,
        "status": status,
        "as_of_date": state_date_text,
        "run_started_at": str((state or {}).get("run_started_at", "") or ""),
        "run_completed_at": str((state or {}).get("run_completed_at", "") or ""),
        "summary_candidate_count": summary_count,
        "candidate_file_count": candidate_count,
        "state_file": str(state_path),
        "summary_file": str(expected_summary),
        "candidate_file": str(expected_candidates),
        "issues": issues,
        "ready": status == "ready" and not issues,
    }


def build_weekly_market_completion_gate(project_root=".", as_of_date=None):
    root = Path(project_root).resolve()
    effective_date = _iso_date(as_of_date or date.today().isoformat())
    if effective_date is None:
        raise ValueError("as_of_date_invalid")

    markets = [
        _market_evidence(root, market, directory, effective_date)
        for market, directory in MARKETS.items()
    ]
    issues = [issue for market in markets for issue in market["issues"]]
    market_dates = _unique(
        market["as_of_date"] for market in markets if _iso_date(market["as_of_date"])
    )
    if len(market_dates) > 1:
        issues.append("market_run_date_mismatch")
    issues = _unique(issues)

    return {
        "gate_schema": GATE_SCHEMA,
        "gate_version": GATE_VERSION,
        "as_of_date": effective_date.isoformat(),
        "status": "ready" if not issues else "blocked",
        "market_count": len(markets),
        "ready_market_count": sum(market["ready"] for market in markets),
        "candidate_count_total": sum(
            market["candidate_file_count"] or 0 for market in markets
        ),
        "market_run_dates": market_dates,
        "markets": markets,
        "issues": issues,
        "formal_model_change_allowed": False,
        "boundary": (
            "只读取三市场运行状态、摘要和候选文件；不抓取行情、不重新评分、"
            "不修改正式模型参数。"
        ),
    }


def render_weekly_market_completion_gate(payload):
    lines = [
        "# 三市场周任务完成屏障",
        "",
        f"- 日期：{payload.get('as_of_date', '')}",
        f"- 状态：{payload.get('status', '')}",
        (
            f"- 已就绪市场：{payload.get('ready_market_count', 0)}/"
            f"{payload.get('market_count', 0)}"
        ),
        f"- 候选总数：{payload.get('candidate_count_total', 0)}",
        "- 正式模型修改：不允许",
        "",
        "| 市场 | 状态 | 日期 | 摘要候选数 | 文件候选数 | 问题 |",
        "|---|---|---|---:|---:|---|",
    ]
    for market in payload.get("markets", []):
        lines.append(
            f"| {market.get('market', '')} | {market.get('status', '')} | "
            f"{market.get('as_of_date', '')} | "
            f"{market.get('summary_candidate_count', '')} | "
            f"{market.get('candidate_file_count', '')} | "
            f"{', '.join(market.get('issues', [])) or '-'} |"
        )
    lines.extend(["", "## 问题"])
    if payload.get("issues"):
        lines.extend(f"- {issue}" for issue in payload["issues"])
    else:
        lines.append("- 无")
    lines.extend(["", "## 边界", f"- {payload.get('boundary', '')}", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Block weekly closure until all market runs are complete."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--as-of-date", default=date.today().isoformat())
    parser.add_argument(
        "--output",
        default="outputs/automation/latest_weekly_market_completion_gate.json",
    )
    parser.add_argument(
        "--report",
        default="outputs/automation/latest_weekly_market_completion_gate.md",
    )
    args = parser.parse_args()

    root = Path(args.project_root)
    output = Path(args.output)
    report = Path(args.report)
    if not output.is_absolute():
        output = root / output
    if not report.is_absolute():
        report = root / report

    payload = build_weekly_market_completion_gate(root, args.as_of_date)
    write_json_atomic(output, payload)
    write_text_atomic(report, render_weekly_market_completion_gate(payload))
    print(render_weekly_market_completion_gate(payload))
    raise SystemExit(0 if payload["status"] == "ready" else 1)


if __name__ == "__main__":
    main()
