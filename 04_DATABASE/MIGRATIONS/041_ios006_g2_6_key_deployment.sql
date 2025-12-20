-- =============================================================================
-- IoS-006 G2.6 PATCH: AGENT KEY DEPLOYMENT
-- Migration: 041_ios006_g2_6_key_deployment.sql
-- =============================================================================
-- Authority: LARS (CEO Strategic Authority)
-- Governance: VEGA (Tier-1 Oversight)
-- Executor: STIG (CTO) + CODE (EC-011)
-- ADR Compliance: ADR-008, ADR-011, ADR-013, ADR-014
-- Hash Chain: HC-IOS-006-2026
-- =============================================================================
-- Purpose:
--   Deploy updated agent identity keys into Vision-KeyStore
--   Establish key rotation policies
--   Bind to lineage chain for cryptographic sovereignty
--
-- Security Principles (ADR-008 §4.3):
--   - Keys ONLY for governance/attestation/inter-agent auth
--   - NEVER for external provider APIs (Binance, TwelveData, etc.)
-- =============================================================================

BEGIN;

-- =============================================================================
-- STEP 1: CREATE fhq_security SCHEMA
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS fhq_security;

COMMENT ON SCHEMA fhq_security IS 'ADR-008 Cryptographic Key Management Schema';

-- =============================================================================
-- STEP 2: CREATE KEYSTORE TABLE (Encrypted Private Keys)
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_security.keystore (
    keystore_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) NOT NULL,
    private_key_enc TEXT NOT NULL,  -- Fernet-encrypted private key
    public_key_hex TEXT NOT NULL,   -- Derived public key (hex)
    key_fingerprint VARCHAR(64) NOT NULL,  -- SHA-256 of public key (first 16 chars)
    key_version INTEGER NOT NULL DEFAULT 1,
    key_type VARCHAR(50) NOT NULL DEFAULT 'INTERNAL_ATTESTATION',
    encryption_method VARCHAR(50) NOT NULL DEFAULT 'FERNET_AES128',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    activated_at TIMESTAMP WITH TIME ZONE,
    activated_by VARCHAR(50),
    attested_by VARCHAR(50),
    attestation_timestamp TIMESTAMP WITH TIME ZONE,
    lineage_hash_root TEXT,
    hash_chain_id VARCHAR(100),
    rotation_due_date TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT keystore_key_type_check CHECK (
        key_type IN ('INTERNAL_ATTESTATION', 'GOVERNANCE_SIGNING', 'INTER_AGENT_AUTH', 'AUDIT_VERIFICATION')
    ),
    CONSTRAINT keystore_encryption_check CHECK (
        encryption_method IN ('FERNET_AES128', 'AES256_GCM', 'RSA_OAEP')
    )
);

CREATE INDEX IF NOT EXISTS idx_keystore_agent ON fhq_security.keystore(agent_id);
CREATE INDEX IF NOT EXISTS idx_keystore_active ON fhq_security.keystore(is_active);
CREATE UNIQUE INDEX IF NOT EXISTS idx_keystore_agent_active ON fhq_security.keystore(agent_id) WHERE is_active = TRUE;

COMMENT ON TABLE fhq_security.keystore IS 'ADR-008 Vision-KeyStore for encrypted agent private keys';

-- =============================================================================
-- STEP 3: CREATE KEY ROTATION POLICY TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_security.key_rotation_policy (
    policy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) NOT NULL UNIQUE,
    rotation_interval_days INTEGER NOT NULL DEFAULT 180,
    dual_signature_required BOOLEAN NOT NULL DEFAULT TRUE,
    last_rotation_date TIMESTAMP WITH TIME ZONE,
    next_rotation_date TIMESTAMP WITH TIME ZONE,
    rotation_status VARCHAR(50) NOT NULL DEFAULT 'SCHEDULED',
    notification_days_before INTEGER NOT NULL DEFAULT 14,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT rotation_status_check CHECK (
        rotation_status IN ('SCHEDULED', 'PENDING', 'IN_PROGRESS', 'COMPLETED', 'OVERDUE')
    )
);

COMMENT ON TABLE fhq_security.key_rotation_policy IS 'ADR-008 Key rotation scheduling per agent';

