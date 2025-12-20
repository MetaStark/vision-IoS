-- ============================================================================
-- MIGRATION: 045_ios005_recalibration_pathway.sql
-- PURPOSE: IoS-005 Recalibration Pathway for IoS-007 Edge Weight Modification
-- AUTHORITY: BOARD (Vice-CEO) → STIG (Technical Authority)
-- ADR COMPLIANCE: ADR-003, ADR-004, ADR-011, ADR-013
-- STATUS: G0 EXTENSION — Connects IoS-005 (G4) to IoS-007 (G4)
-- ============================================================================
--
-- CONTEXT:
-- IoS-007 G4 activation locked all edge weights with trg_enforce_edge_weight_lock.
-- The ONLY pathway to modify edge strengths is through IoS-005 Recalibration.
-- This migration creates the formal request/approval/execution infrastructure.
--
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. RECALIBRATION REQUESTS TABLE
-- ============================================================================
-- Formal governance-tracked requests to modify IoS-007 edge weights

CREATE TABLE IF NOT EXISTS fhq_research.recalibration_requests (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Request Identification
    request_code TEXT NOT NULL UNIQUE,              -- e.g., "RECAL-IOS007-20251130-001"
    request_type TEXT NOT NULL,                     -- EDGE_STRENGTH, EDGE_LAG, CONFIDENCE_UPDATE

    -- Target Edge
    target_edge_id TEXT NOT NULL,                   -- References fhq_graph.edges.edge_id
    target_schema TEXT NOT NULL DEFAULT 'fhq_graph',
    target_table TEXT NOT NULL DEFAULT 'edges',

    -- Current Values (snapshot at request time)
    current_strength NUMERIC(10,5),
    current_lag_days INTEGER,
    current_confidence NUMERIC(5,4),

    -- Proposed Values
    proposed_strength NUMERIC(10,5),
    proposed_lag_days INTEGER,
    proposed_confidence NUMERIC(5,4),

    -- Statistical Evidence (from IoS-005 analysis)
    evidence_scorecard_id UUID,                     -- FK to forecast_skill_registry
    evidence_correlation NUMERIC(8,5),
    evidence_t_statistic NUMERIC(10,4),
    evidence_p_value NUMERIC(10,8),
    evidence_sample_size INTEGER,
    evidence_date_range_start DATE,
    evidence_date_range_end DATE,
    evidence_hash TEXT NOT NULL,                    -- SHA-256 of evidence payload

    -- Justification
    justification TEXT NOT NULL,
    methodology TEXT,                               -- Statistical method used

    -- Request Lifecycle
    status TEXT NOT NULL DEFAULT 'PENDING',         -- PENDING, UNDER_REVIEW, APPROVED, REJECTED, EXECUTED, ROLLED_BACK
    requested_by TEXT NOT NULL,                     -- Agent ID (must be IoS-005 role)
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Review (VEGA)
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,

    -- Approval (CEO/BOARD)
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    approval_notes TEXT,

    -- Execution
    executed_by TEXT,
    executed_at TIMESTAMPTZ,
    execution_signature_id UUID,

    -- Rollback (if needed)
    rolled_back_by TEXT,
    rolled_back_at TIMESTAMPTZ,
    rollback_reason TEXT,

    -- ADR-011 Hash Chain
    lineage_hash TEXT NOT NULL,
    hash_prev TEXT,
    hash_self TEXT NOT NULL,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT chk_request_type CHECK (request_type IN ('EDGE_STRENGTH', 'EDGE_LAG', 'CONFIDENCE_UPDATE', 'FULL_RECALIBRATION')),
    CONSTRAINT chk_status CHECK (status IN ('PENDING', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'EXECUTED', 'ROLLED_BACK')),
    CONSTRAINT chk_p_value_range CHECK (evidence_p_value IS NULL OR (evidence_p_value >= 0 AND evidence_p_value <= 1)),
    CONSTRAINT chk_strength_change CHECK (proposed_strength IS NOT NULL OR proposed_lag_days IS NOT NULL OR proposed_confidence IS NOT NULL)
);

