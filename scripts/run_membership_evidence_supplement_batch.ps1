param(
  [string]$ProjectRoot = "",
  [string]$Queue = "",
  [int]$BatchSize = 10,
  [string]$OutputJson = "",
  [string]$OutputCsv = "",
  [string]$OutputMarkdown = "",
  [string]$IntakeDraft = "",
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
if (-not $OutputJson) {
  $OutputJson = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_supplement_batch.json"
}
if (-not $OutputCsv) {
  $OutputCsv = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_supplement_batch.csv"
}
if (-not $OutputMarkdown) {
  $OutputMarkdown = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_supplement_batch.md"
}
if (-not $IntakeDraft) {
  $IntakeDraft = Join-Path $ProjectRoot "inputs\sp500_membership_evidence\verified_membership_evidence_intake.csv"
}
if (-not $AsOfDate) {
  $AsOfDate = Get-Date -Format "yyyy-MM-dd"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "membership_evidence_supplement_batch.py"

Write-Host "Membership evidence supplement batch"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "Queue: $Queue"
Write-Host "BatchSize: $BatchSize"
Write-Host "OutputJson: $OutputJson"
Write-Host "OutputCsv: $OutputCsv"
Write-Host "OutputMarkdown: $OutputMarkdown"
Write-Host "IntakeDraft: $IntakeDraft"
Write-Host "AsOfDate: $AsOfDate"
Write-Host "Reads: latest_membership_evidence_supplement_queue.json"
Write-Host "Writes: latest_membership_evidence_supplement_batch.json, latest_membership_evidence_supplement_batch.csv, latest_membership_evidence_supplement_batch.md, verified_membership_evidence_intake.csv"
Write-Host "Boundary: read-only batch; does not modify historical_membership.csv"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script `
  --queue $Queue `
  --batch-size $BatchSize `
  --as-of-date $AsOfDate `
  --output-json $OutputJson `
  --output-csv $OutputCsv `
  --output-md $OutputMarkdown `
  --intake-draft $IntakeDraft
if ($LASTEXITCODE -ne 0) {
  throw "Membership evidence supplement batch failed with exit code $LASTEXITCODE."
}
