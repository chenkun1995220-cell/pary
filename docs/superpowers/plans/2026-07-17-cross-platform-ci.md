# 跨平台持续集成实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为仓库增加 Windows 与 Ubuntu 双平台全量测试门槛，并以机器可读契约防止工作流误触行情、评分或模型链路。

**Architecture:** 使用一个 GitHub Actions 工作流和 `os` 矩阵运行相同的 Python 3.12 语法检查与全量单元测试。使用 PyYAML `BaseLoader` 的契约测试结构化读取工作流，验证触发范围、权限、矩阵、命令和禁止项；远端以两个矩阵任务真实成功作为最终验收。

**Tech Stack:** GitHub Actions、Python 3.12、`unittest`、PyYAML 6.x、PowerShell、GitHub CLI。

## Global Constraints

- 工作流只在向 `main` 推送、针对 `main` 的拉取请求和手动触发时运行。
- 测试矩阵必须同时包含 `windows-latest` 与 `ubuntu-latest`。
- 仓库权限只能是 `contents: read`，不得使用生产密钥。
- 不调用三市场周任务、行情抓取、候选评分、估值或模型更新入口。
- 不读取或写入 `outputs` 运行产物作为成功条件。
- 不删减现有测试、不降低质量门槛、不修改正式模型和影子分类阈值。
- 远端任一矩阵失败时必须读取本次日志并修复，不得引用旧运行结果。

---

## 文件结构

- Create: `.github/workflows/test.yml`：定义只读、双平台、全量测试工作流。
- Create: `requirements-dev.txt`：仅包含工作流契约测试所需的 PyYAML。
- Create: `tests/test_cross_platform_ci_workflow.py`：结构化验证工作流安全边界和执行契约。

### Task 1: 工作流契约测试与最小 CI 配置

**Files:**
- Create: `tests/test_cross_platform_ci_workflow.py`
- Create: `requirements-dev.txt`
- Create: `.github/workflows/test.yml`

**Interfaces:**
- Consumes: `requirements.txt` 与现有 `python -m unittest discover -s tests` 测试入口。
- Produces: GitHub Actions 工作流及 `CrossPlatformCIWorkflowTests` 契约测试类。

- [ ] **Step 1: 添加测试依赖与失败契约测试**

创建 `requirements-dev.txt`：

```text
PyYAML>=6.0,<7
```

创建 `tests/test_cross_platform_ci_workflow.py`：

```python
from pathlib import Path
import unittest

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "test.yml"


class CrossPlatformCIWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(WORKFLOW_PATH.exists(), "cross-platform workflow is missing")
        self.workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.workflow = yaml.load(self.workflow_text, Loader=yaml.BaseLoader)

    def test_triggers_only_target_main_and_manual_dispatch(self):
        triggers = self.workflow["on"]
        self.assertEqual(triggers["push"]["branches"], ["main"])
        self.assertEqual(triggers["pull_request"]["branches"], ["main"])
        self.assertEqual(triggers["workflow_dispatch"], None)

    def test_uses_read_only_permissions_and_cancels_superseded_runs(self):
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        self.assertEqual(self.workflow["concurrency"]["cancel-in-progress"], "true")

    def test_runs_full_suite_on_windows_and_ubuntu_with_python_312(self):
        job = self.workflow["jobs"]["test"]
        self.assertEqual(
            job["strategy"]["matrix"]["os"],
            ["windows-latest", "ubuntu-latest"],
        )
        self.assertEqual(job["runs-on"], "${{ matrix.os }}")
        steps = job["steps"]
        setup = next(step for step in steps if step.get("uses") == "actions/setup-python@v5")
        self.assertEqual(setup["with"]["python-version"], "3.12")
        commands = "\n".join(step.get("run", "") for step in steps)
        self.assertIn("pip install -r requirements.txt -r requirements-dev.txt", commands)
        self.assertIn("python -m compileall -q", commands)
        self.assertIn("python -m unittest discover -s tests", commands)

    def test_excludes_production_automation_and_write_capabilities(self):
        forbidden = (
            "run_us_universe_weekly",
            "run_cn_weekly",
            "run_hk_weekly",
            "SEC_USER_AGENT",
            "secrets.",
            "contents: write",
        )
        for value in forbidden:
            self.assertNotIn(value, self.workflow_text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行契约测试并确认因工作流缺失而失败**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_cross_platform_ci_workflow -v
```

