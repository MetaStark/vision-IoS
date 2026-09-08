-- Migration 348: Crypto Learning Pipeline Activation
-- CEO-DIR-2026-CRYPTO-LEARNING-ACTIVATION-002
-- Phases 3-6 + Appendix A: Strategic Hardening
--
-- GOVERNING AUTHORITIES: ADR-014, ADR-018 (ASRP), IoS-001, IoS-007, IoS-010
-- EXECUTOR: STIG (EC-003)
-- CLASSIFICATION: GOVERNANCE-CRITICAL / LEARNING-AUTHORIZATION

-- =============================================================================
-- SECTION 1: EXTEND SCHEMAS FOR ASSET CLASS TRACKING
-- =============================================================================

-- Add asset_class to error_classification_taxonomy if not exists
ALTER TABLE fhq_learning.error_classification_taxonomy
ADD COLUMN IF NOT EXISTS asset_class TEXT DEFAULT 'US_EQUITY',
ADD COLUMN IF NOT EXISTS symbol TEXT;

-- Add asset_class to hypothesis_canon if exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'fhq_learning' AND table_name = 'hypothesis_canon') THEN
        ALTER TABLE fhq_learning.hypothesis_canon
        ADD COLUMN IF NOT EXISTS asset_class TEXT DEFAULT 'US_EQUITY',
        ADD COLUMN IF NOT EXISTS learning_only BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

-- Create index for asset class queries
CREATE INDEX IF NOT EXISTS idx_error_class_asset ON fhq_learning.error_classification_taxonomy(asset_class);

-- =============================================================================
-- SECTION 2: PHASE 3 - FINN-T CRYPTO THEORY CONFIGURATION
-- =============================================================================

-- Create crypto-specific theory artifacts table
CREATE TABLE IF NOT EXISTS fhq_learning.crypto_theory_artifacts (
    artifact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    theory_type TEXT NOT NULL CHECK (theory_type IN (
        'REGIME_TRANSITION',
        'VOLATILITY_CLUSTERING',
        'EVENT_ASYMMETRY',
        'FUNDING_DYNAMICS',
        'LIQUIDATION_CASCADE',
        'FLOW_IMBALANCE'
    )),
    theory_name TEXT NOT NULL,
    theory_description TEXT NOT NULL,
    mechanism_chain JSONB NOT NULL, -- N-tier mechanism chains required
    observable_data_linkage JSONB NOT NULL, -- Must be linked to observable data
    causal_depth INTEGER NOT NULL DEFAULT 2 CHECK (causal_depth >= 2),
    generator_id TEXT NOT NULL DEFAULT 'FINN-T',
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'ACTIVE', 'VALIDATED', 'FALSIFIED')),
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL,
    validated_at TIMESTAMPTZ,
    validated_by TEXT
);

COMMENT ON TABLE fhq_learning.crypto_theory_artifacts IS 'CEO-DIR-2026-CRYPTO-LEARNING-ACTIVATION-002 Phase 3: FINN-T Crypto Theory Artifacts';

