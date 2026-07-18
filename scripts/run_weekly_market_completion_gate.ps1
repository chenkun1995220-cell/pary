param(
  [string]$ProjectRoot = "",
  [string]$AsOfDate = (Get-Date -Format "yyyy-MM-dd"),
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "weekly_market_completion_gate.py"
$Output = Join-Path $ProjectRoot "outputs\automation\latest_weekly_market_completion_gate.json"
$Report = Join-Path $ProjectRoot "outputs\automation\latest_weekly_market_completion_gate.md"

Write-Host "Weekly market completion gate"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "AsOfDate: $AsOfDate"
Write-Host "Output: $Output"
Write-Host "Report: $Report"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script `
  --project-root $ProjectRoot `
  --as-of-date $AsOfDate `
  --output $Output `
  --report $Report
exit $LASTEXITCODE
