# 三市场 Codex 自动化时间

截至 2026-07-05，三市场自动化任务按北京时间每周日下午运行：

| 市场 | 自动化 id | 时间 | 状态 | 说明 |
|---|---|---:|---|---|
| 美股 | `us-weekly` | 14:05 | 保持既有配置 | S&P 500 当前成分来源优先使用交叉校验替代文件。 |
| A 股 | `a-300` | 14:10 | ACTIVE | 运行沪深 300 每周筛选。 |
| 港股 | `automation-3` | 14:15 | ACTIVE | 运行恒生大型股/中型股每周筛选，并作为三市场周筛收口任务。 |

A 股和港股任务已从旧时间调整为：

- A 股：`FREQ=WEEKLY;INTERVAL=1;BYDAY=SU;BYHOUR=14;BYMINUTE=10`
- 港股：`FREQ=WEEKLY;INTERVAL=1;BYDAY=SU;BYHOUR=14;BYMINUTE=15`

旧 Windows 计划任务不作为当前调度入口；当前以 Codex 自动化任务为准。
