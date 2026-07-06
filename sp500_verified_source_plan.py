import argparse
import json
import sys
from datetime import date
from pathlib import Path

from sp500_current_membership_sources import OFFICIAL_EXPORT_URL, SOURCE_FILE_INBOX
from sp500_membership_source_policy import classify_membership_source


REVIEW_SCHEMA = "sp500_verified_source_plan"
REVIEW_VERSION = 1
OFFICIAL_INDEX_PAGE = "https://www.spglobal.com/spdji/en/indices/equity/sp-500/"
ISHARES_IVV_PAGE = "https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf"
SSGA_SPY_PAGE = "https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy"
VANGUARD_VOO_PAGE = "https://investor.vanguard.com/investment-products/etfs/profile/voo"
DEFAULT_OFFICIAL_EXPORT_PROBE = "outputs/automation/latest_sp500_official_export_probe.json"


def _read_json(path):
    source = Path(path)
    if not source.exists():
        return {}
    return json.loads(source.read_text(encoding="utf-8-sig"))


def _int_value(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float_value(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _source_item(source_id, name, url, evidence_kind, intended_use, required_artifact, acceptance):
    policy = classify_membership_source(url, evidence_kind=evidence_kind)
    return {
        "source_id": source_id,
        "name": name,
        "url": url,
        "evidence_kind": evidence_kind,
        "intended_use": intended_use,
        "required_artifact": required_artifact,
        "acceptance_criteria": acceptance,
        "trust_level": policy["trust_level"],
        "can_upgrade_membership": policy["can_upgrade_membership"],
        "policy_reason": policy["reason"],
    }


def _source_matrix(official_export_url):
    return [
        _source_item(
            "spglobal_full_constituents_export",
            "S&P Global full constituents export",
            official_export_url or OFFICIAL_EXPORT_URL,
            "current_constituents",
            "verified_current_membership_import",
            SOURCE_FILE_INBOX,
            [
                "official_spglobal_https_source",
                "contains_symbol_or_ticker_column",
                "parsed_ticker_count_at_least_400",
            ],
        ),
        _source_item(
            "spglobal_index_announcements",
            "S&P DJI index announcements",
            OFFICIAL_INDEX_PAGE,
            "index_announcement",
            "verified_change_evidence",
            "official announcement PDF or official index page",
            ["official_spglobal_https_source", "announcement_date_and_change_scope_clear"],
        ),
        _source_item(
            "ishares_ivv_holdings",
            "iShares IVV official holdings",
            ISHARES_IVV_PAGE,
            "etf_holdings",
            "cross_check_only",
            "official holdings download",
            ["issuer_official_holdings", "ticker_and_weight_available", "do_not_upgrade_membership"],
        ),
        _source_item(
            "ssga_spy_holdings",
            "State Street SPY official holdings",
            SSGA_SPY_PAGE,
            "etf_holdings",
            "cross_check_only",
            "official holdings download",
            ["issuer_official_holdings", "ticker_and_weight_available", "do_not_upgrade_membership"],
        ),
        _source_item(
            "vanguard_voo_holdings",
            "Vanguard VOO official holdings",
            VANGUARD_VOO_PAGE,
            "etf_holdings",
            "cross_check_only",
            "official portfolio holdings",
            ["issuer_official_holdings", "ticker_and_weight_available", "do_not_upgrade_membership"],
        ),
    ]


def _probe_reason(official_probe):
    status = str(official_probe.get("status", "") or "").strip()
    if not status:
        return ""
    parts = [f"official_export_probe_status={status}"]
    http_status = official_probe.get("http_status")
    if http_status:
        parts.append(f"http_status={http_status}")
    next_action = str(official_probe.get("next_action", "") or "").strip()
    if next_action:
        parts.append(f"probe_next_action={next_action}")
    return "; ".join(parts)


def _next_actions(
    ready_to_import_count,
    verified_candidate_count,
    source_file_inbox,
    crosscheck_active=False,
    official_probe=None,
):
    if ready_to_import_count > 0:
        return [
            {
                "action": "run_membership_evidence_apply_preview",
                "reason": "verified_current_sources_ready",
                "command": "powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_membership_evidence_apply_preview.ps1 -ProjectRoot <project_root>",
            }
        ]
    if crosscheck_active:
        actions = [
            {
                "action": "refresh_crosscheck_substitute_weekly",
                "reason": "official_full_file_abandoned_for_weekly_current_screening",
                "command": "build latest outputs\\sp500_crosscheck_*\\sp500_full_constituents_crosscheck_*.xlsx from approved crosscheck inputs",
            },
            {
                "action": "rerun_us_weekly_screening_with_crosscheck_substitute",
                "reason": "crosscheck_substitute_ready_for_current_weekly_screening",
                "command": "powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root>",
            },
            {
                "action": "keep_formal_backtest_upgrade_blocked",
                "reason": "crosscheck_substitute_is_not_official_index_membership_evidence",
            },
        ]
        if verified_candidate_count > 0:
            actions.insert(
                0,
                {
                    "action": "review_verified_candidates_blocked_by_policy",
                    "reason": "verified_candidates_present_but_not_ready_to_import",
                },
            )
        return actions
    probe_reason = _probe_reason(official_probe or {})
    source_reason = "no_verified_current_membership_sources_ready"
    if probe_reason:
        source_reason = f"{source_reason}; {probe_reason}"
    actions = [
        {
            "action": "obtain_official_spglobal_full_constituents_file",
            "reason": source_reason,
            "target_file": source_file_inbox or SOURCE_FILE_INBOX,
        },
        {
            "action": "validate_official_source_file_dry_run",
            "reason": "prevent_top10_or_partial_file_import",
            "command": "powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> -DryRun -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv",
        },
        {
            "action": "import_current_membership_sources",
            "reason": "dry_run_passed_with_at_least_400_official_tickers",
            "command": "powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_sp500_current_membership_sources.ps1 -ProjectRoot <project_root> -SourceFileInbox inputs/sp500_current_membership/official_constituents.csv",
        },
        {
            "action": "rerun_membership_evidence_import_plan",
            "reason": "refresh_ready_to_import_count_after_verified_source_import",
            "command": "powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_membership_evidence_import_plan.ps1 -ProjectRoot <project_root>",
        },
        {
            "action": "use_etf_holdings_for_cross_check_only",
            "reason": "etf_holdings_are_not_index_membership_authority",
            "sources": ["ishares_ivv_holdings", "ssga_spy_holdings", "vanguard_voo_holdings"],
        },
    ]
    if verified_candidate_count > 0:
        actions.insert(
            0,
            {
                "action": "review_verified_candidates_blocked_by_policy",
                "reason": "verified_candidates_present_but_not_ready_to_import",
            },
        )
    return actions


def build_sp500_verified_source_plan(
    project_root=".",
    import_plan=None,
    current_sources=None,
    inbox_status=None,
    backtest_review=None,
    official_export_probe=None,
    as_of_date=None,
):
    root = Path(project_root)
    import_plan_path = Path(import_plan) if import_plan else root / "outputs/automation/latest_membership_evidence_import_plan.json"
    current_sources_path = (
        Path(current_sources) if current_sources else root / "outputs/automation/latest_sp500_current_membership_sources.json"
    )
    inbox_status_path = (
        Path(inbox_status)
        if inbox_status
        else root / "outputs/automation/latest_sp500_current_membership_source_inbox_status.json"
    )
    backtest_review_path = (
        Path(backtest_review) if backtest_review else root / "outputs/automation/latest_backtest_evidence_review.json"
    )
    official_probe_path = (
        Path(official_export_probe) if official_export_probe else root / DEFAULT_OFFICIAL_EXPORT_PROBE
    )
    import_payload = _read_json(import_plan_path)
    current_payload = _read_json(current_sources_path)
    inbox_payload = _read_json(inbox_status_path)
    backtest_payload = _read_json(backtest_review_path)
    official_probe_payload = _read_json(official_probe_path)

    ready_to_import = _int_value(import_payload.get("ready_to_import_count"))
    verified_candidates = _int_value(import_payload.get("verified_candidate_count"))
    invalid_sources = _int_value(import_payload.get("invalid_source_count"))
    blocked_by_policy = _int_value(import_payload.get("blocked_by_source_policy_count"))
    source_file_inbox = inbox_payload.get("source_file_inbox") or SOURCE_FILE_INBOX
    official_export_url = current_payload.get("official_export_url") or inbox_payload.get("official_export_url") or OFFICIAL_EXPORT_URL
    verified_ratio = _float_value(backtest_payload.get("verified_membership_ratio"))
    weak_rows = _int_value(backtest_payload.get("weak_evidence_rows"))
    source_matrix = _source_matrix(official_export_url)
    crosscheck_active = current_payload.get("status") == "crosscheck_substitute_ready"
    if ready_to_import > 0:
        status = "ready_for_apply_preview"
    elif crosscheck_active:
        status = "crosscheck_substitute_active"
    else:
        status = "verified_source_required"
    return {
        "review_schema": REVIEW_SCHEMA,
        "review_version": REVIEW_VERSION,
        "as_of_date": as_of_date or date.today().isoformat(),
        "status": status,
        "source_inputs": {
            "import_plan": str(import_plan_path),
            "current_sources": str(current_sources_path),
            "inbox_status": str(inbox_status_path),
            "backtest_review": str(backtest_review_path),
            "official_export_probe": str(official_probe_path),
        },
        "ready_to_import_count": ready_to_import,
        "verified_candidate_count": verified_candidates,
        "invalid_source_count": invalid_sources,
        "blocked_by_source_policy_count": blocked_by_policy,
        "verified_membership_ratio": verified_ratio,
        "weak_evidence_rows": weak_rows,
        "current_source_status": current_payload.get("status", "missing"),
        "current_source_recommended_followup": current_payload.get("recommended_followup", ""),
        "crosscheck_constituents_file": current_payload.get("crosscheck_constituents_file", ""),
        "parsed_crosscheck_ticker_count": _int_value(current_payload.get("parsed_crosscheck_ticker_count")),
        "source_file_inbox_status": inbox_payload.get("status", "missing"),
        "source_file_inbox": source_file_inbox,
        "minimum_official_ticker_count": _int_value(inbox_payload.get("minimum_official_ticker_count"), 400),
        "official_export_url": official_export_url,
        "official_export_probe_status": official_probe_payload.get("status", ""),
        "official_export_probe_http_status": _int_value(official_probe_payload.get("http_status")),
        "official_export_probe_next_action": official_probe_payload.get("next_action", ""),
        "official_export_probe_error": official_probe_payload.get("error", ""),
        "official_full_file_required": not crosscheck_active and ready_to_import == 0,
        "source_matrix": source_matrix,
        "next_actions": _next_actions(
            ready_to_import,
            verified_candidates,
            source_file_inbox,
            crosscheck_active=crosscheck_active,
            official_probe=official_probe_payload,
        ),
        "formal_backtest_upgrade_allowed": False,
        "boundary": "只生成 S&P 500 verified 来源补强计划；不抓取网页，不导入来源，不改写 historical_membership.csv，不升级正式模型。",
    }


def render_sp500_verified_source_plan(payload):
    probe_lines = [
        "",
        "## official_export_probe",
        "",
        f"- official_export_probe_status：{payload.get('official_export_probe_status', '')}",
        f"- official_export_probe_http_status：{payload.get('official_export_probe_http_status', 0)}",
        f"- official_export_probe_next_action：{payload.get('official_export_probe_next_action', '')}",
    ]
    lines = [
        "# S&P 500 verified 来源补强计划",
        "",
        f"- 日期：{payload.get('as_of_date', '')}",
        f"- 状态：{payload.get('status', '')}",
        f"- ready_to_import_count：{payload.get('ready_to_import_count', 0)}",
        f"- verified_candidate_count：{payload.get('verified_candidate_count', 0)}",
        f"- invalid_source_count：{payload.get('invalid_source_count', 0)}",
        f"- blocked_by_source_policy_count：{payload.get('blocked_by_source_policy_count', 0)}",
        f"- verified_membership_ratio：{payload.get('verified_membership_ratio')}",
        f"- weak_evidence_rows：{payload.get('weak_evidence_rows', 0)}",
        f"- official_export_url：{payload.get('official_export_url', '')}",
        "- formal_backtest_upgrade_allowed：false",
        "",
        "## 来源矩阵",
        "",
        "| source_id | trust_level | can_upgrade | intended_use | url |",
        "|---|---|---:|---|---|",
    ]
    for item in payload.get("source_matrix", []):
        lines.append(
            f"| {item.get('source_id', '')} | {item.get('trust_level', '')} | "
            f"{str(item.get('can_upgrade_membership')).lower()} | {item.get('intended_use', '')} | "
            f"{item.get('url', '')} |"
        )
    lines.extend(["", "## 下一步", "", "| action | reason | command / target |", "|---|---|---|"])
    for item in payload.get("next_actions", []):
        command = item.get("command") or item.get("target_file") or ";".join(item.get("sources", []))
        lines.append(f"| {item.get('action', '')} | {item.get('reason', '')} | {command} |")
    lines.extend(["", "## 边界", "", f"- {payload.get('boundary', '')}", ""])
    lines.extend(probe_lines)
    lines.append("")
    return "\n".join(lines)


def write_json(payload, output):
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8-sig",
    )


def write_text(text, output):
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8-sig")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build S&P 500 verified source plan.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--import-plan", default="")
    parser.add_argument("--current-sources", default="")
    parser.add_argument("--inbox-status", default="")
    parser.add_argument("--backtest-review", default="")
    parser.add_argument("--official-export-probe", default="")
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--output", default="outputs/automation/latest_sp500_verified_source_plan.json")
    parser.add_argument("--report", default="outputs/automation/latest_sp500_verified_source_plan.md")
    args = parser.parse_args()

    payload = build_sp500_verified_source_plan(
        project_root=args.project_root,
        import_plan=args.import_plan or None,
        current_sources=args.current_sources or None,
        inbox_status=args.inbox_status or None,
        backtest_review=args.backtest_review or None,
        official_export_probe=args.official_export_probe or None,
        as_of_date=args.as_of_date or None,
    )
    report = render_sp500_verified_source_plan(payload)
    if args.output:
        write_json(payload, args.output)
    if args.report:
        write_text(report, args.report)
    print(report, end="")
    print(f"S&P 500 verified source plan: {args.report}")


if __name__ == "__main__":
    main()
