param(
  [string]$ProjectRoot = "",
  [string]$CandidateRiskPriorityReview = "",
  [string]$Output = "",
  [string]$Report = "",
  [string]$CsvOutput = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $CandidateRiskPriorityReview) {
  $CandidateRiskPriorityReview = Join-Path $ProjectRoot "outputs\automation\latest_candidate_risk_priority_review.json"
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_candidate_risk_manual_review_plan.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_candidate_risk_manual_review_plan.md"
}
if (-not $CsvOutput) {
  $CsvOutput = Join-Path $ProjectRoot "outputs\automation\candidate_risk_manual_review_plan.csv"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "candidate_risk_manual_review_plan.py"

Write-Host "Candidate risk manual review plan"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "CandidateRiskPriorityReview: $CandidateRiskPriorityReview"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "CsvOutput: $CsvOutput"
Write-Host "Reads: latest_candidate_risk_priority_review.json"
Write-Host "Writes: latest_candidate_risk_manual_review_plan.json, latest_candidate_risk_manual_review_plan.md, candidate_risk_manual_review_plan.csv"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script --candidate-risk-priority-review $CandidateRiskPriorityReview --output $Output --report $Report --csv-output $CsvOutput
if ($LASTEXITCODE -ne 0) {
  throw "Candidate risk manual review plan failed with exit code $LASTEXITCODE."
}
