param(
  [string]$ProjectRoot = "",
  [string]$AsOfDate = "",
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
if (-not $AsOfDate) {
  $AsOfDate = Get-Date -Format "yyyy-MM-dd"
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_first_one_month_forecast_evaluation_review.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_first_one_month_forecast_evaluation_review.md"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "first_one_month_forecast_evaluation_review.py"

Write-Host "First one-month forecast evaluation review"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "AsOfDate: $AsOfDate"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "Reads: forecast_history.csv, forecast_evaluations.csv"
Write-Host "Writes: latest_first_one_month_forecast_evaluation_review.json, latest_first_one_month_forecast_evaluation_review.md"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script --project-root $ProjectRoot --as-of-date $AsOfDate --output $Output --report $Report
if ($LASTEXITCODE -ne 0) {
  throw "First one-month forecast evaluation review failed with exit code $LASTEXITCODE."
}
