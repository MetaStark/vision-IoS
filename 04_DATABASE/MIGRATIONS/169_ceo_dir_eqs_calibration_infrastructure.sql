-- ============================================================================
-- Migration 169: CEO-DIR-2025-EQS-001 - EQS Calibration Infrastructure
-- ============================================================================
-- Directive: CEO-DIR-2025-EQS-001
-- Status: CEO SIGNED
-- Scope: Signal Quality Governance
--
-- STIG Responsibilities:
--   1. Make EQS threshold configurable, versioned, and logged
--   2. Ensure Hunter refuses execution below threshold
--   3. Log EQS distribution snapshots daily
--   4. Reject hard-coded thresholds in scoring logic
--
-- Core Principle: EQS is a ranking instrument, not a confidence stamp.
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: EQS Threshold Configuration Table
-- ============================================================================
-- Versioned, auditable threshold governance
-- FINN proposes -> VEGA approves -> STIG enforces -> LINE executes

CREATE TABLE IF NOT EXISTS fhq_canonical.eqs_threshold_config (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Threshold value
    threshold_value NUMERIC(5,4) NOT NULL CHECK (threshold_value BETWEEN 0 AND 1),

    -- Validity period
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_until TIMESTAMPTZ,

    -- Governance chain (separation of powers)
    proposed_by TEXT NOT NULL,           -- FINN (model owner)
    proposed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_by TEXT,                     -- VEGA (governance)
    approved_at TIMESTAMPTZ,
    enforced_by TEXT,                     -- STIG (infrastructure)
    enforced_at TIMESTAMPTZ,

    -- Rationale and documentation
    rationale TEXT NOT NULL,
    calibration_evidence JSONB,           -- Link to FINN's recalibration pack
    selectivity_target TEXT,              -- e.g., "Top 5-15% execution eligible"

    -- Versioning
    version INTEGER NOT NULL DEFAULT 1,
    supersedes_config_id UUID REFERENCES fhq_canonical.eqs_threshold_config(config_id),

    -- Activation state
    is_active BOOLEAN DEFAULT FALSE,
    activation_signature TEXT,            -- Ed25519 signature

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Only one active threshold at a time
CREATE UNIQUE INDEX IF NOT EXISTS idx_eqs_threshold_active_unique
ON fhq_canonical.eqs_threshold_config(is_active) WHERE is_active = TRUE;

-- Version history index
CREATE INDEX IF NOT EXISTS idx_eqs_threshold_version
ON fhq_canonical.eqs_threshold_config(version DESC);

-- ============================================================================
-- STEP 2: EQS Distribution Snapshots Table
-- ============================================================================
-- Daily logging for VEGA audit and selectivity monitoring

CREATE TABLE IF NOT EXISTS fhq_canonical.eqs_distribution_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date DATE NOT NULL,

    -- Segmentation
    asset TEXT NOT NULL,                  -- e.g., 'BTC-USD', 'ALL'
    regime TEXT NOT NULL,                 -- e.g., 'BULL', 'BEAR', 'NEUTRAL', 'ALL'
    signal_state TEXT NOT NULL DEFAULT 'DORMANT',

    -- Distribution statistics
    signal_count INTEGER NOT NULL,
    min_eqs NUMERIC(5,4),
    max_eqs NUMERIC(5,4),
    median_eqs NUMERIC(5,4),
    mean_eqs NUMERIC(5,4),
    std_dev NUMERIC(5,4),

    -- Selectivity metrics
    active_threshold NUMERIC(5,4),        -- Threshold at snapshot time
    count_above_threshold INTEGER,
    pct_above_threshold NUMERIC(5,2),

    -- Percentile distribution
    p10 NUMERIC(5,4),
    p25 NUMERIC(5,4),
    p50 NUMERIC(5,4),
    p75 NUMERIC(5,4),
    p90 NUMERIC(5,4),
    p95 NUMERIC(5,4),
    p99 NUMERIC(5,4),

    -- Histogram (for visualization)
    distribution_histogram JSONB,         -- [{bin: "0.90-0.92", count: 15}, ...]

    -- Governance flags
    distribution_collapsed BOOLEAN DEFAULT FALSE,  -- VEGA alert trigger
    collapse_reason TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Unique constraint per date/asset/regime
CREATE UNIQUE INDEX IF NOT EXISTS idx_eqs_snapshot_unique
ON fhq_canonical.eqs_distribution_snapshots(snapshot_date, asset, regime, signal_state);

-- Time-series index
CREATE INDEX IF NOT EXISTS idx_eqs_snapshot_date
ON fhq_canonical.eqs_distribution_snapshots(snapshot_date DESC);

-- ============================================================================
-- STEP 3: Function to Get Active Threshold
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_canonical.get_active_eqs_threshold()
RETURNS NUMERIC AS $$
DECLARE
    v_threshold NUMERIC;
BEGIN
    SELECT threshold_value INTO v_threshold
    FROM fhq_canonical.eqs_threshold_config
    WHERE is_active = TRUE
      AND (effective_until IS NULL OR effective_until > NOW())
    ORDER BY effective_from DESC
    LIMIT 1;

    -- Fallback to constitutional default if no active config
    RETURN COALESCE(v_threshold, 0.85);
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- STEP 4: Function to Capture Daily Distribution Snapshot
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_canonical.capture_eqs_distribution_snapshot(
    p_snapshot_date DATE DEFAULT CURRENT_DATE
)
RETURNS TABLE (
    asset TEXT,
    regime TEXT,
    signal_count INTEGER,
    median_eqs NUMERIC,
    pct_above_threshold NUMERIC,
    distribution_collapsed BOOLEAN
) AS $$
DECLARE
    v_threshold NUMERIC;
BEGIN
    -- Get active threshold
    v_threshold := fhq_canonical.get_active_eqs_threshold();

    -- Capture distribution for each asset/regime combination
    RETURN QUERY
    WITH stats AS (
        SELECT
            gn.target_asset,
            gn.regime_technical,
            ss.current_state,
            COUNT(*) as cnt,
            MIN(gn.eqs_score) as min_eqs,
            MAX(gn.eqs_score) as max_eqs,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gn.eqs_score) as med_eqs,
            AVG(gn.eqs_score) as mean_eqs,
            STDDEV(gn.eqs_score) as std_dev,
            PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY gn.eqs_score) as p10,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY gn.eqs_score) as p25,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY gn.eqs_score) as p50,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY gn.eqs_score) as p75,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY gn.eqs_score) as p90,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY gn.eqs_score) as p95,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY gn.eqs_score) as p99,
            SUM(CASE WHEN gn.eqs_score >= v_threshold THEN 1 ELSE 0 END) as above_threshold
        FROM fhq_canonical.golden_needles gn
        JOIN fhq_canonical.g5_signal_state ss ON gn.needle_id = ss.needle_id
        WHERE ss.current_state = 'DORMANT'
        GROUP BY gn.target_asset, gn.regime_technical, ss.current_state
    )
    INSERT INTO fhq_canonical.eqs_distribution_snapshots (
        snapshot_date,
        asset,
        regime,
        signal_state,
        signal_count,
        min_eqs,
        max_eqs,
        median_eqs,
        mean_eqs,
        std_dev,
        active_threshold,
        count_above_threshold,
        pct_above_threshold,
        p10, p25, p50, p75, p90, p95, p99,
        distribution_collapsed,
        collapse_reason
    )
    SELECT
        p_snapshot_date,
        s.target_asset,
        COALESCE(s.regime_technical, 'UNKNOWN'),
        s.current_state,
        s.cnt::INTEGER,
        s.min_eqs::NUMERIC(5,4),
        s.max_eqs::NUMERIC(5,4),
        s.med_eqs::NUMERIC(5,4),
        s.mean_eqs::NUMERIC(5,4),
        s.std_dev::NUMERIC(5,4),
        v_threshold,
        s.above_threshold::INTEGER,
        ROUND(100.0 * s.above_threshold / NULLIF(s.cnt, 0), 2)::NUMERIC(5,2),
        s.p10::NUMERIC(5,4), s.p25::NUMERIC(5,4), s.p50::NUMERIC(5,4),
        s.p75::NUMERIC(5,4), s.p90::NUMERIC(5,4), s.p95::NUMERIC(5,4), s.p99::NUMERIC(5,4),
        -- Distribution is collapsed if >50% above threshold (VEGA rejection criteria)
        (100.0 * s.above_threshold / NULLIF(s.cnt, 0)) > 50,
        CASE
            WHEN (100.0 * s.above_threshold / NULLIF(s.cnt, 0)) > 50
            THEN 'VEGA ALERT: ' || ROUND(100.0 * s.above_threshold / NULLIF(s.cnt, 0), 1) || '% above threshold (max 50%)'
            ELSE NULL
        END
    FROM stats s
    ON CONFLICT (snapshot_date, asset, regime, signal_state)
    DO UPDATE SET
        signal_count = EXCLUDED.signal_count,
        min_eqs = EXCLUDED.min_eqs,
        max_eqs = EXCLUDED.max_eqs,
        median_eqs = EXCLUDED.median_eqs,
        mean_eqs = EXCLUDED.mean_eqs,
        std_dev = EXCLUDED.std_dev,
        active_threshold = EXCLUDED.active_threshold,
        count_above_threshold = EXCLUDED.count_above_threshold,
        pct_above_threshold = EXCLUDED.pct_above_threshold,
        p10 = EXCLUDED.p10, p25 = EXCLUDED.p25, p50 = EXCLUDED.p50,
        p75 = EXCLUDED.p75, p90 = EXCLUDED.p90, p95 = EXCLUDED.p95, p99 = EXCLUDED.p99,
        distribution_collapsed = EXCLUDED.distribution_collapsed,
        collapse_reason = EXCLUDED.collapse_reason,
        created_at = NOW()
    RETURNING
        fhq_canonical.eqs_distribution_snapshots.asset,
        fhq_canonical.eqs_distribution_snapshots.regime,
        fhq_canonical.eqs_distribution_snapshots.signal_count,
        fhq_canonical.eqs_distribution_snapshots.median_eqs,
        fhq_canonical.eqs_distribution_snapshots.pct_above_threshold,
        fhq_canonical.eqs_distribution_snapshots.distribution_collapsed;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- STEP 5: Function to Activate New Threshold (STIG enforces)
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_canonical.activate_eqs_threshold(
    p_config_id UUID,
    p_enforcer TEXT DEFAULT 'STIG'
)
RETURNS BOOLEAN AS $$
DECLARE
    v_config RECORD;
