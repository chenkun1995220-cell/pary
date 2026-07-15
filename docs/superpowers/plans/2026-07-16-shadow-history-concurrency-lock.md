# Shadow History Concurrency Lock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serialize shadow-history read, deduplication, append, and report writes across concurrent processes without changing business decisions.

**Architecture:** Use a standard-library advisory lock on a stable sidecar lock file, then move the complete file-writing workflow into one transaction function called by the CLI. Tests use a separate lock-holder process so blocking and timeout behavior are deterministic.

**Tech Stack:** Python standard library, `msvcrt` on Windows, `fcntl` on POSIX, `unittest`, subprocess integration tests.

## Global Constraints

- No third-party dependency.
- Lock scope includes history reread, payload build, history append, JSON output, and Markdown output.
- Default timeout is 30 seconds and timeout failure writes no history or report output.
- Do not change shadow thresholds, scoring, market data, formal model parameters, or action-policy contracts.
- Keep the persistent `.lock` sidecar; do not delete it on release.

---

### Task 1: Add the cross-platform history lock and transactional writer

**Files:**
- Modify: `one_week_forecast_shadow_disposition.py:1-20,420-490`
- Modify: `tests/test_one_week_forecast_shadow_disposition.py:1-20,200-330`

**Interfaces:**
- Produces: `history_file_lock(history_path, timeout_seconds=30.0, poll_interval=0.05)` context manager.
- Produces: `write_shadow_disposition_files(plan_path, validation_path, history_path, performance_path, output_path, report_path, as_of_date=None, lock_timeout_seconds=30.0) -> dict`.

- [ ] **Step 1: Add deterministic failing tests**

Add a test that starts a subprocess holding `history_file_lock`, waits for a signal file, and asserts a second request raises `TimeoutError` within a short timeout. After the holder exits, assert the lock can be acquired.

Add a transaction test that starts the same holder, launches a subprocess calling `write_shadow_disposition_files`, asserts history/output/report do not exist while the holder owns the lock, then releases the holder and asserts the writer succeeds with one history row.

- [ ] **Step 2: Run the focused test and verify RED**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_one_week_forecast_shadow_disposition
```

Expected: imports for `history_file_lock` and `write_shadow_disposition_files` fail because they do not exist.

- [ ] **Step 3: Implement the lock primitive**

Use `contextlib.contextmanager`, `time.monotonic`, and a stable `<history>.lock` file. On Windows lock byte 0 with `msvcrt.LK_NBLCK`; on POSIX use `fcntl.LOCK_EX | fcntl.LOCK_NB`. Retry until the deadline, then raise `TimeoutError`. Release in `finally` with the matching platform API.

- [ ] **Step 4: Implement and wire the transaction**

Move the current CLI file reads/build/filter/append/output writes into `write_shadow_disposition_files`. Read history only after acquiring the lock and keep the lock until both output files are written. Replace the inline CLI workflow with a call to this function.

- [ ] **Step 5: Run focused and neighboring tests**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_one_week_forecast_shadow_disposition tests.test_extended_shadow_validation_tracker tests.test_automation_self_analysis tests.test_pre_submit_review
```

Expected: PASS with no warnings or leaked subprocesses.

- [ ] **Step 6: Commit code and tests**

```powershell
git add one_week_forecast_shadow_disposition.py tests/test_one_week_forecast_shadow_disposition.py
git commit -m "fix: serialize shadow history writes"
```

---

### Task 2: Verify reporting behavior and publish

**Files:**
- Runtime only: `outputs/automation/one_week_forecast_shadow_parameter_validation_history.jsonl.lock`

**Interfaces:**
- Consumes: the transactional writer from Task 1.
- Produces: unchanged weekly business outputs with concurrency protection.

- [ ] **Step 1: Run the shadow disposition wrapper twice**

Run `scripts/run_one_week_forecast_shadow_disposition.ps1` twice. Assert both exit zero, history remains 8 physical/8 logical rows, duplicate count remains zero, and the second payload reports `history_records_added=0`.

- [ ] **Step 2: Run the fixed nine-step report chain**

Run the report-only chain in its existing order and stop at the first nonzero exit. Do not run market scripts.

- [ ] **Step 3: Verify business invariants**

Assert consistency and pre-submit are `ready`, all six action-policy versions are `1`, candidate count is `65`, top action is `continue_sample_accumulation`, and formal model change remains false.

- [ ] **Step 4: Run full verification**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m py_compile one_week_forecast_shadow_disposition.py
git diff --check
```

Expected: all tests pass, compilation succeeds, and no whitespace errors.

- [ ] **Step 5: Independent review and merge**

Review the complete branch diff for lock correctness, timeout safety, transaction scope, subprocess cleanup, and unchanged business behavior. After approval, push the branch, fast-forward merge into `main`, rerun the full suite on `main`, push `main`, and verify remote divergence is `0 0`.
