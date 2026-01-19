-- =============================================================================
-- G0-2026-019: CEIO GEOPOLITICAL FRICTION MANDATE EXPANSION
-- =============================================================================
--
-- Authority: CEO (Pending G4 Approval)
-- Gate Status: G0 SUBMITTED
-- Scope: CEIO mandate expansion for geopolitical friction monitoring
-- Classification: INFRASTRUCTURE_EXTENSION
--
-- This migration creates the infrastructure for tracking:
-- 1. Geopolitical friction indicators (tariffs, BRICS settlement, sanctions)
-- 2. New macro nodes for de-dollarization monitoring
-- 3. Causal edges for geopolitical → market transmission
-- 4. BIFURCATED_LIQUIDITY regime definition
--
-- DO NOT EXECUTE until G4 CEO approval received.
-- =============================================================================

BEGIN;

-- =============================================================================
-- SECTION 1: NEW DATA SOURCES
-- =============================================================================

INSERT INTO fhq_governance.approved_data_sources
    (source_code, source_name, source_type, api_endpoint, verification_method, approved_by, is_active)
VALUES
    ('USTR', 'US Trade Representative', 'GOVERNMENT_AGENCY',
     'https://ustr.gov/issue-areas/industry-manufacturing/industrial-tariffs',
     'OFFICIAL_PUBLICATION', 'CEO', true),

    ('BIS', 'Bank for International Settlements', 'INTERNATIONAL_ORG',
     'https://www.bis.org/statistics/index.htm',
     'API_WITH_HASH', 'CEO', true),

    ('IMF_COFER', 'IMF Currency Composition of FX Reserves', 'INTERNATIONAL_ORG',
     'https://data.imf.org/regular.aspx?key=41175',
     'QUARTERLY_PUBLICATION', 'CEO', true),

    ('OFAC', 'Office of Foreign Assets Control', 'GOVERNMENT_AGENCY',
     'https://sanctionssearch.ofac.treas.gov/',
     'OFFICIAL_PUBLICATION', 'CEO', true)
ON CONFLICT (source_code) DO NOTHING;

-- =============================================================================
-- SECTION 2: NEW MACRO NODES - GEOPOLITICAL FRICTION
-- =============================================================================

-- Composite Geopolitical Friction Index
INSERT INTO fhq_macro.macro_nodes (
    node_id, canonical_id, node_type, subtype, description,
    source_tier, source_provider, frequency,
    relevance_horizon_days, stress_threshold, extreme_threshold,
    created_by, g2_integrated
) VALUES (
    'MACRO_GEOPOLITICAL_FRICTION',
    'MACRO_GEOPOLITICAL_FRICTION',
    'MACRO_FACTOR',
    'GEOPOLITICAL',
    'Composite de-dollarization pressure index (0-1 scale)',
    'DERIVED',
    NULL,
    'WEEKLY',
    30,
    0.70,
    0.85,
    'CEIO',
    false  -- Pending G2 integration
) ON CONFLICT (node_id) DO NOTHING;

-- Effective Tariff Rate
INSERT INTO fhq_macro.macro_nodes (
    node_id, canonical_id, node_type, subtype, description,
    source_tier, source_provider, frequency,
    relevance_horizon_days, stress_threshold, extreme_threshold,
    created_by, g2_integrated
) VALUES (
    'MACRO_TARIFF_EFFECTIVE_RATE',
    'MACRO_TARIFF_EFFECTIVE_RATE',
    'MACRO_FACTOR',
    'TRADE',
    'Trade-weighted average US tariff rate (percentage)',
    'LAKE',
    'USTR',
    'MONTHLY',
    60,
    15.0,
    25.0,
    'CEIO',
    false
) ON CONFLICT (node_id) DO NOTHING;

-- BRICS Settlement Share
INSERT INTO fhq_macro.macro_nodes (
    node_id, canonical_id, node_type, subtype, description,
    source_tier, source_provider, frequency,
    relevance_horizon_days, stress_threshold, extreme_threshold,
    created_by, g2_integrated
) VALUES (
    'MACRO_BRICS_SETTLEMENT_SHARE',
    'MACRO_BRICS_SETTLEMENT_SHARE',
    'MACRO_FACTOR',
    'LIQUIDITY',
    'Non-USD international settlement percentage (BRICS+ systems)',
    'PULSE',
    'BIS',
    'QUARTERLY',
    90,
    20.0,
    30.0,
    'CEIO',
    false
) ON CONFLICT (node_id) DO NOTHING;

