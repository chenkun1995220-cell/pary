# 1周预测影子验证闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将单批1周预测影子验证扩展为跨周、跨市场的候选处置闭环，使每个候选自动进入继续观察、驳回或待人工审批，同时始终禁止正式模型自动变更。

**Architecture:** 保留现有参数计划和单批验证模块，在单批结果中补充可累计的命中数、错误数和市场明细；新增独立处置模块，将最新验证追加到按日期和动作码去重的 JSONL 历史。自我分析、人工清单、统一结论和提交前复核只消费处置结果，不直接修改预测或估值模型。

**Tech Stack:** Python 3 标准库、`unittest`、CSV/JSON/JSONL、PowerShell 5.1、现有周度自动化脚本。

## Global Constraints

- 人工审批门槛：至少 3 个独立 `evaluation_as_of_date`、累计受影响样本不少于 30、覆盖至少 2 个市场。
- 候选处置值只能是 `continue_observation`、`rejected`、`pending_human_approval`。
- 明显市场恶化：该市场累计受影响样本不少于 10，且影子命中率比基准低至少 5 个百分点。
- 来源产物新鲜度上限为 8 天。
- 同一 `evaluation_as_of_date + action_code` 只计一个独立批次；JSONL 重复键保留最后一条逻辑记录。
- 所有路径必须保持 `formal_model_change_allowed=false`。
- 不抓取行情、不重新评分、不运行正式预测、不修改正式模型代码或参数。
- 不修改或提交 `data/samples/us_universe_quotes.csv`。

---

### Task 1: 为单批影子验证补齐可累计统计

**Files:**
- Modify: `one_week_forecast_shadow_parameter_validation.py`
- Modify: `tests/test_one_week_forecast_shadow_parameter_validation.py`

**Interfaces:**
- Consumes: 现有 `build_shadow_parameter_validation(project_root, plan_path, as_of_date=None)`。
- Produces: 每个 `candidate_results[]` 增加 `evaluation_sample_count`、`baseline_hit_count`、`shadow_hit_count`、错误变化、`affected_market_count` 和 `market_results`。

- [ ] **Step 1: 写入失败测试**

新增 `test_validation_includes_accumulable_market_metrics`，构造两个港股样本：一个 `down -> neutral`，一个 `down -> up`。断言：

```python
result = next(
    item for item in payload["candidate_results"]
    if item["action_code"] == "shadow_demote_down_signal_to_neutral"
)
self.assertEqual(result["evaluation_sample_count"], 2)
self.assertEqual(result["baseline_hit_count"], 0)
self.assertEqual(result["shadow_hit_count"], 1)
self.assertEqual(result["affected_market_count"], 1)
self.assertEqual(result["market_results"][0]["affected_count"], 2)
self.assertEqual(result["baseline_opposite_miss_count"], 1)
self.assertEqual(result["shadow_opposite_miss_count"], 0)
self.assertFalse(result["formal_model_change_allowed"])
```

- [ ] **Step 2: 运行测试并确认缺少新字段**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_one_week_forecast_shadow_parameter_validation.OneWeekForecastShadowParameterValidationTests.test_validation_includes_accumulable_market_metrics
```

Expected: `FAIL` 或 `ERROR`，缺少累计统计字段。

- [ ] **Step 3: 实现统计函数并扩展结果**

增加：

```python
def _is_opposite(predicted, actual):
    return (predicted, actual) in {("up", "down"), ("down", "up")}


def _error_counts(rows, direction_field):
    opposite = 0
    neutral = 0
    for row in rows:
        predicted = _direction(row, direction_field)
        actual = _direction(row, "actual_direction")
        if predicted == actual:
            continue
        if _is_opposite(predicted, actual):
            opposite += 1
        elif "neutral" in {predicted, actual}:
            neutral += 1
    return opposite, neutral
```

`_validate_candidate` 同时保存布尔 `affected_flags`，按 `_market_label` 分组计算样本数、受影响数、基准/影子命中数和命中率变化。不可评估候选也输出零计数和空 `market_results`，保持契约稳定。

- [ ] **Step 4: 运行模块测试并提交**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_one_week_forecast_shadow_parameter_validation
git add one_week_forecast_shadow_parameter_validation.py tests/test_one_week_forecast_shadow_parameter_validation.py
git commit -m "feat: add accumulable forecast shadow metrics"
```

Expected: 测试 `OK`，提交仅包含验证模块及测试。

