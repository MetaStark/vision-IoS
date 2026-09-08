-- Migration 189: Paper-to-Live Proof Standard (PLPS) Gate & Market Realism Filter
-- Classification: GOVERNANCE-CRITICAL (Tier-1)
-- Authority: CEO Hard Correction 2025-12-31
-- Purpose: Prevent psychological drift into "just one small live test"

BEGIN;

-- ============================================================================
-- SECTION 1: Store CEO Directive in governance_documents
-- ============================================================================

INSERT INTO fhq_governance.governance_documents (
    document_id,
    document_name,
    document_type,
    tier,
    version,
    content,
    created_at,
    approved_by,
    status
) VALUES (
    gen_random_uuid(),
    'CEO-DIR-2026-PLPS-001',
    'CEO_DIRECTIVE',
    1,
    'v1',
    '{
        "directive_id": "CEO-DIR-2026-PLPS-001",
        "title": "Paper-to-Live Proof Standard (PLPS) Gate",
        "classification": "GOVERNANCE-CRITICAL (Tier-1)",
        "status": "MANDATORY_EXECUTION",
        "authority": "CEO Hard Correction",
        "effective_date": "2025-12-31T23:30:00Z",
        "executive_intent": "Prevent psychological drift into live trading before rigorous paper validation. 0% real capital loss tolerance. 100% paper drawdown tolerance.",
        "sections": {
            "risk_tolerance_semantics": {
                "real_capital_loss_tolerance": "0%",
                "paper_drawdown_tolerance": "100%",
                "principle": "Paper until proven - no small live tests"
            },
            "graduation_criteria": {
                "minimum_trades": 50,
                "profit_factor_floor": 1.2,
                "max_drawdown_pct": 15,
                "sharpe_ratio_floor": 0.5,
                "regime_coverage_min": 2,
                "vega_attestation": "REQUIRED",
                "conservative_pnl_positive": true
            },
            "market_realism_filter": {
                "slippage_haircut_bps": {"min": 2, "max": 10},
                "spread_haircut_bps": {"min": 5, "max": 20},
                "per_asset_calibration": true,
                "track_haircut_pnl": true
            }
        }
    }',
    NOW(),
    'CEO',
    'ACTIVE'
);

-- ============================================================================
-- SECTION 2: PLPS Gate Configuration Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.plps_gate_config (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    directive_id TEXT NOT NULL DEFAULT 'CEO-DIR-2026-PLPS-001',

    -- Risk Tolerance Semantics
    real_capital_loss_tolerance_pct NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    paper_drawdown_tolerance_pct NUMERIC(5,2) NOT NULL DEFAULT 100.00,

    -- Graduation Criteria
    minimum_trades INT NOT NULL DEFAULT 50,
    profit_factor_floor NUMERIC(5,2) NOT NULL DEFAULT 1.20,
    max_drawdown_pct NUMERIC(5,2) NOT NULL DEFAULT 15.00,
    sharpe_ratio_floor NUMERIC(5,2) NOT NULL DEFAULT 0.50,
    regime_coverage_min INT NOT NULL DEFAULT 2,

    -- Conservative PnL Gate
    conservative_pnl_must_be_positive BOOLEAN NOT NULL DEFAULT TRUE,

    -- Governance
    vega_attestation_required BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT plps_no_live_risk CHECK (real_capital_loss_tolerance_pct = 0.00)
);

-- Insert default PLPS config
INSERT INTO fhq_governance.plps_gate_config (
    minimum_trades,
    profit_factor_floor,
    max_drawdown_pct,
    sharpe_ratio_floor,
    regime_coverage_min
) VALUES (50, 1.20, 15.00, 0.50, 2);

