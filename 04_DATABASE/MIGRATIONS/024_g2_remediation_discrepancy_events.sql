-- ============================================================================
-- MIGRATION 024: G2 REMEDIATION - Discrepancy Events & Legacy Cleanup
-- ============================================================================
-- Authority: ADR-010 (State Reconciliation & Discrepancy Scoring)
-- Purpose: Resolve G2 Governance Validation warning for IoS-002
-- Owner: STIG (CTO)
-- Date: 2025-11-29
-- ============================================================================

BEGIN;

-- ============================================================================
-- PHASE 1: Create fhq_archive schema for legacy backup
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS fhq_archive;

COMMENT ON SCHEMA fhq_archive IS 'Archive schema for deprecated tables - ADR-013 One-True-Source cleanup';

-- ============================================================================
-- PHASE 2: Backup legacy indicator tables
-- ============================================================================

-- Backup fhq_data.indicators if exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'fhq_data' AND table_name = 'indicators') THEN
        EXECUTE 'CREATE TABLE fhq_archive.indicators_fhq_data_backup_20251129 AS
                 SELECT * FROM fhq_data.indicators';
        RAISE NOTICE 'Backed up fhq_data.indicators to fhq_archive';
    END IF;
END $$;

-- Backup fhq_research.indicators if exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'fhq_research' AND table_name = 'indicators') THEN
        EXECUTE 'CREATE TABLE fhq_archive.indicators_fhq_research_backup_20251129 AS
                 SELECT * FROM fhq_research.indicators';
        RAISE NOTICE 'Backed up fhq_research.indicators to fhq_archive';
    END IF;
END $$;

-- ============================================================================
-- PHASE 3: DROP legacy indicator tables (One-True-Source enforcement)
-- ============================================================================

DROP TABLE IF EXISTS fhq_data.indicators CASCADE;
DROP TABLE IF EXISTS fhq_research.indicators CASCADE;

-- ============================================================================
-- PHASE 4: Create discrepancy_events table (ADR-010)
-- ============================================================================

CREATE TYPE fhq_governance.discrepancy_severity AS ENUM (
    'INFO',      -- Informational, no action required
    'WARN',      -- Warning, may require investigation
    'CRITICAL'   -- Critical, immediate action required
);

CREATE TABLE fhq_governance.discrepancy_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source identification
    ios_id TEXT NOT NULL,                    -- e.g., 'IoS-002'
    agent_id TEXT NOT NULL,                  -- Agent that detected/reported
    target_table TEXT NOT NULL,              -- e.g., 'fhq_research.indicator_momentum'
    target_column TEXT,                      -- Specific column if applicable
    target_key JSONB,                        -- Primary key of affected row(s)

    -- Discrepancy details
    canonical_value TEXT,                    -- Expected/canonical value
    reported_value TEXT,                     -- Actual/reported value
    discrepancy_type TEXT NOT NULL,          -- e.g., 'MISSING_ROW', 'VALUE_DRIFT', 'NULL_VALUE'
    discrepancy_score NUMERIC(10,6),         -- 0.0 to 1.0 score per ADR-010
    severity fhq_governance.discrepancy_severity NOT NULL DEFAULT 'INFO',

    -- Context
    detection_method TEXT,                   -- e.g., 'VEGA_DAILY_SCAN', 'RECONCILIATION_WORKER'
    context_data JSONB,                      -- Additional context

    -- Resolution tracking
    resolution_status TEXT DEFAULT 'OPEN' CHECK (resolution_status IN ('OPEN', 'INVESTIGATING', 'RESOLVED', 'ACCEPTED')),
    resolved_by TEXT,
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,

    -- Audit trail
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ADR-010 compliance
    adr_reference TEXT DEFAULT 'ADR-010',

    -- Hash chain for immutability
    hash_prev TEXT,
    hash_self TEXT
);

-- Create indexes for common queries
CREATE INDEX idx_discrepancy_events_ios_id ON fhq_governance.discrepancy_events(ios_id);
CREATE INDEX idx_discrepancy_events_severity ON fhq_governance.discrepancy_events(severity);
CREATE INDEX idx_discrepancy_events_status ON fhq_governance.discrepancy_events(resolution_status);
CREATE INDEX idx_discrepancy_events_created ON fhq_governance.discrepancy_events(created_at DESC);
CREATE INDEX idx_discrepancy_events_agent ON fhq_governance.discrepancy_events(agent_id);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION fhq_governance.update_discrepancy_events_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_discrepancy_events_updated
    BEFORE UPDATE ON fhq_governance.discrepancy_events
    FOR EACH ROW
    EXECUTE FUNCTION fhq_governance.update_discrepancy_events_timestamp();

-- Add table comment
COMMENT ON TABLE fhq_governance.discrepancy_events IS
'ADR-010 Discrepancy Events Log - Tracks all data quality issues detected by VEGA reconciliation.
Used for IoS-002 Indicator Engine validation and G3 Audit compliance.';

-- ============================================================================
-- PHASE 5: Log migration to governance
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    hash_chain_id,
    signature_id
) VALUES (
    gen_random_uuid(),
    'G2_REMEDIATION',
    'discrepancy_events',
    'TABLE',
    'STIG',
    NOW(),
    'APPROVED',
    'Created fhq_governance.discrepancy_events for ADR-010 compliance. Backed up and dropped legacy indicator tables for One-True-Source enforcement.',
    'G2-REM-20251129',
    gen_random_uuid()
);

-- Log to ios_audit
INSERT INTO fhq_meta.ios_audit_log (
    ios_id,
    event_type,
    actor,
    event_data,
    gate_level
) VALUES (
    'IoS-002',
    'G2_REMEDIATION',
    'STIG',
    jsonb_build_object(
        'action', 'G2_REMEDIATION',
        'tables_created', ARRAY['fhq_governance.discrepancy_events'],
        'tables_archived', ARRAY['fhq_data.indicators', 'fhq_research.indicators'],
        'adr_reference', 'ADR-010'
    ),
    'G2'
);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES (Run after migration)
-- ============================================================================

-- Verify discrepancy_events exists
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'fhq_governance' AND table_name = 'discrepancy_events';

-- Verify legacy tables are gone
-- SELECT table_schema, table_name FROM information_schema.tables
-- WHERE table_name = 'indicators' AND table_schema IN ('fhq_data', 'fhq_research');

-- Verify backups exist
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'fhq_archive';
