param(
  [string]$ProjectRoot = "",
  [string]$CalibrationReview = "",
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
if (-not $CalibrationReview) {
  $CalibrationReview = Join-Path $ProjectRoot "outputs\automation\latest_one_week_forecast_calibration_review.json"
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_one_week_forecast_shadow_parameter_plan.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_one_week_forecast_shadow_parameter_plan.md"
}
if (-not $AsOfDate) {
  $AsOfDate = Get-Date -Format "yyyy-MM-dd"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "one_week_forecast_shadow_parameter_plan.py"

Write-Host "One-week forecast shadow parameter plan"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "CalibrationReview: $CalibrationReview"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "AsOfDate: $AsOfDate"
Write-Host "Reads: latest_one_week_forecast_calibration_review.json"
Write-Host "Writes: latest_one_week_forecast_shadow_parameter_plan.json, latest_one_week_forecast_shadow_parameter_plan.md"
Write-Host "Boundary: shadow-only; does not modify formal model parameters"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script `
  --calibration-review $CalibrationReview `
  --as-of-date $AsOfDate `
  --output $Output `
  --report $Report
if ($LASTEXITCODE -ne 0) {
  throw "One-week forecast shadow parameter plan failed with exit code $LASTEXITCODE."
}
