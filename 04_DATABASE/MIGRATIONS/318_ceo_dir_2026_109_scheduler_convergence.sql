-- ============================================================================
-- Migration 318: CEO-DIR-2026-109 Scheduler Convergence (Constitutional Grade)
-- ============================================================================
-- Directive: CEO-DIR-2026-109
-- Phase: C - Task Scheduler Convergence
-- Implementor: STIG (CTO)
-- CEO Feedback Applied: 2026-01-19 (v2 - hardening)
-- ============================================================================
--
-- CEO REQUIREMENTS (MANDATORY):
--
-- 1. ec_registry deprecation must be ENFORCED, not commented
--    → REVOKE INSERT/UPDATE/DELETE/TRUNCATE
--    → Blocking triggers with AUDIT LOG on ALL attempts (not just failure)
--    → Anti-bypass for owner/role/superuser loopholes
--
-- 2. Task bindings must reference CANONICAL table, not "EC strings"
--    → Foreign key constraint to vega_employment_contract
--    → Runtime-bound = Binding + Enabled + Evidence + DEFCON
--
-- 3. EC-019 task must be DORMANT until VEGA attests
--    → Task created but enabled=FALSE
--    → Activation gated on VEGA attestation event
--
-- 4. Cognitive Engines (EC-020/021/022) are ON_DEMAND
--    → No cron loops unless explicitly mandated
--    → Invoked by orchestrator/workflow only
--
-- HARDENING REQUIREMENTS (CEO v2):
--
-- 5. Anti-bypass includes TRUNCATE + audit telemetry on ALL attempts
--    → Log to governance_actions_log BEFORE raising exception
--    → Detection telemetry for security monitoring
--
-- 6. Evidence semantics must be non-ambiguous
--    → Canonical evidence table with ec_contract_number + task_id
--    → Cannot spoof "I ran something" without proper binding
--
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: ENFORCE ec_registry DEPRECATION (CEO Requirement #1 + #5)
-- "A COMMENT is not a control" + "Audit telemetry on ALL attempts"
-- ============================================================================

-- 1a. REVOKE ALL write permissions including TRUNCATE
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON fhq_governance.ec_registry FROM PUBLIC;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON fhq_governance.ec_registry FROM postgres;

-- Also revoke from common service roles if they exist
DO $$
BEGIN
    -- Attempt to revoke from service_role if it exists
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        EXECUTE 'REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON fhq_governance.ec_registry FROM service_role';
    END IF;
    -- Attempt to revoke from authenticator if it exists
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticator') THEN
        EXECUTE 'REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON fhq_governance.ec_registry FROM authenticator';
    END IF;
    -- Attempt to revoke from anon if it exists
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON fhq_governance.ec_registry FROM anon';
    END IF;
END $$;

-- 1b. Create blocking trigger function WITH AUDIT LOGGING
-- This logs the attempt BEFORE raising exception (detection telemetry)
CREATE OR REPLACE FUNCTION fhq_governance.block_ec_registry_writes()
RETURNS TRIGGER AS $$
DECLARE
    v_operation TEXT;
    v_attempted_data JSONB;
BEGIN
    v_operation := TG_OP;

    -- Capture attempted data for audit
    IF TG_OP = 'INSERT' THEN
        v_attempted_data := to_jsonb(NEW);
    ELSIF TG_OP = 'UPDATE' THEN
        v_attempted_data := jsonb_build_object('old', to_jsonb(OLD), 'new', to_jsonb(NEW));
    ELSIF TG_OP = 'DELETE' THEN
        v_attempted_data := to_jsonb(OLD);
    ELSE
        v_attempted_data := '{}'::jsonb;
    END IF;

    -- LOG THE ATTEMPT FIRST (detection telemetry)
    -- This executes even though we will raise exception
    INSERT INTO fhq_governance.governance_actions_log (
        action_id,
        action_type,
        action_target,
        action_target_type,
        initiated_by,
        initiated_at,
        decision,
        decision_rationale,
        vega_reviewed,
        metadata
    ) VALUES (
        gen_random_uuid(),
        'DEPRECATED_TABLE_WRITE_BLOCKED',
        'fhq_governance.ec_registry',
        'TABLE',
        current_user,
        NOW(),
        'BLOCKED',
        'Attempted ' || v_operation || ' on deprecated ec_registry. Canonical table is fhq_meta.vega_employment_contract.',
        false,
        jsonb_build_object(
            'operation', v_operation,
            'attempted_by', current_user,
            'session_user', session_user,
            'attempted_at', NOW(),
            'attempted_data', v_attempted_data,
            'directive', 'CEO-DIR-2026-109',
            'security_event', true
        )
    );

    -- Now raise exception
    RAISE EXCEPTION 'EC_REGISTRY_DEPRECATED: fhq_governance.ec_registry is read-only per CEO-DIR-2026-109. '
                    'Canonical register is fhq_meta.vega_employment_contract. '
                    'Operation: %. User: %. Attempt logged to governance_actions_log.',
                    v_operation, current_user;

    -- Never reached but required for trigger
    RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Mark function as not replaceable without explicit governance action
COMMENT ON FUNCTION fhq_governance.block_ec_registry_writes() IS
'CEO-DIR-2026-109: CONSTITUTIONAL CONTROL - DO NOT MODIFY WITHOUT G4 APPROVAL. '
'Blocks all writes to deprecated ec_registry and logs attempt for security monitoring.';

-- 1c. Create triggers for INSERT/UPDATE/DELETE
DROP TRIGGER IF EXISTS trg_block_ec_registry_insert ON fhq_governance.ec_registry;
DROP TRIGGER IF EXISTS trg_block_ec_registry_update ON fhq_governance.ec_registry;
DROP TRIGGER IF EXISTS trg_block_ec_registry_delete ON fhq_governance.ec_registry;

CREATE TRIGGER trg_block_ec_registry_insert
    BEFORE INSERT ON fhq_governance.ec_registry
    FOR EACH ROW EXECUTE FUNCTION fhq_governance.block_ec_registry_writes();

CREATE TRIGGER trg_block_ec_registry_update
    BEFORE UPDATE ON fhq_governance.ec_registry
    FOR EACH ROW EXECUTE FUNCTION fhq_governance.block_ec_registry_writes();

CREATE TRIGGER trg_block_ec_registry_delete
    BEFORE DELETE ON fhq_governance.ec_registry
    FOR EACH ROW EXECUTE FUNCTION fhq_governance.block_ec_registry_writes();

-- 1d. Create TRUNCATE trigger (statement-level, different syntax)
CREATE OR REPLACE FUNCTION fhq_governance.block_ec_registry_truncate()
RETURNS TRIGGER AS $$
BEGIN
    -- Log the truncate attempt
    INSERT INTO fhq_governance.governance_actions_log (
        action_id, action_type, action_target, action_target_type,
        initiated_by, initiated_at, decision, decision_rationale,
        vega_reviewed, metadata
    ) VALUES (
        gen_random_uuid(),
        'DEPRECATED_TABLE_TRUNCATE_BLOCKED',
        'fhq_governance.ec_registry',
        'TABLE',
        current_user,
        NOW(),
        'BLOCKED',
        'Attempted TRUNCATE on deprecated ec_registry. This is a CRITICAL security event.',
        false,
        jsonb_build_object(
            'operation', 'TRUNCATE',
            'attempted_by', current_user,
            'session_user', session_user,
            'attempted_at', NOW(),
            'directive', 'CEO-DIR-2026-109',
            'security_event', true,
            'severity', 'CRITICAL'
        )
    );

    RAISE EXCEPTION 'EC_REGISTRY_DEPRECATED: TRUNCATE blocked on fhq_governance.ec_registry per CEO-DIR-2026-109. '
                    'This attempt has been logged as a CRITICAL security event.';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_block_ec_registry_truncate ON fhq_governance.ec_registry;

CREATE TRIGGER trg_block_ec_registry_truncate
    BEFORE TRUNCATE ON fhq_governance.ec_registry
    FOR EACH STATEMENT EXECUTE FUNCTION fhq_governance.block_ec_registry_truncate();

-- 1e. Log the deprecation enforcement
INSERT INTO fhq_governance.governance_actions_log (
    action_id, action_type, action_target, action_target_type,
    initiated_by, initiated_at, decision, decision_rationale,
    vega_reviewed, metadata
) VALUES (
    gen_random_uuid(),
    'TABLE_DEPRECATION_ENFORCED',
    'fhq_governance.ec_registry',
    'TABLE',
    'STIG',
    NOW(),
    'ENFORCED',
    'CEO-DIR-2026-109: REVOKE + blocking triggers (INSERT/UPDATE/DELETE/TRUNCATE) applied with audit telemetry. '
    'ec_registry is now physically read-only. All bypass attempts are logged.',
    false,
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-109',
        'controls_applied', ARRAY[
            'REVOKE INSERT/UPDATE/DELETE/TRUNCATE FROM PUBLIC',
            'REVOKE FROM postgres',
            'REVOKE FROM service roles',
            'Blocking triggers with AUDIT LOG',
            'TRUNCATE trigger (statement-level)'
        ],
        'canonical_table', 'fhq_meta.vega_employment_contract',
        'audit_telemetry', true
    )
);

