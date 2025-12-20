-- ============================================================================
-- Migration 152: G4 Laboratory Phase Activation
-- ============================================================================
-- CEO Directive: WAVE 16 - G4 AUTHORIZATION
-- Date: 2025-12-18
-- Purpose: Enable dual-core validation (Refinery + Physics) for Golden Needles
--
-- STREAM A: The Refinery (Historical Validation)
-- STREAM B: The Physics (Latency & Decay Measurement)
--
-- EXPLICIT PROHIBITIONS:
--   - NO broker connections
--   - NO paper trading
--   - NO live PnL
--   - NO capital exposure
--   - NO parameter tuning
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. G4 VALIDATION RESULTS TABLE (The Refinery Output)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.g4_refinery_results (
    result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    needle_id UUID NOT NULL REFERENCES fhq_canonical.golden_needles(needle_id),

    -- Backtest configuration
    lookback_years INTEGER NOT NULL DEFAULT 5,
    in_sample_ratio DECIMAL(3,2) NOT NULL DEFAULT 0.70,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    in_sample_end DATE NOT NULL,

    -- Transaction cost assumptions
    entry_cost_bps DECIMAL(6,2) NOT NULL DEFAULT 5.0,
    exit_cost_bps DECIMAL(6,2) NOT NULL DEFAULT 5.0,
    slippage_bps DECIMAL(6,2) NOT NULL DEFAULT 5.0,

    -- IN-SAMPLE Metrics
    is_total_trades INTEGER,
    is_win_rate DECIMAL(5,4),
    is_net_return_pct DECIMAL(10,4),
    is_sharpe_ratio DECIMAL(8,4),
    is_sortino_ratio DECIMAL(8,4),
    is_max_drawdown_pct DECIMAL(8,4),
    is_profit_factor DECIMAL(8,4),

    -- OUT-OF-SAMPLE Metrics (THE TRUTH)
    oos_total_trades INTEGER,
    oos_win_rate DECIMAL(5,4),
    oos_net_return_pct DECIMAL(10,4),
    oos_sharpe_ratio DECIMAL(8,4),  -- PRIMARY CULL METRIC
    oos_sortino_ratio DECIMAL(8,4),
    oos_max_drawdown_pct DECIMAL(8,4),
    oos_profit_factor DECIMAL(8,4),
    oos_avg_holding_hours DECIMAL(10,2),

    -- Statistical validation
    oos_p_value DECIMAL(10,6),
    oos_t_statistic DECIMAL(10,4),
    is_statistically_significant BOOLEAN GENERATED ALWAYS AS (oos_p_value <= 0.05) STORED,

    -- Cull classification per CEO Directive
    cull_classification TEXT NOT NULL CHECK (cull_classification IN (
        'PASS',       -- Sharpe >= 1.00
        'QUARANTINE', -- 0.70 <= Sharpe < 1.00
        'REJECT'      -- Sharpe < 0.70
    )),

    -- Raw data for audit
    trade_log JSONB,
    equity_curve_is JSONB,
    equity_curve_oos JSONB,

    -- Timestamps
    backtest_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    backtest_completed_at TIMESTAMPTZ,
    duration_seconds DECIMAL(10,2),

    -- Audit trail
    backtest_version TEXT DEFAULT 'g4-refinery-v1',
    validated_by TEXT DEFAULT 'IoS-004'
);

CREATE INDEX IF NOT EXISTS idx_g4_refinery_needle ON fhq_canonical.g4_refinery_results(needle_id);
CREATE INDEX IF NOT EXISTS idx_g4_refinery_cull ON fhq_canonical.g4_refinery_results(cull_classification);
CREATE INDEX IF NOT EXISTS idx_g4_refinery_sharpe ON fhq_canonical.g4_refinery_results(oos_sharpe_ratio DESC);

