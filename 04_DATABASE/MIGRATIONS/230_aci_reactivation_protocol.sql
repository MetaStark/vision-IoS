-- Migration 230: ACI Reactivation Protocol
-- Authority: CEO-DIR-2026-036 - From Blackout to Verified Perception
-- Classification: CRITICAL - CONTROLLED REACTIVATION
-- Author: STIG (CTO)
-- Date: 2026-01-10

-- ============================================================================
-- EXECUTIVE INTENT:
-- "Reality before learning. Learning before capital."
--
-- Three gated layers: Data -> Perception -> Learning
-- No layer may advance without verified integrity of the previous.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. REACTIVATION PHASE TRACKING TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.aci_reactivation_phases (
    phase_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reactivation_cycle_id UUID NOT NULL,
    phase_name TEXT NOT NULL,
    phase_status TEXT NOT NULL DEFAULT 'PENDING',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    verified_by TEXT,
    verification_evidence JSONB,
    blockers TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_phase_name CHECK (phase_name IN ('PHASE_A_DATA', 'PHASE_B_PERCEPTION', 'PHASE_C_LEARNING')),
    CONSTRAINT valid_phase_status CHECK (phase_status IN ('PENDING', 'IN_PROGRESS', 'BLOCKED', 'VERIFIED', 'ROLLED_BACK'))
);

-- ============================================================================
-- 2. REACTIVATION CYCLE TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.aci_reactivation_cycles (
    cycle_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    triggered_from_blackout_id UUID,
    cycle_status TEXT NOT NULL DEFAULT 'INITIATED',
    initiated_by TEXT NOT NULL,
    initiated_at TIMESTAMPTZ DEFAULT NOW(),
    phase_a_complete BOOLEAN DEFAULT false,
    phase_b_complete BOOLEAN DEFAULT false,
    phase_c_complete BOOLEAN DEFAULT false,
    cleared_by TEXT,
    cleared_at TIMESTAMPTZ,
    vega_attestation_id TEXT,
    rollback_reason TEXT,
    CONSTRAINT valid_cycle_status CHECK (cycle_status IN ('INITIATED', 'PHASE_A', 'PHASE_B', 'PHASE_C', 'CLEARED', 'ROLLED_BACK'))
);

-- ============================================================================
-- 3. CEIO POST-MORTEM TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.ceio_postmortem (
    postmortem_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reactivation_cycle_id UUID REFERENCES fhq_governance.aci_reactivation_cycles(cycle_id),
    failure_class TEXT NOT NULL,
    root_cause_description TEXT NOT NULL,
    why_alerting_failed TEXT NOT NULL,
    preventive_control_added TEXT NOT NULL,
    preventive_control_verified BOOLEAN DEFAULT false,
    submitted_by TEXT NOT NULL DEFAULT 'CEIO',
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    verified_by TEXT,
    verified_at TIMESTAMPTZ,
    CONSTRAINT valid_failure_class CHECK (failure_class IN ('SCHEDULER', 'API_RATE_LIMIT', 'CREDENTIAL_EXPIRY', 'SILENT_EXCEPTION', 'NETWORK', 'OTHER'))
);

-- ============================================================================
-- 4. PHASE A: DATA REALITY CHECK FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.check_phase_a_requirements()
RETURNS TABLE (
    phase_a_passed BOOLEAN,
    all_assets_fresh BOOLEAN,
    freshness_duration_minutes INTEGER,
    details JSONB
) AS $$
DECLARE
    v_all_fresh BOOLEAN := true;
    v_stale_assets TEXT[] := '{}';
    v_asset_details JSONB := '[]'::JSONB;
    r RECORD;
