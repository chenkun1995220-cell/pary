# 模型无关开发治理设计

## 目标

从开发习惯、治理产物和提交前闸门中删除 `gpt5.3-codex-spark` 与 `gpt5.5` 的固定角色分工，不再模拟双模型协作。保留小步实现、证据留存、独立复核、完整测试、失败回退和正式模型禁改等工程纪律，并使这些纪律在当前模型、后续模型升级或运行环境变化时保持有效。

## 采用方案

采用版本化硬迁移，不双写旧协作字段。

- 新产物不包含 `automatic_multi_model_collaboration_enabled`、`collaboration_execution_mode`、`collaboration_boundary_note`、`spark_execution_summary` 或 `gpt55_review_checklist`。
- 已存在的旧产物由提交前检查识别为遗留契约，要求重新生成，不能继续作为 ready 证据。
- 保留 `model_handoff_review.py`、`run_model_handoff_review.ps1` 和现有输出路径，避免破坏周度脚本入口；其语义改为“开发治理交接复核”。
- 不读取或绑定具体模型名称、版本、供应商或自动多模型调度状态。

## 新治理契约

`medium_term_goal_review` 和开发治理交接产物统一使用以下字段：

- `development_execution_profile=capability_adaptive_single_agent`：一个明确执行主体根据当前环境能力完成任务。
- `review_policy=risk_based_independent_verification`：按风险等级决定复核深度，高风险变更必须有独立验证证据。
- `environment_compatibility_policy=runtime_capability_detection_with_safe_fallback`：运行时识别工具、权限、依赖和数据可用性；能力不足时降级到安全路径或明确失败，不降低验收门槛。
- `model_version_pinned=false`：开发治理不依赖固定模型版本。
- `upgrade_compatibility_required=true`：模型或环境升级后必须重跑既有验证，不允许通过改名绕过质量闸门。
- `development_governance_note`：明确说明模型无关、能力自适应、风险复核、证据留存、完整测试和失败回退边界。

开发治理交接产物另提供：

- `execution_summary`：记录当前任务如何小步实现并保留可回放证据。
- `quality_review_checklist`：检查数据新鲜度、正式模型边界、测试证据、输出一致性和失败回退。
- `compatibility_contract`：声明不依赖模型名称、允许模型升级、升级后必须重新验证，且最低质量闸门不可降低。

## 数据流

1. `medium_term_goal_review.py` 从提交前复核和周度产物生成模型无关治理状态。
2. `model_handoff_review.py` 读取新的中期目标字段，生成开发治理交接复核。
3. `development_closeout_summary.py` 只透传新的执行配置、复核策略和兼容策略。
4. `pre_submit_review.py` 校验新字段、治理文档和交接清单；发现旧协作字段、固定模型绑定或缺少升级兼容契约时返回 `needs_attention`。
5. 周度报告脚本保持现有调用顺序，重新生成全部治理产物后恢复 `ready`。

## 错误与迁移处理

- 新字段缺失：输出明确的 `*_missing_adaptive_governance_fields` 原因。
- 执行配置或策略值异常：输出 `*_adaptive_governance_mode_unsafe`。
- 发现旧协作字段：输出 `*_legacy_model_collaboration_fields_present`，要求重生成，不静默兼容。
- `compatibility_contract` 未声明无模型名称依赖、升级后重验或质量门槛不可降低：交接复核不得 ready。
- 正式模型的自动修改权限继续固定为 `false`，本次迁移不触碰评分与预测参数。

## 文档迁移

更新中期目标规范、进度看板、模型交接包说明、提交前复核清单和美股每周自动运行说明。所有开发习惯改写为：

1. 先识别当前环境能力和限制。
2. 按最小可验证单元实施。
3. 按风险等级执行独立复核。
4. 保存可回放证据并运行完整验证。
5. 失败时回退或明确阻塞，不降低验收标准。
6. 模型或环境升级后重跑相同闸门，不依赖固定模型名称。

## 测试与验收

- 使用测试先行迁移 `medium_term_goal_review`、开发治理交接、开发收尾摘要和提交前复核。
- 新测试证明新字段存在、旧字段不存在、旧产物被拒绝、模型升级兼容契约缺失时被拒绝。
- 更新文档测试，确认治理规范不再要求固定模型名称或模拟协作。
- 运行全部单元测试和真实周度治理刷新链。
- 最终搜索开发治理代码与文档，除专门验证遗留产物拒绝逻辑外，不得残留固定模型协作习惯。

## 非目标

- 不修改 Codex 自动化任务自身的运行模型配置。
- 不实现多代理或多模型自动调度。
- 不修改正式估值、评分、预测或交易逻辑。
- 不借本次迁移调整中期目标的业务完成度。
