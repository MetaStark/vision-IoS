-- ============================================================================
-- MIGRATION 211: CNRP-001 COGNITIVE NODE REFRESH PROTOCOL
-- ============================================================================
-- CEO Directive: CEO-DIR-2026-009-B
-- Classification: STRATEGIC-CONSTITUTIONAL (Class A+)
-- Purpose: Register constitutional daemons for cognitive freshness
-- Author: STIG (CTO)
-- Date: 2026-01-07
--
-- Constitutional Basis:
--   ADR-004: Change Gates (G1-G4)
--   ADR-013: One-True-Source
--   ADR-017: LIDS Truth Engine
--   CEO-DIR-2026-007: Epistemic Memory
--
-- This migration establishes cognitive freshness as a CONSTITUTIONAL requirement.
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: REGISTER CNRP-001 CONSTITUTIONAL DAEMONS
-- ============================================================================

-- R1: CEIO Evidence Refresh Daemon
INSERT INTO fhq_execution.task_registry (
    task_id,
    task_name,
    gate_level,
    owned_by,
    executed_by,
    enabled,
    schedule_cron,
    config,
    created_at,
    updated_at
) VALUES (
    gen_random_uuid(),
    'ceio_evidence_refresh_daemon',
    'G2',
    'CEIO',
    'ORCHESTRATOR',
    true,
    '0 */4 * * *',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-009-B',
        'phase', 'R1',
        'purpose', 'Force-refresh all evidence sources for epistemic freshness',
        'script', '03_FUNCTIONS/ceio_evidence_refresh_daemon.py',
        'constraint', 'Evidence freshness must never exceed staleness threshold'
    ),
    NOW(),
    NOW()
) ON CONFLICT (task_name) DO UPDATE SET
    enabled = true,
    config = EXCLUDED.config,
    updated_at = NOW();

-- R2: CRIO Alpha Graph Rebuild
INSERT INTO fhq_execution.task_registry (
    task_id,
    task_name,
    gate_level,
    owned_by,
    executed_by,
    enabled,
    schedule_cron,
    config,
    created_at,
    updated_at
) VALUES (
    gen_random_uuid(),
    'crio_alpha_graph_rebuild',
    'G3',
    'CRIO',
    'ORCHESTRATOR',
    true,
    '30 */4 * * *',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-009-B',
        'phase', 'R2',
        'purpose', 'Reconstruct Alpha Graph from refreshed evidence only',
        'script', '03_FUNCTIONS/crio_alpha_graph_rebuild.py',
        'trigger', 'Post R1 completion',
        'constraint', 'No causal edge may reference stale evidence'
    ),
    NOW(),
    NOW()
) ON CONFLICT (task_name) DO UPDATE SET
    enabled = true,
    config = EXCLUDED.config,
    updated_at = NOW();

-- R3: CDMO Data Hygiene Attestation
INSERT INTO fhq_execution.task_registry (
    task_id,
    task_name,
    gate_level,
    owned_by,
    executed_by,
    enabled,
    schedule_cron,
    config,
    created_at,
    updated_at
) VALUES (
    gen_random_uuid(),
    'cdmo_data_hygiene_attestation',
    'G3',
    'CDMO',
    'ORCHESTRATOR',
    true,
    '0 0 * * *',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-009-B',
        'phase', 'R3',
        'purpose', 'Verify no deprecated or orphaned nodes remain active',
        'script', '03_FUNCTIONS/cdmo_data_hygiene_attestation.py',
        'output', 'Formal hygiene attestation'
    ),
    NOW(),
    NOW()
) ON CONFLICT (task_name) DO UPDATE SET
    enabled = true,
    config = EXCLUDED.config,
    updated_at = NOW();

-- R4: VEGA Epistemic Integrity Monitor
INSERT INTO fhq_execution.task_registry (
    task_id,
    task_name,
    gate_level,
    owned_by,
    executed_by,
    enabled,
    schedule_cron,
    config,
    created_at,
    updated_at
) VALUES (
    gen_random_uuid(),
    'vega_epistemic_integrity_monitor',
    'G1',
    'VEGA',
    'ORCHESTRATOR',
    true,
    '*/15 * * * *',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-009-B',
        'phase', 'R4',
        'purpose', 'Continuous monitoring of lineage and hash integrity',
        'script', '03_FUNCTIONS/vega_epistemic_integrity_monitor.py',
        'escalation', 'Immediate CEO escalation on violation'
    ),
    NOW(),
    NOW()
) ON CONFLICT (task_name) DO UPDATE SET
    enabled = true,
    config = EXCLUDED.config,
    updated_at = NOW();

