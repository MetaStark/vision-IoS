-- ============================================================================
-- MIGRATION 102: ADR-021 & COGNITIVE ENGINE REGISTRATION (EC-020/021/022)
-- ============================================================================
-- CEO Directive: Canonical Registration of Cognitive Engine Architecture
-- Authority: ADR-001, ADR-003, ADR-004, ADR-011, ADR-013
-- Gate: G0_SUBMISSION (CEO Mandated)
-- Executor: STIG (CTO)
-- Date: 2025-12-09
--
-- PURPOSE: Register ADR-021 and three Cognitive Engines (EC-020, EC-021, EC-022)
--          as canonical governance documents with full lineage and hash chains.
--
-- DOCUMENTS REGISTERED:
--   1. ADR-021 – Cognitive Engine Architecture & Deep Research Protocol
--   2. EC-020  – SitC: Search-in-the-Chain Research Architecture (Parent: LARS)
--   3. EC-021  – InForage: Information Foraging Protocol (Parent: FINN)
--   4. EC-022  – IKEA: Knowledge Boundary Framework (Parent: VEGA)
--
-- CONSTRAINTS (CEO Directive §3):
--   - NO implementation - registration only
--   - NO runtime integration
--   - NO code changes
--   - NO agent access changes until G1
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: REGISTER ADR-021 IN ADR REGISTRY
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
    'ADR-021',
    'Cognitive Engine Architecture & Deep Research Protocol',
    'APPROVED',
    'CONSTITUTIONAL',
    '2026.PROD.1',
    'CEO',
    '2025-12-09',
    '00_CONSTITUTION/ADR-021_2026_PRODUCTION_Cognitive_Engine_Architecture_Deep_Research_Protocol.md',
    'c74b5f2c3642136360caad12c141deb73df098ea6b356fb9aaa662d719289606',
    '{
        "classification": "TIER-1 CONSTITUTIONAL-RESEARCH",
        "dependencies": ["ADR-001", "ADR-007", "ADR-010", "ADR-012", "ADR-014", "ADR-016", "ADR-017"],
        "governing_authorities": ["LARS", "FINN", "VEGA"],
        "cognitive_engines": {
            "EC-020": {"name": "SitC", "parent": "LARS", "role": "Reasoning & Global Planning"},
            "EC-021": {"name": "InForage", "parent": "FINN", "role": "Search Optimization & ROI"},
            "EC-022": {"name": "IKEA", "parent": "VEGA", "role": "Hallucination Firewall"}
        },
        "hash_chain_id": "HC-ADR-021-CONSTITUTIONAL-20251209",
        "research_basis": ["arXiv:2505.00186", "arXiv:2304.14732", "arXiv:2505.09316", "arXiv:2505.07596"],
        "mit_quad_alignment": {
            "SitC": "LIDS (Inference & Truth)",
            "InForage": "DSL (Optimization & Operations Research)",
            "IKEA": "RISL (Resilience & Immunity)"
        }
    }'::jsonb,
    'c74b5f2c3642136360caad12c141deb73df098ea6b356fb9aaa662d719289606',
    'ADR-021: Cognitive Engine Architecture & Deep Research Protocol',
    'APPROVED',
    '2026.PROD.1',
    'STIG',
    'TIER-1',
    'CEO',
    21,
    12,
    '2026-12-09',
    ARRAY['FINN', 'STIG', 'VEGA', 'LARS', 'Orchestrator', 'All Tier-2 Agents'],
    'CEO',
    'Establishes three Tier-2 Cognitive Engines (SitC, InForage, IKEA) as the foundational reasoning layer for autonomous Deep Research operations. Implements Chain-of-Query verification, information foraging optimization, and knowledge boundary enforcement.',
    'To transform from Chain-of-Thought (linear, fragile) to Chain-of-Reasoning with Active Foraging (dynamic, economic, self-aware). Directly protects $100,000 revenue target.',
    false
) ON CONFLICT (adr_id) DO UPDATE SET
    adr_status = EXCLUDED.adr_status,
    current_version = EXCLUDED.current_version,
    sha256_hash = EXCLUDED.sha256_hash,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- ============================================================================
