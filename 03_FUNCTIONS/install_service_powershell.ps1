# CEO-DIR-045: Install outcome_settlement_daemon as scheduled task
$taskName = "FjordHQ_OutcomeSettlement_Daemon"
$pythonPath = "C:\Python312\python.exe"
$scriptPath = "C:\fhq-market-system\vision-ios\03_FUNCTIONS\outcome_settlement_daemon.py"
$arguments = "--continuous --interval 3600"

Write-Host "[$(Get-Date)] Installing $taskName..."

# Delete existing task if present
Unregister-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue -Confirm:$false 2>$null

# Create new task
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument "$scriptPath $arguments"
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)

try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -User "SYSTEM" -Force
    Write-Host "[$(Get-Date)] Task created successfully"
} catch {
    Write-Host "[$(Get-Date)] ERROR: $_"
    Exit 1
}

# Start the task immediately
try {
    Start-ScheduledTask -TaskName $taskName
    Write-Host "[$(Get-Date)] Task started"
} catch {
    Write-Host "[$(Get-Date)] WARNING: Could not start task: $_"
}

# Wait and verify
Start-Sleep -Seconds 5

$taskInfo = Get-ScheduledTaskInfo -TaskName $taskName
Write-Host "[$(Get-Date)] Task State: $($taskInfo.State)"
Write-Host "[$(Get-Date)] Last Run: $($taskInfo.LastRunTime)"
Write-Host "[$(Get-Date)] Next Run: $($taskInfo.NextRunTime)"
