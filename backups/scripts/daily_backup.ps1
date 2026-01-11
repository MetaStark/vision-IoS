# FjordHQ Tier 1-2 Daily Backup
# CEO Decision: 2026-01-11
# Runs via Windows Task Scheduler
#
# Purpose: Local backup + push to GitHub as versioned offsite copy

$ErrorActionPreference = "Stop"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = "$PSScriptRoot\..\backup.log"

function Log {
    param([string]$msg)
    $entry = "[$timestamp] $msg"
    Write-Host $entry
    Add-Content -Path $logFile -Value $entry
}

try {
    Log "=== BACKUP STARTED ==="

    # Navigate to repo
    Set-Location "C:\fhq-market-system\vision-ios"

    # Run Python backup script
    Log "Executing backup script..."
    python backups/scripts/backup_to_github.py
    if ($LASTEXITCODE -ne 0) {
        throw "Backup script failed with exit code $LASTEXITCODE"
    }

    # Git operations
    Log "Staging backup files..."
    git add backups/schema/*.sql
    git add backups/governance/*.json
    git add backups/evidence/*.json
    git add backups/*_manifest.json

    # Commit (will skip if no changes)
    $date = Get-Date -Format "yyyy-MM-dd"
    $commitMsg = "backup(tier1-2): Automated backup $date`n`nCo-Authored-By: STIG <stig@fjordhq.io>"

    git commit -m $commitMsg 2>$null
    if ($LASTEXITCODE -eq 0) {
        Log "Changes committed"

        # Push to GitHub
        Log "Pushing to GitHub..."
        git push origin master
        if ($LASTEXITCODE -ne 0) {
            throw "Git push failed"
        }
        Log "Push complete"
    } else {
        Log "No changes to commit"
    }

    Log "=== BACKUP COMPLETE ==="
    exit 0

} catch {
    Log "ERROR: $_"
    exit 1
}
