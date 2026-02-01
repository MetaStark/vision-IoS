-- Migration 280: CFAO Bear→Stress Synthesis Scenarios
-- CEO Post-G3 Directive 4.1: Generate stress transition scenarios
-- Date: 2026-01-17
-- Author: STIG
-- Purpose: Create synthetic scenarios for BEAR→STRESS regime transitions

-- ============================================================================
-- CFAO BEAR→STRESS SYNTHESIS
-- ============================================================================
-- Critical finding: STRESS regime has 0% hit rate (complete model failure)
-- Need scenarios to understand transition dynamics and improve detection

-- Step 1: Generate BEAR→STRESS transition scenarios
INSERT INTO fhq_governance.cfao_synthetic_scenarios (
    scenario_id, scenario_type, scenario_name, description, severity,
    volatility_multiplier, regime_before, regime_after, correlation_shift,
    primary_assets, secondary_assets, expected_brier_impact,
    expected_confidence_impact, expected_hit_rate_impact,
    duration_hours, ramp_up_hours, created_by
) VALUES

-- Scenario 1: Flash Crash Transition
('BEAR_STRESS_001', 'REGIME_TRANSITION', 'Flash Crash - Rapid BEAR to STRESS',
 'Simulates sudden flash crash scenario where BEAR regime rapidly transitions to STRESS. VIX spike 50%+, correlations break down.',
 'EXTREME', 3.5, 'BEAR', 'STRESS', -0.40,
 ARRAY['SPY', 'QQQ', 'VIX'], ARRAY['TLT', 'GLD', 'BTC-USD'],
 0.35, -0.50, -0.30, 4, 0, 'CFAO'),

-- Scenario 2: Slow Deterioration
('BEAR_STRESS_002', 'REGIME_TRANSITION', 'Slow BEAR Deterioration to STRESS',
 'Gradual transition over 48h as BEAR conditions worsen. Selling pressure builds, liquidity dries up.',
 'HIGH', 2.0, 'BEAR', 'STRESS', -0.25,
 ARRAY['SPY', 'IWM', 'HYG'], ARRAY['TLT', 'SHY', 'UUP'],
 0.25, -0.35, -0.20, 48, 12, 'CFAO'),

-- Scenario 3: Geopolitical Shock
('BEAR_STRESS_003', 'BLACK_SWAN', 'Geopolitical BEAR→STRESS Shock',
 'Major geopolitical event during BEAR market triggers STRESS. Oil spikes, safe havens rally.',
 'EXTREME', 4.0, 'BEAR', 'STRESS', -0.50,
 ARRAY['USO', 'XLE', 'EFA'], ARRAY['GLD', 'TLT', 'UUP'],
 0.40, -0.60, -0.35, 12, 2, 'CFAO'),

-- Scenario 4: Liquidity Crisis
('BEAR_STRESS_004', 'LIQUIDITY_CRISIS', 'BEAR Market Liquidity Seizure',
 'Liquidity crisis during BEAR market. Spreads widen dramatically, market makers pull back.',
 'EXTREME', 5.0, 'BEAR', 'STRESS', -0.60,
 ARRAY['HYG', 'LQD', 'JNK'], ARRAY['TLT', 'SHY', 'GOVT'],
 0.50, -0.70, -0.40, 8, 1, 'CFAO'),

-- Scenario 5: FOMC Emergency Cut
('BEAR_STRESS_005', 'REGIME_TRANSITION', 'Emergency Fed Action During BEAR',
 'Fed emergency rate cut signals STRESS conditions. Initial rally then uncertainty.',
 'HIGH', 2.5, 'BEAR', 'STRESS', -0.20,
 ARRAY['SPY', 'TLT', 'GLD'], ARRAY['XLF', 'KRE', 'XLI'],
 0.20, -0.25, -0.15, 24, 4, 'CFAO'),

-- Scenario 6: Crypto Contagion
('BEAR_STRESS_006', 'CORRELATION_BREAK', 'Crypto Collapse → Equity STRESS',
 'Major crypto exchange failure during BEAR triggers equity STRESS. Risk-off cascade.',
 'EXTREME', 3.0, 'BEAR', 'STRESS', -0.35,
 ARRAY['BTC-USD', 'ETH-USD', 'COIN'], ARRAY['SPY', 'QQQ', 'ARKK'],
 0.35, -0.45, -0.25, 16, 3, 'CFAO'),

-- Scenario 7: Credit Event
('BEAR_STRESS_007', 'BLACK_SWAN', 'Major Credit Default During BEAR',
 'Large corporate default triggers credit contagion during BEAR market.',
 'EXTREME', 4.5, 'BEAR', 'STRESS', -0.55,
 ARRAY['HYG', 'JNK', 'XLF'], ARRAY['TLT', 'GOVT', 'GLD'],
 0.45, -0.55, -0.35, 36, 6, 'CFAO'),

