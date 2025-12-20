-- ============================================================
-- IoS-012: G2 PAPER TRADING INFRASTRUCTURE
-- ============================================================
-- Authority: BOARD (Vice-CEO)
-- Technical Lead: STIG (CTO)
-- Operations: LINE
-- Governance: VEGA
-- Classification: Tier-1 Critical
-- Migration: 053_ios012_g2_paper_trading.sql
-- ============================================================
--
-- "The Hand reaches into the world"
--
-- G2 validates external connectivity with Alpaca Paper Trading API.
-- NO LIVE ENDPOINTS. PAPER_API ONLY.
-- ============================================================

BEGIN;

-- ============================================================
-- SECTION 1: CREATE fhq_execution SCHEMA
-- ============================================================

CREATE SCHEMA IF NOT EXISTS fhq_execution;

COMMENT ON SCHEMA fhq_execution IS 'IoS-012 Execution Domain: Trade execution, broker state, order management. PAPER_API mode only until QG-F6.';

-- ============================================================
-- SECTION 2: TRADES TABLE (Append-Only Audit Trail)
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_execution.trades (
    trade_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Decision Link
    decision_id UUID NOT NULL,
    execution_id UUID,

    -- Broker Details
    broker TEXT NOT NULL DEFAULT 'ALPACA',
    broker_order_id TEXT,
    broker_environment TEXT NOT NULL DEFAULT 'PAPER'
        CHECK (broker_environment IN ('PAPER', 'LIVE')),

    -- Order Details
    asset_id TEXT NOT NULL,
    order_side TEXT NOT NULL CHECK (order_side IN ('BUY', 'SELL')),
    order_type TEXT NOT NULL DEFAULT 'MARKET'
        CHECK (order_type IN ('MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT')),
    order_qty NUMERIC NOT NULL,
    limit_price NUMERIC,
    stop_price NUMERIC,

    -- Fill Details
    filled_qty NUMERIC,
    filled_avg_price NUMERIC,
    fill_status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (fill_status IN ('PENDING', 'SUBMITTED', 'PARTIAL', 'FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED')),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ,
    filled_at TIMESTAMPTZ,

    -- Latency Metrics
    submission_latency_ms INTEGER,
    fill_latency_ms INTEGER,
    total_lifecycle_ms INTEGER,

    -- Security
    decision_signature TEXT,
    signature_verified BOOLEAN DEFAULT FALSE,

    -- Audit
    created_by TEXT NOT NULL DEFAULT 'IoS-012',
    hash_chain_id TEXT
);

-- Immutability trigger (append-only)
CREATE OR REPLACE FUNCTION fhq_execution.enforce_trades_immutability()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        -- Only allow fill updates (not order modifications)
        IF OLD.broker_order_id IS NOT NULL AND NEW.broker_order_id != OLD.broker_order_id THEN
            RAISE EXCEPTION 'IMMUTABILITY_VIOLATION: Cannot modify broker_order_id after submission';
        END IF;
        IF OLD.order_qty != NEW.order_qty OR OLD.order_side != NEW.order_side THEN
            RAISE EXCEPTION 'IMMUTABILITY_VIOLATION: Cannot modify order details after creation';
        END IF;
    ELSIF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'IMMUTABILITY_VIOLATION: Deletes not permitted on trades table';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_trades_immutability
    BEFORE UPDATE OR DELETE ON fhq_execution.trades
    FOR EACH ROW EXECUTE FUNCTION fhq_execution.enforce_trades_immutability();

CREATE INDEX IF NOT EXISTS idx_trades_decision ON fhq_execution.trades(decision_id);
CREATE INDEX IF NOT EXISTS idx_trades_broker_order ON fhq_execution.trades(broker_order_id);
CREATE INDEX IF NOT EXISTS idx_trades_asset ON fhq_execution.trades(asset_id);
CREATE INDEX IF NOT EXISTS idx_trades_created ON fhq_execution.trades(created_at);

-- ============================================================
-- SECTION 3: BROKER STATE SNAPSHOTS
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_execution.broker_state_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Snapshot Context
    broker TEXT NOT NULL DEFAULT 'ALPACA',
    broker_environment TEXT NOT NULL DEFAULT 'PAPER'
        CHECK (broker_environment IN ('PAPER', 'LIVE')),
    snapshot_type TEXT NOT NULL DEFAULT 'POSITIONS'
        CHECK (snapshot_type IN ('ACCOUNT', 'POSITIONS', 'ORDERS', 'FULL')),

    -- Account State
    account_id TEXT,
    account_status TEXT,
    buying_power NUMERIC,
    cash NUMERIC,
    portfolio_value NUMERIC,

    -- Position State (JSONB for flexibility)
    positions JSONB,

    -- Open Orders State
    open_orders JSONB,

    -- Reconciliation
    fhq_internal_state JSONB,
    divergence_detected BOOLEAN DEFAULT FALSE,
    divergence_details JSONB,

    -- Timestamps
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    broker_timestamp TIMESTAMPTZ,

    -- Audit
    created_by TEXT NOT NULL DEFAULT 'IoS-012',
    hash_chain_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_broker_snapshots_captured ON fhq_execution.broker_state_snapshots(captured_at);
CREATE INDEX IF NOT EXISTS idx_broker_snapshots_divergence ON fhq_execution.broker_state_snapshots(divergence_detected);

-- ============================================================
-- SECTION 4: LATENCY BENCHMARKS TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_execution.latency_benchmarks (
    benchmark_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Test Context
    test_name TEXT NOT NULL,
    test_type TEXT NOT NULL DEFAULT 'G2_VALIDATION',

    -- Latency Measurements (ms)
    detection_latency_ms INTEGER,
    verification_latency_ms INTEGER,
    submission_latency_ms INTEGER,
    fill_latency_ms INTEGER,
    reconciliation_latency_ms INTEGER,
    total_lifecycle_ms INTEGER NOT NULL,

    -- Benchmark Result
    threshold_ms INTEGER NOT NULL DEFAULT 500,
    passed BOOLEAN NOT NULL,

    -- Details
    details JSONB,

    -- Timestamps
    measured_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- SECTION 5: GOVERNANCE LOG
-- ============================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id, action_type, action_target, action_target_type,
    initiated_by, initiated_at, decision, decision_rationale,
    vega_reviewed, vega_override, hash_chain_id
) VALUES (
    gen_random_uuid(),
    'IOS_GATE_PROGRESSION',
    'IoS-012',
    'MODULE',
    'BOARD',
    NOW(),
    'APPROVED',
    'IoS-012 G2 Paper Trading Infrastructure: fhq_execution schema, trades table, broker_state_snapshots, latency_benchmarks. PAPER_API mode only.',
    false,
    false,
    'HC-IOS012-G2-001'
);

COMMIT;

-- ============================================================
-- VERIFICATION
-- ============================================================

SELECT 'SCHEMA' as type, schema_name
FROM information_schema.schemata
WHERE schema_name = 'fhq_execution';

SELECT 'TABLE' as type, table_name
FROM information_schema.tables
WHERE table_schema = 'fhq_execution'
ORDER BY table_name;
