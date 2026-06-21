# 预测跟踪与模型审计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每周跟踪三市场历史预测，在4、12、26、52周生成不可覆盖的正式评价，并输出模型审计与受控影子优化建议。

**Architecture:** 扩展现有 Yahoo 行情适配器以保存复权价和公司行动，新增独立 `forecast_tracker.py` 计算预测表现，新增 `model_audit.py` 汇总评价并执行最小样本门槛。三个周脚本在估值完成后依次调用跟踪器和审计器，正式估值模型保持只读。

**Tech Stack:** Python 3 标准库、Yahoo Chart JSON、CSV/Markdown、`unittest`、PowerShell 5、Codex cron automation。

**Repository note:** 当前目录不是 Git 仓库，任务检查点使用失败测试、通过测试和真实产物验证，不包含无法执行的提交步骤。

---

## 文件结构

- Modify: `candidate_price_history.py`：解析复权收盘价、分红和拆股事件，并支持基准代码。
- Modify: `tests/test_candidate_price_history.py`：复权行情与公司行动测试。
- Create: `data/config/market_benchmarks.csv`：三市场基准配置。
- Create: `forecast_tracker.py`：日期选择、收益、路径风险、周跟踪和正式评价。
- Create: `tests/test_forecast_tracker.py`：跟踪与评价单元测试。
- Create: `model_audit.py`：分组审计、样本门槛和影子建议。
- Create: `tests/test_model_audit.py`：审计与防过拟合测试。
- Modify: `scripts/run_us_universe_weekly.ps1`：追加跟踪与审计步骤。
- Modify: `scripts/run_cn_weekly.ps1`：追加跟踪与审计步骤。
- Modify: `scripts/run_hk_weekly.ps1`：追加跟踪与审计步骤。
- Modify: `tests/test_weekly_automation.py`：美股编排测试。
- Modify: `tests/test_regional_weekly_scripts.py`：A/H 编排测试。
- Modify: `docs/美股每周自动运行说明.md`：跟踪和审计说明。

### Task 1: 复权行情、公司行动和基准配置

**Files:**
- Modify: `candidate_price_history.py`
- Modify: `tests/test_candidate_price_history.py`
- Create: `data/config/market_benchmarks.csv`

- [ ] **Step 1: 写入复权行情解析失败测试**

```python
def test_parse_history_includes_adjusted_close_and_events(self):
    payload = {"chart": {"result": [{
        "timestamp": [1704067200],
        "indicators": {
            "quote": [{"close": [100.0]}],
            "adjclose": [{"adjclose": [98.0]}],
        },
        "events": {
            "dividends": {"1704067200": {"amount": 1.0}},
            "splits": {"1704067200": {"numerator": 2, "denominator": 1}},
        },
    }], "error": None}}
    row = parse_yahoo_history("US", "TEST", payload)[0]
    self.assertEqual(row["adjusted_close"], 98.0)
    self.assertEqual(row["dividend"], 1.0)
    self.assertEqual(row["split_ratio"], 2.0)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m unittest tests.test_candidate_price_history -v`

Expected: FAIL，缺少新字段或字段值为空。

- [ ] **Step 3: 扩展标准行情字段**

`HISTORY_FIELDS` 固定为：

```python
["market", "ticker", "date", "close", "adjusted_close",
 "dividend", "split_ratio", "source", "data_status"]
```

无 `adjclose` 时使用 `close` 并标记 `data_status=unadjusted_fallback`；正常复权为 `ready`。分红默认0，拆股默认1。异常非正拆股比例标记 `corporate_action_review`。

- [ ] **Step 4: 写入并验证基准配置**

创建：

```csv
market,benchmark_name,provider_symbol
US,S&P 500,^GSPC
CN,CSI 300,000300.SS
HK,Hang Seng Composite,^HSCI
```

增加测试确认三个市场均存在且代码唯一；真实运行前对三个代码执行联网探测，失败的基准必须报告，不得静默替换。

- [ ] **Step 5: 运行行情测试**

Run: `python -m unittest tests.test_candidate_price_history -v`

Expected: PASS。

### Task 2: 评价日期与单条预测计算

**Files:**
- Create: `forecast_tracker.py`
- Create: `tests/test_forecast_tracker.py`

- [ ] **Step 1: 写入到期判断和交易日选择失败测试**

```python
def test_due_checkpoints_and_previous_trading_day(self):
    due = due_checkpoints("2026-01-01", "2026-07-02")
    self.assertEqual(due, [4, 12, 26])
    row = latest_on_or_before(prices, "2026-02-01", tolerance_days=7)
    self.assertEqual(row["date"], "2026-01-30")
```

覆盖27/28天、83/84天、181/182天、363/364天边界，以及最近交易日超过7天返回 `None`。

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m unittest tests.test_forecast_tracker -v`

Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现日期函数**

```python
CHECKPOINTS = {4: 28, 12: 84, 26: 182, 52: 364}

