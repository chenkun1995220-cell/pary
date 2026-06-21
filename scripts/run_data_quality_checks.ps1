param(
  [Parameter(Mandatory=$true)]
  [string]$InputPath,

  [string]$IssuesPath = "outputs\data_quality_issues.csv",

  [string]$ReportPath = "outputs\data_quality_report.md"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (-not (Test-Path $InputPath)) {
  throw "缺少输入文件：$InputPath"
}

Set-Location $ProjectRoot

& $Python -B data_quality_checks.py `
  --input $InputPath `
  --issues $IssuesPath `
  --report $ReportPath
