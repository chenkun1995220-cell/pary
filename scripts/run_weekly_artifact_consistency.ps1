param(
  [string]$ProjectRoot = "",
  [string]$AsOfDate = "",
  [int]$MaxAgeDays = 8,
  [string]$Output = "",
  [string]$Report = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

if (-not $ProjectRoot) { $ProjectRoot = Split-Path -Parent $PSScriptRoot }
if (-not $AsOfDate) { $AsOfDate = Get-Date -Format "yyyy-MM-dd" }
if (-not $Output) { $Output = Join-Path $ProjectRoot "outputs\automation\latest_weekly_artifact_consistency.json" }
if (-not $Report) { $Report = Join-Path $ProjectRoot "outputs\automation\latest_weekly_artifact_consistency.md" }

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "weekly_artifact_consistency.py"

Write-Host "Weekly artifact consistency review"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "AsOfDate: $AsOfDate"
Write-Host "MaxAgeDays: $MaxAgeDays"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "Reads: three market summaries and candidate pools, weekly conclusion, delivery check, runtime US quote snapshot"
Write-Host "Writes: latest_weekly_artifact_consistency.json, latest_weekly_artifact_consistency.md"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script `
  --project-root $ProjectRoot `
  --as-of-date $AsOfDate `
  --max-age-days $MaxAgeDays `
  --output $Output `
  --report $Report
if ($LASTEXITCODE -ne 0) {
  throw "Weekly artifact consistency review failed with exit code $LASTEXITCODE."
}
