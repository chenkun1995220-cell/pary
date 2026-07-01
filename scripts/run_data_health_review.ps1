param(
  [string]$ProjectRoot = "",
  [string]$Manifest = "",
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
if (-not $Manifest) {
  $Manifest = Join-Path $ProjectRoot "outputs\automation\latest_self_analysis_manifest.json"
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_data_health_review.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_data_health_review.md"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "data_health_review.py"

Write-Host "Data health review"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "Manifest: $Manifest"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "Reads: latest_self_analysis_manifest.json, data_health_history.csv, quote_gaps.csv"
Write-Host "Writes: latest_data_health_review.json, latest_data_health_review.md"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script --manifest $Manifest --output $Output --report $Report
if ($LASTEXITCODE -ne 0) {
  throw "Data health review failed with exit code $LASTEXITCODE."
}
