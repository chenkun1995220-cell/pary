param(
  [string]$Symbols = "",
  [string]$Output = "",
  [string]$Sp500Cache = "",
  [switch]$SkipConstituentRefresh
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (-not $Symbols) {
  $Symbols = Join-Path $ProjectRoot "data\config\us_universe_symbols.csv"
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "data\samples\us_universe_companies.csv"
}
if (-not $Sp500Cache) {
  $Sp500Cache = Join-Path $ProjectRoot "data\cache\sp500"
}
if (-not $env:SEC_USER_AGENT) {
  throw "Please set SEC_USER_AGENT before downloading the SEC ticker list."
}

Set-Location $ProjectRoot

if (-not $SkipConstituentRefresh) {
  & $Python -B sp500_constituents.py `
    --output $Symbols `
    --cache-dir $Sp500Cache `
    --user-agent $env:SEC_USER_AGENT
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

& $Python -B us_universe_builder.py `
  --symbols $Symbols `
  --output $Output `
  --user-agent $env:SEC_USER_AGENT `
  --minimum-match-rate 0.98
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
