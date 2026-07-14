# 行动策略版本全链路传播设计

## 目标

将当前 `action_policy_version=1` 从自我分析和自动化检查扩展到完整周度报告链，使旧版、缺字段或混合版本产物在最早消费者处被拒绝，而不是等到提交前复核才发现。

本设计只调整工程产物契约，不抓取行情、不重新评分、不修改正式选股、估值或预测模型参数。

## 当前问题

当前自我分析 manifest 和 `latest_automation_check.json` 已写入 `action_policy_version=1`，提交前复核也会校验该版本及两个行动性字段：

- `candidate_review_actionable`
- `weekly_delivery_history_actionable`

但下游仍存在以下缺口：

- `weekly_action_items.py` 只校验 `manifest_version`。
- `weekly_ops_check.py` 只校验 `check_version`。
- 周结论、交付检查和一致性复核没有证明自己读取的是当前行动策略版本。
- 混合新旧产物可能先生成周结论和交付结果，最后才由提交前复核拦截。

## 设计原则

1. **单一版本源**：项目只保留一个行动策略版本常量，所有生产者和消费者从同一模块导入。
2. **逐级传播**：每个派生产物都写出其实际读取的 `action_policy_version`。
3. **尽早失败**：消费者在执行业务汇总前校验输入版本。
4. **保留失败证据**：适合输出验收结果的步骤写出 `needs_attention` 和精确失败原因；严格生成器不覆盖旧正式产物。
5. **不改变业务结论**：版本有效时，候选数量、排序、估值、风险状态和建议动作保持不变。

## 共享契约模块

新增 `action_policy_contract.py`，提供：

- `ACTION_POLICY_VERSION = 1`
- `SOURCE_ACTION_POLICY_REQUIRED_FIELDS`：源产物必须包含版本和两个行动性字段。
- `action_policy_contract_status(payload, require_actionability=False)`：返回 `valid`、`missing` 或 `mismatch`。
- `action_policy_version(payload)`：安全解析整数版本；缺失或非法值返回 `None`。

`automation_self_analysis.py` 和 `pre_submit_review.py` 不再各自维护重复版本常量，统一导入共享常量。

## 产物契约

### 源产物

以下产物必须包含版本和两个行动性字段：

- `latest_self_analysis_manifest.json`
- `latest_automation_check.json`

必填字段：

- `action_policy_version`
- `candidate_review_actionable`
- `weekly_delivery_history_actionable`

### 派生产物

以下产物必须写出 `action_policy_version`：

- `latest_weekly_action_items.json`
- `latest_weekly_ops_check.json`
- `latest_weekly_conclusion.json`
- `latest_weekly_delivery_check.json`
- `latest_weekly_artifact_consistency.json`
- `latest_pre_submit_review.json`

一致性复核额外写出：

- `action_policy_contract_status`
- `action_policy_versions`：按 manifest、automation check、action items、ops check、conclusion、delivery 分项记录实际版本。

## 数据流

```text
self analysis manifest
  |---> weekly action items
  |---> automation check ---> weekly ops check
                               |
automation check + action items + ops check
  |---> weekly conclusion
          |
weekly conclusion + action items
  |---> weekly delivery check
          |
manifest + automation check + action items + ops check + conclusion + delivery
  |---> weekly artifact consistency
          |
all current closure artifacts
  |---> pre-submit review
```

每一步只传播已经校验通过的版本，不用默认值伪造成功版本。

## 各步骤行为

### 每周行动清单

`weekly_action_items.load_manifest` 必须校验 manifest 的源契约。缺字段或版本不匹配时抛出精确错误并停止，不覆盖已有 `latest_weekly_action_items.*`。成功时输出当前版本。

错误类型：

- `manifest_action_policy_contract_missing`
- `manifest_action_policy_version_mismatch`

### 周度运维检查

