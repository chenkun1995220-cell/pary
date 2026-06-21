param(
  [string]$Output = "",
  [string]$CacheDir = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (-not $Output) {
  $Output = Join-Path $ProjectRoot "data\config\us_universe_symbols.csv"
}
if (-not $CacheDir) {
  $CacheDir = Join-Path $ProjectRoot "data\cache\sp500"
}

Set-Location $ProjectRoot
& $Python -B sp500_constituents.py `
  --output $Output `
  --cache-dir $CacheDir `
  --user-agent $env:SEC_USER_AGENT
exit $LASTEXITCODE
