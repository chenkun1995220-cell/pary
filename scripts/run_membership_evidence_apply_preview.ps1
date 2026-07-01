param(
  [string]$ProjectRoot = "",
  [string]$Membership = "",
  [string]$CurrentSourcePack = "",
  [string]$OutputJson = "",
  [string]$OutputCsv = "",
  [string]$OutputMarkdown = "",
  [string]$AsOfDate = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $Membership) {
  $Membership = Join-Path $ProjectRoot "outputs\backtests\us_3y_weekly\historical_membership.csv"
}
if (-not $CurrentSourcePack) {
  $CurrentSourcePack = Join-Path $ProjectRoot "data\config\us_sp500_current_membership_sources.csv"
}
if (-not $OutputJson) {
  $OutputJson = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_apply_preview.json"
}
if (-not $OutputCsv) {
  $OutputCsv = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_apply_preview.csv"
}
if (-not $OutputMarkdown) {
  $OutputMarkdown = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_apply_preview.md"
}
if (-not $AsOfDate) {
  $AsOfDate = Get-Date -Format "yyyy-MM-dd"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "membership_evidence_apply_preview.py"

Write-Host "Membership evidence apply preview"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "Membership: $Membership"
Write-Host "CurrentSourcePack: $CurrentSourcePack"
Write-Host "OutputJson: $OutputJson"
Write-Host "OutputCsv: $OutputCsv"
Write-Host "OutputMarkdown: $OutputMarkdown"
Write-Host "AsOfDate: $AsOfDate"
Write-Host "Reads: historical_membership.csv, us_sp500_current_membership_sources.csv"
Write-Host "Writes: latest_membership_evidence_apply_preview.json, latest_membership_evidence_apply_preview.csv, latest_membership_evidence_apply_preview.md"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script `
  --membership $Membership `
  --current-source-pack $CurrentSourcePack `
  --as-of-date $AsOfDate `
  --output-json $OutputJson `
  --output-csv $OutputCsv `
  --output-md $OutputMarkdown
if ($LASTEXITCODE -ne 0) {
  throw "Membership evidence apply preview failed with exit code $LASTEXITCODE."
}
