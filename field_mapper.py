import argparse
import csv
from pathlib import Path


STANDARD_FIELDS = [
    "market",
    "ticker",
    "company_name",
    "industry",
    "currency",
    "quote_date",
    "price",
    "shares_outstanding",
    "market_cap",
    "net_debt",
    "enterprise_value",
    "net_assets",
    "revenue_ttm",
    "net_income_ttm",
    "ebitda",
    "operating_cash_flow",
    "capex",
    "dividend_yield",
    "industry_pe_median",
    "industry_pb_median",
    "industry_ev_ebitda_median",
    "roe",
    "roic",
    "gross_margin",
    "debt_to_assets",
    "net_debt_to_ebitda",
    "current_ratio",
    "revenue_cagr_3y",
    "net_income_cagr_3y",
    "audit_opinion",
    "risk_flag",
    "source",
    "source_cik",
    "source_filed",
    "unmapped_fields",
]


def canonical_key(value):
    return " ".join(str(value or "").strip().lower().split())


def load_csv_rows(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return [{key.strip(): value for key, value in row.items() if key is not None} for row in csv.DictReader(f)]


def load_field_aliases(path):
    aliases = {}
    for row in load_csv_rows(path):
        alias = canonical_key(row.get("alias"))
        standard = str(row.get("standard_field", "")).strip()
        if alias and standard:
            aliases[alias] = standard
    return aliases


def map_row_fields(row, aliases):
    mapped = {}
    unmapped = []
    for original_key, value in row.items():
        key = str(original_key or "").strip()
        if key == "":
            continue
        standard = aliases.get(canonical_key(key))
        if standard:
            mapped[standard] = value
        else:
            mapped[f"source_{key}"] = value
            unmapped.append(key)
    mapped["unmapped_fields"] = ";".join(unmapped)
    return mapped


def write_csv(path, rows):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(STANDARD_FIELDS)
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_field_mapping(input_path, output_path, aliases_path):
    aliases = load_field_aliases(aliases_path)
    rows = load_csv_rows(input_path)
    mapped = [map_row_fields(row, aliases) for row in rows]
    write_csv(output_path, mapped)
    return {
        "rows": len(mapped),
        "unmapped_rows": sum(1 for row in mapped if row.get("unmapped_fields")),
        "output_path": Path(output_path),
    }


def main():
    parser = argparse.ArgumentParser(description="把外部 CSV 表头映射为股票筛选标准字段。")
    parser.add_argument("--input", required=True, help="外部导出 CSV")
    parser.add_argument("--output", required=True, help="标准字段输出 CSV")
    parser.add_argument("--aliases", default="data/config/field_aliases.csv", help="字段别名表")
    args = parser.parse_args()

    result = run_field_mapping(args.input, args.output, args.aliases)
    print(f"已处理行数：{result['rows']}")
    print(f"存在未识别字段的行数：{result['unmapped_rows']}")
    print(f"输出文件：{result['output_path']}")


if __name__ == "__main__":
    main()
