param(
  [string]$ProjectRoot = "",
  [string]$Output = "",
  [string]$Report = "",
  [string]$GoalCode = "",
  [string[]]$ValidationCommand = @(),
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_model_handoff_review.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_model_handoff_review.md"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "model_handoff_review.py"

Write-Host "Model handoff review"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "Reads: latest_medium_term_goal_review.json"
Write-Host "Writes: latest_model_handoff_review.json, latest_model_handoff_review.md"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

if ($ValidationCommand.Count -eq 0) {
  $ValidationCommand = @(
    "powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\run_pre_submit_review.ps1 -MaxAgeDays 8",
    "$Python -m unittest tests.test_model_handoff_review tests.test_pre_submit_review"
  )
}

$Arguments = @(
  "-B",
  $Script,
  "--project-root",
  $ProjectRoot,
  "--output",
  $Output,
  "--report",
  $Report
)
if ($GoalCode) {
  $Arguments += @("--goal-code", $GoalCode)
}

foreach ($Command in $ValidationCommand) {
  $Arguments += @("--validation-command", $Command)
}

& $Python @Arguments
if ($LASTEXITCODE -ne 0) {
  throw "Model handoff review failed with exit code $LASTEXITCODE."
}
