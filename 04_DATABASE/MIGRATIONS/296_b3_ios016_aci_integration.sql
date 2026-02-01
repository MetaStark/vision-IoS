-- Migration 296: B3 IoS-016 ACI Integration
-- Authority: CEO-DIR-2026-064
-- Gate: ADR-004 APPROVED
-- Executed by: STIG
-- Date: 2026-01-17

BEGIN;

-- C3.3.1: Event Learning Tags
CREATE TABLE IF NOT EXISTS vision_signals.event_learning_tags (
    tag_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL,
    event_name TEXT,
    event_type TEXT,
    scheduled_time TIMESTAMPTZ,
    actual_release_time TIMESTAMPTZ,

    -- Consensus data (from B1)
    consensus_tier VARCHAR(1),
    consensus_value NUMERIC,
    consensus_source TEXT,
    consensus_captured_at TIMESTAMPTZ,

    -- FjordHQ internal expectation (Tier C)
    fjordhq_expectation NUMERIC,
    fjordhq_confidence NUMERIC,
    fjordhq_source_model TEXT,

    -- Outcome
    actual_value NUMERIC,
    outcome_captured_at TIMESTAMPTZ,

    -- Surprise calculations
    surprise_vs_consensus NUMERIC,
    surprise_vs_fjordhq NUMERIC,
    surprise_direction VARCHAR(10),

    -- Regime context
    regime_before_event TEXT,
    regime_after_event TEXT,
    regime_change_detected BOOLEAN DEFAULT FALSE,

    -- Learning annotation
    learning_annotation JSONB,
    epistemic_lesson_id UUID,

    -- ACI delivery
    delivered_to_aci_at TIMESTAMPTZ,
    aci_acknowledgment_ref TEXT,

    -- Governance
    evidence_ref TEXT,
    hash_chain_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_elt_event_id ON vision_signals.event_learning_tags(event_id);
CREATE INDEX IF NOT EXISTS idx_elt_delivered ON vision_signals.event_learning_tags(delivered_to_aci_at);
CREATE INDEX IF NOT EXISTS idx_elt_consensus_tier ON vision_signals.event_learning_tags(consensus_tier);

-- C3.3.2: Learning Tag Generation Function
CREATE OR REPLACE FUNCTION vision_signals.fn_generate_event_learning_tag(
    p_event_id UUID,
    p_actual_value NUMERIC,
    p_outcome_captured_at TIMESTAMPTZ DEFAULT NOW()
) RETURNS UUID AS $$
DECLARE
    v_tag_id UUID;
    v_event RECORD;
    v_consensus RECORD;
    v_surprise_vs_consensus NUMERIC;
BEGIN
    -- Get event details
    SELECT * INTO v_event
    FROM fhq_calendar.calendar_events
    WHERE event_id = p_event_id;

    -- Get consensus (from B1 hierarchy view)
    SELECT * INTO v_consensus
    FROM fhq_calendar.v_consensus_hierarchy
    WHERE event_id = p_event_id;

    -- Calculate surprises
    IF v_consensus.consensus_value IS NOT NULL THEN
        v_surprise_vs_consensus := p_actual_value - v_consensus.consensus_value;
    END IF;

    -- Insert learning tag
    INSERT INTO vision_signals.event_learning_tags (
        event_id,
        event_name,
        event_type,
        scheduled_time,
        consensus_tier,
        consensus_value,
        consensus_source,
        consensus_captured_at,
        actual_value,
        outcome_captured_at,
        surprise_vs_consensus,
        surprise_direction,
        learning_annotation
    ) VALUES (
        p_event_id,
        v_event.event_type_code,
        v_event.event_type_code,
        v_event.event_timestamp,
        v_consensus.resolved_tier,
        v_consensus.consensus_value,
        v_consensus.consensus_source,
        v_consensus.consensus_captured_at,
        p_actual_value,
        p_outcome_captured_at,
        v_surprise_vs_consensus,
        CASE
            WHEN v_surprise_vs_consensus > 0 THEN 'POSITIVE'
            WHEN v_surprise_vs_consensus < 0 THEN 'NEGATIVE'
            ELSE 'NEUTRAL'
        END,
        jsonb_build_object(
            'event_type', v_event.event_type_code,
            'consensus_available', v_consensus.resolved_tier IS NOT NULL,
            'surprise_magnitude', ABS(v_surprise_vs_consensus),
            'generated_at', NOW()
        )
    ) RETURNING tag_id INTO v_tag_id;

    RETURN v_tag_id;
END;
$$ LANGUAGE plpgsql;

-- C3.3.3: Knowledge Delivery Status View
CREATE OR REPLACE VIEW vision_signals.v_event_knowledge_delivery_status AS
SELECT
    tag_id,
    event_id,
    event_name,
    scheduled_time,
    consensus_tier,
    CASE WHEN consensus_tier IS NULL THEN 'CONSENSUS_UNAVAILABLE' ELSE 'AVAILABLE' END AS q1_status,
    surprise_vs_consensus,
    delivered_to_aci_at,
    CASE WHEN delivered_to_aci_at IS NOT NULL THEN 'DELIVERED' ELSE 'PENDING' END AS delivery_status,
    created_at
FROM vision_signals.event_learning_tags
ORDER BY created_at DESC;

-- Log migration to governance_actions_log
INSERT INTO fhq_governance.governance_actions_log (
    action_type, action_target, action_target_type, initiated_by, initiated_at, decision, decision_rationale, metadata, agent_id
) VALUES (
    'MIGRATION', '296_b3_ios016_aci', 'DATABASE_SCHEMA', 'STIG', NOW(), 'EXECUTED',
    'CEO-DIR-2026-064 B3 - IoS-016 ACI Integration',
    '{"directive": "CEO-DIR-2026-064", "gap": "B3", "tables_created": ["event_learning_tags"], "views_created": ["v_event_knowledge_delivery_status"], "functions_created": ["fn_generate_event_learning_tag"]}'::jsonb,
    'STIG'
);

COMMIT;
