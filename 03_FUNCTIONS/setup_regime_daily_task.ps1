# IoS-003 v4 Daily Regime Update - Windows Task Scheduler Setup
# ==============================================================
# CEO Directive: Regime must be updated DAILY (max 1 day stale)
# Date: 2025-12-16
# Executor: STIG (CTO)

$TaskName = "FHQ_IOS003_REGIME_DAILY_V4"
$Description = "IoS-003 v4 Daily Regime Update - Runs daily at 06:00 for HMM regime inference"

# Find Python - use full path for scheduled tasks
$PythonPaths = @(
    "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python312\python.exe",
    "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python313\python.exe",
    "C:\Python312\python.exe",
    "C:\Python313\python.exe"
)

$PythonPath = $null
foreach ($p in $PythonPaths) {
    if (Test-Path $p) {
        $PythonPath = $p
        break
    }
}

if (-not $PythonPath) {
    Write-Error "Python not found! Install Python or update paths."
    exit 1
}

$ScriptPath = "C:\fhq-market-system\vision-ios\03_FUNCTIONS\ios003_daily_regime_update_v4.py"
$WorkingDir = "C:\fhq-market-system\vision-ios\03_FUNCTIONS"
$LogPath = "C:\fhq-market-system\vision-ios\logs"

# Ensure directories exist
if (!(Test-Path $LogPath)) { New-Item -ItemType Directory -Path $LogPath -Force }

Write-Host "============================================================"
Write-Host "IoS-003 v4 DAILY REGIME UPDATE - Task Setup"
Write-Host "============================================================"
Write-Host "Python: $PythonPath"
Write-Host "Script: $ScriptPath"
Write-Host ""

# Remove existing task if present
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task."
}

# Create action with full paths
$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$ScriptPath`"" `
    -WorkingDirectory $WorkingDir

# Daily trigger at 06:00
$Trigger = New-ScheduledTaskTrigger -Daily -At "06:00"

# Settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

# Register task
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description $Description

Write-Host ""
Write-Host "Task '$TaskName' created!"
Write-Host "  Schedule: Daily at 06:00"
Write-Host "  Script: $ScriptPath"
Write-Host ""
Write-Host "Commands:"
Write-Host "  Start now: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "  Check status: Get-ScheduledTask -TaskName '$TaskName' | Get-ScheduledTaskInfo"
