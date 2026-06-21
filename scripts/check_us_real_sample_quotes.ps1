param(
  [string]$Quotes = "",
  [string]$OutputCsv = "",
  [string]$OutputReport = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (-not $Quotes) {
  $Quotes = Join-Path $ProjectRoot "data\samples\us_real_sample_quotes.csv"
}
if (-not $OutputCsv) {
  $OutputCsv = Join-Path $ProjectRoot "outputs\us_real_sample_quote_gaps.csv"
}
if (-not $OutputReport) {
  $OutputReport = Join-Path $ProjectRoot "outputs\us_real_sample_quote_gaps.md"
}

Set-Location $ProjectRoot

& $Python -B quote_fill_assistant.py `
  --quotes $Quotes `
  --output-csv $OutputCsv `
  --output-report $OutputReport
