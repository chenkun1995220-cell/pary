# S&P 500 历史证据上限收口设计

## 目标

将 S&P 500 历史成分证据从“每周持续补充官方来源”改为“证据上限已确认、仅保留受限回测”。保留全部历史缺口、证据等级和 verified 比例作为审计事实，但停止把已证明不可得的官方来源作为每周人工待办或中期目标缺口，同时继续禁止扩大正式回测样本、自动更新历史成分文件或自动升级正式模型。

## 权威策略

新增 `data/config/sp500_historical_evidence_policy.json`：

- `policy_schema=sp500_historical_evidence_policy`
- `policy_version=1`
- `status=evidence_ceiling_confirmed`
- `effective_date=2026-07-11`
- `official_source_acquisition_closed=true`
- `limited_backtest_only=true`
- `recurring_supplement_request_enabled=false`
- `formal_backtest_expansion_allowed=false`
- `historical_membership_auto_update_allowed=false`
- `formal_model_change_allowed=false`

策略文件记录关闭依据和允许的后续动作。若未来用户提供新的可靠官方历史证据，必须通过单独人工评审修改策略版本，不能由周度任务自动重新开启。

## 回测证据复核

`backtest_evidence_review.py` 读取策略文件。策略生效时：

- `status=evidence_ceiling_confirmed`
- `recommended_action=maintain_limited_backtest`
- `backtest_mode=limited_verified_only`
- `membership_evidence_unresolved_gap_count` 保留真实缺口总数
- `membership_evidence_action_required_count=0`
- `membership_evidence_action_queue=[]`
- `backtest_sample_expansion_allowed=false`
- `backtest_sample_expansion_decision=do_not_expand_backtest_sample`
- `membership_evidence_gate_status=blocked`
- `membership_evidence_gate_decision=verified_only_no_expansion`

原始回测摘要中的 `Evidence next action` 仅保存为 `source_evidence_next_action`，不得继续驱动待办。

## 周度流程

从 `scripts/run_weekly_reporting_bundle.ps1` 删除历史补证链：

- import plan
- supplement queue / batch
- source intake status / verified intake import
- official export probe / verified source plan
- apply preview / confirmation / approved apply plan

保留当前成分股交叉校验、严格时点回测和回测证据复核。历史补证脚本本身暂不删除，作为只读历史工具保留，但不再每周自动执行。

## 下游收口

- 自我分析：识别 `evidence_ceiling_confirmed`，不再输出 `review_backtest_evidence` 或补证建议。
- 每周行动清单：禁止生成 `supplement_verified_membership_evidence`、`review_backtest_evidence`、历史证据 apply 动作。
- 中期目标：模块改为“S&P 500 受限回测证据边界”，完成度 100%，下一步为 `maintain_limited_backtest`。
- 统一结论：显示“证据上限已确认”和 `limited_verified_only`，同时明确 `no_sample_expansion`。
- 提交前复核：当策略生效时，不再要求历史补证产物保持新鲜或存在；反向检查受限回测字段和周行动清单，发现补证动作重新出现则 `needs_attention`。

当前成分股来源仍使用交叉校验替代策略，当前成员缺失、交叉校验失效或来源异常仍须按原规则处理；本设计只关闭历史证据补强任务。

## 验收标准

1. 回测复核保留真实缺口数，但行动数和队列均为 0。
2. 正式回测扩样、历史成员自动更新和正式模型变更均为 false。
3. 周度脚本不再运行历史补证链。
4. 自我分析、行动清单和中期目标不再要求补充官方历史来源。
5. 统一结论明确“证据上限已确认、仅保留受限回测”。
6. 提交前复核为 ready，且能拦截任何重新出现的历史补证动作或扩样权限。
7. 当前成分股交叉校验和三市场交付检查不受影响。

## 非目标

- 不删除历史缺口或伪造 verified 比例。
- 不把 secondary / weak 证据升级为 verified。
- 不扩大正式回测样本。
- 不修改估值、预测、评分或交易逻辑。
- 不关闭当前成分股每周交叉校验。
