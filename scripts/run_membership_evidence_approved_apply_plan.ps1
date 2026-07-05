param(
  [string]$ProjectRoot = "",
  [string]$ApprovedPackage = "",
  [string]$Membership = "",
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
if (-not $ApprovedPackage) {
  $ApprovedPackage = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_approved_apply_package.csv"
}
if (-not $Membership) {
  $Membership = Join-Path $ProjectRoot "outputs\backtests\us_3y_weekly\historical_membership.csv"
}
if (-not $OutputJson) {
  $OutputJson = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_approved_apply_plan.json"
}
if (-not $OutputCsv) {
  $OutputCsv = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_approved_apply_plan.csv"
}
if (-not $OutputMarkdown) {
  $OutputMarkdown = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_approved_apply_plan.md"
}
if (-not $AsOfDate) {
  $AsOfDate = Get-Date -Format "yyyy-MM-dd"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "membership_evidence_approved_apply_plan.py"

Write-Host "Membership evidence approved apply plan"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "ApprovedPackage: $ApprovedPackage"
Write-Host "Membership: $Membership"
Write-Host "OutputJson: $OutputJson"
Write-Host "OutputCsv: $OutputCsv"
Write-Host "OutputMarkdown: $OutputMarkdown"
Write-Host "AsOfDate: $AsOfDate"
Write-Host "Reads: latest_membership_evidence_approved_apply_package.csv, historical_membership.csv"
Write-Host "Writes: latest_membership_evidence_approved_apply_plan.json, latest_membership_evidence_approved_apply_plan.csv, latest_membership_evidence_approved_apply_plan.md"
Write-Host "Boundary: read-only plan; does not modify historical_membership.csv"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script `
  --approved-package $ApprovedPackage `
  --membership $Membership `
  --as-of-date $AsOfDate `
  --output-json $OutputJson `
  --output-csv $OutputCsv `
  --output-md $OutputMarkdown
if ($LASTEXITCODE -ne 0) {
  throw "Membership evidence approved apply plan failed with exit code $LASTEXITCODE."
}