-- ============================================================================
-- SECTION 2: CREATE CNRP CONFIGURATION TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.cnrp_configuration (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_key TEXT UNIQUE NOT NULL,
    config_value JSONB NOT NULL,
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'STIG',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert constitutional staleness thresholds (CEO-DIR-2026-009-B Section 4)
INSERT INTO fhq_governance.cnrp_configuration (config_key, config_value, created_by)
VALUES
    ('staleness_thresholds', jsonb_build_object(
        'evidence_nodes_hours', 24,
        'causal_edges_hours', 48,
        'previous_evidence_nodes_hours', 48,
        'previous_causal_edges_hours', 72,
        'directive', 'CEO-DIR-2026-009-B',
        'effective_date', NOW()::text
    ), 'CEO'),
    ('cnrp_phases', jsonb_build_object(
        'R1', jsonb_build_object('name', 'CEIO_EVIDENCE_REFRESH', 'gate', 'G2', 'frequency', '4h'),
        'R2', jsonb_build_object('name', 'CRIO_ALPHA_GRAPH_REBUILD', 'gate', 'G3', 'trigger', 'post_R1'),
        'R3', jsonb_build_object('name', 'CDMO_DATA_HYGIENE', 'gate', 'G3', 'frequency', 'daily'),
        'R4', jsonb_build_object('name', 'VEGA_INTEGRITY_MONITOR', 'gate', 'G1', 'frequency', '15m')
    ), 'CEO')
ON CONFLICT (config_key) DO UPDATE SET
    config_value = EXCLUDED.config_value,
    updated_at = NOW();

-- ============================================================================
-- SECTION 3: CREATE CNRP EXECUTION LOG
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.cnrp_execution_log (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_id TEXT NOT NULL,
    phase TEXT NOT NULL CHECK (phase IN ('R1', 'R2', 'R3', 'R4')),
    daemon_name TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'RUNNING' CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED', 'SKIPPED')),
    records_processed INTEGER DEFAULT 0,
    evidence_hash TEXT,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cnrp_exec_cycle ON fhq_governance.cnrp_execution_log(cycle_id);
CREATE INDEX IF NOT EXISTS idx_cnrp_exec_phase ON fhq_governance.cnrp_execution_log(phase);
CREATE INDEX IF NOT EXISTS idx_cnrp_exec_status ON fhq_governance.cnrp_execution_log(status);

-- ============================================================================
-- SECTION 4: LOG MIGRATION TO GOVERNANCE
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
    'CNRP_001_MIGRATION',
    'fhq_execution.task_registry',
    'MIGRATION',
    'STIG',
    'EXECUTED',
    'CEO-DIR-2026-009-B: Constitutional Cognitive Node Refresh Protocol implementation',
    jsonb_build_object(
        'migration', '211_cnrp001_cognitive_refresh_protocol',
        'directive', 'CEO-DIR-2026-009-B',
        'daemons_registered', ARRAY['ceio_evidence_refresh_daemon', 'crio_alpha_graph_rebuild', 'cdmo_data_hygiene_attestation', 'vega_epistemic_integrity_monitor'],
        'new_thresholds', jsonb_build_object('evidence_nodes', '24h', 'causal_edges', '48h'),
        'timestamp', NOW()
    )
);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify CNRP-001 tasks registered
SELECT task_name, gate_level, owned_by, enabled, schedule_cron
FROM fhq_execution.task_registry
WHERE task_name IN (
    'ceio_evidence_refresh_daemon',
    'crio_alpha_graph_rebuild',
    'cdmo_data_hygiene_attestation',
    'vega_epistemic_integrity_monitor'
)
ORDER BY owned_by;

-- Verify configuration stored
SELECT config_key, config_value
FROM fhq_governance.cnrp_configuration;
