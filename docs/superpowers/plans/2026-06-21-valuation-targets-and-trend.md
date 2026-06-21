# 12个月目标价与走势跟踪 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为美股、A股和港股候选公司生成可解释的12个月目标价、建议买入价、趋势判断和可追踪的每周预测历史。

**Architecture:** 新增独立的历史行情适配器和候选估值引擎。行情适配器将 Yahoo Chart 日线统一为标准 CSV；估值引擎合并候选池、行业中位数、当前报价与历史行情，计算混合公允价、质量调整、趋势分类并追加预测历史。三条现有周脚本只负责编排与失败传播。

**Tech Stack:** Python 3 标准库、`urllib`、CSV/JSON、`unittest`、PowerShell 5、Codex cron automation。

**Repository note:** `F:\chatgptssd\project2` 当前不是 Git 仓库，因此本计划不包含无法执行的提交步骤；每个任务以测试通过和产物核验作为检查点。

---

## 文件结构

- Create: `candidate_price_history.py`：三市场 Yahoo 代码映射、日线抓取、缓存、覆盖率校验和标准 CSV 输出。
- Create: `candidate_valuation.py`：趋势特征、混合估值、置信度、报告和预测历史。
- Create: `tests/test_candidate_price_history.py`：行情适配器单元测试。
- Create: `tests/test_candidate_valuation.py`：趋势、估值、历史记录与输出测试。
- Modify: `scripts/run_cn_weekly.ps1`：筛选后追加行情与估值步骤。
- Modify: `scripts/run_hk_weekly.ps1`：筛选后追加行情与估值步骤。
- Modify: `scripts/run_us_universe_weekly.ps1`：研究包后追加行情与估值步骤。
- Modify: `tests/test_regional_weekly_scripts.py`：验证 A/H 编排。
- Modify: `tests/test_weekly_automation.py`：验证美股编排。
- Modify: `docs/美股每周自动运行说明.md`：补充三市场目标价产物与口径。

### Task 1: 三市场历史行情适配器

**Files:**
- Create: `candidate_price_history.py`
- Create: `tests/test_candidate_price_history.py`

- [ ] **Step 1: 写入代码映射与 Yahoo 响应解析的失败测试**

```python
import unittest
from candidate_price_history import provider_symbol, parse_yahoo_history

class CandidatePriceHistoryTests(unittest.TestCase):
    def test_provider_symbol_maps_three_markets(self):
        self.assertEqual(provider_symbol("US", "BRK.B"), "BRK-B")
        self.assertEqual(provider_symbol("CN", "600519.SH"), "600519.SS")
        self.assertEqual(provider_symbol("CN", "000001.SZ"), "000001.SZ")
        self.assertEqual(provider_symbol("HK", "01530.HK"), "1530.HK")

    def test_parse_yahoo_history_skips_null_close(self):
        payload = {"chart": {"result": [{
            "timestamp": [1704067200, 1704153600],
            "indicators": {"quote": [{"close": [10.0, None]}]},
        }], "error": None}}
        rows = parse_yahoo_history("CN", "600519.SH", payload)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["close"], 10.0)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m unittest tests.test_candidate_price_history -v`

Expected: FAIL，错误为 `ModuleNotFoundError: candidate_price_history`。

- [ ] **Step 3: 实现代码映射、URL 和响应解析**

```python
def provider_symbol(market, ticker):
    ticker = ticker.upper()
    if market == "US":
        return ticker.replace(".", "-")
    if market == "CN" and ticker.endswith(".SH"):
        return ticker[:-3] + ".SS"
    if market == "CN" and ticker.endswith(".SZ"):
        return ticker
    if market == "HK" and ticker.endswith(".HK"):
        return f"{int(ticker[:-3])}.HK"
    raise ValueError(f"Unsupported ticker: {market} {ticker}")

def build_history_url(market, ticker):
    symbol = quote(provider_symbol(market, ticker), safe=".-")
    return f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1y&interval=1d&events=history"
```

`parse_yahoo_history` 必须输出 `market,ticker,date,close,source,data_status`，日期使用 UTC 时间戳转换出的 ISO 日期，空收盘价直接跳过。

- [ ] **Step 4: 增加缓存、覆盖率和运行入口测试**

