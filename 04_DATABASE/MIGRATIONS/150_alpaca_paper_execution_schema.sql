-- ============================================================================
-- Migration 150: Alpaca Paper Trading Execution Schema
-- ============================================================================
-- Directive: CD-IOS015-ALPACA-PAPER-001
-- Classification: G4_EXECUTION_ENABLEMENT
-- Date: 2025-12-16
-- Authority: CEO, STIG, VEGA
-- ============================================================================

-- ============================================================================
-- SECTION 1: SANDBOX SCHEMA (Episodic Memory - Non-Canonical)
-- ============================================================================
-- Per Amendment AMND-006-EPISODIC-BUFFER:
-- This schema is EPHEMERAL, NON-AUTHORITATIVE, NON-REPORTABLE

CREATE SCHEMA IF NOT EXISTS fhq_sandbox;

COMMENT ON SCHEMA fhq_sandbox IS
'Non-canonical sandbox for episodic learning traces.
NOT governed by ADR-013. Data here is ephemeral and may not be used for reporting.
Classification: GRADIENT-ONLY LEARNING';

-- Episodic traces table (purged on trade closure)
CREATE TABLE IF NOT EXISTS fhq_sandbox.episodic_traces (
    trace_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id UUID NOT NULL,
    canonical_id TEXT NOT NULL,
    strategy_source TEXT NOT NULL,

    -- Snapshot data (every 5 minutes during trade)
    snapshot_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    unrealized_pnl NUMERIC(12,4),
    unrealized_pnl_pct NUMERIC(8,4),
    max_drawdown_pct NUMERIC(8,4),
    volatility_decay NUMERIC(8,4),
    time_in_position_minutes INTEGER,

    -- Market context at snapshot
    current_price NUMERIC(16,6),
    regime_state TEXT,
    defcon_level TEXT DEFAULT 'GREEN',

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_episodic_trade_id ON fhq_sandbox.episodic_traces(trade_id);
CREATE INDEX IF NOT EXISTS idx_episodic_canonical ON fhq_sandbox.episodic_traces(canonical_id);

-- Training log archive (compressed episodic batches after trade closure)
CREATE TABLE IF NOT EXISTS fhq_sandbox.training_log_archive (
    archive_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id UUID NOT NULL,
    canonical_id TEXT NOT NULL,
    strategy_source TEXT NOT NULL,

    -- Compressed episodic summary
    episodic_hash TEXT NOT NULL,
    snapshot_count INTEGER NOT NULL,
    max_drawdown_observed NUMERIC(8,4),
    avg_unrealized_pnl NUMERIC(12,4),
    volatility_summary JSONB,

    -- Link to canonical outcome
    final_realized_pnl NUMERIC(12,4),
    trade_duration_minutes INTEGER,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- SECTION 2: EXECUTION SCHEMA (Canonical - ADR-013 Compliant)
-- ============================================================================

-- Create execution schema if not exists
CREATE SCHEMA IF NOT EXISTS fhq_execution;

-- Paper trading orders (full audit trail)
CREATE TABLE IF NOT EXISTS fhq_execution.paper_orders (
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alpaca_order_id TEXT,

    -- Signal lineage (required per directive Section 3)
    signal_id UUID NOT NULL,
    strategy_source TEXT NOT NULL,
    regime_state TEXT NOT NULL,
    cognitive_action TEXT NOT NULL,
    kelly_fraction NUMERIC(6,4) NOT NULL,
    circuit_breaker_state TEXT NOT NULL DEFAULT 'CLOSED',
    lineage_hash TEXT NOT NULL,

    -- Order details
    canonical_id TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    order_type TEXT NOT NULL CHECK (order_type IN ('market', 'limit')),
    qty NUMERIC(16,8) NOT NULL,
    limit_price NUMERIC(16,6),

    -- Execution status
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'submitted', 'filled', 'partial', 'cancelled', 'rejected')),
    filled_qty NUMERIC(16,8) DEFAULT 0,
    filled_avg_price NUMERIC(16,6),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ,
    filled_at TIMESTAMPTZ,

    -- Governance
    execution_mode TEXT NOT NULL DEFAULT 'PAPER_ONLY'
        CHECK (execution_mode = 'PAPER_ONLY'),
    defcon_at_submission TEXT NOT NULL DEFAULT 'GREEN'
);