-- Sanctions Intensity Index
INSERT INTO fhq_macro.macro_nodes (
    node_id, canonical_id, node_type, subtype, description,
    source_tier, source_provider, frequency,
    relevance_horizon_days, stress_threshold, extreme_threshold,
    created_by, g2_integrated
) VALUES (
    'MACRO_SANCTIONS_INTENSITY',
    'MACRO_SANCTIONS_INTENSITY',
    'MACRO_FACTOR',
    'GEOPOLITICAL',
    'Active US/EU sanctions programs intensity (normalized 0-1)',
    'LAKE',
    'OFAC',
    'WEEKLY',
    14,
    0.60,
    0.80,
    'CEIO',
    false
) ON CONFLICT (node_id) DO NOTHING;

-- USD Reserve Share (IMF COFER)
INSERT INTO fhq_macro.macro_nodes (
    node_id, canonical_id, node_type, subtype, description,
    source_tier, source_provider, frequency,
    relevance_horizon_days, stress_threshold, extreme_threshold,
    created_by, g2_integrated
) VALUES (
    'MACRO_USD_RESERVE_SHARE',
    'MACRO_USD_RESERVE_SHARE',
    'MACRO_FACTOR',
    'LIQUIDITY',
    'USD share of global FX reserves (IMF COFER)',
    'LAKE',
    'IMF_COFER',
    'QUARTERLY',
    90,
    55.0,  -- Below 55% is stress (historical floor ~58%)
    50.0,  -- Below 50% is extreme
    'CEIO',
    false
) ON CONFLICT (node_id) DO NOTHING;

-- =============================================================================
-- SECTION 3: CAUSAL EDGES - GEOPOLITICAL TRANSMISSION MECHANISMS
-- =============================================================================

-- Tariffs amplify USD strength (short-term)
INSERT INTO fhq_macro.macro_edges (
    source_node_id, target_node_id, edge_type,
    lag_days, amplification_factor,
    minimum_observations, significance_level,
    is_significant, stability_verified,
    created_by, g2_integrated
) VALUES (
    'MACRO_TARIFF_EFFECTIVE_RATE',
    'MACRO_DXY',
    'AMPLIFIES',
    NULL,
    1.3,
    52,  -- 1 year of weekly data
    0.05,
    false,  -- Pending CRIO validation
    false,
    'CEIO',
    false
) ON CONFLICT DO NOTHING;

-- BRICS settlement inhibits USD demand
INSERT INTO fhq_macro.macro_edges (
    source_node_id, target_node_id, edge_type,
    lag_days, inhibition_score,
    minimum_observations, significance_level,
    is_significant, stability_verified,
    created_by, g2_integrated
) VALUES (
    'MACRO_BRICS_SETTLEMENT_SHARE',
    'MACRO_DXY',
    'INHIBITS',
    NULL,
    0.7,
    20,  -- 5 years of quarterly data
    0.05,
    false,
    false,
    'CEIO',
    false
) ON CONFLICT DO NOTHING;

-- Geopolitical friction leads crypto adoption (neutral reserve thesis)
INSERT INTO fhq_macro.macro_edges (
    source_node_id, target_node_id, edge_type,
    lag_days, correlation_value,
    minimum_observations, significance_level,
    is_significant, stability_verified,
    created_by, g2_integrated
) VALUES (
    'MACRO_GEOPOLITICAL_FRICTION',
    'BTC-USD',
    'LEADS',
    14,  -- 2-week lag
    0.45,
    104,  -- 2 years of weekly data
    0.05,
    false,
    false,
    'CEIO',
    false
) ON CONFLICT DO NOTHING;

-- Sanctions accelerate BRICS adoption
INSERT INTO fhq_macro.macro_edges (
    source_node_id, target_node_id, edge_type,
    lag_days, amplification_factor,
    minimum_observations, significance_level,
    is_significant, stability_verified,
    created_by, g2_integrated
) VALUES (
    'MACRO_SANCTIONS_INTENSITY',
    'MACRO_BRICS_SETTLEMENT_SHARE',
    'AMPLIFIES',
    NULL,
    1.5,
    20,
    0.05,
    false,
    false,
    'CEIO',
    false
) ON CONFLICT DO NOTHING;

-- Geopolitical friction amplifies volatility
INSERT INTO fhq_macro.macro_edges (
    source_node_id, target_node_id, edge_type,
    lag_days, amplification_factor,
    minimum_observations, significance_level,
    is_significant, stability_verified,
    created_by, g2_integrated
) VALUES (
    'MACRO_GEOPOLITICAL_FRICTION',
    'MACRO_VIX',
    'AMPLIFIES',
    NULL,
    1.8,
    104,
    0.05,
    false,
    false,
    'CEIO',
    false
) ON CONFLICT DO NOTHING;

