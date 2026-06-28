param(
  [string]$ProjectRoot = "",
  [string]$History = "",
  [string]$Output = "",
  [string]$Report = "",
  [int]$Window = 8
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $History) {
  $History = Join-Path $ProjectRoot "outputs\automation\weekly_delivery_check_history.jsonl"
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_weekly_delivery_history_summary.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_weekly_delivery_history_report.md"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "weekly_delivery_history_report.py"

& $Python -B $Script --history $History --window $Window --output $Output --report $Report
if ($LASTEXITCODE -ne 0) {
  throw "Weekly delivery history report failed with exit code $LASTEXITCODE."
}
