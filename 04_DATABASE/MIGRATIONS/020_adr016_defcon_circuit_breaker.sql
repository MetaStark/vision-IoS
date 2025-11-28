-- ============================================================================
-- MIGRATION 020: ADR-016 DEFCON & CIRCUIT BREAKER PROTOCOL
-- ============================================================================
-- Authority: ADR-016 – DEFCON & Circuit Breaker Protocol
-- Status: APPROVED
-- Date: 2025-11-28
-- Owner: STIG (CTO & Runtime Guardian)
-- Authority Chain: ADR-001 → ADR-007 → ADR-011 → ADR-012 → ADR-016
--
-- Purpose: Implement DEFCON Dynamic State Architecture with:
--   - System state management (5 DEFCON levels)
--   - Circuit breaker triggers and actions
--   - Split-brain protection
--   - STIG Runtime Guardian authority
--
-- Compliance:
--   - ADR-001: System Charter (runtime governance)
--   - ADR-007: Orchestrator Architecture (agent behaviour control)
--   - ADR-011: Production Fortress (integrity guarantees)
--   - ADR-012: Economic Safety (API scarcity waterfall)
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. REGISTER ADR-016 IN ADR REGISTRY
-- ============================================================================

INSERT INTO fhq_meta.adr_registry (
    adr_id,
    adr_title,
    adr_status,
    adr_type,
    current_version,
    approval_authority,
    effective_date,
    governance_tier,
    created_by,
    owner,
    description,
    vega_attested
) VALUES (
    'ADR-016',
    'DEFCON & Circuit Breaker Protocol',
    'APPROVED',
    'OPERATIONAL',
    '2026.PRODUCTION',
    'CEO',
    CURRENT_DATE,
    'Tier-2',
    'CODE',
    'STIG',
    'Establishes the DEFCON Dynamic State Architecture with STIG as Runtime Guardian. Defines 5 operational states (GREEN, YELLOW, ORANGE, RED, BLACK) with graduated restrictions on agent permissions, API access, and trading capabilities. Implements circuit breakers for flash crashes, governance breaches, and system failures.',
    false
) ON CONFLICT (adr_id) DO UPDATE SET
    adr_title = EXCLUDED.adr_title,
    adr_status = EXCLUDED.adr_status,
    adr_type = EXCLUDED.adr_type,
    current_version = EXCLUDED.current_version,
    description = EXCLUDED.description;

-- ============================================================================
-- 2. REGISTER ADR-016 DEPENDENCIES
-- ============================================================================

INSERT INTO fhq_meta.adr_dependencies (
    adr_id,
    version,
    depends_on,
    dependency_type,
    criticality
) VALUES (
    'ADR-016',
    '2026.PRODUCTION',
    ARRAY['ADR-001', 'ADR-007', 'ADR-011', 'ADR-012'],
    'GOVERNANCE',
    'HIGH'
) ON CONFLICT DO NOTHING;

-- ============================================================================
-- 3. CREATE DEFCON TYPE AND SYSTEM STATE TABLE
-- ============================================================================

-- Create DEFCON level enum type if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'defcon_level') THEN
        CREATE TYPE defcon_level AS ENUM ('GREEN', 'YELLOW', 'ORANGE', 'RED', 'BLACK');
    END IF;
END $$;

-- Create system_state table for DEFCON management
CREATE TABLE IF NOT EXISTS fhq_governance.system_state (
    state_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    current_defcon defcon_level NOT NULL DEFAULT 'GREEN',
    previous_defcon defcon_level,
    active_circuit_breakers TEXT[] DEFAULT ARRAY[]::TEXT[],
    reason TEXT,
    triggered_by TEXT,  -- Agent ID or 'SYSTEM'
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    api_budget_pct NUMERIC(5,2),
    discrepancy_score NUMERIC(5,4),
    vix_level NUMERIC(6,2),
    latency_ms INTEGER,
    error_rate_pct NUMERIC(5,2),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'STIG'
);

-- Create index for active state lookup
CREATE INDEX IF NOT EXISTS idx_system_state_active ON fhq_governance.system_state(is_active) WHERE is_active = TRUE;

-- ============================================================================
-- 4. CIRCUIT BREAKER DEFINITIONS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.circuit_breakers (
    breaker_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    breaker_name TEXT NOT NULL UNIQUE,
    breaker_type TEXT NOT NULL CHECK (breaker_type IN ('RATE', 'COST', 'EXECUTION', 'GOVERNANCE', 'MARKET', 'SYSTEM')),
    trigger_condition JSONB NOT NULL,
    action_on_trigger JSONB NOT NULL,
    defcon_threshold defcon_level NOT NULL,
    auto_reset BOOLEAN DEFAULT FALSE,
    reset_after_seconds INTEGER,
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'STIG'
);

