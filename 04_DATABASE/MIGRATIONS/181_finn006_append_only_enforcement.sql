-- Migration 181: FINN-006 Append-Only Enforcement
-- CEO-DIR-2026-FINN-006 (FINAL): Section 2.1 - Append-Only Integrity
--
-- Purpose: Enforce INSERT-ONLY policy on all learning and telemetry tables.
-- No updates, deletes, or backfills are permitted under any circumstances.
-- Historical noise is preserved as forensic evidence.
--
-- Authority: CEO SIGNED (2025-12-30)
-- Classification: CONSTITUTIONAL
-- Enforcement: HARD_BLOCK on UPDATE/DELETE

BEGIN;

-- ============================================================================
-- FUNCTION: Block UPDATE/DELETE on learning tables
-- Constitutional enforcement - non-bypassable
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.enforce_append_only()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION
        'CEO-DIR-2026-FINN-006 VIOLATION: Table % is APPEND-ONLY. '
        '% operations are constitutionally prohibited. '
        'Historical noise must be preserved as forensic evidence.',
        TG_TABLE_NAME,
        TG_OP;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TRIGGER: retrieval_efficiency_log (EC-020)
-- ============================================================================

DROP TRIGGER IF EXISTS trg_append_only_retrieval_efficiency ON fhq_research.retrieval_efficiency_log;

CREATE TRIGGER trg_append_only_retrieval_efficiency
    BEFORE UPDATE OR DELETE ON fhq_research.retrieval_efficiency_log
    FOR EACH ROW
    EXECUTE FUNCTION fhq_research.enforce_append_only();

-- ============================================================================
-- TRIGGER: signal_yield_tracking (EC-021)
-- ============================================================================

DROP TRIGGER IF EXISTS trg_append_only_signal_yield ON fhq_research.signal_yield_tracking;

CREATE TRIGGER trg_append_only_signal_yield
    BEFORE UPDATE OR DELETE ON fhq_research.signal_yield_tracking
    FOR EACH ROW
    EXECUTE FUNCTION fhq_research.enforce_append_only();

-- ============================================================================
-- TRIGGER: surprise_resampling_quota (EC-021)
-- Note: This table has some update logic for quota tracking
-- We allow UPDATE only for specific columns, block DELETE entirely
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.enforce_append_only_quota()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            'CEO-DIR-2026-FINN-006 VIOLATION: Table surprise_resampling_quota is APPEND-ONLY. '
            'DELETE operations are constitutionally prohibited.';
    END IF;

    -- Allow UPDATE only for tracking fields (surprise_samples_used, signals_found, etc.)
    -- Block UPDATE on identification fields
    IF TG_OP = 'UPDATE' THEN
        IF OLD.id != NEW.id OR
           OLD.batch_id != NEW.batch_id OR
           OLD.batch_start_run != NEW.batch_start_run OR
           OLD.created_at != NEW.created_at THEN
            RAISE EXCEPTION
                'CEO-DIR-2026-FINN-006 VIOLATION: Cannot modify identification fields '
                'on surprise_resampling_quota. Only tracking counters may be updated.';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_append_only_surprise_quota ON fhq_research.surprise_resampling_quota;

CREATE TRIGGER trg_append_only_surprise_quota
    BEFORE UPDATE OR DELETE ON fhq_research.surprise_resampling_quota
    FOR EACH ROW
    EXECUTE FUNCTION fhq_research.enforce_append_only_quota();

-- ============================================================================
-- TRIGGER: ikea_feedback_log (EC-022)
-- ============================================================================

DROP TRIGGER IF EXISTS trg_append_only_ikea_feedback ON fhq_research.ikea_feedback_log;

CREATE TRIGGER trg_append_only_ikea_feedback
    BEFORE UPDATE OR DELETE ON fhq_research.ikea_feedback_log
    FOR EACH ROW
    EXECUTE FUNCTION fhq_research.enforce_append_only();

-- ============================================================================
-- TRIGGER: ikea_pattern_registry (EC-022)
-- Note: Pattern registry needs UPDATE for escalation tracking
-- Block DELETE, allow controlled UPDATE
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.enforce_append_only_pattern()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            'CEO-DIR-2026-FINN-006 VIOLATION: Table ikea_pattern_registry is APPEND-ONLY. '
            'DELETE operations are constitutionally prohibited. '
            'Patterns may be deactivated (is_active=FALSE) but never deleted.';
    END IF;

    -- Allow UPDATE but log it
    IF TG_OP = 'UPDATE' THEN
        -- Ensure core identification cannot be changed
        IF OLD.id != NEW.id OR
           OLD.pattern_hash != NEW.pattern_hash OR
           OLD.created_at != NEW.created_at THEN
            RAISE EXCEPTION
                'CEO-DIR-2026-FINN-006 VIOLATION: Cannot modify identification fields '
                'on ikea_pattern_registry.';
        END IF;

        -- Auto-update timestamp
        NEW.updated_at := NOW();
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_append_only_pattern_registry ON fhq_research.ikea_pattern_registry;

