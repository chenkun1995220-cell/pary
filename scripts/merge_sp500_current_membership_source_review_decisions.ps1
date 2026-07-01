param(
  [string]$ProjectRoot = "",
  [string]$Template = "",
  [string]$Decisions = "",
  [string]$SummaryJson = "",
  [string]$SummaryMarkdown = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $Template) {
  $Template = Join-Path $ProjectRoot "outputs\automation\sp500_current_membership_source_review_decisions_template.csv"
}
if (-not $Decisions) {
  $Decisions = Join-Path $ProjectRoot "outputs\automation\sp500_current_membership_source_review_decisions.csv"
}
if (-not $SummaryJson) {
  $SummaryJson = Join-Path $ProjectRoot "outputs\automation\latest_sp500_current_membership_source_review_decision_merge.json"
}
if (-not $SummaryMarkdown) {
  $SummaryMarkdown = Join-Path $ProjectRoot "outputs\automation\latest_sp500_current_membership_source_review_decision_merge.md"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "sp500_current_membership_source_review_decision_merge.py"

$Args = @(
  "-B", $Script,
  "--template", $Template,
  "--decisions", $Decisions,
  "--summary-json", $SummaryJson,
  "--summary-md", $SummaryMarkdown
)

& $Python @Args
if ($LASTEXITCODE -ne 0) {
  throw "S&P 500 current membership source review decision merge failed with exit code $LASTEXITCODE."
}
