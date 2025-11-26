-- =====================================================
-- MIGRATION 019: ADR-008 CRYPTOGRAPHIC KEY MANAGEMENT
-- =====================================================
--
-- Authority: LARS (CSO – Strategy & Governance)
-- ADR: ADR-008_2026_PRODUCTION
-- Title: Cryptographic Key Management & Rotation Architecture
-- Constitutional Authority: ADR-001 → ADR-002 → ADR-006 → ADR-007 → EC-001
-- Governance Tier: Tier-2 (Security, Integrity, Non-Repudiation)
--
-- This migration creates:
--   1. fhq_meta.adr_registry - Canonical ADR registration
--   2. fhq_meta.adr_dependencies - ADR lineage and dependencies
--   3. fhq_meta.agent_keys - Key lifecycle management (ADR-008 Section 2.3)
--   4. fhq_meta.key_archival_log - Multi-tier key archival audit (ADR-008 Section 2.4)
--   5. G3/G4 audit log entries for ADR-008 approval
--
-- Compliance:
--   - ISO/IEC 11770-1 (Key Management)
--   - ISO 8000-110 (Data Quality & Lineage)
--   - BCBS 239 (Risk Data Aggregation)
--   - GIPS Transparency Principles
--
-- =====================================================

BEGIN;

-- =====================================================
-- SCHEMA VERIFICATION
-- =====================================================

CREATE SCHEMA IF NOT EXISTS fhq_meta;
CREATE SCHEMA IF NOT EXISTS fhq_governance;

-- =====================================================
-- 1. ADR REGISTRY TABLE
-- =====================================================
-- Canonical registration of all Architectural Decision Records
-- Authority: ADR-004 (Change Gates)

CREATE TABLE IF NOT EXISTS fhq_meta.adr_registry (
    -- Primary identification
    adr_id TEXT PRIMARY KEY,
    adr_number INTEGER NOT NULL UNIQUE,

    -- ADR metadata
    title TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '2026.PRODUCTION',
    status TEXT NOT NULL DEFAULT 'DRAFT',

    -- Governance
    author TEXT NOT NULL,
    owner TEXT NOT NULL,
    governance_tier TEXT NOT NULL DEFAULT 'Tier-3',

    -- Dates
    created_date DATE NOT NULL,
    approved_date DATE,
    effective_date DATE,
    review_cycle_months INTEGER NOT NULL DEFAULT 12,
    next_review_date DATE,

    -- Supersession
    supersedes TEXT,
    superseded_by TEXT,

    -- Scope
    affects TEXT[] NOT NULL DEFAULT '{}',

    -- Constitutional authority chain
    constitutional_authority TEXT NOT NULL,

    -- Canonical hash (SHA-256 of ADR content)
    canonical_hash TEXT NOT NULL,
    hash_algorithm TEXT NOT NULL DEFAULT 'SHA-256',
    hash_computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Verification
    vega_attested BOOLEAN NOT NULL DEFAULT FALSE,
    vega_attestation_id UUID,
    vega_attestation_date TIMESTAMPTZ,

    -- Metadata
    description TEXT,
    rationale TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT adr_registry_status_check CHECK (
        status IN ('DRAFT', 'PROPOSED', 'APPROVED', 'DEPRECATED', 'SUPERSEDED', 'REJECTED')
    ),
    CONSTRAINT adr_registry_tier_check CHECK (
        governance_tier IN ('Tier-1', 'Tier-2', 'Tier-3')
    )
);

CREATE INDEX IF NOT EXISTS idx_adr_registry_status ON fhq_meta.adr_registry(status);
CREATE INDEX IF NOT EXISTS idx_adr_registry_tier ON fhq_meta.adr_registry(governance_tier);
CREATE INDEX IF NOT EXISTS idx_adr_registry_owner ON fhq_meta.adr_registry(owner);
CREATE INDEX IF NOT EXISTS idx_adr_registry_number ON fhq_meta.adr_registry(adr_number);

COMMENT ON TABLE fhq_meta.adr_registry IS 'ADR-004: Canonical registry of all Architectural Decision Records with SHA-256 hashes';

-- =====================================================
-- 2. ADR DEPENDENCIES TABLE (LINEAGE)
-- =====================================================
-- Tracks dependency relationships between ADRs
-- Implements: Authority chain verification

