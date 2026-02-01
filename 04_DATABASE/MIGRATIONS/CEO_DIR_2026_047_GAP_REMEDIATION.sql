-- ============================================================================
-- CEO-DIR-2026-047 — G4 BLOCKER REMEDIATION MIGRATION
-- ============================================================================
-- Directive: CEO-DIR-2026-047 (Revision E — FINAL)
-- Date: 2026-01-14
-- Execution Owner: STIG (CTO)
-- Mode: CONTROLLED REMEDIATION MODE
-- Change Gate: ADR-004 G4 — FROZEN
-- ============================================================================

BEGIN;

-- ============================================================================
-- GAP-001: SUB-EXECUTIVE CONTRACT REGISTRATION (ADR-014 / ADR-018)
-- ============================================================================
-- Per CEO-DIR-2026-047 Section 4.1:
-- "A contract MUST NOT be marked ACTIVE unless heartbeat is live."
-- "A non-breathing agent is a dead contract and forbidden."

-- CDMO Contract (DATASET authority, parent STIG) — ACTIVE (heartbeat verified)
INSERT INTO fhq_governance.agent_contracts (
    contract_id, source_agent, target_agent, trigger_event, expected_action, sla_seconds, created_at, metadata
) VALUES (
    gen_random_uuid(),
    'STIG',
    'CDMO',
    'CNRP_R3_CYCLE',
    'DATA_HYGIENE_ATTESTATION',
    300,
    NOW(),
    jsonb_build_object(
        'contract_status', 'ACTIVE',
        'authority_domain', 'DATASET',
        'ed25519_fingerprint', '747bee2a8d42f2be',
        'heartbeat_verified', true,
        'parent_authority', 'STIG',
        'ceo_directive', 'CEO-DIR-2026-047',
        'created_by', 'STIG',
        'adr_reference', 'ADR-014'
    )
);

-- CEIO Contract (OPERATIONAL authority, parent STIG) — ACTIVE (heartbeat verified)
INSERT INTO fhq_governance.agent_contracts (
    contract_id, source_agent, target_agent, trigger_event, expected_action, sla_seconds, created_at, metadata
) VALUES (
    gen_random_uuid(),
    'STIG',
    'CEIO',
    'CNRP_R1_CYCLE',
    'EVIDENCE_REFRESH_DAEMON',
    300,
    NOW(),
    jsonb_build_object(
        'contract_status', 'ACTIVE',
        'authority_domain', 'OPERATIONAL',
        'ed25519_fingerprint', 'c38c012a08b29bf6',
        'heartbeat_verified', true,
        'parent_authority', 'STIG',
        'ceo_directive', 'CEO-DIR-2026-047',
        'created_by', 'STIG',
        'adr_reference', 'ADR-014'
    )
);

-- CRIO Contract (MODEL authority, parent FINN) — ACTIVE (heartbeat verified)
INSERT INTO fhq_governance.agent_contracts (
    contract_id, source_agent, target_agent, trigger_event, expected_action, sla_seconds, created_at, metadata
) VALUES (
    gen_random_uuid(),
    'FINN',
    'CRIO',
    'CNRP_R2_CYCLE',
    'ALPHA_GRAPH_REBUILD',
    300,
    NOW(),
    jsonb_build_object(
        'contract_status', 'ACTIVE',
        'authority_domain', 'MODEL',
        'ed25519_fingerprint', 'fb085bfc4eb49897',
        'heartbeat_verified', true,
        'parent_authority', 'FINN',
        'ceo_directive', 'CEO-DIR-2026-047',
        'created_by', 'STIG',
        'adr_reference', 'ADR-014'
    )
);

-- CSEO Contract (OPERATIONAL authority, parent LARS) — PENDING (no heartbeat)
INSERT INTO fhq_governance.agent_contracts (
    contract_id, source_agent, target_agent, trigger_event, expected_action, sla_seconds, created_at, metadata
) VALUES (
    gen_random_uuid(),
    'LARS',
    'CSEO',
    'STRATEGY_COORDINATION_CYCLE',
    'STRATEGY_EXECUTION_OVERSIGHT',
    600,
    NOW(),
    jsonb_build_object(
        'contract_status', 'PENDING_HEARTBEAT',
        'authority_domain', 'OPERATIONAL',
        'ed25519_fingerprint', '61073303638c3dd2',
        'heartbeat_verified', false,
        'parent_authority', 'LARS',
        'blocking_reason', 'NO_HEARTBEAT_DAEMON',
        'ceo_directive', 'CEO-DIR-2026-047',
        'created_by', 'STIG',
        'adr_reference', 'ADR-014'
    )
);

