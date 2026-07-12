param(
  [string]$ProjectRoot = "",
  [string]$AsOfDate = "",
  [string]$Authorizations = "",
  [string]$Output = "",
  [string]$Report = "",
  [string]$CsvOutput = "",
  [string]$History = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"
if (-not $ProjectRoot) { $ProjectRoot = Split-Path -Parent $PSScriptRoot }
if (-not $AsOfDate) { $AsOfDate = Get-Date -Format "yyyy-MM-dd" }
if (-not $Authorizations) { $Authorizations = Join-Path $ProjectRoot "data\manual\human_decision_authorizations.csv" }
if (-not $Output) { $Output = Join-Path $ProjectRoot "outputs\automation\latest_human_decision_inbox.json" }
if (-not $Report) { $Report = Join-Path $ProjectRoot "outputs\automation\latest_human_decision_inbox.md" }
if (-not $CsvOutput) { $CsvOutput = Join-Path $ProjectRoot "outputs\automation\human_decision_inbox.csv" }
if (-not $History) { $History = Join-Path $ProjectRoot "outputs\automation\human_decision_history.csv" }

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "human_decision_inbox.py"
Write-Host "Unified human decision inbox"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "Authorizations: $Authorizations"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "CsvOutput: $CsvOutput"
Write-Host "History: $History"
if ($DryRun) { Write-Host "DryRun: no files were created."; exit 0 }

& $Python -B $Script `
  --project-root $ProjectRoot `
  --candidate-risk-review "outputs/automation/latest_candidate_risk_resolution_review.json" `
  --shadow-disposition "outputs/automation/latest_one_week_forecast_shadow_disposition.json" `
  --authorizations $Authorizations `
  --as-of-date $AsOfDate `
  --output $Output `
  --report $Report `
  --csv-output $CsvOutput `
  --authorization-template $Authorizations `
  --history $History
if ($LASTEXITCODE -ne 0) { throw "Unified human decision inbox failed with exit code $LASTEXITCODE." }
