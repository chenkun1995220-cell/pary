param(
  [string]$ProjectRoot = "",
  [string]$Queue = "",
  [string]$Intake = "",
  [string]$Template = "",
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
if (-not $Queue) {
  $Queue = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_supplement_queue.json"
}
if (-not $Intake) {
  $Intake = Join-Path $ProjectRoot "inputs\sp500_membership_evidence\verified_membership_evidence_intake.csv"
}
if (-not $Template) {
  $Template = Join-Path $ProjectRoot "outputs\automation\us_sp500_verified_membership_evidence_intake_template.csv"
}
if (-not $OutputJson) {
  $OutputJson = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_source_intake_status.json"
}
if (-not $OutputCsv) {
  $OutputCsv = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_source_intake_status.csv"
}
if (-not $OutputMarkdown) {
  $OutputMarkdown = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_source_intake_status.md"
}
if (-not $AsOfDate) {
  $AsOfDate = Get-Date -Format "yyyy-MM-dd"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "membership_evidence_source_intake_status.py"

Write-Host "Membership evidence source intake status"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "Queue: $Queue"
Write-Host "Intake: $Intake"
Write-Host "Template: $Template"
Write-Host "OutputJson: $OutputJson"
Write-Host "OutputCsv: $OutputCsv"
Write-Host "OutputMarkdown: $OutputMarkdown"
Write-Host "AsOfDate: $AsOfDate"
Write-Host "Reads: latest_membership_evidence_supplement_queue.json, verified_membership_evidence_intake.csv when present"
Write-Host "Writes: latest_membership_evidence_source_intake_status.json, latest_membership_evidence_source_intake_status.csv, latest_membership_evidence_source_intake_status.md, us_sp500_verified_membership_evidence_intake_template.csv"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script `
  --queue $Queue `
  --intake $Intake `
  --template $Template `
  --as-of-date $AsOfDate `
  --output-json $OutputJson `
  --output-csv $OutputCsv `
  --output-md $OutputMarkdown
if ($LASTEXITCODE -ne 0) {
  throw "Membership evidence source intake status failed with exit code $LASTEXITCODE."
}
