$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Input = Join-Path $ProjectRoot "data\raw\sec_us_stocks.csv"
$Quotes = Join-Path $ProjectRoot "data\config\us_market_quotes.csv"
$Output = Join-Path $ProjectRoot "data\raw\us_stocks_enriched.csv"

if (-not (Test-Path $Input)) {
  throw "缺少 SEC 标准化输入：$Input"
}

if (-not (Test-Path $Quotes)) {
  throw "缺少美股行情/股本配置：$Quotes"
}

Set-Location $ProjectRoot

& $Python -B us_market_data_enricher.py `
  --input $Input `
  --quotes $Quotes `
  --output $Output

