import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path


MARKETS = (
    {"market": "US", "label": "美股", "dir": "us_universe"},
    {"market": "CN", "label": "A股", "dir": "cn_universe"},
    {"market": "HK", "label": "港股", "dir": "hk_universe"},
)

REQUIRED_MARKET_FILES = (
    "latest_run_summary.md",
    "candidate_pool.csv",
    "valuation_targets.csv",
    "valuation_report.md",
    "latest_investment_summary.md",
)

AUTOMATION_FILES = {
    "automation_check": "latest_automation_check.json",
    "weekly_ops_check": "latest_weekly_ops_check.json",
    "weekly_ops_history": "latest_weekly_ops_history_summary.json",
}

DEFAULT_MARKDOWN_OUTPUT = "outputs/automation/latest_weekly_conclusion.md"
DEFAULT_JSON_OUTPUT = "outputs/automation/latest_weekly_conclusion.json"


def build_weekly_conclusion(project_root, today=None, max_age_days=8):
    project_root = Path(project_root)
    as_of_date = today or date.today().isoformat()
    missing_inputs = []
    warnings = []
    markets = []
    candidates = []

    automation = read_automation_state(project_root, as_of_date, max_age_days, warnings, missing_inputs)
    for market_config in MARKETS:
        market_result = read_market(project_root, market_config, missing_inputs, warnings)
        markets.append(market_result["summary"])
        candidates.extend(market_result["candidates"])

    status = decide_status(markets, candidates, automation, missing_inputs, warnings)
    return build_payload(as_of_date, status, automation, markets, candidates, missing_inputs, warnings)


def read_automation_state(project_root, as_of_date, max_age_days, warnings, missing_inputs):
    automation_dir = project_root / "outputs" / "automation"
    state = {}
    for key, filename in AUTOMATION_FILES.items():
        path = automation_dir / filename
        payload = read_json(path)
        if payload is None:
            missing_inputs.append(relative_path(project_root, path))
            state[key] = {"status": "missing", "path": relative_path(project_root, path)}
            continue
        state[key] = {
            "status": payload.get("status") or payload.get("latest_status") or "unknown",
            "as_of_date": payload.get("as_of_date") or payload.get("latest_as_of_date"),
            "path": relative_path(project_root, path),
        }

    check = state.get("automation_check", {})
    check_date = parse_iso_date(check.get("as_of_date"))
    current_date = parse_iso_date(as_of_date)
    if check_date and current_date:
        if check_date > current_date:
            warnings.append("latest_automation_check.json is later than today")
        elif (current_date - check_date).days > max_age_days:
            warnings.append(f"latest_automation_check.json is older than {max_age_days} days")
    elif check.get("status") != "missing":
        warnings.append("latest_automation_check.json has invalid as_of_date")
    return state


def read_market(project_root, market_config, missing_inputs, warnings):
    market_dir = project_root / "outputs" / market_config["dir"]
    required_missing = []
    source_files = []
    for filename in REQUIRED_MARKET_FILES:
        resolved = resolve_required_market_file(project_root, market_config, market_dir, filename)
        source_files.append(relative_path(project_root, resolved["path"]))
        if not resolved["exists"]:
            missing = relative_path(project_root, resolved["path"])
            missing_inputs.append(missing)
            required_missing.append(missing)

    candidate_rows = read_csv_rows(market_dir / "candidate_pool.csv")
    target_rows = index_by_ticker(read_csv_rows(market_dir / "valuation_targets.csv"))
    risk_by_ticker = extract_risks(market_dir / "latest_investment_summary.md")

    candidates = []
    for row in candidate_rows:
        ticker = pick(row, "ticker", "symbol", "code", "股票代码", "证券代码")
        if not ticker:
            warnings.append(f"{market_config['market']} candidate row missing ticker")
            continue
        target = target_rows.get(ticker, {})
        candidates.append(
            {
                "market": market_config["market"],
                "market_label": market_config["label"],
                "ticker": ticker,
                "company": pick(row, "company", "company_name", "name", "股票名称", "证券简称"),
                "score": pick(row, "total_score", "score", "评分"),
                "target_price": pick(target, "target_price", "target", "目标价"),
                "buy_price": pick(target, "buy_price", "suggested_buy_price", "建议买入价"),
                "expected_return": pick(target, "expected_return", "expected_return_pct", "预期收益率"),
                "trend_label": pick(target, "trend_label", "trend", "趋势分类"),
                "trend_confidence": pick(target, "trend_confidence", "趋势置信度"),
                "valuation_confidence": pick(target, "valuation_confidence", "估值置信度"),
                "reason": pick(target, "reason", "valuation_reason", "候选理由"),
                "risk_reason": risk_by_ticker.get(ticker) or risk_by_ticker.get("*", ""),
                "source_paths": {
                    "candidate_pool": relative_path(project_root, market_dir / "candidate_pool.csv"),
                    "valuation_targets": relative_path(project_root, market_dir / "valuation_targets.csv"),
                    "investment_summary": relative_path(project_root, market_dir / "latest_investment_summary.md"),
                },
            }
        )

    status = "ready" if not required_missing else "missing"
    summary = {
        "market": market_config["market"],
        "label": market_config["label"],
        "status": status,
        "candidate_count": len(candidates),
        "missing_inputs": required_missing,
        "source_dir": relative_path(project_root, market_dir),
        "source_files": source_files,
    }
    return {"summary": summary, "candidates": candidates}


