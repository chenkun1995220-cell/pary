param(
  [string]$TaskName = "StockUndervaluationWeekly",
  [ValidateSet("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")]
  [string]$DayOfWeek = "Saturday",
  [string]$At = "09:00",
  [string]$SecUserAgent = $env:SEC_USER_AGENT,
  [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

if (-not $SecUserAgent) {
  throw "SEC_USER_AGENT is required. Pass -SecUserAgent or set the environment variable."
}

$scheduledTime = [datetime]::MinValue
if (-not [datetime]::TryParseExact($At, "HH:mm", $null, [Globalization.DateTimeStyles]::None, [ref]$scheduledTime)) {
  throw "Invalid -At value '$At'. Use HH:mm, for example 09:00."
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Orchestrator = Join-Path $PSScriptRoot "run_us_universe_weekly.ps1"
$escapedUserAgent = $SecUserAgent.Replace('"', '\"')
$arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$Orchestrator`" -SecUserAgent `"$escapedUserAgent`""

Write-Host "TaskName: $TaskName"
Write-Host "Schedule: $DayOfWeek $At"
Write-Host "Orchestrator: $Orchestrator"

if ($WhatIf) {
  Write-Host "WhatIf: scheduled task was not registered."
  exit 0
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments -WorkingDirectory $ProjectRoot
$trigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek $DayOfWeek -At $scheduledTime
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $action `
  -Trigger $trigger `
  -Settings $settings `
  -Principal $principal `
  -Description "Weekly US stock data refresh, undervaluation screening, and research packs." `
  -Force | Out-Null

Write-Host "Scheduled task registered: $TaskName"
