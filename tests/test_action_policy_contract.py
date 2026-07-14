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
