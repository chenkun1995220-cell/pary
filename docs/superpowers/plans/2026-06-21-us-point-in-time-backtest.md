# 美股近3年严格时点回测实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立近3年、周频、可断点续跑且无未来数据泄漏的美股事件驱动回测，并输出正式模型与影子参数的样本外比较。

**Architecture:** 新增独立的历史名单、SEC时点截断、行情截止、单周重放和影子回测模块，复用现有 `calculate_financial_metrics()`、`score_stock()`、`run_candidate_valuation()` 与 `evaluate_forecast()`。所有结果写入 `outputs/backtests/us_3y_weekly`，正式周任务目录和正式模型配置保持只读。

**Tech Stack:** Python 3 标准库、CSV/JSON、现有 SEC Company Facts 缓存、Yahoo Chart、`unittest`、PowerShell、Git。

---

## 文件结构

- Create: `historical_sp500.py`：历史增删事件解析、成员反向恢复与证据等级。
- Create: `sec_point_in_time.py`：按 `filed` 日期截断 Company Facts 并生成时点指标。
- Create: `historical_price_store.py`：三年行情抓取、缓存与回测日期截断。
- Create: `us_weekly_replay.py`：单周重放、覆盖率质量门和不可修改预测输出。
- Create: `backtest_manifest.py`：批次摘要、周状态、检查点和断点续跑。
- Create: `shadow_backtest.py`：滚动窗口、正式/影子比较和升级门槛。
- Create: `scripts/run_us_point_in_time_backtest.ps1`：8周试跑和156周完整运行入口。
- Create: `tests/test_historical_sp500.py`
- Create: `tests/test_sec_point_in_time.py`
- Create: `tests/test_historical_price_store.py`
- Create: `tests/test_us_weekly_replay.py`
- Create: `tests/test_backtest_manifest.py`
- Create: `tests/test_shadow_backtest.py`
- Modify: `docs/美股每周自动运行说明.md`：补充回测运行、输出和限制。

### Task 1: 历史标普500成员恢复

**Files:**
- Create: `historical_sp500.py`
- Create: `tests/test_historical_sp500.py`

- [ ] **Step 1: 写入反向恢复失败测试**

```python
from historical_sp500 import restore_membership


def test_restore_membership_reverses_events_after_as_of_date():
    current = {"NEW": {"ticker": "NEW", "company_name": "New Co"}}
    events = [{
        "effective_date": "2025-06-01",
        "added_ticker": "NEW",
        "removed_ticker": "OLD",
        "removed_company": "Old Co",
        "source_url": "https://example.test/event",
        "evidence_level": "verified",
    }]
    restored = restore_membership(current, events, "2025-05-25")
    assert set(restored) == {"OLD"}
    assert restored["OLD"]["membership_evidence"] == "verified"
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m unittest tests.test_historical_sp500 -v`

Expected: FAIL，提示 `No module named 'historical_sp500'`。

- [ ] **Step 3: 实现最小反向恢复与事件校验**

```python
from datetime import date


EVIDENCE_LEVELS = {"verified", "secondary", "insufficient"}


def restore_membership(current_rows, events, as_of_date):
    members = {key: dict(value) for key, value in current_rows.items()}
    cutoff = date.fromisoformat(as_of_date)
    ordered = sorted(events, key=lambda row: row["effective_date"], reverse=True)
    for event in ordered:
        if date.fromisoformat(event["effective_date"]) <= cutoff:
            continue
        level = event.get("evidence_level", "insufficient")
        if level not in EVIDENCE_LEVELS:
            raise ValueError(f"invalid evidence level: {level}")
        added = event.get("added_ticker", "").upper()
        removed = event.get("removed_ticker", "").upper()
        if added:
            members.pop(added, None)
        if removed:
            members[removed] = {
                "ticker": removed,
                "company_name": event.get("removed_company", ""),
                "membership_evidence": level,
                "membership_source_url": event.get("source_url", ""),
            }
    return members
```

- [ ] **Step 4: 增加代码变更、重复事件和证据不足测试**

测试要求：同日事件按输入顺序稳定处理；重复加入/移除抛出 `ValueError`；`insufficient` 成员保留但周次不可升级。

- [ ] **Step 5: 解析历史变更并生成历史成员文件**

增加 `parse_change_events_html(html_text)`，读取“Date / Added / Removed / Reason”列。历史网页事件默认标记为 `secondary`；只有配置了可核验一手 `source_url` 的事件才能标记为 `verified`。增加：

