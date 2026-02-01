# Create remaining IOS001 tasks
$pythonPath = "C:\Users\RJANSK~1\AppData\Local\Programs\Python\PYTHON~2\python.exe"
$scriptPath = "C:\fhq-market-system\vision-ios\03_FUNCTIONS\ios001_bulletproof_ingest.py"
$workDir = "C:\fhq-market-system\vision-ios"

$tasks = @(
    @{ Name = "FHQ_IOS001_CRYPTO_DAILY"; Args = "--asset-class CRYPTO"; Time = "23:05" },
    @{ Name = "FHQ_IOS001_FX_DAILY"; Args = "--asset-class FX"; Time = "23:10" }
)

foreach ($task in $tasks) {
    Write-Host "Creating: $($task.Name)"

    $action = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$scriptPath`" $($task.Args)" -WorkingDirectory $workDir
    $trigger = New-ScheduledTaskTrigger -Daily -At $task.Time
    $principal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\SYSTEM" -LogonType ServiceAccount -RunLevel Highest

    Register-ScheduledTask -TaskName $task.Name -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null

    $check = Get-ScheduledTask -TaskName $task.Name -ErrorAction SilentlyContinue
    if ($check) {
        Write-Host "  -> OK: $($check.Actions.Execute)" -ForegroundColor Green
    } else {
        Write-Host "  -> FAILED" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "All IOS001 tasks:" -ForegroundColor Cyan
Get-ScheduledTask | Where-Object TaskName -like "*IOS001*" | Select-Object TaskName, State | Format-Table