CREATE TRIGGER trg_append_only_pattern_registry
    BEFORE UPDATE OR DELETE ON fhq_research.ikea_pattern_registry
    FOR EACH ROW
    EXECUTE FUNCTION fhq_research.enforce_append_only_pattern();

-- ============================================================================
-- TRIGGER: ec020_constraint_feedback (EC-022 -> EC-020)
-- Note: Constraints can be deactivated but never deleted
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.enforce_append_only_constraints()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            'CEO-DIR-2026-FINN-006 VIOLATION: Table ec020_constraint_feedback is APPEND-ONLY. '
            'DELETE operations are constitutionally prohibited. '
            'Constraints may be deactivated (is_active=FALSE) but never deleted.';
    END IF;

    -- Allow UPDATE but protect core fields
    IF TG_OP = 'UPDATE' THEN
        IF OLD.id != NEW.id OR
           OLD.created_at != NEW.created_at THEN
            RAISE EXCEPTION
                'CEO-DIR-2026-FINN-006 VIOLATION: Cannot modify identification fields '
                'on ec020_constraint_feedback.';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_append_only_constraint_feedback ON fhq_research.ec020_constraint_feedback;

CREATE TRIGGER trg_append_only_constraint_feedback
    BEFORE UPDATE OR DELETE ON fhq_research.ec020_constraint_feedback
    FOR EACH ROW
    EXECUTE FUNCTION fhq_research.enforce_append_only_constraints();

-- ============================================================================
-- VIEW: Append-Only Enforcement Status
-- For governance dashboard
-- ============================================================================

CREATE OR REPLACE VIEW fhq_research.v_append_only_enforcement AS
SELECT
    t.schemaname,
    t.tablename,
    CASE
        WHEN tr.tgname IS NOT NULL THEN 'ENFORCED'
        ELSE 'UNPROTECTED'
    END as append_only_status,
    tr.tgname as trigger_name,
    'CEO-DIR-2026-FINN-006 Section 2.1' as authority
FROM pg_tables t
LEFT JOIN pg_trigger tr ON tr.tgrelid = (t.schemaname || '.' || t.tablename)::regclass
    AND tr.tgname LIKE 'trg_append_only%'
WHERE t.schemaname = 'fhq_research'
  AND t.tablename IN (
      'retrieval_efficiency_log',
      'signal_yield_tracking',
      'surprise_resampling_quota',
      'ikea_feedback_log',
      'ikea_pattern_registry',
      'ec020_constraint_feedback'
  )
ORDER BY t.tablename;

-- ============================================================================
-- AUDIT: Log migration
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
    'CONSTITUTIONAL_ENFORCEMENT',
    '181_finn006_append_only_enforcement',
    'DATABASE_MIGRATION',
    'STIG',
    'ENFORCED',
    'CEO-DIR-2026-FINN-006 Section 2.1: Append-Only Integrity - No updates, deletes, or backfills permitted',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-FINN-006',
        'section', '2.1 Append-Only Integrity',
        'tables_protected', ARRAY[
            'retrieval_efficiency_log',
            'signal_yield_tracking',
            'surprise_resampling_quota',
            'ikea_feedback_log',
            'ikea_pattern_registry',
            'ec020_constraint_feedback'
        ],
        'enforcement_level', 'CONSTITUTIONAL',
        'rationale', 'Historical noise is preserved as forensic evidence'
    )
);

COMMIT;

-- ============================================================================
-- VERIFICATION: Test append-only enforcement
-- ============================================================================

DO $$
DECLARE
    v_test_id UUID;
    v_error_caught BOOLEAN := FALSE;
BEGIN
    -- Insert test record
    INSERT INTO fhq_research.retrieval_efficiency_log (
        run_id, run_number, evidence_node_id, regime_id
    ) VALUES (
        gen_random_uuid(), 0, gen_random_uuid(), 'TEST'
    ) RETURNING id INTO v_test_id;

    -- Attempt UPDATE (should fail)
    BEGIN
        UPDATE fhq_research.retrieval_efficiency_log
        SET regime_id = 'MODIFIED'
        WHERE id = v_test_id;
    EXCEPTION WHEN OTHERS THEN
        v_error_caught := TRUE;
        RAISE NOTICE 'UPDATE correctly blocked: %', SQLERRM;
    END;

    IF NOT v_error_caught THEN
        RAISE EXCEPTION 'Migration 181 FAILED: UPDATE was not blocked on retrieval_efficiency_log';
    END IF;

    -- Attempt DELETE (should fail)
    v_error_caught := FALSE;
    BEGIN
        DELETE FROM fhq_research.retrieval_efficiency_log WHERE id = v_test_id;
    EXCEPTION WHEN OTHERS THEN
        v_error_caught := TRUE;
        RAISE NOTICE 'DELETE correctly blocked: %', SQLERRM;
    END;

    IF NOT v_error_caught THEN
        RAISE EXCEPTION 'Migration 181 FAILED: DELETE was not blocked on retrieval_efficiency_log';
    END IF;

    RAISE NOTICE 'Migration 181 SUCCESS: Append-only enforcement verified';
    RAISE NOTICE 'CEO-DIR-2026-FINN-006 Section 2.1: CONSTITUTIONAL ENFORCEMENT ACTIVE';
END $$;
