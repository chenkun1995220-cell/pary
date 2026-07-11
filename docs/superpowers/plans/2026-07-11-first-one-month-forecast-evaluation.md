# First One-Month Forecast Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 自动锁定港股 2026-07-06 首批37个预测样本，并在周度链路中分别评价1周和1个月的方向命中率、超额收益、市场覆盖与失败类型。

**Architecture:** 新建只读评价模块，从 `forecast_history.csv` 构造固定队列，再按复合唯一键关联 `forecast_evaluations.csv`，生成独立 JSON/Markdown。现有自我分析、周结论和提交前复核只消费该结构化产物，不重新计算评价，也不改变正式模型。

**Tech Stack:** Python 3 标准库、PowerShell、`unittest`、现有 JSON/Markdown 周度报告链路。

## Global Constraints

- 固定队列为港股 `generated_date=2026-07-06`、预期37个样本。
- 1周评价日为 `2026-07-13`，1个月评价日为 `2026-08-03`。
- 样本唯一键为 `market + ticker + generated_date + model_version`。
- 评价唯一键再加 `prediction_horizon`。
- 2026-08-03 前允许 `awaiting_maturity`，不得生成修复噪声。
- 到期后不足37个有效评价必须为 `sample_incomplete` 或 `needs_attention`。
- `formal_model_change_allowed=false` 且 `formal_model_conclusion_allowed=false`。
- 不抓取行情、不重新预测、不重新评分、不写预测历史、不修改 `valuation_trend_v1`。

---

### Task 1: 固定队列与分周期评价器

**Files:**
- Create: `first_one_month_forecast_evaluation_review.py`
- Create: `tests/test_first_one_month_forecast_evaluation_review.py`

**Interfaces:**
- Consumes: `build_review(project_root: Path, as_of_date: str) -> dict`
- Produces: schema 为 `first_one_month_forecast_evaluation_review` 的完整 payload；`write_report(payload: dict, path: Path) -> None`

- [ ] **Step 1: 写队列未到期的失败测试**

```python
def test_before_one_month_maturity_keeps_fixed_cohort_in_waiting_state(self):
    root = self.make_project(cohort_size=37, one_week_count=37, one_month_count=0)
    payload = build_review(root, as_of_date="2026-07-20")
    self.assertEqual(payload["status"], "awaiting_maturity")
    self.assertEqual(payload["cohort"]["expected_sample_count"], 37)
    self.assertEqual(payload["one_week"]["valid_evaluation_count"], 37)
    self.assertEqual(payload["one_month"]["valid_evaluation_count"], 0)
    self.assertEqual(payload["recommended_action"], "wait_for_one_month_maturity")
    self.assertFalse(payload["formal_model_change_allowed"])
    self.assertFalse(payload["formal_model_conclusion_allowed"])
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `python -m unittest tests.test_first_one_month_forecast_evaluation_review.FirstOneMonthForecastEvaluationReviewTests.test_before_one_month_maturity_keeps_fixed_cohort_in_waiting_state`

Expected: FAIL，原因是模块或 `build_review` 尚不存在。

- [ ] **Step 3: 实现读取、固定队列与状态骨架**

```python
REVIEW_SCHEMA = "first_one_month_forecast_evaluation_review"
REVIEW_VERSION = 1
COHORT_MARKET = "港股"
COHORT_GENERATED_DATE = "2026-07-06"
EXPECTED_SAMPLE_COUNT = 37
ONE_MONTH_MATURITY_DATE = date(2026, 8, 3)

def _cohort_key(row):
    return (
        row.get("market", ""), row.get("ticker", ""),
        row.get("generated_date", ""), row.get("model_version", ""),
    )

def _evaluation_key(row):
    return _cohort_key(row) + (row.get("prediction_horizon", ""),)
```

实现 `_read_csv_rows`、`_fixed_cohort`、`_index_evaluations`、`build_review`；输入限定为 `outputs/hk_universe/forecast_history.csv` 和三市场评价文件，固定队列数量异常进入 `needs_attention`。

- [ ] **Step 4: 增加到期不完整、完整和重复键测试**

```python
def test_after_maturity_requires_all_37_one_month_evaluations(self):
    payload = build_review(self.make_project(37, 37, 36), "2026-08-04")
    self.assertEqual(payload["status"], "sample_incomplete")
    self.assertEqual(payload["one_month"]["missing_evaluation_count"], 1)