-- SECTION 2: REGISTER EC-020 (SitC) IN ADR REGISTRY
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
    'EC-020',
    'SitC – Chief Cognitive Architect & Dynamic Planner',
    'APPROVED',
    'ARCHITECTURAL',
    '2026.PROD.1',
    'CEO',
    '2025-12-09',
    '00_CONSTITUTION/EC-020_2026_PRODUCTION_SitC_Search_in_the_Chain.md',
    '4dbde922470ecfbd843aea7ce3ba78ce3defa36c72e3cfcbafffa36ef28ea31c',
    '{
        "classification": "RESEARCH-METHOD",
        "document_type": "COGNITIVE_ENGINE",
        "parent_executive": "LARS (EC-002)",
        "role_type": "Tier-2 Cognitive Authority (Reasoning & Global Planning)",
        "research_basis": "arXiv:2304.14732",
        "authority_chain": ["ADR-001", "ADR-007", "ADR-010", "ADR-017", "ADR-021", "EC-020"],
        "core_function": "Dynamic Global Planning with Interleaved Search",
        "mandate": "Decomposition, Interleaving, Traceability",
        "hash_chain_id": "HC-EC-020-COGNITIVE-20251209",
        "mit_quad_pillar": "LIDS"
    }'::jsonb,
    '4dbde922470ecfbd843aea7ce3ba78ce3defa36c72e3cfcbafffa36ef28ea31c',
    'EC-020: SitC (Search-in-the-Chain Protocol)',
    'APPROVED',
    '2026.PROD.1',
    'STIG',
    'TIER-2',
    'FINN',
    20,
    12,
    '2026-12-09',
    ARRAY['LARS', 'CSEO', 'CRIO', 'Orchestrator'],
    'ADR-021',
    'The system Prefrontal Cortex - ensures complex multi-hop reasoning chains are constructed dynamically and verified incrementally. Constructs Chain-of-Query (CoQ) and dynamically modifies it during execution based on intermediate search results.',
    'Prevents strategic drift by enforcing that no reasoning chain proceeds past an unverified node. Protects capital by preventing trade hypothesis execution unless full causality chain is verified.',
    false
) ON CONFLICT (adr_id) DO UPDATE SET
    adr_status = EXCLUDED.adr_status,
    current_version = EXCLUDED.current_version,
    sha256_hash = EXCLUDED.sha256_hash,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- ============================================================================
-- SECTION 3: REGISTER EC-021 (InForage) IN ADR REGISTRY
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
    'EC-021',
    'InForage – Chief Information Economist',
    'APPROVED',
    'ARCHITECTURAL',
    '2026.PROD.1',
    'CEO',
    '2025-12-09',
    '00_CONSTITUTION/EC-021_2026_PRODUCTION_InForage_Information_Foraging.md',
    '4bc6ed92ad30a409fb89168ffa096933888cc881c4b2b99fa8051e5a4b988dd0',
    '{
        "classification": "RESEARCH-METHOD",
        "document_type": "COGNITIVE_ENGINE",
        "parent_executive": "FINN (EC-005)",
        "role_type": "Tier-2 Cognitive Authority (Search Optimization & ROI)",
        "research_basis": "arXiv:2505.09316",
        "authority_chain": ["ADR-001", "ADR-012", "ADR-017", "ADR-021", "EC-021"],
        "core_function": "ROI on Curiosity - Maximize Information Gain per Token Cost",
        "mandate": "Scent Score Assignment, Adaptive Termination, Budget Management",
        "reward_function": "Reward = Rₒ + λ₁×Rᵢ - λ₂×Pₑ",
        "hash_chain_id": "HC-EC-021-COGNITIVE-20251209",
        "mit_quad_pillar": "DSL"
    }'::jsonb,
    '4bc6ed92ad30a409fb89168ffa096933888cc881c4b2b99fa8051e5a4b988dd0',
    'EC-021: InForage (Information Foraging Protocol)',
    'APPROVED',
    '2026.PROD.1',
    'STIG',
    'TIER-2',
    'FINN',
    21,
    12,
    '2026-12-09',
    ARRAY['FINN', 'CRIO', 'CDMO', 'CEIO'],
    'ADR-021',
    'The system CFO of Curiosity - treats information retrieval as economic investment, not free resource. Uses Reinforcement Learning reward function to decide if search is profitable.',
    'Ensures research factory is self-funding. Reduces API/Compute costs by up to 60% by stopping searches early when marginal utility drops. Increases Alpha precision by filtering low-nutrition noise.',
    false
) ON CONFLICT (adr_id) DO UPDATE SET
    adr_status = EXCLUDED.adr_status,
    current_version = EXCLUDED.current_version,
    sha256_hash = EXCLUDED.sha256_hash,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- ============================================================================
