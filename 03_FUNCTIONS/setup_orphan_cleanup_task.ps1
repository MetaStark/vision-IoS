# =====================================================================
# ORPHAN STATE CLEANUP DAEMON - WINDOWS TASK SCHEDULER SETUP
# =====================================================================
# Authority: DAY30 Session 9 — Pipeline Integrity
# Date: 2026-01-30
# Usage: .\setup_orphan_cleanup_task.ps1
# =====================================================================

$ErrorActionPreference = "Stop"

$PythonPath = (Get-Command python).Source
$ScriptPath = "C:\fhq-market-system\vision-ios\03_FUNCTIONS\orphan_state_cleanup_daemon.py"
$WorkingDir = "C:\fhq-market-system\vision-ios"
$TaskName = "FHQ-Orphan-State-Cleanup"

Write-Host "Python path: $PythonPath" -ForegroundColor Gray

if (-not (Test-Path $ScriptPath)) {
    Write-Error "Script not found: $ScriptPath"
    exit 1
}

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "ORPHAN STATE CLEANUP DAEMON - TASK SCHEDULER SETUP" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$ScriptPath`" --once" `
    -WorkingDirectory $WorkingDir

# Run every 60 minutes via repetition
$Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).Date.AddHours(0) `
    -RepetitionInterval (New-TimeSpan -Minutes 60) `
    -RepetitionDuration (New-TimeSpan -Days 365)

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5)

Write-Host "[*] Registering task..." -ForegroundColor Yellow
try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

$Task = Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Orphan State Cleanup - Cascades FALSIFIED hypothesis status to shadow trades, simulations, and experiments (60-min cycle)"

Write-Host "[+] Task registered" -ForegroundColor Green
Write-Host "    Schedule: Every 60 minutes" -ForegroundColor Gray
Write-Host "    Timeout: 10 minutes" -ForegroundColor Gray

Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "VERIFICATION" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan

$registeredTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($registeredTask) {
    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    Write-Host "[+] Task registered successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  $($registeredTask.TaskName)" -ForegroundColor White
    Write-Host "    State: $($registeredTask.State)" -ForegroundColor Gray
    Write-Host "    Next Run: $($info.NextRunTime)" -ForegroundColor Gray
} else {
    Write-Host "[!] Warning: Task not found" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "To test: python `"$ScriptPath`" --once" -ForegroundColor Gray
Write-Host ""
