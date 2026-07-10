# S&P 500 历史证据上限收口实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 关闭不可得官方历史证据的每周补充任务，保留真实审计缺口并把回测固定为不可扩样的受限模式。

**Architecture:** 由受版本控制的策略文件声明证据上限；回测证据复核将历史缺口从行动队列转为只读审计指标；自我分析、周行动、中期目标、统一结论和提交前复核消费同一关闭状态。当前成分股交叉校验链保持独立。

**Tech Stack:** Python 3 标准库、PowerShell、JSON、Markdown、`unittest`。

## Global Constraints

- 真实历史证据缺口和 verified 比例不得删除或改写。
- 正式回测样本不得扩大。
- `historical_membership.csv` 不得自动更新。
- 正式模型和正式评分参数不得自动修改。
- 当前成分股交叉校验流程必须继续运行。

---

### Task 1: 策略文件与回测复核

**Files:**
- Create: `data/config/sp500_historical_evidence_policy.json`
- Modify: `backtest_evidence_review.py`
- Modify: `scripts/run_backtest_evidence_review.ps1`
- Modify: `tests/test_backtest_evidence_review.py`

**Interfaces:**
- Produces: `evidence_ceiling_status`, `backtest_mode`, `membership_evidence_unresolved_gap_count` 和受限回测安全字段。

- [ ] **Step 1: 写失败测试**

```python
self.assertEqual(result["status"], "evidence_ceiling_confirmed")
self.assertEqual(result["membership_evidence_unresolved_gap_count"], 425)
self.assertEqual(result["membership_evidence_action_required_count"], 0)
self.assertFalse(result["backtest_sample_expansion_allowed"])
self.assertEqual(result["backtest_mode"], "limited_verified_only")
```

- [ ] **Step 2: 运行并确认红灯**

Run: `python -m unittest tests.test_backtest_evidence_review`

Expected: FAIL，当前状态仍为 `evidence_review_needed` 且行动队列非空。

- [ ] **Step 3: 实现策略读取和受限输出**

策略生效时保留 gap count，清空行动队列，固定扩样和升级权限为 false，并在报告中写明证据上限。

- [ ] **Step 4: 运行并确认绿灯**

Run: `python -m unittest tests.test_backtest_evidence_review`

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add data/config/sp500_historical_evidence_policy.json backtest_evidence_review.py scripts/run_backtest_evidence_review.ps1 tests/test_backtest_evidence_review.py
git commit -m "feat: close sp500 historical evidence ceiling"
```

### Task 2: 周度待办和中期目标收口

**Files:**
- Modify: `automation_self_analysis.py`
- Modify: `weekly_action_items.py`
- Modify: `medium_term_goal_review.py`
- Modify: `weekly_conclusion_report.py`
- Modify: corresponding tests in `tests/`

**Interfaces:**
- Consumes: Task 1 的 `evidence_ceiling_status=evidence_ceiling_confirmed`。
- Produces: 无历史补证待办、完成度 100% 的受限回测目标和明确统一结论。

- [ ] **Step 1: 写失败测试**

```python
self.assertNotIn("review_backtest_evidence", result["automation_priority_actions"])
self.assertNotIn("supplement_verified_membership_evidence", action_codes)
self.assertEqual(backtest_goal["completion_percent"], 100)
self.assertEqual(backtest_goal["next_action"], "maintain_limited_backtest")
self.assertEqual(summary["backtest_mode"], "limited_verified_only")
```

- [ ] **Step 2: 运行相关测试并确认红灯**

Run: `python -m unittest tests.test_automation_self_analysis tests.test_weekly_action_items tests.test_medium_term_goal_review tests.test_weekly_conclusion_report`

Expected: FAIL，旧补证动作仍存在。

- [ ] **Step 3: 实现下游状态传播和动作抑制**

自我分析读取最新回测复核；行动清单跳过历史补证动作；中期目标按关闭状态完成；统一结论增加证据上限与受限模式字段。

- [ ] **Step 4: 运行并确认绿灯**

Run: 同 Step 2。

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add automation_self_analysis.py weekly_action_items.py medium_term_goal_review.py weekly_conclusion_report.py tests
git commit -m "feat: propagate limited backtest closure"
```

### Task 3: 停止周度历史补证链并加强提交闸门

**Files:**
- Modify: `scripts/run_weekly_reporting_bundle.ps1`
- Modify: `pre_submit_review.py`
- Modify: `tests/test_pre_submit_review.py`
- Modify: bundle assertions in `tests/`

**Interfaces:**
- Produces: 证据上限生效时跳过历史补证产物新鲜度要求，并拒绝扩样或补证动作重新出现。

- [ ] **Step 1: 写失败测试**

```python
self.assertNotIn("run_membership_evidence_supplement_batch", bundle)
self.assertEqual(result["status"], "ready")
self.assertIn("historical_evidence_supplement_action_present", unsafe["attention_reasons"])
```

- [ ] **Step 2: 运行并确认红灯**

Run: `python -m unittest tests.test_pre_submit_review tests.test_weekly_automation`

Expected: FAIL，周度 bundle 仍运行补证链，提交复核仍要求旧产物。

- [ ] **Step 3: 移除周度步骤并实现条件式提交检查**

关闭状态下跳过历史补证 INPUT_SPECS 和专用校验，但强制检查受限回测字段、正式权限和周行动清单。

- [ ] **Step 4: 运行并确认绿灯**

Run: 同 Step 2。

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add scripts/run_weekly_reporting_bundle.ps1 pre_submit_review.py tests
git commit -m "feat: stop recurring historical evidence requests"
```

### Task 4: 文档、真实产物和全量验证

**Files:**
- Modify: `docs/S&P500成分证据官方来源补强方案.md`
- Modify: `docs/回测成分证据补强队列.md`
- Modify: `docs/中期目标进度看板.md`
- Modify: `docs/提交前复核清单.md`
- Modify: `docs/美股每周自动运行说明.md`

- [ ] **Step 1: 更新文档为关闭状态**

明确历史证据上限、受限回测和重新开启条件；保留当前成分股交叉校验说明。

- [ ] **Step 2: 重新生成闭环产物**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/run_backtest_evidence_review.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/run_self_analysis.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/show_weekly_action_items.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/show_weekly_conclusion.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/run_weekly_delivery_check.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/run_medium_term_goal_review.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/run_model_handoff_review.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/run_pre_submit_review.ps1
```

Expected: 提交前复核和交付检查均为 ready，行动清单不含历史补证动作。

- [ ] **Step 3: 全量验证**

Run: `python -m unittest discover -s tests`

Expected: PASS。

- [ ] **Step 4: 差异与残留检查**

Run: `git diff --check`

Expected: 退出码 0；周度 bundle 不含历史补证脚本。

- [ ] **Step 5: 提交**

```powershell
git add docs
git commit -m "docs: record sp500 evidence ceiling closure"
```
