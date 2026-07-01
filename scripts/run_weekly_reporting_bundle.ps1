param(
  [string]$ProjectRoot = "",
  [int]$MaxAgeDays = 8,
  [switch]$DryRun,
  [switch]$Strict,
  [switch]$IgnorePreSubmitFailure
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}

$PowerShell = (Get-Command powershell.exe).Source

$postSteps = @(
  @{ Label = "run_self_analysis"; Script = "run_self_analysis.ps1"; Critical = $true },
  @{ Label = "run_data_health_review"; Script = "run_data_health_review.ps1"; Critical = $true },
  @{ Label = "run_backtest_evidence_review"; Script = "run_backtest_evidence_review.ps1"; Critical = $true },
  @{ Label = "run_sp500_current_membership_sources"; Script = "run_sp500_current_membership_sources.ps1"; Critical = $true },
  @{ Label = "merge_sp500_current_membership_source_review_decisions"; Script = "merge_sp500_current_membership_source_review_decisions.ps1"; Critical = $true },
  @{ Label = "apply_sp500_current_membership_source_review_decisions"; Script = "apply_sp500_current_membership_source_review_decisions.ps1"; Critical = $true },
  @{ Label = "run_sp500_current_membership_source_review_status"; Script = "run_sp500_current_membership_source_review_status.ps1"; Critical = $true },
  @{ Label = "run_membership_evidence_import_plan"; Script = "run_membership_evidence_import_plan.ps1"; Critical = $true },
  @{ Label = "run_membership_evidence_apply_preview"; Script = "run_membership_evidence_apply_preview.ps1"; Critical = $true },
  @{ Label = "run_candidate_findings_review"; Script = "run_candidate_findings_review.ps1"; Critical = $true },
  @{ Label = "run_forecast_performance_review"; Script = "run_forecast_performance_review.ps1"; Critical = $true },
  @{ Label = "run_medium_term_goal_review"; Script = "run_medium_term_goal_review.ps1"; Critical = $true },
  @{ Label = "run_model_handoff_review"; Script = "run_model_handoff_review.ps1"; Critical = $true },
  @{ Label = "show_automation_check"; Script = "show_automation_check.ps1"; Critical = $true },
  @{ Label = "show_weekly_action_items"; Script = "show_weekly_action_items.ps1"; Critical = $true },
  @{ Label = "run_weekly_ops_check"; Script = "run_weekly_ops_check.ps1"; Critical = $true },
  @{ Label = "show_weekly_ops_history"; Script = "show_weekly_ops_history.ps1"; Critical = $true },
  @{ Label = "show_weekly_conclusion"; Script = "show_weekly_conclusion.ps1"; Critical = $true },
  @{ Label = "run_weekly_delivery_check"; Script = "run_weekly_delivery_check.ps1"; Critical = $true },
  @{ Label = "show_weekly_delivery_history"; Script = "show_weekly_delivery_history.ps1"; Critical = $true },
  @{ Label = "run_pre_submit_review"; Script = "run_pre_submit_review.ps1"; Critical = $false },
  @{ Label = "show_development_closeout"; Script = "show_development_closeout.ps1"; Critical = $true }
)

Write-Host "Starting weekly reporting closure bundle"

foreach ($step in $postSteps) {
  $scriptPath = Join-Path $ProjectRoot (Join-Path "scripts" $step.Script)
  if (-not (Test-Path -LiteralPath $scriptPath)) {
    throw "Required step script not found: $($step.Script)"
  }

  $label = $step.Label
  Write-Host "Running: $label"

  if ($DryRun) {
    Write-Host "DryRun: no script executed for $label"
    continue
  }

  $args = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $scriptPath)
  if ($step.Script -eq "run_pre_submit_review.ps1") {
    $args += @("-MaxAgeDays", "$MaxAgeDays")
  }

  & $PowerShell @args

  $exitCode = $LASTEXITCODE
  if ($exitCode -eq 0) {
    continue
  }

  if (-not $step.Critical -and $IgnorePreSubmitFailure) {
    Write-Warning "Step $label returned exit code $exitCode and was intentionally non-blocking."
    continue
  }

  if (-not $Strict) {
    Write-Warning "Step $label returned exit code $exitCode."
    continue
  }

  throw "Step $label failed with exit code $exitCode."
}

Write-Host "Weekly reporting closure bundle completed."
