-- CEO-DIR-2026-111 Phase 3: CPTO Shadow Consumption Configuration
-- Classification: MANDATORY – IMMEDIATE EXECUTION
-- Implementor: STIG
-- Date: 2026-01-20

-- =============================================================================
-- PHASE 3: CPTO SHADOW CONSUMPTION
-- State: ACTIVE (Shadow)
-- can_place_orders = false
-- submit_to_line = disabled
-- =============================================================================

BEGIN;

-- Step 1: Create CPTO operational state table
CREATE TABLE IF NOT EXISTS fhq_alpha.cpto_operational_state (
    state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Operational mode
    cpto_mode TEXT NOT NULL DEFAULT 'SHADOW',
    can_place_orders BOOLEAN NOT NULL DEFAULT false,
    submit_to_line BOOLEAN NOT NULL DEFAULT false,

    -- Observation period
    shadow_observation_hours INTEGER NOT NULL DEFAULT 48,
    shadow_started_at TIMESTAMPTZ,
    shadow_ends_at TIMESTAMPTZ,

    -- Gate controls
    ttl_enforcement_enabled BOOLEAN NOT NULL DEFAULT true,
    defcon_enforcement_enabled BOOLEAN NOT NULL DEFAULT true,
    liquidity_check_enabled BOOLEAN NOT NULL DEFAULT true,
    friction_monitoring_enabled BOOLEAN NOT NULL DEFAULT true,

    -- Counters
    trade_packets_generated INTEGER NOT NULL DEFAULT 0,
    trade_packets_blocked_ttl INTEGER NOT NULL DEFAULT 0,
    trade_packets_blocked_defcon INTEGER NOT NULL DEFAULT 0,
    trade_packets_blocked_liquidity INTEGER NOT NULL DEFAULT 0,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    directive_reference TEXT NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT true,

    CONSTRAINT chk_cpto_mode CHECK (cpto_mode IN ('SHADOW', 'PAPER', 'LIVE', 'DISABLED'))
);

-- Step 2: Set initial CPTO state per CEO-DIR-2026-111
INSERT INTO fhq_alpha.cpto_operational_state (
    cpto_mode,
    can_place_orders,
    submit_to_line,
    shadow_observation_hours,
    shadow_started_at,
    shadow_ends_at,
    ttl_enforcement_enabled,
    defcon_enforcement_enabled,
    liquidity_check_enabled,
    friction_monitoring_enabled,
    directive_reference,
    is_current
) VALUES (
    'SHADOW',
    false,   -- CEO-DIR-2026-111: can_place_orders = false
    false,   -- CEO-DIR-2026-111: submit_to_line = disabled
    48,
    NOW(),
    NOW() + INTERVAL '48 hours',
    true,    -- TTL enforcement active
    true,    -- DEFCON enforcement active
    true,    -- Liquidity check active
    true,    -- Friction monitoring active
    'CEO-DIR-2026-111',
    true
);

