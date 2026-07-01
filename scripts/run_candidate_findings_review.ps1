param(
  [string]$ProjectRoot = "",
  [string]$Output = "",
  [string]$Report = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_candidate_findings_review.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_candidate_findings_review.md"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "candidate_findings_review.py"

Write-Host "Candidate findings review"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "Reads: valuation_targets.csv, latest_investment_summary.md"
Write-Host "Writes: latest_candidate_findings_review.json, latest_candidate_findings_review.md"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script --output $Output --report $Report
if ($LASTEXITCODE -ne 0) {
  throw "Candidate findings review failed with exit code $LASTEXITCODE."
}
