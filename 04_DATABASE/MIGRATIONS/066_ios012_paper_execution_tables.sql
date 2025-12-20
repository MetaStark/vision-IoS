-- ============================================================================
-- MIGRATION 066: IoS-012 Paper Execution Tables
-- ============================================================================
-- Purpose: Create paper trading infrastructure for IoS-012
-- Author: STIG (CTO)
-- Date: 2025-12-02
-- Authority: CEO Directive HC-CEO-TASK-ACTIVATION-20251202
-- ADR Reference: ADR-012 (Economic Safety)
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: Paper Execution Log
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_execution.paper_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Order identification
    order_id UUID NOT NULL,
    parent_order_id UUID,

    -- Instrument
    symbol TEXT NOT NULL,
    asset_class TEXT NOT NULL,

    -- Order details
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    order_type TEXT NOT NULL CHECK (order_type IN ('MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT')),
    quantity NUMERIC(18, 8) NOT NULL,
    limit_price NUMERIC(18, 8),
    stop_price NUMERIC(18, 8),

    -- Execution details
    fill_price NUMERIC(18, 8),
    fill_quantity NUMERIC(18, 8),
    fill_value_usd NUMERIC(18, 2),
    commission_usd NUMERIC(18, 4) DEFAULT 0,
    slippage_bps NUMERIC(8, 2),

    -- Status
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'SUBMITTED', 'PARTIAL', 'FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED')),
    reject_reason TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ,
    filled_at TIMESTAMPTZ,

    -- Source tracking
    ios_id TEXT NOT NULL DEFAULT 'IoS-012',
    signal_source TEXT,
    regime_state TEXT,

    -- Governance
    task_run_id UUID,
    hash_chain_id TEXT
);

CREATE INDEX idx_paper_log_symbol ON fhq_execution.paper_log(symbol);
CREATE INDEX idx_paper_log_created_at ON fhq_execution.paper_log(created_at);
CREATE INDEX idx_paper_log_status ON fhq_execution.paper_log(status);

-- ============================================================================
-- SECTION 2: Paper Position State
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_execution.paper_positions (
    position_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    symbol TEXT NOT NULL UNIQUE,
    asset_class TEXT NOT NULL,

    -- Position size
    quantity NUMERIC(18, 8) NOT NULL DEFAULT 0,
    avg_entry_price NUMERIC(18, 8),
    current_price NUMERIC(18, 8),

    -- P&L
    unrealized_pnl_usd NUMERIC(18, 2) DEFAULT 0,
    realized_pnl_usd NUMERIC(18, 2) DEFAULT 0,

    -- Risk
    notional_usd NUMERIC(18, 2) DEFAULT 0,
    weight_pct NUMERIC(8, 4) DEFAULT 0,

    -- Timestamps
    opened_at TIMESTAMPTZ,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Governance
    ios_id TEXT NOT NULL DEFAULT 'IoS-012'
);

CREATE INDEX idx_paper_positions_symbol ON fhq_execution.paper_positions(symbol);

-- ============================================================================
-- SECTION 3: Paper Execution Metrics
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_execution.paper_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Time bucket
    bucket_date DATE NOT NULL,
    bucket_hour INTEGER CHECK (bucket_hour >= 0 AND bucket_hour < 24),

    -- Volume metrics
    order_count INTEGER NOT NULL DEFAULT 0,
    fill_count INTEGER NOT NULL DEFAULT 0,
    reject_count INTEGER NOT NULL DEFAULT 0,

    -- Value metrics
    total_turnover_usd NUMERIC(18, 2) DEFAULT 0,
    total_commission_usd NUMERIC(18, 4) DEFAULT 0,

    -- Performance metrics
    avg_slippage_bps NUMERIC(8, 2),
    avg_fill_time_ms INTEGER,

    -- P&L
    realized_pnl_usd NUMERIC(18, 2) DEFAULT 0,

    -- ADR-012 compliance
    daily_limit_remaining_usd NUMERIC(18, 2),
    daily_trades_remaining INTEGER,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Governance
    ios_id TEXT NOT NULL DEFAULT 'IoS-012',

    UNIQUE(bucket_date, bucket_hour)
);

CREATE INDEX idx_paper_metrics_date ON fhq_execution.paper_metrics(bucket_date);

-- ============================================================================
-- SECTION 4: ADR-012 Daily Budget Tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_execution.paper_daily_budget (
    budget_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    budget_date DATE NOT NULL UNIQUE,

    -- Limits (from economic_safety_limits)
    max_trades INTEGER NOT NULL DEFAULT 50,
    max_turnover_usd NUMERIC(18, 2) NOT NULL DEFAULT 50000.00,
    max_position_usd NUMERIC(18, 2) NOT NULL DEFAULT 10000.00,

    -- Usage
    trades_used INTEGER NOT NULL DEFAULT 0,
    turnover_used_usd NUMERIC(18, 2) NOT NULL DEFAULT 0,
    max_position_reached_usd NUMERIC(18, 2) DEFAULT 0,

    -- Status
    limit_breached BOOLEAN NOT NULL DEFAULT FALSE,
    breach_type TEXT,
    breach_time TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Governance
    ios_id TEXT NOT NULL DEFAULT 'IoS-012'
);

CREATE INDEX idx_paper_daily_budget_date ON fhq_execution.paper_daily_budget(budget_date);

-- ============================================================================
-- SECTION 5: Initialize today's budget
-- ============================================================================

INSERT INTO fhq_execution.paper_daily_budget (budget_date, max_trades, max_turnover_usd, max_position_usd)
VALUES (CURRENT_DATE, 50, 50000.00, 10000.00)
ON CONFLICT (budget_date) DO NOTHING;

-- ============================================================================
-- SECTION 6: Governance logging
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    vega_reviewed,
    hash_chain_id
) VALUES (
    'SCHEMA_CREATION',
    'fhq_execution.paper_*',
    'TABLE_SET',
    'STIG',
    NOW(),
    'COMPLETED',
    'Created paper trading tables for IoS-012: paper_log, paper_positions, paper_metrics, paper_daily_budget. ADR-012 compliant.',
    false,
    'HC-IOS012-SCHEMA-20251202'
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'fhq_execution' AND table_name LIKE 'paper%'
ORDER BY table_name;
