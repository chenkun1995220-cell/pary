param(
  [string]$ProjectRoot = "",
  [string]$ApplyPreview = "",
  [string]$Decisions = "",
  [string]$Template = "",
  [string]$ApprovedPackage = "",
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
if (-not $ApplyPreview) {
  $ApplyPreview = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_apply_preview.json"
}
if (-not $Decisions) {
  $Decisions = Join-Path $ProjectRoot "inputs\sp500_membership_evidence\apply_confirmation_decisions.csv"
}
if (-not $Template) {
  $Template = Join-Path $ProjectRoot "outputs\automation\membership_evidence_apply_confirmation_decisions_template.csv"
}
if (-not $ApprovedPackage) {
  $ApprovedPackage = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_approved_apply_package.csv"
}
if (-not $OutputJson) {
  $OutputJson = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_apply_confirmation_status.json"
}
if (-not $OutputCsv) {
  $OutputCsv = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_apply_confirmation_status.csv"
}
if (-not $OutputMarkdown) {
  $OutputMarkdown = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_apply_confirmation_status.md"
}
if (-not $AsOfDate) {
  $AsOfDate = Get-Date -Format "yyyy-MM-dd"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "membership_evidence_apply_confirmation_status.py"

Write-Host "Membership evidence apply confirmation status"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "ApplyPreview: $ApplyPreview"
Write-Host "Decisions: $Decisions"
Write-Host "Template: $Template"
Write-Host "ApprovedPackage: $ApprovedPackage"
Write-Host "OutputJson: $OutputJson"
Write-Host "OutputCsv: $OutputCsv"
Write-Host "OutputMarkdown: $OutputMarkdown"
Write-Host "AsOfDate: $AsOfDate"
Write-Host "Reads: latest_membership_evidence_apply_preview.json, apply_confirmation_decisions.csv when present"
Write-Host "Writes: latest_membership_evidence_apply_confirmation_status.json, latest_membership_evidence_apply_confirmation_status.csv, latest_membership_evidence_apply_confirmation_status.md, membership_evidence_apply_confirmation_decisions_template.csv, latest_membership_evidence_approved_apply_package.csv"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script `
  --apply-preview $ApplyPreview `
  --decisions $Decisions `
  --template $Template `
  --approved-package $ApprovedPackage `
  --as-of-date $AsOfDate `
  --output-json $OutputJson `
  --output-csv $OutputCsv `
  --output-md $OutputMarkdown
if ($LASTEXITCODE -ne 0) {
  throw "Membership evidence apply confirmation status failed with exit code $LASTEXITCODE."
}
