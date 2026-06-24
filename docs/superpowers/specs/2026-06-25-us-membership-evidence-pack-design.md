# 美股历史成分证据包导入层设计

## 目标

为美股严格时点回测增加一个可人工维护、可审计的历史成分证据包导入层，使部分历史成分事件能够从 `secondary` 升级为 `verified`，从而逐步解除 `membership_not_verified` 质量门限制。

该能力只处理“历史成分证据等级”，不修改估值模型、候选筛选规则、SEC 财务截断、行情截断或模型升级门槛。

## 背景

当前 `historical_sp500.py` 已支持 `verified`、`secondary`、`insufficient` 三档证据，并且只有官方 S&P Global 来源链接可以让事件保持 `verified`。`backtest_membership_inputs.py` 为机械试跑生成历史成员名单时，只基于本地当前股票池和 `date_added` 生成周度成员，因此默认全部标记为 `secondary`。

20 家真实样本回测已经验证 SEC 与行情链路可用，质量门现在主要卡在 `membership_not_verified`。下一步不应放宽质量门，而应引入更可靠的历史成分证据输入。

## 推荐方案

新增本地证据包文件：

`data/config/us_sp500_membership_evidence.csv`

建议字段：

```csv
effective_date,added_ticker,removed_ticker,membership_evidence,membership_source_url,notes
```

字段含义：

- `effective_date`：成分变动生效日期，格式为 `YYYY-MM-DD`。
- `added_ticker`：加入标普500的股票代码。
- `removed_ticker`：被移出的股票代码。
- `membership_evidence`：人工录入的证据等级，只允许 `verified`、`secondary`、`insufficient`。
- `membership_source_url`：证据来源链接。
- `notes`：人工说明，不参与逻辑判断。

证据升级规则：

- 当 `membership_evidence=verified` 且 `membership_source_url` 是 `https://spglobal.com` 或 `https://*.spglobal.com` 时，该事件可以保持 `verified`。
- 非官方来源、空来源、非 HTTPS、带用户名密码、非标准端口或仿冒域名，即使写入 `verified`，也必须自动降级为 `secondary`。
- `secondary` 和 `insufficient` 不会被自动升级。
- 证据包缺失时，回测仍按当前逻辑执行机械试跑，生成的周度成员继续为 `secondary`。

## 数据流

1. `scripts/run_us_point_in_time_backtest.ps1` 检查是否存在 `data/config/us_sp500_membership_evidence.csv`。
2. 存在时，将证据包路径传给 `backtest_membership_inputs.py`。
3. `backtest_membership_inputs.py` 读取当前股票池，并读取证据包。
4. 证据包事件经过 `historical_sp500.py` 的事件校验和官方来源降级逻辑。
5. 生成 `historical_membership.csv` 时，周度成员的 `membership_evidence` 使用对应历史事件或当前成员证据。
6. `us_weekly_replay.py` 继续使用现有质量门：只有当周所有成员均为 `verified`，该周才不会触发 `membership_not_verified`。

## 错误处理

- 证据包字段缺失、日期非法、证据等级非法、加入/移除代码不完整时，回测准备阶段应失败并打印明确错误。
- 证据包为空时不失败，只等同于没有可升级证据。
- 证据包中的非官方 `verified` 来源不失败，但必须降级为 `secondary`。
- 如果某个事件无法应用到当前成员恢复链路，应失败，避免产生看似可信但实际错误的历史名单。

## 测试策略

新增或扩展测试覆盖：

- 官方 S&P Global 来源的 `verified` 事件可以保留为 `verified`。
- 非官方来源写入 `verified` 会降级为 `secondary`。
- 证据包缺失时，现有机械试跑行为保持不变。
- 证据包字段非法时，准备阶段失败并保留清晰错误。
- PowerShell 回测入口包含证据包默认路径，但 dry run 不写文件、不联网。

## 不做的事

- 不放宽 `membership_not_verified` 质量门。
- 不自动抓取或爬取官方历史成分来源。
- 不把 Wikipedia、当前成分表或本地 `date_added` 直接升级为 `verified`。
- 不自动修改 `valuation_trend_v1` 或任何正式模型参数。

## 后续扩展

证据包机制跑通后，可以分批人工补入最近 12 个月、24 个月、36 个月的官方历史成分事件。每批补入后用 `-MaxCompanies` 小样本和 `-FullRun` 局部验证，再决定是否扩大到完整标普500回测。
