# IoS-001 Daily Ingest - Windows Task Scheduler Setup
# Authority: CEO_DIRECTIVE_LINE_DAILY_INGEST_ACTIVATION_20251212
# Executor: LINE (EC-004)

$PythonPath = "python"
$ScriptPath = "C:\fhq-market-system\vision-ios\03_FUNCTIONS\ios001_daily_ingest.py"
$WorkDir = "C:\fhq-market-system\vision-ios"

Write-Host "=========================================="
Write-Host "IoS-001 DAILY INGEST SCHEDULER SETUP"
Write-Host "=========================================="

# CRYPTO - Daily at 02:00 CET (01:00 UTC)
Write-Host "`nCreating CRYPTO daily task (02:00 CET)..."
$cryptoAction = New-ScheduledTaskAction -Execute $PythonPath -Argument "$ScriptPath --asset-class CRYPTO --trigger-regime" -WorkingDirectory $WorkDir
$cryptoTrigger = New-ScheduledTaskTrigger -Daily -At 02:00
$cryptoSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName "FHQ_IOS001_CRYPTO_DAILY" -Action $cryptoAction -Trigger $cryptoTrigger -Settings $cryptoSettings -Description "IoS-001 Daily Crypto Price Ingest" -Force

# EQUITY - Weekdays at 23:00 CET (22:00 UTC)
Write-Host "Creating EQUITY weekday task (23:00 CET Mon-Fri)..."
$equityAction = New-ScheduledTaskAction -Execute $PythonPath -Argument "$ScriptPath --asset-class EQUITY --trigger-regime" -WorkingDirectory $WorkDir
$equityTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 23:00
$equitySettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName "FHQ_IOS001_EQUITY_DAILY" -Action $equityAction -Trigger $equityTrigger -Settings $equitySettings -Description "IoS-001 Daily Equity Price Ingest (Weekdays)" -Force

# FX - Sun-Thu at 23:00 CET (22:00 UTC)
Write-Host "Creating FX task (23:00 CET Sun-Thu)..."
$fxAction = New-ScheduledTaskAction -Execute $PythonPath -Argument "$ScriptPath --asset-class FX --trigger-regime" -WorkingDirectory $WorkDir
$fxTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday,Monday,Tuesday,Wednesday,Thursday -At 23:00
$fxSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName "FHQ_IOS001_FX_DAILY" -Action $fxAction -Trigger $fxTrigger -Settings $fxSettings -Description "IoS-001 Daily FX Price Ingest (Sun-Thu)" -Force

Write-Host "`n=========================================="
Write-Host "SCHEDULED TASKS CREATED"
Write-Host "=========================================="
Write-Host "FHQ_IOS001_CRYPTO_DAILY  - Daily 02:00 CET"
Write-Host "FHQ_IOS001_EQUITY_DAILY  - Mon-Fri 23:00 CET"
Write-Host "FHQ_IOS001_FX_DAILY      - Sun-Thu 23:00 CET"
Write-Host "=========================================="

# Verify tasks
Write-Host "`nVerifying scheduled tasks..."
Get-ScheduledTask | Where-Object {$_.TaskName -like "FHQ_IOS001*"} | Format-Table TaskName, State, Description
