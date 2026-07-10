# 候选研究可用性与风险收敛设计

## 目标

完成中期目标 P3：解释大量预期收益率接近 60% 的估值封顶现象，把 15 个风险行动项分流为明确处置并将待人工深研项降至最多 5 个，同时为优先研究公司补齐估值敏感性、核心风险、买入条件和放弃条件。

## 安全边界

- 正式估值模型继续使用 `valuation_trend_v1`。
- 正式目标价仍受当前价 1.60 倍上限保护，不修改评分、估值权重、安全边际或候选排序。
- 自动分流只允许产生“继续跟踪”或“暂缓研究”，不得自动批准买入或升级正式模型。
- 所有自动处置必须保留原因、条件和重新进入人工复核的触发条件。

## 估值封顶诊断

`candidate_valuation.py` 在现有目标价字段之外增加：

- `uncapped_target_price`：应用质量因子后、60%上限前的基础估值。
- `target_cap_price`：当前价的 1.60 倍。
- `target_cap_applied`：基础估值是否被保护上限截断。
- `target_cap_ratio`：未封顶估值与上限价之比。
- `sensitivity_low_price`：可用估值方法最低值乘质量因子。
- `sensitivity_base_price`：未封顶基础估值。
- `sensitivity_high_price`：可用估值方法最高值乘质量因子。
- `target_cap_note`：触顶时明确“60%为保护上限，不是精确收益预测”。

这些字段只解释估值分散度和保护上限，不改变 `target_price`、`buy_price` 或 `expected_return` 的计算结果。

## 风险处置层

新增 `candidate_risk_resolution_review.py`，读取：

- `latest_candidate_risk_priority_review.json`
- 三市场 `valuation_targets.csv`

按现有优先级排序处理全部风险行动项：

1. `defer_research` 项自动处置为 `defer_until_margin_returns`。
2. 排名前 5 的 `priority_research` 项保留为 `manual_deep_dive_required`。
3. 其余 `priority_research` 和 `watchlist_review` 项保守分流为 `continue_tracking`，不视为买入批准。

输出每项的核心风险、估值敏感性、买入条件、放弃条件、重新进入人工复核条件和处置原因。聚合字段包括总行动项、自动分流数、待人工项、触顶数量及触顶比例。待人工项上限固定为 5；若生成结果超过 5，状态必须为 `needs_attention`。

## 研究条件生成规则

### 买入条件

- 当前价格不高于正式建议买入价。
- 估值置信度不得为 `low`。
- 若目标价触顶，必须人工复核未封顶估值、三档敏感性和估值方法分散度。
- 存在收入、利润、现金流或负债风险时，最新报告必须显示风险停止恶化或能够由一次性因素解释。
- 弱趋势本身不构成永久放弃，但要求价格和相对基准走势稳定后再进入买入讨论。

### 放弃条件

- 当前价格持续高于建议买入价且安全边际无法恢复。
- 收入或净利润恶化持续、自由现金流不能支持估值，或负债风险继续上升。
- 估值方法高度分散且低置信度问题无法补证。
- 关键事实与候选论文相反，或者正式目标价降至当前价以下。

## 自动化接入

- 新增 PowerShell 包装脚本和 JSON/Markdown/CSV 产物。
- 周收口在候选风险优先研究复核后生成风险处置报告。
- 提交前复核要求处置报告新鲜、结构完整、`formal_model_change_allowed=false` 且待人工项不超过 5。
- 统一周结论展示风险行动总数、自动分流数、待人工数和触顶诊断。
- 中期目标看板以待人工数作为“未完成风险项”，保留原始 15 项作为审计总量。

## 输出

- `outputs/automation/latest_candidate_risk_resolution_review.json`
- `outputs/automation/latest_candidate_risk_resolution_review.md`
- `outputs/automation/candidate_risk_resolution_review.csv`

## 验收

- 正式估值结果在新增字段前后完全一致。
- 触顶候选明确标识，不再把接近 60% 描述成精确预测。
- 当前 15 个风险行动项全部进入处置报告，待人工深研项不超过 5。
- 每个前 5 优先研究项均具有敏感性、核心风险、买入条件和放弃条件。
- 提交前复核和周结论能读取新产物，正式模型保持不变。