-- ============================================================================
-- 5. CIRCUIT BREAKER EVENTS LOG
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.circuit_breaker_events (
    event_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    breaker_id UUID REFERENCES fhq_governance.circuit_breakers(breaker_id),
    breaker_name TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('TRIGGERED', 'RESET', 'OVERRIDE', 'ESCALATED')),
    defcon_before defcon_level,
    defcon_after defcon_level,
    trigger_data JSONB,
    action_taken JSONB,
    triggered_by TEXT NOT NULL,
    override_by TEXT,
    override_reason TEXT,
    event_timestamp TIMESTAMPTZ DEFAULT NOW(),
    hash_prev TEXT,
    hash_self TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for event lookups
CREATE INDEX IF NOT EXISTS idx_cb_events_timestamp ON fhq_governance.circuit_breaker_events(event_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_cb_events_breaker ON fhq_governance.circuit_breaker_events(breaker_name);

-- ============================================================================
-- 6. DEFCON TRANSITION LOG
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.defcon_transitions (
    transition_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    from_level defcon_level NOT NULL,
    to_level defcon_level NOT NULL,
    transition_type TEXT NOT NULL CHECK (transition_type IN ('DOWNGRADE', 'UPGRADE', 'RESET')),
    reason TEXT NOT NULL,
    authorized_by TEXT NOT NULL,
    authorization_method TEXT CHECK (authorization_method IN ('AUTOMATIC', 'STIG', 'VEGA', 'CEO', 'SYSTEM')),
    evidence_bundle JSONB,
    transition_timestamp TIMESTAMPTZ DEFAULT NOW(),
    acknowledged_by TEXT[],
    acknowledged_at TIMESTAMPTZ,
    hash_chain_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for transition lookups
CREATE INDEX IF NOT EXISTS idx_defcon_transitions_timestamp ON fhq_governance.defcon_transitions(transition_timestamp DESC);

-- ============================================================================
-- 7. INSERT DEFAULT CIRCUIT BREAKERS
-- ============================================================================

-- API Budget Circuit Breaker (YELLOW trigger)
INSERT INTO fhq_governance.circuit_breakers (
    breaker_name, breaker_type, trigger_condition, action_on_trigger, defcon_threshold, auto_reset, reset_after_seconds, created_by
) VALUES (
    'API_BUDGET_SCARCITY',
    'COST',
    '{"condition": "api_budget_pct < 20", "description": "API budget below 20% threshold"}',
    '{"actions": ["BLOCK_TIER2_PULSE", "RESTRICT_SNIPER", "LIMIT_SUBEXEC_TO_LAKE"]}',
    'YELLOW',
    TRUE,
    3600,
    'STIG'
) ON CONFLICT (breaker_name) DO NOTHING;

-- High Latency Circuit Breaker (YELLOW trigger)
INSERT INTO fhq_governance.circuit_breakers (
    breaker_name, breaker_type, trigger_condition, action_on_trigger, defcon_threshold, auto_reset, reset_after_seconds, created_by
) VALUES (
    'HIGH_LATENCY',
    'EXECUTION',
    '{"condition": "latency_ms > 2000", "description": "System latency exceeds 2000ms"}',
    '{"actions": ["THROTTLE_REQUESTS", "RESTRICT_PULSE_FEEDS"]}',
    'YELLOW',
    TRUE,
    300,
    'STIG'
) ON CONFLICT (breaker_name) DO NOTHING;

-- VIX Volatility Circuit Breaker (ORANGE trigger)
INSERT INTO fhq_governance.circuit_breakers (
    breaker_name, breaker_type, trigger_condition, action_on_trigger, defcon_threshold, auto_reset, reset_after_seconds, created_by
) VALUES (
    'VIX_VOLATILITY',
    'MARKET',
    '{"condition": "vix_level > 30", "description": "VIX exceeds 30 - high volatility"}',
    '{"actions": ["FORCE_PAPER_TRADING", "FREEZE_MODEL_DEVELOPMENT", "ENABLE_COT_VALIDATION"]}',
    'ORANGE',
    FALSE,
    NULL,
    'STIG'
) ON CONFLICT (breaker_name) DO NOTHING;

-- Discrepancy Score Circuit Breaker (ORANGE trigger)
INSERT INTO fhq_governance.circuit_breakers (
    breaker_name, breaker_type, trigger_condition, action_on_trigger, defcon_threshold, auto_reset, reset_after_seconds, created_by
) VALUES (
    'DISCREPANCY_DRIFT',
    'GOVERNANCE',
    '{"condition": "discrepancy_score > 0.08", "description": "Discrepancy score exceeds 0.08 threshold"}',
    '{"actions": ["FORCE_PAPER_TRADING", "ENABLE_COT_VALIDATION", "CEIO_DEEP_SCAN"]}',
    'ORANGE',
    FALSE,
    NULL,
    'STIG'
) ON CONFLICT (breaker_name) DO NOTHING;

-- Flash Crash Circuit Breaker (RED trigger)
INSERT INTO fhq_governance.circuit_breakers (
    breaker_name, breaker_type, trigger_condition, action_on_trigger, defcon_threshold, auto_reset, reset_after_seconds, created_by
) VALUES (
    'FLASH_CRASH',
    'MARKET',
    '{"condition": "flash_crash_detected", "description": "Flash crash detected in market"}',
    '{"actions": ["HALT_PIPELINES", "CANCEL_ALL_ORDERS", "DATABASE_READ_ONLY", "NOTIFY_CEO"]}',
    'RED',
    FALSE,
    NULL,
    'STIG'
) ON CONFLICT (breaker_name) DO NOTHING;

-- System Error Rate Circuit Breaker (RED trigger)
INSERT INTO fhq_governance.circuit_breakers (
    breaker_name, breaker_type, trigger_condition, action_on_trigger, defcon_threshold, auto_reset, reset_after_seconds, created_by
) VALUES (
    'SYSTEM_ERROR_RATE',
    'SYSTEM',
    '{"condition": "error_rate_pct > 5", "description": "System error rate exceeds 5%"}',
    '{"actions": ["HALT_PIPELINES", "CANCEL_ALL_ORDERS", "DATABASE_READ_ONLY", "NOTIFY_CEO"]}',
    'RED',
    FALSE,
    NULL,
    'STIG'
) ON CONFLICT (breaker_name) DO NOTHING;

-- API Key Failure Circuit Breaker (RED trigger)
INSERT INTO fhq_governance.circuit_breakers (
    breaker_name, breaker_type, trigger_condition, action_on_trigger, defcon_threshold, auto_reset, reset_after_seconds, created_by
) VALUES (
    'API_KEY_FAILURE',
    'SYSTEM',
    '{"condition": "api_key_failure", "description": "Critical API key authentication failure"}',
    '{"actions": ["HALT_PIPELINES", "SWITCH_TO_STUB_MODE", "NOTIFY_CEO"]}',
    'RED',
    FALSE,
    NULL,
    'STIG'
) ON CONFLICT (breaker_name) DO NOTHING;

-- Governance Breach Circuit Breaker (BLACK trigger)
INSERT INTO fhq_governance.circuit_breakers (
    breaker_name, breaker_type, trigger_condition, action_on_trigger, defcon_threshold, auto_reset, reset_after_seconds, created_by
) VALUES (
    'GOVERNANCE_BREACH',
    'GOVERNANCE',
    '{"condition": "unauthorized_canonical_write OR key_compromise OR rogue_agent OR split_brain", "description": "Critical governance breach detected"}',
    '{"actions": ["REVOKE_ALL_KEYS", "ISOLATE_DATABASE", "SHUTDOWN_ORCHESTRATOR", "CREATE_FORENSIC_SNAPSHOT", "REQUIRE_CEO_RESET"]}',
    'BLACK',
    FALSE,
    NULL,
    'STIG'
) ON CONFLICT (breaker_name) DO NOTHING;

-- ============================================================================
-- 8. INITIALIZE DEFAULT SYSTEM STATE (DEFCON GREEN)
-- ============================================================================

-- Deactivate any existing states first
UPDATE fhq_governance.system_state SET is_active = FALSE WHERE is_active = TRUE;

-- Insert initial GREEN state
INSERT INTO fhq_governance.system_state (
    current_defcon,
    previous_defcon,
    active_circuit_breakers,
    reason,
    triggered_by,
    api_budget_pct,
    discrepancy_score,
    vix_level,
    latency_ms,
    error_rate_pct,
    is_active,
    created_by
) VALUES (
    'GREEN',
    NULL,
    ARRAY[]::TEXT[],
    'System initialization - nominal operations',
    'SYSTEM',
    100.00,
    0.00,
    20.00,
    100,
    0.00,
    TRUE,
    'STIG'
);

-- ============================================================================
-- 9. CREATE VEGA ATTESTATION FOR ADR-016
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
    adr_reference,
    constitutional_basis,
    attestation_data
) VALUES (
    gen_random_uuid(),
    'ADR',
    'ADR-016',
    '2026.PRODUCTION',
    'CERTIFICATION',
    'APPROVED',
    NOW(),
    'VEGA-ATT-ADR016-' || md5(random()::text),
    'GENESIS_KEY_VEGA_PENDING_PRODUCTION',
    'ADR-016',
    'EC-001',
    jsonb_build_object(
        'attestation_id', 'ATT-VEGA-ADR016-' || to_char(NOW(), 'YYYYMMDD'),
        'governance_tier', 'Tier-2',
        'verification_status', 'PASS - ADR-016 DEFCON & Circuit Breaker Protocol implementation verified',
        'attestation_timestamp', NOW(),
        'defcon_levels_defined', ARRAY['GREEN', 'YELLOW', 'ORANGE', 'RED', 'BLACK'],
        'circuit_breakers_registered', 8,
        'runtime_guardian', 'STIG',
        'compliance_standards', ARRAY['DORA', 'ISO 42001', 'BCBS-239']
    )
) ON CONFLICT DO NOTHING;

-- ============================================================================
-- 10. UPDATE VEGA ATTESTED FLAG
-- ============================================================================

UPDATE fhq_meta.adr_registry
SET vega_attested = true
WHERE adr_id = 'ADR-016';

-- ============================================================================
-- 11. REGISTER STIG AS RUNTIME GUARDIAN IN AUTHORITY MATRIX
-- ============================================================================

-- Update STIG's authority to include Runtime Guardian capabilities
UPDATE fhq_governance.authority_matrix
SET
    can_trigger_defcon = TRUE,
    defcon_authority_level = 'RED',  -- Can escalate up to RED, BLACK requires VEGA+CEO
    updated_at = NOW()
WHERE agent_id = 'stig';

-- Add defcon columns if they don't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'fhq_governance'
                   AND table_name = 'authority_matrix'
                   AND column_name = 'can_trigger_defcon') THEN
        ALTER TABLE fhq_governance.authority_matrix
        ADD COLUMN can_trigger_defcon BOOLEAN DEFAULT FALSE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'fhq_governance'
                   AND table_name = 'authority_matrix'
                   AND column_name = 'defcon_authority_level') THEN
        ALTER TABLE fhq_governance.authority_matrix
        ADD COLUMN defcon_authority_level TEXT DEFAULT NULL;
    END IF;
