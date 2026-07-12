# Unified Human Decision Inbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one audited weekly inbox for candidate-risk authorizations and forecast-shadow approvals without permitting trades or formal-model changes.

**Architecture:** A new focused Python module reads the two authoritative review JSON files and one human-maintained CSV, normalizes stable decision items, validates type-specific decisions, and writes JSON/Markdown/CSV plus an idempotent history ledger. Existing weekly governance modules consume only the normalized inbox summary, and the PowerShell reporting bundle runs the inbox after both source reviews and before action items.

**Tech Stack:** Python 3 standard library, `unittest`, CSV/JSON/Markdown artifacts, Windows PowerShell 5.1 wrappers.

## Global Constraints

- `trade_execution_allowed=false`, `formal_model_change_allowed=false`, and `formal_model_conclusion_allowed=false` in every output path.
- Human authorization may change research or shadow-validation state only; it must never rewrite candidate scores, buy prices, target prices, source reviews, or `valuation_trend_v1`.
- Current source batches produce new stable keys; decisions from older source dates must not carry forward.
- Missing or invalid decisions remain pending; conflicting decisions never resolve by last-write-wins.
- Candidate delivery may remain available while decisions are pending, but missing, stale, or structurally invalid source reviews block governance closeout.
- Use test-driven development: verify each new test fails for the intended missing behavior before production edits.

---

### Task 1: Core Inbox Normalization and Renderers

**Files:**
- Create: `human_decision_inbox.py`
- Create: `scripts/run_human_decision_inbox.ps1`
- Create: `tests/test_human_decision_inbox.py`

**Interfaces:**
- Consumes: `latest_candidate_risk_resolution_review.json`, `latest_one_week_forecast_shadow_disposition.json`, and optional `data/manual/human_decision_authorizations.csv`.
- Produces: `build_human_decision_inbox(project_root=".", candidate_risk_review="outputs/automation/latest_candidate_risk_resolution_review.json", shadow_disposition="outputs/automation/latest_one_week_forecast_shadow_disposition.json", authorizations="data/manual/human_decision_authorizations.csv", as_of_date=None) -> dict`.
- Produces: `render_human_decision_inbox(payload) -> str`, `write_inbox_csv(payload, path)`, `write_authorization_template(path)`, and CLI outputs defined in the design.

- [ ] **Step 1: Write failing tests for the six-item current-shape inbox**

Create fixtures with five candidate items where `manual_decision_required=True` and one shadow item where `disposition="pending_human_approval"`. Add assertions:

```python
payload = build_human_decision_inbox(root, as_of_date="2026-07-12")
self.assertEqual(payload["inbox_schema"], "human_decision_inbox")
self.assertEqual(payload["item_count"], 6)
self.assertEqual(payload["pending_count"], 6)
self.assertEqual(payload["decided_count"], 0)
self.assertEqual(payload["status"], "manual_review_needed")
self.assertEqual(
    {item["item_type"] for item in payload["items"]},
    {"candidate_risk", "forecast_shadow"},
)
self.assertFalse(payload["trade_execution_allowed"])
self.assertFalse(payload["formal_model_change_allowed"])
self.assertFalse(payload["formal_model_conclusion_allowed"])
```

Also assert candidate keys equal `candidate_risk|港股周筛|06110.HK|2026-07-12` and the shadow key equals `forecast_shadow|shadow_demote_down_signal_to_neutral|2026-07-12`.

- [ ] **Step 2: Run the new test and verify RED**

Run: `python -m unittest tests.test_human_decision_inbox -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'human_decision_inbox'`.

- [ ] **Step 3: Implement minimal normalization and state calculation**

Implement these constants and entry point:

