param(
  [string]$ProjectRoot = "",
  [string]$Output = "",
  [string]$JsonOutput = "",
  [string]$DecisionsTemplateOutput = "",
  [string]$Today = "",
  [int]$MaxAgeDays = 8
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_weekly_conclusion.md"
}
if (-not $JsonOutput) {
  $JsonOutput = Join-Path $ProjectRoot "outputs\automation\latest_weekly_conclusion.json"
}
if (-not $DecisionsTemplateOutput) {
  $DecisionsTemplateOutput = Join-Path $ProjectRoot "outputs\automation\manual_review_decisions_template.csv"
}

# Manual equivalent:
# powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\show_weekly_conclusion.ps1
$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "weekly_conclusion_report.py"
$Args = @(
  "-B", $Script,
  "--project-root", $ProjectRoot,
  "--output", $Output,
  "--json-output", $JsonOutput,
  "--decisions-template-output", $DecisionsTemplateOutput,
  "--max-age-days", $MaxAgeDays
)
if ($Today) {
  $Args += @("--today", $Today)
}

& $Python @Args
if ($LASTEXITCODE -ne 0) {
  throw "Weekly conclusion report failed with exit code $LASTEXITCODE."
}