测试用临时目录与注入的 `fetcher` 覆盖以下行为：成功抓取写入 `price_history.csv` 和每只股票 JSON 缓存；网络失败时使用不超过10天的缓存；候选覆盖率低于 `0.80` 抛出 `RuntimeError`；零候选时输出空文件并成功退出。

- [ ] **Step 5: 实现 `run_price_history` 和 CLI**

```python
def run_price_history(candidates_path, output_path, cache_dir, market,
                      minimum_coverage=0.80, cache_max_age_days=10,
                      fetcher=None):
    """返回 candidates、ready、coverage、output、cache_fallbacks。"""
```

CLI 参数固定为：`--market`、`--candidates`、`--output`、`--cache-dir`、`--minimum-coverage`、`--cache-max-age-days`。写正式输出前先完成覆盖率校验，失败时不得覆盖原文件。

- [ ] **Step 6: 运行行情适配器测试**

Run: `python -m unittest tests.test_candidate_price_history -v`

Expected: PASS，且不存在真实网络依赖。

### Task 2: 趋势特征与分类

**Files:**
- Create: `candidate_valuation.py`
- Create: `tests/test_candidate_valuation.py`

- [ ] **Step 1: 写入趋势计算失败测试**

```python
from candidate_valuation import calculate_trend

def test_uptrend_uses_only_past_prices(self):
    closes = [100 + i * 0.2 for i in range(252)]
    trend = calculate_trend(closes)
    assert trend["trend_label"] == "偏强"
    assert trend["history_days"] == 252
    assert trend["ma20"] > trend["ma60"] > trend["ma120"]

def test_short_history_is_insufficient(self):
    trend = calculate_trend([10.0] * 59)
    assert trend["trend_label"] == "数据不足"
    assert trend["trend_confidence"] == "low"
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m unittest tests.test_candidate_valuation.CandidateTrendTests -v`

Expected: FAIL，错误为缺少 `candidate_valuation` 或 `calculate_trend`。

- [ ] **Step 3: 实现趋势指标**

`calculate_trend(closes)` 计算 20/60/120 日简单均线、首尾12个月动量、日收益率样本标准差乘 `sqrt(252)`、52周高低点位置。分类规则固定为：

```python
if len(closes) < 60:
    label = "数据不足"
elif len(closes) >= 120 and close > ma20 > ma60 > ma120 and momentum > 0.10:
    label = "偏强"
elif close > ma60 and momentum > 0:
    label = "温和偏强"
elif close < ma60 and momentum < -0.10:
    label = "偏弱"
else:
    label = "中性"
```

历史不少于120日为 `high`，60至119日为 `medium`，不足60日为 `low`。

- [ ] **Step 4: 运行趋势测试**

Run: `python -m unittest tests.test_candidate_valuation.CandidateTrendTests -v`

Expected: PASS。

### Task 3: 混合估值与安全边际

**Files:**
- Modify: `candidate_valuation.py`
- Modify: `tests/test_candidate_valuation.py`

- [ ] **Step 1: 写入公允价、权重重分配和上限测试**

```python
from candidate_valuation import value_candidate

def test_blended_target_and_high_confidence_margin(self):
    row = {
        "market": "A股", "ticker": "TEST.SZ", "price": "100",
        "pe": "10", "pb": "2", "industry_pe_median": "15",
        "industry_pb_median": "3", "profitability_score": "25",
        "balance_sheet_score": "15", "cash_flow_score": "10",
        "growth_score": "10", "confidence": "high",
    }
    result = value_candidate(row, trend={"trend_label": "中性"})
    assert result["target_price"] <= 160.0
    assert result["buy_price"] == round(result["target_price"] * 0.80, 2)
    assert result["margin_of_safety"] == 0.20

def test_missing_fcf_renormalizes_pe_pb_weights(self):
    result = value_candidate(valid_row_without_fcf(), trend={})
    assert result["pe_weight_used"] == 0.625
    assert result["pb_weight_used"] == 0.375
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m unittest tests.test_candidate_valuation.CandidateValuationTests -v`

Expected: FAIL，错误为缺少 `value_candidate`。

- [ ] **Step 3: 实现统一估值公式**

固定边界与公式：

