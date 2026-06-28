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
MANUAL_REVIEW_QUEUE_PATH = "outputs/automation/latest_manual_review_queue.csv"

ACTION_DETAILS = {
    "review_manual_queue": {
        "label": "复核人工队列",
        "description": "查看本周人工复核队列，优先处理估值口径、风险提示和候选结论缺口。",
    },
    "review_data_health": {
        "label": "复核数据健康",
        "description": "检查行情、财务字段、数据质量问题和人工覆盖项是否影响候选可信度。",
    },
    "review_backtest_evidence": {
        "label": "复核回测证据",
        "description": "确认严格时点回测证据等级、弱证据周次和泄漏审计结果。",
    },
    "review_candidate_findings": {
        "label": "复核候选结论",
        "description": "检查候选公司的风险说明、建议买入价、目标价和跟踪状态是否完整。",
    },
    "continue_sample_accumulation": {
        "label": "继续积累样本",
        "description": "维持正式模型不变，等待更多成熟跟踪样本后再评估参数优化。",
    },
    "monitor_next_run": {
        "label": "继续观察下次运行",
        "description": "当前未发现优先处理项，下次自动运行后继续复核输出。",
    },
    "review_inputs": {
        "label": "复核输入文件",
        "description": "先处理缺失、过期或字段异常的输入文件，再使用本周结论。",
    },
}


def build_weekly_conclusion(project_root, today=None, max_age_days=8):
    project_root = Path(project_root)
    as_of_date = today or date.today().isoformat()
    missing_inputs = []
    warnings = []
    markets = []
    candidates = []

    automation = read_automation_state(project_root, as_of_date, max_age_days, warnings, missing_inputs)
    manual_review_queue = read_manual_review_queue(project_root)
    for market_config in MARKETS:
        market_result = read_market(project_root, market_config, missing_inputs, warnings)
        markets.append(market_result["summary"])
        candidates.extend(market_result["candidates"])

    status = decide_status(markets, candidates, automation, missing_inputs, warnings)
    return build_payload(as_of_date, status, automation, markets, candidates, missing_inputs, warnings, manual_review_queue)


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
            "recommended_action": payload.get("recommended_action"),
            "priority_actions": payload.get("priority_actions", []),
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


def build_payload(as_of_date, status, automation, markets, candidates, missing_inputs, warnings, manual_review_queue):
    recommended_action = choose_recommended_action(status, automation)
    priority_actions = choose_priority_actions(status, automation, recommended_action)
    priority_action_details = describe_priority_actions(priority_actions)
    return {
        "conclusion_schema": "weekly_conclusion",
        "conclusion_version": 1,
        "as_of_date": as_of_date,
        "status": status,
        "recommended_action": recommended_action,
        "priority_actions": priority_actions,
        "priority_action_details": priority_action_details,
        "automation": automation,
        "markets": markets,
        "manual_review_queue": manual_review_queue,
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
    lines.extend(render_priority_actions_section(payload))
    lines.extend(render_market_section(payload))
    lines.extend(render_candidate_section(payload, per_market_limit=per_market_limit))
    lines.extend(render_manual_review_queue_section(payload))
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


def render_priority_actions_section(payload):
    lines = ["## 优先动作", ""]
    details = payload.get("priority_action_details") or describe_priority_actions(payload.get("priority_actions") or [])
    lines.extend(["| 动作码 | 中文动作 | 说明 |", "|---|---|---|"])
    for item in details:
        lines.append(
            "| {action} | {label} | {description} |".format(
                action=escape_cell(item.get("action")),
                label=escape_cell(item.get("label")),
                description=escape_cell(item.get("description")),
            )
        )
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


def render_manual_review_queue_section(payload):
    queue = payload.get("manual_review_queue", {})
    lines = ["## 人工复核队列", ""]
    if not queue.get("items"):
        lines.append("- 当前没有人工复核队列记录。")
        lines.append("")
        return lines

    lines.extend(
        [
            f"- 队列数量：{queue.get('count', 0)}",
            f"- 来源：{queue.get('path', '')}",
            f"- 按市场：{format_queue_counts(queue.get('by_market', []), 'market')}",
            f"- 按类型：{format_queue_counts(queue.get('by_review_type', []), 'review_type')}",
            "",
            "| 序号 | 市场 | 类型 | 股票 | 公司 | 复核要点 |",
            "|---:|---|---|---|---|---|",
        ]
    )
    for item in queue["items"]:
        lines.append(
            "| {rank} | {market} | {review_type} | {ticker} | {company} | {review_detail} |".format(
                rank=escape_cell(item.get("rank")),
                market=escape_cell(item.get("market")),
                review_type=escape_cell(item.get("review_type")),
                ticker=escape_cell(item.get("ticker")),
                company=escape_cell(item.get("company")),
                review_detail=escape_cell(item.get("review_detail")),
            )
        )
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


def read_manual_review_queue(project_root, item_limit=10):
    path = project_root / MANUAL_REVIEW_QUEUE_PATH
    rows = read_csv_rows(path)
    items = []
    for row in rows[:item_limit]:
        items.append(
            {
                "rank": pick(row, "rank", "priority", "优先级序号"),
                "market": pick(row, "market", "市场"),
                "review_type": pick(row, "review_type", "复核类型"),
                "ticker": pick(row, "ticker", "股票"),
                "company": pick(row, "company", "公司"),
                "review_detail": pick(row, "review_detail", "复核要点"),
            }
        )
    return {
        "path": relative_path(project_root, path),
        "count": len(rows),
        "by_market": count_queue_rows(rows, "market", "market"),
        "by_review_type": count_queue_rows(rows, "review_type", "review_type"),
        "items": items,
    }


def count_queue_rows(rows, source_key, output_key):
    counts = {}
    for row in rows:
        value = pick(row, source_key)
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return [{output_key: key, "count": count} for key, count in counts.items()]


def format_queue_counts(items, label_key):
    if not items:
        return "无"
    return "；".join(f"{item.get(label_key, '')} {item.get('count', 0)}" for item in items)


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
    return normalized in {"ready", "ok", "success", "completed", "fresh", "manual_review_needed"}


def choose_recommended_action(status, automation):
    if status != "ready":
        return "review_inputs"
    automation_action = automation.get("automation_check", {}).get("recommended_action")
    return automation_action or "monitor_next_run"


def choose_priority_actions(status, automation, recommended_action):
    if status != "ready":
        return [recommended_action]
    actions = automation.get("automation_check", {}).get("priority_actions") or []
    if actions:
        return actions
    return [recommended_action]


def describe_priority_actions(actions):
    details = []
    for action in actions or ["monitor_next_run"]:
        template = ACTION_DETAILS.get(
            action,
            {
                "label": "未分类动作",
                "description": "保留原始动作码，等待后续补充中文说明。",
            },
        )
        details.append(
            {
                "action": action,
                "label": template["label"],
                "description": template["description"],
            }
        )
    return details


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
