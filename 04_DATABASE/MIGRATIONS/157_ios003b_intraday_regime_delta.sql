-- =============================================================================
-- MIGRATION 157: IoS-003-B INTRADAY REGIME-DELTA SYSTEM
-- =============================================================================
-- Constitutional Basis: LARS CEO Directive - Intraday Regime-Delta Implementation
-- ADR Compliance: ADR-013 (Canonical Integrity), ADR-014 (Sub-Executive Governance)
-- ADR-017 (MIT-QUAD), ADR-020 (ACI)
--
-- PURPOSE:
-- Implements a dual-layer "Climate vs Weather" regime architecture:
-- - Daily Canonical Regime = slow "climate" (unchanged, ADR-013 compliant)
-- - Intraday Regime-Delta = fast "weather" (ephemeral, TTL-bound)
--
-- KEY CONSTRAINTS:
-- 1. Canonical regime (fhq_perception.regime_daily) is NEVER modified
-- 2. All intraday data carries TTL and expires automatically
-- 3. No circular feedback into canonical regime log
-- 4. DEFCON safeguards always override intraday permits
-- =============================================================================

BEGIN;

-- =============================================================================
-- SECTION 1: OPERATIONAL SCHEMA FOR EPHEMERAL DATA
-- =============================================================================

-- Create fhq_operational schema for non-canonical operational data
CREATE SCHEMA IF NOT EXISTS fhq_operational;

COMMENT ON SCHEMA fhq_operational IS
    'Ephemeral operational data - NOT canonical, subject to TTL expiration. IoS-003-B intraday regime delta lives here.';

-- =============================================================================
-- SECTION 2: INTRADAY OHLCV AGGREGATION TABLES
-- =============================================================================

-- H1 (1-hour) aggregated bars from tick data
CREATE TABLE IF NOT EXISTS fhq_operational.intraday_bars_h1 (
    bar_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id TEXT NOT NULL,
    bar_timestamp TIMESTAMPTZ NOT NULL,  -- Start of the hour
    open_price NUMERIC(20, 8) NOT NULL,
    high_price NUMERIC(20, 8) NOT NULL,
    low_price NUMERIC(20, 8) NOT NULL,
    close_price NUMERIC(20, 8) NOT NULL,
    volume NUMERIC(20, 8) DEFAULT 0,
    tick_count INTEGER DEFAULT 0,
    source TEXT DEFAULT 'BINANCE',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '7 days',  -- Rolling 7-day window
    UNIQUE(listing_id, bar_timestamp)
);

CREATE INDEX idx_h1_bars_listing_time ON fhq_operational.intraday_bars_h1(listing_id, bar_timestamp DESC);
CREATE INDEX idx_h1_bars_expires ON fhq_operational.intraday_bars_h1(expires_at);

-- H4 (4-hour) aggregated bars
CREATE TABLE IF NOT EXISTS fhq_operational.intraday_bars_h4 (
    bar_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id TEXT NOT NULL,
    bar_timestamp TIMESTAMPTZ NOT NULL,  -- Start of the 4-hour period
    open_price NUMERIC(20, 8) NOT NULL,
    high_price NUMERIC(20, 8) NOT NULL,
    low_price NUMERIC(20, 8) NOT NULL,
    close_price NUMERIC(20, 8) NOT NULL,
    volume NUMERIC(20, 8) DEFAULT 0,
    tick_count INTEGER DEFAULT 0,
    source TEXT DEFAULT 'BINANCE',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '7 days',
    UNIQUE(listing_id, bar_timestamp)
);

CREATE INDEX idx_h4_bars_listing_time ON fhq_operational.intraday_bars_h4(listing_id, bar_timestamp DESC);
CREATE INDEX idx_h4_bars_expires ON fhq_operational.intraday_bars_h4(expires_at);

-- =============================================================================
-- SECTION 3: INTRADAY REGIME DELTA TABLE
-- =============================================================================