-- SECTION 4: REGISTER EC-022 (IKEA) IN ADR REGISTRY
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
    'EC-022',
    'IKEA – Chief Knowledge Boundary Officer',
    'APPROVED',
    'ARCHITECTURAL',
    '2026.PROD.1',
    'CEO',
    '2025-12-09',
    '00_CONSTITUTION/EC-022_2026_PRODUCTION_IKEA_Knowledge_Boundary.md',
    '2281e98691a50a8ce6923c22873f18776bd4b307cac4e910a06c3b6592a70331',
    '{
        "classification": "RESEARCH-METHOD / KNOWLEDGE-BOUNDARY",
        "document_type": "COGNITIVE_ENGINE",
        "parent_executive": "VEGA (EC-001)",
        "role_type": "Tier-2 Cognitive Authority (Hallucination Firewall)",
        "research_basis": "arXiv:2505.07596",
        "authority_chain": ["ADR-001", "ADR-010", "ADR-017", "ADR-021", "EC-022"],
        "core_function": "The Truth Boundary - Know what you know",
        "mandate": "Query Classification, Uncertainty Quantification, Volatility Flagging",
        "classification_types": ["PARAMETRIC", "EXTERNAL_REQUIRED", "HYBRID"],
        "hash_chain_id": "HC-EC-022-COGNITIVE-20251209",
        "mit_quad_pillar": "RISL",
        "override_authority": "All Tier-2 outputs"
    }'::jsonb,
    '2281e98691a50a8ce6923c22873f18776bd4b307cac4e910a06c3b6592a70331',
    'EC-022: IKEA (Internal-External Knowledge Synergistic Reasoning)',
    'APPROVED',
    '2026.PROD.1',
    'STIG',
    'TIER-2',
    'VEGA',
    22,
    12,
    '2026-12-09',
    ARRAY['VEGA', 'All Tier-2 Agents', 'CSEO', 'CRIO', 'CFAO', 'CDMO', 'CEIO'],
    'ADR-021',
    'The system Conscience - solves knowledge boundary problem: Do I know this, or do I need to look it up? Prevents hallucination (guessing when should search) and redundancy (searching when already know).',
    'Primary defense against Bad Data Loss. Prevents trading on fabricated data, using outdated internal weights, and wasting resources on stable knowledge lookups.',
    false
) ON CONFLICT (adr_id) DO UPDATE SET
    adr_status = EXCLUDED.adr_status,
    current_version = EXCLUDED.current_version,
    sha256_hash = EXCLUDED.sha256_hash,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- ============================================================================
-- SECTION 5: CREATE HASH CHAINS (ADR-011 Fortress Standard)
-- ============================================================================

-- Hash Chain for ADR-021
INSERT INTO vision_verification.hash_chains (
    chain_id,
    chain_type,
    chain_scope,
    genesis_hash,
    current_hash,
    chain_length,
    integrity_verified,
    last_verification_at,
    created_by,
    created_at,
    updated_at
) VALUES (
    'HC-ADR-021-CONSTITUTIONAL-20251209',
    'ADR_CONSTITUTIONAL',
    'ADR-021',
    encode(sha256(('ADR-021:COGNITIVE-ENGINE-ARCHITECTURE:GENESIS:CONSTITUTIONAL:2025-12-09')::bytea), 'hex'),
    'c74b5f2c3642136360caad12c141deb73df098ea6b356fb9aaa662d719289606',
    1,
    TRUE,
    NOW(),
    'STIG',
    NOW(),
    NOW()
) ON CONFLICT (chain_id) DO NOTHING;

-- Hash Chain for EC-020
INSERT INTO vision_verification.hash_chains (
    chain_id,
    chain_type,
    chain_scope,
    genesis_hash,
    current_hash,
    chain_length,
    integrity_verified,
    last_verification_at,
    created_by,
    created_at,
    updated_at
) VALUES (
    'HC-EC-020-COGNITIVE-20251209',
    'COGNITIVE_ENGINE',
    'EC-020',
    encode(sha256(('EC-020:SITC:GENESIS:COGNITIVE:2025-12-09')::bytea), 'hex'),
    '4dbde922470ecfbd843aea7ce3ba78ce3defa36c72e3cfcbafffa36ef28ea31c',
    1,
    TRUE,
    NOW(),
    'STIG',
    NOW(),
    NOW()
) ON CONFLICT (chain_id) DO NOTHING;

