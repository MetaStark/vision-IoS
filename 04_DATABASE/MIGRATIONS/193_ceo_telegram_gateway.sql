-- ============================================================================
-- MIGRATION 193: CEO-DIR-2026-01-03 CEO Telegram Gateway (Glass Window)
-- ============================================================================
--
-- CEO DIRECTIVE: COGNITIVE DIGITAL INTUITION PLATFORM & CEO GLASS WINDOW
--
-- This migration creates the infrastructure for a READ-ONLY CEO interface
-- on Telegram that allows observation of system state with full governance.
--
-- Non-Negotiables:
--   - Read-Only Observability (ADR-019 compliance)
--   - Canonical Data Sources Only
--   - Auditable Memory with court-proof evidence
--   - Rate limiting per ADR-012
--
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. CEO AUTHENTICATION WHITELIST
-- ============================================================================
-- Only whitelisted Telegram chat IDs can access the CEO Glass Window.
-- This is the primary authentication mechanism.

CREATE TABLE IF NOT EXISTS fhq_governance.ceo_access_whitelist (
    whitelist_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_chat_id TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'CEO',
    access_level TEXT NOT NULL DEFAULT 'FULL_READ',

    -- Rate limiting configuration per user
    rate_limit_per_minute INT NOT NULL DEFAULT 10,
    rate_limit_per_hour INT NOT NULL DEFAULT 100,

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'STIG',
    updated_at TIMESTAMPTZ,
    updated_by TEXT,

    -- ADR-008 Ed25519 signature (optional, for enhanced security)
    ed25519_signature TEXT,

    CONSTRAINT valid_role CHECK (role IN ('CEO', 'CTO', 'AUDITOR')),
    CONSTRAINT valid_access_level CHECK (access_level IN ('FULL_READ', 'LIMITED_READ', 'AUDIT_ONLY'))
);

-- Index for fast lookup
CREATE INDEX IF NOT EXISTS idx_ceo_whitelist_chat_id
    ON fhq_governance.ceo_access_whitelist(telegram_chat_id)
    WHERE is_active = TRUE;

COMMENT ON TABLE fhq_governance.ceo_access_whitelist IS
'CEO-DIR-2026-01-03: Telegram chat ID whitelist for CEO Glass Window access';

-- ============================================================================
-- 2. CEO ACCESS LOG (Court-Proof Audit Trail)
-- ============================================================================
-- Every CEO interaction is logged with cryptographic evidence.
-- Links to vision_verification.summary_evidence_ledger for court-proof.

CREATE TABLE IF NOT EXISTS fhq_governance.ceo_access_log (
    access_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Request identification
    chat_id TEXT NOT NULL,
    command TEXT NOT NULL,
    command_args JSONB,

    -- Query evidence (court-proof per CEO Directive 2025-12-20)
    query_executed TEXT,              -- Raw SQL for court-proof
    query_result_hash TEXT,           -- SHA-256 of query result
    response_sent TEXT,               -- Actual response text
    response_hash TEXT,               -- SHA-256 of response

    -- Evidence chain linkage
    evidence_id UUID,                 -- FK to summary_evidence_ledger

    -- Timing
    access_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    response_timestamp TIMESTAMPTZ,
    latency_ms INT,

    -- Rate limiting state at time of request
    rate_limit_remaining_minute INT,
    rate_limit_remaining_hour INT,

    -- Authentication result
    auth_status TEXT NOT NULL,        -- AUTHENTICATED, REJECTED, RATE_LIMITED
    auth_rejection_reason TEXT,

    -- Optional metadata
    telegram_message_id TEXT,
    ip_address TEXT,
    user_agent TEXT,

    CONSTRAINT valid_auth_status CHECK (
        auth_status IN ('AUTHENTICATED', 'REJECTED', 'RATE_LIMITED')
    )
);

-- Indexes for audit queries
CREATE INDEX IF NOT EXISTS idx_ceo_access_log_chat_id
    ON fhq_governance.ceo_access_log(chat_id);
