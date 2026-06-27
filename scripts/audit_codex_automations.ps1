param(
  [string]$AutomationRoot = "C:\Users\pechen\.codex\automations"
)

$ErrorActionPreference = "Stop"

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

& $Python -B codex_automation_audit.py --automation-root $AutomationRoot
if ($LASTEXITCODE -ne 0) {
  throw "Codex automation audit failed with exit code $LASTEXITCODE."
}
