param(
  [string]$ProjectRoot = "",
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

& $Python -B automation_check_report.py --check $Check
if ($LASTEXITCODE -ne 0) {
  throw "Weekly automation check report failed with exit code $LASTEXITCODE."
}
