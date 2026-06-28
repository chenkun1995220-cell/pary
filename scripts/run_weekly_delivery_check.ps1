param(
  [string]$ProjectRoot = "",
  [string]$ConclusionJson = "",
  [string]$Output = "",
  [string]$History = "",
  [int]$MaxAgeDays = 8
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $ConclusionJson) {
  $ConclusionJson = Join-Path $ProjectRoot "outputs\automation\latest_weekly_conclusion.json"
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_weekly_delivery_check.json"
}
if (-not $History) {
  $History = Join-Path $ProjectRoot "outputs\automation\weekly_delivery_check_history.jsonl"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "weekly_delivery_check.py"

# Recommended invocation:
# powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\run_weekly_delivery_check.ps1
& $Python -B $Script --project-root $ProjectRoot --conclusion-json $ConclusionJson --output $Output --history $History --max-age-days $MaxAgeDays
if ($LASTEXITCODE -ne 0) {
  throw "Weekly delivery check failed with exit code $LASTEXITCODE."
}
