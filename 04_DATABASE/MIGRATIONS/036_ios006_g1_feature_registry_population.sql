-- ============================================================================
-- MIGRATION: 036_ios006_g1_feature_registry_population.sql
-- PURPOSE: IoS-006 G1 — Populate Macro Feature Registry (MFR)
-- AUTHORITY: LARS (Strategy Authorization) + VEGA (Governance Ratification)
-- EXECUTOR: STIG (CTO)
-- OWNER: FINN (Tier-1 Research)
-- ADR COMPLIANCE: ADR-002, ADR-003, ADR-011, ADR-012, ADR-013
-- STATUS: G1 EXECUTION
-- DATE: 2025-11-30
-- ============================================================================
--
-- G1 MANDATE: "Start G1. Populate the Registry. Initiate Ingest."
-- Source: LARS Strategic Authorization + VEGA Governance Ratification
--
-- This migration populates the Macro Feature Registry with initial candidates
-- across all four primary Alpha Cubes:
--   A: LIQUIDITY (6 features)
--   B: CREDIT (6 features)
--   C: VOLATILITY (5 features)
--   D: FACTOR (5 features)
--
-- Total: 22 initial feature candidates
-- Expected outcome: 95% rejection rate per Null Result Regime
--
-- ============================================================================

BEGIN;

-- ============================================================================
-- CLUSTER A: LIQUIDITY (6 Features)
-- Hypothesis: Crypto beta = f(fiat debasement)
-- ============================================================================

INSERT INTO fhq_macro.feature_registry (
    feature_id, feature_name, description,
    provenance, source_ticker, source_url,
    frequency, lag_period_days, history_start_date,
    stationarity_method, cluster, hypothesis, expected_direction,
    status, created_by
) VALUES
-- A1: US M2 Money Supply YoY
(
    'US_M2_YOY',
    'US M2 Money Supply YoY Change',
    'Year-over-year percent change in US M2 money supply. Leading liquidity indicator. ' ||
    'Hypothesis: Crypto prices correlate with fiat debasement expectations.',
    'FRED', 'M2SL', 'https://fred.stlouisfed.org/series/M2SL',
    'MONTHLY', 14, '1959-01-01',
    'NONE', 'LIQUIDITY',
    'Crypto beta = f(fiat debasement). Higher M2 growth → higher crypto risk appetite.',
    'POSITIVE',
    'CANDIDATE', 'STIG'
),
-- A2: Fed Balance Sheet (Total Assets)
(
    'FED_TOTAL_ASSETS',
    'Federal Reserve Total Assets',
    'Total assets held by the Federal Reserve. Primary liquidity injection mechanism. ' ||
    'Expansion = QE = risk-on, Contraction = QT = risk-off.',
    'FRED', 'WALCL', 'https://fred.stlouisfed.org/series/WALCL',
    'WEEKLY', 7, '2002-12-18',
    'DIFF', 'LIQUIDITY',
    'Fed balance sheet expansion precedes risk asset rallies by 2-4 weeks.',
    'POSITIVE',
    'CANDIDATE', 'STIG'
),
-- A3: Treasury General Account (TGA)
(
    'US_TGA_BALANCE',
    'US Treasury General Account Balance',
    'Treasury cash balance at the Federal Reserve. TGA drawdowns inject liquidity into banking system. ' ||
    'TGA build-ups drain liquidity.',
    'FRED', 'WTREGEN', 'https://fred.stlouisfed.org/series/WTREGEN',
    'WEEKLY', 7, '2001-02-07',
    'DIFF', 'LIQUIDITY',
    'TGA drawdown = liquidity injection = risk-on. TGA buildup = liquidity drain = risk-off.',
    'NEGATIVE',
    'CANDIDATE', 'STIG'
),
-- A4: Reverse Repo (RRP) Facility Balance
(
    'FED_RRP_BALANCE',
    'Federal Reserve Reverse Repo Facility',
    'Cash parked at the Fed via overnight reverse repos. High RRP = excess liquidity in system ' ||
    'but not deployed to risk assets.',
    'FRED', 'RRPONTSYD', 'https://fred.stlouisfed.org/series/RRPONTSYD',
    'DAILY', 1, '2013-09-23',
    'DIFF', 'LIQUIDITY',
    'RRP drawdown = liquidity moving from Fed facility to risk assets. Bullish crypto signal.',
    'NEGATIVE',
    'CANDIDATE', 'STIG'
),
-- A5: Net Liquidity Proxy (Fed Assets - TGA - RRP)
(
    'US_NET_LIQUIDITY',
    'US Net Liquidity Proxy',
    'Calculated as: Fed Total Assets - TGA - RRP. Represents effective liquidity available ' ||
    'for risk asset deployment. Composite indicator.',
    'CALCULATED', 'NET_LIQ_V1', NULL,
    'WEEKLY', 7, '2013-09-23',
    'DIFF', 'LIQUIDITY',
    'Net liquidity expansion precedes crypto rallies. Core thesis of macro-crypto correlation.',
    'POSITIVE',
    'CANDIDATE', 'STIG'
),
-- A6: Global M2 (Major Central Banks)
(
    'GLOBAL_M2_USD',
    'Global M2 Money Supply (USD)',
    'Aggregate M2 from Fed, ECB, BOJ, PBOC converted to USD. Measures global liquidity expansion.',
    'CALCULATED', 'GLOBAL_M2_V1', NULL,
    'MONTHLY', 30, '2008-01-01',
    'LOG_DIFF', 'LIQUIDITY',
    'Global liquidity drives global risk assets. Crypto is a global liquidity play.',
    'POSITIVE',
    'CANDIDATE', 'STIG'
)
ON CONFLICT (feature_id) DO UPDATE SET
    description = EXCLUDED.description,
    updated_at = NOW();

