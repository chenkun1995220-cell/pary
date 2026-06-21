param(
  [Parameter(Mandatory=$true)]
  [string]$InputPath,

  [string]$Output = "data\samples\us_real_sample_quotes_imported.csv"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Aliases = Join-Path $ProjectRoot "data\config\quote_field_aliases.csv"

if (-not (Test-Path $InputPath)) {
  throw "Missing input quote CSV: $InputPath"
}

if (-not (Test-Path $Aliases)) {
  throw "Missing quote field aliases: $Aliases"
}

Set-Location $ProjectRoot

& $Python -B quote_importer.py `
  --input $InputPath `
  --output $Output `
  --aliases $Aliases
