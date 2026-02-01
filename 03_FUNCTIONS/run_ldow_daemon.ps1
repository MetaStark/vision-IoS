# FHQ LDOW Cycle Completion Daemon Runner
# Created: 2026-01-17
# Purpose: Wrapper script for Windows Task Scheduler to run LDOW daemon
# Runs daily at 01:30 to evaluate forecasts from previous cycle

$ErrorActionPreference = "Continue"
$LogFile = "C:\fhq-market-system\vision-ios\03_FUNCTIONS\ldow_cycle_daemon.log"

# Log start
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $LogFile -Value "[$timestamp] LDOW Daemon Started via Task Scheduler"

# Change to working directory
Set-Location "C:\fhq-market-system\vision-ios\03_FUNCTIONS"

# Run the LDOW daemon
try {
    $output = python ldow_cycle_completion_daemon.py 2>&1
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogFile -Value "[$timestamp] LDOW Output:"
    Add-Content -Path $LogFile -Value $output
    Add-Content -Path $LogFile -Value "[$timestamp] LDOW Daemon Completed Successfully"
}
catch {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogFile -Value "[$timestamp] LDOW Daemon ERROR: $_"
}
