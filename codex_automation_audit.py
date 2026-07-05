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
            "latest_automation_check.json",
            "不要运行或引用",
        ],
    },
    {
        "id": "a-300-2",
        "name": "A股沪深300每周筛选",
        "minute": 10,
        "required_prompt_terms": [
            "scripts\\run_cn_weekly.ps1",
            "latest_automation_check.json",
            "不要运行或引用",
        ],
    },
    {
        "id": "automation-4",
        "name": "港股大中盘每周筛选",
        "minute": 15,
        "required_prompt_terms": [
            "scripts\\run_hk_weekly.ps1",
            "scripts\\run_self_analysis.ps1",
            "scripts\\show_automation_check.ps1",
            "scripts\\run_weekly_ops_check.ps1",
            "scripts\\show_weekly_ops_history.ps1",
            "scripts\\show_weekly_conclusion.ps1",
            "scripts\\run_weekly_delivery_check.ps1",
            "scripts\\show_weekly_delivery_history.ps1",
            "scripts\\run_pre_submit_review.ps1",
        ],
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
    if "F:\\chatgptssd\\project2" not in data.get("cwds", []):
        issues.append("cwds missing F:\\chatgptssd\\project2")
    prompt = data.get("prompt", "")
    for term in expected["required_prompt_terms"]:
        if term not in prompt:
            if term == "scripts\\show_weekly_conclusion.ps1":
                issues.append(f"weekly_conclusion_report_missing: prompt missing {term}")
            else:
                issues.append(f"prompt missing {term}")
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
            "- 美股和 A 股任务不得提前引用旧 latest_automation_check.json。",
            "- 港股任务必须在三市场完成后运行 run_self_analysis.ps1、show_automation_check.ps1、run_weekly_ops_check.ps1、show_weekly_ops_history.ps1、show_weekly_conclusion.ps1、run_weekly_delivery_check.ps1、show_weekly_delivery_history.ps1 和 run_pre_submit_review.ps1。",
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