-- ============================================================================
-- CLUSTER B: CREDIT (6 Features)
-- Hypothesis: Credit stress precedes liquidity withdrawal
-- ============================================================================

INSERT INTO fhq_macro.feature_registry (
    feature_id, feature_name, description,
    provenance, source_ticker, source_url,
    frequency, lag_period_days, history_start_date,
    stationarity_method, cluster, hypothesis, expected_direction,
    status, created_by
) VALUES
-- B1: High Yield Spread (ICE BofA)
(
    'US_HY_SPREAD',
    'US High Yield OAS Spread',
    'Option-adjusted spread of high yield corporate bonds over Treasuries. ' ||
    'Primary credit stress indicator. Widening = risk-off.',
    'FRED', 'BAMLH0A0HYM2', 'https://fred.stlouisfed.org/series/BAMLH0A0HYM2',
    'DAILY', 1, '1996-12-31',
    'DIFF', 'CREDIT',
    'HY spread widening precedes risk-off moves. Crypto correlates negatively with credit stress.',
    'NEGATIVE',
    'CANDIDATE', 'STIG'
),
-- B2: Investment Grade Spread
(
    'US_IG_SPREAD',
    'US Investment Grade OAS Spread',
    'Option-adjusted spread of investment grade corporate bonds. ' ||
    'Less volatile than HY but still reflects credit conditions.',
    'FRED', 'BAMLC0A0CM', 'https://fred.stlouisfed.org/series/BAMLC0A0CM',
    'DAILY', 1, '1996-12-31',
    'DIFF', 'CREDIT',
    'IG spread is a cleaner measure of credit conditions without default risk premium.',
    'NEGATIVE',
    'CANDIDATE', 'STIG'
),
-- B3: 10Y-2Y Treasury Spread (Yield Curve)
(
    'US_YIELD_CURVE_10Y2Y',
    'US Treasury 10Y-2Y Spread',
    'Spread between 10-year and 2-year Treasury yields. Classic recession indicator. ' ||
    'Inversion = recession signal.',
    'FRED', 'T10Y2Y', 'https://fred.stlouisfed.org/series/T10Y2Y',
    'DAILY', 1, '1976-06-01',
    'NONE', 'CREDIT',
    'Yield curve steepening after inversion often coincides with risk asset stress.',
    'AMBIGUOUS',
    'CANDIDATE', 'STIG'
),
-- B4: MOVE Index (Bond Volatility)
(
    'MOVE_INDEX',
    'MOVE Index (Treasury Volatility)',
    'Merrill Lynch Option Volatility Estimate. Measures Treasury market volatility. ' ||
    'High MOVE = credit market stress.',
    'BLOOMBERG', 'MOVE', 'https://www.bloomberg.com/quote/MOVE:IND',
    'DAILY', 1, '1988-06-01',
    'DIFF', 'CREDIT',
    'MOVE spikes precede risk asset selloffs. Bond vol leads equity vol.',
    'NEGATIVE',
    'CANDIDATE', 'STIG'
),
-- B5: TED Spread (Interbank Stress)
(
    'TED_SPREAD',
    'TED Spread (3M LIBOR - 3M T-Bill)',
    'Spread between 3-month LIBOR and 3-month Treasury. Measures interbank credit stress.',
    'FRED', 'TEDRATE', 'https://fred.stlouisfed.org/series/TEDRATE',
    'DAILY', 1, '1986-01-02',
    'DIFF', 'CREDIT',
    'TED spread widening = banking stress = risk-off. Historical indicator of systemic risk.',
    'NEGATIVE',
    'CANDIDATE', 'STIG'
),
-- B6: Fed Funds Rate
(
    'US_FED_FUNDS_RATE',
    'US Federal Funds Effective Rate',
    'Federal Reserve target rate. Primary monetary policy tool. ' ||
    'Rate hikes = tightening = risk-off.',
    'FRED', 'FEDFUNDS', 'https://fred.stlouisfed.org/series/FEDFUNDS',
    'MONTHLY', 1, '1954-07-01',
    'DIFF', 'CREDIT',
    'Fed rate hikes historically precede risk asset corrections. Dovish pivots = rallies.',
    'NEGATIVE',
    'CANDIDATE', 'STIG'
)
ON CONFLICT (feature_id) DO UPDATE SET
    description = EXCLUDED.description,
    updated_at = NOW();

