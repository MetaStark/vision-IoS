-- ============================================================================
-- MIGRATION 093: ADR-020 Autonomous Cognitive Intelligence Constitutional Registration
-- ============================================================================
-- Authority: CEO Directive 2025-12-08
-- Executor: STIG (CTO)
-- Classification: TIER-1 CONSTITUTIONAL
-- Hash Chain: HC-ADR020-CONSTITUTIONAL-20251208
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: ADR-020 CANONICAL REGISTRATION
-- ============================================================================

INSERT INTO fhq_meta.adr_registry (
    adr_id,
    adr_title,
    adr_status,
    adr_type,
    current_version,
    approval_authority,
    effective_date,
    file_path,
    sha256_hash,
    metadata,
    hash,
    title,
    status,
    version,
    created_by,
    governance_tier,
    owner,
    adr_number,
    review_cycle_months,
    next_review_date,
    affects,
    constitutional_authority,
    description,
    rationale,
    vega_attested
) VALUES (
    'ADR-020',
    'Autonomous Cognitive Intelligence (ACI) Protocol',
    'APPROVED',
    'CONSTITUTIONAL',
    '2026.PROD.1',
    'CEO',
    '2025-12-08',
    '01_ADR/ADR-020/ADR-020_2026_PRODUCTION_Autonomous_Cognitive_Intelligence.md',
    'edfff2d4ee62efd39dda9078cdb5e9bbc3137e7589266bb1e226134236919635',
    '{
        "classification": "TIER-1 CONSTITUTIONAL",
        "dependencies": ["ADR-001", "ADR-003", "ADR-004", "ADR-010", "ADR-012", "ADR-013", "ADR-016", "ADR-017", "ADR-018"],
        "governing_authorities": ["FINN", "STIG", "VEGA"],
        "appendices": {
            "A": {
                "title": "Normative Mathematical Specification",
                "file": "APPENDIX_A_Normative_Mathematical_Specification.md",
                "hash": "e5500b0b4d7374906f765b86da38bdffbb7f32d87b6b151db6d2715a60071f10"
            },
            "B": {
                "title": "Shadow Execution Protocol (SHADOW_PAPER Mandate)",
                "file": "APPENDIX_B_Shadow_Execution_Protocol.md",
                "hash": "6186590191c4f8115edc6776692be3f4e6ef71f8b68cbb0f9d2d2e522591d2a0"
            }
        },
        "hash_chain_id": "HC-ADR020-CONSTITUTIONAL-20251208",
        "key_concepts": ["Search-in-the-Chain", "InForage Logic", "IKEA Protocol", "Zero Execution Authority", "SHADOW_PAPER"]
    }'::jsonb,
    'edfff2d4ee62efd39dda9078cdb5e9bbc3137e7589266bb1e226134236919635',
    'ADR-020: Autonomous Cognitive Intelligence (ACI) Protocol',
    'APPROVED',
    '2026.PROD.1',
    'STIG',
    'TIER-1',
    'CEO',
    20,
    12,
    '2026-12-08',
    ARRAY['FINN', 'STIG', 'VEGA', 'LARS', 'ACI'],
    'CEO',
    'Establishes Autonomous Cognitive Intelligence (ACI) as a constitutional capability for dynamic research planning, recursive fact-finding, causal inference, and epistemic uncertainty measurement. ACI is authorized to think, hunt, infer and explain, but constitutionally prohibited from making or executing financial decisions.',
    'To industrialize Epistemic Certainty at scale. Where IoS-003 tells the system what is happening, ACI determines why it is happening - with evidence, not intuition.',
    false
) ON CONFLICT (adr_id) DO UPDATE SET
    adr_status = EXCLUDED.adr_status,
    current_version = EXCLUDED.current_version,
    sha256_hash = EXCLUDED.sha256_hash,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- ============================================================================
-- SECTION 2: G4 ARTIFACT HASHES (ADR-011 Hash Chain)
-- ============================================================================

-- Main document hash
INSERT INTO fhq_governance.g4_artifact_hashes (
    hash_id,
    ios_id,
    gate_level,
    artifact_path,
    sha256_hash,
    validated_at,
    validated_by,
    drift_detected,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'ADR-020',
    'G4',
    '01_ADR/ADR-020/ADR-020_2026_PRODUCTION_Autonomous_Cognitive_Intelligence.md',
    'edfff2d4ee62efd39dda9078cdb5e9bbc3137e7589266bb1e226134236919635',
    NOW(),
    'STIG',
    false,
    'HC-ADR020-CONSTITUTIONAL-20251208'
);

-- Appendix A hash
INSERT INTO fhq_governance.g4_artifact_hashes (
    hash_id,
    ios_id,
    gate_level,
    artifact_path,
    sha256_hash,
    validated_at,
    validated_by,
    drift_detected,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'ADR-020-APPENDIX-A',
    'G4',
    '01_ADR/ADR-020/APPENDIX_A_Normative_Mathematical_Specification.md',
    'e5500b0b4d7374906f765b86da38bdffbb7f32d87b6b151db6d2715a60071f10',
    NOW(),
    'STIG',
    false,
    'HC-ADR020-CONSTITUTIONAL-20251208'
);

