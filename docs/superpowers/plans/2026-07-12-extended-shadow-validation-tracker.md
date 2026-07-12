# Extended Shadow Validation Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Track three independent post-approval weekly shadow-validation batches and require reapproval after completion or an early safety stop.

**Architecture:** A focused tracker reads the immutable human-decision history and existing shadow-validation history, derives one state per approved action code, and emits normalized JSON/Markdown/CSV. Existing weekly governance modules consume that single tracker output; no component mutates source histories, candidate outputs, or the formal model.

**Tech Stack:** Python 3 standard library, `unittest`, CSV/JSON/JSONL/Markdown artifacts, Windows PowerShell 5.1.

## Global Constraints

- An approval covers exactly 3 independent evaluable batches strictly after its authorization source date.
- A severe market deterioration pauses immediately; 2 consecutive negative evaluable batches pause early.
- `not_evaluable` batches remain auditable but do not consume the 3-batch allowance.
- Duplicate `action_code|evaluation_as_of_date` batches never increase counts.
- Every output fixes `trade_execution_allowed=false`, `formal_model_change_allowed=false`, and `formal_model_conclusion_allowed=false`.
- No step may fetch market data, rewrite validation history, alter candidates, or modify `valuation_trend_v1`.
- Every production behavior starts with a failing test that is verified before implementation.

---

### Task 1: Core Authorization and Batch Normalization

**Files:**
- Create: `extended_shadow_validation_tracker.py`
- Create: `scripts/run_extended_shadow_validation_tracker.ps1`
- Create: `tests/test_extended_shadow_validation_tracker.py`

**Interfaces:**
- Consumes: `human_decision_history.csv`, `one_week_forecast_shadow_parameter_validation_history.jsonl`, `latest_human_decision_inbox.json`, and `latest_one_week_forecast_shadow_disposition.json`.
- Produces: `build_extended_shadow_validation_tracker(project_root=".", decision_history="outputs/automation/human_decision_history.csv", validation_history="outputs/automation/one_week_forecast_shadow_parameter_validation_history.jsonl", decision_inbox="outputs/automation/latest_human_decision_inbox.json", shadow_disposition="outputs/automation/latest_one_week_forecast_shadow_disposition.json", as_of_date=None) -> dict`.
- Produces: `render_extended_shadow_validation_tracker(payload) -> str` and `write_batch_csv(payload, path)`.

- [ ] **Step 1: Write the failing current-baseline test**

Create a legal approval dated `2026-07-12` for `shadow_demote_down_signal_to_neutral` and three validation-history batches dated on or before `2026-07-12`. Assert:

```python
payload = build_extended_shadow_validation_tracker(root, as_of_date="2026-07-12")
item = payload["items"][0]
self.assertEqual(payload["status"], "active")
self.assertEqual(item["post_approval_history_batch_count"], 0)
self.assertEqual(item["evaluable_batch_count"], 0)
self.assertEqual(item["remaining_evaluable_batch_count"], 3)
self.assertEqual(item["status"], "active")
self.assertEqual(item["recommended_action"], "continue_extended_shadow_validation")
self.assertFalse(payload["formal_model_change_allowed"])
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m unittest tests.test_extended_shadow_validation_tracker -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'extended_shadow_validation_tracker'`.

- [ ] **Step 3: Implement strict input readers and stable identities**

Implement constants:

```python
TRACKER_SCHEMA = "extended_shadow_validation_tracker"
TRACKER_VERSION = 1
APPROVAL_DECISION = "approve_for_extended_shadow_validation"
BOUNDARY = "human_decision_only_no_trade_or_model_change"
REQUIRED_BATCHES = 3
```

Parse action code and authorization date from `forecast_shadow|<action_code>|<date>`. Accept only matching history rows with the approved decision and boundary. Deduplicate validation rows first by their existing logical row identity, then aggregate batches by `action_code|evaluation_as_of_date`.

- [ ] **Step 4: Implement the active 0/3 payload and renderers**

Each item includes authorization metadata, post-approval history count, evaluable/positive/negative/not-evaluable/severe counts, consecutive negatives, remaining count, state, action, and batch summaries. Add a CLI with explicit paths for all four inputs and three outputs. Add a PowerShell wrapper using the bundled Python path and project-relative defaults.

