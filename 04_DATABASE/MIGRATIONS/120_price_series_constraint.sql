-- ============================================================================
-- Migration 120: Price Series Unique Constraint
-- Prerequisite for IoS-001 Price Backfill Pipeline
-- ============================================================================
-- Authority: STIG (CTO) per EC-003
-- ADR References: ADR-013 (Canonical Architecture)
-- Purpose: Enable upsert functionality for price backfill
-- ============================================================================

BEGIN;

-- Add unique constraint for ON CONFLICT upsert
ALTER TABLE fhq_data.price_series
ADD CONSTRAINT price_series_listing_timestamp_vendor_unique
UNIQUE (listing_id, timestamp, vendor_id);

-- Add index for efficient lookups
CREATE INDEX IF NOT EXISTS idx_price_series_listing_timestamp
ON fhq_data.price_series (listing_id, timestamp);

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
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'SCHEMA_MIGRATION',
    'fhq_data.price_series',
    'TABLE',
    'STIG',
    NOW(),
    'APPROVED',
    'Migration 120: Added unique constraint (listing_id, timestamp, vendor_id) to enable upsert for IoS-001 price backfill pipeline. Added index for efficient lookups.',
    false,
    'MIG-120-PRICE-CONSTRAINT-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS')
);

COMMIT;

-- ============================================================================
-- Migration 120 Complete
-- Constraint: price_series_listing_timestamp_vendor_unique
-- Index: idx_price_series_listing_timestamp
-- ============================================================================
