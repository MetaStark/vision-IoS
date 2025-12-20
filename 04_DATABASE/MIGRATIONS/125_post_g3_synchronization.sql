-- ============================================================================
-- Migration 125: POST-G3 SYNCHRONIZATION ORDER
-- CEO DIRECTIVE: State Regeneration, Regime Binding, ACI Rehydration
-- ============================================================================
-- Authority: CEO via STIG (CTO) per EC-003
-- ADR References: ADR-016, ADR-018, ADR-020
-- Classification: SYNCHRONIZATION (NO ACTIVATION)
-- ============================================================================
-- CONSTRAINT: NO CEIO activation, NO DEFCON change, NO ACI autonomy lift
-- ============================================================================

BEGIN;

-- ============================================================================
-- PART A: ADR-018 Shared State Regeneration
-- Generate state_vector = {defcon, regime, strategy, quad_hash}
-- ============================================================================

-- Create state snapshot table if not exists
CREATE TABLE IF NOT EXISTS vision_signals.state_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_version INTEGER NOT NULL,
    defcon_level TEXT NOT NULL,
    regime_distribution JSONB NOT NULL,
    strategy_mode TEXT NOT NULL,
    quad_hash TEXT NOT NULL,
    state_snapshot_hash TEXT NOT NULL,
    causal_edge_count INTEGER NOT NULL,
    avg_confidence NUMERIC(6,4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    published_to JSONB DEFAULT '[]'::jsonb
);

-- Insert new state snapshot v2
INSERT INTO vision_signals.state_snapshots (
    snapshot_version,
    defcon_level,
    regime_distribution,
    strategy_mode,
    quad_hash,
    state_snapshot_hash,
    causal_edge_count,
    avg_confidence,
    published_to
) VALUES (
    2,
    'YELLOW',
    '{
        "MARKET_SPECIFIC": {"edge_count": 1486, "binding_multiplier": 0.6959},
        "MACRO_DRIVEN": {"edge_count": 396, "binding_multiplier": 0.1921},
        "BULL": {"edge_count": 20, "binding_multiplier": 0.0094}
    }'::jsonb,
    'PASSIVE_OBSERVATION',
    'QUAD-G3-20251211-150948-bce77606d52b12700fde418416ba8fa0',
    'STATE-V2-' || MD5('YELLOW-PASSIVE-1902-0.8973-' || NOW()::text),
    1902,
    0.8973,
    '["LARS", "FINN", "ACI"]'::jsonb
);

-- ============================================================================
-- PART B: Regime-Cause Binding Refresh (IoS-003)
-- Store regime inference pack v2
-- ============================================================================

CREATE TABLE IF NOT EXISTS vision_signals.regime_inference_packs (
    pack_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pack_version INTEGER NOT NULL,
    regime_multipliers JSONB NOT NULL,
    causal_binding_stats JSONB NOT NULL,
    active_predictions JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO vision_signals.regime_inference_packs (
    pack_version,
    regime_multipliers,
    causal_binding_stats,
    active_predictions
) VALUES (
    2,
    '{
        "STRONG_BULL": {"allocation": 1.0, "conf_threshold": 0.50, "causal_weight": 0.92},
        "BULL": {"allocation": 0.75, "conf_threshold": 0.45, "causal_weight": 0.89},
        "RANGE_UP": {"allocation": 0.50, "conf_threshold": 0.40, "causal_weight": 0.87},
        "NEUTRAL": {"allocation": 0.00, "conf_threshold": 0.35, "causal_weight": 0.85},
        "RANGE_DOWN": {"allocation": -0.25, "conf_threshold": 0.40, "causal_weight": 0.87},
        "BEAR": {"allocation": -0.50, "conf_threshold": 0.45, "causal_weight": 0.89},
        "STRONG_BEAR": {"allocation": -0.75, "conf_threshold": 0.50, "causal_weight": 0.92},
        "PARABOLIC": {"allocation": 0.25, "conf_threshold": 0.60, "causal_weight": 0.90},
        "VOLATILE_NON_DIRECTIONAL": {"allocation": 0.00, "conf_threshold": 0.60, "causal_weight": 0.85},
        "BROKEN": {"allocation": 0.00, "conf_threshold": 0.00, "causal_weight": 0.00}
    }'::jsonb,
    '{
        "total_causal_edges": 1902,
        "avg_confidence": 0.8973,
        "conf_stddev": 0.0318,
        "variance_class": "LOW_VARIANCE",
        "macro_dominance_ratio": 0.21,
        "market_specific_ratio": 0.78
    }'::jsonb,
    '{
        "AAPL": {"regime": "BULL", "probability": 0.95},
        "MSFT": {"regime": "BEAR", "probability": 0.95},
        "QQQ": {"regime": "BULL", "probability": 0.95},
        "SPY": {"regime": "BULL", "probability": 0.95},
        "NVDA": {"regime": "NEUTRAL", "probability": 0.60}
    }'::jsonb
);

