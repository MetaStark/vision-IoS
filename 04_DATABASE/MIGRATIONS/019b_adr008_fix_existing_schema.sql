-- =====================================================
-- MIGRATION 019b: ADR-008 FIX FOR EXISTING SCHEMA
-- =====================================================
--
-- Purpose: Add missing columns to existing adr_registry and create
--          new tables for ADR-008 Cryptographic Key Management
--
-- Run this instead of 019 if adr_registry already exists
--
-- =====================================================

BEGIN;

-- =====================================================
-- 1. ADD MISSING COLUMNS TO adr_registry
-- =====================================================

-- Add governance_tier column
ALTER TABLE fhq_meta.adr_registry
ADD COLUMN IF NOT EXISTS governance_tier TEXT DEFAULT 'Tier-3';

-- Add owner column
ALTER TABLE fhq_meta.adr_registry
ADD COLUMN IF NOT EXISTS owner TEXT;

-- Add adr_number column
ALTER TABLE fhq_meta.adr_registry
ADD COLUMN IF NOT EXISTS adr_number INTEGER;

-- Add review_cycle_months
ALTER TABLE fhq_meta.adr_registry
ADD COLUMN IF NOT EXISTS review_cycle_months INTEGER DEFAULT 12;

-- Add next_review_date
ALTER TABLE fhq_meta.adr_registry
ADD COLUMN IF NOT EXISTS next_review_date DATE;

-- Add affects array
ALTER TABLE fhq_meta.adr_registry
ADD COLUMN IF NOT EXISTS affects TEXT[] DEFAULT '{}';

-- Add constitutional_authority
ALTER TABLE fhq_meta.adr_registry
ADD COLUMN IF NOT EXISTS constitutional_authority TEXT;

-- Add description
ALTER TABLE fhq_meta.adr_registry
ADD COLUMN IF NOT EXISTS description TEXT;

-- Add rationale
ALTER TABLE fhq_meta.adr_registry
ADD COLUMN IF NOT EXISTS rationale TEXT;

-- Add VEGA attestation columns
ALTER TABLE fhq_meta.adr_registry
ADD COLUMN IF NOT EXISTS vega_attested BOOLEAN DEFAULT FALSE;

ALTER TABLE fhq_meta.adr_registry
ADD COLUMN IF NOT EXISTS vega_attestation_id UUID;

ALTER TABLE fhq_meta.adr_registry
ADD COLUMN IF NOT EXISTS vega_attestation_date TIMESTAMPTZ;

-- Create index on governance_tier
CREATE INDEX IF NOT EXISTS idx_adr_registry_tier
ON fhq_meta.adr_registry(governance_tier);

CREATE INDEX IF NOT EXISTS idx_adr_registry_owner
ON fhq_meta.adr_registry(owner);

COMMIT;

-- =====================================================
-- 2. ADR DEPENDENCIES TABLE (LINEAGE)
-- =====================================================

BEGIN;

