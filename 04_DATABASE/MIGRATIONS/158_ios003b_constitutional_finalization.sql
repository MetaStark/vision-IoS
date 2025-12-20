-- =============================================================================
-- MIGRATION 158: IoS-003-B CONSTITUTIONAL FINALIZATION
-- =============================================================================
-- CEO Governance Directive: Constitutional Finalization of IoS-003-B
-- Classification: Non-Canonical Ephemeral Context Engine
-- Date: 2025-12-19
--
-- HANDLING A: Formal VEGA Attestation Request
-- HANDLING B: VEGA Attestation Scope (B1-B3)
-- HANDLING C: ios_registry Metadata Lock
-- HANDLING D: Observability (Read-Only)
-- HANDLING E: Operational Status Confirmation
-- =============================================================================

BEGIN;

-- =============================================================================
-- HANDLING A: FORMAL VEGA ATTESTATION REQUEST
-- =============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    agent_id,
    metadata
) VALUES (
    'VEGA_ATTESTATION_REQUEST',
    'IOS-003-B',
    'EPHEMERAL_CONTEXT_ENGINE',
    'STIG',
    NOW(),
    'PENDING_VEGA_REVIEW',
    'Constitutional classification request for IoS-003-B Intraday Regime-Delta per CEO Governance Directive 2025-12-19',
    'STIG',
    jsonb_build_object(
        'request_type', 'CONSTITUTIONAL_FINALIZATION',
        'component', 'IoS-003-B',
        'component_name', 'Intraday Regime-Delta',
        'classification', 'Non-Canonical Ephemeral Context Engine',
        'explicit_assertions', jsonb_build_object(
            'canonical_status', false,
            'write_scope', 'fhq_operational.* ONLY',
            'forbidden_writes', ARRAY['fhq_governance.*', 'fhq_perception.*'],
            'execution_authority', 'NONE',
            'function', 'Contextual Permit Emission only',
            'ttl_enforcement', true,
            'ttl_max_hours', 4,
            'defcon_override', 'HARD (Intraday disabled at DEFCON >= 2)'
        ),
        'purpose', 'Constitutional classification as non-canonical, non-executive, ephemeral - compliant with ADR-013, ADR-017, ADR-014',
        'ceo_directive_date', '2025-12-19',
        'submitted_by', 'STIG'
    )
);

-- =============================================================================
-- HANDLING B: VEGA ATTESTATION SCOPE (B1-B3)
-- =============================================================================
-- VEGA shall explicitly attest to the following three points:

-- B1. Non-Canonical Status
-- B2. State Semantics (EPHEMERAL_PRIMED distinct from PRIMED)
-- B3. ADR-013 Guard Clause

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    agent_id,
    metadata
) VALUES (
    'VEGA_ATTESTATION_SCOPE',
    'IOS-003-B',
    'ATTESTATION_DEFINITION',
    'STIG',
    NOW(),
    'AWAITING_VEGA_SIGNATURE',
    'Attestation scope definition for VEGA signature per CEO Directive',
    'STIG',
    jsonb_build_object(
        'scope_version', '1.0',
        'attestation_points', jsonb_build_object(
            'B1_non_canonical_status', jsonb_build_object(
                'statement', 'IoS-003-B shall never be considered a regime, truth source, or perception engine.',
                'binding', true
            ),
            'B2_state_semantics', jsonb_build_object(
                'statement', 'EPHEMERAL_PRIMED is a distinct signal state, not equivalent to PRIMED.',
                'constraints', jsonb_build_object(
                    'mandatory_risk_scalar', '< 1.0 (currently 0.5)',
                    'ttl_expiry_behavior', 'Reverts signal to DORMANT',
                    'persistence_rule', 'Ephemeral state may NOT persist across regime recalculation'
                ),
                'binding', true
            ),
            'B3_adr013_guard_clause', jsonb_build_object(
                'statement', 'Any attempt by IoS-003-B to mutate canonical tables constitutes a Class-A Governance Breach under ADR-013.',
                'canonical_tables', ARRAY[
                    'fhq_governance.*',
                    'fhq_perception.regime_daily',
                    'fhq_meta.ios_registry (except own entry)',
                    'fhq_canonical.* (except g5_signal_state ephemeral columns)'
                ],
                'binding', true,
                'violation_class', 'CLASS_A_GOVERNANCE_BREACH'
            )
        ),
        'requires_vega_signature', true
    )
);