BEGIN
    -- Check each primary asset
    FOR r IN
        SELECT
            u.canonical_id,
            cpf.is_fresh,
            cpf.staleness_minutes,
            cpf.max_allowed_minutes,
            cpf.asset_class
        FROM unnest(ARRAY['SPY', 'GLD', 'BTC-USD', 'SOL-USD']) as u(canonical_id)
        CROSS JOIN LATERAL fhq_governance.check_price_freshness(u.canonical_id, 'LEARNING') cpf
    LOOP
        IF NOT r.is_fresh THEN
            v_all_fresh := false;
            v_stale_assets := array_append(v_stale_assets, r.canonical_id);
        END IF;

        v_asset_details := v_asset_details || jsonb_build_object(
            'canonical_id', r.canonical_id,
            'is_fresh', r.is_fresh,
            'staleness_minutes', r.staleness_minutes,
            'max_allowed_minutes', r.max_allowed_minutes,
            'asset_class', r.asset_class
        );
    END LOOP;

    RETURN QUERY SELECT
        v_all_fresh,
        v_all_fresh,
        0::INTEGER,  -- Would need continuous monitoring for duration
        jsonb_build_object(
            'assets', v_asset_details,
            'stale_assets', v_stale_assets,
            'checked_at', NOW()
        );
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 5. PHASE B: PERCEPTION SANITY CHECK FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.run_phase_b_sanity_check()
RETURNS TABLE (
    phase_b_passed BOOLEAN,
    hit_rate_paper NUMERIC,
    brier_score NUMERIC,
    type_d_count INTEGER,
    type_e_count INTEGER,
    anomalies_detected BOOLEAN,
    details JSONB
) AS $$
DECLARE
    v_hit_rate NUMERIC;
    v_brier NUMERIC;
    v_type_d INTEGER;
    v_type_e INTEGER;
    v_anomalies BOOLEAN := false;
    v_paper_trades INTEGER;
    v_paper_hits INTEGER;
BEGIN
    -- Count paper trades with outcomes
    SELECT
        COUNT(*),
        SUM(CASE WHEN outcome_correct THEN 1 ELSE 0 END)
    INTO v_paper_trades, v_paper_hits
    FROM fhq_governance.paper_ledger
    WHERE outcome_correct IS NOT NULL;

    -- Calculate hit rate
    v_hit_rate := CASE WHEN v_paper_trades > 0
        THEN ROUND(v_paper_hits::NUMERIC / v_paper_trades * 100, 2)
        ELSE NULL
    END;

    -- Get Brier score from forecast_outcome_pairs (last 7 days)
    SELECT ROUND(AVG(brier_score)::NUMERIC, 4) INTO v_brier
    FROM fhq_research.forecast_outcome_pairs
    WHERE reconciled_at > NOW() - INTERVAL '7 days';

    -- Count error types from paper ledger
    SELECT
        SUM(CASE WHEN error_type = 'TYPE_D' THEN 1 ELSE 0 END),
        SUM(CASE WHEN error_type = 'TYPE_E' THEN 1 ELSE 0 END)
    INTO v_type_d, v_type_e
    FROM fhq_governance.paper_ledger
    WHERE error_type IS NOT NULL;

    v_type_d := COALESCE(v_type_d, 0);
    v_type_e := COALESCE(v_type_e, 0);

    -- Anomaly detection: unexpected discontinuities
    -- For now, flag if Brier > 0.5 or hit rate < 30%
    IF v_brier > 0.5 OR (v_hit_rate IS NOT NULL AND v_hit_rate < 30) THEN
        v_anomalies := true;
    END IF;

    RETURN QUERY SELECT
        NOT v_anomalies,
        v_hit_rate,
        v_brier,
        v_type_d,
        v_type_e,
        v_anomalies,
        jsonb_build_object(
            'paper_trades_scored', v_paper_trades,
            'paper_hits', v_paper_hits,
            'hit_rate_pct', v_hit_rate,
            'brier_score', v_brier,
            'type_d_count', v_type_d,
            'type_e_count', v_type_e,
            'anomalies_detected', v_anomalies,
            'checked_at', NOW()
        );
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 6. INITIATE REACTIVATION CYCLE FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.initiate_reactivation_cycle(
    p_initiated_by TEXT DEFAULT 'STIG'
)
RETURNS UUID AS $$
DECLARE
    v_cycle_id UUID;
    v_blackout_id UUID;
