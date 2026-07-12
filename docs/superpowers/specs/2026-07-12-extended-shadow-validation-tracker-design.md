# 扩展影子验证跟踪器设计

## 目标

在人工批准 `approve_for_extended_shadow_validation` 后，自动跟踪后续 3 个真实、独立、去重的周批次，并在证据到期或触发安全停止规则时重新进入人工复核。该流程只改变影子验证阶段，不回写历史评价、不修改候选评分，也不修改正式模型 `valuation_trend_v1`。

## 授权范围

扩展授权以人工决策历史中的以下记录为起点：

- `item_type=forecast_shadow`
- `decision=approve_for_extended_shadow_validation`
- `boundary_acknowledgement=human_decision_only_no_trade_or_model_change`

授权按 `action_code` 独立管理。授权批次日期取决于决定键中的来源日期；只有评价日期严格晚于该日期的验证批次才计入扩展阶段。授权覆盖最多 3 个独立周批次，不跨方案代码复用，也不自动延长。

## 输入

跟踪器读取：

- `outputs/automation/latest_human_decision_inbox.json`
- `outputs/automation/human_decision_history.csv`
- `outputs/automation/one_week_forecast_shadow_parameter_validation_history.jsonl`
- `outputs/automation/latest_one_week_forecast_shadow_disposition.json`

人工决策历史提供授权事实，验证历史提供逐批证据，最新处置产物提供当前来源状态和安全边界。跟踪器不得抓取行情、重新计算评分或修改任何输入。

## 批次身份与去重

独立批次键固定为：

`action_code|evaluation_as_of_date`

同一动作和评价日期的重复历史行只计一个批次。一个批次内可以包含多个市场结果；批次级结论从该动作在该日期的全部市场证据聚合得出。授权日期及以前的批次只作为审批前基线，不计入 3 批扩展额度。

## 批次分类

每个批准后批次分类为：

- `positive`：可比较样本大于 0，汇总命中率差值大于 0，且没有严重市场恶化。
- `negative`：可比较样本大于 0，汇总命中率差值小于等于 0，且没有严重市场恶化。
- `not_evaluable`：没有可比较样本或验证状态不可评价。
- `severe_deterioration`：任一市场被验证层标记为严重恶化，优先级高于其他分类。

`not_evaluable` 不消耗 3 个有效扩展批次额度，但保留在审计计数中；相同日期重跑不得增加任何计数。

## 状态机

每个授权方案只有一种有效状态：

- `active`：授权有效，尚未达到 3 个可评价批次，也未触发提前停止。
- `ready_for_reapproval`：累计达到 3 个可评价批次，需要人工复核。
- `paused_severe_deterioration`：任一批准后批次出现严重市场恶化，立即暂停。
- `paused_two_consecutive_negative_batches`：最近两个可评价批次均为 `negative`，提前暂停。
- `blocked`：授权、验证历史或来源结构缺失、损坏、日期冲突，无法安全判断。
- `inactive`：当前没有合法扩展授权。

状态优先级为：`blocked`、`paused_severe_deterioration`、`paused_two_consecutive_negative_batches`、`ready_for_reapproval`、`active`、`inactive`。

## 推荐动作

- `active`：`continue_extended_shadow_validation`
- `ready_for_reapproval`：`review_extended_shadow_validation_results`
- 两种 `paused_*`：`request_shadow_safety_reapproval`
- `blocked`：`repair_extended_shadow_validation_inputs`
- `inactive`：`monitor_shadow_authorizations`

任何推荐动作都不得转换成正式模型变更。达到 3 批或提前暂停后，必须产生新的人工决策键；旧授权不得自动续期。

## 输出

新增：

- `outputs/automation/latest_extended_shadow_validation_tracker.json`
- `outputs/automation/latest_extended_shadow_validation_tracker.md`
- `outputs/automation/extended_shadow_validation_batches.csv`

顶层字段至少包括：

- `as_of_date`
- `status`
- `recommended_action`
- `authorization_count`
- `active_authorization_count`
- `ready_for_reapproval_count`
- `paused_count`
- `items`
- `issues`
- `trade_execution_allowed=false`
- `formal_model_change_allowed=false`
- `formal_model_conclusion_allowed=false`

每个方案项至少包括授权决定键、方案代码、授权日期、授权人、授权后历史批次数、可评价批次数、正负批次数、不可评价批次数、连续负批次数、严重恶化批次数、剩余有效批次数、状态、推荐动作和逐批摘要。

## 周度链路

跟踪器在统一人工决策收件箱之后运行，在自我分析、每周行动清单、统一周结论、中期目标和提交前复核之前运行。

- `active` 只显示继续积累，不生成重复审批项。
- 达到 3 批或提前暂停时，每周行动清单新增唯一人工复核事项。
- 周结论同时展示授权前原始证据、批准后批次进度和有效状态。
- 中期目标将批准后批次进度作为 P1 后续成熟度信号。
- 提交前复核拒绝缺失、过期、计数不一致、重复批次、非法状态或任何允许正式模型变更的跟踪产物。

## 失败边界

- 授权记录缺失必要字段、边界错误或同一决定键冲突时进入 `blocked`。
- 验证历史损坏、动作代码无法匹配或评价日期早于授权日期时保留问题并保守阻断。
- 新批次尚未出现时允许 `active` 且进度为 0/3。
- `not_evaluable` 可以持续记录，但不得伪装成有效扩展批次。
- 严重恶化只触发暂停和人工复核，不自动回滚、删除候选或修改正式模型。

## 验收标准

- 当前已批准方案生成 `active`，扩展进度为 0/3，因为现有 3 批均属于授权前证据。
- 后续每个真实新周批次最多增加一次计数。
- 3 个可评价批次后状态变为 `ready_for_reapproval`。
- 任一严重恶化批次立即变为 `paused_severe_deterioration`。
- 连续 2 个负批次变为 `paused_two_consecutive_negative_batches`。
- 正、负、不可评价和重复批次计数准确。
- 周行动、周结论、中期看板和提交前复核读取同一跟踪产物。
- 所有相关测试与完整测试通过。
- 所有输出始终禁止交易执行、正式模型变更和正式模型结论。
