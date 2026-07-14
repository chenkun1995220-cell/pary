# 行动策略版本全链路传播 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让周度报告链的每个关键产物携带并校验 `action_policy_version=1`，使缺失、旧版或混合版本产物在最早消费者处被拒绝。

**Architecture:** 新增 `action_policy_contract.py` 作为唯一版本源和轻量校验器。自我分析生成源契约，行动清单、运维检查、周结论、交付检查和一致性复核逐级传播版本；提交前复核校验所有下游产物，正式迁移只重跑报告链。

**Tech Stack:** Python 3 标准库、PowerShell、`unittest`、JSON。

## Global Constraints

- `ACTION_POLICY_VERSION = 1`，不得在多个模块重复维护独立常量。
- 不运行美股、A 股或港股市场抓取入口。
- 不重新评分，不修改正式选股、估值或预测模型参数。
- 不改变候选数量、排序、风险状态和有效建议动作。
- 任一步报告链失败立即停止，不引用旧下游产物。
- 所有行为修改先写失败测试，再做最小实现。

## File Structure

- Create: `action_policy_contract.py`，唯一版本常量和契约状态函数。
- Create: `tests/test_action_policy_contract.py`，共享契约单元测试。
- Modify: `automation_self_analysis.py`，从共享模块读取版本。
- Modify: `weekly_action_items.py`，严格校验 manifest 并传播版本。
- Modify: `weekly_ops_check.py`，把旧自动化检查写成本次 `needs_attention` 证据。
- Modify: `weekly_conclusion_report.py`，核对自动化检查、运维检查和行动清单版本。
- Modify: `weekly_delivery_check.py`，核对周结论与行动清单版本。
- Modify: `weekly_artifact_consistency.py`，生成六项版本映射并识别混合版本。
- Modify: `pre_submit_review.py`，要求全部下游产物携带当前版本。
- Modify: 对应 `tests/test_*.py` fixture 和回归测试。
- Modify: `docs/美股每周自动运行说明.md`，记录全链路契约和恢复顺序。

---

### Task 1: 建立共享行动策略契约

**Files:**
- Create: `action_policy_contract.py`
- Create: `tests/test_action_policy_contract.py`
- Modify: `automation_self_analysis.py:1-60`
- Modify: `pre_submit_review.py:1-20,1257-1278`
- Test: `tests/test_automation_self_analysis.py`
- Test: `tests/test_pre_submit_review.py`

**Interfaces:**
- Consumes: 任意 JSON object `dict`。
- Produces: `ACTION_POLICY_VERSION: int`、`action_policy_version(payload) -> int | None`、`action_policy_contract_status(payload, require_actionability=False) -> str`。

- [ ] **Step 1: 写共享契约失败测试**

```python
import unittest

from action_policy_contract import (
    ACTION_POLICY_VERSION,
    action_policy_contract_status,
    action_policy_version,
)


class ActionPolicyContractTests(unittest.TestCase):
    def test_current_source_contract_is_valid(self):
        payload = {
            "action_policy_version": 1,
            "candidate_review_actionable": False,
            "weekly_delivery_history_actionable": False,
        }
        self.assertEqual(ACTION_POLICY_VERSION, 1)
        self.assertEqual(action_policy_version(payload), 1)
        self.assertEqual(
            action_policy_contract_status(payload, require_actionability=True),
            "valid",
        )

    def test_contract_distinguishes_missing_and_mismatch(self):
        self.assertEqual(action_policy_contract_status({}), "missing")
        self.assertEqual(
            action_policy_contract_status({"action_policy_version": 0}),
            "mismatch",
        )
        self.assertEqual(
            action_policy_contract_status(
                {"action_policy_version": 1},
                require_actionability=True,
            ),
            "missing",
        )
        self.assertIsNone(action_policy_version({"action_policy_version": True}))
```

- [ ] **Step 2: 运行测试确认红灯**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_action_policy_contract
```

Expected: FAIL，`ModuleNotFoundError: No module named 'action_policy_contract'`。

- [ ] **Step 3: 实现共享模块**

```python
ACTION_POLICY_VERSION = 1
SOURCE_ACTION_POLICY_REQUIRED_FIELDS = (
    "action_policy_version",
    "candidate_review_actionable",
    "weekly_delivery_history_actionable",
)