---

### Task 2: 实现跨周历史与候选处置器

**Files:**
- Create: `one_week_forecast_shadow_disposition.py`
- Create: `tests/test_one_week_forecast_shadow_disposition.py`

**Interfaces:**
- Consumes: 参数计划 JSON、扩展后的 validation JSON、历史 JSONL、预测表现 JSON。
- Produces: `build_shadow_disposition(plan, validation, history_rows, performance, as_of_date=None) -> dict`、`render_shadow_disposition(payload) -> str` 和 CLI。

- [ ] **Step 1: 写入历史去重与继续观察失败测试**

测试文件先定义确定性 fixture：

```python
ACTION = "shadow_demote_down_signal_to_neutral"
WIDEN_ACTION = "shadow_widen_neutral_band"


def history_row(batch_date, action=ACTION, affected=10, markets=("US", "HK"), baseline_hits=3,
                shadow_hits=5, status="validated", reason=""):
    per_market = []
    for market in markets:
        per_market.append({
            "market": market,
            "sample_count": 5,
            "affected_count": affected // max(len(markets), 1),
            "baseline_hit_count": baseline_hits // max(len(markets), 1),
            "shadow_hit_count": shadow_hits // max(len(markets), 1),
        })
    return {
        "evaluation_as_of_date": batch_date,
        "action_code": action,
        "validation_status": status,
        "reason": reason,
        "evaluation_sample_count": 10,
        "affected_count": affected,
        "baseline_hit_count": baseline_hits,
        "shadow_hit_count": shadow_hits,
        "market_results": per_market,
        "formal_model_change_allowed": False,
    }


def by_action(payload, action):
    return next(item for item in payload["candidate_dispositions"] if item["action_code"] == action)


def build_from_rows(rows):
    latest = rows[-1]
    plan = {
        "plan_schema": "one_week_forecast_shadow_parameter_plan",
        "status": "shadow_plan_ready",
        "candidate_shadow_changes": [{"action_code": latest["action_code"]}],
        "formal_model_change_allowed": False,
    }
    validation = {
        "validation_schema": "one_week_forecast_shadow_parameter_validation",
        "status": "shadow_validation_ready",
        "evaluation_as_of_date": latest["evaluation_as_of_date"],
        "candidate_results": [dict(latest)],
        "formal_model_change_allowed": False,
    }
    performance = {
        "review_schema": "forecast_performance_review",
        "status": "performance_review_needed",
        "next_one_week_evaluation_date": "2026-07-26",
        "next_one_week_evaluation_count": 20,
    }
    return build_shadow_disposition(plan, validation, rows, performance, as_of_date="2026-07-20")


def build_missing_date():
    row = history_row("")
    return build_from_rows([row])
```

同一个 validation 转成两组相同历史记录，断言：

```python
candidate = by_action(payload, "shadow_demote_down_signal_to_neutral")
self.assertEqual(candidate["independent_batch_count"], 1)
self.assertEqual(candidate["affected_count"], 4)
self.assertEqual(candidate["disposition"], "continue_observation")
self.assertEqual(candidate["next_action"], "continue_shadow_validation")
self.assertFalse(payload["formal_model_change_allowed"])
```

- [ ] **Step 2: 写入成熟、驳回与异常输入失败测试**

使用上面的 `history_row` 明确构造三组数据：

```python
dates = ("2026-07-05", "2026-07-12", "2026-07-19")
positive = [history_row(day, affected=10, baseline_hits=3, shadow_hits=5) for day in dates]
non_positive = [history_row(day, affected=10, baseline_hits=5, shadow_hits=4) for day in dates]
not_evaluable = [
    history_row(day, action=WIDEN_ACTION, affected=0, markets=(), baseline_hits=0,
                shadow_hits=0, status="not_evaluable_current_fields", reason="prediction_score_missing")
    for day in dates
]
self.assertEqual(by_action(build_from_rows(positive), ACTION)["disposition"], "pending_human_approval")
self.assertEqual(by_action(build_from_rows(non_positive), ACTION)["disposition"], "rejected")
self.assertEqual(by_action(build_from_rows(not_evaluable), WIDEN_ACTION)["disposition"], "rejected")
self.assertEqual(build_missing_date()["status"], "needs_attention")
self.assertEqual(build_missing_date()["history_records_added"], 0)
```