-- =============================================================================
-- SECTION 4: GEOPOLITICAL FRICTION DATA TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_macro.geopolitical_friction_data (
    friction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    observation_date DATE NOT NULL,

    -- Component values (raw)
    tariff_effective_rate NUMERIC,
    brics_settlement_share NUMERIC,
    sanctions_intensity_raw NUMERIC,
    usd_reserve_share NUMERIC,

    -- Normalized components (0-1)
    tariff_normalized NUMERIC,
    brics_settlement_normalized NUMERIC,
    sanctions_normalized NUMERIC,
    usd_reserve_delta_normalized NUMERIC,

    -- Composite index
    geopolitical_friction_index NUMERIC GENERATED ALWAYS AS (
        0.30 * COALESCE(tariff_normalized, 0) +
        0.35 * COALESCE(brics_settlement_normalized, 0) +
        0.20 * COALESCE(sanctions_normalized, 0) +
        0.15 * COALESCE(usd_reserve_delta_normalized, 0)
    ) STORED,

    -- Metadata
    source_notes TEXT,
    data_quality_score NUMERIC DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'CEIO',

    CONSTRAINT chk_date_unique UNIQUE (observation_date)
);

-- Index for time-series queries
CREATE INDEX IF NOT EXISTS idx_friction_date
ON fhq_macro.geopolitical_friction_data(observation_date DESC);

-- Index for threshold monitoring
CREATE INDEX IF NOT EXISTS idx_friction_index
ON fhq_macro.geopolitical_friction_data(geopolitical_friction_index)
WHERE geopolitical_friction_index > 0.60;

-- =============================================================================
-- SECTION 5: TARIFF SCHEDULE TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_macro.tariff_schedule (
    tariff_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    effective_date DATE NOT NULL,
    target_country TEXT NOT NULL,
    tariff_category TEXT,  -- 'SECTION_301', 'NATIONAL_SECURITY', 'RETALIATORY', etc.
    tariff_rate_pct NUMERIC NOT NULL,
    trade_value_usd NUMERIC,  -- Annual trade volume affected
    source_announcement TEXT,
    source_url TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'CEIO'
);

CREATE INDEX IF NOT EXISTS idx_tariff_effective_date
ON fhq_macro.tariff_schedule(effective_date DESC);

CREATE INDEX IF NOT EXISTS idx_tariff_country
ON fhq_macro.tariff_schedule(target_country);

-- =============================================================================
-- SECTION 6: BIFURCATED_LIQUIDITY REGIME DEFINITION
-- =============================================================================

-- Add new regime to regime definitions if table exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'fhq_meta' AND table_name = 'regime_definitions') THEN
        INSERT INTO fhq_meta.regime_definitions (
            regime_code, regime_name, description, trigger_conditions,
            hysteresis_entry_days, hysteresis_exit_days, confidence_ceiling,
            created_by
        ) VALUES (
            'BIFURCATED_LIQUIDITY',
            'Bifurcated Liquidity',
            'Global liquidity split between USD and alternative settlement systems (BRICS+)',
            jsonb_build_object(
                'conditions', ARRAY[
                    'MACRO_BRICS_SETTLEMENT_SHARE > 15%',
                    'MACRO_TARIFF_EFFECTIVE_RATE > 20%',
                    'MACRO_GEOPOLITICAL_FRICTION > 0.60'
                ],
                'logic', 'ANY_TWO_OF_THREE'
            ),
            5,   -- Entry confirmation days
            10,  -- Exit confirmation days
            0.60, -- Confidence ceiling in this regime
            'CEIO'
        ) ON CONFLICT DO NOTHING;
    END IF;
END$$;

-- =============================================================================
-- SECTION 7: CEIO EXPANDED CONTRACTS
-- =============================================================================

-- Contract: Geopolitical Data Refresh
INSERT INTO fhq_governance.agent_contracts (
    contract_id, source_agent, target_agent, trigger_event, expected_action, sla_seconds, metadata
) VALUES (
    gen_random_uuid(),
    'CEIO',
    'STIG',
    'GEOPOLITICAL_DATA_REFRESH',
    'UPDATE_FRICTION_NODES',
    21600,  -- 6 hours
    jsonb_build_object(
        'directive', 'G0-2026-019',
        'contract_status', 'PENDING_G4',
        'frequency', 'WEEKLY',
        'target_tables', ARRAY['fhq_macro.geopolitical_friction_data', 'fhq_macro.tariff_schedule']
    )
) ON CONFLICT DO NOTHING;

-- Contract: Friction Stress Alert
INSERT INTO fhq_governance.agent_contracts (
    contract_id, source_agent, target_agent, trigger_event, expected_action, sla_seconds, metadata
) VALUES (
    gen_random_uuid(),
    'CEIO',
    'LARS',
    'FRICTION_STRESS_THRESHOLD',
    'ALERT_CEO_AND_LARS',
    1800,  -- 30 minutes
    jsonb_build_object(
        'directive', 'G0-2026-019',
        'contract_status', 'PENDING_G4',
        'threshold', 0.70,
        'escalation_path', 'CEIO → LARS → CEO'
    )
) ON CONFLICT DO NOTHING;

