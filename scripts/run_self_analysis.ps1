param(
  [string]$ProjectRoot = "",
  [string]$Output = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_self_analysis.md"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

Write-Host "Weekly self-analysis aggregator"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "Output: $Output"
Write-Host "Reads: latest_run_summary.md, latest_backtest_summary.md, model_audit.md, data_health_history.csv, quote_gaps.csv, latest_investment_summary.md"
Write-Host "Writes: latest_self_analysis.md, latest_self_analysis_manifest.json, latest_manual_review_queue.csv, manual_review_queue_history.csv, manual_review_repeats.csv"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B automation_self_analysis.py --project-root $ProjectRoot --output $Output
if ($LASTEXITCODE -ne 0) {
  throw "Weekly self-analysis failed with exit code $LASTEXITCODE."
}
