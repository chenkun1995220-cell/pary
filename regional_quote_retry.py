import argparse
import csv
from pathlib import Path

from regional_market_snapshot import (
    OUTPUT_FIELDS,
    fetch_eastmoney_batch,
    parse_eastmoney_snapshot,
    ticker_to_secid,
)


REFETCH_REMEDIATIONS = {"refetch_quote", "refetch_or_supplement_quote"}
REFETCH_ISSUES = {"missing_quote", "partial_quote"}


def load_csv_rows(path):
    csv_path = Path(path)
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
        ]


def write_snapshot(path, rows):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(OUTPUT_FIELDS)
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _target_tickers(gap_rows):
    targets = []
    for row in gap_rows:
        ticker = row.get("ticker", "").strip().upper()
        if not ticker:
            continue
        remediation = row.get("remediation_type", "").strip().lower()
        issue_type = row.get("issue_type", "").strip().lower()
        if remediation in REFETCH_REMEDIATIONS or (
            not remediation and issue_type in REFETCH_ISSUES
        ):
            targets.append(ticker)
    return sorted(set(targets))


def _row_by_ticker(rows):
    return {row.get("ticker", "").strip().upper(): row for row in rows if row.get("ticker")}


def _is_ready(row):
    return row.get("data_quality_status", "").strip().lower() == "ready"


def _merge_rows(snapshot_rows, retry_rows):
    retry_by_ticker = _row_by_ticker(retry_rows)
    merged = []
    updated = 0
    for row in snapshot_rows:
        ticker = row.get("ticker", "").strip().upper()
        retry = retry_by_ticker.get(ticker)
        if retry and _is_ready(retry):
            merged.append(retry)
            updated += 1
        else:
            merged.append(row)
    snapshot_tickers = set(_row_by_ticker(snapshot_rows))
    for ticker, retry in sorted(retry_by_ticker.items()):
        if ticker not in snapshot_tickers and _is_ready(retry):
            merged.append(retry)
            updated += 1
    return merged, updated


def write_report(path, attempted, updated, results, errors):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 区域行情缺口重抓",
        "",
        f"- 尝试重抓：{attempted}",
        f"- 成功更新：{updated}",
        f"- 失败批次：{len(errors)}",
        "",
        "| 股票 | 状态 | 说明 |",
        "|---|---|---|",
    ]
    if results:
        for item in results:
            lines.append(f"| {item['ticker']} | {item['status']} | {item['message']} |")
    else:
        lines.append("| 无 | skipped | 无可重抓缺口 |")
    for error in errors:
        lines.append(f"| batch | failed | {error} |")
    lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8-sig")


def run_regional_quote_retry(
    companies_path,
    snapshot_path,
    gaps_path,
    output_path,
    report_path,
    fetcher=None,
    batch_size=20,
    quote_date=None,
):
    companies = load_csv_rows(companies_path)
    snapshot_rows = load_csv_rows(snapshot_path)
    gap_rows = load_csv_rows(gaps_path)
    targets = _target_tickers(gap_rows)
    companies_by_ticker = _row_by_ticker(companies)
    retry_companies = [companies_by_ticker[ticker] for ticker in targets if ticker in companies_by_ticker]
    fetch = fetcher or fetch_eastmoney_batch

    retry_rows = []
    errors = []
    for start in range(0, len(retry_companies), batch_size):
        batch = retry_companies[start : start + batch_size]
        try:
            payload = fetch([ticker_to_secid(row["ticker"]) for row in batch])
            parsed, _missing = parse_eastmoney_snapshot(payload, batch, quote_date=quote_date)
            retry_rows.extend(parsed)
        except Exception as exc:  # best-effort retry should not erase the original snapshot
            errors.append(str(exc))

    merged, updated = _merge_rows(snapshot_rows, retry_rows)
    write_snapshot(output_path, merged)

    retry_by_ticker = _row_by_ticker(retry_rows)
    results = []
    for ticker in targets:
        retry = retry_by_ticker.get(ticker)
        if retry and _is_ready(retry):
            results.append({"ticker": ticker, "status": "updated", "message": "重抓后字段达到 ready"})
        elif retry:
            results.append({"ticker": ticker, "status": "partial", "message": "重抓后仍未达到 ready"})
        else:
            results.append({"ticker": ticker, "status": "missing", "message": "重抓未返回可用行情"})
    write_report(report_path, len(targets), updated, results, errors)
    return {
        "attempted": len(targets),
        "updated": updated,
        "errors": len(errors),
        "output_path": Path(output_path),
        "report_path": Path(report_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Retry refetchable regional quote gaps once.")
    parser.add_argument("--companies", required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--gaps", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--batch-size", type=int, default=20)
    args = parser.parse_args()

    result = run_regional_quote_retry(
        companies_path=args.companies,
        snapshot_path=args.snapshot,
        gaps_path=args.gaps,
        output_path=args.output,
        report_path=args.report,
        batch_size=args.batch_size,
    )
    print(f"Regional quote retry attempted: {result['attempted']}")
    print(f"Regional quote retry updated: {result['updated']}")
    print(f"Quote retry report: {result['report_path']}")


if __name__ == "__main__":
    main()
