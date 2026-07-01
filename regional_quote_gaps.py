import argparse
import csv
import json
from pathlib import Path


GAP_FIELDS = [
    "market",
    "ticker",
    "company_name",
    "issue_type",
    "missing_fields",
    "reason",
    "remediation_type",
    "review_category",
    "review_detail",
    "cache_status",
    "recommended_action",
]

REQUIRED_QUOTE_FIELDS = ["price", "market_cap", "pe", "pb"]


def load_csv_rows(path):
    csv_path = Path(path)
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
        ]


def _to_number(value):
    try:
        return float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None


def _missing_quote_fields(row):
    missing = []
    for field in REQUIRED_QUOTE_FIELDS:
        number = _to_number(row.get(field))
        if number is None or number <= 0:
            missing.append(field)
    return missing


def _missing_field_groups(row):
    missing_values = []
    non_positive_values = []
    for field in REQUIRED_QUOTE_FIELDS:
        value = str(row.get(field) or "").strip()
        number = _to_number(value)
        if number is None:
            missing_values.append(field)
        elif number <= 0:
            non_positive_values.append(field)
    return missing_values, non_positive_values


def _non_positive_review_fields(row, non_positive_values):
    categories = []
    details = []

    if "pe" in non_positive_values:
        categories.append("loss_making_or_negative_pe")
        details.append(f"pe={row.get('pe', '')}")
    if "pb" in non_positive_values:
        categories.append("non_positive_book_value_or_pb")
        details.append(f"pb={row.get('pb', '')}")

    industry = str(
        row.get("industry")
        or row.get("sector")
        or row.get("industry_name")
        or ""
    ).strip()
    company_name = str(row.get("company_name") or row.get("name") or "").strip()
    industry_text = f"{industry} {company_name}".lower()
    special_tokens = ["reit", "real estate", "property", "bank", "insurance", "financial"]
    if any(token in industry_text for token in special_tokens):
        categories.append("special_industry_valuation_review")
        if industry:
            details.append(f"industry={industry}")
        else:
            details.append(f"company_name={company_name}")

    if not categories:
        categories.append("valuation_metric_review")
    return ";".join(categories), ";".join(details)


def read_cache_status(cache_dir):
    metadata_path = Path(cache_dir) / "refresh_metadata.json"
    if not metadata_path.exists():
        return "unknown"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return "unknown"
    return str(metadata.get("status") or "unknown")


def build_quote_gap_rows(companies, snapshot_rows, market, cache_status):
    snapshot_by_ticker = {
        row.get("ticker", "").strip().upper(): row
        for row in snapshot_rows
        if row.get("ticker")
    }
    gaps = []
    for company in companies:
        ticker = company.get("ticker", "").strip().upper()
        if not ticker:
            continue
        snapshot = snapshot_by_ticker.get(ticker)
        company_name = (
            (snapshot or {}).get("company_name")
            or company.get("company_name")
            or company.get("name")
            or ""
        )
        if snapshot is None:
            gaps.append(
                {
                    "market": market or company.get("market", ""),
                    "ticker": ticker,
                    "company_name": company_name,
                    "issue_type": "missing_quote",
                    "missing_fields": "all_quote_fields",
                    "reason": "Eastmoney batch quote 未返回该 ticker",
                    "remediation_type": "refetch_quote",
                    "review_category": "",
                    "review_detail": "",
                    "cache_status": cache_status,
                    "recommended_action": "重新运行 regional_market_snapshot.py；若仍缺失，检查 raw_ticker/secid 映射或临时剔除",
                }
            )
            continue

        missing_values, non_positive_values = _missing_field_groups(snapshot)
        missing_fields = missing_values + non_positive_values
        status = snapshot.get("data_quality_status", "").strip().lower()
        if status != "ready" or missing_fields:
            if missing_values:
                issue_type = "partial_quote"
                reason = "行情字段不完整或未达到 ready 状态"
                remediation_type = "refetch_or_supplement_quote"
                review_category = ""
                review_detail = ""
                recommended_action = "重新运行 regional_market_snapshot.py；必要时补充行情源或人工复核字段口径"
            else:
                issue_type = "non_positive_metric"
                reason = "PE/PB 非正，通常来自亏损、净资产异常或估值字段口径不可用"
                remediation_type = "manual_financial_review"
                review_category, review_detail = _non_positive_review_fields(snapshot, non_positive_values)
                recommended_action = "不要反复重抓行情；进入盈利、净资产和估值口径复核，筛选时保持质量门禁"
            gaps.append(
                {
                    "market": market or company.get("market", ""),
                    "ticker": ticker,
                    "company_name": company_name,
                    "issue_type": issue_type,
                    "missing_fields": ";".join(missing_fields) or "data_quality_status",
                    "reason": reason,
                    "remediation_type": remediation_type,
                    "review_category": review_category,
                    "review_detail": review_detail,
                    "cache_status": cache_status,
                    "recommended_action": recommended_action,
                }
            )
    issue_order = {"partial_quote": 0, "missing_quote": 1, "non_positive_metric": 2}
    return sorted(gaps, key=lambda row: (issue_order.get(row["issue_type"], 9), row["ticker"]))