def test_complete_cohort_is_review_ready(self):
    payload = build_review(self.make_project(37, 37, 37), "2026-08-04")
    self.assertEqual(payload["status"], "review_ready")

def test_duplicate_evaluation_key_needs_attention(self):
    root = self.make_project(37, 37, 37, duplicate_horizon="1m")
    payload = build_review(root, "2026-08-04")
    self.assertEqual(payload["status"], "needs_attention")
    self.assertIn("duplicate_evaluation_keys", payload["issues"])
```

- [ ] **Step 5: 实现两个周期指标与七类失败原因**

```python
def _failure_type(row):
    predicted = row.get("predicted_direction", "")
    actual = row.get("actual_direction", "")
    if not row.get("prediction_signal") or predicted in {"", "unknown"}:
        return "missing_prediction_signal"
    if _float_value(row.get("actual_return")) is None or _float_value(row.get("excess_return")) is None:
        return "return_data_missing"
    if predicted == actual:
        return None
    if predicted == "neutral":
        return "predicted_neutral_but_moved"
    if actual == "neutral":
        return "predicted_move_but_actual_neutral"
    return "opposite_direction"
```

固定队列缺失关联记录时按日期分别归为 `evaluation_not_mature` 或 `evaluation_missing`。每条记录只产生一个主失败类型。每周期独立计算命中率、平均收益、平均基准收益、平均超额收益和正超额收益数量。

- [ ] **Step 6: 增加市场覆盖与报告测试**

```python
def test_hk_only_cohort_does_not_claim_cross_market_comparison(self):
    payload = build_review(self.make_project(37, 37, 37), "2026-08-04")
    self.assertEqual(payload["market_comparison"]["status"], "insufficient_market_coverage")
    self.assertEqual(payload["market_comparison"]["markets"]["US"]["status"], "not_in_cohort")
    self.assertEqual(payload["market_comparison"]["markets"]["CN"]["status"], "not_in_cohort")
```

- [ ] **Step 7: 运行模块测试确认 GREEN**

Run: `python -m unittest tests.test_first_one_month_forecast_evaluation_review`

Expected: 全部 PASS。

- [ ] **Step 8: 提交核心评价器**

```powershell
git add first_one_month_forecast_evaluation_review.py tests/test_first_one_month_forecast_evaluation_review.py
git commit -m "feat: evaluate first one-month forecast cohort"
```

---

### Task 2: 命令入口与周度顺序

**Files:**
- Create: `scripts/run_first_one_month_forecast_evaluation_review.ps1`
- Modify: `scripts/run_weekly_reporting_bundle.ps1`
- Modify: `tests/test_first_one_month_forecast_evaluation_review.py`

**Interfaces:**
- Consumes: Task 1 CLI 参数 `--project-root`、`--as-of-date`、`--output`、`--report`
- Produces: `latest_first_one_month_forecast_evaluation_review.json/.md`

- [ ] **Step 1: 写包装器和顺序失败测试**

```python
def test_wrapper_and_bundle_run_after_forecast_performance_before_shadow_review(self):
    wrapper = (PROJECT_ROOT / "scripts/run_first_one_month_forecast_evaluation_review.ps1").read_text(encoding="utf-8-sig")
    bundle = (PROJECT_ROOT / "scripts/run_weekly_reporting_bundle.ps1").read_text(encoding="utf-8-sig")
    self.assertIn("first_one_month_forecast_evaluation_review.py", wrapper)
    self.assertLess(bundle.index("run_forecast_performance_review"), bundle.index("run_first_one_month_forecast_evaluation_review"))
    self.assertLess(bundle.index("run_first_one_month_forecast_evaluation_review"), bundle.index("run_one_week_forecast_shadow_review"))
