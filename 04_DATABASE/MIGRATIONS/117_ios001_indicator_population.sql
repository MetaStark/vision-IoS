-- ============================================================================
-- Migration 117: IoS-001 Canonical Indicator Registry Population
-- §3.4 Compliance - Technical Indicator Registration
-- ============================================================================
-- Authority: STIG (CTO) per EC-003
-- ADR References: ADR-013 (Canonical Architecture), ADR-002 (Audit)
-- IoS Reference: IoS-001 §3.4, §4.5
-- CEO Directive: Dual Price Ontology - indicators use price_input_field
-- ============================================================================

BEGIN;

-- ============================================================================
-- PART A: Get or create domain for indicators
-- ============================================================================
-- Domain ID for 'indicators' category: 3d9ccd51-55e5-4276-8d2c-a7c8376441e8

-- ============================================================================
-- PART B: MOMENTUM Indicators
-- ============================================================================

INSERT INTO fhq_meta.canonical_indicator_registry (
    indicator_id,
    domain_id,
    indicator_name,
    indicator_version,
    calculation_method,
    canonical_table,
    asset_universe,
    default_parameters,
    is_active,
    is_canonical,
    created_by,
    category,
    source_standard,
    ios_module,
    formula_hash,
    price_input_field
) VALUES
    -- RSI - Relative Strength Index
    (
        gen_random_uuid(),
        '3d9ccd51-55e5-4276-8d2c-a7c8376441e8'::uuid,
        'RSI_14',
        '1.0.0',
        'RSI = 100 - (100 / (1 + RS)), where RS = Avg Gain / Avg Loss over period',
        'fhq_data.technical_indicators',
        ARRAY['*'],
        '{"period": 14, "overbought": 70, "oversold": 30}'::jsonb,
        true,
        true,
        'STIG',
        'MOMENTUM',
        'Wilder 1978 (New Concepts in Technical Trading Systems)',
        'IoS-002',
        encode(sha256('RSI_14_Wilder1978'::bytea), 'hex'),
        'adj_close'
    ),
    -- Stochastic RSI
    (
        gen_random_uuid(),
        '3d9ccd51-55e5-4276-8d2c-a7c8376441e8'::uuid,
        'STOCH_RSI_14',
        '1.0.0',
        'StochRSI = (RSI - Lowest RSI) / (Highest RSI - Lowest RSI) over period',
        'fhq_data.technical_indicators',
        ARRAY['*'],
        '{"rsi_period": 14, "stoch_period": 14, "smooth_k": 3, "smooth_d": 3}'::jsonb,
        true,
        true,
        'STIG',
        'MOMENTUM',
        'Chande & Kroll 1994 (The New Technical Trader)',
        'IoS-002',
        encode(sha256('STOCH_RSI_14_ChandeKroll1994'::bytea), 'hex'),
        'adj_close'
    ),
    -- CCI - Commodity Channel Index
    (
        gen_random_uuid(),
        '3d9ccd51-55e5-4276-8d2c-a7c8376441e8'::uuid,
        'CCI_20',
        '1.0.0',
        'CCI = (Typical Price - SMA) / (0.015 * Mean Deviation)',
        'fhq_data.technical_indicators',
        ARRAY['*'],
        '{"period": 20, "constant": 0.015}'::jsonb,
        true,
        true,
        'STIG',
        'MOMENTUM',
        'Lambert 1980 (Commodities Magazine)',
        'IoS-002',
        encode(sha256('CCI_20_Lambert1980'::bytea), 'hex'),
        'adj_close'
    ),
    -- MFI - Money Flow Index
    (
        gen_random_uuid(),
        '3d9ccd51-55e5-4276-8d2c-a7c8376441e8'::uuid,
        'MFI_14',
        '1.0.0',
        'MFI = 100 - (100 / (1 + Money Flow Ratio)), uses volume weighting',
        'fhq_data.technical_indicators',
        ARRAY['*'],
        '{"period": 14, "overbought": 80, "oversold": 20}'::jsonb,
        true,
        true,
        'STIG',
        'MOMENTUM',
        'Quong & Soudack 1989 (Technical Analysis of Stocks & Commodities)',
        'IoS-002',
        encode(sha256('MFI_14_QuongSoudack1989'::bytea), 'hex'),
        'adj_close'
    ),
    -- Williams %R
    (
        gen_random_uuid(),
        '3d9ccd51-55e5-4276-8d2c-a7c8376441e8'::uuid,
        'WILLIAMS_R_14',
        '1.0.0',
        'Williams R = (Highest High - Close) / (Highest High - Lowest Low) * -100',
        'fhq_data.technical_indicators',
        ARRAY['*'],
        '{"period": 14, "overbought": -20, "oversold": -80}'::jsonb,
        true,
        true,
        'STIG',
        'MOMENTUM',
        'Williams 1979 (How I Made One Million Dollars)',
        'IoS-002',
        encode(sha256('WILLIAMS_R_14_Williams1979'::bytea), 'hex'),
        'adj_close'
    ),
    -- ROC - Rate of Change
    (
        gen_random_uuid(),
        '3d9ccd51-55e5-4276-8d2c-a7c8376441e8'::uuid,
        'ROC_20',
        '1.0.0',
        'ROC = ((Close - Close_n) / Close_n) * 100',
        'fhq_data.technical_indicators',
        ARRAY['*'],
        '{"period": 20}'::jsonb,
        true,
        true,
        'STIG',
        'MOMENTUM',
        'Standard Technical Analysis',
        'IoS-002',
        encode(sha256('ROC_20_Standard'::bytea), 'hex'),
        'adj_close'
    ),
    -- MACD
    (
        gen_random_uuid(),
        '3d9ccd51-55e5-4276-8d2c-a7c8376441e8'::uuid,
        'MACD_12_26_9',
        '1.0.0',
        'MACD Line = EMA(12) - EMA(26), Signal Line = EMA(9) of MACD Line',
        'fhq_data.technical_indicators',
        ARRAY['*'],
        '{"fast_period": 12, "slow_period": 26, "signal_period": 9}'::jsonb,
        true,
        true,
        'STIG',
        'TREND',
        'Appel 1979 (Systems and Forecasts)',
        'IoS-002',
        encode(sha256('MACD_12_26_9_Appel1979'::bytea), 'hex'),
        'adj_close'
    ),
    -- EMA 9
    (
        gen_random_uuid(),
        '3d9ccd51-55e5-4276-8d2c-a7c8376441e8'::uuid,
        'EMA_9',
        '1.0.0',
        'EMA = (Close * k) + (EMA_prev * (1-k)), where k = 2/(period+1)',
        'fhq_data.technical_indicators',
        ARRAY['*'],
        '{"period": 9}'::jsonb,
        true,
        true,
        'STIG',
        'TREND',
        'Standard Exponential Moving Average',
        'IoS-002',
        encode(sha256('EMA_9_Standard'::bytea), 'hex'),
        'adj_close'
    ),
    -- EMA 20
    (
        gen_random_uuid(),
        '3d9ccd51-55e5-4276-8d2c-a7c8376441e8'::uuid,
        'EMA_20',
        '1.0.0',
        'EMA = (Close * k) + (EMA_prev * (1-k)), where k = 2/(period+1)',
        'fhq_data.technical_indicators',
        ARRAY['*'],
        '{"period": 20}'::jsonb,
        true,
        true,
        'STIG',
        'TREND',
        'Standard Exponential Moving Average',
        'IoS-002',
        encode(sha256('EMA_20_Standard'::bytea), 'hex'),
        'adj_close'
    ),
    -- SMA 50
    (
        gen_random_uuid(),
        '3d9ccd51-55e5-4276-8d2c-a7c8376441e8'::uuid,
        'SMA_50',
        '1.0.0',
        'SMA = Sum(Close_i) / n for i=1 to n',
        'fhq_data.technical_indicators',
        ARRAY['*'],
        '{"period": 50}'::jsonb,
        true,
        true,
        'STIG',
        'TREND',
        'Standard Simple Moving Average',
        'IoS-002',
        encode(sha256('SMA_50_Standard'::bytea), 'hex'),
        'adj_close'
    ),
    -- SMA 200
    (
        gen_random_uuid(),
        '3d9ccd51-55e5-4276-8d2c-a7c8376441e8'::uuid,
        'SMA_200',
        '1.0.0',
        'SMA = Sum(Close_i) / n for i=1 to n',
        'fhq_data.technical_indicators',
        ARRAY['*'],
        '{"period": 200}'::jsonb,
        true,
        true,
        'STIG',
        'TREND',
        'Standard Simple Moving Average',
        'IoS-002',
        encode(sha256('SMA_200_Standard'::bytea), 'hex'),
        'adj_close'
    ),
    -- ADX
    (
        gen_random_uuid(),
        '3d9ccd51-55e5-4276-8d2c-a7c8376441e8'::uuid,
        'ADX_14',
        '1.0.0',
        'ADX = 100 * EMA(abs(+DI - -DI) / (+DI + -DI))',
        'fhq_data.technical_indicators',
        ARRAY['*'],
        '{"period": 14, "strong_trend": 25}'::jsonb,
        true,
        true,
        'STIG',
        'TREND',
        'Wilder 1978 (New Concepts in Technical Trading Systems)',
        'IoS-002',
        encode(sha256('ADX_14_Wilder1978'::bytea), 'hex'),
        'adj_close'
    ),
    -- Bollinger Bands
    (
        gen_random_uuid(),
        '3d9ccd51-55e5-4276-8d2c-a7c8376441e8'::uuid,
        'BB_20_2',
        '1.0.0',
        'Middle = SMA(20), Upper = SMA + 2*StdDev, Lower = SMA - 2*StdDev',
        'fhq_data.technical_indicators',
        ARRAY['*'],
        '{"period": 20, "std_dev": 2}'::jsonb,
        true,
        true,
        'STIG',
        'VOLATILITY',
        'Bollinger 1983 (Technical Analysis of Stocks & Commodities)',
        'IoS-002',
        encode(sha256('BB_20_2_Bollinger1983'::bytea), 'hex'),
        'adj_close'
    ),
    -- ATR
    (
        gen_random_uuid(),
        '3d9ccd51-55e5-4276-8d2c-a7c8376441e8'::uuid,
        'ATR_14',
        '1.0.0',
        'ATR = EMA(True Range), TR = max(High-Low, abs(High-Close_prev), abs(Low-Close_prev))',
        'fhq_data.technical_indicators',
        ARRAY['*'],
        '{"period": 14}'::jsonb,
        true,
        true,
        'STIG',
        'VOLATILITY',
        'Wilder 1978 (New Concepts in Technical Trading Systems)',
        'IoS-002',
        encode(sha256('ATR_14_Wilder1978'::bytea), 'hex'),
        'adj_close'
    ),
    -- Ichimoku Cloud
    (
        gen_random_uuid(),
        '3d9ccd51-55e5-4276-8d2c-a7c8376441e8'::uuid,
        'ICHIMOKU',
        '1.0.0',
        'Tenkan = (HH9 + LL9)/2, Kijun = (HH26 + LL26)/2, Senkou A/B, Chikou',
        'fhq_data.technical_indicators',
        ARRAY['*'],
        '{"tenkan_period": 9, "kijun_period": 26, "senkou_b_period": 52, "displacement": 26}'::jsonb,
        true,
        true,
        'STIG',
        'ICHIMOKU',
        'Hosoda 1968 (Ichimoku Kinko Hyo)',
        'IoS-002',
        encode(sha256('ICHIMOKU_Hosoda1968'::bytea), 'hex'),
        'adj_close'
    ),
    -- OBV - On-Balance Volume
    (
        gen_random_uuid(),
        '3d9ccd51-55e5-4276-8d2c-a7c8376441e8'::uuid,
        'OBV',
        '1.0.0',
        'OBV = OBV_prev + Volume if Close > Close_prev, - Volume if Close < Close_prev',
        'fhq_data.technical_indicators',
        ARRAY['*'],
        '{}'::jsonb,
        true,
        true,
        'STIG',
        'VOLUME',
        'Granville 1963 (Granvilles New Key to Stock Market Profits)',
        'IoS-002',
        encode(sha256('OBV_Granville1963'::bytea), 'hex'),
        'adj_close'
    ),
    -- VWAP
    (
        gen_random_uuid(),
        '3d9ccd51-55e5-4276-8d2c-a7c8376441e8'::uuid,
        'VWAP',
        '1.0.0',
        'VWAP = Cumulative(Typical Price * Volume) / Cumulative(Volume)',
        'fhq_data.technical_indicators',
        ARRAY['*'],
        '{"anchor": "session"}'::jsonb,
        true,
        true,
        'STIG',
        'VOLUME',
        'Standard Institutional Benchmark',
        'IoS-002',
        encode(sha256('VWAP_Standard'::bytea), 'hex'),
        'adj_close'
    )