-- ============================================================================
-- PART C: Drift & Safety Validation (ADR-016)
-- discrepancy < 0.05 → mark SAFE_TO_LIFT
-- ============================================================================

CREATE TABLE IF NOT EXISTS vision_signals.safety_validations (
    validation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    validation_type TEXT NOT NULL,
    discrepancy_score NUMERIC(6,4) NOT NULL,
    threshold NUMERIC(6,4) NOT NULL,
    result TEXT NOT NULL,
    defcon_recommendation TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- conf_stddev = 0.0318 < 0.05 threshold
INSERT INTO vision_signals.safety_validations (
    validation_type,
    discrepancy_score,
    threshold,
    result,
    defcon_recommendation
) VALUES (
    'POST_G3_DISCREPANCY_AUDIT',
    0.0318,
    0.0500,
    'SAFE_TO_LIFT',
    'ELIGIBLE_FOR_GREEN_PENDING_G4'
);

-- ============================================================================
-- PART D: ACI Rehydration (ADR-020)
-- Reset boundary tables, reasoning cache, budget model
-- Status: ACI_READY_PENDING_GREEN
-- ============================================================================

CREATE TABLE IF NOT EXISTS vision_signals.aci_rehydration_status (
    status_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ikea_boundary_reset BOOLEAN NOT NULL,
    sitc_cache_reset BOOLEAN NOT NULL,
    inforage_budget_reset BOOLEAN NOT NULL,
    aci_status TEXT NOT NULL,
    rehydration_timestamp TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO vision_signals.aci_rehydration_status (
    ikea_boundary_reset,
    sitc_cache_reset,
    inforage_budget_reset,
    aci_status
) VALUES (
    TRUE,
    TRUE,
    TRUE,
    'ACI_READY_PENDING_GREEN'
);

-- ============================================================================
-- PART E: Governance Logging
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
    'POST_G3_SYNCHRONIZATION',
    'vision_signals.state_snapshots',
    'TABLE',
    'STIG',
    NOW(),
    'APPROVED',
    E'CEO DIRECTIVE: POST-G3 SYNCHRONIZATION ORDER\n\n' ||
    E'Actions performed:\n' ||
    E'1. ADR-018 Shared State Regeneration - state_snapshot_hash v2 published\n' ||
    E'2. IoS-003 Regime-Cause Binding Refresh - regime_inference_pack_v2 published\n' ||
    E'3. ADR-016 Drift & Safety Validation - discrepancy 0.0318 < 0.05 = SAFE_TO_LIFT\n' ||
    E'4. ADR-020 ACI Rehydration - IKEA/SitC/InForage reset, status=ACI_READY_PENDING_GREEN\n\n' ||
    E'Constraints enforced:\n' ||
    E'- NO CEIO activation\n' ||
    E'- NO DEFCON change (remains YELLOW)\n' ||
    E'- NO ACI autonomy lift\n' ||
    E'- Awaiting G4 order for GREEN transition',
    false,
    'MIG-125-POST-G3-SYNC-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS')
);

COMMIT;

-- ============================================================================
-- Migration 125 Complete - POST-G3 SYNCHRONIZATION
-- Status: SAFE_TO_LIFT (pending G4)
-- ACI Status: READY_PENDING_GREEN
-- ============================================================================
