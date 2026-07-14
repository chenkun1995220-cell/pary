# 动作策略产物契约 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 刷新当前正式报告产物，并让提交前复核能够拒绝缺少当前动作策略版本或有效性字段的旧自动化检查产物。

**Architecture:** 先运行不含市场抓取的报告链，使正式 `latest_*` 产物反映现有动作统一逻辑。随后由 `automation_self_analysis.py` 在 manifest 和自动化检查中写入固定动作策略版本，`pre_submit_review.py` 校验版本及两个动作有效性字段；最后重跑同一报告链证明正式产物满足新契约。

**Tech Stack:** Python 3 标准库、PowerShell、`unittest`、JSON。

## Global Constraints

- 不运行美股、A 股或港股市场抓取入口。
- 不重新评分，不修改正式选股、估值或预测模型参数。
- 候选业务风险原样保留，只规范顶层建议动作的产物契约。
- 所有行为修改遵循红灯、绿灯、全量回归流程。

---

### Task 1: 刷新当前正式报告链

**Files:**
- Runtime outputs: `outputs/automation/latest_*.json`

**Interfaces:**
- Consumes: 当前三市场运行摘要及现有复核产物。
- Produces: 统一后的自动化检查、行动清单、周结论、交付检查、一致性检查和提交前复核。

- [x] **Step 1: 依次运行只读输入的报告入口**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_self_analysis.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/show_weekly_action_items.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_weekly_ops_check.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/show_weekly_ops_history.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/show_weekly_conclusion.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_weekly_delivery_check.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_weekly_artifact_consistency.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/show_weekly_delivery_history.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_pre_submit_review.ps1
```

- [x] **Step 2: 验证动作和交付状态**

检查 `latest_automation_check.json`、`latest_weekly_action_items.json`、`latest_weekly_conclusion.json` 和 `latest_pre_submit_review.json`。预期顶层动作均为 `continue_sample_accumulation`，交付及提交前复核为 `ready`。

### Task 2: 增加动作策略版本契约

**Files:**
- Modify: `automation_self_analysis.py`
- Modify: `pre_submit_review.py`
- Modify: `tests/test_automation_self_analysis.py`
- Modify: `tests/test_pre_submit_review.py`
- Modify: `docs/美股每周自动运行说明.md`

**Interfaces:**
- Consumes: `latest_automation_check.json`。
- Produces: `action_policy_version=1`、`candidate_review_actionable`、`weekly_delivery_history_actionable`，以及版本/字段缺失时的提交前阻断原因。

- [x] **Step 1: 写自动化检查版本字段失败测试**

在 `test_automation_check_payload_exposes_actionability_flags` 中断言：

```python
self.assertEqual(payload.get("action_policy_version"), 1)
```

- [x] **Step 2: 写提交前复核旧产物失败测试**

从 ready fixture 中删除 `action_policy_version`、`candidate_review_actionable` 和 `weekly_delivery_history_actionable`，断言结果为 `needs_attention` 且包含 `automation_check_missing_quality_fields`。另写版本值为 `0` 的用例，断言包含 `automation_check_action_policy_version_mismatch`。

- [x] **Step 3: 运行测试并确认红灯**

```powershell
python -m unittest tests.test_automation_self_analysis.AutomationSelfAnalysisTests.test_automation_check_payload_exposes_actionability_flags
python -m unittest tests.test_pre_submit_review.PreSubmitReviewTests.test_review_needs_attention_when_automation_check_lacks_action_policy_contract
```

预期：字段或版本契约尚未实现，测试失败。

- [x] **Step 4: 最小实现产物契约**

在 `automation_self_analysis.py` 定义 `ACTION_POLICY_VERSION = 1`，写入 manifest 和 `_automation_check_payload`。在 `pre_submit_review.py` 将三个字段加入 `AUTOMATION_CHECK_REQUIRED_QUALITY_FIELDS`，并校验版本等于 `1`。

- [x] **Step 5: 运行相关测试**

```powershell
python -m unittest tests.test_automation_self_analysis tests.test_pre_submit_review tests.test_weekly_automation
```

预期：全部通过。

- [x] **Step 6: 更新说明并重新刷新正式报告链**

在 `docs/美股每周自动运行说明.md` 记录版本契约。重复 Task 1 的报告链，预期提交前复核恢复为 `ready`。

- [x] **Step 7: 全量验证并提交**

```powershell
python -m unittest discover -s tests
git diff --check
```

预期：全量测试通过，无空白错误；仅提交本计划、相关代码、测试和文档。
