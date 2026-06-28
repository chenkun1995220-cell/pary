import argparse
import csv
from pathlib import Path


FIELDNAMES = [
    "as_of_date",
    "market",
    "review_type",
    "ticker",
    "company",
    "decision_status",
    "decision_note",
    "reviewer",
    "decided_at",
]

FINAL_STATUSES = {"accepted", "rejected", "needs_more_data"}


def read_rows(path):
    try:
        with Path(path).open("r", newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    except FileNotFoundError:
        return []


def write_rows(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def decision_key(row):
    market = (row.get("market") or "").strip()
    review_type = (row.get("review_type") or "").strip()
    ticker = (row.get("ticker") or "").strip()
    if not (market and review_type and ticker):
        return None
    return (market, review_type, ticker)


def normalize_decision_row(row):
    return {field: (row.get(field) or "").strip() for field in FIELDNAMES}


def merge_decisions(template_rows, existing_rows):
    merged = {}
    order = []
    for row in existing_rows:
        key = decision_key(row)
        if not key:
            continue
        if key not in merged:
            order.append(key)
        merged[key] = normalize_decision_row(row)

    skipped_pending = 0
    skipped_invalid = 0
    merged_count = 0
    for row in template_rows:
        status = (row.get("decision_status") or "").strip()
        if status in {"", "pending"}:
            skipped_pending += 1
            continue
        if status not in FINAL_STATUSES:
            skipped_invalid += 1
            continue
        key = decision_key(row)
        if not key:
            skipped_invalid += 1
            continue
        if key not in merged:
            order.append(key)
        merged[key] = normalize_decision_row(row)
        merged_count += 1

    return {
        "rows": [merged[key] for key in order],
        "merged": merged_count,
        "skipped_pending": skipped_pending,
        "skipped_invalid": skipped_invalid,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", required=True)
    parser.add_argument("--decisions", required=True)
    args = parser.parse_args(argv)

    template_rows = read_rows(args.template)
    existing_rows = read_rows(args.decisions)
    result = merge_decisions(template_rows, existing_rows)
    write_rows(args.decisions, result["rows"])
    print(
        "merged={merged} skipped_pending={skipped_pending} skipped_invalid={skipped_invalid} output={output}".format(
            merged=result["merged"],
            skipped_pending=result["skipped_pending"],
            skipped_invalid=result["skipped_invalid"],
            output=args.decisions,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
