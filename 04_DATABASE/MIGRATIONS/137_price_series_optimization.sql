-- ============================================================================
-- MIGRATION 137: Price Series Optimization
-- ============================================================================
-- Authority: STIG (CTO) per ADR-013 Infrastructure Sovereignty
-- Purpose: Optimize fhq_data.price_series for faster queries
-- Issue: Database queries hanging on large table scans
-- Date: 2025-12-16
-- ============================================================================

-- 1. Create optimized indexes for common query patterns
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_price_series_listing_date
ON fhq_data.price_series (listing_id, date DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_price_series_resolution
ON fhq_data.price_series (resolution);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_price_series_date_resolution
ON fhq_data.price_series (date DESC, resolution);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_price_series_listing_resolution_date
ON fhq_data.price_series (listing_id, resolution, date DESC);

-- 2. Add partial index for recent data (last 30 days) - most common queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_price_series_recent
ON fhq_data.price_series (listing_id, date DESC)
WHERE date >= CURRENT_DATE - INTERVAL '30 days';

-- 3. Analyze table to update statistics
ANALYZE fhq_data.price_series;

-- 4. Log optimization in governance
INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    entity_type,
    entity_id,
    agent_id,
    action_details,
    governance_status,
    created_at
) VALUES (
    gen_random_uuid(),
    'SCHEMA_OPTIMIZATION',
    'TABLE',
    'fhq_data.price_series',
    'STIG',
    jsonb_build_object(
        'migration', '137_price_series_optimization',
        'indexes_created', 5,
        'reason', 'Query performance optimization for IoS-001 price ingest'
    ),
    'EXECUTED',
    NOW()
) ON CONFLICT DO NOTHING;

-- 5. Verify indexes were created
DO $$
DECLARE
    idx_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO idx_count
    FROM pg_indexes
    WHERE tablename = 'price_series'
    AND schemaname = 'fhq_data'
    AND indexname LIKE 'idx_price_series%';

    IF idx_count >= 4 THEN
        RAISE NOTICE 'Migration 137 SUCCESS: Created % indexes on price_series', idx_count;
    ELSE
        RAISE WARNING 'Migration 137 PARTIAL: Only % indexes created', idx_count;
    END IF;
END $$;
