-- ============================================================================
-- Migration 351: Options DEFCON Kill-Switch Tables
-- ============================================================================
-- Directive:  CEO-DIR-2026-OPS-AUTONOMY-001
-- Gate:       G1 (Technical Validation)
-- Author:     STIG (EC-003)
-- Date:       2026-02-01
-- Spec:       IoS-012-C (Options Execution Architecture)
-- Depends:    Migration 350 (options_trading_infrastructure)
-- ============================================================================
-- Creates kill-switch event log and latency breach tracking tables.
-- Supports ADR-016 DEFCON integration, ADR-013 hash-chain, ADR-019 break-glass.
-- ============================================================================

BEGIN;

-- ============================================================================
-- A. fhq_monitoring: Options Kill-Switch Events
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhq_monitoring.options_killswitch_events (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trigger_type    VARCHAR(40) NOT NULL CHECK (trigger_type IN (
                        'LATENCY_BREACH', 'RUNAWAY_ORDERS', 'MARGIN_BREACH',
                        'GREEKS_BREACH', 'DEFCON_TRANSITION', 'REGIME_CHANGE',
                        'MANUAL_HALT', 'OPTIONS_FLATTEN', 'STALE_IV'
                    )),
    trigger_value   NUMERIC(14,4),
    threshold       NUMERIC(14,4),
    defcon_level    VARCHAR(20) NOT NULL,
    action_taken    VARCHAR(40) NOT NULL CHECK (action_taken IN (
                        'HALT_NEW_ORDERS', 'HALT_ALL_OPTIONS', 'FLATTEN_ALL_OPTIONS',
                        'TIGHTEN_GREEKS_LIMITS', 'SYSTEM_ISOLATED', 'ALERT_ONLY'
                    )),
    affected_orders JSONB,                  -- [order_id, ...]
    details         JSONB,                  -- free-form context
    content_hash    VARCHAR(64) NOT NULL,
    chain_hash      VARCHAR(64) NOT NULL,
    previous_hash   VARCHAR(64),            -- NULL for first event in chain
    triggered_by    VARCHAR(30) NOT NULL DEFAULT 'RISL_OPTIONS_KILLSWITCH',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_oke_trigger ON fhq_monitoring.options_killswitch_events (trigger_type);
CREATE INDEX IF NOT EXISTS idx_oke_created ON fhq_monitoring.options_killswitch_events (created_at);
CREATE INDEX IF NOT EXISTS idx_oke_chain   ON fhq_monitoring.options_killswitch_events (chain_hash);

COMMENT ON TABLE fhq_monitoring.options_killswitch_events IS
    'IoS-012-C / ADR-016: Immutable hash-chained kill-switch event log. Court-proof audit trail.';

-- ============================================================================
-- B. fhq_monitoring: Options Latency Breaches
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhq_monitoring.options_latency_breaches (
    breach_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id        UUID REFERENCES fhq_execution.options_shadow_orders(order_id),
    roundtrip_ms    INTEGER NOT NULL,
    threshold_ms    INTEGER NOT NULL DEFAULT 500,
    action          VARCHAR(40) NOT NULL DEFAULT 'HALT_NEW_ORDERS',
    resolved        BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_olb_unresolved
    ON fhq_monitoring.options_latency_breaches (resolved) WHERE resolved = FALSE;

COMMENT ON TABLE fhq_monitoring.options_latency_breaches IS
    'IoS-012-C / MiFID II Art.17: Latency breach records. >500ms roundtrip = automatic halt.';

-- ============================================================================
-- Migration metadata
-- ============================================================================
INSERT INTO fhq_monitoring.run_ledger (
    task_name, started_at, finished_at, exit_code, error_excerpt
) VALUES (
    'MIGRATION_351_OPTIONS_DEFCON_KILLSWITCH',
    NOW(), NOW(), 0,
    'IoS-012-C: 2 tables (killswitch_events + latency_breaches). ADR-016/ADR-019 integration. G1.'
);

COMMIT;