ON CONFLICT (indicator_name, indicator_version, calculation_method) DO UPDATE SET
    category = EXCLUDED.category,
    source_standard = EXCLUDED.source_standard,
    formula_hash = EXCLUDED.formula_hash,
    price_input_field = EXCLUDED.price_input_field,
    updated_at = NOW();

-- ============================================================================
-- PART C: Governance Logging (ADR-002)
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
    vega_reviewed,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'INDICATOR_REGISTRATION',
    'fhq_meta.canonical_indicator_registry',
    'DATA',
    'STIG',
    NOW(),
    'APPROVED',
    'IoS-001 §3.4 Indicator Population - 17 canonical indicators registered. Categories: MOMENTUM (6), TREND (6), VOLATILITY (2), ICHIMOKU (1), VOLUME (2). All indicators include source_standard (academic reference), formula_hash (SHA-256), price_input_field (adj_close per Dual Price Ontology). Compliant with §4.5 Indicator Governance Protocol.',
    false,
    'MIG-117-IOS001-INDICATORS-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS')
);

-- ============================================================================
-- PART D: Verification
-- ============================================================================

DO $$
DECLARE
    indicator_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO indicator_count
    FROM fhq_meta.canonical_indicator_registry
    WHERE is_active = true AND ios_module = 'IoS-002';

    IF indicator_count < 15 THEN
        RAISE WARNING 'Expected at least 15 indicators, found %', indicator_count;
    ELSE
        RAISE NOTICE 'Indicator registration complete: % IoS-002 indicators', indicator_count;
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- Migration 117 Complete
-- Indicators: 17 registered
-- All indicators include:
--   - source_standard (academic/industry reference)
--   - formula_hash (SHA-256 for integrity)
--   - price_input_field (Dual Price Ontology compliance)
--   - ios_module = 'IoS-002' (indicator calculation engine)
-- Next: Migration 118 (Model Context Population)
-- ============================================================================
