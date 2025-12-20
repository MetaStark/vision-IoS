<#
.SYNOPSIS
    Sets up Windows Task Scheduler for Daily OHLCV Ingest

.DESCRIPTION
    Creates a scheduled task to run the daily_ingest_worker.py at 00:05 UTC every day.
    Implements ADR-007 Orchestrator requirements.

.PARAMETER Install
    Install the scheduled task

.PARAMETER Uninstall
    Remove the scheduled task

.PARAMETER Status
    Check task status

.PARAMETER RunNow
    Trigger immediate execution

.EXAMPLE
    .\setup_daily_ingest_task.ps1 -Install
    .\setup_daily_ingest_task.ps1 -Status
    .\setup_daily_ingest_task.ps1 -RunNow

.NOTES
    Authority: ADR-007, ADR-013, IoS-001
    Owner: STIG (CTO)
#>

[CmdletBinding()]
param(
    [switch]$Install,
    [switch]$Uninstall,
    [switch]$Status,
    [switch]$RunNow
)

# Configuration
$TaskName = "FHQ_DailyOHLCVIngest"
$TaskDescription = "Daily OHLCV data ingestion for IoS-001 universe (BTC-USD, ETH-USD, SOL-USD, EURUSD)"
$VisionIosRoot = "C:\fhq-market-system\vision-ios"
$PythonPath = "python"
$ScriptPath = Join-Path $VisionIosRoot "03_FUNCTIONS\daily_ingest_worker.py"
$LogPath = Join-Path $VisionIosRoot "logs"

# Ensure log directory exists
if (-not (Test-Path $LogPath)) {
    New-Item -ItemType Directory -Path $LogPath -Force | Out-Null
}

function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host "=" * 60 -ForegroundColor Blue
    Write-Host " $Message" -ForegroundColor White
    Write-Host "=" * 60 -ForegroundColor Blue
    Write-Host ""
}

function Install-DailyIngestTask {
    Write-Header "Installing Daily OHLCV Ingest Task"

    # Check if task exists
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Write-Host "Task already exists. Removing..." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }

    # Create action
    # Run at 00:05 UTC = 01:05 CET (winter) or 02:05 CEST (summer)
    # Using --full-pipeline for complete automation
    $Action = New-ScheduledTaskAction `
        -Execute $PythonPath `
        -Argument "`"$ScriptPath`" --full-pipeline" `
        -WorkingDirectory $VisionIosRoot

    # Create trigger - Daily at 01:05 (CET, approximating UTC+1)
    # Note: Windows uses local time, so adjust for your timezone
    $Trigger = New-ScheduledTaskTrigger -Daily -At "01:05"

    # Create settings
    $Settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RunOnlyIfNetworkAvailable `
        -WakeToRun `
        -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 5)

    # Create principal (run whether user is logged in or not)
    $Principal = New-ScheduledTaskPrincipal `
        -UserId "$env:USERDOMAIN\$env:USERNAME" `
        -LogonType S4U `
        -RunLevel Highest

    # Register task
    try {
        Register-ScheduledTask `
            -TaskName $TaskName `
            -Description $TaskDescription `
            -Action $Action `
            -Trigger $Trigger `
            -Settings $Settings `
            -Principal $Principal `
            -Force

        Write-Host "✅ Task installed successfully!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Task Details:" -ForegroundColor Cyan
        Write-Host "  Name: $TaskName"
        Write-Host "  Schedule: Daily at 01:05 (local time, ~00:05 UTC)"
        Write-Host "  Script: $ScriptPath"
        Write-Host "  Logs: $LogPath"
        Write-Host ""
        Write-Host "To run immediately: .\setup_daily_ingest_task.ps1 -RunNow" -ForegroundColor Yellow
    }
    catch {
        Write-Host "❌ Failed to install task: $_" -ForegroundColor Red
        exit 1
    }
}

function Uninstall-DailyIngestTask {
    Write-Header "Removing Daily OHLCV Ingest Task"

    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "✅ Task removed successfully!" -ForegroundColor Green
    }
    else {
        Write-Host "Task does not exist." -ForegroundColor Yellow
    }
}

function Get-TaskStatus {
    Write-Header "Daily OHLCV Ingest Task Status"

    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

    if ($task) {
        $taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName

        Write-Host "Task: $TaskName" -ForegroundColor Cyan
        Write-Host "State: $($task.State)"
        Write-Host "Last Run: $($taskInfo.LastRunTime)"
        Write-Host "Last Result: $($taskInfo.LastTaskResult)"
        Write-Host "Next Run: $($taskInfo.NextRunTime)"
        Write-Host ""

        # Show recent logs
        $recentLog = Get-ChildItem "$LogPath\daily_ingest_*.log" -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1

        if ($recentLog) {
            Write-Host "Recent Log: $($recentLog.Name)" -ForegroundColor Cyan
            Write-Host "-" * 40
            Get-Content $recentLog.FullName -Tail 20
        }
    }
    else {
        Write-Host "Task not found. Install with: .\setup_daily_ingest_task.ps1 -Install" -ForegroundColor Yellow
    }
}

function Invoke-TaskNow {
    Write-Header "Triggering Immediate Execution"

    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

    if ($task) {
        Write-Host "Starting task..." -ForegroundColor Cyan
        Start-ScheduledTask -TaskName $TaskName
        Write-Host "✅ Task triggered!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Monitor progress with: .\setup_daily_ingest_task.ps1 -Status" -ForegroundColor Yellow
    }
    else {
        Write-Host "Task not found. Install first with: .\setup_daily_ingest_task.ps1 -Install" -ForegroundColor Red
    }
}

# Main
if ($Install) {
    Install-DailyIngestTask
}
elseif ($Uninstall) {
    Uninstall-DailyIngestTask
}
elseif ($Status) {
    Get-TaskStatus
}
elseif ($RunNow) {
    Invoke-TaskNow
}
else {
    Write-Header "FHQ Daily OHLCV Ingest Task Setup"
    Write-Host "Usage:"
    Write-Host "  .\setup_daily_ingest_task.ps1 -Install    # Install scheduled task"
    Write-Host "  .\setup_daily_ingest_task.ps1 -Uninstall  # Remove scheduled task"
    Write-Host "  .\setup_daily_ingest_task.ps1 -Status     # Check task status"
    Write-Host "  .\setup_daily_ingest_task.ps1 -RunNow     # Trigger immediate run"
    Write-Host ""
    Write-Host "Schedule: Daily at 00:05 UTC"
    Write-Host "Pipeline: FETCH → STAGE → RECONCILE → CANONICALIZE"
    Write-Host ""
}
