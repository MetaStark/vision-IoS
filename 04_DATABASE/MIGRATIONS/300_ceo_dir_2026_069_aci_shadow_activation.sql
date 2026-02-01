-- ============================================================================
-- Migration 300: CEO-DIR-2026-069 ACI Triangle Shadow Activation
-- ============================================================================
-- PURPOSE: Enable ACI Triangle Shadow Activation for UMA Signal Proposal Mode
--
-- SCOPE:
--   - UMA: Signal Proposal Authority (SHADOW mode only)
--   - SitC: Cognitive Planner (SHADOW mode)
--   - InForage: Retrieval Specialist (SHADOW mode)
--   - IKEA: Knowledge Boundary Enforcer (ACTIVE - override authority)
--
-- CONSTRAINT: Reference Epoch 001 lock remains intact
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: Create Execution Gates for ACI Shadow Mode
-- ============================================================================

-- Create execution_gates table if not exists
CREATE TABLE IF NOT EXISTS fhq_governance.execution_gates (
    gate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gate_name TEXT NOT NULL UNIQUE,
    gate_status TEXT NOT NULL CHECK (gate_status IN ('ALLOWED', 'BLOCKED', 'SHADOW', 'ACTIVE')),
    description TEXT,
    directive_ref TEXT,
    controlled_agents TEXT[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB
);

-- Insert ACI Shadow Mode gates
INSERT INTO fhq_governance.execution_gates (gate_name, gate_status, description, directive_ref, controlled_agents, metadata)
VALUES
    ('UMA_SIGNAL_PROPOSAL', 'SHADOW', 'UMA authorized to propose alpha hypotheses in PROPOSED_SHADOW state only',
     'CEO-DIR-2026-069', ARRAY['UMA'],
     jsonb_build_object('max_proposals_per_week', 5, 'min_proposals_per_week', 3, 'proposal_state', 'PROPOSED_SHADOW')),

    ('SITC_REASONING', 'SHADOW', 'SitC authorized as cognitive planner for UMA proposals',
     'CEO-DIR-2026-069', ARRAY['SitC'],
     jsonb_build_object('logging_table', 'fhq_meta.chain_of_query', 'execution_authority', false, 'decision_authority', false)),

    ('INFORAGE_RETRIEVAL', 'SHADOW', 'InForage authorized for retrieval when requested by SitC or mandated by IKEA',
     'CEO-DIR-2026-069', ARRAY['InForage'],
     jsonb_build_object('logging_table', 'fhq_meta.search_foraging_log', 'autonomous_search', false, 'requesters', ARRAY['SitC', 'IKEA'])),

    ('IKEA_BOUNDARY_ENFORCEMENT', 'ACTIVE', 'IKEA fully active as hallucination firewall with override authority',
     'CEO-DIR-2026-069', ARRAY['IKEA'],
     jsonb_build_object('logging_table', 'fhq_meta.knowledge_boundary_log', 'override_authority', 'ABSOLUTE'))
ON CONFLICT (gate_name) DO UPDATE SET
    gate_status = EXCLUDED.gate_status,
    description = EXCLUDED.description,
    directive_ref = EXCLUDED.directive_ref,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- ============================================================================
-- SECTION 2: Create Hard Stop Constraints
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.hard_stops (
    stop_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stop_name TEXT NOT NULL UNIQUE,
    stop_type TEXT NOT NULL CHECK (stop_type IN ('FORBIDDEN', 'BLOCKED', 'REQUIRES_APPROVAL')),
    description TEXT NOT NULL,
    directive_ref TEXT NOT NULL,
    affected_agents TEXT[],
    breach_consequence TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB
);

-- Insert hard stops per CEO-DIR-2026-069
INSERT INTO fhq_governance.hard_stops (stop_name, stop_type, description, directive_ref, affected_agents, breach_consequence, metadata)
VALUES
    ('TRADE_EXECUTION', 'FORBIDDEN', 'Trade execution or paper trading', 'CEO-DIR-2026-069',
     ARRAY['UMA', 'SitC', 'InForage', 'IKEA'], 'Immediate halt and VEGA escalation', NULL),

    ('CAPITAL_ALLOCATION', 'FORBIDDEN', 'Capital allocation of any form', 'CEO-DIR-2026-069',
     ARRAY['UMA', 'SitC', 'InForage', 'IKEA'], 'Immediate halt and VEGA escalation', NULL),

    ('AUTOMATED_SIGNAL_ACTIVATION', 'FORBIDDEN', 'Automated signal activation', 'CEO-DIR-2026-069',
     ARRAY['UMA', 'SitC', 'InForage', 'IKEA'], 'Immediate halt and VEGA escalation', NULL),

    ('CALENDAR_DRIVEN_LEARNING', 'FORBIDDEN', 'Calendar-driven learning or execution', 'CEO-DIR-2026-069',
     ARRAY['UMA', 'SitC', 'InForage', 'IKEA'], 'Immediate halt and VEGA escalation', NULL),

    ('TIER_A_CONSENSUS_INGESTION', 'FORBIDDEN', 'Tier A (market-implied) consensus ingestion', 'CEO-DIR-2026-069',
     ARRAY['UMA', 'SitC', 'InForage', 'IKEA', 'CEIO'], 'Immediate halt and VEGA escalation', NULL),

    ('PROPOSAL_FEEDBACK_LOOP', 'FORBIDDEN', 'Feedback from proposals into forecasting models', 'CEO-DIR-2026-069',
     ARRAY['UMA', 'SitC', 'InForage'], 'Immediate halt and VEGA escalation', NULL),

    ('ADR_EC_STATE_CHANGES', 'FORBIDDEN', 'Any ADR or EC state changes', 'CEO-DIR-2026-069',
     ARRAY['UMA', 'SitC', 'InForage', 'IKEA'], 'Immediate halt and VEGA escalation', NULL),

    ('MODEL_RETRAINING', 'FORBIDDEN', 'Retrain models or alter forecast logic', 'CEO-DIR-2026-069',
     ARRAY['UMA'], 'Immediate halt and VEGA escalation', NULL),

    ('INFORAGE_AUTONOMOUS_SEARCH', 'FORBIDDEN', 'InForage autonomous search without SitC/IKEA request', 'CEO-DIR-2026-069',
     ARRAY['InForage'], 'Immediate halt and VEGA escalation', NULL)
ON CONFLICT (stop_name) DO UPDATE SET
    stop_type = EXCLUDED.stop_type,
    description = EXCLUDED.description,
    directive_ref = EXCLUDED.directive_ref,
    affected_agents = EXCLUDED.affected_agents,
    breach_consequence = EXCLUDED.breach_consequence;

-- ============================================================================
-- SECTION 3: Create UMA Signal Proposal Pipeline
-- ============================================================================

-- Create UMA alpha proposals table with Q1-Q5 traceability
CREATE TABLE IF NOT EXISTS fhq_alpha.uma_signal_proposals (
    proposal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_code TEXT NOT NULL UNIQUE,

    -- Proposal content
    hypothesis_text TEXT NOT NULL,
    rationale TEXT NOT NULL,
    target_asset TEXT,
    target_asset_class TEXT,
    signal_direction TEXT CHECK (signal_direction IN ('LONG', 'SHORT', 'NEUTRAL', 'HEDGE')),
    confidence_score NUMERIC(5,4) CHECK (confidence_score BETWEEN 0 AND 1),

    -- Q1-Q5 Traceability (CEO-DIR-2026-069 requirement)
    q1_consensus_ref JSONB,  -- Q1: What did experts/market expect?
    q2_forecast_ref JSONB NOT NULL,  -- Q2: What did FjordHQ expect?
    q3_outcome_ref JSONB,  -- Q3: What actually happened?
    q4_error_ref JSONB,  -- Q4: How wrong were we?
    q5_hindsight_ref JSONB,  -- Q5: What opportunities appeared post-hoc?

    -- Reasoning chain (SitC)
    sitc_reasoning_chain_id UUID,
    reasoning_summary TEXT NOT NULL,
    regime_state_at_proposal JSONB,
    forecast_error_patterns JSONB,
    hindsight_findings JSONB,

    -- Retrieval evidence (InForage)
    inforage_retrieval_ids UUID[],
    external_data_sources JSONB,

    -- Validation (IKEA)
    ikea_validation_id UUID,
    ikea_classification TEXT CHECK (ikea_classification IN ('PARAMETRIC', 'EXTERNAL_REQUIRED', 'HYBRID', 'BLOCKED')),
    ikea_verdict TEXT CHECK (ikea_verdict IN ('APPROVED', 'BLOCKED', 'PENDING')),
    ikea_block_reason TEXT,

    -- Status (SHADOW mode only per CEO-DIR-2026-069)
    status TEXT NOT NULL DEFAULT 'PROPOSED_SHADOW'
        CHECK (status IN ('PROPOSED_SHADOW', 'IKEA_REVIEW', 'IKEA_BLOCKED', 'READY_FOR_HUMAN_REVIEW', 'HUMAN_APPROVED', 'HUMAN_REJECTED', 'EXPIRED')),

    -- Metadata
    generated_by TEXT NOT NULL DEFAULT 'UMA',
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '7 days'),
    directive_ref TEXT NOT NULL DEFAULT 'CEO-DIR-2026-069',

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create index for efficient querying
CREATE INDEX IF NOT EXISTS idx_uma_proposals_status ON fhq_alpha.uma_signal_proposals(status);
CREATE INDEX IF NOT EXISTS idx_uma_proposals_generated_at ON fhq_alpha.uma_signal_proposals(generated_at);
CREATE INDEX IF NOT EXISTS idx_uma_proposals_ikea_verdict ON fhq_alpha.uma_signal_proposals(ikea_verdict);

-- ============================================================================
-- SECTION 4: Create IKEA Validation Infrastructure
-- ============================================================================

-- Create IKEA validation log table
CREATE TABLE IF NOT EXISTS fhq_governance.ikea_proposal_validations (
    validation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES fhq_alpha.uma_signal_proposals(proposal_id),

    -- Classification
    classification TEXT NOT NULL CHECK (classification IN ('PARAMETRIC', 'EXTERNAL_REQUIRED', 'HYBRID', 'BLOCKED')),

    -- Claims analyzed
    claims_analyzed JSONB NOT NULL,
    parametric_claims INTEGER NOT NULL DEFAULT 0,
    external_claims INTEGER NOT NULL DEFAULT 0,
    unverified_claims INTEGER NOT NULL DEFAULT 0,

    -- Verdict
    verdict TEXT NOT NULL CHECK (verdict IN ('APPROVED', 'BLOCKED', 'PENDING')),
    block_reason TEXT,

    -- Evidence
    evidence_chain JSONB,

    -- Audit
    validated_by TEXT NOT NULL DEFAULT 'IKEA',
    validated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    directive_ref TEXT NOT NULL DEFAULT 'CEO-DIR-2026-069'
);

CREATE INDEX IF NOT EXISTS idx_ikea_validations_proposal ON fhq_governance.ikea_proposal_validations(proposal_id);
CREATE INDEX IF NOT EXISTS idx_ikea_validations_verdict ON fhq_governance.ikea_proposal_validations(verdict);

-- ============================================================================
-- SECTION 5: Create SitC Reasoning Chain Linkage
-- ============================================================================

-- Add proposal linkage to chain_of_query if needed
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_meta' AND table_name = 'chain_of_query' AND column_name = 'uma_proposal_id'
    ) THEN
        ALTER TABLE fhq_meta.chain_of_query ADD COLUMN uma_proposal_id UUID;
    END IF;
