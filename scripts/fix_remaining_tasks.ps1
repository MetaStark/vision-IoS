# Fix remaining tasks with Unicode/relative path issues
# Run as Administrator

$pythonPath = "C:\Users\RJANSK~1\AppData\Local\Programs\Python\PYTHON~2\python.exe"
$workDir = "C:\fhq-market-system\vision-ios"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Fix Remaining FHQ Tasks" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 1. Fix FHQ_IOS003_REGIME_DAILY_V4
Write-Host "1. Fixing FHQ_IOS003_REGIME_DAILY_V4..." -ForegroundColor Yellow
Unregister-ScheduledTask -TaskName "FHQ_IOS003_REGIME_DAILY_V4" -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction `
    -Execute $pythonPath `
    -Argument "`"$workDir\03_FUNCTIONS\ios003_daily_regime_update_v4.py`"" `
    -WorkingDirectory "$workDir\03_FUNCTIONS"
$trigger = New-ScheduledTaskTrigger -Daily -At "06:00"
$principal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)

try {
    Register-ScheduledTask -TaskName "FHQ_IOS003_REGIME_DAILY_V4" -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "IoS-003 v4 Daily Regime Update" | Out-Null
    Write-Host "  -> Created successfully" -ForegroundColor Green
} catch {
    Write-Host "  -> Failed: $($_.Exception.Message)" -ForegroundColor Red
}

# 2. Fix FHQ_WAVE17C_Promotion_Daemon
Write-Host ""
Write-Host "2. Fixing FHQ_WAVE17C_Promotion_Daemon..." -ForegroundColor Yellow
Unregister-ScheduledTask -TaskName "FHQ_WAVE17C_Promotion_Daemon" -Confirm:$false -ErrorAction SilentlyContinue

$action2 = New-ScheduledTaskAction `
    -Execute $pythonPath `
    -Argument "`"$workDir\03_FUNCTIONS\wave17c_promotion.py`"" `
    -WorkingDirectory $workDir
$trigger2 = New-ScheduledTaskTrigger -AtStartup
$principal2 = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings2 = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

try {
    Register-ScheduledTask -TaskName "FHQ_WAVE17C_Promotion_Daemon" -Action $action2 -Trigger $trigger2 -Principal $principal2 -Settings $settings2 -Description "WAVE 17C Promotion Daemon" | Out-Null
    Write-Host "  -> Created successfully" -ForegroundColor Green
} catch {
    Write-Host "  -> Failed: $($_.Exception.Message)" -ForegroundColor Red
}

# 3. Delete old \FHQ\ folder tasks (replaced by new FHQ_IOS001_* tasks)
Write-Host ""
Write-Host "3. Removing old \FHQ\ folder tasks (replaced by FHQ_IOS001_*)..." -ForegroundColor Yellow
$oldTasks = @("ios001_daily_ingest_equity", "ios001_daily_ingest_crypto", "ios001_daily_ingest_fx")
foreach ($taskName in $oldTasks) {
    try {
        Unregister-ScheduledTask -TaskPath "\FHQ\" -TaskName $taskName -Confirm:$false -ErrorAction Stop
        Write-Host "  Deleted: \FHQ\$taskName" -ForegroundColor Green
    } catch {
        Write-Host "  Not found or error: \FHQ\$taskName" -ForegroundColor Gray
    }
}

# Verification
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Verification" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$tasksToCheck = @("FHQ_IOS003_REGIME_DAILY_V4", "FHQ_WAVE17C_Promotion_Daemon")
foreach ($name in $tasksToCheck) {
    $t = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($t) {
        $isOK = $t.Actions.Execute -like "*RJANSK*"
        $status = if ($isOK) { "OK" } else { "BAD" }
        $color = if ($isOK) { "Green" } else { "Red" }
        Write-Host "$name : $status" -ForegroundColor $color
        Write-Host "  Path: $($t.Actions.Execute)"
    } else {
        Write-Host "$name : NOT FOUND" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
