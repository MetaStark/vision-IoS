# IoS-004 Backtest Worker Scheduled Task Setup
# CEO Directive: CD-EC018-IOS004-ALPHA-PIPELINE-001
#
# Creates Windows Scheduled Task to automatically backtest G0 hypotheses

$ErrorActionPreference = "Stop"

$taskName = "FHQ_IOS004_BACKTEST_WORKER"
$pythonPath = "python"
$scriptPath = "C:\fhq-market-system\vision-ios\03_FUNCTIONS\ios004_backtest_worker.py"
$logPath = "C:\fhq-market-system\vision-ios\logs\ios004_backtest_worker.log"

# Remove existing task if exists
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing existing task: $taskName" -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# Create action
$action = New-ScheduledTaskAction `
    -Execute $pythonPath `
    -Argument "$scriptPath --process-queue" `
    -WorkingDirectory "C:\fhq-market-system\vision-ios\03_FUNCTIONS"

# Create trigger - run every 15 minutes
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15)

# Create settings
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

# Register task
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "IoS-004 Backtest Worker - Validates G0 alpha hypotheses every 15 minutes"

Write-Host ""
Write-Host "Task '$taskName' created successfully!" -ForegroundColor Green
Write-Host "Schedule: Every 15 minutes" -ForegroundColor Cyan
Write-Host "Script: $scriptPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "To verify: Get-ScheduledTask -TaskName '$taskName'" -ForegroundColor Gray
Write-Host "To run now: Start-ScheduledTask -TaskName '$taskName'" -ForegroundColor Gray
