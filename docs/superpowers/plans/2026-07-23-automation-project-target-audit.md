# Automation Project Target Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让三项市场定时任务在 Codex 项目绑定缺失或无效时被自动化审计阻断，同时允许非空项目 ID 随项目迁移而变化。

**Architecture:** 沿用 `codex_automation_audit.py` 的单任务校验流程，在 `cron` 分支读取 TOML `target` 表并追加明确问题；心跳任务仍只校验 `target_thread_id`。审计结果增加目标字段供 Markdown 报告展示，不改变现有任务定义或正式模型。

**Tech Stack:** Python 3 标准库（`tomllib`、`unittest`）、TOML、Git。

## Global Constraints

- `target.type` 必须为 `project`。
- `target.project_id` 去除首尾空白后必须非空。
- 不绑定具体 `project_id`。
- 心跳验收任务继续使用 `target_thread_id`。
- 不修改 Codex 自动化配置、三市场抓取流程或正式模型参数。
- 不引入第三方依赖，不降低任何现有质量门槛。

---

### Task 1: 校验并展示市场任务项目绑定

**Files:**
- Modify: `tests/test_codex_automation_audit.py`
- Modify: `tests/test_weekly_ops_check.py`
- Modify: `codex_automation_audit.py`

**Interfaces:**
- Consumes: `_load_toml(path) -> dict` 解析出的 `target` TOML 表。
- Produces: `_check_automation(...)` 返回新增的 `target_type: str` 与 `target_project_id: str`，并在无效绑定时向 `issues: list[str]` 追加原因。

- [x] **Step 1: 扩展测试夹具并编写失败测试**

在 `write_automation` 参数中加入：

```python
    include_target=True,
    target_type="project",
    target_project_id="test-project",
```

在 `kind == "cron"` 的配置行中按参数生成：

```python
        if include_target:
            lines.append(
                "target = { "
                f"type = {json.dumps(target_type)}, "
                f"project_id = {json.dumps(target_project_id)} "
                "}"
            )
```

新增无效绑定测试，分别覆盖缺失目标、错误类型和空白 ID：

```python
    def test_audit_requires_valid_project_target_for_market_crons(self):
        cases = (
            ({"include_target": False}, "target.type"),
            ({"target_type": "thread"}, "target.type"),
            ({"target_project_id": "   "}, "target.project_id"),
        )
        for kwargs, expected_issue in cases:
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

                result = audit_automations(tmp)
                us_check = result["checks"][0]

                self.assertEqual(us_check["status"], "needs_attention")
                self.assertTrue(
                    any(expected_issue in issue for issue in us_check["issues"])
                )
```

新增可迁移性和报告展示测试：

```python
    def test_audit_allows_any_nonempty_project_id_and_reports_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_automation(
                tmp,
                "automation",
                "美股低估公司每周筛选",
                "scripts\\run_us_universe_weekly.ps1 不提前运行三市场统一收口 market_quotes.csv",
                5,
                target_project_id="migrated-project",
            )

            from codex_automation_audit import audit_automations, render_audit_report

            result = audit_automations(tmp)
            us_check = result["checks"][0]

            self.assertFalse(
                any("target." in issue for issue in us_check["issues"])
            )
            self.assertEqual(us_check["target_type"], "project")
            self.assertEqual(us_check["target_project_id"], "migrated-project")
            self.assertIn("target: project / migrated-project", render_audit_report(result))
```

- [x] **Step 2: 运行新增测试并确认准确失败**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_codex_automation_audit.CodexAutomationAuditTests.test_audit_requires_valid_project_target_for_market_crons tests.test_codex_automation_audit.CodexAutomationAuditTests.test_audit_allows_any_nonempty_project_id_and_reports_it
```

Expected: `FAIL`，原因是审计尚未校验或返回 `target_type` / `target_project_id`。

- [x] **Step 3: 实施最小项目绑定校验**

在 `_check_automation` 的 `cron` 分支加入：

```python
        target = data.get("target")
        if not isinstance(target, dict):
            target = {}
        if target.get("type") != "project":
            issues.append(
                f"target.type expected project got {target.get('type', '')}"
            )
        if not str(target.get("project_id", "")).strip():
            issues.append("target.project_id must be configured")
```

在返回字典加入：

```python
        "target_type": target.get("type", "") if expected_kind == "cron" else "",
        "target_project_id": (
            target.get("project_id", "") if expected_kind == "cron" else ""
        ),
```

在 `render_audit_report` 的任务详情中加入：

```python
        if check.get("target_type") or check.get("target_project_id"):
            lines.append(
                "  - target: "
                f"{check.get('target_type', '')} / {check.get('target_project_id', '')}"
            )
```

在验收重点加入：

```python
            "- 三项市场任务必须绑定 project 类型且提供非空 project_id；审计不绑定具体项目 ID。",
```

- [x] **Step 4: 运行新增测试和关联测试并确认通过**

在 `tests/test_weekly_ops_check.py` 的有效自动化夹具中补充：

```python
                    'target = { type = "project", project_id = "test-project" }',
```

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_codex_automation_audit tests.test_weekly_ops_check
```

Expected: 全部测试 `OK`。

- [x] **Step 5: 运行真实配置审计和全量测试**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' codex_automation_audit.py
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
```

Expected: 真实配置审计为 `4/4 ready`，三项市场任务展示非空项目绑定；全量测试 `OK`。

- [x] **Step 6: 核对范围、提交并推送**

Run:

```powershell
git diff --check
git status --short
git diff --stat
git add -- codex_automation_audit.py tests/test_codex_automation_audit.py tests/test_weekly_ops_check.py docs/superpowers/plans/2026-07-23-automation-project-target-audit.md
git commit -m "Audit automation project targets"
git push origin main
git rev-list --left-right --count origin/main...HEAD
```

Expected: 仅计划、审计器和两份测试被提交；远端同步结果为 `0 0`。