```python
INBOX_SCHEMA = "human_decision_inbox"
INBOX_VERSION = 1
BOUNDARY = "human_decision_only_no_trade_or_model_change"

def build_human_decision_inbox(
    project_root=".",
    candidate_risk_review="outputs/automation/latest_candidate_risk_resolution_review.json",
    shadow_disposition="outputs/automation/latest_one_week_forecast_shadow_disposition.json",
    authorizations="data/manual/human_decision_authorizations.csv",
    as_of_date=None,
):
    root = Path(project_root)
    risk_payload = _read_json(root / candidate_risk_review)
    shadow_payload = _read_json(root / shadow_disposition)
    effective_date = str(as_of_date or max(risk_payload.get("as_of_date", ""), shadow_payload.get("as_of_date", "")))
    items = _candidate_items(risk_payload) + _shadow_items(shadow_payload)
    decisions, decision_issues = validate_authorizations(items, _read_csv(root / authorizations))
    return _build_payload(effective_date, items, decisions, decision_issues)
```

Normalize candidate evidence fields from each source item and shadow evidence from each `candidate_dispositions` item. Include `allowed_decisions`, `decision_status="pending"`, source path/date, and all three hard-false safety fields per item and at the top level. Compute `blocked` only for invalid sources, `manual_review_needed` for pending items, and `ready` for an empty inbox.

- [ ] **Step 4: Add renderers, CLI, and PowerShell wrapper**

The CLI accepts `--project-root`, both source paths, authorization path, JSON output, Markdown report, CSV output, template path, history path, and `--as-of-date`. The wrapper resolves the bundled workspace Python using the same pattern as `scripts/run_candidate_risk_resolution_review.ps1`, then invokes:

```powershell
& $Python $Script `
  --project-root $ProjectRoot `
  --output $Output `
  --report $Report `
  --csv-output $CsvOutput `
  --authorizations $Authorizations `
  --authorization-template $AuthorizationTemplate `
  --history $History
```

- [ ] **Step 5: Run tests and verify GREEN**

Run: `python -m unittest tests.test_human_decision_inbox -v`

Expected: all Task 1 tests PASS and generated Markdown contains both item types and the no-trade/no-model-change boundary.

- [ ] **Step 6: Commit Task 1**

```powershell
git add human_decision_inbox.py scripts/run_human_decision_inbox.ps1 tests/test_human_decision_inbox.py
git commit -m "feat: add unified human decision inbox"
```

---

### Task 2: Decision Validation and Idempotent Audit History

**Files:**
- Modify: `human_decision_inbox.py`
- Modify: `tests/test_human_decision_inbox.py`
- Generate: `outputs/automation/human_decision_history.csv`

**Interfaces:**
- Consumes: authorization rows with `decision_key`, `decision`, `decided_by`, `decided_at`, `decision_reason`, and `boundary_acknowledgement`.
- Produces: `validate_authorizations(items, rows) -> tuple[dict, list[str]]` keyed by stable decision key.
- Produces: `append_decision_history(payload, path) -> int`, returning the number of newly appended rows.

- [ ] **Step 1: Write failing tests for valid, invalid, conflicting, and stale decisions**

Add one legal candidate decision and one legal shadow decision:

```python
{
    "decision_key": "candidate_risk|港股周筛|06110.HK|2026-07-12",
    "decision": "approve_for_continued_research",
    "decided_by": "user",
    "decided_at": "2026-07-12T15:30:00+08:00",
    "decision_reason": "研究底稿完整，继续观察基本面",
    "boundary_acknowledgement": "human_decision_only_no_trade_or_model_change",
}
```

Assert legal decisions become `decision_status="decided"`; a shadow decision used on a candidate key, an empty reason, a wrong boundary, and two different decisions for one key remain pending and increment `invalid_decision_count`. Add a prior-week decision ending in `2026-07-05` and assert it does not apply to the `2026-07-12` item.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m unittest tests.test_human_decision_inbox.HumanDecisionInboxTests.test_validates_type_specific_decisions tests.test_human_decision_inbox.HumanDecisionInboxTests.test_rejects_conflicts_and_old_batch_decisions -v`

Expected: FAIL because authorization validation is not implemented.

- [ ] **Step 3: Implement exact decision enums and conservative validation**

Use immutable sets:

```python
CANDIDATE_DECISIONS = {
    "approve_for_continued_research",
    "downgrade_to_watchlist",
    "reject_candidate_research",
    "continue_observation",
}
SHADOW_DECISIONS = {
    "approve_for_extended_shadow_validation",
    "reject_shadow_candidate",
    "continue_observation",
}
```

