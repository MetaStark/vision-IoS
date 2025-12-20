# =====================================================================
# IoS-001 BULLETPROOF INGEST - WINDOWS TASK SCHEDULER SETUP
# =====================================================================
# CEO Directive: CD-IOS-001-DAILY-INGEST-BULLETPROOF-001
# Date: 2025-12-16
#
# This script creates Windows Task Scheduler tasks for bulletproof
# daily price ingestion with multi-provider fallback.
#
# Usage:
#   Run as Administrator:
#   .\setup_bulletproof_ingest_task.ps1
#
# Tasks Created:
#   1. FHQ-IoS001-Bulletproof-CRYPTO  - Daily 02:00 UTC (03:00 CET)
#   2. FHQ-IoS001-Bulletproof-EQUITY  - Weekdays 22:30 UTC (23:30 CET)
#   3. FHQ-IoS001-Bulletproof-FX      - Weekdays 22:30 UTC (23:30 CET)
#
# =====================================================================

$ErrorActionPreference = "Stop"

# Configuration
$PythonPath = "python"  # Use system Python
$ScriptPath = "C:\fhq-market-system\vision-ios\03_FUNCTIONS\ios001_bulletproof_ingest.py"
$TaskFolder = "\FjordHQ\"

# Verify script exists
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Script not found: $ScriptPath"
    exit 1
}

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "IoS-001 BULLETPROOF INGEST - TASK SCHEDULER SETUP" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

# Create task folder if it doesn't exist
try {
    $scheduleService = New-Object -ComObject Schedule.Service
    $scheduleService.Connect()
    $rootFolder = $scheduleService.GetFolder("\")
    try {
        $folder = $rootFolder.GetFolder("FjordHQ")
    } catch {
        $rootFolder.CreateFolder("FjordHQ") | Out-Null
        Write-Host "[+] Created task folder: $TaskFolder" -ForegroundColor Green
    }
} catch {
    Write-Warning "Could not create task folder - tasks will be in root"
    $TaskFolder = "\"
}

# Common settings for all tasks
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 10)

$principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

# =====================================================================
# TASK 1: CRYPTO - Daily 02:00 UTC (03:00 CET)
# =====================================================================

Write-Host ""
Write-Host "[CRYPTO] Creating daily crypto ingest task..." -ForegroundColor Yellow

$cryptoAction = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$ScriptPath`" --asset-class CRYPTO" `
    -WorkingDirectory "C:\fhq-market-system\vision-ios\03_FUNCTIONS"

$cryptoTrigger = New-ScheduledTaskTrigger `
    -Daily `
    -At "03:00"  # 02:00 UTC = 03:00 CET

$cryptoTask = Register-ScheduledTask `
    -TaskName "FHQ-IoS001-Bulletproof-CRYPTO" `
    -TaskPath $TaskFolder `
    -Action $cryptoAction `
    -Trigger $cryptoTrigger `
    -Settings $settings `
    -Principal $principal `
    -Description "IoS-001 Bulletproof Daily Price Ingest - CRYPTO (02:00 UTC daily)" `
    -Force

Write-Host "[+] CRYPTO task registered successfully" -ForegroundColor Green
Write-Host "    Schedule: Daily at 03:00 CET (02:00 UTC)" -ForegroundColor Gray
Write-Host "    Task: $($cryptoTask.TaskPath)$($cryptoTask.TaskName)" -ForegroundColor Gray

# =====================================================================
# TASK 2: EQUITY - Weekdays 22:30 UTC (23:30 CET)
# =====================================================================

Write-Host ""
Write-Host "[EQUITY] Creating weekday equity ingest task..." -ForegroundColor Yellow

$equityAction = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$ScriptPath`" --asset-class EQUITY" `
    -WorkingDirectory "C:\fhq-market-system\vision-ios\03_FUNCTIONS"

# Weekdays only trigger
$equityTrigger = New-ScheduledTaskTrigger `
    -Weekly `
    -WeeksInterval 1 `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday `
    -At "23:30"  # 22:30 UTC = 23:30 CET