```python
target_pe = clamp(industry_pe_median, 5.0, 40.0)
target_pb = clamp(industry_pb_median, 0.5, 8.0)
pe_fair = price * target_pe / pe
pb_fair = price * target_pb / pb
fcf_fair = price * fcf_yield / 0.05
base_weights = {"pe": 0.50, "pb": 0.30, "fcf": 0.20}
target_price = min(weighted_fair * quality_factor, price * 1.60)
```

仅正数估值项有效；有效权重重新归一化。质量系数优先使用 ROE、ROIC、现金流、增长和负债原始字段；美股缺少原始字段时，以盈利、资产负债、现金流和增长分项得分归一化计算，最终限制在 `0.85..1.10`。

安全边际：高置信度20%、中置信度25%、低置信度30%。估值方法少于两项、趋势数据不足或各方法最大值/最小值大于2.5时，至少降为低置信度。

- [ ] **Step 4: 增加异常值与状态测试**

覆盖非正 PE/PB、缺失行业中位数、目标价低于当前价、三项均无效和估值分歧大于2.5倍。无有效估值项时 `valuation_status=insufficient_data` 且目标价为空；目标价低于当前价时 `price_action=等待回调/当前无安全边际`。

- [ ] **Step 5: 运行估值测试**

Run: `python -m unittest tests.test_candidate_valuation.CandidateValuationTests -v`

Expected: PASS。

### Task 4: 输入合并、报告和预测历史

**Files:**
- Modify: `candidate_valuation.py`
- Modify: `tests/test_candidate_valuation.py`

- [ ] **Step 1: 写入三类输入合并测试**

A/H 从候选行读取 `price` 和行业中位数；美股从 `--quotes` 按 ticker 合并当前价，从 `--industry-medians` 按 `market,industry` 合并 PE/PB 中位数。测试必须证明美股缺少报价时只标记该股票，不污染其他股票。

- [ ] **Step 2: 写入输出和历史去重测试**

使用临时目录执行两次相同生成日期：`valuation_targets.csv` 与 `valuation_report.md` 被本批次更新，`forecast_history.csv` 只保留一条唯一键；改用下一日期后历史增加一条且旧记录不变。

- [ ] **Step 3: 运行测试并确认失败**

Run: `python -m unittest tests.test_candidate_valuation.CandidateOutputTests -v`

Expected: FAIL，错误为缺少 `run_candidate_valuation`。

- [ ] **Step 4: 实现运行入口与原子输出**

```python
def run_candidate_valuation(candidates_path, price_history_path, output_root,
                            market, industry_medians_path=None,
                            quotes_path=None, generated_date=None):
    """生成 valuation_targets.csv、forecast_history.csv 和 valuation_report.md。"""
```

`valuation_targets.csv` 至少包含：`market,ticker,company_name,currency,current_price,target_price,buy_price,expected_return,pe_fair_price,pb_fair_price,fcf_fair_price,quality_factor,margin_of_safety,trend_label,trend_confidence,valuation_confidence,valuation_status,price_action,reason,price_date,financial_report_date,generated_date,model_version`。

模型版本固定为 `valuation_trend_v1`。正式结果先写临时文件，再使用 `Path.replace` 更新，避免失败时留下半成品。

- [ ] **Step 5: 实现 CLI 与中文报告**

CLI 参数：`--market`、`--candidates`、`--price-history`、`--output-root`、可选 `--industry-medians`、可选 `--quotes`、可选 `--generated-date`。报告表格展示股票、当前价、目标价、买入价、预期收益率、趋势、置信度与理由，并包含研究用途风险提示。

- [ ] **Step 6: 运行完整估值模块测试**

Run: `python -m unittest tests.test_candidate_valuation -v`

Expected: PASS。

### Task 5: 接入三市场周流程

**Files:**
- Modify: `scripts/run_cn_weekly.ps1`
- Modify: `scripts/run_hk_weekly.ps1`
- Modify: `scripts/run_us_universe_weekly.ps1`
- Modify: `tests/test_regional_weekly_scripts.py`
- Modify: `tests/test_weekly_automation.py`

- [ ] **Step 1: 先修改脚本测试并确认失败**

