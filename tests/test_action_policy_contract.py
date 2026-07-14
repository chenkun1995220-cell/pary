import unittest

from action_policy_contract import (
    ACTION_POLICY_VERSION,
    action_policy_contract_status,
    action_policy_version,
)


class ActionPolicyContractTests(unittest.TestCase):
    def test_current_source_contract_is_valid(self):
        payload = {
            "action_policy_version": 1,
            "candidate_review_actionable": False,
            "weekly_delivery_history_actionable": False,
        }
        self.assertEqual(ACTION_POLICY_VERSION, 1)
        self.assertEqual(action_policy_version(payload), 1)
        self.assertEqual(
            action_policy_contract_status(payload, require_actionability=True),
            "valid",
        )

    def test_contract_distinguishes_missing_and_mismatch(self):
        self.assertEqual(action_policy_contract_status({}), "missing")
        self.assertEqual(
            action_policy_contract_status({"action_policy_version": 0}),
            "mismatch",
        )
        self.assertEqual(
            action_policy_contract_status(
                {"action_policy_version": 1},
                require_actionability=True,
            ),
            "missing",
        )
        self.assertIsNone(action_policy_version({"action_policy_version": True}))

    def test_version_parser_rejects_ambiguous_numeric_values(self):
        for value in (True, False, 1.5, 1.9, float("inf"), float("-inf"), 1e309):
            with self.subTest(value=value):
                payload = {"action_policy_version": value}
                self.assertIsNone(action_policy_version(payload))
                self.assertEqual(action_policy_contract_status(payload), "mismatch")

    def test_version_parser_accepts_explicit_integer_representations(self):
        cases = (
            (1, 1),
            (1.0, 1),
            ("1", 1),
            ("+1", 1),
            ("-1", -1),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(
                    action_policy_version({"action_policy_version": value}),
                    expected,
                )

    def test_version_parser_rejects_noncanonical_integer_strings(self):
        for value in ("1.0", "1e0", " 1 ", "1_0", ""):
            with self.subTest(value=value):
                self.assertIsNone(
                    action_policy_version({"action_policy_version": value})
                )
