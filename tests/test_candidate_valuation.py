import math
import statistics
import csv
import tempfile
import unittest
from pathlib import Path

from candidate_valuation import calculate_trend, run_candidate_valuation, value_candidate


class CandidateTrendTests(unittest.TestCase):
    def test_classifies_strong_uptrend(self):
        result = calculate_trend(range(1, 131))

        self.assertEqual(result["trend_label"], "偏强")
        self.assertEqual(result["confidence"], "high")
        self.assertAlmostEqual(result["ma20"], 120.5)
        self.assertAlmostEqual(result["ma60"], 100.5)
        self.assertAlmostEqual(result["ma120"], 70.5)

    def test_classifies_moderately_strong_trend(self):
        closes = [100 + index * 0.05 for index in range(120)]

        result = calculate_trend(closes)

        self.assertEqual(result["trend_label"], "温和偏强")
        self.assertEqual(result["confidence"], "high")
        self.assertGreater(result["momentum_12m"], 0)
        self.assertLessEqual(result["momentum_12m"], 0.10)

    def test_classifies_neutral_trend(self):
        result = calculate_trend([100] * 120)

        self.assertEqual(result["trend_label"], "中性")
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["momentum_12m"], 0)

    def test_classifies_weak_trend(self):
        result = calculate_trend(range(130, 0, -1))

        self.assertEqual(result["trend_label"], "偏弱")
        self.assertEqual(result["confidence"], "high")
        self.assertLess(result["momentum_12m"], -0.10)

    def test_59_days_is_insufficient(self):
        result = calculate_trend(range(1, 60))

        self.assertEqual(result["trend_label"], "数据不足")
        self.assertEqual(result["confidence"], "low")

    def test_60_to_119_days_has_medium_confidence(self):
        result = calculate_trend(range(1, 81))

        self.assertEqual(result["trend_label"], "温和偏强")
        self.assertEqual(result["confidence"], "medium")
        self.assertIsNone(result["ma120"])

    def test_calculates_volatility_and_52_week_position(self):
        closes = [100, 110, 99] + [99] * 117
        returns = [0.10, -0.10] + [0.0] * 117

        result = calculate_trend(closes)

        expected_volatility = statistics.stdev(returns) * math.sqrt(252)
        self.assertAlmostEqual(result["annualized_volatility"], expected_volatility)
        self.assertEqual(result["high_52w"], 110)
        self.assertEqual(result["low_52w"], 99)
        self.assertEqual(result["position_52w"], 0)

    def test_52_week_position_uses_latest_252_observations(self):
        closes = [1000] + list(range(1, 253))

        result = calculate_trend(closes)

        self.assertEqual(result["high_52w"], 252)
        self.assertEqual(result["low_52w"], 1)
        self.assertEqual(result["position_52w"], 1)

    def test_12_month_momentum_uses_latest_252_observations(self):
        closes = [1000] + [100] * 251 + [110]

        result = calculate_trend(closes)

        self.assertAlmostEqual(result["momentum_12m"], 0.10)

    def test_calculates_one_week_and_one_month_trend_forecasts(self):
        closes = [100] * 90 + [100 + index for index in range(30)]

        result = calculate_trend(closes)

        self.assertEqual(result["one_week_trend_label"], "偏强")
        self.assertEqual(result["one_week_expected_direction"], "上行")
        self.assertEqual(result["one_week_trend_confidence"], "high")
        self.assertEqual(result["one_month_trend_label"], "偏强")
        self.assertEqual(result["one_month_expected_direction"], "上行")
        self.assertEqual(result["one_month_trend_confidence"], "high")

    def test_finite_extremes_do_not_produce_non_finite_outputs(self):
        closes = [1e-308, 1e308] * 60

        result = calculate_trend(closes)

        numeric_keys = (
            "latest_close",
            "ma20",
            "ma60",
            "ma120",
            "momentum_12m",
            "annualized_volatility",
            "high_52w",
            "low_52w",
            "position_52w",
        )
        for key in numeric_keys:
            with self.subTest(key=key):
                value = result[key]
                self.assertTrue(value is None or math.isfinite(value))