def due_checkpoints(generated_date, as_of_date):
    elapsed = (date.fromisoformat(as_of_date) - date.fromisoformat(generated_date)).days
    return [weeks for weeks, days in CHECKPOINTS.items() if elapsed >= days]

def latest_on_or_before(rows, target_date, tolerance_days=7):
    target = date.fromisoformat(target_date)
    eligible = [
        row for row in rows
        if date.fromisoformat(row["date"]) <= target
    ]
    if not eligible:
        return None
    selected = max(eligible, key=lambda row: row["date"])
    age = (target - date.fromisoformat(selected["date"])).days
    return selected if age <= tolerance_days else None
```

所有日期使用 ISO 格式和 `datetime.date`，不得用行号或交易日数量代替自然日评价点。

- [ ] **Step 4: 写入收益与方向失败测试**

测试起始复权价100、评价价120、基准100到110、目标价130：实际收益20%、基准10%、超额10%、目标价误差 `10/130`、最大有利30%、最大不利-10%。预测和实际方向使用±5%阈值。

- [ ] **Step 5: 实现 `evaluate_forecast`**

```python
def evaluate_forecast(forecast, stock_prices, benchmark_prices,
                      as_of_date, checkpoint_weeks=None):
    """返回 tracking 或正式 checkpoint 评价，输入历史记录保持只读。"""
```

公司行动状态不是 `ready` 时返回 `corporate_action_review`；基准缺失时保留绝对收益并将基准和超额收益留空。

- [ ] **Step 6: 运行单条评价测试**

Run: `python -m unittest tests.test_forecast_tracker.ForecastCalculationTests -v`

Expected: PASS。

### Task 3: 跟踪快照、正式评价历史和报告

**Files:**
- Modify: `forecast_tracker.py`
- Modify: `tests/test_forecast_tracker.py`

- [ ] **Step 1: 写入运行入口失败测试**

临时目录包含两条预测、股票复权行情和基准行情。执行后断言：

- `tracking_snapshot.csv` 每条预测一行。
- 未到4周的记录为 `tracking`，不进入正式评价。
- 到4周的记录进入 `forecast_evaluations.csv`。
- 同日重跑不重复。
- 后续52周重跑只追加新评价点，不覆盖旧记录。

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m unittest tests.test_forecast_tracker.ForecastTrackerOutputTests -v`

Expected: FAIL，缺少 `run_forecast_tracking`。

- [ ] **Step 3: 实现运行入口和原子输出**

```python
def run_forecast_tracking(forecasts_path, stock_history_path,
                          benchmark_history_path, output_root,
                          market, as_of_date=None):
    """生成 tracking_snapshot.csv、forecast_evaluations.csv 和 performance_report.md。"""
```

评价唯一键为 `market,ticker,generated_date,model_version,checkpoint_weeks,evaluation_version`。`evaluation_version` 初始固定为 `forecast_eval_v1`。快照可原子替换，正式评价按唯一键追加去重。

- [ ] **Step 4: 实现中文表现报告**

报告列出跟踪数、到期数、数据不足、公司行动复核、方向命中率、平均绝对收益、平均超额收益、目标价误差和最大不利波动。无到期样本时写“样本积累中”。

- [ ] **Step 5: 实现 CLI**

参数固定为：`--market --forecasts --stock-history --benchmark-history --output-root --as-of-date`。

- [ ] **Step 6: 运行跟踪器全部测试**

Run: `python -m unittest tests.test_forecast_tracker -v`

Expected: PASS。

### Task 4: 模型审计和影子建议门槛

**Files:**
- Create: `model_audit.py`
- Create: `tests/test_model_audit.py`

- [ ] **Step 1: 写入样本不足失败测试**

```python
def test_less_than_thirty_mature_samples_only_reports_accumulating(self):
    result = audit_model(make_evaluations(29))
    self.assertEqual(result["audit_status"], "sample_accumulating")
    self.assertEqual(result["proposals"], [])
```

另测30条成熟样本但验证集少于15条仍不得产生升级建议。

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m unittest tests.test_model_audit -v`

Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现基础审计**

`audit_model(evaluations)` 按生成时间排序，汇总市场、行业、评分等级、置信度和模型版本；输出方向命中率、平均收益、平均超额收益、目标价误差和最大不利波动。低于30条时不运行候选参数比较。

- [ ] **Step 4: 写入时间切分和跨市场约束测试**

测试至少45条成熟记录，前70%为训练集、后30%为验证集且验证集不少于15条；输入顺序打乱后仍按日期切分。仅单一市场改善或尾部风险恶化时不得生成 `promote_candidate`。

- [ ] **Step 5: 实现受控影子比较**

首版只比较现有预测中的可解释分组，不搜索无限参数空间：

- 置信度安全边际20/25/30与统一25%的对照。
- 目标价1.60倍上限与1.40、1.50倍影子上限。
- 方向阈值5%与3%、8%的影子阈值。

影子结果必须包含训练区间、验证区间、样本数、命中率、平均超额收益、目标价误差和最大不利波动。只有跨至少两个市场、验证集改善且风险未恶化时状态可为 `review_candidate`；永远不写正式配置。

- [ ] **Step 6: 实现输出与 CLI**

```python
def run_model_audit(evaluations_path, tracking_path, output_root, as_of_date=None):
    """生成 model_audit.md 和 shadow_model_proposals.csv。"""