CREATE TABLE IF NOT EXISTS fhq_meta.adr_dependencies (
    dependency_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_adr_id TEXT NOT NULL,
    target_adr_id TEXT NOT NULL,
    dependency_type TEXT NOT NULL DEFAULT 'EXTENDS',
    relationship_description TEXT,
    is_mandatory BOOLEAN NOT NULL DEFAULT TRUE,
    chain_order INTEGER NOT NULL DEFAULT 0,
    verified_at TIMESTAMPTZ,
    verified_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'LARS',

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

COMMIT;

-- =====================================================
-- 3. AGENT KEYS TABLE (ADR-008 Section 2.2/2.3)
-- =====================================================

BEGIN;

CREATE TABLE IF NOT EXISTS fhq_meta.agent_keys (
    key_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL,
    public_key TEXT NOT NULL,
    key_fingerprint TEXT NOT NULL,
    signing_algorithm TEXT NOT NULL DEFAULT 'Ed25519',
    key_state TEXT NOT NULL DEFAULT 'PENDING',
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_at TIMESTAMPTZ,
    deprecated_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    rotation_sequence INTEGER NOT NULL DEFAULT 1,
    previous_key_id UUID REFERENCES fhq_meta.agent_keys(key_id),
    next_key_id UUID REFERENCES fhq_meta.agent_keys(key_id),
    grace_period_hours INTEGER NOT NULL DEFAULT 24,
    grace_period_ends_at TIMESTAMPTZ,
    keystore_backend TEXT NOT NULL DEFAULT 'ENV',
    keystore_path TEXT,
    allows_verification BOOLEAN NOT NULL DEFAULT FALSE,
    verification_priority INTEGER NOT NULL DEFAULT 0,
    retention_tier TEXT NOT NULL DEFAULT 'HOT',
    retention_days INTEGER NOT NULL DEFAULT 90,
    adr_reference TEXT NOT NULL DEFAULT 'ADR-008',
    created_by TEXT NOT NULL DEFAULT 'SYSTEM',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

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

COMMIT;

-- =====================================================
-- 4. KEY ARCHIVAL LOG (ADR-008 Section 2.4)
-- =====================================================

BEGIN;

CREATE TABLE IF NOT EXISTS fhq_meta.key_archival_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_id UUID NOT NULL REFERENCES fhq_meta.agent_keys(key_id),
    agent_id TEXT NOT NULL,
    key_fingerprint TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_tier TEXT,
    target_tier TEXT NOT NULL,
    storage_location TEXT,
    storage_encrypted BOOLEAN NOT NULL DEFAULT TRUE,
    encryption_algorithm TEXT DEFAULT 'AES-256-GCM',
    retention_days INTEGER NOT NULL,
    scheduled_deletion_at TIMESTAMPTZ,
    compliance_standard TEXT,
    regulatory_requirement TEXT,
    archival_hash TEXT NOT NULL,
    hash_algorithm TEXT NOT NULL DEFAULT 'SHA-256',
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    verified_at TIMESTAMPTZ,
    verified_by TEXT,
    adr_reference TEXT NOT NULL DEFAULT 'ADR-008',
    performed_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

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

COMMIT;

-- =====================================================
-- 5. G3/G4 AUDIT LOG TABLE
-- =====================================================

BEGIN;

CREATE TABLE IF NOT EXISTS fhq_governance.audit_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    event_category TEXT NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_version TEXT,
    actor_id TEXT NOT NULL,
    actor_role TEXT,
    event_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    previous_state JSONB,
    new_state JSONB,
    event_hash TEXT NOT NULL,
    hash_algorithm TEXT NOT NULL DEFAULT 'SHA-256',
    signature TEXT,
    signature_verified BOOLEAN DEFAULT FALSE,
    governance_gate TEXT,
    adr_reference TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

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

COMMIT;

-- =====================================================
-- 6. UPDATE EXISTING ADRs WITH NEW COLUMNS
-- =====================================================

BEGIN;

-- Update ADR-001
UPDATE fhq_meta.adr_registry SET
    adr_number = 1,
    governance_tier = 'Tier-1',
    owner = 'CEO',
    constitutional_authority = 'Constitutional Foundation',
    affects = ARRAY['All Agents', 'All Systems']
WHERE adr_id = 'ADR-001';

-- Update ADR-002
UPDATE fhq_meta.adr_registry SET
    adr_number = 2,
    governance_tier = 'Tier-2',
    owner = 'LARS',
    constitutional_authority = 'ADR-001',
    affects = ARRAY['Audit', 'Logging', 'Error Handling']
WHERE adr_id = 'ADR-002';

-- Update ADR-003
UPDATE fhq_meta.adr_registry SET
    adr_number = 3,
    governance_tier = 'Tier-2',
    owner = 'LARS',
    constitutional_authority = 'ADR-001 → ADR-002',
    affects = ARRAY['Compliance', 'Standards']
WHERE adr_id = 'ADR-003';

-- Update ADR-004
UPDATE fhq_meta.adr_registry SET
    adr_number = 4,
    governance_tier = 'Tier-2',
    owner = 'LARS',
    constitutional_authority = 'ADR-001 → ADR-002',
    affects = ARRAY['Change Management', 'Gates G1-G4']
WHERE adr_id = 'ADR-004';

-- Update ADR-006
UPDATE fhq_meta.adr_registry SET
    adr_number = 6,
    governance_tier = 'Tier-1',
    owner = 'VEGA',
    constitutional_authority = 'ADR-001 → EC-001',
    affects = ARRAY['VEGA', 'Governance', 'Autonomy']
WHERE adr_id = 'ADR-006';

-- Update ADR-007
UPDATE fhq_meta.adr_registry SET
    adr_number = 7,
    governance_tier = 'Tier-2',
    owner = 'LARS',
    constitutional_authority = 'ADR-001 → ADR-002 → ADR-006 → EC-001',
    affects = ARRAY['Orchestrator', 'All Agents']
WHERE adr_id = 'ADR-007';

COMMIT;

-- =====================================================
-- 7. INSERT ADR-008
-- =====================================================

BEGIN;

INSERT INTO fhq_meta.adr_registry (
    adr_id,
    adr_number,
    adr_title,
    adr_status,
    adr_type,
    current_version,
    approval_authority,
    effective_date,
    governance_tier,
    owner,
    constitutional_authority,
    affects,
    description,
    rationale,
    sha256_hash,
    hash,
    title,
    status,
    version,
    created_by
) VALUES (
    'ADR-008',
    8,
    'Cryptographic Key Management & Rotation Architecture',
    'APPROVED',
    'ARCHITECTURAL',
    '2026.PRODUCTION',
    'LARS (CSO – Strategy & Governance)',
    '2025-11-22',
    'Tier-2',
    'LARS – Chief Strategy & Alpha Officer',
    'ADR-001 → ADR-002 → ADR-006 → ADR-007 → EC-001',
    ARRAY['Orchestrator', 'LARS', 'STIG', 'LINE', 'FINN', 'VEGA', 'fhq_org', 'fhq_meta'],
    'Defines deterministic, tamper-evident and non-repudiable signatures for all agent actions using Ed25519 keys, controlled rotation with dual-publishing, secure archival and cross-agent verification.',
    'Tier-2 governance mandates real Ed25519 keys, controlled rotation, secure archival and cross-agent verification. Architecture supports migration from local → Vault → HSM without redesign.',
    ENCODE(SHA256('ADR-008|Cryptographic Key Management|2026.PRODUCTION|APPROVED|LARS|Tier-2'::bytea), 'hex'),
    ENCODE(SHA256('ADR-008|Cryptographic Key Management|2026.PRODUCTION|APPROVED|LARS|Tier-2'::bytea), 'hex'),
    'Cryptographic Key Management & Rotation Architecture',
    'APPROVED',
    '2026.PRODUCTION',
    'LARS'
)
ON CONFLICT (adr_id) DO UPDATE SET
    adr_status = EXCLUDED.adr_status,
    governance_tier = EXCLUDED.governance_tier,
    owner = EXCLUDED.owner,
    constitutional_authority = EXCLUDED.constitutional_authority,
    affects = EXCLUDED.affects,
    description = EXCLUDED.description,
    rationale = EXCLUDED.rationale,
    sha256_hash = EXCLUDED.sha256_hash,
    hash = EXCLUDED.hash,
    updated_at = NOW();

COMMIT;

-- =====================================================
-- 8. REGISTER ADR DEPENDENCIES (LINEAGE)
-- =====================================================

BEGIN;

-- ADR-008 EXTENDS ADR-001
INSERT INTO fhq_meta.adr_dependencies (
    source_adr_id, target_adr_id, dependency_type, chain_order,
    relationship_description, is_mandatory
) VALUES (
    'ADR-008', 'ADR-001', 'EXTENDS', 1,
    'ADR-008 derives constitutional authority from ADR-001 Agent Architecture',
    TRUE
) ON CONFLICT (source_adr_id, target_adr_id, dependency_type) DO NOTHING;

-- ADR-008 EXTENDS ADR-002
INSERT INTO fhq_meta.adr_dependencies (
    source_adr_id, target_adr_id, dependency_type, chain_order,
    relationship_description, is_mandatory
) VALUES (
    'ADR-008', 'ADR-002', 'EXTENDS', 2,
    'ADR-008 implements audit requirements from ADR-002',
    TRUE
) ON CONFLICT (source_adr_id, target_adr_id, dependency_type) DO NOTHING;

-- ADR-008 EXTENDS ADR-006
INSERT INTO fhq_meta.adr_dependencies (
    source_adr_id, target_adr_id, dependency_type, chain_order,
    relationship_description, is_mandatory
) VALUES (
    'ADR-008', 'ADR-006', 'EXTENDS', 3,
    'ADR-008 implements VEGA attestation requirements from ADR-006',
    TRUE
) ON CONFLICT (source_adr_id, target_adr_id, dependency_type) DO NOTHING;

-- ADR-008 EXTENDS ADR-007
INSERT INTO fhq_meta.adr_dependencies (
    source_adr_id, target_adr_id, dependency_type, chain_order,
    relationship_description, is_mandatory
) VALUES (
    'ADR-008', 'ADR-007', 'EXTENDS', 4,
    'ADR-008 provides cryptographic foundation for ADR-007 orchestrator binding',
    TRUE
) ON CONFLICT (source_adr_id, target_adr_id, dependency_type) DO NOTHING;

COMMIT;

-- =====================================================
-- 9. REGISTER GENESIS KEYS FOR ALL AGENTS
-- =====================================================

BEGIN;

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
    created_by,
    activated_at
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
    'LARS',
    NOW()
FROM fhq_org.org_agents
WHERE signing_algorithm = 'Ed25519'
ON CONFLICT DO NOTHING;

COMMIT;

-- =====================================================
-- 10. G3/G4 AUDIT LOG ENTRIES FOR ADR-008
-- =====================================================

BEGIN;

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
        'tables_created', jsonb_build_array(
            'fhq_meta.adr_dependencies',
            'fhq_meta.agent_keys',
            'fhq_meta.key_archival_log',
            'fhq_governance.audit_log'
        )
    ),
    ENCODE(SHA256('G4_ADR_APPROVED_ADR-008_2025-11-22_PRODUCTION'::bytea), 'hex'),
    'G4',
    'ADR-008'
);

