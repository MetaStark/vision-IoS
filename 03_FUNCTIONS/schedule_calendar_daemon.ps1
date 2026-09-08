# CEO-DIR-2026-088: Schedule Monthly Trading Calendar Governance Daemon
# Run on 1st of each month at 02:00 UTC

$TaskName = "FjordHQ-TradingCalendarGovernance"
$ScriptPath = "C:\fhq-market-system\vision-ios\03_FUNCTIONS\trading_calendar_governance_daemon.py"
$PythonPath = (Get-Command python).Source

# Create the action
$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument $ScriptPath -WorkingDirectory "C:\fhq-market-system\vision-ios\03_FUNCTIONS"

# Create monthly trigger (1st of each month at 02:00)
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -WeeksInterval 4 -At "02:00"

# Settings
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -AllowStartIfOnBatteries

# Register the task
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "CEO-DIR-2026-088: Monthly trading calendar extension daemon" -Force

Write-Host "Scheduled task '$TaskName' created successfully"
Write-Host "Next run: 1st of next month at 02:00 UTC"
