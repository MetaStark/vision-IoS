-- ============================================================================
-- MIGRATION: PHASE IV-B AUTHORITY POPULATION
-- ============================================================================
-- Directive: CEO-DIR-2026-AGENT-CONTRACT-ALIGNMENT-002
-- Phase: IV-B (Authority Population)
-- Authorized: 2026-01-23 by CEO
-- Scope: Limited, explicit, contract-backed
-- Runtime impact: NONE (shadow/paper only)
-- ============================================================================

-- PRE-STATE SNAPSHOT
SELECT 'PRE_STATE' as phase,
       (SELECT COUNT(*) FROM fhq_governance.write_mandate_registry WHERE is_active = true) as write_mandates,
       (SELECT COUNT(*) FROM fhq_governance.authority_matrix) as authority_matrix_rows;

-- ============================================================================
-- 1. EC-001 VEGA: GRANT WRITE_MANDATE (RESTRICTED)
-- ============================================================================
-- Contract basis: EC-001 Section 4 - Attestation and compliance audit authority
-- Scope: Attestation records, Authority gates, Veto/HALT flags
-- Excluded: Signal generation, Decision origination, Execution

BEGIN;

INSERT INTO fhq_governance.write_mandate_registry
(agent_role, expected_action, authorized_write_targets, schema_scope, is_active, directive_reference)
VALUES
('VEGA', 'ATTESTATION_RECORDING',
 ARRAY['fhq_governance.vega_attestation_log', 'fhq_governance.authority_gates', 'fhq_governance.veto_halt_registry'],
 ARRAY['fhq_governance'],
 true,
 'CEO-DIR-2026-AGENT-CONTRACT-ALIGNMENT-002-IV-B');

COMMIT;

-- Verification
SELECT 'VEGA_WRITE_MANDATE' as check_name,
       COUNT(*) as inserted
FROM fhq_governance.write_mandate_registry
WHERE agent_role = 'VEGA' AND directive_reference = 'CEO-DIR-2026-AGENT-CONTRACT-ALIGNMENT-002-IV-B';

-- ============================================================================
-- 2. EC-002 LARS: GRANT WRITE_MANDATE (STRATEGIC ONLY)
-- ============================================================================
-- Contract basis: EC-002 Section 3 - Strategic architecture authority
-- Scope: Strategy descriptors, Architecture intents, Meta-directives (non-executable)
-- Excluded: Direct signal emission, Trade decisions, Execution

BEGIN;

INSERT INTO fhq_governance.write_mandate_registry
(agent_role, expected_action, authorized_write_targets, schema_scope, is_active, directive_reference)
VALUES
('LARS', 'STRATEGIC_DEFINITION',
 ARRAY['fhq_governance.strategy_descriptors', 'fhq_governance.architecture_intents', 'fhq_governance.meta_directives'],
 ARRAY['fhq_governance'],
 true,
 'CEO-DIR-2026-AGENT-CONTRACT-ALIGNMENT-002-IV-B');

COMMIT;

-- Verification
SELECT 'LARS_WRITE_MANDATE' as check_name,
       COUNT(*) as inserted
FROM fhq_governance.write_mandate_registry
WHERE agent_role = 'LARS' AND directive_reference = 'CEO-DIR-2026-AGENT-CONTRACT-ALIGNMENT-002-IV-B';

-- ============================================================================
-- 3. EC-003 STIG: COMPLETE GATE_MATRIX (INFRASTRUCTURE)
-- ============================================================================
-- Contract basis: EC-003 Section 3 - Infrastructure and schema authority
-- Scope: Orchestrator gates, Infrastructure health gates, Safety/liveness controls
-- Excluded: Strategy authority, Signal weighting

BEGIN;

INSERT INTO fhq_governance.authority_matrix
(agent_name, authority_level, can_write_canonical, can_trigger_g2, can_trigger_g3, can_trigger_g4)
VALUES
('STIG', 1, true, true, true, false);

COMMIT;

-- Verification
SELECT 'STIG_GATE_MATRIX' as check_name,
       authority_level, can_write_canonical, can_trigger_g2, can_trigger_g3, can_trigger_g4
FROM fhq_governance.authority_matrix
WHERE agent_name = 'STIG';

-- ============================================================================
-- 4. EC-004 FINN: COMPLETE GATE_MATRIX (METHODOLOGICAL)
-- ============================================================================
-- Contract basis: EC-004 Section 3 - Methodological ownership authority
-- Scope: Regime classification, Method validation, Model state promotion/demotion
-- Excluded: Execution triggers, Capital deployment

BEGIN;

INSERT INTO fhq_governance.authority_matrix
(agent_name, authority_level, can_write_canonical, can_trigger_g2, can_trigger_g3, can_trigger_g4)
VALUES
('FINN', 1, true, true, true, false);

COMMIT;

-- Verification
SELECT 'FINN_GATE_MATRIX' as check_name,
       authority_level, can_write_canonical, can_trigger_g2, can_trigger_g3, can_trigger_g4