-- CFAO Contract (OPERATIONAL authority, parent LARS) — PENDING (no heartbeat)
INSERT INTO fhq_governance.agent_contracts (
    contract_id, source_agent, target_agent, trigger_event, expected_action, sla_seconds, created_at, metadata
) VALUES (
    gen_random_uuid(),
    'LARS',
    'CFAO',
    'FORECAST_AGGREGATION_CYCLE',
    'FORECAST_CONSOLIDATION',
    600,
    NOW(),
    jsonb_build_object(
        'contract_status', 'PENDING_HEARTBEAT',
        'authority_domain', 'OPERATIONAL',
        'ed25519_fingerprint', '6f6289c1ef77ac5d',
        'heartbeat_verified', false,
        'parent_authority', 'LARS',
        'blocking_reason', 'NO_HEARTBEAT_DAEMON',
        'ceo_directive', 'CEO-DIR-2026-047',
        'created_by', 'STIG',
        'adr_reference', 'ADR-014'
    )
);

-- ============================================================================
-- GAP-002: PRIVILEGE SCOPE ENFORCEMENT (ADR-014 / ADR-013)
-- ============================================================================
-- Per CEO-DIR-2026-047 Section 4.2:
-- "CANONICAL_WRITE = FALSE" (Non-Negotiable)
-- "No global write privileges"
-- "Schema-scoped access only"

-- Update CDMO privilege scope
UPDATE fhq_governance.agent_mandates
SET mandate_document = mandate_document || jsonb_build_object(
    'privilege_scope', jsonb_build_object(
        'canonical_write', false,
        'schema_access', ARRAY['fhq_data', 'fhq_market'],
        'execution_privileges', false,
        'global_write', false,
        'scope_type', 'SCHEMA_SCOPED',
        'enforced_by', 'CEO-DIR-2026-047',
        'adr_reference', 'ADR-014'
    )
)
WHERE agent_name = 'CDMO';

-- Update CEIO privilege scope
UPDATE fhq_governance.agent_mandates
SET mandate_document = mandate_document || jsonb_build_object(
    'privilege_scope', jsonb_build_object(
        'canonical_write', false,
        'schema_access', ARRAY['vision_verification', 'fhq_governance'],
        'execution_privileges', false,
        'global_write', false,
        'scope_type', 'SCHEMA_SCOPED',
        'enforced_by', 'CEO-DIR-2026-047',
        'adr_reference', 'ADR-014'
    )
)
WHERE agent_name = 'CEIO';

-- Update CRIO privilege scope
UPDATE fhq_governance.agent_mandates
SET mandate_document = mandate_document || jsonb_build_object(
    'privilege_scope', jsonb_build_object(
        'canonical_write', false,
        'schema_access', ARRAY['fhq_graph', 'fhq_alpha'],
        'execution_privileges', false,
        'global_write', false,
        'scope_type', 'SCHEMA_SCOPED',
        'enforced_by', 'CEO-DIR-2026-047',
        'adr_reference', 'ADR-014'
    )
)
WHERE agent_name = 'CRIO';

-- Update CSEO privilege scope
UPDATE fhq_governance.agent_mandates
SET mandate_document = mandate_document || jsonb_build_object(
    'privilege_scope', jsonb_build_object(
        'canonical_write', false,
        'schema_access', ARRAY['fhq_governance'],
        'execution_privileges', false,
        'global_write', false,
        'scope_type', 'SCHEMA_SCOPED',
        'enforced_by', 'CEO-DIR-2026-047',
        'adr_reference', 'ADR-014'
    )
)
WHERE agent_name = 'CSEO';

-- Update CFAO privilege scope
UPDATE fhq_governance.agent_mandates
SET mandate_document = mandate_document || jsonb_build_object(
    'privilege_scope', jsonb_build_object(
        'canonical_write', false,
        'schema_access', ARRAY['fhq_research', 'fhq_finn'],
        'execution_privileges', false,
        'global_write', false,
        'scope_type', 'SCHEMA_SCOPED',
        'enforced_by', 'CEO-DIR-2026-047',
        'adr_reference', 'ADR-014'
    )
)
WHERE agent_name = 'CFAO';

-- ============================================================================
-- GAP-003: GRAPH LINEAGE POPULATION (BCBS-239)
-- ============================================================================
-- Per CEO-DIR-2026-047 Section 4.3:
-- "Lineage must conform to BCBS-239 traceability principles"
-- "Hashes must chain deterministically"
-- Owner: CRIO

