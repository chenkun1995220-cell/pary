import argparse
import re
import tomllib
from pathlib import Path


CACHE_FALLBACK_GUARD = "缓存回退不得视为成功"
PRE_SUBMIT_RELAXATION = "-IgnorePreSubmitFailure"
MARKET_FRESH_ARTIFACT_GUARD = "不得把旧产物当作本次结果"
HK_FRESH_ARTIFACT_GUARD = "不得引用旧结论或旧交付产物"
FORMAL_MODEL_GUARD = "正式模型不得自动修改"
RESEARCH_ONLY_GUARD = "结果仅供研究"
ACCEPTANCE_FRESH_ARTIFACT_GUARD = "不得继续引用旧交付"
FAILURE_EVIDENCE_TERMS = ("失败步骤", "本次最新日志")
NETWORK_RETRY_TERMS = ("WinError 10013", "完全相同的入口命令", "重试一次")
ONLINE_FIRST_TERMS = ("首次执行正式入口", "允许网络访问", "CodexSandboxOffline")
POWERSHELL_ENTRYPOINT_TERMS = (
    "powershell.exe",
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
)
VALID_REASONING_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max"}


EXPECTED_AUTOMATIONS = [
    {
        "id": "automation",
        "name": "美股低估公司每周筛选",
        "kind": "cron",
        "hour": 14,
        "minute": 5,
        "required_prompt_terms": [
            "scripts\\run_us_universe_weekly.ps1",
            "不提前运行三市场统一收口",
            "market_quotes.csv",
            CACHE_FALLBACK_GUARD,
            MARKET_FRESH_ARTIFACT_GUARD,
            FORMAL_MODEL_GUARD,
            RESEARCH_ONLY_GUARD,
            *FAILURE_EVIDENCE_TERMS,
            *NETWORK_RETRY_TERMS,
            *ONLINE_FIRST_TERMS,
            *POWERSHELL_ENTRYPOINT_TERMS,
        ],
        "forbidden_prompt_terms": ["-RunPostChecks", PRE_SUBMIT_RELAXATION],
    },
    {
        "id": "a-300-3",
        "name": "A股沪深300每周筛选",
        "kind": "cron",
        "hour": 14,
        "minute": 10,
        "required_prompt_terms": [
            "scripts\\run_cn_weekly.ps1",
            "不提前运行三市场统一收口",
            CACHE_FALLBACK_GUARD,
            MARKET_FRESH_ARTIFACT_GUARD,
            FORMAL_MODEL_GUARD,
            RESEARCH_ONLY_GUARD,
            *FAILURE_EVIDENCE_TERMS,
            *NETWORK_RETRY_TERMS,
            *ONLINE_FIRST_TERMS,
            *POWERSHELL_ENTRYPOINT_TERMS,
        ],
        "forbidden_prompt_terms": ["-RunPostChecks", PRE_SUBMIT_RELAXATION],
    },
    {
        "id": "automation-5",
        "name": "港股大中盘每周筛选",
        "kind": "cron",
        "hour": 14,
        "minute": 30,
        "required_prompt_terms": [
            "scripts\\run_hk_weekly.ps1",
            "-RunPostChecks",
            "scripts\\run_weekly_reporting_bundle.ps1",
            "latest_weekly_artifact_consistency.json",
            "latest_first_one_month_forecast_evaluation_review.json",
            "latest_pre_submit_review.json",
            "同一自然日",
            CACHE_FALLBACK_GUARD,
            HK_FRESH_ARTIFACT_GUARD,
            FORMAL_MODEL_GUARD,
            RESEARCH_ONLY_GUARD,
            *FAILURE_EVIDENCE_TERMS,
            *NETWORK_RETRY_TERMS,
            *ONLINE_FIRST_TERMS,
            *POWERSHELL_ENTRYPOINT_TERMS,
        ],
        "forbidden_prompt_terms": [PRE_SUBMIT_RELAXATION],
    },
    {
        "id": "automation-2",
        "name": "三市场周交付验收跟进",
        "kind": "heartbeat",
        "hour": 15,
        "minute": 0,
        "required_prompt_terms": [
            "latest_weekly_artifact_consistency.json",
            "latest_extended_shadow_validation_tracker.json",
            "latest_pre_submit_review.json",
            "不要重新运行市场抓取",
            "不要修改正式模型",
            ACCEPTANCE_FRESH_ARTIFACT_GUARD,
        ],
        "forbidden_prompt_terms": [],
    },
]