-- Appendix B hash
INSERT INTO fhq_governance.g4_artifact_hashes (
    hash_id,
    ios_id,
    gate_level,
    artifact_path,
    sha256_hash,
    validated_at,
    validated_by,
    drift_detected,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'ADR-020-APPENDIX-B',
    'G4',
    '01_ADR/ADR-020/APPENDIX_B_Shadow_Execution_Protocol.md',
    '6186590191c4f8115edc6776692be3f4e6ef71f8b68cbb0f9d2d2e522591d2a0',
    NOW(),
    'STIG',
    false,
    'HC-ADR020-CONSTITUTIONAL-20251208'
);

-- ============================================================================
-- SECTION 3: GOVERNANCE ACTION LOG - CONSTITUTIONAL REGISTRATION
-- ============================================================================

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
    'CONSTITUTIONAL_REGISTRATION',
    'ADR-020',
    'ADR',
    'STIG',
    NOW(),
    'APPROVED',
    'CEO Directive 2025-12-08: Constitutional registration of Autonomous Cognitive Intelligence (ACI) Protocol. Establishes ACI as intelligence layer with Zero Execution Authority. Document hash: edfff2d4ee62efd39dda9078cdb5e9bbc3137e7589266bb1e226134236919635',
    true,
    'HC-ADR020-CONSTITUTIONAL-20251208'
);

-- G4 ACTIVATION EVENT
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
    'G4_ACTIVATION',
    'ADR-020',
    'ADR',
    'CEO',
    NOW(),
    'COMPLETED',
    'G4 Constitutional Activation: ADR-020 is now Law of the Land. Two-Man Rule satisfied (STIG code approval + CEO governance approval). Appendices A and B registered. Hash chain integrated.',
    true,
    'HC-ADR020-CONSTITUTIONAL-20251208'
);

-- ============================================================================
-- SECTION 4: AGENT BROADCAST NOTIFICATIONS
-- ============================================================================

-- Notification to LARS
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
    'AGENT_BROADCAST',
    'LARS',
    'AGENT',
    'STIG',
    NOW(),
    'COMPLETED',
    'ADR-020 ACTIVATED: ACI Protocol is now constitutional law. LARS may request research tasks from ACI layer. ACI outputs are advisory-only under Zero Execution Authority.',
    false,
    'HC-ADR020-CONSTITUTIONAL-20251208'
);

-- Notification to FINN
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
    'AGENT_BROADCAST',
    'FINN',
    'AGENT',
    'STIG',
    NOW(),
    'COMPLETED',
    'ADR-020 ACTIVATED: ACI Protocol is now constitutional law. FINN owns methodology validation for Search-in-the-Chain, InForage Logic, IKEA Protocol compliance, and causal inference frameworks.',
    false,
    'HC-ADR020-CONSTITUTIONAL-20251208'
);

-- Notification to VEGA
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
    'AGENT_BROADCAST',
    'VEGA',
    'AGENT',
    'STIG',
    NOW(),
    'COMPLETED',
    'ADR-020 ACTIVATED: ACI Protocol is now constitutional law. VEGA must monitor: ZEA firewall integrity, IKEA protocol adherence, hallucination detection, SHADOW_PAPER isolation. Continuous compliance required.',
    false,
    'HC-ADR020-CONSTITUTIONAL-20251208'
);

-- ============================================================================
-- SECTION 5: MIGRATION AUDIT TRAIL
-- ============================================================================

INSERT INTO fhq_meta.adr_audit_log (
    audit_id,
    change_proposal_id,
    event_type,
    gate_stage,
    adr_id,
    initiated_by,
    decision,
    resolution_notes,
    evidence_path,
    sha256_hash,
    hash_chain_id,
    metadata,
    timestamp
) VALUES (
    gen_random_uuid(),
    'CP-ADR020-20251208',
    'G4_CANONICALIZATION',
    'G4',
    'ADR-020',
    'STIG',
    'APPROVED',
    'CEO Directive 2025-12-08: Constitutional registration of Autonomous Cognitive Intelligence (ACI) Protocol with Appendix A (Normative Math Spec) and Appendix B (SHADOW_PAPER)',
    '01_ADR/ADR-020/',
    'edfff2d4ee62efd39dda9078cdb5e9bbc3137e7589266bb1e226134236919635',
    'HC-ADR020-CONSTITUTIONAL-20251208',
    '{"version": "2026.PROD.1", "classification": "TIER-1 CONSTITUTIONAL", "appendices": ["A", "B"]}'::jsonb,
    NOW()
);

COMMIT;

-- ============================================================================
-- MIGRATION COMPLETE
-- Document Hash: edfff2d4ee62efd39dda9078cdb5e9bbc3137e7589266bb1e226134236919635
-- Appendix A Hash: e5500b0b4d7374906f765b86da38bdffbb7f32d87b6b151db6d2715a60071f10
-- Appendix B Hash: 6186590191c4f8115edc6776692be3f4e6ef71f8b68cbb0f9d2d2e522591d2a0
-- ============================================================================