- [ ] **Step 5: Run tests and verify GREEN**

Run: `python -m unittest tests.test_extended_shadow_validation_tracker -v`

Expected: the current-baseline test passes and the Markdown states `0/3` with all three safety flags false.

- [ ] **Step 6: Commit Task 1**

```powershell
git add extended_shadow_validation_tracker.py scripts/run_extended_shadow_validation_tracker.ps1 tests/test_extended_shadow_validation_tracker.py
git commit -m "feat: add extended shadow validation tracker"
```

---

### Task 2: State Machine, Stops, and Conservative Failures

**Files:**
- Modify: `extended_shadow_validation_tracker.py`
- Modify: `tests/test_extended_shadow_validation_tracker.py`

**Interfaces:**
- Produces: `classify_batch(rows) -> dict` with `classification`, aggregate sample/rate fields, and severe-market details.
- Produces: `classify_tracker_state(batches) -> tuple[str, str]` returning status and recommended action.

- [ ] **Step 1: Write failing tests for all four batch classes**

Add fixtures asserting positive when aggregate delta is greater than 0, negative when it is less than or equal to 0, not-evaluable when comparable sample count is 0, and severe deterioration whenever any market row carries a severe deterioration marker.

- [ ] **Step 2: Run classification tests and verify RED**

Run: `python -m unittest tests.test_extended_shadow_validation_tracker.ExtendedShadowValidationTrackerTests.test_classifies_post_approval_batches -v`

Expected: FAIL because classification functions are absent.

- [ ] **Step 3: Implement batch classification and non-consuming not-evaluable batches**

Aggregate hit counts and comparable samples across an action/date batch. Compute aggregate delta from aggregate rates, not an unweighted average of market deltas. Set `evaluable_batch_count` to positive plus negative batches only.

- [ ] **Step 4: Write failing tests for completion and both early stops**

Assert three evaluable batches yield `ready_for_reapproval`; one severe batch yields `paused_severe_deterioration`; and two latest consecutive evaluable negative batches yield `paused_two_consecutive_negative_batches`. Insert a not-evaluable batch between two negatives and assert it does not break their evaluable-sequence adjacency.

- [ ] **Step 5: Implement state priority and remaining-count logic**

Apply priority `blocked` > severe > two consecutive negative > three evaluable > active > inactive. Clamp remaining count at 0. Never emit a formal-model action.

- [ ] **Step 6: Write failing tests for duplicate, malformed, and mismatched inputs**

Assert duplicate action/date rows count once; malformed decision history, conflicting authorization rows, invalid boundary, malformed JSONL, and a disposition action that cannot match authorization produce `blocked` with stable reason codes.

- [ ] **Step 7: Implement conservative validation and verify GREEN**

Run: `python -m unittest tests.test_extended_shadow_validation_tracker -v`

Expected: all state, stop, deduplication, and failure-boundary tests pass.

- [ ] **Step 8: Commit Task 2**

```powershell
git add extended_shadow_validation_tracker.py tests/test_extended_shadow_validation_tracker.py
git commit -m "feat: enforce extended shadow validation stops"
```

---

### Task 3: Weekly Governance Integration

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
- Consumes: `outputs/automation/latest_extended_shadow_validation_tracker.json` schema version 1.
- Produces: synchronized tracker status, progress, remaining batches, stop reason, and recommended action across all governance outputs.

- [ ] **Step 1: Add failing consumer tests**

Use an `active` tracker at 1/3 and assert no approval action is created, the conclusion displays `1/3`, and the forecast goal exposes the same progress. Use `ready_for_reapproval` and both paused states to assert exactly one `review_extended_shadow_validation_results` or `request_shadow_safety_reapproval` action. Assert pre-submit accepts `active` but rejects malformed counts, unsafe flags, blocked state, duplicate batch keys, and stale dates.

- [ ] **Step 2: Run consumer suites and verify RED**

Run: `python -m unittest tests.test_weekly_action_items tests.test_weekly_conclusion_report tests.test_medium_term_goal_review tests.test_pre_submit_review -v`

Expected: new tracker assertions fail because no consumer reads the artifact.

- [ ] **Step 3: Implement normalized consumption**

