param(
  [string]$ProjectRoot = "",
  [string]$AutomationRoot = "C:\Users\pechen\.codex\automations",
  [string]$Check = ""
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $Check) {
  $Check = Join-Path $ProjectRoot "outputs\automation\latest_automation_check.json"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "weekly_ops_check.py"

& $Python -B $Script --project-root $ProjectRoot --automation-root $AutomationRoot --check $Check
if ($LASTEXITCODE -ne 0) {
  throw "Weekly operations check failed with exit code $LASTEXITCODE."
}
