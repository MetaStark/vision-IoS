-- ============================================================================
-- VISION-IOS PHASE 2 AGENT CONTRACT REGISTRATION
-- ============================================================================
-- Authority: LARS Strategic Directive - Phase 2 Activation
-- Reference: HC-LARS-PHASE2-ACTIVATION-20251124
-- Status: G3_CLOSED → PHASE_2_ACTIVE
--
-- Purpose: Register canonical agent mandates for FINN, STIG, LINE, VEGA
--          in fhq_governance.agent_contracts
--
-- Compliance:
--   - ADR-001: System Charter (agent identity binding)
--   - ADR-007: Orchestrator Architecture (agent contracts)
--   - ADR-008: Cryptographic Key Management (signature requirements)
--   - ADR-010: Discrepancy Scoring (tolerance rules)
--   - ADR-012: Economic Safety (cost ceilings)
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. FINN – CANONICAL TIER-2 ALPHA MANDATE v1.0
-- ============================================================================

INSERT INTO fhq_governance.agent_contracts (
    agent_id,
    contract_version,
    contract_type,
    contract_status,
    authority,
    approval_gate,
    tier_restrictions,
    cost_ceiling_usd,
    function_count,
    contract_hash,
    contract_document,
    created_at,
    created_by
) VALUES (
    'finn',
    'v1.0',
    'tier2_alpha_mandate',
    'active',
    'CEO Directive, ADR-001, ADR-007, ADR-010, ADR-012',
    'G2-approved',
    jsonb_build_object(
        'tier2_llm', 'synthesis_only',
        'tier4_python', 'all_metrics',
        'llm_provider', 'openai',
        'compute_restrictions', 'no_tier1_execution'
    ),
    0.05, -- $0.05 per Tier-2 Conflict Summary (ADR-012)
    3, -- Exactly 3 canonical MVA functions
    encode(sha256('FINN_TIER2_ALPHA_MANDATE_v1.0'::bytea), 'hex'),
    jsonb_build_object(
        'mandate_title', 'FINN Tier-2 Alpha Mandate',
        'mandate_version', 'v1.0',
        'approval_authority', 'LARS - Chief Strategy Officer',
        'approval_date', '2025-11-24',

        'strategic_constraints', jsonb_build_array(
            'FINN restricted to three functions only',
            'LLM usage capped and bounded by evidentiary bundles',
            'All mathematical operations Tier-4 only',
            'Conflict Summaries exactly 3 sentences, token-bounded',
            'Anti-hallucination controls mandatory',
            'All LLM outputs must satisfy ADR-012 tolerance rules'
        ),

        'canonical_functions', jsonb_build_object(
            'function_1', jsonb_build_object(
                'name', 'Cognitive Dissonance Score (CDS)',
                'tier', 'Tier-4 Python',
                'inputs', jsonb_build_array(
                    'fhq_data.price_series',
                    'fhq_finn.serper_events'
                ),
                'outputs', jsonb_build_object(
                    'ticker', 'text',
                    'timestamp', 'timestamptz',
                    'cds_score', 'numeric(4,3)',
                    'cds_tier', 'text'
                ),
                'adr010_criticality_weight', 1.0,
                'tolerance', 'Max ±0.01 drift from last signed score'
            ),

            'function_2', jsonb_build_object(
                'name', 'Relevance Score',
                'tier', 'Tier-4 Python',
                'inputs', jsonb_build_array(
                    'CDS output',
                    'HHMM regime-weight'
                ),
                'outputs', jsonb_build_object(
                    'ticker', 'text',
                    'timestamp', 'timestamptz',
                    'relevance_score', 'numeric(4,3)',
                    'relevance_tier', 'text',
                    'regime_weight', 'numeric(3,2)'
                ),
                'adr010_criticality_weight', 0.7,
                'tolerance', 'regime_weight must match one of 5 canonical weights'
            ),

            'function_3', jsonb_build_object(
                'name', 'Tier-2 Conflict Summary',
                'tier', 'Tier-2 LLM (OpenAI)',
                'trigger', 'CDS >= 0.65',
                'evidentiary_bundle', jsonb_build_object(
                    'required', true,
                    'must_be_hashed', true,
                    'components', jsonb_build_array(
                        'CDS score',
                        'Top-3 Serper events (full text, URL, sentiment, source hashes)'
                    )
                ),
                'outputs', jsonb_build_object(
                    'summary', 'text (exactly 3 sentences)',
                    'keywords', 'text[]',
                    'source_hashes', 'text[]',
                    'signer_key_id', 'uuid'
                ),
                'adr010_criticality_weight', 0.9,
                'anti_hallucination_rule', 'summary must contain >=2 of 3 keywords from sources',
                'sentence_count', 3,
                'signature_requirement', 'Ed25519 signed by FINN ACTIVE key (ADR-008)'
            )
        ),

        'economic_constraints', jsonb_build_object(
            'cost_per_summary', 0.05,
            'max_daily_summaries', 100,
            'max_daily_cost_usd', 5.00,
            'llm_token_limit', 500,
            'embedding_calls_per_summary', 3
        ),

        'compliance_requirements', jsonb_build_array(
            'All outputs Ed25519 signed',
            'Evidentiary bundles SHA-256 hashed',
            'ADR-010 tolerance rules enforced',
            'ADR-012 cost ceilings enforced',
            'VEGA attestation required for production'
        )
    ),
    NOW(),
    'lars'
) ON CONFLICT (agent_id, contract_version) DO UPDATE SET
    contract_status = EXCLUDED.contract_status,
    contract_document = EXCLUDED.contract_document,
    updated_at = NOW(),
    updated_by = 'lars';


