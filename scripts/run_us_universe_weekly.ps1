param(
  [string]$SecUserAgent = $env:SEC_USER_AGENT,
  [string]$OutputRoot = "",
  [switch]$RunPostChecks,
  [int]$PostCheckMaxAgeDays = 8,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputRoot) {
  $OutputRoot = Join-Path $ProjectRoot "outputs\us_universe"
}

$Symbols = Join-Path $ProjectRoot "data\config\us_universe_symbols.csv"
$Companies = Join-Path $ProjectRoot "data\samples\us_universe_companies.csv"
$Quotes = Join-Path $OutputRoot "market_quotes.csv"
$Sp500Cache = Join-Path $ProjectRoot "data\cache\sp500"
$SecCache = Join-Path $ProjectRoot "data\cache\sec_companyfacts"
$PowerShell = (Get-Command powershell.exe).Source
$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$ReviewChecklistPath = Join-Path $ProjectRoot "docs\提交前复核清单.md"

$Steps = @(
  @{ Label = "1/10 Refresh S&P 500 constituents"; Script = "refresh_sp500_constituents.ps1"; Arguments = @("-Output", $Symbols, "-CacheDir", $Sp500Cache) },
  @{ Label = "2/10 Build US universe"; Script = "build_us_universe.ps1"; Arguments = @("-Symbols", $Symbols, "-Output", $Companies, "-Sp500Cache", $Sp500Cache, "-SkipConstituentRefresh") },
  @{ Label = "3/10 Fill market quotes"; Script = "auto_fill_us_real_sample_quotes.ps1"; Arguments = @("-Companies", $Companies, "-Output", $Quotes, "-CacheDir", $SecCache) },
  @{ Label = "4/10 Run screening"; Script = "run_us_real_sample.ps1"; Arguments = @("-Companies", $Companies, "-Quotes", $Quotes, "-OutputRoot", $OutputRoot, "-CacheDir", $SecCache) },
  @{ Label = "5/10 Generate research packs"; Script = "generate_candidate_research_packs.ps1"; Arguments = @("-ScreeningRoot", $OutputRoot, "-Companies", $Companies) }
)
$ValuationSteps = @("6/10 Fetch candidate price history", "7/10 Generate valuation targets", "8/10 Fetch benchmark history", "9/10 Track forecast performance", "10/10 Audit forecast model", "11/11 Generate investment summary")

Write-Host "US weekly screening pipeline"
Write-Host "OutputRoot: $OutputRoot"
foreach ($step in $Steps) {
  Write-Host $step.Label
}
foreach ($label in $ValuationSteps) { Write-Host $label }
if ($RunPostChecks) {
  Write-Host "完成后将自动执行 run_weekly_reporting_bundle.ps1"
} else {
  Write-Host "完成后请先执行复核清单：$ReviewChecklistPath"
  Write-Host "完成后请执行 run_pre_submit_review.ps1"
  Write-Host "可一键收口：powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\\run_weekly_reporting_bundle.ps1"
}

if ($DryRun) {
  Write-Host "DryRun: no files or network requests were created."
  exit 0
}

if (-not $SecUserAgent) {
  throw "SEC_USER_AGENT is required. Pass -SecUserAgent or set the environment variable."
}

$env:SEC_USER_AGENT = $SecUserAgent
$mutex = [System.Threading.Mutex]::new($false, "Local\StockUndervaluationWeekly")
$hasLock = $false
$transcriptStarted = $false

