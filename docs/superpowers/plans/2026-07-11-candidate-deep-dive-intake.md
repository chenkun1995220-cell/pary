# Candidate Deep-Dive Intake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将结构化候选深研底稿接入每周风险处置和治理链，同时保留人工授权边界。

**Architecture:** `candidate_risk_resolution_review.py` 负责读取并匹配持久化底稿，输出深研完成统计；周结论、中期看板和提交前复核只消费该标准产物，不重复解析原始CSV。缺失底稿保守保持待办，但不阻断基础候选交付。

**Tech Stack:** Python 3 标准库、CSV/JSON、PowerShell包装器、unittest。

## Global Constraints

- 研究建议不得转换为买入批准。
- `manual_pending_count` 不因研究完成而自动清零。
- 不抓取行情、不重新评分、不修改正式模型参数。
- 使用TDD，每个行为先看到失败测试再实现。

---

### Task 1: 风险处置读取深研底稿

**Files:**
- Modify: `candidate_risk_resolution_review.py`
- Modify: `scripts/run_candidate_risk_resolution_review.ps1`
- Test: `tests/test_candidate_risk_resolution_review.py`

**Interfaces:**
- Consumes: `data/manual/candidate_risk_deep_dive_reviews.csv`
- Produces: `deep_dive_required_count`、`deep_dive_completed_count`、`deep_dive_pending_count` 和项目级 `deep_dive_review`

- [x] **Step 1:** 新增失败测试，传入5条合格底稿，断言完成5、待办0且 `manual_pending_count` 仍为5。
- [x] **Step 2:** 运行 `python -m unittest tests.test_candidate_risk_resolution_review`，确认因缺少新参数或字段失败。
- [x] **Step 3:** 实现CSV读取、股票代码匹配、合格性验证、计数和CLI参数；包装器传入默认底稿路径。
- [x] **Step 4:** 重跑测试并确认通过。

### Task 2: 下游治理消费标准字段

**Files:**
- Modify: `weekly_conclusion_report.py`
- Modify: `medium_term_goal_review.py`
- Modify: `pre_submit_review.py`
- Test: `tests/test_weekly_conclusion_report.py`
- Test: `tests/test_medium_term_goal_review.py`
- Test: `tests/test_pre_submit_review.py`

**Interfaces:**
- Consumes: `latest_candidate_risk_resolution_review.json` 的深研统计和项目级底稿
- Produces: 周结论深研摘要、中期模块95%状态、提交前质量闸门

- [x] **Step 1:** 分别新增失败测试，断言周结论传递统计、中期模块达到95%、提交前复核拒绝计数或边界异常。
- [x] **Step 2:** 运行三个测试模块并确认预期失败。
- [x] **Step 3:** 最小实现字段传递、完成度规则和质量检查。
- [x] **Step 4:** 重跑相关测试并确认通过。

### Task 3: 真实产物与完整验收

**Files:**
- Modify runtime outputs only: `outputs/automation/*`
- Modify: `docs/美股每周自动运行说明.md`
- Modify: `docs/中期目标进度看板.md`

**Interfaces:**
- Consumes: 本周5家公司深研底稿和三市场现有运行产物
- Produces: 深研5/5完成、治理链ready的当前周产物

- [x] **Step 1:** 更新说明文档中的底稿路径、字段和研究/授权边界。
- [x] **Step 2:** 依次刷新风险处置、周结论、交付、一致性、中期看板、模型交接和提交前复核。
- [x] **Step 3:** 校验完成5、待办0、人工授权5、正式模型变更不允许。
- [x] **Step 4:** 运行 `python -m unittest discover -s tests`，确认完整测试通过。
- [ ] **Step 5:** 仅提交本计划涉及文件并推送当前分支。