Expected: FAIL，错误包含 `cross-platform workflow is missing`。

- [ ] **Step 3: 创建最小 GitHub Actions 工作流**

创建 `.github/workflows/test.yml`：

```yaml
name: Cross-platform tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: tests-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    name: Python 3.12 / ${{ matrix.os }}
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [windows-latest, ubuntu-latest]
    steps:
      - name: Check out repository
        uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: |
            requirements.txt
            requirements-dev.txt
      - name: Install dependencies
        run: python -m pip install --disable-pip-version-check -r requirements.txt -r requirements-dev.txt
      - name: Compile Python sources
        run: python -m compileall -q -x '(^|[\\/])(\.git|\.venv|__pycache__|inputs|outputs)([\\/]|$)' .
      - name: Run full unit test suite
        run: python -m unittest discover -s tests
```

- [ ] **Step 4: 运行聚焦测试并确认通过**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_cross_platform_ci_workflow -v
```

Expected: 4 tests PASS。

- [ ] **Step 5: 运行完整本地验证**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q -x '(^|[\\/])(\.git|\.venv|__pycache__|inputs|outputs)([\\/]|$)' .
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
git diff --check
```

Expected: compileall 退出码 0；现有 994 项加 4 项契约测试全部通过；`git diff --check` 无输出。

- [ ] **Step 6: 提交实现**

```powershell
git add .github/workflows/test.yml requirements-dev.txt tests/test_cross_platform_ci_workflow.py
git commit -m "ci: add cross-platform test matrix"
```

Expected: 提交仅包含上述三个文件。

### Task 2: 远端矩阵验收与合并

**Files:**
- Verify: `.github/workflows/test.yml`
- Verify: GitHub Actions 当前分支运行日志

**Interfaces:**
- Consumes: Task 1 提交的工作流和测试。
- Produces: Windows 与 Ubuntu 两个平台均成功的远端验收证据，以及同步后的 `main`。

- [ ] **Step 1: 推送功能分支并创建针对 main 的拉取请求**

```powershell
git push -u origin codex/cross-platform-ci
gh pr create --base main --head codex/cross-platform-ci --title "Add cross-platform CI" --body "Adds read-only Windows and Ubuntu full-test validation. Does not run market automation or modify model outputs."
```

Expected: 推送成功并返回拉取请求 URL；`pull_request` 事件启动 `test.yml`。

- [ ] **Step 2: 等待并检查当前拉取请求的两个矩阵任务**

```powershell
gh pr checks codex/cross-platform-ci --watch --interval 10
```

Expected: `windows-latest` 与 `ubuntu-latest` 均成功。不得使用旧 Actions 运行作为证据。

- [ ] **Step 3: 若远端失败，读取精确日志并最小修复**

```powershell
$runId = gh run list --branch codex/cross-platform-ci --workflow test.yml --limit 1 --json databaseId --jq '.[0].databaseId'
gh run view $runId --log-failed
```

Expected: 只根据当前运行的失败步骤定位问题。代码缺陷先增加可复现测试再修复；工作流语法或环境配置缺陷只做最小配置修复。不得删减 Ubuntu、Windows、全量测试或只读权限要求。

- [ ] **Step 4: 独立复核与合并前验证**

Run:

```powershell
git diff --check main..HEAD
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
```

Expected: 差异检查通过、完整测试通过，独立复核没有 Critical、Important 或 Minor 问题。

- [ ] **Step 5: 快进合并、推送 main 并验证远端一致**

```powershell
git switch main
git pull --ff-only origin main
git merge --ff-only codex/cross-platform-ci
git push origin main
git rev-list --left-right --count HEAD...origin/main
```

Expected: 快进合并和推送成功，最终差异为 `0 0`。推送 `main` 触发的工作流也必须在 Windows 与 Ubuntu 成功后，才能声明本轮优化完成。