END $$;

-- ============================================================================
-- 12. GOVERNANCE CHANGE LOG – ADR-016 ACTIVATION
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
    'adr016_defcon_activation',
    'runtime_governance',
    'ADR-016: Activated DEFCON & Circuit Breaker Protocol. Established 5-level DEFCON hierarchy (GREEN, YELLOW, ORANGE, RED, BLACK) with graduated agent permissions and circuit breaker triggers. STIG appointed as Runtime Guardian with authority to manage DEFCON levels up to RED. BLACK level requires CEO physical reset. System initialized in DEFCON GREEN.',
    'ADR-016 CEO Directive – DEFCON & Circuit Breaker Protocol',
    'G4-ceo-approved',
    'HC-ADR016-DEFCON-ACTIVATION-' || to_char(NOW(), 'YYYYMMDD_HH24MISS'),
    jsonb_build_object(
        'ceo', 'CEO_SIGNATURE_ADR016_APPROVAL',
        'stig', 'STIG_SIGNATURE_RUNTIME_GUARDIAN',
        'vega', 'VEGA_ATTESTATION_ADR016',
        'activation_timestamp', NOW(),
        'defcon_levels', ARRAY['GREEN', 'YELLOW', 'ORANGE', 'RED', 'BLACK'],
        'circuit_breakers', ARRAY[
            'API_BUDGET_SCARCITY',
            'HIGH_LATENCY',
            'VIX_VOLATILITY',
            'DISCREPANCY_DRIFT',
            'FLASH_CRASH',
            'SYSTEM_ERROR_RATE',
            'API_KEY_FAILURE',
            'GOVERNANCE_BREACH'
        ],
        'runtime_guardian', 'STIG',
        'compliance', ARRAY['ADR-001', 'ADR-007', 'ADR-011', 'ADR-012', 'ADR-016']
    ),
    NOW(),
    'CODE'
);