COMMIT;

-- =====================================================
-- 11. KEY ARCHIVAL LOG GENESIS ENTRIES
-- =====================================================

BEGIN;

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

COMMIT;

-- =====================================================
-- 12. VERIFICATION
-- =====================================================

DO $$
DECLARE
    adr008_exists BOOLEAN;
    deps_count INTEGER;
    keys_count INTEGER;
BEGIN
    -- Check ADR-008
    SELECT EXISTS (SELECT 1 FROM fhq_meta.adr_registry WHERE adr_id = 'ADR-008') INTO adr008_exists;
    IF adr008_exists THEN
        RAISE NOTICE 'ADR-008 registered successfully';
    ELSE
        RAISE WARNING 'ADR-008 NOT registered';
    END IF;

    -- Check dependencies
    SELECT COUNT(*) INTO deps_count FROM fhq_meta.adr_dependencies WHERE source_adr_id = 'ADR-008';
    RAISE NOTICE 'ADR-008 dependencies: %', deps_count;

    -- Check agent keys
    SELECT COUNT(*) INTO keys_count FROM fhq_meta.agent_keys WHERE key_state = 'ACTIVE';
    RAISE NOTICE 'Active agent keys: %', keys_count;
END $$;

-- =====================================================
-- SUMMARY
-- =====================================================

SELECT 'MIGRATION 019b COMPLETE' AS status, NOW() AS completed_at;

\echo ''
\echo '=========================================='
\echo 'MIGRATION 019b: ADR-008 FIX COMPLETE'
\echo '=========================================='
\echo 'Added columns to adr_registry:'
\echo '  - governance_tier, owner, adr_number'
\echo '  - affects, constitutional_authority'
\echo '  - description, rationale'
\echo '  - vega_attested, vega_attestation_id/date'
\echo ''
\echo 'Created tables:'
\echo '  - fhq_meta.adr_dependencies'
\echo '  - fhq_meta.agent_keys'
\echo '  - fhq_meta.key_archival_log'
\echo '  - fhq_governance.audit_log'
\echo ''
\echo 'ADR-008 registered with Tier-2 governance'
\echo '=========================================='
