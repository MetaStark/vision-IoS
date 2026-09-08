-- ============================================================
-- CEO-DIR-2026-UNIFIED-DECISION-001 — SHADOW OBSERVATION LAYER
-- ============================================================
-- Migration: 207_unified_decision_shadow_observation.sql
-- Authority: CEO (Constitutional Directive)
-- Technical Lead: STIG (CTO)
-- Governance: VEGA
-- ADR Compliance: ADR-002, ADR-013, ADR-014
-- ============================================================
-- PURPOSE: Implement Unified Decision + Shadow Observation architecture
--          v4 (STRESS) becomes One-True-Source for decisions
--          Global BULL degraded to observation layer (IoS-010 Shadow)
-- ============================================================
-- CONSTITUTIONAL PROTECTION:
--   - Eliminates Split-Brain governance risk (Class A violation)
--   - Enables Replay Mode per ADR-011
--   - VEGA can attest 100% model-derived decisions
-- ============================================================

BEGIN;

-- ============================================================
-- SECTION 1: SHADOW OBSERVATION LEDGER
-- Stores discarded signals alongside active decisions for training
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_research.shadow_observation_ledger (
    observation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Decision Context
    decision_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decision_date DATE NOT NULL DEFAULT CURRENT_DATE,
    asset_id TEXT NOT NULL,

    -- Active Decision (v4 Source-of-Truth)
    active_regime TEXT NOT NULL,
    active_confidence NUMERIC(8,6) NOT NULL,
    active_source TEXT NOT NULL DEFAULT 'sovereign_regime_state_v4',
    active_model_version TEXT NOT NULL,

    -- Shadow Observation (Discarded Signal)
    shadow_regime TEXT,
    shadow_confidence NUMERIC(8,6),
    shadow_source TEXT DEFAULT 'fhq_meta.regime_state',
    shadow_reason_discarded TEXT DEFAULT 'ADR-013_ONE_SOURCE_OF_TRUTH',

    -- State Probabilities (full HMM output)
    state_probabilities JSONB,

    -- Decision Hash (for ADR-011 Replay)
    decision_hash TEXT NOT NULL,

    -- Outcome Tracking (filled by IoS-010)
    outcome_realized BOOLEAN DEFAULT FALSE,
    outcome_date DATE,
    outcome_return NUMERIC(10,6),
    opportunity_cost NUMERIC(10,6),

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT chk_active_regime_valid CHECK (
        active_regime IN ('BULL', 'BEAR', 'NEUTRAL', 'STRESS')
    ),
    CONSTRAINT chk_shadow_regime_valid CHECK (
        shadow_regime IS NULL OR shadow_regime IN ('BULL', 'BEAR', 'NEUTRAL', 'STRESS')
    )
);

-- Index for time-series queries
CREATE INDEX IF NOT EXISTS idx_shadow_obs_date
    ON fhq_research.shadow_observation_ledger(decision_date DESC);

-- Index for asset analysis
CREATE INDEX IF NOT EXISTS idx_shadow_obs_asset
    ON fhq_research.shadow_observation_ledger(asset_id, decision_date DESC);

-- Index for opportunity cost analysis
CREATE INDEX IF NOT EXISTS idx_shadow_obs_opportunity
    ON fhq_research.shadow_observation_ledger(outcome_realized, opportunity_cost)
    WHERE opportunity_cost IS NOT NULL;

COMMENT ON TABLE fhq_research.shadow_observation_ledger IS
'CEO-DIR-2026-UNIFIED-DECISION-001: Shadow Observation Layer.
Stores v4 active decisions alongside discarded signals (e.g., Global BULL).
Enables MoE training data collection and opportunity cost tracking.
STIG 2026-01-06';

-- ============================================================
-- SECTION 2: SAFE STALENESS FUNCTION
-- Guarantees staleness >= 0 (handles FX close_time semantics)
-- ============================================================