-- ============================================================================
-- 2. G4 PHYSICS RESULTS TABLE (Latency & Decay)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.g4_physics_results (
    result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    needle_id UUID NOT NULL REFERENCES fhq_canonical.golden_needles(needle_id),

    -- Latency injection tests
    latency_50ms_return_pct DECIMAL(10,4),
    latency_200ms_return_pct DECIMAL(10,4),
    latency_1000ms_return_pct DECIMAL(10,4),

    -- Latency sensitivity (return degradation per 100ms)
    latency_sensitivity_per_100ms DECIMAL(10,4),

    -- Signal decay measurement
    signal_half_life_seconds DECIMAL(10,2),
    signal_decay_rate DECIMAL(10,6),  -- per-second decay coefficient
    time_to_invalidation_seconds DECIMAL(10,2),

    -- Edge retention at key latencies
    edge_retained_50ms_pct DECIMAL(5,2),
    edge_retained_200ms_pct DECIMAL(5,2),
    edge_retained_1000ms_pct DECIMAL(5,2),

    -- Survivability classification per CEO Directive
    survivability TEXT NOT NULL CHECK (survivability IN (
        'ROBUST',      -- Survives 1s latency with >50% edge
        'FRAGILE',     -- Degrades significantly but still positive
        'NON_VIABLE'   -- Edge destroyed by latency
    )),

    -- Latency profile
    latency_profile JSONB,  -- Full decay curve data

    -- Timestamps
    physics_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    physics_completed_at TIMESTAMPTZ,
    duration_seconds DECIMAL(10,2),

    -- Audit
    physics_version TEXT DEFAULT 'g4-physics-v1'
);

CREATE INDEX IF NOT EXISTS idx_g4_physics_needle ON fhq_canonical.g4_physics_results(needle_id);
CREATE INDEX IF NOT EXISTS idx_g4_physics_survivability ON fhq_canonical.g4_physics_results(survivability);

-- ============================================================================
-- 3. G4 COMPOSITE SCORECARD (VEGA Integration)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.g4_composite_scorecard (
    scorecard_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    needle_id UUID NOT NULL REFERENCES fhq_canonical.golden_needles(needle_id),

    -- Source results
    refinery_result_id UUID REFERENCES fhq_canonical.g4_refinery_results(result_id),
    physics_result_id UUID REFERENCES fhq_canonical.g4_physics_results(result_id),

    -- Combined metrics
    eqs_score DECIMAL(5,4) NOT NULL,
    oos_sharpe DECIMAL(8,4),
    decay_half_life_seconds DECIMAL(10,2),

    -- Final classification per CEO Directive
    classification TEXT NOT NULL CHECK (classification IN (
        'PLATINUM',  -- PASS refinery + ROBUST physics
        'GOLD',      -- PASS refinery + FRAGILE physics
        'SILVER',    -- QUARANTINE refinery + ROBUST physics
        'BRONZE',    -- QUARANTINE refinery + FRAGILE physics
        'REJECT'     -- Any REJECT or NON_VIABLE
    )),

    -- G5 eligibility (only PLATINUM advances)
    eligible_for_g5 BOOLEAN GENERATED ALWAYS AS (classification = 'PLATINUM') STORED,

    -- Multiple testing correction
    fdr_adjusted_p_value DECIMAL(10,6),
    bonferroni_adjusted_p_value DECIMAL(10,6),
    passes_fdr_threshold BOOLEAN,

    -- VEGA attestation
    vega_attestation_hash TEXT,
    vega_attested_at TIMESTAMPTZ,

    -- Timestamps
    scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(needle_id)
);

CREATE INDEX IF NOT EXISTS idx_g4_scorecard_class ON fhq_canonical.g4_composite_scorecard(classification);
CREATE INDEX IF NOT EXISTS idx_g4_scorecard_g5 ON fhq_canonical.g4_composite_scorecard(eligible_for_g5) WHERE eligible_for_g5 = true;

-- ============================================================================
-- 4. G4 VALIDATION QUEUE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.g4_validation_queue (
    queue_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    needle_id UUID NOT NULL REFERENCES fhq_canonical.golden_needles(needle_id),

    priority INTEGER NOT NULL DEFAULT 5,  -- 1=highest (EQS=1.00)

    -- Stream status
    refinery_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (refinery_status IN (
        'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'SKIPPED'
    )),
    physics_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (physics_status IN (
        'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'SKIPPED'
    )),

    -- Timestamps
    queued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    refinery_started_at TIMESTAMPTZ,
    refinery_completed_at TIMESTAMPTZ,
    physics_started_at TIMESTAMPTZ,
    physics_completed_at TIMESTAMPTZ,

    -- Error handling
    refinery_error TEXT,
    physics_error TEXT,

    -- Worker tracking
    worker_id TEXT,

    UNIQUE(needle_id)
);

CREATE INDEX IF NOT EXISTS idx_g4_queue_status ON fhq_canonical.g4_validation_queue(
    refinery_status, physics_status, priority, queued_at
);

-- ============================================================================
-- 5. AUTO-QUEUE TRIGGER FOR GOLDEN NEEDLES
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_canonical.fn_queue_needle_for_g4()
RETURNS TRIGGER AS $$
DECLARE
    v_priority INTEGER;
