import argparse
from datetime import date
from pathlib import Path


MARKETS = [
    {
        "name": "美股周筛",
        "summary": Path("outputs/automation/latest_run_summary.md"),
        "default_audit": Path("outputs/us_universe/model_audit.md"),
    },
    {
        "name": "A股周筛",
        "summary": Path("outputs/cn_universe/latest_run_summary.md"),
        "default_audit": Path("outputs/cn_universe/model_audit.md"),
    },
    {
        "name": "港股周筛",
        "summary": Path("outputs/hk_universe/latest_run_summary.md"),
        "default_audit": Path("outputs/hk_universe/model_audit.md"),
    },
]


def _read_text(path):
    path = Path(path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig")


def _summary_fields(text):
    fields = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        body = line[2:]
        separator = "：" if "：" in body else ":"
        if separator not in body:
            continue
        key, value = body.split(separator, 1)
        fields[key.strip()] = value.strip()
    return fields


def _resolve_path(project_root, text):
    if not text:
        return None
    path = Path(text)
    if path.is_absolute():
        return path
    return Path(project_root) / path


def _audit_status(path):
    text = _read_text(path)
    fields = _summary_fields(text)
    return fields.get("审计状态") or fields.get("Audit status") or "unknown"


def _market_snapshot(project_root, config):
    path = Path(project_root) / config["summary"]
    text = _read_text(path)
    if not text:
        return {
            "name": config["name"],
            "status": "missing",
            "candidate_count": "unknown",
            "candidate_tickers": "unknown",
            "audit_status": "unknown",
            "summary_path": str(path),
        }
    fields = _summary_fields(text)
    audit_path = _resolve_path(project_root, fields.get("Model audit")) or (Path(project_root) / config["default_audit"])
    return {
        "name": config["name"],
        "status": "ready",
        "candidate_count": fields.get("Candidate count", "unknown"),
        "candidate_tickers": fields.get("Candidate tickers", "unknown"),
        "audit_status": _audit_status(audit_path),
        "summary_path": str(path),
    }


def _backtest_snapshot(project_root):
    path = Path(project_root) / "outputs" / "automation" / "latest_backtest_summary.md"
    text = _read_text(path)
    if not text:
        return {
            "status": "missing",
            "weeks_completed": "unknown",
            "weeks_failed": "unknown",
            "verified": "unknown",
            "weak_rows": "unknown",
            "summary_path": str(path),
        }
    fields = _summary_fields(text)
    return {
        "status": "ready",
        "weeks_completed": fields.get("Weeks completed", "unknown"),
        "weeks_failed": fields.get("Weeks failed", "unknown"),
        "verified": fields.get("Membership evidence verified", "unknown"),
        "weak_rows": fields.get("Weak evidence rows", "unknown"),
        "summary_path": str(path),
    }


def _as_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _risks(markets, backtest):
    risks = []
    missing = [market["name"] for market in markets if market["status"] != "ready"]
    if missing:
        risks.append("缺失摘要：" + "、".join(missing))
    sample_markets = [market["name"] for market in markets if market["audit_status"] == "sample_accumulating"]
    if sample_markets:
        risks.append("模型审计仍在样本积累：" + "、".join(sample_markets))
    if backtest["status"] != "ready":
        risks.append("缺失严格时点回测摘要")
    failed_weeks = _as_int(backtest.get("weeks_failed"))
    if failed_weeks and failed_weeks > 0:
        risks.append(f"严格时点回测失败周数：{failed_weeks}")
    weak_rows = _as_int(backtest.get("weak_rows"))
    if weak_rows and weak_rows > 0:
        risks.append(f"历史成分仍有弱证据行：{weak_rows}")
    return risks or ["未发现新的自动化阻断项"]


def _recommendations(risks, backtest):
    recommendations = []
    if any(risk.startswith("缺失摘要") for risk in risks) or "缺失严格时点回测摘要" in risks:
        recommendations.append("先补齐缺失的周筛或回测摘要，再做模型参数判断。")
    if _as_int(backtest.get("weak_rows")):
        recommendations.append("继续补充历史成分 verified 证据，降低严格时点回测的数据质量风险。")
    if any("样本积累" in risk for risk in risks):
        recommendations.append("继续积累 4/12/26/52 周评价样本，暂不升级正式模型。")
    if not recommendations:
        recommendations.append("保持现有模型，只做人工复核和样本外观察。")
    return recommendations


def _render(as_of_date, markets, backtest):
    risks = _risks(markets, backtest)
    recommendations = _recommendations(risks, backtest)
    lines = [
        f"# 每周自我分析摘要（{as_of_date}）",
        "",
        "## 运行覆盖",
        "",
        "| 模块 | 状态 | 候选数 | 候选代码 | 模型审计 | 摘要 |",
        "|---|---|---:|---|---|---|",
    ]
    for market in markets:
        lines.append(
            f"| {market['name']} | {market['status']} | {market['candidate_count']} | "
            f"{market['candidate_tickers']} | {market['audit_status']} | {market['summary_path']} |"
        )
        lines.append(f"- {market['name']} 候选数：{market['candidate_count']}")
    lines.extend(
        [
            "",
            "## 严格时点回测",
            "",
            f"- 状态：{backtest['status']}",
            f"- 完成周数：{backtest['weeks_completed']}",
            f"- 失败周数：{backtest['weeks_failed']}",
            f"- 成员证据 verified：{backtest['verified']}",
            f"- 弱证据行：{backtest['weak_rows']}",
            f"- 摘要：{backtest['summary_path']}",
            "",
            "## 风险与缺口",
            "",
        ]
    )
    lines.extend(f"- {risk}" for risk in risks)
    lines.extend(["", "## 下周优化建议", ""])
    lines.extend(f"- {item}" for item in recommendations)
    lines.append("")
    return "\n".join(lines)


def run_self_analysis(project_root, output=None, as_of_date=None):
    project_root = Path(project_root)
    as_of_date = as_of_date or date.today().isoformat()
    output = Path(output) if output else project_root / "outputs" / "automation" / "latest_self_analysis.md"
    if not output.is_absolute():
        output = project_root / output
    markets = [_market_snapshot(project_root, config) for config in MARKETS]
    backtest = _backtest_snapshot(project_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_render(as_of_date, markets, backtest), encoding="utf-8-sig")
    return {"output": str(output), "markets": markets, "backtest": backtest}


def main():
    parser = argparse.ArgumentParser(description="Generate weekly automation self-analysis summary.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--output")
    parser.add_argument("--as-of-date")
    args = parser.parse_args()
    result = run_self_analysis(args.project_root, args.output, args.as_of_date)
    print(f"Self-analysis summary: {result['output']}")


if __name__ == "__main__":
    main()
