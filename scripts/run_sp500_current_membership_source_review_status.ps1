param(
  [string]$ProjectRoot = "",
  [string]$Queue = "",
  [string]$Output = "",
  [string]$Report = "",
  [string]$DecisionsTemplate = "",
  [string]$Decisions = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $Queue) {
  $Queue = Join-Path $ProjectRoot "outputs\automation\sp500_current_membership_source_review_queue.csv"
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_sp500_current_membership_source_review_status.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_sp500_current_membership_source_review_status.md"
}
if (-not $DecisionsTemplate) {
  $DecisionsTemplate = Join-Path $ProjectRoot "outputs\automation\sp500_current_membership_source_review_decisions_template.csv"
}
if (-not $Decisions) {
  $Decisions = Join-Path $ProjectRoot "outputs\automation\sp500_current_membership_source_review_decisions.csv"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "sp500_current_membership_source_review_status.py"

Write-Host "S&P 500 current membership source review status"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "Queue: $Queue"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "DecisionsTemplate: $DecisionsTemplate"
Write-Host "Decisions: $Decisions"
Write-Host "Reads: sp500_current_membership_source_review_queue.csv"
Write-Host "Writes: latest_sp500_current_membership_source_review_status.json, latest_sp500_current_membership_source_review_status.md, sp500_current_membership_source_review_decisions_template.csv"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script --queue $Queue --output $Output --report $Report --decisions-template $DecisionsTemplate --decisions $Decisions
if ($LASTEXITCODE -ne 0) {
  throw "S&P 500 current membership source review status failed with exit code $LASTEXITCODE."
}