-- Hash Chain for EC-021
INSERT INTO vision_verification.hash_chains (
    chain_id,
    chain_type,
    chain_scope,
    genesis_hash,
    current_hash,
    chain_length,
    integrity_verified,
    last_verification_at,
    created_by,
    created_at,
    updated_at
) VALUES (
    'HC-EC-021-COGNITIVE-20251209',
    'COGNITIVE_ENGINE',
    'EC-021',
    encode(sha256(('EC-021:INFORAGE:GENESIS:COGNITIVE:2025-12-09')::bytea), 'hex'),
    '4bc6ed92ad30a409fb89168ffa096933888cc881c4b2b99fa8051e5a4b988dd0',
    1,
    TRUE,
    NOW(),
    'STIG',
    NOW(),
    NOW()
) ON CONFLICT (chain_id) DO NOTHING;

-- Hash Chain for EC-022
INSERT INTO vision_verification.hash_chains (
    chain_id,
    chain_type,
    chain_scope,
    genesis_hash,
    current_hash,
    chain_length,
    integrity_verified,
    last_verification_at,
    created_by,
    created_at,
    updated_at
) VALUES (
    'HC-EC-022-COGNITIVE-20251209',
    'COGNITIVE_ENGINE',
    'EC-022',
    encode(sha256(('EC-022:IKEA:GENESIS:COGNITIVE:2025-12-09')::bytea), 'hex'),
    '2281e98691a50a8ce6923c22873f18776bd4b307cac4e910a06c3b6592a70331',
    1,
    TRUE,
    NOW(),
    'STIG',
    NOW(),
    NOW()
) ON CONFLICT (chain_id) DO NOTHING;

-- ============================================================================
-- SECTION 6: LOG G4 ARTIFACT HASHES
-- ============================================================================

-- ADR-021 hash
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
    'ADR-021',
    'G0',
    '00_CONSTITUTION/ADR-021_2026_PRODUCTION_Cognitive_Engine_Architecture_Deep_Research_Protocol.md',
    'c74b5f2c3642136360caad12c141deb73df098ea6b356fb9aaa662d719289606',
    NOW(),
    'STIG',
    false,
    'HC-ADR-021-CONSTITUTIONAL-20251209'
);

-- EC-020 hash
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
    'EC-020',
    'G0',
    '00_CONSTITUTION/EC-020_2026_PRODUCTION_SitC_Search_in_the_Chain.md',
    '4dbde922470ecfbd843aea7ce3ba78ce3defa36c72e3cfcbafffa36ef28ea31c',
    NOW(),
    'STIG',
    false,
    'HC-EC-020-COGNITIVE-20251209'
);

-- EC-021 hash
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
    'EC-021',
    'G0',
    '00_CONSTITUTION/EC-021_2026_PRODUCTION_InForage_Information_Foraging.md',
    '4bc6ed92ad30a409fb89168ffa096933888cc881c4b2b99fa8051e5a4b988dd0',
    NOW(),
    'STIG',
    false,
    'HC-EC-021-COGNITIVE-20251209'
);

-- EC-022 hash
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
    'EC-022',
    'G0',
    '00_CONSTITUTION/EC-022_2026_PRODUCTION_IKEA_Knowledge_Boundary.md',
    '2281e98691a50a8ce6923c22873f18776bd4b307cac4e910a06c3b6592a70331',
    NOW(),
    'STIG',
    false,
    'HC-EC-022-COGNITIVE-20251209'
);

-- ============================================================================
-- SECTION 7: LOG GOVERNANCE ACTIONS
-- ============================================================================

-- ADR-021 Constitutional Registration
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
    'ADR_CONSTITUTIONAL_REGISTRATION',
    'ADR-021',
    'ADR',
    'STIG',
    NOW(),
    'APPROVED',
    'CEO Directive 2025-12-09: Constitutional registration of Cognitive Engine Architecture & Deep Research Protocol. Establishes three Tier-2 Cognitive Engines (SitC, InForage, IKEA) as foundational reasoning layer. Document hash: c74b5f2c3642136360caad12c141deb73df098ea6b356fb9aaa662d719289606',
    true,
    'HC-ADR-021-CONSTITUTIONAL-20251209'
);