def action_policy_version(payload):
    if not isinstance(payload, dict) or "action_policy_version" not in payload:
        return None
    value = payload.get("action_policy_version")
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def action_policy_contract_status(payload, require_actionability=False):
    if not isinstance(payload, dict) or "action_policy_version" not in payload:
        return "missing"
    if require_actionability and any(
        field not in payload for field in SOURCE_ACTION_POLICY_REQUIRED_FIELDS
    ):
        return "missing"
    return "valid" if action_policy_version(payload) == ACTION_POLICY_VERSION else "mismatch"
```

在 `automation_self_analysis.py` 和 `pre_submit_review.py` 导入 `ACTION_POLICY_VERSION`，删除各自重复常量；提交前版本比较继续使用共享常量。

- [ ] **Step 4: 运行共享与源产物测试**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_action_policy_contract tests.test_automation_self_analysis tests.test_pre_submit_review
```

Expected: PASS。

- [ ] **Step 5: 提交共享契约**

```powershell
git add action_policy_contract.py tests/test_action_policy_contract.py automation_self_analysis.py pre_submit_review.py
git commit -m "refactor: centralize action policy contract"
```

---

### Task 2: 行动清单严格校验并传播版本

**Files:**
- Modify: `weekly_action_items.py:1-70,1569-1815`
- Modify: `tests/test_weekly_action_items.py:13-70`

**Interfaces:**
- Consumes: `latest_self_analysis_manifest.json`，要求完整源契约。
- Produces: `latest_weekly_action_items.json.action_policy_version`。

- [ ] **Step 1: 写缺失、旧版和成功传播测试**

```python
def test_load_manifest_rejects_missing_action_policy_contract(self):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "manifest.json"
        path.write_text(
            json.dumps({"manifest_schema": "self_analysis_manifest", "manifest_version": 1}),
            encoding="utf-8-sig",
        )
        from weekly_action_items import load_manifest
        with self.assertRaisesRegex(ValueError, "manifest_action_policy_contract_missing"):
            load_manifest(path)

def test_load_manifest_rejects_old_action_policy_version(self):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "manifest.json"
        path.write_text(json.dumps({
            "manifest_schema": "self_analysis_manifest",
            "manifest_version": 1,
            "action_policy_version": 0,
            "candidate_review_actionable": False,
            "weekly_delivery_history_actionable": False,
        }), encoding="utf-8-sig")
        from weekly_action_items import load_manifest
        with self.assertRaisesRegex(ValueError, "manifest_action_policy_version_mismatch"):
            load_manifest(path)
```

在现有 ready 用例中增加 `self.assertEqual(payload["action_policy_version"], 1)`。

- [ ] **Step 2: 运行目标测试确认红灯**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_action_items
```

Expected: 新测试 FAIL，现有 fixture 尚未提供契约字段。

- [ ] **Step 3: 实现严格读取和版本传播**

```python
from action_policy_contract import action_policy_contract_status, action_policy_version


def load_manifest(manifest):
    manifest_path = Path(manifest)
    payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if payload.get("manifest_schema") != EXPECTED_MANIFEST_SCHEMA:
        raise ValueError(f"unexpected manifest_schema: {payload.get('manifest_schema', '')}")
    if int(payload.get("manifest_version", 0) or 0) != EXPECTED_MANIFEST_VERSION:
        raise ValueError(f"unexpected manifest_version: {payload.get('manifest_version', '')}")
    contract_status = action_policy_contract_status(payload, require_actionability=True)
    if contract_status == "missing":
        raise ValueError("manifest_action_policy_contract_missing")
    if contract_status == "mismatch":
        raise ValueError("manifest_action_policy_version_mismatch")
    return payload
```

行动清单返回 payload 增加 `"action_policy_version": action_policy_version(source)`，并统一更新测试 manifest fixture 的三个契约字段。

- [ ] **Step 4: 运行行动清单测试**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_action_items
```

