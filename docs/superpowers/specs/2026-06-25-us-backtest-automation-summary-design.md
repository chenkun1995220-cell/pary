# 美股严格时点回测自动化摘要设计

## 背景

美股严格时点回测已经输出 `backtest_report.md`、`replay_manifest.csv`、`checkpoint.json` 和泄漏审计文件，并且报告中已经包含成员证据覆盖情况。当前缺口是：定时任务或人工复核需要打开长报告才能确认本次回测是否完成、证据覆盖是否可靠、输出文件在哪里。

## 目标

在 `scripts/run_us_point_in_time_backtest.ps1` 完成运行后，写入 `outputs/automation/latest_backtest_summary.md`，作为严格时点回测的自动化摘要入口。

## 非目标

- 不改变回测模型、评分、候选生成或质量门规则。
- 不把严格时点回测摘要混入美股周筛的 `latest_run_summary.md`。
- 不处理本地行情样本文件 `data/samples/us_universe_quotes.csv` 的已有改动。

## 输出文件

`outputs/automation/latest_backtest_summary.md`

摘要内容固定包含：

- 运行时间
- 输出目录
- 回放周数
- 失败周数
- 成员证据 `verified` 比例
- 弱证据行数
- 回测报告路径
- 泄漏审计路径
- 模型对比路径
- 日志路径

## 数据来源

- `checkpoint.json`：成功周数、失败周数、批次信息。
- `backtest_report.md`：成员证据覆盖段落。
- 脚本运行时变量：输出目录、报告路径、模型对比路径、泄漏审计路径、日志路径。

## 错误处理

摘要只在回测 runner 成功完成后写入。若准备输入或回测步骤失败，脚本继续按现有异常路径退出，并保留 transcript 日志用于排查。

## 测试

在 `tests/test_weekly_automation.py` 中增加脚本静态测试，确认 `run_us_point_in_time_backtest.ps1` 声明并写入 `latest_backtest_summary.md`，且摘要包含关键字段和输出路径。
