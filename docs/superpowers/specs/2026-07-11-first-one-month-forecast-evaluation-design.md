# 首批1个月预测评价设计

## 背景与目标

P2 要求在 2026-08-03 之后自动评价首批 37 个1个月预测样本，并将同一批样本的1周结果作为对照，分别输出方向命中率、超额收益、市场差异与失败类型。样本不足或尚未成熟时必须明确标记，不形成正式模型优劣结论，也不得自动修改 `valuation_trend_v1`。

当前证据已确认：首批样本来自港股 `generated_date=2026-07-06`，样本数为 37，1周评价日为 2026-07-13，1个月评价日为 2026-08-03，短周期预测字段缺失数为 0。

## 范围

本模块只读取三市场现有 `forecast_history.csv` 与 `forecast_evaluations.csv`，生成独立的首批1个月评价复核产物，并接入周度收口和提交前复核。

本模块不抓取行情、不重新生成预测、不重新评分、不修改候选排序、不写入预测历史或评价明细、不形成正式模型升级结论。

## 方案选择

采用独立评价层，而不是继续扩充综合预测表现报告。

原因：

1. 可以固定首批 37 个样本，避免后续批次改变分母。
2. 可以独立表达“尚未到期”“部分成熟”“完整可复核”三种状态。
3. 可以将1周与1个月指标严格分开，避免综合指标混合不同周期。
4. 可以在提交前复核中设置专属契约，而不影响通用预测表现模块。

## 首批样本契约

固定队列：

- 市场：`HK`
- 预测生成日期：`2026-07-06`
- 预期样本数：`37`
- 1周预期评价日期：`2026-07-13`
- 1个月预期评价日期：`2026-08-03`
- 正式模型版本：读取样本中的 `model_version`，预期为 `valuation_trend_v1`

样本唯一键：

`market + ticker + generated_date + model_version`

评价唯一键：

`market + ticker + generated_date + model_version + prediction_horizon`

评价层必须先从 `forecast_history.csv` 构造固定队列，再到 `forecast_evaluations.csv` 中按唯一键关联。不能直接取评价文件中“最近37行”，也不能把后续预测批次补入分母。

## 状态机

顶层 `status` 只允许：

- `awaiting_maturity`：尚未到 2026-08-03，或1个月成熟评价数为 0。
- `sample_incomplete`：已到评价日，但固定队列、1周或1个月有效评价不足 37。
- `review_ready`：固定队列正好 37 个样本，1周和1个月各有 37 个唯一、有效评价。
- `needs_attention`：输入缺失、结构异常、重复唯一键、队列被污染、正式模型边界不安全或日期逻辑冲突。

`review_ready` 只表示统计证据完整，不表示模型表现优秀或允许升级。

## 分层指标

顶层输出固定队列摘要和两个周期对象：`one_week`、`one_month`。

每个周期包含：

- `expected_sample_count`
- `matched_evaluation_count`
- `valid_evaluation_count`
- `missing_evaluation_count`
- `direction_hits`
- `direction_hit_rate`
- `average_return`
- `average_benchmark_return`
- `average_excess_return`
- `positive_excess_return_count`
- `failure_type_counts`
- `failure_samples`
- `market_results`

市场结果使用相同字段。首批队列当前只有港股，因此市场差异必须明确输出：港股有样本，美股和A股为 `not_in_cohort`，不得伪造跨市场比较。后续其他市场出现独立首批队列时，可沿用同一结构，但不得混入本次 37 样本。

## 失败类型

每条未命中或无法评价的记录只能进入一个主失败类型：

- `opposite_direction`：预测上涨但实际下跌，或预测下跌但实际上涨。
- `predicted_neutral_but_moved`：预测中性，实际上涨或下跌。
- `predicted_move_but_actual_neutral`：预测上涨或下跌，实际中性。
- `missing_prediction_signal`：预测方向字段缺失或无法归一化。
- `evaluation_missing`：固定队列样本没有对应周期评价。
- `evaluation_not_mature`：到当前日期仍处于正常等待成熟窗口。
- `return_data_missing`：实际收益、基准收益或超额收益无法解析。

