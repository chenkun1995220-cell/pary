param(
  [string]$ProjectRoot = "",
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
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_one_week_forecast_calibration_review.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_one_week_forecast_calibration_review.md"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "one_week_forecast_calibration_review.py"

Write-Host "One-week forecast calibration shadow review"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "Reads: forecast_evaluations.csv"
Write-Host "Writes: latest_one_week_forecast_calibration_review.json, latest_one_week_forecast_calibration_review.md"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script --project-root $ProjectRoot --output $Output --report $Report
if ($LASTEXITCODE -ne 0) {
  throw "One-week forecast calibration shadow review failed with exit code $LASTEXITCODE."
}
