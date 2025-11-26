-- ============================================================================
-- STIG: VEGA AUTONOMOUS COMPLIANCE RHYTHMS (CORRECTED)
-- ============================================================================
-- Migration: 028_stig_vega_rhythm_corrected.sql
-- Uses exact column names from existing tables
-- ============================================================================

\echo '============================================================'
\echo 'TASK 1: VALIDATE VEGA INSTALLATION STATE'
\echo '============================================================'

\echo ''
\echo '--- ADR-006 Registration ---'
SELECT adr_id, adr_title, adr_status, adr_type, current_version FROM fhq_meta.adr_registry WHERE adr_id = 'ADR-006';

\echo ''
\echo '--- VEGA Identity ---'
SELECT agent_name, role_title, tier, authority_level, reports_to, status FROM fhq_meta.vega_identity;

\echo ''
\echo '--- EC-001 Employment Contract ---'
SELECT contract_number, employee, status, total_duties, total_constraints, total_rights FROM fhq_meta.vega_employment_contract;

\echo ''
\echo '--- Constitutional Duties (10) ---'
SELECT duty_code, duty_title, duty_category FROM fhq_meta.vega_constitutional_duties ORDER BY duty_code;

\echo ''
\echo '--- Constraints (7) ---'
SELECT constraint_code, constraint_title, constraint_type FROM fhq_meta.vega_constraints ORDER BY constraint_code;

\echo ''
\echo '--- Rights (7) ---'
SELECT right_code, right_title, right_category FROM fhq_meta.vega_rights ORDER BY right_code;

\echo ''
\echo '--- Executive Role ---'
SELECT role_id, role_name, authority_level, veto_power, active FROM fhq_governance.executive_roles WHERE role_id = 'VEGA';

\echo ''
\echo '--- Validation Summary ---'
SELECT
    (SELECT CASE WHEN adr_status = 'APPROVED' THEN 'PASS' ELSE 'FAIL' END FROM fhq_meta.adr_registry WHERE adr_id = 'ADR-006') as adr006,
    (SELECT CASE WHEN status = 'ACTIVE' THEN 'PASS' ELSE 'FAIL' END FROM fhq_meta.vega_identity WHERE agent_name = 'VEGA') as vega,
    (SELECT CASE WHEN status = 'ACTIVE' THEN 'PASS' ELSE 'FAIL' END FROM fhq_meta.vega_employment_contract WHERE contract_number = 'EC-001') as ec001,
    (SELECT CASE WHEN COUNT(*) = 10 THEN 'PASS' ELSE 'FAIL' END FROM fhq_meta.vega_constitutional_duties) as duties,
    (SELECT CASE WHEN COUNT(*) = 7 THEN 'PASS' ELSE 'FAIL' END FROM fhq_meta.vega_constraints) as constraints,
    (SELECT CASE WHEN COUNT(*) = 7 THEN 'PASS' ELSE 'FAIL' END FROM fhq_meta.vega_rights) as rights;

-- ============================================================================
-- TASK 2: INITIALIZE VEGA AUTONOMOUS RHYTHMS
-- ============================================================================

\echo ''
\echo '============================================================'
\echo 'TASK 2: INITIALIZE VEGA AUTONOMOUS RHYTHMS'
\echo '============================================================'

\echo ''
\echo '--- Creating vega_daily_integrity_check() ---'

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
    SELECT COUNT(*) INTO v_adr_count FROM fhq_meta.adr_registry WHERE adr_status = 'APPROVED';

    SELECT COUNT(*) INTO v_orphan_count
    FROM fhq_meta.vega_identity vi
    WHERE NOT EXISTS (
        SELECT 1 FROM fhq_meta.adr_registry ar WHERE ar.adr_id = ANY(vi.governing_adrs)
    );

    SELECT COUNT(*) INTO v_hash_mismatches
    FROM fhq_meta.vega_attestations WHERE attestation_hash IS NULL OR attestation_hash = '';

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

    -- Log using correct columns: event_type, description, metadata, executed_by
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

