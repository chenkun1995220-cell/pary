import csv
import tempfile
import unittest
from pathlib import Path

from industry_mapper import (
    apply_industry_mapping,
    load_industry_aliases,
    normalize_industry_name,
    run_industry_mapping,
)


class IndustryMapperTests(unittest.TestCase):
    def test_normalizes_aliases_to_standard_industry(self):
        aliases = {
            "software": "科技软件",
            "saas": "科技软件",
            "软件": "科技软件",
        }

        self.assertEqual(normalize_industry_name("Software", aliases), "科技软件")
        self.assertEqual(normalize_industry_name(" SaaS ", aliases), "科技软件")
        self.assertEqual(normalize_industry_name("软件", aliases), "科技软件")

    def test_apply_mapping_preserves_raw_industry_and_marks_status(self):
        rows = [
            {"ticker": "A", "industry": "Software"},
            {"ticker": "B", "industry": "未知行业"},
        ]
        aliases = {"software": "科技软件"}

        mapped = apply_industry_mapping(rows, aliases)

        self.assertEqual(mapped[0]["raw_industry"], "Software")
        self.assertEqual(mapped[0]["industry"], "科技软件")
        self.assertEqual(mapped[0]["industry_mapping_status"], "mapped")
        self.assertEqual(mapped[1]["industry"], "未知行业")
        self.assertEqual(mapped[1]["industry_mapping_status"], "unmapped")

    def test_marks_registered_standard_industry_as_mapped(self):
        rows = [{"ticker": "A", "industry": "科技软件"}]
        aliases = {"科技软件": "科技软件"}

        mapped = apply_industry_mapping(rows, aliases)

        self.assertEqual(mapped[0]["industry"], "科技软件")
        self.assertEqual(mapped[0]["industry_mapping_status"], "mapped")

    def test_run_mapping_writes_standardized_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "stocks.csv"
            aliases_path = root / "aliases.csv"
            output_path = root / "stocks_mapped.csv"

            with input_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["ticker", "industry"])
                writer.writeheader()
                writer.writerow({"ticker": "A", "industry": "Software"})
            with aliases_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["alias", "standard_industry"])
                writer.writeheader()
                writer.writerow({"alias": "software", "standard_industry": "科技软件"})

            aliases = load_industry_aliases(aliases_path)
            result = run_industry_mapping(input_path, output_path, aliases_path)
            output = output_path.read_text(encoding="utf-8-sig")

            self.assertEqual(aliases["software"], "科技软件")
            self.assertEqual(result["rows"], 1)
            self.assertIn("科技软件", output)
            self.assertIn("raw_industry", output)


if __name__ == "__main__":
    unittest.main()
