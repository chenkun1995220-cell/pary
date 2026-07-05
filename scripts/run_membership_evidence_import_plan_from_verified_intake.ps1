param(
  [string]$ProjectRoot = "",
  [string]$Gaps = "",
  [string]$VerifiedSourcePack = "",
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
if (-not $VerifiedSourcePack) {
  $VerifiedSourcePack = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_verified_source_pack.csv"
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

$Script = Join-Path $ProjectRoot "scripts\run_membership_evidence_import_plan.ps1"

Write-Host "Membership evidence import plan from verified intake"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "Gaps: $Gaps"
Write-Host "VerifiedSourcePack: $VerifiedSourcePack"
Write-Host "OutputJson: $OutputJson"
Write-Host "OutputCsv: $OutputCsv"
Write-Host "OutputMarkdown: $OutputMarkdown"
Write-Host "SourceTemplate: $SourceTemplate"
Write-Host "Reads: latest_membership_evidence_gaps.json, latest_membership_evidence_verified_source_pack.csv"
Write-Host "Writes: latest_membership_evidence_import_plan.json, latest_membership_evidence_import_plan.csv, latest_membership_evidence_import_plan.md"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

$readyRows = @()
if (Test-Path -LiteralPath $VerifiedSourcePack) {
  $readyRows = @(Import-Csv -LiteralPath $VerifiedSourcePack)
}
if ($readyRows.Count -le 0) {
  Write-Host "No verified intake source rows found; keeping existing membership evidence import plan unchanged."
  exit 0
}

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Script `
  -ProjectRoot $ProjectRoot `
  -Gaps $Gaps `
  -CurrentSourcePack $VerifiedSourcePack `
  -OutputJson $OutputJson `
  -OutputCsv $OutputCsv `
  -OutputMarkdown $OutputMarkdown `
  -SourceTemplate $SourceTemplate
if ($LASTEXITCODE -ne 0) {
  throw "Membership evidence import plan from verified intake failed with exit code $LASTEXITCODE."
}
