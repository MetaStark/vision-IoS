# Create single EQUITY task for testing
$pythonPath = "C:\Users\RJANSK~1\AppData\Local\Programs\Python\PYTHON~2\python.exe"
$scriptPath = "C:\fhq-market-system\vision-ios\03_FUNCTIONS\ios001_bulletproof_ingest.py"
$workDir = "C:\fhq-market-system\vision-ios"

$action = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$scriptPath`" --asset-class EQUITY" -WorkingDirectory $workDir
$trigger = New-ScheduledTaskTrigger -Daily -At "23:00"
$principal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\SYSTEM" -LogonType ServiceAccount -RunLevel Highest

$result = Register-ScheduledTask -TaskName "FHQ_IOS001_EQUITY_DAILY" -Action $action -Trigger $trigger -Principal $principal -Description "IOS001 EQUITY Ingest" -Force

Write-Host "Task created: $($result.TaskName)"
Write-Host "State: $($result.State)"

# Verify
$task = Get-ScheduledTask -TaskName "FHQ_IOS001_EQUITY_DAILY" -ErrorAction SilentlyContinue
if ($task) {
    Write-Host "Verification: Task exists"
    Write-Host "Execute: $($task.Actions.Execute)"
} else {
    Write-Host "Verification: Task NOT found" -ForegroundColor Red
}