Expected: PASS。

- [ ] **Step 5: 提交行动清单契约**

```powershell
git add weekly_action_items.py tests/test_weekly_action_items.py
git commit -m "fix: validate action policy in weekly items"
```

---

### Task 3: 运维检查提前输出版本失败证据

**Files:**
- Modify: `weekly_ops_check.py:1-135`
- Modify: `tests/test_weekly_ops_check.py:50-130`

**Interfaces:**
- Consumes: `latest_automation_check.json` 完整源契约。
- Produces: `action_policy_version`、`action_policy_contract_status` 和精确 attention reason。

- [ ] **Step 1: 写缺失与旧版运维测试**

```python
def test_ops_check_needs_attention_for_missing_action_policy_contract(self):
    payload = json.loads(check_path.read_text(encoding="utf-8-sig"))
    del payload["action_policy_version"]
    check_path.write_text(json.dumps(payload), encoding="utf-8-sig")
    result = run_weekly_ops_check(root, automation_tmp, check_path, today="2026-06-28")
    self.assertEqual(result["status"], "needs_attention")
    self.assertEqual(result["action_policy_contract_status"], "missing")
    self.assertIn("automation_check_action_policy_contract_missing", result["attention_reasons"])

def test_ops_check_needs_attention_for_old_action_policy_version(self):
    payload["action_policy_version"] = 0
    result = run_weekly_ops_check(root, automation_tmp, check_path, today="2026-06-28")
    self.assertEqual(result["action_policy_contract_status"], "mismatch")
    self.assertIn("automation_check_action_policy_version_mismatch", result["attention_reasons"])
```

- [ ] **Step 2: 运行测试确认红灯**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_ops_check
```

Expected: 新断言 FAIL。

- [ ] **Step 3: 实现运维契约状态**

```python
policy_status = action_policy_contract_status(weekly_check, require_actionability=True)
policy_version = action_policy_version(weekly_check)
if policy_status == "missing":
    attention_reasons.append("automation_check_action_policy_contract_missing")
elif policy_status == "mismatch":
    attention_reasons.append("automation_check_action_policy_version_mismatch")
```

返回 payload 增加 `action_policy_version` 和 `action_policy_contract_status`。更新 `write_weekly_check` fixture，默认加入版本和两个行动性字段。

- [ ] **Step 4: 运行运维测试**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_ops_check
```

Expected: PASS。

- [ ] **Step 5: 提交运维契约**

```powershell
git add weekly_ops_check.py tests/test_weekly_ops_check.py
git commit -m "fix: fail early on stale action policy"
```

---

### Task 4: 周结论拒绝混合行动策略版本

**Files:**
- Modify: `weekly_conclusion_report.py:184-230,414-430,823-865`
- Modify: `tests/test_weekly_conclusion_report.py:130-190`

**Interfaces:**
- Consumes: automation check、weekly ops check、weekly action items 的版本。
- Produces: `latest_weekly_conclusion.json.action_policy_version` 和版本 warnings。

- [ ] **Step 1: 写当前版本与混合版本测试**

```python
def test_conclusion_propagates_current_action_policy_version(self):
    write_three_markets(root)
    write_ready_automation(root)
    payload = build_weekly_conclusion(root, today="2026-06-28")
    self.assertEqual(payload["action_policy_version"], 1)
    self.assertEqual(payload["status"], "ready")

def test_conclusion_rejects_mixed_action_policy_versions(self):
    write_three_markets(root)
    write_ready_automation(root)
    action_path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
    action_payload = json.loads(action_path.read_text(encoding="utf-8-sig"))
    action_payload["action_policy_version"] = 0
    write_json(action_path, action_payload)
    payload = build_weekly_conclusion(root, today="2026-06-28")
    self.assertEqual(payload["status"], "needs_attention")
    self.assertIsNone(payload["action_policy_version"])
    self.assertIn("weekly_action_items_action_policy_version_mismatch", payload["warnings"])
```

