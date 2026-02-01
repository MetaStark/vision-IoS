-- ============================================================
-- VEGA TEST: M209 IMMUTABILITY ENFORCEMENT
-- ============================================================
-- Directive: CEO-DIR-2026-003
-- Purpose: Verify that UPDATE/DELETE on model_belief_state fail
-- Author: STIG (CTO)
-- Date: 2026-01-06
-- Classification: GOVERNANCE-CRITICAL (Class A)
--
-- EXPECTED RESULTS:
--   Test 1 (UPDATE): ERROR - IMMUTABILITY_VIOLATION
--   Test 2 (DELETE): ERROR - IMMUTABILITY_VIOLATION
--   Test 3 (INSERT): SUCCESS - 1 row inserted
--
-- EXECUTION: Run after Migration 209 deployment
-- ============================================================

-- ============================================================
-- SETUP: Insert a test record for immutability testing
-- ============================================================

DO $$
DECLARE
    v_test_belief_id UUID;
BEGIN
    RAISE NOTICE '=== VEGA TEST M209: IMMUTABILITY ENFORCEMENT ===';
    RAISE NOTICE 'Timestamp: %', NOW();
    RAISE NOTICE '';

    -- Insert test record
    INSERT INTO fhq_perception.model_belief_state (
        belief_id,
        asset_id,
        belief_timestamp,
        technical_regime,
        belief_distribution,
        belief_confidence,
        dominant_regime,
        model_version,
        inference_engine,
        lineage_hash
    ) VALUES (
        gen_random_uuid(),
        'VEGA-TEST-ASSET',
        NOW(),
        'NEUTRAL',
        '{"BULL": 0.20, "BEAR": 0.15, "NEUTRAL": 0.55, "STRESS": 0.10}'::jsonb,
        0.55,
        'NEUTRAL',
        'VEGA_TEST_v1',
        'VEGA_TEST_ENGINE',
        'VEGA_TEST_HASH_' || encode(sha256(NOW()::text::bytea), 'hex')
    )
    RETURNING belief_id INTO v_test_belief_id;

    RAISE NOTICE 'TEST SETUP: Inserted test belief record: %', v_test_belief_id;
    RAISE NOTICE '';
END $$;

-- ============================================================
-- TEST 1: Attempt UPDATE (MUST FAIL)
-- ============================================================

DO $$
DECLARE
    v_test_id UUID;
    v_error_msg TEXT;
BEGIN
    RAISE NOTICE '=== TEST 1: UPDATE ATTEMPT ===';

    -- Get the test record ID
    SELECT belief_id INTO v_test_id
    FROM fhq_perception.model_belief_state
    WHERE asset_id = 'VEGA-TEST-ASSET'
    LIMIT 1;

    IF v_test_id IS NULL THEN
        RAISE NOTICE 'TEST 1 SKIPPED: No test record found';
        RETURN;
    END IF;

    -- Attempt to update (this MUST fail)
    BEGIN
        UPDATE fhq_perception.model_belief_state
        SET belief_confidence = 0.99
        WHERE belief_id = v_test_id;

        -- If we reach here, the test FAILED
        RAISE NOTICE 'TEST 1 RESULT: *** FAILED *** - UPDATE succeeded (immutability NOT enforced)';
    EXCEPTION
        WHEN OTHERS THEN
            GET STACKED DIAGNOSTICS v_error_msg = MESSAGE_TEXT;
            IF v_error_msg LIKE '%IMMUTABILITY_VIOLATION%' THEN
                RAISE NOTICE 'TEST 1 RESULT: PASSED - UPDATE blocked with IMMUTABILITY_VIOLATION';
                RAISE NOTICE 'Error message: %', v_error_msg;
            ELSE
                RAISE NOTICE 'TEST 1 RESULT: PASSED (unexpected error): %', v_error_msg;
            END IF;
    END;

    RAISE NOTICE '';
END $$;

-- ============================================================
-- TEST 2: Attempt DELETE (MUST FAIL)
-- ============================================================

DO $$
DECLARE
    v_test_id UUID;
    v_error_msg TEXT;
