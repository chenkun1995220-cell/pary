import argparse
import csv
import json
from pathlib import Path


WEAK_EVIDENCE_LEVELS = {"secondary", "insufficient"}

GAP_FIELDNAMES = [
    "rank",
    "ticker",
    "company_name",
    "effective_date",
    "current_evidence",
    "membership_source_url",
    "weeks_affected",
    "first_week",
    "last_week",
    "recommended_action",
]


def read_rows(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
        ]


def evidence_level(row):
    level = (row.get("membership_evidence") or row.get("evidence_level") or "secondary").strip().lower()
    if level not in {"verified", "secondary", "insufficient"}:
        return "insufficient"
    return level


def gap_key(row, level):
    return (
        (row.get("ticker") or "").strip().upper(),
        (row.get("effective_date") or row.get("date_added") or "").strip(),
        level,
        (row.get("membership_source_url") or "").strip(),
    )


def build_evidence_gap_report(membership_path, limit=50):
    rows = read_rows(membership_path)
    groups = {}
    verified_rows = 0
    weak_rows = 0
    for row in rows:
        level = evidence_level(row)
        if level == "verified":
            verified_rows += 1
            continue
        if level not in WEAK_EVIDENCE_LEVELS:
            continue
        weak_rows += 1
        key = gap_key(row, level)
        entry = groups.setdefault(
            key,
            {
                "ticker": key[0],
                "company_name": row.get("company_name", ""),
                "effective_date": key[1],
                "current_evidence": level,
                "membership_source_url": key[3],
                "weeks": set(),
            },
        )
        if row.get("week"):
            entry["weeks"].add(row["week"])

    gaps = []
    for entry in groups.values():
        weeks = sorted(entry.pop("weeks"))
        entry["weeks_affected"] = len(weeks)
        entry["first_week"] = weeks[0] if weeks else ""
        entry["last_week"] = weeks[-1] if weeks else ""
        entry["recommended_action"] = "supplement_official_spglobal_source"
        gaps.append(entry)

    gaps.sort(
        key=lambda item: (
            -int(item.get("weeks_affected") or 0),
            item.get("current_evidence", ""),
            item.get("effective_date", ""),
            item.get("ticker", ""),
        )
    )
    limited_gaps = []
    for index, gap in enumerate(gaps[:limit], start=1):
        next_gap = dict(gap)
        next_gap["rank"] = index
        limited_gaps.append(next_gap)

    return {
        "schema": "membership_evidence_gap_report",
        "version": 1,
        "membership_path": str(membership_path),
        "total_rows": len(rows),
        "verified_rows": verified_rows,
        "weak_rows": weak_rows,
        "gap_count": len(gaps),
        "returned_gap_count": len(limited_gaps),
        "gaps": limited_gaps,
    }


def write_gap_outputs(report, json_path, csv_path, markdown_path):
    json_path = Path(json_path)
    csv_path = Path(csv_path)
    markdown_path = Path(markdown_path)
    for path in (json_path, csv_path, markdown_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=GAP_FIELDNAMES)
        writer.writeheader()
        for row in report.get("gaps", []):
            writer.writerow({field: row.get(field, "") for field in GAP_FIELDNAMES})
    markdown_path.write_text(render_markdown(report), encoding="utf-8-sig")
    return {"json": str(json_path), "csv": str(csv_path), "markdown": str(markdown_path)}


def render_markdown(report):
    lines = [
        "# membership_evidence_gap_report",
        "",
        f"- Membership file: {report.get('membership_path', '')}",
        f"- Total rows: {report.get('total_rows', 0)}",
        f"- Verified rows: {report.get('verified_rows', 0)}",
        f"- Weak rows: {report.get('weak_rows', 0)}",
        f"- Weak evidence groups: {report.get('gap_count', 0)}",
        "",
        "| Rank | Ticker | Company | Effective date | Evidence | Weeks affected | First week | Last week | Action |",
        "|---:|---|---|---|---|---:|---|---|---|",
    ]
    for row in report.get("gaps", []):
        lines.append(
            "| {rank} | {ticker} | {company_name} | {effective_date} | {current_evidence} | "
            "{weeks_affected} | {first_week} | {last_week} | {recommended_action} |".format(**row)
        )
    if not report.get("gaps"):
        lines.append("| - | - | - | - | - | 0 | - | - | No weak membership evidence found. |")
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--membership", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args(argv)

    report = build_evidence_gap_report(args.membership, limit=args.limit)
    outputs = write_gap_outputs(report, args.output_json, args.output_csv, args.output_md)
    print(
        "membership_evidence_gaps weak_rows={weak_rows} gap_count={gap_count} csv={csv}".format(
            weak_rows=report["weak_rows"],
            gap_count=report["gap_count"],
            csv=outputs["csv"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
