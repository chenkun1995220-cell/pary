param(
  [string]$Companies = "",
  [string]$CacheDir = "",
  [string]$OutputRoot = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (-not $Companies) { $Companies = Join-Path $ProjectRoot "data\samples\cn_universe_companies.csv" }
if (-not $CacheDir) { $CacheDir = Join-Path $ProjectRoot "data\cache\csi300" }
if (-not $OutputRoot) { $OutputRoot = Join-Path $ProjectRoot "outputs\cn_universe" }

Write-Host "Market: CN"
Write-Host "Companies: $Companies"
Write-Host "Cache: $CacheDir"
Write-Host "OutputRoot: $OutputRoot"
Write-Host "Steps: universe -> market snapshot -> financial snapshot -> regional screening -> price history -> valuation_trend_v1 -> benchmark -> forecast tracking -> model audit"

if ($DryRun) {
  Write-Host "DryRun: no files or network requests were created."
  exit 0
}

$mutex = [System.Threading.Mutex]::new($false, "Local\StockUndervaluationCNWeekly")
$hasLock = $false
$transcriptStarted = $false
try {
  $hasLock = $mutex.WaitOne(0)
  if (-not $hasLock) { throw "Another CN weekly run is already in progress." }
  New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
  $logPath = Join-Path $OutputRoot ("run_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log")
  Start-Transcript -Path $logPath | Out-Null
  $transcriptStarted = $true

  Set-Location $ProjectRoot
  & $Python -B regional_universe.py --market CN --output $Companies --cache-dir $CacheDir
  if ($LASTEXITCODE -ne 0) { throw "CN universe refresh failed with exit code $LASTEXITCODE." }

  $snapshotPath = Join-Path $OutputRoot "market_snapshot.csv"
  $rawSnapshotPath = Join-Path $CacheDir "market_snapshot_raw.json"
  & $Python -B regional_market_snapshot.py `
    --companies $Companies `
    --output $snapshotPath `
    --raw-cache $rawSnapshotPath `
    --minimum-coverage 0.95
  if ($LASTEXITCODE -ne 0) { throw "CN market snapshot failed with exit code $LASTEXITCODE." }

  $financialPath = Join-Path $OutputRoot "financial_snapshot.csv"
  $rawFinancialPath = Join-Path $CacheDir "financial_snapshot_raw.json"
  & $Python -B regional_financials.py `
    --market CN `
    --snapshot $snapshotPath `
    --output $financialPath `
    --raw-cache $rawFinancialPath `
    --minimum-coverage 0.80
  if ($LASTEXITCODE -ne 0) { throw "CN financial snapshot failed with exit code $LASTEXITCODE." }

  & $Python -B regional_value_screener.py `
    --input $financialPath `
    --output-root $OutputRoot `
    --candidate-min-score 75
  if ($LASTEXITCODE -ne 0) { throw "CN regional screening failed with exit code $LASTEXITCODE." }

  $candidatesPath = Join-Path $OutputRoot "candidate_pool.csv"
  $historyPath = Join-Path $OutputRoot "price_history.csv"
  $historyCache = Join-Path $CacheDir "candidate_price_history"
  & $Python -B candidate_price_history.py `
    --market CN `
    --candidates $candidatesPath `
    --output $historyPath `
    --cache-dir $historyCache `
    --minimum-coverage 0.80
  if ($LASTEXITCODE -ne 0) { throw "CN candidate price history failed with exit code $LASTEXITCODE." }

  & $Python -B candidate_valuation.py `
    --market CN `
    --candidates $candidatesPath `
    --price-history $historyPath `
    --industry-medians (Join-Path $OutputRoot "industry_medians.csv") `
    --output-root $OutputRoot
  if ($LASTEXITCODE -ne 0) { throw "CN candidate valuation failed with exit code $LASTEXITCODE." }

  & $Python -B candidate_price_history.py `
    --market CN `
    --candidates (Join-Path $OutputRoot "forecast_history.csv") `
    --output $historyPath `
    --cache-dir $historyCache `
    --minimum-coverage 0.80
  if ($LASTEXITCODE -ne 0) { throw "CN forecast history price refresh failed with exit code $LASTEXITCODE." }

  $benchmarkPath = Join-Path $OutputRoot "benchmark_history.csv"
  & $Python -B candidate_price_history.py `
    --market CN `
    --candidates (Join-Path $ProjectRoot "data\config\market_benchmarks.csv") `
    --output $benchmarkPath `
    --cache-dir (Join-Path $CacheDir "benchmark_history") `
    --minimum-coverage 0.80
  if ($LASTEXITCODE -ne 0) { throw "CN benchmark history failed with exit code $LASTEXITCODE." }

  & $Python -B forecast_tracker.py --market CN --forecasts (Join-Path $OutputRoot "forecast_history.csv") --stock-history $historyPath --benchmark-history $benchmarkPath --output-root $OutputRoot
  if ($LASTEXITCODE -ne 0) { throw "CN forecast tracking failed with exit code $LASTEXITCODE." }

  & $Python -B model_audit.py --evaluations (Join-Path $OutputRoot "forecast_evaluations.csv") --tracking (Join-Path $OutputRoot "tracking_snapshot.csv") --output-root $OutputRoot
  if ($LASTEXITCODE -ne 0) { throw "CN model audit failed with exit code $LASTEXITCODE." }

  $investmentSummaryPath = Join-Path $OutputRoot "latest_investment_summary.md"
  & $Python -B investment_summary.py `
    --candidates $candidatesPath `
    --valuations (Join-Path $OutputRoot "valuation_targets.csv") `
    --tracking (Join-Path $OutputRoot "tracking_snapshot.csv") `
    --forecast-history (Join-Path $OutputRoot "forecast_history.csv") `
    --model-audit (Join-Path $OutputRoot "model_audit.md") `
    --output $investmentSummaryPath
  if ($LASTEXITCODE -ne 0) { throw "CN investment summary failed with exit code $LASTEXITCODE." }

  $rows = @(Import-Csv -LiteralPath $Companies)
  $financialRows = @(Import-Csv -LiteralPath $financialPath)
  $financialReady = @($financialRows | Where-Object { $_.financial_data_status -eq "ready" }).Count
  $financialCoverage = if ($financialRows.Count -gt 0) { "{0:P2}" -f ($financialReady / $financialRows.Count) } else { "0.00%" }
  $candidates = @(Import-Csv -LiteralPath $candidatesPath)
  $candidateTickers = @($candidates | ForEach-Object { $_.ticker }) -join ", "
  if (-not $candidateTickers) { $candidateTickers = "None" }
  $metadata = Get-Content -Raw -LiteralPath (Join-Path $CacheDir "refresh_metadata.json") | ConvertFrom-Json
  $summary = @(
    "# CN Weekly Data Summary",
    "",
    "- Run time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "- Universe: CSI 300",
    "- Company count: $($rows.Count)",
    "- Refresh status: $($metadata.status)",
    "- Financial coverage: $financialCoverage",
    "- Screening model: regional_fundamental_v2",
    "- Valuation model: valuation_trend_v1",
    "- Candidate count: $($candidates.Count)",
    "- Candidate tickers: $candidateTickers",
    "- Company file: $Companies",
    "- Candidate file: $candidatesPath",
    "- Valuation targets: $(Join-Path $OutputRoot 'valuation_targets.csv')",
    "- Valuation report: $(Join-Path $OutputRoot 'valuation_report.md')",
    "- Tracking snapshot: $(Join-Path $OutputRoot 'tracking_snapshot.csv')",
    "- Forecast evaluations: $(Join-Path $OutputRoot 'forecast_evaluations.csv')",
    "- Performance report: $(Join-Path $OutputRoot 'performance_report.md')",
    "- Model audit: $(Join-Path $OutputRoot 'model_audit.md')",
    "- Shadow proposals: $(Join-Path $OutputRoot 'shadow_model_proposals.csv')",
    "- Investment summary: $investmentSummaryPath",
    "- Report: $(Join-Path $OutputRoot 'weekly_report.md')",
    "- Log: $logPath"
  )
  Set-Content -LiteralPath (Join-Path $OutputRoot "latest_run_summary.md") -Value $summary -Encoding UTF8
}
finally {
  if ($transcriptStarted) { Stop-Transcript | Out-Null }
  if ($hasLock) { $mutex.ReleaseMutex() }
  $mutex.Dispose()
}
