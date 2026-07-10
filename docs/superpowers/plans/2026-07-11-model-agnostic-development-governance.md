# 模型无关开发治理实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除固定模型协作开发习惯，建立按运行环境能力自适应、风险驱动复核且兼容未来模型升级的开发治理契约。

**Architecture:** 中期目标产物作为模型无关治理契约的权威来源，开发治理交接复核消费该契约，开发收尾与提交前复核只透传和校验新字段。保留既有脚本入口与输出路径，但通过版本化硬迁移拒绝遗留固定模型协作字段。

**Tech Stack:** Python 3 标准库、PowerShell、`unittest`、Markdown、JSON。

## Global Constraints

- 不绑定任何具体模型名称、版本或供应商。
- 正式估值、评分和预测模型不得自动修改。
- 旧固定模型协作字段不得出现在新生成产物中。
- 模型或运行环境升级不得降低既有质量闸门，升级后必须重新验证。
- 保留现有周度脚本入口和输出文件路径。

---

### Task 1: 中期目标治理契约

**Files:**
- Modify: `tests/test_medium_term_goal_review.py`
- Modify: `medium_term_goal_review.py`

**Interfaces:**
- Produces: `development_execution_profile`, `review_policy`, `environment_compatibility_policy`, `model_version_pinned`, `upgrade_compatibility_required`, `development_governance_note`。
- Removes: `automatic_multi_model_collaboration_enabled`, `collaboration_execution_mode`, `collaboration_boundary_note`。

- [ ] **Step 1: 写失败测试**

```python
self.assertEqual(payload["development_execution_profile"], "capability_adaptive_single_agent")
self.assertEqual(payload["review_policy"], "risk_based_independent_verification")
self.assertFalse(payload["model_version_pinned"])
self.assertTrue(payload["upgrade_compatibility_required"])
self.assertNotIn("collaboration_execution_mode", payload)
```

- [ ] **Step 2: 验证测试因旧契约而失败**

Run: `python -m unittest tests.test_medium_term_goal_review`

Expected: FAIL，缺少 `development_execution_profile` 或仍存在旧字段。

- [ ] **Step 3: 实现最小新契约**

```python
DEVELOPMENT_EXECUTION_PROFILE = "capability_adaptive_single_agent"
REVIEW_POLICY = "risk_based_independent_verification"
ENVIRONMENT_COMPATIBILITY_POLICY = "runtime_capability_detection_with_safe_fallback"
MODEL_VERSION_PINNED = False
UPGRADE_COMPATIBILITY_REQUIRED = True
```

更新模型治理目标、完成度判断和 Markdown 渲染，删除旧协作字段。

- [ ] **Step 4: 验证通过**

Run: `python -m unittest tests.test_medium_term_goal_review`

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add medium_term_goal_review.py tests/test_medium_term_goal_review.py
git commit -m "feat: make medium-term governance model agnostic"
```

### Task 2: 开发治理交接复核

**Files:**
- Modify: `tests/test_model_handoff_review.py`
- Modify: `model_handoff_review.py`

**Interfaces:**
- Consumes: Task 1 的六个模型无关治理字段。
- Produces: `execution_summary`, `quality_review_checklist`, `compatibility_contract`。

- [ ] **Step 1: 写失败测试**

```python
self.assertEqual(result["development_execution_profile"], "capability_adaptive_single_agent")
self.assertTrue(result["compatibility_contract"]["no_model_name_dependency"])
self.assertTrue(result["compatibility_contract"]["revalidate_after_upgrade"])
self.assertNotIn("spark_execution_summary", result)
self.assertNotIn("gpt55_review_checklist", result)
```

另加异常测试：缺少升级重验要求、出现遗留字段或执行配置不匹配时不得 ready。

- [ ] **Step 2: 验证测试失败**

Run: `python -m unittest tests.test_model_handoff_review`

Expected: FAIL，当前结果仍输出旧协作字段。

- [ ] **Step 3: 实现开发治理交接版本 2**

```python
HANDOFF_VERSION = 2
EXPECTED_DEVELOPMENT_EXECUTION_PROFILE = "capability_adaptive_single_agent"
EXPECTED_REVIEW_POLICY = "risk_based_independent_verification"
EXPECTED_ENVIRONMENT_COMPATIBILITY_POLICY = "runtime_capability_detection_with_safe_fallback"
```

生成模型无关执行摘要、质量复核清单和兼容契约；Markdown 标题改为“开发治理交接复核”。

- [ ] **Step 4: 验证通过**

Run: `python -m unittest tests.test_model_handoff_review`

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add model_handoff_review.py tests/test_model_handoff_review.py
git commit -m "feat: replace model handoff roles with adaptive governance"
```