-- ============================================================================
-- SECTION 3: Market Realism Filter Configuration
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_execution.market_realism_config (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_class TEXT NOT NULL,  -- 'CRYPTO', 'EQUITY', 'FX'
    asset_symbol TEXT,          -- NULL = class default

    -- Slippage Haircut (basis points)
    slippage_haircut_bps NUMERIC(6,2) NOT NULL DEFAULT 5.00,

    -- Spread Haircut (basis points)
    spread_haircut_bps NUMERIC(6,2) NOT NULL DEFAULT 10.00,

    -- Partial Fill Assumptions
    expected_fill_rate_pct NUMERIC(5,2) NOT NULL DEFAULT 95.00,

    -- Liquidity Tier (affects haircut multiplier)
    liquidity_tier TEXT NOT NULL CHECK (liquidity_tier IN ('HIGH', 'MEDIUM', 'LOW')),

    -- Governance
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert default realism configs by asset class
INSERT INTO fhq_execution.market_realism_config (asset_class, asset_symbol, slippage_haircut_bps, spread_haircut_bps, liquidity_tier) VALUES
    ('CRYPTO', 'BTC-USD', 3.00, 5.00, 'HIGH'),
    ('CRYPTO', 'ETH-USD', 4.00, 7.00, 'HIGH'),
    ('CRYPTO', NULL, 8.00, 15.00, 'MEDIUM'),  -- Default for other crypto
    ('EQUITY', NULL, 2.00, 3.00, 'HIGH'),
    ('FX', NULL, 1.00, 2.00, 'HIGH');

-- ============================================================================
-- SECTION 4: Capital Ledger Extensions for Conservative PnL
-- ============================================================================

ALTER TABLE fhq_execution.capital_ledger
    ADD COLUMN IF NOT EXISTS slippage_haircut_bps NUMERIC(6,2) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS spread_haircut_bps NUMERIC(6,2) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS haircut_total_usd NUMERIC(12,2) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS conservative_pnl_usd NUMERIC(12,2) GENERATED ALWAYS AS (
        simulated_pnl_usd - COALESCE(haircut_total_usd, 0)
    ) STORED,
    ADD COLUMN IF NOT EXISTS signal_id UUID,
    ADD COLUMN IF NOT EXISTS regime_id TEXT,
    ADD COLUMN IF NOT EXISTS lsa_hash TEXT;

-- ============================================================================
-- SECTION 5: PLPS Graduation Tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.plps_graduation_attempts (
    attempt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_id UUID REFERENCES fhq_governance.plps_gate_config(config_id),

    -- Evaluation Window
    evaluation_start DATE NOT NULL,
    evaluation_end DATE NOT NULL,

    -- Trade Metrics
    total_trades INT NOT NULL,
    winning_trades INT NOT NULL,
    losing_trades INT NOT NULL,

    -- Performance Metrics
    gross_pnl_usd NUMERIC(12,2) NOT NULL,
    haircut_total_usd NUMERIC(12,2) NOT NULL,
    conservative_pnl_usd NUMERIC(12,2) NOT NULL,
    profit_factor NUMERIC(6,3),
    max_drawdown_pct NUMERIC(5,2),
    sharpe_ratio NUMERIC(6,3),

    -- Regime Coverage
    regimes_traded TEXT[] NOT NULL,
    regime_count INT NOT NULL,

    -- Gate Results
    gate_min_trades_passed BOOLEAN NOT NULL,
    gate_profit_factor_passed BOOLEAN NOT NULL,
    gate_max_drawdown_passed BOOLEAN NOT NULL,
    gate_sharpe_passed BOOLEAN NOT NULL,
    gate_regime_coverage_passed BOOLEAN NOT NULL,
    gate_conservative_pnl_passed BOOLEAN NOT NULL,

    -- Overall
    all_gates_passed BOOLEAN NOT NULL,
    graduation_status TEXT NOT NULL CHECK (graduation_status IN (
        'PENDING', 'GRADUATED', 'FAILED', 'INSUFFICIENT_DATA'
    )),

    -- VEGA Attestation
    vega_attestation_id UUID,
    vega_signed_at TIMESTAMPTZ,
    evidence_bundle_hash TEXT,

    -- Metadata
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    evaluated_by TEXT NOT NULL DEFAULT 'VEGA'
);

CREATE INDEX idx_plps_graduation_status ON fhq_governance.plps_graduation_attempts(graduation_status);

-- ============================================================================
-- SECTION 6: Alpaca Trade Sync Table (for pulling history)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_execution.alpaca_trade_sync (
    sync_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alpaca_order_id TEXT NOT NULL UNIQUE,

    -- Order Details
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    qty NUMERIC(18,8) NOT NULL,
    filled_qty NUMERIC(18,8),
    avg_fill_price NUMERIC(18,8),

    -- Timing
    submitted_at TIMESTAMPTZ NOT NULL,
    filled_at TIMESTAMPTZ,

    -- Fees & Realism
    commission_usd NUMERIC(10,4) DEFAULT 0,
    slippage_est_bps NUMERIC(6,2),
    spread_est_bps NUMERIC(6,2),

    -- PnL
    realized_pnl_usd NUMERIC(12,2),
    unrealized_pnl_usd NUMERIC(12,2),

    -- Linkage
    signal_id UUID,
    needle_id UUID,
    regime_at_entry TEXT,
    lsa_hash TEXT,

    -- VEGA
    vega_attestation_id UUID,

    -- Sync Metadata
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sync_source TEXT NOT NULL DEFAULT 'ALPACA_API'
);

CREATE INDEX idx_alpaca_sync_symbol ON fhq_execution.alpaca_trade_sync(symbol);
CREATE INDEX idx_alpaca_sync_filled_at ON fhq_execution.alpaca_trade_sync(filled_at);

-- ============================================================================
-- SECTION 7: Regime x Strategy Performance Matrix View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_execution.v_regime_strategy_matrix AS
SELECT
    regime_at_entry AS regime,
    symbol,
    COUNT(*) AS trade_count,
    SUM(CASE WHEN realized_pnl_usd > 0 THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN realized_pnl_usd < 0 THEN 1 ELSE 0 END) AS losses,
    ROUND(AVG(realized_pnl_usd)::NUMERIC, 2) AS avg_pnl,
    ROUND(SUM(realized_pnl_usd)::NUMERIC, 2) AS total_pnl,
    ROUND((SUM(CASE WHEN realized_pnl_usd > 0 THEN realized_pnl_usd ELSE 0 END) /
           NULLIF(ABS(SUM(CASE WHEN realized_pnl_usd < 0 THEN realized_pnl_usd ELSE 0 END)), 0))::NUMERIC, 3) AS profit_factor,
    ROUND((SUM(CASE WHEN realized_pnl_usd > 0 THEN 1 ELSE 0 END)::NUMERIC / NULLIF(COUNT(*), 0) * 100)::NUMERIC, 1) AS win_rate_pct
FROM fhq_execution.alpaca_trade_sync
WHERE filled_at IS NOT NULL
GROUP BY regime_at_entry, symbol
ORDER BY total_pnl DESC;

-- ============================================================================
-- SECTION 8: Audit Trail
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    metadata,
    agent_id,
    timestamp
) VALUES (
    gen_random_uuid(),
    'MIGRATION_APPLIED',
    'CEO-DIR-2026-PLPS-001',
    'CEO_DIRECTIVE',
    'STIG',
    NOW(),
    'EXECUTED',
    'Applied Migration 189: PLPS Gate & Market Realism Filter - CEO Hard Correction preventing live trading before paper proof',
    jsonb_build_object(
        'migration_id', '189',
        'directive', 'CEO-DIR-2026-PLPS-001',
        'tables_created', ARRAY[
            'fhq_governance.plps_gate_config',
            'fhq_execution.market_realism_config',
            'fhq_governance.plps_graduation_attempts',
            'fhq_execution.alpaca_trade_sync'
        ],
        'views_created', ARRAY['fhq_execution.v_regime_strategy_matrix'],
        'risk_tolerance', jsonb_build_object(
            'real_capital_loss', '0%',
            'paper_drawdown', '100%'
        )
    ),
    'STIG',
    NOW()
);

COMMIT;