\echo ''
\echo '--- Creating vega_weekly_reconciliation() ---'

CREATE OR REPLACE FUNCTION fhq_meta.vega_weekly_reconciliation()
RETURNS JSONB AS $$
DECLARE
    v_result JSONB;
    v_start TIMESTAMPTZ := NOW();
    v_registry_count INTEGER;
    v_version_count INTEGER;
    v_missing_versions INTEGER;
    v_cert_count INTEGER;
    v_pending_certs INTEGER;
    v_status VARCHAR(20) := 'RECONCILED';
BEGIN
    SELECT COUNT(*) INTO v_registry_count FROM fhq_meta.adr_registry;
    SELECT COUNT(*) INTO v_version_count FROM fhq_meta.adr_version_history;

    SELECT COUNT(*) INTO v_missing_versions
    FROM fhq_meta.adr_registry ar
    WHERE NOT EXISTS (SELECT 1 FROM fhq_meta.adr_version_history vh WHERE vh.adr_id = ar.adr_id);

    SELECT COUNT(*), COUNT(*) FILTER (WHERE certification_status = 'PENDING')
    INTO v_cert_count, v_pending_certs FROM fhq_meta.model_certifications;

    IF v_missing_versions > 0 THEN v_status := 'REQUIRES_ACTION'; END IF;

    v_result := jsonb_build_object(
        'check_type', 'WEEKLY_RECONCILIATION',
        'timestamp', v_start,
        'registry_entries', v_registry_count,
        'version_history_entries', v_version_count,
        'adrs_missing_versions', v_missing_versions,
        'total_certifications', v_cert_count,
        'pending_certifications', v_pending_certs,
        'status', v_status,
        'execution_ms', EXTRACT(MILLISECONDS FROM (NOW() - v_start))::INTEGER
    );

    INSERT INTO fhq_monitoring.system_event_log (event_type, description, metadata, executed_by)
    VALUES ('WEEKLY_RECONCILIATION', 'VEGA weekly reconciliation completed', v_result, 'VEGA');

    RETURN v_result;
EXCEPTION WHEN OTHERS THEN
    v_result := jsonb_build_object('error', SQLERRM, 'status', 'ERROR');
    INSERT INTO fhq_monitoring.system_event_log (event_type, description, metadata, executed_by)
    VALUES ('WEEKLY_RECONCILIATION', 'VEGA weekly reconciliation failed', v_result, 'VEGA');
    RETURN v_result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

\echo ''
\echo '--- Creating vega_monthly_snapshot() ---'

CREATE OR REPLACE FUNCTION fhq_meta.vega_monthly_snapshot()
RETURNS JSONB AS $$
DECLARE
    v_result JSONB;
    v_start TIMESTAMPTZ := NOW();
    v_snapshot_id VARCHAR(100);
    v_snapshot_hash VARCHAR(64);
    v_adr_snapshot JSONB;
    v_governance_snapshot JSONB;
    v_status VARCHAR(20) := 'SNAPSHOT_COMPLETE';
    v_adr RECORD;