```

- [ ] **Step 2: 运行测试确认 RED**

Expected: FAIL，包装器和 bundle 标签不存在。

- [ ] **Step 3: 实现 PowerShell 包装器和 CLI**

包装器沿用 `run_forecast_performance_review.ps1`，支持 `ProjectRoot`、`AsOfDate`、`Output`、`Report`、`DryRun`。CLI 必须使用 UTF-8 JSON 和 Markdown 输出，并在异常时返回非零退出码。

- [ ] **Step 4: 插入周度步骤**

```powershell
@{ Label = "run_forecast_performance_review"; Script = "run_forecast_performance_review.ps1"; Critical = $true },
@{ Label = "run_first_one_month_forecast_evaluation_review"; Script = "run_first_one_month_forecast_evaluation_review.ps1"; Critical = $true },
@{ Label = "run_one_week_forecast_shadow_review"; Script = "run_one_week_forecast_shadow_review.ps1"; Critical = $true },
```

- [ ] **Step 5: 运行 Task 1/2 测试并提交**

Run: `python -m unittest tests.test_first_one_month_forecast_evaluation_review tests.test_weekly_automation`

Expected: PASS。

```powershell
git add scripts/run_first_one_month_forecast_evaluation_review.ps1 scripts/run_weekly_reporting_bundle.ps1 first_one_month_forecast_evaluation_review.py tests/test_first_one_month_forecast_evaluation_review.py
git commit -m "feat: wire first one-month evaluation review"
```

---

### Task 3: 下游自我分析、行动清单和周结论

**Files:**
- Modify: `automation_self_analysis.py`
- Modify: `weekly_action_items.py`
- Modify: `weekly_conclusion_report.py`
- Modify: `tests/test_automation_self_analysis.py`
- Modify: `tests/test_weekly_action_items.py`
- Modify: `tests/test_weekly_conclusion_report.py`

**Interfaces:**
- Consumes: `latest_first_one_month_forecast_evaluation_review.json`
- Produces: manifest 的 `first_one_month_forecast_evaluation` 快照、具体推荐动作和周结论 P2 摘要

- [ ] **Step 1: 写快照与等待状态失败测试**

```python
self.assertEqual(manifest["first_one_month_forecast_evaluation"]["status"], "awaiting_maturity")
self.assertEqual(manifest["first_one_month_forecast_evaluation"]["one_month_valid_count"], 0)
self.assertEqual(manifest["first_one_month_forecast_evaluation"]["recommended_action"], "wait_for_one_month_maturity")
```

- [ ] **Step 2: 运行三组测试确认 RED**

Run: `python -m unittest tests.test_automation_self_analysis tests.test_weekly_action_items tests.test_weekly_conclusion_report`

Expected: 新断言 FAIL。

- [ ] **Step 3: 实现只读快照**

新增 `_first_one_month_forecast_evaluation_snapshot(project_root)`，验证 schema 后透传状态、队列数、两个周期有效数/命中率/平均超额收益、失败类型、市场覆盖状态、推荐动作与两个正式模型边界字段。

- [ ] **Step 4: 映射行动项**

```python
"wait_for_one_month_maturity": {
    "title": "等待首批1个月预测成熟",
    "category": "forecast_performance",
    "priority": "monitor",
},
"repair_first_cohort_evaluation_gaps": {
    "title": "修复首批1个月评价缺口",
    "category": "forecast_performance",
    "priority": "high",
},
```

等待成熟动作只进入监控摘要，不生成高优先级修复噪声；到期不完整才进入人工待办。

- [ ] **Step 5: 周结论分别展示两个周期**

在 `automation.forecast_first_one_month_evaluation` 和 Markdown 中输出队列数、1周/1个月命中率、平均超额收益、失败类型和市场覆盖边界，不复用综合预测指标。

- [ ] **Step 6: 运行测试并提交**

Run: `python -m unittest tests.test_automation_self_analysis tests.test_weekly_action_items tests.test_weekly_conclusion_report`

Expected: PASS。

```powershell
git add automation_self_analysis.py weekly_action_items.py weekly_conclusion_report.py tests/test_automation_self_analysis.py tests/test_weekly_action_items.py tests/test_weekly_conclusion_report.py
git commit -m "feat: surface first one-month evaluation status"
```

---

### Task 4: 提交前质量门与中期目标

**Files:**
- Modify: `pre_submit_review.py`
- Modify: `medium_term_goal_review.py`
- Modify: `tests/test_pre_submit_review.py`
- Modify: `tests/test_medium_term_goal_review.py`

**Interfaces:**
- Consumes: Task 1 payload 和 Task 3 manifest 快照
- Produces: P2 结构契约、成熟日期边界和中期目标进度字段

- [ ] **Step 1: 写质量门失败测试**

```python
def test_pre_submit_accepts_waiting_before_maturity(self):
    payload = make_review(status="awaiting_maturity", as_of_date="2026-07-20")
    result = run_review_with(payload)
    self.assertNotIn("first_one_month_review_not_acceptable", result["attention_reasons"])

