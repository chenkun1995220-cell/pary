# US Backtest Automation Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a machine-readable human summary file for the US strict point-in-time backtest automation.

**Architecture:** Keep the summary in the PowerShell orchestrator because it already owns run metadata and transcript log paths. Reuse `checkpoint.json` and `backtest_report.md` after the Python runner succeeds, then write `outputs/automation/latest_backtest_summary.md`.

**Tech Stack:** PowerShell orchestrator, Python `unittest`, Markdown output files.

---

### Task 1: Script Static Contract

**Files:**
- Modify: `tests/test_weekly_automation.py`
- Modify: `scripts/run_us_point_in_time_backtest.ps1`
- Modify: `docs/美股每周自动运行说明.md`

- [ ] **Step 1: Write the failing test**

Add these assertions to `test_point_in_time_backtest_script_static_contract`:

```python
self.assertIn("latest_backtest_summary.md", script)
self.assertIn("BacktestSummary", script)
self.assertIn("Membership evidence verified", script)
self.assertIn("Weak evidence rows", script)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_automation.WeeklyAutomationTests.test_point_in_time_backtest_script_static_contract
```

Expected: FAIL because `latest_backtest_summary.md` is not declared in the script yet.

- [ ] **Step 3: Implement the minimal script output**

In `scripts/run_us_point_in_time_backtest.ps1`, add:

```powershell
$BacktestSummary = Join-Path $AutomationRoot "latest_backtest_summary.md"
```

After the Python runner succeeds, read `checkpoint.json` and `backtest_report.md`, then write:

```powershell
$checkpointData = Get-Content -Raw -LiteralPath $Checkpoint | ConvertFrom-Json
$reportText = Get-Content -Raw -LiteralPath $BacktestReport
$reportLines = @($reportText -split "\r?\n")
$verifiedLine = ($reportLines | Where-Object { $_ -match "\d+/\d+\s+\(\d+(\.\d+)?%\)" } | Select-Object -First 1)
$verifiedValue = if ($verifiedLine) { $verifiedLine -replace "^[^0-9]*", "" } else { "unknown" }
$weakLine = $null
if ($verifiedLine) {
  $verifiedIndex = [array]::IndexOf($reportLines, $verifiedLine)
  if (($verifiedIndex -ge 0) -and (($verifiedIndex + 3) -lt $reportLines.Count)) {
    $weakLine = $reportLines[$verifiedIndex + 3]
  }
}
$weakValue = if ($weakLine) { $weakLine -replace "^[^0-9]*", "" } else { "unknown" }
$summary = @(
  "# US Point-in-Time Backtest Summary",
  "",
  "- Run time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
  "- OutputRoot: $OutputRoot",
  "- Weeks completed: $($checkpointData.success_count)",
  "- Weeks failed: $($checkpointData.failure_count)",
  "- Membership evidence verified: $verifiedValue",
  "- Weak evidence rows: $weakValue",
  "- Backtest report: $BacktestReport",
  "- Data leakage audit: $LeakageAudit",
  "- Model comparison: $ModelComparison",
  "- Log: $logPath"
)
Set-Content -LiteralPath $BacktestSummary -Value $summary -Encoding UTF8
Write-Host "Backtest summary: $BacktestSummary"
```

- [ ] **Step 4: Document the new summary file**

Add `outputs/automation/latest_backtest_summary.md` to the run-mode documentation and explain that it is the short automation entrypoint for weekly review.

- [ ] **Step 5: Verify targeted and full tests**

Run:

```powershell
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_weekly_automation
& 'C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
```

Expected: all tests pass.