运维检查保留当前 schema/version 校验，并新增行动策略校验。无效时仍写出本次 `needs_attention` 产物，避免旧的 `latest_weekly_ops_check.json` 被误认为本次结果。

原因码：

- `automation_check_action_policy_contract_missing`
- `automation_check_action_policy_version_mismatch`

输出记录实际版本和 `action_policy_contract_status`。

### 统一周结论

周结论核对自动化检查、行动清单和运维检查的行动策略版本。任一缺失、非当前版本或互不一致时：

- 状态为 `needs_attention`。
- 不从旧行动清单生成新的优先动作。
- 写入明确 warning，不复用旧结论作为成功结论。

### 交付检查

交付检查核对周结论与行动清单版本。缺失或不一致时输出 `needs_attention`，并写入：

- `weekly_conclusion_action_policy_version_missing/mismatch`
- `weekly_action_items_action_policy_version_missing/mismatch`
- `action_policy_version_inconsistent`

### 周产物一致性复核

一致性复核读取六个关键产物的版本并生成版本映射。任何缺失、非当前版本或混合版本都会形成 issue：

- `<artifact>_action_policy_version_missing`
- `<artifact>_action_policy_version_mismatch`
- `action_policy_version_inconsistent`

该复核继续保留候选数量、运行日期、行情快照和收口顺序检查。

### 提交前复核

提交前复核继续校验源产物，并把行动策略版本加入运维检查、周结论、交付检查和一致性复核的必填质量字段。任何下游旧产物都会阻断提交。

## 失败与恢复

正式链按以下顺序恢复：

1. `run_self_analysis.ps1`
2. `show_weekly_action_items.ps1`
3. `run_weekly_ops_check.ps1`
4. `show_weekly_ops_history.ps1`
5. `show_weekly_conclusion.ps1`
6. `run_weekly_delivery_check.ps1`
7. `run_weekly_artifact_consistency.ps1`
8. `show_weekly_delivery_history.ps1`
9. `run_pre_submit_review.ps1`

任一步失败立即停止，不引用该步骤之前遗留的旧下游产物。恢复只重跑报告链，不运行美股、A 股或港股市场抓取入口。

## 测试策略

实施采用测试驱动方式，每个行为先添加失败测试：

1. 共享契约正确区分有效、缺失、非法和旧版本。
2. 行动清单拒绝缺失或旧版 manifest。
3. 运维检查对缺失或旧版自动化检查写出 `needs_attention`。
4. 周结论拒绝混合版本输入，不生成旧策略动作。
5. 交付检查拒绝缺失、旧版或混合版本输入。
6. 一致性复核输出完整版本映射并识别混合版本。
7. 提交前复核拒绝缺少下游版本字段的陈旧产物。
8. 当前版本输入下，原有候选数、动作和状态保持不变。
9. 运行所有相关测试及全量测试。

## 正式产物迁移

代码通过全量测试后，按固定顺序重新运行报告链，使所有 `latest_*` 产物升级到版本 1。迁移验收要求：

- 六个关键派生产物均包含 `action_policy_version=1`。
- 一致性复核的版本映射全部为 1，状态为 `ready`。
- 候选总数仍为当前三市场实际总数。
- 顶层建议动作不因迁移发生变化。
- 提交前复核为 `ready` 且无行动策略版本原因项。

## 非目标

- 不修改 `valuation_trend_v1` 或任何正式模型参数。
- 不改变候选公司筛选、评分、目标价或预测逻辑。
- 不自动批准影子模型候选。
- 不运行市场抓取或行情补齐。
- 不借版本迁移降低任何现有质量门槛。

## 成功标准

1. 旧版或混合版本产物无法进入成功交付状态。
2. 失败步骤提供机器可读、精确且可定位的原因码。
3. 当前版本完整链仍输出 65 个候选和 `continue_sample_accumulation`，除非输入市场产物在实施期间真实变化。
4. 全量测试通过，Git 仅包含契约相关代码、测试和文档。