Group rows by key before validation. Unknown keys are ignored as historical rows; duplicate identical rows collapse; different decisions for one current key create `conflicting_authorizations:<key>`. Never mutate either source JSON.

- [ ] **Step 4: Write the failing idempotency test**

Call `append_decision_history` twice against the same temporary history file and assert the first return is `2`, the second is `0`, and the CSV still has exactly two data rows. Assert history identity includes `decision_key`, `decision`, and `decided_at`.

- [ ] **Step 5: Implement template creation and append-only history**

Write a UTF-8 BOM CSV template only when the authorization file is absent. Append validated decisions using a deterministic history key; preserve existing rows; write the full file atomically through a sibling temporary path and `Path.replace`.

- [ ] **Step 6: Run tests and verify GREEN**

Run: `python -m unittest tests.test_human_decision_inbox -v`

Expected: all tests PASS, including duplicate-run history idempotency.

- [ ] **Step 7: Commit Task 2**

```powershell
git add human_decision_inbox.py tests/test_human_decision_inbox.py
git commit -m "feat: validate and audit human decisions"
```

---

### Task 3: Governance Consumers and Quality Gates

**Files:**
- Modify: `weekly_action_items.py`
- Modify: `weekly_conclusion_report.py`
- Modify: `medium_term_goal_review.py`
- Modify: `pre_submit_review.py`
- Modify: `tests/test_weekly_action_items.py`
- Modify: `tests/test_weekly_conclusion_report.py`
- Modify: `tests/test_medium_term_goal_review.py`
- Modify: `tests/test_pre_submit_review.py`

**Interfaces:**
- Consumes: `outputs/automation/latest_human_decision_inbox.json` schema version 1.
- Produces: one authoritative pending/decided/invalid count across action items, conclusion, medium-term governance state, and pre-submit checks.

- [ ] **Step 1: Add failing consumer tests**

In each test fixture write:

```python
{
    "inbox_schema": "human_decision_inbox",
    "inbox_version": 1,
    "as_of_date": "2026-07-12",
    "status": "manual_review_needed",
    "item_count": 6,
    "pending_count": 6,
    "decided_count": 0,
    "invalid_decision_count": 0,
    "issues": [],
    "trade_execution_allowed": False,
    "formal_model_change_allowed": False,
    "formal_model_conclusion_allowed": False,
}
```

Assert weekly actions contain one `review_human_decision_inbox` item, the conclusion summary reports 6/0/0, the governance goal current state includes the same counts, and pre-submit remains `ready` for valid pending decisions but rejects unsafe boundaries, mismatched totals, stale dates, invalid decisions, or `blocked` status.

- [ ] **Step 2: Run consumer tests and verify RED**

Run: `python -m unittest tests.test_weekly_action_items tests.test_weekly_conclusion_report tests.test_medium_term_goal_review tests.test_pre_submit_review -v`

Expected: new assertions FAIL because the inbox is not yet consumed.

- [ ] **Step 3: Implement one normalized inbox reader per module boundary**

Add the path constant `outputs/automation/latest_human_decision_inbox.json`. Weekly actions add exactly one governance item when pending or invalid decisions exist. The conclusion copies normalized counts into `integrated_review_summary`. The medium-term governance goal exposes counts and chooses `review_human_decision_inbox` when pending. Pre-submit validates schema/version/date/counts/issues and hard-false boundaries without treating ordinary pending decisions as a delivery blocker.

- [ ] **Step 4: Run consumer tests and verify GREEN**

Run: `python -m unittest tests.test_weekly_action_items tests.test_weekly_conclusion_report tests.test_medium_term_goal_review tests.test_pre_submit_review -v`

Expected: all four modules' tests PASS and report the same inbox counts.

- [ ] **Step 5: Commit Task 3**

```powershell
git add weekly_action_items.py weekly_conclusion_report.py medium_term_goal_review.py pre_submit_review.py tests/test_weekly_action_items.py tests/test_weekly_conclusion_report.py tests/test_medium_term_goal_review.py tests/test_pre_submit_review.py
git commit -m "feat: surface human decisions in weekly governance"
```

