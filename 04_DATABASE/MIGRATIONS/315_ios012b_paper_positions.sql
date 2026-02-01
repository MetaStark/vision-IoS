-- Migration 315: IoS-012-B Paper Trading Positions
-- Directive: CEO-DIR-2026-106 (Option C Approval)
-- Date: 2026-01-19
-- Author: STIG
-- Purpose: Paper trading position tracking for IoS-012-B
--
-- CEO DECISION (2026-01-19):
-- "go with option C, activate paper trading"
--
-- Option C: Keep hindsight firewall for LIVE trading, but activate PAPER trading NOW.
--
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: Paper Positions Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.ios012b_paper_positions (
    position_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Signal linkage
    source_overlay_id UUID NOT NULL REFERENCES fhq_alpha.inversion_overlay_shadow(overlay_id),

    -- Position details
    ticker TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('UP', 'DOWN')),
    entry_price NUMERIC NOT NULL,
    entry_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    position_size_usd NUMERIC NOT NULL,
    shares INTEGER NOT NULL,

    -- Strategy type
    strategy_type TEXT NOT NULL DEFAULT 'SPOT' CHECK (strategy_type IN ('SPOT', 'OPTIONS_SIMULATED')),

    -- Status
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'CANCELLED')),

    -- Current state (for open positions)
    current_price NUMERIC,
    unrealized_pnl NUMERIC,
    unrealized_pnl_pct NUMERIC,

    -- Exit details (for closed positions)
    exit_price NUMERIC,
    exit_timestamp TIMESTAMPTZ,
    exit_reason TEXT,
    realized_pnl NUMERIC,
    realized_pnl_pct NUMERIC,

    -- Audit
    evidence_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_ios012b_paper_positions_status
ON fhq_alpha.ios012b_paper_positions(status);

CREATE INDEX IF NOT EXISTS idx_ios012b_paper_positions_ticker
ON fhq_alpha.ios012b_paper_positions(ticker);

CREATE INDEX IF NOT EXISTS idx_ios012b_paper_positions_overlay
ON fhq_alpha.ios012b_paper_positions(source_overlay_id);

-- ============================================================================
-- SECTION 2: Paper Trade Log
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.ios012b_paper_trade_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id UUID REFERENCES fhq_alpha.ios012b_paper_positions(position_id),
    event_type TEXT NOT NULL,  -- OPEN, UPDATE, CLOSE, ERROR
    event_timestamp TIMESTAMPTZ DEFAULT NOW(),
    event_data JSONB,
    evidence_hash TEXT
);

-- ============================================================================
-- SECTION 3: Portfolio Summary View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_alpha.v_ios012b_paper_portfolio AS
SELECT
    COUNT(*) as total_positions,
    COUNT(CASE WHEN status = 'OPEN' THEN 1 END) as open_positions,
    COUNT(CASE WHEN status = 'CLOSED' THEN 1 END) as closed_positions,
    COALESCE(SUM(CASE WHEN status = 'OPEN' THEN position_size_usd END), 0) as total_exposure,
    COALESCE(SUM(CASE WHEN status = 'OPEN' THEN unrealized_pnl END), 0) as total_unrealized_pnl,
    COALESCE(SUM(CASE WHEN status = 'CLOSED' THEN realized_pnl END), 0) as total_realized_pnl,
    COALESCE(SUM(CASE WHEN status = 'OPEN' THEN unrealized_pnl END), 0) +
    COALESCE(SUM(CASE WHEN status = 'CLOSED' THEN realized_pnl END), 0) as total_pnl,
    ROUND(
        COALESCE(SUM(CASE WHEN status = 'CLOSED' AND realized_pnl > 0 THEN 1 END), 0)::NUMERIC /
        NULLIF(COUNT(CASE WHEN status = 'CLOSED' THEN 1 END), 0) * 100,
        2
    ) as win_rate_pct
FROM fhq_alpha.ios012b_paper_positions;

-- ============================================================================
-- SECTION 4: Position Performance View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_alpha.v_ios012b_paper_positions_detail AS
SELECT
    pp.position_id,
    pp.ticker,
    pp.direction,
    pp.entry_price,
    pp.entry_timestamp,
    pp.shares,
    pp.position_size_usd,
    pp.status,
    pp.current_price,
    pp.unrealized_pnl,
    pp.unrealized_pnl_pct,
    pp.exit_price,
    pp.exit_timestamp,
    pp.realized_pnl,
    pp.realized_pnl_pct,
    ios.source_confidence,
    ios.inverted_brier,
    EXTRACT(EPOCH FROM (COALESCE(pp.exit_timestamp, NOW()) - pp.entry_timestamp)) / 3600 as hours_held
FROM fhq_alpha.ios012b_paper_positions pp
JOIN fhq_alpha.inversion_overlay_shadow ios
    ON pp.source_overlay_id = ios.overlay_id
ORDER BY pp.entry_timestamp DESC;

-- ============================================================================
-- SECTION 5: Log CEO Option C Approval
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale
) VALUES (
    gen_random_uuid(),
    'CEO_OPTION_C_PAPER_TRADING_APPROVAL',
    'IoS-012-B',
    'SYNTHETIC_INVERSION_MODULE',
    'CEO',
    NOW(),
    'APPROVED',
    'Option C approved: Keep hindsight firewall for LIVE trading until 2026-02-02, but activate PAPER trading immediately. Paper trading tests execution mechanics, tracks simulated P&L, validates strike selection/timing, and builds G4 evidence package.'
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- SELECT * FROM fhq_alpha.v_ios012b_paper_portfolio;
-- SELECT * FROM fhq_alpha.v_ios012b_paper_positions_detail;