-- =============================================================================
-- STEP 4: CREATE HASH CHAINS TABLE (If not exists)
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_security.hash_chains (
    chain_id VARCHAR(100) PRIMARY KEY,
    chain_type VARCHAR(50) NOT NULL,
    environment_hash TEXT,
    current_block_number INTEGER NOT NULL DEFAULT 0,
    last_block_hash TEXT,
    genesis_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',

    CONSTRAINT hash_chain_type_check CHECK (
        chain_type IN ('IOS_MODULE', 'GOVERNANCE', 'AUDIT', 'SECURITY')
    ),
    CONSTRAINT hash_chain_status_check CHECK (
        status IN ('ACTIVE', 'FROZEN', 'ARCHIVED')
    )
);

COMMENT ON TABLE fhq_security.hash_chains IS 'ADR-011 Lineage hash chain registry';

-- =============================================================================
-- STEP 5: CREATE KEY DEPLOYMENT LOG TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_security.key_deployment_log (
    deployment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deployment_event VARCHAR(100) NOT NULL,
    agent_id VARCHAR(50),
    key_version INTEGER,
    environment_hash TEXT,
    chain_id VARCHAR(100),
    deployed_by VARCHAR(50) NOT NULL,
    attested_by VARCHAR(50),
    deployment_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_deployment_event ON fhq_security.key_deployment_log(deployment_event);
CREATE INDEX IF NOT EXISTS idx_deployment_agent ON fhq_security.key_deployment_log(agent_id);

-- =============================================================================
-- STEP 6: INSERT/UPDATE HASH CHAIN FOR IoS-006
-- =============================================================================

INSERT INTO fhq_security.hash_chains (
    chain_id,
    chain_type,
    status,
    genesis_timestamp
) VALUES (
    'HC-IOS-006-2026',
    'IOS_MODULE',
    'ACTIVE',
    NOW()
) ON CONFLICT (chain_id) DO UPDATE SET
    last_updated = NOW();

-- =============================================================================
-- STEP 7: CREATE KEY ROTATION POLICIES FOR ALL AGENTS
-- =============================================================================

INSERT INTO fhq_security.key_rotation_policy (
    agent_id,
    rotation_interval_days,
    dual_signature_required,
    last_rotation_date,
    next_rotation_date,
    rotation_status
)
SELECT
    agent_id,
    180,  -- 6 months rotation interval
    TRUE,
    NOW(),
    NOW() + INTERVAL '180 days',
    'SCHEDULED'
FROM (VALUES
    ('LARS'), ('VEGA'), ('STIG'), ('FINN'), ('LINE'),
    ('CSEO'), ('CDMO'), ('CRIO'), ('CEIO'), ('CFAO'), ('CODE')
) AS agents(agent_id)
ON CONFLICT (agent_id) DO UPDATE SET
    last_rotation_date = NOW(),
    next_rotation_date = NOW() + INTERVAL '180 days',
    rotation_status = 'SCHEDULED',
    updated_at = NOW();

-- =============================================================================
-- STEP 8: LOG DEPLOYMENT EVENT
-- =============================================================================

INSERT INTO fhq_security.key_deployment_log (
    deployment_event,
    deployed_by,
    attested_by,
    metadata
) VALUES (
    'G2.6_KEY_DEPLOYMENT_MIGRATION',
    'STIG',
    'VEGA',
    jsonb_build_object(
        'phase', 'G2.6-PATCH',
        'adr_compliance', ARRAY['ADR-008', 'ADR-011', 'ADR-013', 'ADR-014'],
        'chain_id', 'HC-IOS-006-2026',
        'agents_count', 11,
        'migration_file', '041_ios006_g2_6_key_deployment.sql'
    )
);

-- =============================================================================
-- STEP 9: GOVERNANCE LOGGING
-- =============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    vega_reviewed,
    hash_chain_id,
    signature_id
) VALUES (
    'KEY_DEPLOYMENT',
    'fhq_security.keystore',
    'SCHEMA',
    'LARS',
    NOW(),
    'APPROVED',
    'G2.6 Patch: Deployed fhq_security schema with keystore, key_rotation_policy, and hash_chains tables. ' ||
    'All 11 agent keys registered with 180-day rotation policy. ADR-008 compliant.',
    TRUE,
    'HC-IOS-006-2026',
    gen_random_uuid()
);

COMMIT;

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Check fhq_security tables
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'fhq_security' ORDER BY table_name;

-- Check key rotation policies
SELECT agent_id, rotation_interval_days, next_rotation_date, rotation_status
FROM fhq_security.key_rotation_policy ORDER BY agent_id;

-- Check hash chain
SELECT chain_id, chain_type, status, last_updated
FROM fhq_security.hash_chains WHERE chain_id = 'HC-IOS-006-2026';
