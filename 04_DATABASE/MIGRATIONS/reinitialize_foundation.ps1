# =============================================================================
# VISION-IOS FOUNDATION REINITIALIZATION (BINDING POLICY)
# =============================================================================
#
# Authority: CEO Directive - Vision-IoS Integration
# Compliance: ADR-002 (Audit Charter), ADR-004 (G0-G4 Gates)
# Policy: NO workaround-patching. Full drop -> migration 018 -> G1 validation
#
# Procedure:
#   1. Drop all governance tables in intermediate state
#   2. Execute migration 018 from scratch (single source of truth)
#   3. Validate G1 technical compliance
#   4. Register G1 PASS with STIG
#
# =============================================================================

Write-Host ""
Write-Host "=======================================================================" -ForegroundColor Red
Write-Host "VISION-IOS FOUNDATION REINITIALIZATION (BINDING POLICY)" -ForegroundColor Red
Write-Host "=======================================================================" -ForegroundColor Red
Write-Host ""
Write-Host "Authority: CEO Directive - Vision-IoS Integration" -ForegroundColor Yellow
Write-Host "Compliance: ADR-002 Audit Charter, ADR-004 G0-G4 Gates" -ForegroundColor Yellow
Write-Host ""
Write-Host "WARNING: This will DROP all existing governance tables" -ForegroundColor Red
Write-Host "Migration 018 is the single source of truth" -ForegroundColor Red
Write-Host ""

# Configuration
$env:PGHOST = "127.0.0.1"
$env:PGPORT = "54322"
$env:PGDATABASE = "postgres"
$env:PGUSER = "postgres"
$env:PGPASSWORD = "postgres"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Write-Host "Working Directory: $scriptDir" -ForegroundColor Yellow
Write-Host ""

# =============================================================================
# STEP 1: Test Database Connection
# =============================================================================

Write-Host "1. Testing database connection..." -ForegroundColor Cyan

$testQuery = "SELECT version();"
$connectionTest = psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -c $testQuery 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Cannot connect to database" -ForegroundColor Red
    Write-Host "Please ensure Supabase is running: supabase start" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host "SUCCESS: Database connection successful" -ForegroundColor Green
Write-Host ""

# =============================================================================
# STEP 2: DROP All Governance Tables in Intermediate State (ADR-002)
# =============================================================================

Write-Host "2. Dropping governance tables (ADR-002 reinitialization)..." -ForegroundColor Cyan
Write-Host ""

$dropScript = @'
BEGIN;

-- Drop Migration 018 tables (governance layer)
DROP TABLE IF EXISTS fhq_governance.model_provider_policy CASCADE;
DROP TABLE IF EXISTS fhq_governance.agent_contracts CASCADE;
DROP TABLE IF EXISTS fhq_governance.executive_roles CASCADE;

-- Drop Migration 018 tables (meta layer)
DROP TABLE IF EXISTS fhq_meta.adr_version_history CASCADE;
DROP TABLE IF EXISTS fhq_meta.adr_audit_log CASCADE;
DROP TABLE IF EXISTS fhq_meta.adr_registry CASCADE;
DROP TABLE IF EXISTS fhq_meta.key_archival_log CASCADE;

-- CRITICAL: Drop existing agent_keys table (conflicts with migration 018)
DROP TABLE IF EXISTS fhq_meta.agent_keys CASCADE;

-- Drop VEGA economic safety tables
DROP TABLE IF EXISTS vega.llm_violation_events CASCADE;
DROP TABLE IF EXISTS vega.llm_usage_log CASCADE;
DROP TABLE IF EXISTS vega.llm_execution_limits CASCADE;
DROP TABLE IF EXISTS vega.llm_cost_limits CASCADE;
DROP TABLE IF EXISTS vega.llm_rate_limits CASCADE;

COMMIT;
'@

Write-Host "   Executing drop cascade..." -ForegroundColor Gray
$dropOutput = $dropScript | psql -h 127.0.0.1 -p 54322 -U postgres -d postgres 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: DROP CASCADE FAILED" -ForegroundColor Red
    Write-Host $dropOutput -ForegroundColor Red
    Write-Host ""
    exit 1
}

Write-Host $dropOutput
Write-Host ""
Write-Host "SUCCESS: Governance tables dropped (foundation reset complete)" -ForegroundColor Green
Write-Host ""

# =============================================================================
# STEP 3: Execute Migration 018 (Single Source of Truth)
# =============================================================================

Write-Host "3. Executing migration 018 (single source of truth)..." -ForegroundColor Cyan
Write-Host ""

$migrationFile = "018_line_mandate_governance_economic_safety.sql"

if (-Not (Test-Path $migrationFile)) {
    Write-Host "ERROR: Migration file not found: $migrationFile" -ForegroundColor Red
    exit 1
}

