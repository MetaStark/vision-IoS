-- ============================================================================
-- MIGRATION 214: Block Contaminated Regime Outcomes
-- ============================================================================
-- CEO-DIR-2026-020 D1: Eliminate Outcome Contamination
-- Author: STIG (CTO)
-- Date: 2026-01-08
-- Classification: SAFETY INVARIANT - PERMANENT
--
-- PURPOSE:
--   This migration formally kills circular learning at the database level.
--   After this migration, the system can no longer lie to itself about
--   regime outcomes derived from prediction sources.
--
-- FAIL-CLOSED BEHAVIOR:
--   Any attempt to INSERT a REGIME outcome with evidence_source containing
--   contaminated sources will be REJECTED at the database level.
--
-- CONTAMINATED SOURCES (BLACKLIST):
--   - sovereign_regime_state_v4 (predictions validated against predictions)
--   - regime_predictions_v2 (prediction source)
--   - model_belief_state (belief source, not outcome)
--
-- VALID SOURCES (WHITELIST):
--   - fhq_market.prices (independent price data)
--   - Any source explicitly documented as outcome-independent
--
-- THIS IS NOW A PERMANENT SAFETY INVARIANT.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. Create contaminated sources blacklist table
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhq_research.outcome_source_blacklist (
    source_pattern TEXT PRIMARY KEY,
    reason TEXT NOT NULL,
    blocked_at TIMESTAMPTZ DEFAULT NOW(),
    blocked_by TEXT DEFAULT 'CEO-DIR-2026-020'
);

COMMENT ON TABLE fhq_research.outcome_source_blacklist IS
'CEO-DIR-2026-020 D1: Contaminated evidence sources that cannot be used for REGIME outcomes. Permanent safety invariant.';

-- Insert known contaminated sources
INSERT INTO fhq_research.outcome_source_blacklist (source_pattern, reason) VALUES
    ('sovereign_regime_state_v4', 'Circular validation: predictions validated against predictions'),
    ('regime_predictions_v2', 'Prediction source cannot be outcome source'),
    ('model_belief_state', 'Belief source is not independent outcome'),
    ('regime_predictions', 'Legacy prediction source'),
    ('sovereign_regime_state', 'Legacy prediction-derived state')
ON CONFLICT (source_pattern) DO NOTHING;

-- ============================================================================
-- 2. Create trigger function to block contaminated regime outcomes
-- ============================================================================
CREATE OR REPLACE FUNCTION fhq_research.block_contaminated_regime_outcome()
RETURNS TRIGGER AS $$
DECLARE
    v_blacklisted BOOLEAN;
    v_blocked_source TEXT;
BEGIN
    -- Only check REGIME outcome types
    IF NEW.outcome_type = 'REGIME' THEN
        -- Check if evidence_source matches any blacklisted pattern
        SELECT EXISTS (
            SELECT 1 FROM fhq_research.outcome_source_blacklist
            WHERE NEW.evidence_source ILIKE '%' || source_pattern || '%'
        ), (
            SELECT source_pattern FROM fhq_research.outcome_source_blacklist
            WHERE NEW.evidence_source ILIKE '%' || source_pattern || '%'
            LIMIT 1
        )
        INTO v_blacklisted, v_blocked_source;

        IF v_blacklisted THEN
            -- Log the rejection to governance
            INSERT INTO fhq_governance.governance_actions_log (
                action_type,
                action_target,
                action_target_type,
                decision,
                decision_rationale,
                initiated_by,
                initiated_at,
                metadata
            ) VALUES (
                'CONTAMINATED_OUTCOME_BLOCKED',
                NEW.outcome_id::TEXT,
                'OUTCOME',
                'REJECTED',
                format('CEO-DIR-2026-020 D1: Blocked contaminated REGIME outcome. Source "%s" matches blacklist pattern "%s"',
                       NEW.evidence_source, v_blocked_source),
                'DB_TRIGGER:block_contaminated_regime_outcome',
                NOW(),
                jsonb_build_object(
                    'outcome_type', NEW.outcome_type,
                    'evidence_source', NEW.evidence_source,
                    'blocked_pattern', v_blocked_source,
                    'outcome_timestamp', NEW.outcome_timestamp,
                    'created_by', NEW.created_by
                )
            );

            -- FAIL-CLOSED: Reject the insert
            RAISE EXCEPTION 'CEO-DIR-2026-020 VIOLATION: Cannot insert REGIME outcome with contaminated source "%". Source matches blacklist pattern "%". Use fhq_market.prices for independent regime outcomes.',
                NEW.evidence_source, v_blocked_source;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_research.block_contaminated_regime_outcome() IS
'CEO-DIR-2026-020 D1: Trigger function that enforces outcome independence. REGIME outcomes with contaminated evidence sources are rejected at DB level. This is a permanent safety invariant.';

-- ============================================================================
-- 3. Apply trigger to outcome_ledger
-- ============================================================================
DROP TRIGGER IF EXISTS trg_block_contaminated_regime_outcome ON fhq_research.outcome_ledger;