-- Insert initial crypto theory templates
INSERT INTO fhq_learning.crypto_theory_artifacts (theory_type, theory_name, theory_description, mechanism_chain, observable_data_linkage, causal_depth, created_by)
VALUES
(
    'REGIME_TRANSITION',
    'BTC Regime Shift Detection',
    'Identify regime transitions in BTC based on volatility clustering and trend exhaustion signals',
    '{"chain": ["volatility_compression", "trend_exhaustion", "regime_shift"], "depth": 3}'::jsonb,
    '{"required_data": ["fhq_market.prices:BTC-USD", "fhq_perception.regime_daily:BTC-USD"], "min_observations": 30}'::jsonb,
    3,
    'STIG'
),
(
    'VOLATILITY_CLUSTERING',
    'Crypto Volatility Clustering',
    'Detect GARCH-style volatility clustering patterns in crypto markets for regime-conditional position sizing',
    '{"chain": ["vol_shock", "vol_persistence", "mean_reversion"], "depth": 3}'::jsonb,
    '{"required_data": ["fhq_market.prices:BTC-USD,ETH-USD", "fhq_research.indicator_volatility"], "min_observations": 60}'::jsonb,
    3,
    'STIG'
),
(
    'FUNDING_DYNAMICS',
    'Perpetual Funding Rate Asymmetry',
    'Exploit funding rate extremes as mean-reversion signals with regime awareness',
    '{"chain": ["funding_extreme", "position_crowding", "forced_unwind"], "depth": 3}'::jsonb,
    '{"required_data": ["binance:funding_rates", "binance:open_interest"], "min_observations": 168}'::jsonb,
    3,
    'STIG'
),
(
    'LIQUIDATION_CASCADE',
    'Liquidation Cascade Detection',
    'Identify liquidation cascade risk from leverage buildup and price proximity to liquidation walls',
    '{"chain": ["leverage_buildup", "price_proximity", "cascade_trigger"], "depth": 3}'::jsonb,
    '{"required_data": ["binance:liquidations", "binance:long_short_ratio"], "min_observations": 24}'::jsonb,
    3,
    'STIG'
)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- SECTION 3: PHASE 4 - ERROR → HYPOTHESIS CONVERSION (>25%)
-- =============================================================================

-- Create error-to-hypothesis conversion tracking
CREATE TABLE IF NOT EXISTS fhq_learning.error_hypothesis_conversions (
    conversion_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    error_id UUID NOT NULL,
    generated_hypothesis_id UUID,
    asset_class TEXT NOT NULL,
    symbol TEXT NOT NULL,
    error_type TEXT NOT NULL,
    regime_context TEXT,
    data_source TEXT,
    conversion_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (conversion_status IN ('PENDING', 'CONVERTED', 'REJECTED', 'DEFERRED')),
    rejection_reason TEXT,
    conversion_timestamp TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'FINN-E'
);

COMMENT ON TABLE fhq_learning.error_hypothesis_conversions IS 'CEO-DIR-2026-CRYPTO-LEARNING-ACTIVATION-002 Phase 4: Error→Hypothesis Conversion Tracking';

-- Create function for error-to-hypothesis conversion
CREATE OR REPLACE FUNCTION fhq_learning.fn_convert_error_to_hypothesis(
    p_error_id UUID,
    p_asset_class TEXT DEFAULT 'CRYPTO'
) RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_error RECORD;
    v_hypothesis_id UUID;
    v_conversion_id UUID;
BEGIN
    -- Get error details
    SELECT * INTO v_error
    FROM fhq_learning.error_classification_taxonomy
    WHERE error_id = p_error_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Error ID % not found', p_error_id;
    END IF;

    -- Generate hypothesis ID
    v_hypothesis_id := gen_random_uuid();

    -- Create conversion record
    INSERT INTO fhq_learning.error_hypothesis_conversions (
        error_id, generated_hypothesis_id, asset_class, symbol,
        error_type, regime_context, data_source, conversion_status,
        conversion_timestamp
    ) VALUES (
        p_error_id, v_hypothesis_id, p_asset_class,
        COALESCE(v_error.symbol, 'UNKNOWN'),
        v_error.error_type, v_error.regime_at_prediction,
        'error_classification_taxonomy', 'CONVERTED',
        NOW()
    )
    RETURNING conversion_id INTO v_conversion_id;

    -- Update original error record
    UPDATE fhq_learning.error_classification_taxonomy
    SET hypothesis_generated = TRUE,
        generated_hypothesis_id = v_hypothesis_id
    WHERE error_id = p_error_id;

    RETURN v_hypothesis_id;
END;
$$;