def _automation_path(root, automation_id):
    return Path(root) / automation_id / "automation.toml"


def _load_toml(path):
    return tomllib.loads(Path(path).read_text(encoding="utf-8-sig"))


def _has_nonempty_cli_argument(prompt, argument):
    value_pattern = r'(?:"[^"\r\n]+"|\'[^\'\r\n]+\'|(?![-\'\"])\S+)'
    return re.search(
        rf"(?<!\S){re.escape(argument)}\s+{value_pattern}",
        prompt,
    ) is not None


def _check_automation(root, expected):
    path = _automation_path(root, expected["id"])
    if not path.exists():
        return {
            "id": expected["id"],
            "name": expected["name"],
            "status": "missing",
            "path": str(path),
            "issues": [f"missing automation.toml: {path}"],
        }
    data = _load_toml(path)
    issues = []
    target = {}
    expected_kind = expected["kind"]
    expected_rrule = (
        "FREQ=WEEKLY;INTERVAL=1;BYDAY=SA;"
        f"BYHOUR={expected['hour']};BYMINUTE={expected['minute']}"
    )
    if data.get("kind") != expected_kind:
        issues.append(f"kind expected {expected_kind} got {data.get('kind', '')}")
    if data.get("status") != "ACTIVE":
        issues.append(f"status expected ACTIVE got {data.get('status', '')}")
    if data.get("rrule") != expected_rrule:
        issues.append(f"rrule expected {expected_rrule} got {data.get('rrule', '')}")
    if expected_kind == "cron":
        target = data.get("target")
        if not isinstance(target, dict):
            target = {}
        if target.get("type") != "project":
            issues.append(
                f"target.type expected project got {target.get('type', '')}"
            )
        if not str(target.get("project_id", "")).strip():
            issues.append("target.project_id must be configured")
        if data.get("execution_environment") != "local":
            issues.append(f"execution_environment expected local got {data.get('execution_environment', '')}")
        if not str(data.get("model", "")).strip():
            issues.append("model must be configured")
        if data.get("reasoning_effort") not in VALID_REASONING_EFFORTS:
            issues.append(
                "reasoning_effort must be one of "
                + ", ".join(sorted(VALID_REASONING_EFFORTS))
                + f"; got {data.get('reasoning_effort', '')}"
            )
        if "F:\\chatgptssd\\project2" not in data.get("cwds", []):
            issues.append("cwds missing F:\\chatgptssd\\project2")
    elif not str(data.get("target_thread_id", "")).strip():
        issues.append("target_thread_id must be configured")
    prompt = data.get("prompt", "")
    for term in expected["required_prompt_terms"]:
        if term not in prompt:
            if expected["id"] == "automation-5":
                issues.append(f"weekly_bundle_contract_missing: prompt missing {term}")
            else:
                issues.append(f"prompt missing {term}")
    for term in expected.get("forbidden_prompt_terms", []):
        if term in prompt:
            if term == PRE_SUBMIT_RELAXATION:
                issues.append(f"production prompt must not use {term}")
            else:
                issues.append(f"prompt must not run {term} before the final HK task")
    if expected["id"] == "automation" and not _has_nonempty_cli_argument(
        prompt,
        "-SecUserAgent",
    ):
        issues.append("US prompt must provide a non-empty -SecUserAgent value")
    return {
        "id": expected["id"],
        "name": data.get("name", expected["name"]),
        "kind": data.get("kind", ""),
        "status": "ready" if not issues else "needs_attention",
        "path": str(path),
        "rrule": data.get("rrule", ""),
        "model": data.get("model", ""),
        "reasoning_effort": data.get("reasoning_effort", ""),
        "target_type": target.get("type", ""),
        "target_project_id": target.get("project_id", ""),
        "required_prompt_terms": expected["required_prompt_terms"],
        "issues": issues,
    }