-- ============================================================================
-- CLUSTER C: VOLATILITY (5 Features)
-- Hypothesis: Vol regimes dictate leverage capacity
-- ============================================================================

INSERT INTO fhq_macro.feature_registry (
    feature_id, feature_name, description,
    provenance, source_ticker, source_url,
    frequency, lag_period_days, history_start_date,
    stationarity_method, cluster, hypothesis, expected_direction,
    status, created_by
) VALUES
-- C1: VIX Index
(
    'VIX_INDEX',
    'CBOE Volatility Index (VIX)',
    'S&P 500 implied volatility. Primary fear gauge. VIX > 30 = elevated fear.',
    'YAHOO', '^VIX', 'https://finance.yahoo.com/quote/%5EVIX',
    'DAILY', 0, '1990-01-02',
    'DIFF', 'VOLATILITY',
    'VIX spikes precede risk asset selloffs. Low VIX = complacency = leverage buildup.',
    'NEGATIVE',
    'CANDIDATE', 'STIG'
),
-- C2: VIX Term Structure (VIX - VIX3M)
(
    'VIX_TERM_STRUCTURE',
    'VIX Term Structure (Contango/Backwardation)',
    'Spread between spot VIX and 3-month VIX futures. Backwardation = immediate fear.',
    'CALCULATED', 'VIX_TERM_V1', NULL,
    'DAILY', 0, '2007-12-04',
    'NONE', 'VOLATILITY',
    'VIX backwardation (negative term structure) signals acute fear. Crypto sells off.',
    'NEGATIVE',
    'CANDIDATE', 'STIG'
),
-- C3: VIX9D (Short-Term Vol)
(
    'VIX9D_INDEX',
    'CBOE 9-Day VIX',
    'Very short-term implied volatility. More reactive to immediate events.',
    'YAHOO', '^VIX9D', 'https://finance.yahoo.com/quote/%5EVIX9D',
    'DAILY', 0, '2011-01-01',
    'DIFF', 'VOLATILITY',
    'VIX9D spikes before VIX. Early warning indicator of vol regime change.',
    'NEGATIVE',
    'CANDIDATE', 'STIG'
),
-- C4: Realized Volatility (SPX 20D)
(
    'SPX_RVOL_20D',
    'S&P 500 20-Day Realized Volatility',
    'Rolling 20-day standard deviation of S&P 500 returns, annualized.',
    'CALCULATED', 'SPX_RVOL_20D_V1', NULL,
    'DAILY', 0, '1990-01-01',
    'NONE', 'VOLATILITY',
    'Realized vol is backward-looking but confirms vol regime. High RVOL = sustained stress.',
    'NEGATIVE',
    'CANDIDATE', 'STIG'
),
-- C5: Implied vs Realized Vol Spread
(
    'VIX_RVOL_SPREAD',
    'VIX - Realized Vol Spread',
    'Spread between implied (VIX) and realized volatility. High spread = fear premium.',
    'CALCULATED', 'VIX_RVOL_SPREAD_V1', NULL,
    'DAILY', 0, '1990-01-01',
    'NONE', 'VOLATILITY',
    'Elevated VRP (variance risk premium) indicates market pricing tail risk.',
    'NEGATIVE',
    'CANDIDATE', 'STIG'
)
ON CONFLICT (feature_id) DO UPDATE SET
    description = EXCLUDED.description,
    updated_at = NOW();

