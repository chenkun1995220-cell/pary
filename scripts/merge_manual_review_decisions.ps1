param(
  [string]$ProjectRoot = "",
  [string]$Template = "",
  [string]$Decisions = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

if (-not $ProjectRoot) {
  $ProjectRoot = $RepoRoot
}
if (-not $Template) {
  $Template = Join-Path $ProjectRoot "outputs\automation\manual_review_decisions_template.csv"
}
if (-not $Decisions) {
  $Decisions = Join-Path $ProjectRoot "outputs\automation\manual_review_decisions.csv"
}

# Manual equivalent:
# powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\merge_manual_review_decisions.ps1
$Python = "C:\Users\pechen\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Script = Join-Path $RepoRoot "manual_review_decisions.py"
$Args = @("-B", $Script, "--template", $Template, "--decisions", $Decisions)

& $Python @Args
if ($LASTEXITCODE -ne 0) {
  throw "Manual review decision merge failed with exit code $LASTEXITCODE."
}