$equityTask = Register-ScheduledTask `
    -TaskName "FHQ-IoS001-Bulletproof-EQUITY" `
    -TaskPath $TaskFolder `
    -Action $equityAction `
    -Trigger $equityTrigger `
    -Settings $settings `
    -Principal $principal `
    -Description "IoS-001 Bulletproof Daily Price Ingest - EQUITY (22:30 UTC weekdays)" `
    -Force

Write-Host "[+] EQUITY task registered successfully" -ForegroundColor Green
Write-Host "    Schedule: Weekdays at 23:30 CET (22:30 UTC)" -ForegroundColor Gray
Write-Host "    Task: $($equityTask.TaskPath)$($equityTask.TaskName)" -ForegroundColor Gray

# =====================================================================
# TASK 3: FX - Sun-Thu 22:30 UTC (23:30 CET)
# =====================================================================

Write-Host ""
Write-Host "[FX] Creating FX ingest task..." -ForegroundColor Yellow

$fxAction = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$ScriptPath`" --asset-class FX" `
    -WorkingDirectory "C:\fhq-market-system\vision-ios\03_FUNCTIONS"

# Sun-Thu (FX market hours)
$fxTrigger = New-ScheduledTaskTrigger `
    -Weekly `
    -WeeksInterval 1 `
    -DaysOfWeek Sunday, Monday, Tuesday, Wednesday, Thursday `
    -At "23:30"  # 22:30 UTC = 23:30 CET

$fxTask = Register-ScheduledTask `
    -TaskName "FHQ-IoS001-Bulletproof-FX" `
    -TaskPath $TaskFolder `
    -Action $fxAction `
    -Trigger $fxTrigger `
    -Settings $settings `
    -Principal $principal `
    -Description "IoS-001 Bulletproof Daily Price Ingest - FX (22:30 UTC Sun-Thu)" `
    -Force

Write-Host "[+] FX task registered successfully" -ForegroundColor Green
Write-Host "    Schedule: Sun-Thu at 23:30 CET (22:30 UTC)" -ForegroundColor Gray
Write-Host "    Task: $($fxTask.TaskPath)$($fxTask.TaskName)" -ForegroundColor Gray

# =====================================================================
# VERIFICATION
# =====================================================================

Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "VERIFICATION" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan

$tasks = Get-ScheduledTask -TaskPath "$TaskFolder*" -TaskName "FHQ-IoS001-Bulletproof-*" -ErrorAction SilentlyContinue

if ($tasks.Count -eq 3) {
    Write-Host "[+] All 3 tasks registered successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Tasks:" -ForegroundColor White
    foreach ($task in $tasks) {
        $info = Get-ScheduledTaskInfo -TaskPath $task.TaskPath -TaskName $task.TaskName
        Write-Host "  - $($task.TaskName)" -ForegroundColor White
        Write-Host "    State: $($task.State)" -ForegroundColor Gray
        Write-Host "    Next Run: $($info.NextRunTime)" -ForegroundColor Gray
    }
} else {
    Write-Host "[!] Warning: Expected 3 tasks, found $($tasks.Count)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "SETUP COMPLETE" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""
Write-Host "To run immediately:" -ForegroundColor White
Write-Host "  Start-ScheduledTask -TaskPath '$TaskFolder' -TaskName 'FHQ-IoS001-Bulletproof-CRYPTO'" -ForegroundColor Gray
Write-Host ""
Write-Host "To view task history:" -ForegroundColor White
Write-Host "  Get-ScheduledTaskInfo -TaskPath '$TaskFolder' -TaskName 'FHQ-IoS001-Bulletproof-CRYPTO'" -ForegroundColor Gray
Write-Host ""
Write-Host "To remove all tasks:" -ForegroundColor White
Write-Host "  Get-ScheduledTask -TaskPath '$TaskFolder*' -TaskName 'FHQ-IoS001-*' | Unregister-ScheduledTask" -ForegroundColor Gray
Write-Host ""