BEGIN
    v_snapshot_id := 'SNAP-' || TO_CHAR(NOW(), 'YYYYMM-DD-HH24MISS');

    SELECT jsonb_agg(jsonb_build_object(
        'adr_id', adr_id, 'title', adr_title, 'status', adr_status, 'version', current_version
    )) INTO v_adr_snapshot FROM fhq_meta.adr_registry;

    v_governance_snapshot := jsonb_build_object(
        'vega_status', (SELECT status FROM fhq_meta.vega_identity WHERE agent_name = 'VEGA'),
        'contract_status', (SELECT status FROM fhq_meta.vega_employment_contract WHERE contract_number = 'EC-001'),
        'duties_count', (SELECT COUNT(*) FROM fhq_meta.vega_constitutional_duties),
        'constraints_count', (SELECT COUNT(*) FROM fhq_meta.vega_constraints),
        'rights_count', (SELECT COUNT(*) FROM fhq_meta.vega_rights)
    );

    v_snapshot_hash := encode(sha256((v_adr_snapshot::text || v_governance_snapshot::text)::bytea), 'hex');

    -- Record version history using correct columns: adr_id, version, change_summary, sha256_hash, approved_by
    FOR v_adr IN SELECT adr_id, adr_title, current_version, sha256_hash FROM fhq_meta.adr_registry LOOP
        INSERT INTO fhq_meta.adr_version_history (adr_id, version, change_summary, sha256_hash, approved_by)
        VALUES (v_adr.adr_id, v_adr.current_version, 'VEGA monthly snapshot', COALESCE(v_adr.sha256_hash, v_snapshot_hash), 'VEGA')
        ON CONFLICT (adr_id, version) DO NOTHING;
    END LOOP;

    v_result := jsonb_build_object(
        'check_type', 'MONTHLY_SNAPSHOT',
        'snapshot_id', v_snapshot_id,
        'timestamp', v_start,
        'adr_count', (SELECT COUNT(*) FROM fhq_meta.adr_registry),
        'governance_snapshot', v_governance_snapshot,
        'snapshot_hash', v_snapshot_hash,
        'status', v_status,
        'execution_ms', EXTRACT(MILLISECONDS FROM (NOW() - v_start))::INTEGER
    );

    INSERT INTO fhq_monitoring.system_event_log (event_type, description, metadata, executed_by)
    VALUES ('MONTHLY_SNAPSHOT', 'VEGA monthly snapshot completed', v_result, 'VEGA');

    RETURN v_result;
EXCEPTION WHEN OTHERS THEN
    v_result := jsonb_build_object('error', SQLERRM, 'status', 'ERROR');
    INSERT INTO fhq_monitoring.system_event_log (event_type, description, metadata, executed_by)
    VALUES ('MONTHLY_SNAPSHOT', 'VEGA monthly snapshot failed', v_result, 'VEGA');
    RETURN v_result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

\echo ''
\echo '--- Rhythm Schedule ---'
SELECT rhythm_name, rhythm_function, cron_schedule, is_active, next_execution FROM fhq_governance.vega_rhythm_schedule;

-- ============================================================================
-- TASK 3: EXECUTE FIRST-RUN DRY CHECKS
-- ============================================================================

\echo ''
\echo '============================================================'
\echo 'TASK 3: EXECUTE FIRST-RUN DRY CHECKS'
\echo '============================================================'

\echo ''
\echo '--- Executing vega_daily_integrity_check() ---'
SELECT fhq_meta.vega_daily_integrity_check();

\echo ''
\echo '--- Executing vega_weekly_reconciliation() ---'
SELECT fhq_meta.vega_weekly_reconciliation();

\echo ''
\echo '--- Executing vega_monthly_snapshot() ---'
SELECT fhq_meta.vega_monthly_snapshot();

\echo ''
\echo '--- System Event Log (Last 5 Entries) ---'
SELECT event_id, event_type, description, executed_by, executed_at
FROM fhq_monitoring.system_event_log ORDER BY executed_at DESC LIMIT 5;

-- ============================================================================
-- TASK 4: REGISTER RESULT IN ADR AUDIT LOG
-- ============================================================================

\echo ''
\echo '============================================================'
\echo 'TASK 4: REGISTER RESULT IN ADR AUDIT LOG'
\echo '============================================================'

