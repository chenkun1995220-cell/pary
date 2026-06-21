import argparse
import csv
import statistics
from pathlib import Path


MEDIAN_FIELDS = [
    "market",
    "industry",
    "sample_count",
    "industry_pe_median",
    "industry_pb_median",
    "industry_ev_ebitda_median",
]


def to_float(value):
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def ratio(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def load_csv_rows(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return [{key.strip(): value for key, value in row.items() if key is not None} for row in csv.DictReader(f)]


def median_or_blank(values):
    clean = [value for value in values if value is not None and value > 0]
    if not clean:
        return ""
    return round(float(statistics.median(clean)), 4)


def calculate_industry_medians(rows):
    grouped = {}
    for row in rows:
        market = row.get("market", "").strip()
        industry = row.get("industry", "").strip()
        if not market or not industry:
            continue
        market_cap = to_float(row.get("market_cap"))
        net_income = to_float(row.get("net_income_ttm"))
        net_assets = to_float(row.get("net_assets"))
        enterprise_value = to_float(row.get("enterprise_value"))
        ebitda = to_float(row.get("ebitda"))
        key = (market, industry)
        grouped.setdefault(key, {"pe": [], "pb": [], "ev_ebitda": [], "sample_count": 0})
        grouped[key]["sample_count"] += 1
        grouped[key]["pe"].append(ratio(market_cap, net_income) if net_income and net_income > 0 else None)
        grouped[key]["pb"].append(ratio(market_cap, net_assets) if net_assets and net_assets > 0 else None)
        grouped[key]["ev_ebitda"].append(
            ratio(enterprise_value, ebitda) if ebitda and ebitda > 0 else None
        )

    medians = {}
    for key, values in grouped.items():
        medians[key] = {
            "sample_count": values["sample_count"],
            "industry_pe_median": median_or_blank(values["pe"]),
            "industry_pb_median": median_or_blank(values["pb"]),
            "industry_ev_ebitda_median": median_or_blank(values["ev_ebitda"]),
        }
    return medians


def is_blank(value):
    return value is None or str(value).strip() == ""


def apply_industry_medians(rows, medians, overwrite=False):
    updated = []
    for row in rows:
        out = dict(row)
        key = (out.get("market", "").strip(), out.get("industry", "").strip())
        median = medians.get(key)
        if median:
            for field in [
                "industry_pe_median",
                "industry_pb_median",
                "industry_ev_ebitda_median",
            ]:
                if overwrite or is_blank(out.get(field)):
                    out[field] = median[field]
            out["industry_median_sample_count"] = median["sample_count"]
        updated.append(out)
    return updated


def write_csv(path, rows, preferred_fields=None):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(preferred_fields or [])
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def median_rows(medians):
    rows = []
    for (market, industry), values in sorted(medians.items()):
        row = {"market": market, "industry": industry}
        row.update(values)
        rows.append(row)
    return rows


def run_industry_median_update(input_path, output_path, medians_path, overwrite=False):
    rows = load_csv_rows(input_path)
    medians = calculate_industry_medians(rows)
    updated = apply_industry_medians(rows, medians, overwrite=overwrite)
    write_csv(output_path, updated)
    write_csv(medians_path, median_rows(medians), preferred_fields=MEDIAN_FIELDS)
    return {
        "rows": len(updated),
        "groups": len(medians),
        "output_path": Path(output_path),
        "medians_path": Path(medians_path),
    }


def main():
    parser = argparse.ArgumentParser(description="按市场和行业自动计算估值中位数并回填。")
    parser.add_argument("--input", default="data/raw/us_stocks_enriched.csv", help="输入股票 CSV")
    parser.add_argument("--output", default="data/raw/us_stocks_with_industry_medians.csv", help="回填后输出 CSV")
    parser.add_argument("--medians", default="data/derived/industry_medians.csv", help="行业中位数表输出")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已有手工行业阈值")
    args = parser.parse_args()

    result = run_industry_median_update(
        args.input,
        args.output,
        args.medians,
        overwrite=args.overwrite,
    )
    print(f"已回填行业中位数股票行数：{result['rows']}")
    print(f"行业分组数：{result['groups']}")
    print(f"输出文件：{result['output_path']}")
    print(f"中位数表：{result['medians_path']}")


if __name__ == "__main__":
    main()