---

### Task 4: Weekly Bundle, Documentation, and Real-Artifact Acceptance

**Files:**
- Modify: `scripts/run_weekly_reporting_bundle.ps1`
- Modify: `tests/test_weekly_automation.py`
- Modify: `docs/美股每周自动运行说明.md`
- Modify: `docs/提交前复核清单.md`
- Modify: `docs/中期目标进度看板.md`
- Generate: `data/manual/human_decision_authorizations.csv`
- Generate: allowed `outputs/automation/latest_human_decision_inbox.*` artifacts and `human_decision_inbox.csv`

**Interfaces:**
- Consumes: the wrapper from Task 1.
- Produces: weekly execution ordering where the inbox runs after `run_candidate_risk_resolution_review` and `run_one_week_forecast_shadow_disposition`, and before `show_weekly_action_items` and all closeout consumers.

- [ ] **Step 1: Write the failing static-order test**

Add assertions:

```python
self.assertIn("run_human_decision_inbox.ps1", bundle)
inbox_index = bundle.index("run_human_decision_inbox.ps1")
self.assertGreater(inbox_index, bundle.index("run_candidate_risk_resolution_review.ps1"))
self.assertGreater(inbox_index, bundle.index("run_one_week_forecast_shadow_disposition.ps1"))
self.assertLess(inbox_index, bundle.index("show_weekly_action_items.ps1"))
```

- [ ] **Step 2: Run the static test and verify RED**

Run: `python -m unittest tests.test_weekly_automation.WeeklyAutomationTests.test_weekly_bundle_runs_human_decision_inbox_before_actions -v`

Expected: FAIL because the wrapper is absent from the bundle.

- [ ] **Step 3: Insert the critical bundle step and document the contract**

Add one critical step labeled `run_human_decision_inbox`. Document the four generated outputs, the single manual input, stable key/date behavior, valid decision enums, history idempotency, pending-versus-blocked behavior, and all three prohibited automatic effects. Update the checklists to require synchronized counts and safe boundaries.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m unittest tests.test_human_decision_inbox tests.test_weekly_action_items tests.test_weekly_conclusion_report tests.test_medium_term_goal_review tests.test_pre_submit_review tests.test_weekly_automation -v`

Expected: all focused tests PASS.

- [ ] **Step 5: Generate this week's real inbox without rerunning market fetches**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\run_human_decision_inbox.ps1
```

Expected: `status=manual_review_needed`, `item_count=6`, `pending_count=6`, `decided_count=0`, `invalid_decision_count=0`; the five candidate items and one forecast-shadow item all use `2026-07-12` source keys; all three safety flags are false.

- [ ] **Step 6: Refresh downstream governance only**

Run the existing non-market reporting wrappers in bundle order from weekly action items through the final pre-submit review. Do not run `run_us_universe_weekly.ps1`, `run_cn_weekly.ps1`, or `run_hk_weekly.ps1`.

Expected: candidate total remains 65, delivery remains available, inbox counts are synchronized, and formal-model change remains false.

- [ ] **Step 7: Run full verification**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Expected: all tests PASS with no failures or errors. Then run `git diff --check` and verify `git status --short` contains only files intentionally changed or approved generated artifacts.

- [ ] **Step 8: Commit and push the completed feature**

```powershell
git add human_decision_inbox.py scripts/run_human_decision_inbox.ps1 weekly_action_items.py weekly_conclusion_report.py medium_term_goal_review.py pre_submit_review.py scripts/run_weekly_reporting_bundle.ps1 tests/test_human_decision_inbox.py tests/test_weekly_action_items.py tests/test_weekly_conclusion_report.py tests/test_medium_term_goal_review.py tests/test_pre_submit_review.py tests/test_weekly_automation.py docs/美股每周自动运行说明.md docs/提交前复核清单.md docs/中期目标进度看板.md data/manual/human_decision_authorizations.csv
git commit -m "feat: integrate unified human decision workflow"
git push
```

Do not stage runtime quote snapshots, market candidate pools, logs, or unrelated weekly output churn.
