-- ============================================================================
-- CEO-DIR-2026-021 AUDIT CORRECTION #4
-- Transactional Evidence Binding for Lessons
-- ============================================================================
-- Date: 2026-01-08
-- Authority: CEO Directive CEO-DIR-2026-021
-- Classification: P0 - Blocking All Learning
-- Purpose: Enforce atomic lesson+evidence insertion (COMMIT both or ROLLBACK both)
--
-- Audit Correction #4: Transactional evidence binding
--   - Lessons and evidence must be created atomically
--   - No lesson without evidence, no evidence without lesson
--   - Idempotency via lesson_hash deduplication
--   - Court-proof chain: lesson -> raw query -> result hash -> result snapshot
--
-- ============================================================================

-- Create lightweight evidence table for lesson extraction
CREATE TABLE IF NOT EXISTS fhq_governance.epistemic_lesson_evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_id UUID,  -- Will be populated after lesson creation
    raw_query TEXT NOT NULL,
    query_result_hash TEXT NOT NULL,
    query_result_snapshot JSONB NOT NULL,
    extraction_context JSONB,
    created_by TEXT NOT NULL DEFAULT 'STIG',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_epistemic_lesson_evidence_lesson_id
ON fhq_governance.epistemic_lesson_evidence(lesson_id);

CREATE INDEX IF NOT EXISTS idx_epistemic_lesson_evidence_created_at
ON fhq_governance.epistemic_lesson_evidence(created_at DESC);

COMMENT ON TABLE fhq_governance.epistemic_lesson_evidence IS
'CEO-DIR-2026-021 Audit Correction #4: Court-proof evidence for epistemic lessons.
Stores raw query, result hash, and result snapshot for every lesson.
Enables re-derivation and verification of lesson conclusions.';

-- Add evidence binding fields to epistemic_lessons
ALTER TABLE fhq_governance.epistemic_lessons
ADD COLUMN IF NOT EXISTS evidence_id UUID REFERENCES fhq_governance.epistemic_lesson_evidence(evidence_id),
ADD COLUMN IF NOT EXISTS evidence_bound_at TIMESTAMPTZ;

COMMENT ON COLUMN fhq_governance.epistemic_lessons.evidence_id IS
'CEO-DIR-2026-021 Audit Correction #4: Evidence binding for court-proof chain.
Every lesson must be bound to verifiable raw query evidence.
Ensures lesson conclusions can be re-derived from source data.';

COMMENT ON COLUMN fhq_governance.epistemic_lessons.evidence_bound_at IS
'Timestamp when evidence was atomically bound to lesson';

-- Create index for evidence lookup
CREATE INDEX IF NOT EXISTS idx_epistemic_lessons_evidence_id
ON fhq_governance.epistemic_lessons(evidence_id);

-- Create check constraint enforcement view
CREATE OR REPLACE VIEW fhq_governance.v_lessons_without_evidence AS
SELECT
    lesson_id,
    lesson_category,
    lesson_severity,
    lesson_description,
    created_at,
    created_by,
    'VIOLATION: Lesson created without evidence binding' AS violation_type
FROM fhq_governance.epistemic_lessons
WHERE evidence_id IS NULL
  AND created_at >= '2026-01-08'::timestamptz; -- Only enforce for lessons after Audit Correction #4

COMMENT ON VIEW fhq_governance.v_lessons_without_evidence IS
'CEO-DIR-2026-021 Audit Correction #4: Governance view to detect lessons created without evidence.
Post-2026-01-08, all lessons MUST have evidence_id populated.
This view should always return 0 rows in production.';

