<#
.SYNOPSIS
    Vision-IoS Setup Script for Windows PowerShell

.DESCRIPTION
    This script pulls the latest governance artifacts and sets up the Vision-IoS environment.

    Features:
    - Pulls latest changes from governance branch
    - Verifies governance artifacts (G1, G2, G3 files)
    - Checks Python environment
    - Displays system status

.PARAMETER Pull
    Pull latest changes from remote

.PARAMETER Verify
    Verify governance artifacts only

.PARAMETER Status
    Show current system status

.EXAMPLE
    .\setup.ps1 -Pull
    .\setup.ps1 -Verify
    .\setup.ps1 -Status

.NOTES
    Authority: CODE Team
    Reference: HC-CODE-G3-CORRECTION-20251124
    Status: G3 Pre-Audit State
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [switch]$Pull,

    [Parameter(Mandatory=$false)]
    [switch]$Verify,

    [Parameter(Mandatory=$false)]
    [switch]$Status,

    [Parameter(Mandatory=$false)]
    [switch]$Init
)

# Colors for output
function Write-Success { Write-Host "✅ $args" -ForegroundColor Green }
function Write-Info { Write-Host "ℹ️  $args" -ForegroundColor Cyan }
function Write-Warning { Write-Host "⚠️  $args" -ForegroundColor Yellow }
function Write-Error { Write-Host "❌ $args" -ForegroundColor Red }
function Write-Header {
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Blue
    Write-Host " $args" -ForegroundColor White
    Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Blue
    Write-Host ""
}

# Main setup function
function Invoke-Setup {
    Write-Header "VISION-IOS SETUP (G3 PRE-AUDIT STATE)"

    Write-Info "Repository: MetaStark/vision-IoS"
    Write-Info "Branch: claude/review-governance-directive-01Ybe9eqjHD9fk2ePLffJyu8"
    Write-Info "Status: 🟡 G3-READY (Governance frozen)"
    Write-Host ""

    # Check git
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Error "Git is not installed or not in PATH"
        return 1
    }
    Write-Success "Git found: $(git --version)"

    # Check Python
    if (Get-Command python -ErrorAction SilentlyContinue) {
        Write-Success "Python found: $(python --version)"
    } else {
        Write-Warning "Python not found (optional for initialization)"
    }

    Write-Host ""
    return 0
}

# Pull latest changes
function Invoke-GitPull {
    Write-Header "PULLING LATEST GOVERNANCE ARTIFACTS"

    try {
        # Check current branch
        $currentBranch = git branch --show-current
        Write-Info "Current branch: $currentBranch"

        # Fetch latest
        Write-Info "Fetching from remote..."
        git fetch origin

        # Pull governance branch
        $targetBranch = "claude/review-governance-directive-01Ybe9eqjHD9fk2ePLffJyu8"

        if ($currentBranch -ne $targetBranch) {
            Write-Warning "Switching to governance branch: $targetBranch"
            git checkout $targetBranch
        }

        Write-Info "Pulling latest changes..."
        git pull origin $targetBranch

        Write-Success "Pull completed successfully!"

        # Show latest commit
        Write-Host ""
        Write-Info "Latest commit:"
        git log -1 --oneline

        return 0
    }
    catch {
        Write-Error "Git pull failed: $_"
        return 1
    }
}

# Verify governance artifacts
function Test-GovernanceArtifacts {
    Write-Header "VERIFYING GOVERNANCE ARTIFACTS"

    $requiredFiles = @(
        "05_GOVERNANCE/FINN_TIER2_MANDATE.md",
        "05_GOVERNANCE/FINN_PHASE2_ROADMAP.md",
        "05_GOVERNANCE/G1_STIG_PASS_DECISION.md",
        "05_GOVERNANCE/G2_LARS_GOVERNANCE_MATERIALS.md",
        "05_GOVERNANCE/G3_VEGA_TRANSITION_RECORD.md",
        "05_GOVERNANCE/CODE_G3_VERIFICATION_COMPLETE.md"
    )

    $allPresent = $true

    foreach ($file in $requiredFiles) {
        if (Test-Path $file) {
            $size = (Get-Item $file).Length
            $sizeKB = [math]::Round($size / 1KB, 1)
            Write-Success "$file ($sizeKB KB)"
        } else {
            Write-Error "MISSING: $file"
            $allPresent = $false
        }
    }

    Write-Host ""

    if ($allPresent) {
        Write-Success "All 6 governance files present ✓"
        Write-Info "System is G3-READY"
        return 0
    } else {
        Write-Error "Governance artifacts incomplete!"
        Write-Warning "Run: .\setup.ps1 -Pull"
        return 1
    }
}

