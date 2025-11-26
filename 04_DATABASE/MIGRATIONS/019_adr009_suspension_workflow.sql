-- =====================================================
-- MIGRATION 019: ADR-009 AGENT SUSPENSION WORKFLOW
-- =====================================================
--
-- Authority: LARS (ADR-009 Governance Approval Workflow for Agent Suspension)
-- Purpose: Create governance infrastructure for dual-approval agent suspension
-- Compliance: ADR-009, ADR-010, ADR-007, ADR-008
-- Constitutional Authority: ADR-001 -> ADR-002 -> ADR-006 -> ADR-007 -> ADR-008 -> EC-001
--
-- This migration creates:
--   1. fhq_governance.agent_suspension_requests - Suspension request records
--   2. fhq_governance.suspension_audit_log - Immutable audit trail
--   3. Indexes for efficient query patterns
--
-- ADR-009 Key Requirements:
--   - VEGA can only RECOMMEND suspension (never enforce)
--   - CEO (or delegate) must APPROVE/REJECT
--   - All decisions logged with hash-linked evidence
--   - Worker must check agent status before task execution
--
-- =====================================================

BEGIN;

-- =====================================================
-- SCHEMA VERIFICATION
-- =====================================================

-- Ensure required schemas exist
CREATE SCHEMA IF NOT EXISTS fhq_governance;
CREATE SCHEMA IF NOT EXISTS fhq_org;
CREATE SCHEMA IF NOT EXISTS fhq_meta;

-- =====================================================
-- 9.1: AGENT SUSPENSION REQUESTS TABLE
-- =====================================================

-- ADR-009 Section 5.2: Suspension Request Record
-- Each request stores comprehensive evidence and workflow state

CREATE TABLE IF NOT EXISTS fhq_governance.agent_suspension_requests (
    -- Primary Key
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Agent identification
    agent_id TEXT NOT NULL REFERENCES fhq_org.org_agents(agent_id),

    -- Request originator (normally VEGA for automatic recommendations)
    requested_by TEXT NOT NULL REFERENCES fhq_org.org_agents(agent_id),

    -- Request details
    reason TEXT NOT NULL,
    discrepancy_score NUMERIC(6,5) NOT NULL CHECK (discrepancy_score >= 0 AND discrepancy_score <= 1.0),

    -- Evidence bundle (JSONB) - includes:
    --   - state_snapshots: snapshot_ids from reconciliation
    --   - metrics: discrepancy metrics at detection time
    --   - signatures: cryptographic signatures (ADR-008)
    --   - timestamps: all relevant timestamps
    --   - reconciliation_data: ADR-010 reconciliation output
    evidence JSONB NOT NULL,

    -- Workflow status (ADR-009 Section 5.2)
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),

    -- Review details (filled by CEO on APPROVE/REJECT)
    reviewed_by TEXT REFERENCES fhq_org.org_agents(agent_id),
    reviewed_at TIMESTAMPTZ,
    review_rationale TEXT,

    -- Hash chain for immutability (ADR-008)
    evidence_hash TEXT NOT NULL,
    hash_chain_id TEXT NOT NULL,

    -- Cryptographic signature of request
    request_signature TEXT NOT NULL,
    signature_verified BOOLEAN DEFAULT FALSE,

    -- ADR references
    adr_reference TEXT NOT NULL DEFAULT 'ADR-009',
    discrepancy_threshold NUMERIC(6,5) NOT NULL DEFAULT 0.10,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Performance indexes per ADR-009 Section 6.1
CREATE INDEX IF NOT EXISTS idx_suspension_requests_agent_status
    ON fhq_governance.agent_suspension_requests(agent_id, status);

