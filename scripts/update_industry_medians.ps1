$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Input = Join-Path $ProjectRoot "data\raw\us_stocks_enriched.csv"
$Output = Join-Path $ProjectRoot "data\raw\us_stocks_with_industry_medians.csv"
$Medians = Join-Path $ProjectRoot "data\derived\industry_medians.csv"

if (-not (Test-Path $Input)) {
  throw "缺少输入文件：$Input"
}

Set-Location $ProjectRoot

& $Python -B industry_medians.py `
  --input $Input `
  --output $Output `
  --medians $Medians