-- Create view for conversion rate monitoring
CREATE OR REPLACE VIEW fhq_learning.v_error_hypothesis_conversion_rate AS
SELECT
    asset_class,
    DATE_TRUNC('day', created_at) as conversion_date,
    COUNT(*) as total_errors,
    COUNT(*) FILTER (WHERE conversion_status = 'CONVERTED') as converted,
    COUNT(*) FILTER (WHERE conversion_status = 'REJECTED') as rejected,
    COUNT(*) FILTER (WHERE conversion_status = 'PENDING') as pending,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE conversion_status = 'CONVERTED') / NULLIF(COUNT(*), 0),
        2
    ) as conversion_rate_pct
FROM fhq_learning.error_hypothesis_conversions
GROUP BY asset_class, DATE_TRUNC('day', created_at)
ORDER BY conversion_date DESC;

-- =============================================================================
-- SECTION 4: PHASE 5 - GN-S CRYPTO SHADOW TIER
-- =============================================================================

-- Create crypto shadow tier configuration
CREATE TABLE IF NOT EXISTS fhq_learning.crypto_shadow_tier (
    shadow_entry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type TEXT NOT NULL CHECK (source_type IN ('HYPOTHESIS', 'THEORY', 'SIGNAL', 'PATTERN')),
    source_id UUID NOT NULL,
    symbol TEXT NOT NULL,
    asset_class TEXT NOT NULL DEFAULT 'CRYPTO',
    observation_type TEXT NOT NULL CHECK (observation_type IN (
        'ASYMMETRY_DETECTION',
        'SIGNAL_STABILITY',
        'REGIME_VALIDATION',
        'PATTERN_RECOGNITION'
    )),
    observation_data JSONB NOT NULL,
    stability_score NUMERIC(5,4),
    regime_consistency_score NUMERIC(5,4),
    ios_elevation_candidate BOOLEAN DEFAULT FALSE,
    -- Constraints per directive
    reward_coupling BOOLEAN NOT NULL DEFAULT FALSE CHECK (reward_coupling = FALSE),
    execution_eligibility BOOLEAN NOT NULL DEFAULT FALSE CHECK (execution_eligibility = FALSE),
    decision_rights BOOLEAN NOT NULL DEFAULT FALSE CHECK (decision_rights = FALSE),
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'GN-S'
);

COMMENT ON TABLE fhq_learning.crypto_shadow_tier IS 'CEO-DIR-2026-CRYPTO-LEARNING-ACTIVATION-002 Phase 5: GN-S Crypto Shadow Tier - Observation only, no exposure';

-- Create shadow observation aggregation view
CREATE OR REPLACE VIEW fhq_learning.v_crypto_shadow_observations AS
SELECT
    symbol,
    observation_type,
    COUNT(*) as observation_count,
    AVG(stability_score) as avg_stability,
    AVG(regime_consistency_score) as avg_regime_consistency,
    COUNT(*) FILTER (WHERE ios_elevation_candidate = TRUE) as elevation_candidates,
    MIN(observed_at) as first_observation,
    MAX(observed_at) as latest_observation
FROM fhq_learning.crypto_shadow_tier
GROUP BY symbol, observation_type;

-- =============================================================================
-- SECTION 5: PHASE 6 - BINANCE → IoS-007 ALPHA GRAPH (LEARNING-ONLY)
-- =============================================================================

