param(
  [string]$ProjectRoot = "",
  [string]$Output = "",
  [string]$Report = "",
  [string]$CloseoutGoalCode = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_medium_term_goal_review.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_medium_term_goal_review.md"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "medium_term_goal_review.py"

Write-Host "Medium-term goal review"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "Reads: weekly review artifacts in outputs\automation"
Write-Host "Writes: latest_medium_term_goal_review.json, latest_medium_term_goal_review.md"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
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
if ($CloseoutGoalCode) {
  $Arguments += @("--closeout-goal-code", $CloseoutGoalCode)
}

& $Python @Arguments
if ($LASTEXITCODE -ne 0) {
  throw "Medium-term goal review failed with exit code $LASTEXITCODE."
}
