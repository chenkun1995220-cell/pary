param(
  [string]$ProjectRoot = "",
  [string]$DataHealthReview = "",
  [string]$Output = "",
  [string]$Report = "",
  [string]$CsvOutput = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $DataHealthReview) {
  $DataHealthReview = Join-Path $ProjectRoot "outputs\automation\latest_data_health_review.json"
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_data_quality_manual_review_plan.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_data_quality_manual_review_plan.md"
}
if (-not $CsvOutput) {
  $CsvOutput = Join-Path $ProjectRoot "outputs\automation\data_quality_manual_review_plan.csv"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "data_quality_manual_review_plan.py"

Write-Host "Data quality manual review plan"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "DataHealthReview: $DataHealthReview"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "CsvOutput: $CsvOutput"
Write-Host "Reads: latest_data_health_review.json"
Write-Host "Writes: latest_data_quality_manual_review_plan.json, latest_data_quality_manual_review_plan.md, data_quality_manual_review_plan.csv"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script --data-health-review $DataHealthReview --output $Output --report $Report --csv-output $CsvOutput
if ($LASTEXITCODE -ne 0) {
  throw "Data quality manual review plan failed with exit code $LASTEXITCODE."
}