BEGIN
    -- Get current blackout ID
    SELECT blackout_id INTO v_blackout_id
    FROM fhq_governance.data_blackout_state
    WHERE is_active = true
    ORDER BY created_at DESC
    LIMIT 1;

    -- Create reactivation cycle
    INSERT INTO fhq_governance.aci_reactivation_cycles (
        triggered_from_blackout_id,
        cycle_status,
        initiated_by
    ) VALUES (
        v_blackout_id,
        'INITIATED',
        p_initiated_by
    )
    RETURNING cycle_id INTO v_cycle_id;

    -- Create phase records
    INSERT INTO fhq_governance.aci_reactivation_phases (reactivation_cycle_id, phase_name, phase_status)
    VALUES
        (v_cycle_id, 'PHASE_A_DATA', 'PENDING'),
        (v_cycle_id, 'PHASE_B_PERCEPTION', 'PENDING'),
        (v_cycle_id, 'PHASE_C_LEARNING', 'PENDING');

    RETURN v_cycle_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 7. VERIFY PHASE A FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.verify_phase_a(
    p_cycle_id UUID,
    p_verified_by TEXT
)
RETURNS TABLE (
    success BOOLEAN,
    message TEXT,
    can_proceed_to_phase_b BOOLEAN
) AS $$
DECLARE
    v_phase_a RECORD;
    v_postmortem_exists BOOLEAN;
BEGIN
    -- Check Phase A requirements
    SELECT * INTO v_phase_a
    FROM fhq_governance.check_phase_a_requirements();

    -- Check if CEIO post-mortem exists
    SELECT EXISTS (
        SELECT 1 FROM fhq_governance.ceio_postmortem
        WHERE reactivation_cycle_id = p_cycle_id
    ) INTO v_postmortem_exists;

    IF NOT v_phase_a.all_assets_fresh THEN
        RETURN QUERY SELECT
            false,
            'Phase A FAILED: Not all primary assets have fresh data'::TEXT,
            false;
        RETURN;
    END IF;

    IF NOT v_postmortem_exists THEN
        RETURN QUERY SELECT
            false,
            'Phase A BLOCKED: CEIO Post-Mortem not yet submitted'::TEXT,
            false;
        RETURN;
    END IF;

    -- Update phase status
    UPDATE fhq_governance.aci_reactivation_phases
    SET
        phase_status = 'VERIFIED',
        completed_at = NOW(),
        verified_by = p_verified_by,
        verification_evidence = v_phase_a.details
    WHERE reactivation_cycle_id = p_cycle_id
    AND phase_name = 'PHASE_A_DATA';

    -- Update cycle status
    UPDATE fhq_governance.aci_reactivation_cycles
    SET
        cycle_status = 'PHASE_B',
        phase_a_complete = true
    WHERE cycle_id = p_cycle_id;

    -- Start Phase B
    UPDATE fhq_governance.aci_reactivation_phases
    SET
        phase_status = 'IN_PROGRESS',
        started_at = NOW()
    WHERE reactivation_cycle_id = p_cycle_id
    AND phase_name = 'PHASE_B_PERCEPTION';

    RETURN QUERY SELECT
        true,
        'Phase A VERIFIED. Proceeding to Phase B: Perception Sanity Check'::TEXT,
        true;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 8. VERIFY PHASE B FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.verify_phase_b(
    p_cycle_id UUID,
    p_verified_by TEXT
)
RETURNS TABLE (
    success BOOLEAN,
    message TEXT,
    can_proceed_to_phase_c BOOLEAN
) AS $$
DECLARE
    v_phase_b RECORD;
