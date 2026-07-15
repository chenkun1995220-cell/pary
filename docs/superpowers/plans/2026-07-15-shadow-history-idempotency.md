# Shadow History Idempotency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent identical weekly shadow-validation reruns from appending duplicate JSONL history while preserving changed same-key revisions.

**Architecture:** Add one pure filtering function beside the existing history helpers and make both payload construction and CLI persistence use it. Keep the existing last-record-wins logical history behavior, then compact the current runtime file once with a timestamped backup.

**Tech Stack:** Python standard library, `unittest`, JSONL runtime artifacts, PowerShell wrappers.

## Global Constraints

- Do not fetch market data, rerun scoring, modify formal model parameters, or change shadow classification thresholds.
- The history key is exactly `(evaluation_as_of_date, action_code)`.
- Identical same-key rows are idempotent; changed same-key rows remain append-only revisions.
- `history_records_added` equals the physical rows appended by that invocation.
- Back up the runtime JSONL before one-time compaction; runtime artifacts are not committed.

---

### Task 1: Make shadow history append idempotent

**Files:**
- Modify: `one_week_forecast_shadow_disposition.py:90-125,260-325,432-444`
- Modify: `tests/test_one_week_forecast_shadow_disposition.py:107-245`

**Interfaces:**
- Consumes: existing history rows and `validation_history_records(validation)` output.
- Produces: `history_rows_to_append(history_rows, new_rows) -> list[dict]`.

- [ ] **Step 1: Add failing tests**

Add a CLI test that runs the command twice with identical inputs and asserts:

```python
self.assertEqual(len(history.read_text(encoding="utf-8-sig").splitlines()), 1)
self.assertEqual(second_payload["history_records_added"], 0)
```

Add a unit test proving a changed row with the same key is returned and becomes the logical latest row:

```python
pending = history_rows_to_append([original], [revised])
self.assertEqual(pending, [revised])
self.assertEqual(logical_history([original, *pending])[0], [revised])
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_one_week_forecast_shadow_disposition
```

Expected: the second CLI run appends another physical row and reports one added record.

- [ ] **Step 3: Implement the minimal filter**

Add canonical comparison and filtering:

```python
def _history_key(row):
    key = (
        str(row.get("evaluation_as_of_date", "") or ""),
        str(row.get("action_code", "") or ""),
    )
    return key if all(key) else None


def _canonical_history_row(row):
    return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def history_rows_to_append(history_rows, new_rows):
    latest = {}
    for row in history_rows or []:
        if isinstance(row, dict) and (key := _history_key(row)):
            latest[key] = _canonical_history_row(row)
    pending = []
    for row in new_rows or []:
        if not isinstance(row, dict) or not (key := _history_key(row)):
            continue
        canonical = _canonical_history_row(row)
        if latest.get(key) == canonical:
            continue
        pending.append(row)
        latest[key] = canonical
    return pending
```

Use `pending_rows` in `build_shadow_disposition` and in the CLI append path. Set
`history_records_added = len(pending_rows)`.

- [ ] **Step 4: Run focused and neighboring tests**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_one_week_forecast_shadow_disposition tests.test_extended_shadow_validation_tracker tests.test_automation_self_analysis tests.test_pre_submit_review
```

Expected: PASS.

- [ ] **Step 5: Commit code and tests**

```powershell
git add one_week_forecast_shadow_disposition.py tests/test_one_week_forecast_shadow_disposition.py
git commit -m "fix: make shadow history append idempotent"
```

---

### Task 2: Compact existing duplicate runtime history safely

**Files:**
- Runtime only: `outputs/automation/one_week_forecast_shadow_parameter_validation_history.jsonl`
- Runtime backup: same filename plus `.pre-idempotency-<timestamp>.bak`

**Interfaces:**
- Consumes: existing JSONL and `logical_history(rows)`.
- Produces: backup plus compacted last-record-per-key JSONL.

- [ ] **Step 1: Capture pre-compaction metrics**

Read all valid rows and assert 32 physical rows, 8 logical rows, and 24 duplicates before changing the file.

- [ ] **Step 2: Back up and compact**

Copy the original bytes to a timestamped backup, call `logical_history(rows)`, and atomically replace the source with the eight logical rows serialized as UTF-8 JSONL.

- [ ] **Step 3: Verify runtime integrity**

Assert the backup exists, the compacted file has 8 physical rows and 8 logical rows, duplicate count is zero, and the canonical logical rows before and after are identical.

- [ ] **Step 4: Rebuild report-only outputs**

Run `scripts/run_one_week_forecast_shadow_disposition.ps1`, then the fixed nine-step report chain. Stop on the first nonzero exit. Do not run market scripts.

- [ ] **Step 5: Verify final artifacts**

Assert consistency and pre-submit are `ready`, six action policy versions are `1`, candidate count is `65`, the top action remains `continue_sample_accumulation`, and shadow history adds no duplicate for the current batch.

---

### Task 3: Final verification and publication

**Files:**
- No additional production files.

**Interfaces:**
- Consumes: completed code, tests, and runtime verification evidence.
- Produces: reviewed commit on `main` and synchronized GitHub state.

- [ ] **Step 1: Run the full suite and static checks**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m py_compile one_week_forecast_shadow_disposition.py
git diff --check
```

Expected: all tests PASS, compilation succeeds, and no whitespace errors.

- [ ] **Step 2: Request an independent code review**

Review the branch diff against this plan, focusing on idempotency, preservation of changed revisions, report/write count consistency, and runtime-history safety.

- [ ] **Step 3: Push and fast-forward merge after approval**

Push the feature branch, fast-forward merge it into `main`, rerun the full suite on `main`, push `main`, and verify `HEAD...origin/main` is `0 0`.