class CandidateValuationTests(unittest.TestCase):
    def base_row(self, **overrides):
        row = {
            "market": "CN",
            "ticker": "TEST.SZ",
            "price": "100",
            "pe": "10",
            "pb": "2",
            "industry_pe_median": "15",
            "industry_pb_median": "3",
            "profitability_score": "20",
            "balance_sheet_score": "12",
            "cash_flow_score": "8",
            "growth_score": "8",
            "confidence": "high",
        }
        row.update(overrides)
        return row

    def test_missing_fcf_renormalizes_pe_pb_weights(self):
        result = value_candidate(self.base_row(), {"trend_label": "中性", "confidence": "high"})

        self.assertAlmostEqual(result["pe_weight_used"], 0.625)
        self.assertAlmostEqual(result["pb_weight_used"], 0.375)
        self.assertEqual(result["valuation_status"], "ready")

    def test_target_is_capped_and_high_confidence_uses_twenty_percent_margin(self):
        result = value_candidate(
            self.base_row(industry_pe_median="40", industry_pb_median="8"),
            {"trend_label": "偏强", "confidence": "high"},
        )

        self.assertEqual(result["target_price"], 160.0)
        self.assertEqual(result["buy_price"], 128.0)
        self.assertEqual(result["margin_of_safety"], 0.20)

    def test_rounded_target_never_exceeds_cap(self):
        result = value_candidate(
            self.base_row(price="16.23", industry_pe_median="40", industry_pb_median="8"),
            {"trend_label": "偏强", "confidence": "high"},
        )

        self.assertLessEqual(result["target_price"], 16.23 * 1.60)

    def test_fcf_adds_twenty_percent_weight(self):
        result = value_candidate(
            self.base_row(fcf_yield="0.10"),
            {"trend_label": "中性", "confidence": "high"},
        )

        self.assertEqual(result["pe_weight_used"], 0.50)
        self.assertEqual(result["pb_weight_used"], 0.30)
        self.assertEqual(result["fcf_weight_used"], 0.20)
        self.assertEqual(result["fcf_fair_price"], 200.0)

    def test_medium_and_low_confidence_expand_margin(self):
        medium = value_candidate(
            self.base_row(confidence="medium"),
            {"trend_label": "中性", "confidence": "medium"},
        )
        low = value_candidate(
            self.base_row(confidence="low"),
            {"trend_label": "数据不足", "confidence": "low"},
        )

        self.assertEqual(medium["margin_of_safety"], 0.25)
        self.assertEqual(low["margin_of_safety"], 0.30)

    def test_no_valid_method_returns_insufficient_data(self):
        result = value_candidate(
            self.base_row(pe="-1", pb="", industry_pe_median="", industry_pb_median=""),
            {"trend_label": "中性", "confidence": "high"},
        )

        self.assertEqual(result["valuation_status"], "insufficient_data")
        self.assertIsNone(result["target_price"])
        self.assertIsNone(result["buy_price"])

    def test_target_below_market_marks_no_margin_of_safety(self):
        result = value_candidate(
            self.base_row(industry_pe_median="5", industry_pb_median="0.5"),
            {"trend_label": "中性", "confidence": "high"},
        )

        self.assertLess(result["target_price"], 100)
        self.assertEqual(result["price_action"], "等待回调/当前无安全边际")

    def test_large_method_dispersion_forces_low_confidence(self):
        result = value_candidate(
            self.base_row(pe="40", pb="0.5", industry_pe_median="5", industry_pb_median="8"),
            {"trend_label": "中性", "confidence": "high"},
        )

        self.assertEqual(result["valuation_confidence"], "low")
        self.assertEqual(result["margin_of_safety"], 0.30)

    def test_non_iterable_inputs_return_insufficient_data(self):
        for closes in (None, 42):
            with self.subTest(closes=closes):
                result = calculate_trend(closes)

                self.assertEqual(result["observations"], 0)
                self.assertEqual(result["trend_label"], "数据不足")
                self.assertEqual(result["confidence"], "low")

    def test_ignores_invalid_values_and_zero_previous_returns(self):
        closes = ["bad", None, float("nan"), float("inf"), 0, 0]
        closes.extend([10] * 60)

        result = calculate_trend(closes)

        self.assertEqual(result["observations"], 62)
        self.assertEqual(result["trend_label"], "中性")
        self.assertEqual(result["confidence"], "medium")
        self.assertEqual(result["annualized_volatility"], 0)
        for key in ("momentum_12m", "annualized_volatility", "position_52w"):
            value = result[key]
            self.assertTrue(value is None or math.isfinite(value))