`build_from_rows` 会把最后一条历史记录同时作为最新 validation；处置模块必须按唯一键去重，因此不会把它重复计数。
再增加三个契约测试：plan 与 validation 动作码不一致时顶层状态为 `needs_attention`；缺失市场名的批次可以计入批次数但市场覆盖数保持 0；每个计划候选在 `candidate_dispositions` 中恰好出现一次且处置值属于三种合法值。

- [ ] **Step 3: 运行测试并确认模块不存在**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_one_week_forecast_shadow_disposition
```

Expected: `ERROR`，无法导入新模块。

- [ ] **Step 4: 实现逻辑历史和处置规则**

定义：

```python
DISPOSITION_SCHEMA = "one_week_forecast_shadow_disposition"
DISPOSITION_VERSION = 1
MIN_BATCHES = 3
MIN_AFFECTED = 30
MIN_MARKETS = 2
SEVERE_MARKET_MIN_AFFECTED = 10
SEVERE_MARKET_DELTA = -0.05
MAX_SOURCE_AGE_DAYS = 8


def logical_history(rows):
    by_key = {}
    duplicate_count = 0
    for row in rows:
        key = (str(row.get("evaluation_as_of_date", "")), str(row.get("action_code", "")))
        duplicate_count += int(key in by_key)
        by_key[key] = row
    return list(by_key.values()), duplicate_count
```

`classify_candidate(summary)` 按以下顺序返回 `(disposition, reason_codes, next_action)`：连续3次同原因不可评估、3批次零影响、明显市场恶化、3批次累计变化不为正均驳回；全部成熟门槛达标则待人工审批；其余继续观察。汇总命中数后再计算总命中率，不直接平均批次百分比。

- [ ] **Step 5: 实现 CLI、JSONL 追加和报告**

CLI 参数：

```python
--plan --validation --history --performance --as-of-date --output --report
```

只有 validation schema 正确且 `evaluation_as_of_date` 非空才追加历史。顶层输出必须包含 `disposition_counts`、`candidate_dispositions`、`recommended_action`、下一成熟日期和 `formal_model_change_allowed=false`。动作优先级：修复输入、人工审批、继续观察、无动作。

- [ ] **Step 6: 运行测试并提交**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_one_week_forecast_shadow_disposition
git add one_week_forecast_shadow_disposition.py tests/test_one_week_forecast_shadow_disposition.py
git commit -m "feat: add forecast shadow candidate disposition"
```

Expected: 测试 `OK`。

---

### Task 3: 接入周度脚本、自我分析与人工清单

**Files:**
- Create: `scripts/run_one_week_forecast_shadow_disposition.ps1`
- Modify: `scripts/run_weekly_reporting_bundle.ps1`
- Modify: `automation_self_analysis.py`
- Modify: `weekly_action_items.py`
- Modify: `tests/test_automation_self_analysis.py`
- Modify: `tests/test_weekly_action_items.py`
- Modify: `tests/test_one_week_forecast_shadow_disposition.py`

**Interfaces:**
- Consumes: Task 2 disposition JSON。
- Produces: manifest 处置摘要，以及 `continue_shadow_validation`、`review_shadow_candidate_approval`、`repair_shadow_disposition_inputs` 三种具体人工动作。

- [ ] **Step 1: 写入脚本顺序和 manifest 失败测试**

断言 bundle 顺序：

```python
self.assertLess(bundle.index("run_one_week_forecast_shadow_parameter_validation"), bundle.index("run_one_week_forecast_shadow_disposition"))
self.assertLess(bundle.index("run_one_week_forecast_shadow_disposition"), bundle.index("refresh_self_analysis_after_shadow_disposition"))
```

写入 disposition fixture 后断言 manifest 的 `forecast_performance_recommended_action == "continue_shadow_validation"`，优先动作包含该值且不含 `review_forecast_performance`。

- [ ] **Step 2: 写入人工清单路由失败测试**

在测试文件定义：

```python
def manifest_with_disposition(action):
    manifest = base_manifest()
    manifest["automation_priority_actions"] = [action]
    manifest["one_week_forecast_shadow_disposition"] = {
        "status": "ready",
        "recommended_action": action,
        "disposition_counts": {
            "continue_observation": 3,
            "rejected": 0,
            "pending_human_approval": 0,
        },
        "next_one_week_evaluation_date": "2026-07-13",
        "formal_model_change_allowed": False,
    }
    return manifest
```

