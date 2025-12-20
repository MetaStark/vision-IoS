# ============================================================================
# CCO DAEMON TASK SCHEDULER SETUP
# CEO Directive WAVE 17A - Central Context Orchestrator
# ============================================================================
# Run as Administrator:
#   powershell -ExecutionPolicy Bypass -File setup_cco_daemon_task.ps1
# ============================================================================

$TaskName = "FjordHQ_CCO_Daemon"
$TaskDescription = "Central Context Orchestrator - WAVE 17A Paper Execution Mode"
$BatchFile = "C:\fhq-market-system\vision-ios\run_cco_daemon.bat"
$WorkingDir = "C:\fhq-market-system\vision-ios"

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    exit 1
}

# Check if batch file exists
if (-not (Test-Path $BatchFile)) {
    Write-Host "ERROR: Batch file not found: $BatchFile" -ForegroundColor Red
    exit 1
}

# Remove existing task if present
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Removing existing task: $TaskName" -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create trigger: At system startup
$Trigger = New-ScheduledTaskTrigger -AtStartup

# Create action: Run batch file
$Action = New-ScheduledTaskAction -Execute $BatchFile -WorkingDirectory $WorkingDir

# Create settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 365) `
    -MultipleInstances IgnoreNew

# Create principal: Run as current user (required for user-installed Python)
# Note: Task will run even when user is not logged in
$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType S4U `
    -RunLevel Highest

# Register the task
$Task = New-ScheduledTask `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description $TaskDescription

Register-ScheduledTask -TaskName $TaskName -InputObject $Task

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "CCO DAEMON TASK CREATED SUCCESSFULLY" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host "Task Name:    $TaskName"
Write-Host "Trigger:      At system startup"
Write-Host "Run As:       $env:USERNAME (S4U - runs without login)"
Write-Host "Restart:      On failure (after 1 min, max 3 times)"
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "To start immediately:" -ForegroundColor Cyan
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
Write-Host "To check status:" -ForegroundColor Cyan
Write-Host "  Get-ScheduledTask -TaskName '$TaskName' | Select-Object State"
Write-Host ""
Write-Host "To view logs:" -ForegroundColor Cyan
Write-Host "  Get-Content C:\fhq-market-system\vision-ios\logs\cco_daemon.log -Tail 50"
Write-Host ""
