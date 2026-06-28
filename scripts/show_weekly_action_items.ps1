param(
  [string]$ProjectRoot = "",
  [string]$Manifest = "",
  [string]$Output = "",
  [string]$Report = ""
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $Manifest) {
  $Manifest = Join-Path $ProjectRoot "outputs\automation\latest_self_analysis_manifest.json"
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_weekly_action_items.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_weekly_action_items.md"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "weekly_action_items.py"

& $Python -B $Script --manifest $Manifest --output $Output --report $Report
if ($LASTEXITCODE -ne 0) {
  throw "Weekly action items report failed with exit code $LASTEXITCODE."
}