```python
result = build_weekly_action_items(manifest_with_disposition("continue_shadow_validation"))
actions = [item["action_code"] for item in result["action_items"]]
self.assertIn("continue_shadow_validation", actions)
self.assertNotIn("review_forecast_performance", actions)
```

- [ ] **Step 3: 运行测试并确认失败**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_automation_self_analysis tests.test_weekly_action_items tests.test_one_week_forecast_shadow_disposition
```

Expected: 缺少 manifest 字段、模板或脚本步骤而失败。

- [ ] **Step 4: 实现包装器和 bundle 顺序**

包装器默认读写：

```powershell
$Plan = Join-Path $ProjectRoot "outputs\automation\latest_one_week_forecast_shadow_parameter_plan.json"
$Validation = Join-Path $ProjectRoot "outputs\automation\latest_one_week_forecast_shadow_parameter_validation.json"
$History = Join-Path $ProjectRoot "outputs\automation\one_week_forecast_shadow_parameter_validation_history.jsonl"
$Performance = Join-Path $ProjectRoot "outputs\automation\latest_forecast_performance_review.json"
$Output = Join-Path $ProjectRoot "outputs\automation\latest_one_week_forecast_shadow_disposition.json"
$Report = Join-Path $ProjectRoot "outputs\automation\latest_one_week_forecast_shadow_disposition.md"
```

bundle 在 validation 后运行 disposition，再以标签 `refresh_self_analysis_after_shadow_disposition` 第二次调用 `run_self_analysis.ps1`。保留开头第一次自我分析，避免破坏依赖现有 manifest 的前置步骤。

- [ ] **Step 5: 自我分析加载处置并替换泛化动作**

新增 `_one_week_forecast_shadow_disposition_snapshot(project_root)`。schema 无效或缺失时返回修复动作；schema 正确时透传处置计数、候选摘要、下一成熟日期和安全边界。整体预测状态为 `performance_review_needed` 时优先采用具体处置动作，并把新字段加入 manifest 验证契约。

- [ ] **Step 6: 人工清单增加具体模板**

模板代码：

```python
"continue_shadow_validation": {"title": "继续积累1周预测影子验证批次", "category": "forecast_performance"},
"review_shadow_candidate_approval": {"title": "审批已达门槛的影子候选", "category": "forecast_performance"},
"repair_shadow_disposition_inputs": {"title": "修复影子候选处置输入", "category": "forecast_performance"},
```

每个模板展示三类计数、批次/样本/市场缺口、下一成熟日期和正式模型保护。已有具体动作时不得创建旧泛化动作。

- [ ] **Step 7: 运行测试并提交**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_automation_self_analysis tests.test_weekly_action_items tests.test_one_week_forecast_shadow_disposition
git add scripts/run_one_week_forecast_shadow_disposition.ps1 scripts/run_weekly_reporting_bundle.ps1 automation_self_analysis.py weekly_action_items.py tests/test_automation_self_analysis.py tests/test_weekly_action_items.py tests/test_one_week_forecast_shadow_disposition.py
git commit -m "feat: route weekly forecast shadow dispositions"
```

Expected: 定向测试 `OK`。

---

### Task 4: 接入统一结论与提交前安全闸门

**Files:**
- Modify: `weekly_conclusion_report.py`
- Modify: `pre_submit_review.py`
- Modify: `tests/test_weekly_conclusion_report.py`
- Modify: `tests/test_pre_submit_review.py`

**Interfaces:**
- Consumes: manifest 处置摘要和最新处置 JSON。
- Produces: 统一结论处置概览；提交前复核拦截缺失、契约错误或正式模型不安全状态。

- [ ] **Step 1: 写入统一结论失败测试**

```python
self.assertEqual(payload["automation"]["forecast_shadow_disposition"]["continue_observation_count"], 3)
self.assertIn("继续观察=3", render_weekly_conclusion(payload))
self.assertIn("2026-07-13", render_weekly_conclusion(payload))
```

- [ ] **Step 2: 写入提交前安全失败测试**

创建 `formal_model_change_allowed=True` 的处置 fixture，断言：

```python
self.assertIn(
    "one_week_forecast_shadow_disposition_formal_model_change_unsafe",
    result["attention_reasons"],
)
```

另加缺失字段、非法处置值和缺失输出测试。