try {
  $hasLock = $mutex.WaitOne(0)
  if (-not $hasLock) {
    throw "Another weekly screening run is already in progress."
  }

  $runStartedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
  $runStamp = Get-Date -Format "yyyyMMdd_HHmmss"
  $logPath = Join-Path $OutputRoot "run_$runStamp.log"
  Start-Transcript -Path $logPath | Out-Null
  $transcriptStarted = $true

  foreach ($step in $Steps) {
    $scriptPath = Join-Path $PSScriptRoot $step.Script
    Write-Host "Running: $($step.Label)"
    & $PowerShell -NoProfile -ExecutionPolicy Bypass -File $scriptPath @($step.Arguments)
    if ($LASTEXITCODE -ne 0) {
      throw "$($step.Label) failed with exit code $LASTEXITCODE."
    }
  }

  $candidatePath = Join-Path $OutputRoot "candidate_pool.csv"
  $historyPath = Join-Path $OutputRoot "price_history.csv"
  $historyCache = Join-Path $SecCache "candidate_price_history"
  Write-Host "Running: $($ValuationSteps[0])"
  & $Python -B candidate_price_history.py --market US --candidates $candidatePath --output $historyPath --cache-dir $historyCache --minimum-coverage 0.80
  if ($LASTEXITCODE -ne 0) { throw "$($ValuationSteps[0]) failed with exit code $LASTEXITCODE." }

  Write-Host "Running: $($ValuationSteps[1])"
  & $Python -B candidate_valuation.py `
    --market US `
    --candidates $candidatePath `
    --price-history $historyPath `
    --industry-medians (Join-Path $OutputRoot "industry_medians.csv") `
    --quotes $Quotes `
    --output-root $OutputRoot
  if ($LASTEXITCODE -ne 0) { throw "$($ValuationSteps[1]) failed with exit code $LASTEXITCODE." }

  & $Python -B candidate_price_history.py --market US --candidates (Join-Path $OutputRoot "forecast_history.csv") --output $historyPath --cache-dir $historyCache --minimum-coverage 0.80
  if ($LASTEXITCODE -ne 0) { throw "Forecast history price refresh failed with exit code $LASTEXITCODE." }

  $benchmarkPath = Join-Path $OutputRoot "benchmark_history.csv"
  Write-Host "Running: $($ValuationSteps[2])"
  & $Python -B candidate_price_history.py --market US --candidates (Join-Path $ProjectRoot "data\config\market_benchmarks.csv") --output $benchmarkPath --cache-dir (Join-Path $SecCache "benchmark_history") --minimum-coverage 0.80
  if ($LASTEXITCODE -ne 0) { throw "$($ValuationSteps[2]) failed with exit code $LASTEXITCODE." }

  Write-Host "Running: $($ValuationSteps[3])"
  & $Python -B forecast_tracker.py --market US --forecasts (Join-Path $OutputRoot "forecast_history.csv") --stock-history $historyPath --benchmark-history $benchmarkPath --output-root $OutputRoot
  if ($LASTEXITCODE -ne 0) { throw "$($ValuationSteps[3]) failed with exit code $LASTEXITCODE." }

  Write-Host "Running: $($ValuationSteps[4])"
  & $Python -B model_audit.py --evaluations (Join-Path $OutputRoot "forecast_evaluations.csv") --tracking (Join-Path $OutputRoot "tracking_snapshot.csv") --output-root $OutputRoot
  if ($LASTEXITCODE -ne 0) { throw "$($ValuationSteps[4]) failed with exit code $LASTEXITCODE." }

  $runTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  $investmentSummaryPath = Join-Path $OutputRoot "latest_investment_summary.md"
  Write-Host "Running: $($ValuationSteps[5])"
  & $Python -B investment_summary.py `
    --candidates $candidatePath `
    --valuations (Join-Path $OutputRoot "valuation_targets.csv") `
    --tracking (Join-Path $OutputRoot "tracking_snapshot.csv") `
    --evaluations (Join-Path $OutputRoot "forecast_evaluations.csv") `
    --forecast-history (Join-Path $OutputRoot "forecast_history.csv") `
    --model-audit (Join-Path $OutputRoot "model_audit.md") `
    --quote-gaps (Join-Path $OutputRoot "quote_gaps.csv") `
    --data-quality-issues (Join-Path $OutputRoot "data_quality_issues.csv") `
    --share-override-audit (Join-Path $OutputRoot "share_override_audit.csv") `
    --output $investmentSummaryPath
  if ($LASTEXITCODE -ne 0) { throw "$($ValuationSteps[5]) failed with exit code $LASTEXITCODE." }

  $dataHealthHistoryPath = Join-Path $OutputRoot "data_health_history.csv"
  $dataHealthReportPath = Join-Path $OutputRoot "data_health_history.md"
  & $Python -B data_health_history.py `
    --output-root $OutputRoot `
    --history $dataHealthHistoryPath `
    --report $dataHealthReportPath `
    --run-time $runTime
  if ($LASTEXITCODE -ne 0) { throw "Data health history update failed with exit code $LASTEXITCODE." }

  $candidateRows = if (Test-Path $candidatePath) { @(Import-Csv -LiteralPath $candidatePath) } else { @() }
  $tickers = @($candidateRows | ForEach-Object { $_.ticker }) -join ", "
  if (-not $tickers) { $tickers = "None" }
  $universeRows = if (Test-Path $Companies) { @(Import-Csv -LiteralPath $Companies) } else { @() }
  $quoteRows = if (Test-Path $Quotes) { @(Import-Csv -LiteralPath $Quotes) } else { @() }
  $quoteDates = @($quoteRows | ForEach-Object { $_.quote_date } | Where-Object { $_ } | Sort-Object -Unique)
  $quoteDateMin = if ($quoteDates.Count -gt 0) { $quoteDates[0] } else { "none" }
  $quoteDateMax = if ($quoteDates.Count -gt 0) { $quoteDates[-1] } else { "none" }
  $quoteSnapshotSha256 = if (Test-Path $Quotes) { (Get-FileHash -LiteralPath $Quotes -Algorithm SHA256).Hash.ToLowerInvariant() } else { "none" }
  $refreshMetadataPath = Join-Path $Sp500Cache "sp500_refresh_metadata.json"
  $refreshStatus = "unknown"
  if (Test-Path $refreshMetadataPath) {
    $refreshMetadata = Get-Content -Raw -LiteralPath $refreshMetadataPath | ConvertFrom-Json
    $refreshStatus = $refreshMetadata.status
  }
  $secCacheCount = @(Get-ChildItem -Path $SecCache -Filter "CIK*.json" -File -ErrorAction SilentlyContinue).Count

  $summaryPath = Join-Path $OutputRoot "latest_run_summary.md"
  $summary = @(
    "# US Weekly Screening Run Summary",
    "",
    "- Run start time: $runStartedAt",
    "- Run time: $runTime",
    "- Universe count: $($universeRows.Count)",
    "- Constituent refresh status: $refreshStatus",
    "- SEC cache files: $secCacheCount",
    "- Candidate count: $($candidateRows.Count)",
    "- Candidate tickers: $tickers",
    "- Candidate file: $candidatePath",
    "- Quote snapshot policy: runtime_output_only",
    "- Quote snapshot file: $Quotes",
    "- Quote snapshot rows: $($quoteRows.Count)",
    "- Quote date min: $quoteDateMin",
    "- Quote date max: $quoteDateMax",
    "- Quote snapshot sha256: $quoteSnapshotSha256",
    "- Valuation model: valuation_trend_v1",
    "- Valuation targets: $(Join-Path $OutputRoot 'valuation_targets.csv')",
    "- Valuation report: $(Join-Path $OutputRoot 'valuation_report.md')",
    "- Tracking snapshot: $(Join-Path $OutputRoot 'tracking_snapshot.csv')",
    "- Forecast evaluations: $(Join-Path $OutputRoot 'forecast_evaluations.csv')",
    "- Performance report: $(Join-Path $OutputRoot 'performance_report.md')",
    "- Model audit: $(Join-Path $OutputRoot 'model_audit.md')",
    "- Share override audit: $(Join-Path $OutputRoot 'share_override_audit.md')",
    "- Data health history: $dataHealthHistoryPath",
    "- Data health report: $dataHealthReportPath",
    "- Shadow proposals: $(Join-Path $OutputRoot 'shadow_model_proposals.csv')",
    "- Investment summary: $investmentSummaryPath",
    "- Research directory: $(Join-Path $OutputRoot 'research')",
    "- Log: $logPath"
  )
  Set-Content -LiteralPath $summaryPath -Value $summary -Encoding UTF8
  Write-Host "Weekly pipeline completed. Summary: $summaryPath"

  if ($RunPostChecks) {
    & (Get-Command powershell.exe).Source -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot "scripts\\run_weekly_reporting_bundle.ps1") -ProjectRoot $ProjectRoot -MaxAgeDays $PostCheckMaxAgeDays -IgnorePreSubmitFailure
    if ($LASTEXITCODE -ne 0) {
      throw "post-check bundle failed with exit code $LASTEXITCODE."
    }
  }
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
