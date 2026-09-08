# Fix LDOW Scheduled Tasks - Run as Administrator
# Uses short path to avoid Unicode encoding issues

$pythonPath = "C:\Users\RJANSK~1\AppData\Local\Programs\Python\PYTHON~2\python.exe"
$workingDir = "C:\fhq-market-system\vision-ios"
$scriptPath = "C:\fhq-market-system\vision-ios\03_FUNCTIONS\ldow_cycle_completion_daemon.py"

Write-Host "Using Python path: $pythonPath"
Write-Host "Verifying path exists: $(Test-Path $pythonPath)"
Write-Host ""

Write-Host "Fixing FHQ_LDOW_Cycle1_Completion..."
$action1 = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$scriptPath`" --cycle 1" -WorkingDirectory $workingDir
Set-ScheduledTask -TaskName "FHQ_LDOW_Cycle1_Completion" -Action $action1
Write-Host "Cycle 1 task updated."

Write-Host "Fixing FHQ_LDOW_Cycle2_Completion..."
$action2 = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$scriptPath`" --cycle 2" -WorkingDirectory $workingDir
Set-ScheduledTask -TaskName "FHQ_LDOW_Cycle2_Completion" -Action $action2
Write-Host "Cycle 2 task updated."

Write-Host ""
Write-Host "Verifying updates..."
$task1 = Get-ScheduledTask -TaskName "FHQ_LDOW_Cycle1_Completion"
$task2 = Get-ScheduledTask -TaskName "FHQ_LDOW_Cycle2_Completion"

Write-Host "Cycle 1 Execute: $($task1.Actions.Execute)"
Write-Host "Cycle 1 Path exists: $(Test-Path $task1.Actions.Execute)"
Write-Host "Cycle 2 Execute: $($task2.Actions.Execute)"
Write-Host "Cycle 2 Path exists: $(Test-Path $task2.Actions.Execute)"

Write-Host ""
Write-Host "Done."