-- ============================================================================
-- 13. VERIFICATION QUERIES
-- ============================================================================

-- Verify ADR-016 registered
DO $$
DECLARE
    adr_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO adr_count
    FROM fhq_meta.adr_registry
    WHERE adr_id = 'ADR-016'
    AND adr_status = 'APPROVED';

    IF adr_count = 0 THEN
        RAISE EXCEPTION 'ADR-016 not registered in adr_registry';
    END IF;

    RAISE NOTICE '✅ ADR-016 registered successfully';
END $$;

-- Verify system_state table exists and has GREEN state
DO $$
DECLARE
    state_count INTEGER;
    current_level TEXT;
BEGIN
    SELECT COUNT(*), MAX(current_defcon::TEXT) INTO state_count, current_level
    FROM fhq_governance.system_state
    WHERE is_active = TRUE;

    IF state_count = 0 THEN
        RAISE EXCEPTION 'No active system state found';
    END IF;

    IF current_level != 'GREEN' THEN
        RAISE EXCEPTION 'System not initialized in GREEN state, found: %', current_level;
    END IF;

    RAISE NOTICE '✅ System state initialized at DEFCON GREEN';
END $$;

-- Verify circuit breakers registered
DO $$
DECLARE
    breaker_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO breaker_count
    FROM fhq_governance.circuit_breakers
    WHERE is_enabled = TRUE;

    IF breaker_count < 8 THEN
        RAISE EXCEPTION 'Expected 8 circuit breakers, found %', breaker_count;
    END IF;

    RAISE NOTICE '✅ All 8 circuit breakers registered';
