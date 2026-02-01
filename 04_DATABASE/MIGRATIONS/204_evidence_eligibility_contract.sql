-- Migration 204: Evidence Eligibility Schema Contract
-- CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001 Pre-condition #2
-- Author: STIG (CTO)
-- Date: 2026-01-04
--
-- Purpose: Guarantees court_proof_verified, source_preference, trusted, quarantined
-- fields exist with safe defaults, so the injection gate is enforceable by
-- database truth, not by convention.

BEGIN;

-- 1. Add eligibility fields to evidence_nodes (if not exist)
ALTER TABLE fhq_canonical.evidence_nodes
ADD COLUMN IF NOT EXISTS court_proof_verified BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE fhq_canonical.evidence_nodes
ADD COLUMN IF NOT EXISTS source_preference INT NOT NULL DEFAULT 999;

ALTER TABLE fhq_canonical.evidence_nodes
ADD COLUMN IF NOT EXISTS trusted BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE fhq_canonical.evidence_nodes
ADD COLUMN IF NOT EXISTS quarantined BOOLEAN NOT NULL DEFAULT FALSE;

-- 2. Create index for retrieval eligibility predicate
-- This partial index optimizes the eligibility gate query
CREATE INDEX IF NOT EXISTS idx_evidence_nodes_retrieval_eligible
ON fhq_canonical.evidence_nodes (court_proof_verified, trusted, quarantined)
WHERE court_proof_verified = TRUE
  AND quarantined = FALSE;

-- 3. Add documentation comments
COMMENT ON COLUMN fhq_canonical.evidence_nodes.court_proof_verified IS
  'TRUE if evidence has passed court-proof validation. Required for Qdrant sync.';

COMMENT ON COLUMN fhq_canonical.evidence_nodes.source_preference IS
  'Lower = more trusted. 0=constitutional, 1=CEO, 10=automated. Default 999=untrusted.';

COMMENT ON COLUMN fhq_canonical.evidence_nodes.trusted IS
  'Explicit trust flag. Overrides source_preference threshold check.';

COMMENT ON COLUMN fhq_canonical.evidence_nodes.quarantined IS
  'TRUE if evidence is flagged for review. Excluded from all retrieval.';

-- 4. Add constraint: quarantined evidence cannot be court_proof_verified
-- This is a business rule: if evidence is quarantined, it cannot also be verified
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_quarantine_not_verified'
    ) THEN
        ALTER TABLE fhq_canonical.evidence_nodes
        ADD CONSTRAINT chk_quarantine_not_verified
        CHECK (NOT (quarantined = TRUE AND court_proof_verified = TRUE));
    END IF;
END $$;

-- 5. Mark existing evidence as court_proof_verified if they have content_hash
-- Evidence with content_hash is considered to have passed court-proof validation
UPDATE fhq_canonical.evidence_nodes
SET court_proof_verified = TRUE,
    source_preference = 10,  -- Automated but verified
    trusted = TRUE
WHERE content_hash IS NOT NULL
  AND court_proof_verified = FALSE;

-- 6. Migration logged via evidence file system (CEO-DIR-2025-12-20)
-- Evidence stored in: 03_FUNCTIONS/evidence/MIGRATION_204_*.json

COMMIT;

-- Verification query
SELECT
    COUNT(*) AS total_evidence,
    COUNT(*) FILTER (WHERE court_proof_verified = TRUE) AS verified_count,
    COUNT(*) FILTER (WHERE trusted = TRUE) AS trusted_count,
    COUNT(*) FILTER (WHERE quarantined = TRUE) AS quarantined_count
FROM fhq_canonical.evidence_nodes;
