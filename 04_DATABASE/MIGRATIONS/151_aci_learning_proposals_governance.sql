-- ============================================================================
-- MIGRATION 151: ACI Learning Proposals Governance Infrastructure
-- ============================================================================
-- CEO DIRECTIVE COMPLIANCE: 2025-12-17
-- Mandate IV: Governance of Learning Loop (ADR-020/021)
--
-- "NO automated updates to IKEA classifier. All updates go to staging
--  + G1/VEGA approval."
--
-- This migration creates the staging infrastructure for cognitive engine
-- learning proposals. Updates are PROPOSED here, not applied directly.
--
-- Authority: CEO Directive 2025-12-17, ADR-020, ADR-021
-- Classification: STIG-2025-ACI-INTEGRATION
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. LEARNING PROPOSALS TABLE (Staging Area)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.learning_proposals (
    proposal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Engine identification
    engine_id VARCHAR(10) NOT NULL,  -- 'IKEA', 'INFORAGE', 'SITC'
    proposal_type VARCHAR(50) NOT NULL,  -- 'BOUNDARY_WEIGHT', 'SCENT_MODEL', 'PLAN_PRIOR'

    -- Value comparison
    current_value JSONB NOT NULL,
    proposed_value JSONB NOT NULL,
    delta_description TEXT,  -- Human-readable change description

    -- Evidence chain (trade outcomes that justify the change)
    evidence_bundle JSONB NOT NULL,
    evidence_count INTEGER DEFAULT 0,
    evidence_win_rate NUMERIC(5,4),
    evidence_confidence NUMERIC(5,4),

    -- Governance state
    status VARCHAR(20) DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'EXPIRED')),

    -- Submission tracking
    submitted_by VARCHAR(50) NOT NULL,
    submitted_at TIMESTAMPTZ DEFAULT NOW(),

    -- Review tracking
    reviewed_by VARCHAR(50),
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,

    -- VEGA attestation binding (required for approval)
    vega_attestation_id UUID,
    vega_attestation_hash VARCHAR(64),

    -- State binding (Mandate I: ASRP)
    state_snapshot_hash VARCHAR(64),
    state_timestamp TIMESTAMPTZ,

    -- Expiry (proposals expire after 7 days without review)
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '7 days',

    -- Audit trail
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_learning_proposals_engine
    ON fhq_governance.learning_proposals(engine_id);
CREATE INDEX IF NOT EXISTS idx_learning_proposals_status
    ON fhq_governance.learning_proposals(status);