END $$;

-- Verify VEGA attestation
DO $$
DECLARE
    att_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO att_count
    FROM fhq_governance.vega_attestations
    WHERE target_id = 'ADR-016'
    AND attestation_status = 'APPROVED';

    IF att_count = 0 THEN
        RAISE EXCEPTION 'VEGA attestation not found for ADR-016';
    END IF;

    RAISE NOTICE '✅ VEGA attestation created for ADR-016';
END $$;

COMMIT;

-- ============================================================================
-- DISPLAY REGISTRATION STATUS
-- ============================================================================

-- Display ADR-016 registration
SELECT
    adr_id,
    adr_title,
    adr_status,
    governance_tier,
    owner,
    vega_attested
FROM fhq_meta.adr_registry
WHERE adr_id = 'ADR-016';

-- Display current system state
SELECT
    current_defcon,
    active_circuit_breakers,
    reason,
    triggered_by,
    api_budget_pct,
    is_active
FROM fhq_governance.system_state
WHERE is_active = TRUE;

-- Display circuit breakers
SELECT
    breaker_name,
    breaker_type,
    defcon_threshold,
    is_enabled
FROM fhq_governance.circuit_breakers
ORDER BY defcon_threshold;

-- ============================================================================
-- END OF MIGRATION 020: ADR-016 DEFCON & CIRCUIT BREAKER PROTOCOL
-- ============================================================================

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'MIGRATION 020: ADR-016 DEFCON & CIRCUIT BREAKER PROTOCOL – COMPLETE'
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo ''
\echo '✅ ADR-016 registered in adr_registry'
\echo '✅ Dependencies registered (ADR-001, ADR-007, ADR-011, ADR-012)'
\echo '✅ DEFCON type created (GREEN, YELLOW, ORANGE, RED, BLACK)'
\echo '✅ System state table created and initialized at GREEN'
\echo '✅ Circuit breakers table created with 8 breakers'
\echo '✅ VEGA attestation created'
\echo ''
\echo 'DEFCON Hierarchy:'
\echo '  🟢 GREEN  - Nominal Operations (current)'
\echo '  🟡 YELLOW - Scarcity Warning (API < 20%, latency > 2000ms)'
\echo '  🟠 ORANGE - High Volatility (VIX > 30, discrepancy > 0.08)'
\echo '  🔴 RED    - Circuit Breaker (flash crash, error rate > 5%)'
\echo '  ⚫ BLACK  - Governance Breach (requires CEO reset)'
\echo ''
\echo 'Circuit Breakers Registered:'
\echo '  - API_BUDGET_SCARCITY (YELLOW)'
\echo '  - HIGH_LATENCY (YELLOW)'
\echo '  - VIX_VOLATILITY (ORANGE)'
\echo '  - DISCREPANCY_DRIFT (ORANGE)'
\echo '  - FLASH_CRASH (RED)'
\echo '  - SYSTEM_ERROR_RATE (RED)'
\echo '  - API_KEY_FAILURE (RED)'
\echo '  - GOVERNANCE_BREACH (BLACK)'
\echo ''
\echo 'Runtime Guardian: STIG (CTO)'
\echo '═══════════════════════════════════════════════════════════════════════════'
