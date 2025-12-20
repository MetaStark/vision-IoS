# =============================================================================
# G2C ALPHA DAEMON - WINDOWS TASK SCHEDULER SETUP
# =============================================================================
# CEO Directive: CD-G2C-ALPHA-IGNITION-48H-2025-12-13
#
# This script creates a Windows Scheduled Task that runs the G2C Alpha Daemon
# persistently, restarting automatically on failure or system reboot.
#
# Run as Administrator: .\setup_g2c_daemon_task.ps1
# =============================================================================

param(
    [switch]$Uninstall,
    [switch]$Status,
    [switch]$Restart
)

$ErrorActionPreference = "Stop"

# Configuration
$TaskName = "FHQ_G2C_Alpha_Daemon"
$TaskDescription = "FjordHQ G2-C Alpha Daemon - Continuous forecast generation, resolution, and skill scoring"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $ProjectRoot) {
    $ProjectRoot = "C:\fhq-market-system\vision-ios"
}
$PythonScript = Join-Path $ProjectRoot "03_FUNCTIONS\g2c_alpha_daemon.py"
$LogDir = Join-Path $ProjectRoot "logs"
$PythonExe = "python"  # Assumes python is in PATH

# Ensure log directory exists
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

function Get-TaskStatus {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        $info = Get-ScheduledTaskInfo -TaskName $TaskName
        Write-Host ""
        Write-Host "===== FHQ G2C ALPHA DAEMON STATUS =====" -ForegroundColor Cyan
        Write-Host "Task Name:      $TaskName"
        Write-Host "State:          $($task.State)" -ForegroundColor $(if ($task.State -eq "Running") { "Green" } else { "Yellow" })
        Write-Host "Last Run:       $($info.LastRunTime)"
        Write-Host "Last Result:    $($info.LastTaskResult)"
        Write-Host "Next Run:       $($info.NextRunTime)"
        Write-Host "========================================" -ForegroundColor Cyan
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
    Write-Host "===== INSTALLING FHQ G2C ALPHA DAEMON =====" -ForegroundColor Cyan
    Write-Host "Task Name:      $TaskName"
    Write-Host "Python Script:  $PythonScript"
    Write-Host "Log Directory:  $LogDir"
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""

    # Create the action - run Python with the script
    $Action = New-ScheduledTaskAction `
        -Execute $PythonExe `
        -Argument "`"$PythonScript`"" `
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
    # Note: For SYSTEM account, use -UserId "SYSTEM"
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
        Write-Host "The G2C Alpha Daemon is now running in the background." -ForegroundColor Green
        Write-Host "It will automatically restart on system reboot or failure." -ForegroundColor Green
        Write-Host ""
        Write-Host "Logs are written to: $LogDir\g2c_alpha_daemon.log" -ForegroundColor Cyan
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
