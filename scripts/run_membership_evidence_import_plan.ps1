param(
  [string]$ProjectRoot = "",
  [string]$Gaps = "",
  [string]$CurrentSourcePack = "",
  [string]$OutputJson = "",
  [string]$OutputCsv = "",
  [string]$OutputMarkdown = "",
  [string]$SourceTemplate = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $Gaps) {
  $Gaps = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_gaps.json"
}
if (-not $CurrentSourcePack) {
  $CurrentSourcePack = Join-Path $ProjectRoot "data\config\us_sp500_current_membership_sources.csv"
}
if (-not $OutputJson) {
  $OutputJson = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_import_plan.json"
}
if (-not $OutputCsv) {
  $OutputCsv = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_import_plan.csv"
}
if (-not $OutputMarkdown) {
  $OutputMarkdown = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_import_plan.md"
}
if (-not $SourceTemplate) {
  $SourceTemplate = Join-Path $ProjectRoot "outputs\automation\us_sp500_current_membership_sources_template.csv"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "membership_evidence_import_plan.py"

Write-Host "Membership evidence import plan"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "Gaps: $Gaps"
Write-Host "CurrentSourcePack: $CurrentSourcePack"
Write-Host "OutputJson: $OutputJson"
Write-Host "OutputCsv: $OutputCsv"
Write-Host "OutputMarkdown: $OutputMarkdown"
Write-Host "SourceTemplate: $SourceTemplate"
Write-Host "Reads: latest_membership_evidence_gaps.json, us_sp500_current_membership_sources.csv"
Write-Host "Writes: latest_membership_evidence_import_plan.json, latest_membership_evidence_import_plan.csv, latest_membership_evidence_import_plan.md, us_sp500_current_membership_sources_template.csv"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script `
  --gaps $Gaps `
  --current-source-pack $CurrentSourcePack `
  --output-json $OutputJson `
  --output-csv $OutputCsv `
  --output-md $OutputMarkdown `
  --source-template $SourceTemplate
if ($LASTEXITCODE -ne 0) {
  throw "Membership evidence import plan failed with exit code $LASTEXITCODE."
}
