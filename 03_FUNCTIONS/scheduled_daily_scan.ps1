# FHQ Daily Scan - Volatility Observer + Micro-Regime Classifier
# Scheduled via Windows Task Scheduler
# Directive: CEO-DIR-2026-OPS-ALPHA-002A / CEO-DIR-2026-OPS-MICROREGIME-003
# Author: STIG (EC-003)

$ErrorActionPreference = "Continue"
$dateStr = Get-Date -Format "yyyyMMdd"
$workDir = "C:\fhq-market-system\vision-ios"
$logFile = Join-Path $workDir "03_FUNCTIONS\evidence\daily_scan_$dateStr.log"
$python = (Get-Command python | Select-Object -First 1).Source

function Write-Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$ts] $msg" | Out-File -Append -FilePath $logFile -Encoding utf8
}

Set-Location $workDir

Write-Log "============================================"
Write-Log "FHQ Daily Scan started"
Write-Log "============================================"

# 1. Volatility Observer
Write-Log "[1/2] Volatility Observer --scan"
$output1 = & $python "03_FUNCTIONS\volatility_observer.py" --scan 2>&1
$exit1 = $LASTEXITCODE
$output1 | Out-File -Append -FilePath $logFile -Encoding utf8
Write-Log "Exit code: $exit1"

# 2. Micro-Regime Classifier
Write-Log "[2/2] Micro-Regime Classifier --classify"
$output2 = & $python "03_FUNCTIONS\micro_regime_classifier.py" --classify 2>&1
$exit2 = $LASTEXITCODE
$output2 | Out-File -Append -FilePath $logFile -Encoding utf8
Write-Log "Exit code: $exit2"

Write-Log "============================================"
Write-Log "FHQ Daily Scan completed"
Write-Log "============================================"
