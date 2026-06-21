import argparse
import csv
from pathlib import Path


DEFAULT_FIELDS = ["ticker", "company_name", "raw_industry", "industry", "industry_mapping_status"]


def canonical_key(value):
    return " ".join(str(value or "").strip().lower().split())


def load_csv_rows(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return [{key.strip(): value for key, value in row.items() if key is not None} for row in csv.DictReader(f)]


def load_industry_aliases(path):
    aliases = {}
    for row in load_csv_rows(path):
        alias = canonical_key(row.get("alias"))
        standard = str(row.get("standard_industry", "")).strip()
        if alias and standard:
            aliases[alias] = standard
    return aliases


def normalize_industry_name(industry, aliases):
    key = canonical_key(industry)
    return aliases.get(key, str(industry or "").strip())


def apply_industry_mapping(rows, aliases):
    mapped = []
    for row in rows:
        out = dict(row)
        raw = str(out.get("industry", "")).strip()
        normalized = normalize_industry_name(raw, aliases)
        out["raw_industry"] = raw
        out["industry"] = normalized
        out["industry_mapping_status"] = (
            "mapped" if canonical_key(raw) in aliases else "unmapped"
        )
        mapped.append(out)
    return mapped


def write_csv(path, rows):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(DEFAULT_FIELDS)
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_industry_mapping(input_path, output_path, aliases_path):
    aliases = load_industry_aliases(aliases_path)
    rows = load_csv_rows(input_path)
    mapped = apply_industry_mapping(rows, aliases)
    write_csv(output_path, mapped)
    return {
        "rows": len(mapped),
        "mapped_rows": sum(1 for row in mapped if row.get("industry_mapping_status") == "mapped"),
        "output_path": Path(output_path),
    }


def main():
    parser = argparse.ArgumentParser(description="按别名表统一行业分类。")
    parser.add_argument("--input", required=True, help="输入股票 CSV")
    parser.add_argument("--output", required=True, help="行业标准化后输出 CSV")
    parser.add_argument("--aliases", default="data/config/industry_aliases.csv", help="行业别名表")
    args = parser.parse_args()

    result = run_industry_mapping(args.input, args.output, args.aliases)
    print(f"已处理股票行数：{result['rows']}")
    print(f"已映射行业行数：{result['mapped_rows']}")
    print(f"输出文件：{result['output_path']}")


if __name__ == "__main__":
    main()