BEGIN
    -- Verify config exists and is approved by VEGA
    SELECT * INTO v_config
    FROM fhq_canonical.eqs_threshold_config
    WHERE config_id = p_config_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Config % not found', p_config_id;
    END IF;

    IF v_config.approved_by IS NULL THEN
        RAISE EXCEPTION 'Config % not approved by VEGA - cannot activate', p_config_id;
    END IF;

    -- Deactivate current active threshold
    UPDATE fhq_canonical.eqs_threshold_config
    SET is_active = FALSE,
        effective_until = NOW(),
        updated_at = NOW()
    WHERE is_active = TRUE;

    -- Activate new threshold
    UPDATE fhq_canonical.eqs_threshold_config
    SET is_active = TRUE,
        enforced_by = p_enforcer,
        enforced_at = NOW(),
        updated_at = NOW()
    WHERE config_id = p_config_id;

    -- Log to governance
    INSERT INTO fhq_governance.governance_actions_log (
        action_id,
        action_type,
        action_target,
        action_target_type,
        initiated_by,
        initiated_at,
        decision,
        decision_rationale,
        metadata,
        agent_id,
        timestamp
    ) VALUES (
        gen_random_uuid(),
        'EQS_THRESHOLD_ACTIVATION',
        p_config_id::TEXT,
        'EQS_CONFIG',
        p_enforcer,
        NOW(),
        'ACTIVATED',
        'EQS threshold activated per CEO-DIR-2025-EQS-001',
        jsonb_build_object(
            'config_id', p_config_id,
            'threshold_value', v_config.threshold_value,
            'proposed_by', v_config.proposed_by,
            'approved_by', v_config.approved_by,
            'version', v_config.version
        ),
        p_enforcer,
        NOW()
    );

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- STEP 6: Initial Threshold Configuration (Legacy 0.85)
-- ============================================================================
-- Seed with current hardcoded value for continuity

