-- ============================================================================
-- Migration 087: Oracle Staging for G0 Submissions
-- Authority: G1 UI Governance Patch - Vision-Chat 2026
--
-- Creates the oracle_staging table for CEO narrative vector submissions
-- that require VEGA G1 review before promotion to narrative_vectors
-- ============================================================================

-- Ensure governance schema exists
CREATE SCHEMA IF NOT EXISTS fhq_governance;

-- Create oracle_staging table
CREATE TABLE IF NOT EXISTS fhq_governance.oracle_staging (
    submission_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Narrative content
    domain TEXT NOT NULL,
    narrative TEXT NOT NULL,
    probability NUMERIC(4,3) NOT NULL CHECK (probability >= 0 AND probability <= 1),
    confidence NUMERIC(4,3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    half_life_hours INTEGER NOT NULL DEFAULT 24,

    -- Submission metadata
    submitted_by TEXT NOT NULL DEFAULT 'CEO',
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submission_source TEXT DEFAULT 'VISION_CHAT',

    -- Review workflow
    review_status TEXT NOT NULL DEFAULT 'PENDING',
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    rejection_reason TEXT,

    -- Promotion tracking
    promoted_to_vector_id UUID,
    promoted_at TIMESTAMPTZ,

    -- Constraints
    CONSTRAINT valid_review_status CHECK (
        review_status IN ('PENDING', 'APPROVED', 'REJECTED', 'PROMOTED')
    ),
    CONSTRAINT valid_domain CHECK (
        domain IN ('Regulatory', 'Geopolitical', 'Liquidity', 'Reflexivity', 'Sentiment', 'Technical', 'Macro', 'Other')
    )
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_oracle_staging_status
    ON fhq_governance.oracle_staging(review_status);

CREATE INDEX IF NOT EXISTS idx_oracle_staging_submitted_at
    ON fhq_governance.oracle_staging(submitted_at DESC);

CREATE INDEX IF NOT EXISTS idx_oracle_staging_domain
    ON fhq_governance.oracle_staging(domain);

-- Create view for pending reviews
CREATE OR REPLACE VIEW fhq_governance.v_pending_oracle_submissions AS
SELECT
    submission_id,
    domain,
    LEFT(narrative, 200) AS narrative_preview,
    probability,
    confidence,
    half_life_hours,
    submitted_by,
    submitted_at,
    EXTRACT(EPOCH FROM (NOW() - submitted_at)) / 3600 AS hours_pending
FROM fhq_governance.oracle_staging
WHERE review_status = 'PENDING'
ORDER BY submitted_at DESC;

-- Create function to promote approved submissions to narrative_vectors
CREATE OR REPLACE FUNCTION fhq_governance.promote_oracle_submission(
    p_submission_id UUID,
    p_reviewer TEXT DEFAULT 'VEGA'
)
RETURNS UUID AS $$
DECLARE
    v_submission RECORD;
    v_vector_id UUID;
BEGIN
    -- Get the submission
    SELECT * INTO v_submission
    FROM fhq_governance.oracle_staging
    WHERE submission_id = p_submission_id
      AND review_status = 'APPROVED';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Submission not found or not in APPROVED status';
    END IF;

    -- Insert into narrative_vectors
    INSERT INTO fhq_meta.narrative_vectors (
        domain,
        narrative,
        probability,
        confidence,
        half_life_hours,
        created_by,
        is_expired
    ) VALUES (
        v_submission.domain,
        v_submission.narrative,
        v_submission.probability,
        v_submission.confidence,
        v_submission.half_life_hours,
        v_submission.submitted_by,
        FALSE
    )
    RETURNING vector_id INTO v_vector_id;

    -- Update staging record
    UPDATE fhq_governance.oracle_staging
    SET review_status = 'PROMOTED',
        promoted_to_vector_id = v_vector_id,
        promoted_at = NOW()
    WHERE submission_id = p_submission_id;

    -- Log the promotion
    INSERT INTO fhq_governance.governance_actions_log (
        action_type, action_target, action_target_type, initiated_by,
        decision, decision_rationale, hash_chain_id
    ) VALUES (
        'ORACLE_PROMOTION',
        v_vector_id::TEXT,
        'NARRATIVE_VECTOR',
        p_reviewer,
        'PROMOTED',
        format('Promoted submission %s to vector %s', p_submission_id, v_vector_id),
        format('HC-PROMOTE-%s', CURRENT_DATE)
    );

    RETURN v_vector_id;
END;
$$ LANGUAGE plpgsql;

-- Grant appropriate permissions
GRANT SELECT ON fhq_governance.oracle_staging TO ceo_read_only;
GRANT SELECT ON fhq_governance.v_pending_oracle_submissions TO ceo_read_only;
GRANT ALL ON fhq_governance.oracle_staging TO stig_write_engine;
GRANT EXECUTE ON FUNCTION fhq_governance.promote_oracle_submission TO stig_write_engine;

-- Log migration
INSERT INTO fhq_meta.adr_audit_log (
    adr_id,
    change_type,
    change_description,
    changed_by,
    governance_gate
) VALUES (
    'ADR-019',
    'MIGRATION',
    'Created oracle_staging table for G0 narrative vector submissions with VEGA review workflow',
    'STIG',
    'G1_TECHNICAL'
);

COMMENT ON TABLE fhq_governance.oracle_staging IS
    'G0 submissions for narrative vectors pending VEGA G1 review. Per G1 UI Governance Patch.';
