# 三市场连续周日交付验收台账 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 2026-07-12 起生成可审计、同日重跑不重复计数的三市场连续 3 周日交付验收台账。

**Architecture:** 三个市场脚本记录开始和完成时间；一致性复核标准化这些时间；独立台账模块把当周一致性、交付和提交前状态写入按日期去重的 JSONL，并计算连续成功周数。周度链在第一次提交前复核后写台账，再刷新看板、治理交接和最终提交前复核。

**Tech Stack:** Python 3 标准库、PowerShell 5.1、JSON/JSONL、`unittest`。

## Global Constraints

- 验收起始日固定为 `2026-07-12`，要求连续 3 个周日。
- 港股正常启动窗口固定为本地时间 `14:15:00` 至 `14:30:00`。
- 同一日期重跑替换历史记录，不得增加周数。
- 非周日和起始日前运行不写历史。
- 所有输出固定 `formal_model_change_allowed=false`。
- 不抓取行情、不重新评分、不修改筛选、估值、预测或正式模型。
- 不修改主工作区现有未提交的 `docs/中期目标与模型协作规范.md`。

---

### Task 1: 三市场运行起止时间证据

**Files:**
- Modify: `scripts/run_us_universe_weekly.ps1`
- Modify: `scripts/run_cn_weekly.ps1`
- Modify: `scripts/run_hk_weekly.ps1`
- Modify: `tests/test_weekly_automation.py`

**Interfaces:**
- Produces: `Run start time: YYYY-MM-DD HH:mm:ss` and existing `Run time` in each `latest_run_summary.md`.

- [ ] **Step 1:** Add static tests requiring `$runStartedAt` after dry-run and before market work, plus `Run start time` in all summaries.
- [ ] **Step 2:** Run `python -m unittest tests.test_weekly_automation.WeeklyAutomationTests.test_market_weekly_summaries_include_run_start_time -v`; expect FAIL.
- [ ] **Step 3:** Capture `$runStartedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"` after lock acquisition and write it before `Run time` in each summary.
- [ ] **Step 4:** Run `python -m unittest tests.test_weekly_automation -v`; expect PASS.
- [ ] **Step 5:** Commit `feat: record weekly market start times`.

### Task 2: 连续周日台账核心

**Files:**
- Create: `weekly_delivery_streak_review.py`
- Create: `tests/test_weekly_delivery_streak_review.py`

**Interfaces:**
- Produces: `build_weekly_delivery_streak_review(...)`, `update_history(...)`, JSON/Markdown rendering and CLI.
- Consumes: consistency, delivery, pre-submit payloads and prior JSONL rows.

- [ ] **Step 1:** Write tests for non-Sunday no-write, same-day replacement, three consecutive successes, gaps/failures, candidate mismatch, and HK start-window failures.
- [ ] **Step 2:** Run `python -m unittest tests.test_weekly_delivery_streak_review -v`; expect import or assertion failures.
- [ ] **Step 3:** Implement strict payload validation, Sunday record construction, date-key deduplication, consecutive streak calculation and status routing.
- [ ] **Step 4:** Add CLI outputs `latest_weekly_delivery_streak_review.json/.md` and `weekly_delivery_streak_history.jsonl`.
- [ ] **Step 5:** Run `python -m unittest tests.test_weekly_delivery_streak_review -v`; expect PASS.
- [ ] **Step 6:** Commit `feat: add weekly delivery streak ledger`.

### Task 3: 一致性与周度链集成

**Files:**
- Modify: `weekly_artifact_consistency.py`
- Modify: `tests/test_weekly_artifact_consistency.py`
- Create: `scripts/run_weekly_delivery_streak_review.ps1`
- Modify: `scripts/run_weekly_reporting_bundle.ps1`
- Modify: `tests/test_weekly_automation.py`

**Interfaces:**
- Consistency market rows add `run_started_at` and `run_completed_at`.
- Wrapper runs after first pre-submit; medium goal, handoff and final pre-submit run afterward.

- [ ] **Step 1:** Add failing tests for normalized timestamps, wrapper contract and exact tail ordering.
- [ ] **Step 2:** Run targeted tests; expect missing fields/script/order failures.
- [ ] **Step 3:** Add timestamp normalization and wrapper.
- [ ] **Step 4:** Reorder the reporting tail to generate current-cycle pre-submit, ledger, refreshed governance and final pre-submit.
- [ ] **Step 5:** Run `python -m unittest tests.test_weekly_artifact_consistency tests.test_weekly_automation tests.test_weekly_delivery_streak_review -v`; expect PASS.
- [ ] **Step 6:** Commit `feat: wire weekly delivery streak review`.

### Task 4: 看板、文档与真实边界验证

**Files:**
- Modify: `medium_term_goal_review.py`
- Modify: `tests/test_medium_term_goal_review.py`
- Modify: `docs/中期目标进度看板.md`
- Modify: `docs/提交前复核清单.md`
- Modify: `docs/美股每周自动运行说明.md`

**Interfaces:**
- `weekly_delivery_stability.current` exposes streak status, count, required count, dates and HK first-start validation.

- [ ] **Step 1:** Add failing fixture/assertions for 0/3 accumulating and 3/3 phase-ready states.
- [ ] **Step 2:** Run `python -m unittest tests.test_medium_term_goal_review -v`; expect failures.
- [ ] **Step 3:** Consume the streak review and require 3/3 before P0 phase completion.
- [ ] **Step 4:** Document output paths, start window, deduplication and non-model boundary.
- [ ] **Step 5:** On Saturday run the wrapper with `--as-of-date 2026-07-11`; verify `not_scheduled_day` and no history write.
- [ ] **Step 6:** Run `python -m unittest discover -s tests` and `git diff --check`; expect PASS.
- [ ] **Step 7:** Commit `docs: document consecutive Sunday delivery acceptance`.

### Task 5: 合并与周日验收准备

- [ ] **Step 1:** Review the complete diff against the design and confirm formal model files are unchanged.
- [ ] **Step 2:** Fast-forward merge to `codex/regional-valuation-review-categories` while preserving the user's local document change.
- [ ] **Step 3:** Run all tests on the merged branch.
- [ ] **Step 4:** Push the merged branch and verify local/remote SHA equality.
- [ ] **Step 5:** Keep P0 incomplete until real Sunday records reach 3/3; do not synthesize history.