END $$;

-- ============================================================================
-- SECTION 6: Create InForage Search Request Log
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.inforage_search_requests (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Request context
    requesting_agent TEXT NOT NULL CHECK (requesting_agent IN ('SitC', 'IKEA')),
    request_type TEXT NOT NULL CHECK (request_type IN ('SITC_REASONING', 'IKEA_VERIFICATION')),
    search_query TEXT NOT NULL,

    -- Search parameters
    search_scope TEXT,
    time_sensitivity TEXT CHECK (time_sensitivity IN ('REAL_TIME', 'RECENT', 'HISTORICAL')),

    -- Linkage
    uma_proposal_id UUID,
    sitc_chain_id UUID,

    -- Result
    search_executed BOOLEAN NOT NULL DEFAULT FALSE,
    search_result JSONB,
    scent_score NUMERIC(5,4),
    roi_assessment TEXT,

    -- Audit
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    executed_at TIMESTAMPTZ,
    directive_ref TEXT NOT NULL DEFAULT 'CEO-DIR-2026-069'
);

CREATE INDEX IF NOT EXISTS idx_inforage_requests_proposal ON fhq_meta.inforage_search_requests(uma_proposal_id);
CREATE INDEX IF NOT EXISTS idx_inforage_requests_requester ON fhq_meta.inforage_search_requests(requesting_agent);