CREATE INDEX IF NOT EXISTS idx_ceo_access_log_timestamp
    ON fhq_governance.ceo_access_log(access_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ceo_access_log_auth_status
    ON fhq_governance.ceo_access_log(auth_status);
CREATE INDEX IF NOT EXISTS idx_ceo_access_log_command
    ON fhq_governance.ceo_access_log(command);

COMMENT ON TABLE fhq_governance.ceo_access_log IS
'CEO-DIR-2026-01-03: Court-proof audit trail of all CEO Glass Window interactions';

-- ============================================================================
-- 3. COMMAND REGISTRY (Approved Read-Only Commands)
-- ============================================================================
-- Only commands in this registry can be executed.
-- Each command maps to a specific canonical view (read-only).

CREATE TABLE IF NOT EXISTS fhq_governance.ceo_command_registry (
    command_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    command_name TEXT NOT NULL UNIQUE,      -- e.g., '/status', '/agents'
    command_description TEXT,

    -- Data source (MUST be a read-only view)
    view_source TEXT NOT NULL,              -- Canonical view to query

    -- Configuration
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    requires_args BOOLEAN NOT NULL DEFAULT FALSE,
    arg_schema JSONB,                       -- JSON schema for validation

    -- Rate limit override (NULL = use user default)
    rate_limit_override INT,

    -- Command-specific timeout (seconds)
    query_timeout_seconds INT NOT NULL DEFAULT 10,

    -- Governance
    approved_by TEXT NOT NULL DEFAULT 'CEO',
    approved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE fhq_governance.ceo_command_registry IS
'CEO-DIR-2026-01-03: Registry of approved read-only commands for CEO Glass Window';

-- ============================================================================
-- 4. RATE LIMIT STATE
-- ============================================================================
-- Tracks per-user rate limiting with sliding window.

CREATE TABLE IF NOT EXISTS fhq_governance.ceo_rate_limit_state (
    chat_id TEXT PRIMARY KEY,

    -- Per-minute window
    requests_this_minute INT NOT NULL DEFAULT 0,
    minute_window_start TIMESTAMPTZ,

    -- Per-hour window
    requests_this_hour INT NOT NULL DEFAULT 0,
    hour_window_start TIMESTAMPTZ,

    -- Last request tracking
    last_request_at TIMESTAMPTZ,

    -- Statistics
    total_requests_lifetime BIGINT NOT NULL DEFAULT 0,
    total_rejections_lifetime BIGINT NOT NULL DEFAULT 0
);

COMMENT ON TABLE fhq_governance.ceo_rate_limit_state IS
'CEO-DIR-2026-01-03: Rate limiting state for CEO Glass Window';

-- ============================================================================
-- 5. SEED DATA: CEO WHITELIST ENTRY
-- ============================================================================
-- Add the CEO's Telegram chat ID to the whitelist.

INSERT INTO fhq_governance.ceo_access_whitelist
    (telegram_chat_id, display_name, role, access_level, created_by)
VALUES
    ('6194473125', 'CEO Orjan', 'CEO', 'FULL_READ', 'STIG')
ON CONFLICT (telegram_chat_id) DO NOTHING;

-- ============================================================================
-- 6. SEED DATA: APPROVED COMMANDS
-- ============================================================================
-- Register all approved read-only commands with their canonical view sources.

INSERT INTO fhq_governance.ceo_command_registry
    (command_name, command_description, view_source, requires_args)
VALUES
    -- System status commands
    ('/status', 'System DEFCON status, regime, agent health summary',
     'fhq_governance.mv_system_health_summary', FALSE),

    -- Agent commands
    ('/agents', 'All agent metrics overview (ARS, CSI, GII, DDS)',
     'fhq_governance.mv_aol_agent_metrics', FALSE),

    ('/agent', 'Single agent detailed metrics',
     'fhq_governance.mv_aol_agent_metrics', TRUE),

    -- Market regime
    ('/regime', 'Current BTC regime classification and confidence',
     'fhq_canonical.btc_regimes', FALSE),

    -- Golden needles
    ('/needles', 'Recent golden needles queue',
     'fhq_canonical.golden_needles', FALSE),

    -- LLM balance
    ('/balance', 'LLM provider balance (DeepSeek)',
     'fhq_governance.llm_provider_balance', FALSE),

    -- ACI Triangle
    ('/aci', 'ACI triangle shadow metrics (SitC, InForage, IKEA)',
     'fhq_canonical.aci_shadow_evaluations', FALSE),

    -- Governance ledger
    ('/ledger', 'Recent governance actions log',
     'fhq_governance.governance_actions_log', FALSE),

    -- Help command (no view source)
    ('/help', 'List available commands',
     'NONE', FALSE)
ON CONFLICT (command_name) DO UPDATE SET
    command_description = EXCLUDED.command_description,
    view_source = EXCLUDED.view_source;

-- ============================================================================
-- 7. VIEWS FOR CEO QUERIES
-- ============================================================================
-- Note: Complex views will be created by Python code that can query
-- schema dynamically. This avoids migration failures due to schema drift.

-- Simple placeholder view for system health (will be replaced by Python queries)
CREATE OR REPLACE VIEW fhq_governance.mv_system_health_summary AS
SELECT
    COALESCE(
        (SELECT current_level FROM fhq_monitoring.defcon_status ORDER BY activated_at DESC LIMIT 1),
        'GREEN'
    ) AS defcon_level,
    COALESCE(
        (SELECT regime_label FROM fhq_finn.v_btc_regime_current LIMIT 1),
        'UNKNOWN'
    ) AS current_regime,
    COALESCE(
        (SELECT regime_confidence FROM fhq_finn.v_btc_regime_current LIMIT 1),
        0.0
    )::NUMERIC(5,2) AS regime_confidence,
    0 AS total_agents,  -- Will be computed dynamically
    0 AS active_needles, -- Will be computed dynamically
    NOW() AS snapshot_timestamp;

-- ============================================================================
-- 8. GOVERNANCE ACTION LOGGING
-- ============================================================================
-- Log this migration as a governance action.

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    decision,
    decision_rationale,
    initiated_by,
    vega_reviewed
) VALUES (
    'MIGRATION',
    'CEO_TELEGRAM_GATEWAY',
    'APPROVED',
    'CEO-DIR-2026-01-03: Cognitive Digital Intuition Platform & CEO Glass Window',
    'STIG',
    FALSE
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    -- Verify tables created
    IF EXISTS(SELECT 1 FROM information_schema.tables
              WHERE table_schema = 'fhq_governance'
              AND table_name = 'ceo_access_whitelist') THEN
        RAISE NOTICE 'CEO-DIR-2026-01-03 Migration 193: ceo_access_whitelist CREATED';
    END IF;

    IF EXISTS(SELECT 1 FROM information_schema.tables
              WHERE table_schema = 'fhq_governance'
              AND table_name = 'ceo_access_log') THEN
        RAISE NOTICE 'CEO-DIR-2026-01-03 Migration 193: ceo_access_log CREATED';
    END IF;

    IF EXISTS(SELECT 1 FROM information_schema.tables
              WHERE table_schema = 'fhq_governance'
              AND table_name = 'ceo_command_registry') THEN
        RAISE NOTICE 'CEO-DIR-2026-01-03 Migration 193: ceo_command_registry CREATED';
    END IF;

    IF EXISTS(SELECT 1 FROM information_schema.tables
              WHERE table_schema = 'fhq_governance'
              AND table_name = 'ceo_rate_limit_state') THEN
        RAISE NOTICE 'CEO-DIR-2026-01-03 Migration 193: ceo_rate_limit_state CREATED';
    END IF;

    -- Verify seed data
    IF EXISTS(SELECT 1 FROM fhq_governance.ceo_access_whitelist
              WHERE telegram_chat_id = '6194473125') THEN
        RAISE NOTICE 'CEO-DIR-2026-01-03 Migration 193: CEO whitelist entry SEEDED';
    END IF;

    IF (SELECT COUNT(*) FROM fhq_governance.ceo_command_registry) >= 9 THEN
        RAISE NOTICE 'CEO-DIR-2026-01-03 Migration 193: % commands REGISTERED',
                     (SELECT COUNT(*) FROM fhq_governance.ceo_command_registry);
    END IF;

    RAISE NOTICE '============================================================';
    RAISE NOTICE 'CEO-DIR-2026-01-03 Migration 193 COMPLETE';
    RAISE NOTICE '============================================================';
END $$;