-- Contract: Friction Extreme DEFCON Trigger
INSERT INTO fhq_governance.agent_contracts (
    contract_id, source_agent, target_agent, trigger_event, expected_action, sla_seconds, metadata
) VALUES (
    gen_random_uuid(),
    'CEIO',
    'DEFCON_CONTROLLER',
    'FRICTION_EXTREME_THRESHOLD',
    'TRIGGER_DEFCON_3',
    600,  -- 10 minutes
    jsonb_build_object(
        'directive', 'G0-2026-019',
        'contract_status', 'PENDING_G4',
        'threshold', 0.85,
        'defcon_level', 3,
        'rationale', 'Extreme geopolitical friction indicates systemic regime shift'
    )
) ON CONFLICT DO NOTHING;

-- =============================================================================
-- SECTION 8: CEIO SCHEDULED TASKS
-- =============================================================================

INSERT INTO fhq_execution.task_registry (
    task_id, task_name, gate_level, owned_by, executed_by, enabled,
    schedule_cron, run_count, error_count, config, created_at
) VALUES (
    gen_random_uuid(),
    'ceio_geopolitical_friction_update',
    'G2',
    'CEIO',
    'WINDOWS_SCHEDULER',
    false,  -- Disabled until G4 approval
    '0 6 * * 1',  -- Weekly on Monday 06:00 UTC
    0,
    0,
    jsonb_build_object(
        'directive', 'G0-2026-019',
        'description', 'Weekly geopolitical friction index update',
        'target_table', 'fhq_macro.geopolitical_friction_data',
        'awaiting_g4', true
    ),
    NOW()
) ON CONFLICT DO NOTHING;

INSERT INTO fhq_execution.task_registry (
    task_id, task_name, gate_level, owned_by, executed_by, enabled,
    schedule_cron, run_count, error_count, config, created_at
) VALUES (
    gen_random_uuid(),
    'ceio_tariff_schedule_monitor',
    'G2',
    'CEIO',
    'WINDOWS_SCHEDULER',
    false,  -- Disabled until G4 approval
    '0 12 * * *',  -- Daily at 12:00 UTC
    0,
    0,
    jsonb_build_object(
        'directive', 'G0-2026-019',
        'description', 'Daily tariff announcement monitor',
        'target_table', 'fhq_macro.tariff_schedule',
        'awaiting_g4', true
    ),
    NOW()
) ON CONFLICT DO NOTHING;

-- =============================================================================
-- SECTION 9: GOVERNANCE LOGGING
-- =============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id, action_type, action_target, action_target_type,
    initiated_by, initiated_at, decision, decision_rationale, metadata
) VALUES (
    gen_random_uuid(),
    'G0_PROPOSAL_SUBMITTED',
    'CEIO_GEOPOLITICAL_FRICTION_MANDATE',
    'MANDATE_EXPANSION',
    'STIG',
    NOW(),
    'PENDING_G4',
    'G0-2026-019: CEIO mandate expansion for geopolitical friction monitoring. Infrastructure created but tasks disabled pending CEO G4 approval.',
    jsonb_build_object(
        'proposal_id', 'G0-2026-019',
        'new_nodes', ARRAY['MACRO_GEOPOLITICAL_FRICTION', 'MACRO_TARIFF_EFFECTIVE_RATE', 'MACRO_BRICS_SETTLEMENT_SHARE', 'MACRO_SANCTIONS_INTENSITY', 'MACRO_USD_RESERVE_SHARE'],
        'new_edges', 5,
        'new_contracts', 3,
        'new_tasks', 2,
        'new_regime', 'BIFURCATED_LIQUIDITY',
        'constitutional_alignment', ARRAY['ADR-014', 'ADR-013', 'IoS-006', 'IoS-007']
    )
);

COMMIT;

-- =============================================================================
-- VERIFICATION QUERIES (Run after migration)
-- =============================================================================

-- SELECT * FROM fhq_macro.macro_nodes WHERE subtype IN ('GEOPOLITICAL', 'TRADE');
-- SELECT * FROM fhq_macro.macro_edges WHERE source_node_id LIKE 'MACRO_GEO%' OR source_node_id LIKE 'MACRO_TARIFF%' OR source_node_id LIKE 'MACRO_BRICS%' OR source_node_id LIKE 'MACRO_SANCTIONS%';
-- SELECT * FROM fhq_governance.agent_contracts WHERE metadata->>'directive' = 'G0-2026-019';
-- SELECT * FROM fhq_execution.task_registry WHERE config->>'directive' = 'G0-2026-019';
