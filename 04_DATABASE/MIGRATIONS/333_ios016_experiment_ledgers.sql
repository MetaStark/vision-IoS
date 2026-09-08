-- ============================================================================
-- Migration: 333_ios016_experiment_ledgers.sql
-- Directive: CEO-DIR-2026-023 Order 5
-- Purpose: Create IoS-016 experiment ledger infrastructure
-- Date: 2026-01-23
-- Author: STIG (EC-003)
-- ============================================================================

-- ============================================================================
-- Hypothesis Ledger (pre-commit before event)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_learning.hypothesis_ledger (
    hypothesis_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES fhq_calendar.calendar_events(event_id),
    signal_plan_id UUID,  -- Optional link to weighted_signal_plan
    hypothesis_text TEXT NOT NULL,
    expected_direction TEXT CHECK (expected_direction IN ('BULLISH', 'BEARISH', 'NEUTRAL')),
    expected_magnitude TEXT CHECK (expected_magnitude IN ('HIGH', 'MEDIUM', 'LOW')),
    confidence_pre_event NUMERIC CHECK (confidence_pre_event BETWEEN 0 AND 1),
    rationale TEXT,
    asset_symbols TEXT[],  -- Assets affected by this hypothesis
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'STIG',
    created_before_event BOOLEAN DEFAULT TRUE,
    immutable_after TIMESTAMPTZ,  -- event_time, after which no edits allowed
    evidence_hash TEXT,
    CONSTRAINT hypothesis_pre_commit CHECK (
        created_before_event = TRUE OR immutable_after IS NULL
    )
);

CREATE INDEX idx_hypothesis_ledger_event ON fhq_learning.hypothesis_ledger(event_id);
CREATE INDEX idx_hypothesis_ledger_created ON fhq_learning.hypothesis_ledger(created_at DESC);
CREATE INDEX idx_hypothesis_ledger_immutable ON fhq_learning.hypothesis_ledger(immutable_after);

COMMENT ON TABLE fhq_learning.hypothesis_ledger IS 'Pre-event hypothesis commitments for IoS-016 experiment loop';
COMMENT ON COLUMN fhq_learning.hypothesis_ledger.immutable_after IS 'Event timestamp - no edits allowed after this time';

-- Trigger to enforce immutability after event
CREATE OR REPLACE FUNCTION fhq_learning.enforce_hypothesis_immutability()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.immutable_after IS NOT NULL AND OLD.immutable_after < NOW() THEN
        RAISE EXCEPTION 'IMMUTABLE_VIOLATION: Hypothesis % is immutable after event time %',
            OLD.hypothesis_id, OLD.immutable_after;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER hypothesis_immutability_check
    BEFORE UPDATE ON fhq_learning.hypothesis_ledger
    FOR EACH ROW
    EXECUTE FUNCTION fhq_learning.enforce_hypothesis_immutability();

-- ============================================================================
-- Decision Experiment Ledger (bind decision to hypothesis)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_learning.decision_experiment_ledger (
    experiment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis_id UUID REFERENCES fhq_learning.hypothesis_ledger(hypothesis_id),
    decision_pack_id UUID REFERENCES fhq_learning.decision_packs(pack_id),
    decision_type TEXT NOT NULL CHECK (decision_type IN ('TRADE', 'NO_TRADE', 'WAIT')),
    no_trade_reason TEXT,  -- Required if decision_type = NO_TRADE
    trade_direction TEXT,  -- LONG, SHORT if TRADE
    position_size_usd NUMERIC,
    entry_price NUMERIC,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'STIG',
    evidence_hash TEXT,
    CONSTRAINT no_trade_requires_reason CHECK (
        decision_type != 'NO_TRADE' OR no_trade_reason IS NOT NULL
    )
);

CREATE INDEX idx_decision_experiment_hypothesis ON fhq_learning.decision_experiment_ledger(hypothesis_id);
CREATE INDEX idx_decision_experiment_pack ON fhq_learning.decision_experiment_ledger(decision_pack_id);
CREATE INDEX idx_decision_experiment_type ON fhq_learning.decision_experiment_ledger(decision_type);

COMMENT ON TABLE fhq_learning.decision_experiment_ledger IS 'Binds trading decisions to pre-event hypotheses';

-- ============================================================================
-- Expectation Outcome Ledger (record actual vs expected)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_learning.expectation_outcome_ledger (
    outcome_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis_id UUID REFERENCES fhq_learning.hypothesis_ledger(hypothesis_id),
    experiment_id UUID REFERENCES fhq_learning.decision_experiment_ledger(experiment_id),
    actual_direction TEXT CHECK (actual_direction IN ('BULLISH', 'BEARISH', 'NEUTRAL')),
    actual_magnitude TEXT CHECK (actual_magnitude IN ('HIGH', 'MEDIUM', 'LOW')),
    actual_value NUMERIC,  -- Actual data release value
    consensus_value NUMERIC,  -- Expected consensus
    surprise_pct NUMERIC,  -- (actual - consensus) / consensus * 100
    surprise_score NUMERIC,  -- Normalized: (actual - expected) / historical_std
    market_response TEXT CHECK (market_response IN ('OVER', 'UNDER', 'INLINE')),
    price_change_pct NUMERIC,  -- Price change T+0 to T+24h
    learning_verdict TEXT CHECK (learning_verdict IN ('VALIDATED', 'WEAKENED', 'FALSIFIED')),
    verdict_rationale TEXT,
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    recorded_by TEXT DEFAULT 'STIG',
    recorded_within_24h BOOLEAN,
    evaluation_hours NUMERIC,  -- Hours from event to outcome recording
    evidence_hash TEXT
);