### Task 3: 开发收尾与提交前硬迁移

**Files:**
- Modify: `tests/test_pre_submit_review.py`
- Modify: `pre_submit_review.py`
- Modify: `development_closeout_summary.py`

**Interfaces:**
- Consumes: Tasks 1-2 的模型无关字段。
- Rejects: 新产物中的任一遗留固定模型协作字段。

- [ ] **Step 1: 写失败测试**

```python
self.assertEqual(result["development_closeout"]["development_execution_profile"], "capability_adaptive_single_agent")
self.assertNotIn("collaboration_execution_mode", result["development_closeout"])
```

加入三类闸门测试：旧字段存在、模型版本被固定、升级兼容契约不完整时，`attention_reasons` 必须包含对应原因。

- [ ] **Step 2: 验证测试失败**

Run: `python -m unittest tests.test_pre_submit_review`

Expected: FAIL，提交前检查仍要求旧固定模型字段。

- [ ] **Step 3: 实现硬迁移闸门**

```python
LEGACY_MODEL_COLLABORATION_FIELDS = {
    "automatic_multi_model_collaboration_enabled",
    "collaboration_execution_mode",
    "collaboration_boundary_note",
    "spark_execution_summary",
    "gpt55_review_checklist",
}
```

替换必填字段、治理文档关键词、交接校验和开发收尾渲染；发现遗留字段时要求重新生成。

- [ ] **Step 4: 验证相关测试通过**

Run: `python -m unittest tests.test_pre_submit_review tests.test_model_handoff_review tests.test_medium_term_goal_review`

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add pre_submit_review.py development_closeout_summary.py tests/test_pre_submit_review.py
git commit -m "feat: enforce adaptive development governance before submit"
```

### Task 4: 文档迁移、真实产物刷新与全量验证

**Files:**
- Modify: `docs/中期目标与模型协作规范.md`
- Modify: `docs/中期目标进度看板.md`
- Modify: `docs/模型交接包说明.md`
- Modify: `docs/提交前复核清单.md`
- Modify: `docs/美股每周自动运行说明.md`
- Modify: affected documentation assertions in `tests/`

**Interfaces:**
- Produces: 不绑定模型名称的中文开发治理说明和本次重新生成的运行产物。

- [ ] **Step 1: 写或更新文档契约测试并验证失败**

Run: `python -m unittest tests.test_pre_submit_review tests.test_model_handoff_review tests.test_medium_term_goal_review`

Expected: FAIL，现有文档仍包含旧固定模型协作习惯。

- [ ] **Step 2: 改写五份文档**

统一为“环境能力识别 -> 最小可验证实现 -> 风险分级复核 -> 完整验证 -> 失败回退 -> 升级后重验”，删除固定模型角色与模拟双模型协作表述。

- [ ] **Step 3: 重新生成治理链产物**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/run_medium_term_goal_review.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/run_model_handoff_review.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/run_pre_submit_review.ps1
```

Expected: 三个脚本退出码均为 0，提交前复核为 `ready`。

- [ ] **Step 4: 检查旧习惯残留与完整测试**

```powershell
rg -n -i "gpt5\.3-codex-spark|gpt5\.5|single_codex_with_gpt55_review_checklist" medium_term_goal_review.py model_handoff_review.py development_closeout_summary.py pre_submit_review.py docs
python -m unittest discover -s tests
git diff --check
```

Expected: 除迁移设计与专门遗留拒绝说明外无固定模型协作习惯；全量测试 PASS；差异检查退出码 0。

- [ ] **Step 5: 提交**

```powershell
git add docs tests medium_term_goal_review.py model_handoff_review.py development_closeout_summary.py pre_submit_review.py
git commit -m "docs: adopt capability-adaptive development habits"
```
