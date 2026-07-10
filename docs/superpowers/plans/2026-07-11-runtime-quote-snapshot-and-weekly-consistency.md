# 行情快照与周交付一致性 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将可重建的美股行情快照迁出 Git，并让每周提交前复核验证三市场日期、候选数和交付结论一致。

**Architecture:** 美股周任务把快照写到被忽略的 `outputs/us_universe/market_quotes.csv`，并在运行摘要记录审计元数据。新的 `weekly_artifact_consistency.py` 独立读取运行产物并生成机器可读复核，周收口在交付验收后执行它，`pre_submit_review.py` 将其作为必需输入。

**Tech Stack:** Python 3 标准库、PowerShell、CSV、JSON、unittest。

## Global Constraints

- 不自动提交或推送运行数据。
- 不修改正式估值、筛选或预测模型参数。
- 三市场运行时刻可以不同，但运行日期必须属于同一自然日，且每个市场必须在 8 天新鲜度窗口内。
- 候选数必须在运行摘要、候选池、统一结论和交付验收之间一致。
- 主工作区已有未提交改动不得进入本任务提交。

---

### Task 1: 迁移美股运行行情快照

**Files:**
- Modify: `scripts/run_us_universe_weekly.ps1`
- Modify: `tests/test_weekly_automation.py`
- Delete: `data/samples/us_universe_quotes.csv`
- Modify: `docs/美股扩展股票池V1.md`

**Interfaces:**
- Produces: `outputs/us_universe/market_quotes.csv` and summary fields `Quote snapshot policy`, `Quote snapshot file`, `Quote snapshot rows`, `Quote date min`, `Quote date max`, `Quote snapshot sha256`.

- [ ] **Step 1: Write failing path and summary tests**

Add assertions that the weekly script contains:

```python
self.assertIn('Join-Path $OutputRoot "market_quotes.csv"', script)
self.assertIn("Quote snapshot policy: runtime_output_only", script)
self.assertIn("Quote snapshot sha256", script)
self.assertNotIn('data\\samples\\us_universe_quotes.csv', script)
```

- [ ] **Step 2: Run the failing test**

Run: `python -m unittest tests.test_weekly_automation`

Expected: FAIL because the script still writes the tracked sample path.

- [ ] **Step 3: Implement runtime path and audit metadata**

Set `$Quotes = Join-Path $OutputRoot "market_quotes.csv"` after resolving `$OutputRoot`. After quote generation, import the CSV and calculate row count, non-empty quote date min/max and SHA-256 with `Get-FileHash`. Append the six exact fields to `latest_run_summary.md`.

- [ ] **Step 4: Remove tracked snapshot and update current user documentation**

Delete `data/samples/us_universe_quotes.csv`. Update manual examples to use `outputs/us_universe/market_quotes.csv` and explain that it is rebuilt by the weekly task and excluded from Git.

- [ ] **Step 5: Run tests and commit**

Run: `python -m unittest tests.test_weekly_automation tests.test_quote_auto_filler`

Expected: all tests pass.

Commit: `feat: move us quote snapshot to runtime outputs`

### Task 2: 新增周产物一致性复核

**Files:**
- Create: `weekly_artifact_consistency.py`
- Create: `scripts/run_weekly_artifact_consistency.ps1`
- Create: `tests/test_weekly_artifact_consistency.py`

**Interfaces:**
- Produces: `build_weekly_artifact_consistency(project_root: Path, as_of_date: str, max_age_days: int = 8) -> dict`.
- Produces JSON schema `weekly_artifact_consistency`, version `1`, status `ready|needs_attention`.

- [ ] **Step 1: Write failing happy-path test**

Create temporary US/CN/HK summaries and candidate pools, a runtime quote snapshot, weekly conclusion and delivery JSON. Assert:

```python
self.assertEqual(payload["status"], "ready")
self.assertEqual(payload["candidate_count_total"], 6)
self.assertEqual(payload["runtime_quote_snapshot"]["git_policy"], "runtime_output_only")
self.assertEqual(payload["issues"], [])
```

- [ ] **Step 2: Write failure tests**

Cover stale market summary, summary/candidate CSV mismatch, conclusion market mismatch, delivery total mismatch, closure date mismatch, snapshot hash mismatch, snapshot row mismatch, snapshot outside `outputs/us_universe`, and legacy tracked-path file present. Each test must assert `status=needs_attention` and a stable issue code.