-- ============================================================================
-- SECTION 7: Update Agent Mandates with Shadow Authorization
-- ============================================================================

-- Update UMA mandate with signal proposal authorization
UPDATE fhq_governance.agent_mandates
SET mandate_document = mandate_document || jsonb_build_object(
    'shadow_activation', jsonb_build_object(
        'directive', 'CEO-DIR-2026-069',
        'mode', 'SHADOW',
        'authorized_actions', jsonb_build_array(
            'Generate alpha hypotheses in PROPOSED_SHADOW state',
            'Consume outputs from SitC, InForage, IKEA',
            'Propose 3-5 alpha hypotheses per week',
            'Write proposals to canonical pipeline with Q1-Q5 traceability'
        ),
        'hard_stops', jsonb_build_array(
            'Execute, allocate, simulate capital or trigger automation',
            'Retrain models or alter forecast logic',
            'Feed proposals back into forecasting or learning loops'
        ),
        'activated_at', NOW()
    )
)
WHERE agent_name = 'UMA';

-- Update SitC mandate with reasoning activation
UPDATE fhq_governance.agent_mandates
SET mandate_document = mandate_document || jsonb_build_object(
    'shadow_activation', jsonb_build_object(
        'directive', 'CEO-DIR-2026-069',
        'mode', 'SHADOW',
        'role', 'Cognitive Planner for UMA proposals',
        'authorized_actions', jsonb_build_array(
            'Synthesize regime state, forecast error patterns, hindsight findings',
            'Produce explicit reasoning chains for each proposed signal',
            'Log all reasoning to fhq_meta.chain_of_query'
        ),
        'hard_stops', jsonb_build_array(
            'No execution authority',
            'No decision authority'
        ),
        'activated_at', NOW()
    )
)
WHERE agent_name = 'SitC';

