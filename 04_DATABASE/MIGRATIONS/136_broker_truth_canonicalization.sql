-- ============================================================================
-- MIGRATION 136: Broker-Truth Canonicalization
-- ============================================================================
-- Directive: CD-EXEC-ALPACA-SOT-001 (Alpaca-Only Paper Execution)
-- Authority: CEO
-- Owners: STIG (architecture), LINE (execution), VEGA (attestation)
--
-- PURPOSE:
-- Eliminates split-brain between "internal simulated NAV" and "broker reality."
-- Alpaca Paper is now the sole execution venue and sole source of truth.
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: QUARANTINE SYNTHETIC LEDGER
-- ============================================================================

-- Add deprecation markers to synthetic_lab_nav
ALTER TABLE fhq_positions.synthetic_lab_nav
ADD COLUMN IF NOT EXISTS is_synthetic BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS deprecated_at TIMESTAMPTZ DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS deprecation_reason TEXT DEFAULT 'CD-EXEC-ALPACA-SOT-001: Replaced by broker-truth NAV';

-- Mark table as deprecated
COMMENT ON TABLE fhq_positions.synthetic_lab_nav IS
'DEPRECATED [CD-EXEC-ALPACA-SOT-001 2025-12-13]: Synthetic NAV ledger - DO NOT USE FOR REPORTING.
Use fhq_execution.broker_state_snapshots as sole source of truth for portfolio value.
Retained for audit trail only. Any code reading from this table is non-compliant.';

-- ============================================================================
-- STEP 2: CREATE BROKER-TRUTH VIEWS
-- ============================================================================

-- Canonical view for broker NAV (single source of truth)
CREATE OR REPLACE VIEW fhq_execution.v_broker_truth_nav AS
SELECT
    snapshot_id,
    broker,
    broker_environment,
    account_id,
    account_status,
    CAST(portfolio_value AS NUMERIC(20,2)) as nav,
    CAST(cash AS NUMERIC(20,2)) as cash_balance,
    CAST(buying_power AS NUMERIC(20,2)) as buying_power,
    positions,
    COALESCE(JSONB_ARRAY_LENGTH(positions), 0) as position_count,
    divergence_detected,
    divergence_details,
    captured_at as snapshot_at,
    created_by,
    -- Staleness detection (>5 min = stale)
    (NOW() - captured_at > INTERVAL '5 minutes') as is_stale,
    EXTRACT(EPOCH FROM (NOW() - captured_at)) as seconds_since_snapshot
FROM fhq_execution.broker_state_snapshots
WHERE broker = 'ALPACA' AND broker_environment = 'PAPER'
ORDER BY captured_at DESC;

COMMENT ON VIEW fhq_execution.v_broker_truth_nav IS
'CANONICAL [CD-EXEC-ALPACA-SOT-001]: Broker-truth NAV view.
This is the ONLY authorized source for portfolio value, positions, and cash.
All execution and reporting systems MUST use this view.';

