-- Migration 296: Canonical Source Provider Alignment
-- Purpose: Enforce single canonical source taxonomy per CEO-DIR-2026-064 Order 1
-- Directive: CEO-DIR-2026-064 - Canonical Source Provider Alignment & Calendar-Orchestrator Integration
-- Author: STIG
-- Date: 2026-01-17
-- Mode: EXECUTION AUTHORIZED – P1

-- ============================================
-- SECTION 1: Pre-Migration Audit Snapshot
-- ============================================

BEGIN;

-- Create audit table to capture before/after diff
CREATE TABLE IF NOT EXISTS fhq_governance.source_provider_alignment_audit (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    migration_id INTEGER NOT NULL DEFAULT 296,
    event_id UUID NOT NULL,
    event_type_code TEXT NOT NULL,
    old_source_provider TEXT NOT NULL,
    new_source_provider TEXT NOT NULL,
    change_type TEXT NOT NULL,  -- 'CENTRAL_BANK_SUFFIX' | 'CONSOLIDATION' | 'NO_CHANGE'
    migrated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Capture pre-migration state
INSERT INTO fhq_governance.source_provider_alignment_audit
    (event_id, event_type_code, old_source_provider, new_source_provider, change_type)
SELECT
    event_id,
    event_type_code,
    source_provider as old_source_provider,
    CASE
        WHEN source_provider = 'ECB' THEN 'ECB_OFFICIAL'
        WHEN source_provider = 'BOE' THEN 'BOE_OFFICIAL'
        WHEN source_provider = 'BOJ' THEN 'BOJ_OFFICIAL'
        WHEN source_provider = 'PBOC' THEN 'PBOC_OFFICIAL'
        WHEN source_provider = 'CENSUS' THEN 'CENSUS_BUREAU'
        ELSE source_provider
    END as new_source_provider,
    CASE
        WHEN source_provider IN ('ECB', 'BOE', 'BOJ', 'PBOC') THEN 'CENTRAL_BANK_SUFFIX'
        WHEN source_provider = 'CENSUS' THEN 'CONSOLIDATION'
        ELSE 'NO_CHANGE'
    END as change_type
FROM fhq_calendar.calendar_events
WHERE is_canonical = true;

-- ============================================
-- SECTION 2: Add Missing Approved Data Sources
-- ============================================

-- Add US government agencies that are legitimate data sources
-- Valid source_types: CENTRAL_BANK, GOVERNMENT_AGENCY, OFFICIAL_STATISTICAL
INSERT INTO fhq_governance.approved_data_sources
    (source_code, source_name, source_type, api_endpoint, verification_method, is_active, approved_by, approved_at)
VALUES
    ('DOL', 'Department of Labor', 'GOVERNMENT_AGENCY', 'https://www.dol.gov/ui/data',
     'API_RESPONSE_HASH', true, 'CEO', NOW()),
    ('CENSUS_BUREAU', 'US Census Bureau', 'GOVERNMENT_AGENCY', 'https://www.census.gov/economic-indicators',
     'API_RESPONSE_HASH', true, 'CEO', NOW()),
    ('ISM', 'Institute for Supply Management', 'OFFICIAL_STATISTICAL', 'https://www.ismworld.org',
     'API_RESPONSE_HASH', true, 'CEO', NOW()),
    ('ISM_CHICAGO', 'ISM Chicago', 'OFFICIAL_STATISTICAL', 'https://www.ismchicago.org',
     'API_RESPONSE_HASH', true, 'CEO', NOW()),
    ('CONFERENCE_BOARD', 'The Conference Board', 'OFFICIAL_STATISTICAL', 'https://www.conference-board.org',
     'API_RESPONSE_HASH', true, 'CEO', NOW()),
    ('SP_GLOBAL', 'S&P Global', 'OFFICIAL_STATISTICAL', 'https://www.spglobal.com/marketintelligence',
     'API_RESPONSE_HASH', true, 'CEO', NOW())
ON CONFLICT (source_code) DO UPDATE SET
    is_active = true,
    approved_at = NOW();

-- ============================================
-- SECTION 3: Update Calendar Events to Canonical Source Providers
-- ============================================

-- Central Bank Suffix Updates
UPDATE fhq_calendar.calendar_events
SET source_provider = 'ECB_OFFICIAL'
WHERE source_provider = 'ECB' AND is_canonical = true;

UPDATE fhq_calendar.calendar_events
SET source_provider = 'BOE_OFFICIAL'
WHERE source_provider = 'BOE' AND is_canonical = true;

UPDATE fhq_calendar.calendar_events
SET source_provider = 'BOJ_OFFICIAL'
WHERE source_provider = 'BOJ' AND is_canonical = true;

UPDATE fhq_calendar.calendar_events
SET source_provider = 'PBOC_OFFICIAL'
WHERE source_provider = 'PBOC' AND is_canonical = true;

-- Consolidate CENSUS to CENSUS_BUREAU
UPDATE fhq_calendar.calendar_events
SET source_provider = 'CENSUS_BUREAU'
WHERE source_provider = 'CENSUS' AND is_canonical = true;

-- ============================================
-- SECTION 4: Add Legacy Classification Column
-- ============================================

-- Add lineage_status column for Order 3 (LEGACY_UNVERIFIED classification)
ALTER TABLE fhq_calendar.calendar_events
ADD COLUMN IF NOT EXISTS lineage_status TEXT DEFAULT 'PENDING';

-- Classify existing events without lineage as LEGACY_UNVERIFIED
UPDATE fhq_calendar.calendar_events ce
SET lineage_status = 'LEGACY_UNVERIFIED'
WHERE is_canonical = true
  AND NOT EXISTS (
      SELECT 1 FROM fhq_calendar.data_lineage_proof dlp
      WHERE dlp.event_id = ce.event_id
  );

-- Add CHECK constraint for valid lineage statuses
ALTER TABLE fhq_calendar.calendar_events
DROP CONSTRAINT IF EXISTS chk_lineage_status;

ALTER TABLE fhq_calendar.calendar_events
ADD CONSTRAINT chk_lineage_status
CHECK (lineage_status IN ('PENDING', 'LEGACY_UNVERIFIED', 'VERIFIED', 'VERIFICATION_FAILED'));

-- Create index for lineage status queries
CREATE INDEX IF NOT EXISTS idx_calendar_lineage_status
ON fhq_calendar.calendar_events(lineage_status)
WHERE is_canonical = true;

-- ============================================
-- SECTION 5: Governance Logging
-- ============================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id, action_type, action_target, action_target_type,
    initiated_by, initiated_at, decision, decision_rationale
) VALUES (
    gen_random_uuid(),
    'SOURCE_PROVIDER_ALIGNMENT',
    'fhq_calendar.calendar_events',
    'SCHEMA',
    'STIG',
    NOW(),
    'APPROVED',
    'CEO-DIR-2026-064 Order 1: Canonical source provider alignment. Central banks updated to _OFFICIAL suffix (ECB→ECB_OFFICIAL, BOE→BOE_OFFICIAL, BOJ→BOJ_OFFICIAL, PBOC→PBOC_OFFICIAL). CENSUS consolidated to CENSUS_BUREAU. 6 new approved sources added (DOL, CENSUS_BUREAU, ISM, ISM_CHICAGO, CONFERENCE_BOARD, SP_GLOBAL). Order 3: Added lineage_status column, existing events classified as LEGACY_UNVERIFIED.'
);

COMMIT;

-- ============================================
-- VERIFICATION QUERIES (Run after migration)
-- ============================================

-- Verify no calendar rows exist with unapproved source_provider
-- SELECT source_provider, COUNT(*) as count
-- FROM fhq_calendar.calendar_events
-- WHERE is_canonical = true
--   AND source_provider NOT IN (SELECT source_code FROM fhq_governance.approved_data_sources WHERE is_active = true)
-- GROUP BY source_provider;

-- Show before/after diff
-- SELECT old_source_provider, new_source_provider, change_type, COUNT(*) as count
-- FROM fhq_governance.source_provider_alignment_audit
-- WHERE change_type != 'NO_CHANGE'
-- GROUP BY old_source_provider, new_source_provider, change_type
-- ORDER BY change_type, old_source_provider;

-- Show lineage status distribution
-- SELECT lineage_status, COUNT(*) as count
-- FROM fhq_calendar.calendar_events
-- WHERE is_canonical = true
-- GROUP BY lineage_status;