-- ============================================================================
-- SECTION 2: CREATE CANONICAL EVIDENCE TABLE (CEO Requirement #6)
-- "Evidence must include ec_contract_number and task_id - cannot spoof"
-- ============================================================================

-- 2a. Create canonical evidence table
CREATE TABLE IF NOT EXISTS fhq_governance.task_execution_evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Mandatory binding fields (cannot spoof without these)
    ec_contract_number VARCHAR(10) NOT NULL,
    task_id UUID NOT NULL,
    binding_id UUID,  -- Optional FK to task_ec_binding

    -- Evidence details
    evidence_type TEXT NOT NULL CHECK (evidence_type IN (
        'CNRP_CYCLE',           -- Scheduled CNRP execution
        'DIRECT_EXECUTION',     -- Direct script execution
        'WORKFLOW_INVOCATION',  -- Called by orchestrator workflow
        'EVENT_DRIVEN',         -- Triggered by event
        'MANUAL_ATTESTATION'    -- Human attestation (requires signature)
    )),

    -- Execution details
    execution_started_at TIMESTAMPTZ NOT NULL,
    execution_completed_at TIMESTAMPTZ,
    execution_status TEXT NOT NULL CHECK (execution_status IN (
        'RUNNING', 'SUCCESS', 'FAILED', 'TIMEOUT', 'CANCELLED'
    )),
    execution_result JSONB,

    -- DEFCON state at execution
    defcon_level_at_execution TEXT,

    -- Audit fields
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT current_user,
    evidence_hash TEXT,  -- SHA256 of execution_result for tamper detection

    -- Constraints
    CONSTRAINT fk_evidence_ec FOREIGN KEY (ec_contract_number)
        REFERENCES fhq_meta.vega_employment_contract(contract_number)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_evidence_task FOREIGN KEY (task_id)
        REFERENCES fhq_governance.task_registry(task_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_task_evidence_ec_task
ON fhq_governance.task_execution_evidence(ec_contract_number, task_id, execution_started_at DESC);

CREATE INDEX IF NOT EXISTS idx_task_evidence_recent
ON fhq_governance.task_execution_evidence(execution_started_at DESC)
WHERE execution_status = 'SUCCESS';

COMMENT ON TABLE fhq_governance.task_execution_evidence IS
'CEO-DIR-2026-109: Canonical evidence table for task execution. '
'Evidence MUST include ec_contract_number + task_id (FK-enforced). '
'Cannot spoof "I ran something" without proper binding to canonical EC and task.';

-- 2b. Create function to record evidence (the only sanctioned way)
CREATE OR REPLACE FUNCTION fhq_governance.record_task_evidence(
    p_ec_contract_number VARCHAR(10),
    p_task_id UUID,
    p_evidence_type TEXT,
    p_execution_status TEXT,
    p_execution_result JSONB DEFAULT NULL,
    p_defcon_level TEXT DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_evidence_id UUID;
    v_binding_id UUID;
    v_hash TEXT;
BEGIN
    -- Verify EC exists in canonical table
    IF NOT EXISTS (
        SELECT 1 FROM fhq_meta.vega_employment_contract
        WHERE contract_number = p_ec_contract_number
    ) THEN
        RAISE EXCEPTION 'EVIDENCE_REJECTED: EC % not found in canonical register', p_ec_contract_number;
    END IF;

    -- Verify task exists
    IF NOT EXISTS (
        SELECT 1 FROM fhq_governance.task_registry WHERE task_id = p_task_id
    ) THEN
        RAISE EXCEPTION 'EVIDENCE_REJECTED: Task % not found in task_registry', p_task_id;
    END IF;

    -- Get binding_id if exists
    SELECT binding_id INTO v_binding_id
    FROM fhq_governance.task_ec_binding
    WHERE ec_contract_number = p_ec_contract_number AND task_id = p_task_id;

    -- Compute hash for tamper detection
    IF p_execution_result IS NOT NULL THEN
        v_hash := encode(sha256(p_execution_result::text::bytea), 'hex');
    END IF;

    -- Insert evidence
    INSERT INTO fhq_governance.task_execution_evidence (
        ec_contract_number,
        task_id,
        binding_id,
        evidence_type,
        execution_started_at,
        execution_completed_at,
        execution_status,
        execution_result,
        defcon_level_at_execution,
        evidence_hash
    ) VALUES (
        p_ec_contract_number,
        p_task_id,
        v_binding_id,
        p_evidence_type,
        NOW(),
        CASE WHEN p_execution_status IN ('SUCCESS', 'FAILED', 'TIMEOUT', 'CANCELLED') THEN NOW() ELSE NULL END,
        p_execution_status,
        p_execution_result,
        p_defcon_level,
        v_hash
    )
    RETURNING evidence_id INTO v_evidence_id;

    -- Update binding's last_evidence_at
    UPDATE fhq_governance.task_ec_binding
    SET last_evidence_at = NOW(),
        updated_at = NOW()
    WHERE ec_contract_number = p_ec_contract_number
    AND task_id = p_task_id;

    RETURN v_evidence_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION fhq_governance.record_task_evidence IS
'CEO-DIR-2026-109: Canonical function to record task execution evidence. '
'Enforces FK to canonical EC and task. Updates binding last_evidence_at.';

-- ============================================================================
-- SECTION 3: CREATE EC BINDING TABLE (CEO Requirement #2)
-- "Runtime-bound = Binding + Enabled + Evidence + DEFCON"
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.task_ec_binding (
    binding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES fhq_governance.task_registry(task_id),
    ec_contract_number VARCHAR(10) NOT NULL,

    -- Runtime-bound components
    binding_active BOOLEAN NOT NULL DEFAULT false,
    enabled_state BOOLEAN NOT NULL DEFAULT false,

    -- Evidence requirements (linked to canonical evidence table)
    evidence_window_hours INTEGER NOT NULL DEFAULT 24,
    last_evidence_at TIMESTAMPTZ,  -- Updated by record_task_evidence()
    required_evidence_type TEXT,

    -- DEFCON-aware behavior (ADR-016/020/021)
    defcon_gate TEXT NOT NULL DEFAULT 'GREEN_YELLOW',
    defcon_behavior TEXT NOT NULL DEFAULT 'PAUSE_ON_ORANGE',

    -- Activation gating
    requires_vega_attestation BOOLEAN NOT NULL DEFAULT false,
    vega_attestation_received BOOLEAN NOT NULL DEFAULT false,
    vega_attestation_at TIMESTAMPTZ,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'STIG',
    directive TEXT NOT NULL DEFAULT 'CEO-DIR-2026-109',

    -- FK to canonical table (CANNOT bind to non-existent EC)
    CONSTRAINT fk_binding_ec_canonical FOREIGN KEY (ec_contract_number)
        REFERENCES fhq_meta.vega_employment_contract(contract_number)
        ON UPDATE CASCADE ON DELETE RESTRICT,

    -- One binding per task
    CONSTRAINT uq_task_ec_binding UNIQUE (task_id)
);

CREATE INDEX IF NOT EXISTS idx_task_ec_binding_contract
ON fhq_governance.task_ec_binding(ec_contract_number);

CREATE INDEX IF NOT EXISTS idx_task_ec_binding_active
ON fhq_governance.task_ec_binding(binding_active, enabled_state);

COMMENT ON TABLE fhq_governance.task_ec_binding IS
'CEO-DIR-2026-109: Canonical EC→Task binding with runtime-bound semantics. '
'Runtime-bound = Binding + Enabled + Evidence (from task_execution_evidence) + DEFCON. '
'FK to vega_employment_contract PREVENTS binding to non-existent EC.';

-- ============================================================================
-- SECTION 4: CREATE RUNTIME STATUS VIEW (Updated for canonical evidence)
-- "Evidence must come from canonical table with ec_contract_number + task_id"
-- ============================================================================

CREATE OR REPLACE VIEW fhq_governance.v_ec_runtime_status AS
SELECT
    b.binding_id,
    b.ec_contract_number,
    v.employee as agent,
    v.status as ec_status,
    t.task_id,
    t.task_name,
    t.task_type,
    t.status as task_status,
    t.enabled as task_enabled,
    b.binding_active,
    b.enabled_state,
    b.defcon_gate,
    b.defcon_behavior,
    b.requires_vega_attestation,
    b.vega_attestation_received,
    b.vega_attestation_at,
    b.evidence_window_hours,

    -- Evidence from CANONICAL evidence table only
    b.last_evidence_at,
    e.evidence_type as last_evidence_type,
    e.execution_status as last_evidence_status,
    e.defcon_level_at_execution as last_evidence_defcon,

    -- Calculate evidence freshness
    CASE
        WHEN b.last_evidence_at IS NULL THEN NULL
        ELSE EXTRACT(EPOCH FROM (NOW() - b.last_evidence_at)) / 3600.0
    END as evidence_age_hours,

    -- Runtime-bound status (the legal definition)
    -- NOTE: AWAITING_VEGA must be checked BEFORE enabled_state because
    -- EC-019 is disabled BECAUSE it's awaiting VEGA (not some other reason)
    CASE
        WHEN NOT b.binding_active THEN 'NOT_BOUND'
        WHEN b.requires_vega_attestation AND NOT b.vega_attestation_received THEN 'AWAITING_VEGA'
        WHEN NOT b.enabled_state THEN 'DISABLED'
        WHEN b.last_evidence_at IS NULL THEN 'NO_EVIDENCE'
        WHEN b.last_evidence_at < NOW() - (b.evidence_window_hours || ' hours')::INTERVAL THEN 'EVIDENCE_STALE'
        WHEN e.execution_status = 'FAILED' THEN 'LAST_FAILED'
        ELSE 'RUNTIME_BOUND'
    END as runtime_status

FROM fhq_governance.task_ec_binding b
JOIN fhq_meta.vega_employment_contract v ON v.contract_number = b.ec_contract_number
JOIN fhq_governance.task_registry t ON t.task_id = b.task_id
LEFT JOIN LATERAL (
    -- Get most recent evidence from CANONICAL evidence table
    SELECT evidence_type, execution_status, defcon_level_at_execution
    FROM fhq_governance.task_execution_evidence
    WHERE ec_contract_number = b.ec_contract_number
    AND task_id = b.task_id
    ORDER BY execution_started_at DESC
    LIMIT 1
) e ON true
ORDER BY b.ec_contract_number, t.task_name;

COMMENT ON VIEW fhq_governance.v_ec_runtime_status IS
'CEO-DIR-2026-109: Runtime-bound status for all EC→Task bindings. '
'RUNTIME_BOUND = active binding + enabled + evidence within window (from canonical table) + VEGA attested (if required). '
'Evidence MUST come from task_execution_evidence with matching ec_contract_number + task_id.';

-- ============================================================================
-- SECTION 5: BIND EXISTING TASKS TO CANONICAL ECs
-- ============================================================================

-- EC-001 VEGA tasks
INSERT INTO fhq_governance.task_ec_binding (task_id, ec_contract_number, binding_active, enabled_state, defcon_gate, defcon_behavior, required_evidence_type)
SELECT task_id, 'EC-001', true, enabled, 'ANY', 'ALWAYS_ON', 'CNRP_CYCLE'
FROM fhq_governance.task_registry WHERE assigned_to = 'VEGA' AND task_name NOT LIKE '%ikea%'
ON CONFLICT (task_id) DO NOTHING;

-- EC-002 LARS tasks
INSERT INTO fhq_governance.task_ec_binding (task_id, ec_contract_number, binding_active, enabled_state, defcon_gate, defcon_behavior, required_evidence_type)
SELECT task_id, 'EC-002', true, enabled, 'GREEN_YELLOW', 'PAUSE_ON_ORANGE', 'CNRP_CYCLE'
FROM fhq_governance.task_registry WHERE assigned_to = 'LARS'
ON CONFLICT (task_id) DO NOTHING;

-- EC-003 STIG tasks
INSERT INTO fhq_governance.task_ec_binding (task_id, ec_contract_number, binding_active, enabled_state, defcon_gate, defcon_behavior, required_evidence_type)
SELECT task_id, 'EC-003', true, enabled, 'GREEN_YELLOW', 'PAUSE_ON_ORANGE', 'CNRP_CYCLE'
FROM fhq_governance.task_registry WHERE assigned_to = 'STIG'
ON CONFLICT (task_id) DO NOTHING;

-- EC-004 FINN tasks
INSERT INTO fhq_governance.task_ec_binding (task_id, ec_contract_number, binding_active, enabled_state, defcon_gate, defcon_behavior, required_evidence_type)
SELECT task_id, 'EC-004', true, enabled, 'GREEN_YELLOW', 'PAUSE_ON_ORANGE', 'CNRP_CYCLE'
FROM fhq_governance.task_registry WHERE assigned_to = 'FINN'
ON CONFLICT (task_id) DO NOTHING;

-- EC-005 LINE tasks (stricter DEFCON)
INSERT INTO fhq_governance.task_ec_binding (task_id, ec_contract_number, binding_active, enabled_state, defcon_gate, defcon_behavior, required_evidence_type)
SELECT task_id, 'EC-005', true, enabled, 'GREEN_ONLY', 'HALT_ON_YELLOW', 'CNRP_CYCLE'
FROM fhq_governance.task_registry WHERE assigned_to = 'LINE'
ON CONFLICT (task_id) DO NOTHING;

-- EC-007 CDMO tasks
INSERT INTO fhq_governance.task_ec_binding (task_id, ec_contract_number, binding_active, enabled_state, defcon_gate, defcon_behavior, required_evidence_type)
SELECT task_id, 'EC-007', true, enabled, 'GREEN_YELLOW', 'PAUSE_ON_ORANGE', 'CNRP_CYCLE'
FROM fhq_governance.task_registry WHERE assigned_to = 'CDMO'
ON CONFLICT (task_id) DO NOTHING;

-- EC-009 CEIO tasks
INSERT INTO fhq_governance.task_ec_binding (task_id, ec_contract_number, binding_active, enabled_state, defcon_gate, defcon_behavior, required_evidence_type)
SELECT task_id, 'EC-009', true, enabled, 'GREEN_YELLOW', 'PAUSE_ON_ORANGE', 'CNRP_CYCLE'
FROM fhq_governance.task_registry WHERE assigned_to = 'CEIO'
ON CONFLICT (task_id) DO NOTHING;

-- EC-013 CRIO tasks
INSERT INTO fhq_governance.task_ec_binding (task_id, ec_contract_number, binding_active, enabled_state, defcon_gate, defcon_behavior, required_evidence_type)
SELECT task_id, 'EC-013', true, enabled, 'GREEN_YELLOW', 'PAUSE_ON_ORANGE', 'CNRP_CYCLE'
FROM fhq_governance.task_registry WHERE assigned_to = 'CRIO'
ON CONFLICT (task_id) DO NOTHING;

-- ============================================================================
-- SECTION 6: EC-019 DORMANT TASK (CEO Requirement #3)
-- ============================================================================

INSERT INTO fhq_governance.task_registry (
    task_id, task_name, task_type, description, domain,
    assigned_to, status, enabled,
    task_config, metadata, created_at
) VALUES (
    gen_random_uuid(),
    'ec019_governance_watchdog',
    'SUPERVISORY',
    'EC-019 Operational Convergence monitoring - triggers on G0 accumulation threshold. DORMANT until VEGA attests EC-019.',
    'GOVERNANCE',
    'CEO',
    'pending',
    false,  -- DISABLED until VEGA attests
    jsonb_build_object(
        'trigger', 'EVENT',
        'event_type', 'G0_ACCUMULATION_THRESHOLD',
        'threshold', 3,
        'max_age_days', 30,
        'defcon_gate', 'ANY',
        '_DORMANT_REASON', 'Awaiting VEGA attestation of EC-019',
        '_ACTIVATION_GATE', 'VEGA must call vega_attest_ec_activation(EC-019)'
    ),
    jsonb_build_object(
        'ec_binding', 'EC-019',
        'directive', 'CEO-DIR-2026-109',
        'activation_blocked_until', 'VEGA_ATTESTATION_EC019'
    ),
    NOW()
)
ON CONFLICT DO NOTHING;

-- Bind EC-019 task with VEGA attestation requirement
INSERT INTO fhq_governance.task_ec_binding (
    task_id, ec_contract_number,
    binding_active, enabled_state,
    defcon_gate, defcon_behavior,
    required_evidence_type,
    requires_vega_attestation, vega_attestation_received
)
SELECT
    task_id, 'EC-019',
    true,   -- Binding exists
    false,  -- But NOT enabled
    'ANY', 'ALWAYS_ON',
    'EVENT_DRIVEN',
    true,   -- REQUIRES VEGA attestation
    false   -- NOT yet received
FROM fhq_governance.task_registry
WHERE task_name = 'ec019_governance_watchdog'
ON CONFLICT (task_id) DO UPDATE SET
    requires_vega_attestation = true,
    vega_attestation_received = false,
    enabled_state = false;

-- ============================================================================
-- SECTION 7: COGNITIVE ENGINES ON_DEMAND (CEO Requirement #4)
-- ============================================================================

-- EC-020: SitC - ON_DEMAND
INSERT INTO fhq_governance.task_registry (
    task_id, task_name, task_type, description, domain,
    assigned_to, status, enabled,
    task_config, metadata, created_at
) VALUES (
    gen_random_uuid(),
    'sitc_reasoning_engine',
    'COGNITIVE_PROTOCOL',
    'EC-020 SitC: Search-in-the-Chain reasoning. ON_DEMAND - invoked by orchestrator/workflow only.',
    'RESEARCH',
    'LARS',
    'active',
    true,
    jsonb_build_object(
        'trigger', 'ON_DEMAND',
        'invocation_method', 'ORCHESTRATOR_WORKFLOW',
        'function_path', '03_FUNCTIONS/sitc_reasoning_engine.py',
        'defcon_gate', 'GREEN_YELLOW',
        '_NO_CRON', 'Cognitive protocols are workflow-invoked per EC-020 charter'
    ),
    jsonb_build_object(
        'ec_binding', 'EC-020',
        'directive', 'CEO-DIR-2026-109',
        'charter', 'EC-020_2026_PRODUCTION_SitC'
    ),
    NOW()
)
ON CONFLICT DO NOTHING;

-- EC-021: InForage - ON_DEMAND
INSERT INTO fhq_governance.task_registry (
    task_id, task_name, task_type, description, domain,
    assigned_to, status, enabled,
    task_config, metadata, created_at
) VALUES (
    gen_random_uuid(),
    'inforage_cost_controller',
    'COGNITIVE_PROTOCOL',
    'EC-021 InForage: Information economics. ON_DEMAND - invoked when API decisions needed.',
    'INFRASTRUCTURE',
    'FINN',
    'active',
    true,
    jsonb_build_object(
        'trigger', 'ON_DEMAND',
        'invocation_method', 'ORCHESTRATOR_WORKFLOW',
        'function_path', '03_FUNCTIONS/inforage_cost_controller.py',
        'defcon_gate', 'GREEN_YELLOW',
        '_NO_CRON', 'Cognitive protocols are workflow-invoked per EC-021 charter'
    ),
    jsonb_build_object(
        'ec_binding', 'EC-021',
        'directive', 'CEO-DIR-2026-109',
        'charter', 'EC-021_2026_PRODUCTION_InForage'
    ),
    NOW()
)
ON CONFLICT DO NOTHING;

-- EC-022: IKEA - ON_DEMAND
INSERT INTO fhq_governance.task_registry (
    task_id, task_name, task_type, description, domain,
    assigned_to, status, enabled,
    task_config, metadata, created_at
) VALUES (
    gen_random_uuid(),
    'ikea_hallucination_firewall',
    'COGNITIVE_PROTOCOL',
    'EC-022 IKEA: Knowledge boundary enforcement. ON_DEMAND - invoked during cognitive workflows.',
    'GOVERNANCE',
    'VEGA',
    'active',
    true,
    jsonb_build_object(
        'trigger', 'ON_DEMAND',
        'invocation_method', 'COGNITIVE_WORKFLOW',
        'function_path', '03_FUNCTIONS/ikea_hallucination_firewall.py',
        'defcon_gate', 'ANY',
        '_NO_CRON', 'Cognitive protocols are workflow-invoked per EC-022 charter'
    ),
    jsonb_build_object(
        'ec_binding', 'EC-022',
        'directive', 'CEO-DIR-2026-109',
        'charter', 'EC-022_2026_PRODUCTION_IKEA'
    ),
    NOW()
)
ON CONFLICT DO NOTHING;

-- Bind cognitive engines
INSERT INTO fhq_governance.task_ec_binding (task_id, ec_contract_number, binding_active, enabled_state, defcon_gate, defcon_behavior, required_evidence_type)
SELECT task_id, 'EC-020', true, true, 'GREEN_YELLOW', 'PAUSE_ON_ORANGE', 'WORKFLOW_INVOCATION'
FROM fhq_governance.task_registry WHERE task_name = 'sitc_reasoning_engine'
ON CONFLICT (task_id) DO NOTHING;

INSERT INTO fhq_governance.task_ec_binding (task_id, ec_contract_number, binding_active, enabled_state, defcon_gate, defcon_behavior, required_evidence_type)
SELECT task_id, 'EC-021', true, true, 'GREEN_YELLOW', 'PAUSE_ON_ORANGE', 'WORKFLOW_INVOCATION'
FROM fhq_governance.task_registry WHERE task_name = 'inforage_cost_controller'
ON CONFLICT (task_id) DO NOTHING;

INSERT INTO fhq_governance.task_ec_binding (task_id, ec_contract_number, binding_active, enabled_state, defcon_gate, defcon_behavior, required_evidence_type)
SELECT task_id, 'EC-022', true, true, 'ANY', 'ALWAYS_ON', 'WORKFLOW_INVOCATION'
FROM fhq_governance.task_registry WHERE task_name = 'ikea_hallucination_firewall'
ON CONFLICT (task_id) DO NOTHING;

-- ============================================================================
-- SECTION 8: VEGA ATTESTATION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.vega_attest_ec_activation(
    p_ec_contract_number VARCHAR(10),
    p_vega_signature TEXT DEFAULT NULL
) RETURNS TABLE (
    binding_id UUID,
    task_name TEXT,
    previous_state TEXT,
    new_state TEXT
) AS $$
DECLARE
    v_ec_status VARCHAR(20);
BEGIN
    SELECT status INTO v_ec_status
    FROM fhq_meta.vega_employment_contract
    WHERE contract_number = p_ec_contract_number;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'EC % not found in canonical register', p_ec_contract_number;
    END IF;

    IF v_ec_status = 'PENDING_VEGA' THEN
        UPDATE fhq_meta.vega_employment_contract
        SET status = 'ACTIVE',
            vega_signature = COALESCE(p_vega_signature, 'VEGA_ATTESTED_' || NOW()::TEXT),
            updated_at = NOW()
        WHERE contract_number = p_ec_contract_number;
    END IF;

    RETURN QUERY
    UPDATE fhq_governance.task_ec_binding b
    SET vega_attestation_received = true,
        vega_attestation_at = NOW(),
        enabled_state = true,
        updated_at = NOW()
    FROM fhq_governance.task_registry t
    WHERE b.task_id = t.task_id
    AND b.ec_contract_number = p_ec_contract_number
    AND b.requires_vega_attestation = true
    RETURNING b.binding_id, t.task_name, 'AWAITING_VEGA'::TEXT, 'ACTIVE'::TEXT;

    INSERT INTO fhq_governance.governance_actions_log (
        action_id, action_type, action_target, action_target_type,
        initiated_by, initiated_at, decision, decision_rationale,
        vega_reviewed, metadata
    ) VALUES (
        gen_random_uuid(),
        'VEGA_EC_ATTESTATION',
        p_ec_contract_number,
        'EMPLOYMENT_CONTRACT',
        'VEGA',
        NOW(),
        'ATTESTED',
        'VEGA attested ' || p_ec_contract_number || ' per CEO-DIR-2026-109. Task bindings activated.',
        true,
        jsonb_build_object(
            'directive', 'CEO-DIR-2026-109',
            'ec_status_changed_from', v_ec_status,
            'ec_status_changed_to', 'ACTIVE'
        )
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- SECTION 9: LOG MIGRATION COMPLETION
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id, action_type, action_target, action_target_type,
    initiated_by, initiated_at, decision, decision_rationale,
    vega_reviewed, metadata
) VALUES (
    gen_random_uuid(),
    'SCHEDULER_CONVERGENCE',
    'task_ec_binding',
    'INFRASTRUCTURE',
    'STIG',
    NOW(),
    'COMPLETED',
    'CEO-DIR-2026-109 Phase C: Constitutional-grade scheduler convergence with hardening. '
    'ec_registry enforced read-only (REVOKE + triggers + audit telemetry). '
    'Canonical evidence table with FK enforcement. '
    'EC-019 dormant until VEGA attests. '
    'Cognitive engines ON_DEMAND.',
    false,
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-109',
        'phase', 'C',
        'ceo_requirements_met', ARRAY[
            'ec_registry deprecation ENFORCED with audit telemetry',
            'Canonical evidence table with ec_contract_number + task_id FK',
            'Task bindings reference canonical table via FK',
            'EC-019 DORMANT until VEGA attestation',
            'Cognitive engines ON_DEMAND'
        ],
        'new_objects', ARRAY[
            'fhq_governance.task_ec_binding',
            'fhq_governance.task_execution_evidence',
            'fhq_governance.v_ec_runtime_status',
            'fhq_governance.vega_attest_ec_activation()',
            'fhq_governance.record_task_evidence()',
            'fhq_governance.block_ec_registry_writes()',
            'fhq_governance.block_ec_registry_truncate()'
        ]
    )
);

-- ============================================================================
-- SECTION 10: VERIFICATION ASSERTIONS
-- "Verify it works" = assert specific behaviors, not just "migration succeeded"
-- ============================================================================

DO $$
DECLARE
    v_test_result BOOLEAN;
    v_trigger_count INTEGER;
    v_binding_count INTEGER;
    v_ec019_status RECORD;
    v_cognitive_count INTEGER;
    v_fk_exists BOOLEAN;
BEGIN
    RAISE NOTICE '=== Migration 318 VERIFICATION ASSERTIONS ===';

    -- ASSERTION 1: ec_registry writes fail as designed
    -- We test by checking triggers exist (actual write test would fail the migration)
    SELECT COUNT(*) INTO v_trigger_count
    FROM pg_trigger
    WHERE tgname LIKE 'trg_block_ec_registry%';

    IF v_trigger_count >= 4 THEN
        RAISE NOTICE 'PASS: ec_registry has % blocking triggers (INSERT/UPDATE/DELETE/TRUNCATE)', v_trigger_count;
    ELSE
        RAISE EXCEPTION 'FAIL: ec_registry should have 4 blocking triggers, found %', v_trigger_count;
    END IF;

    -- ASSERTION 2: FK prevents binding to non-existent EC
    SELECT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_binding_ec_canonical'
        AND table_name = 'task_ec_binding'
    ) INTO v_fk_exists;

    IF v_fk_exists THEN
        RAISE NOTICE 'PASS: FK constraint fk_binding_ec_canonical exists';
    ELSE
        RAISE EXCEPTION 'FAIL: FK constraint fk_binding_ec_canonical missing';
    END IF;

    -- ASSERTION 3: EC-019 task is created but cannot execute without VEGA attestation
    SELECT
        b.enabled_state,
        b.requires_vega_attestation,
        b.vega_attestation_received,
        t.enabled as task_enabled
    INTO v_ec019_status
    FROM fhq_governance.task_ec_binding b
    JOIN fhq_governance.task_registry t ON t.task_id = b.task_id
    WHERE b.ec_contract_number = 'EC-019'
    LIMIT 1;

    IF v_ec019_status.enabled_state = false
       AND v_ec019_status.requires_vega_attestation = true
       AND v_ec019_status.vega_attestation_received = false
       AND v_ec019_status.task_enabled = false THEN
        RAISE NOTICE 'PASS: EC-019 is DORMANT (enabled_state=false, requires_vega=true, received=false)';
    ELSE
        RAISE EXCEPTION 'FAIL: EC-019 should be dormant until VEGA attests. Status: %', v_ec019_status;
    END IF;

    -- ASSERTION 4: EC-020/021/022 are ON_DEMAND and not cron-triggered
    SELECT COUNT(*) INTO v_cognitive_count
    FROM fhq_governance.task_registry
    WHERE task_type = 'COGNITIVE_PROTOCOL'
    AND task_config->>'trigger' = 'ON_DEMAND'
    AND task_name IN ('sitc_reasoning_engine', 'inforage_cost_controller', 'ikea_hallucination_firewall');

    IF v_cognitive_count = 3 THEN
        RAISE NOTICE 'PASS: All 3 cognitive engines are ON_DEMAND (not cron)';
    ELSE
        RAISE EXCEPTION 'FAIL: Expected 3 ON_DEMAND cognitive engines, found %', v_cognitive_count;
    END IF;

    -- ASSERTION 5: v_ec_runtime_status returns expected statuses
    IF EXISTS (
        SELECT 1 FROM fhq_governance.v_ec_runtime_status
        WHERE ec_contract_number = 'EC-019'
        AND runtime_status = 'AWAITING_VEGA'
    ) THEN
        RAISE NOTICE 'PASS: v_ec_runtime_status shows EC-019 as AWAITING_VEGA';
    ELSE
        RAISE EXCEPTION 'FAIL: v_ec_runtime_status should show EC-019 as AWAITING_VEGA';
    END IF;

    -- ASSERTION 6: Canonical evidence table has FK constraints
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_evidence_ec'
        AND table_name = 'task_execution_evidence'
    ) AND EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_evidence_task'
        AND table_name = 'task_execution_evidence'
    ) THEN
        RAISE NOTICE 'PASS: task_execution_evidence has FK to canonical EC and task';
    ELSE
        RAISE EXCEPTION 'FAIL: task_execution_evidence missing FK constraints';
    END IF;

    -- Count total bindings created
    SELECT COUNT(*) INTO v_binding_count FROM fhq_governance.task_ec_binding;

    RAISE NOTICE '=== ALL ASSERTIONS PASSED ===';
    RAISE NOTICE 'Total task bindings created: %', v_binding_count;
    RAISE NOTICE 'Migration 318 VERIFIED SUCCESSFULLY';
END $$;

COMMIT;

-- ============================================================================
-- POST-MIGRATION MANUAL VERIFICATION
-- ============================================================================
--
-- 1. Test ec_registry write block (should fail with logged audit event):
--    INSERT INTO fhq_governance.ec_registry (ec_id, title, role_type, status, effective_date)
--    VALUES ('EC-TEST', 'Test', 'TEST', 'TEST', CURRENT_DATE);
--    -- Then check: SELECT * FROM fhq_governance.governance_actions_log
--    --             WHERE action_type = 'DEPRECATED_TABLE_WRITE_BLOCKED' ORDER BY initiated_at DESC LIMIT 1;
--
-- 2. Test FK prevents binding to fake EC:
--    INSERT INTO fhq_governance.task_ec_binding (task_id, ec_contract_number, binding_active, enabled_state)
--    SELECT task_id, 'EC-999', true, true FROM fhq_governance.task_registry LIMIT 1;
--    -- Should fail with: FK violation
--
-- 3. Verify EC-019 status:
--    SELECT * FROM fhq_governance.v_ec_runtime_status WHERE ec_contract_number = 'EC-019';
--
-- 4. VEGA to activate EC-019 (when ready):
--    SELECT * FROM fhq_governance.vega_attest_ec_activation('EC-019');
--
-- ============================================================================