-- ============================================================================
-- STEP 3: BROKER NAV FUNCTION (for programmatic access)
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_execution.get_broker_nav()
RETURNS TABLE(
    nav NUMERIC(20,2),
    cash_balance NUMERIC(20,2),
    positions_value NUMERIC(20,2),
    position_count INTEGER,
    snapshot_at TIMESTAMPTZ,
    is_stale BOOLEAN,
    seconds_since_snapshot NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        CAST(bs.portfolio_value AS NUMERIC(20,2)) as nav,
        CAST(bs.cash AS NUMERIC(20,2)) as cash_balance,
        CAST(bs.portfolio_value - bs.cash AS NUMERIC(20,2)) as positions_value,
        COALESCE(JSONB_ARRAY_LENGTH(bs.positions), 0)::INTEGER as position_count,
        bs.captured_at as snapshot_at,
        (NOW() - bs.captured_at > INTERVAL '5 minutes') as is_stale,
        EXTRACT(EPOCH FROM (NOW() - bs.captured_at))::NUMERIC as seconds_since_snapshot
    FROM fhq_execution.broker_state_snapshots bs
    WHERE bs.broker = 'ALPACA' AND bs.broker_environment = 'PAPER'
    ORDER BY bs.captured_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_execution.get_broker_nav() IS
'CANONICAL [CD-EXEC-ALPACA-SOT-001]: Returns current broker NAV from Alpaca Paper.
Use this function in all execution systems. Returns is_stale=TRUE if snapshot >5 min old.';

-- ============================================================================
-- STEP 4: EXECUTION ROUTING GUARDRAIL
-- ============================================================================

-- Create table to track execution routing decisions
CREATE TABLE IF NOT EXISTS fhq_execution.execution_routing_log (
    routing_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_source TEXT NOT NULL,
    requested_broker TEXT NOT NULL,
    routing_decision TEXT NOT NULL, -- 'ALLOWED', 'REJECTED', 'REDIRECTED'
    rejection_reason TEXT,
    directive_reference TEXT DEFAULT 'CD-EXEC-ALPACA-SOT-001',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE fhq_execution.execution_routing_log IS
'[CD-EXEC-ALPACA-SOT-001]: Logs all execution routing decisions.
Any non-Alpaca request must be rejected and logged here.';

-- Function to validate execution routing (guardrail)
CREATE OR REPLACE FUNCTION fhq_execution.validate_execution_route(
    p_broker TEXT,
    p_environment TEXT,
    p_source TEXT
) RETURNS TABLE(
    allowed BOOLEAN,
    rejection_reason TEXT,
    redirect_to TEXT
) AS $$
DECLARE
    v_rejection TEXT;
BEGIN
    -- Only ALPACA PAPER is allowed
    IF p_broker = 'ALPACA' AND p_environment = 'PAPER' THEN
        -- Log allowed
        INSERT INTO fhq_execution.execution_routing_log
            (request_source, requested_broker, routing_decision)
        VALUES (p_source, p_broker || ':' || p_environment, 'ALLOWED');

        RETURN QUERY SELECT TRUE, NULL::TEXT, NULL::TEXT;
    ELSE
        -- REJECT non-Alpaca routes
        v_rejection := 'CD-EXEC-ALPACA-SOT-001: Only ALPACA:PAPER execution is authorized. ' ||
                       'Requested: ' || COALESCE(p_broker, 'NULL') || ':' || COALESCE(p_environment, 'NULL');

        -- Log rejection
        INSERT INTO fhq_execution.execution_routing_log
            (request_source, requested_broker, routing_decision, rejection_reason)
        VALUES (p_source, COALESCE(p_broker, 'NULL') || ':' || COALESCE(p_environment, 'NULL'),
                'REJECTED', v_rejection);

        RETURN QUERY SELECT FALSE, v_rejection, 'ALPACA:PAPER'::TEXT;
    END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_execution.validate_execution_route IS
'[CD-EXEC-ALPACA-SOT-001]: Execution routing guardrail.
REJECTS any non-Alpaca-Paper execution request. All routes logged for audit.';

-- ============================================================================
-- STEP 5: BROKER RECONCILIATION TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_execution.broker_reconciliation_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reconciliation_type TEXT NOT NULL, -- 'CONTINUOUS', 'MANUAL', 'STARTUP'
    broker_nav NUMERIC(20,2),
    broker_cash NUMERIC(20,2),
    broker_positions JSONB,
    internal_nav NUMERIC(20,2),
    internal_cash NUMERIC(20,2),
    internal_positions JSONB,
    nav_divergence NUMERIC(20,4),
    cash_divergence NUMERIC(20,4),
    position_divergence JSONB,
    is_reconciled BOOLEAN NOT NULL,
    divergence_severity TEXT, -- 'NONE', 'MINOR', 'MAJOR', 'CRITICAL'
    governance_event_triggered BOOLEAN DEFAULT FALSE,
    governance_event_id UUID,
    reconciled_at TIMESTAMPTZ DEFAULT NOW(),
    reconciled_by TEXT DEFAULT 'STIG',
    hash_chain_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_broker_recon_time ON fhq_execution.broker_reconciliation_events(reconciled_at DESC);
CREATE INDEX IF NOT EXISTS idx_broker_recon_severity ON fhq_execution.broker_reconciliation_events(divergence_severity);

COMMENT ON TABLE fhq_execution.broker_reconciliation_events IS
'[CD-EXEC-ALPACA-SOT-001]: Continuous broker reconciliation log.
Any divergence between broker state and internal state is logged here.
MAJOR/CRITICAL divergence triggers governance escalation.';

-- ============================================================================
-- STEP 6: HCP LAB BROKER-TRUTH CONFIGURATION
-- ============================================================================

-- Update HCP engine config to use broker truth
INSERT INTO fhq_positions.hcp_engine_config (config_key, config_value, config_type, description)
VALUES
    ('nav_source', 'BROKER_TRUTH', 'STRING', 'NAV source: BROKER_TRUTH (Alpaca) or SYNTHETIC (deprecated)'),
    ('require_fresh_broker_snapshot', 'true', 'BOOLEAN', 'Reject execution if broker snapshot is stale'),
    ('max_snapshot_age_seconds', '300', 'INTEGER', 'Maximum age of broker snapshot before considered stale'),
    ('synthetic_nav_allowed', 'false', 'BOOLEAN', 'Whether synthetic NAV is allowed (MUST be false per CD-EXEC-ALPACA-SOT-001)')
ON CONFLICT (config_key) DO UPDATE SET
    config_value = EXCLUDED.config_value,
    description = EXCLUDED.description;

-- ============================================================================
-- STEP 7: REGISTER DIRECTIVE IN GOVERNANCE
-- ============================================================================
-- NOTE: Governance document registration handled via 05_GOVERNANCE/PHASE3 evidence files
-- The directive CD-EXEC-ALPACA-SOT-001 is recorded in JSON evidence format per ADR-004

-- ============================================================================
-- STEP 8: AUDIT LOG ENTRY
-- ============================================================================

INSERT INTO fhq_governance.audit_log (
    log_id,
    event_type,
    event_category,
    event_timestamp,
    target_type,
    target_id,
    actor_id,
    actor_role,
    event_data,
    event_hash,
    hash_algorithm,
    governance_gate,
    adr_reference
) VALUES (
    gen_random_uuid(),
    'BROKER_TRUTH_CANONICALIZATION',
    'SYSTEM',
    NOW(),
    'TABLE',
    'fhq_execution.broker_state_snapshots',
    'STIG',
    'CTO',
    jsonb_build_object(
        'directive', 'CD-EXEC-ALPACA-SOT-001',
        'authority', 'CEO',
        'changes', jsonb_build_array(
            'Deprecated fhq_positions.synthetic_lab_nav',
            'Created fhq_execution.v_broker_truth_nav as canonical source',
            'Created fhq_execution.get_broker_nav() function',
            'Created fhq_execution.validate_execution_route() guardrail',
            'Created fhq_execution.broker_reconciliation_events table',
            'Updated HCP engine config for broker-truth mode'
        ),
        'effective_at', NOW()
    ),
    encode(sha256('CD-EXEC-ALPACA-SOT-001-BROKER-TRUTH-2025-12-13'::bytea), 'hex'),
    'SHA-256',
    'G4',
    'ADR-013, ADR-016, ADR-018, ADR-019'
);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES (run after migration)
-- ============================================================================

-- Verify synthetic_lab_nav is marked deprecated
-- SELECT * FROM fhq_positions.synthetic_lab_nav;

-- Verify broker truth view works
-- SELECT * FROM fhq_execution.v_broker_truth_nav LIMIT 1;

-- Verify broker NAV function works
-- SELECT * FROM fhq_execution.get_broker_nav();

-- Verify routing guardrail works
-- SELECT * FROM fhq_execution.validate_execution_route('ALPACA', 'PAPER', 'TEST');
-- SELECT * FROM fhq_execution.validate_execution_route('SIMULATION', 'LOCAL', 'TEST');
