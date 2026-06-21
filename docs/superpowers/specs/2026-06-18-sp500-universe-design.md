# 标普 500 全量股票池设计

## 1. 目标

把当前 15 家美股种子池替换为动态更新的标普 500 成分股池，并继续复用现有行情补齐、SEC 财务指标、行业中位数、低估评分、每周报告和候选深研流程。

成功标准：

- 每周从公开成分表更新股票池。
- 导入成分表中的全部证券行，不按名称强制截断为 500 行。
- 在线名单不可用或校验失败时，使用最后一次成功缓存。
- 约 500 家公司的 SEC Company Facts 在一次周任务中只下载一次，并供后续步骤复用。
- 输出名单来源、抓取时间、在线或缓存状态、总数和异常代码。

## 2. 数据来源与缓存

使用 Wikipedia `List of S&P 500 companies` 页面作为成分股来源，通过 MediaWiki API 获取页面解析后的 HTML。读取第一张成分股表中的代码、公司名、GICS 行业、GICS 子行业、CIK 和加入日期。

本地文件：

```text
data/cache/sp500/sp500_constituents.csv
data/cache/sp500/sp500_source.json
data/cache/sp500/sp500_refresh_metadata.json
data/cache/sec_companyfacts/CIK##########.json
```

成分股缓存采用“下载到临时文件、校验、原子替换”方式。在线结果必须满足以下条件才能覆盖最后一次有效缓存：

- 证券行数在 450 到 550 之间。
- 标准化后的股票代码唯一。
- 股票代码、公司名、GICS 行业和 CIK 均非空。
- CIK 为数字。

在线抓取失败或校验失败时，如果存在有效缓存则继续运行并记录 `cache_fallback`；不存在缓存时终止任务，不生成伪造名单。

## 3. 股票代码与行业标准化

保留来源代码 `source_ticker`，新增标准代码 `ticker`。点号类别股转换为连字符格式，例如 `BRK.B` 转为 `BRK-B`、`BF.B` 转为 `BF-B`，以匹配 SEC 和 Yahoo 接口。

GICS 十一个一级行业映射为中文标准行业：

| GICS 行业 | 标准行业 |
|---|---|
| Information Technology | 信息技术 |
| Health Care | 医疗保健 |
| Financials | 金融 |
| Consumer Discretionary | 可选消费 |
| Industrials | 工业 |
| Communication Services | 通信服务 |
| Consumer Staples | 日常消费 |
| Energy | 能源 |
| Utilities | 公用事业 |
| Real Estate | 房地产 |
| Materials | 原材料 |

行业映射配置继续由 `data/config/industry_aliases.csv` 管理，不在评分代码中硬编码。

## 4. 组件边界

新增 `sp500_constituents.py`，只负责抓取、解析、标准化、校验和缓存成分股名单。它输出兼容现有 `us_universe_builder.py` 的 symbols CSV，并返回刷新元数据。

扩展 `sec_edgar_adapter.py` 的 Company Facts 加载接口，支持共享缓存目录、缓存有效期和失败时读取旧缓存。`quote_auto_filler.py`、`sec_edgar_adapter.py`、`sec_financial_metrics.py` 使用同一缓存目录。

更新 `scripts/build_us_universe.ps1`，先刷新标普 500 symbols，再与 SEC ticker/exchange 列表核对并生成公司配置。更新 `scripts/run_us_universe_weekly.ps1`，把总流程调整为：

1. 刷新标普 500 成分股名单。
2. 构建 SEC 公司配置。
3. 下载或复用 Company Facts 缓存并补齐行情。
4. 执行财务指标、行业中位数和低估评分。
5. 生成每周报告和候选深研包。

## 5. 错误处理与可观测性

- 成分股在线源失败：使用最后有效缓存，并在周报摘要中提示。
- SEC 单家公司下载失败：有旧缓存则使用旧缓存并记录警告；无缓存则记录该公司失败，不用空值覆盖已有有效文件。
- SEC 名单无法匹配的代码：写入缺失列表；匹配率低于 98% 时阻止评分流程。
- 行情或财务字段缺失：继续沿用现有数据质量门禁，不让严重缺失公司进入候选池。
- 每周摘要增加股票池总数、名单更新时间、缓存状态、SEC 成功数、失败数和候选数。

## 6. 测试策略

所有网络行为使用本地 fixture 测试，不依赖实时网站：

- 解析 Wikipedia 成分表 HTML。
- 特殊股票代码标准化。
- 拒绝行数不足、重复代码和缺少必填字段的名单。
- 在线失败时读取最后有效缓存，无缓存时明确失败。
- Company Facts 新缓存写入、有效缓存复用和旧缓存回退。
- 总控脚本演练模式展示新增步骤且不写文件。
- 完整测试集通过后，再执行一次真实名单刷新；全量财务抓取留给 Codex 周任务运行，避免交互会话中重复请求约 500 家公司。

## 7. 非目标

- 本阶段不加入标普 400、标普 600 或非标普美股。
- 不改变现有低估评分权重和候选分数门槛。
- 不把 Wikipedia 公司描述或新闻文本用于自动投资结论。
- 不在来源校验失败时生成或猜测成分股。