-- EC-020 Registration
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
    'COGNITIVE_ENGINE_REGISTRATION',
    'EC-020',
    'COGNITIVE_ENGINE',
    'STIG',
    NOW(),
    'APPROVED',
    'CEO Directive 2025-12-09: Registration of SitC (Search-in-the-Chain) Cognitive Engine. Parent: LARS. Role: Dynamic Global Planning with Interleaved Search. MIT Quad Pillar: LIDS. Document hash: 4dbde922470ecfbd843aea7ce3ba78ce3defa36c72e3cfcbafffa36ef28ea31c',
    true,
    'HC-EC-020-COGNITIVE-20251209'
);

-- EC-021 Registration
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
    'COGNITIVE_ENGINE_REGISTRATION',
    'EC-021',
    'COGNITIVE_ENGINE',
    'STIG',
    NOW(),
    'APPROVED',
    'CEO Directive 2025-12-09: Registration of InForage (Information Foraging Protocol) Cognitive Engine. Parent: FINN. Role: Search Optimization & ROI. MIT Quad Pillar: DSL. Document hash: 4bc6ed92ad30a409fb89168ffa096933888cc881c4b2b99fa8051e5a4b988dd0',
    true,
    'HC-EC-021-COGNITIVE-20251209'
);

-- EC-022 Registration
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
    'COGNITIVE_ENGINE_REGISTRATION',
    'EC-022',
    'COGNITIVE_ENGINE',
    'STIG',
    NOW(),
    'APPROVED',
    'CEO Directive 2025-12-09: Registration of IKEA (Knowledge Boundary Framework) Cognitive Engine. Parent: VEGA. Role: Hallucination Firewall. MIT Quad Pillar: RISL. Document hash: 2281e98691a50a8ce6923c22873f18776bd4b307cac4e910a06c3b6592a70331',
    true,
    'HC-EC-022-COGNITIVE-20251209'
);

-- ============================================================================
-- SECTION 8: CREATE VEGA ATTESTATIONS (PENDING)
-- ============================================================================

-- VEGA Attestation for ADR-021
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
    adr_reference,
    constitutional_basis,
    attestation_data
) VALUES (
    gen_random_uuid(),
    'ADR',
    'ADR-021',
    '2026.PROD.1',
    'CERTIFICATION',
    'PENDING',
    NOW(),
    'VEGA-ATT-ADR021-' || md5(random()::text),
    'GENESIS_KEY_VEGA_PENDING_PRODUCTION',
    'ADR-021',
    'EC-001',
    jsonb_build_object(
        'attestation_id', 'ATT-VEGA-ADR021-' || to_char(NOW(), 'YYYYMMDD'),
        'governance_tier', 'Tier-1',
        'verification_status', 'PENDING - Awaiting VEGA formal attestation',
        'cognitive_engines', jsonb_build_array('EC-020', 'EC-021', 'EC-022'),
        'constitutional_mandate', 'Cognitive Engine Architecture compliance mandatory for Deep Research',
        'gate_status', 'G0_SUBMITTED'
    )
) ON CONFLICT DO NOTHING;

-- VEGA Attestation for EC-020
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
    adr_reference,
    constitutional_basis,
    attestation_data
) VALUES (
    gen_random_uuid(),
    'COGNITIVE_ENGINE',
    'EC-020',
    '2026.PROD.1',
    'CERTIFICATION',
    'PENDING',
    NOW(),
    'VEGA-ATT-EC020-' || md5(random()::text),
    'GENESIS_KEY_VEGA_PENDING_PRODUCTION',
    'ADR-021',
    'EC-001',
    jsonb_build_object(
        'attestation_id', 'ATT-VEGA-EC020-' || to_char(NOW(), 'YYYYMMDD'),
        'engine_name', 'SitC',
        'parent_executive', 'LARS',
        'governance_class', 'RESEARCH-METHOD',
        'gate_status', 'G0_SUBMITTED'
    )
) ON CONFLICT DO NOTHING;

