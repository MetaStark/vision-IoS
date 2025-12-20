# Fix All FHQ Scheduled Tasks - Use Full Python Path
# ===================================================
# Issue: Tasks failing with "file not found" due to missing Python in PATH
# Solution: Update all tasks to use full Python path
# Date: 2025-12-16

# Find Python
$PythonPath = "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python312\python.exe"
if (!(Test-Path $PythonPath)) {
    $PythonPath = "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python313\python.exe"
}
if (!(Test-Path $PythonPath)) {
    Write-Error "Python not found!"
    exit 1
}

Write-Host "Using Python: $PythonPath"
Write-Host ""

$WorkingDir = "C:\fhq-market-system\vision-ios\03_FUNCTIONS"

# Task definitions
$Tasks = @(
    @{
        Name = "FHQ_IOS001_CRYPTO_DAILY"
        Script = "ios001_daily_ingest.py"
        Args = "--asset-class CRYPTO --trigger-regime"
        Schedule = "Daily at 02:00"
        Trigger = { New-ScheduledTaskTrigger -Daily -At "02:00" }
    },
    @{
        Name = "FHQ_IOS001_EQUITY_DAILY"
        Script = "ios001_daily_ingest.py"
        Args = "--asset-class EQUITY --trigger-regime"
        Schedule = "Weekdays at 23:00"
        Trigger = { New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At "23:00" }
    },
    @{
        Name = "FHQ_IOS001_FX_DAILY"
        Script = "ios001_daily_ingest.py"
        Args = "--asset-class FX --trigger-regime"
        Schedule = "Sun-Thu at 23:00"
        Trigger = { New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday,Monday,Tuesday,Wednesday,Thursday -At "23:00" }
    }
)

foreach ($task in $Tasks) {
    Write-Host "Updating: $($task.Name)"

    # Remove existing
    $existing = Get-ScheduledTask -TaskName $task.Name -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $task.Name -Confirm:$false
    }

    # Create action with full paths
    $ScriptPath = Join-Path $WorkingDir $task.Script
    $Action = New-ScheduledTaskAction `
        -Execute $PythonPath `
        -Argument "`"$ScriptPath`" $($task.Args)" `
        -WorkingDirectory $WorkingDir

    # Create trigger
    $Trigger = & $task.Trigger

    # Settings
    $Settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Hours 2)

    # Register
    Register-ScheduledTask -TaskName $task.Name -Action $Action -Trigger $Trigger -Settings $Settings -Description "IoS-001 Price Ingest - $($task.Schedule)"

    Write-Host "  Created: $($task.Schedule)"
}

Write-Host ""
Write-Host "All tasks updated!"
Write-Host ""
Write-Host "Current status:"
Get-ScheduledTask -TaskName "FHQ_*" | Format-Table TaskName, State -AutoSize
