-- ============================================================================
-- MIGRATION 134: G1 CANONICAL RECONCILIATION INFRASTRUCTURE
-- ============================================================================
-- Authority: CEO DIRECTIVE — G1 DOCUMENT INGESTION & CANONICAL RECONCILIATION ORDER
-- Classification: G1 — Canonical Reconciliation Phase
-- Purpose: Infrastructure for systematic document-database reconciliation
-- ============================================================================

BEGIN;

-- ============================================================================
-- PRE-FLIGHT CHECK
-- ============================================================================
DO $$
DECLARE
    g1_active BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM fhq_meta.g1_activation_registry WHERE g1_status = 'ACTIVE'
    ) INTO g1_active;

    IF NOT g1_active THEN
        RAISE EXCEPTION 'G1 not active. Cannot establish reconciliation infrastructure.';
    END IF;

    RAISE NOTICE 'Pre-flight PASSED: G1 is ACTIVE';
END $$;

-- ============================================================================
-- SECTION 1: CANONICAL DOCUMENT REGISTRY (Enhanced)
-- ============================================================================

-- Update canonical_document_queue with reconciliation classification
ALTER TABLE fhq_meta.canonical_document_queue
ADD COLUMN IF NOT EXISTS reconciliation_status VARCHAR(20) DEFAULT 'PENDING'
    CHECK (reconciliation_status IN ('PENDING', 'ALIGNED', 'DIVERGENT', 'DEFERRED'));

ALTER TABLE fhq_meta.canonical_document_queue
ADD COLUMN IF NOT EXISTS claims_extracted INTEGER DEFAULT 0;

ALTER TABLE fhq_meta.canonical_document_queue
ADD COLUMN IF NOT EXISTS mismatches_found INTEGER DEFAULT 0;

ALTER TABLE fhq_meta.canonical_document_queue
ADD COLUMN IF NOT EXISTS reconciliation_timestamp TIMESTAMPTZ;

ALTER TABLE fhq_meta.canonical_document_queue
ADD COLUMN IF NOT EXISTS reconciliation_notes TEXT;