Add one tracker path constant per module. Weekly actions route only terminal or paused states to human review. The conclusion preserves raw preapproval disposition and adds extension progress. The forecast goal exposes progress without raising its completion percentage solely from synthetic or not-evaluable rows. Pre-submit validates schema, version, freshness, unique keys, counts, state/action compatibility, and hard-false boundaries.

- [ ] **Step 4: Run consumer suites and verify GREEN**

Run: `python -m unittest tests.test_weekly_action_items tests.test_weekly_conclusion_report tests.test_medium_term_goal_review tests.test_pre_submit_review -v`

Expected: all suites pass and share the same tracker counts.

- [ ] **Step 5: Commit Task 3**

```powershell
git add weekly_action_items.py weekly_conclusion_report.py medium_term_goal_review.py pre_submit_review.py tests/test_weekly_action_items.py tests/test_weekly_conclusion_report.py tests/test_medium_term_goal_review.py tests/test_pre_submit_review.py
git commit -m "feat: surface extended shadow validation progress"
```

---

### Task 4: Weekly Bundle, Documentation, and Real Acceptance

**Files:**
- Modify: `scripts/run_weekly_reporting_bundle.ps1`
- Modify: `tests/test_weekly_automation.py`
- Modify: `docs/美股每周自动运行说明.md`
- Modify: `docs/提交前复核清单.md`
- Modify: `docs/中期目标进度看板.md`

**Interfaces:**
- Consumes: the Task 1 wrapper.
- Produces: tracker execution after the human-decision inbox and before refreshed self-analysis/action items.

- [ ] **Step 1: Write the failing static-order test**

Assert `run_extended_shadow_validation_tracker.ps1` appears after `run_human_decision_inbox.ps1` and before `refresh_self_analysis_after_shadow_disposition` and `show_weekly_action_items.ps1`.

- [ ] **Step 2: Run the static test and verify RED**

Run: `python -m unittest tests.test_weekly_automation.WeeklyAutomationTests.test_weekly_bundle_runs_extended_shadow_tracker_before_governance -v`

Expected: FAIL because the wrapper is absent from the bundle.

- [ ] **Step 3: Add the critical bundle step and document operations**

Document authorization scope, 3-batch counting, deduplication, not-evaluable handling, both stop rules, commands, artifacts, governance behavior, and all prohibited effects. Add checklist requirements for status/action compatibility and safety flags.

- [ ] **Step 4: Run focused verification**

Run: `python -m unittest tests.test_extended_shadow_validation_tracker tests.test_weekly_action_items tests.test_weekly_conclusion_report tests.test_medium_term_goal_review tests.test_pre_submit_review tests.test_weekly_automation -v`

Expected: all focused tests pass.

- [ ] **Step 5: Generate the real tracker without market refresh**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\run_extended_shadow_validation_tracker.ps1
```

Expected: current approved action is `active`, post-approval progress is `0/3`, no stop rule is triggered, and all safety flags are false.

- [ ] **Step 6: Refresh downstream governance only**

Run existing wrappers from self-analysis through final pre-submit review without invoking any market weekly script.

Expected: candidate total remains 65, pre-submit remains `ready`, weekly actions contain only real open work, and the conclusion displays the tracker baseline.

- [ ] **Step 7: Run full verification and inspect scope**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Expected: all tests pass. Then run `git diff --check` and confirm only planned code, tests, docs, and approved configuration artifacts changed.

- [ ] **Step 8: Commit and push**

```powershell
git add extended_shadow_validation_tracker.py scripts/run_extended_shadow_validation_tracker.ps1 weekly_action_items.py weekly_conclusion_report.py medium_term_goal_review.py pre_submit_review.py scripts/run_weekly_reporting_bundle.ps1 tests/test_extended_shadow_validation_tracker.py tests/test_weekly_action_items.py tests/test_weekly_conclusion_report.py tests/test_medium_term_goal_review.py tests/test_pre_submit_review.py tests/test_weekly_automation.py docs/美股每周自动运行说明.md docs/提交前复核清单.md docs/中期目标进度看板.md
git commit -m "feat: track post-approval shadow validation"
git push
```

Do not stage market snapshots, candidate pools, logs, or unrelated automation output churn.