-- VEGA Attestation for EC-021
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
    adr_reference,
    constitutional_basis,
    attestation_data
) VALUES (
    gen_random_uuid(),
    'COGNITIVE_ENGINE',
    'EC-021',
    '2026.PROD.1',
    'CERTIFICATION',
    'PENDING',
    NOW(),
    'VEGA-ATT-EC021-' || md5(random()::text),
    'GENESIS_KEY_VEGA_PENDING_PRODUCTION',
    'ADR-021',
    'EC-001',
    jsonb_build_object(
        'attestation_id', 'ATT-VEGA-EC021-' || to_char(NOW(), 'YYYYMMDD'),
        'engine_name', 'InForage',
        'parent_executive', 'FINN',
        'governance_class', 'RESEARCH-METHOD',
        'gate_status', 'G0_SUBMITTED'
    )
) ON CONFLICT DO NOTHING;

-- VEGA Attestation for EC-022
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
    adr_reference,
    constitutional_basis,
    attestation_data
) VALUES (
    gen_random_uuid(),
    'COGNITIVE_ENGINE',
    'EC-022',
    '2026.PROD.1',
    'CERTIFICATION',
    'PENDING',
    NOW(),
    'VEGA-ATT-EC022-' || md5(random()::text),
    'GENESIS_KEY_VEGA_PENDING_PRODUCTION',
    'ADR-021',
    'EC-001',
    jsonb_build_object(
        'attestation_id', 'ATT-VEGA-EC022-' || to_char(NOW(), 'YYYYMMDD'),
        'engine_name', 'IKEA',
        'parent_executive', 'VEGA',
        'governance_class', 'RESEARCH-METHOD / KNOWLEDGE-BOUNDARY',
        'gate_status', 'G0_SUBMITTED'
    )
) ON CONFLICT DO NOTHING;

-- ============================================================================
-- SECTION 9: AUDIT LOG ENTRIES (ADR-002 Compliance)
-- ============================================================================

-- ADR-021 Audit Entry
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
    'CP-ADR021-REG-' || TO_CHAR(NOW(), 'YYYYMMDD'),
    'SUBMISSION',
    'G0',
    'ADR-021',
    'STIG',
    'APPROVED',
    'CEO Directive 2025-12-09: Constitutional registration of Cognitive Engine Architecture. Three Cognitive Engines (SitC, InForage, IKEA) registered. No implementation - registration only per CEO constraints.',
    '05_GOVERNANCE/PHASE3/STIG_REGISTRATION_LOG_20251209.json',
    'c74b5f2c3642136360caad12c141deb73df098ea6b356fb9aaa662d719289606',
    'HC-ADR-021-CONSTITUTIONAL-20251209',
    jsonb_build_object(
        'adr_id', 'ADR-021',
        'version', '2026.PROD.1',
        'type', 'CONSTITUTIONAL',
        'owner', 'CEO',
        'cognitive_engines', jsonb_build_array(
            jsonb_build_object('id', 'EC-020', 'name', 'SitC', 'parent', 'LARS'),
            jsonb_build_object('id', 'EC-021', 'name', 'InForage', 'parent', 'FINN'),
            jsonb_build_object('id', 'EC-022', 'name', 'IKEA', 'parent', 'VEGA')
        ),
        'constraints', jsonb_build_object(
            'implementation', false,
            'runtime_integration', false,
            'code_changes', false,
            'agent_access_changes', false
        )
    ),
    NOW()
);

-- EC-020 Audit Entry
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
    'CP-EC020-REG-' || TO_CHAR(NOW(), 'YYYYMMDD'),
    'SUBMISSION',
    'G0',
    'EC-020',
    'STIG',
    'APPROVED',
    'CEO Directive 2025-12-09: Registration of SitC Cognitive Engine under ADR-021.',
    '05_GOVERNANCE/PHASE3/STIG_REGISTRATION_LOG_20251209.json',
    '4dbde922470ecfbd843aea7ce3ba78ce3defa36c72e3cfcbafffa36ef28ea31c',
    'HC-EC-020-COGNITIVE-20251209',
    jsonb_build_object('engine_id', 'EC-020', 'engine_name', 'SitC', 'parent', 'LARS', 'governance_class', 'RESEARCH-METHOD'),
    NOW()
);