-- ============================================================================
-- SECTION 2: DOCUMENT CLAIMS REGISTRY
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.document_claims (
    claim_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Document Reference
    document_id UUID REFERENCES fhq_meta.canonical_document_queue(queue_id),
    document_path TEXT NOT NULL,
    document_section TEXT,

    -- Claim Details
    claim_type VARCHAR(50) NOT NULL
        CHECK (claim_type IN (
            'SCHEMA_REQUIRED', 'TABLE_REQUIRED', 'COLUMN_REQUIRED',
            'CONSTRAINT_REQUIRED', 'INDEX_REQUIRED', 'FUNCTION_REQUIRED',
            'ROLE_AUTHORITY', 'BEHAVIORAL_CONSTRAINT', 'GOVERNANCE_RULE',
            'WORKFLOW_STEP', 'INTEGRATION_REQUIREMENT', 'OTHER'
        )),
    claim_text TEXT NOT NULL,
    claim_context TEXT,

    -- Database Correspondence
    database_object_type VARCHAR(30),  -- 'TABLE', 'COLUMN', 'CONSTRAINT', 'FUNCTION', etc.
    database_object_name TEXT,
    database_schema TEXT,

    -- Verification Status
    verification_status VARCHAR(30) NOT NULL DEFAULT 'PENDING'
        CHECK (verification_status IN (
            'PENDING', 'PRESENT', 'ABSENT', 'PARTIAL', 'SEMANTICALLY_INCONSISTENT'
        )),
    verification_evidence TEXT,
    verification_timestamp TIMESTAMPTZ,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_document_claims_document ON fhq_meta.document_claims(document_id);
CREATE INDEX idx_document_claims_status ON fhq_meta.document_claims(verification_status);
CREATE INDEX idx_document_claims_type ON fhq_meta.document_claims(claim_type);

COMMENT ON TABLE fhq_meta.document_claims IS
'G1 Reconciliation: Explicit and implicit claims extracted from canonical documents. Each claim verified against database reality.';

-- ============================================================================
-- SECTION 3: CANONICAL MISMATCH REGISTRY
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.canonical_mismatches (
    mismatch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Reference
    claim_id UUID REFERENCES fhq_meta.document_claims(claim_id),
    document_path TEXT NOT NULL,

    -- Mismatch Details
    mismatch_type VARCHAR(50) NOT NULL
        CHECK (mismatch_type IN (
            'MISSING_SCHEMA', 'MISSING_TABLE', 'MISSING_COLUMN',
            'MISSING_CONSTRAINT', 'MISSING_FUNCTION', 'MISSING_INDEX',
            'SEMANTIC_DRIFT', 'PARTIAL_IMPLEMENTATION', 'CONFLICTING_DEFINITION',
            'DEPRECATED_REFERENCE', 'UNIMPLEMENTED_INTENT', 'OTHER'
        )),
    severity VARCHAR(20) NOT NULL DEFAULT 'MEDIUM'
        CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),

    -- Document Side
    document_claim TEXT NOT NULL,
    document_section TEXT,

    -- Database Side
    database_reality TEXT,
    database_evidence TEXT,

    -- Resolution Tracking (CEO Decision Required)
    resolution_status VARCHAR(30) NOT NULL DEFAULT 'UNRESOLVED'
        CHECK (resolution_status IN (
            'UNRESOLVED', 'FIX_DOCUMENT', 'FIX_DATABASE',
            'TOLERATE_BY_DESIGN', 'DEPRECATE', 'DEFERRED'
        )),
    resolution_decision_by VARCHAR(20),  -- Must be 'CEO' for resolution
    resolution_timestamp TIMESTAMPTZ,
    resolution_notes TEXT,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_canonical_mismatches_status ON fhq_meta.canonical_mismatches(resolution_status);
CREATE INDEX idx_canonical_mismatches_severity ON fhq_meta.canonical_mismatches(severity);
CREATE INDEX idx_canonical_mismatches_type ON fhq_meta.canonical_mismatches(mismatch_type);

COMMENT ON TABLE fhq_meta.canonical_mismatches IS
'G1 Reconciliation: All document-database mismatches. No remediation implied. Discovery precedes correction. CEO sole authority for resolution.';

-- ============================================================================
-- SECTION 4: G1 RECONCILIATION SUMMARY VIEW
-- ============================================================================

CREATE OR REPLACE VIEW fhq_meta.v_g1_reconciliation_summary AS
SELECT
    -- Document Counts by Category
    (SELECT COUNT(*) FROM fhq_meta.canonical_document_queue
     WHERE document_type = 'ADR') AS adr_documents,
    (SELECT COUNT(*) FROM fhq_meta.canonical_document_queue
     WHERE document_type = 'IOS') AS ios_documents,
    (SELECT COUNT(*) FROM fhq_meta.canonical_document_queue
     WHERE document_type IN ('DIRECTIVE', 'OTHER')) AS ec_documents,

    -- Classification Counts
    (SELECT COUNT(*) FROM fhq_meta.canonical_document_queue
     WHERE reconciliation_status = 'ALIGNED') AS aligned_count,
    (SELECT COUNT(*) FROM fhq_meta.canonical_document_queue
     WHERE reconciliation_status = 'DIVERGENT') AS divergent_count,
    (SELECT COUNT(*) FROM fhq_meta.canonical_document_queue
     WHERE reconciliation_status = 'DEFERRED') AS deferred_count,
    (SELECT COUNT(*) FROM fhq_meta.canonical_document_queue
     WHERE reconciliation_status = 'PENDING') AS pending_count,

    -- Claim Statistics
    (SELECT COUNT(*) FROM fhq_meta.document_claims) AS total_claims,
    (SELECT COUNT(*) FROM fhq_meta.document_claims
     WHERE verification_status = 'PRESENT') AS claims_verified,
    (SELECT COUNT(*) FROM fhq_meta.document_claims
     WHERE verification_status IN ('ABSENT', 'PARTIAL', 'SEMANTICALLY_INCONSISTENT')) AS claims_mismatched,

    -- Mismatch Statistics
    (SELECT COUNT(*) FROM fhq_meta.canonical_mismatches) AS total_mismatches,
    (SELECT COUNT(*) FROM fhq_meta.canonical_mismatches
     WHERE resolution_status = 'UNRESOLVED') AS unresolved_mismatches,
    (SELECT COUNT(*) FROM fhq_meta.canonical_mismatches
     WHERE severity = 'CRITICAL') AS critical_mismatches,

    -- G1 Exit Readiness
    CASE
        WHEN (SELECT COUNT(*) FROM fhq_meta.canonical_document_queue
              WHERE reconciliation_status = 'PENDING') = 0
         AND (SELECT COUNT(*) FROM fhq_meta.canonical_mismatches
              WHERE resolution_status = 'UNRESOLVED') = 0
        THEN true
        ELSE false
    END AS g1_exit_ready,

    NOW() AS summary_timestamp;

COMMENT ON VIEW fhq_meta.v_g1_reconciliation_summary IS
'G1 Reconciliation progress summary. G1 exit requires all documents reconciled and all mismatches explicitly addressed (not necessarily fixed).';

-- ============================================================================
-- SECTION 5: AUDIT LOG ENTRY
-- ============================================================================

INSERT INTO fhq_meta.adr_audit_log (
    change_proposal_id,
    adr_id,
    event_type,
    gate_stage,
    initiated_by,
    decision,
    resolution_notes,
    sha256_hash,
    hash_chain_id,
    metadata
) VALUES (
    'CP-G1-RECONCILIATION-INFRA-20251212',
    'CD-G1-ACTIVATION',
    'G1_TECHNICAL_VALIDATION',
    'G1',
    'CEO',
    'APPROVED',
    'G1 Canonical Reconciliation infrastructure established. Document claims registry, mismatch tracking, and reconciliation summary view created.',
    ENCODE(SHA256('G1-RECONCILIATION-INFRA-20251212'::bytea), 'hex'),
    'HC-G1-RECONCILIATION-INFRA-20251212',
    jsonb_build_object(
        'tables_created', ARRAY['document_claims', 'canonical_mismatches'],
        'views_created', ARRAY['v_g1_reconciliation_summary'],
        'document_scope', ARRAY['00_CONSTITUTION (ADR)', '02_IOS (IoS)', '10_EMPLOYMENT CONTRACTS (EC)'],
        'classification_options', ARRAY['ALIGNED', 'DIVERGENT', 'DEFERRED']
    )
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'MIGRATION 134: G1 CANONICAL RECONCILIATION INFRASTRUCTURE — VERIFICATION'
\echo '═══════════════════════════════════════════════════════════════════════════'

SELECT 'Infrastructure Tables:' as check_type;
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'fhq_meta'
  AND table_name IN ('document_claims', 'canonical_mismatches', 'canonical_document_queue');

SELECT 'Queue Columns Added:' as check_type;
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'fhq_meta'
  AND table_name = 'canonical_document_queue'
  AND column_name IN ('reconciliation_status', 'claims_extracted', 'mismatches_found');

SELECT 'Reconciliation Summary:' as check_type;
SELECT * FROM fhq_meta.v_g1_reconciliation_summary;

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'G1 CANONICAL RECONCILIATION INFRASTRUCTURE — READY'
\echo ''
\echo 'Discovery precedes correction.'
\echo '═══════════════════════════════════════════════════════════════════════════'