-- Update InForage mandate with retrieval activation
UPDATE fhq_governance.agent_mandates
SET mandate_document = mandate_document || jsonb_build_object(
    'shadow_activation', jsonb_build_object(
        'directive', 'CEO-DIR-2026-069',
        'mode', 'SHADOW',
        'role', 'Retrieval Specialist',
        'authorized_actions', jsonb_build_array(
            'Retrieve time-sensitive or market-specific data when requested by SitC',
            'Retrieve data when mandated by IKEA',
            'Evaluate search ROI and log all retrieval actions',
            'Provide retrieved data as inputs only'
        ),
        'hard_stops', jsonb_build_array(
            'No autonomous search',
            'No conclusions - data inputs only'
        ),
        'requesters', jsonb_build_array('SitC', 'IKEA'),
        'activated_at', NOW()
    )
)
WHERE agent_name = 'InForage';

-- Update IKEA mandate with active enforcement
UPDATE fhq_governance.agent_mandates
SET mandate_document = mandate_document || jsonb_build_object(
    'shadow_activation', jsonb_build_object(
        'directive', 'CEO-DIR-2026-069',
        'mode', 'ACTIVE',
        'role', 'Knowledge Boundary Enforcer',
        'authorized_actions', jsonb_build_array(
            'Classify all factual claims used in UMA proposals',
            'Enforce PARAMETRIC vs EXTERNAL_REQUIRED rules',
            'Block any proposal containing unverified external claims',
            'Log all classifications and blocks to fhq_meta.knowledge_boundary_log'
        ),
        'override_authority', 'ABSOLUTE',
        'activated_at', NOW()
    )
)
WHERE agent_name = 'IKEA';