- [ ] **Step 2: 运行测试确认红灯**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_conclusion_report
```

Expected: 新测试 FAIL。

- [ ] **Step 3: 实现周结论版本汇总**

读取 automation state 时保留三个输入的 `action_policy_version`，新增：

```python
def action_policy_summary(automation):
    keys = ("automation_check", "weekly_ops_check", "weekly_action_items")
    versions = {key: action_policy_version(automation.get(key, {})) for key in keys}
    warnings = []
    for key, version in versions.items():
        if version is None:
            warnings.append(f"{key}_action_policy_version_missing")
        elif version != ACTION_POLICY_VERSION:
            warnings.append(f"{key}_action_policy_version_mismatch")
    if len({version for version in versions.values() if version is not None}) > 1:
        warnings.append("action_policy_version_inconsistent")
    return {"version": ACTION_POLICY_VERSION if not warnings else None, "versions": versions, "warnings": warnings}
```

把 summary warnings 加入现有 warnings；`build_payload` 写入汇总版本。版本无效时不得从旧行动清单生成新优先动作。更新 ready fixture，使三个输入默认都为版本 1。

- [ ] **Step 4: 运行周结论测试**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_conclusion_report
```

Expected: PASS。

- [ ] **Step 5: 提交周结论契约**

```powershell
git add weekly_conclusion_report.py tests/test_weekly_conclusion_report.py
git commit -m "fix: reject mixed action policy conclusions"
```

---

### Task 5: 交付检查核对周结论与行动清单版本

**Files:**
- Modify: `weekly_delivery_check.py:51-190,300-390`
- Modify: `tests/test_weekly_delivery_check.py:20-170`

**Interfaces:**
- Consumes: weekly conclusion 与 weekly action items 版本。
- Produces: `latest_weekly_delivery_check.json.action_policy_version` 和精确 attention reasons。

- [ ] **Step 1: 写交付版本测试**

```python
def test_delivery_check_propagates_current_action_policy_version(self):
    write_ready_delivery_files(root)
    result = run_delivery_check(root, today="2026-06-28")
    self.assertEqual(result["action_policy_version"], 1)
    self.assertEqual(result["status"], "ready")

def test_delivery_check_rejects_mixed_action_policy_versions(self):
    write_ready_delivery_files(root)
    path = root / "outputs" / "automation" / "latest_weekly_action_items.json"
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    payload["action_policy_version"] = 0
    write_json(path, payload)
    result = run_delivery_check(root, today="2026-06-28")
    self.assertEqual(result["status"], "needs_attention")
    self.assertIn("weekly_action_items_action_policy_version_mismatch", result["attention_reasons"])
    self.assertIn("action_policy_version_inconsistent", result["attention_reasons"])
```

- [ ] **Step 2: 运行测试确认红灯**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_delivery_check
```

Expected: 新测试 FAIL。

- [ ] **Step 3: 实现交付版本校验**

`_check_action_items` 返回 `action_policy_version`。`run_delivery_check` 分别解析 conclusion/action items 版本，缺失时生成 `<artifact>_action_policy_version_missing`，非当前版本时生成 `<artifact>_action_policy_version_mismatch`，两者不同则生成 `action_policy_version_inconsistent`。结果仅在两者均为当前版本时写 `action_policy_version=1`，否则写 `None`。

- [ ] **Step 4: 运行交付测试**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_delivery_check
```

Expected: PASS。

- [ ] **Step 5: 提交交付契约**

```powershell
git add weekly_delivery_check.py tests/test_weekly_delivery_check.py
git commit -m "fix: validate action policy at delivery"
```

---

### Task 6: 一致性复核生成完整版本映射

**Files:**
- Modify: `weekly_artifact_consistency.py:1-30,270-380`
- Modify: `tests/test_weekly_artifact_consistency.py:40-165`

**Interfaces:**
- Consumes: manifest、automation check、action items、ops check、conclusion、delivery 六个 JSON。
- Produces: `action_policy_versions`、`action_policy_contract_status`、`action_policy_version`。

- [ ] **Step 1: 写完整映射和混合版本测试**

