# Fix IOS001 tasks in \FHQ\ folder
# These tasks already exist with the old broken paths
# Run as Administrator

$pythonPath = "C:\Users\RJANSK~1\AppData\Local\Programs\Python\PYTHON~2\python.exe"
$workDir = "C:\fhq-market-system\vision-ios"
$scriptPath = "$workDir\03_FUNCTIONS\ios001_bulletproof_ingest.py"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Fix IOS001 Tasks in \FHQ\ Folder" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# These tasks exist in \FHQ\ folder
$tasks = @(
    @{ Name = "ios001_daily_ingest_equity"; Args = "--asset-class EQUITY"; Time = "23:00" },
    @{ Name = "ios001_daily_ingest_crypto"; Args = "--asset-class CRYPTO"; Time = "02:00" },
    @{ Name = "ios001_daily_ingest_fx"; Args = "--asset-class FX"; Time = "23:00" }
)

foreach ($task in $tasks) {
    $taskPath = "\FHQ\"
    $fullName = "$taskPath$($task.Name)"

    Write-Host ""
    Write-Host "Processing: $fullName" -ForegroundColor Cyan

    # Remove old task
    Write-Host "  Removing old task..."
    Unregister-ScheduledTask -TaskPath $taskPath -TaskName $task.Name -Confirm:$false -ErrorAction SilentlyContinue

    # Create new task with correct path
    $action = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$scriptPath`" $($task.Args)" -WorkingDirectory $workDir
    $trigger = New-ScheduledTaskTrigger -Daily -At $task.Time
    $principal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries

    try {
        Register-ScheduledTask -TaskPath $taskPath -TaskName $task.Name -Action $action -Trigger $trigger -Principal $principal -Settings $settings -ErrorAction Stop | Out-Null
        Write-Host "  -> Created successfully" -ForegroundColor Green
    }
    catch {
        Write-Host "  -> Failed: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Also creating root-level tasks..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

$rootTasks = @(
    @{ Name = "FHQ_IOS001_EQUITY_DAILY"; Args = "--asset-class EQUITY"; Time = "23:00" },
    @{ Name = "FHQ_IOS001_CRYPTO_DAILY"; Args = "--asset-class CRYPTO"; Time = "23:05" },
    @{ Name = "FHQ_IOS001_FX_DAILY"; Args = "--asset-class FX"; Time = "23:10" }
)

foreach ($task in $rootTasks) {
    Write-Host ""
    Write-Host "Creating: $($task.Name)" -ForegroundColor Cyan

    # Remove if exists
    Unregister-ScheduledTask -TaskName $task.Name -Confirm:$false -ErrorAction SilentlyContinue

    $action = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$scriptPath`" $($task.Args)" -WorkingDirectory $workDir
    $trigger = New-ScheduledTaskTrigger -Daily -At $task.Time
    $principal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries

    try {
        Register-ScheduledTask -TaskName $task.Name -Action $action -Trigger $trigger -Principal $principal -Settings $settings -ErrorAction Stop | Out-Null
        Write-Host "  -> Created successfully" -ForegroundColor Green
    }
    catch {
        Write-Host "  -> Failed: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Verification" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

Write-Host ""
Write-Host "Root tasks:" -ForegroundColor Yellow
Get-ScheduledTask -TaskPath "\" | Where-Object TaskName -like "*IOS001*" | ForEach-Object {
    $isCorrect = $_.Actions.Execute -like "*RJANSK*"
    $status = if ($isCorrect) { "OK" } else { "WRONG" }
    Write-Host "  $($_.TaskName): $status - $($_.Actions.Execute)"
}

Write-Host ""
Write-Host "\FHQ\ tasks:" -ForegroundColor Yellow
Get-ScheduledTask -TaskPath "\FHQ\" -ErrorAction SilentlyContinue | Where-Object TaskName -like "*ios001*" | ForEach-Object {
    $isCorrect = $_.Actions.Execute -like "*RJANSK*"
    $status = if ($isCorrect) { "OK" } else { "WRONG" }
    Write-Host "  $($_.TaskName): $status - $($_.Actions.Execute)"
}

Write-Host ""
Write-Host "Done. Test with: schtasks /Run /TN 'FHQ_IOS001_EQUITY_DAILY'" -ForegroundColor Green
