# FjordHQ Dashboard - Permanent Uptime Startup Script
# CD-EXEC-PERMANENT-UPTIME: Always run on localhost:3000
#
# Usage: .\start-dashboard.ps1
# Or add to Windows Task Scheduler for auto-start on boot

$ErrorActionPreference = "Stop"
$DashboardPath = $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "FjordHQ Dashboard - Permanent Uptime" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting on http://localhost:3000"
Write-Host ""

# Kill any existing process on port 3000
$existingProcess = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if ($existingProcess) {
    Write-Host "Killing existing process on port 3000..." -ForegroundColor Yellow
    Stop-Process -Id $existingProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# Clean stale build files
Write-Host "Cleaning stale build files..." -ForegroundColor Yellow
Remove-Item -Path "$DashboardPath\.next" -Recurse -Force -ErrorAction SilentlyContinue

# Start the dev server
Write-Host "Starting Next.js dev server..." -ForegroundColor Green
Set-Location $DashboardPath

# Run with auto-restart on crash
while ($true) {
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Starting dashboard..." -ForegroundColor Cyan

    try {
        npm run dev
    }
    catch {
        Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Dashboard crashed: $_" -ForegroundColor Red
    }

    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Dashboard stopped. Restarting in 5 seconds..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}
