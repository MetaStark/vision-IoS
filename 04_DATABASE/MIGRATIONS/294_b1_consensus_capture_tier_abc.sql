-- Migration 294: B1 Consensus Capture Tier A/B/C
-- Authority: CEO-DIR-2026-064
-- Gate: ADR-004 APPROVED
-- Executed by: STIG
-- Date: 2026-01-17

BEGIN;

-- C1.3.1: Consensus Tier Configuration
CREATE TABLE IF NOT EXISTS fhq_calendar.consensus_tier_config (
    tier_id VARCHAR(1) PRIMARY KEY,
    tier_name TEXT NOT NULL,
    tier_priority INTEGER NOT NULL,
    description TEXT,
    capture_window_hours INTEGER DEFAULT 24,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_tier CHECK (tier_id IN ('A', 'B', 'C'))
);

INSERT INTO fhq_calendar.consensus_tier_config (tier_id, tier_name, tier_priority, description) VALUES
('A', 'Market-Implied', 1, 'OIS curves, futures, swaps, breakevens'),
('B', 'Survey Consensus', 2, 'Bloomberg/Reuters poll median'),
('C', 'House/Model', 3, 'FINN/UMA/ACI internal forecasts')
ON CONFLICT (tier_id) DO NOTHING;

-- C1.3.2: Market-Implied Consensus (Tier A)
CREATE TABLE IF NOT EXISTS fhq_calendar.market_implied_consensus (
    consensus_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES fhq_calendar.calendar_events(event_id),
    tier VARCHAR(1) DEFAULT 'A' CHECK (tier = 'A'),
    instrument_type TEXT NOT NULL,
    instrument_id TEXT,
    implied_value NUMERIC NOT NULL,
    implied_unit TEXT,
    captured_at TIMESTAMPTZ NOT NULL,
    data_source TEXT NOT NULL,
    source_timestamp TIMESTAMPTZ,
    hash_chain_id UUID,
    evidence_ref TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mic_event_id ON fhq_calendar.market_implied_consensus(event_id);
CREATE INDEX IF NOT EXISTS idx_mic_captured_at ON fhq_calendar.market_implied_consensus(captured_at);

-- C1.3.3: Survey Consensus (Tier B)
CREATE TABLE IF NOT EXISTS fhq_calendar.survey_consensus (
    consensus_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES fhq_calendar.calendar_events(event_id),
    tier VARCHAR(1) DEFAULT 'B' CHECK (tier = 'B'),
    survey_source TEXT NOT NULL,
    consensus_median NUMERIC NOT NULL,
    consensus_mean NUMERIC,
    consensus_high NUMERIC,
    consensus_low NUMERIC,
    respondent_count INTEGER,
    captured_at TIMESTAMPTZ NOT NULL,
    source_timestamp TIMESTAMPTZ,
    hash_chain_id UUID,
    evidence_ref TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sc_event_id ON fhq_calendar.survey_consensus(event_id);
CREATE INDEX IF NOT EXISTS idx_sc_captured_at ON fhq_calendar.survey_consensus(captured_at);

-- C1.3.4: Consensus Hierarchy Resolution View
CREATE OR REPLACE VIEW fhq_calendar.v_consensus_hierarchy AS
SELECT
    e.event_id,
    e.event_type_code,
    e.event_timestamp,
    CASE
        WHEN mic.consensus_id IS NOT NULL THEN 'A'
        WHEN sc.consensus_id IS NOT NULL THEN 'B'
        ELSE NULL
    END AS resolved_tier,
    COALESCE(mic.implied_value, sc.consensus_median) AS consensus_value,
    COALESCE(mic.captured_at, sc.captured_at) AS consensus_captured_at,
    COALESCE(mic.data_source, sc.survey_source) AS consensus_source,
    COALESCE(mic.evidence_ref, sc.evidence_ref) AS evidence_ref,
    CASE
        WHEN mic.consensus_id IS NULL AND sc.consensus_id IS NULL THEN TRUE
        ELSE FALSE
    END AS determinism_failure
FROM fhq_calendar.calendar_events e
LEFT JOIN LATERAL (
    SELECT * FROM fhq_calendar.market_implied_consensus
    WHERE event_id = e.event_id
    ORDER BY captured_at DESC LIMIT 1
) mic ON TRUE
LEFT JOIN LATERAL (
    SELECT * FROM fhq_calendar.survey_consensus
    WHERE event_id = e.event_id
    ORDER BY captured_at DESC LIMIT 1
) sc ON TRUE;

-- C1.3.5: Surprise Calculation Function
CREATE OR REPLACE FUNCTION fhq_calendar.fn_compute_surprise(
    p_event_id UUID,
    p_actual_value NUMERIC
) RETURNS TABLE (
    surprise_value NUMERIC,
    surprise_pct NUMERIC,
    consensus_tier VARCHAR(1),
    consensus_value NUMERIC,
    determinism_status TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        CASE WHEN ch.determinism_failure THEN NULL
             ELSE p_actual_value - ch.consensus_value
        END AS surprise_value,
        CASE WHEN ch.determinism_failure OR ch.consensus_value = 0 THEN NULL
             ELSE ((p_actual_value - ch.consensus_value) / ABS(ch.consensus_value)) * 100
        END AS surprise_pct,
        ch.resolved_tier AS consensus_tier,
        ch.consensus_value,
        CASE WHEN ch.determinism_failure THEN 'CONSENSUS_UNAVAILABLE'
             ELSE 'DETERMINISTIC'
        END AS determinism_status
    FROM fhq_calendar.v_consensus_hierarchy ch
    WHERE ch.event_id = p_event_id;
END;
$$ LANGUAGE plpgsql STABLE;

-- Log migration to governance_actions_log
INSERT INTO fhq_governance.governance_actions_log (
    action_type, action_target, action_target_type, initiated_by, initiated_at, decision, decision_rationale, metadata, agent_id
) VALUES (
    'MIGRATION', '294_b1_consensus_capture', 'DATABASE_SCHEMA', 'STIG', NOW(), 'EXECUTED',
    'CEO-DIR-2026-064 B1 - Consensus Capture Tier A/B/C',
    '{"directive": "CEO-DIR-2026-064", "gap": "B1", "tables_created": ["consensus_tier_config", "market_implied_consensus", "survey_consensus"], "views_created": ["v_consensus_hierarchy"], "functions_created": ["fn_compute_surprise"]}'::jsonb,
    'STIG'
);

COMMIT;
