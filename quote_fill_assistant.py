import argparse
import csv
from pathlib import Path


REQUIRED_FILL_FIELDS = [
    "price",
    "shares_outstanding",
    "currency",
    "quote_date",
    "price_unit",
    "shares_unit",
    "debt_unit",
    "quote_source",
    "updated_at",
]

GAP_FIELDS = [
    "ticker",
    "status",
    "missing_fields",
    "remediation_type",
    "review_category",
    "review_detail",
    "ready_field_count",
    "total_required_field_count",
]
USABLE_STATUSES = {"ready", "manual_override_applied"}


def load_csv_rows(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return [
            {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(f)
        ]


def missing_fields_for_row(row):
    return [field for field in REQUIRED_FILL_FIELDS if not row.get(field, "").strip()]


def status_for_quote_row(row, missing):
    quote_source = row.get("quote_source", "")
    if not missing and "Manual share override" in quote_source:
        return "manual_override_applied"
    if "shares_outstanding" in missing and "share sanity failed" in quote_source:
        return "needs_manual_review"
    if "shares_outstanding" in missing and "SEC official share fact pending" in quote_source:
        return "waiting_official_fact"
    return "ready" if not missing else "needs_fill"


def review_fields_for_quote_row(row, status):
    if status == "waiting_official_fact":
        return {
            "remediation_type": "manual_financial_review",
            "review_category": "official_share_fact_pending",
            "review_detail": "SEC Company Facts and recent filing search completed; monitor for an official share fact.",
        }
    return {"remediation_type": "", "review_category": "", "review_detail": ""}


def find_quote_fill_gaps(quotes_path):
    gaps = []
    for row in load_csv_rows(quotes_path):
        ticker = row.get("ticker", "").strip().upper()
        if not ticker:
            continue
        missing = missing_fields_for_row(row)
        status = status_for_quote_row(row, missing)
        gap = {
            "ticker": ticker,
            "status": status,
            "missing_fields": ", ".join(missing),
            "ready_field_count": len(REQUIRED_FILL_FIELDS) - len(missing),
            "total_required_field_count": len(REQUIRED_FILL_FIELDS),
        }
        gap.update(review_fields_for_quote_row(row, status))
        gaps.append(gap)
    return gaps


def write_gap_csv(path, gaps):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=GAP_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(gaps)


def write_gap_report(path, gaps):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    needs_fill = [gap for gap in gaps if gap.get("status") not in USABLE_STATUSES]
    manual_overrides = [gap for gap in gaps if gap.get("status") == "manual_override_applied"]
    lines = [
        "# 真实行情待补清单",
        "",
        f"- 股票数量：{len(gaps)}",
        f"- 待补股票：{len(needs_fill)}",
        f"- 已应用人工覆盖：{len(manual_overrides)}",
        "",
    ]
    if not needs_fill:
        lines.append("暂无待补字段。")
    else:
        lines.extend(
            [
                "| 股票 | 状态 | 待补字段 |",
                "|---|---|---|",
            ]
        )
        for gap in needs_fill:
            lines.append(
                f"| {gap['ticker']} | {gap['status']} | {gap['missing_fields']} |"
            )
        lines.extend(
            [
                "",
                "补齐后建议重新运行样本包校验，再执行真实样本试跑。",
            ]
        )
    if manual_overrides:
        lines.extend(
            [
                "",
                "## 已应用人工覆盖",
                "",
                "| 股票 | 状态 | 字段 |",
                "|---|---|---|",
            ]
        )
        for gap in manual_overrides:
            lines.append(f"| {gap['ticker']} | {gap['status']} | shares_outstanding |")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def run_quote_fill_check(quotes_path, output_csv, output_report):
    gaps = find_quote_fill_gaps(quotes_path)
    write_gap_csv(output_csv, gaps)
    write_gap_report(output_report, gaps)
    return {
        "rows": len(gaps),
        "needs_fill": sum(1 for gap in gaps if gap.get("status") not in USABLE_STATUSES),
        "output_csv": Path(output_csv),
        "output_report": Path(output_report),
    }


def main():
    parser = argparse.ArgumentParser(description="生成真实行情待补字段清单。")
    parser.add_argument("--quotes", default="data/samples/us_real_sample_quotes.csv")
    parser.add_argument("--output-csv", default="outputs/us_real_sample_quote_gaps.csv")
    parser.add_argument("--output-report", default="outputs/us_real_sample_quote_gaps.md")
    args = parser.parse_args()

    result = run_quote_fill_check(args.quotes, args.output_csv, args.output_report)
    print(f"已检查股票数量：{result['rows']}")
    print(f"待补股票数量：{result['needs_fill']}")
    print(f"CSV 输出：{result['output_csv']}")
    print(f"报告输出：{result['output_report']}")


if __name__ == "__main__":
    main()