def audit_automations(root):
    checks = [_check_automation(root, expected) for expected in EXPECTED_AUTOMATIONS]
    missing = [check["id"] for check in checks if check["status"] == "missing"]
    ready_count = sum(1 for check in checks if check["status"] == "ready")
    return {
        "status": "ready" if ready_count == len(EXPECTED_AUTOMATIONS) else "needs_attention",
        "automation_count": len(EXPECTED_AUTOMATIONS),
        "ready_count": ready_count,
        "missing_automations": missing,
        "checks": checks,
    }


def render_audit_report(result):
    lines = [
        "# Codex 自动化任务配置审计",
        "",
        f"- 总体状态：{result['status']}",
        f"- 通过数量：{result['ready_count']}/{result['automation_count']}",
    ]
    if result["missing_automations"]:
        lines.append("- 缺失任务：" + ", ".join(result["missing_automations"]))
    lines.extend(["", "## 任务明细"])
    for check in result["checks"]:
        lines.append(f"- {check['id']}：{check['status']}，{check['name']}")
        if check.get("rrule"):
            lines.append(f"  - schedule: {check['rrule']}")
        if check.get("reasoning_effort"):
            lines.append(f"  - reasoning_effort: {check['reasoning_effort']}")
        if check.get("target_type") or check.get("target_project_id"):
            lines.append(
                "  - target: "
                f"{check.get('target_type', '')} / {check.get('target_project_id', '')}"
            )
        for issue in check["issues"]:
            lines.append(f"  - issue: {issue}")
    lines.extend(
        [
            "",
            "## 验收重点",
            "- 美股和 A 股任务只生成各自市场产物，不得提前运行 -RunPostChecks。",
            "- 港股任务必须使用 -RunPostChecks 调用 run_weekly_reporting_bundle.ps1，并读取 latest_weekly_artifact_consistency.json、latest_first_one_month_forecast_evaluation_review.json 和 latest_pre_submit_review.json。",
            "- 三市场周交付验收跟进必须在周六 15:00 运行，读取 latest_extended_shadow_validation_tracker.json 与提交前复核，并保持不重跑市场抓取、不修改正式模型的边界。",
            f"- 验收完成门失败时必须停止，{ACCEPTANCE_FRESH_ARTIFACT_GUARD}、旧提交前复核或旧结论。",
            f"- 三项市场任务必须保留提示词保护：{CACHE_FALLBACK_GUARD}。",
            "- 三项市场任务只能引用本次新产物，不得用旧报告、旧结论或旧交付产物替代本次结果。",
            f"- 三项市场生产任务不得使用提交前复核放宽参数 {PRE_SUBMIT_RELAXATION}。",
            f"- 三项市场任务必须保持正式模型保护：{FORMAL_MODEL_GUARD}。",
            f"- 三项市场任务必须保留研究用途边界：{RESEARCH_ONLY_GUARD}，不构成交易指令。",
            "- 三项市场任务失败时必须报告精确失败步骤和本次最新日志，不得用模糊成功结论替代。",
            "- 三项市场任务遇到 WinError 10013 或网络权限失败时，只允许使用完全相同的入口命令联网重试一次。",
            "- 三项市场任务首次执行正式入口时应直接使用允许网络访问的权限，不得先在 CodexSandboxOffline 离线沙箱运行。",
            "- 三项市场任务必须保留 powershell.exe -NoProfile -ExecutionPolicy Bypass -File 正式入口。",
            "- 美股任务必须为 -SecUserAgent 提供非空值，审计不绑定具体姓名或邮箱。",
            "- 三项市场任务必须配置合法 reasoning_effort；允许按任务选择强度，不绑定单一值。",
            "- 三项市场任务必须绑定 project 类型且提供非空 project_id；审计不绑定具体项目 ID。",
            "- 模型版本允许升级或切换，但必须配置有效模型，并重新通过相同质量门；开发治理不绑定具体模型名称。",
        ]
    )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Audit the Codex weekly market and acceptance automations.")
    parser.add_argument("--automation-root", default=str(Path.home() / ".codex" / "automations"))
    args = parser.parse_args()
    result = audit_automations(args.automation_root)
    print(render_audit_report(result), end="")
    if result["status"] != "ready":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