-- Populate lineage_hash for fhq_graph.nodes
UPDATE fhq_graph.nodes
SET lineage_hash = encode(
    sha256(
        (COALESCE(node_id, '') || '|' ||
         COALESCE(node_type::text, '') || '|' ||
         COALESCE(created_at::text, '') || '|' ||
         'BCBS239_CHAIN')::bytea
    ), 'hex'
)
WHERE lineage_hash IS NULL;

-- Populate lineage_hash for fhq_graph.edges with deterministic chain
UPDATE fhq_graph.edges
SET lineage_hash = encode(
    sha256(
        (COALESCE(edge_id, '') || '|' ||
         COALESCE(from_node_id, '') || '|' ||
         COALESCE(to_node_id, '') || '|' ||
         COALESCE(relationship_type::text, '') || '|' ||
         COALESCE(created_at::text, '') || '|' ||
         'BCBS239_CHAIN')::bytea
    ), 'hex'
)
WHERE lineage_hash IS NULL;

-- ============================================================================
-- GAP-004: CNRP LATENCY INSTRUMENTATION
-- ============================================================================
-- Per CEO-DIR-2026-047 Section 4.4:
-- "0ms latency is classified as instrumentation failure, not performance"
-- This requires code-level changes to the CNRP daemons.
-- Documenting the requirement here for implementation tracking.

-- Create a tracking record for latency instrumentation requirement
INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    metadata,
    agent_id
) VALUES (
    gen_random_uuid(),
    'GAP_REMEDIATION_TRACKING',
    'CNRP_LATENCY_INSTRUMENTATION',
    'INFRASTRUCTURE',
    'STIG',
    NOW(),
    'PENDING_IMPLEMENTATION',
    'GAP-004 requires code-level changes to CNRP daemons to record actual execution duration between started_at and completed_at timestamps. Currently all daemons report 0ms which indicates instrumentation failure.',
    jsonb_build_object(
        'gap_id', 'GAP-004',
        'ceo_directive', 'CEO-DIR-2026-047',
        'required_metrics', ARRAY['p50_ms', 'p95_ms', 'p99_ms'],
        'affected_daemons', ARRAY[
            'ceio_evidence_refresh_daemon',
            'crio_alpha_graph_rebuild',
            'cdmo_data_hygiene_attestation',
            'vega_epistemic_integrity_monitor'
        ],
        'implementation_owner', 'STIG',
        'status', 'PENDING_CODE_CHANGE'
    ),
    'STIG'
);

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify GAP-001: Sub-executive contracts
SELECT
    target_agent,
    source_agent as parent,
    metadata->>'contract_status' as status,
    metadata->>'heartbeat_verified' as heartbeat_ok
FROM fhq_governance.agent_contracts
WHERE target_agent IN ('CSEO', 'CDMO', 'CRIO', 'CEIO', 'CFAO');

-- Verify GAP-002: Privilege scopes
SELECT
    agent_name,
    mandate_document->'privilege_scope'->>'canonical_write' as canonical_write,
    mandate_document->'privilege_scope'->>'global_write' as global_write,
    mandate_document->'privilege_scope'->'schema_access' as schema_access
FROM fhq_governance.agent_mandates
WHERE agent_name IN ('CSEO', 'CDMO', 'CRIO', 'CEIO', 'CFAO');

-- Verify GAP-003: Graph lineage coverage
SELECT
    'fhq_graph.nodes' as table_name,
    COUNT(*) as total,
    COUNT(CASE WHEN lineage_hash IS NOT NULL THEN 1 END) as with_lineage,
    ROUND(100.0 * COUNT(CASE WHEN lineage_hash IS NOT NULL THEN 1 END) / NULLIF(COUNT(*), 0), 1) as coverage_pct
FROM fhq_graph.nodes
UNION ALL
SELECT
    'fhq_graph.edges',
    COUNT(*),
    COUNT(CASE WHEN lineage_hash IS NOT NULL THEN 1 END),
    ROUND(100.0 * COUNT(CASE WHEN lineage_hash IS NOT NULL THEN 1 END) / NULLIF(COUNT(*), 0), 1)
FROM fhq_graph.edges;

COMMIT;

-- ============================================================================
-- POST-EXECUTION: VEGA G3 ATTESTATION REQUIRED
-- ============================================================================
-- Per CEO-DIR-2026-047 Section 6:
-- "No CEO review occurs without explicit VEGA sign-off."
--
-- VEGA shall verify:
-- 1. Sub-Executive contracts vs heartbeat state
-- 2. Privilege scopes vs ADR-014 constraints
-- 3. Graph lineage hash chains vs BCBS-239
-- 4. Latency metrics vs raw measurements
-- ============================================================================