def resolve_required_market_file(project_root, market_config, market_dir, filename):
    default_path = market_dir / filename
    if default_path.exists():
        return {"path": default_path, "exists": True}
    if market_config["market"] == "US" and filename == "latest_run_summary.md":
        fallback = project_root / "outputs" / "automation" / "latest_run_summary.md"
        if fallback.exists():
            return {"path": fallback, "exists": True}
    return {"path": default_path, "exists": False}


def decide_status(markets, candidates, automation, missing_inputs, warnings):
    if not candidates and automation.get("automation_check", {}).get("status") == "missing":
        return "missing"
    automation_bad = any(
        not is_acceptable_status(entry.get("status"))
        for entry in automation.values()
    )
    market_bad = any(market.get("status") != "ready" for market in markets)
    candidate_bad = any(not candidate.get("ticker") for candidate in candidates)
    if missing_inputs or warnings or automation_bad or market_bad or candidate_bad:
        return "needs_attention"
    return "ready"


def build_payload(as_of_date, status, automation, markets, candidates, missing_inputs, warnings):
    recommended_action = "monitor_next_run" if status == "ready" else "review_inputs"
    return {
        "conclusion_schema": "weekly_conclusion",
        "conclusion_version": 1,
        "as_of_date": as_of_date,
        "status": status,
        "recommended_action": recommended_action,
        "automation": automation,
        "markets": markets,
        "candidate_count_total": len(candidates),
        "candidates": candidates,
        "missing_inputs": sorted(set(missing_inputs)),
        "warnings": sorted(set(warnings)),
        "outputs": {
            "markdown": DEFAULT_MARKDOWN_OUTPUT,
            "json": DEFAULT_JSON_OUTPUT,
        },
    }


def render_markdown(payload, per_market_limit=10):
    lines = ["# 每周低估候选统一结论", ""]
    lines.extend(render_automation_section(payload))
    lines.extend(render_market_section(payload))
    lines.extend(render_candidate_section(payload, per_market_limit=per_market_limit))
    lines.extend(render_risk_section(payload))
    lines.extend(render_output_section(payload))
    lines.extend(render_boundary_section())
    return "\n".join(lines).rstrip() + "\n"


def render_automation_section(payload):
    automation = payload["automation"]
    lines = [
        "## 自动化状态",
        "",
        f"- 本周日期：{payload['as_of_date']}",
        f"- 结论状态：{payload['status']}",
        f"- 优先动作：{payload['recommended_action']}",
    ]
    for key in ("automation_check", "weekly_ops_check", "weekly_ops_history"):
        entry = automation.get(key, {})
        lines.append(f"- {key}：{entry.get('status', 'missing')} ({entry.get('path', '')})")
    lines.append("")
    return lines


def render_market_section(payload):
    lines = ["## 三市场候选概览", "", "| 市场 | 状态 | 候选数 | 来源 |", "|---|---:|---:|---|"]
    for market in payload["markets"]:
        lines.append(
            f"| {market['market']} | {market['status']} | {market['candidate_count']} | {escape_cell(market['source_dir'])} |"
        )
    lines.append("")
    return lines


def render_candidate_section(payload, per_market_limit=10):
    lines = [
        "## 候选公司摘要",
        "",
        "| 市场 | 股票 | 公司 | 评分 | 目标价 | 建议买入价 | 预期收益率 | 趋势 | 置信度 | 风险理由 |",
        "|---|---|---|---:|---:|---:|---:|---|---|---|",
    ]
    for market in ("US", "CN", "HK"):
        market_candidates = [candidate for candidate in payload["candidates"] if candidate["market"] == market]
        for candidate in market_candidates[:per_market_limit]:
            confidence = " / ".join(
                value for value in (candidate.get("trend_confidence"), candidate.get("valuation_confidence")) if value
            )
            lines.append(
                "| {market} | {ticker} | {company} | {score} | {target_price} | {buy_price} | "
                "{expected_return} | {trend_label} | {confidence} | {risk_reason} |".format(
                    market=candidate["market"],
                    ticker=escape_cell(candidate.get("ticker")),
                    company=escape_cell(candidate.get("company")),
                    score=escape_cell(candidate.get("score")),
                    target_price=escape_cell(candidate.get("target_price")),
                    buy_price=escape_cell(candidate.get("buy_price")),
                    expected_return=escape_cell(candidate.get("expected_return")),
                    trend_label=escape_cell(candidate.get("trend_label")),
                    confidence=escape_cell(confidence),
                    risk_reason=escape_cell(candidate.get("risk_reason")),
                )
            )
    if not payload["candidates"]:
        lines.append("| - | - | - | - | - | - | - | - | - | 无可读候选 |")
    lines.append("")
    return lines


