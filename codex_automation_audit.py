import argparse
import tomllib
from pathlib import Path


EXPECTED_AUTOMATIONS = [
    {
        "id": "automation",
        "name": "美股低估公司每周筛选",
        "minute": 5,
        "required_prompt_terms": [
            "scripts\\run_us_universe_weekly.ps1",
            "不提前运行三市场统一收口",
            "market_quotes.csv",
        ],
        "forbidden_prompt_terms": ["-RunPostChecks"],
    },
    {
        "id": "a-300-3",
        "name": "A股沪深300每周筛选",
        "minute": 10,
        "required_prompt_terms": [
            "scripts\\run_cn_weekly.ps1",
            "不提前运行三市场统一收口",
        ],
        "forbidden_prompt_terms": ["-RunPostChecks"],
    },
    {
        "id": "automation-5",
        "name": "港股大中盘每周筛选",
        "minute": 30,
        "required_prompt_terms": [
            "scripts\\run_hk_weekly.ps1",
            "-RunPostChecks",
            "scripts\\run_weekly_reporting_bundle.ps1",
            "latest_weekly_artifact_consistency.json",
            "latest_first_one_month_forecast_evaluation_review.json",
            "latest_pre_submit_review.json",
            "同一自然日",
        ],
        "forbidden_prompt_terms": [],
    },
]


def _automation_path(root, automation_id):
    return Path(root) / automation_id / "automation.toml"


def _load_toml(path):
    return tomllib.loads(Path(path).read_text(encoding="utf-8-sig"))


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
    expected_rrule = f"FREQ=WEEKLY;INTERVAL=1;BYDAY=SU;BYHOUR=14;BYMINUTE={expected['minute']}"
    if data.get("status") != "ACTIVE":
        issues.append(f"status expected ACTIVE got {data.get('status', '')}")
    if data.get("rrule") != expected_rrule:
        issues.append(f"rrule expected {expected_rrule} got {data.get('rrule', '')}")
    if data.get("execution_environment") != "local":
        issues.append(f"execution_environment expected local got {data.get('execution_environment', '')}")
    if not str(data.get("model", "")).strip():
        issues.append("model must be configured")
    if "F:\\chatgptssd\\project2" not in data.get("cwds", []):
        issues.append("cwds missing F:\\chatgptssd\\project2")
    prompt = data.get("prompt", "")
    for term in expected["required_prompt_terms"]:
        if term not in prompt:
            if expected["id"] == "automation-5":
                issues.append(f"weekly_bundle_contract_missing: prompt missing {term}")
            else:
                issues.append(f"prompt missing {term}")
    for term in expected.get("forbidden_prompt_terms", []):
        if term in prompt:
            issues.append(f"prompt must not run {term} before the final HK task")
    return {
        "id": expected["id"],
        "name": data.get("name", expected["name"]),
        "status": "ready" if not issues else "needs_attention",
        "path": str(path),
        "rrule": data.get("rrule", ""),
        "model": data.get("model", ""),
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
        for issue in check["issues"]:
            lines.append(f"  - issue: {issue}")
    lines.extend(
        [
            "",
            "## 验收重点",
            "- 美股和 A 股任务只生成各自市场产物，不得提前运行 -RunPostChecks。",
            "- 港股任务必须使用 -RunPostChecks 调用 run_weekly_reporting_bundle.ps1，并读取 latest_weekly_artifact_consistency.json、latest_first_one_month_forecast_evaluation_review.json 和 latest_pre_submit_review.json。",
            "- 模型版本允许升级或切换，但必须配置有效模型，并重新通过相同质量门；开发治理不绑定具体模型名称。",
        ]
    )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Audit the three Codex weekly stock automations.")
    parser.add_argument("--automation-root", default=str(Path.home() / ".codex" / "automations"))
    args = parser.parse_args()
    result = audit_automations(args.automation_root)
    print(render_audit_report(result), end="")
    if result["status"] != "ready":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
