function Invoke-WeeklyTransientStep {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Label,
    [Parameter(Mandatory = $true)]
    [scriptblock]$Command,
    [int]$RetryDelaySeconds = 5
  )

  for ($attempt = 1; $attempt -le 2; $attempt += 1) {
    & $Command
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) {
      return
    }
    if ($exitCode -ne 120 -or $attempt -eq 2) {
      throw "$Label failed with exit code $exitCode."
    }

    Write-Warning "$Label failed with exit code 120; retrying once."
    if ($RetryDelaySeconds -gt 0) {
      Start-Sleep -Seconds $RetryDelaySeconds
    }
  }
}
