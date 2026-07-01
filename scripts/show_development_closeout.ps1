param(
  [string]$ProjectRoot = "",
  [string]$Review = "",
  [string]$GoalCode = "",
  [string]$Module = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $Review) {
  $Review = Join-Path $ProjectRoot "outputs\automation\latest_medium_term_goal_review.json"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "development_closeout_summary.py"

$ArgsList = @($Script, "--review", $Review)
if ($GoalCode) {
  $ArgsList += @("--goal-code", $GoalCode)
}
if ($Module) {
  $ArgsList += @("--module", $Module)
}

& $Python -B @ArgsList
if ($LASTEXITCODE -ne 0) {
  throw "Development closeout summary failed with exit code $LASTEXITCODE."
}