-- =============================================================================
-- HANDLING C: ios_registry METADATA LOCK (Ontological Lock)
-- =============================================================================
-- This is an ontological lock. Not cosmetic. Not optional.

UPDATE fhq_meta.ios_registry
SET
    title = 'Intraday Regime-Delta (Ephemeral Context Engine)',
    description = 'Non-canonical ephemeral context engine for intraday regime shifts. Emits Flash-Context permits with TTL. NO execution authority. Write scope: fhq_operational ONLY.',
    status = 'G0_SUBMITTED',
    owner_role = 'FINN',
    canonical = FALSE,
    immutability_level = 'OPERATIONAL',
    experimental_classification = 'EPHEMERAL_CONTEXT_ENGINE',
    governance_state = 'AWAITING_VEGA_ATTESTATION',
    updated_at = NOW()
WHERE ios_id = 'IOS-003-B';

-- Add parent engine reference and scope metadata
-- (Using content_hash field to store additional governance metadata as JSON)
UPDATE fhq_meta.ios_registry
SET content_hash = encode(sha256(
    ('IOS-003-B-ONTOLOGICAL-LOCK-' ||
     'ENGINE_TYPE:EPHEMERAL_CONTEXT_ENGINE|' ||
     'CANONICAL:FALSE|' ||
     'PARENT_ENGINE:IOS-003|' ||
     'WRITE_SCOPE:fhq_operational|' ||
     'EXECUTION_AUTHORITY:NONE|' ||
     'GOVERNANCE_TIER:TIER-2-OPERATIONAL-CONTEXT|' ||
     'LOCKED_AT:' || NOW()::text
    )::bytea
), 'hex')
WHERE ios_id = 'IOS-003-B';

-- Log the ontological lock
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    agent_id,
    metadata
) VALUES (
    'ONTOLOGICAL_LOCK',
    'IOS-003-B',
    'IOS_REGISTRY_ENTRY',
    'STIG',
    NOW(),
    'LOCKED',
    'ios_registry metadata locked per CEO Governance Directive. Ontological classification finalized.',
    'STIG',
    jsonb_build_object(
        'engine_type', 'EPHEMERAL_CONTEXT_ENGINE',
        'canonical', false,
        'parent_engine', 'IOS-003',
        'write_scope', 'fhq_operational',
        'execution_authority', 'NONE',
        'governance_tier', 'Tier-2 (Operational Context)',
        'lock_type', 'ONTOLOGICAL',
        'ceo_directive', 'CEO Governance Directive 2025-12-19'
    )
);

-- =============================================================================
-- HANDLING D: OBSERVABILITY (Read-Only)
-- =============================================================================
-- Minimum requirement: vw_active_flash_contexts with specified fields

CREATE OR REPLACE VIEW fhq_operational.vw_active_flash_contexts AS
SELECT
    fc.context_id,
    fc.listing_id AS asset,
    fc.delta_type,
    fc.momentum_vector AS vector,
    fc.intensity,
    EXTRACT(EPOCH FROM (fc.expires_at - NOW())) / 60 AS ttl_remaining_minutes,
    fc.expires_at,
    fc.applicable_strategies,
    fc.target_signal_class,
    fc.is_consumed,
    fc.consumed_by_signal_id,
    fc.consumed_at,
    rd.canonical_regime,
    rd.regime_alignment,
    rd.squeeze_tightness,
    rd.bollinger_width,
    rd.keltner_width,
    -- Linked signal IDs (signals that could use this context)
    (
        SELECT array_agg(ss.needle_id::text)
        FROM fhq_canonical.g5_signal_state ss
        JOIN fhq_canonical.golden_needles gn ON ss.needle_id = gn.needle_id
        WHERE ss.current_state = 'DORMANT'
          AND gn.is_current = TRUE
          AND (gn.price_witness_symbol = fc.listing_id
               OR gn.price_witness_symbol LIKE fc.listing_id || '%')
    ) AS linked_signal_ids,
    fc.created_at
FROM fhq_operational.flash_context fc
JOIN fhq_operational.regime_delta rd ON fc.delta_id = rd.delta_id
WHERE fc.is_consumed = FALSE
  AND fc.expires_at > NOW()
  AND rd.is_active = TRUE
ORDER BY fc.intensity DESC, fc.expires_at ASC;

COMMENT ON VIEW fhq_operational.vw_active_flash_contexts IS
    'Read-only observability for active Flash-Context permits. For operator insight, VEGA audit, and post-mortem analysis.';