-- ============================================================================
-- CLUSTER D: FACTOR (5 Features)
-- Hypothesis: Macro-gravity on crypto prices
-- ============================================================================

INSERT INTO fhq_macro.feature_registry (
    feature_id, feature_name, description,
    provenance, source_ticker, source_url,
    frequency, lag_period_days, history_start_date,
    stationarity_method, cluster, hypothesis, expected_direction,
    status, created_by
) VALUES
-- D1: US Dollar Index (DXY)
(
    'DXY_INDEX',
    'US Dollar Index (DXY)',
    'Trade-weighted US dollar index. Strong dollar = headwind for risk assets.',
    'YAHOO', 'DX-Y.NYB', 'https://finance.yahoo.com/quote/DX-Y.NYB',
    'DAILY', 0, '1971-01-04',
    'DIFF', 'FACTOR',
    'Dollar strength is historically negative for crypto. DXY down = BTC up.',
    'NEGATIVE',
    'CANDIDATE', 'STIG'
),
-- D2: US 10Y Real Rate (TIPS)
(
    'US_10Y_REAL_RATE',
    'US 10Y Real Interest Rate',
    'Real yield on 10-year TIPS. Rising real rates = tightening financial conditions.',
    'FRED', 'DFII10', 'https://fred.stlouisfed.org/series/DFII10',
    'DAILY', 1, '2003-01-02',
    'DIFF', 'FACTOR',
    'Rising real rates increase opportunity cost of non-yielding assets like crypto.',
    'NEGATIVE',
    'CANDIDATE', 'STIG'
),
-- D3: NASDAQ-100 (Tech Beta)
(
    'NDX_INDEX',
    'NASDAQ-100 Index',
    'Large-cap technology index. Crypto historically shows high beta to tech.',
    'YAHOO', '^NDX', 'https://finance.yahoo.com/quote/%5ENDX',
    'DAILY', 0, '1985-02-01',
    'LOG_DIFF', 'FACTOR',
    'Crypto trades as high-beta tech. NDX regime drives crypto regime.',
    'POSITIVE',
    'CANDIDATE', 'STIG'
),
-- D4: Gold/SPX Ratio
(
    'GOLD_SPX_RATIO',
    'Gold to S&P 500 Ratio',
    'Relative value of gold vs equities. Rising ratio = flight to safety.',
    'CALCULATED', 'GOLD_SPX_V1', NULL,
    'DAILY', 0, '1970-01-01',
    'DIFF', 'FACTOR',
    'Gold outperformance vs stocks signals risk-off. Crypto behavior varies (store of value vs risk).',
    'AMBIGUOUS',
    'CANDIDATE', 'STIG'
),
-- D5: Copper/Gold Ratio (Dr. Copper)
(
    'COPPER_GOLD_RATIO',
    'Copper to Gold Ratio',
    'Cyclical vs defensive metal ratio. Rising ratio = growth optimism.',
    'CALCULATED', 'COPPER_GOLD_V1', NULL,
    'DAILY', 0, '1990-01-01',
    'DIFF', 'FACTOR',
    'Copper/Gold rising = risk-on environment. Crypto benefits from growth optimism.',
    'POSITIVE',
    'CANDIDATE', 'STIG'
)
ON CONFLICT (feature_id) DO UPDATE SET
    description = EXCLUDED.description,
    updated_at = NOW();

-- ============================================================================
-- UPDATE TASK REGISTRY: G1 STATUS
-- ============================================================================

UPDATE fhq_governance.task_registry
SET gate_level = 'G1',
    task_status = 'ACTIVE',
    updated_at = NOW()
WHERE task_name = 'MACRO_FACTOR_ENGINE_V1';

-- ============================================================================
-- UPDATE IOS REGISTRY: G1 STATUS
-- ============================================================================

UPDATE fhq_meta.ios_registry
SET version = '2026.PROD.G1',
    status = 'ACTIVE',
    updated_at = NOW()
WHERE ios_id = 'IoS-006';

-- ============================================================================
-- LOG G1 GOVERNANCE ACTION
-- ============================================================================

DO $$
DECLARE
    v_signature_id UUID := gen_random_uuid();
    v_action_id UUID := gen_random_uuid();
    v_payload JSONB;
    v_signature_value TEXT;
    v_feature_count INTEGER;
