# 候选深研底稿接入设计

## 目标

让每周候选风险处置自动读取 `data/manual/candidate_risk_deep_dive_reviews.csv`，区分“研究已完成”和“仍需人工决策”，避免已经完成的深研在每周重跑后再次显示为未研究，同时不把研究建议转换成买入批准。

## 数据契约

底稿按股票代码匹配当前 `manual_deep_dive_required` 项。只有同时满足以下条件才计为已完成：

- `review_status=completed`
- `research_recommendation` 属于 `continue_tracking`、`downgrade_to_watchlist`、`defer_until_better_entry`、`maintain_priority_research`
- `decision_boundary=research_only_no_buy_approval`
- `financial_evidence`、`risk_evidence`、`source_1`、`source_2` 均非空

底稿可以包含不在本周前五的历史股票；这些记录保留但不计入本周完成数。缺失或不合格记录不会阻断候选交付，只会保持对应深研待办。

## 产物变化

`latest_candidate_risk_resolution_review.json` 新增：

- `deep_dive_required_count`
- `deep_dive_completed_count`
- `deep_dive_pending_count`
- `deep_dive_review_source`

每个待深研项目新增 `deep_dive_review`，包含状态、研究建议、证据摘要、来源和研究边界。`manual_pending_count` 继续表示人工授权待办，不因研究完成而清零。

## 下游规则

- 周结论展示深研完成数和待办数。
- 中期看板在深研待办为0时把候选研究模块提升至95%，下一步改为 `continue_candidate_monitoring`。
- 提交前复核验证计数一致、已完成条目的字段完整、所有条目保持 `research_only_no_buy_approval`。
- 正式模型参数、候选评分、建议买入价和目标价均不受该底稿自动修改。

## 验收

- 当前5个待深研股票全部匹配底稿，输出 `deep_dive_completed_count=5`、`deep_dive_pending_count=0`。
- `manual_pending_count` 仍为5，证明人工授权边界未被绕过。
- 周结论、中期看板、交付检查和提交前复核均可为 `ready`。
- 完整测试通过，正式模型变更仍为不允许。