-- ============================================================================
-- 2. RECALIBRATION AUDIT LOG
-- ============================================================================
-- Immutable append-only log of all recalibration events

CREATE TABLE IF NOT EXISTS fhq_research.recalibration_audit_log (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Reference
    request_id UUID NOT NULL REFERENCES fhq_research.recalibration_requests(request_id),

    -- Event
    event_type TEXT NOT NULL,                       -- CREATED, REVIEWED, APPROVED, REJECTED, EXECUTED, ROLLED_BACK
    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_agent TEXT NOT NULL,

    -- State Change
    previous_status TEXT,
    new_status TEXT NOT NULL,

    -- Details
    event_details JSONB,

    -- ADR-011 Hash Chain
    lineage_hash TEXT NOT NULL,

    -- Audit (append-only, no updates)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Prevent updates/deletes on audit log
CREATE OR REPLACE FUNCTION fhq_research.prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'ADR-011 VIOLATION: recalibration_audit_log is append-only. Modifications are prohibited.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_audit_update ON fhq_research.recalibration_audit_log;
CREATE TRIGGER trg_prevent_audit_update
    BEFORE UPDATE OR DELETE ON fhq_research.recalibration_audit_log
    FOR EACH ROW
    EXECUTE FUNCTION fhq_research.prevent_audit_modification();

-- ============================================================================
-- 3. DETERMINISTIC FSS CALCULATION FUNCTION
-- ============================================================================
-- FjordHQ Skill Score: Deterministic, auditable formula

CREATE OR REPLACE FUNCTION fhq_research.calculate_fss(
    p_risk_adj_return NUMERIC,      -- Normalized Sharpe/Sortino (0-1 scale)
    p_stability NUMERIC,            -- 1 - (drawdown severity) (0-1 scale)
    p_significance NUMERIC,         -- 1 - p_value (0-1 scale)
    p_consistency NUMERIC           -- Hit rate or win consistency (0-1 scale)
)
RETURNS NUMERIC AS $$
DECLARE
    v_fss NUMERIC(5,4);
    v_weight_risk_adj CONSTANT NUMERIC := 0.40;
    v_weight_stability CONSTANT NUMERIC := 0.30;
    v_weight_significance CONSTANT NUMERIC := 0.20;
    v_weight_consistency CONSTANT NUMERIC := 0.10;
BEGIN
    -- FSS Formula (deterministic, weights sum to 1.0)
    v_fss := (
        (COALESCE(p_risk_adj_return, 0) * v_weight_risk_adj) +
        (COALESCE(p_stability, 0) * v_weight_stability) +
        (COALESCE(p_significance, 0) * v_weight_significance) +
        (COALESCE(p_consistency, 0) * v_weight_consistency)
    );

    -- Clamp to valid range
    v_fss := GREATEST(0, LEAST(1, v_fss));

    RETURN ROUND(v_fss, 4);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fhq_research.calculate_fss IS
'FjordHQ Skill Score (FSS) - Deterministic calculation per IoS-005 specification.
Weights: Risk-Adjusted Return (40%), Stability (30%), Significance (20%), Consistency (10%).
All inputs normalized to 0-1 scale. Output clamped to [0,1].';

-- ============================================================================
-- 4. RECALIBRATION EXECUTION FUNCTION
-- ============================================================================
-- The ONLY authorized pathway to modify IoS-007 edge strengths

CREATE OR REPLACE FUNCTION fhq_research.execute_recalibration(
    p_request_id UUID,
    p_executing_agent TEXT
)
RETURNS TABLE (
    success BOOLEAN,
    message TEXT,
    execution_signature_id UUID
) AS $$
DECLARE
    v_request RECORD;
    v_sig_id UUID;
    v_old_strength NUMERIC;
BEGIN
    -- Validate request exists and is approved
    SELECT * INTO v_request
    FROM fhq_research.recalibration_requests
    WHERE request_id = p_request_id;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 'Request not found', NULL::UUID;
        RETURN;
    END IF;

    IF v_request.status != 'APPROVED' THEN
        RETURN QUERY SELECT FALSE, 'Request status must be APPROVED. Current: ' || v_request.status, NULL::UUID;
        RETURN;
    END IF;

    -- Validate executing agent has IoS-005 authority
    IF p_executing_agent NOT IN ('STIG', 'VEGA', 'IOS005_ENGINE') THEN
        RETURN QUERY SELECT FALSE, 'Executing agent must have IoS-005 authority', NULL::UUID;
        RETURN;
    END IF;

    -- Get current edge strength for audit
    SELECT strength INTO v_old_strength
    FROM fhq_graph.edges
    WHERE edge_id = v_request.target_edge_id;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 'Target edge not found: ' || v_request.target_edge_id, NULL::UUID;
        RETURN;
    END IF;

    -- Generate execution signature
    v_sig_id := gen_random_uuid();

    INSERT INTO vision_verification.operation_signatures (
        signature_id, operation_type, operation_id, operation_table, operation_schema,
        signing_agent, signing_key_id, signature_value, signed_payload,
        verified, verified_at, verified_by, created_at, hash_chain_id
    )
    VALUES (
        v_sig_id,
        'IOS005_EDGE_RECALIBRATION',
        p_request_id,
        'edges',
        'fhq_graph',
        p_executing_agent,
        p_executing_agent || '-RECAL-' || v_request.request_code,
        encode(sha256((v_request.request_code || '-' || NOW()::text)::bytea), 'hex'),
        jsonb_build_object(
            'request_id', p_request_id,
            'request_code', v_request.request_code,
            'edge_id', v_request.target_edge_id,
            'old_strength', v_old_strength,
            'new_strength', v_request.proposed_strength,
            'evidence_hash', v_request.evidence_hash,
            'evidence_p_value', v_request.evidence_p_value
        ),
        TRUE,
        NOW(),
        'VEGA',
        NOW(),
        'HC-IOS-005-2026'
    );

    -- Execute the edge modification (bypasses lock via recalibration_id)
    UPDATE fhq_graph.edges
    SET
        strength = COALESCE(v_request.proposed_strength, strength),
        lag_days = COALESCE(v_request.proposed_lag_days, lag_days),
        confidence = COALESCE(v_request.proposed_confidence, confidence),
        ios005_recalibration_id = p_request_id,
        ios005_tested = TRUE,
        ios005_test_date = NOW(),
        ios005_audit_id = v_sig_id,
        updated_at = NOW()
    WHERE edge_id = v_request.target_edge_id;

    -- Update request status
    UPDATE fhq_research.recalibration_requests
    SET
        status = 'EXECUTED',
        executed_by = p_executing_agent,
        executed_at = NOW(),
        execution_signature_id = v_sig_id,
        updated_at = NOW()
    WHERE request_id = p_request_id;

    -- Log to audit
    INSERT INTO fhq_research.recalibration_audit_log (
        request_id, event_type, event_agent, previous_status, new_status,
        event_details, lineage_hash
    )
    VALUES (
        p_request_id,
        'EXECUTED',
        p_executing_agent,
        'APPROVED',
        'EXECUTED',
        jsonb_build_object(
            'old_strength', v_old_strength,
            'new_strength', v_request.proposed_strength,
            'signature_id', v_sig_id
        ),
        encode(sha256((p_request_id::text || '-EXECUTED-' || NOW()::text)::bytea), 'hex')
    );

    RETURN QUERY SELECT TRUE, 'Recalibration executed successfully', v_sig_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_research.execute_recalibration IS
'IoS-005 Recalibration Pathway - The ONLY authorized method to modify IoS-007 edge weights.
Requires: APPROVED request status, authorized agent (STIG/VEGA/IOS005_ENGINE).
Creates: Operation signature, audit log entry, updates edge with recalibration reference.';

-- ============================================================================
-- 5. RECALIBRATION REQUEST CREATION FUNCTION
-- ============================================================================
-- Helper function to create properly formatted recalibration requests

CREATE OR REPLACE FUNCTION fhq_research.create_recalibration_request(
    p_edge_id TEXT,
    p_proposed_strength NUMERIC,
    p_evidence_correlation NUMERIC,
    p_evidence_t_stat NUMERIC,
    p_evidence_p_value NUMERIC,
    p_evidence_sample_size INTEGER,
    p_justification TEXT,
    p_requesting_agent TEXT DEFAULT 'IOS005_ENGINE'
)
RETURNS UUID AS $$
DECLARE
    v_request_id UUID;
    v_request_code TEXT;
    v_current_strength NUMERIC;
    v_evidence_hash TEXT;
    v_lineage_hash TEXT;
    v_hash_prev TEXT;
BEGIN
    -- Validate p-value threshold (must be significant)
    IF p_evidence_p_value > 0.05 THEN
        RAISE EXCEPTION 'IoS-005 VIOLATION: Recalibration requires p-value < 0.05. Provided: %', p_evidence_p_value;
    END IF;

    -- Get current edge strength
    SELECT strength INTO v_current_strength
    FROM fhq_graph.edges
    WHERE edge_id = p_edge_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Edge not found: %', p_edge_id;
    END IF;

    -- Generate request code
    v_request_code := 'RECAL-IOS007-' || TO_CHAR(NOW(), 'YYYYMMDD') || '-' ||
                      LPAD((SELECT COUNT(*) + 1 FROM fhq_research.recalibration_requests
                            WHERE requested_at::date = CURRENT_DATE)::text, 3, '0');

    -- Generate evidence hash
    v_evidence_hash := encode(sha256(
        (p_edge_id || '-' || p_proposed_strength::text || '-' ||
         p_evidence_correlation::text || '-' || p_evidence_p_value::text || '-' ||
         p_evidence_sample_size::text)::bytea
    ), 'hex');

    -- Get previous hash for chain
    SELECT hash_self INTO v_hash_prev
    FROM fhq_research.recalibration_requests
    ORDER BY created_at DESC
    LIMIT 1;

    -- Generate lineage hash
    v_lineage_hash := encode(sha256(
        (COALESCE(v_hash_prev, 'GENESIS') || '-' || v_request_code || '-' || v_evidence_hash)::bytea
    ), 'hex');

    -- Create request
    INSERT INTO fhq_research.recalibration_requests (
        request_code, request_type, target_edge_id,
        current_strength, proposed_strength,
        evidence_correlation, evidence_t_statistic, evidence_p_value, evidence_sample_size,
        evidence_hash, justification, methodology,
        requested_by, lineage_hash, hash_prev, hash_self
    )
    VALUES (
        v_request_code, 'EDGE_STRENGTH', p_edge_id,
        v_current_strength, p_proposed_strength,
        p_evidence_correlation, p_evidence_t_stat, p_evidence_p_value, p_evidence_sample_size,
        v_evidence_hash, p_justification, 'Pearson correlation with t-test',
        p_requesting_agent, v_lineage_hash, v_hash_prev, v_lineage_hash
    )
    RETURNING request_id INTO v_request_id;

    -- Log to audit
    INSERT INTO fhq_research.recalibration_audit_log (
        request_id, event_type, event_agent, previous_status, new_status,
        event_details, lineage_hash
    )
    VALUES (
        v_request_id,
        'CREATED',
        p_requesting_agent,
        NULL,
        'PENDING',
        jsonb_build_object(
            'edge_id', p_edge_id,
            'current_strength', v_current_strength,
            'proposed_strength', p_proposed_strength,
            'p_value', p_evidence_p_value
        ),
        v_lineage_hash
    );

    RETURN v_request_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 6. INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_recal_requests_status ON fhq_research.recalibration_requests(status);
CREATE INDEX IF NOT EXISTS idx_recal_requests_edge ON fhq_research.recalibration_requests(target_edge_id);
CREATE INDEX IF NOT EXISTS idx_recal_requests_requested_at ON fhq_research.recalibration_requests(requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_recal_audit_request ON fhq_research.recalibration_audit_log(request_id);
CREATE INDEX IF NOT EXISTS idx_recal_audit_timestamp ON fhq_research.recalibration_audit_log(event_timestamp DESC);

-- ============================================================================
-- 7. VIEWS
-- ============================================================================

-- Active recalibration requests view
CREATE OR REPLACE VIEW fhq_research.v_pending_recalibrations AS
SELECT
    r.request_id,
    r.request_code,
    r.target_edge_id,
    e.from_node_id,
    e.to_node_id,
    e.relationship_type,
    r.current_strength,
    r.proposed_strength,
    r.proposed_strength - r.current_strength AS strength_delta,
    r.evidence_p_value,
    r.evidence_t_statistic,
    r.evidence_sample_size,
    r.status,
    r.requested_by,
    r.requested_at,
    r.justification
FROM fhq_research.recalibration_requests r
JOIN fhq_graph.edges e ON e.edge_id = r.target_edge_id
WHERE r.status IN ('PENDING', 'UNDER_REVIEW', 'APPROVED')
ORDER BY r.requested_at DESC;

-- Recalibration history view
CREATE OR REPLACE VIEW fhq_research.v_recalibration_history AS
SELECT
    r.request_code,
    r.target_edge_id,
    r.current_strength AS old_strength,
    r.proposed_strength AS new_strength,
    r.evidence_p_value,
    r.status,
    r.requested_at,
    r.approved_at,
    r.executed_at,
    r.approved_by,
    r.executed_by
FROM fhq_research.recalibration_requests r
WHERE r.status = 'EXECUTED'
ORDER BY r.executed_at DESC;

-- ============================================================================
-- 8. GOVERNANCE REGISTRY UPDATE
-- ============================================================================

-- Update IoS-005 to reflect recalibration pathway activation
UPDATE fhq_meta.ios_registry
SET
    description = 'Scientific validation layer for FjordHQ. Measures statistical significance of regime-driven allocations via bootstrap/permutation tests. Computes FjordHQ Skill Score (FSS). RECALIBRATION PATHWAY ACTIVE for IoS-007 edge weight governance.',
    dependencies = ARRAY['IoS-001', 'IoS-002', 'IoS-003', 'IoS-004', 'IoS-007'],
    updated_at = NOW()
WHERE ios_id = 'IoS-005';

-- ============================================================================
-- 9. OPERATION SIGNATURE
-- ============================================================================

INSERT INTO vision_verification.operation_signatures (
    signature_id,
    operation_type,
    operation_id,
    operation_table,
    operation_schema,
    signing_agent,
    signing_key_id,
    signature_value,
    signed_payload,
    verified,
    verified_at,
    verified_by,
    created_at,
    hash_chain_id
)
VALUES (
    gen_random_uuid(),
    'IOS005_RECALIBRATION_PATHWAY_ACTIVATION',
    gen_random_uuid(),
    'recalibration_requests',
    'fhq_research',
    'STIG',
    'STIG-EC003-IOS005-RECAL',
    encode(sha256(('IOS005-RECAL-PATHWAY-' || NOW()::text)::bytea), 'hex'),
    '{
        "ios_id": "IoS-005",
        "extension": "RECALIBRATION_PATHWAY",
        "target_ios": "IoS-007",
        "tables_created": ["recalibration_requests", "recalibration_audit_log"],
        "functions_created": ["calculate_fss", "execute_recalibration", "create_recalibration_request"],
        "pathway_status": "ACTIVE_PENDING_G4_UNLOCK"
    }'::jsonb,
    TRUE,
    NOW(),
    'VEGA',
    NOW(),
    'HC-IOS-005-2026'
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT 'Recalibration Pathway Tables' as check_type, COUNT(*) as count
FROM information_schema.tables
WHERE table_schema = 'fhq_research' AND table_name IN ('recalibration_requests', 'recalibration_audit_log');

SELECT 'Recalibration Functions' as check_type, COUNT(*) as count
FROM information_schema.routines
WHERE routine_schema = 'fhq_research' AND routine_name IN ('calculate_fss', 'execute_recalibration', 'create_recalibration_request');
