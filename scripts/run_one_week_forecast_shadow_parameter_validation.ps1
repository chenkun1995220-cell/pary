param(
  [string]$ProjectRoot = "",
  [string]$Plan = "",
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
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_one_week_forecast_shadow_parameter_validation.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_one_week_forecast_shadow_parameter_validation.md"
}
if (-not $AsOfDate) {
  $AsOfDate = Get-Date -Format "yyyy-MM-dd"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "one_week_forecast_shadow_parameter_validation.py"

Write-Host "One-week forecast shadow parameter validation"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "Plan: $Plan"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "AsOfDate: $AsOfDate"
Write-Host "Reads: latest_one_week_forecast_shadow_parameter_plan.json and market forecast_evaluations.csv"
Write-Host "Writes: latest_one_week_forecast_shadow_parameter_validation.json, latest_one_week_forecast_shadow_parameter_validation.md"
Write-Host "Boundary: shadow-only; does not modify formal model parameters"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script `
  --project-root $ProjectRoot `
  --plan $Plan `
  --as-of-date $AsOfDate `
  --output $Output `
  --report $Report
if ($LASTEXITCODE -ne 0) {
  throw "One-week forecast shadow parameter validation failed with exit code $LASTEXITCODE."
}
