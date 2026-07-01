param(
  [string]$ProjectRoot = "",
  [string]$Output = "",
  [string]$Report = "",
  [string]$History = "",
  [string]$Checklist = "",
  [string]$CloseoutGoalCode = "",
  [int]$MaxAgeDays = 8
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_pre_submit_review.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_pre_submit_review.md"
}
if (-not $History) {
  $History = Join-Path $ProjectRoot "outputs\automation\pre_submit_review_history.jsonl"
}
$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "pre_submit_review.py"

$Arguments = @(
  "-B",
  $Script,
  "--project-root",
  $ProjectRoot,
  "--output",
  $Output,
  "--report",
  $Report,
  "--history",
  $History,
  "--max-age-days",
  $MaxAgeDays
)
if ($Checklist) {
  $Arguments += @("--checklist", $Checklist)
}
if ($CloseoutGoalCode) {
  $Arguments += @("--closeout-goal-code", $CloseoutGoalCode)
}

& $Python @Arguments
if ($LASTEXITCODE -ne 0) {
  throw "Pre-submit review failed with exit code $LASTEXITCODE."
}