CREATE INDEX IF NOT EXISTS idx_suspension_requests_created
    ON fhq_governance.agent_suspension_requests(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_suspension_requests_status
    ON fhq_governance.agent_suspension_requests(status);

CREATE INDEX IF NOT EXISTS idx_suspension_requests_pending
    ON fhq_governance.agent_suspension_requests(status)
    WHERE status = 'PENDING';

CREATE INDEX IF NOT EXISTS idx_suspension_requests_requested_by
    ON fhq_governance.agent_suspension_requests(requested_by);

CREATE INDEX IF NOT EXISTS idx_suspension_requests_reviewed_by
    ON fhq_governance.agent_suspension_requests(reviewed_by)
    WHERE reviewed_by IS NOT NULL;

COMMENT ON TABLE fhq_governance.agent_suspension_requests IS
    'ADR-009 Section 5.2: Agent suspension request records with dual-approval workflow';

COMMENT ON COLUMN fhq_governance.agent_suspension_requests.status IS
    'Workflow status: PENDING (awaiting CEO review), APPROVED (suspension enforced), REJECTED (override logged)';

COMMENT ON COLUMN fhq_governance.agent_suspension_requests.evidence IS
    'JSONB evidence bundle: state_snapshots, metrics, signatures, timestamps, reconciliation_data';

-- =====================================================
-- 9.2: SUSPENSION AUDIT LOG TABLE
-- =====================================================

-- Immutable audit trail for all suspension-related actions
-- Provides non-repudiation per ADR-008

CREATE TABLE IF NOT EXISTS fhq_governance.suspension_audit_log (
    -- Primary Key
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to suspension request
    request_id UUID NOT NULL REFERENCES fhq_governance.agent_suspension_requests(request_id),

    -- Action details
    action_type TEXT NOT NULL CHECK (action_type IN (
        'REQUEST_CREATED',      -- VEGA created suspension request
        'CEO_APPROVED',         -- CEO approved suspension
        'CEO_REJECTED',         -- CEO rejected suspension
        'SUSPENSION_ENFORCED',  -- Agent status set to SUSPENDED
        'AGENT_REINSTATED',     -- Agent manually reinstated
        'EVIDENCE_UPDATED',     -- Additional evidence added
        'NOTIFICATION_SENT'     -- LARS/CEO notification sent
    )),

    -- Actor information
    performed_by TEXT NOT NULL REFERENCES fhq_org.org_agents(agent_id),

    -- Action metadata
    action_data JSONB NOT NULL,

    -- Cryptographic proof (ADR-008)
    action_hash TEXT NOT NULL,
    previous_audit_id UUID REFERENCES fhq_governance.suspension_audit_log(audit_id),
    signature TEXT NOT NULL,

    -- Timestamp
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_suspension_audit_request
    ON fhq_governance.suspension_audit_log(request_id);

CREATE INDEX IF NOT EXISTS idx_suspension_audit_timestamp
    ON fhq_governance.suspension_audit_log(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_suspension_audit_action_type
    ON fhq_governance.suspension_audit_log(action_type);

CREATE INDEX IF NOT EXISTS idx_suspension_audit_performed_by
    ON fhq_governance.suspension_audit_log(performed_by);

COMMENT ON TABLE fhq_governance.suspension_audit_log IS
    'ADR-009 Section 5: Immutable audit trail for all suspension workflow actions';

-- =====================================================
-- 9.3: UPDATE TRIGGER FOR TIMESTAMPS
-- =====================================================

CREATE OR REPLACE FUNCTION fhq_governance.update_suspension_request_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_suspension_request_updated
    ON fhq_governance.agent_suspension_requests;

CREATE TRIGGER trigger_suspension_request_updated
    BEFORE UPDATE ON fhq_governance.agent_suspension_requests
    FOR EACH ROW
    EXECUTE FUNCTION fhq_governance.update_suspension_request_timestamp();

-- =====================================================
-- 9.4: HELPER FUNCTIONS FOR SUSPENSION WORKFLOW
-- =====================================================

-- Function: Check if agent has pending suspension request
CREATE OR REPLACE FUNCTION fhq_governance.has_pending_suspension(p_agent_id TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM fhq_governance.agent_suspension_requests
        WHERE agent_id = p_agent_id AND status = 'PENDING'
    );
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION fhq_governance.has_pending_suspension(TEXT) IS
    'ADR-009: Check if an agent has a pending suspension request awaiting CEO review';

-- Function: Get agent suspension status (consolidated view)
CREATE OR REPLACE FUNCTION fhq_governance.get_agent_suspension_status(p_agent_id TEXT)
RETURNS TABLE (
    agent_id TEXT,
    is_suspended BOOLEAN,
    has_pending_request BOOLEAN,
    pending_request_id UUID,
    last_suspension_request_at TIMESTAMPTZ,
    discrepancy_score NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.agent_id,
        a.is_suspended,
        EXISTS (
            SELECT 1 FROM fhq_governance.agent_suspension_requests r
            WHERE r.agent_id = a.agent_id AND r.status = 'PENDING'
        ) AS has_pending_request,
        (
            SELECT r.request_id FROM fhq_governance.agent_suspension_requests r
            WHERE r.agent_id = a.agent_id AND r.status = 'PENDING'
            ORDER BY r.created_at DESC LIMIT 1
        ) AS pending_request_id,
        (
            SELECT MAX(r.created_at) FROM fhq_governance.agent_suspension_requests r
            WHERE r.agent_id = a.agent_id
        ) AS last_suspension_request_at,
        (
            SELECT r.discrepancy_score FROM fhq_governance.agent_suspension_requests r
            WHERE r.agent_id = a.agent_id AND r.status = 'PENDING'
            ORDER BY r.created_at DESC LIMIT 1
        ) AS discrepancy_score
    FROM fhq_org.org_agents a
    WHERE a.agent_id = p_agent_id;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION fhq_governance.get_agent_suspension_status(TEXT) IS
    'ADR-009: Get comprehensive suspension status for an agent';

-- Function: List all pending suspension requests (for CEO dashboard)
CREATE OR REPLACE FUNCTION fhq_governance.list_pending_suspension_requests()
RETURNS TABLE (
    request_id UUID,
    agent_id TEXT,
    agent_name TEXT,
    requested_by TEXT,
    reason TEXT,
    discrepancy_score NUMERIC,
    created_at TIMESTAMPTZ,
    evidence_summary JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        r.request_id,
        r.agent_id,
        a.agent_name,
        r.requested_by,
        r.reason,
        r.discrepancy_score,
        r.created_at,
        jsonb_build_object(
            'threshold_exceeded', r.discrepancy_score > r.discrepancy_threshold,
            'threshold', r.discrepancy_threshold,
            'adr_reference', r.adr_reference
        ) AS evidence_summary
    FROM fhq_governance.agent_suspension_requests r
    JOIN fhq_org.org_agents a ON r.agent_id = a.agent_id
    WHERE r.status = 'PENDING'
    ORDER BY r.created_at DESC;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION fhq_governance.list_pending_suspension_requests() IS
    'ADR-009 Section 5.3: List all pending suspension requests for CEO review';

-- =====================================================
-- 9.5: VIEW FOR SUSPENSION REQUEST OVERVIEW
-- =====================================================

CREATE OR REPLACE VIEW fhq_governance.v_suspension_requests_overview AS
SELECT
    r.request_id,
    r.agent_id,
    a.agent_name,
    a.agent_role,
    r.requested_by,
    req_agent.agent_name AS requested_by_name,
    r.reason,
    r.discrepancy_score,
    r.discrepancy_threshold,
    r.status,
    r.reviewed_by,
    rev_agent.agent_name AS reviewed_by_name,
    r.reviewed_at,
    r.review_rationale,
    r.created_at,
    r.updated_at,
    CASE
        WHEN r.status = 'PENDING' THEN NOW() - r.created_at
        ELSE r.updated_at - r.created_at
    END AS time_in_workflow,
    a.is_suspended AS agent_currently_suspended
FROM fhq_governance.agent_suspension_requests r
JOIN fhq_org.org_agents a ON r.agent_id = a.agent_id
JOIN fhq_org.org_agents req_agent ON r.requested_by = req_agent.agent_id
LEFT JOIN fhq_org.org_agents rev_agent ON r.reviewed_by = rev_agent.agent_id
ORDER BY r.created_at DESC;

COMMENT ON VIEW fhq_governance.v_suspension_requests_overview IS
    'ADR-009: Comprehensive view of all suspension requests with agent details';

-- =====================================================
-- 9.6: GOVERNANCE METRICS VIEW
-- =====================================================

CREATE OR REPLACE VIEW fhq_governance.v_suspension_metrics AS
SELECT
    COUNT(*) FILTER (WHERE status = 'PENDING') AS pending_requests,
    COUNT(*) FILTER (WHERE status = 'APPROVED') AS approved_requests,
    COUNT(*) FILTER (WHERE status = 'REJECTED') AS rejected_requests,
    COUNT(*) AS total_requests,
    AVG(CASE WHEN status != 'PENDING' THEN EXTRACT(EPOCH FROM (updated_at - created_at)) END) AS avg_review_time_seconds,
    MAX(discrepancy_score) AS max_discrepancy_score,
    AVG(discrepancy_score) AS avg_discrepancy_score,
    COUNT(DISTINCT agent_id) AS unique_agents_flagged
FROM fhq_governance.agent_suspension_requests;

COMMENT ON VIEW fhq_governance.v_suspension_metrics IS
    'ADR-009: Aggregate metrics for suspension workflow monitoring';

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================

-- Verify table created correctly
DO $$
DECLARE
    table_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'fhq_governance'
        AND table_name = 'agent_suspension_requests'
    ) INTO table_exists;

    IF NOT table_exists THEN
        RAISE EXCEPTION 'agent_suspension_requests table was not created';
    END IF;

    RAISE NOTICE '9.1 Table verification: agent_suspension_requests created';
END $$;

-- Verify audit log table created
DO $$
DECLARE
    table_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'fhq_governance'
        AND table_name = 'suspension_audit_log'
    ) INTO table_exists;

    IF NOT table_exists THEN
        RAISE EXCEPTION 'suspension_audit_log table was not created';
    END IF;

    RAISE NOTICE '9.2 Table verification: suspension_audit_log created';
END $$;

-- Verify indexes created
DO $$
DECLARE
    index_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes
    WHERE tablename = 'agent_suspension_requests'
    AND schemaname = 'fhq_governance';

    IF index_count < 6 THEN
        RAISE WARNING '9.1 Index verification: Only % indexes created, expected at least 6', index_count;
    ELSE
        RAISE NOTICE '9.1 Index verification: % indexes created', index_count;
    END IF;
END $$;

-- Verify helper functions exist
DO $$
DECLARE
    func_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO func_count
    FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname = 'fhq_governance'
    AND p.proname IN ('has_pending_suspension', 'get_agent_suspension_status', 'list_pending_suspension_requests');

    IF func_count < 3 THEN
        RAISE WARNING '9.4 Function verification: Only % functions created', func_count;
    ELSE
        RAISE NOTICE '9.4 Function verification: All % helper functions created', func_count;
    END IF;
END $$;

COMMIT;

-- =====================================================
-- MIGRATION SUMMARY
-- =====================================================

SELECT
    'MIGRATION 019 COMPLETE' AS status,
    'ADR-009 Agent Suspension Workflow' AS description,
    NOW() AS completed_at;

\echo ''
\echo '=========================================='
\echo 'MIGRATION 019: ADR-009 AGENT SUSPENSION WORKFLOW'
\echo '=========================================='
\echo 'Tables created:'
\echo '  - fhq_governance.agent_suspension_requests (9.1)'
\echo '  - fhq_governance.suspension_audit_log (9.2)'
\echo ''
\echo 'Functions created:'
\echo '  - fhq_governance.has_pending_suspension()'
\echo '  - fhq_governance.get_agent_suspension_status()'
\echo '  - fhq_governance.list_pending_suspension_requests()'
\echo ''
\echo 'Views created:'
\echo '  - fhq_governance.v_suspension_requests_overview'
\echo '  - fhq_governance.v_suspension_metrics'
\echo ''
\echo 'ADR-009 Workflow:'
\echo '  1. VEGA detects discrepancy_score > 0.10'
\echo '  2. VEGA creates PENDING suspension request'
\echo '  3. CEO reviews and APPROVES or REJECTS'
\echo '  4. On APPROVE: Agent status set to SUSPENDED'
\echo '  5. Worker respects suspended status'
\echo '=========================================='
\echo ''
\echo 'Next step: Implement VEGA suspension recommendation function'
\echo '  python 04_AGENTS/PHASE3/vega_suspension_workflow.py'
\echo ''