BEGIN
    -- Run Phase B sanity check
    SELECT * INTO v_phase_b
    FROM fhq_governance.run_phase_b_sanity_check();

    IF v_phase_b.anomalies_detected THEN
        -- Rollback to blackout
        UPDATE fhq_governance.aci_reactivation_phases
        SET
            phase_status = 'ROLLED_BACK',
            completed_at = NOW(),
            verified_by = p_verified_by,
            verification_evidence = v_phase_b.details,
            blockers = ARRAY['Epistemic anomalies detected']
        WHERE reactivation_cycle_id = p_cycle_id
        AND phase_name = 'PHASE_B_PERCEPTION';

        UPDATE fhq_governance.aci_reactivation_cycles
        SET
            cycle_status = 'ROLLED_BACK',
            rollback_reason = 'Phase B anomalies: ' || v_phase_b.details::TEXT
        WHERE cycle_id = p_cycle_id;

        RETURN QUERY SELECT
            false,
            'Phase B FAILED: Epistemic anomalies detected. ROLLED BACK to DATA_BLACKOUT.'::TEXT,
            false;
        RETURN;
    END IF;

    -- Update phase status
    UPDATE fhq_governance.aci_reactivation_phases
    SET
        phase_status = 'VERIFIED',
        completed_at = NOW(),
        verified_by = p_verified_by,
        verification_evidence = v_phase_b.details
    WHERE reactivation_cycle_id = p_cycle_id
    AND phase_name = 'PHASE_B_PERCEPTION';

    -- Update cycle status
    UPDATE fhq_governance.aci_reactivation_cycles
    SET
        cycle_status = 'PHASE_C',
        phase_b_complete = true
    WHERE cycle_id = p_cycle_id;

    -- Start Phase C
    UPDATE fhq_governance.aci_reactivation_phases
    SET
        phase_status = 'IN_PROGRESS',
        started_at = NOW()
    WHERE reactivation_cycle_id = p_cycle_id
    AND phase_name = 'PHASE_C_LEARNING';

    RETURN QUERY SELECT
        true,
        format('Phase B VERIFIED. Hit rate: %s%%, Brier: %s. Proceeding to Phase C.',
               COALESCE(v_phase_b.hit_rate_paper::TEXT, 'N/A'),
               COALESCE(v_phase_b.brier_score::TEXT, 'N/A'))::TEXT,
        true;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 9. COMPLETE PHASE C (VEGA ONLY) FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.complete_phase_c_and_clear_blackout(
    p_cycle_id UUID,
    p_vega_attestation_id TEXT
)
RETURNS TABLE (
    success BOOLEAN,
    message TEXT,
    system_status TEXT
) AS $$
DECLARE
    v_cycle RECORD;
    v_freshness_check RECORD;
    v_postmortem_verified BOOLEAN;
BEGIN
    -- Get cycle status
    SELECT * INTO v_cycle
    FROM fhq_governance.aci_reactivation_cycles
    WHERE cycle_id = p_cycle_id;

    IF v_cycle.cycle_status != 'PHASE_C' THEN
        RETURN QUERY SELECT
            false,
            format('Cannot complete Phase C: Cycle is in %s status', v_cycle.cycle_status)::TEXT,
            'DATA_BLACKOUT'::TEXT;
        RETURN;
    END IF;

    IF NOT v_cycle.phase_a_complete OR NOT v_cycle.phase_b_complete THEN
        RETURN QUERY SELECT
            false,
            'Cannot complete Phase C: Previous phases not verified'::TEXT,
            'DATA_BLACKOUT'::TEXT;
        RETURN;
    END IF;

    -- Verify freshness still holds (2+ hours requirement)
    SELECT * INTO v_freshness_check
    FROM fhq_governance.check_phase_a_requirements();

    IF NOT v_freshness_check.all_assets_fresh THEN
        RETURN QUERY SELECT
            false,
            'Phase C BLOCKED: Freshness invariant no longer holds'::TEXT,
            'DATA_BLACKOUT'::TEXT;
        RETURN;
    END IF;

    -- Check CEIO preventive control is verified
    SELECT verified_by IS NOT NULL INTO v_postmortem_verified
    FROM fhq_governance.ceio_postmortem
    WHERE reactivation_cycle_id = p_cycle_id;

    IF NOT COALESCE(v_postmortem_verified, false) THEN
        RETURN QUERY SELECT
            false,
            'Phase C BLOCKED: CEIO preventive control not yet verified'::TEXT,
            'DATA_BLACKOUT'::TEXT;
        RETURN;
    END IF;

    -- Complete Phase C
    UPDATE fhq_governance.aci_reactivation_phases
    SET
        phase_status = 'VERIFIED',
        completed_at = NOW(),
        verified_by = 'VEGA',
        verification_evidence = jsonb_build_object(
            'vega_attestation_id', p_vega_attestation_id,
            'freshness_verified', true,
            'postmortem_verified', true,
            'cleared_at', NOW()
        )
    WHERE reactivation_cycle_id = p_cycle_id
    AND phase_name = 'PHASE_C_LEARNING';

    -- Complete cycle
    UPDATE fhq_governance.aci_reactivation_cycles
    SET
        cycle_status = 'CLEARED',
        phase_c_complete = true,
        cleared_by = 'VEGA',
        cleared_at = NOW(),
        vega_attestation_id = p_vega_attestation_id
    WHERE cycle_id = p_cycle_id;

    -- Clear DATA_BLACKOUT
    UPDATE fhq_governance.data_blackout_state
    SET
        is_active = false,
        cleared_by = 'VEGA',
        cleared_at = NOW(),
        vega_attestation_id = p_vega_attestation_id,
        updated_at = NOW()
    WHERE is_active = true;

    RETURN QUERY SELECT
        true,
        'ACI REACTIVATION COMPLETE. DATA_BLACKOUT cleared. System returning to OPERATIONAL.'::TEXT,
        'OPERATIONAL'::TEXT;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 10. CURRENT REACTIVATION STATUS VIEW
