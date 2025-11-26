-- =====================================================
-- MIGRATION 019c: ADR-008 USING EXISTING TABLE SCHEMAS
-- =====================================================
--
-- Purpose: Register ADR-008 using existing table structures
-- Use this when tables already exist with different column names
--
-- =====================================================

BEGIN;

-- =====================================================
-- 1. INSERT ADR-008 DEPENDENCIES (using existing schema)
-- =====================================================
-- Existing schema: adr_id, depends_on[], dependency_type, criticality

INSERT INTO fhq_meta.adr_dependencies (
    adr_id,
    version,
    depends_on,
    dependency_type,
    criticality
) VALUES (
    'ADR-008',
    '2026.PRODUCTION',
    ARRAY['ADR-001', 'ADR-002', 'ADR-006', 'ADR-007'],
    'EXTENDS',
    'CRITICAL'
) ON CONFLICT DO NOTHING;

COMMIT;

-- =====================================================
-- 2. INSERT GENESIS KEYS FOR AGENTS (using existing schema)
-- =====================================================
-- Existing schema: agent_id, key_type, key_state, public_key_hex, key_storage_tier

BEGIN;

-- Insert keys from org_agents using existing column names
INSERT INTO fhq_meta.agent_keys (
    agent_id,
    key_type,
    key_state,
    public_key_hex,
    key_storage_tier,
    activation_date,
    retention_period_days,
    sha256_hash,
    metadata
)
SELECT
    agent_id,
    'ED25519_SIGNING',
    'ACTIVE',
    public_key,
    'TIER1_HOT',
    NOW(),
    90,
    ENCODE(SHA256(public_key::bytea), 'hex'),
    jsonb_build_object(
        'source', 'ADR-008 Migration',
        'signing_algorithm', signing_algorithm,
        'adr_reference', 'ADR-008'
    )
FROM fhq_org.org_agents
WHERE signing_algorithm = 'Ed25519'
  AND agent_id NOT IN (SELECT agent_id FROM fhq_meta.agent_keys WHERE key_state = 'ACTIVE')
ON CONFLICT DO NOTHING;

COMMIT;

-- =====================================================
-- 3. LOG KEY GENERATION EVENTS (using existing schema)
-- =====================================================
-- Existing schema: key_id, agent_id, archival_event, from_state, to_state, performed_by

BEGIN;

INSERT INTO fhq_meta.key_archival_log (
    key_id,
    agent_id,
    archival_event,
    from_state,
    to_state,
    from_tier,
    to_tier,
    reason,
    performed_by,
    sha256_hash
)
SELECT
    key_id,
    agent_id,
    'KEY_GENERATION',
    NULL,
    'ACTIVE',
    NULL,
    'TIER1_HOT',
    'ADR-008 Genesis key registration',
    'LARS',
    sha256_hash
FROM fhq_meta.agent_keys
WHERE key_state = 'ACTIVE'
  AND key_id NOT IN (SELECT key_id FROM fhq_meta.key_archival_log)
ON CONFLICT DO NOTHING;

COMMIT;

-- =====================================================
-- 4. VERIFICATION
-- =====================================================

DO $$
DECLARE
    adr008_exists BOOLEAN;
    deps_count INTEGER;
    keys_count INTEGER;
    archival_count INTEGER;
    audit_count INTEGER;
BEGIN
    -- Check ADR-008 in registry
    SELECT EXISTS (
        SELECT 1 FROM fhq_meta.adr_registry WHERE adr_id = 'ADR-008'
    ) INTO adr008_exists;

    IF adr008_exists THEN
        RAISE NOTICE '✓ ADR-008 registered in adr_registry';
    ELSE
        RAISE WARNING '✗ ADR-008 NOT in adr_registry';
    END IF;

    -- Check dependencies
    SELECT COUNT(*) INTO deps_count
    FROM fhq_meta.adr_dependencies
    WHERE adr_id = 'ADR-008';
    RAISE NOTICE '✓ ADR-008 dependencies: % entry/entries', deps_count;

    -- Check agent keys
    SELECT COUNT(*) INTO keys_count
    FROM fhq_meta.agent_keys
    WHERE key_state = 'ACTIVE';
    RAISE NOTICE '✓ Active agent keys: %', keys_count;

    -- Check archival log
    SELECT COUNT(*) INTO archival_count
    FROM fhq_meta.key_archival_log;
    RAISE NOTICE '✓ Key archival log entries: %', archival_count;

    -- Check G3/G4 audit
    SELECT COUNT(*) INTO audit_count
    FROM fhq_governance.audit_log
    WHERE adr_reference = 'ADR-008';
    RAISE NOTICE '✓ G3/G4 audit entries for ADR-008: %', audit_count;
END $$;

-- =====================================================
-- 5. SHOW REGISTERED ADR-008
-- =====================================================

SELECT
    adr_id,
    adr_title,
    adr_status,
    governance_tier,
    owner,
    constitutional_authority
FROM fhq_meta.adr_registry
WHERE adr_id = 'ADR-008';

-- =====================================================
-- 6. SHOW AUTHORITY CHAIN
-- =====================================================

SELECT
    adr_id,
    depends_on AS authority_chain,
    dependency_type,
    criticality
FROM fhq_meta.adr_dependencies
WHERE adr_id = 'ADR-008';

-- =====================================================
-- 7. SHOW ACTIVE KEYS
-- =====================================================

SELECT
    agent_id,
    key_type,
    key_state,
    key_storage_tier,
    LEFT(public_key_hex, 32) || '...' AS public_key_preview,
    activation_date
FROM fhq_meta.agent_keys
WHERE key_state = 'ACTIVE'
ORDER BY agent_id;

\echo ''
\echo '=========================================='
\echo 'MIGRATION 019c: ADR-008 COMPLETE'
\echo '=========================================='
\echo 'ADR-008 Cryptographic Key Management registered'
\echo ''
\echo 'Authority Chain: ADR-001 → ADR-002 → ADR-006 → ADR-007 → ADR-008'
\echo ''
\echo 'Key Lifecycle: PENDING → ACTIVE → DEPRECATED → ARCHIVED'
\echo 'Storage Tiers: TIER1_HOT (24h) → TIER2_WARM (90d) → TIER3_COLD (7y)'
\echo '=========================================='
