param(
  [string]$ProjectRoot = "",
  [string]$AsOfDate = "",
  [int]$ManualLimit = 5,
  [string]$Output = "",
  [string]$Report = "",
  [string]$CsvOutput = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"
if (-not $ProjectRoot) { $ProjectRoot = Split-Path -Parent $PSScriptRoot }
if (-not $AsOfDate) { $AsOfDate = Get-Date -Format "yyyy-MM-dd" }
if (-not $Output) { $Output = Join-Path $ProjectRoot "outputs\automation\latest_candidate_risk_resolution_review.json" }
if (-not $Report) { $Report = Join-Path $ProjectRoot "outputs\automation\latest_candidate_risk_resolution_review.md" }
if (-not $CsvOutput) { $CsvOutput = Join-Path $ProjectRoot "outputs\automation\candidate_risk_resolution_review.csv" }

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "candidate_risk_resolution_review.py"
Write-Host "Candidate risk resolution review"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "ManualLimit: $ManualLimit"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "CsvOutput: $CsvOutput"
Write-Host "Reads: latest_candidate_risk_priority_review.json and three valuation_targets.csv files"
Write-Host "Writes: latest_candidate_risk_resolution_review.json, .md and candidate_risk_resolution_review.csv"
if ($DryRun) { Write-Host "DryRun: no files were created."; exit 0 }

& $Python -B $Script `
  --project-root $ProjectRoot `
  --candidate-risk-priority-review (Join-Path $ProjectRoot "outputs\automation\latest_candidate_risk_priority_review.json") `
  --as-of-date $AsOfDate `
  --manual-limit $ManualLimit `
  --output $Output `
  --report $Report `
  --csv-output $CsvOutput
if ($LASTEXITCODE -ne 0) { throw "Candidate risk resolution review failed with exit code $LASTEXITCODE." }
