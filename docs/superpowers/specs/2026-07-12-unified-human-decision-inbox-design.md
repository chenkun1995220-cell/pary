# 统一人工决策收件箱设计

## 目标

把当前分散在候选风险处置和一周预测影子验证中的人工授权事项，汇总为一个每周可读取、可填写、可审计的决策收件箱。系统自动完成事项发现、证据摘要、决定校验和历史留痕，但任何自动步骤都不得形成买入批准、修改候选评分、改写建议买入价或目标价，也不得修改正式模型 `valuation_trend_v1`。

## 范围

首版只接入两类事项：

- 候选风险授权：来源为 `latest_candidate_risk_resolution_review.json` 中 `manual_decision_required=true` 的项目。
- 预测影子方案审批：来源为 `latest_one_week_forecast_shadow_disposition.json` 中 `disposition=pending_human_approval` 的项目。

自动分流、已拒绝、继续观察或已关闭事项不进入当前待审批列表，但保留在来源产物和历史账本中。首版不开发图形界面，不接入交易账户，不增加自动调参能力。

## 产物与持久化

新增只读生成产物：

- `outputs/automation/latest_human_decision_inbox.json`
- `outputs/automation/latest_human_decision_inbox.md`
- `outputs/automation/human_decision_inbox.csv`

新增人工维护文件：

- `data/manual/human_decision_authorizations.csv`

新增追加式审计账本：

- `outputs/automation/human_decision_history.csv`

JSON 是下游机器读取的权威产物，Markdown 面向人工复核，CSV 提供紧凑的待办视图。人工维护文件只记录决定，不复制自动生成的证据字段；审计账本记录每个已校验决定首次生效时的来源批次与决定内容。同一决定重复运行不得产生重复历史行。

## 事项标识

每个事项使用稳定键：

- 候选风险授权：`candidate_risk|<market>|<ticker>|<source_as_of_date>`
- 预测影子方案审批：`forecast_shadow|<action_code>|<evaluation_as_of_date>`

稳定键同时写入收件箱、人工维护文件和历史账本。来源日期变化会创建新批次事项，旧决定不得静默套用到新一周证据。

## 决策契约

人工维护文件固定字段：

- `decision_key`
- `decision`
- `decided_by`
- `decided_at`
- `decision_reason`
- `boundary_acknowledgement`

候选风险授权允许：

- `approve_for_continued_research`
- `downgrade_to_watchlist`
- `reject_candidate_research`
- `continue_observation`

预测影子方案允许：

- `approve_for_extended_shadow_validation`
- `reject_shadow_candidate`
- `continue_observation`

所有已决定记录必须具备决定人、时间和理由，并明确填写 `human_decision_only_no_trade_or_model_change`。字段缺失、决定类型不匹配、重复键冲突或边界确认不正确时，该事项保持 `pending`，同时输出结构化问题，不得部分生效。

## 生效边界

候选风险决定只改变研究队列状态：

- 批准表示允许继续研究，不表示批准买入。
- 降级或拒绝只影响人工研究优先级，不回写正式筛选结果。
- 继续观察保留待办，并在下一批次重新评估。

预测影子方案决定只改变影子验证阶段：

- 批准表示允许积累更多影子样本，不得直接合并到正式模型。
- 拒绝关闭当前影子候选，不改变历史评价数据。
- 继续观察保持影子候选待定。

无论决定内容如何，输出均固定 `trade_execution_allowed=false`、`formal_model_change_allowed=false` 和 `formal_model_conclusion_allowed=false`。

## 收件箱状态

顶层至少输出：

- `as_of_date`
- `status`
- `item_count`
- `pending_count`
- `decided_count`
- `invalid_decision_count`
- `items`
- `issues`
- 三项安全边界字段

状态规则：

- 来源缺失、过期或结构无效：`blocked`。
- 来源有效但存在待决定或非法决定：`manual_review_needed`。
- 所有当前事项均有合法决定：`ready`。
- 当前没有需审批事项：`ready`，推荐动作设为 `monitor_next_run`。

单项必须包含来源类型、稳定键、市场或方案代码、证据摘要、允许决定、当前决定状态、人工决定信息和安全边界。候选项展示总分、当前价、建议买入价、目标价、预期收益、估值敏感性、核心风险、买入条件、放弃条件和深研结论；影子项展示独立批次、样本数、覆盖市场、基线命中率、影子命中率、差值及严重市场恶化检查。

## 周度链路

收件箱在候选风险处置和一周预测影子处置之后生成，在每周人工处理清单、统一周结论、中期目标看板和提交前复核之前运行。该步骤为关键只读治理步骤：来源无效时阻断周度治理收口，但存在合法的人工待审批事项本身不阻断候选列表交付。

下游统一读取收件箱，不再分别推断两类审批数量：

- 每周人工处理清单展示待审批总数及分类。
- 统一周结论展示当前决定状态和安全边界。
- 中期目标看板将待审批数量作为治理进度信号，不将其误判为数据缺失。
- 提交前复核验证来源新鲜度、计数、稳定键唯一性、决定合法性和三项安全边界。

## 错误处理

- 人工文件不存在时自动生成仅含表头的模板，所有事项保持待审批。
- 未知决定、错误事项类型决定、空理由、无决定人、无时间或边界确认错误均作为非法决定报告。
- 同一稳定键存在不同决定时标记冲突，不选择较新记录自动覆盖。
- 人工文件包含当前收件箱以外的历史键时保留但不生效，也不视为错误。
- 来源日期不同、候选代码变化或影子方案证据变化时生成新事项，不继承旧决定。
- 任何错误路径都不得回写来源产物、候选池、估值结果或正式模型配置。

## 测试与验收

按测试驱动方式覆盖：

- 汇总 5 个候选风险事项和 1 个影子审批事项，得到 6 个待审批事项。
- 合法决定被识别并写入一次审计历史，重复运行保持幂等。
- 两类事项使用各自决定枚举，跨类型决定被拒绝。
- 缺失字段、冲突决定、错误边界和过期来源均保持保守状态。
- 新一周来源不会复用上一周决定。
- 空收件箱返回 `ready`，存在待决定返回 `manual_review_needed`，来源错误返回 `blocked`。
- 周度人工清单、统一结论、中期目标与提交前复核消费同一计数。
- 相关测试与完整测试全部通过。
- 实际产物始终声明不允许交易执行、正式模型变更或正式模型结论。

## 完成标准

当前本周产物可自动形成包含 6 项的统一收件箱；人工只需维护一个决定文件；周度链路能校验并展示决定状态；所有决定均具备来源批次和审计历史；系统不自动执行交易、不修改正式选股或估值参数，也不绕过后续正式模型变更审批。
