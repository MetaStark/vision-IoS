<#
.SYNOPSIS
    FHQ Services Setup - NSSM-based Windows Services

.DESCRIPTION
    Installs and manages all FHQ background services using NSSM (Non-Sucking Service Manager).
    These services run persistently in the background, restart on failure, and survive reboots.

    Services:
    1. FHQ-Streamer       - Market data ingestion (market_streamer_v2.py)
    2. FHQ-G2C-Daemon     - Forecast generation, resolution, skill metrics (g2c_alpha_daemon.py)
    3. FHQ-Daily-Ingest   - Daily OHLCV batch ingestion (scheduled task, not NSSM)

.PARAMETER Install
    Install all services

.PARAMETER Uninstall
    Remove all services

.PARAMETER Status
    Check status of all services

.PARAMETER Start
    Start all services

.PARAMETER Stop
    Stop all services

.PARAMETER Restart
    Restart all services

.PARAMETER InstallNSSM
    Download and install NSSM if not present

.EXAMPLE
    .\setup_fhq_services.ps1 -InstallNSSM
    .\setup_fhq_services.ps1 -Install
    .\setup_fhq_services.ps1 -Status

.NOTES
    Authority: ADR-007, ADR-013, CEO Directive CD-G2C-ALPHA-IGNITION-48H
    Owner: STIG (CTO)
#>

[CmdletBinding()]
param(
    [switch]$Install,
    [switch]$Uninstall,
    [switch]$Status,
    [switch]$Start,
    [switch]$Stop,
    [switch]$Restart,
    [switch]$InstallNSSM
)

$ErrorActionPreference = "Continue"

# =============================================================================
# CONFIGURATION
# =============================================================================

$VisionIosRoot = "C:\fhq-market-system\vision-ios"
$LogPath = Join-Path $VisionIosRoot "logs"
$NSSMPath = "C:\tools\nssm\nssm.exe"
$PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonPath) { $PythonPath = "python" }

# Service definitions
$Services = @(
    @{
        Name = "FHQ-Streamer"
        DisplayName = "FHQ Market Streamer"
        Description = "Persistent market data ingestion service - ARO-20251209"
        Script = Join-Path $VisionIosRoot "03_FUNCTIONS\market_streamer_v2.py"
        LogFile = Join-Path $LogPath "fhq_streamer_nssm.log"
        Enabled = $true
    },
    @{
        Name = "FHQ-G2C-Daemon"
        DisplayName = "FHQ G2-C Alpha Daemon"
        Description = "Forecast generation, resolution, skill metrics - CD-G2C-ALPHA-IGNITION"
        Script = Join-Path $VisionIosRoot "03_FUNCTIONS\g2c_alpha_daemon.py"
        LogFile = Join-Path $LogPath "g2c_alpha_daemon_nssm.log"
        Enabled = $true
    }
)

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor Blue
    Write-Host " $Message" -ForegroundColor White
    Write-Host ("=" * 70) -ForegroundColor Blue
    Write-Host ""
}

function Write-ServiceStatus {
    param(
        [string]$Name,
        [string]$Status,
        [string]$Color = "White"
    )
    $statusIcon = switch ($Status) {
        "Running" { "[OK]" }
        "Stopped" { "[--]" }
        "Not Installed" { "[XX]" }
        default { "[??]" }
    }
    Write-Host "  $statusIcon " -ForegroundColor $Color -NoNewline
    Write-Host "$Name" -NoNewline
    Write-Host " - $Status" -ForegroundColor $Color
}

function Test-NSSMInstalled {
    if (Test-Path $NSSMPath) {
        return $true
    }
    # Check if nssm is in PATH
    $nssm = Get-Command nssm -ErrorAction SilentlyContinue
    if ($nssm) {
        $script:NSSMPath = $nssm.Source
        return $true
    }
    return $false
}

function Install-NSSM {
    Write-Header "Installing NSSM (Non-Sucking Service Manager)"

    $nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
    $downloadPath = Join-Path $env:TEMP "nssm.zip"
    $extractPath = Join-Path $env:TEMP "nssm-extract"
    $targetDir = "C:\tools\nssm"

    Write-Host "Downloading NSSM..." -ForegroundColor Cyan
    try {
        Invoke-WebRequest -Uri $nssmUrl -OutFile $downloadPath -UseBasicParsing
    }
    catch {
        Write-Host "Failed to download NSSM. Please download manually from https://nssm.cc" -ForegroundColor Red
        Write-Host "Extract nssm.exe to $targetDir" -ForegroundColor Yellow
        return $false
    }

    Write-Host "Extracting..." -ForegroundColor Cyan
    Expand-Archive -Path $downloadPath -DestinationPath $extractPath -Force

    # Find the correct nssm.exe (64-bit if available)
    $nssmExe = Get-ChildItem -Path $extractPath -Recurse -Filter "nssm.exe" |
        Where-Object { $_.DirectoryName -like "*win64*" } |
        Select-Object -First 1

    if (-not $nssmExe) {
        $nssmExe = Get-ChildItem -Path $extractPath -Recurse -Filter "nssm.exe" |
            Select-Object -First 1
    }

    if (-not $nssmExe) {
        Write-Host "Could not find nssm.exe in archive" -ForegroundColor Red
        return $false
    }

    # Create target directory and copy
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    Copy-Item $nssmExe.FullName -Destination $NSSMPath -Force

    # Cleanup
    Remove-Item $downloadPath -Force -ErrorAction SilentlyContinue
    Remove-Item $extractPath -Recurse -Force -ErrorAction SilentlyContinue

    Write-Host "NSSM installed to $NSSMPath" -ForegroundColor Green
    return $true
}