CREATE TABLE IF NOT EXISTS fhq_meta.adr_dependencies (
    -- Primary key
    dependency_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Dependency relationship
    source_adr_id TEXT NOT NULL REFERENCES fhq_meta.adr_registry(adr_id),
    target_adr_id TEXT NOT NULL REFERENCES fhq_meta.adr_registry(adr_id),

    -- Relationship type
    dependency_type TEXT NOT NULL DEFAULT 'EXTENDS',

    -- Relationship metadata
    relationship_description TEXT,
    is_mandatory BOOLEAN NOT NULL DEFAULT TRUE,

    -- Ordering in authority chain
    chain_order INTEGER NOT NULL DEFAULT 0,

    -- Verification
    verified_at TIMESTAMPTZ,
    verified_by TEXT,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'LARS',

    -- Constraints
    CONSTRAINT adr_dependencies_type_check CHECK (
        dependency_type IN ('EXTENDS', 'IMPLEMENTS', 'SUPERSEDES', 'REQUIRES', 'CONFLICTS', 'RELATED')
    ),
    CONSTRAINT adr_dependencies_no_self_ref CHECK (source_adr_id != target_adr_id),
    CONSTRAINT adr_dependencies_unique_pair UNIQUE (source_adr_id, target_adr_id, dependency_type)
);

CREATE INDEX IF NOT EXISTS idx_adr_dependencies_source ON fhq_meta.adr_dependencies(source_adr_id);
CREATE INDEX IF NOT EXISTS idx_adr_dependencies_target ON fhq_meta.adr_dependencies(target_adr_id);
CREATE INDEX IF NOT EXISTS idx_adr_dependencies_type ON fhq_meta.adr_dependencies(dependency_type);

COMMENT ON TABLE fhq_meta.adr_dependencies IS 'ADR-004: Lineage tracking for ADR authority chains and dependencies';

-- =====================================================
-- 3. AGENT KEYS TABLE (ADR-008 Section 2.2/2.3)
-- =====================================================
-- Key lifecycle management with dual-publishing support
-- States: PENDING → ACTIVE → DEPRECATED → ARCHIVED

CREATE TABLE IF NOT EXISTS fhq_meta.agent_keys (
    -- Primary identification
    key_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Agent binding
    agent_id TEXT NOT NULL,

    -- Key data
    public_key TEXT NOT NULL,
    key_fingerprint TEXT NOT NULL,
    signing_algorithm TEXT NOT NULL DEFAULT 'Ed25519',

    -- Key lifecycle state (ADR-008 Appendix A)
    key_state TEXT NOT NULL DEFAULT 'PENDING',

    -- Lifecycle timestamps
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_at TIMESTAMPTZ,
    deprecated_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,

    -- Rotation tracking (ADR-008 Section 2.3)
    rotation_sequence INTEGER NOT NULL DEFAULT 1,
    previous_key_id UUID REFERENCES fhq_meta.agent_keys(key_id),
    next_key_id UUID REFERENCES fhq_meta.agent_keys(key_id),

    -- Grace period (24h dual-publishing)
    grace_period_hours INTEGER NOT NULL DEFAULT 24,
    grace_period_ends_at TIMESTAMPTZ,

    -- KeyStore backend (ADR-008 Section 2.2)
    keystore_backend TEXT NOT NULL DEFAULT 'ENV',
    keystore_path TEXT,

    -- Verification allowance
    allows_verification BOOLEAN NOT NULL DEFAULT FALSE,
    verification_priority INTEGER NOT NULL DEFAULT 0,

    -- Retention (ADR-008 Section 2.4)
    retention_tier TEXT NOT NULL DEFAULT 'HOT',
    retention_days INTEGER NOT NULL DEFAULT 90,

    -- Compliance
    adr_reference TEXT NOT NULL DEFAULT 'ADR-008',

    -- Audit
    created_by TEXT NOT NULL DEFAULT 'SYSTEM',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT agent_keys_state_check CHECK (
        key_state IN ('PENDING', 'ACTIVE', 'DEPRECATED', 'ARCHIVED', 'REVOKED')
    ),
    CONSTRAINT agent_keys_backend_check CHECK (
        keystore_backend IN ('ENV', 'VAULT', 'HSM')
    ),
    CONSTRAINT agent_keys_retention_tier_check CHECK (
        retention_tier IN ('HOT', 'WARM', 'COLD')
    ),
    CONSTRAINT agent_keys_algorithm_check CHECK (
        signing_algorithm = 'Ed25519'
    )
);

-- Unique constraint: only one ACTIVE key per agent
CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_keys_active_unique
    ON fhq_meta.agent_keys(agent_id)
    WHERE key_state = 'ACTIVE';