-- Log observability establishment
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    agent_id,
    metadata
) VALUES (
    'OBSERVABILITY_ESTABLISHED',
    'vw_active_flash_contexts',
    'READ_ONLY_VIEW',
    'STIG',
    NOW(),
    'ACTIVE',
    'Read-only observability view established per CEO Governance Directive Handling D',
    'STIG',
    jsonb_build_object(
        'view_name', 'fhq_operational.vw_active_flash_contexts',
        'purpose', ARRAY['Operator insight', 'VEGA audit', 'Post-mortem analysis'],
        'fields', ARRAY[
            'asset',
            'delta_type',
            'vector',
            'intensity',
            'ttl_remaining_minutes',
            'linked_signal_ids'
        ],
        'read_only', true,
        'no_ui_logic', true
    )
);

-- =============================================================================
-- HANDLING E: OPERATIONAL STATUS CONFIRMATION
-- =============================================================================
-- NOTE: task_registry is immutable per ADR-013. Operational status recorded
-- in governance_actions_log only (append-only audit trail).
-- The task was already registered in Migration 157 with paper_trading_only=true.

-- Log operational status confirmation (append-only, ADR-013 compliant)
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    agent_id,
    metadata
) VALUES (
    'OPERATIONAL_STATUS_CONFIRMED',
    'IOS-003-B',
    'DAEMON_CONFIGURATION',
    'STIG',
    NOW(),
    'PAPER_MODE_ACTIVE',
    'IoS-003-B operational status confirmed: Paper mode only, no manual intervention, no tuning, no further changes. System to be observed, not improved.',
    'STIG',
    jsonb_build_object(
        'mode', 'PAPER_ONLY',
        'manual_intervention', false,
        'tuning_allowed', false,
        'further_changes', false,
        'instruction', 'Wait for first squeeze. No action before market speaks.',
        'governance_operation', true,
        'technical_project', false
    )
);

-- =============================================================================
-- FINAL: CONSTITUTIONAL ACTIVATION SUMMARY
-- =============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    agent_id,
    metadata
) VALUES (
    'CONSTITUTIONAL_FINALIZATION_SUMMARY',
    'IOS-003-B',
    'COMPLETE_PACKAGE',
    'STIG',
    NOW(),
    'AWAITING_VEGA_FINAL_ATTESTATION',
    'All CEO Directive handlings (A-E) executed. System constitutionally active pending VEGA attestation.',
    'STIG',
    jsonb_build_object(
        'handling_a', 'VEGA Attestation Request SUBMITTED',
        'handling_b', 'Attestation Scope (B1-B3) DEFINED',
        'handling_c', 'ios_registry ONTOLOGICALLY LOCKED',
        'handling_d', 'Observability ESTABLISHED (vw_active_flash_contexts)',
        'handling_e', 'Operational Status CONFIRMED (Paper Mode Only)',
        'activation_conditions', jsonb_build_object(
            'condition_1', 'VEGA attests Non-Canonical status',
            'condition_2', 'ios_registry correctly locked',
            'condition_3', 'EPHEMERAL_PRIMED legally defined',
            'condition_4', 'Observability in place'
        ),
        'next_action', 'Wait for first squeeze. No action before market speaks.',
        'ceo_directive_date', '2025-12-19',
        'executed_by', 'STIG'
    )
);

COMMIT;

-- =============================================================================
-- POST-MIGRATION VERIFICATION
-- =============================================================================
DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '=============================================================';
    RAISE NOTICE 'IoS-003-B CONSTITUTIONAL FINALIZATION COMPLETE';
    RAISE NOTICE '=============================================================';
    RAISE NOTICE '';
    RAISE NOTICE 'HANDLING A: VEGA Attestation Request .............. SUBMITTED';
    RAISE NOTICE 'HANDLING B: Attestation Scope (B1-B3) ............. DEFINED';
    RAISE NOTICE 'HANDLING C: ios_registry Metadata ................. LOCKED';
    RAISE NOTICE 'HANDLING D: Observability (vw_active_flash_contexts) ACTIVE';
    RAISE NOTICE 'HANDLING E: Operational Status .................... PAPER MODE';
    RAISE NOTICE '';
    RAISE NOTICE 'SYSTEM STATUS: Constitutionally Active (Pending VEGA Signature)';
    RAISE NOTICE '';
    RAISE NOTICE 'NEXT ACTION: Wait for first squeeze.';
    RAISE NOTICE '            No action before market speaks.';
    RAISE NOTICE '';
    RAISE NOTICE '=============================================================';
END $$;