-- ============================================================================
-- SECTION 8: Create Proposal Validation Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_alpha.fn_validate_uma_proposal(p_proposal_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_proposal RECORD;
    v_validation_result JSONB;
    v_ikea_verdict TEXT;
BEGIN
    -- Get proposal
    SELECT * INTO v_proposal FROM fhq_alpha.uma_signal_proposals WHERE proposal_id = p_proposal_id;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('error', 'Proposal not found', 'proposal_id', p_proposal_id);
    END IF;

    -- Check hard stops
    IF v_proposal.status NOT IN ('PROPOSED_SHADOW', 'IKEA_REVIEW') THEN
        RETURN jsonb_build_object('error', 'Proposal not in valid state for validation', 'current_status', v_proposal.status);
    END IF;

    -- Determine IKEA verdict based on classification
    IF v_proposal.ikea_classification = 'BLOCKED' THEN
        v_ikea_verdict := 'BLOCKED';
    ELSIF v_proposal.ikea_classification = 'EXTERNAL_REQUIRED' AND v_proposal.external_data_sources IS NULL THEN
        v_ikea_verdict := 'BLOCKED';
    ELSE
        v_ikea_verdict := 'APPROVED';
    END IF;

    -- Update proposal with IKEA verdict
    UPDATE fhq_alpha.uma_signal_proposals
    SET
        ikea_verdict = v_ikea_verdict,
        status = CASE
            WHEN v_ikea_verdict = 'BLOCKED' THEN 'IKEA_BLOCKED'
            ELSE 'READY_FOR_HUMAN_REVIEW'
        END,
        updated_at = NOW()
    WHERE proposal_id = p_proposal_id;

    -- Log validation
    INSERT INTO fhq_governance.ikea_proposal_validations (
        proposal_id, classification, claims_analyzed,
        parametric_claims, external_claims, unverified_claims,
        verdict, block_reason, evidence_chain
    ) VALUES (
        p_proposal_id,
        COALESCE(v_proposal.ikea_classification, 'PARAMETRIC'),
        COALESCE(v_proposal.q2_forecast_ref, '{}'::jsonb),
        1, 0, 0,
        v_ikea_verdict,
        v_proposal.ikea_block_reason,
        jsonb_build_object('q1', v_proposal.q1_consensus_ref, 'q2', v_proposal.q2_forecast_ref,
                          'q3', v_proposal.q3_outcome_ref, 'q4', v_proposal.q4_error_ref, 'q5', v_proposal.q5_hindsight_ref)
    );

    RETURN jsonb_build_object(
        'proposal_id', p_proposal_id,
        'ikea_verdict', v_ikea_verdict,
        'new_status', CASE WHEN v_ikea_verdict = 'BLOCKED' THEN 'IKEA_BLOCKED' ELSE 'READY_FOR_HUMAN_REVIEW' END,
        'validated_at', NOW()
    );
END;
$$;

-- ============================================================================
-- SECTION 9: Create View for Pending Proposals
-- ============================================================================

CREATE OR REPLACE VIEW fhq_alpha.v_uma_pending_proposals AS
SELECT
    p.proposal_id,
    p.proposal_code,
    p.hypothesis_text,
    p.target_asset,
    p.signal_direction,
    p.confidence_score,
    p.ikea_classification,
    p.ikea_verdict,
    p.status,
    p.generated_at,
    p.expires_at,
    p.reasoning_summary,
    -- Q1-Q5 traceability summary
    CASE WHEN p.q1_consensus_ref IS NOT NULL THEN 'YES' ELSE 'NO' END AS has_q1,
    CASE WHEN p.q2_forecast_ref IS NOT NULL THEN 'YES' ELSE 'NO' END AS has_q2,
    CASE WHEN p.q3_outcome_ref IS NOT NULL THEN 'YES' ELSE 'NO' END AS has_q3,
    CASE WHEN p.q4_error_ref IS NOT NULL THEN 'YES' ELSE 'NO' END AS has_q4,
    CASE WHEN p.q5_hindsight_ref IS NOT NULL THEN 'YES' ELSE 'NO' END AS has_q5
FROM fhq_alpha.uma_signal_proposals p
WHERE p.status IN ('PROPOSED_SHADOW', 'IKEA_REVIEW', 'READY_FOR_HUMAN_REVIEW')
  AND p.expires_at > NOW()
ORDER BY p.confidence_score DESC, p.generated_at DESC;

COMMENT ON VIEW fhq_alpha.v_uma_pending_proposals IS
'CEO-DIR-2026-069: View of UMA proposals pending review. Shows Q1-Q5 traceability status.';

-- ============================================================================
-- SECTION 10: Log Activation to Governance Actions
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'ACI_SHADOW_ACTIVATION',
    'UMA,SitC,InForage,IKEA',
    'DIRECTIVE_EXECUTION',
    'STIG',
    'APPROVED',
    'CEO-DIR-2026-069: ACI Triangle Shadow Activation for UMA Signal Proposal Mode',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-069',
        'agents_activated', jsonb_build_object(
            'UMA', 'SHADOW',
            'SitC', 'SHADOW',
            'InForage', 'SHADOW',
            'IKEA', 'ACTIVE'
        ),
        'reference_epoch', '001',
        'epoch_lock_status', 'PRESERVED',
        'activation_timestamp', NOW()
    )
);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES (Run after migration)
-- ============================================================================
-- SELECT * FROM fhq_governance.execution_gates WHERE directive_ref = 'CEO-DIR-2026-069';
-- SELECT * FROM fhq_governance.hard_stops WHERE directive_ref = 'CEO-DIR-2026-069';
-- SELECT agent_name, mandate_document->'shadow_activation' FROM fhq_governance.agent_mandates WHERE agent_name IN ('UMA', 'SitC', 'InForage', 'IKEA');
