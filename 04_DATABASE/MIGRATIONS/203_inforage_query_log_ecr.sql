-- Migration 203: InForage Query Log ECR Column
-- CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001 Phase A Step 7
-- Author: STIG (CTO)
-- Date: 2026-01-04
--
-- Purpose: Add evidence_coverage_ratio and result_type columns to inforage_query_log
-- for production metrics (ECR and NO_SIGNAL rate monitoring).

BEGIN;

-- 1. Add evidence_coverage_ratio column
ALTER TABLE fhq_governance.inforage_query_log
ADD COLUMN IF NOT EXISTS evidence_coverage_ratio FLOAT;

-- 2. Add result_type column (for NO_SIGNAL tracking)
ALTER TABLE fhq_governance.inforage_query_log
ADD COLUMN IF NOT EXISTS result_type VARCHAR(20);

-- 3. Add retrieved_snippet_count for ECR calculation
ALTER TABLE fhq_governance.inforage_query_log
ADD COLUMN IF NOT EXISTS retrieved_snippet_count INT;

-- 4. Add bundle_id for court-proof tracing
ALTER TABLE fhq_governance.inforage_query_log
ADD COLUMN IF NOT EXISTS bundle_id UUID;

-- 5. Add comments
COMMENT ON COLUMN fhq_governance.inforage_query_log.evidence_coverage_ratio IS
    'ECR = retrieved_snippets / expected_minimum (3). CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001';

COMMENT ON COLUMN fhq_governance.inforage_query_log.result_type IS
    'SIGNAL or NO_SIGNAL - for NO_SIGNAL rate monitoring';

COMMENT ON COLUMN fhq_governance.inforage_query_log.retrieved_snippet_count IS
    'Number of evidence snippets retrieved for ECR calculation';

COMMENT ON COLUMN fhq_governance.inforage_query_log.bundle_id IS
    'FK to evidence_bundles for court-proof tracing';

-- 6. Create index for result_type analysis
CREATE INDEX IF NOT EXISTS idx_inforage_query_log_result_type
ON fhq_governance.inforage_query_log (result_type, created_at DESC);

-- 7. Create index for ECR monitoring
CREATE INDEX IF NOT EXISTS idx_inforage_query_log_ecr
ON fhq_governance.inforage_query_log (evidence_coverage_ratio, created_at DESC)
WHERE evidence_coverage_ratio IS NOT NULL;

COMMIT;

-- Verification query
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'fhq_governance'
  AND table_name = 'inforage_query_log'
  AND column_name IN ('evidence_coverage_ratio', 'result_type', 'retrieved_snippet_count', 'bundle_id')
ORDER BY column_name;
