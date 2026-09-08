-- Migration 000: Create trigger_events table
-- CEO Directive: Phase 2 Preparation & Hypothesis Swarm V1.1
-- Date: 2026-01-28
-- Author: STIG
-- Status: DESIGN ONLY - No prod deployment until Gate 2 signed

-- =============================================================================
-- TRIGGER EVENTS TABLE
-- Purpose: Links experiments to outcomes with 1:1 traceability
-- Rationale: IoS-013 signal tables are trade-oriented, not experiment-oriented
--            3000-test scaling requires independent trigger lineage
--            Enables cross-experiment trigger reuse analysis
-- =============================================================================

CREATE TABLE fhq_learning.trigger_events (
    -- Primary Key
    trigger_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Experiment Link
    experiment_id UUID NOT NULL REFERENCES fhq_learning.experiment_registry(experiment_id),

    -- Asset & Timing
    asset_id TEXT NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,

    -- Trigger Indicator Values at Entry
    trigger_indicators JSONB NOT NULL,
    -- Expected structure:
    -- {
    --   "bbw": 0.042,
    --   "bbw_percentile": 8,
    --   "rsi_14": 72.5,
    --   "bb_position": "ABOVE_UPPER",
    --   "atr_14": 2.45,
    --   "entry_price": 185.50
    -- }

    -- Entry Price Reference
    entry_price NUMERIC(18,6) NOT NULL,
    price_source_table TEXT NOT NULL DEFAULT 'fhq_data.price_series',
    price_source_row_id UUID,

    -- Context Snapshot at Entry
    context_snapshot_hash TEXT NOT NULL,
    context_details JSONB NOT NULL,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'STIG',
    evidence_hash TEXT,

    -- Constraints: One trigger per experiment+asset+time
    CONSTRAINT uq_trigger_experiment_asset_time
        UNIQUE (experiment_id, asset_id, event_timestamp)
);

-- =============================================================================
-- INDICES
-- =============================================================================

-- Experiment lookups (primary join path)
CREATE INDEX idx_trigger_events_experiment ON fhq_learning.trigger_events(experiment_id);

-- Asset-based queries (cross-experiment analysis)
CREATE INDEX idx_trigger_events_asset ON fhq_learning.trigger_events(asset_id);

-- Time-based queries (temporal analysis)
CREATE INDEX idx_trigger_events_timestamp ON fhq_learning.trigger_events(event_timestamp);

-- Context hash lookups (causal attribution)
CREATE INDEX idx_trigger_events_context_hash ON fhq_learning.trigger_events(context_snapshot_hash);

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE fhq_learning.trigger_events IS 'Trigger event primitive for Phase 2 Hypothesis Swarm. Links experiments to outcomes with 1:1 traceability. V1.1';

COMMENT ON COLUMN fhq_learning.trigger_events.trigger_event_id IS 'Primary key - unique trigger event identifier';
COMMENT ON COLUMN fhq_learning.trigger_events.experiment_id IS 'FK to experiment_registry - which experiment triggered this event';
COMMENT ON COLUMN fhq_learning.trigger_events.asset_id IS 'Asset identifier (e.g., SPY, BTC-USD)';
COMMENT ON COLUMN fhq_learning.trigger_events.event_timestamp IS 'When the trigger condition fired';
COMMENT ON COLUMN fhq_learning.trigger_events.trigger_indicators IS 'JSONB snapshot of indicator values at trigger (BBW, RSI, ATR, etc.)';
COMMENT ON COLUMN fhq_learning.trigger_events.entry_price IS 'Price at trigger event for PnL calculation';
COMMENT ON COLUMN fhq_learning.trigger_events.price_source_table IS 'Source table for price data traceability';
COMMENT ON COLUMN fhq_learning.trigger_events.price_source_row_id IS 'Optional: specific row ID in price source for audit';
COMMENT ON COLUMN fhq_learning.trigger_events.context_snapshot_hash IS 'SHA256 hash of context including model versions';
COMMENT ON COLUMN fhq_learning.trigger_events.context_details IS 'Full context snapshot with regime, vol_state, macro_state, model versions';
COMMENT ON COLUMN fhq_learning.trigger_events.evidence_hash IS 'Evidence artifact hash for court-proof traceability';

-- =============================================================================
-- LINEAGE DOCUMENTATION
-- =============================================================================
-- [Indicator Data] -> [Trigger Detection Engine] -> trigger_events row
--                                                        |
--                                                        v
--                                               [Outcome Tracking]
--                                                        |
--                                                        v
--                                               outcome_ledger row
--
-- Generation Point: Trigger events are created when:
-- 1. Indicator condition fires (BBW < 10th percentile, RSI > 70, etc.)
-- 2. Regime filter passes (if applicable)
-- 3. Asset is in experiment universe
--
-- One trigger = One outcome row (enforced by UNIQUE constraint)
-- =============================================================================
