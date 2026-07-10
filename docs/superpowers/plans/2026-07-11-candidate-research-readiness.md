# 候选研究可用性与风险收敛 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变正式估值和评分结果的前提下解释 60% 目标价上限，并把候选风险待人工项从 15 项压降到最多 5 项。

**Architecture:** 估值模块增加只读诊断字段；新的风险处置模块把原始风险队列、估值敏感性和研究条件合并成结构化处置。周收口、统一结论、中期目标和提交前复核消费该处置产物，但不回写候选池或正式模型。

**Tech Stack:** Python 3 标准库、CSV、JSON、PowerShell、unittest。

## Global Constraints

- `valuation_trend_v1` 的正式目标价、买入价、预期收益率、权重和安全边际不得变化。
- 自动处置不得产生买入批准，只能继续跟踪、暂缓研究或保留人工深研。
- 待人工深研上限为 5。
- 正式模型变更始终为 false。

---

### Task 1: 估值封顶与敏感性诊断

**Files:**
- Modify: `candidate_valuation.py`
- Modify: `tests/test_candidate_valuation.py`

**Interfaces:**
- Adds output fields `uncapped_target_price`, `target_cap_price`, `target_cap_applied`, `target_cap_ratio`, `sensitivity_low_price`, `sensitivity_base_price`, `sensitivity_high_price`, `target_cap_note`.

- [ ] **Step 1: Write failing tests**

Assert a capped fixture keeps `target_price=160`, reports an uncapped value above 160, sets `target_cap_applied=true`, and includes the protection-note text. Assert an uncapped fixture keeps its existing target and sets the flag false.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_candidate_valuation.CandidateValuationTests`

Expected: FAIL because diagnostic fields do not exist.

- [ ] **Step 3: Implement additive diagnostics**

Calculate the uncapped value before the existing `min(..., price * 1.60)`. Use the minimum and maximum available method values times the quality factor for low/high sensitivity. Round diagnostic prices to two decimals without feeding them back into formal outputs.

- [ ] **Step 4: Verify unchanged formal outputs and commit**

Run: `python -m unittest tests.test_candidate_valuation`

Expected: all tests pass, including existing exact target assertions.

Commit: `feat: expose valuation cap diagnostics`

### Task 2: 风险处置与研究条件

**Files:**
- Create: `candidate_risk_resolution_review.py`
- Create: `scripts/run_candidate_risk_resolution_review.ps1`
- Create: `tests/test_candidate_risk_resolution_review.py`

**Interfaces:**
- Produces schema `candidate_risk_resolution_review`, version 1.
- Consumes priority risk JSON and three valuation target CSV files.
- Produces JSON, Markdown and CSV under `outputs/automation`.

- [ ] **Step 1: Write failing happy-path and boundary tests**

Build 15 risk fixtures with at least 7 priority, 5 watchlist and 1 defer item. Assert total 15, manual pending exactly 5, auto-routed 10, formal model false, and every item has core risks, buy conditions, abandon conditions and reopen conditions. Assert cap diagnostics are propagated.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_candidate_risk_resolution_review`

Expected: import failure because the module does not exist.

- [ ] **Step 3: Implement deterministic routing**

Sort with the existing tier/expected-return/score order. Keep only the first five priority items as `manual_deep_dive_required`; route defer items to `defer_until_margin_returns` and all remaining items to `continue_tracking`. Generate conditions from risk categories and valuation fields.

- [ ] **Step 4: Add CLI/wrapper and verify**

Run: `python -m unittest tests.test_candidate_risk_resolution_review`

Expected: all tests pass.

Commit: `feat: resolve candidate risk backlog`

### Task 3: 周收口、统一结论和治理闸门

**Files:**
- Modify: `scripts/run_weekly_reporting_bundle.ps1`
- Modify: `pre_submit_review.py`
- Modify: `weekly_conclusion_report.py`
- Modify: `medium_term_goal_review.py`
- Modify: corresponding tests

**Interfaces:**
- Requires fresh `latest_candidate_risk_resolution_review.json`.
- Adds raw/action-routed/manual-pending/cap counts to weekly conclusion and medium-term current metrics.

- [ ] **Step 1: Write failing integration tests**

Assert bundle ordering after priority research review and before self-analysis refresh; pre-submit blocks missing, stale, unsafe or pending-count-above-five payloads; conclusion and medium-term review display raw count 15 and pending count 5.

- [ ] **Step 2: Verify RED**

Run the four affected test modules and confirm failures are caused by absent integration.

- [ ] **Step 3: Implement integration**

Add the wrapper as critical, add the input schema/quality checks, and prefer resolution `manual_pending_count` for unfinished-risk progress while retaining findings `risk_action_required_count` as audit total.

- [ ] **Step 4: Verify and commit**

Run affected tests and require all pass.

Commit: `feat: surface candidate risk resolution`

### Task 4: 文档、真实产物和完整复验

**Files:**
- Modify: `docs/美股每周自动运行说明.md`
- Modify: `docs/提交前复核清单.md`
- Modify: `docs/中期目标进度看板.md`

- [ ] **Step 1: Document cap semantics and disposition rules**

State explicitly that near-60% expected returns are protection-cap outputs, not precise forecasts, and that automatic routing is not a buy decision.

- [ ] **Step 2: Run full tests**

Run: `python -m unittest discover -s tests`

Expected: all tests pass.

- [ ] **Step 3: Generate current runtime outputs**

Run candidate findings, priority review, manual plan, priority research review and risk resolution in order. Require 15 total current actions and no more than 5 manual pending items.

- [ ] **Step 4: Refresh downstream closure and inspect**

Run self-analysis, weekly actions, conclusion, delivery, medium-term review and pre-submit. Mixed market dates may remain the only P0 blocker; candidate risk resolution itself must be ready.

- [ ] **Step 5: Merge, reverify and push**

Fast-forward into `codex/regional-valuation-review-categories`, preserve unrelated local changes, rerun full tests and push.