CREATE OR REPLACE FUNCTION fhq_market.safe_staleness_hours(
    bar_timestamp TIMESTAMP,
    reference_time TIMESTAMP DEFAULT NOW()
)
RETURNS NUMERIC AS $$
BEGIN
    -- STIG Guardrail: Staleness is always >= 0 by construction
    -- If bar_timestamp is in future (close_time semantics), staleness = 0
    RETURN GREATEST(
        0,
        EXTRACT(EPOCH FROM (reference_time - bar_timestamp)) / 3600.0
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fhq_market.safe_staleness_hours IS
'CEO-DIR-2026-TIME-TRUTH-VERIFICATION-001: Safe staleness calculation.
Guarantees staleness >= 0 by construction.
Handles FX close_time semantics where bar timestamp may be in future.
STIG 2026-01-06';

-- ============================================================
-- SECTION 3: CDMO AIRLOCK PROTOCOL
-- Prevents Global BULL from leaking into decision logic
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_research.regime_airlock (
    airlock_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Quarantined Signal
    signal_source TEXT NOT NULL,
    signal_regime TEXT NOT NULL,
    signal_confidence NUMERIC(8,6),
    signal_timestamp TIMESTAMPTZ NOT NULL,

    -- Airlock Status
    airlock_status TEXT NOT NULL DEFAULT 'QUARANTINED',
    airlock_reason TEXT NOT NULL,

    -- Release Conditions (for future MoE integration)
    release_requires_adr TEXT,
    release_approved_by TEXT,
    release_approved_at TIMESTAMPTZ,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT chk_airlock_status CHECK (
        airlock_status IN ('QUARANTINED', 'RELEASED', 'EXPIRED', 'REJECTED')
    )
);

COMMENT ON TABLE fhq_research.regime_airlock IS
'CEO-DIR-2026-UNIFIED-DECISION-001: CDMO Airlock Protocol.
Quarantines non-authoritative regime signals (e.g., Global BULL).
Prevents contamination of IoS-004 decision logic.
Release requires ADR-004 G4 approval.
STIG 2026-01-06';

-- Quarantine current Global BULL signal
INSERT INTO fhq_research.regime_airlock (
    signal_source,
    signal_regime,
    signal_confidence,
    signal_timestamp,
    airlock_status,
    airlock_reason,
    release_requires_adr
)
SELECT
    'fhq_meta.regime_state',
    current_regime,
    regime_confidence,
    last_updated_at,
    'QUARANTINED',
    'CEO-DIR-2026-UNIFIED-DECISION-001: Degraded to observation layer. v4 is now One-True-Source.',
    'ADR-004 G4'
FROM fhq_meta.regime_state
ON CONFLICT DO NOTHING;

-- ============================================================
-- SECTION 4: SYNC GLOBAL REGIME FROM V4 SOURCE
-- One-time sync to eliminate split-brain
-- Note: v4 uses (BULL, BEAR, NEUTRAL, STRESS)
--       v2/global uses (BULL, BEAR, SIDEWAYS, CRISIS, UNKNOWN)
--       Mapping: NEUTRAL -> SIDEWAYS, STRESS -> CRISIS
-- ============================================================

-- Get latest BTC-USD v4 regime and update global (with v4->v2 mapping)
UPDATE fhq_meta.regime_state
SET
    current_regime = (
        SELECT CASE sovereign_regime
            WHEN 'NEUTRAL' THEN 'SIDEWAYS'
            WHEN 'STRESS' THEN 'CRISIS'
            ELSE sovereign_regime
        END
        FROM fhq_perception.sovereign_regime_state_v4
        WHERE asset_id = 'BTC-USD'
        ORDER BY timestamp DESC
        LIMIT 1
    ),
    regime_confidence = (
        SELECT (state_probabilities->>sovereign_regime)::numeric
        FROM fhq_perception.sovereign_regime_state_v4
        WHERE asset_id = 'BTC-USD'
        ORDER BY timestamp DESC
        LIMIT 1
    ),
    last_updated_at = NOW(),
    updated_by = 'STIG.UNIFIED_v4'
WHERE state_id IS NOT NULL;

-- ============================================================
-- SECTION 5: GOVERNANCE ATTESTATION
-- ============================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'CONSTITUTIONAL_DIRECTIVE',
    'CEO-DIR-2026-UNIFIED-DECISION-001',
    'DIRECTIVE',
    'CEO',
    'APPROVED',
    'Unified Decision + Shadow Observation architecture. v4 is One-True-Source. Global BULL degraded to IoS-010 Shadow observation layer. Class A risk mitigated.',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-UNIFIED-DECISION-001',
        'active_source', 'fhq_perception.sovereign_regime_state_v4',
        'shadow_source', 'fhq_meta.regime_state (quarantined)',
        'constitutional_protection', ARRAY['ADR-002', 'ADR-011', 'ADR-013'],
        'split_brain_eliminated', true
    )
);

COMMIT;

-- ============================================================
-- VERIFICATION QUERIES
-- ============================================================

-- Verify global regime synced from v4
SELECT
    'GLOBAL_REGIME' as check_type,
    current_regime,
    regime_confidence,
    updated_by,
    last_updated_at
FROM fhq_meta.regime_state;

-- Verify airlock contains quarantined signal
SELECT
    'AIRLOCK_STATUS' as check_type,
    signal_source,
    signal_regime,
    airlock_status,
    airlock_reason
FROM fhq_research.regime_airlock
WHERE signal_source = 'fhq_meta.regime_state';
