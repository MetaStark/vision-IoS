-- ============================================================================
-- MIGRATION 159: Canonical Document Ingestion
-- ============================================================================
-- Directive: CEO-DIR-2025-INGEST-001
-- Purpose: First-Order Truth Declaration for ADR, IoS, EC documents
-- Executor: STIG
-- Verifier: VEGA
-- ============================================================================

-- ============================================================================
-- FORBEHOLD 1: KONSTITUSJONELL FORANKRING
-- ============================================================================
-- Dette er LAYER 8 (Observability & Audit Layer), IKKE Layer 1.
-- Fil-dokumenter i 00_CONSTITUTION forblir ULTIMATE TRUTH.
-- canonical_documents er database-representasjon for ACI/VEGA queries.
-- ============================================================================

-- ============================================================================
-- FORBEHOLD 2: ÉN-VEIS AUTORITET
-- ============================================================================
-- Dataflyt: Fil → canonical_documents → adr_registry/ios_registry
-- INGEN tilbakeskriving til canonical_documents fra runtime registries.
-- ============================================================================

-- ============================================================================
-- FORBEHOLD 3: INGESTION ≠ AKTIVERING
-- ============================================================================
-- Dette gir LESBARHET, ikke operasjonell autoritet.
-- EC-018/020/021/022 forblir FROZEN etter ingestion.
-- ============================================================================

BEGIN;

-- Drop if exists (idempotent)
DROP TABLE IF EXISTS fhq_meta.canonical_documents CASCADE;

-- Create canonical document store
CREATE TABLE fhq_meta.canonical_documents (
    -- Identity
    document_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_type       TEXT NOT NULL CHECK (document_type IN ('ADR', 'IoS', 'EC', 'APPENDIX', 'SYNTHESIS')),
    document_code       TEXT NOT NULL UNIQUE,  -- e.g., 'ADR-001', 'IoS-003', 'EC-005'

    -- Content
    title               TEXT NOT NULL,
    version             TEXT NOT NULL DEFAULT '2026.PRODUCTION',
    status              TEXT NOT NULL CHECK (status IN ('ACTIVE', 'DRAFT', 'DEPRECATED', 'SUPERSEDED', 'FROZEN', 'RESERVED', 'FRAMEWORK_CHARTER')),
    tier                INTEGER CHECK (tier BETWEEN 1 AND 4),
    owner               TEXT NOT NULL,  -- CEO, VEGA, STIG, LARS, FINN, LINE, etc.

    -- First-Order Truth
    content_hash        TEXT NOT NULL,  -- SHA-256 of document content
    content_text        TEXT,           -- Full document text (first-order truth)
    source_path         TEXT NOT NULL,  -- Original file path

    -- Ingestion Metadata
    ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source              TEXT NOT NULL DEFAULT 'CANONICAL_DOCUMENT',
    ingestion_directive TEXT DEFAULT 'CEO-DIR-2025-INGEST-001',

    -- VEGA Attestation Binding
    vega_attested       BOOLEAN NOT NULL DEFAULT FALSE,
    vega_attestation_id UUID,  -- Will reference fhq_governance.vega_attestations

    -- Governance Links
    governing_adrs      TEXT[],         -- For IoS/EC: which ADRs govern this
    dependencies        TEXT[],         -- Document dependencies

    -- Extended Metadata
    metadata            JSONB DEFAULT '{}',

    -- Timestamps
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Comments for documentation
COMMENT ON TABLE fhq_meta.canonical_documents IS
'First-order truth store for constitutional documents. Per CEO-DIR-2025-INGEST-001.
LAYER 8: Observability & Audit Layer. NOT a replacement for Layer 1 file documents.
One-way authority: Files → canonical_documents → runtime registries.
Ingestion = readability only, NOT activation authority.';

COMMENT ON COLUMN fhq_meta.canonical_documents.content_text IS
'Full document text as first-order truth. ACI and VEGA may query this directly.';

COMMENT ON COLUMN fhq_meta.canonical_documents.content_hash IS
'SHA-256 hash of content_text for integrity verification.';

COMMENT ON COLUMN fhq_meta.canonical_documents.status IS
'Document status. FROZEN = cognitive engine not activated. See CEO-DIR-2025-ACT-001.';

-- Indexes for efficient querying
CREATE INDEX idx_canonical_docs_type ON fhq_meta.canonical_documents(document_type);
CREATE INDEX idx_canonical_docs_status ON fhq_meta.canonical_documents(status);
CREATE INDEX idx_canonical_docs_code ON fhq_meta.canonical_documents(document_code);
CREATE INDEX idx_canonical_docs_owner ON fhq_meta.canonical_documents(owner);
CREATE INDEX idx_canonical_docs_hash ON fhq_meta.canonical_documents(content_hash);

-- Full-text search index on content
CREATE INDEX idx_canonical_docs_content_fts ON fhq_meta.canonical_documents
USING gin(to_tsvector('english', COALESCE(content_text, '')));

-- GIN index on governing_adrs for array queries
CREATE INDEX idx_canonical_docs_governing ON fhq_meta.canonical_documents USING gin(governing_adrs);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION fhq_meta.update_canonical_documents_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_canonical_documents_updated
    BEFORE UPDATE ON fhq_meta.canonical_documents
    FOR EACH ROW
    EXECUTE FUNCTION fhq_meta.update_canonical_documents_timestamp();

-- ============================================================================
-- GOVERNANCE LOGGING
-- ============================================================================

-- Log this migration to governance_actions_log
INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    metadata,
    vega_reviewed
) VALUES (
    gen_random_uuid(),
    'SCHEMA_CREATION',
    'fhq_meta.canonical_documents',
    'MIGRATION_159',
    'STIG',
    NOW(),
    'EXECUTED',
    'CEO-DIR-2025-INGEST-001: Canonical Document Ingestion schema created. Layer 8 first-order truth store.',
    jsonb_build_object(
        'directive', 'CEO-DIR-2025-INGEST-001',
        'purpose', 'First-Order Truth Declaration',
        'layer', 8,
        'forbehold_1', 'Konstitusjonell forankring - Layer 8, ikke Layer 1',
        'forbehold_2', 'Én-veis autoritet - Fil → canonical → registry',
        'forbehold_3', 'Ingestion ≠ Aktivering - Kun lesbarhet',
        'target_documents', 54,
        'adr_count', 21,
        'ios_count', 15,
        'ec_count', 18
    ),
    false  -- Pending VEGA review
);

-- ============================================================================
-- NOTE: CEO Directives are NOT added to adr_registry (they are not ADRs)
-- The governance_actions_log entry above is the authoritative record
-- ============================================================================

COMMIT;

-- ============================================================================
-- VERIFICATION QUERY
-- ============================================================================
-- Run after migration:
-- SELECT
--     'canonical_documents created' as status,
--     (SELECT COUNT(*) FROM information_schema.tables
--      WHERE table_schema = 'fhq_meta' AND table_name = 'canonical_documents') as table_exists,
--     (SELECT COUNT(*) FROM information_schema.columns
--      WHERE table_schema = 'fhq_meta' AND table_name = 'canonical_documents') as column_count;
-- ============================================================================
