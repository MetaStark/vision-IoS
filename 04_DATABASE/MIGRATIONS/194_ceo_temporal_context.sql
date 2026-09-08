-- ============================================================================
-- MIGRATION 194: CEO-DIR-2026-01-03-PHASE-B Temporal Context Commands
-- ============================================================================
--
-- CEO DIRECTIVE: COGNITIVE INTUITION CONTRACT - HISTORICAL REFLECTION
--
-- This migration extends the CEO Glass Window with temporal context queries
-- that show WHAT WAS, never WHAT TO DO.
--
-- Non-Negotiables:
--   - Historical reflection ONLY (not analytics)
--   - No trend analysis, no advice, no forward-looking summaries
--   - Every response grounded in historical state
--   - End with silence (no recommendation language)
--
-- Approved Query Types:
--   1. "What did the system look like the last time DEFCON changed?"
--   2. "How many needles existed the last time regime confidence >X%?"
--   3. "What governance actions preceded [event]?"
--   4. "What was ACI triangle state during prior regime transitions?"
--
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. TEMPORAL CONTEXT SNAPSHOT TABLE
-- ============================================================================
-- Stores system state snapshots at significant events for temporal queries.

CREATE TABLE IF NOT EXISTS fhq_governance.ceo_temporal_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Event identification
    event_type TEXT NOT NULL,           -- DEFCON_CHANGE, REGIME_TRANSITION, HIGH_CONFIDENCE, etc.
    event_trigger TEXT NOT NULL,        -- What triggered the snapshot
    event_timestamp TIMESTAMPTZ NOT NULL,

    -- System state at time of event
    defcon_level TEXT,
    regime_label TEXT,
    regime_confidence NUMERIC(5,4),
    active_needle_count INT,

    -- ACI Triangle state at snapshot
    sitc_score NUMERIC(5,2),
    inforage_score NUMERIC(5,2),
    ikea_score NUMERIC(5,2),

    -- Golden needle summary at snapshot
    needle_categories JSONB,            -- {"MEAN_REVERSION": 5, "CATALYST": 3, ...}

    -- Governance context
    recent_governance_actions JSONB,    -- Last 5 actions before event

    -- Court-proof evidence
    snapshot_hash TEXT NOT NULL,        -- SHA-256 of full snapshot
    evidence_id UUID,                   -- FK to summary_evidence_ledger

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_event_type CHECK (
        event_type IN (
            'DEFCON_CHANGE',
            'REGIME_TRANSITION',
            'HIGH_CONFIDENCE',
            'NEEDLE_SPIKE',
            'GOVERNANCE_BLOCK',
            'ACI_BREACH'
        )
    )
);

-- Indexes for temporal queries
CREATE INDEX IF NOT EXISTS idx_temporal_snapshots_event_type
    ON fhq_governance.ceo_temporal_snapshots(event_type);
