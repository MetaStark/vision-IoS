# FjordHQ Daemon Scheduled Tasks Setup
# CEO-DIR-2026-DAEMON-SCHEDULED-TASKS
# Run as Administrator: powershell -ExecutionPolicy Bypass -File setup_scheduled_tasks.ps1

$WorkingDir = "C:\fhq-market-system\vision-ios"
$PythonPath = "python"

# Define daemons
$Daemons = @(
    @{Name="FjordHQ_FINN_Brain"; Script="03_FUNCTIONS\finn_brain_scheduler.py"; Desc="FINN Cognitive Brain Scheduler"},
    @{Name="FjordHQ_FINN_Crypto"; Script="03_FUNCTIONS\finn_crypto_scheduler.py"; Desc="FINN Crypto Learning Scheduler"},
    @{Name="FjordHQ_Economic_Outcome"; Script="03_FUNCTIONS\economic_outcome_daemon.py"; Desc="Economic Outcome Daemon"},
    @{Name="FjordHQ_G2C_Forecast"; Script="03_FUNCTIONS\g2c_continuous_forecast_engine.py"; Desc="G2C Forecast Engine"},
    @{Name="FjordHQ_iOS003b_Regime"; Script="03_FUNCTIONS\ios003b_intraday_regime_delta.py"; Desc="iOS003b Regime Delta"}
)

Write-Host "============================================================"
Write-Host "FjordHQ Daemon Scheduled Tasks Setup"
Write-Host "============================================================"
Write-Host ""

foreach ($daemon in $Daemons) {
    $taskName = $daemon.Name
    $scriptPath = Join-Path $WorkingDir $daemon.Script
    $description = $daemon.Desc

    Write-Host "Creating task: $taskName"

    # Remove existing task if exists
    $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host "  Removed existing task"
    }

    # Create action
    $action = New-ScheduledTaskAction -Execute $PythonPath -Argument "`"$scriptPath`"" -WorkingDirectory $WorkingDir

    # Create trigger - at startup
    $trigger = New-ScheduledTaskTrigger -AtStartup

    # Create settings - restart on failure, run indefinitely
    $settings = New-ScheduledTaskSettingsSet `
        -RestartCount 999 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit (New-TimeSpan -Days 0) `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable

    # Register task (runs as current user)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description $description -Force

    Write-Host "  Created: $taskName"
    Write-Host ""
}

Write-Host "============================================================"
Write-Host "All tasks created. Starting daemons now..."
Write-Host "============================================================"

# Start all tasks immediately
foreach ($daemon in $Daemons) {
    $taskName = $daemon.Name
    Write-Host "Starting: $taskName"
    Start-ScheduledTask -TaskName $taskName
}

Write-Host ""
Write-Host "Done! Check Task Scheduler for FjordHQ_* tasks."
Write-Host "Or run: Get-ScheduledTask -TaskName 'FjordHQ_*' | Format-Table TaskName, State"
