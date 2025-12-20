# =============================================================================
# WAVE 17C PROMOTION DAEMON - WINDOWS TASK SCHEDULER SETUP
# =============================================================================
# WAVE 17D - VEGA Evidence Generator for Golden Needles
#
# This script creates a Windows Scheduled Task that runs the WAVE 17C Promotion
# Daemon persistently, ensuring all Golden Needles receive VEGA attestations.
#
# Run as Administrator: .\setup_wave17c_task.ps1
# =============================================================================

param(
    [switch]$Uninstall,
    [switch]$Status,
    [switch]$Restart
)

$ErrorActionPreference = "Stop"

# Configuration
$TaskName = "FHQ_WAVE17C_Promotion_Daemon"
$TaskDescription = "FjordHQ WAVE 17C Promotion Daemon - VEGA evidence generation for Golden Needles"
$ProjectRoot = "C:\fhq-market-system\vision-ios"
$PythonScript = Join-Path $ProjectRoot "03_FUNCTIONS\wave17c_promotion_daemon.py"
$LogDir = Join-Path $ProjectRoot "logs"
$PythonExe = "python"

# Ensure log directory exists
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

function Get-TaskStatus {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        $info = Get-ScheduledTaskInfo -TaskName $TaskName
        Write-Host ""
        Write-Host "===== FHQ WAVE 17C PROMOTION DAEMON STATUS =====" -ForegroundColor Cyan
        Write-Host "Task Name:      $TaskName"
        Write-Host "State:          $($task.State)" -ForegroundColor $(if ($task.State -eq "Running") { "Green" } else { "Yellow" })
        Write-Host "Last Run:       $($info.LastRunTime)"
        Write-Host "Last Result:    $($info.LastTaskResult)"
        Write-Host "Next Run:       $($info.NextRunTime)"
        Write-Host "================================================" -ForegroundColor Cyan
        Write-Host ""
        return $task
    } else {
        Write-Host ""
        Write-Host "Task '$TaskName' is NOT installed." -ForegroundColor Yellow
        Write-Host ""
        return $null
    }
}

function Uninstall-Task {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Write-Host "Stopping task..." -ForegroundColor Yellow
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

        Write-Host "Unregistering task..." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false

        Write-Host "Task '$TaskName' has been uninstalled." -ForegroundColor Green
    } else {
        Write-Host "Task '$TaskName' was not found." -ForegroundColor Yellow
    }
}

function Restart-Task {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Write-Host "Stopping task..." -ForegroundColor Yellow
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2

        Write-Host "Starting task..." -ForegroundColor Yellow
        Start-ScheduledTask -TaskName $TaskName
        Start-Sleep -Seconds 2

        Get-TaskStatus
    } else {
        Write-Host "Task '$TaskName' is not installed. Run setup first." -ForegroundColor Red
    }
}

function Install-Task {
    # Check if task already exists
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Write-Host "Task '$TaskName' already exists. Use -Restart to restart or -Uninstall to remove." -ForegroundColor Yellow
        Get-TaskStatus
        return
    }

    # Verify Python script exists
    if (-not (Test-Path $PythonScript)) {
        Write-Host "ERROR: Python script not found at: $PythonScript" -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "===== INSTALLING FHQ WAVE 17C PROMOTION DAEMON =====" -ForegroundColor Cyan
    Write-Host "Task Name:      $TaskName"
    Write-Host "Python Script:  $PythonScript"
    Write-Host "Log Directory:  $LogDir"
    Write-Host "===================================================" -ForegroundColor Cyan
    Write-Host ""

    # Create the action - run Python with the script (continuous mode with 60s interval)
    $Action = New-ScheduledTaskAction `
        -Execute $PythonExe `
        -Argument "`"$PythonScript`" --interval 60" `
        -WorkingDirectory $ProjectRoot

    # Trigger: At startup and also now
    $TriggerAtStartup = New-ScheduledTaskTrigger -AtStartup
    $TriggerNow = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(10)

    # Settings
    $Settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit (New-TimeSpan -Days 0) `
        -MultipleInstances IgnoreNew

    # Principal - run whether user is logged on or not
    $Principal = New-ScheduledTaskPrincipal `
        -UserId $env:USERNAME `
        -LogonType S4U `
        -RunLevel Highest

    # Register the task
    try {
        Register-ScheduledTask `
            -TaskName $TaskName `
            -Description $TaskDescription `
            -Action $Action `
            -Trigger $TriggerAtStartup, $TriggerNow `
            -Settings $Settings `
            -Principal $Principal `
            -Force

        Write-Host ""
        Write-Host "Task '$TaskName' installed successfully!" -ForegroundColor Green
        Write-Host ""

        # Start the task immediately
        Write-Host "Starting the daemon now..." -ForegroundColor Yellow
        Start-ScheduledTask -TaskName $TaskName
        Start-Sleep -Seconds 3

        Get-TaskStatus

        Write-Host ""
        Write-Host "The WAVE 17C Promotion Daemon is now running in the background." -ForegroundColor Green
        Write-Host "It will automatically restart on system reboot or failure." -ForegroundColor Green
        Write-Host ""
        Write-Host "Logs are written to: $ProjectRoot\03_FUNCTIONS\wave17c_promotion.log" -ForegroundColor Cyan
        Write-Host ""

    } catch {
        Write-Host "ERROR: Failed to create scheduled task: $_" -ForegroundColor Red
        Write-Host ""
        Write-Host "If you see an access denied error, try running PowerShell as Administrator." -ForegroundColor Yellow
        exit 1
    }
}

# Main logic
if ($Status) {
    Get-TaskStatus
} elseif ($Uninstall) {
    Uninstall-Task
} elseif ($Restart) {
    Restart-Task
} else {
    Install-Task
}