CREATE TRIGGER trg_block_contaminated_regime_outcome
    BEFORE INSERT ON fhq_research.outcome_ledger
    FOR EACH ROW
    EXECUTE FUNCTION fhq_research.block_contaminated_regime_outcome();

-- ============================================================================
-- 4. Create real-time contamination visibility view
-- ============================================================================
CREATE OR REPLACE VIEW fhq_research.v_outcome_contamination_realtime AS
SELECT
    DATE(created_at) as outcome_date,
    outcome_type,
    evidence_source,
    COUNT(*) as record_count,
    CASE
        WHEN EXISTS (
            SELECT 1 FROM fhq_research.outcome_source_blacklist b
            WHERE evidence_source ILIKE '%' || b.source_pattern || '%'
        ) THEN 'CONTAMINATED'
        WHEN evidence_source = 'fhq_market.prices' THEN 'VALID_INDEPENDENT'
        ELSE 'UNKNOWN_REQUIRES_AUDIT'
    END as contamination_status,
    MIN(created_at) as first_record,
    MAX(created_at) as last_record
FROM fhq_research.outcome_ledger
WHERE created_at > CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(created_at), outcome_type, evidence_source
ORDER BY outcome_date DESC, record_count DESC;

COMMENT ON VIEW fhq_research.v_outcome_contamination_realtime IS
'CEO-DIR-2026-020 D1: Real-time visibility into outcome contamination status. CONTAMINATED outcomes are now blocked at insert, but historical data may still show contamination.';

-- ============================================================================
-- 5. Create summary view for daily audit
-- ============================================================================
CREATE OR REPLACE VIEW fhq_research.v_outcome_independence_daily AS
SELECT
    outcome_date,
    outcome_type,
    SUM(CASE WHEN contamination_status = 'VALID_INDEPENDENT' THEN record_count ELSE 0 END) as valid_count,
    SUM(CASE WHEN contamination_status = 'CONTAMINATED' THEN record_count ELSE 0 END) as contaminated_count,
    SUM(CASE WHEN contamination_status = 'UNKNOWN_REQUIRES_AUDIT' THEN record_count ELSE 0 END) as unknown_count,
    SUM(record_count) as total_count,
    ROUND(
        100.0 * SUM(CASE WHEN contamination_status = 'VALID_INDEPENDENT' THEN record_count ELSE 0 END) /
        NULLIF(SUM(record_count), 0),
        2
    ) as independence_percent,
    CASE
        WHEN SUM(CASE WHEN contamination_status = 'VALID_INDEPENDENT' THEN record_count ELSE 0 END) >=
             SUM(CASE WHEN contamination_status = 'CONTAMINATED' THEN record_count ELSE 0 END)
        THEN 'MAJORITY_INDEPENDENT'
        ELSE 'MAJORITY_CONTAMINATED'
    END as daily_status
FROM fhq_research.v_outcome_contamination_realtime
GROUP BY outcome_date, outcome_type
ORDER BY outcome_date DESC, outcome_type;

COMMENT ON VIEW fhq_research.v_outcome_independence_daily IS
'CEO-DIR-2026-020 D1: Daily audit view showing independence ratio. Learning on regime skill remains BLOCKED until daily_status = MAJORITY_INDEPENDENT.';

-- ============================================================================
-- 6. Log migration to governance
-- ============================================================================
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    decision,
    decision_rationale,
    initiated_by,
    initiated_at,
    metadata
) VALUES (
    'MIGRATION_214_CONTAMINATION_BLOCK',
    'fhq_research.outcome_ledger',
    'TABLE',
    'DEPLOYED',
    'CEO-DIR-2026-020 D1: Deployed permanent safety invariant blocking contaminated REGIME outcomes. Circular learning is now impossible at DB level.',
    'STIG',
    NOW(),
    jsonb_build_object(
        'migration', '214_block_contaminated_regime_outcomes.sql',
        'trigger', 'trg_block_contaminated_regime_outcome',
        'blacklist_table', 'fhq_research.outcome_source_blacklist',
        'views_created', ARRAY['v_outcome_contamination_realtime', 'v_outcome_independence_daily'],
        'ceo_directive', 'CEO-DIR-2026-020',
        'effective_immediately', true
    )
);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES (Run after migration)
-- ============================================================================
-- 1. Check blacklist contents:
--    SELECT * FROM fhq_research.outcome_source_blacklist;
--
-- 2. Check trigger exists:
--    SELECT tgname, tgenabled FROM pg_trigger WHERE tgname = 'trg_block_contaminated_regime_outcome';
--
-- 3. Test contaminated insert rejection:
--    INSERT INTO fhq_research.outcome_ledger (..., evidence_source = 'sovereign_regime_state_v4', ...)
--    Expected: ERROR with CEO-DIR-2026-020 VIOLATION message
--
-- 4. Check contamination status:
--    SELECT * FROM fhq_research.v_outcome_independence_daily WHERE outcome_type = 'REGIME';
-- ============================================================================