def render_risk_section(payload):
    lines = ["## 风险与人工复核", ""]
    if payload["missing_inputs"]:
        lines.append("- 缺失输入：" + "；".join(payload["missing_inputs"]))
    if payload["warnings"]:
        lines.append("- 警告：" + "；".join(payload["warnings"]))
    missing_risks = [
        f"{candidate['market']} {candidate['ticker']}"
        for candidate in payload["candidates"]
        if not candidate.get("risk_reason")
    ]
    if missing_risks:
        lines.append("- 风险理由缺口：" + "；".join(missing_risks[:20]))
    if not payload["missing_inputs"] and not payload["warnings"] and not missing_risks:
        lines.append("- 暂未发现需要优先人工复核的输入缺口。")
    lines.append("")
    return lines


def render_output_section(payload):
    outputs = payload["outputs"]
    return [
        "## 输出路径",
        "",
        f"- Markdown：{outputs['markdown']}",
        f"- JSON：{outputs['json']}",
        "",
    ]


def render_boundary_section():
    return [
        "## 边界",
        "",
        "- 本报告只汇总当前文件系统中已经生成的结果，不重新抓取行情，不重新评分，不修改正式模型参数。",
        "- 内容用于研究筛选和人工复核用途，不构成投资建议。",
        "",
    ]


def write_outputs(payload, markdown, output=None, json_output=None):
    output_path = Path(output or DEFAULT_MARKDOWN_OUTPUT)
    json_path = Path(json_output or DEFAULT_JSON_OUTPUT)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8-sig")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return {"markdown": str(output_path), "json": str(json_path)}


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def read_csv_rows(path):
    try:
        with Path(path).open("r", newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    except FileNotFoundError:
        return []


def index_by_ticker(rows):
    result = {}
    for row in rows:
        ticker = pick(row, "ticker", "symbol", "code", "股票代码", "证券代码")
        if ticker:
            result[ticker] = row
    return result


def extract_risks(path):
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return {}
    risks = {}
    current_ticker = "*"
    for line in text.splitlines():
        heading = re.match(r"^#+\s+(.+?)\s*$", line)
        if heading:
            current_ticker = heading.group(1).split()[0]
        risk = re.search(r"风险[：:]\s*(.+)", line)
        if risk:
            risks[current_ticker] = risk.group(1).strip()
            risks.setdefault("*", risk.group(1).strip())
        table_risk = parse_risk_table_row(line)
        if table_risk:
            risks[table_risk["ticker"]] = table_risk["risk_reason"]
    return risks


def parse_risk_table_row(line):
    if not line.lstrip().startswith("|"):
        return None
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    if len(cells) < 3:
        return None
    ticker, _company, risk_reason = cells[:3]
    if ticker in {"股票", "---", ""} or set(ticker) <= {"-"}:
        return None
    if risk_reason in {"风险说明", "---", ""} or set(risk_reason) <= {"-"}:
        return None
    return {"ticker": ticker, "risk_reason": risk_reason}


def pick(row, *names):
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return str(value)
    return ""


def is_acceptable_status(status):
    normalized = str(status or "").strip().lower()
    return normalized in {"ready", "ok", "success", "completed", "fresh"}


def parse_iso_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def relative_path(project_root, path):
    try:
        return Path(path).relative_to(project_root).as_posix()
    except ValueError:
        return Path(path).as_posix()


def escape_cell(value):
    return str(value or "").replace("|", "\\|")


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--today", default=None)
    parser.add_argument("--max-age-days", type=int, default=8)
    parser.add_argument("--output", default=None)
    parser.add_argument("--json-output", default=None)
    args = parser.parse_args(argv)

    project_root = Path(args.project_root)
    payload = build_weekly_conclusion(project_root, today=args.today, max_age_days=args.max_age_days)
    markdown = render_markdown(payload)
    default_output = project_root / DEFAULT_MARKDOWN_OUTPUT
    default_json_output = project_root / DEFAULT_JSON_OUTPUT
    write_outputs(
        payload,
        markdown,
        output=args.output or default_output,
        json_output=args.json_output or default_json_output,
    )
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
