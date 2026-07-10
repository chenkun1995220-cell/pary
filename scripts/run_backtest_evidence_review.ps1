param(
  [string]$ProjectRoot = "",
  [string]$Summary = "",
  [string]$Policy = "",
  [string]$Output = "",
  [string]$Report = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $Summary) {
  $Summary = Join-Path $ProjectRoot "outputs\automation\latest_backtest_summary.md"
}
if (-not $Policy) {
  $Policy = Join-Path $ProjectRoot "data\config\sp500_historical_evidence_policy.json"
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_backtest_evidence_review.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_backtest_evidence_review.md"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "backtest_evidence_review.py"

Write-Host "Backtest evidence review"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "Summary: $Summary"
Write-Host "Policy: $Policy"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "Reads: latest_backtest_summary.md, latest_membership_evidence_gaps.json, sp500_historical_evidence_policy.json"
Write-Host "Writes: latest_backtest_evidence_review.json, latest_backtest_evidence_review.md"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script --summary $Summary --policy $Policy --output $Output --report $Report
if ($LASTEXITCODE -ne 0) {
  throw "Backtest evidence review failed with exit code $LASTEXITCODE."
}