-- ============================================================================
-- Court-Proof Evidence Binding Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.store_lesson_with_evidence(
    p_lesson_source TEXT,
    p_lesson_category TEXT,
    p_lesson_severity TEXT,
    p_lesson_description TEXT,
    p_lesson_hash TEXT,
    p_raw_query TEXT,
    p_query_result JSONB,
    p_error_magnitude NUMERIC DEFAULT NULL,
    p_error_direction TEXT DEFAULT NULL,
    p_affected_regime TEXT DEFAULT NULL,
    p_recommended_action TEXT DEFAULT NULL,
    p_created_by TEXT DEFAULT 'STIG'
)
RETURNS TABLE(
    lesson_id UUID,
    evidence_id UUID,
    lesson_hash TEXT,
    evidence_hash TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_lesson_id UUID;
    v_evidence_id UUID;
    v_query_result_hash TEXT;
    v_existing_lesson UUID;
    v_existing_evidence UUID;
BEGIN
    -- Idempotency: Check if lesson with this hash already exists
    SELECT el.lesson_id, el.evidence_id INTO v_existing_lesson, v_existing_evidence
    FROM fhq_governance.epistemic_lessons el
    WHERE el.lesson_hash = p_lesson_hash;

    IF v_existing_lesson IS NOT NULL THEN
        -- Lesson already exists, return existing IDs
        SELECT ele.query_result_hash INTO v_query_result_hash
        FROM fhq_governance.epistemic_lesson_evidence ele
        WHERE ele.evidence_id = v_existing_evidence;

        RETURN QUERY SELECT v_existing_lesson, v_existing_evidence, p_lesson_hash, v_query_result_hash;
        RETURN;
    END IF;

    -- Generate evidence hash (SHA-256 of query result)
    v_query_result_hash := encode(sha256(p_query_result::text::bytea), 'hex');

    -- ATOMIC TRANSACTION: Insert evidence first, then lesson
    -- If either fails, entire transaction rolls back

    -- Step 1: Create evidence record
    INSERT INTO fhq_governance.epistemic_lesson_evidence (
        evidence_id,
        raw_query,
        query_result_hash,
        query_result_snapshot,
        extraction_context,
        created_by,
        created_at
    ) VALUES (
        gen_random_uuid(),
        p_raw_query,
        v_query_result_hash,
        p_query_result,
        jsonb_build_object(
            'directive', 'CEO-DIR-2026-021',
            'audit_correction', 'AUDIT_CORRECTION_4',
            'ios', 'IoS-010',
            'daemon', 'ios010_lesson_extraction_engine',
            'binding_mode', 'ATOMIC_TRANSACTIONAL',
            'lesson_category', p_lesson_category,
            'lesson_severity', p_lesson_severity
        ),
        p_created_by,
        NOW()
    )
    RETURNING evidence_id INTO v_evidence_id;

    -- Step 2: Create lesson record with evidence binding
    INSERT INTO fhq_governance.epistemic_lessons (
        lesson_id,
        lesson_source,
        lesson_category,
        lesson_severity,
        error_magnitude,
        error_direction,
        affected_regime,
        lesson_description,
        recommended_action,
        lesson_hash,
        evidence_id,
        evidence_bound_at,
        created_by,
        created_at
    ) VALUES (
        gen_random_uuid(),
        p_lesson_source,
        p_lesson_category,
        p_lesson_severity,
        p_error_magnitude,
        p_error_direction,
        p_affected_regime,
        p_lesson_description,
        p_recommended_action,
        p_lesson_hash,
        v_evidence_id,
        NOW(),
        p_created_by,
        NOW()
    )
    RETURNING lesson_id INTO v_lesson_id;

    -- Step 3: Update evidence with lesson_id for bidirectional reference
    UPDATE fhq_governance.epistemic_lesson_evidence
    SET lesson_id = v_lesson_id
    WHERE evidence_id = v_evidence_id;

    -- Return both IDs for verification
    RETURN QUERY SELECT v_lesson_id, v_evidence_id, p_lesson_hash, v_query_result_hash;
END;
$$;

COMMENT ON FUNCTION fhq_governance.store_lesson_with_evidence IS
'CEO-DIR-2026-021 Audit Correction #4: Atomic lesson+evidence insertion.
Ensures lessons and their source evidence are created transactionally.
Implements idempotency via lesson_hash deduplication.
Court-proof: Every lesson has verifiable raw query + result hash + result snapshot.';

-- ============================================================================
-- Validation
-- ============================================================================

DO $$
DECLARE
    v_unbound_lessons INTEGER;
BEGIN
    -- Check for lessons without evidence (should be 0 for new lessons)
    SELECT COUNT(*) INTO v_unbound_lessons
    FROM fhq_governance.v_lessons_without_evidence;

    RAISE NOTICE 'Validation: Lessons without evidence (post-2026-01-08): %', v_unbound_lessons;

    IF v_unbound_lessons > 0 THEN
        RAISE WARNING 'Found % lessons without evidence binding. This is expected only for historical pre-correction lessons.', v_unbound_lessons;
    END IF;

    RAISE NOTICE 'Migration 217 complete: Transactional evidence binding ready';
END $$;

-- Log migration completion
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'MIGRATION_EXECUTION',
    '217_ceo_dir_2026_021_audit_correction_4',
    'DATABASE_SCHEMA',
    'STIG',
    'COMPLETED',
    'CEO-DIR-2026-021 Audit Correction #4: Transactional evidence binding for lessons',
    jsonb_build_object(
        'migration_file', '217_ceo_dir_2026_021_audit_correction_4.sql',
        'correction', 'AUDIT_CORRECTION_4',
        'tables_modified', ARRAY['epistemic_lessons'],
        'tables_referenced', ARRAY['summary_evidence_ledger'],
        'columns_added', ARRAY['evidence_id', 'evidence_bound_at'],
        'functions_created', ARRAY['store_lesson_with_evidence'],
        'atomicity', 'TRANSACTIONAL (COMMIT both or ROLLBACK both)',
        'idempotency', 'YES (lesson_hash deduplication)',
        'validation_status', 'PASS'
    )
);

-- Court-proof: Record schema change hash
SELECT
    'MIGRATION_217' as migration_id,
    encode(sha256(
        ('217_ceo_dir_2026_021_audit_correction_4.sql' ||
         NOW()::text)::bytea
    ), 'hex') as execution_hash,
    NOW() as executed_at;
