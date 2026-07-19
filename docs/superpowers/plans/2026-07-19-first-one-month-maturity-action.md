# First One-Month Maturity Action Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在每周样本积累待办中同时显示首批固定队列和下一批全市场队列的一个月评价日期与样本数。

**Architecture:** `automation_self_analysis.py` 继续负责把首批评价产物规范化为 manifest 摘要；`weekly_action_items.py` 只读取 manifest 和现有预测表现摘要生成待办。两个日期保持独立，不让待办生成器直接读取新的文件。

**Tech Stack:** Python 3、标准库 `json`/`unittest`、PowerShell 报告入口。

## Global Constraints

- 首批固定队列为 2026-08-03、37 条港股样本；下一批全市场队列为 2026-08-15、62 条三市场样本。
- 只有首批状态为 `awaiting_maturity` 且成熟日期存在时才显示首批检查点。
- 缺失首批日期时保留现有下一批提示，不制造日期。
- 不抓取行情，不重新预测，不修改选股、估值或正式模型参数。
- `formal_model_change_allowed` 必须保持 `false`。

---

### Task 1: 扩展首批评价 manifest 摘要

**Files:**
- Modify: `automation_self_analysis.py:801-850`
- Test: `tests/test_automation_self_analysis.py:2779-2820`

**Interfaces:**
- Consumes: `latest_first_one_month_forecast_evaluation_review.json` 中的 `cohort.one_month_maturity_date`、`cohort.expected_sample_count` 和 `one_month.maturity_date`。
- Produces: `first_one_month_forecast_evaluation.one_month_maturity_date: str` 与既有 `expected_sample_count: int`。

- [ ] **Step 1: 写入失败测试**

在 `test_first_one_month_snapshot_preserves_waiting_boundary` 的输入中加入：

```python
"cohort": {
    "expected_sample_count": 37,
    "actual_sample_count": 37,
    "one_month_maturity_date": "2026-08-03",
},
"one_month": {
    "maturity_date": "2026-08-03",
    "valid_evaluation_count": 0,
    "direction_hit_rate": None,
    "average_excess_return": None,
},
```

并断言：

```python
self.assertEqual(snapshot["one_month_maturity_date"], "2026-08-03")
self.assertEqual(snapshot["expected_sample_count"], 37)
```

- [ ] **Step 2: 确认测试因字段缺失而失败**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_automation_self_analysis.AutomationSelfAnalysisTests.test_first_one_month_snapshot_preserves_waiting_boundary
```

Expected: `FAIL` 或 `ERROR`，原因是 `one_month_maturity_date` 尚未进入 snapshot。

- [ ] **Step 3: 实施最小字段映射**

在 `_first_one_month_forecast_evaluation_snapshot` 的返回值中加入：

```python
"one_month_maturity_date": (
    one_month.get("maturity_date")
    or cohort.get("one_month_maturity_date")
    or ""
),
```

缺失 schema 的返回值加入：

```python
"one_month_maturity_date": "",
```

- [ ] **Step 4: 运行自我分析测试**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_automation_self_analysis
```

Expected: 全部通过。

- [ ] **Step 5: 提交 Task 1**

```powershell
git add automation_self_analysis.py tests/test_automation_self_analysis.py
git commit -m "Expose first one-month maturity in self analysis"
```

---

### Task 2: 在样本积累待办中显示两个评价节点

**Files:**
- Modify: `weekly_action_items.py:275-290`
- Modify: `weekly_action_items.py:745-765`
- Test: `tests/test_weekly_action_items.py:1158-1185`

**Interfaces:**
- Consumes: Task 1 产生的 `manifest["first_one_month_forecast_evaluation"]["one_month_maturity_date"]` 和 `expected_sample_count`。
- Produces: `continue_sample_accumulation` 的 `source` 与 `recommended_check`，分别标明首批固定队列和下一批全市场队列。

- [ ] **Step 1: 写入失败测试**

在 `write_manifest` 的 `first_one_month_forecast_evaluation` 中加入：

```python
"status": "awaiting_maturity",
"one_month_maturity_date": "2026-07-14",
"expected_sample_count": 37,
"formal_model_change_allowed": False,
```

对 `continue_sample_accumulation` 增加断言：

```python
self.assertIn("first_one_month_maturity_date:2026-07-14", sample["source"])
self.assertIn("first_one_month_expected_count:37", sample["source"])
self.assertIn("首批固定队列 2026-07-14（37 samples）", sample["recommended_check"])
self.assertIn("下一批全市场", sample["recommended_check"])
```

- [ ] **Step 2: 确认待办测试失败**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_action_items.WeeklyActionItemsTests.test_builds_action_items_from_self_analysis_manifest
```

Expected: `FAIL`，现有待办尚未显示首批固定队列。

- [ ] **Step 3: 实施最小提示逻辑**

新增一个只格式化首批节点的函数：

```python
def _first_one_month_maturity_text(manifest):
    first_month = manifest.get("first_one_month_forecast_evaluation", {}) or {}
    maturity_date = first_month.get("one_month_maturity_date", "")
    if first_month.get("status") != "awaiting_maturity" or not maturity_date:
        return ""
    expected_count = _int_value(first_month.get("expected_sample_count"), 0)
    return f"；首批固定队列 {maturity_date}（{expected_count} samples）"
```

在 `continue_sample_accumulation.source` 中加入：

```python
f"first_one_month_maturity_date:{first_month.get('one_month_maturity_date', 'unknown')}; "
f"first_one_month_expected_count:{_int_value(first_month.get('expected_sample_count'), 0)}; "
```

在 `recommended_check` 中先显示首批固定队列，再将既有下一批日期标注为“下一批全市场”。

- [ ] **Step 4: 运行相关测试和全量测试**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_automation_self_analysis tests.test_weekly_action_items
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
```

Expected: 相关测试和全量测试全部通过。

- [ ] **Step 5: 用当前产物进行只读验证**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_self_analysis.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\show_weekly_action_items.ps1
```

Expected:

- 人工队列仍为 0。
- 待办数量仍为 1。
- 同一条 `continue_sample_accumulation` 同时显示 2026-08-03/37 和 2026-08-15/62。
- 正式模型修改仍为不允许。

- [ ] **Step 6: 提交并推送**

```powershell
git add weekly_action_items.py tests/test_weekly_action_items.py
git commit -m "Show first one-month maturity in weekly actions"
git push origin main
```

