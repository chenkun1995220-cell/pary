param(
  [string]$ProjectRoot = "",
  [string]$ImportPlan = "",
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
if (-not $ImportPlan) {
  $ImportPlan = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_import_plan.json"
}
if (-not $OutputJson) {
  $OutputJson = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_supplement_queue.json"
}
if (-not $OutputCsv) {
  $OutputCsv = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_supplement_queue.csv"
}
if (-not $OutputMarkdown) {
  $OutputMarkdown = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_supplement_queue.md"
}
if (-not $AsOfDate) {
  $AsOfDate = Get-Date -Format "yyyy-MM-dd"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "membership_evidence_supplement_queue.py"

Write-Host "Membership evidence supplement queue"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "ImportPlan: $ImportPlan"
Write-Host "OutputJson: $OutputJson"
Write-Host "OutputCsv: $OutputCsv"
Write-Host "OutputMarkdown: $OutputMarkdown"
Write-Host "AsOfDate: $AsOfDate"
Write-Host "Reads: latest_membership_evidence_import_plan.json"
Write-Host "Writes: latest_membership_evidence_supplement_queue.json, latest_membership_evidence_supplement_queue.csv, latest_membership_evidence_supplement_queue.md"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script `
  --import-plan $ImportPlan `
  --as-of-date $AsOfDate `
  --output-json $OutputJson `
  --output-csv $OutputCsv `
  --output-md $OutputMarkdown
if ($LASTEXITCODE -ne 0) {
  throw "Membership evidence supplement queue failed with exit code $LASTEXITCODE."
}