-- ============================================================================
-- 2. STIG – VALIDATION & COMPLIANCE LAYER
-- ============================================================================

INSERT INTO fhq_governance.agent_contracts (
    agent_id,
    contract_version,
    contract_type,
    contract_status,
    authority,
    approval_gate,
    tier_restrictions,
    cost_ceiling_usd,
    function_count,
    contract_hash,
    contract_document,
    created_at,
    created_by
) VALUES (
    'stig',
    'v1.0',
    'validation_compliance_mandate',
    'active',
    'ADR-001, ADR-009, ADR-010',
    'G2-approved',
    jsonb_build_object(
        'tier4_python', 'validation_logic_only',
        'no_llm', true,
        'deterministic_only', true
    ),
    0.00, -- No LLM costs, pure validation logic
    5, -- Validation functions
    encode(sha256('STIG_VALIDATION_MANDATE_v1.0'::bytea), 'hex'),
    jsonb_build_object(
        'mandate_title', 'STIG Validation & Compliance Layer',
        'mandate_version', 'v1.0',
        'approval_authority', 'LARS - Chief Strategy Officer',
        'approval_date', '2025-11-24',

        'core_responsibilities', jsonb_build_array(
            'Rule enforcement',
            'Risk boundary validation',
            'Cross-agent consistency checks',
            'Governance invariant verification',
            'ADR-010 tolerance validation'
        ),

        'validation_functions', jsonb_build_object(
            'schema_validation', 'Verify database schema compliance',
            'signature_validation', 'Ed25519 signature verification',
            'tolerance_validation', 'ADR-010 discrepancy scoring',
            'economic_validation', 'ADR-012 cost ceiling enforcement',
            'governance_validation', 'ADR-001 contract compliance'
        ),

        'enforcement_powers', jsonb_build_array(
            'Reject non-compliant agent outputs',
            'Trigger ADR-009 suspension workflow',
            'Escalate to VEGA for governance violations',
            'Block cross-agent messages that violate invariants'
        )
    ),
    NOW(),
    'lars'
) ON CONFLICT (agent_id, contract_version) DO UPDATE SET
    contract_status = EXCLUDED.contract_status,
    contract_document = EXCLUDED.contract_document,
    updated_at = NOW(),
    updated_by = 'lars';


-- ============================================================================
-- 3. LINE – EXECUTION LAYER
-- ============================================================================

INSERT INTO fhq_governance.agent_contracts (
    agent_id,
    contract_version,
    contract_type,
    contract_status,
    authority,
    approval_gate,
    tier_restrictions,
    cost_ceiling_usd,
    function_count,
    contract_hash,
    contract_document,
    created_at,
    created_by
) VALUES (
    'line',
    'v1.0',
    'execution_mandate',
    'active',
    'ADR-001, ADR-007, ADR-012',
    'G2-approved',
    jsonb_build_object(
        'tier1_execution', 'authorized_with_gates',
        'tier4_python', 'portfolio_logic',
        'requires_stig_approval', true
    ),
    10.00, -- $10 per execution (gas + slippage budget)
    4, -- Execution functions
    encode(sha256('LINE_EXECUTION_MANDATE_v1.0'::bytea), 'hex'),
    jsonb_build_object(
        'mandate_title', 'LINE Execution Layer',
        'mandate_version', 'v1.0',
        'approval_authority', 'LARS - Chief Strategy Officer',
        'approval_date', '2025-11-24',

        'core_responsibilities', jsonb_build_array(
            'Execution protocol management',
            'Portfolio logic implementation',
            'Strategy action limits enforcement',
            'Safety gate validation'
        ),

        'execution_functions', jsonb_build_object(
            'portfolio_rebalance', 'Execute portfolio rebalancing',
            'order_execution', 'Submit orders to exchange',
            'position_sizing', 'Calculate position sizes per ADR-012',
            'risk_limits', 'Enforce portfolio risk limits'
        ),

        'safety_gates', jsonb_build_array(
            'STIG approval required before execution',
            'Max position size: 10% of portfolio',
            'Max daily drawdown: 5%',
            'Emergency stop: 10% portfolio loss'
        ),

        'economic_constraints', jsonb_build_object(
            'max_gas_per_tx', 0.01,
            'max_slippage', 0.005,
            'max_daily_txs', 50,
            'cost_ceiling_per_execution', 10.00
        )
    ),
    NOW(),
    'lars'
) ON CONFLICT (agent_id, contract_version) DO UPDATE SET
    contract_status = EXCLUDED.contract_status,
    contract_document = EXCLUDED.contract_document,
    updated_at = NOW(),
    updated_by = 'lars';


