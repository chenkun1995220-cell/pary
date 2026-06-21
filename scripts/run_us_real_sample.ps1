param(
  [string]$Companies = "",
  [string]$FixtureDir = "",
  [string]$OutputRoot = "",
  [string]$Quotes = "",
  [string]$CacheDir = "",
  [double]$MinimumQuoteCoverage = 0.95,
  [switch]$AllowIncompleteQuotes
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$ReportDate = Get-Date -Format "yyyy-MM-dd"
if (-not $Companies) {
  $Companies = Join-Path $ProjectRoot "data\samples\us_real_sample_companies.csv"
}
if (-not $Quotes) {
  $Quotes = Join-Path $ProjectRoot "data\samples\us_real_sample_quotes.csv"
}
if (-not $OutputRoot) {
  $OutputRoot = Join-Path $ProjectRoot "outputs\us_real_sample"
}
if (-not $CacheDir) {
  $CacheDir = Join-Path $ProjectRoot "data\cache\sec_companyfacts"
}
$RawForScreening = Join-Path $OutputRoot "raw_for_screening"

if (-not (Test-Path $Companies)) {
  throw "Missing sample companies file: $Companies"
}

if (-not (Test-Path $Quotes)) {
  throw "Missing sample quotes file: $Quotes"
}

if (-not $FixtureDir -and -not $env:SEC_USER_AGENT) {
  throw "Please set SEC_USER_AGENT, or pass -FixtureDir for local SEC Company Facts JSON files."
}

Set-Location $ProjectRoot
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

$QuoteGapsCsv = Join-Path $OutputRoot "quote_gaps.csv"
$QuoteGapsReport = Join-Path $OutputRoot "quote_gaps.md"

& $Python -B real_sample_pack.py `
  --companies $Companies `
  --quotes $Quotes
if ($LASTEXITCODE -ne 0) { throw "Real sample pack validation failed with exit code $LASTEXITCODE." }

& $Python -B quote_fill_assistant.py `
  --quotes $Quotes `
  --output-csv $QuoteGapsCsv `
  --output-report $QuoteGapsReport

$QuoteGapRows = Import-Csv -LiteralPath $QuoteGapsCsv
$NeedsFillRows = @($QuoteGapRows | Where-Object { $_.status -ne "ready" })
$ReadyQuoteRows = @($QuoteGapRows | Where-Object { $_.status -eq "ready" })
$QuoteCoverage = if ($QuoteGapRows.Count -gt 0) { $ReadyQuoteRows.Count / $QuoteGapRows.Count } else { 0 }
Write-Host ("QuoteCoverage: {0:P2}" -f $QuoteCoverage)
if ($QuoteCoverage -lt $MinimumQuoteCoverage -and -not $AllowIncompleteQuotes) {
  throw "Quote coverage $QuoteCoverage is below required $MinimumQuoteCoverage. Report: $QuoteGapsReport"
}

$SecOutput = Join-Path $OutputRoot "sec_us_stocks.csv"
$MetricsOutput = Join-Path $OutputRoot "sec_us_stocks_metrics.csv"
$EnrichedOutput = Join-Path $OutputRoot "us_stocks_enriched.csv"
$MappedOutput = Join-Path $OutputRoot "us_stocks_industry_mapped.csv"
$MedianOutput = Join-Path $OutputRoot "us_stocks_with_industry_medians.csv"
$Medians = Join-Path $OutputRoot "industry_medians.csv"
$Issues = Join-Path $OutputRoot "data_quality_issues.csv"
$QualityReport = Join-Path $OutputRoot "data_quality_report.md"

if ($FixtureDir) {
  & $Python -B sec_edgar_adapter.py `
    --config $Companies `
    --output $SecOutput `
    --fixture-dir $FixtureDir

  & $Python -B sec_financial_metrics.py `
    --input $SecOutput `
    --output $MetricsOutput `
    --fixture-dir $FixtureDir
} else {
  & $Python -B sec_edgar_adapter.py `
    --config $Companies `
    --output $SecOutput `
    --user-agent $env:SEC_USER_AGENT `
    --cache-dir $CacheDir

  & $Python -B sec_financial_metrics.py `
    --input $SecOutput `
    --output $MetricsOutput `
    --user-agent $env:SEC_USER_AGENT `
    --cache-dir $CacheDir
}

& $Python -B us_market_data_enricher.py `
  --input $MetricsOutput `
  --quotes $Quotes `
  --output $EnrichedOutput

& $Python -B industry_mapper.py `
  --input $EnrichedOutput `
  --output $MappedOutput `
  --aliases data/config/industry_aliases.csv

& $Python -B industry_medians.py `
  --input $MappedOutput `
  --output $MedianOutput `
  --medians $Medians

& $Python -B data_quality_checks.py `
  --input $MedianOutput `
  --issues $Issues `
  --report $QualityReport

if (Test-Path $RawForScreening) {
  Remove-Item -LiteralPath $RawForScreening -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $RawForScreening | Out-Null
Copy-Item -LiteralPath $MedianOutput -Destination (Join-Path $RawForScreening "us_real_sample.csv")

& $Python -B stock_screener.py `
  --raw-dir $RawForScreening `
  --output-dir $OutputRoot `
  --candidate-min-score 80 `
  --weekly-report `
  --report-date $ReportDate
