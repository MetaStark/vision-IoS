-- ============================================================================
-- Migration 140: IoS-007 G2 Oversight Directive Registration
-- ============================================================================
-- CEO Directive: CD-IOS-007-G2-OVERSIGHT-003 (Revision 1)
-- Date: 2025-12-14
-- Executor: EC-019 (Operational Convergence)
--
-- This migration:
-- 1. Registers CD-IOS-007-G2-OVERSIGHT-003 in governance registry
-- 2. Activates Monitored Learning Mode for IoS-007
-- 3. Records oversight parameters and stop conditions
-- 4. Establishes reporting cadence constraints
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: DIRECTIVE REGISTRATION
-- ============================================================================

-- Register the CEO directive
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
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'CEO_DIRECTIVE_REGISTRATION',
    'CD-IOS-007-G2-OVERSIGHT-003',
    'DIRECTIVE',
    'CEO',
    NOW(),
    'APPROVED',
    'CD-IOS-007-G2-OVERSIGHT-003 (Rev 1): Mandatory Oversight and Minimal Reporting for IoS-007 G2 Causal Discovery Phase. Monitored Learning Mode activated. Maximum trust with minimum friction.',
    TRUE,
    encode(sha256('CD-IOS-007-G2-OVERSIGHT-003|REV1|2025-12-14|CEO'::bytea), 'hex')
);

-- ============================================================================
-- SECTION 2: MONITORED LEARNING MODE ACTIVATION
-- ============================================================================

-- Record G2 Monitored Learning Mode activation
INSERT INTO fhq_governance.system_events (
    event_id,
    event_type,
    event_category,
    event_severity,
    source_agent,
    source_component,
    source_ios_layer,
    event_title,
    event_description,
    event_data,
    lineage_hash,
    created_at
) VALUES (
    gen_random_uuid(),
    'G2_MONITORED_LEARNING_MODE_ACTIVATED',
    'GOVERNANCE',
    'INFO',
    'VEGA',
    'IoS-007',
    'ALPHA',
    'IoS-007 G2 Monitored Learning Mode Activated',
    'CD-IOS-007-G2-OVERSIGHT-003: IoS-007 enters Monitored Learning Mode for G2 Causal Discovery. FINN/CRIO authorized. Non-interference rule in effect. Weekly snapshot reporting only.',
    jsonb_build_object(
        'directive', 'CD-IOS-007-G2-OVERSIGHT-003',
        'directive_revision', 1,
        'mode', 'MONITORED_LEARNING',
        'research_owners', ARRAY['FINN', 'CRIO'],
        'focus_constraint', jsonb_build_object(
            'allowed_work', ARRAY['IoS-007 G2 Historical Build', 'IoS-005 Edge Validation Contracts'],
            'blocked', ARRAY['parallel research', 'feature expansion', 'new G0/G1 work'],
            'constraint_type', 'HARD'
        ),
        'reporting_cadence', jsonb_build_object(
            'frequency', 'WEEKLY',
            'snapshot_count', 1,
            'required_fields', ARRAY['ECT', 'edge_count_validated', 'edge_count_candidate', 'ios005_rejection_rate'],
            'prohibited', ARRAY['narrative justification', 'deep dives', 'interim hypotheses']
        ),
        'non_interference_rule', jsonb_build_object(
            'ad_hoc_reporting', false,
            'progress_meetings', false,
            'analytical_steering', false,
            'binding_on', ARRAY['all leadership roles'],
            'exception', 'CRITICAL_BLOCKER alerts for architectural incompatibility or data integrity issues'
        ),
        'stop_conditions', ARRAY[
            'determinism_violation',
            'schema_breach',
            'ios005_governance_regression',
            'ios005_rejection_rate_exceeds_80pct_3_batches',
            'unauthorized_intervention'
        ],
        'g2_exit_criteria', jsonb_build_object(
            'output', 'Stable Causal Graph Snapshot',
            'requirements', ARRAY['validated nodes', 'validated edges', 'confidence scores', 'lineage hashes'],
            'downstream_consumer', 'IoS-008 via CausalVector interface',
            'submission_type', 'G2_COMPLETE_SUBMISSION'
        )
    ),
    encode(sha256('IoS-007|G2_MONITORED_LEARNING|ACTIVATED|2025-12-14'::bytea), 'hex'),
    NOW()
);

-- ============================================================================
-- SECTION 3: OVERSIGHT PARAMETERS REGISTRATION
-- ============================================================================

-- Create oversight parameters table if not exists
CREATE TABLE IF NOT EXISTS fhq_governance.g2_oversight_parameters (
    parameter_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    directive_id TEXT NOT NULL,
    ios_id TEXT NOT NULL,
    parameter_type TEXT NOT NULL,
    parameter_key TEXT NOT NULL,
    parameter_value JSONB NOT NULL,
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_until TIMESTAMPTZ,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(directive_id, ios_id, parameter_key)
);

-- Register oversight parameters
INSERT INTO fhq_governance.g2_oversight_parameters
(directive_id, ios_id, parameter_type, parameter_key, parameter_value, created_by)
VALUES
-- Reporting cadence
('CD-IOS-007-G2-OVERSIGHT-003', 'IoS-007', 'REPORTING', 'snapshot_frequency',
 '{"value": "WEEKLY", "count": 1, "recipients": ["CEO", "LARS"]}'::jsonb, 'CEO'),

-- IoS-005 rejection threshold
('CD-IOS-007-G2-OVERSIGHT-003', 'IoS-007', 'STOP_CONDITION', 'ios005_rejection_threshold',
 '{"threshold_percent": 80, "consecutive_batches": 3, "action": "PAUSE_AND_REPORT"}'::jsonb, 'CEO'),