CREATE INDEX IF NOT EXISTS idx_agent_keys_agent ON fhq_meta.agent_keys(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_keys_state ON fhq_meta.agent_keys(key_state);
CREATE INDEX IF NOT EXISTS idx_agent_keys_fingerprint ON fhq_meta.agent_keys(key_fingerprint);
CREATE INDEX IF NOT EXISTS idx_agent_keys_verification ON fhq_meta.agent_keys(allows_verification) WHERE allows_verification = TRUE;

COMMENT ON TABLE fhq_meta.agent_keys IS 'ADR-008 Section 2.3: Agent Ed25519 key lifecycle management with dual-publishing rotation';

-- =====================================================
-- 4. KEY ARCHIVAL LOG (ADR-008 Section 2.4)
-- =====================================================
-- Multi-tier archival audit trail
-- Tier 1 (Hot): 24h, Tier 2 (Warm): 90d, Tier 3 (Cold): 7 years

CREATE TABLE IF NOT EXISTS fhq_meta.key_archival_log (
    -- Primary identification
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Key reference
    key_id UUID NOT NULL REFERENCES fhq_meta.agent_keys(key_id),
    agent_id TEXT NOT NULL,
    key_fingerprint TEXT NOT NULL,

    -- Archival event
    event_type TEXT NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Source and target tiers
    source_tier TEXT,
    target_tier TEXT NOT NULL,

    -- Storage location
    storage_location TEXT,
    storage_encrypted BOOLEAN NOT NULL DEFAULT TRUE,
    encryption_algorithm TEXT DEFAULT 'AES-256-GCM',

    -- Retention policy
    retention_days INTEGER NOT NULL,
    scheduled_deletion_at TIMESTAMPTZ,

    -- Compliance
    compliance_standard TEXT,
    regulatory_requirement TEXT,

    -- Verification
    archival_hash TEXT NOT NULL,
    hash_algorithm TEXT NOT NULL DEFAULT 'SHA-256',
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    verified_at TIMESTAMPTZ,
    verified_by TEXT,

    -- ADR reference
    adr_reference TEXT NOT NULL DEFAULT 'ADR-008',

    -- Audit
    performed_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT key_archival_event_type_check CHECK (
        event_type IN ('GENERATED', 'ACTIVATED', 'ROTATED', 'DEPRECATED', 'ARCHIVED', 'MIGRATED', 'DELETED', 'RESTORED', 'REVOKED')
    ),
    CONSTRAINT key_archival_tier_check CHECK (
        target_tier IN ('HOT', 'WARM', 'COLD', 'DELETED')
    )
);

CREATE INDEX IF NOT EXISTS idx_key_archival_key ON fhq_meta.key_archival_log(key_id);
CREATE INDEX IF NOT EXISTS idx_key_archival_agent ON fhq_meta.key_archival_log(agent_id);
CREATE INDEX IF NOT EXISTS idx_key_archival_event ON fhq_meta.key_archival_log(event_type);
CREATE INDEX IF NOT EXISTS idx_key_archival_timestamp ON fhq_meta.key_archival_log(event_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_key_archival_tier ON fhq_meta.key_archival_log(target_tier);

COMMENT ON TABLE fhq_meta.key_archival_log IS 'ADR-008 Section 2.4: Multi-tier key archival audit trail (Hot 24h, Warm 90d, Cold 7y)';

-- =====================================================
-- 5. G3/G4 AUDIT LOG TABLE (IF NOT EXISTS)
-- =====================================================
-- Governance audit trail for G3/G4 approvals

CREATE TABLE IF NOT EXISTS fhq_governance.audit_log (
    -- Primary identification
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Event identification
    event_type TEXT NOT NULL,
    event_category TEXT NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Target
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_version TEXT,

    -- Actor
    actor_id TEXT NOT NULL,
    actor_role TEXT,

    -- Event data
    event_data JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Previous state (for changes)
    previous_state JSONB,
    new_state JSONB,

    -- Cryptographic evidence
    event_hash TEXT NOT NULL,
    hash_algorithm TEXT NOT NULL DEFAULT 'SHA-256',
    signature TEXT,
    signature_verified BOOLEAN DEFAULT FALSE,

    -- Governance gate
    governance_gate TEXT,

    -- ADR reference
    adr_reference TEXT,

    -- Audit metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT audit_log_category_check CHECK (
        event_category IN ('ADR', 'GOVERNANCE', 'SECURITY', 'COMPLIANCE', 'OPERATIONAL', 'SYSTEM')
    ),
    CONSTRAINT audit_log_gate_check CHECK (
        governance_gate IS NULL OR governance_gate IN ('G1', 'G2', 'G3', 'G4')
    )
);

CREATE INDEX IF NOT EXISTS idx_audit_log_type ON fhq_governance.audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_log_category ON fhq_governance.audit_log(event_category);
CREATE INDEX IF NOT EXISTS idx_audit_log_target ON fhq_governance.audit_log(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON fhq_governance.audit_log(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON fhq_governance.audit_log(event_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_gate ON fhq_governance.audit_log(governance_gate);

COMMENT ON TABLE fhq_governance.audit_log IS 'G3/G4 Governance audit trail for ADR approvals and compliance events';

-- =====================================================
-- 6. REGISTER ADR-008 IN ADR REGISTRY
-- =====================================================

-- Compute canonical hash for ADR-008
-- SHA-256 of: ADR-008 | Cryptographic Key Management & Rotation Architecture | 2026.PRODUCTION | APPROVED | LARS

INSERT INTO fhq_meta.adr_registry (
    adr_id,
    adr_number,
    title,
    version,
    status,
    author,
    owner,
    governance_tier,
    created_date,
    approved_date,
    effective_date,
    review_cycle_months,
    next_review_date,
    supersedes,
    affects,
    constitutional_authority,
    canonical_hash,
    hash_algorithm,
    description,
    rationale
) VALUES (
    'ADR-008',
    8,
    'Cryptographic Key Management & Rotation Architecture',
    '2026.PRODUCTION',
    'APPROVED',
    'LARS (CSO – Strategy & Governance)',
    'LARS – Chief Strategy & Alpha Officer',
    'Tier-2',
    '2025-11-22',
    '2025-11-22',
    '2025-11-22',
    12,
    '2026-11-22',
    NULL,
    ARRAY['Orchestrator', 'LARS', 'STIG', 'LINE', 'FINN', 'VEGA', 'fhq_org', 'fhq_meta'],
    'ADR-001 → ADR-002 → ADR-006 → ADR-007 → EC-001',
    -- SHA-256 canonical hash (computed from ADR content)
    ENCODE(SHA256(
        'ADR-008|Cryptographic Key Management & Rotation Architecture|2026.PRODUCTION|APPROVED|LARS|2025-11-22|Tier-2|Ed25519|KeyStore|Rolling Rotation|Multi-Tier Archival'::bytea
    ), 'hex'),
    'SHA-256',
    'Defines deterministic, tamper-evident and non-repudiable signatures for all agent actions using Ed25519 keys, controlled rotation with dual-publishing, secure archival and cross-agent verification.',
    'Tier-2 governance mandates real Ed25519 keys, controlled rotation, secure archival and cross-agent verification. Architecture supports migration from local → Vault → HSM without redesign.'
)
ON CONFLICT (adr_id) DO UPDATE SET
    status = EXCLUDED.status,
    approved_date = EXCLUDED.approved_date,
    effective_date = EXCLUDED.effective_date,
    canonical_hash = EXCLUDED.canonical_hash,
    hash_computed_at = NOW(),
    updated_at = NOW();

-- =====================================================
-- 7. REGISTER ADR DEPENDENCIES (LINEAGE)
-- =====================================================

-- ADR-008 EXTENDS ADR-001 (Constitutional Foundation)
INSERT INTO fhq_meta.adr_dependencies (
    source_adr_id, target_adr_id, dependency_type, chain_order,
    relationship_description, is_mandatory
) VALUES (
    'ADR-008', 'ADR-001', 'EXTENDS', 1,
    'ADR-008 derives constitutional authority from ADR-001 Agent Architecture',
    TRUE
) ON CONFLICT (source_adr_id, target_adr_id, dependency_type) DO NOTHING;

-- ADR-008 EXTENDS ADR-002 (Audit Reconciliation)
INSERT INTO fhq_meta.adr_dependencies (
    source_adr_id, target_adr_id, dependency_type, chain_order,
    relationship_description, is_mandatory
) VALUES (
    'ADR-008', 'ADR-002', 'EXTENDS', 2,
    'ADR-008 implements audit requirements from ADR-002',
    TRUE
) ON CONFLICT (source_adr_id, target_adr_id, dependency_type) DO NOTHING;

-- ADR-008 EXTENDS ADR-006 (VEGA Compliance)
INSERT INTO fhq_meta.adr_dependencies (
    source_adr_id, target_adr_id, dependency_type, chain_order,
    relationship_description, is_mandatory
) VALUES (
    'ADR-008', 'ADR-006', 'EXTENDS', 3,
    'ADR-008 implements VEGA attestation requirements from ADR-006',
    TRUE
) ON CONFLICT (source_adr_id, target_adr_id, dependency_type) DO NOTHING;

-- ADR-008 EXTENDS ADR-007 (Orchestrator Architecture)
INSERT INTO fhq_meta.adr_dependencies (
    source_adr_id, target_adr_id, dependency_type, chain_order,
    relationship_description, is_mandatory
) VALUES (
    'ADR-008', 'ADR-007', 'EXTENDS', 4,
    'ADR-008 provides cryptographic foundation for ADR-007 orchestrator binding',
    TRUE
) ON CONFLICT (source_adr_id, target_adr_id, dependency_type) DO NOTHING;

-- =====================================================
-- 8. REGISTER GENESIS KEYS FOR ALL AGENTS
-- =====================================================
-- Initial key registration with PENDING state
-- Production keys will be activated via key rotation

INSERT INTO fhq_meta.agent_keys (
    agent_id,
    public_key,
    key_fingerprint,
    signing_algorithm,
    key_state,
    keystore_backend,
    allows_verification,
    verification_priority,
    retention_tier,
    retention_days,
    created_by
)
SELECT
    agent_id,
    public_key,
    ENCODE(SHA256(public_key::bytea), 'hex'),
    signing_algorithm,
    'ACTIVE',
    'ENV',
    TRUE,
    1,
    'HOT',
    90,
    'LARS'
FROM fhq_org.org_agents
WHERE signing_algorithm = 'Ed25519'
ON CONFLICT DO NOTHING;

-- =====================================================
-- 9. G3/G4 AUDIT LOG ENTRIES FOR ADR-008
-- =====================================================

-- G3 Audit Entry: ADR-008 Proposed
INSERT INTO fhq_governance.audit_log (
    event_type,
    event_category,
    target_type,
    target_id,
    target_version,
    actor_id,
    actor_role,
    event_data,
    event_hash,
    governance_gate,
    adr_reference
) VALUES (
    'ADR_PROPOSED',
    'ADR',
    'ADR',
    'ADR-008',
    '2026.PRODUCTION',
    'LARS',
    'CSO – Strategy & Governance',
    jsonb_build_object(
        'title', 'Cryptographic Key Management & Rotation Architecture',
        'governance_tier', 'Tier-2',
        'constitutional_authority', 'ADR-001 → ADR-002 → ADR-006 → ADR-007 → EC-001',
        'key_decisions', jsonb_build_array(
            'Ed25519 as canonical signature scheme',
            'Hierarchical KeyStore with three operational modes',
            'Rolling key rotation with dual-publishing',
            'Multi-tier key archival strategy'
        ),
        'compliance_standards', jsonb_build_array(
            'ISO/IEC 11770-1',
            'ISO 8000-110',
            'BCBS 239',
            'GIPS'
        )
    ),
    ENCODE(SHA256('G3_ADR_PROPOSED_ADR-008_2025-11-22'::bytea), 'hex'),
    'G3',
    'ADR-008'
);

-- G4 Audit Entry: ADR-008 Approved for Production
INSERT INTO fhq_governance.audit_log (
    event_type,
    event_category,
    target_type,
    target_id,
    target_version,
    actor_id,
    actor_role,
    event_data,
    event_hash,
    governance_gate,
    adr_reference
) VALUES (
    'ADR_APPROVED',
    'ADR',
    'ADR',
    'ADR-008',
    '2026.PRODUCTION',
    'LARS',
    'CSO – Strategy & Governance',
    jsonb_build_object(
        'approval_status', 'APPROVED',
        'effective_date', '2025-11-22',
        'authority_chain', 'ADR-001 → ADR-002 → ADR-006 → ADR-007 → ADR-008 → EC-001',
        'production_environment', 'Supabase PostgreSQL (127.0.0.1:54322)',
        'tables_created', jsonb_build_array(
            'fhq_meta.adr_registry',
            'fhq_meta.adr_dependencies',
            'fhq_meta.agent_keys',
            'fhq_meta.key_archival_log'
        ),
        'verification_requirements', jsonb_build_object(
            'key_rotation_days', 90,
            'grace_period_hours', 24,
            'archival_tiers', jsonb_build_object(
                'hot', '24h',
                'warm', '90d',
                'cold', '7y'
            )
        )
    ),
    ENCODE(SHA256('G4_ADR_APPROVED_ADR-008_2025-11-22_PRODUCTION'::bytea), 'hex'),
    'G4',
    'ADR-008'
);

-- =====================================================
-- 10. KEY ARCHIVAL LOG GENESIS ENTRIES
-- =====================================================

-- Log initial key generation for each agent
INSERT INTO fhq_meta.key_archival_log (
    key_id,
    agent_id,
    key_fingerprint,
    event_type,
    target_tier,
    retention_days,
    archival_hash,
    performed_by,
    compliance_standard,
    regulatory_requirement
)
SELECT
    key_id,
    agent_id,
    key_fingerprint,
    'GENERATED',
    'HOT',
    90,
    ENCODE(SHA256((agent_id || '_GENESIS_KEY_' || NOW()::TEXT)::bytea), 'hex'),
    'LARS',
    'ISO/IEC 11770-1',
    'Key lifecycle tracking'
FROM fhq_meta.agent_keys
WHERE key_state = 'ACTIVE'
ON CONFLICT DO NOTHING;

-- =====================================================
-- 11. VERIFICATION QUERIES
-- =====================================================

-- Verify ADR-008 registered
DO $$
DECLARE
    adr_registered BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM fhq_meta.adr_registry
        WHERE adr_id = 'ADR-008'
          AND status = 'APPROVED'
    ) INTO adr_registered;

    IF NOT adr_registered THEN
        RAISE WARNING 'ADR-008 not registered in adr_registry';
    ELSE
        RAISE NOTICE 'ADR-008 successfully registered and APPROVED';
    END IF;
END $$;

-- Verify dependencies registered
DO $$
DECLARE
    dep_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO dep_count
    FROM fhq_meta.adr_dependencies
    WHERE source_adr_id = 'ADR-008';

    IF dep_count < 4 THEN
        RAISE WARNING 'ADR-008 dependencies incomplete: %/4', dep_count;
    ELSE
        RAISE NOTICE 'ADR-008 dependencies: %/4 registered', dep_count;
    END IF;
END $$;

-- Verify agent keys registered
DO $$
DECLARE
    key_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO key_count
    FROM fhq_meta.agent_keys
    WHERE key_state = 'ACTIVE';

    IF key_count < 5 THEN
        RAISE WARNING 'Active agent keys: %/5', key_count;
    ELSE
        RAISE NOTICE 'Active agent keys: %/5 registered', key_count;
    END IF;
END $$;

-- Verify G3/G4 audit entries
DO $$
DECLARE
    audit_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO audit_count
    FROM fhq_governance.audit_log
    WHERE adr_reference = 'ADR-008'
      AND governance_gate IN ('G3', 'G4');

    IF audit_count < 2 THEN
        RAISE WARNING 'ADR-008 audit entries: %/2', audit_count;
    ELSE
        RAISE NOTICE 'ADR-008 G3/G4 audit entries: %/2 registered', audit_count;
    END IF;
END $$;

COMMIT;

-- =====================================================
-- MIGRATION SUMMARY
-- =====================================================

SELECT
    'MIGRATION 019 COMPLETE' AS status,
    'ADR-008 Cryptographic Key Management' AS description,
    NOW() AS completed_at;

\echo ''
\echo '=========================================='
\echo 'MIGRATION 019: ADR-008 CRYPTOGRAPHIC KEY MANAGEMENT'
\echo '=========================================='
\echo 'Tables created:'
\echo '  - fhq_meta.adr_registry (ADR registration)'
\echo '  - fhq_meta.adr_dependencies (ADR lineage)'
\echo '  - fhq_meta.agent_keys (Key lifecycle)'
\echo '  - fhq_meta.key_archival_log (Archival audit)'
\echo '  - fhq_governance.audit_log (G3/G4 audit)'
\echo ''
\echo 'ADR-008 registered with:'
\echo '  - Status: APPROVED'
\echo '  - Governance Tier: Tier-2'
\echo '  - Authority Chain: ADR-001 → ADR-002 → ADR-006 → ADR-007 → EC-001'
\echo ''
\echo 'Key lifecycle states: PENDING → ACTIVE → DEPRECATED → ARCHIVED'
\echo 'Archival tiers: HOT (24h) → WARM (90d) → COLD (7y)'
\echo '=========================================='
\echo ''
\echo 'Next step: Run STIG verification script'
\echo '  python 04_AGENTS/PHASE3/stig_adr008_verification.py'
\echo ''
