$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$ReportDate = Get-Date -Format "yyyy-MM-dd"
$WeeklyRaw = Join-Path $ProjectRoot "data\weekly_raw"

Set-Location $ProjectRoot

if ($env:SEC_USER_AGENT -and (Test-Path (Join-Path $ProjectRoot "data\config\sec_us_companies.csv"))) {
  & $Python -B sec_edgar_adapter.py `
    --config data/config/sec_us_companies.csv `
    --output data/raw/sec_us_stocks.csv `
    --user-agent $env:SEC_USER_AGENT

  & $Python -B sec_financial_metrics.py `
    --input data/raw/sec_us_stocks.csv `
    --output data/raw/sec_us_stocks_metrics.csv `
    --user-agent $env:SEC_USER_AGENT
}

$SecMarketInput = Join-Path $ProjectRoot "data\raw\sec_us_stocks_metrics.csv"
if (-not (Test-Path $SecMarketInput)) {
  $SecMarketInput = Join-Path $ProjectRoot "data\raw\sec_us_stocks.csv"
}

if ((Test-Path $SecMarketInput) -and (Test-Path (Join-Path $ProjectRoot "data\config\us_market_quotes.csv"))) {
  & $Python -B us_market_data_enricher.py `
    --input $SecMarketInput `
    --quotes data/config/us_market_quotes.csv `
    --output data/raw/us_stocks_enriched.csv
}

if ((Test-Path (Join-Path $ProjectRoot "data\raw\us_stocks_enriched.csv")) -and (Test-Path (Join-Path $ProjectRoot "data\config\industry_aliases.csv"))) {
  & $Python -B industry_mapper.py `
    --input data/raw/us_stocks_enriched.csv `
    --output data/raw/us_stocks_industry_mapped.csv `
    --aliases data/config/industry_aliases.csv
}

if (Test-Path (Join-Path $ProjectRoot "data\raw\us_stocks_industry_mapped.csv")) {
  & $Python -B industry_medians.py `
    --input data/raw/us_stocks_industry_mapped.csv `
    --output data/raw/us_stocks_with_industry_medians.csv `
    --medians data/derived/industry_medians.csv
}

if (Test-Path $WeeklyRaw) {
  Remove-Item -LiteralPath $WeeklyRaw -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $WeeklyRaw | Out-Null

Get-ChildItem -Path (Join-Path $ProjectRoot "data\raw") -Filter "*.csv" | Where-Object {
  $_.Name -notin @("sec_us_stocks.csv", "sec_us_stocks_metrics.csv", "us_stocks_enriched.csv", "us_stocks_industry_mapped.csv")
} | ForEach-Object {
  Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $WeeklyRaw $_.Name)
}

Get-ChildItem -Path $WeeklyRaw -Filter "*.csv" | ForEach-Object {
  $baseName = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
  & $Python -B data_quality_checks.py `
    --input $_.FullName `
    --issues (Join-Path $ProjectRoot "outputs\data_quality_${baseName}_issues.csv") `
    --report (Join-Path $ProjectRoot "outputs\data_quality_${baseName}_report.md")
}

& $Python -B stock_screener.py `
  --raw-dir data/weekly_raw `
  --output-dir outputs `
  --candidate-min-score 80 `
  --weekly-report `
  --report-date $ReportDate
