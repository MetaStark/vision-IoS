# Create FjordHQ Daemon Watchdog Task
$Action = New-ScheduledTaskAction -Execute "pythonw" -Argument "`"C:\fhq-market-system\vision-ios\03_FUNCTIONS\daemon_watchdog.py`""
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName "FjordHQ_Daemon_Watchdog" -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force

Write-Host "Task created. Starting now..."
Start-ScheduledTask -TaskName "FjordHQ_Daemon_Watchdog"
Start-Sleep -Seconds 3
Get-ScheduledTask -TaskName "FjordHQ_Daemon_Watchdog" | Select-Object TaskName, State
(Get-ScheduledTask -TaskName "FjordHQ_Daemon_Watchdog").Actions | Select-Object Execute, Arguments
