# 2026-07-18 可立即执行的治理优化设计

## 目标

在不修改正式选股、估值和预测模型参数的前提下，修正当前自动化治理层的三个可验证问题：

1. 中期目标仍输出 Sunday 命名的动作代码，与已迁移到周六的自动化计划不一致。
2. 人工复核积压会同时触发 `review_manual_review_backlog` 和泛化的
   `review_delivery_health_issues`，重复表达同一个问题。
3. 三市场 PowerShell 入口没有统一声明 UTF-8 输出，中文日志在部分 Codex/终端采集链路中乱码。

## 行为约束

- 周六验收正在积累时输出 `continue_consecutive_saturday_validation`。
- 本周运行正常但因非计划时段人工验证导致周六时间窗不满足时，输出
  `validate_next_scheduled_saturday_delivery`。
- 其他周六交付证据异常输出 `repair_current_saturday_delivery_evidence`。
- `manual_review_pending:*` 只触发 `review_manual_review_backlog`。
- 只有非镜像交付原因、缺失结论信号或修复指向才触发
  `review_delivery_health_issues`。
- 三个市场入口均设置 PowerShell 与 Python 的 UTF-8 输出编码。

## 验证

- 先增加会失败的单元测试并确认失败。
- 实施最小修复后运行相关测试和全量测试。
- 重新生成只读治理产物，确认交付健康重复待办消失，周六动作代码更新。