```python
MEMBERSHIP_FIELDS = [
    "week", "ticker", "company_name", "effective_date",
    "membership_evidence", "membership_source_url",
]


def build_weekly_membership(current_rows, events, weeks):
    output = []
    for week in sorted(weeks):
        members = restore_membership(current_rows, events, week)
        for ticker, row in sorted(members.items()):
            output.append({
                "week": week,
                "ticker": ticker,
                "company_name": row.get("company_name", ""),
                "effective_date": row.get("effective_date", ""),
                "membership_evidence": row.get("membership_evidence", "secondary"),
                "membership_source_url": row.get("membership_source_url", ""),
            })
    return output
```

使用原子CSV写入 `historical_membership.csv`，并测试156个周次按周和代码稳定排序。

- [ ] **Step 6: 运行测试并提交**

Run: `python -m unittest tests.test_historical_sp500 -v`

Expected: PASS。

```powershell
git add historical_sp500.py tests/test_historical_sp500.py
git commit -m "实现标普500历史成员恢复"
```

### Task 2: SEC时点财务截断

**Files:**
- Create: `sec_point_in_time.py`
- Create: `tests/test_sec_point_in_time.py`
- Reuse: `sec_financial_metrics.py`
- Reuse: `sec_edgar_adapter.py`

- [ ] **Step 1: 写入未来申报和未来重述隔离测试**

```python
from sec_point_in_time import filter_company_facts_as_of


def test_filter_company_facts_excludes_future_filing_and_restatement():
    payload = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
        {"val": 100, "end": "2024-12-31", "filed": "2025-02-01", "form": "10-K"},
        {"val": 120, "end": "2024-12-31", "filed": "2025-08-01", "form": "10-K"},
    ]}}}}}
    filtered = filter_company_facts_as_of(payload, "2025-03-01")
    rows = filtered["facts"]["us-gaap"]["Revenues"]["units"]["USD"]
    assert [row["val"] for row in rows] == [100]
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m unittest tests.test_sec_point_in_time -v`

Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现深拷贝截断与来源审计**

```python
import copy
from datetime import date


def filter_company_facts_as_of(payload, as_of_date):
    cutoff = date.fromisoformat(as_of_date)
    result = copy.deepcopy(payload)
    for taxonomy in result.get("facts", {}).values():
        for concept in taxonomy.values():
            for unit, entries in concept.get("units", {}).items():
                concept["units"][unit] = [
                    row for row in entries
                    if row.get("filed") and date.fromisoformat(row["filed"]) <= cutoff
                ]
    return result
```

- [ ] **Step 4: 增加时点指标接口**

实现：

```python
from sec_financial_metrics import calculate_financial_metrics


def calculate_metrics_as_of(payload, as_of_date):
    filtered = filter_company_facts_as_of(payload, as_of_date)
    metrics = calculate_financial_metrics(filtered)
    used_filed_dates = sorted({
        row["filed"]
        for taxonomy in filtered.get("facts", {}).values()
        for concept in taxonomy.values()
        for entries in concept.get("units", {}).values()
        for row in entries if row.get("filed")
    })
    metrics["backtest_date"] = as_of_date
    metrics["latest_source_filed"] = used_filed_dates[-1] if used_filed_dates else ""
    metrics["leakage_status"] = "ready"
    return metrics
```

- [ ] **Step 5: 测试空申报、无 `filed`、边界日期和原对象不变**

Run: `python -m unittest tests.test_sec_point_in_time tests.test_sec_financial_metrics -v`

Expected: PASS。

- [ ] **Step 6: 提交**

```powershell
git add sec_point_in_time.py tests/test_sec_point_in_time.py
git commit -m "实现SEC历史时点财务截断"
```

### Task 3: 三年行情存储与日期截止

**Files:**
- Create: `historical_price_store.py`
- Create: `tests/test_historical_price_store.py`
- Reuse: `candidate_price_history.py`

- [ ] **Step 1: 写入严格截止与复权价格测试**

```python
from historical_price_store import prices_available_as_of


def test_prices_available_as_of_excludes_future_rows():
    rows = [
        {"date": "2025-01-03", "adjusted_close": "10", "data_status": "ready"},
        {"date": "2025-01-06", "adjusted_close": "11", "data_status": "ready"},
    ]
    assert prices_available_as_of(rows, "2025-01-05") == [rows[0]]
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m unittest tests.test_historical_price_store -v`

Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现日期截止、覆盖率和异常公司行动隔离**