- [ ] **Step 3: Run tests to verify failure**

Run: `python -m unittest tests.test_weekly_artifact_consistency`

Expected: import failure because the module does not exist.

- [ ] **Step 4: Implement parser and checks**

Use standard-library `csv`, `hashlib`, `json`, `datetime` and `pathlib`. Parse Markdown list fields with a strict `- Key: Value` mapping. Return per-market evidence with `run_date`, `age_days`, `summary_candidate_count`, `candidate_file_count`, and issue codes. Require all non-empty market run dates to resolve to one natural date. Treat any issue as blocking.

- [ ] **Step 5: Add CLI and PowerShell wrapper**

CLI arguments:

```text
--project-root
--as-of-date
--max-age-days
--output
--report
```

PowerShell defaults write `latest_weekly_artifact_consistency.json` and `.md` under `outputs/automation`.

- [ ] **Step 6: Run tests and commit**

Run: `python -m unittest tests.test_weekly_artifact_consistency`

Expected: all tests pass.

Commit: `feat: verify weekly artifact consistency`

### Task 3: 接入周收口和提交前闸门

**Files:**
- Modify: `scripts/run_weekly_reporting_bundle.ps1`
- Modify: `pre_submit_review.py`
- Modify: `tests/test_weekly_automation.py`
- Modify: `tests/test_pre_submit_review.py`

**Interfaces:**
- Consumes: `outputs/automation/latest_weekly_artifact_consistency.json`.
- Adds `weekly_artifact_consistency` to `INPUT_SPECS` with required status `ready` and freshness checks.

- [ ] **Step 1: Write failing integration tests**

Assert bundle ordering:

```python
self.assertLess(script.index("run_weekly_delivery_check.ps1"), script.index("run_weekly_artifact_consistency.ps1"))
self.assertLess(script.index("run_weekly_artifact_consistency.ps1"), script.index("run_pre_submit_review.ps1"))
```

Add pre-submit fixtures and assert missing, stale or `needs_attention` consistency input prevents `ready`, while a fresh `ready` payload passes.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m unittest tests.test_weekly_automation tests.test_pre_submit_review`

Expected: FAIL because the new step/input is absent.

- [ ] **Step 3: Implement integration**

Add the wrapper as a critical bundle step immediately after delivery check. Add an input spec using schema field `consistency_schema`, version field `consistency_version`, status field `status`, and require fields `markets`, `candidate_count_total`, `conclusion_candidate_count_total`, `delivery_candidate_count_total`, `runtime_quote_snapshot`, and `issues`.

- [ ] **Step 4: Run tests and commit**

Run: `python -m unittest tests.test_weekly_automation tests.test_pre_submit_review tests.test_weekly_artifact_consistency`

Expected: all tests pass.

Commit: `feat: gate pre-submit on weekly consistency`

### Task 4: 文档、运行复验与合并

**Files:**
- Modify: `docs/提交前复核清单.md`
- Modify: `docs/美股每周自动运行说明.md`
- Modify: `docs/中期目标进度看板.md`

**Interfaces:**
- Documents P5 policy `runtime_output_only` and consistency status `ready`.

- [ ] **Step 1: Update operational documentation**

Document the runtime quote path, six summary metadata fields, consistency output paths, blocking issue behavior, and the requirement that no weekly snapshot be committed.

- [ ] **Step 2: Run targeted and full tests**

Run targeted consistency, pre-submit and automation tests, then:

`python -m unittest discover -s tests`

Expected: all tests pass.

- [ ] **Step 3: Refresh real runtime review**

Copy only current ignored runtime outputs needed by the isolated workspace. Run `run_weekly_artifact_consistency.ps1`, then `run_pre_submit_review.ps1 -CloseoutGoalCode weekly_delivery_stability`. Require both reports to be `ready`.

- [ ] **Step 4: Verify Git policy and commit**

Run `git ls-files data/samples/us_universe_quotes.csv` and require no output. Run `git diff --check` and inspect `git status --short`.

Commit: `docs: document runtime snapshot audit policy`

- [ ] **Step 5: Merge, reverify and push**

Fast-forward merge into `codex/regional-valuation-review-categories`, preserving unrelated main-worktree modifications. Rerun the consistency review, pre-submit review and complete tests, then push the branch.
