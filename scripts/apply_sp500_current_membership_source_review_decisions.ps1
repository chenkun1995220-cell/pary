param(
  [string]$ProjectRoot = "",
  [string]$Queue = "",
  [string]$Decisions = "",
  [string]$SummaryJson = "",
  [string]$SummaryMd = "",
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
if (-not $Decisions) {
  $Decisions = Join-Path $ProjectRoot "outputs\automation\sp500_current_membership_source_review_decisions.csv"
}
if (-not $SummaryJson) {
  $SummaryJson = Join-Path $ProjectRoot "outputs\automation\latest_sp500_current_membership_source_review_decision_apply.json"
}
if (-not $SummaryMd) {
  $SummaryMd = Join-Path $ProjectRoot "outputs\automation\latest_sp500_current_membership_source_review_decision_apply.md"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "sp500_current_membership_source_review_decisions.py"

Write-Host "Apply S&P 500 current membership source review decisions"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "Queue: $Queue"
Write-Host "Decisions: $Decisions"
Write-Host "SummaryJson: $SummaryJson"
Write-Host "SummaryMd: $SummaryMd"
Write-Host "DryRun: $DryRun"

$Args = @(
  "-B", $Script,
  "--queue", $Queue,
  "--decisions", $Decisions,
  "--summary-json", $SummaryJson,
  "--summary-md", $SummaryMd
)
if ($DryRun) {
  $Args += "--dry-run"
}

& $Python @Args
if ($LASTEXITCODE -ne 0) {
  throw "S&P 500 current membership source review decision apply failed with exit code $LASTEXITCODE."
}