-- EC-021 Audit Entry
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
    'CP-EC021-REG-' || TO_CHAR(NOW(), 'YYYYMMDD'),
    'SUBMISSION',
    'G0',
    'EC-021',
    'STIG',
    'APPROVED',
    'CEO Directive 2025-12-09: Registration of InForage Cognitive Engine under ADR-021.',
    '05_GOVERNANCE/PHASE3/STIG_REGISTRATION_LOG_20251209.json',
    '4bc6ed92ad30a409fb89168ffa096933888cc881c4b2b99fa8051e5a4b988dd0',
    'HC-EC-021-COGNITIVE-20251209',
    jsonb_build_object('engine_id', 'EC-021', 'engine_name', 'InForage', 'parent', 'FINN', 'governance_class', 'RESEARCH-METHOD'),
    NOW()
);

-- EC-022 Audit Entry
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
    'CP-EC022-REG-' || TO_CHAR(NOW(), 'YYYYMMDD'),
    'SUBMISSION',
    'G0',
    'EC-022',
    'STIG',
    'APPROVED',
    'CEO Directive 2025-12-09: Registration of IKEA Cognitive Engine under ADR-021.',
    '05_GOVERNANCE/PHASE3/STIG_REGISTRATION_LOG_20251209.json',
    '2281e98691a50a8ce6923c22873f18776bd4b307cac4e910a06c3b6592a70331',
    'HC-EC-022-COGNITIVE-20251209',
    jsonb_build_object('engine_id', 'EC-022', 'engine_name', 'IKEA', 'parent', 'VEGA', 'governance_class', 'RESEARCH-METHOD / KNOWLEDGE-BOUNDARY'),
    NOW()
);

COMMIT;

-- ============================================================================
-- POST-MIGRATION VERIFICATION
-- ============================================================================

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'MIGRATION 102: ADR-021 & COGNITIVE ENGINE REGISTRATION — VERIFICATION'
\echo '═══════════════════════════════════════════════════════════════════════════'

-- Verify ADR-021 and EC registrations
SELECT 'Registry Entries:' AS check_type;
SELECT adr_id, adr_title, adr_status, adr_type, governance_tier
FROM fhq_meta.adr_registry
WHERE adr_id IN ('ADR-021', 'EC-020', 'EC-021', 'EC-022')
ORDER BY adr_id;

-- Verify Hash Chains
SELECT 'Hash Chains:' AS check_type;
SELECT chain_id, chain_type, chain_scope, integrity_verified
FROM vision_verification.hash_chains
WHERE chain_id LIKE 'HC-ADR-021%' OR chain_id LIKE 'HC-EC-02%'
ORDER BY chain_id;

-- Verify Governance Actions
SELECT 'Governance Actions:' AS check_type;
SELECT action_type, action_target, decision, initiated_by
FROM fhq_governance.governance_actions_log
WHERE action_target IN ('ADR-021', 'EC-020', 'EC-021', 'EC-022')
ORDER BY initiated_at DESC
LIMIT 4;

-- Verify VEGA Attestations
SELECT 'VEGA Attestations:' AS check_type;
SELECT target_id, target_type, attestation_status
FROM fhq_governance.vega_attestations
WHERE target_id IN ('ADR-021', 'EC-020', 'EC-021', 'EC-022')
ORDER BY target_id;

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'ADR-021 & COGNITIVE ENGINE REGISTRATION — COMPLETE'
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo ''
\echo 'Documents Registered:'
\echo '  ADR-021 — Cognitive Engine Architecture & Deep Research Protocol (CONSTITUTIONAL)'
\echo '  EC-020  — SitC: Search-in-the-Chain (Parent: LARS, Pillar: LIDS)'
\echo '  EC-021  — InForage: Information Foraging Protocol (Parent: FINN, Pillar: DSL)'
\echo '  EC-022  — IKEA: Knowledge Boundary Framework (Parent: VEGA, Pillar: RISL)'
\echo ''
\echo 'Gate Status: G0_SUBMITTED'
\echo 'VEGA Attestation: PENDING'
\echo ''
\echo 'CEO Directive Constraints Enforced:'
\echo '  ✓ No implementation - registration only'
\echo '  ✓ No runtime integration'
\echo '  ✓ No code changes'
\echo '  ✓ No agent access changes until G1'
\echo ''
\echo 'Next Step: G1 Technical Validation (requires STIG + VEGA approval)'
\echo '═══════════════════════════════════════════════════════════════════════════'
