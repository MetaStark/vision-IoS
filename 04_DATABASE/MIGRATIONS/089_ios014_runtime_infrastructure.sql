-- ============================================================================
-- Migration 089: IoS-014 Runtime Infrastructure
-- Authority: CEO DIRECTIVE — IoS-014 BUILD & AUTONOMOUS AGENT ACTIVATION
--
-- Creates defcon_state, execution_mode, daemon_health, and orchestrator_cycles
-- tables required for IoS-014 autonomous operation
-- ============================================================================

-- =============================================================================
-- Table: fhq_governance.defcon_state
-- Purpose: Track current and historical DEFCON levels per ADR-016
-- =============================================================================
CREATE TABLE IF NOT EXISTS fhq_governance.defcon_state (
    state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    defcon_level TEXT NOT NULL,
    CONSTRAINT valid_defcon_level CHECK (defcon_level IN ('GREEN', 'YELLOW', 'ORANGE', 'RED', 'BLACK')),

    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    triggered_by TEXT NOT NULL,
    trigger_reason TEXT,

    -- Auto-expire (for automatic recovery)
    auto_expire_at TIMESTAMPTZ,

    -- Current state flag
    is_current BOOLEAN NOT NULL DEFAULT FALSE,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ensure only one current state
CREATE UNIQUE INDEX IF NOT EXISTS idx_defcon_current ON fhq_governance.defcon_state (is_current) WHERE is_current = TRUE;

-- =============================================================================
-- Table: fhq_governance.execution_mode
-- Purpose: Track current execution mode (LOCAL_DEV, PAPER_PROD, LIVE_PROD)
-- =============================================================================
CREATE TABLE IF NOT EXISTS fhq_governance.execution_mode (
    mode_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mode_name TEXT NOT NULL,
    CONSTRAINT valid_mode_name CHECK (mode_name IN ('LOCAL_DEV', 'PAPER_PROD', 'LIVE_PROD')),

    set_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    set_by TEXT NOT NULL,
    reason TEXT,

    -- Current mode flag
    is_current BOOLEAN NOT NULL DEFAULT FALSE,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ensure only one current mode
CREATE UNIQUE INDEX IF NOT EXISTS idx_mode_current ON fhq_governance.execution_mode (is_current) WHERE is_current = TRUE;

-- =============================================================================
-- Table: fhq_monitoring.daemon_health
-- Purpose: Track health status of running daemons
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS fhq_monitoring;

CREATE TABLE IF NOT EXISTS fhq_monitoring.daemon_health (
    daemon_name TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    CONSTRAINT valid_daemon_status CHECK (status IN ('HEALTHY', 'DEGRADED', 'UNHEALTHY', 'STOPPED')),

    last_heartbeat TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- Table: fhq_governance.orchestrator_cycles
-- Purpose: Detailed log of orchestrator execution cycles
-- =============================================================================
CREATE TABLE IF NOT EXISTS fhq_governance.orchestrator_cycles (
    cycle_id TEXT PRIMARY KEY,
    cycle_type TEXT NOT NULL DEFAULT 'STANDARD',
    CONSTRAINT valid_cycle_type CHECK (cycle_type IN ('NIGHTLY', 'HOURLY', 'REALTIME', 'EVENT', 'STANDARD')),

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,

    execution_mode TEXT,
    defcon_level TEXT,

    tasks_scheduled INTEGER NOT NULL DEFAULT 0,
    tasks_completed INTEGER NOT NULL DEFAULT 0,
    tasks_failed INTEGER NOT NULL DEFAULT 0,
    tasks_skipped INTEGER NOT NULL DEFAULT 0,

    vendor_snapshot JSONB,
    evidence_hash TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cycles_started ON fhq_governance.orchestrator_cycles(started_at);
CREATE INDEX IF NOT EXISTS idx_cycles_mode ON fhq_governance.orchestrator_cycles(execution_mode);
CREATE INDEX IF NOT EXISTS idx_cycles_defcon ON fhq_governance.orchestrator_cycles(defcon_level);

-- =============================================================================
-- Seed data: Initialize system state
-- =============================================================================

-- Set initial DEFCON to GREEN
INSERT INTO fhq_governance.defcon_state (defcon_level, triggered_by, trigger_reason, is_current)
VALUES ('GREEN', 'STIG', 'System initialization - default GREEN state', TRUE)
ON CONFLICT DO NOTHING;

-- Set initial execution mode to PAPER_PROD per CEO directive
INSERT INTO fhq_governance.execution_mode (mode_name, set_by, reason, is_current)
VALUES ('PAPER_PROD', 'CEO_DIRECTIVE', 'IoS-014 initial activation per CEO DIRECTIVE IoS-014', TRUE)
ON CONFLICT DO NOTHING;

-- Register orchestrator daemon
INSERT INTO fhq_monitoring.daemon_health (daemon_name, status, metadata)
VALUES ('ios014_orchestrator', 'STOPPED', '{"initialized": true}'::jsonb)
ON CONFLICT (daemon_name) DO NOTHING;

-- =============================================================================
-- Log migration
-- =============================================================================
INSERT INTO fhq_governance.governance_actions_log (
    action_type, action_target, action_target_type, initiated_by,
    decision, decision_rationale, hash_chain_id
) VALUES (
    'MIGRATION',
    'ios014_runtime_infrastructure',
    'DATABASE_SCHEMA',
    'STIG',
    'COMPLETED',
    'Created defcon_state, execution_mode, daemon_health, orchestrator_cycles tables per CEO DIRECTIVE IoS-014',
    'HC-MIGRATION-089-2025-12-07'
);

COMMENT ON TABLE fhq_governance.defcon_state IS 'DEFCON level tracking per ADR-016. IoS-014 reads current state for task scheduling.';
COMMENT ON TABLE fhq_governance.execution_mode IS 'Execution mode tracking (LOCAL_DEV, PAPER_PROD, LIVE_PROD). CEO mandate: PAPER_PROD until G3 validation.';
COMMENT ON TABLE fhq_monitoring.daemon_health IS 'Daemon health monitoring with heartbeat tracking.';
COMMENT ON TABLE fhq_governance.orchestrator_cycles IS 'Detailed orchestrator cycle audit log for VEGA compliance.';