def test_pre_submit_rejects_false_ready_after_maturity(self):
    payload = make_review(status="review_ready", as_of_date="2026-08-04", one_month_valid=36)
    result = run_review_with(payload)
    self.assertIn("first_one_month_review_count_mismatch", result["attention_reasons"])
```

- [ ] **Step 2: 运行测试确认 RED**

Expected: FAIL，`OUTPUT_SPECS` 和原因函数尚不存在。

- [ ] **Step 3: 增加 OUTPUT_SPECS 和原因函数**

```python
"first_one_month_forecast_evaluation_review": {
    "path": "outputs/automation/latest_first_one_month_forecast_evaluation_review.json",
    "schema_key": "review_schema",
    "schema_value": "first_one_month_forecast_evaluation_review",
    "version_key": "review_version",
    "version": 1,
},
```

新增 `_first_one_month_forecast_evaluation_reasons(payload)`，验证允许状态、核心字段、37分母、日期状态、唯一键问题和两个 `false` 边界。

- [ ] **Step 4: 更新中期目标字段**

`forecast_tracking_maturity.current` 新增：

```python
"first_one_month_review_status": review.get("status", "missing"),
"first_one_month_expected_count": cohort.get("expected_sample_count", 37),
"first_one_month_valid_count": one_month.get("valid_evaluation_count", 0),
"first_one_month_maturity_date": cohort.get("one_month_maturity_date", "2026-08-03"),
```

`awaiting_maturity` 保持按计划推进；`sample_incomplete`/`needs_attention` 降为需要处理；`review_ready` 只提高证据完成度，不允许正式模型升级。

- [ ] **Step 5: 运行测试并提交**

Run: `python -m unittest tests.test_pre_submit_review tests.test_medium_term_goal_review`

Expected: PASS。

```powershell
git add pre_submit_review.py medium_term_goal_review.py tests/test_pre_submit_review.py tests/test_medium_term_goal_review.py
git commit -m "feat: gate first one-month evaluation evidence"
```

---

### Task 5: 真实预成熟验证、文档和自动任务汇报

**Files:**
- Modify: `docs/美股每周自动运行说明.md`
- Modify: `docs/提交前复核清单.md`
- Modify: `docs/中期目标进度看板.md`
- Modify: `tests/test_weekly_automation.py`

**Interfaces:**
- Consumes: 当前真实港股 `2026-07-06` 队列和现有评价文件
- Produces: 当前日期的 `awaiting_maturity` 产物、可执行文档和自动任务汇报契约

- [ ] **Step 1: 写文档契约测试**

```python
self.assertIn("latest_first_one_month_forecast_evaluation_review.json", doc)
self.assertIn("2026-08-03", doc)
self.assertIn("sample_incomplete", doc)
self.assertIn("formal_model_conclusion_allowed=false", doc)
```

- [ ] **Step 2: 运行真实包装器**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\run_first_one_month_forecast_evaluation_review.ps1 -ProjectRoot F:\chatgptssd\project2
```

Expected: `status=awaiting_maturity`、队列37、1个月有效数0、推荐动作 `wait_for_one_month_maturity`、两个正式模型边界均为 `false`。

- [ ] **Step 3: 更新三份文档**

说明固定队列、两个周期指标、失败类型、到期前后状态、市场覆盖不足边界、运行命令和输出路径。不得改动用户未提交的 `docs/中期目标与模型协作规范.md`。

- [ ] **Step 4: 更新港股 Codex 自动任务**

保持每周日14:30，提示词增加读取 `latest_first_one_month_forecast_evaluation_review.json`，并要求分别报告1周/1个月指标、失败类型、市场覆盖与结论边界。

- [ ] **Step 5: 运行目标测试和全量测试**

Run:

```powershell
python -m unittest tests.test_first_one_month_forecast_evaluation_review tests.test_automation_self_analysis tests.test_weekly_action_items tests.test_weekly_conclusion_report tests.test_pre_submit_review tests.test_medium_term_goal_review tests.test_weekly_automation
python -m unittest discover -s tests -p "test_*.py"
git diff --check
```

Expected: 全部 PASS，`git diff --check` 无输出。

- [ ] **Step 6: 提交文档并完成分支复核**

```powershell
git add docs/美股每周自动运行说明.md docs/提交前复核清单.md docs/中期目标进度看板.md tests/test_weekly_automation.py
git commit -m "docs: document first one-month evaluation review"
git status --short
```

Expected: 工作树无已跟踪改动；被忽略的运行输出不进入提交。