- [ ] **Step 3: 运行测试并确认失败**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_conclusion_report tests.test_pre_submit_review
```

Expected: 缺少处置摘要和输出契约而失败。

- [ ] **Step 4: 统一结论增加处置摘要**

固定结构：

```python
"forecast_shadow_disposition": {
    "status": disposition.get("status", "missing"),
    "continue_observation_count": counts.get("continue_observation", 0),
    "rejected_count": counts.get("rejected", 0),
    "pending_human_approval_count": counts.get("pending_human_approval", 0),
    "recommended_action": disposition.get("recommended_action", "repair_shadow_disposition_inputs"),
    "next_one_week_evaluation_date": disposition.get("next_one_week_evaluation_date", ""),
    "formal_model_change_allowed": False,
}
```

Markdown 一屏结论增加“预测影子处置”行，不删除现有整体预测表现和影子诊断。

- [ ] **Step 5: 提交前复核增加必需输出和原因码**

在 `OUTPUT_SPECS` 增加 schema/version 契约，新增 `_one_week_forecast_shadow_disposition_reasons(payload)`，验证状态、三类计数、候选处置合法性、8天新鲜度和 `formal_model_change_allowed is False`。原因码固定为：

```text
one_week_forecast_shadow_disposition_not_acceptable
one_week_forecast_shadow_disposition_missing_fields
one_week_forecast_shadow_disposition_invalid_candidate_status
one_week_forecast_shadow_disposition_formal_model_change_unsafe
```

- [ ] **Step 6: 运行测试并提交**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_conclusion_report tests.test_pre_submit_review
git add weekly_conclusion_report.py pre_submit_review.py tests/test_weekly_conclusion_report.py tests/test_pre_submit_review.py
git commit -m "feat: gate forecast shadow dispositions before delivery"
```

Expected: 定向测试 `OK`。

---

### Task 5: 文档、真实产物与全量验收

**Files:**
- Modify: `docs/美股每周自动运行说明.md`
- Generate: `outputs/automation/one_week_forecast_shadow_parameter_validation_history.jsonl`
- Generate: `outputs/automation/latest_one_week_forecast_shadow_disposition.json`
- Generate: `outputs/automation/latest_one_week_forecast_shadow_disposition.md`
- Refresh: `outputs/automation/latest_self_analysis_manifest.json`
- Refresh: `outputs/automation/latest_weekly_action_items.json`
- Refresh: `outputs/automation/latest_weekly_conclusion.json`
- Refresh: `outputs/automation/latest_weekly_delivery_check.json`
- Refresh: `outputs/automation/latest_pre_submit_review.json`

**Interfaces:**
- Consumes: 当前三市场预测评价和 Task 1-4 实现。
- Produces: 当前真实数据首个历史批次、具体人工动作和完整验收证据。

- [ ] **Step 1: 更新运行说明**

记录历史唯一键、3批次/30样本/2市场门槛、三种处置、明显市场恶化、8天新鲜度和正式模型保护；明确旧泛化动作会被具体处置动作替换。

- [ ] **Step 2: 运行处置器并验证真实边界**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\run_one_week_forecast_shadow_parameter_validation.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\run_one_week_forecast_shadow_disposition.ps1
```

Expected: `status=ready`、`recommended_action=continue_shadow_validation`、3个候选均继续观察、待审批0、正式模型变更不允许。当前有效候选只有1批次和4个受影响样本。

- [ ] **Step 3: 刷新只读周度收口产物**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\run_self_analysis.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\show_weekly_action_items.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\show_weekly_conclusion.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\run_weekly_delivery_check.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\run_pre_submit_review.ps1
```

Expected: 人工清单包含 `continue_shadow_validation` 且不含旧泛化动作；统一结论展示处置计数；交付检查 `ready`；提交前复核不因处置产物缺失或不安全报警。

- [ ] **Step 4: 运行全量测试和格式检查**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
git diff --check
```

Expected: 全量测试 `OK`，格式检查无输出。

- [ ] **Step 5: 提交允许跟踪的文档和基线产物**

先运行 `git status --short` 和 `git diff -- data/samples/us_universe_quotes.csv`。只暂存P1文档及仓库已经跟踪或明确允许跟踪的自动化产物；不得暂存行情快照。提交信息：

```powershell
git commit -m "chore: record forecast shadow disposition baseline"
```

- [ ] **Step 6: 推送并记录P1状态**

```powershell
git push origin codex/regional-valuation-review-categories
```

Expected: 远端包含P1代码、测试、文档和允许跟踪的基线产物。软件闭环完成后，现实成熟度仍需后续周日运行自然积累；正式模型保持不变。
