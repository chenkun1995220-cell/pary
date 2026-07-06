param(
  [string]$ProjectRoot = "",
  [string]$ImportPlan = "",
  [string]$CurrentSources = "",
  [string]$InboxStatus = "",
  [string]$BacktestReview = "",
  [string]$OfficialExportProbe = "",
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
if (-not $ImportPlan) {
  $ImportPlan = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_import_plan.json"
}
if (-not $CurrentSources) {
  $CurrentSources = Join-Path $ProjectRoot "outputs\automation\latest_sp500_current_membership_sources.json"
}
if (-not $InboxStatus) {
  $InboxStatus = Join-Path $ProjectRoot "outputs\automation\latest_sp500_current_membership_source_inbox_status.json"
}
if (-not $BacktestReview) {
  $BacktestReview = Join-Path $ProjectRoot "outputs\automation\latest_backtest_evidence_review.json"
}
if (-not $OfficialExportProbe) {
  $OfficialExportProbe = Join-Path $ProjectRoot "outputs\automation\latest_sp500_official_export_probe.json"
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_sp500_verified_source_plan.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_sp500_verified_source_plan.md"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "sp500_verified_source_plan.py"

Write-Host "S&P 500 verified source plan"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "ImportPlan: $ImportPlan"
Write-Host "CurrentSources: $CurrentSources"
Write-Host "InboxStatus: $InboxStatus"
Write-Host "BacktestReview: $BacktestReview"
Write-Host "OfficialExportProbe: $OfficialExportProbe"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "Reads: latest_membership_evidence_import_plan.json, latest_sp500_current_membership_sources.json, latest_sp500_current_membership_source_inbox_status.json, latest_backtest_evidence_review.json, latest_sp500_official_export_probe.json"
Write-Host "Writes: latest_sp500_verified_source_plan.json, latest_sp500_verified_source_plan.md"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script --project-root $ProjectRoot --import-plan $ImportPlan --current-sources $CurrentSources --inbox-status $InboxStatus --backtest-review $BacktestReview --official-export-probe $OfficialExportProbe --output $Output --report $Report
if ($LASTEXITCODE -ne 0) {
  throw "S&P 500 verified source plan failed with exit code $LASTEXITCODE."
}