INSERT INTO fhq_canonical.eqs_threshold_config (
    config_id,
    threshold_value,
    effective_from,
    proposed_by,
    proposed_at,
    approved_by,
    approved_at,
    enforced_by,
    enforced_at,
    rationale,
    selectivity_target,
    version,
    is_active
) VALUES (
    gen_random_uuid(),
    0.85,
    NOW(),
    'LEGACY',
    NOW(),
    'CEO',
    NOW(),
    'STIG',
    NOW(),
    'Initial threshold migrated from hardcoded value. Pending FINN recalibration per CEO-DIR-2025-EQS-001.',
    'Legacy: All signals >= 0.85 eligible (no selectivity target)',
    1,
    TRUE
)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- STEP 7: VEGA Alert View for Distribution Collapse
-- ============================================================================

CREATE OR REPLACE VIEW fhq_canonical.v_eqs_distribution_alerts AS
SELECT
    snapshot_date,
    asset,
    regime,
    signal_count,
    median_eqs,
    pct_above_threshold,
    active_threshold,
    collapse_reason,
    CASE
        WHEN pct_above_threshold > 90 THEN 'CRITICAL'
        WHEN pct_above_threshold > 75 THEN 'HIGH'
        WHEN pct_above_threshold > 50 THEN 'MEDIUM'
        ELSE 'OK'
    END as alert_level
FROM fhq_canonical.eqs_distribution_snapshots
WHERE distribution_collapsed = TRUE
ORDER BY snapshot_date DESC, pct_above_threshold DESC;

-- ============================================================================
-- STEP 8: Log Migration Completion
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
    metadata,
    agent_id,
    timestamp
) VALUES (
    gen_random_uuid(),
    'MIGRATION_DEPLOYED',
    '169_ceo_dir_eqs_calibration_infrastructure',
    'MIGRATION',
    'STIG',
    NOW(),
    'COMPLETED',
    'CEO-DIR-2025-EQS-001: EQS Calibration Infrastructure deployed',
    jsonb_build_object(
        'directive_id', 'CEO-DIR-2025-EQS-001',
        'tables_created', jsonb_build_array(
            'fhq_canonical.eqs_threshold_config',
            'fhq_canonical.eqs_distribution_snapshots'
        ),
        'functions_created', jsonb_build_array(
            'get_active_eqs_threshold()',
            'capture_eqs_distribution_snapshot()',
            'activate_eqs_threshold()'
        ),
        'views_created', jsonb_build_array(
            'v_eqs_distribution_alerts'
        ),
        'initial_threshold', 0.85,
        'stig_responsibilities', jsonb_build_array(
            'Configurable threshold enforcement',
            'Daily distribution logging',
            'Reject hardcoded thresholds'
        )
    ),
    'STIG',
    NOW()
);

COMMIT;