-- Focus constraint
('CD-IOS-007-G2-OVERSIGHT-003', 'IoS-007', 'CONSTRAINT', 'focus_scope',
 '{"allowed": ["IoS-007 G2", "IoS-005 Edge Validation"], "blocked": ["new G0", "new G1", "parallel research"], "type": "HARD"}'::jsonb, 'CEO'),

-- Non-interference rule
('CD-IOS-007-G2-OVERSIGHT-003', 'IoS-007', 'RULE', 'non_interference',
 '{"ad_hoc_reporting": false, "progress_meetings": false, "analytical_steering": false, "exception": "CRITICAL_BLOCKER"}'::jsonb, 'CEO'),

-- G2 exit criteria
('CD-IOS-007-G2-OVERSIGHT-003', 'IoS-007', 'EXIT_CRITERIA', 'g2_completion',
 '{"output": "Causal Graph Snapshot", "requirements": ["validated_nodes", "validated_edges", "confidence_scores", "lineage_hashes"], "submission": "G2_COMPLETE_SUBMISSION"}'::jsonb, 'CEO')

ON CONFLICT (directive_id, ios_id, parameter_key) DO UPDATE SET
    parameter_value = EXCLUDED.parameter_value,
    created_at = NOW();

-- ============================================================================
-- SECTION 4: UPDATE IoS-007 STATUS
-- ============================================================================

-- Update IoS-007 to G2 in progress
UPDATE fhq_meta.ios_registry
SET
    governance_state = 'G2_HISTORICAL_BUILD_IN_PROGRESS',
    updated_at = NOW()
WHERE ios_id = 'IoS-007';

-- Record state transition
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
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'G2_HISTORICAL_BUILD_STARTED',
    'IoS-007',
    'IOS',
    'FINN',
    NOW(),
    'IN_PROGRESS',
    'CD-IOS-007-G2-OVERSIGHT-003: G2 Historical Build commenced under Monitored Learning Mode. FINN/CRIO executing causal discovery. Weekly snapshot reporting in effect.',
    TRUE,
    encode(sha256('IoS-007|G2|STARTED|2025-12-14|FINN'::bytea), 'hex')
);

-- ============================================================================
-- SECTION 5: VEGA ATTESTATION FOR DIRECTIVE
-- ============================================================================

INSERT INTO fhq_governance.vega_attestations (
    attestation_id,
    target_type,
    target_id,
    target_version,
    attestation_type,
    attestation_status,
    attestation_timestamp,
    vega_signature,
    vega_public_key,
    signature_verified,
    attestation_data,
    adr_reference,
    constitutional_basis,
    created_at
) VALUES (
    gen_random_uuid(),
    'DIRECTIVE',
    'CD-IOS-007-G2-OVERSIGHT-003',
    'REV1',
    'DIRECTIVE_REGISTRATION',
    'ACTIVE',
    NOW(),
    encode(sha256('VEGA_DIRECTIVE|CD-IOS-007-G2-OVERSIGHT-003|REV1|2025-12-14'::bytea), 'hex'),
    '7c71b6356827f270200cc3b870b8c8d33b72eca77d5b87145c377812705515c9',
    TRUE,
    jsonb_build_object(
        'directive', 'CD-IOS-007-G2-OVERSIGHT-003',
        'revision', 1,
        'title', 'Mandatory Oversight and Minimal Reporting for IoS-007 G2',
        'classification', 'ALPHA DISCOVERY - GOVERNANCE',
        'mode', 'MONITORED_LEARNING',
        'governing_principle', 'Maximum trust with minimum friction',
        'research_owners', ARRAY['FINN', 'CRIO'],
        'enforcement', 'EC-019',
        'key_parameters', jsonb_build_object(
            'reporting', 'Weekly snapshot only',
            'focus', 'Hard constraint - G2 and IoS-005 only',
            'non_interference', 'Binding on all leadership',
            'critical_blocker_exception', true,
            'ios005_rejection_threshold', '80% over 3 batches'
        ),
        'stop_conditions_count', 5,
        'attestation_summary', 'Directive registered and active. IoS-007 G2 Monitored Learning Mode in effect.'
    ),
    'ADR-001,ADR-004,ADR-013',
    'CEO Authority - Alpha Discovery Governance',
    NOW()
);

COMMIT;

-- ============================================================================
-- MIGRATION 140 SUMMARY
-- ============================================================================
--
-- DIRECTIVE REGISTRATION:
-- [DONE] CD-IOS-007-G2-OVERSIGHT-003 (Rev 1) registered
-- [DONE] VEGA attestation created
--
-- MONITORED LEARNING MODE:
-- [ACTIVATED] IoS-007 G2 Historical Build
-- [ACTIVE] Non-interference rule
-- [ACTIVE] Weekly snapshot reporting only
-- [ACTIVE] Hard focus constraint
--
-- OVERSIGHT PARAMETERS:
-- [SET] Reporting: Weekly, 1 snapshot, to CEO/LARS
-- [SET] IoS-005 rejection threshold: 80% over 3 batches
-- [SET] Focus scope: G2 + IoS-005 Edge Validation only
-- [SET] Non-interference: No ad-hoc reporting, no meetings, no steering
-- [SET] Exit criteria: G2_COMPLETE_SUBMISSION
--
-- IoS-007 STATUS:
-- [UPDATED] G2_HISTORICAL_BUILD_IN_PROGRESS
--
-- FINN/CRIO may now proceed with causal discovery.
-- ============================================================================