-- Scenario 8: VIX Explosion
('BEAR_STRESS_008', 'VOLATILITY_SPIKE', 'VIX 80+ BEAR to STRESS',
 'VIX spikes above 80 during BEAR market, signaling extreme fear and STRESS transition.',
 'EXTREME', 6.0, 'BEAR', 'STRESS', -0.70,
 ARRAY['VIX', 'UVXY', 'VIXY'], ARRAY['SPY', 'QQQ', 'IWM'],
 0.55, -0.75, -0.45, 6, 1, 'CFAO'),

-- Scenario 9: Bond Market Stress
('BEAR_STRESS_009', 'REGIME_TRANSITION', 'Treasury Auction Failure',
 'Failed Treasury auction during BEAR triggers liquidity crisis and STRESS.',
 'HIGH', 2.8, 'BEAR', 'STRESS', -0.30,
 ARRAY['TLT', 'IEF', 'GOVT'], ARRAY['SPY', 'GLD', 'UUP'],
 0.28, -0.40, -0.22, 18, 4, 'CFAO'),

-- Scenario 10: Weekend Gap STRESS
('BEAR_STRESS_010', 'EDGE_CASE', 'Weekend Gap into STRESS',
 'BEAR market Friday close, major weekend news, gap into STRESS Monday open.',
 'HIGH', 3.2, 'BEAR', 'STRESS', -0.35,
 ARRAY['SPY', 'ES', 'NQ'], ARRAY['VIX', 'GLD', 'TLT'],
 0.32, -0.45, -0.28, 8, 0, 'CFAO');

-- Step 2: Generate model-specific failure scenarios (based on 0% hit rate finding)
INSERT INTO fhq_governance.cfao_synthetic_scenarios (
    scenario_id, scenario_type, scenario_name, description, severity,
    volatility_multiplier, regime_before, regime_after, correlation_shift,
    primary_assets, secondary_assets, expected_brier_impact,
    expected_confidence_impact, expected_hit_rate_impact,
    duration_hours, ramp_up_hours, created_by
) VALUES

-- Model failure scenarios
('STRESS_MODEL_001', 'EDGE_CASE', 'STRESS Regime Model Breakdown',
 'Scenario simulating complete model failure in STRESS regime. All predictions inverted.',
 'EXTREME', 4.0, 'STRESS', 'STRESS', -0.50,
 ARRAY['SPY', 'QQQ', 'VIX'], ARRAY['ALL'],
 0.80, -0.90, -0.50, 12, 2, 'CFAO'),

('STRESS_MODEL_002', 'EDGE_CASE', 'STRESS Confidence Inversion',
 'High confidence predictions systematically wrong in STRESS. Tests confidence damping.',
 'EXTREME', 3.5, 'STRESS', 'STRESS', -0.40,
 ARRAY['SPY', 'TLT', 'GLD'], ARRAY['ALL'],
 0.70, -0.85, -0.45, 24, 4, 'CFAO'),

('STRESS_MODEL_003', 'EDGE_CASE', 'Anti-Predictive STRESS Behavior',
 'Model predictions become anti-correlated with outcomes during STRESS.',
 'EXTREME', 3.0, 'STRESS', 'STRESS', -0.30,
 ARRAY['ALL'], ARRAY['ALL'],
 0.60, -0.80, -0.40, 48, 8, 'CFAO');

-- Step 3: Create view for Bear→Stress scenario analysis
CREATE OR REPLACE VIEW fhq_governance.v_bear_stress_scenarios AS
SELECT
    scenario_id,
    scenario_name,
    severity,
    volatility_multiplier,
    expected_brier_impact,
    expected_hit_rate_impact,
    duration_hours,
    CASE
        WHEN expected_brier_impact > 0.40 THEN 'CRITICAL'
        WHEN expected_brier_impact > 0.25 THEN 'HIGH'
        ELSE 'MODERATE'
    END as calibration_priority
FROM fhq_governance.cfao_synthetic_scenarios
WHERE regime_before = 'BEAR' AND regime_after = 'STRESS'
ORDER BY expected_brier_impact DESC;

-- Step 4: Log governance action
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'CFAO_BEAR_STRESS_SYNTHESIS',
    'cfao_synthetic_scenarios',
    'STRESS_TEST_SUITE',
    'CFAO',
    'GENERATED',
    'CEO Post-G3 Directive 4.1: Generated 13 Bear→Stress synthesis scenarios for stress testing. Includes model failure scenarios based on 0% STRESS hit rate finding.',
    jsonb_build_object(
        'bear_stress_scenarios', 10,
        'model_failure_scenarios', 3,
        'total_scenarios', 13,
        'severity_extreme', 9,
        'severity_high', 4,
        'key_finding', 'STRESS regime 0% hit rate = complete model failure',
        'directive', 'CEO Post-G3 Directive 4.1'
    )
);

-- Verification
DO $$
DECLARE
    scenario_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO scenario_count
    FROM fhq_governance.cfao_synthetic_scenarios
    WHERE scenario_id LIKE 'BEAR_STRESS%' OR scenario_id LIKE 'STRESS_MODEL%';

    RAISE NOTICE 'CFAO Bear→Stress Synthesis: % scenarios generated', scenario_count;
END $$;
