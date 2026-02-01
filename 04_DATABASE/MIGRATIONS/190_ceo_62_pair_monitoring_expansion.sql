-- ============================================================================
-- MIGRATION 190: CEO 62-PAIR MONITORING EXPANSION
-- ============================================================================
-- CEO Directive: "62-PAIR MONITORING EXPANSION"
-- Mode: OBSERVE → QUALIFY → EXECUTE (MONITORING-ONLY initially)
-- Authority: CEO / VEGA enforced
-- Status: APPROVED WITH CONSTRAINTS
--
-- Key Principles:
-- 1. All 62 pairs start in MONITORING-ONLY mode (no execution)
-- 2. Hard liquidity/tradability gates before promotion
-- 3. Regime coverage requirement (2+ regimes)
-- 4. Signal quality thresholds before execution
-- 5. Capital safety constraints (25% single, 40% cluster)
-- 6. VEGA enforcement with auto-block and escalation
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. CRYPTO PAIR REGISTRY (All 62 Alpaca Pairs)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.crypto_pair_registry (
    pair_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(20) NOT NULL UNIQUE,  -- e.g., 'BTC/USD'
    base_asset VARCHAR(10) NOT NULL,      -- e.g., 'BTC'
    quote_asset VARCHAR(10) NOT NULL,     -- e.g., 'USD'

    -- Lifecycle Status
    lifecycle_status VARCHAR(20) NOT NULL DEFAULT 'MONITORING',
    -- MONITORING: Observe only, no execution
    -- QUALIFIED: Passed gates, paper execution allowed (capped)
    -- EXECUTABLE: Full paper execution
    -- LIVE_ELIGIBLE: Future (after global paper profitability)

    -- Timestamps
    added_at TIMESTAMPTZ DEFAULT NOW(),
    qualified_at TIMESTAMPTZ,
    executable_at TIMESTAMPTZ,

    -- Metadata
    cluster_id VARCHAR(50),  -- For correlated cluster tracking
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT,

    CONSTRAINT valid_lifecycle CHECK (lifecycle_status IN
        ('MONITORING', 'QUALIFIED', 'EXECUTABLE', 'LIVE_ELIGIBLE', 'SUSPENDED'))
);

-- ============================================================================
-- 2. LIQUIDITY & TRADABILITY METRICS (Hard Gates)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_monitoring.crypto_liquidity_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(20) NOT NULL REFERENCES fhq_governance.crypto_pair_registry(symbol),
    metric_date DATE NOT NULL,

    -- Liquidity Metrics (CEO Gate 2)
    volume_24h_usd NUMERIC(20,2),           -- Must be >= $5M
    median_spread_bps NUMERIC(10,4),         -- Must be <= 30 bps
    orderbook_depth_50bps NUMERIC(20,2),     -- Must be >= $100k within 0.5%

    -- Volatility Metrics (CEO Gate 2)
    atr_14_pct NUMERIC(10,4),                -- ATR(14) / Price, must be >= 1.5%
    max_single_candle_pct NUMERIC(10,4),     -- Flash spike filter, must be < 15%

    -- Computed Gates
    passes_liquidity_gate BOOLEAN GENERATED ALWAYS AS (
        volume_24h_usd >= 5000000 AND
        median_spread_bps <= 30 AND
        orderbook_depth_50bps >= 100000
    ) STORED,

    passes_volatility_gate BOOLEAN GENERATED ALWAYS AS (
        atr_14_pct >= 1.5 AND
        COALESCE(max_single_candle_pct, 0) < 15
    ) STORED,

    passes_all_gates BOOLEAN GENERATED ALWAYS AS (
        volume_24h_usd >= 5000000 AND
        median_spread_bps <= 30 AND
        orderbook_depth_50bps >= 100000 AND
        atr_14_pct >= 1.5 AND
        COALESCE(max_single_candle_pct, 0) < 15
    ) STORED,

    captured_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(symbol, metric_date)
);

