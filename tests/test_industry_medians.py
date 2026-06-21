import csv
import tempfile
import unittest
from pathlib import Path

from industry_medians import (
    apply_industry_medians,
    calculate_industry_medians,
    run_industry_median_update,
)


class IndustryMedianTests(unittest.TestCase):
    def test_calculates_medians_by_market_and_industry(self):
        rows = [
            {
                "market": "美股",
                "industry": "科技软件",
                "market_cap": "1000",
                "net_income_ttm": "100",
                "net_assets": "500",
                "enterprise_value": "1200",
                "ebitda": "200",
            },
            {
                "market": "美股",
                "industry": "科技软件",
                "market_cap": "1500",
                "net_income_ttm": "100",
                "net_assets": "500",
                "enterprise_value": "1800",
                "ebitda": "200",
            },
            {
                "market": "A股",
                "industry": "科技软件",
                "market_cap": "3000",
                "net_income_ttm": "100",
                "net_assets": "1000",
                "enterprise_value": "3600",
                "ebitda": "300",
            },
        ]

        medians = calculate_industry_medians(rows)

        self.assertEqual(medians[("美股", "科技软件")]["sample_count"], 2)
        self.assertEqual(medians[("美股", "科技软件")]["industry_pe_median"], 12.5)
        self.assertEqual(medians[("美股", "科技软件")]["industry_pb_median"], 2.5)
        self.assertEqual(medians[("美股", "科技软件")]["industry_ev_ebitda_median"], 7.5)
        self.assertEqual(medians[("A股", "科技软件")]["industry_pe_median"], 30.0)

    def test_apply_medians_fills_missing_values_without_overwriting_manual_values(self):
        rows = [
            {
                "market": "美股",
                "ticker": "A",
                "industry": "科技软件",
                "industry_pe_median": "",
                "industry_pb_median": "99",
            }
        ]
        medians = {
            ("美股", "科技软件"): {
                "industry_pe_median": 12.5,
                "industry_pb_median": 2.5,
                "industry_ev_ebitda_median": 7.5,
                "sample_count": 2,
            }
        }

        updated = apply_industry_medians(rows, medians)

        self.assertEqual(updated[0]["industry_pe_median"], 12.5)
        self.assertEqual(updated[0]["industry_pb_median"], "99")
        self.assertEqual(updated[0]["industry_ev_ebitda_median"], 7.5)
        self.assertEqual(updated[0]["industry_median_sample_count"], 2)

    def test_run_update_writes_enriched_rows_and_median_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "stocks.csv"
            output_path = root / "stocks_with_medians.csv"
            medians_path = root / "industry_medians.csv"

            rows = [
                {
                    "market": "美股",
                    "ticker": "A",
                    "industry": "科技软件",
                    "market_cap": "1000",
                    "net_income_ttm": "100",
                    "net_assets": "500",
                    "enterprise_value": "1200",
                    "ebitda": "200",
                },
                {
                    "market": "美股",
                    "ticker": "B",
                    "industry": "科技软件",
                    "market_cap": "1500",
                    "net_income_ttm": "100",
                    "net_assets": "500",
                    "enterprise_value": "1800",
                    "ebitda": "200",
                },
            ]
            with input_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)

            result = run_industry_median_update(input_path, output_path, medians_path)
            output_text = output_path.read_text(encoding="utf-8-sig")
            medians_text = medians_path.read_text(encoding="utf-8-sig")

            self.assertEqual(result["rows"], 2)
            self.assertIn("industry_pe_median", output_text)
            self.assertIn("12.5", output_text)
            self.assertIn("sample_count", medians_text)


if __name__ == "__main__":
    unittest.main()
