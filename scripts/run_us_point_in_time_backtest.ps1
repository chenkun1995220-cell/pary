param(
  [int]$Years = 3,
  [int]$PilotWeeks = 8,
  [string]$OutputRoot = "",
  [string]$SecUserAgent = $env:SEC_USER_AGENT,
  [switch]$FullRun,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputRoot) {
  $OutputRoot = Join-Path $ProjectRoot "outputs\backtests\us_3y_weekly"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$AutomationRoot = Join-Path $ProjectRoot "outputs\automation"
$HistoricalMembership = Join-Path $OutputRoot "historical_membership.csv"
$ReplayManifest = Join-Path $OutputRoot "replay_manifest.csv"
$Checkpoint = Join-Path $OutputRoot "checkpoint.json"
$BacktestForecasts = Join-Path $OutputRoot "backtest_forecasts.csv"
$BacktestEvaluations = Join-Path $OutputRoot "backtest_evaluations.csv"
$ModelComparison = Join-Path $OutputRoot "model_comparison.csv"
$BacktestReport = Join-Path $OutputRoot "backtest_report.md"
$LeakageAudit = Join-Path $OutputRoot "data_leakage_audit.md"

$Steps = @(
  "1/8 Build historical S&P 500 membership",
  "2/8 Load point-in-time SEC facts",
  "3/8 Load historical prices",
  "4/8 Replay weekly screening",
  "5/8 Write replay manifest and checkpoint",
  "6/8 Evaluate backtest forecasts",
  "7/8 Run rolling shadow comparison",
  "8/8 Write backtest report"
)

Write-Host "US strict point-in-time backtest pipeline"
Write-Host "OutputRoot: $OutputRoot"
Write-Host "Years: $Years"
Write-Host "PilotWeeks: $PilotWeeks"
Write-Host "FullRun: $([bool]$FullRun)"
Write-Host "historical_sp500.py -> $HistoricalMembership"
Write-Host "us_weekly_replay.py -> $BacktestForecasts"
Write-Host "shadow_backtest.py -> $ModelComparison"
Write-Host "replay_manifest.csv -> $ReplayManifest"
Write-Host "checkpoint.json -> $Checkpoint"
Write-Host "backtest_evaluations.csv -> $BacktestEvaluations"
Write-Host "backtest_report.md -> $BacktestReport"
Write-Host "data_leakage_audit.md -> $LeakageAudit"
foreach ($step in $Steps) { Write-Host $step }
Write-Host "Default command: scripts\run_us_point_in_time_backtest.ps1 -PilotWeeks 8"

if ($DryRun) {
  Write-Host "DryRun: no files or network requests were created."
  exit 0
}

throw "Batch weekly replay runner is not wired yet. Use -DryRun for plan inspection; implement the week loop before pilot or FullRun execution."

if (-not $SecUserAgent) {
  throw "SEC_USER_AGENT is required. Pass -SecUserAgent or set the environment variable."
}

$env:SEC_USER_AGENT = $SecUserAgent
$mutex = [System.Threading.Mutex]::new($false, "Local\StockUndervaluationPointInTimeBacktest")
$hasLock = $false
$transcriptStarted = $false

try {
  $hasLock = $mutex.WaitOne(0)
  if (-not $hasLock) {
    throw "Another point-in-time backtest run is already in progress."
  }

  New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
  New-Item -ItemType Directory -Force -Path $AutomationRoot | Out-Null
  $runStamp = Get-Date -Format "yyyyMMdd_HHmmss"
  $logPath = Join-Path $AutomationRoot "us_point_in_time_backtest_$runStamp.log"
  Start-Transcript -Path $logPath | Out-Null
  $transcriptStarted = $true

  $weeksToRun = if ($FullRun) { 156 } else { $PilotWeeks }
  Write-Host "Running pilot weeks: $weeksToRun"

  Write-Host "Running: $($Steps[0])"
  & $Python -B historical_sp500.py --output $HistoricalMembership --years $Years
  if ($LASTEXITCODE -ne 0) { throw "$($Steps[0]) failed with exit code $LASTEXITCODE." }

  Write-Host "Running: $($Steps[1])"
  Write-Host "SEC facts are loaded by us_weekly_replay.py from the configured Company Facts cache."

  Write-Host "Running: $($Steps[2])"
  Write-Host "Historical prices are loaded by historical_price_store.py during weekly replay."

  Write-Host "Running: $($Steps[3])"
  & $Python -B us_weekly_replay.py --help | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "$($Steps[3]) failed with exit code $LASTEXITCODE." }

  Write-Host "Running: $($Steps[4])"
  $checkpointPayload = @{
    batch_id = $runStamp
    output_root = $OutputRoot
    pilot_weeks = $weeksToRun
    full_run = [bool]$FullRun
    updated_at = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    replay_manifest = $ReplayManifest
  } | ConvertTo-Json -Depth 4
  Set-Content -LiteralPath $Checkpoint -Value $checkpointPayload -Encoding UTF8
  if (-not (Test-Path $ReplayManifest)) {
    "batch_id,week,status,config_digest,updated_at" | Set-Content -LiteralPath $ReplayManifest -Encoding UTF8
  }

  Write-Host "Running: $($Steps[5])"
  if (Test-Path $BacktestForecasts) {
    & $Python -B forecast_tracker.py --market US --forecasts $BacktestForecasts --stock-history (Join-Path $OutputRoot "price_history.csv") --benchmark-history (Join-Path $OutputRoot "benchmark_history.csv") --output-root $OutputRoot
    if ($LASTEXITCODE -ne 0) { throw "$($Steps[5]) failed with exit code $LASTEXITCODE." }
  } else {
    Write-Host "No backtest_forecasts.csv yet; skipping evaluation until replay output exists."
  }

  Write-Host "Running: $($Steps[6])"
  if (Test-Path $BacktestEvaluations) {
    & $Python -B shadow_backtest.py --evaluations $BacktestEvaluations --output-root $OutputRoot
    if ($LASTEXITCODE -ne 0) { throw "$($Steps[6]) failed with exit code $LASTEXITCODE." }
  } else {
    Write-Host "No backtest_evaluations.csv yet; skipping shadow comparison until evaluations exist."
  }

  Write-Host "Running: $($Steps[7])"
  if (-not (Test-Path $BacktestReport)) {
    @(
      "# US Strict Point-in-Time Backtest Report",
      "",
      "- Conclusion: sample or evidence accumulation in progress; do not auto-upgrade the formal model.",
      "- OutputRoot: $OutputRoot",
      "- Log: $logPath"
    ) | Set-Content -LiteralPath $BacktestReport -Encoding UTF8
  }

  Write-Host "Point-in-time backtest completed. OutputRoot: $OutputRoot"
}
finally {
  if ($transcriptStarted) {
    Stop-Transcript | Out-Null
  }
  if ($hasLock) {
    $mutex.ReleaseMutex()
  }
  $mutex.Dispose()
}