-- Step 3: Create CPTO shadow trade packet log
CREATE TABLE IF NOT EXISTS fhq_alpha.cpto_shadow_trade_packets (
    packet_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Signal source
    source_signal_id UUID NOT NULL,
    source_plan_id UUID,
    source_module TEXT NOT NULL,
    signal_class TEXT NOT NULL,

    -- Instrument
    instrument TEXT NOT NULL,
    direction TEXT NOT NULL,
    confidence NUMERIC NOT NULL,

    -- Precision calculations (CPTO mandate)
    entry_price NUMERIC NOT NULL,
    entry_aggression NUMERIC NOT NULL,
    regime_at_calculation TEXT NOT NULL,

    -- Canonical exits (CEO-DIR-2026-107)
    atr_at_entry NUMERIC NOT NULL,
    r_value NUMERIC NOT NULL,
    stop_loss_price NUMERIC NOT NULL,
    take_profit_price NUMERIC NOT NULL,

    -- Alpha attribution (CEO Amendment B)
    mid_market_price NUMERIC NOT NULL,
    slippage_saved_bps NUMERIC NOT NULL,

    -- TTL
    signal_valid_until TIMESTAMPTZ NOT NULL,
    ttl_remaining_seconds NUMERIC NOT NULL,

    -- DEFCON
    defcon_at_creation TEXT NOT NULL,
    defcon_behavior TEXT NOT NULL,

    -- Decision
    packet_status TEXT NOT NULL DEFAULT 'SHADOW_GENERATED',
    blocked_reason TEXT,
    friction_recorded BOOLEAN NOT NULL DEFAULT false,

    -- SHADOW mode enforcement
    submitted_to_line BOOLEAN NOT NULL DEFAULT false,
    orders_placed BOOLEAN NOT NULL DEFAULT false,

    -- Audit lineage (Fix #5)
    parameter_set_version TEXT NOT NULL,
    parameter_set_hash TEXT NOT NULL,
    input_features_hash TEXT NOT NULL,
    calculation_logic_hash TEXT NOT NULL,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    directive_reference TEXT NOT NULL DEFAULT 'CEO-DIR-2026-111',

    CONSTRAINT chk_shadow_enforcement CHECK (
        submitted_to_line = false AND orders_placed = false
    )
);

CREATE INDEX IF NOT EXISTS idx_shadow_packets_status
ON fhq_alpha.cpto_shadow_trade_packets(packet_status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_shadow_packets_instrument
ON fhq_alpha.cpto_shadow_trade_packets(instrument, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_shadow_packets_signal_class
ON fhq_alpha.cpto_shadow_trade_packets(signal_class, created_at DESC);

-- Step 4: Create function to get current CPTO state
CREATE OR REPLACE FUNCTION fhq_alpha.get_cpto_state()
RETURNS TABLE (
    cpto_mode TEXT,
    can_place_orders BOOLEAN,
    submit_to_line BOOLEAN,
    shadow_ends_at TIMESTAMPTZ,
    ttl_enforcement BOOLEAN,
    defcon_enforcement BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.cpto_mode,
        s.can_place_orders,
        s.submit_to_line,
        s.shadow_ends_at,
        s.ttl_enforcement_enabled,
        s.defcon_enforcement_enabled
    FROM fhq_alpha.cpto_operational_state s
    WHERE s.is_current = true
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Step 5: Create function to verify CPTO shadow compliance
CREATE OR REPLACE FUNCTION fhq_alpha.verify_cpto_shadow_compliance()
RETURNS JSONB AS $$
DECLARE
    v_state RECORD;
    v_packets INTEGER;
    v_violations INTEGER;
BEGIN
    SELECT * INTO v_state
    FROM fhq_alpha.cpto_operational_state
    WHERE is_current = true;

    SELECT COUNT(*) INTO v_packets
    FROM fhq_alpha.cpto_shadow_trade_packets
    WHERE created_at > v_state.shadow_started_at;

    SELECT COUNT(*) INTO v_violations
    FROM fhq_alpha.cpto_shadow_trade_packets
    WHERE created_at > v_state.shadow_started_at
    AND (submitted_to_line = true OR orders_placed = true);

    RETURN jsonb_build_object(
        'cpto_mode', v_state.cpto_mode,
        'can_place_orders', v_state.can_place_orders,
        'submit_to_line', v_state.submit_to_line,
        'shadow_started_at', v_state.shadow_started_at,
        'shadow_ends_at', v_state.shadow_ends_at,
        'trade_packets_generated', v_packets,
        'shadow_violations', v_violations,
        'compliance_status', CASE WHEN v_violations = 0 THEN 'COMPLIANT' ELSE 'VIOLATION' END,
        'checked_at', NOW()
    );
END;
$$ LANGUAGE plpgsql;

-- Step 6: Log governance action
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    metadata,
    vega_reviewed
) VALUES (
    'CPTO_SHADOW_ACTIVATION',
    'EC-015',
    'EMPLOYMENT_CONTRACT',
    'CEO',
    NOW(),
    'APPROVED',
    'CEO-DIR-2026-111 Phase 3: CPTO configured for Shadow consumption. ' ||
    'can_place_orders = false, submit_to_line = disabled. ' ||
    'CPTO will perform: precision entry calculation, ATR-based SL/TP, ' ||
    'slippage-saved attribution, TTL enforcement, DEFCON-aware refusal, friction monitoring. ' ||
    'TradePackets generated but NEVER executed.',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-111',
        'phase', 3,
        'cpto_mode', 'SHADOW',
        'can_place_orders', false,
        'submit_to_line', false,
        'shadow_observation_hours', 48,
        'success_criteria', ARRAY[
            'Precision entry calculation',
            'ATR-based SL / R-based TP',
            'Slippage-saved attribution (bps)',
            'TTL enforcement',
            'DEFCON-aware refusal logic',
            'Friction monitoring',
            'TradePackets generated, never executed'
        ]
    ),
    false
);

COMMIT;

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Verify CPTO operational state
SELECT * FROM fhq_alpha.cpto_operational_state WHERE is_current = true;

-- Verify compliance function
SELECT fhq_alpha.verify_cpto_shadow_compliance();
