param(
  [string]$ProjectRoot = "",
  [string]$AutomationRoot = "C:\Users\pechen\.codex\automations",
  [string]$Check = "",
  [string]$Output = "",
  [string]$History = "",
  [int]$MaxAgeDays = 8
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $Check) {
  $Check = Join-Path $ProjectRoot "outputs\automation\latest_automation_check.json"
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_weekly_ops_check.json"
}
if (-not $History) {
  $History = Join-Path $ProjectRoot "outputs\automation\weekly_ops_check_history.jsonl"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "weekly_ops_check.py"

& $Python -B $Script --project-root $ProjectRoot --automation-root $AutomationRoot --check $Check --output $Output --history $History --max-age-days $MaxAgeDays
if ($LASTEXITCODE -ne 0) {
  throw "Weekly operations check failed with exit code $LASTEXITCODE."
}