BEGIN
    -- Count registered features
    SELECT COUNT(*) INTO v_feature_count FROM fhq_macro.feature_registry;

    v_payload := jsonb_build_object(
        'action_type', 'IOS_MODULE_G1_POPULATION',
        'action_target', 'IoS-006',
        'decision', 'EXECUTED',
        'initiated_by', 'STIG',
        'authorized_by', ARRAY['LARS', 'VEGA'],
        'timestamp', NOW()::text,
        'chain_id', 'HC-IOS-006-2026',
        'execution_details', jsonb_build_object(
            'features_registered', v_feature_count,
            'clusters_populated', ARRAY['LIQUIDITY', 'CREDIT', 'VOLATILITY', 'FACTOR'],
            'cluster_counts', jsonb_build_object(
                'LIQUIDITY', 6,
                'CREDIT', 6,
                'VOLATILITY', 5,
                'FACTOR', 5
            ),
            'data_sources', ARRAY['FRED', 'YAHOO', 'BLOOMBERG', 'CALCULATED'],
            'compliance', ARRAY['ADR-002', 'ADR-003', 'ADR-011', 'ADR-012', 'ADR-013']
        )
    );

    v_signature_value := encode(sha256(v_payload::text::bytea), 'hex');

    INSERT INTO vision_verification.operation_signatures (
        signature_id, operation_type, operation_id, operation_table, operation_schema,
        signing_agent, signing_key_id, signature_value, signed_payload,
        verified, verified_at, verified_by, created_at, hash_chain_id
    ) VALUES (
        v_signature_id, 'IOS_MODULE_G1_POPULATION', v_action_id, 'governance_actions_log',
        'fhq_governance', 'STIG', 'STIG-EC003-IOS006-G1', v_signature_value, v_payload,
        TRUE, NOW(), 'STIG', NOW(), 'HC-IOS-006-2026'
    );

    INSERT INTO fhq_governance.governance_actions_log (
        action_id, action_type, action_target, action_target_type, initiated_by,
        initiated_at, decision, decision_rationale, vega_reviewed, vega_override,
        vega_notes, hash_chain_id, signature_id
    ) VALUES (
        v_action_id, 'IOS_MODULE_G1_POPULATION', 'IoS-006', 'IOS_MODULE', 'STIG', NOW(),
        'APPROVED',
        'G1 EXECUTION: Macro Feature Registry populated with 22 candidate features across 4 clusters. ' ||
        'Cluster A (LIQUIDITY): 6 features including M2, Fed Balance Sheet, TGA, RRP, Net Liquidity, Global M2. ' ||
        'Cluster B (CREDIT): 6 features including HY Spread, IG Spread, Yield Curve, MOVE, TED, Fed Funds. ' ||
        'Cluster C (VOLATILITY): 5 features including VIX, VIX Term Structure, VIX9D, Realized Vol, VRP. ' ||
        'Cluster D (FACTOR): 5 features including DXY, Real Rates, NDX, Gold/SPX, Copper/Gold. ' ||
        'Authorization: LARS Strategic Mandate + VEGA Governance Ratification.',
        TRUE, FALSE,
        'G1 Population authorized by joint LARS-VEGA audit synthesis. Features comply with ADR-012 API Waterfall ' ||
        '(FRED = Tier 1 Lake, YAHOO = Tier 1 Lake, BLOOMBERG = Tier 2 Pulse). Awaiting stationarity testing and IoS-005 integration.',
        'HC-IOS-006-2026', v_signature_id
    );

    RAISE NOTICE 'IoS-006 G1 POPULATION: action_id=%, signature_id=%, features=%', v_action_id, v_signature_id, v_feature_count;
END $$;

-- ============================================================================
-- UPDATE HASH CHAIN
-- ============================================================================

UPDATE vision_verification.hash_chains
SET current_hash = encode(sha256(('IoS-006_G1_POPULATION_' || NOW()::text)::bytea), 'hex'),
    chain_length = chain_length + 1,
    updated_at = NOW()
WHERE chain_id = 'HC-IOS-006-2026';

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================
-- SELECT feature_id, cluster, status FROM fhq_macro.feature_registry ORDER BY cluster, feature_id;
-- SELECT cluster, COUNT(*) FROM fhq_macro.feature_registry GROUP BY cluster;
-- SELECT * FROM fhq_governance.governance_actions_log WHERE action_target = 'IoS-006' ORDER BY initiated_at DESC;
