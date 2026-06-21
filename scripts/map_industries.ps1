$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Input = Join-Path $ProjectRoot "data\raw\us_stocks_enriched.csv"
$Output = Join-Path $ProjectRoot "data\raw\us_stocks_industry_mapped.csv"
$Aliases = Join-Path $ProjectRoot "data\config\industry_aliases.csv"

if (-not (Test-Path $Input)) {
  throw "缺少输入文件：$Input"
}

if (-not (Test-Path $Aliases)) {
  throw "缺少行业别名表：$Aliases"
}

Set-Location $ProjectRoot

& $Python -B industry_mapper.py `
  --input $Input `
  --output $Output `
  --aliases $Aliases