CREATE INDEX idx_expectation_outcome_hypothesis ON fhq_learning.expectation_outcome_ledger(hypothesis_id);
CREATE INDEX idx_expectation_outcome_experiment ON fhq_learning.expectation_outcome_ledger(experiment_id);
CREATE INDEX idx_expectation_outcome_verdict ON fhq_learning.expectation_outcome_ledger(learning_verdict);
CREATE INDEX idx_expectation_outcome_recorded ON fhq_learning.expectation_outcome_ledger(recorded_at DESC);

COMMENT ON TABLE fhq_learning.expectation_outcome_ledger IS 'Records actual outcomes vs pre-event expectations';

-- ============================================================================
-- Experiment Summary View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_learning.v_experiment_summary AS
SELECT
    h.hypothesis_id,
    h.hypothesis_text,
    h.expected_direction,
    h.confidence_pre_event,
    h.created_at as hypothesis_created,
    h.immutable_after as event_time,
    d.decision_type,
    d.trade_direction,
    o.actual_direction,
    o.learning_verdict,
    o.evaluation_hours,
    o.recorded_within_24h,
    CASE
        WHEN o.outcome_id IS NULL AND h.immutable_after < NOW() - INTERVAL '24 hours' THEN 'OVERDUE'
        WHEN o.outcome_id IS NULL AND h.immutable_after < NOW() THEN 'PENDING'
        WHEN o.outcome_id IS NOT NULL THEN 'COMPLETE'
        ELSE 'UPCOMING'
    END as experiment_status
FROM fhq_learning.hypothesis_ledger h
LEFT JOIN fhq_learning.decision_experiment_ledger d ON h.hypothesis_id = d.hypothesis_id
LEFT JOIN fhq_learning.expectation_outcome_ledger o ON h.hypothesis_id = o.hypothesis_id
ORDER BY h.immutable_after DESC;

COMMENT ON VIEW fhq_learning.v_experiment_summary IS 'Unified view of IoS-016 experiment pipeline';

-- ============================================================================
-- Overdue Outcomes View (for alerting)
-- ============================================================================

CREATE OR REPLACE VIEW fhq_learning.v_overdue_outcomes AS
SELECT
    h.hypothesis_id,
    h.hypothesis_text,
    h.immutable_after as event_time,
    EXTRACT(EPOCH FROM NOW() - h.immutable_after) / 3600 as hours_overdue,
    ce.event_type_code
FROM fhq_learning.hypothesis_ledger h
LEFT JOIN fhq_learning.expectation_outcome_ledger o ON h.hypothesis_id = o.hypothesis_id
LEFT JOIN fhq_calendar.calendar_events ce ON h.event_id = ce.event_id
WHERE h.immutable_after < NOW() - INTERVAL '24 hours'
  AND o.outcome_id IS NULL
ORDER BY h.immutable_after ASC;

COMMENT ON VIEW fhq_learning.v_overdue_outcomes IS 'Hypotheses past T+24h without recorded outcomes';

-- ============================================================================
-- Upcoming Events Without Hypotheses View (for alerting)
-- ============================================================================

CREATE OR REPLACE VIEW fhq_learning.v_events_without_hypotheses AS
SELECT
    ce.event_id,
    ce.event_type_code,
    ce.event_timestamp,
    EXTRACT(EPOCH FROM ce.event_timestamp - NOW()) / 3600 as hours_until_event
FROM fhq_calendar.calendar_events ce
LEFT JOIN fhq_learning.hypothesis_ledger h ON ce.event_id = h.event_id
WHERE ce.event_timestamp > NOW()
  AND ce.event_timestamp < NOW() + INTERVAL '4 hours'
  AND h.hypothesis_id IS NULL
ORDER BY ce.event_timestamp ASC;

COMMENT ON VIEW fhq_learning.v_events_without_hypotheses IS 'Upcoming events within 4h without pre-committed hypotheses';

-- ============================================================================
-- Learning Metrics View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_learning.v_learning_metrics AS
SELECT
    COUNT(*) as total_hypotheses,
    COUNT(*) FILTER (WHERE o.outcome_id IS NOT NULL) as completed_experiments,
    COUNT(*) FILTER (WHERE o.learning_verdict = 'VALIDATED') as validated_count,
    COUNT(*) FILTER (WHERE o.learning_verdict = 'WEAKENED') as weakened_count,
    COUNT(*) FILTER (WHERE o.learning_verdict = 'FALSIFIED') as falsified_count,
    COUNT(*) FILTER (WHERE o.recorded_within_24h = TRUE) as recorded_on_time,
    AVG(o.evaluation_hours) FILTER (WHERE o.evaluation_hours IS NOT NULL) as avg_evaluation_hours,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE o.learning_verdict = 'VALIDATED') /
        NULLIF(COUNT(*) FILTER (WHERE o.outcome_id IS NOT NULL), 0),
        2
    ) as validation_rate_pct
FROM fhq_learning.hypothesis_ledger h
LEFT JOIN fhq_learning.expectation_outcome_ledger o ON h.hypothesis_id = o.hypothesis_id
WHERE h.created_at > NOW() - INTERVAL '30 days';

COMMENT ON VIEW fhq_learning.v_learning_metrics IS 'Aggregate learning metrics for last 30 days';

-- ============================================================================
-- Migration complete
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 333_ios016_experiment_ledgers.sql completed successfully';
    RAISE NOTICE 'Created tables: hypothesis_ledger, decision_experiment_ledger, expectation_outcome_ledger';
    RAISE NOTICE 'Created views: v_experiment_summary, v_overdue_outcomes, v_events_without_hypotheses, v_learning_metrics';
END $$;