```python
from datetime import date


def prices_available_as_of(rows, as_of_date):
    cutoff = date.fromisoformat(as_of_date)
    return sorted(
        [row for row in rows if date.fromisoformat(row["date"]) <= cutoff],
        key=lambda row: row["date"],
    )


def price_coverage(tickers, rows):
    ready = {row["ticker"].upper() for row in rows if row.get("data_status") == "ready"}
    return len(ready & {ticker.upper() for ticker in tickers}) / len(tickers) if tickers else 1.0
```

- [ ] **Step 4: 增加Yahoo `range=5y` 抓取与原子缓存**

新增 `build_historical_url(ticker, range_name="5y")`，保留现有 `candidate_price_history.py` 的解析字段和Windows安全缓存名；网络失败只允许使用10天内完整缓存。

- [ ] **Step 5: 运行行情相关测试并提交**

Run: `python -m unittest tests.test_historical_price_store tests.test_candidate_price_history -v`

Expected: PASS。

```powershell
git add historical_price_store.py tests/test_historical_price_store.py
git commit -m "实现回测历史行情存储"
```

### Task 4: 回测批次清单与断点续跑

**Files:**
- Create: `backtest_manifest.py`
- Create: `tests/test_backtest_manifest.py`

- [ ] **Step 1: 写入配置摘要和幂等检查点测试**

```python
from backtest_manifest import config_digest, should_run_week


def test_completed_week_is_reused_only_for_same_config():
    digest = config_digest({"model": "valuation_trend_v1", "start": "2023-06-01"})
    row = {"week": "2025-01-05", "status": "completed", "config_digest": digest}
    assert should_run_week(row, digest) is False
    assert should_run_week(row, "different") is True
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m unittest tests.test_backtest_manifest -v`

Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现稳定摘要、原子JSON检查点与清单追加去重**

```python
import hashlib
import json


def config_digest(config):
    payload = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def should_run_week(row, digest):
    return not row or row.get("status") != "completed" or row.get("config_digest") != digest
```

检查点必须包含 `batch_id`、配置摘要、最后完成周、成功数、失败数和更新时间。`replay_manifest.csv` 以“批次 + 周次”为唯一键。

- [ ] **Step 4: 测试中断恢复、失败重试和不同配置新批次**

Run: `python -m unittest tests.test_backtest_manifest -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add backtest_manifest.py tests/test_backtest_manifest.py
git commit -m "实现回测断点与运行清单"
```

### Task 5: 单周严格时点重放

**Files:**
- Create: `us_weekly_replay.py`
- Create: `tests/test_us_weekly_replay.py`
- Reuse: `historical_sp500.py`
- Reuse: `sec_point_in_time.py`
- Reuse: `historical_price_store.py`
- Reuse: `stock_screener.py`
- Reuse: `industry_medians.py`
- Reuse: `candidate_valuation.py`

- [ ] **Step 1: 写入质量门失败测试**

```python
from us_weekly_replay import assess_week_quality


def test_week_is_ineligible_when_membership_or_coverage_fails():
    result = assess_week_quality(
        membership_evidence="secondary",
        quote_coverage=0.97,
        financial_coverage=0.90,
        benchmark_ready=True,
        leakage_errors=0,
    )
    assert result["eligible"] is False
    assert "membership_not_verified" in result["reasons"]
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m unittest tests.test_us_weekly_replay -v`

Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现质量门**

```python
def assess_week_quality(membership_evidence, quote_coverage, financial_coverage,
                        benchmark_ready, leakage_errors):
    reasons = []
    if membership_evidence != "verified": reasons.append("membership_not_verified")
    if quote_coverage < 0.95: reasons.append("quote_coverage_below_95pct")
    if financial_coverage < 0.80: reasons.append("financial_coverage_below_80pct")
    if not benchmark_ready: reasons.append("benchmark_missing")
    if leakage_errors: reasons.append("data_leakage_detected")
    return {"eligible": not reasons, "reasons": reasons}
```

- [ ] **Step 4: 实现 `replay_week()` 编排**

接口固定为：

```python
def replay_week(backtest_date, membership_rows, company_facts_by_cik,
                price_rows, benchmark_rows, output_root, config_digest):
    """生成单周输入、筛选结果、估值预测、质量状态和泄漏审计。"""
```

实现要求：

