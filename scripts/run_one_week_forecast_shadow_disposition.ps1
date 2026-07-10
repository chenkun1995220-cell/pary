param(
  [string]$ProjectRoot = "",
  [string]$Plan = "",
  [string]$Validation = "",
  [string]$History = "",
  [string]$Performance = "",
  [string]$Output = "",
  [string]$Report = "",
  [string]$AsOfDate = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $Plan) {
  $Plan = Join-Path $ProjectRoot "outputs\automation\latest_one_week_forecast_shadow_parameter_plan.json"
}
if (-not $Validation) {
  $Validation = Join-Path $ProjectRoot "outputs\automation\latest_one_week_forecast_shadow_parameter_validation.json"
}
if (-not $History) {
  $History = Join-Path $ProjectRoot "outputs\automation\one_week_forecast_shadow_parameter_validation_history.jsonl"
}
if (-not $Performance) {
  $Performance = Join-Path $ProjectRoot "outputs\automation\latest_forecast_performance_review.json"
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_one_week_forecast_shadow_disposition.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_one_week_forecast_shadow_disposition.md"
}
if (-not $AsOfDate) {
  $AsOfDate = Get-Date -Format "yyyy-MM-dd"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "one_week_forecast_shadow_disposition.py"

Write-Host "One-week forecast shadow disposition"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "Plan: $Plan"
Write-Host "Validation: $Validation"
Write-Host "History: $History"
Write-Host "Performance: $Performance"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "AsOfDate: $AsOfDate"
Write-Host "Boundary: shadow-only; formal model parameters remain unchanged"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script `
  --plan $Plan `
  --validation $Validation `
  --history $History `
  --performance $Performance `
  --as-of-date $AsOfDate `
  --output $Output `
  --report $Report
if ($LASTEXITCODE -ne 0) {
  throw "One-week forecast shadow disposition failed with exit code $LASTEXITCODE."
}
