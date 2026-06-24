# Weekly Self Analysis Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a unified weekly self-analysis summary that reads existing market summaries and backtest summaries without rerunning pipelines.

**Architecture:** Add a focused Python module for parsing Markdown summaries and generating `latest_self_analysis.md`. Add a thin PowerShell wrapper for automation use, and document the new output path in the existing Chinese operations guide.

**Tech Stack:** Python standard library, `unittest`, PowerShell wrapper, Markdown output.

---

### Task 1: Self Analysis Aggregator

**Files:**
- Create: `automation_self_analysis.py`
- Create: `tests/test_automation_self_analysis.py`

- [ ] **Step 1: Write the failing complete-summary test**

Create `tests/test_automation_self_analysis.py` with a test that builds a temporary project tree, writes:

```text
outputs/automation/latest_run_summary.md
outputs/cn_universe/latest_run_summary.md
outputs/hk_universe/latest_run_summary.md
outputs/automation/latest_backtest_summary.md
outputs/us_universe/model_audit.md
outputs/cn_universe/model_audit.md
outputs/hk_universe/model_audit.md
```

Assert that `run_self_analysis(root, as_of_date="2026-06-25")` writes `outputs/automation/latest_self_analysis.md` and includes `每周自我分析摘要`, `美股周筛`, `候选数：2`, `成员证据 verified：35/40 (87.5%)`, `弱证据行：5`, and `继续补充历史成分 verified 证据`.

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_automation_self_analysis
```

Expected: import failure because `automation_self_analysis.py` does not exist.

- [ ] **Step 3: Implement minimal aggregator**

Create `automation_self_analysis.py` with:

```python
def run_self_analysis(project_root, output=None, as_of_date=None):
    ...
```

The function reads existing summaries, treats missing files as `missing`, writes Markdown to `outputs/automation/latest_self_analysis.md`, and returns a result dict containing `output`.

- [ ] **Step 4: Verify aggregator tests pass**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_automation_self_analysis
```

Expected: PASS.

### Task 2: Automation Entry Point And Docs

**Files:**
- Create: `scripts/run_self_analysis.ps1`
- Modify: `tests/test_weekly_automation.py`
- Modify: `docs/美股每周自动运行说明.md`

- [ ] **Step 1: Write failing script contract test**

Add a test to `tests/test_weekly_automation.py` asserting `scripts/run_self_analysis.ps1` includes:

```python
self.assertIn("automation_self_analysis.py", script)
self.assertIn("latest_self_analysis.md", script)
self.assertIn("DryRun", script)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_automation.WeeklyAutomationTests.test_self_analysis_script_static_contract
```

Expected: FAIL because the script does not exist.

- [ ] **Step 3: Create PowerShell wrapper**

Create `scripts/run_self_analysis.ps1` with parameters:

```powershell
param(
  [string]$ProjectRoot = "",
  [string]$Output = "",
  [switch]$DryRun
)
```

It prints the planned output in dry-run mode and invokes:

```powershell
& $Python -B automation_self_analysis.py --project-root $ProjectRoot --output $Output
```

- [ ] **Step 4: Update docs**

Add `outputs/automation/latest_self_analysis.md` and `scripts/run_self_analysis.ps1` to the Chinese automation guide.

- [ ] **Step 5: Verify script and full tests**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_automation_self_analysis tests.test_weekly_automation
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m py_compile automation_self_analysis.py
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
```

Expected: all tests pass.