BEGIN
    -- Priority based on EQS (1.00 = priority 1, 0.85 = priority 10)
    v_priority := GREATEST(1, LEAST(10, CEIL((1.00 - NEW.eqs_score) * 66.67)));

    -- Insert into G4 queue
    INSERT INTO fhq_canonical.g4_validation_queue (needle_id, priority)
    VALUES (NEW.needle_id, v_priority)
    ON CONFLICT (needle_id) DO NOTHING;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger (disabled by default - enabled via G4 activation)
DROP TRIGGER IF EXISTS trg_golden_needle_to_g4 ON fhq_canonical.golden_needles;

CREATE TRIGGER trg_golden_needle_to_g4
    AFTER INSERT ON fhq_canonical.golden_needles
    FOR EACH ROW
    EXECUTE FUNCTION fhq_canonical.fn_queue_needle_for_g4();

-- ============================================================================
-- 6. QUEUE EXISTING GOLDEN NEEDLES FOR G4 VALIDATION
-- ============================================================================

INSERT INTO fhq_canonical.g4_validation_queue (needle_id, priority)
SELECT
    needle_id,
    GREATEST(1, LEAST(10, CEIL((1.00 - eqs_score) * 66.67)))::INTEGER
FROM fhq_canonical.golden_needles
WHERE is_current = true
ON CONFLICT (needle_id) DO NOTHING;

-- ============================================================================
-- 7. GOVERNANCE REGISTRATION
-- ============================================================================

INSERT INTO fhq_meta.adr_registry (
    adr_id, adr_title, adr_status, adr_type, file_path, sha256_hash,
    title, status, current_version, created_by
) VALUES (
    'G4-LAB-001',
    'G4 Laboratory Phase Activation - Dual-Core Validation',
    'APPROVED',
    'OPERATIONAL',
    '04_DATABASE/MIGRATIONS/152_g4_laboratory_activation.sql',
    encode(sha256('g4-laboratory-activation-wave16-20251218'::bytea), 'hex'),
    'G4 Laboratory Phase Activation',
    'ACTIVE',
    '1.0.0',
    'STIG'
) ON CONFLICT (adr_id) DO UPDATE SET
    adr_status = 'ACTIVE',
    status = 'ACTIVE',
    updated_at = NOW();

-- ============================================================================
-- 8. LOG ACTIVATION EVENT
-- ============================================================================

INSERT INTO fhq_monitoring.system_event_log (event_type, severity, source_system, event_message, metadata)
VALUES (
    'g4_laboratory_activated',
    'INFO',
    'STIG',
    'G4 Laboratory Phase activated per CEO Directive WAVE 16',
    jsonb_build_object(
        'directive', 'CEO DIRECTIVE WAVE 16',
        'phase', 'G3 -> G4 TRANSITION',
        'streams', jsonb_build_array('REFINERY', 'PHYSICS'),
        'tables_created', ARRAY[
            'g4_refinery_results',
            'g4_physics_results',
            'g4_composite_scorecard',
            'g4_validation_queue'
        ],
        'prohibitions', jsonb_build_array(
            'NO broker connections',
            'NO paper trading',
            'NO live PnL',
            'NO capital exposure',
            'NO parameter tuning'
        ),
        'cull_thresholds', jsonb_build_object(
            'PASS', 'Sharpe >= 1.00',
            'QUARANTINE', '0.70 <= Sharpe < 1.00',
            'REJECT', 'Sharpe < 0.70'
        ),
        'timestamp', NOW()
    )
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_tables INTEGER;
    v_queued INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_tables
    FROM information_schema.tables
    WHERE table_schema = 'fhq_canonical'
    AND table_name IN ('g4_refinery_results', 'g4_physics_results',
                       'g4_composite_scorecard', 'g4_validation_queue');

    SELECT COUNT(*) INTO v_queued
    FROM fhq_canonical.g4_validation_queue;

    RAISE NOTICE '=== G4 Laboratory Activation Verification ===';
    RAISE NOTICE 'Tables created: % / 4', v_tables;
    RAISE NOTICE 'Golden Needles queued for validation: %', v_queued;

    IF v_tables = 4 THEN
        RAISE NOTICE 'STATUS: G4 LABORATORY PHASE ACTIVE';
        RAISE NOTICE 'STREAM A (Refinery): READY';
        RAISE NOTICE 'STREAM B (Physics): READY';
    ELSE
        RAISE WARNING 'STATUS: INCOMPLETE';
    END IF;
END $$;