-- ============================================================================
-- 3. SIGNAL QUALITY TRACKING (Per Pair)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_monitoring.crypto_signal_quality (
    quality_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(20) NOT NULL REFERENCES fhq_governance.crypto_pair_registry(symbol),

    -- Signal Counts
    total_signals INTEGER DEFAULT 0,
    signals_in_trend INTEGER DEFAULT 0,
    signals_in_range INTEGER DEFAULT 0,
    signals_in_highvol INTEGER DEFAULT 0,

    -- Quality Metrics (CEO Gate 4)
    signal_consistency_score NUMERIC(5,4) DEFAULT 0,  -- Must be >= 0.55
    false_positive_rate NUMERIC(5,4) DEFAULT 1.0,     -- Must be <= 0.35
    pamphlets_generated INTEGER DEFAULT 0,
    pamphlets_reused INTEGER DEFAULT 0,

    -- Regime Coverage (CEO Gate 3)
    regimes_covered INTEGER GENERATED ALWAYS AS (
        CASE WHEN signals_in_trend > 0 THEN 1 ELSE 0 END +
        CASE WHEN signals_in_range > 0 THEN 1 ELSE 0 END +
        CASE WHEN signals_in_highvol > 0 THEN 1 ELSE 0 END
    ) STORED,

    -- Qualification Gates
    passes_signal_threshold BOOLEAN GENERATED ALWAYS AS (
        total_signals >= 20 AND
        signal_consistency_score >= 0.55 AND
        false_positive_rate <= 0.35 AND
        pamphlets_generated >= 1
    ) STORED,

    passes_regime_coverage BOOLEAN GENERATED ALWAYS AS (
        (CASE WHEN signals_in_trend > 0 THEN 1 ELSE 0 END +
         CASE WHEN signals_in_range > 0 THEN 1 ELSE 0 END +
         CASE WHEN signals_in_highvol > 0 THEN 1 ELSE 0 END) >= 2
    ) STORED,

    last_updated TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(symbol)
);