# Show system status
function Show-SystemStatus {
    Write-Header "VISION-IOS SYSTEM STATUS"

    # Git status
    Write-Info "Git Repository Status:"
    git status --short --branch
    Write-Host ""

    # Recent commits
    Write-Info "Recent Commits:"
    git log --oneline -5
    Write-Host ""

    # Governance files
    Write-Info "Governance Files (05_GOVERNANCE/):"
    if (Test-Path "05_GOVERNANCE") {
        Get-ChildItem "05_GOVERNANCE/*.md" | ForEach-Object {
            $size = [math]::Round($_.Length / 1KB, 1)
            Write-Host "  • $($_.Name) ($size KB)"
        }
    } else {
        Write-Warning "05_GOVERNANCE/ directory not found"
    }
    Write-Host ""

    # ADR foundation
    Write-Info "ADR Foundation (00_CONSTITUTION/):"
    if (Test-Path "00_CONSTITUTION") {
        $adrCount = (Get-ChildItem "00_CONSTITUTION/ADR-*.md" -ErrorAction SilentlyContinue).Count
        Write-Host "  • $adrCount ADR files found"
    } else {
        Write-Warning "00_CONSTITUTION/ directory not found"
    }
    Write-Host ""

    # Operational mode
    Write-Info "Operational Mode: 🟡 REACTIVE STANDBY (G3 Pre-Audit)"
    Write-Warning "No changes permitted until VEGA completes G3 audit"
    Write-Host ""

    return 0
}

# Initialize Vision-IoS (run Python script)
function Invoke-Initialize {
    Write-Header "INITIALIZING VISION-IOS"

    if (-not (Test-Path "init_vision_ios.py")) {
        Write-Error "init_vision_ios.py not found!"
        return 1
    }

    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Error "Python is required for initialization"
        Write-Info "Install Python from: https://www.python.org/downloads/"
        return 1
    }

    Write-Info "Running initialization script..."
    python init_vision_ios.py --yes

    return $LASTEXITCODE
}

# Main execution
function Main {
    # If no parameters, show usage
    if (-not ($Pull -or $Verify -or $Status -or $Init)) {
        Write-Header "VISION-IOS SETUP SCRIPT"
        Write-Host "Usage:"
        Write-Host "  .\setup.ps1 -Pull      # Pull latest governance artifacts"
        Write-Host "  .\setup.ps1 -Verify    # Verify governance files"
        Write-Host "  .\setup.ps1 -Status    # Show system status"
        Write-Host "  .\setup.ps1 -Init      # Initialize Vision-IoS (run Python script)"
        Write-Host ""
        Write-Host "Examples:"
        Write-Host "  .\setup.ps1 -Pull      # Most common: get latest changes"
        Write-Host "  .\setup.ps1 -Verify    # Check if all governance files present"
        Write-Host ""
        Write-Info "Quick Start: .\setup.ps1 -Pull"
        Write-Host ""
        return 0
    }

    # Run initial setup check
    $setupResult = Invoke-Setup
    if ($setupResult -ne 0) {
        return $setupResult
    }

    # Execute requested operations
    if ($Pull) {
        $result = Invoke-GitPull
        if ($result -ne 0) { return $result }
        Write-Host ""
        # Auto-verify after pull
        Test-GovernanceArtifacts | Out-Null
    }

    if ($Verify) {
        $result = Test-GovernanceArtifacts
        if ($result -ne 0) { return $result }
    }

    if ($Status) {
        Show-SystemStatus
    }

    if ($Init) {
        $result = Invoke-Initialize
        if ($result -ne 0) { return $result }
    }

    Write-Host ""
    Write-Success "Setup complete!"
    Write-Host ""

    return 0
}

# Execute
exit (Main)
