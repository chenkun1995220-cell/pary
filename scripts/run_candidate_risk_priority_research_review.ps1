param(
  [string]$ProjectRoot = "",
  [string]$CandidateRiskManualReviewPlan = "",
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
if (-not $CandidateRiskManualReviewPlan) {
  $CandidateRiskManualReviewPlan = Join-Path $ProjectRoot "outputs\automation\latest_candidate_risk_manual_review_plan.json"
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_candidate_risk_priority_research_review.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_candidate_risk_priority_research_review.md"
}
if (-not $CsvOutput) {
  $CsvOutput = Join-Path $ProjectRoot "outputs\automation\candidate_risk_priority_research_review.csv"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "candidate_risk_priority_research_review.py"

Write-Host "Candidate risk priority research review"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "CandidateRiskManualReviewPlan: $CandidateRiskManualReviewPlan"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "CsvOutput: $CsvOutput"
Write-Host "Reads: latest_candidate_risk_manual_review_plan.json"
Write-Host "Writes: latest_candidate_risk_priority_research_review.json, latest_candidate_risk_priority_research_review.md, candidate_risk_priority_research_review.csv"

if ($DryRun) {
  Write-Host "DryRun: no files were created."
  exit 0
}

& $Python -B $Script --candidate-risk-manual-review-plan $CandidateRiskManualReviewPlan --output $Output --report $Report --csv-output $CsvOutput
if ($LASTEXITCODE -ne 0) {
  throw "Candidate risk priority research review failed with exit code $LASTEXITCODE."
}