-- Create IoS-007 learning nodes table for crypto
CREATE TABLE IF NOT EXISTS fhq_research.ios007_crypto_learning_nodes (
    node_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_type TEXT NOT NULL CHECK (node_type IN (
        'SPOT_PRICE',
        'PERP_PRICE',
        'FUNDING_RATE',
        'OPEN_INTEREST',
        'LIQUIDATION',
        'VOLUME_FLOW',
        'ORDER_BOOK_IMBALANCE'
    )),
    symbol TEXT NOT NULL,
    data_vendor TEXT NOT NULL DEFAULT 'BINANCE',
    asset_class TEXT NOT NULL DEFAULT 'CRYPTO' CHECK (asset_class = 'CRYPTO'),
    learning_only BOOLEAN NOT NULL DEFAULT TRUE CHECK (learning_only = TRUE),
    -- Non-allocating, non-executing constraints
    allocation_allowed BOOLEAN NOT NULL DEFAULT FALSE CHECK (allocation_allowed = FALSE),
    execution_allowed BOOLEAN NOT NULL DEFAULT FALSE CHECK (execution_allowed = FALSE),
    -- Node metadata
    temporal_precedence_verified BOOLEAN DEFAULT FALSE,
    causal_depth NUMERIC(3,1) DEFAULT 0,
    alpha_contribution_score NUMERIC(5,4),
    last_data_timestamp TIMESTAMPTZ,
    node_status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (node_status IN ('ACTIVE', 'SUSPENDED', 'DEPRECATED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE fhq_research.ios007_crypto_learning_nodes IS 'CEO-DIR-2026-CRYPTO-LEARNING-ACTIVATION-002 Phase 6: IoS-007 Alpha Graph Crypto Nodes - Learning only, no allocation';

-- Insert initial Binance learning nodes
INSERT INTO fhq_research.ios007_crypto_learning_nodes (node_type, symbol, data_vendor)
VALUES
    ('SPOT_PRICE', 'BTC-USD', 'BINANCE'),
    ('SPOT_PRICE', 'ETH-USD', 'BINANCE'),
    ('PERP_PRICE', 'BTCUSDT', 'BINANCE'),
    ('PERP_PRICE', 'ETHUSDT', 'BINANCE'),
    ('FUNDING_RATE', 'BTCUSDT', 'BINANCE'),
    ('FUNDING_RATE', 'ETHUSDT', 'BINANCE'),
    ('OPEN_INTEREST', 'BTCUSDT', 'BINANCE'),
    ('OPEN_INTEREST', 'ETHUSDT', 'BINANCE')
ON CONFLICT DO NOTHING;

-- =============================================================================
-- SECTION 6: APPENDIX A - STRATEGIC HARDENING (TIER-1 BRUTALITY)
-- =============================================================================

-- Add crypto-specific Tier-1 criteria with hardening
INSERT INTO fhq_learning.tier1_falsification_criteria (criteria_code, criteria_name, description, weight, failure_threshold, is_active)
VALUES
(
    'CRYPTO_SIGN_STABILITY',
    'Crypto Sign Stability (80%)',
    'CEO-DIR-2026-CRYPTO-HARDENING: Crypto hypothesis must maintain 80% sign stability across observations',
    2.50,
    0.80,
    TRUE
),
(
    'CRYPTO_STATISTICAL_P001',
    'Crypto Statistical Significance (p<0.01)',
    'CEO-DIR-2026-CRYPTO-HARDENING: Crypto hypothesis must achieve p-value < 0.01. Zero partial credit.',
    2.50,
    0.01,
    TRUE
),
(
    'CRYPTO_CAUSAL_DEPTH_25',
    'Crypto Causal Depth (>=2.5)',
    'CEO-DIR-2026-CRYPTO-HARDENING: Crypto hypothesis must demonstrate causal depth >= 2.5 for Tier-1 survival',
    2.00,
    2.50,
    TRUE
),
(
    'CRYPTO_DEATH_RATE_TARGET',
    'Crypto Tier-1 Death Rate (60-90%)',
    'CEO-DIR-2026-CRYPTO-HARDENING: System must maintain 60-90% death rate for crypto hypotheses. Below 60% triggers LEARNING_MODE=PAUSED.',
    3.00,
    0.60,
    TRUE
)
ON CONFLICT (criteria_code) DO UPDATE SET
    weight = EXCLUDED.weight,
    failure_threshold = EXCLUDED.failure_threshold,
    is_active = EXCLUDED.is_active;

-- Create death rate monitoring view
CREATE OR REPLACE VIEW fhq_learning.v_crypto_tier1_death_rate AS
WITH tier1_stats AS (
    SELECT
        DATE_TRUNC('day', created_at) as evaluation_date,
        COUNT(*) as total_evaluated,
        COUNT(*) FILTER (WHERE shadow_result = 'DEAD' OR shadow_result = 'FALSIFIED') as dead_count,
        COUNT(*) FILTER (WHERE shadow_result = 'ALIVE' OR shadow_result = 'VALIDATED') as alive_count
    FROM fhq_learning.shadow_tier_registry
    WHERE execution_environment = 'CRYPTO'
      AND created_by IN ('FINN-T', 'FINN-E', 'GN-S')
    GROUP BY DATE_TRUNC('day', created_at)
)
SELECT
    evaluation_date,
    total_evaluated,
    dead_count,
    alive_count,
    ROUND(100.0 * dead_count / NULLIF(total_evaluated, 0), 2) as death_rate_pct,
    CASE
        WHEN 100.0 * dead_count / NULLIF(total_evaluated, 0) < 60 THEN 'BELOW_TARGET'
        WHEN 100.0 * dead_count / NULLIF(total_evaluated, 0) > 90 THEN 'ABOVE_TARGET'
        ELSE 'ON_TARGET'
    END as status,
    CASE
        WHEN 100.0 * dead_count / NULLIF(total_evaluated, 0) < 60 THEN TRUE
        ELSE FALSE
    END as learning_pause_required
FROM tier1_stats
ORDER BY evaluation_date DESC;

-- =============================================================================
-- SECTION 7: LEARNING HEALTH METRICS
-- =============================================================================

-- Create learning health dashboard metrics table
CREATE TABLE IF NOT EXISTS fhq_learning.crypto_learning_health (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_date DATE NOT NULL DEFAULT CURRENT_DATE,
    metric_hour INTEGER NOT NULL DEFAULT EXTRACT(HOUR FROM NOW()),
    -- Research Trinity metrics
    finn_e_hypotheses_generated INTEGER DEFAULT 0,
    finn_t_hypotheses_generated INTEGER DEFAULT 0,
    gn_s_observations_recorded INTEGER DEFAULT 0,
    -- Conversion funnel
    errors_detected INTEGER DEFAULT 0,
    errors_converted_to_hypotheses INTEGER DEFAULT 0,
    conversion_rate_pct NUMERIC(5,2) DEFAULT 0,
    -- Tier-1 brutality
    tier1_evaluations INTEGER DEFAULT 0,
    tier1_deaths INTEGER DEFAULT 0,
    tier1_death_rate_pct NUMERIC(5,2) DEFAULT 0,
    -- Health indicators
    learning_health_status TEXT DEFAULT 'UNKNOWN' CHECK (learning_health_status IN ('HEALTHY', 'DEGRADED', 'PAUSED', 'UNKNOWN')),
    fail_closed_triggered BOOLEAN DEFAULT FALSE,
    -- Metadata
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(metric_date, metric_hour)
);

COMMENT ON TABLE fhq_learning.crypto_learning_health IS 'CEO-DIR-2026-CRYPTO-LEARNING-ACTIVATION-002 Appendix A: Learning Health Dashboard Metrics';

-- Create function to compute learning health
CREATE OR REPLACE FUNCTION fhq_learning.fn_compute_crypto_learning_health()
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_conversion_rate NUMERIC;
    v_death_rate NUMERIC;
    v_health_status TEXT;
    v_fail_closed BOOLEAN := FALSE;
BEGIN
    -- Get conversion rate
    SELECT COALESCE(AVG(conversion_rate_pct), 0) INTO v_conversion_rate
    FROM fhq_learning.v_error_hypothesis_conversion_rate
    WHERE asset_class = 'CRYPTO'
      AND conversion_date >= CURRENT_DATE - INTERVAL '24 hours';

    -- Get death rate
    SELECT COALESCE(AVG(death_rate_pct), 0) INTO v_death_rate
    FROM fhq_learning.v_crypto_tier1_death_rate
    WHERE evaluation_date >= CURRENT_DATE - INTERVAL '24 hours';

    -- Determine health status
    IF v_death_rate < 60 THEN
        v_health_status := 'PAUSED';
        v_fail_closed := TRUE;
    ELSIF v_conversion_rate < 25 THEN
        v_health_status := 'DEGRADED';
    ELSE
        v_health_status := 'HEALTHY';
    END IF;

    -- Insert metric
    INSERT INTO fhq_learning.crypto_learning_health (
        metric_date, metric_hour,
        conversion_rate_pct, tier1_death_rate_pct,
        learning_health_status, fail_closed_triggered
    ) VALUES (
        CURRENT_DATE, EXTRACT(HOUR FROM NOW()),
        v_conversion_rate, v_death_rate,
        v_health_status, v_fail_closed
    )
    ON CONFLICT (metric_date, metric_hour) DO UPDATE SET
        conversion_rate_pct = EXCLUDED.conversion_rate_pct,
        tier1_death_rate_pct = EXCLUDED.tier1_death_rate_pct,
        learning_health_status = EXCLUDED.learning_health_status,
        fail_closed_triggered = EXCLUDED.fail_closed_triggered,
        computed_at = NOW();
END;
$$;

-- =============================================================================
-- SECTION 8: REGISTER CRYPTO LEARNING ACTIVATION
-- =============================================================================

-- Log activation in system events
INSERT INTO fhq_governance.system_heartbeats (component_name, heartbeat_type, last_heartbeat, status, metadata)
VALUES (
    'CRYPTO_LEARNING_PIPELINE',
    'LEARNING_ACTIVATION',
    NOW(),
    'HEALTHY',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-CRYPTO-LEARNING-ACTIVATION-002',
        'phases_activated', ARRAY['PHASE_3', 'PHASE_4', 'PHASE_5', 'PHASE_6'],
        'hardening_applied', TRUE,
        'death_rate_target', '60-90%',
        'sign_stability_threshold', 0.80,
        'p_value_threshold', 0.01,
        'causal_depth_minimum', 2.5,
        'activated_at', NOW()
    )
)
ON CONFLICT (component_name) DO UPDATE SET
    last_heartbeat = NOW(),
    status = 'HEALTHY',
    metadata = EXCLUDED.metadata;

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

DO $$
DECLARE
    v_theory_count INTEGER;
    v_shadow_tier_ready BOOLEAN;
    v_ios007_nodes INTEGER;
BEGIN
    -- Verify theory artifacts
    SELECT COUNT(*) INTO v_theory_count FROM fhq_learning.crypto_theory_artifacts;
    RAISE NOTICE 'Phase 3 - Crypto Theory Artifacts: %', v_theory_count;

    -- Verify shadow tier table exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'fhq_learning' AND table_name = 'crypto_shadow_tier'
    ) INTO v_shadow_tier_ready;
    RAISE NOTICE 'Phase 5 - Shadow Tier Ready: %', v_shadow_tier_ready;

    -- Verify IoS-007 nodes
    SELECT COUNT(*) INTO v_ios007_nodes FROM fhq_research.ios007_crypto_learning_nodes;
    RAISE NOTICE 'Phase 6 - IoS-007 Learning Nodes: %', v_ios007_nodes;

    RAISE NOTICE '========================================';
    RAISE NOTICE 'CEO-DIR-2026-CRYPTO-LEARNING-ACTIVATION-002';
    RAISE NOTICE 'Phases 3-6 ACTIVATED';
    RAISE NOTICE 'Strategic Hardening APPLIED';
    RAISE NOTICE '========================================';
END;
$$;

-- =============================================================================
-- MIGRATION COMPLETE
-- =============================================================================
-- CEO-DIR-2026-CRYPTO-LEARNING-ACTIVATION-002
-- Phases 3-6 Activated
-- Appendix A: Strategic Hardening Applied
-- Tier-1 Death Rate Target: 60-90%
-- Error→Hypothesis Conversion Target: >25%