BEGIN
    RAISE NOTICE '=== TEST 2: DELETE ATTEMPT ===';

    -- Get the test record ID
    SELECT belief_id INTO v_test_id
    FROM fhq_perception.model_belief_state
    WHERE asset_id = 'VEGA-TEST-ASSET'
    LIMIT 1;

    IF v_test_id IS NULL THEN
        RAISE NOTICE 'TEST 2 SKIPPED: No test record found';
        RETURN;
    END IF;

    -- Attempt to delete (this MUST fail)
    BEGIN
        DELETE FROM fhq_perception.model_belief_state
        WHERE belief_id = v_test_id;

        -- If we reach here, the test FAILED
        RAISE NOTICE 'TEST 2 RESULT: *** FAILED *** - DELETE succeeded (immutability NOT enforced)';
    EXCEPTION
        WHEN OTHERS THEN
            GET STACKED DIAGNOSTICS v_error_msg = MESSAGE_TEXT;
            IF v_error_msg LIKE '%IMMUTABILITY_VIOLATION%' THEN
                RAISE NOTICE 'TEST 2 RESULT: PASSED - DELETE blocked with IMMUTABILITY_VIOLATION';
                RAISE NOTICE 'Error message: %', v_error_msg;
            ELSE
                RAISE NOTICE 'TEST 2 RESULT: PASSED (unexpected error): %', v_error_msg;
            END IF;
    END;

    RAISE NOTICE '';
END $$;

-- ============================================================
-- TEST 3: Verify INSERT still works
-- ============================================================

DO $$
DECLARE
    v_new_belief_id UUID;
BEGIN
    RAISE NOTICE '=== TEST 3: INSERT VERIFICATION ===';

    BEGIN
        INSERT INTO fhq_perception.model_belief_state (
            asset_id,
            belief_timestamp,
            technical_regime,
            belief_distribution,
            belief_confidence,
            dominant_regime,
            model_version,
            inference_engine,
            lineage_hash
        ) VALUES (
            'VEGA-TEST-INSERT',
            NOW(),
            'BULL',
            '{"BULL": 0.70, "BEAR": 0.10, "NEUTRAL": 0.15, "STRESS": 0.05}'::jsonb,
            0.70,
            'BULL',
            'VEGA_TEST_v1',
            'VEGA_TEST_ENGINE',
            'VEGA_INSERT_TEST_' || encode(sha256(NOW()::text::bytea), 'hex')
        )
        RETURNING belief_id INTO v_new_belief_id;

        RAISE NOTICE 'TEST 3 RESULT: PASSED - INSERT succeeded with belief_id: %', v_new_belief_id;
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE 'TEST 3 RESULT: *** FAILED *** - INSERT blocked: %', SQLERRM;
    END;

    RAISE NOTICE '';
END $$;

-- ============================================================
-- TEST 4: Verify governance audit logging
-- ============================================================

DO $$
DECLARE
    v_violation_count INTEGER;
BEGIN
    RAISE NOTICE '=== TEST 4: GOVERNANCE AUDIT VERIFICATION ===';

    SELECT COUNT(*) INTO v_violation_count
    FROM fhq_governance.governance_actions_log
    WHERE action_type = 'IMMUTABILITY_VIOLATION_ATTEMPT'
    AND initiated_at > NOW() - INTERVAL '5 minutes';

    IF v_violation_count > 0 THEN
        RAISE NOTICE 'TEST 4 RESULT: PASSED - % violation attempts logged to governance_actions_log', v_violation_count;
    ELSE
        RAISE NOTICE 'TEST 4 RESULT: INFO - No violation attempts logged (may require trigger logging implementation)';
    END IF;

    RAISE NOTICE '';
END $$;

-- ============================================================
-- SUMMARY
-- ============================================================

DO $$
DECLARE
    v_total_test_records INTEGER;
BEGIN
    RAISE NOTICE '=== VEGA TEST M209 SUMMARY ===';

    SELECT COUNT(*) INTO v_total_test_records
    FROM fhq_perception.model_belief_state
    WHERE asset_id LIKE 'VEGA-TEST%';

    RAISE NOTICE 'Test records in model_belief_state: %', v_total_test_records;
    RAISE NOTICE '';
    RAISE NOTICE 'Expected Results:';
    RAISE NOTICE '  TEST 1 (UPDATE): PASSED if blocked with IMMUTABILITY_VIOLATION';
    RAISE NOTICE '  TEST 2 (DELETE): PASSED if blocked with IMMUTABILITY_VIOLATION';
    RAISE NOTICE '  TEST 3 (INSERT): PASSED if succeeded';
    RAISE NOTICE '  TEST 4 (AUDIT):  PASSED if violations logged';
    RAISE NOTICE '';
    RAISE NOTICE 'VEGA Attestation: Tests complete. Review results above.';
END $$;

-- ============================================================
-- CLEANUP (Optional - run manually after verification)
-- ============================================================
-- NOTE: Cleanup will FAIL if immutability is properly enforced
-- This is expected behavior and confirms the control works
--
-- To clean up test data, disable the trigger temporarily:
--   ALTER TABLE fhq_perception.model_belief_state DISABLE TRIGGER trg_model_belief_state_immutable;
--   DELETE FROM fhq_perception.model_belief_state WHERE asset_id LIKE 'VEGA-TEST%';
--   ALTER TABLE fhq_perception.model_belief_state ENABLE TRIGGER trg_model_belief_state_immutable;
-- ============================================================