def write_csv_rows(path, rows):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=GAP_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_markdown_report(path, rows, market, cache_status):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    missing_count = sum(1 for row in rows if row["issue_type"] == "missing_quote")
    partial_count = sum(1 for row in rows if row["issue_type"] == "partial_quote")
    non_positive_count = sum(1 for row in rows if row["issue_type"] == "non_positive_metric")
    lines = [
        "# 区域行情缺口诊断",
        "",
        f"- 市场：{market}",
        f"- 缺口数量：{len(rows)}",
        f"- 完全缺行情：{missing_count}",
        f"- 字段不完整：{partial_count}",
        f"- 非正估值指标：{non_positive_count}",
        f"- 缓存状态：{cache_status}",
        "",
        "| 股票 | 公司 | 缺口类型 | 缺失字段 | 复核分类 | 建议动作 |",
        "|---|---|---|---|---|---|",
    ]
    if rows:
        for row in rows:
            lines.append(
                "| {ticker} | {company} | {issue_type} | {missing_fields} | {review_category} | {action} |".format(
                    ticker=row["ticker"],
                    company=row["company_name"],
                    issue_type=row["issue_type"],
                    missing_fields=row["missing_fields"],
                    review_category=row.get("review_category", ""),
                    action=row["recommended_action"],
                )
            )
    else:
        lines.append("| 无 | 无 | none | none | none | 保持当前抓取流程 |")
    lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8-sig")


def run_regional_quote_gaps(
    companies_path,
    snapshot_path,
    output_path,
    report_path,
    market,
    cache_dir,
):
    cache_status = read_cache_status(cache_dir)
    rows = build_quote_gap_rows(
        load_csv_rows(companies_path),
        load_csv_rows(snapshot_path),
        market=market,
        cache_status=cache_status,
    )
    write_csv_rows(output_path, rows)
    write_markdown_report(report_path, rows, market, cache_status)
    return {
        "issue_count": len(rows),
        "output_path": Path(output_path),
        "report_path": Path(report_path),
        "cache_status": cache_status,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate regional quote gap diagnostics.")
    parser.add_argument("--companies", required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--market", required=True)
    parser.add_argument("--cache-dir", required=True)
    args = parser.parse_args()

    result = run_regional_quote_gaps(
        companies_path=args.companies,
        snapshot_path=args.snapshot,
        output_path=args.output,
        report_path=args.report,
        market=args.market,
        cache_dir=args.cache_dir,
    )
    print(f"Regional quote gaps: {result['issue_count']}")
    print(f"Quote gap CSV: {result['output_path']}")
    print(f"Quote gap report: {result['report_path']}")


if __name__ == "__main__":
    main()
