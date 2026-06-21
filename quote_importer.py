import argparse
import csv
from pathlib import Path


QUOTE_FIELDS = [
    "ticker",
    "price",
    "shares_outstanding",
    "net_debt",
    "currency",
    "quote_date",
    "price_unit",
    "shares_unit",
    "debt_unit",
    "quote_source",
    "updated_at",
    "unmapped_fields",
]

DEFAULTS = {
    "currency": "USD",
    "price_unit": "USD/share",
    "shares_unit": "million_shares",
    "debt_unit": "USD_million",
}


def canonical_key(value):
    return " ".join(str(value or "").strip().lower().split())


def load_csv_rows(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return [
            {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(f)
        ]


def load_quote_aliases(path):
    aliases = {}
    for row in load_csv_rows(path):
        alias = canonical_key(row.get("alias"))
        standard = str(row.get("standard_field", "")).strip()
        if alias and standard:
            aliases[alias] = standard
    return aliases


def map_quote_row(row, aliases):
    mapped = {}
    unmapped = []
    for original_key, value in row.items():
        key = str(original_key or "").strip()
        if not key:
            continue
        standard = aliases.get(canonical_key(key))
        if standard:
            mapped[standard] = value
        else:
            mapped[f"source_{key}"] = value
            unmapped.append(key)

    for field, value in DEFAULTS.items():
        mapped.setdefault(field, value)
    if mapped.get("ticker"):
        mapped["ticker"] = mapped["ticker"].upper()
    if not mapped.get("updated_at") and mapped.get("quote_date"):
        mapped["updated_at"] = mapped["quote_date"]
    mapped["unmapped_fields"] = ";".join(unmapped)
    return mapped


def write_quote_csv(path, rows):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(QUOTE_FIELDS)
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def import_quote_csv(input_path, output_path, aliases_path):
    aliases = load_quote_aliases(aliases_path)
    rows = [map_quote_row(row, aliases) for row in load_csv_rows(input_path)]
    write_quote_csv(output_path, rows)
    return {
        "rows": len(rows),
        "unmapped_rows": sum(1 for row in rows if row.get("unmapped_fields")),
        "output_path": Path(output_path),
    }


def main():
    parser = argparse.ArgumentParser(description="导入外部行情 CSV 并映射为标准行情补充表。")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--aliases", default="data/config/quote_field_aliases.csv")
    args = parser.parse_args()

    result = import_quote_csv(args.input, args.output, args.aliases)
    print(f"已处理行情行数：{result['rows']}")
    print(f"存在未识别字段的行数：{result['unmapped_rows']}")
    print(f"输出文件：{result['output_path']}")


if __name__ == "__main__":
    main()
