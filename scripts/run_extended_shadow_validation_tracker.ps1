param(
  [string]$ProjectRoot = "",
  [string]$DecisionHistory = "",
  [string]$ValidationHistory = "",
  [string]$DecisionInbox = "",
  [string]$ShadowDisposition = "",
  [string]$Output = "",
  [string]$Report = "",
  [string]$BatchCsv = "",
  [string]$AsOfDate = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $DecisionHistory) {
  $DecisionHistory = Join-Path $ProjectRoot "outputs\automation\human_decision_history.csv"
}
if (-not $ValidationHistory) {
  $ValidationHistory = Join-Path $ProjectRoot "outputs\automation\one_week_forecast_shadow_parameter_validation_history.jsonl"
}
if (-not $DecisionInbox) {
  $DecisionInbox = Join-Path $ProjectRoot "outputs\automation\latest_human_decision_inbox.json"
}
if (-not $ShadowDisposition) {
  $ShadowDisposition = Join-Path $ProjectRoot "outputs\automation\latest_one_week_forecast_shadow_disposition.json"
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_extended_shadow_validation_tracker.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_extended_shadow_validation_tracker.md"
}
if (-not $BatchCsv) {
  $BatchCsv = Join-Path $ProjectRoot "outputs\automation\extended_shadow_validation_batches.csv"
}
if (-not $AsOfDate) {
  $AsOfDate = Get-Date -Format "yyyy-MM-dd"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "extended_shadow_validation_tracker.py"

Write-Host "Extended shadow validation tracker"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "AsOfDate: $AsOfDate"
Write-Host "Boundary: human decision only; no trade or formal model change"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script `
  --project-root $ProjectRoot `
  --decision-history $DecisionHistory `
  --validation-history $ValidationHistory `
  --decision-inbox $DecisionInbox `
  --shadow-disposition $ShadowDisposition `
  --as-of-date $AsOfDate `
  --output $Output `
  --report $Report `
  --batch-csv $BatchCsv
if ($LASTEXITCODE -ne 0) {
  throw "Extended shadow validation tracker failed with exit code $LASTEXITCODE."
}