CREATE INDEX IF NOT EXISTS idx_temporal_snapshots_timestamp
    ON fhq_governance.ceo_temporal_snapshots(event_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_temporal_snapshots_defcon
    ON fhq_governance.ceo_temporal_snapshots(defcon_level);
CREATE INDEX IF NOT EXISTS idx_temporal_snapshots_regime
    ON fhq_governance.ceo_temporal_snapshots(regime_label);

COMMENT ON TABLE fhq_governance.ceo_temporal_snapshots IS
'CEO-DIR-2026-01-03-PHASE-B: Temporal context snapshots for historical reflection queries';

-- ============================================================================
-- 2. REGISTER PHASE B TEMPORAL COMMANDS
-- ============================================================================
-- Add new temporal context commands to the command registry.

INSERT INTO fhq_governance.ceo_command_registry
    (command_name, command_description, view_source, requires_args)
VALUES
    -- Temporal: Last DEFCON change
    ('/when_defcon', 'System state at last DEFCON transition',
     'fhq_governance.defcon_transitions', FALSE),

    -- Temporal: Regime transitions
    ('/when_regime', 'System state at recent regime transitions',
     'fhq_governance.ceo_temporal_snapshots', FALSE),

    -- Temporal: High confidence moments
    ('/when_confidence', 'State when regime confidence exceeded threshold',
     'fhq_governance.ceo_temporal_snapshots', TRUE),

    -- Temporal: Governance patterns
    ('/when_blocked', 'Context around recent governance blocks',
     'fhq_governance.governance_actions_log', FALSE),

    -- Temporal: Needle history
    ('/history_needles', 'Historical needle counts by period',
     'fhq_canonical.golden_needles', FALSE)
ON CONFLICT (command_name) DO UPDATE SET
    command_description = EXCLUDED.command_description,
    view_source = EXCLUDED.view_source;

-- ============================================================================
-- 3. VIEW: DEFCON TRANSITION CONTEXT
-- ============================================================================
-- Shows system state at each DEFCON transition.

CREATE OR REPLACE VIEW fhq_governance.v_defcon_transition_context AS
SELECT
    dt.transition_id,
    dt.from_level,
    dt.to_level,
    dt.reason,
    dt.authorized_by,
    dt.transition_timestamp,

    -- Needle count at transition time (approximate)
    (SELECT COUNT(*)
     FROM fhq_canonical.golden_needles gn
     WHERE gn.created_at <= dt.transition_timestamp
       AND gn.is_current = TRUE) AS needles_at_transition,

    -- Time since last transition
    dt.transition_timestamp - LAG(dt.transition_timestamp)
        OVER (ORDER BY dt.transition_timestamp) AS time_since_last

FROM fhq_governance.defcon_transitions dt
ORDER BY dt.transition_timestamp DESC;

COMMENT ON VIEW fhq_governance.v_defcon_transition_context IS
'CEO-DIR-2026-01-03-PHASE-B: DEFCON transitions with system context (historical reflection)';

-- ============================================================================
-- 4. VIEW: REGIME TRANSITION CONTEXT
-- ============================================================================
-- Shows what the system looked like at regime changes.

CREATE OR REPLACE VIEW fhq_governance.v_regime_transition_context AS
WITH regime_changes AS (
    SELECT
        gn.created_at AS observation_time,
        gn.regime_sovereign AS regime_at_time,
        gn.regime_confidence,
        gn.defcon_level,
        LAG(gn.regime_sovereign) OVER (ORDER BY gn.created_at) AS prev_regime,
        COUNT(*) OVER (
            PARTITION BY DATE(gn.created_at)
        ) AS needles_that_day
    FROM fhq_canonical.golden_needles gn
    WHERE gn.regime_sovereign IS NOT NULL
)
SELECT
    observation_time,
    prev_regime,
    regime_at_time AS new_regime,
    regime_confidence,
    defcon_level,
    needles_that_day
FROM regime_changes
WHERE prev_regime IS NOT NULL
  AND prev_regime != regime_at_time
ORDER BY observation_time DESC
LIMIT 20;

COMMENT ON VIEW fhq_governance.v_regime_transition_context IS
'CEO-DIR-2026-01-03-PHASE-B: Regime transitions with context (historical reflection)';

-- ============================================================================
-- 5. VIEW: HIGH CONFIDENCE MOMENTS
-- ============================================================================
-- Shows system state when regime confidence exceeded thresholds.

CREATE OR REPLACE VIEW fhq_governance.v_high_confidence_moments AS
SELECT
    gn.created_at AS observation_time,
    gn.regime_sovereign AS regime,
    gn.regime_confidence,
    gn.defcon_level,
    gn.target_asset,
    gn.hypothesis_category,
    gn.eqs_score,
    COUNT(*) OVER (
        PARTITION BY DATE(gn.created_at)
    ) AS needles_that_day
FROM fhq_canonical.golden_needles gn
WHERE gn.regime_confidence >= 0.90
ORDER BY gn.created_at DESC
LIMIT 50;

COMMENT ON VIEW fhq_governance.v_high_confidence_moments IS
'CEO-DIR-2026-01-03-PHASE-B: Moments when regime confidence exceeded 90% (historical reflection)';

-- ============================================================================
-- 6. VIEW: GOVERNANCE BLOCK PATTERNS
-- ============================================================================
-- Shows context around governance blocks without interpretation.

CREATE OR REPLACE VIEW fhq_governance.v_governance_block_context AS
SELECT
    gal.action_type,
    gal.action_target,
    gal.decision,
    gal.decision_rationale,
    gal.initiated_at,
    gal.initiated_by,

    -- Count blocks in surrounding window (no interpretation, just count)
    (SELECT COUNT(*)
     FROM fhq_governance.governance_actions_log gal2
     WHERE gal2.decision = 'BLOCKED'
       AND gal2.initiated_at BETWEEN gal.initiated_at - INTERVAL '1 hour'
                                  AND gal.initiated_at) AS blocks_in_prior_hour
FROM fhq_governance.governance_actions_log gal
WHERE gal.decision = 'BLOCKED'
ORDER BY gal.initiated_at DESC
LIMIT 50;

COMMENT ON VIEW fhq_governance.v_governance_block_context IS
'CEO-DIR-2026-01-03-PHASE-B: Governance blocks with temporal context (historical reflection)';

-- ============================================================================
-- 7. VIEW: NEEDLE HISTORY BY PERIOD
-- ============================================================================
-- Shows needle counts by day/week (raw counts, no trends).

CREATE OR REPLACE VIEW fhq_governance.v_needle_history AS
SELECT
    DATE(created_at) AS date,
    COUNT(*) AS total_needles,
    COUNT(*) FILTER (WHERE is_current = TRUE) AS current_needles,

    -- Category breakdown (raw counts)
    COUNT(*) FILTER (WHERE hypothesis_category LIKE '%MEAN_REVERSION%') AS mean_reversion,
    COUNT(*) FILTER (WHERE hypothesis_category LIKE '%CATALYST%') AS catalyst,
    COUNT(*) FILTER (WHERE hypothesis_category LIKE '%TIMING%') AS timing,
    COUNT(*) FILTER (WHERE hypothesis_category LIKE '%REGIME%') AS regime_edge,

    -- Regime at that time (most common that day)
    MODE() WITHIN GROUP (ORDER BY regime_sovereign) AS dominant_regime,

    -- Average confidence that day
    AVG(regime_confidence)::NUMERIC(5,4) AS avg_confidence
FROM fhq_canonical.golden_needles
GROUP BY DATE(created_at)
ORDER BY DATE(created_at) DESC
LIMIT 30;

COMMENT ON VIEW fhq_governance.v_needle_history IS
'CEO-DIR-2026-01-03-PHASE-B: Daily needle counts by category (historical reflection, no trends)';

-- ============================================================================
-- 8. FUNCTION: CAPTURE TEMPORAL SNAPSHOT
-- ============================================================================
-- Called by daemons when significant events occur.

CREATE OR REPLACE FUNCTION fhq_governance.capture_temporal_snapshot(
    p_event_type TEXT,
    p_event_trigger TEXT
) RETURNS UUID AS $$
DECLARE
    v_snapshot_id UUID;
    v_defcon_level TEXT;
    v_regime_label TEXT;
    v_regime_confidence NUMERIC(5,4);
    v_needle_count INT;
    v_snapshot_data JSONB;
    v_snapshot_hash TEXT;
BEGIN
    -- Capture current state
    SELECT current_level INTO v_defcon_level
    FROM fhq_monitoring.defcon_status
    ORDER BY activated_at DESC LIMIT 1;

    SELECT regime_label, regime_confidence
    INTO v_regime_label, v_regime_confidence
    FROM fhq_finn.v_btc_regime_current LIMIT 1;

    SELECT COUNT(*) INTO v_needle_count
    FROM fhq_canonical.golden_needles
    WHERE is_current = TRUE;

    -- Build snapshot data for hashing
    v_snapshot_data := jsonb_build_object(
        'event_type', p_event_type,
        'event_trigger', p_event_trigger,
        'defcon_level', v_defcon_level,
        'regime_label', v_regime_label,
        'regime_confidence', v_regime_confidence,
        'needle_count', v_needle_count,
        'timestamp', NOW()
    );

    -- Compute hash
    v_snapshot_hash := encode(sha256(v_snapshot_data::TEXT::BYTEA), 'hex');

    -- Insert snapshot
    INSERT INTO fhq_governance.ceo_temporal_snapshots (
        event_type,
        event_trigger,
        event_timestamp,
        defcon_level,
        regime_label,
        regime_confidence,
        active_needle_count,
        snapshot_hash
    ) VALUES (
        p_event_type,
        p_event_trigger,
        NOW(),
        v_defcon_level,
        v_regime_label,
        v_regime_confidence,
        v_needle_count,
        v_snapshot_hash
    ) RETURNING snapshot_id INTO v_snapshot_id;

    RETURN v_snapshot_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.capture_temporal_snapshot IS
'CEO-DIR-2026-01-03-PHASE-B: Captures system state snapshot at significant events';

-- ============================================================================
-- 9. GOVERNANCE ACTION LOGGING
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    decision,
    decision_rationale,
    initiated_by,
    vega_reviewed
) VALUES (
    'MIGRATION',
    'CEO_TEMPORAL_CONTEXT',
    'APPROVED',
    'CEO-DIR-2026-01-03-PHASE-B: Temporal Context Commands for Historical Reflection',
    'STIG',
    FALSE
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    -- Verify table created
    IF EXISTS(SELECT 1 FROM information_schema.tables
              WHERE table_schema = 'fhq_governance'
              AND table_name = 'ceo_temporal_snapshots') THEN
        RAISE NOTICE 'CEO-DIR-2026-01-03-PHASE-B Migration 194: ceo_temporal_snapshots CREATED';
    END IF;

    -- Verify new commands registered
    IF (SELECT COUNT(*) FROM fhq_governance.ceo_command_registry
        WHERE command_name LIKE '/when_%' OR command_name LIKE '/history_%') >= 5 THEN
        RAISE NOTICE 'CEO-DIR-2026-01-03-PHASE-B Migration 194: % temporal commands REGISTERED',
                     (SELECT COUNT(*) FROM fhq_governance.ceo_command_registry
                      WHERE command_name LIKE '/when_%' OR command_name LIKE '/history_%');
    END IF;

    -- Verify views created
    IF EXISTS(SELECT 1 FROM information_schema.views
              WHERE table_schema = 'fhq_governance'
              AND table_name = 'v_defcon_transition_context') THEN
        RAISE NOTICE 'CEO-DIR-2026-01-03-PHASE-B Migration 194: v_defcon_transition_context VIEW CREATED';
    END IF;

    RAISE NOTICE '============================================================';
    RAISE NOTICE 'CEO-DIR-2026-01-03-PHASE-B Migration 194 COMPLETE';
    RAISE NOTICE 'COGNITIVE INTUITION CONTRACT: Historical reflection ONLY';
    RAISE NOTICE '============================================================';
END $$;