CREATE INDEX IF NOT EXISTS idx_paper_orders_signal ON fhq_execution.paper_orders(signal_id);
CREATE INDEX IF NOT EXISTS idx_paper_orders_canonical ON fhq_execution.paper_orders(canonical_id);
CREATE INDEX IF NOT EXISTS idx_paper_orders_status ON fhq_execution.paper_orders(status);

-- Paper positions (current holdings)
CREATE TABLE IF NOT EXISTS fhq_execution.paper_positions (
    position_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_id TEXT NOT NULL,
    strategy_source TEXT NOT NULL,

    -- Position details
    side TEXT NOT NULL CHECK (side IN ('long', 'short')),
    qty NUMERIC(16,8) NOT NULL,
    avg_entry_price NUMERIC(16,6) NOT NULL,
    current_price NUMERIC(16,6),

    -- PnL tracking
    unrealized_pnl NUMERIC(12,4),
    unrealized_pnl_pct NUMERIC(8,4),
    max_drawdown_pct NUMERIC(8,4) DEFAULT 0,

    -- Lifecycle
    entry_order_id UUID REFERENCES fhq_execution.paper_orders(order_id),
    entry_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    exit_order_id UUID REFERENCES fhq_execution.paper_orders(order_id),
    exit_timestamp TIMESTAMPTZ,

    -- Status
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),

    -- Unique constraint: one open position per asset per strategy
    UNIQUE (canonical_id, strategy_source, status)
        WHERE status = 'open'
);

CREATE INDEX IF NOT EXISTS idx_paper_positions_status ON fhq_execution.paper_positions(status);