方向命中记录不计入失败类型。失败样例必须包含市场、ticker、公司名、生成日期、周期、预测方向、实际方向、实际收益、超额收益和失败类型。

## 市场差异

输出 `market_comparison`：

- 三市场各自队列数、有效评价数、命中率和平均超额收益。
- 无样本市场标记 `not_in_cohort`。
- 只有一个市场存在有效样本时，`cross_market_comparison_status=insufficient_market_coverage`。
- 至少两个市场存在有效样本时，才允许输出最高/最低命中率市场和超额收益差异。

本次首批 37 样本预期只能报告港股内部结果和“市场覆盖不足”，不能据此推断模型在三市场的相对优劣。

## 输出

新增：

- `outputs/automation/latest_first_one_month_forecast_evaluation_review.json`
- `outputs/automation/latest_first_one_month_forecast_evaluation_review.md`

JSON 固定包含：

- `review_schema=first_one_month_forecast_evaluation_review`
- `review_version=1`
- `as_of_date`
- `status`
- `cohort`
- `one_week`
- `one_month`
- `market_comparison`
- `issues`
- `recommended_action`
- `formal_model_change_allowed=false`
- `formal_model_conclusion_allowed=false`
- `boundary`

推荐动作：

- `wait_for_one_month_maturity`
- `repair_first_cohort_evaluation_gaps`
- `review_first_one_month_results_manually`
- `repair_first_one_month_review_inputs`

## 周度链路集成

新增 PowerShell 包装入口，并在每周预测跟踪和综合预测表现复核之后运行。随后刷新自我分析、行动清单、周结论、交付检查、中期目标和提交前复核，使所有下游产物读取同一次 P2 状态。

提交前复核要求：

- 文件存在且 schema/version 正确。
- 状态属于允许集合。
- 固定队列和两个周期的计数字段完整。
- `formal_model_change_allowed=false`。
- `formal_model_conclusion_allowed=false`。
- 2026-08-03 之前允许 `awaiting_maturity`，但不得误报为缺陷。
- 2026-08-03 之后若不足37个有效样本，必须为 `sample_incomplete` 或 `needs_attention`，不得标记 `review_ready`。

港股自动任务最终汇报读取该产物，分别报告1周与1个月样本数、命中率、平均超额收益、失败类型、市场覆盖边界和推荐动作。

## 异常处理

- 输入文件缺失或列缺失：`needs_attention`，列出精确文件和字段。
- 队列少于或多于37：`needs_attention`，不得改变预期分母。
- 队列唯一键重复：`needs_attention`，输出重复键数量与样例。
- 评价唯一键重复：按唯一键拒绝静默去重，`needs_attention`。
- 到期后评价不足：`sample_incomplete`，输出缺失 ticker 和周期。
- 尚未到期：`awaiting_maturity`，缺失1个月评价归为正常等待，不进入修复待办。
- 正式模型边界字段不是 `false`：提交前复核阻断。

## 测试与验收

至少覆盖：

1. 2026-08-03 前 37 个队列完整但1个月未成熟，状态为 `awaiting_maturity`。
2. 到期后1个月评价不足37，状态为 `sample_incomplete`。
3. 1周和1个月各37条有效评价，状态为 `review_ready`。
4. 两个周期指标独立计算，不混用分母。
5. 七类失败原因正确分类且每条最多一个主类型。
6. 只有港股样本时市场比较明确标记覆盖不足。
7. 队列或评价出现重复唯一键时阻断。
8. 缺失预测信号或收益字段时不进入有效评价分母。
9. 包装脚本、周度顺序、提交前复核和自动任务契约完整。
10. 正式模型代码和参数无变化，全项目测试通过。

## 完成边界

代码和自动链路完成后，P2 进入“已准备、等待真实到期数据”状态。只有 2026-08-03 之后真实运行产生 37 个1个月有效评价，并由独立产物验证为 `review_ready`，才可认定 P2 数据验收完成。