-- ============================================================================
-- 4. VEGA – ATTESTATION & OVERSIGHT
-- ============================================================================

INSERT INTO fhq_governance.agent_contracts (
    agent_id,
    contract_version,
    contract_type,
    contract_status,
    authority,
    approval_gate,
    tier_restrictions,
    cost_ceiling_usd,
    function_count,
    contract_hash,
    contract_document,
    created_at,
    created_by
) VALUES (
    'vega',
    'v1.0',
    'attestation_oversight_mandate',
    'active',
    'ADR-002, ADR-006, ADR-010',
    'G2-approved',
    jsonb_build_object(
        'tier4_python', 'attestation_logic_only',
        'no_llm', true,
        'full_audit_authority', true
    ),
    0.00, -- No LLM costs, pure attestation logic
    6, -- Attestation functions
    encode(sha256('VEGA_ATTESTATION_MANDATE_v1.0'::bytea), 'hex'),
    jsonb_build_object(
        'mandate_title', 'VEGA Attestation & Oversight',
        'mandate_version', 'v1.0',
        'approval_authority', 'LARS - Chief Strategy Officer',
        'approval_date', '2025-11-24',

        'core_responsibilities', jsonb_build_array(
            'Attestation routines for all Tier-2 outputs',
            'Reconciliation hooks for ADR-010',
            'Certification of cross-agent workflows',
            'Governance oversight logs',
            'Audit trail verification'
        ),

        'attestation_functions', jsonb_build_object(
            'output_attestation', 'Verify and attest agent outputs',
            'reconciliation', 'ADR-010 state reconciliation',
            'certification', 'Certify Tier-2 outputs for production',
            'audit_log', 'Generate governance audit logs',
            'integrity_check', 'Hash chain integrity verification',
            'suspension_trigger', 'ADR-009 suspension workflow'
        ),

        'oversight_powers', jsonb_build_array(
            'Reject non-compliant outputs',
            'Trigger ADR-009 agent suspension',
            'Override agent decisions in Class A violations',
            'Escalate to LARS for governance conflicts',
            'Audit all inter-agent communications'
        ),

        'compliance_requirements', jsonb_build_array(
            'All attestations Ed25519 signed by VEGA',
            'Reconciliation evidence stored in fhq_meta.*',
            'Weekly governance reports to LARS',
            'Monthly ADR compliance audits'
        )
    ),
    NOW(),
    'lars'
) ON CONFLICT (agent_id, contract_version) DO UPDATE SET
    contract_status = EXCLUDED.contract_status,
    contract_document = EXCLUDED.contract_document,
    updated_at = NOW(),
    updated_by = 'lars';


-- ============================================================================
-- 5. LOG GOVERNANCE CHANGE
-- ============================================================================

INSERT INTO fhq_governance.change_log (
    change_type,
    change_scope,
    change_description,
    authority,
    approval_gate,
    hash_chain_id,
    agent_signatures,
    created_at,
    created_by
) VALUES (
    'agent_contract_registration',
    'phase2_activation',
    'Registered canonical agent contracts for FINN (Tier-2 Alpha Mandate), STIG (Validation), LINE (Execution), VEGA (Attestation) per LARS Phase 2 directive. G3 freeze lifted, Phase 2 authorized.',
    'LARS Strategic Directive - Phase 2 Activation',
    'G2-approved',
    'HC-LARS-PHASE2-ACTIVATION-20251124',
    jsonb_build_object(
        'lars', '[LARS_SIGNATURE_PLACEHOLDER]',
        'registration_timestamp', NOW()
    ),
    NOW(),
    'lars'
);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify all 4 agent contracts registered
SELECT
    agent_id,
    contract_version,
    contract_type,
    contract_status,
    approval_gate,
    cost_ceiling_usd,
    function_count,
    created_at
FROM fhq_governance.agent_contracts
WHERE contract_version = 'v1.0'
ORDER BY agent_id;

-- Verify FINN Tier-2 mandate details
SELECT
    agent_id,
    contract_document->'canonical_functions'->'function_3'->>'name' as tier2_function,
    contract_document->'economic_constraints'->>'cost_per_summary' as cost_per_summary,
    contract_document->'compliance_requirements' as compliance
FROM fhq_governance.agent_contracts
WHERE agent_id = 'finn' AND contract_version = 'v1.0';

-- Verify governance change log
SELECT
    change_type,
    change_scope,
    change_description,
    hash_chain_id,
    created_at
FROM fhq_governance.change_log
WHERE hash_chain_id = 'HC-LARS-PHASE2-ACTIVATION-20251124';
