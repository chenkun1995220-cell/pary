param(
  [Parameter(Mandatory=$true)]
  [string]$InputPath,

  [string]$Output = "data\raw\imported_mapped.csv"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Aliases = Join-Path $ProjectRoot "data\config\field_aliases.csv"

if (-not (Test-Path $InputPath)) {
  throw "缺少输入文件：$InputPath"
}

if (-not (Test-Path $Aliases)) {
  throw "缺少字段别名表：$Aliases"
}

Set-Location $ProjectRoot

& $Python -B field_mapper.py `
  --input $InputPath `
  --output $Output `
  --aliases $Aliases