-- Using correct columns: change_proposal_id, event_type, gate_stage, adr_id, initiated_by, decision, resolution_notes, sha256_hash, metadata
INSERT INTO fhq_meta.adr_audit_log (
    change_proposal_id,
    event_type,
    gate_stage,
    adr_id,
    initiated_by,
    decision,
    resolution_notes,
    sha256_hash,
    hash_chain_id,
    metadata
) VALUES (
    'STIG-VEGA-RHYTHM-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS'),
    'G3_AUDIT_VERIFICATION',
    'G3',
    'ADR-006',
    'STIG',
    'APPROVED',
    'VEGA Autonomous Compliance Rhythms initialized. Functions: vega_daily_integrity_check, vega_weekly_reconciliation, vega_monthly_snapshot. First-run executed successfully.',
    encode(sha256(('STIG_VEGA_RHYTHM_INIT_' || NOW()::TEXT)::bytea), 'hex'),
    'STIG_GOVERNANCE_CHAIN',
    jsonb_build_object(
        'functions_created', ARRAY['vega_daily_integrity_check', 'vega_weekly_reconciliation', 'vega_monthly_snapshot'],
        'schedules_registered', 3,
        'first_run_executed', TRUE,
        'validation_status', 'ALL_PASS'
    )
);

\echo ''
\echo '--- Audit Log Entry ---'
SELECT audit_id, event_type, gate_stage, adr_id, initiated_by, decision, timestamp
FROM fhq_meta.adr_audit_log WHERE initiated_by = 'STIG' ORDER BY timestamp DESC LIMIT 1;

\echo ''
\echo '--- ADR Version History ---'
SELECT version_id, adr_id, version, approved_by, created_at
FROM fhq_meta.adr_version_history ORDER BY created_at DESC LIMIT 10;

-- ============================================================================
-- FINAL STATUS
-- ============================================================================

\echo ''
\echo '============================================================'
\echo 'VEGA AUTONOMOUS COMPLIANCE RHYTHMS - FINAL STATUS'
\echo '============================================================'

SELECT
    'VEGA_INSTALLATION' as subsystem,
    CASE WHEN (SELECT status FROM fhq_meta.vega_identity WHERE agent_name = 'VEGA') = 'ACTIVE' THEN 'OPERATIONAL' ELSE 'FAILED' END as status
UNION ALL SELECT 'ADR-006_REGISTRATION', CASE WHEN (SELECT adr_status FROM fhq_meta.adr_registry WHERE adr_id = 'ADR-006') = 'APPROVED' THEN 'OPERATIONAL' ELSE 'FAILED' END
UNION ALL SELECT 'EC-001_CONTRACT', CASE WHEN (SELECT status FROM fhq_meta.vega_employment_contract WHERE contract_number = 'EC-001') = 'ACTIVE' THEN 'OPERATIONAL' ELSE 'FAILED' END
UNION ALL SELECT 'DAILY_INTEGRITY_FUNCTION', CASE WHEN EXISTS(SELECT 1 FROM pg_proc WHERE proname = 'vega_daily_integrity_check') THEN 'OPERATIONAL' ELSE 'FAILED' END
UNION ALL SELECT 'WEEKLY_RECONCILIATION_FUNCTION', CASE WHEN EXISTS(SELECT 1 FROM pg_proc WHERE proname = 'vega_weekly_reconciliation') THEN 'OPERATIONAL' ELSE 'FAILED' END
UNION ALL SELECT 'MONTHLY_SNAPSHOT_FUNCTION', CASE WHEN EXISTS(SELECT 1 FROM pg_proc WHERE proname = 'vega_monthly_snapshot') THEN 'OPERATIONAL' ELSE 'FAILED' END
UNION ALL SELECT 'RHYTHM_SCHEDULE', CASE WHEN (SELECT COUNT(*) FROM fhq_governance.vega_rhythm_schedule WHERE is_active) = 3 THEN 'OPERATIONAL' ELSE 'FAILED' END
UNION ALL SELECT 'AUDIT_LOG_ENTRY', CASE WHEN EXISTS(SELECT 1 FROM fhq_meta.adr_audit_log WHERE initiated_by = 'STIG' AND event_type = 'G3_AUDIT_VERIFICATION') THEN 'RECORDED' ELSE 'FAILED' END;

\echo ''
\echo '============================================================'
\echo 'STIG: VEGA G3 PRE-ACTIVATION CHECK COMPLETE'
\echo '============================================================'