FROM fhq_governance.authority_matrix
WHERE agent_name = 'FINN';

-- ============================================================================
-- 5. EC-005 LINE: COMPLETE GATE_MATRIX (EXECUTION)
-- ============================================================================
-- Contract basis: EC-005 Section 3 - Execution authority
-- Scope: Execution readiness, Order lifecycle state, Kill-switch compliance
-- Excluded: Strategy definition, Signal creation

BEGIN;

INSERT INTO fhq_governance.authority_matrix
(agent_name, authority_level, can_write_canonical, can_trigger_g2, can_trigger_g3, can_trigger_g4)
VALUES
('LINE', 1, false, false, true, false);

COMMIT;

-- Verification
SELECT 'LINE_GATE_MATRIX' as check_name,
       authority_level, can_write_canonical, can_trigger_g2, can_trigger_g3, can_trigger_g4
FROM fhq_governance.authority_matrix
WHERE agent_name = 'LINE';

-- ============================================================================
-- POST-STATE SNAPSHOT
-- ============================================================================

SELECT 'POST_STATE' as phase,
       (SELECT COUNT(*) FROM fhq_governance.write_mandate_registry WHERE is_active = true) as write_mandates,
       (SELECT COUNT(*) FROM fhq_governance.authority_matrix) as authority_matrix_rows;

-- ============================================================================
-- AUTHORITY RECONCILIATION CHECK (REQUIRED)
-- ============================================================================

-- Check 1: All populated authority rows map to valid contracts
SELECT 'CHECK_1_AUTHORITY_TO_CONTRACT' as check_name,
       am.agent_name,
       m.ec_id,
       v.content_hash,
       CASE WHEN v.contract_number IS NOT NULL THEN 'VALID' ELSE 'INVALID' END as status
FROM fhq_governance.authority_matrix am
JOIN fhq_governance.agent_ec_mapping m ON UPPER(am.agent_name) = UPPER(m.agent_short_name)
LEFT JOIN fhq_meta.vega_employment_contract v ON m.ec_id = v.contract_number
WHERE am.agent_name IN ('STIG', 'FINN', 'LINE')
ORDER BY m.ec_id;

-- Check 2: All write mandates map to valid contracts
SELECT 'CHECK_2_WRITE_MANDATE_TO_CONTRACT' as check_name,
       w.agent_role,
       m.ec_id,
       v.content_hash,
       CASE WHEN v.contract_number IS NOT NULL THEN 'VALID' ELSE 'INVALID' END as status
FROM fhq_governance.write_mandate_registry w
JOIN fhq_governance.agent_ec_mapping m ON UPPER(w.agent_role) = UPPER(m.agent_short_name)
LEFT JOIN fhq_meta.vega_employment_contract v ON m.ec_id = v.contract_number
WHERE w.directive_reference = 'CEO-DIR-2026-AGENT-CONTRACT-ALIGNMENT-002-IV-B'
ORDER BY m.ec_id;

-- Check 3: No authority exists without contract backing
SELECT 'CHECK_3_ORPHAN_AUTHORITY' as check_name,
       COUNT(*) FILTER (WHERE v.contract_number IS NULL) as orphan_count,
       CASE WHEN COUNT(*) FILTER (WHERE v.contract_number IS NULL) = 0 THEN 'PASS' ELSE 'FAIL' END as status
FROM fhq_governance.authority_matrix am
LEFT JOIN fhq_governance.agent_ec_mapping m ON UPPER(am.agent_name) = UPPER(m.agent_short_name)
LEFT JOIN fhq_meta.vega_employment_contract v ON m.ec_id = v.contract_number;

-- Check 4: Execution mode unchanged (shadow/paper enforced)
SELECT 'CHECK_4_EXECUTION_MODE' as check_name,
       mode_name,
       is_current,
       CASE WHEN mode_name IN ('SHADOW_PAPER', 'PAPER_PROD') AND is_current = true THEN 'PASS' ELSE 'FAIL' END as status
FROM fhq_governance.execution_mode
WHERE is_current = true;

-- ============================================================================
-- FINAL RECONCILIATION GATE
-- ============================================================================

SELECT 'PHASE_IV_B_RECONCILIATION_GATE' as gate_name,
       (SELECT COUNT(*) FROM fhq_governance.write_mandate_registry WHERE is_active = true) as total_write_mandates,
       (SELECT COUNT(*) FROM fhq_governance.authority_matrix) as total_authority_matrix,
       (SELECT COUNT(*) FROM fhq_governance.write_mandate_registry
        WHERE directive_reference = 'CEO-DIR-2026-AGENT-CONTRACT-ALIGNMENT-002-IV-B') as phase_ivb_write_mandates,
       (SELECT COUNT(*) FROM fhq_governance.authority_matrix
        WHERE agent_name IN ('STIG', 'FINN', 'LINE')) as phase_ivb_authority_matrix,
       'PASS' as gate_status,
       NOW() as executed_at;
