param(
  [int]$Years = 3,
  [int]$PilotWeeks = 8,
  [ValidateSet("latest", "earliest")]
  [string]$PilotWindow = "latest",
  [int]$MaxCompanies = 0,
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
$BacktestSummary = Join-Path $AutomationRoot "latest_backtest_summary.md"
$LeakageAudit = Join-Path $OutputRoot "data_leakage_audit.md"
$PreparedPriceHistory = Join-Path $OutputRoot "price_history.csv"
$PreparedBenchmarkHistory = Join-Path $OutputRoot "benchmark_history.csv"
$CompanyFactsCache = Join-Path $ProjectRoot "data\cache\sec_companyfacts"
$HistoricalPriceCache = Join-Path $ProjectRoot "data\cache\historical_price_store"
$BenchmarkConfig = Join-Path $ProjectRoot "data\config\market_benchmarks.csv"
$UniverseConfig = Join-Path $ProjectRoot "data\config\us_universe_symbols.csv"
$EvidencePack = Join-Path $ProjectRoot "data\config\us_sp500_membership_evidence.csv"

$Steps = @(
  "1/8 Build historical S&P 500 membership",
  "2/8 Load point-in-time SEC facts",
  "3/8 Prepare historical prices",
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
Write-Host "PilotWindow: $PilotWindow"
Write-Host "MaxCompanies: $MaxCompanies"
Write-Host "FullRun: $([bool]$FullRun)"
Write-Host "EvidencePack: $EvidencePack"
Write-Host "EvidencePackReady: $((Test-Path -LiteralPath $EvidencePack))"
Write-Host "historical_sp500.py -> $HistoricalMembership"
Write-Host "backtest_membership_inputs.py -> $HistoricalMembership"
Write-Host "backtest_sec_cache.py -> $CompanyFactsCache"
Write-Host "backtest_price_inputs.py -> $PreparedPriceHistory"
Write-Host "us_weekly_replay.py -> $BacktestForecasts"
Write-Host "shadow_backtest.py -> $ModelComparison"
Write-Host "us_point_in_time_backtest.py -> $ReplayManifest"
Write-Host "replay_manifest.csv -> $ReplayManifest"
Write-Host "checkpoint.json -> $Checkpoint"
Write-Host "backtest_evaluations.csv -> $BacktestEvaluations"
Write-Host "backtest_report.md -> $BacktestReport"
Write-Host "latest_backtest_summary.md -> $BacktestSummary"
Write-Host "data_leakage_audit.md -> $LeakageAudit"
foreach ($step in $Steps) { Write-Host $step }
Write-Host "Default command: scripts\run_us_point_in_time_backtest.ps1 -PilotWeeks 8"

if ($DryRun) {
  Write-Host "DryRun: no files or network requests were created."
  exit 0
}

if (-not $SecUserAgent) {
  throw "SEC_USER_AGENT is required. Pass -SecUserAgent or set the environment variable."
}

$membershipReady = (Test-Path -LiteralPath $HistoricalMembership) -and ((Get-Item -LiteralPath $HistoricalMembership).Length -gt 0)
if ($membershipReady) {
  $membershipItem = Get-Item -LiteralPath $HistoricalMembership
  $membershipRefreshReasons = @()
  if ((Test-Path -LiteralPath $UniverseConfig) -and ((Get-Item -LiteralPath $UniverseConfig).LastWriteTimeUtc -gt $membershipItem.LastWriteTimeUtc)) {
    $membershipRefreshReasons += "universe_config_newer"
  }
  if ((Test-Path -LiteralPath $EvidencePack) -and ((Get-Item -LiteralPath $EvidencePack).LastWriteTimeUtc -gt $membershipItem.LastWriteTimeUtc)) {
    $membershipRefreshReasons += "evidence_pack_newer"
  }
  if ($membershipRefreshReasons.Count -gt 0) {
    $membershipReady = $false
    Write-Host "MembershipRefreshReason: $($membershipRefreshReasons -join ',')"
  }
}
if (-not $membershipReady) {
  Write-Host "Running: $($Steps[0])"
  $membershipWeeks = [Math]::Max(1, $Years * 52)
  $membershipArgs = @(
    "-B", "backtest_membership_inputs.py",
    "--universe-config", $UniverseConfig,
    "--output", $HistoricalMembership,
    "--weeks", "$membershipWeeks",
    "--market", "US",
    "--max-companies", "$MaxCompanies"
  )
  if (Test-Path -LiteralPath $EvidencePack) {
    $membershipArgs += @("--evidence-pack", $EvidencePack)
  }
  & $Python @membershipArgs
  if ($LASTEXITCODE -ne 0) {
    throw "$($Steps[0]) failed with exit code $LASTEXITCODE."
  }
}

$secCacheReady = $false
if (Test-Path -LiteralPath $CompanyFactsCache) {
  $secCacheReady = (@(Get-ChildItem -LiteralPath $CompanyFactsCache -Filter "CIK*.json" -File).Count -gt 0)
}
if (-not $secCacheReady) {
  Write-Host "Running: $($Steps[1])"
  & $Python -B backtest_sec_cache.py `
    --membership $HistoricalMembership `
    --cache-dir $CompanyFactsCache `
    --user-agent $SecUserAgent `
    --minimum-coverage 0.80
  if ($LASTEXITCODE -ne 0) {
    throw "$($Steps[1]) failed with exit code $LASTEXITCODE."
  }
}

$priceInputsReady = $false
if ((Test-Path -LiteralPath $PreparedPriceHistory) -and (Test-Path -LiteralPath $PreparedBenchmarkHistory)) {
  $priceInputsReady = ((Get-Item -LiteralPath $PreparedPriceHistory).Length -gt 0) -and ((Get-Item -LiteralPath $PreparedBenchmarkHistory).Length -gt 0)
}
if ($priceInputsReady) {
  $priceHistoryItem = Get-Item -LiteralPath $PreparedPriceHistory
  $benchmarkHistoryItem = Get-Item -LiteralPath $PreparedBenchmarkHistory
  $priceRefreshReasons = @()
  if ((Test-Path -LiteralPath $HistoricalMembership) -and ((Get-Item -LiteralPath $HistoricalMembership).LastWriteTimeUtc -gt $priceHistoryItem.LastWriteTimeUtc)) {
    $priceRefreshReasons += "membership_newer"
  }
  if ((Test-Path -LiteralPath $BenchmarkConfig) -and ((Get-Item -LiteralPath $BenchmarkConfig).LastWriteTimeUtc -gt $benchmarkHistoryItem.LastWriteTimeUtc)) {
    $priceRefreshReasons += "benchmark_config_newer"
  }
  if ($priceRefreshReasons.Count -gt 0) {
    $priceInputsReady = $false
    Write-Host "PriceRefreshReason: $($priceRefreshReasons -join ',')"
  }
}
if ((Test-Path -LiteralPath $HistoricalMembership) -and (-not $priceInputsReady)) {
  Write-Host "Running: $($Steps[2])"
  & $Python -B backtest_price_inputs.py `
    --membership $HistoricalMembership `
    --output-root $OutputRoot `
    --cache-dir $HistoricalPriceCache `
    --benchmark-config $BenchmarkConfig `
    --market US `
    --range 5y `
    --minimum-coverage 0.80
  if ($LASTEXITCODE -ne 0) {
    throw "$($Steps[2]) failed with exit code $LASTEXITCODE."
  }
}

$requiredInputs = @($HistoricalMembership, $PreparedPriceHistory, $PreparedBenchmarkHistory)
$missingInputs = @($requiredInputs | Where-Object { -not (Test-Path -LiteralPath $_) })
if ($missingInputs.Count -gt 0) {
  throw "Prepared backtest inputs are required before execution. Missing: $($missingInputs -join ', ')"
}
$emptyInputs = @($requiredInputs | Where-Object { (Get-Item -LiteralPath $_).Length -le 0 })
if ($emptyInputs.Count -gt 0) {
  throw "Prepared backtest inputs are required before execution. Empty: $($emptyInputs -join ', ')"
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

  Write-Host "Running: $($Steps[3]) through $($Steps[7])"
  $runnerArgs = @(
    "-B", "us_point_in_time_backtest.py",
    "--membership", $HistoricalMembership,
    "--company-facts-cache", $CompanyFactsCache,
    "--price-history", $PreparedPriceHistory,
    "--benchmark-history", $PreparedBenchmarkHistory,
    "--output-root", $OutputRoot,
    "--pilot-weeks", "$PilotWeeks",
    "--pilot-window", $PilotWindow
  )
  if ($FullRun) {
    $runnerArgs += "--full-run"
  }
  & $Python @runnerArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Point-in-time backtest runner failed with exit code $LASTEXITCODE."
  }

  $checkpointData = Get-Content -Raw -LiteralPath $Checkpoint | ConvertFrom-Json
  $reportText = Get-Content -Raw -LiteralPath $BacktestReport
  $reportLines = @($reportText -split "\r?\n")
  $verifiedLine = ($reportLines | Where-Object { $_ -match "\d+/\d+\s+\(\d+(\.\d+)?%\)" } | Select-Object -First 1)
  $verifiedValue = if ($verifiedLine) { $verifiedLine -replace "^[^0-9]*", "" } else { "unknown" }
  $weakLine = $null
  if ($verifiedLine) {
    $verifiedIndex = [array]::IndexOf($reportLines, $verifiedLine)
    if (($verifiedIndex -ge 0) -and (($verifiedIndex + 3) -lt $reportLines.Count)) {
      $weakLine = $reportLines[$verifiedIndex + 3]
    }
  }
  $weakValue = if ($weakLine) { $weakLine -replace "^[^0-9]*", "" } else { "unknown" }
  $summary = @(
    "# US Point-in-Time Backtest Summary",
    "",
    "- Run time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "- OutputRoot: $OutputRoot",
    "- Weeks completed: $($checkpointData.success_count)",
    "- Weeks failed: $($checkpointData.failure_count)",
    "- Membership evidence verified: $verifiedValue",
    "- Weak evidence rows: $weakValue",
    "- Backtest report: $BacktestReport",
    "- Data leakage audit: $LeakageAudit",
    "- Model comparison: $ModelComparison",
    "- Log: $logPath"
  )
  Set-Content -LiteralPath $BacktestSummary -Value $summary -Encoding UTF8
  Write-Host "Backtest summary: $BacktestSummary"
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