# =============================================================================
# SERVICE MANAGEMENT FUNCTIONS
# =============================================================================

function Get-ServiceStatus {
    param([hashtable]$ServiceDef)

    try {
        $svc = Get-Service -Name $ServiceDef.Name -ErrorAction SilentlyContinue
        if ($svc) {
            return $svc.Status.ToString()
        }
    } catch {}

    return "Not Installed"
}

function Install-FHQService {
    param([hashtable]$ServiceDef)

    if (-not $ServiceDef.Enabled) {
        Write-Host "  Skipping $($ServiceDef.Name) (disabled)" -ForegroundColor Yellow
        return
    }

    if (-not (Test-Path $ServiceDef.Script)) {
        Write-Host "  ERROR: Script not found: $($ServiceDef.Script)" -ForegroundColor Red
        return
    }

    Write-Host "  Installing $($ServiceDef.Name)..." -ForegroundColor Cyan

    # Remove if exists
    $existingSvc = Get-Service -Name $ServiceDef.Name -ErrorAction SilentlyContinue
    if ($existingSvc) {
        Write-Host "    Removing existing service..." -ForegroundColor Yellow
        & $NSSMPath stop $ServiceDef.Name 2>$null
        & $NSSMPath remove $ServiceDef.Name confirm 2>$null
        Start-Sleep -Seconds 2
    }

    # Install service
    & $NSSMPath install $ServiceDef.Name $PythonPath "`"$($ServiceDef.Script)`""

    # Configure service
    & $NSSMPath set $ServiceDef.Name DisplayName $ServiceDef.DisplayName
    & $NSSMPath set $ServiceDef.Name Description $ServiceDef.Description
    & $NSSMPath set $ServiceDef.Name AppDirectory $VisionIosRoot
    & $NSSMPath set $ServiceDef.Name AppStdout $ServiceDef.LogFile
    & $NSSMPath set $ServiceDef.Name AppStderr $ServiceDef.LogFile
    & $NSSMPath set $ServiceDef.Name AppStdoutCreationDisposition 4  # Append
    & $NSSMPath set $ServiceDef.Name AppStderrCreationDisposition 4  # Append
    & $NSSMPath set $ServiceDef.Name AppRotateFiles 1
    & $NSSMPath set $ServiceDef.Name AppRotateBytes 10485760  # 10MB
    & $NSSMPath set $ServiceDef.Name AppRestartDelay 3000  # 3 seconds
    & $NSSMPath set $ServiceDef.Name Start SERVICE_AUTO_START

    Write-Host "    Service installed!" -ForegroundColor Green
}

function Uninstall-FHQService {
    param([hashtable]$ServiceDef)

    $status = Get-ServiceStatus $ServiceDef
    if ($status -eq "Not Installed") {
        Write-Host "  $($ServiceDef.Name) not installed, skipping" -ForegroundColor Yellow
        return
    }

    Write-Host "  Removing $($ServiceDef.Name)..." -ForegroundColor Cyan
    & $NSSMPath stop $ServiceDef.Name 2>$null
    & $NSSMPath remove $ServiceDef.Name confirm 2>$null
    Write-Host "    Removed!" -ForegroundColor Green
}

function Start-FHQService {
    param([hashtable]$ServiceDef)

    $status = Get-ServiceStatus $ServiceDef
    if ($status -eq "Not Installed") {
        Write-Host "  $($ServiceDef.Name) not installed" -ForegroundColor Yellow
        return
    }

    if ($status -eq "Running") {
        Write-Host "  $($ServiceDef.Name) already running" -ForegroundColor Green
        return
    }

    Write-Host "  Starting $($ServiceDef.Name)..." -ForegroundColor Cyan
    & $NSSMPath start $ServiceDef.Name
    Start-Sleep -Seconds 2

    $newStatus = Get-ServiceStatus $ServiceDef
    if ($newStatus -eq "Running") {
        Write-Host "    Started!" -ForegroundColor Green
    } else {
        Write-Host "    Failed to start (status: $newStatus)" -ForegroundColor Red
    }
}

function Stop-FHQService {
    param([hashtable]$ServiceDef)

    $status = Get-ServiceStatus $ServiceDef
    if ($status -ne "Running") {
        Write-Host "  $($ServiceDef.Name) not running" -ForegroundColor Yellow
        return
    }

    Write-Host "  Stopping $($ServiceDef.Name)..." -ForegroundColor Cyan
    & $NSSMPath stop $ServiceDef.Name
    Write-Host "    Stopped!" -ForegroundColor Green
}

# =============================================================================
# MAIN ACTIONS
# =============================================================================

function Show-AllStatus {
    Write-Header "FHQ Services Status"

    $nssmInstalled = Test-NSSMInstalled
    Write-Host "NSSM: $(if ($nssmInstalled) { 'Installed' } else { 'NOT INSTALLED' })" -ForegroundColor $(if ($nssmInstalled) { 'Green' } else { 'Red' })
    Write-Host ""
    Write-Host "Services:" -ForegroundColor Cyan

    foreach ($svc in $Services) {
        $status = Get-ServiceStatus $svc
        $color = switch ($status) {
            "Running" { "Green" }
            "Stopped" { "Yellow" }
            default { "Red" }
        }
        Write-ServiceStatus -Name $svc.Name -Status $status -Color $color
    }

    Write-Host ""
    Write-Host "Log files:" -ForegroundColor Cyan
    foreach ($svc in $Services) {
        if (Test-Path $svc.LogFile) {
            $logInfo = Get-Item $svc.LogFile
            Write-Host "  $($svc.Name): $($logInfo.Name) ($('{0:N0}' -f ($logInfo.Length / 1KB)) KB)"
        }
    }
    Write-Host ""
}

function Install-AllServices {
    Write-Header "Installing FHQ Services"

    if (-not (Test-NSSMInstalled)) {
        Write-Host "NSSM is not installed. Run: .\setup_fhq_services.ps1 -InstallNSSM" -ForegroundColor Red
        return
    }

    # Ensure log directory exists
    if (-not (Test-Path $LogPath)) {
        New-Item -ItemType Directory -Path $LogPath -Force | Out-Null
    }

    foreach ($svc in $Services) {
        Install-FHQService $svc
    }

    Write-Host ""
    Write-Host "Installation complete!" -ForegroundColor Green
    Write-Host "Starting services..." -ForegroundColor Cyan

    foreach ($svc in $Services) {
        if ($svc.Enabled) {
            Start-FHQService $svc
        }
    }

    Write-Host ""
    Show-AllStatus
}

function Uninstall-AllServices {
    Write-Header "Uninstalling FHQ Services"

    if (-not (Test-NSSMInstalled)) {
        Write-Host "NSSM is not installed" -ForegroundColor Yellow
        return
    }

    foreach ($svc in $Services) {
        Uninstall-FHQService $svc
    }

    Write-Host ""
    Write-Host "All services removed!" -ForegroundColor Green
}

function Start-AllServices {
    Write-Header "Starting FHQ Services"

    foreach ($svc in $Services) {
        Start-FHQService $svc
    }

    Write-Host ""
    Show-AllStatus
}

function Stop-AllServices {
    Write-Header "Stopping FHQ Services"

    foreach ($svc in $Services) {
        Stop-FHQService $svc
    }
}

function Restart-AllServices {
    Write-Header "Restarting FHQ Services"

    foreach ($svc in $Services) {
        Stop-FHQService $svc
    }

    Start-Sleep -Seconds 2

    foreach ($svc in $Services) {
        Start-FHQService $svc
    }

    Write-Host ""
    Show-AllStatus
}

# =============================================================================
# MAIN
# =============================================================================

if ($InstallNSSM) {
    if (Test-NSSMInstalled) {
        Write-Host "NSSM is already installed at $NSSMPath" -ForegroundColor Green
    } else {
        Install-NSSM
    }
}
elseif ($Install) {
    Install-AllServices
}
elseif ($Uninstall) {
    Uninstall-AllServices
}
elseif ($Status) {
    Show-AllStatus
}
elseif ($Start) {
    Start-AllServices
}
elseif ($Stop) {
    Stop-AllServices
}
elseif ($Restart) {
    Restart-AllServices
}
else {
    Write-Header "FHQ Services Manager"
    Write-Host "Usage:" -ForegroundColor Cyan
    Write-Host "  .\setup_fhq_services.ps1 -InstallNSSM  # Download and install NSSM"
    Write-Host "  .\setup_fhq_services.ps1 -Install      # Install all services"
    Write-Host "  .\setup_fhq_services.ps1 -Uninstall    # Remove all services"
    Write-Host "  .\setup_fhq_services.ps1 -Status       # Check status"
    Write-Host "  .\setup_fhq_services.ps1 -Start        # Start all services"
    Write-Host "  .\setup_fhq_services.ps1 -Stop         # Stop all services"
    Write-Host "  .\setup_fhq_services.ps1 -Restart      # Restart all services"
    Write-Host ""
    Write-Host "Services managed:" -ForegroundColor Cyan
    foreach ($svc in $Services) {
        $enabled = if ($svc.Enabled) { "enabled" } else { "disabled" }
        Write-Host "  - $($svc.Name): $($svc.Description) [$enabled]"
    }
    Write-Host ""
    Write-Host "First-time setup:" -ForegroundColor Yellow
    Write-Host "  1. .\setup_fhq_services.ps1 -InstallNSSM"
    Write-Host "  2. .\setup_fhq_services.ps1 -Install"
    Write-Host ""
}
