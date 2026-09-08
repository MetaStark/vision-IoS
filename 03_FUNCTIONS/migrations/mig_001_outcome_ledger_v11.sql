-- Migration 001: Create outcome_ledger V1.1 table
-- CEO Directive: Phase 2 Preparation & Hypothesis Swarm V1.1
-- Date: 2026-01-28
-- Author: STIG
-- Status: DESIGN ONLY - No prod deployment until Gate 2 signed
-- Dependency: Migration 000 (trigger_events) must be applied first

-- =============================================================================
-- OUTCOME LEDGER V1.1
-- Purpose: Record experiment outcomes with full traceability
-- V1.1 Upgrades:
--   - 1:1 trigger traceability via trigger_event_id
--   - PnL realism via gross/net split
--   - Dynamic risk normalization via ATR multiples
--   - Context versioning with model versions in hash
-- =============================================================================

CREATE TABLE fhq_learning.outcome_ledger (
    -- Primary Key
    outcome_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign Keys
    experiment_id UUID NOT NULL REFERENCES fhq_learning.experiment_registry(experiment_id),

    -- V1.1: 1:1 TRACEABILITY
    trigger_event_id UUID NOT NULL REFERENCES fhq_learning.trigger_events(trigger_event_id),

    -- Binary Outcome
    result_bool BOOLEAN NOT NULL,

    -- V1.1: PnL REALISM
    pnl_gross_simulated NUMERIC(18,6),  -- Pure price move
    pnl_net_est NUMERIC(18,6),          -- Gross minus spread/fees/slippage proxy

    -- V1.1: CONTEXT VERSIONING
    context_snapshot_hash TEXT NOT NULL,  -- SHA256 includes model versions
    context_details JSONB NOT NULL,       -- Raw snapshot with versions

    -- Excursion Metrics (pattern from fhq_canonical.canonical_outcomes)
    mfe NUMERIC(18,6),  -- Max Favorable Excursion (absolute)
    mae NUMERIC(18,6),  -- Max Adverse Excursion (absolute)

    -- V1.1: ATR MULTIPLES
    mfe_atr_multiple NUMERIC(18,6),  -- MFE / ATR at entry
    mae_atr_multiple NUMERIC(18,6),  -- MAE / ATR at entry

    -- Time Dimension
    time_to_outcome INTERVAL,

    -- Audit Fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'STIG',
    evidence_hash TEXT,

    -- V1.1: 1:1 ENFORCEMENT
    CONSTRAINT uq_experiment_trigger UNIQUE (experiment_id, trigger_event_id)
);

-- =============================================================================
-- INDICES
-- =============================================================================

-- Experiment lookups (primary aggregation path)
CREATE INDEX idx_outcome_ledger_experiment ON fhq_learning.outcome_ledger(experiment_id);

-- Trigger lookups (1:1 join path)
CREATE INDEX idx_outcome_ledger_trigger ON fhq_learning.outcome_ledger(trigger_event_id);

-- Context hash lookups (causal attribution queries)
CREATE INDEX idx_outcome_ledger_context_hash ON fhq_learning.outcome_ledger(context_snapshot_hash);

-- Result filtering (win/loss aggregations)
CREATE INDEX idx_outcome_ledger_result ON fhq_learning.outcome_ledger(result_bool);

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE fhq_learning.outcome_ledger IS 'Outcome ledger V1.1 for Phase 2 Hypothesis Swarm. Records experiment outcomes with 1:1 trigger traceability, PnL split, and ATR-normalized excursions.';

COMMENT ON COLUMN fhq_learning.outcome_ledger.outcome_id IS 'Primary key - unique outcome identifier';
COMMENT ON COLUMN fhq_learning.outcome_ledger.experiment_id IS 'FK to experiment_registry';
COMMENT ON COLUMN fhq_learning.outcome_ledger.trigger_event_id IS 'FK to trigger_events - 1:1 traceability (V1.1)';
COMMENT ON COLUMN fhq_learning.outcome_ledger.result_bool IS 'Binary outcome: TRUE=hypothesis confirmed, FALSE=falsified';
COMMENT ON COLUMN fhq_learning.outcome_ledger.pnl_gross_simulated IS 'Gross P&L from pure price movement (V1.1)';
COMMENT ON COLUMN fhq_learning.outcome_ledger.pnl_net_est IS 'Net P&L estimate after spread/fees/slippage proxy (V1.1)';
COMMENT ON COLUMN fhq_learning.outcome_ledger.context_snapshot_hash IS 'SHA256 hash of context including model versions (V1.1)';
COMMENT ON COLUMN fhq_learning.outcome_ledger.context_details IS 'Full context JSONB with regime, vol_state, macro_state, model versions';
COMMENT ON COLUMN fhq_learning.outcome_ledger.mfe IS 'Max Favorable Excursion (absolute value)';
COMMENT ON COLUMN fhq_learning.outcome_ledger.mae IS 'Max Adverse Excursion (absolute value)';
COMMENT ON COLUMN fhq_learning.outcome_ledger.mfe_atr_multiple IS 'MFE normalized by ATR at entry (V1.1)';
COMMENT ON COLUMN fhq_learning.outcome_ledger.mae_atr_multiple IS 'MAE normalized by ATR at entry (V1.1)';
COMMENT ON COLUMN fhq_learning.outcome_ledger.time_to_outcome IS 'Duration from trigger to outcome resolution';
COMMENT ON COLUMN fhq_learning.outcome_ledger.evidence_hash IS 'Evidence artifact hash for court-proof traceability';

-- =============================================================================
-- CONTEXT SNAPSHOT STRUCTURE V1.1 (JSONB)
-- =============================================================================
-- {
--   "regime": "STRONG_BULL",
--   "regime_model_version": "sovereign_v4_ddatp_1.2",
--   "vol_state": "LOW_VOL_SQUEEZE",
--   "vol_model_version": "ios017_kc_bb_1.0",
--   "macro_state": "RISK_ON",
--   "macro_model_version": "g3_synthesis_2.1",
--   "defcon_level": 3,
--   "capture_timestamp": "2026-01-28T21:00:00Z",
--   "data_sources": {
--     "regime_source": "fhq_perception.sovereign_regime_state_v4",
--     "vol_source": "fhq_indicators.volatility",
--     "macro_source": "fhq_governance.g3_macro_snapshot"
--   }
-- }
--
-- HASH COMPUTATION RULE:
-- canonical_keys = {
--     "regime": value,
--     "regime_model_version": value,
--     "vol_state": value,
--     "vol_model_version": value,
--     "macro_state": value,
--     "macro_model_version": value or "NA"
-- }
-- hash = SHA256(json.dumps(canonical_keys, sort_keys=True))
-- =============================================================================