```python
def test_consistency_reports_complete_action_policy_versions(self):
    write_fixture(root)
    payload = build_weekly_artifact_consistency(root, "2026-07-11")
    self.assertEqual(payload["action_policy_contract_status"], "valid")
    self.assertEqual(payload["action_policy_version"], 1)
    self.assertEqual(set(payload["action_policy_versions"].values()), {1})

def test_consistency_rejects_mixed_action_policy_versions(self):
    write_fixture(root)
    path = root / "outputs" / "automation" / "latest_weekly_delivery_check.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["action_policy_version"] = 0
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = build_weekly_artifact_consistency(root, "2026-07-11")
    self.assertEqual(result["status"], "needs_attention")
    self.assertEqual(result["action_policy_contract_status"], "mismatch")
    self.assertIn("delivery_action_policy_version_mismatch", result["issues"])
    self.assertIn("action_policy_version_inconsistent", result["issues"])
```

- [ ] **Step 2: 运行测试确认红灯**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_artifact_consistency
```

Expected: 新测试 FAIL。

- [ ] **Step 3: 实现版本映射**

```python
ACTION_POLICY_ARTIFACTS = {
    "manifest": "latest_self_analysis_manifest.json",
    "automation_check": "latest_automation_check.json",
    "action_items": "latest_weekly_action_items.json",
    "ops_check": "latest_weekly_ops_check.json",
    "conclusion": "latest_weekly_conclusion.json",
    "delivery": "latest_weekly_delivery_check.json",
}


def _action_policy_evidence(project_root, issues):
    automation = Path(project_root) / "outputs" / "automation"
    versions = {}
    for key, filename in ACTION_POLICY_ARTIFACTS.items():
        version = action_policy_version(_read_json(automation / filename))
        versions[key] = version
        if version is None:
            issues.append(f"{key}_action_policy_version_missing")
        elif version != ACTION_POLICY_VERSION:
            issues.append(f"{key}_action_policy_version_mismatch")
    present = {version for version in versions.values() if version is not None}
    if len(present) > 1:
        issues.append("action_policy_version_inconsistent")
    status = "valid" if all(version == ACTION_POLICY_VERSION for version in versions.values()) else "mismatch"
    if any(version is None for version in versions.values()):
        status = "missing"
    return versions, status
```

输出增加映射、状态以及仅在 `valid` 时为 1 的顶层版本。更新 fixture，生成六个当前版本产物。

- [ ] **Step 4: 运行一致性测试**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_artifact_consistency
```

Expected: PASS。

- [ ] **Step 5: 提交一致性契约**

```powershell
git add weekly_artifact_consistency.py tests/test_weekly_artifact_consistency.py
git commit -m "fix: audit action policy artifact versions"
```

---

### Task 7: 提交前门槛覆盖全部下游产物

**Files:**
- Modify: `pre_submit_review.py:517-620,1102-1305`
- Modify: `tests/test_pre_submit_review.py:69-1250,2280-2420`

**Interfaces:**
- Consumes: ops、conclusion、delivery、consistency 的版本字段和契约状态。
- Produces: 缺失/旧版下游产物的提交阻断原因。

- [ ] **Step 1: 写下游陈旧产物失败测试**

```python
def test_review_rejects_downstream_outputs_without_action_policy_version(self):
    write_ready_review_inputs(root)
    for filename in (
        "latest_weekly_ops_check.json",
        "latest_weekly_conclusion.json",
        "latest_weekly_delivery_check.json",
        "latest_weekly_artifact_consistency.json",
    ):
        path = root / "outputs" / "automation" / filename
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        del payload["action_policy_version"]
        write_json(path, payload)
    result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)
    self.assertEqual(result["status"], "needs_attention")
    self.assertIn("weekly_ops_check_missing_quality_fields", result["attention_reasons"])
    self.assertIn("weekly_conclusion_missing_summary_fields", result["attention_reasons"])
    self.assertIn("weekly_delivery_check_missing_quality_fields", result["attention_reasons"])
    self.assertIn("weekly_artifact_consistency_missing_quality_fields", result["attention_reasons"])

def test_ready_review_exposes_current_action_policy_version(self):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_ready_review_inputs(root)
        result = run_pre_submit_review(root, today="2026-06-28", max_age_days=8)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["action_policy_version"], 1)
```

