param(
  [string]$ProjectRoot = "",
  [string]$AsOfDate = "",
  [string]$Output = "",
  [string]$Report = "",
  [string]$History = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"
if (-not $ProjectRoot) { $ProjectRoot = Split-Path -Parent $PSScriptRoot }
if (-not $AsOfDate) { $AsOfDate = Get-Date -Format "yyyy-MM-dd" }
if (-not $Output) { $Output = Join-Path $ProjectRoot "outputs\automation\latest_weekly_delivery_streak_review.json" }
if (-not $Report) { $Report = Join-Path $ProjectRoot "outputs\automation\latest_weekly_delivery_streak_review.md" }
if (-not $History) { $History = Join-Path $ProjectRoot "outputs\automation\weekly_delivery_streak_history.jsonl" }

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "weekly_delivery_streak_review.py"
Write-Host "Weekly delivery streak review"
Write-Host "AsOfDate: $AsOfDate"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "History: $History"
if ($DryRun) { Write-Host "DryRun: no files were created."; exit 0 }

& $Python -B $Script `
  --project-root $ProjectRoot `
  --as-of-date $AsOfDate `
  --output $Output `
  --report $Report `
  --history $History
if ($LASTEXITCODE -ne 0) { throw "Weekly delivery streak review failed with exit code $LASTEXITCODE." }
