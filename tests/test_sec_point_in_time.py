import copy
from datetime import date, datetime, timedelta, timezone
import unittest

from sec_point_in_time import (
    _latest_source_filed_key,
    _parse_payload_filed_date,
    _normalize_filed_for_compare,
    calculate_metrics_as_of,
    filter_company_facts_as_of,
)
from tests.test_sec_financial_metrics import duration_fact, metric_facts

class SecPointInTimeTests(unittest.TestCase):
    def test_filter_excludes_future_filed_and_restatement(self):
        payload = metric_facts()
        payload["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"][
            "USD"
        ].append(
            duration_fact(
                999,
                "2025-01-01",
                "2025-06-30",
                2025,
                "Q2",
                "10-Q",
                "2025-12-31",
            )
        )

        filtered = filter_company_facts_as_of(payload, "2025-08-01")

        values = [
            entry["filed"]
            for entry in filtered["facts"]["us-gaap"][
                "RevenueFromContractWithCustomerExcludingAssessedTax"
            ]["units"]["USD"]
        ]
        self.assertIn("2025-07-25", values)
        self.assertNotIn("2025-12-31", values)

    def test_filter_normalizes_non_dict_facts(self):
        payload = {
            "cik": 320193,
            "facts": ["not", "a", "dict"],
        }
        filtered = filter_company_facts_as_of(payload, "2025-12-31")

        self.assertEqual(filtered, {"cik": 320193, "facts": {}})

    def test_filter_keeps_boundary_filed(self):
        payload = metric_facts()
        filtered = filter_company_facts_as_of(payload, "2025-07-25")

        values = [
            entry["filed"]
            for entry in filtered["facts"]["us-gaap"][
                "RevenueFromContractWithCustomerExcludingAssessedTax"
            ]["units"]["USD"]
        ]
        self.assertIn("2025-07-25", values)

    def test_filter_keeps_same_day_naive_datetime_when_as_of_is_date(self):
        payload = metric_facts()
        payload["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"][
            "units"
        ]["USD"].append(
            duration_fact(
                101,
                "2025-01-01",
                "2025-06-30",
                2025,
                "Q2",
                "10-Q",
                "2025-07-25T23:59:59",
            )
        )

        filtered = filter_company_facts_as_of(payload, "2025-07-25")
        values = [
            entry["filed"]
            for entry in filtered["facts"]["us-gaap"][
                "RevenueFromContractWithCustomerExcludingAssessedTax"
            ]["units"]["USD"]
        ]

        self.assertIn("2025-07-25T23:59:59", values)
        self.assertNotIn("2025-07-26T00:00:00", values)

    def test_filter_excludes_same_day_naive_datetime_when_as_of_is_aware_datetime(self):
        payload = metric_facts()
        payload["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"][
            "units"
        ]["USD"].append(
            duration_fact(
                1010,
                "2025-01-01",
                "2025-06-30",
                2025,
                "Q2",
                "10-Q",
                "2025-07-25T12:00:00",
            )
        )

        filtered = filter_company_facts_as_of(
            payload, "2025-07-25T10:00:00+00:00"
        )
        values = [
            entry["filed"]
            for entry in filtered["facts"]["us-gaap"][
                "RevenueFromContractWithCustomerExcludingAssessedTax"
            ]["units"]["USD"]
        ]

        self.assertIn("2025-07-25", values)
        self.assertNotIn("2025-07-25T12:00:00", values)

    def test_filter_keeps_native_date_and_datetime_filed_values(self):
        payload = metric_facts()
        payload["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"][
            "units"
        ]["USD"].append(
            {
                "val": 901,
                "start": "2025-01-01",
                "end": "2025-06-30",
                "fy": 2025,
                "fp": "Q2",
                "form": "10-Q",
                "filed": date(2025, 7, 25),
            }
        )
        payload["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"][
            "units"
        ]["USD"].append(
            {
                "val": 902,
                "start": "2025-01-01",
                "end": "2025-06-30",
                "fy": 2025,
                "fp": "Q2",
                "form": "10-Q",
                "filed": datetime(2025, 7, 25, 10, 0, 0),
            }
        )
        payload["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"][
            "units"
        ]["USD"].append(
            {
                "val": 903,
                "start": "2025-01-01",
                "end": "2025-06-30",
                "fy": 2025,
                "fp": "Q2",
                "form": "10-Q",
                "filed": datetime(2025, 7, 26, 10, 0, 0, tzinfo=timezone.utc),
            }
        )

        filtered = filter_company_facts_as_of(payload, date(2025, 7, 25))
        values = [
            entry["val"]
            for entry in filtered["facts"]["us-gaap"][
                "RevenueFromContractWithCustomerExcludingAssessedTax"
            ]["units"]["USD"]
        ]

        self.assertIn(901, values)
        self.assertIn(902, values)
        self.assertNotIn(903, values)

    def test_filter_accepts_native_datetime_as_of(self):
        payload = metric_facts()
        filtered = filter_company_facts_as_of(payload, datetime(2025, 7, 25, 15, 0, 0))

        values = [
            entry["filed"]
            for entry in filtered["facts"]["us-gaap"][
                "RevenueFromContractWithCustomerExcludingAssessedTax"
            ]["units"]["USD"]
        ]
        self.assertIn("2025-07-25", values)

    def test_filter_excludes_timezone_future_filed(self):
        payload = metric_facts()
        payload["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"][
            "USD"
        ].append(
            duration_fact(
                1200,
                "2025-01-01",
                "2025-06-30",
                2025,
                "Q2",
                "10-Q",
                "2025-07-24T23:30:00-01:00",
            )
        )

        filtered = filter_company_facts_as_of(payload, "2025-07-25T00:00:00+00:00")
        values = [
            entry["filed"]
            for entry in filtered["facts"]["us-gaap"][
                "RevenueFromContractWithCustomerExcludingAssessedTax"
            ]["units"]["USD"]
        ]

        self.assertNotIn("2025-07-24T23:30:00-01:00", values)

    def test_filter_payload_type_errors(self):
        with self.assertRaises(TypeError) as context:
            filter_company_facts_as_of(None, "2025-01-01")
        self.assertIn("payload", str(context.exception))

        with self.assertRaises(TypeError) as context:
            filter_company_facts_as_of([], "2025-01-01")
        self.assertIn("payload", str(context.exception))

    def test_filter_as_of_datetime_and_timezone_formats(self):
        payload = metric_facts()
        payload["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"][
            "units"
        ]["USD"].append(
            duration_fact(
                1300,
                "2025-01-01",
                "2025-06-30",
                2025,
                "Q2",
                "10-Q",
                "2025-07-25T10:00:00",
            )
        )
        payload["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"][
            "units"
        ]["USD"].append(
            duration_fact(
                1400,
                "2025-01-01",
                "2025-06-30",
                2025,
                "Q2",
                "10-Q",
                "2025-07-26T10:00:00+08:00",
            )
        )
        payload["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"][
            "units"
        ]["USD"].append(
            duration_fact(
                1500,
                "2025-01-01",
                "2025-06-30",
                2025,
                "Q2",
                "10-Q",
                "bad-date-value",
            )
        )
        payload["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"][
            "units"
        ]["USD"].append(
            duration_fact(
                1600,
                "2025-01-01",
                "2025-06-30",
                2025,
                "Q2",
                "10-Q",
                "2025-07-25T10:00:00Z",
            )
        )

        filtered = filter_company_facts_as_of(
            payload, "2025-07-25T23:00:00+00:00"
        )
        values = [
            entry["filed"]
            for entry in filtered["facts"]["us-gaap"][
                "RevenueFromContractWithCustomerExcludingAssessedTax"
            ]["units"]["USD"]
        ]
        self.assertIn("2025-07-25T10:00:00", values)
        self.assertIn("2025-07-25T10:00:00Z", values)
        self.assertNotIn("2025-07-26T10:00:00+08:00", values)
        self.assertNotIn("bad-date-value", values)

    def test_normalize_filed_for_compare_preserves_aware_datetime_utc_order(self):
        earlier = datetime(2025, 7, 25, 23, 30, tzinfo=timezone(timedelta(hours=14)))
        later = datetime(2025, 7, 25, 17, 30, tzinfo=timezone(timedelta(hours=3)))

        self.assertLess(
            _normalize_filed_for_compare(earlier),
            _normalize_filed_for_compare(later),
        )
        self.assertEqual(
            _normalize_filed_for_compare(earlier).tzinfo,
            None,
        )
        self.assertEqual(_normalize_filed_for_compare(earlier).date(), date(2025, 7, 25))
        self.assertEqual(_normalize_filed_for_compare(later).date(), date(2025, 7, 25))

    def test_filter_invalid_as_of_date_raises_value_error(self):
        with self.assertRaises(ValueError):
            filter_company_facts_as_of({}, "07/25/2025")

    def test_filter_excludes_missing_filed(self):
        payload = metric_facts()
        payload["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"][
            "USD"
        ].append(
            {
                "val": 111,
                "start": "2025-01-01",
                "end": "2025-06-30",
                "fy": 2025,
                "fp": "Q2",
                "form": "10-Q",
            }
        )
        filtered = filter_company_facts_as_of(payload, "2025-12-31")
        entries = filtered["facts"]["us-gaap"][
            "RevenueFromContractWithCustomerExcludingAssessedTax"
        ]["units"]["USD"]
        self.assertFalse(any(entry.get("val") == 111 for entry in entries))

    def test_filter_handles_empty_payload_parts(self):
        self.assertEqual(filter_company_facts_as_of({}, "2025-01-01"), {})
        payload = {"facts": {}}
        self.assertEqual(filter_company_facts_as_of(payload, "2025-01-01"), {"facts": {}})
        payload_no_units = {
            "facts": {
                "us-gaap": {"RevenueFromContractWithCustomerExcludingAssessedTax": {}}
            }
        }
        self.assertEqual(
            filter_company_facts_as_of(payload_no_units, "2025-01-01"),
            payload_no_units,
        )

    def test_filter_normalizes_non_dict_units(self):
        payload = {
            "facts": {
                "us-gaap": {
                    "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": []},
                    "NetIncomeLoss": {
                        "units": {
                            "USD": [
                                duration_fact(
                                    80,
                                    "2025-01-01",
                                    "2025-06-30",
                                    2025,
                                    "Q2",
                                    "10-Q",
                                    "2025-07-25",
                                )
                            ]
                        }
                    },
                }
            }
        }

        filtered = filter_company_facts_as_of(payload, "2025-12-31")

        self.assertEqual(
            filtered["facts"]["us-gaap"][
                "RevenueFromContractWithCustomerExcludingAssessedTax"
            ]["units"],
            {},
        )
        self.assertEqual(
            filtered["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"][0]["val"],
            80,
        )

    def test_filter_does_not_modify_original(self):
        payload = metric_facts()
        snapshot = copy.deepcopy(payload)
        _ = filter_company_facts_as_of(payload, "2024-12-31")
        self.assertEqual(payload, snapshot)

    def test_calculate_metrics_as_of_reuses_filter_and_tracks_latest_filed(self):
        payload = metric_facts()
        payload["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"][
            "units"
        ]["USD"].append(
            duration_fact(
                1234,
                "2025-01-01",
                "2025-06-30",
                2025,
                "Q2",
                "10-Q",
                "2025-12-31",
            )
        )

        metrics = calculate_metrics_as_of(payload, "2025-07-30")

        self.assertEqual(metrics["backtest_date"], "2025-07-30")
        self.assertEqual(metrics["latest_source_filed"], "2025-07-25")
        self.assertEqual(metrics["leakage_status"], "ready")
        self.assertIn("revenue_ttm", metrics)

    def test_calculate_metrics_as_of_with_non_dict_units_does_not_crash(self):
        payload = metric_facts()
        payload["facts"]["us-gaap"]["WeirdConcept"] = {"units": []}

        metrics = calculate_metrics_as_of(payload, "2025-12-31")

        self.assertEqual(metrics["backtest_date"], "2025-12-31")
        self.assertEqual(metrics["latest_source_filed"], "2025-07-25")
        self.assertIn("revenue_ttm", metrics)

    def test_calculate_metrics_as_of_normalizes_list_concept_data(self):
        payload = {"facts": {"us-gaap": {"RevenueFromContractWithCustomerExcludingAssessedTax": []}}}
        filtered = filter_company_facts_as_of(payload, "2025-12-31")

        concept = filtered["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]
        self.assertIsInstance(concept, dict)

        metrics = calculate_metrics_as_of(payload, "2025-12-31")
        self.assertEqual(metrics["backtest_date"], "2025-12-31")
        self.assertEqual(metrics["latest_source_filed"], "")
        self.assertEqual(metrics["metrics_period_basis"], "partial")

    def test_calculate_metrics_as_of_handles_non_dict_facts(self):
        payload = {
            "cik": 320193,
            "facts": [],
        }
        metrics = calculate_metrics_as_of(payload, "2025-12-31")

        self.assertEqual(metrics["backtest_date"], "2025-12-31")
        self.assertEqual(metrics["latest_source_filed"], "")
        self.assertEqual(metrics["metrics_period_basis"], "partial")

    def test_calculate_metrics_as_of_payload_type_errors(self):
        with self.assertRaises(TypeError) as context:
            calculate_metrics_as_of(None, "2025-01-01")
        self.assertIn("payload", str(context.exception))

        with self.assertRaises(TypeError) as context:
            calculate_metrics_as_of([], "2025-01-01")
        self.assertIn("payload", str(context.exception))

    def test_calculate_metrics_as_of_uses_iso_datetime_and_standardizes_latest_filed(self):
        payload = metric_facts()
        payload["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"][
            "units"
        ]["USD"].append(
            duration_fact(
                1400,
                "2025-01-01",
                "2025-06-30",
                2025,
                "Q2",
                "10-Q",
                "2025-07-26T15:00:00",
            )
        )
        payload["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"][
            "units"
        ]["USD"].append(
            duration_fact(
                1500,
                "2025-01-01",
                "2025-06-30",
                2025,
                "Q2",
                "10-Q",
                "2025-07-25T15:00:00Z",
            )
        )
        payload["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"][
            "units"
        ]["USD"].append(
            duration_fact(
                1600,
                "2025-01-01",
                "2025-06-30",
                2025,
                "Q2",
                "10-Q",
                "bad-date-value",
            )
        )

        metrics = calculate_metrics_as_of(payload, "2025-07-25T23:00:00")

        self.assertEqual(metrics["latest_source_filed"], "2025-07-25")
        self.assertEqual(metrics["backtest_date"], "2025-07-25T23:00:00")

    def test_latest_source_filed_tiebreak_is_order_independent(self):
        payload = {
            "facts": {
                "us-gaap": {
                    "RevenueFromContractWithCustomerExcludingAssessedTax": {
                        "units": {
                            "USD": [
                                duration_fact(
                                    2000,
                                    "2025-01-01",
                                    "2025-06-30",
                                    2025,
                                    "Q2",
                                    "10-Q",
                                    "2025-07-25T10:00:00",
                                ),
                                duration_fact(
                                    3000,
                                    "2025-01-01",
                                    "2025-06-30",
                                    2025,
                                    "Q2",
                                    "10-K",
                                    "2025-07-25T10:00:00+00:00",
                                ),
                            ]
                        }
                    }
                }
            }
        }

        forward = [
            _latest_source_filed_key(_parse_payload_filed_date(entry["filed"]), entry)
            for entry in payload["facts"]["us-gaap"][
                "RevenueFromContractWithCustomerExcludingAssessedTax"
            ]["units"]["USD"]
        ]
        self.assertGreater(forward[0], forward[1])
        self.assertNotEqual(forward[0], forward[1])

        metrics_forward = calculate_metrics_as_of(
            payload, "2025-07-25T12:00:00+00:00"
        )
        payload["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"][
            "units"
        ]["USD"].reverse()
        metrics_reversed = calculate_metrics_as_of(
            payload, "2025-07-25T12:00:00+00:00"
        )

        self.assertEqual(metrics_forward["latest_source_filed"], "2025-07-25")
        self.assertEqual(metrics_reversed["latest_source_filed"], "2025-07-25")

if __name__ == "__main__":
    unittest.main()