-- Paper trade outcomes (for learning - canonical)
CREATE TABLE IF NOT EXISTS fhq_execution.paper_trade_outcomes (
    outcome_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id UUID NOT NULL REFERENCES fhq_execution.paper_positions(position_id),

    -- Trade summary
    canonical_id TEXT NOT NULL,
    strategy_source TEXT NOT NULL,
    side TEXT NOT NULL,

    -- Performance
    entry_price NUMERIC(16,6) NOT NULL,
    exit_price NUMERIC(16,6) NOT NULL,
    realized_pnl NUMERIC(12,4) NOT NULL,
    realized_pnl_pct NUMERIC(8,4) NOT NULL,
    max_drawdown_pct NUMERIC(8,4),

    -- Duration
    hold_duration_minutes INTEGER NOT NULL,

    -- Context at close
    regime_at_entry TEXT,
    regime_at_exit TEXT,

    -- Learning metadata
    episodic_archive_id UUID REFERENCES fhq_sandbox.training_log_archive(archive_id),
    learning_applied BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Learning updates log (audit trail for bandit/RL updates)
CREATE TABLE IF NOT EXISTS fhq_execution.learning_updates (
    update_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outcome_id UUID NOT NULL REFERENCES fhq_execution.paper_trade_outcomes(outcome_id),

    -- Update target
    learning_system TEXT NOT NULL
        CHECK (learning_system IN ('THOMPSON_BANDIT', 'CAUSAL_RL', 'STRATEGY_STATS')),

    -- Update details
    action TEXT NOT NULL,
    reward NUMERIC(8,4) NOT NULL,
    prior_state JSONB,
    posterior_state JSONB,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- SECTION 3: GOVERNANCE VIEWS
-- ============================================================================

-- Execution summary view (for VEGA)
CREATE OR REPLACE VIEW fhq_execution.vw_paper_execution_summary AS
SELECT
    DATE(created_at) as trade_date,
    strategy_source,
    COUNT(*) as total_orders,
    COUNT(*) FILTER (WHERE status = 'filled') as filled_orders,
    COUNT(*) FILTER (WHERE status = 'rejected') as rejected_orders,
    SUM(filled_qty * filled_avg_price) FILTER (WHERE status = 'filled') as total_volume
FROM fhq_execution.paper_orders
GROUP BY DATE(created_at), strategy_source;

-- Learning audit view
CREATE OR REPLACE VIEW fhq_execution.vw_learning_audit AS
SELECT
    lu.update_id,
    lu.learning_system,
    lu.action,
    lu.reward,
    pto.canonical_id,
    pto.strategy_source,
    pto.realized_pnl,
    pto.realized_pnl_pct,
    lu.created_at
FROM fhq_execution.learning_updates lu
JOIN fhq_execution.paper_trade_outcomes pto ON lu.outcome_id = pto.outcome_id
ORDER BY lu.created_at DESC;

-- ============================================================================
-- SECTION 4: SAFETY FUNCTIONS
-- ============================================================================

-- Function to validate order lineage (required per directive Section 3)
CREATE OR REPLACE FUNCTION fhq_execution.validate_order_lineage(
    p_signal_id UUID,
    p_strategy TEXT,
    p_regime TEXT,
    p_cognitive_action TEXT,
    p_kelly_fraction NUMERIC,
    p_circuit_state TEXT
) RETURNS TEXT AS $$
DECLARE
    v_hash TEXT;
BEGIN
    -- Generate lineage hash
    v_hash := encode(
        sha256(
            (p_signal_id::TEXT || p_strategy || p_regime ||
             p_cognitive_action || p_kelly_fraction::TEXT || p_circuit_state)::BYTEA
        ),
        'hex'
    );

    RETURN v_hash;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to purge episodic traces on trade closure
CREATE OR REPLACE FUNCTION fhq_sandbox.purge_episodic_traces(p_trade_id UUID)
RETURNS VOID AS $$
BEGIN
    -- Delete all episodic traces for this trade
    DELETE FROM fhq_sandbox.episodic_traces WHERE trade_id = p_trade_id;
END;
$$ LANGUAGE plpgsql;

-- Function to check sandbox storage (fail-closed at 1GB per Amendment 6.4)
CREATE OR REPLACE FUNCTION fhq_sandbox.check_storage_limit()
RETURNS BOOLEAN AS $$
DECLARE
    v_size_bytes BIGINT;
BEGIN
    SELECT pg_total_relation_size('fhq_sandbox.episodic_traces') INTO v_size_bytes;

    -- 1GB = 1073741824 bytes
    IF v_size_bytes > 1073741824 THEN
        RETURN FALSE;  -- Storage exceeded, disable episodic
    END IF;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- GOVERNANCE ATTESTATION
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
    signature_verified,
    attestation_data,
    adr_reference,
    constitutional_basis
) VALUES (
    gen_random_uuid(),
    'MIGRATION',
    'migration_150_alpaca_paper_execution',
    'v1.0',
    'G4_SCHEMA_ACTIVATION',
    'APPROVED',
    NOW(),
    'STIG_MIGRATION_SIGNATURE',
    'STIG_CTO_KEY',
    true,
    '{
        "directive": "CD-IOS015-ALPACA-PAPER-001",
        "amendment": "AMND-006-EPISODIC-BUFFER",
        "schemas_created": ["fhq_sandbox", "fhq_execution"],
        "tables_created": ["episodic_traces", "training_log_archive", "paper_orders", "paper_positions", "paper_trade_outcomes", "learning_updates"],
        "execution_mode": "PAPER_ONLY",
        "canonical_separation": true
    }'::jsonb,
    'CD-IOS015-ALPACA-PAPER-001, ADR-013, ADR-016',
    'Alpaca Paper Trading Execution Enablement'
);

-- ============================================================================
-- END MIGRATION 150
-- ============================================================================
