-- ============================================================================
-- FIX: vega_daily_integrity_check() with correct column name
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_meta.vega_daily_integrity_check()
RETURNS JSONB AS $$
DECLARE
    v_result JSONB;
    v_start TIMESTAMPTZ := NOW();
    v_adr_count INTEGER;
    v_orphan_count INTEGER;
    v_hash_mismatches INTEGER := 0;
    v_class_a INTEGER := 0;
    v_class_b INTEGER := 0;
    v_class_c INTEGER := 0;
    v_status VARCHAR(20) := 'HEALTHY';
BEGIN
    -- Count approved ADRs
    SELECT COUNT(*) INTO v_adr_count FROM fhq_meta.adr_registry WHERE adr_status = 'APPROVED';

    -- Check orphaned references
    SELECT COUNT(*) INTO v_orphan_count
    FROM fhq_meta.vega_identity vi
    WHERE NOT EXISTS (
        SELECT 1 FROM fhq_meta.adr_registry ar WHERE ar.adr_id = ANY(vi.governing_adrs)
    );

    -- Check for attestations with missing/empty function_hash (correct column name)
    SELECT COUNT(*) INTO v_hash_mismatches
    FROM fhq_meta.vega_attestations
    WHERE function_hash IS NULL OR function_hash = '' OR hash_verified = FALSE;

    -- Determine status based on findings
    IF v_orphan_count > 0 OR v_hash_mismatches > 0 THEN
        v_class_b := v_orphan_count + v_hash_mismatches;
        v_status := 'WARNING';
    END IF;

    v_result := jsonb_build_object(
        'check_type', 'DAILY_INTEGRITY',
        'timestamp', v_start,
        'adr_count', v_adr_count,
        'orphan_references', v_orphan_count,
        'hash_mismatches', v_hash_mismatches,
        'class_a_events', v_class_a,
        'class_b_events', v_class_b,
        'class_c_events', v_class_c,
        'status', v_status,
        'execution_ms', EXTRACT(MILLISECONDS FROM (NOW() - v_start))::INTEGER
    );

    -- Log to monitoring
    INSERT INTO fhq_monitoring.system_event_log (event_type, description, metadata, executed_by)
    VALUES ('DAILY_INTEGRITY_CHECK', 'VEGA daily integrity check completed', v_result, 'VEGA');

    RETURN v_result;
EXCEPTION WHEN OTHERS THEN
    v_result := jsonb_build_object('error', SQLERRM, 'status', 'ERROR');
    INSERT INTO fhq_monitoring.system_event_log (event_type, description, metadata, executed_by)
    VALUES ('DAILY_INTEGRITY_CHECK', 'VEGA daily integrity check failed', v_result, 'VEGA');
    RETURN v_result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Test the fixed function
\echo '--- Testing vega_daily_integrity_check() ---'
SELECT fhq_meta.vega_daily_integrity_check();

\echo ''
\echo '--- System Event Log ---'
SELECT event_id, event_type, executed_by, executed_at,
       metadata->>'status' as status,
       metadata->>'hash_mismatches' as hash_mismatches
FROM fhq_monitoring.system_event_log
WHERE event_type = 'DAILY_INTEGRITY_CHECK'
ORDER BY executed_at DESC LIMIT 3;
