param(
  [string]$ProjectRoot = "",
  [string]$Manifest = "",
  [string]$MembershipImportPlan = "",
  [string]$CurrentMembershipSources = "",
  [string]$CurrentMembershipSourceReviewStatus = "",
  [string]$CurrentMembershipSourceInboxStatus = "",
  [string]$ForecastPerformance = "",
  [string]$ManualReviewQueue = "",
  [string]$DataHealthReview = "",
  [string]$CandidateFindingsReview = "",
  [string]$BacktestEvidenceReview = "",
  [string]$Output = "",
  [string]$Report = ""
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $Manifest) {
  $Manifest = Join-Path $ProjectRoot "outputs\automation\latest_self_analysis_manifest.json"
}
if (-not $MembershipImportPlan) {
  $MembershipImportPlan = Join-Path $ProjectRoot "outputs\automation\latest_membership_evidence_import_plan.json"
}
if (-not $CurrentMembershipSources) {
  $CurrentMembershipSources = Join-Path $ProjectRoot "outputs\automation\latest_sp500_current_membership_sources.json"
}
if (-not $CurrentMembershipSourceReviewStatus) {
  $CurrentMembershipSourceReviewStatus = Join-Path $ProjectRoot "outputs\automation\latest_sp500_current_membership_source_review_status.json"
}
if (-not $CurrentMembershipSourceInboxStatus) {
  $CurrentMembershipSourceInboxStatus = Join-Path $ProjectRoot "outputs\automation\latest_sp500_current_membership_source_inbox_status.json"
}
if (-not $ForecastPerformance) {
  $ForecastPerformance = Join-Path $ProjectRoot "outputs\automation\latest_forecast_performance_review.json"
}
if (-not $ManualReviewQueue) {
  $ManualReviewQueue = Join-Path $ProjectRoot "outputs\automation\latest_manual_review_queue.csv"
}
if (-not $DataHealthReview) {
  $DataHealthReview = Join-Path $ProjectRoot "outputs\automation\latest_data_health_review.json"
}
if (-not $CandidateFindingsReview) {
  $CandidateFindingsReview = Join-Path $ProjectRoot "outputs\automation\latest_candidate_findings_review.json"
}
if (-not $BacktestEvidenceReview) {
  $BacktestEvidenceReview = Join-Path $ProjectRoot "outputs\automation\latest_backtest_evidence_review.json"
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "outputs\automation\latest_weekly_action_items.json"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_weekly_action_items.md"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "weekly_action_items.py"

& $Python -B $Script --manifest $Manifest --membership-import-plan $MembershipImportPlan --current-membership-sources $CurrentMembershipSources --current-membership-source-review-status $CurrentMembershipSourceReviewStatus --current-membership-source-inbox-status $CurrentMembershipSourceInboxStatus --forecast-performance $ForecastPerformance --manual-review-queue $ManualReviewQueue --data-health-review $DataHealthReview --candidate-findings-review $CandidateFindingsReview --backtest-evidence-review $BacktestEvidenceReview --output $Output --report $Report
if ($LASTEXITCODE -ne 0) {
  throw "Weekly action items report failed with exit code $LASTEXITCODE."
}
