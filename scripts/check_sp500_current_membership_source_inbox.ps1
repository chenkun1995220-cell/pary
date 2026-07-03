param(
  [string]$ProjectRoot = "",
  [string]$Template = "",
  [string]$SourceFileInbox = "",
  [string]$IntakeTemplate = "",
  [string]$SourceUrl = "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
  [string]$Output = "",
  [string]$Report = "",
  [string]$AsOfDate = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $Template) {
  $Template = Join-Path $ProjectRoot "outputs\automation\us_sp500_current_membership_sources_template.csv"
}
if (-not $SourceFileInbox) {
  $SourceFileInbox = Join-Path $ProjectRoot "inputs\sp500_current_membership\official_constituents.csv"
}
if (-not $IntakeTemplate) {
  $IntakeTemplate = Join-Path $ProjectRoot "outputs\automation\sp500_current_membership_source_intake_template.csv"
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_sp500_current_membership_source_inbox_status.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_sp500_current_membership_source_inbox_status.md"
}
if (-not $AsOfDate) {
  $AsOfDate = Get-Date -Format "yyyy-MM-dd"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "sp500_current_membership_source_inbox_status.py"

Write-Host "S&P 500 current membership source inbox status"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "Template: $Template"
Write-Host "SourceFileInbox: $SourceFileInbox"
Write-Host "IntakeTemplate: $IntakeTemplate"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "AsOfDate: $AsOfDate"
Write-Host "Reads: official_constituents.csv, sp500_current_membership_source_intake_template.csv"
Write-Host "Writes: latest_sp500_current_membership_source_inbox_status.json, latest_sp500_current_membership_source_inbox_status.md"

& $Python -B $Script --template $Template --source-file-inbox $SourceFileInbox --intake-template $IntakeTemplate --source-url $SourceUrl --as-of-date $AsOfDate --output $Output --report $Report
if ($LASTEXITCODE -ne 0) {
  throw "S&P 500 current membership source inbox status check failed with exit code $LASTEXITCODE."
}
