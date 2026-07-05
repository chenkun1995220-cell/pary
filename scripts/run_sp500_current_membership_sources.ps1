param(
  [string]$ProjectRoot = "",
  [string]$Template = "",
  [string]$SourceUrl = "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
  [string]$SourceHtml = "",
  [string]$SourceFile = "",
  [string]$SecondaryConstituentsCsv = "",
  [string]$Output = "",
  [string]$Report = "",
  [string]$JsonOutput = "",
  [string]$IntakeTemplate = "",
  [string]$ReviewQueueOutput = "",
  [string]$SourceFileRequest = "",
  [string]$SourceFileInbox = "",
  [string]$UserAgent = $env:SEC_USER_AGENT,
  [string]$AsOfDate = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

if (-not $ProjectRoot) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $Template) {
  $Template = Join-Path $ProjectRoot "outputs\automation\us_sp500_current_membership_sources_template.csv"
}
if (-not $Output) {
  $Output = Join-Path $ProjectRoot "data\config\us_sp500_current_membership_sources.csv"
}
if (-not $Report) {
  $Report = Join-Path $ProjectRoot "outputs\automation\latest_sp500_current_membership_sources.md"
}
if (-not $JsonOutput) {
  $JsonOutput = Join-Path $ProjectRoot "outputs\automation\latest_sp500_current_membership_sources.json"
}
if (-not $IntakeTemplate) {
  $IntakeTemplate = Join-Path $ProjectRoot "outputs\automation\sp500_current_membership_source_intake_template.csv"
}
if (-not $ReviewQueueOutput) {
  $ReviewQueueOutput = Join-Path $ProjectRoot "outputs\automation\sp500_current_membership_source_review_queue.csv"
}
if (-not $SourceFileRequest) {
  $SourceFileRequest = Join-Path $ProjectRoot "outputs\automation\sp500_current_membership_source_file_request.md"
}
if (-not $SourceFileInbox) {
  $SourceFileInbox = Join-Path $ProjectRoot "inputs\sp500_current_membership\official_constituents.csv"
}
if ((-not $SourceFile) -and (Test-Path -LiteralPath $SourceFileInbox)) {
  $SourceFile = $SourceFileInbox
}
if ((-not $SourceFile) -and (-not $SourceHtml) -and (-not $SecondaryConstituentsCsv)) {
  $DefaultSecondaryConstituentsCsv = Join-Path $ProjectRoot "data\config\us_universe_symbols.csv"
  if (Test-Path -LiteralPath $DefaultSecondaryConstituentsCsv) {
    $SecondaryConstituentsCsv = $DefaultSecondaryConstituentsCsv
  }
}
if (-not $AsOfDate) {
  $AsOfDate = Get-Date -Format "yyyy-MM-dd"
}

$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $ProjectRoot "sp500_current_membership_sources.py"

Write-Host "S&P 500 current membership sources"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "Template: $Template"
Write-Host "SourceUrl: $SourceUrl"
Write-Host "SourceHtml: $SourceHtml"
Write-Host "SourceFile: $SourceFile"
Write-Host "SecondaryConstituentsCsv: $SecondaryConstituentsCsv"
Write-Host "Output: $Output"
Write-Host "Report: $Report"
Write-Host "JsonOutput: $JsonOutput"
Write-Host "IntakeTemplate: $IntakeTemplate"
Write-Host "ReviewQueueOutput: $ReviewQueueOutput"
Write-Host "SourceFileRequest: $SourceFileRequest"
Write-Host "SourceFileInbox: $SourceFileInbox"
Write-Host "UserAgent: $UserAgent"
Write-Host "AsOfDate: $AsOfDate"
Write-Host "Reads: us_sp500_current_membership_sources_template.csv, official S&P Global source, secondary public constituents fallback"
Write-Host "Writes: us_sp500_current_membership_sources.csv, latest_sp500_current_membership_sources.md, latest_sp500_current_membership_sources.json, sp500_current_membership_source_intake_template.csv, sp500_current_membership_source_review_queue.csv, sp500_current_membership_source_file_request.md"

if ($DryRun) {
  if ($SourceFile) {
    $dryRunArgs = @(
      "-B", $Script,
      "--template", $Template,
      "--source-url", $SourceUrl,
      "--as-of-date", $AsOfDate,
      "--source-file", $SourceFile,
      "--intake-template", $IntakeTemplate,
      "--source-file-inbox", $SourceFileInbox,
      "--validate-source-file-only"
    )
    if ($UserAgent) {
      $dryRunArgs += @("--user-agent", $UserAgent)
    }
    & $Python @dryRunArgs
    if ($LASTEXITCODE -ne 0) {
      throw "S&P 500 current membership source dry-run validation failed with exit code $LASTEXITCODE."
    }
  } elseif ($SecondaryConstituentsCsv) {
    $dryRunRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("sp500-secondary-dryrun-" + [System.Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $dryRunRoot | Out-Null
    try {
      $dryRunArgs = @(
        "-B", $Script,
        "--template", $Template,
        "--source-url", $SourceUrl,
        "--as-of-date", $AsOfDate,
        "--secondary-constituents-csv", $SecondaryConstituentsCsv,
        "--output", (Join-Path $dryRunRoot "sources.csv"),
        "--report", (Join-Path $dryRunRoot "sources.md"),
        "--json-output", (Join-Path $dryRunRoot "sources.json"),
        "--intake-template", (Join-Path $dryRunRoot "intake.csv"),
        "--source-file-request", (Join-Path $dryRunRoot "source_file_request.md"),
        "--source-file-inbox", $SourceFileInbox
      )
      if ($UserAgent) {
        $dryRunArgs += @("--user-agent", $UserAgent)
      }
      & $Python @dryRunArgs
      if ($LASTEXITCODE -ne 0) {
        throw "S&P 500 secondary current membership source dry-run validation failed with exit code $LASTEXITCODE."
      }
    } finally {
      Remove-Item -LiteralPath $dryRunRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
  }
  Write-Host "DryRun: no files or network requests were created."
  exit 0
}

$args = @(
  "-B", $Script,
  "--template", $Template,
  "--source-url", $SourceUrl,
  "--as-of-date", $AsOfDate,
  "--output", $Output,
  "--report", $Report,
  "--json-output", $JsonOutput,
  "--intake-template", $IntakeTemplate,
  "--review-queue-output", $ReviewQueueOutput,
  "--source-file-request", $SourceFileRequest,
  "--source-file-inbox", $SourceFileInbox,
  "--allow-empty-on-fetch-error"
)
if ($UserAgent) {
  $args += @("--user-agent", $UserAgent)
}
if ($SourceHtml) {
  $args += @("--source-html", $SourceHtml)
}
if ($SourceFile) {
  $args += @("--source-file", $SourceFile)
}
if ($SecondaryConstituentsCsv) {
  $args += @("--secondary-constituents-csv", $SecondaryConstituentsCsv)
}

& $Python @args
if ($LASTEXITCODE -ne 0) {
  throw "S&P 500 current membership source build failed with exit code $LASTEXITCODE."
}
