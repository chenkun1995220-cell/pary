param(
  [string]$ScreeningRoot = "",
  [string]$Companies = "",
  [string]$OutputDir = "",
  [string]$FixtureDir = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (-not $ScreeningRoot) {
  $ScreeningRoot = Join-Path $ProjectRoot "outputs\us_universe"
}
if (-not $Companies) {
  $Companies = Join-Path $ProjectRoot "data\samples\us_universe_companies.csv"
}
if (-not $OutputDir) {
  $OutputDir = Join-Path $ScreeningRoot "research"
}
if (-not $FixtureDir -and -not $env:SEC_USER_AGENT) {
  throw "Please set SEC_USER_AGENT, or pass -FixtureDir for local SEC submissions JSON files."
}

$Candidates = Join-Path $ScreeningRoot "candidate_pool.csv"
$Metrics = Join-Path $ScreeningRoot "us_stocks_with_industry_medians.csv"
$Issues = Join-Path $ScreeningRoot "data_quality_issues.csv"

foreach ($path in @($Candidates, $Metrics, $Issues, $Companies)) {
  if (-not (Test-Path $path)) {
    throw "Missing research input: $path"
  }
}

Set-Location $ProjectRoot

$argsList = @(
  "-B",
  "candidate_research_pack.py",
  "--candidates", $Candidates,
  "--metrics", $Metrics,
  "--issues", $Issues,
  "--companies", $Companies,
  "--output-dir", $OutputDir
)

if ($FixtureDir) {
  $argsList += @("--fixture-dir", $FixtureDir)
} else {
  $argsList += @("--user-agent", $env:SEC_USER_AGENT)
}

& $Python @argsList
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
