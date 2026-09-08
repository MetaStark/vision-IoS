# CEO-DIR-2026-088: Register Monthly Trading Calendar Governance Task
# Run on 1st of each month at 03:00 local time

$TaskName = "FjordHQ-TradingCalendarGovernance"
$ScriptPath = "C:\fhq-market-system\vision-ios\03_FUNCTIONS\trading_calendar_governance_daemon.py"
$PythonPath = (Get-Command python).Source

Write-Host "Registering scheduled task: $TaskName"
Write-Host "Python: $PythonPath"
Write-Host "Script: $ScriptPath"

# Create the action
$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument $ScriptPath -WorkingDirectory "C:\fhq-market-system\vision-ios\03_FUNCTIONS"

# Create monthly trigger (1st of each month at 03:00)
$Trigger = New-ScheduledTaskTrigger -Monthly -DaysOfMonth 1 -At "03:00"

# Settings
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -AllowStartIfOnBatteries

# Register the task
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "CEO-DIR-2026-088: Monthly trading calendar extension daemon. Extends US_EQUITY calendar 24+ months forward." -Force

Write-Host ""
Write-Host "Task registered successfully!"
Get-ScheduledTask -TaskName $TaskName | Format-List TaskName, State, Description
