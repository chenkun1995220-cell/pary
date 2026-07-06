param(
  [string]$ProjectRoot = "",
  [string]$OfficialExportUrl = "",
  [string]$Output = "",
  [string]$Report = "",
  [string]$AsOfDate = "",
  [string]$UserAgent = "",
  [int]$TimeoutSeconds = 30,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_sp500_official_export_probe.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_sp500_official_export_probe.md"
}
if (-not $AsOfDate) {
  $AsOfDate = Get-Date -Format "yyyy-MM-dd"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "sp500_official_export_probe.py"

Write-Host "S&P 500 official export probe"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "OfficialExportUrl: $OfficialExportUrl"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "AsOfDate: $AsOfDate"
Write-Host "Writes: latest_sp500_official_export_probe.json, latest_sp500_official_export_probe.md"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

$args = @(
  "-B",
  $Script,
  "--as-of-date",
  $AsOfDate,
  "--timeout",
  "$TimeoutSeconds",
  "--output",
  $Output,
  "--report",
  $Report
)
if ($OfficialExportUrl) {
  $args += @("--official-export-url", $OfficialExportUrl)
}
if ($UserAgent) {
  $args += @("--user-agent", $UserAgent)
}

& $Python @args
if ($LASTEXITCODE -ne 0) {
  throw "S&P 500 official export probe failed with exit code $LASTEXITCODE."
}
