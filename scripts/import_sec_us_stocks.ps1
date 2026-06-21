$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Config = Join-Path $ProjectRoot "data\config\sec_us_companies.csv"
$Output = Join-Path $ProjectRoot "data\raw\sec_us_stocks.csv"

if (-not $env:SEC_USER_AGENT) {
  throw "请先设置 SEC_USER_AGENT，例如：`$env:SEC_USER_AGENT='your-name your-email@example.com'"
}

Set-Location $ProjectRoot

& $Python -B sec_edgar_adapter.py `
  --config $Config `
  --output $Output `
  --user-agent $env:SEC_USER_AGENT

