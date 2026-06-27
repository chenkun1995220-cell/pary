import argparse
import csv
from datetime import date
from pathlib import Path


AUDIT_FIELDS = [
    "ticker",
    "status",
    "age_days",
    "missing_fields",
    "shares_outstanding",
    "shares_unit",
    "as_of_date",
    "source",
    "source_url",
    "note",
]
REQUIRED_FIELDS = ["ticker", "shares_outstanding", "shares_unit", "as_of_date", "source", "source_url"]
REVIEW_STATUSES = {"stale", "incomplete", "invalid_date", "invalid_shares"}


def load_override_rows(path):
    override_path = Path(path)
    if not override_path.exists():
        return []
    with override_path.open(encoding="utf-8-sig", newline="") as handle:
        return [
            {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
        ]


def parse_run_date(run_date=None):
    if run_date:
        return date.fromisoformat(str(run_date))
    return date.today()


def missing_fields(row):
    return [field for field in REQUIRED_FIELDS if not row.get(field, "").strip()]


def audit_share_overrides(rows, run_date=None, max_age_days=365):
    current_date = parse_run_date(run_date)
    audited = []
    for row in rows:
        ticker = row.get("ticker", "").strip().upper()
        missing = missing_fields(row)
        status = "current"
        age_days = ""
        if missing:
            status = "incomplete"
        else:
            try:
                float(str(row.get("shares_outstanding", "")).replace(",", ""))
            except ValueError:
                status = "invalid_shares"
            try:
                override_date = date.fromisoformat(row.get("as_of_date", ""))
                age_days = str((current_date - override_date).days)
                if status == "current" and int(age_days) > int(max_age_days):
                    status = "stale"
            except ValueError:
                status = "invalid_date"
        audited.append(
            {
                "ticker": ticker,
                "status": status,
                "age_days": age_days,
                "missing_fields": ", ".join(missing),
                "shares_outstanding": row.get("shares_outstanding", ""),
                "shares_unit": row.get("shares_unit", ""),
                "as_of_date": row.get("as_of_date", ""),
                "source": row.get("source", ""),
                "source_url": row.get("source_url", ""),
                "note": row.get("note", ""),
            }
        )
    return audited


def write_audit_csv(path, rows):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=AUDIT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_audit_report(path, rows, max_age_days=365):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    needs_review = [row for row in rows if row.get("status") in REVIEW_STATUSES]
    lines = [
        "# 人工股本覆盖审计",
        "",
        f"- 覆盖项：{len(rows)}",
        f"- 需复核：{len(needs_review)}",
        f"- 过期阈值：{max_age_days} 天",
        "",
    ]
    if not rows:
        lines.append("暂无人工覆盖项。")
    else:
        lines.extend(
            [
                "| 股票 | 状态 | 年龄(天) | 来源 | 说明 |",
                "|---|---|---:|---|---|",
            ]
        )
        for row in rows:
            lines.append(
                f"| {row['ticker']} | {row['status']} | {row['age_days']} | {row['source']} | {row['note']} |"
            )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def run_share_override_audit(overrides_path, output_csv, output_report, run_date=None, max_age_days=365):
    rows = audit_share_overrides(
        load_override_rows(overrides_path),
        run_date=run_date,
        max_age_days=max_age_days,
    )
    write_audit_csv(output_csv, rows)
    write_audit_report(output_report, rows, max_age_days=max_age_days)
    return {
        "rows": len(rows),
        "needs_review": sum(1 for row in rows if row.get("status") in REVIEW_STATUSES),
        "output_csv": Path(output_csv),
        "output_report": Path(output_report),
    }


def main():
    parser = argparse.ArgumentParser(description="审计美股人工股本覆盖项。")
    parser.add_argument("--overrides", default="data/manual/us_share_overrides.csv")
    parser.add_argument("--output-csv", default="outputs/us_universe/share_override_audit.csv")
    parser.add_argument("--output-report", default="outputs/us_universe/share_override_audit.md")
    parser.add_argument("--run-date", default=None)
    parser.add_argument("--max-age-days", type=int, default=365)
    args = parser.parse_args()

    result = run_share_override_audit(
        args.overrides,
        args.output_csv,
        args.output_report,
        run_date=args.run_date,
        max_age_days=args.max_age_days,
    )
    print(f"已审计人工覆盖项：{result['rows']}")
    print(f"需复核：{result['needs_review']}")
    print(f"CSV 输出：{result['output_csv']}")
    print(f"报告输出：{result['output_report']}")


if __name__ == "__main__":
    main()
