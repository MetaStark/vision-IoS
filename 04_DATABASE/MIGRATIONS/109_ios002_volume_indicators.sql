-- =============================================================================
-- MIGRATION: 109_ios002_volume_indicators.sql
-- IoS-002 Volume Indicator Completion
-- Authority: STIG (EC-003), Owner: FINN (EC-004)
-- ADR Compliance: ADR-003, ADR-013, IoS-002 §2.4
-- =============================================================================
-- PURPOSE:
-- Creates indicator_volume table for OBV and ROC indicators as specified in
-- IoS-002 §2.4 (Volume Indicators). This completes the indicator infrastructure.
--
-- INDICATORS SUPPORTED:
-- - OBV (On-Balance Volume) - Granville (1963)
-- - ROC (Rate of Change) - Standard momentum indicator
-- =============================================================================

BEGIN;

-- Create indicator_volume table (matching existing indicator_* schema)
CREATE TABLE IF NOT EXISTS fhq_research.indicator_volume (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL,
    asset_id TEXT NOT NULL,
    value_json JSONB NOT NULL,
    engine_version TEXT,
    formula_hash TEXT,
    lineage_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for asset/timestamp queries (matches other indicator tables)
CREATE INDEX IF NOT EXISTS idx_indicator_volume_asset_ts
    ON fhq_research.indicator_volume (asset_id, timestamp DESC);

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON fhq_research.indicator_volume TO postgres;

-- Log governance action
INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    vega_reviewed,
    hash_chain_id,
    signature_id
) VALUES (
    gen_random_uuid(),
    'SCHEMA_MIGRATION',
    'fhq_research.indicator_volume',
    'TABLE',
    'STIG',
    NOW(),
    'APPROVED',
    'IoS-002 §2.4 Volume Indicator table creation. Implements OBV (Granville 1963) and ROC indicators. Authority: EC-003 (STIG), Owner: EC-004 (FINN).',
    false,
    'MIG-109-IOS002-VOLUME-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS'),
    gen_random_uuid()
);

COMMIT;

-- =============================================================================
-- VERIFICATION
-- =============================================================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'fhq_research' AND table_name = 'indicator_volume'
    ) THEN
        RAISE NOTICE 'SUCCESS: fhq_research.indicator_volume created';
    ELSE
        RAISE EXCEPTION 'FAILED: indicator_volume table not created';
    END IF;
END $$;