A/H 测试要求脚本包含 `candidate_price_history.py`、`candidate_valuation.py`、`valuation_targets.csv` 和 `valuation_trend_v1`。美股有序步骤由5步变为7步，新增 `6/7 Fetch candidate price history` 和 `7/7 Generate valuation targets`。

Run: `python -m unittest tests.test_regional_weekly_scripts tests.test_weekly_automation -v`

Expected: FAIL，因为现有脚本尚未调用新模块。

- [ ] **Step 2: 修改 A/H 周脚本**

筛选完成后依次运行：

```powershell
& $Python -B candidate_price_history.py --market CN --candidates $candidatesPath --output $historyPath --cache-dir $historyCache --minimum-coverage 0.80
if ($LASTEXITCODE -ne 0) { throw "CN candidate price history failed with exit code $LASTEXITCODE." }
& $Python -B candidate_valuation.py --market CN --candidates $candidatesPath --price-history $historyPath --industry-medians (Join-Path $OutputRoot "industry_medians.csv") --output-root $OutputRoot
if ($LASTEXITCODE -ne 0) { throw "CN candidate valuation failed with exit code $LASTEXITCODE." }
```

港股使用 `HK`。摘要增加估值模型、估值文件和估值报告路径；只有估值成功后才写摘要。

- [ ] **Step 3: 修改美股周脚本**

保留现有五步，在研究包之后增加行情和估值。估值命令额外传入 `--quotes data\samples\us_universe_quotes.csv` 和 `--industry-medians outputs\us_universe\industry_medians.csv`。摘要增加目标价文件和报告路径。

- [ ] **Step 4: 运行脚本测试与 DryRun**

Run: `python -m unittest tests.test_regional_weekly_scripts tests.test_weekly_automation -v`

Expected: PASS；三个 DryRun 均不创建输出目录。

### Task 6: 文档、真实运行、自动任务和最终验证

**Files:**
- Modify: `docs/美股每周自动运行说明.md`
- Runtime outputs: `outputs/{us_universe,cn_universe,hk_universe}/valuation_targets.csv`
- Runtime outputs: `outputs/{us_universe,cn_universe,hk_universe}/forecast_history.csv`
- Runtime outputs: `outputs/{us_universe,cn_universe,hk_universe}/valuation_report.md`

- [ ] **Step 1: 更新中文使用说明**

说明12个月周期、PE/PB/FCF权重、质量系数、目标价1.60倍上限、安全边际、走势分类、输出路径、失败边界及“仅供研究，不构成投资建议”。

- [ ] **Step 2: 运行全量自动化测试**

Run: `python -m unittest discover -s tests -v`

Expected: 所有测试 PASS，零 failure、零 error。

- [ ] **Step 3: 编译和脚本语法检查**

Run: `python -m py_compile candidate_price_history.py candidate_valuation.py regional_financials.py regional_value_screener.py`

Run: PowerShell Parser 对 `scripts\*.ps1` 全量解析。

Expected: 两条命令退出码均为0。

- [ ] **Step 4: 真实运行三市场周流程**

按 A股、港股、美股顺序运行；美股传入既有 `SEC_USER_AGENT`。若受限网络阻止访问，使用批准后的联网权限完整重跑，不得用失败批次的中间结果验收。

Expected: 候选行情覆盖率不低于80%；每个有有效估值的目标价不超过当前价1.60倍；预测历史成功追加且相同日期重跑不重复。

- [ ] **Step 5: 更新三条 Codex 自动任务提示词**

保持周日14:05、14:25、14:45和当前工作目录不变。三条提示词增加读取 `valuation_targets.csv` 与 `valuation_report.md`，中文汇报目标价、建议买入价、预期收益率、趋势、置信度、数据警告和路径。

- [ ] **Step 6: 核对新产物和自动任务状态**

检查三个输出目录的文件修改时间、行数、模型版本、异常状态和预测历史唯一键；读取三个 automation TOML，确认 `ACTIVE`、原计划时间、`valuation_trend_v1` 与新产物名称。

- [ ] **Step 7: 最终验收记录**

汇报三市场候选数、行情覆盖率、成功估值数、低置信度数、无安全边际数、测试数量和所有可核对输出路径。明确列出仍缺失的数据与模型限制。
