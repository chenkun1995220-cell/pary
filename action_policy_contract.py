ACTION_POLICY_VERSION = 1
SOURCE_ACTION_POLICY_REQUIRED_FIELDS = (
    "action_policy_version",
    "candidate_review_actionable",
    "weekly_delivery_history_actionable",
)


def action_policy_version(payload):
    if not isinstance(payload, dict) or "action_policy_version" not in payload:
        return None
    value = payload.get("action_policy_version")
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def action_policy_contract_status(payload, require_actionability=False):
    if not isinstance(payload, dict) or "action_policy_version" not in payload:
        return "missing"
    if require_actionability and any(
        field not in payload for field in SOURCE_ACTION_POLICY_REQUIRED_FIELDS
    ):
        return "missing"
    return "valid" if action_policy_version(payload) == ACTION_POLICY_VERSION else "mismatch"