CREATE INDEX IF NOT EXISTS idx_learning_proposals_submitted
    ON fhq_governance.learning_proposals(submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_learning_proposals_expires
    ON fhq_governance.learning_proposals(expires_at)
    WHERE status = 'PENDING';

-- ============================================================================
-- 2. LEARNING PROPOSAL AUDIT LOG
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.learning_proposal_audit (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID REFERENCES fhq_governance.learning_proposals(proposal_id),

    action VARCHAR(50) NOT NULL,  -- 'SUBMITTED', 'REVIEWED', 'APPROVED', 'REJECTED', 'EXPIRED'
    previous_status VARCHAR(20),
    new_status VARCHAR(20),

    actor VARCHAR(50) NOT NULL,
    action_reason TEXT,

    -- Hash chain for audit integrity
    hash_prev VARCHAR(64),
    hash_self VARCHAR(64),

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_learning_audit_proposal
    ON fhq_governance.learning_proposal_audit(proposal_id);

-- ============================================================================
-- 3. APPROVED LEARNING VERSIONS (Production)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.learning_versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    engine_id VARCHAR(10) NOT NULL,
    parameter_type VARCHAR(50) NOT NULL,

    -- Version tracking
    version_number INTEGER NOT NULL,
    previous_version_id UUID REFERENCES fhq_governance.learning_versions(version_id),

    -- The approved values
    parameter_value JSONB NOT NULL,

    -- Provenance
    source_proposal_id UUID REFERENCES fhq_governance.learning_proposals(proposal_id),
    vega_attestation_id UUID NOT NULL,

    -- Activation state
    is_active BOOLEAN DEFAULT false,
    activated_at TIMESTAMPTZ,
    deactivated_at TIMESTAMPTZ,

    -- Metadata
    created_by VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(engine_id, parameter_type, version_number)
);

CREATE INDEX IF NOT EXISTS idx_learning_versions_active
    ON fhq_governance.learning_versions(engine_id, parameter_type)
    WHERE is_active = true;

-- ============================================================================
-- 4. HELPER FUNCTIONS
-- ============================================================================

-- Function to submit a learning proposal
CREATE OR REPLACE FUNCTION fhq_governance.fn_submit_learning_proposal(
    p_engine_id VARCHAR(10),
    p_proposal_type VARCHAR(50),
    p_current_value JSONB,
    p_proposed_value JSONB,
    p_evidence_bundle JSONB,
    p_submitted_by VARCHAR(50),
    p_state_hash VARCHAR(64) DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_proposal_id UUID;
    v_evidence_count INTEGER;
BEGIN
    -- Calculate evidence metrics
    v_evidence_count := jsonb_array_length(p_evidence_bundle);

    -- Insert proposal
    INSERT INTO fhq_governance.learning_proposals (
        engine_id,
        proposal_type,
        current_value,
        proposed_value,
        evidence_bundle,
        evidence_count,
        submitted_by,
        state_snapshot_hash,
        state_timestamp
    ) VALUES (
        p_engine_id,
        p_proposal_type,
        p_current_value,
        p_proposed_value,
        p_evidence_bundle,
        v_evidence_count,
        p_submitted_by,
        p_state_hash,
        NOW()
    ) RETURNING proposal_id INTO v_proposal_id;

    -- Log submission
    INSERT INTO fhq_governance.learning_proposal_audit (
        proposal_id,
        action,
        previous_status,
        new_status,
        actor,
        action_reason
    ) VALUES (
        v_proposal_id,
        'SUBMITTED',
        NULL,
        'PENDING',
        p_submitted_by,
        'Learning proposal submitted for governance review'
    );

    RETURN v_proposal_id;
END;
$$ LANGUAGE plpgsql;

-- Function to approve a learning proposal (requires VEGA attestation)
CREATE OR REPLACE FUNCTION fhq_governance.fn_approve_learning_proposal(
    p_proposal_id UUID,
    p_reviewed_by VARCHAR(50),
    p_vega_attestation_id UUID,
    p_review_notes TEXT DEFAULT NULL
) RETURNS BOOLEAN AS $$
DECLARE
    v_engine_id VARCHAR(10);
    v_proposal_type VARCHAR(50);
    v_proposed_value JSONB;
    v_current_version INTEGER;
BEGIN
    -- Validate proposal exists and is pending
    IF NOT EXISTS (
        SELECT 1 FROM fhq_governance.learning_proposals
        WHERE proposal_id = p_proposal_id
        AND status IN ('PENDING', 'UNDER_REVIEW')
    ) THEN
        RAISE EXCEPTION 'Proposal not found or not in reviewable state';
    END IF;

    -- Get proposal details
    SELECT engine_id, proposal_type, proposed_value
    INTO v_engine_id, v_proposal_type, v_proposed_value
    FROM fhq_governance.learning_proposals
    WHERE proposal_id = p_proposal_id;

    -- Get current max version
    SELECT COALESCE(MAX(version_number), 0) INTO v_current_version
    FROM fhq_governance.learning_versions
    WHERE engine_id = v_engine_id AND parameter_type = v_proposal_type;

    -- Update proposal status
    UPDATE fhq_governance.learning_proposals SET
        status = 'APPROVED',
        reviewed_by = p_reviewed_by,
        reviewed_at = NOW(),
        review_notes = p_review_notes,
        vega_attestation_id = p_vega_attestation_id,
        updated_at = NOW()
    WHERE proposal_id = p_proposal_id;

    -- Deactivate current version if exists
    UPDATE fhq_governance.learning_versions SET
        is_active = false,
        deactivated_at = NOW()
    WHERE engine_id = v_engine_id
    AND parameter_type = v_proposal_type
    AND is_active = true;

    -- Create new active version
    INSERT INTO fhq_governance.learning_versions (
        engine_id,
        parameter_type,
        version_number,
        parameter_value,
        source_proposal_id,
        vega_attestation_id,
        is_active,
        activated_at,
        created_by
    ) VALUES (
        v_engine_id,
        v_proposal_type,
        v_current_version + 1,
        v_proposed_value,
        p_proposal_id,
        p_vega_attestation_id,
        true,
        NOW(),
        p_reviewed_by
    );

    -- Log approval
    INSERT INTO fhq_governance.learning_proposal_audit (
        proposal_id,
        action,
        previous_status,
        new_status,
        actor,
        action_reason
    ) VALUES (
        p_proposal_id,
        'APPROVED',
        'PENDING',
        'APPROVED',
        p_reviewed_by,
        COALESCE(p_review_notes, 'VEGA attestation verified')
    );

    RETURN true;
END;
$$ LANGUAGE plpgsql;

-- Function to reject a learning proposal
CREATE OR REPLACE FUNCTION fhq_governance.fn_reject_learning_proposal(
    p_proposal_id UUID,
    p_reviewed_by VARCHAR(50),
    p_rejection_reason TEXT
) RETURNS BOOLEAN AS $$
BEGIN
    UPDATE fhq_governance.learning_proposals SET
        status = 'REJECTED',
        reviewed_by = p_reviewed_by,
        reviewed_at = NOW(),
        review_notes = p_rejection_reason,
        updated_at = NOW()
    WHERE proposal_id = p_proposal_id
    AND status IN ('PENDING', 'UNDER_REVIEW');

    IF NOT FOUND THEN
        RETURN false;
    END IF;

    -- Log rejection
    INSERT INTO fhq_governance.learning_proposal_audit (
        proposal_id,
        action,
        previous_status,
        new_status,
        actor,
        action_reason
    ) VALUES (
        p_proposal_id,
        'REJECTED',
        'PENDING',
        'REJECTED',
        p_reviewed_by,
        p_rejection_reason
    );

    RETURN true;
END;
$$ LANGUAGE plpgsql;

-- Function to get active learning version for an engine
CREATE OR REPLACE FUNCTION fhq_governance.fn_get_active_learning_version(
    p_engine_id VARCHAR(10),
    p_parameter_type VARCHAR(50)
) RETURNS JSONB AS $$
DECLARE
    v_result JSONB;
BEGIN
    SELECT parameter_value INTO v_result
    FROM fhq_governance.learning_versions
    WHERE engine_id = p_engine_id
    AND parameter_type = p_parameter_type
    AND is_active = true;

    RETURN v_result;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 5. AUTOMATIC EXPIRY FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.fn_expire_old_proposals()
RETURNS INTEGER AS $$
DECLARE
    v_expired_count INTEGER;
BEGIN
    WITH expired AS (
        UPDATE fhq_governance.learning_proposals SET
            status = 'EXPIRED',
            updated_at = NOW()
        WHERE status = 'PENDING'
        AND expires_at < NOW()
        RETURNING proposal_id
    )
    SELECT COUNT(*) INTO v_expired_count FROM expired;

    -- Log expirations
    INSERT INTO fhq_governance.learning_proposal_audit (
        proposal_id, action, previous_status, new_status, actor, action_reason
    )
    SELECT
        proposal_id,
        'EXPIRED',
        'PENDING',
        'EXPIRED',
        'SYSTEM',
        'Proposal expired after 7 days without review'
    FROM fhq_governance.learning_proposals
    WHERE status = 'EXPIRED'
    AND updated_at > NOW() - INTERVAL '1 minute';

    RETURN v_expired_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 6. MIGRATION COMPLETE
-- ============================================================================
-- Migration 151: Created learning_proposals governance infrastructure
-- per CEO Directive Mandate IV (2025-12-17)
-- Tables created: learning_proposals, learning_proposal_audit, learning_versions
-- Functions created: fn_submit_learning_proposal, fn_approve_learning_proposal,
--                    fn_reject_learning_proposal, fn_get_active_learning_version,
--                    fn_expire_old_proposals

COMMIT;

-- ============================================================================
-- VERIFICATION QUERY
-- ============================================================================
-- Run after migration to verify tables exist:
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'fhq_governance'
-- AND table_name LIKE 'learning%';
