# SEC TTM 财务指标增强层 V1 设计

## 目标

在现有 SEC Company Facts 适配器之后增加独立派生层，自动补齐筛选器需要的 TTM 与质量指标，减少因字段空白造成的低分。

## 架构

新增 `sec_financial_metrics.py`。它接收单家公司 Company Facts 和现有标准行，输出增强后的标准行。`sec_edgar_adapter.py` 继续负责原始事实标准化，增强层只负责期间计算和派生指标，避免职责混杂。

真实样本流水线调整为：

```text
SEC 标准化
-> SEC TTM/派生指标增强
-> 行情与市值补充
-> 行业映射
-> 行业中位数
-> 质检与评分
```

## 指标口径

- TTM 流量指标：优先使用“最近财年 + 最新累计期 - 上年同期累计期”。无法形成可比累计期时回退最近财年。
- 毛利率：`GrossProfit / Revenue`；缺少 GrossProfit 时使用 `(Revenue - CostOfRevenue) / Revenue`。
- EBITDA：`OperatingIncomeLoss + DepreciationDepletionAndAmortization`。
- 流动比率：`AssetsCurrent / LiabilitiesCurrent`。
- 3 年 CAGR：使用最近财年与三年前财年，按实际年差计算。
- ROIC：`NOPAT / (Equity + Debt - Cash)`；NOPAT 使用经营利润乘以 `(1 - 有效税率)`，税率限制在 0 到 35%。
- 净负债/EBITDA：`(Debt - Cash) / EBITDA`。
- 每个增强行增加 `metrics_period_basis`，值为 `ttm`、`annual_fallback` 或 `partial`。

## 错误处理

缺少某项事实时对应指标留空，不用零值代替。单项缺失不阻断其他指标。所有写入继续使用 UTF-8 BOM CSV。

## 测试

使用本地 Company Facts fixture 覆盖：TTM 公式、年度回退、毛利率、EBITDA、流动比率、CAGR、ROIC、净负债/EBITDA，以及 CSV 批量增强。

