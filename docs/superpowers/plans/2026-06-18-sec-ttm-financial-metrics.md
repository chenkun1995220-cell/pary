# SEC TTM Financial Metrics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 SEC 美股标准行自动计算 TTM 与核心财务质量指标，并接入真实样本流水线。

**Architecture:** 新建独立 `sec_financial_metrics.py` 解析 Company Facts 期间事实并增强标准 CSV。现有 SEC 适配器不承担派生计算，PowerShell 流水线在 SEC 导入后调用增强层。

**Tech Stack:** Python 标准库、CSV、unittest、PowerShell。

---

### Task 1: TTM 和年度历史计算

**Files:**
- Create: `sec_financial_metrics.py`
- Test: `tests/test_sec_financial_metrics.py`

- [ ] 先写失败测试，覆盖 `latest_ttm_value()` 的“财年 + 当期累计 - 上年同期”公式和年度回退。
- [ ] 运行 `python -B -m unittest tests.test_sec_financial_metrics`，确认因模块缺失失败。
- [ ] 实现事实筛选、年度历史和 TTM 计算。
- [ ] 重跑测试并确认通过。

### Task 2: 派生财务指标

**Files:**
- Modify: `sec_financial_metrics.py`
- Modify: `tests/test_sec_financial_metrics.py`

- [ ] 先写失败测试，覆盖毛利率、EBITDA、流动比率、CAGR、ROIC、净负债/EBITDA。
- [ ] 实现 `calculate_financial_metrics()`，缺失事实时留空。
- [ ] 重跑局部测试并确认通过。

### Task 3: CSV 增强和流水线接入

**Files:**
- Modify: `sec_financial_metrics.py`
- Modify: `scripts/run_us_real_sample.ps1`
- Modify: `scripts/run_weekly_screening.ps1`
- Test: `tests/test_sec_financial_metrics.py`

- [ ] 写失败测试，要求 fixture 批量增强标准 CSV。
- [ ] 实现 CLI 与 CSV 写入。
- [ ] 在 SEC 导入和行情补充之间调用增强层。
- [ ] 运行真实样本 fixture/联网流程，确认增强字段进入评分结果。

### Task 4: 文档与完整验证

**Files:**
- Modify: `docs/真实美股样本跑通包.md`

- [ ] 记录指标公式、回退策略和限制。
- [ ] 运行全量 unittest。
- [ ] 检查 PowerShell 语法。
- [ ] 重新生成真实样本报告并对比分数变化。

