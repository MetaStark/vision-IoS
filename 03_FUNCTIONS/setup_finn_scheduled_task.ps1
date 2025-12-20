# FINN Cognitive Brain - Windows Task Scheduler Setup
# ====================================================
# Creates a Windows Scheduled Task to run FINN Brain every 30 minutes
#
# Run this script as Administrator:
#   powershell -ExecutionPolicy Bypass -File setup_finn_scheduled_task.ps1

$TaskName = "FjordHQ_FINN_Cognitive_Brain"
$Description = "FINN Cognitive Brain - Runs every 30 minutes for alpha learning (ADR-020, CD-IOS015)"

# Task settings
$PythonPath = "python"  # Assumes python is in PATH
$ScriptPath = "C:\fhq-market-system\vision-ios\03_FUNCTIONS\finn_brain_scheduler.py"
$WorkingDir = "C:\fhq-market-system\vision-ios\03_FUNCTIONS"
$LogPath = "C:\fhq-market-system\vision-ios\logs"

# Ensure log directory exists
if (!(Test-Path $LogPath)) {
    New-Item -ItemType Directory -Path $LogPath -Force
}

Write-Host "============================================================"
Write-Host "FINN Cognitive Brain - Scheduled Task Setup"
Write-Host "============================================================"
Write-Host ""

# Check if task already exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Task '$TaskName' already exists."
    $response = Read-Host "Do you want to replace it? (y/n)"
    if ($response -eq 'y') {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Existing task removed."
    } else {
        Write-Host "Setup cancelled."
        exit
    }
}

# Create the action
$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument $ScriptPath `
    -WorkingDirectory $WorkingDir

# Create the trigger (every 30 minutes, indefinitely)
$Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 30) `
    -RepetitionDuration ([TimeSpan]::MaxValue)

# Task settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -MultipleInstances IgnoreNew

# Create the task
$Task = New-ScheduledTask `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description $Description

# Register the task
Register-ScheduledTask -TaskName $TaskName -InputObject $Task -User "SYSTEM"

Write-Host ""
Write-Host "Task '$TaskName' created successfully!"
Write-Host ""
Write-Host "Task Details:"
Write-Host "  - Runs every 30 minutes"
Write-Host "  - Script: $ScriptPath"
Write-Host "  - Logs: $LogPath"
Write-Host ""
Write-Host "To start immediately: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "To stop: Stop-ScheduledTask -TaskName '$TaskName'"
Write-Host "To remove: Unregister-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