-- The core Regime-Delta table - captures short-term "weather" shifts
CREATE TABLE IF NOT EXISTS fhq_operational.regime_delta (
    delta_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id TEXT NOT NULL,

    -- Detection Context
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    timeframe TEXT NOT NULL CHECK (timeframe IN ('H1', 'H4')),

    -- Delta Classification
    delta_type TEXT NOT NULL CHECK (delta_type IN (
        'VOLATILITY_SQUEEZE',      -- Bollinger inside Keltner
        'SQUEEZE_FIRE_BULL',       -- Breakout upward
        'SQUEEZE_FIRE_BEAR',       -- Breakout downward
        'MOMENTUM_SHIFT_BULL',     -- Short-term bullish pressure
        'MOMENTUM_SHIFT_BEAR',     -- Short-term bearish pressure
        'VOLUME_SURGE',            -- Unusual volume spike
        'TREND_ACCELERATION'       -- Trend gaining momentum
    )),

    -- Quantitative Metrics
    intensity NUMERIC(5, 4) NOT NULL CHECK (intensity BETWEEN 0 AND 1),
    momentum_vector TEXT CHECK (momentum_vector IN ('BULLISH', 'BEARISH', 'NEUTRAL')),
    bollinger_width NUMERIC(10, 6),
    keltner_width NUMERIC(10, 6),
    squeeze_tightness NUMERIC(10, 6),  -- Bollinger width / Keltner width ratio
    momentum_slope NUMERIC(10, 6),
    volume_ratio NUMERIC(10, 4),  -- Current vs average volume

    -- Canonical Context (READ-ONLY reference)
    canonical_regime TEXT,  -- Current daily regime at time of detection
    regime_alignment BOOLEAN,  -- Does delta align with canonical regime?

    -- TTL Management (Critical for ephemeral nature)
    ttl_hours INTEGER NOT NULL DEFAULT 4 CHECK (ttl_hours BETWEEN 1 AND 4),
    expires_at TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,

    -- Governance
    issuing_agent TEXT NOT NULL DEFAULT 'CSEO',  -- Chief Strategy & Experimentation Officer
    signature TEXT,  -- Ed25519 signature per ADR-008

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_regime_delta_active ON fhq_operational.regime_delta(listing_id, is_active, expires_at DESC);
CREATE INDEX idx_regime_delta_type ON fhq_operational.regime_delta(delta_type, detected_at DESC);
CREATE INDEX idx_regime_delta_expires ON fhq_operational.regime_delta(expires_at) WHERE is_active = TRUE;

COMMENT ON TABLE fhq_operational.regime_delta IS
    'Ephemeral intraday regime shifts - NOT canonical. Expires per TTL. IoS-003-B core table.';

-- =============================================================================
-- SECTION 4: FLASH-CONTEXT EVENT TABLE
-- =============================================================================

-- Flash-Context objects broadcast to Signal Executor
CREATE TABLE IF NOT EXISTS fhq_operational.flash_context (
    context_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source
    delta_id UUID REFERENCES fhq_operational.regime_delta(delta_id),
    listing_id TEXT NOT NULL,

    -- Context Payload
    context_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delta_type TEXT NOT NULL,
    intensity NUMERIC(5, 4) NOT NULL,
    momentum_vector TEXT NOT NULL,

    -- Signal Targeting
    target_signal_class TEXT CHECK (target_signal_class IN ('A', 'B', 'C')),
    applicable_strategies TEXT[],  -- Which strategies can use this context

    -- TTL Management
    ttl_minutes INTEGER NOT NULL DEFAULT 60 CHECK (ttl_minutes BETWEEN 15 AND 240),
    expires_at TIMESTAMPTZ NOT NULL,
    is_consumed BOOLEAN DEFAULT FALSE,
    consumed_by_signal_id UUID,
    consumed_at TIMESTAMPTZ,

    -- Governance
    issuing_agent TEXT NOT NULL DEFAULT 'CSEO',
    signature TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_flash_context_active ON fhq_operational.flash_context(listing_id, is_consumed, expires_at DESC);
CREATE INDEX idx_flash_context_expires ON fhq_operational.flash_context(expires_at) WHERE is_consumed = FALSE;

COMMENT ON TABLE fhq_operational.flash_context IS
    'Ephemeral context permits for Signal Executor. Consumed once or expires. IoS-003-B.';

-- =============================================================================
-- SECTION 5: INTRADAY DECISION LOG (Audit Trail)
-- =============================================================================

-- Operational log for all intraday decisions (NOT in governance log)
CREATE TABLE IF NOT EXISTS fhq_operational.delta_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Event Details
    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type TEXT NOT NULL CHECK (event_type IN (
        'DELTA_DETECTED',
        'FLASH_CONTEXT_EMITTED',
        'CONTEXT_CONSUMED',
        'CONTEXT_EXPIRED',
        'EPHEMERAL_PRIMED',
        'EPHEMERAL_REVOKED',
        'EXECUTION_ATTEMPTED',
        'EXECUTION_SUCCESS',
        'EXECUTION_FAILED',
        'TTL_EXPIRED'
    )),

    -- References
    delta_id UUID,
    context_id UUID,
    signal_id UUID,
    listing_id TEXT,

    -- Details
    details JSONB DEFAULT '{}',

    -- Outcome Tracking
    pnl_result NUMERIC(20, 8),
    was_successful BOOLEAN,

    -- Metadata
    agent_id TEXT DEFAULT 'STIG',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_delta_log_time ON fhq_operational.delta_log(event_timestamp DESC);
CREATE INDEX idx_delta_log_type ON fhq_operational.delta_log(event_type, event_timestamp DESC);
CREATE INDEX idx_delta_log_signal ON fhq_operational.delta_log(signal_id) WHERE signal_id IS NOT NULL;

COMMENT ON TABLE fhq_operational.delta_log IS
    'Audit trail for IoS-003-B intraday decisions. Separate from canonical governance log.';

-- =============================================================================
-- SECTION 6: SIGNAL STATE EXTENSION FOR EPHEMERAL_PRIMED
-- =============================================================================

-- Add ephemeral context tracking to signal state
ALTER TABLE fhq_canonical.g5_signal_state
ADD COLUMN IF NOT EXISTS ephemeral_context_id UUID,
ADD COLUMN IF NOT EXISTS ephemeral_primed_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS ephemeral_expires_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS ephemeral_position_scalar NUMERIC(5, 4) DEFAULT 0.5,
ADD COLUMN IF NOT EXISTS is_ephemeral_promotion BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_signal_state_ephemeral
ON fhq_canonical.g5_signal_state(ephemeral_expires_at)
WHERE is_ephemeral_promotion = TRUE;

-- =============================================================================
-- SECTION 7: SQUEEZE DETECTION CONFIGURATION
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_operational.squeeze_config (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id TEXT NOT NULL,

    -- Bollinger Band Settings
    bb_period INTEGER DEFAULT 20,
    bb_std_dev NUMERIC(4, 2) DEFAULT 2.0,

    -- Keltner Channel Settings
    kc_period INTEGER DEFAULT 20,
    kc_atr_mult NUMERIC(4, 2) DEFAULT 1.5,

    -- Momentum Settings
    momentum_period INTEGER DEFAULT 20,
    momentum_smoothing INTEGER DEFAULT 5,

    -- Thresholds
    squeeze_threshold NUMERIC(5, 4) DEFAULT 0.8,  -- BB width / KC width ratio
    intensity_min NUMERIC(5, 4) DEFAULT 0.6,
    volume_surge_mult NUMERIC(5, 2) DEFAULT 1.5,

    -- Signal Class Targeting
    target_signal_classes TEXT[] DEFAULT ARRAY['C'],

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(listing_id)
);

-- Default configurations for primary assets
INSERT INTO fhq_operational.squeeze_config (listing_id, target_signal_classes)
VALUES
    ('BTC-USD', ARRAY['B', 'C']),
    ('ETH-USD', ARRAY['B', 'C']),
    ('SOL-USD', ARRAY['C'])
ON CONFLICT (listing_id) DO NOTHING;

-- =============================================================================
-- SECTION 8: TTL EXPIRATION FUNCTION
-- =============================================================================

-- Function to expire stale intraday data (run periodically)
CREATE OR REPLACE FUNCTION fhq_operational.expire_intraday_data()
RETURNS TABLE(
    expired_deltas INTEGER,
    expired_contexts INTEGER,
    expired_bars_h1 INTEGER,
    expired_bars_h4 INTEGER
) AS $$
DECLARE
    v_expired_deltas INTEGER := 0;
    v_expired_contexts INTEGER := 0;
    v_expired_bars_h1 INTEGER := 0;
    v_expired_bars_h4 INTEGER := 0;
BEGIN
    -- Expire regime deltas
    UPDATE fhq_operational.regime_delta
    SET is_active = FALSE
    WHERE is_active = TRUE AND expires_at < NOW();
    GET DIAGNOSTICS v_expired_deltas = ROW_COUNT;

    -- Log expirations
    INSERT INTO fhq_operational.delta_log (event_type, details)
    SELECT 'TTL_EXPIRED', jsonb_build_object('delta_id', delta_id, 'listing_id', listing_id)
    FROM fhq_operational.regime_delta
    WHERE is_active = FALSE AND expires_at < NOW() AND expires_at > NOW() - INTERVAL '1 minute';

    -- Expire flash contexts (mark, don't delete for audit)
    UPDATE fhq_operational.flash_context
    SET is_consumed = TRUE
    WHERE is_consumed = FALSE AND expires_at < NOW();
    GET DIAGNOSTICS v_expired_contexts = ROW_COUNT;

    -- Clean old H1 bars (older than 7 days)
    DELETE FROM fhq_operational.intraday_bars_h1
    WHERE expires_at < NOW();
    GET DIAGNOSTICS v_expired_bars_h1 = ROW_COUNT;

    -- Clean old H4 bars
    DELETE FROM fhq_operational.intraday_bars_h4
    WHERE expires_at < NOW();
    GET DIAGNOSTICS v_expired_bars_h4 = ROW_COUNT;

    RETURN QUERY SELECT v_expired_deltas, v_expired_contexts, v_expired_bars_h1, v_expired_bars_h4;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SECTION 9: VIEWS FOR MONITORING
-- =============================================================================

-- Active squeeze conditions view
CREATE OR REPLACE VIEW fhq_operational.v_active_squeezes AS
SELECT
    rd.delta_id,
    rd.listing_id,
    rd.detected_at,
    rd.delta_type,
    rd.intensity,
    rd.momentum_vector,
    rd.squeeze_tightness,
    rd.canonical_regime,
    rd.regime_alignment,
    rd.ttl_hours,
    rd.expires_at,
    EXTRACT(EPOCH FROM (rd.expires_at - NOW())) / 60 AS minutes_remaining
FROM fhq_operational.regime_delta rd
WHERE rd.is_active = TRUE
  AND rd.expires_at > NOW()
  AND rd.delta_type LIKE 'VOLATILITY_SQUEEZE%' OR rd.delta_type LIKE 'SQUEEZE_FIRE%'
ORDER BY rd.detected_at DESC;

-- Active flash contexts awaiting consumption
CREATE OR REPLACE VIEW fhq_operational.v_pending_flash_contexts AS
SELECT
    fc.context_id,
    fc.listing_id,
    fc.delta_type,
    fc.intensity,
    fc.momentum_vector,
    fc.target_signal_class,
    fc.applicable_strategies,
    fc.expires_at,
    EXTRACT(EPOCH FROM (fc.expires_at - NOW())) / 60 AS minutes_remaining
FROM fhq_operational.flash_context fc
WHERE fc.is_consumed = FALSE
  AND fc.expires_at > NOW()
ORDER BY fc.intensity DESC, fc.expires_at ASC;

-- Ephemeral signal status
CREATE OR REPLACE VIEW fhq_operational.v_ephemeral_signals AS
SELECT
    ss.state_id,
    ss.needle_id,
    ss.current_state,
    ss.ephemeral_context_id,
    ss.ephemeral_primed_at,
    ss.ephemeral_expires_at,
    ss.ephemeral_position_scalar,
    fc.delta_type,
    fc.intensity,
    fc.momentum_vector,
    EXTRACT(EPOCH FROM (ss.ephemeral_expires_at - NOW())) / 60 AS minutes_remaining
FROM fhq_canonical.g5_signal_state ss
LEFT JOIN fhq_operational.flash_context fc ON ss.ephemeral_context_id = fc.context_id
WHERE ss.is_ephemeral_promotion = TRUE
ORDER BY ss.ephemeral_primed_at DESC;

-- =============================================================================
-- SECTION 10: GOVERNANCE REGISTRATION
-- =============================================================================

-- Register IoS-003-B in the IoS registry
INSERT INTO fhq_meta.ios_registry (
    ios_id, title, version, status, description,
    owner_role, dependencies, content_hash, created_at
) VALUES (
    'IOS-003-B',
    'Intraday Regime-Delta Engine',
    '1.0.0',
    'G0_SUBMITTED',
    'Ephemeral intraday regime detection for Class C signals. Dual-layer climate/weather architecture per LARS directive.',
    'CSEO',
    ARRAY['IOS-003', 'IOS-008'],
    encode(sha256('IOS-003-B-V1.0.0-INTRADAY-REGIME-DELTA'::bytea), 'hex'),
    NOW()
) ON CONFLICT (ios_id) DO UPDATE SET
    version = EXCLUDED.version,
    status = EXCLUDED.status,
    description = EXCLUDED.description;

-- Register in task registry (FINN owns research/strategy, per ADR-014 CSEO would report to FINN)
INSERT INTO fhq_governance.task_registry (
    description, domain, assigned_to, status,
    task_name, task_type, agent_id,
    task_description, task_config, enabled
) VALUES (
    'Intraday Regime-Delta Engine', 'PERCEPTION', 'FINN', 'active',
    'ios003b_intraday_regime_delta', 'VISION_FUNCTION', 'FINN',
    'IoS-003-B: Intraday squeeze detection and momentum analysis for ephemeral signal priming',
    jsonb_build_object(
        'script', 'ios003b_intraday_regime_delta.py',
        'interval_minutes', 15,
        'continuous', true,
        'target_assets', ARRAY['BTC-USD', 'ETH-USD', 'SOL-USD'],
        'ttl_hours', 4,
        'cseo_function', true
    ),
    true
) ON CONFLICT (task_name) DO UPDATE SET
    task_config = EXCLUDED.task_config,
    enabled = EXCLUDED.enabled;

-- =============================================================================
-- SECTION 11: VEGA ATTESTATION (via governance_actions_log)
-- =============================================================================

-- Log the IoS-003-B activation for VEGA audit trail
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    agent_id,
    metadata
) VALUES (
    'IOS_REGISTRATION',
    'IOS-003-B',
    'INFRASTRUCTURE',
    'STIG',
    NOW(),
    'PENDING_VEGA',
    'Intraday Regime-Delta Engine for Class C signal agility per LARS CEO Directive 2025-12-19',
    'STIG',
    jsonb_build_object(
        'ios_id', 'IOS-003-B',
        'title', 'Intraday Regime-Delta Engine',
        'purpose', 'Intraday Regime-Delta for Class C signal agility',
        'constitutional_basis', 'LARS CEO Directive 2025-12-19',
        'security_constraints', ARRAY[
            'Canonical regime never modified',
            'All data ephemeral with TTL',
            'No circular feedback to governance log',
            'DEFCON always overrides'
        ],
        'paper_trading_only', true
    )
);

COMMIT;

-- =============================================================================
-- POST-MIGRATION VERIFICATION
-- =============================================================================
DO $$
BEGIN
    RAISE NOTICE '=== IoS-003-B INTRADAY REGIME-DELTA MIGRATION COMPLETE ===';
    RAISE NOTICE 'Schema: fhq_operational created';
    RAISE NOTICE 'Tables: regime_delta, flash_context, delta_log, intraday_bars_h1/h4';
    RAISE NOTICE 'Signal state extended with ephemeral columns';
    RAISE NOTICE 'TTL expiration function installed';
    RAISE NOTICE 'IoS-003-B registered in ios_registry and task_registry';
    RAISE NOTICE '';
    RAISE NOTICE 'NEXT STEPS:';
    RAISE NOTICE '1. Deploy ios003b_intraday_regime_delta.py';
    RAISE NOTICE '2. Update signal_executor_daemon.py for EPHEMERAL_PRIMED';
    RAISE NOTICE '3. Run paper trading validation';
    RAISE NOTICE '==========================================================';
END $$;
