# Automation Identity Version Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在四项 Codex 自动化任务的内部 ID 或配置版本缺失、类型错误、值不匹配时阻断审计，避免错误配置被误判为可运行。

**Architecture:** 沿用 `codex_automation_audit.py` 的 `_check_automation` 单任务校验入口，在读取 TOML 后先校验配置头，再执行现有任务类型和运行边界检查。审计返回实际版本并由 Markdown 报告展示；测试夹具默认生成已支持的版本和匹配 ID。

**Tech Stack:** Python 3 标准库（`tomllib`、`unittest`）、TOML、Git。

## Global Constraints

- 文件内部 `id` 必须与审计预期的任务目录 ID 完全一致。
- `version` 必须满足 `type(version) is int` 且值为 `1`，布尔值不得视为整数版本。
- 任务名称、模型名称、推理强度和具体项目 ID 不绑定当前值。
- 不修改 Codex 自动化配置、三市场抓取流程或正式模型参数。
- 不引入第三方依赖，不降低任何既有质量门槛。

---

### Task 1: 校验自动化身份与配置版本

**Files:**
- Modify: `tests/test_codex_automation_audit.py`
- Modify: `tests/test_weekly_ops_check.py`
- Modify: `codex_automation_audit.py`

**Interfaces:**
- Consumes: `_load_toml(path) -> dict` 返回的顶层 `id` 与 `version`。
- Produces: `_check_automation(...)` 在身份或版本无效时追加 `issues: list[str]`，并返回 `version: object | None` 供报告展示。

- [x] **Step 1: 扩展主测试夹具并编写身份失败测试**

在 `write_automation` 参数中加入：

```python
    include_id=True,
    configured_id=None,
    include_version=True,
    version=1,
```

将配置头构造改为：

```python
    lines = []
    if include_version:
        lines.append(f"version = {json.dumps(version)}")
    if include_id:
        lines.append(
            "id = "
            + json.dumps(
                automation_id if configured_id is None else configured_id,
                ensure_ascii=False,
            )
        )
    lines.extend(
        [
            f"kind = {json.dumps(kind)}",
            f"name = {json.dumps(name, ensure_ascii=False)}",
            f"prompt = {json.dumps(prompt, ensure_ascii=False)}",
            'status = "ACTIVE"',
            f'rrule = "FREQ=WEEKLY;INTERVAL=1;BYDAY=SA;BYHOUR={hour};BYMINUTE={minute}"',
        ]
    )
```

新增身份校验测试：

```python
    def test_audit_requires_matching_string_automation_id(self):
        cases = (
            {"include_id": False},
            {"configured_id": "wrong-id"},
            {"configured_id": 42},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as tmp:
                write_automation(
                    tmp,
                    "automation",
                    "美股低估公司每周筛选",
                    "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口 market_quotes.csv",
                    5,
                    **kwargs,
                )

                from codex_automation_audit import audit_automations

                us_check = audit_automations(tmp)["checks"][0]

                self.assertEqual(us_check["status"], "needs_attention")
                self.assertTrue(any("id expected automation" in issue for issue in us_check["issues"]))
```

- [x] **Step 2: 编写严格版本失败测试和报告展示测试**

新增严格版本测试：

```python
    def test_audit_requires_supported_integer_automation_version(self):
        cases = (
            {"include_version": False},
            {"version": "1"},
            {"version": True},
            {"version": 2},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as tmp:
                write_automation(
                    tmp,
                    "automation",
                    "美股低估公司每周筛选",
                    "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口 market_quotes.csv",
                    5,
                    **kwargs,
                )

                from codex_automation_audit import audit_automations

                us_check = audit_automations(tmp)["checks"][0]

                self.assertEqual(us_check["status"], "needs_attention")
                self.assertTrue(any("version expected integer 1" in issue for issue in us_check["issues"]))
```

在现有有效自动化测试中加入：

```python
            self.assertEqual(result["checks"][0]["version"], 1)
            self.assertIn("version: 1", render_audit_report(result))
```

- [x] **Step 3: 运行新增测试并确认准确失败**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_codex_automation_audit.CodexAutomationAuditTests.test_audit_requires_matching_string_automation_id tests.test_codex_automation_audit.CodexAutomationAuditTests.test_audit_requires_supported_integer_automation_version tests.test_codex_automation_audit.CodexAutomationAuditTests.test_audits_market_crons_and_acceptance_heartbeat_as_ready
```

Expected: `FAIL`，无效 ID 与版本尚未被阻断，结果也未返回 `version`。

- [x] **Step 4: 实施最小身份与版本校验**

在模块常量中加入：

```python
SUPPORTED_AUTOMATION_VERSION = 1
```

在 `_check_automation` 读取 TOML 后加入：

```python
    configured_id = data.get("id")
    if configured_id != expected["id"]:
        issues.append(
            f"id expected {expected['id']} got {configured_id!r}"
        )
    configured_version = data.get("version")
    if (
        type(configured_version) is not int
        or configured_version != SUPPORTED_AUTOMATION_VERSION
    ):
        issues.append(
            "version expected integer "
            f"{SUPPORTED_AUTOMATION_VERSION} got {configured_version!r}"
        )
```

在返回字典加入：

```python
        "version": configured_version,
```

在 `render_audit_report` 的任务详情中加入：

```python
        if check.get("version") is not None:
            lines.append(f"  - version: {check['version']}")
```

在验收重点加入：

```python
            "- 四项自动化任务的内部 id 必须匹配任务目录，配置 version 必须为已支持的整数 1。",
```

- [x] **Step 5: 更新周度运维有效配置夹具**

在 `tests/test_weekly_ops_check.py` 的 `lines` 首项前加入：

```python
            "version = 1",
```

该夹具原有 `id` 已与目录一致，无需改变。

- [x] **Step 6: 运行新增测试、关联测试和真实配置审计**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_codex_automation_audit tests.test_weekly_ops_check
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' codex_automation_audit.py
```

Expected: 关联测试全部 `OK`；真实配置审计为 `4/4 ready`，四项任务均展示 `version: 1`。

- [x] **Step 7: 运行全量测试**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
```

Expected: 全量测试 `OK`，测试数不少于 `1047`。

- [x] **Step 8: 核对范围、提交并推送**

Run:

```powershell
git diff --check
git status --short
git diff --stat
git add -- codex_automation_audit.py tests/test_codex_automation_audit.py tests/test_weekly_ops_check.py docs/superpowers/plans/2026-07-23-automation-identity-version-audit.md
git commit -m "Audit automation identity and version"
git push origin main
git rev-list --left-right --count origin/main...HEAD
```

Expected: 仅计划、审计器和两份测试被提交；远端同步结果为 `0 0`。
