# FHQ LDOW Cycle Completion Daemon Runner
# Created: 2026-01-17
# Fixed: 2026-02-03 (DIR-005 DRP — added --cycle parameter)
# Purpose: Wrapper script for Windows Task Scheduler to run LDOW daemon

param(
    [int]$Cycle = 0
)

$ErrorActionPreference = "Continue"
$LogFile = "C:\fhq-market-system\vision-ios\03_FUNCTIONS\ldow_cycle_daemon.log"

# Log start
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $LogFile -Value "[$timestamp] LDOW Daemon Started via Task Scheduler"

# Change to working directory
Set-Location "C:\fhq-market-system\vision-ios\03_FUNCTIONS"

# Run the LDOW daemon with cycle argument
try {
    if ($Cycle -gt 0) {
        $output = python ldow_cycle_completion_daemon.py --cycle $Cycle 2>&1
    } else {
        # No cycle specified — run both sequentially (daemon handles idempotency)
        Add-Content -Path $LogFile -Value "[$timestamp] No --cycle specified, running both cycles"
        $output = python ldow_cycle_completion_daemon.py --cycle 1 2>&1
        $output2 = python ldow_cycle_completion_daemon.py --cycle 2 2>&1
        $output = @($output, $output2) -join "`n"
    }
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogFile -Value "[$timestamp] LDOW Output:"
    Add-Content -Path $LogFile -Value $output
    Add-Content -Path $LogFile -Value "[$timestamp] LDOW Daemon Completed Successfully"
}
catch {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogFile -Value "[$timestamp] LDOW Daemon ERROR: $_"
}
