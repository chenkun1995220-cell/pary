# A股港股市场估值快照筛选实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为沪深300和港股大中盘接入批量行情、市值、PE、PB、ROE和行业，输出可解释的第一版相对估值候选名单。

**Architecture:** 使用东方财富批量列表接口按市场分批抓取快照，保留独立原始缓存并标准化为统一字段。新增区域市场专用评分器，只比较同市场同行业PE/PB和ROE，不复用依赖现金流与SEC数据的美股完整模型。

**Tech Stack:** Python 3标准库、CSV/JSON、PowerShell、unittest

---

### Task 1: 批量市场快照适配器

**Files:**
- Create: `regional_market_snapshot.py`
- Create: `tests/test_regional_market_snapshot.py`

- [ ] 写失败测试覆盖市场代码转换、批量响应解析、百分比单位和缺失代码。
- [ ] 运行 `python -m unittest tests.test_regional_market_snapshot -v` 确认失败。
- [ ] 实现 `ticker_to_secid`、`parse_eastmoney_snapshot` 和分批抓取。
- [ ] 再次运行测试确认通过。

标准输出字段包含：

```text
market,ticker,company_name,industry,currency,price,market_cap,pe,pb,roe,quote_date,source,data_quality_status
```

### Task 2: 区域相对估值评分器

**Files:**
- Create: `regional_value_screener.py`
- Create: `tests/test_regional_value_screener.py`

- [ ] 写失败测试覆盖市场行业中位数、低估得分、无效负PE排除和中文理由。
- [ ] 运行目标测试确认失败。
- [ ] 实现100分制快照模型：PE 35分、PB 25分、ROE 25分、数据完整性10分、指数流动性5分。
- [ ] 候选门槛65分，并要求PE、PB、ROE为正且行业样本不少于5。
- [ ] 输出完整结果、候选池、行业中位数和中文周报。

### Task 3: 接入A股和港股周脚本

**Files:**
- Modify: `scripts/run_cn_weekly.ps1`
- Modify: `scripts/run_hk_weekly.ps1`
- Modify: `tests/test_regional_weekly_scripts.py`

- [ ] 先写失败测试，要求脚本包含快照和正式评分步骤。
- [ ] 接入 `regional_market_snapshot.py` 和 `regional_value_screener.py`。
- [ ] 摘要增加候选数量、代码和报告路径，不再显示 `pending adapter`。
- [ ] 运行脚本测试和PowerShell语法检查。

### Task 4: 真实运行与自动任务更新

**Files:**
- Runtime outputs: `outputs/cn_universe/*`, `outputs/hk_universe/*`
- Modify: `docs/美股每周自动运行说明.md`
- Update: A股、港股Codex自动化提示词

- [ ] 真实批量抓取两个市场快照并执行评分。
- [ ] 检查数据覆盖率、行业样本、候选数与异常值。
- [ ] 更新两个Codex任务，按真实候选池和报告汇报。
- [ ] 运行完整测试、Python编译和自动任务配置核验。

本模型只作为阶段1相对估值初筛。现金流、增长、资产负债、审计与治理数据接入后，将升级为更完整模型并保留版本对比。