- 使用 `filter_company_facts_as_of()` 后再调用现有SEC标准化和指标计算。
- 行业中位数只从该周时点截面计算。
- 评分使用 `score_stock()`，候选阈值保持正式配置。
- 估值使用 `run_candidate_valuation(..., generated_date=backtest_date)`。
- `backtest_forecasts.csv` 唯一键为市场、股票、生成日和模型版本，只追加不覆盖。
- 每条预测保存 `input_available_at_max` 和 `week_eligible`。
- 每条输入证据写入泄漏审计；若 `available_at > generated_date`，记录为 `severe` 并令该周不可用。

```python
def leakage_findings(records, generated_date):
    findings = []
    for row in records:
        available_at = row.get("available_at", "")
        if available_at and available_at > generated_date:
            findings.append({
                "generated_date": generated_date,
                "ticker": row.get("ticker", ""),
                "severity": "severe",
                "available_at": available_at,
                "reason": "future_data_used",
            })
    return findings
```

每个批次原子更新 `data_leakage_audit.csv` 和中文 `data_leakage_audit.md`。

- [ ] **Step 5: 测试未来行情、未来财报和行业中位数不会进入预测**

Run: `python -m unittest tests.test_us_weekly_replay tests.test_sec_point_in_time tests.test_historical_price_store -v`

Expected: PASS。

- [ ] **Step 6: 提交**

```powershell
git add us_weekly_replay.py tests/test_us_weekly_replay.py
git commit -m "实现美股单周严格时点重放"
```

### Task 6: 历史预测评价

**Files:**
- Modify: `us_weekly_replay.py`
- Modify: `tests/test_us_weekly_replay.py`
- Reuse: `forecast_tracker.py`

- [ ] **Step 1: 写入4、12、26、52周评价整合测试**

构造一条2024-01-07预测和覆盖364天的股票/标普500复权行情，断言输出四条唯一评价，且超额收益等于股票收益减基准收益。

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m unittest tests.test_us_weekly_replay.WeeklyReplayEvaluationTests -v`

Expected: FAIL，评价输出尚未实现。

- [ ] **Step 3: 复用 `evaluate_forecast()` 写入回测评价**

```python
from forecast_tracker import CHECKPOINTS, evaluate_forecast


def evaluate_backtest_forecast(forecast, stock_rows, benchmark_rows):
    rows = []
    for weeks, days in CHECKPOINTS.items():
        as_of = (date.fromisoformat(forecast["generated_date"]) + timedelta(days=days)).isoformat()
        row = evaluate_forecast(forecast, stock_rows, benchmark_rows, as_of, weeks)
        row["backtest_eligible"] = forecast.get("week_eligible", "false")
        rows.append(row)
    return rows
```

`backtest_evaluations.csv` 只收录到评价日有足够行情的数据；公司行动异常保留但不进入模型成绩。

- [ ] **Step 4: 运行评价测试并提交**

Run: `python -m unittest tests.test_us_weekly_replay tests.test_forecast_tracker -v`

Expected: PASS。

```powershell
git add us_weekly_replay.py tests/test_us_weekly_replay.py
git commit -m "接入回测预测评价"
```

### Task 7: 滚动影子模型比较

**Files:**
- Create: `shadow_backtest.py`
- Create: `tests/test_shadow_backtest.py`
- Reuse: `model_audit.py`

- [ ] **Step 1: 写入104/26/13滚动窗口测试**

```python
from shadow_backtest import rolling_windows


def test_rolling_windows_use_time_order():
    weeks = [f"W{i:03d}" for i in range(156)]
    windows = rolling_windows(weeks, train_size=104, validation_size=26, step=13)
    assert windows[0] == (weeks[:104], weeks[104:130])
    assert windows[1] == (weeks[13:117], weeks[117:143])
    assert len(windows) == 3
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m unittest tests.test_shadow_backtest -v`

Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现滚动窗口、指标汇总和方案状态**

```python
def rolling_windows(weeks, train_size=104, validation_size=26, step=13):
    ordered = sorted(dict.fromkeys(weeks))
    windows = []
    start = 0
    while start + train_size + validation_size <= len(ordered):
        split = start + train_size
        windows.append((ordered[start:split], ordered[split:split + validation_size]))
        start += step
    return windows