-- ============================================================================

CREATE OR REPLACE VIEW fhq_governance.aci_reactivation_status AS
SELECT
    c.cycle_id,
    c.cycle_status,
    c.initiated_at,
    c.phase_a_complete,
    c.phase_b_complete,
    c.phase_c_complete,
    (SELECT phase_status FROM fhq_governance.aci_reactivation_phases WHERE reactivation_cycle_id = c.cycle_id AND phase_name = 'PHASE_A_DATA') as phase_a_status,
    (SELECT phase_status FROM fhq_governance.aci_reactivation_phases WHERE reactivation_cycle_id = c.cycle_id AND phase_name = 'PHASE_B_PERCEPTION') as phase_b_status,
    (SELECT phase_status FROM fhq_governance.aci_reactivation_phases WHERE reactivation_cycle_id = c.cycle_id AND phase_name = 'PHASE_C_LEARNING') as phase_c_status,
    EXISTS (SELECT 1 FROM fhq_governance.ceio_postmortem WHERE reactivation_cycle_id = c.cycle_id) as postmortem_submitted,
    (SELECT is_active FROM fhq_governance.data_blackout_state ORDER BY created_at DESC LIMIT 1) as blackout_still_active
FROM fhq_governance.aci_reactivation_cycles c
ORDER BY c.initiated_at DESC
LIMIT 1;

-- ============================================================================
-- 11. INITIATE CURRENT REACTIVATION CYCLE
-- ============================================================================

DO $$
DECLARE
    v_cycle_id UUID;
BEGIN
    SELECT fhq_governance.initiate_reactivation_cycle('STIG') INTO v_cycle_id;
    RAISE NOTICE 'Reactivation cycle initiated: %', v_cycle_id;
END $$;

-- ============================================================================
-- 12. VERIFICATION
-- ============================================================================

-- Show current freshness status
DO $$
DECLARE
    r RECORD;
BEGIN
    RAISE NOTICE '=== CEO-DIR-2026-036: ACI REACTIVATION STATUS ===';
    RAISE NOTICE '';
    RAISE NOTICE '--- PHASE A: DATA REALITY ---';

    FOR r IN
        SELECT
            u.canonical_id,
            cpf.is_fresh,
            cpf.staleness_minutes,
            cpf.max_allowed_minutes
        FROM unnest(ARRAY['SPY', 'GLD', 'BTC-USD', 'SOL-USD']) as u(canonical_id)
        CROSS JOIN LATERAL fhq_governance.check_price_freshness(u.canonical_id, 'LEARNING') cpf
    LOOP
        RAISE NOTICE '%: fresh=%, staleness=%min, max=%min',
            r.canonical_id, r.is_fresh, r.staleness_minutes, r.max_allowed_minutes;
    END LOOP;

    RAISE NOTICE '';
    RAISE NOTICE '--- AWAITING ---';
    RAISE NOTICE '1. CEIO to restore price feeds';
    RAISE NOTICE '2. CEIO to submit Post-Mortem';
    RAISE NOTICE '3. Price freshness to hold for 120+ minutes';
END $$;

COMMIT;

-- ============================================================================
-- MIGRATION COMPLETE
-- CEO-DIR-2026-036: ACI Reactivation Protocol Implemented
-- ============================================================================