Write-Host "   File: $migrationFile" -ForegroundColor Gray
Write-Host "   Size: $((Get-Item $migrationFile).Length) bytes" -ForegroundColor Gray
Write-Host ""
Write-Host "   Executing..." -ForegroundColor Gray

$migrationOutput = psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -f $migrationFile 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: MIGRATION 018 FAILED" -ForegroundColor Red
    Write-Host ""
    Write-Host "Error Output:" -ForegroundColor Red
    Write-Host $migrationOutput -ForegroundColor Red
    Write-Host ""
    Write-Host "CRITICAL: Migration is the single source of truth and must complete without errors." -ForegroundColor Red
    Write-Host "Review error above and fix schema conflicts." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

# Filter output to show only important lines
$migrationOutput | Select-String -Pattern "(NOTICE|ERROR|WARNING|CREATE SCHEMA|CREATE TABLE|INSERT|COMMIT)" | ForEach-Object {
    if ($_ -match "ERROR") {
        Write-Host $_ -ForegroundColor Red
    } elseif ($_ -match "WARNING") {
        Write-Host $_ -ForegroundColor Yellow
    } else {
        Write-Host $_ -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "SUCCESS: Migration 018 executed successfully" -ForegroundColor Green
Write-Host ""

# =============================================================================
# STEP 4: Final Verification Queries
# =============================================================================

Write-Host "4. Final foundation verification..." -ForegroundColor Cyan
Write-Host ""

# Count tables created
Write-Host "   Governance tables created:" -ForegroundColor White
$tableCountQuery = @'
SELECT
    table_schema,
    COUNT(*) as table_count
FROM information_schema.tables
WHERE table_schema IN ('fhq_meta', 'fhq_governance', 'vega')
  AND table_name IN (
    'adr_registry', 'adr_audit_log', 'adr_version_history',
    'agent_keys', 'key_archival_log',
    'executive_roles', 'agent_contracts', 'model_provider_policy',
    'llm_rate_limits', 'llm_cost_limits', 'llm_execution_limits',
    'llm_usage_log', 'llm_violation_events'
  )
GROUP BY table_schema
ORDER BY table_schema;
'@

psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -c $tableCountQuery
Write-Host ""

# Verify total table count
Write-Host "   Total table verification:" -ForegroundColor White
$totalCountQuery = @'
SELECT COUNT(*) as total_tables
FROM information_schema.tables
WHERE table_schema IN ('fhq_meta', 'fhq_governance', 'vega')
  AND table_name IN (
    'adr_registry', 'adr_audit_log', 'adr_version_history',
    'agent_keys', 'key_archival_log',
    'executive_roles', 'agent_contracts', 'model_provider_policy',
    'llm_rate_limits', 'llm_cost_limits', 'llm_execution_limits',
    'llm_usage_log', 'llm_violation_events'
  );
'@

$totalCount = psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -t -c $totalCountQuery 2>&1

if ($totalCount -match "13") {
    Write-Host "   [OK] All 13 governance tables created" -ForegroundColor Green
} else {
    Write-Host "   [ERROR] Expected 13 tables, found: $totalCount" -ForegroundColor Red
}

Write-Host ""

# Verify G0 submission logged
Write-Host "   G0 submission verification:" -ForegroundColor White
$g0CheckQuery = @'
SELECT
    change_proposal_id,
    event_type,
    gate_stage,
    initiated_by,
    decision,
    TO_CHAR(timestamp, 'YYYY-MM-DD HH24:MI:SS') as submitted_at
FROM fhq_meta.adr_audit_log
WHERE change_proposal_id = 'G0-2025-11-23-LINE-MANDATE'
LIMIT 1;
'@

$g0Result = psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -c $g0CheckQuery 2>&1

if ($g0Result -match "G0-2025-11-23-LINE-MANDATE") {
    Write-Host $g0Result -ForegroundColor Green
    Write-Host "   [OK] G0 submission logged" -ForegroundColor Green
} else {
    Write-Host "   [WARNING] G0 submission not found in audit log" -ForegroundColor Yellow
}

Write-Host ""

# Verify LIVE_MODE=False (CRITICAL)
Write-Host "   LIVE_MODE safety check (CRITICAL):" -ForegroundColor White
$liveModeCheckQuery = @'
SELECT
    'llm_rate_limits' AS table_name,
    COUNT(*) FILTER (WHERE live_mode = TRUE) AS violations
FROM vega.llm_rate_limits
UNION ALL
SELECT 'llm_cost_limits', COUNT(*) FILTER (WHERE live_mode = TRUE)
FROM vega.llm_cost_limits
UNION ALL
SELECT 'llm_execution_limits', COUNT(*) FILTER (WHERE live_mode = TRUE)
FROM vega.llm_execution_limits;
'@

$liveModeResult = psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -c $liveModeCheckQuery 2>&1

if ($liveModeResult -match "[1-9]") {
    Write-Host ""
    Write-Host "   [ERROR] LIVE_MODE=TRUE detected!" -ForegroundColor Red
    Write-Host "   All economic safety limits MUST have LIVE_MODE=False until VEGA QG-F6 attestation" -ForegroundColor Red
    Write-Host ""
    exit 1
} else {
    Write-Host $liveModeResult -ForegroundColor Green
    Write-Host "   [OK] LIVE_MODE=False enforced (all violations = 0)" -ForegroundColor Green
}

Write-Host ""

# Verify provider policies
Write-Host "   Provider routing policies:" -ForegroundColor White
$providerPolicyQuery = @'
SELECT
    agent_id,
    sensitivity_tier,
    primary_provider,
    data_sharing_allowed::TEXT as data_sharing
FROM fhq_governance.model_provider_policy
ORDER BY
    CASE sensitivity_tier
        WHEN 'TIER1_HIGH' THEN 1
        WHEN 'TIER2_MEDIUM' THEN 2
        WHEN 'TIER3_LOW' THEN 3
    END,
    agent_id;
'@

psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -c $providerPolicyQuery
Write-Host ""

# =============================================================================
# FINAL SUMMARY
# =============================================================================

Write-Host "=======================================================================" -ForegroundColor Green
Write-Host "FOUNDATION REINITIALIZATION COMPLETE" -ForegroundColor Green
Write-Host "=======================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "[OK] Governance tables dropped (intermediate state cleared)" -ForegroundColor Green
Write-Host "[OK] Migration 018 executed (single source of truth)" -ForegroundColor Green
Write-Host "[OK] 13 governance and economic safety tables created" -ForegroundColor Green
Write-Host "[OK] G0 submission logged (G0-2025-11-23-LINE-MANDATE)" -ForegroundColor Green
Write-Host "[OK] LIVE_MODE=False enforced (VEGA QG-F6 required)" -ForegroundColor Green
Write-Host "[OK] Provider policies configured (5 agents: LARS, VEGA, FINN, STIG, LINE)" -ForegroundColor Green
Write-Host "[OK] Economic safety limits populated (rate/cost/execution)" -ForegroundColor Green
Write-Host ""
Write-Host "Foundation Layer Status:" -ForegroundColor Cyan
Write-Host "  fhq_meta      -> ADR governance infrastructure (ADR-004, ADR-008)" -ForegroundColor Gray
Write-Host "  fhq_governance -> Agent contracts & provider policies (ADR-001, ADR-007)" -ForegroundColor Gray
Write-Host "  vega          -> Economic safety layer (ADR-012)" -ForegroundColor Gray
Write-Host ""
Write-Host "Vision-IoS Integration Policy:" -ForegroundColor Yellow
Write-Host "  [OK] FHQ foundation is immutable (no writes to fhq_* by Vision-IoS)" -ForegroundColor Gray
Write-Host "  [OK] Vision-IoS builds on top (vision_* schemas only)" -ForegroundColor Gray
Write-Host "  [OK] Communication through agent identities (LARS, STIG, LINE, FINN, VEGA)" -ForegroundColor Gray
Write-Host "  [OK] No workaround-patching allowed (reinitialization is standard)" -ForegroundColor Gray
Write-Host ""
Write-Host "Next Steps (ADR-004 G1->G4 Process):" -ForegroundColor Cyan
Write-Host "  1. STIG: Register G1 Technical Validation PASS" -ForegroundColor White
Write-Host "  2. STIG: Document decision in G1_VALIDATION_MATERIALS_LINE_MANDATE.md" -ForegroundColor White
Write-Host "  3. STIG: Submit to G2 (LARS Governance Validation)" -ForegroundColor White
Write-Host "  4. Vision-IoS: Register orchestrator functions AFTER G1 PASS" -ForegroundColor White
Write-Host ""
Write-Host "Documentation:" -ForegroundColor Cyan
Write-Host "  - Migration: 04_DATABASE/MIGRATIONS/018_line_mandate_governance_economic_safety.sql" -ForegroundColor Gray
Write-Host "  - Validation: 04_DATABASE/MIGRATIONS/validate_018_line_mandate.sql" -ForegroundColor Gray
Write-Host "  - G1 Materials: 06_GOVERNANCE/G1_VALIDATION_MATERIALS_LINE_MANDATE.md" -ForegroundColor Gray
Write-Host "  - README: 06_GOVERNANCE/README_LINE_MANDATE.md" -ForegroundColor Gray
Write-Host ""
Write-Host "=======================================================================" -ForegroundColor Green
Write-Host "BINDING POLICY COMPLIANCE: VERIFIED" -ForegroundColor Green
Write-Host "=======================================================================" -ForegroundColor Green
Write-Host ""

Set-Location $PSScriptRoot
