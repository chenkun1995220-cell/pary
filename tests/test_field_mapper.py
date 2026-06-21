import csv
import tempfile
import unittest
from pathlib import Path

from field_mapper import load_field_aliases, map_row_fields, run_field_mapping


class FieldMapperTests(unittest.TestCase):
    def test_maps_chinese_headers_to_standard_fields(self):
        aliases = {
            "股票代码": "ticker",
            "公司名称": "company_name",
            "总市值": "market_cap",
            "归母净利润ttm": "net_income_ttm",
        }
        row = {
            "股票代码": "600000",
            "公司名称": "样本公司",
            "总市值": "50000",
            "归母净利润TTM": "3500",
        }

        mapped = map_row_fields(row, aliases)

        self.assertEqual(mapped["ticker"], "600000")
        self.assertEqual(mapped["company_name"], "样本公司")
        self.assertEqual(mapped["market_cap"], "50000")
        self.assertEqual(mapped["net_income_ttm"], "3500")

    def test_unmapped_fields_are_preserved_and_recorded(self):
        aliases = {"股票代码": "ticker"}
        row = {"股票代码": "600000", "未知字段": "abc"}

        mapped = map_row_fields(row, aliases)

        self.assertEqual(mapped["ticker"], "600000")
        self.assertEqual(mapped["source_未知字段"], "abc")
        self.assertEqual(mapped["unmapped_fields"], "未知字段")

    def test_run_field_mapping_writes_standard_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "broker_export.csv"
            aliases_path = root / "field_aliases.csv"
            output_path = root / "mapped.csv"

            with input_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["市场", "股票代码", "公司名称", "行业", "总市值"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "市场": "A股",
                        "股票代码": "600000",
                        "公司名称": "样本公司",
                        "行业": "软件",
                        "总市值": "50000",
                    }
                )
            with aliases_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["alias", "standard_field"])
                writer.writeheader()
                writer.writerow({"alias": "市场", "standard_field": "market"})
                writer.writerow({"alias": "股票代码", "standard_field": "ticker"})
                writer.writerow({"alias": "公司名称", "standard_field": "company_name"})
                writer.writerow({"alias": "行业", "standard_field": "industry"})
                writer.writerow({"alias": "总市值", "standard_field": "market_cap"})

            aliases = load_field_aliases(aliases_path)
            result = run_field_mapping(input_path, output_path, aliases_path)
            output = output_path.read_text(encoding="utf-8-sig")

            self.assertEqual(aliases["股票代码"], "ticker")
            self.assertEqual(result["rows"], 1)
            self.assertIn("ticker", output)
            self.assertIn("600000", output)


if __name__ == "__main__":
    unittest.main()
