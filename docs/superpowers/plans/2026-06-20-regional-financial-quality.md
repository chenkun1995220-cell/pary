# A股港股财务质量增强实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为A股和港股候选补齐财务质量、资产负债、现金流和增长字段，并升级区域评分模型。

**Architecture:** 使用东方财富财务主指标接口按20家公司批量查询，A股和港股使用不同报告名与字段映射，统一输出标准财务字段。行情估值快照与财务快照按ticker合并后交给 `regional_fundamental_v2` 模型评分。

**Tech Stack:** Python 3、CSV/JSON、urllib、PowerShell、unittest

---

### Task 1: 批量财务适配与缓存

- Create: `regional_financials.py`
- Create: `tests/test_regional_financials.py`

- [ ] 写失败测试覆盖批量过滤器、A股字段、港股字段、百分比单位、最新报告选择和缺失证券。
- [ ] 实现批量接口、原始JSON缓存和标准CSV。
- [ ] 输出收入、净利润、经营现金流、ROE、ROIC、毛利率、流动比率、负债率、收入增长、利润增长、报告日期和报告口径。

### Task 2: 基本面评分模型V2

- Modify: `regional_value_screener.py`
- Modify: `tests/test_regional_value_screener.py`

- [ ] 先写失败测试要求模型版本升级并纳入ROIC、现金流、负债和增长。
- [ ] 实现100分权重：估值40、盈利质量25、资产负债15、现金流10、增长10。
- [ ] 保留PE/PB为正、ROE不低于5%、行业样本不少于5的硬门槛。
- [ ] 财务覆盖不足时标记低置信度，不伪造缺失分数。

### Task 3: 周脚本与自动任务

- Modify: `scripts/run_cn_weekly.ps1`
- Modify: `scripts/run_hk_weekly.ps1`
- Modify: `tests/test_regional_weekly_scripts.py`
- Update: A股和港股Codex自动化提示词

- [ ] 将流程改为成分股、行情快照、财务快照、V2评分。
- [ ] 摘要增加财务覆盖率、模型版本和候选数量。
- [ ] 真实运行两个市场，核验候选无负PE、低ROE和严重财务缺失。
- [ ] 完整测试、编译、脚本语法和自动任务配置全部通过。