```

候选方案至少包括方向阈值3%/8%、目标价上限1.4/1.5和统一安全边际25%。比较字段必须包含训练/验证区间、样本数、市场和行业数、方向命中率、平均超额收益、目标价误差、最大不利波动和95分位尾部误差。

`run_shadow_backtest()` 原子写入 `model_comparison.csv` 和中文 `backtest_report.md`。报告分别列出正式模型、每个影子方案、各滚动窗口、被拒绝原因和证据等级分布；没有2个有效验证窗口时，结论固定为“样本或证据积累中”。

- [ ] **Step 4: 实现升级门槛测试**

测试要求：少于2个有效窗口为 `analysis_candidate`；单行业改善为 `rejected`；超额收益提高但最大不利波动明显恶化为 `rejected`；多个窗口稳定改善且风险不恶化才是 `review_candidate`。

- [ ] **Step 5: 运行测试并提交**

Run: `python -m unittest tests.test_shadow_backtest tests.test_model_audit -v`

Expected: PASS。

```powershell
git add shadow_backtest.py tests/test_shadow_backtest.py
git commit -m "实现滚动影子模型比较"
```

### Task 8: CLI、8周试跑与完整批次入口

**Files:**
- Create: `scripts/run_us_point_in_time_backtest.ps1`
- Modify: `tests/test_weekly_automation.py`
- Modify: `docs/美股每周自动运行说明.md`

- [ ] **Step 1: 写入脚本静态与DryRun测试**

测试断言脚本包含 `historical_sp500.py`、`us_weekly_replay.py`、`shadow_backtest.py`、`-PilotWeeks 8`、`historical_membership.csv`、`replay_manifest.csv`、`model_comparison.csv`、`backtest_report.md`、`data_leakage_audit.md` 和 `checkpoint.json`，并且 `-DryRun` 不创建输出目录。

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m unittest tests.test_weekly_automation -v`

Expected: FAIL，脚本不存在。

- [ ] **Step 3: 实现PowerShell入口**

参数：

```powershell
param(
  [int]$Years = 3,
  [int]$PilotWeeks = 8,
  [string]$OutputRoot = "",
  [string]$SecUserAgent = $env:SEC_USER_AGENT,
  [switch]$FullRun,
  [switch]$DryRun
)
```

默认只运行8个分散周次；`-FullRun` 才运行近3年全部周次。脚本使用独立互斥锁、日志和退出码传播，不接入现有三条每周正式任务。

- [ ] **Step 4: 更新中文文档**

记录运行命令、目录、质量门、8周试跑、完整运行、断点恢复、SEC User-Agent、数据来源等级和“不得自动升级正式模型”。

- [ ] **Step 5: 运行脚本与文档测试并提交**

Run: `python -m unittest tests.test_weekly_automation -v`

Expected: PASS。

```powershell
git add scripts/run_us_point_in_time_backtest.ps1 tests/test_weekly_automation.py docs/美股每周自动运行说明.md
git commit -m "增加美股时点回测入口"
```

### Task 9: 真实8周试跑、泄漏审计和全量验证

**Files:**
- Runtime: `outputs/backtests/us_3y_weekly/`
- Modify when defects are found: corresponding module and test only

- [ ] **Step 1: 运行全量自动测试和编译**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -v
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m py_compile historical_sp500.py sec_point_in_time.py historical_price_store.py backtest_manifest.py us_weekly_replay.py shadow_backtest.py
```

Expected: 全部通过。

- [ ] **Step 2: 执行8周真实试跑**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\run_us_point_in_time_backtest.ps1 -PilotWeeks 8 -SecUserAgent "Your Name your-email@example.com"
```

Expected: 8个分散周次均写入 `replay_manifest.csv`；不合格周次有明确原因；任务中断可重跑。

- [ ] **Step 3: 核验泄漏、唯一键和正式文件不变**

核对：

- `data_leakage_audit.md` 严重泄漏数为0。
- `backtest_forecasts.csv` 和 `backtest_evaluations.csv` 唯一键无重复。
- 所有预测的 `input_available_at_max <= generated_date`。
- `candidate_valuation.py`、正式参数和 `outputs/us_universe/forecast_history.csv` 在回测前后内容摘要不变。
- `checkpoint.json` 与清单最后完成周一致。

- [ ] **Step 4: 生成中文8周试跑报告**

报告必须区分 `verified`、`secondary` 和 `insufficient` 周次，不得把二手证据周次作为升级依据。若有效窗口不足，结论固定为“样本或证据积累中”。

- [ ] **Step 5: 最终提交并推送**

```powershell
git add historical_sp500.py sec_point_in_time.py historical_price_store.py backtest_manifest.py us_weekly_replay.py shadow_backtest.py scripts/run_us_point_in_time_backtest.ps1 tests docs
git commit -m "完成美股严格时点回测试跑"
git push
```

完整156周运行仅在8周试跑全部验收通过后执行，并使用相同批次配置和断点机制。
