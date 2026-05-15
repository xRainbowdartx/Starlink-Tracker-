# Registers a Windows Scheduled Task that runs `spacetrack update` every 6 hours.
#
# This keeps the local SQLite catalog refreshed with the latest Starlink TLEs
# from CelesTrak. Logs are written to logs/scheduled_update.log inside the
# project directory.
#
# Usage:
#   .\scripts\register_scheduled_update.ps1                 # install / update
#   .\scripts\register_scheduled_update.ps1 -Uninstall      # remove the task
#
# The task runs under your user account (no admin required) and only fires
# when the user is logged on. To run when logged off, register via
# Task Scheduler GUI and check "Run whether user is logged on or not."

[CmdletBinding()]
param(
    [switch]$Uninstall
)

$TaskName = "SpacetrackUpdate"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $ProjectRoot "logs"
$LogFile = Join-Path $LogDir "scheduled_update.log"

if ($Uninstall) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Removed scheduled task '$TaskName'."
    } else {
        Write-Host "No scheduled task named '$TaskName' is registered."
    }
    return
}

if (-not (Test-Path $PythonExe)) {
    Write-Error "Could not find venv at $PythonExe. Did you run 'python -m venv .venv' and install the package?"
    exit 1
}

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "-m spacetrack.cli update" `
    -WorkingDirectory $ProjectRoot

# Daily trigger that repeats every 6 hours forever, starting at next 00:00.
$TomorrowMidnight = (Get-Date).Date.AddDays(1)
$Trigger = New-ScheduledTaskTrigger -Daily -At $TomorrowMidnight
$Trigger.Repetition = (New-ScheduledTaskTrigger `
    -Once -At $TomorrowMidnight `
    -RepetitionInterval (New-TimeSpan -Hours 6)).Repetition

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

$Task = New-ScheduledTask `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Refreshes Starlink TLE catalog via spacetrack update."

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Set-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal | Out-Null
    Write-Host "Updated existing scheduled task '$TaskName'."
} else {
    Register-ScheduledTask -TaskName $TaskName -InputObject $Task | Out-Null
    Write-Host "Registered scheduled task '$TaskName'."
}

Write-Host ""
Write-Host "Schedule: every 6 hours, starting $TomorrowMidnight"
Write-Host "Logs:     $LogFile"
Write-Host ""
Write-Host "Useful commands:"
Write-Host "  Get-ScheduledTask -TaskName $TaskName                  # view"
Write-Host "  Start-ScheduledTask -TaskName $TaskName                # run now"
Write-Host "  Get-ScheduledTaskInfo -TaskName $TaskName              # last run status"
Write-Host "  .\scripts\register_scheduled_update.ps1 -Uninstall     # remove"