class CandidateOutputTests(unittest.TestCase):
    def write_csv(self, path, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def price_rows(self, market="CN", ticker="TEST.SZ"):
        return [
            {
                "market": market,
                "ticker": ticker,
                "date": f"2025-01-{(index % 28) + 1:02d}",
                "close": 80 + index * 0.2,
                "source": "fixture",
                "data_status": "ready",
            }
            for index in range(120)
        ]

    def candidate(self):
        return {
            "market": "A股", "ticker": "TEST.SZ", "company_name": "测试公司",
            "industry": "软件", "currency": "CNY", "price": "100", "pe": "10",
            "pb": "2", "industry_pe_median": "15", "industry_pb_median": "3",
            "profitability_score": "20", "balance_sheet_score": "12",
            "cash_flow_score": "8", "growth_score": "8", "confidence": "high",
            "financial_report_date": "2026-03-31",
        }

    def test_run_writes_outputs_and_deduplicates_same_day_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidates.csv"
            history = root / "prices.csv"
            output = root / "out"
            self.write_csv(candidates, [self.candidate()])
            self.write_csv(history, self.price_rows())

            first = run_candidate_valuation(candidates, history, output, "CN", generated_date="2026-06-21")
            run_candidate_valuation(candidates, history, output, "CN", generated_date="2026-06-21")

            with (output / "forecast_history.csv").open(encoding="utf-8-sig", newline="") as handle:
                forecasts = list(csv.DictReader(handle))
            with (output / "valuation_targets.csv").open(encoding="utf-8-sig", newline="") as handle:
                target = next(csv.DictReader(handle))
            self.assertEqual(first["rows"], 1)
            self.assertEqual(len(forecasts), 1)
            self.assertEqual(target["one_week_expected_direction"], "上行")
            self.assertEqual(target["one_month_expected_direction"], "上行")
            self.assertEqual(forecasts[0]["one_week_expected_direction"], "上行")
            self.assertEqual(forecasts[0]["one_month_expected_direction"], "上行")
            self.assertTrue((output / "valuation_targets.csv").exists())
            report = (output / "valuation_report.md").read_text(encoding="utf-8-sig")
            self.assertIn("12个月目标价", report)
            self.assertIn("1周走势", report)
            self.assertIn("1个月走势", report)
            self.assertIn("TEST.SZ", report)

    def test_next_day_appends_without_overwriting_old_forecast(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidates.csv"
            history = root / "prices.csv"
            output = root / "out"
            self.write_csv(candidates, [self.candidate()])
            self.write_csv(history, self.price_rows())
            run_candidate_valuation(candidates, history, output, "CN", generated_date="2026-06-21")
            run_candidate_valuation(candidates, history, output, "CN", generated_date="2026-06-22")

            with (output / "forecast_history.csv").open(encoding="utf-8-sig", newline="") as handle:
                forecasts = list(csv.DictReader(handle))
            self.assertEqual([row["generated_date"] for row in forecasts], ["2026-06-21", "2026-06-22"])

    def test_us_merges_quote_and_industry_median(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidates.csv"
            history = root / "prices.csv"
            quotes = root / "quotes.csv"
            medians = root / "medians.csv"
            output = root / "out"
            us = self.candidate()
            us.update({"market": "美股", "ticker": "TEST", "currency": "USD", "price": "", "industry_pe_median": "", "industry_pb_median": ""})
            self.write_csv(candidates, [us])
            self.write_csv(history, self.price_rows("US", "TEST"))
            self.write_csv(quotes, [{"ticker": "TEST", "price": "100", "currency": "USD", "quote_date": "2026-06-21"}])
            self.write_csv(medians, [{"market": "美股", "industry": "软件", "industry_pe_median": "15", "industry_pb_median": "3"}])

            run_candidate_valuation(candidates, history, output, "US", medians, quotes, "2026-06-21")

            with (output / "valuation_targets.csv").open(encoding="utf-8-sig", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["current_price"], "100.0")
            self.assertEqual(row["valuation_status"], "ready")


if __name__ == "__main__":
    unittest.main()