```

无成熟样本时仍生成审计报告和仅有表头的影子 CSV。

- [ ] **Step 7: 运行审计测试**

Run: `python -m unittest tests.test_model_audit -v`

Expected: PASS。

### Task 5: 基准行情抓取和三市场周流程集成

**Files:**
- Modify: `candidate_price_history.py`
- Modify: `scripts/run_us_universe_weekly.ps1`
- Modify: `scripts/run_cn_weekly.ps1`
- Modify: `scripts/run_hk_weekly.ps1`
- Modify: `tests/test_weekly_automation.py`
- Modify: `tests/test_regional_weekly_scripts.py`

- [ ] **Step 1: 写入编排失败测试**

三条脚本必须包含 `forecast_tracker.py`、`model_audit.py`、`tracking_snapshot.csv`、`forecast_evaluations.csv` 和 `model_audit.md`。美股步骤从7步扩展为10步，新增基准行情、预测跟踪和模型审计；A/H 输出的 Steps 文案包含相同顺序。

- [ ] **Step 2: 运行脚本测试并确认失败**

Run: `python -m unittest tests.test_weekly_automation tests.test_regional_weekly_scripts -v`

Expected: FAIL，新模块尚未接入。

- [ ] **Step 3: 为行情适配器增加基准模式**

CLI 增加 `--symbols` 输入，接受 `market,ticker` CSV；基准输出写入各市场 `benchmark_history.csv`，缓存目录独立。股票候选模式保持兼容。

- [ ] **Step 4: 修改三条周脚本**

估值成功后依次：

1. 抓取本市场基准历史。
2. 运行 `forecast_tracker.py`。
3. 运行 `model_audit.py`。

任一步失败必须阻止本周摘要更新。摘要增加跟踪、评价、审计报告和影子建议路径。

- [ ] **Step 5: 运行 DryRun 与语法测试**

Run: `python -m unittest tests.test_weekly_automation tests.test_regional_weekly_scripts -v`

Run: PowerShell Parser 全量解析 `scripts/*.ps1`。

Expected: 全部 PASS，DryRun 不创建文件。

### Task 6: 文档、真实运行和自动任务更新

**Files:**
- Modify: `docs/美股每周自动运行说明.md`
- Runtime outputs: `outputs/{us_universe,cn_universe,hk_universe}/tracking_snapshot.csv`
- Runtime outputs: `outputs/{us_universe,cn_universe,hk_universe}/forecast_evaluations.csv`
- Runtime outputs: `outputs/{us_universe,cn_universe,hk_universe}/performance_report.md`
- Runtime outputs: `outputs/{us_universe,cn_universe,hk_universe}/model_audit.md`
- Runtime outputs: `outputs/{us_universe,cn_universe,hk_universe}/shadow_model_proposals.csv`

- [ ] **Step 1: 更新中文说明**

记录4/12/26/52周、±5%方向、市场基准、复权、80%覆盖率、30条成熟样本、15条验证样本和正式模型不自动修改。

- [ ] **Step 2: 运行全量测试、编译和脚本语法检查**

Run: `python -m unittest discover -s tests -v`

Run: `python -m py_compile candidate_price_history.py forecast_tracker.py model_audit.py`

Expected: 零 failure、零 error，编译和语法检查退出码0。

- [ ] **Step 3: 联网验证三个基准代码**

分别抓取配置中的三个基准一年日线。任何代码失败时停止对应市场跟踪，不静默换指数；记录真实错误和缓存状态。

- [ ] **Step 4: 真实运行三市场周流程**

验证股票预测覆盖率和基准覆盖率不低于80%，三市场均生成五个新产物。首批预测尚未满4周，因此正式评价行为0或仅包含合法历史到期记录，审计报告明确“样本积累中”，影子建议不得出现 `review_candidate`。

- [ ] **Step 5: 更新三条 Codex 自动任务**

保持周日14:05、14:25、14:45。提示词增加读取表现报告、模型审计和影子建议；要求中文汇报成熟样本数、跟踪数、基准缺失、公司行动异常和是否存在人工审核候选。

- [ ] **Step 6: 最终验收**

检查所有产物时间戳、唯一键、评价版本、样本门槛、无目标价上限回归和三条任务 `ACTIVE`。最终报告明确首批样本尚未到期，不能据此评价模型优劣。