- [ ] **Step 2: 运行测试确认红灯**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_pre_submit_review
```

Expected: 新测试 FAIL。

- [ ] **Step 3: 扩展必填字段和版本比较**

向 ops、conclusion、delivery、consistency 四组 required fields 加入 `action_policy_version`。向一致性复核额外加入 `action_policy_contract_status` 和 `action_policy_versions`。在对应 reason 函数中调用共享版本函数：字段缺失或解析为 `None` 时生成 missing 原因，解析成功但不是当前版本时生成 mismatch 原因。`run_pre_submit_review` 的返回 payload 同步写入 `"action_policy_version": ACTION_POLICY_VERSION`，证明本次复核本身使用当前契约。

- [ ] **Step 4: 更新 ready fixture 并运行提交前测试**

所有 ready fixture 为 ops、conclusion、delivery、consistency 写入版本 1；一致性 fixture 写入完整版本映射和 `valid`。

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_pre_submit_review
```

Expected: PASS。

- [ ] **Step 5: 提交最终门槛**

```powershell
git add pre_submit_review.py tests/test_pre_submit_review.py
git commit -m "fix: require action policy across closure artifacts"
```

---

### Task 8: 更新说明、迁移正式产物并完成验证

**Files:**
- Modify: `docs/美股每周自动运行说明.md:341-370`
- Runtime outputs: `outputs/automation/latest_*.json`，不提交 Git。

**Interfaces:**
- Consumes: 已通过测试的完整报告链。
- Produces: 全部版本为 1 的本次正式验收产物。

- [ ] **Step 1: 更新运行说明**

```markdown
行动策略版本由 `action_policy_contract.py` 统一定义。自我分析 manifest、自动化检查、行动清单、运维检查、周结论、交付检查、一致性复核和提交前复核必须使用同一 `action_policy_version`；缺失、旧版或混合版本会在最早消费者处停止。恢复时只按固定顺序重跑报告链，不重新抓取三市场行情。
```

- [ ] **Step 2: 运行相关测试**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_action_policy_contract tests.test_automation_self_analysis tests.test_weekly_action_items tests.test_weekly_ops_check tests.test_weekly_conclusion_report tests.test_weekly_delivery_check tests.test_weekly_artifact_consistency tests.test_pre_submit_review
```

Expected: PASS。

- [ ] **Step 3: 运行全量测试和静态检查**

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m py_compile action_policy_contract.py automation_self_analysis.py weekly_action_items.py weekly_ops_check.py weekly_conclusion_report.py weekly_delivery_check.py weekly_artifact_consistency.py pre_submit_review.py
git diff --check
```

Expected: 全量 PASS、编译成功、无空白错误。

- [ ] **Step 4: 按顺序迁移正式报告产物**

依次运行并在任一步非零退出时停止：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_self_analysis.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\show_weekly_action_items.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_weekly_ops_check.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\show_weekly_ops_history.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\show_weekly_conclusion.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_weekly_delivery_check.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_weekly_artifact_consistency.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\show_weekly_delivery_history.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_pre_submit_review.ps1
```

- [ ] **Step 5: 验证正式版本映射与业务不变性**

使用 Python 读取一致性复核的六项上游版本映射，断言全部为 1；另断言提交前复核自身的版本为 1。核对一致性状态和提交前复核为 `ready`，候选总数仍为当前三市场实际总数，顶层动作仍为 `continue_sample_accumulation`。

- [ ] **Step 6: 提交说明并推送分支**

```powershell
git add docs/美股每周自动运行说明.md
git commit -m "docs: document action policy propagation"
git push origin codex/action-policy-propagation
```

- [ ] **Step 7: 合并后复验并推送 main**

```powershell
git switch main
git pull --ff-only
git merge --ff-only codex/action-policy-propagation
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
git push origin main
git rev-list --left-right --count HEAD...origin/main
```

Expected: 主分支全量 PASS，远端差异 `0 0`。
