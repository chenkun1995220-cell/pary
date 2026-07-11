param(
  [string]$Companies = "",
  [string]$Output = "",
  [string]$FixtureDir = "",
  [string]$PriceFixtureDir = "",
  [string]$CacheDir = "",
  [string]$ShareOverrides = "",
  [switch]$NoQuoteCache
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (-not $Companies) {
  $Companies = Join-Path $ProjectRoot "data\samples\us_real_sample_companies.csv"
}

if (-not $Output) {
  $Output = Join-Path $ProjectRoot "data\samples\us_real_sample_quotes.csv"
}

if (-not (Test-Path $Companies)) {
  throw "Missing sample companies file: $Companies"
}

if (-not $FixtureDir -and -not $env:SEC_USER_AGENT) {
  throw "Please set SEC_USER_AGENT, or pass -FixtureDir for local SEC Company Facts JSON files."
}

Set-Location $ProjectRoot

$argsList = @(
  "-B",
  "quote_auto_filler.py",
  "--companies",
  $Companies,
  "--output",
  $Output
)

if ($FixtureDir) {
  $argsList += @("--fixture-dir", $FixtureDir)
} else {
  $argsList += @("--user-agent", $env:SEC_USER_AGENT)
}

if ($PriceFixtureDir) {
  $argsList += @("--price-fixture-dir", $PriceFixtureDir)
}
if ($CacheDir) {
  $argsList += @("--cache-dir", $CacheDir)
}
if ($ShareOverrides) {
  $argsList += @("--share-overrides", $ShareOverrides)
}
if ($NoQuoteCache) {
  $argsList += "--no-quote-cache"
}

& $Python @argsList
exit $LASTEXITCODE