-- ============================================================================
-- 4. PROMOTION PIPELINE AUDIT LOG
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.crypto_promotion_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(20) NOT NULL,

    -- Transition
    from_status VARCHAR(20) NOT NULL,
    to_status VARCHAR(20) NOT NULL,

    -- Gates Passed
    liquidity_gate_passed BOOLEAN,
    volatility_gate_passed BOOLEAN,
    regime_gate_passed BOOLEAN,
    signal_gate_passed BOOLEAN,

    -- Approval
    approved_by VARCHAR(50) NOT NULL,  -- 'VEGA_AUTO', 'CEO_MANUAL'
    approval_reason TEXT,

    -- Evidence
    evidence_snapshot JSONB,

    transitioned_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 5. VEGA ENFORCEMENT RULES
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.crypto_vega_enforcement (
    rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name VARCHAR(100) NOT NULL UNIQUE,
    rule_type VARCHAR(20) NOT NULL,  -- 'AUTO_BLOCK', 'ESCALATE_CEO'

    -- Trigger Conditions
    trigger_condition TEXT NOT NULL,
    threshold_value NUMERIC(10,4),

    -- Actions
    action_on_trigger VARCHAR(50) NOT NULL,
    escalation_required BOOLEAN DEFAULT FALSE,

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert VEGA enforcement rules from CEO directive
INSERT INTO fhq_governance.crypto_vega_enforcement
    (rule_name, rule_type, trigger_condition, threshold_value, action_on_trigger, escalation_required)
VALUES
    -- Auto-block rules
    ('LIQUIDITY_COLLAPSE', 'AUTO_BLOCK',
     'volume_24h drops >50% in 24h', 50.0,
     'SUSPEND_PAIR', FALSE),

    ('SPREAD_EXPLOSION', 'AUTO_BLOCK',
     'median_spread_bps exceeds 100 bps', 100.0,
     'SUSPEND_PAIR', FALSE),

    ('REGIME_AMBIGUITY', 'AUTO_BLOCK',
     'regime classifier confidence <0.5', 0.5,
     'BLOCK_SIGNALS', FALSE),

    -- Escalate to CEO rules
    ('REPEATED_SIGNAL_FAILURE', 'ESCALATE_CEO',
     'false_positive_rate >50% for 3 consecutive days', 0.50,
     'ESCALATE_AND_SUSPEND', TRUE),

    ('CORRELATED_LOSSES', 'ESCALATE_CEO',
     'cluster losses exceed 5% in single day', 5.0,
     'ESCALATE_AND_REVIEW', TRUE),

    ('MODE_BYPASS_ATTEMPT', 'ESCALATE_CEO',
     'execution attempted on MONITORING pair', NULL,
     'HARD_BLOCK_AND_ALERT', TRUE)
ON CONFLICT (rule_name) DO NOTHING;

-- ============================================================================
-- 6. CLUSTER EXPOSURE TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_monitoring.crypto_cluster_exposure (
    cluster_id VARCHAR(50) PRIMARY KEY,
    cluster_name VARCHAR(100) NOT NULL,

    -- Constituent pairs
    member_symbols TEXT[] NOT NULL,

    -- Exposure tracking
    max_cluster_exposure_pct NUMERIC(5,2) DEFAULT 40.0,  -- CEO: 40% max
    current_exposure_pct NUMERIC(10,4) DEFAULT 0,

    -- Correlation metrics
    avg_pair_correlation NUMERIC(5,4),
    correlation_last_updated TIMESTAMPTZ,

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert known clusters
INSERT INTO fhq_monitoring.crypto_cluster_exposure
    (cluster_id, cluster_name, member_symbols)
VALUES
    ('LAYER1', 'Layer 1 Blockchains',
     ARRAY['BTC/USD', 'ETH/USD', 'SOL/USD', 'AVAX/USD', 'DOT/USD', 'ATOM/USD', 'NEAR/USD', 'APT/USD']),

    ('DEFI', 'DeFi Protocols',
     ARRAY['UNI/USD', 'AAVE/USD', 'LINK/USD', 'CRV/USD', 'SUSHI/USD', 'YFI/USD', 'GRT/USD']),

    ('MEME', 'Meme Coins',
     ARRAY['DOGE/USD', 'SHIB/USD', 'PEPE/USD']),

    ('PAYMENTS', 'Payment Networks',
     ARRAY['XRP/USD', 'LTC/USD', 'XLM/USD', 'BCH/USD'])
ON CONFLICT (cluster_id) DO NOTHING;

-- ============================================================================
-- 7. SEED ALL 62 ALPACA CRYPTO PAIRS
-- ============================================================================

INSERT INTO fhq_governance.crypto_pair_registry
    (symbol, base_asset, quote_asset, lifecycle_status, cluster_id, notes)
VALUES
    -- Major USD pairs (Layer 1)
    ('BTC/USD', 'BTC', 'USD', 'QUALIFIED', 'LAYER1', 'Bitcoin - Primary asset, already trading'),
    ('ETH/USD', 'ETH', 'USD', 'MONITORING', 'LAYER1', 'Ethereum'),
    ('SOL/USD', 'SOL', 'USD', 'MONITORING', 'LAYER1', 'Solana'),
    ('AVAX/USD', 'AVAX', 'USD', 'MONITORING', 'LAYER1', 'Avalanche'),
    ('DOT/USD', 'DOT', 'USD', 'MONITORING', 'LAYER1', 'Polkadot'),
    ('ATOM/USD', 'ATOM', 'USD', 'MONITORING', 'LAYER1', 'Cosmos'),
    ('NEAR/USD', 'NEAR', 'USD', 'MONITORING', 'LAYER1', 'NEAR Protocol'),
    ('APT/USD', 'APT', 'USD', 'MONITORING', 'LAYER1', 'Aptos'),

    -- DeFi
    ('LINK/USD', 'LINK', 'USD', 'MONITORING', 'DEFI', 'Chainlink'),
    ('UNI/USD', 'UNI', 'USD', 'MONITORING', 'DEFI', 'Uniswap'),
    ('AAVE/USD', 'AAVE', 'USD', 'MONITORING', 'DEFI', 'Aave'),
    ('CRV/USD', 'CRV', 'USD', 'MONITORING', 'DEFI', 'Curve'),
    ('SUSHI/USD', 'SUSHI', 'USD', 'MONITORING', 'DEFI', 'SushiSwap'),
    ('YFI/USD', 'YFI', 'USD', 'MONITORING', 'DEFI', 'Yearn Finance'),
    ('GRT/USD', 'GRT', 'USD', 'MONITORING', 'DEFI', 'The Graph'),

    -- Payments
    ('XRP/USD', 'XRP', 'USD', 'MONITORING', 'PAYMENTS', 'Ripple'),
    ('LTC/USD', 'LTC', 'USD', 'MONITORING', 'PAYMENTS', 'Litecoin'),
    ('XLM/USD', 'XLM', 'USD', 'MONITORING', 'PAYMENTS', 'Stellar'),
    ('BCH/USD', 'BCH', 'USD', 'MONITORING', 'PAYMENTS', 'Bitcoin Cash'),

    -- Meme
    ('DOGE/USD', 'DOGE', 'USD', 'MONITORING', 'MEME', 'Dogecoin'),
    ('SHIB/USD', 'SHIB', 'USD', 'MONITORING', 'MEME', 'Shiba Inu'),
    ('PEPE/USD', 'PEPE', 'USD', 'MONITORING', 'MEME', 'Pepe'),

    -- Other majors
    ('TRUMP/USD', 'TRUMP', 'USD', 'MONITORING', NULL, 'Trump Token'),
    ('BAT/USD', 'BAT', 'USD', 'MONITORING', NULL, 'Basic Attention Token'),
    ('XTZ/USD', 'XTZ', 'USD', 'MONITORING', NULL, 'Tezos'),
    ('ALGO/USD', 'ALGO', 'USD', 'MONITORING', NULL, 'Algorand'),
    ('FIL/USD', 'FIL', 'USD', 'MONITORING', NULL, 'Filecoin'),
    ('ARB/USD', 'ARB', 'USD', 'MONITORING', NULL, 'Arbitrum'),
    ('OP/USD', 'OP', 'USD', 'MONITORING', NULL, 'Optimism'),
    ('SKY/USD', 'SKY', 'USD', 'MONITORING', NULL, 'Sky'),

    -- USDC pairs
    ('BTC/USDC', 'BTC', 'USDC', 'MONITORING', 'LAYER1', 'Bitcoin USDC'),
    ('ETH/USDC', 'ETH', 'USDC', 'MONITORING', 'LAYER1', 'Ethereum USDC'),
    ('SOL/USDC', 'SOL', 'USDC', 'MONITORING', 'LAYER1', 'Solana USDC'),
    ('AVAX/USDC', 'AVAX', 'USDC', 'MONITORING', 'LAYER1', 'Avalanche USDC'),
    ('DOT/USDC', 'DOT', 'USDC', 'MONITORING', 'LAYER1', 'Polkadot USDC'),
    ('LINK/USDC', 'LINK', 'USDC', 'MONITORING', 'DEFI', 'Chainlink USDC'),
    ('UNI/USDC', 'UNI', 'USDC', 'MONITORING', 'DEFI', 'Uniswap USDC'),
    ('AAVE/USDC', 'AAVE', 'USDC', 'MONITORING', 'DEFI', 'Aave USDC'),
    ('CRV/USDC', 'CRV', 'USDC', 'MONITORING', 'DEFI', 'Curve USDC'),
    ('SUSHI/USDC', 'SUSHI', 'USDC', 'MONITORING', 'DEFI', 'SushiSwap USDC'),
    ('YFI/USDC', 'YFI', 'USDC', 'MONITORING', 'DEFI', 'Yearn USDC'),
    ('GRT/USDC', 'GRT', 'USDC', 'MONITORING', 'DEFI', 'The Graph USDC'),
    ('DOGE/USDC', 'DOGE', 'USDC', 'MONITORING', 'MEME', 'Dogecoin USDC'),
    ('SHIB/USDC', 'SHIB', 'USDC', 'MONITORING', 'MEME', 'Shiba Inu USDC'),
    ('LTC/USDC', 'LTC', 'USDC', 'MONITORING', 'PAYMENTS', 'Litecoin USDC'),
    ('BCH/USDC', 'BCH', 'USDC', 'MONITORING', 'PAYMENTS', 'Bitcoin Cash USDC'),
    ('XTZ/USDC', 'XTZ', 'USDC', 'MONITORING', NULL, 'Tezos USDC'),
    ('BAT/USDC', 'BAT', 'USDC', 'MONITORING', NULL, 'BAT USDC'),

    -- USDT pairs
    ('BTC/USDT', 'BTC', 'USDT', 'MONITORING', 'LAYER1', 'Bitcoin USDT'),
    ('ETH/USDT', 'ETH', 'USDT', 'MONITORING', 'LAYER1', 'Ethereum USDT'),
    ('SOL/USDT', 'SOL', 'USDT', 'MONITORING', 'LAYER1', 'Solana USDT'),
    ('AVAX/USDT', 'AVAX', 'USDT', 'MONITORING', 'LAYER1', 'Avalanche USDT'),
    ('LINK/USDT', 'LINK', 'USDT', 'MONITORING', 'DEFI', 'Chainlink USDT'),
    ('UNI/USDT', 'UNI', 'USDT', 'MONITORING', 'DEFI', 'Uniswap USDT'),
    ('AAVE/USDT', 'AAVE', 'USDT', 'MONITORING', 'DEFI', 'Aave USDT'),
    ('SUSHI/USDT', 'SUSHI', 'USDT', 'MONITORING', 'DEFI', 'SushiSwap USDT'),
    ('YFI/USDT', 'YFI', 'USDT', 'MONITORING', 'DEFI', 'Yearn USDT'),
    ('DOGE/USDT', 'DOGE', 'USDT', 'MONITORING', 'MEME', 'Dogecoin USDT'),
    ('SHIB/USDT', 'SHIB', 'USDT', 'MONITORING', 'MEME', 'Shiba Inu USDT'),
    ('LTC/USDT', 'LTC', 'USDT', 'MONITORING', 'PAYMENTS', 'Litecoin USDT'),
    ('BCH/USDT', 'BCH', 'USDT', 'MONITORING', 'PAYMENTS', 'Bitcoin Cash USDT'),

    -- BTC pairs
    ('ETH/BTC', 'ETH', 'BTC', 'MONITORING', 'LAYER1', 'ETH/BTC ratio'),
    ('LINK/BTC', 'LINK', 'BTC', 'MONITORING', 'DEFI', 'LINK/BTC ratio'),
    ('UNI/BTC', 'UNI', 'BTC', 'MONITORING', 'DEFI', 'UNI/BTC ratio'),
    ('LTC/BTC', 'LTC', 'BTC', 'MONITORING', 'PAYMENTS', 'LTC/BTC ratio'),
    ('BCH/BTC', 'BCH', 'BTC', 'MONITORING', 'PAYMENTS', 'BCH/BTC ratio')
ON CONFLICT (symbol) DO UPDATE SET
    is_active = TRUE,
    notes = EXCLUDED.notes;

-- Initialize signal quality tracking for all pairs
INSERT INTO fhq_monitoring.crypto_signal_quality (symbol)
SELECT symbol FROM fhq_governance.crypto_pair_registry
ON CONFLICT (symbol) DO NOTHING;

-- ============================================================================
-- 8. MODE SEPARATION ENFORCEMENT FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.check_execution_allowed(
    p_symbol VARCHAR(20)
) RETURNS TABLE (
    allowed BOOLEAN,
    reason TEXT,
    lifecycle_status VARCHAR(20)
) AS $$
DECLARE
    v_status VARCHAR(20);
BEGIN
    -- Get current lifecycle status
    SELECT cpr.lifecycle_status INTO v_status
    FROM fhq_governance.crypto_pair_registry cpr
    WHERE cpr.symbol = p_symbol;

    IF v_status IS NULL THEN
        RETURN QUERY SELECT FALSE, 'Symbol not in registry', NULL::VARCHAR(20);
        RETURN;
    END IF;

    IF v_status = 'MONITORING' THEN
        RETURN QUERY SELECT FALSE,
            'MODE SEPARATION: MONITORING-only, no execution allowed',
            v_status;
        RETURN;
    END IF;

    IF v_status = 'SUSPENDED' THEN
        RETURN QUERY SELECT FALSE,
            'PAIR SUSPENDED: Check VEGA enforcement log',
            v_status;
        RETURN;
    END IF;

    IF v_status IN ('QUALIFIED', 'EXECUTABLE', 'LIVE_ELIGIBLE') THEN
        RETURN QUERY SELECT TRUE,
            'Execution permitted for ' || v_status || ' pair',
            v_status;
        RETURN;
    END IF;

    RETURN QUERY SELECT FALSE, 'Unknown status', v_status;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 9. PROMOTION CHECK FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.check_promotion_eligibility(
    p_symbol VARCHAR(20)
) RETURNS TABLE (
    eligible BOOLEAN,
    current_status VARCHAR(20),
    next_status VARCHAR(20),
    gates_summary JSONB
) AS $$
DECLARE
    v_status VARCHAR(20);
    v_liquidity BOOLEAN;
    v_volatility BOOLEAN;
    v_regime BOOLEAN;
    v_signal BOOLEAN;
    v_gates JSONB;
BEGIN
    -- Get current status
    SELECT lifecycle_status INTO v_status
    FROM fhq_governance.crypto_pair_registry
    WHERE symbol = p_symbol;

    -- Get gate statuses
    SELECT
        COALESCE(passes_liquidity_gate, FALSE),
        COALESCE(passes_volatility_gate, FALSE)
    INTO v_liquidity, v_volatility
    FROM fhq_monitoring.crypto_liquidity_metrics
    WHERE symbol = p_symbol
    ORDER BY metric_date DESC
    LIMIT 1;

    SELECT
        COALESCE(passes_regime_coverage, FALSE),
        COALESCE(passes_signal_threshold, FALSE)
    INTO v_regime, v_signal
    FROM fhq_monitoring.crypto_signal_quality
    WHERE symbol = p_symbol;

    v_gates := jsonb_build_object(
        'liquidity_gate', COALESCE(v_liquidity, FALSE),
        'volatility_gate', COALESCE(v_volatility, FALSE),
        'regime_coverage', COALESCE(v_regime, FALSE),
        'signal_quality', COALESCE(v_signal, FALSE)
    );

    -- Determine eligibility
    IF v_status = 'MONITORING' THEN
        -- Need all gates for QUALIFIED
        IF COALESCE(v_liquidity, FALSE) AND COALESCE(v_volatility, FALSE) AND
           COALESCE(v_regime, FALSE) AND COALESCE(v_signal, FALSE) THEN
            RETURN QUERY SELECT TRUE, v_status, 'QUALIFIED'::VARCHAR(20), v_gates;
        ELSE
            RETURN QUERY SELECT FALSE, v_status, 'MONITORING'::VARCHAR(20), v_gates;
        END IF;
    ELSIF v_status = 'QUALIFIED' THEN
        -- Additional criteria for EXECUTABLE (TBD by CEO)
        RETURN QUERY SELECT FALSE, v_status, 'QUALIFIED'::VARCHAR(20), v_gates;
    ELSE
        RETURN QUERY SELECT FALSE, v_status, v_status, v_gates;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 10. VEGA ATTESTATION (Skipped - log via application layer)
-- ============================================================================
-- CEO 62-PAIR MONITORING EXPANSION infrastructure deployed
-- VEGA attestation to be issued via application layer

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_pairs INTEGER;
    v_rules INTEGER;
    v_clusters INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_pairs FROM fhq_governance.crypto_pair_registry;
    SELECT COUNT(*) INTO v_rules FROM fhq_governance.crypto_vega_enforcement;
    SELECT COUNT(*) INTO v_clusters FROM fhq_monitoring.crypto_cluster_exposure;

    RAISE NOTICE '=== MIGRATION 190 VERIFICATION ===';
    RAISE NOTICE 'Crypto pairs registered: %', v_pairs;
    RAISE NOTICE 'VEGA enforcement rules: %', v_rules;
    RAISE NOTICE 'Cluster definitions: %', v_clusters;
    RAISE NOTICE '==================================';
END $$;
