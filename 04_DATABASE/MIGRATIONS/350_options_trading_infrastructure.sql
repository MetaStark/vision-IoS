-- ============================================================================
-- Migration 350: Options Trading Infrastructure
-- ============================================================================
-- Directive:  CEO-DIR-2026-OPS-AUTONOMY-001
-- Gate:       G1 (Technical Validation)
-- Author:     STIG (EC-003)
-- Date:       2026-02-01
-- Spec:       IoS-012-C (Options Execution Architecture)
-- ============================================================================
-- Creates options-specific tables in fhq_execution, fhq_learning, fhq_monitoring.
-- All execution remains SHADOW_PAPER until G4 CEO approval.
-- ============================================================================

BEGIN;

-- ============================================================================
-- A. fhq_execution: Options Chain Snapshots
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhq_execution.options_chain_snapshots (
    snapshot_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    underlying          VARCHAR(20) NOT NULL,
    expiration_date     DATE NOT NULL,
    strike              NUMERIC(12,4) NOT NULL,
    option_type         VARCHAR(4) NOT NULL CHECK (option_type IN ('CALL', 'PUT')),
    bid                 NUMERIC(12,4),
    ask                 NUMERIC(12,4),
    mid                 NUMERIC(12,4),
    last_price          NUMERIC(12,4),
    delta               NUMERIC(10,6),
    gamma               NUMERIC(10,6),
    vega                NUMERIC(10,6),
    theta               NUMERIC(10,6),
    rho                 NUMERIC(10,6),
    implied_volatility  NUMERIC(10,6),
    open_interest       INTEGER,
    volume              INTEGER,
    snapshot_timestamp  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    content_hash        VARCHAR(64),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ocs_underlying_exp
    ON fhq_execution.options_chain_snapshots (underlying, expiration_date);
CREATE INDEX IF NOT EXISTS idx_ocs_snapshot_ts
    ON fhq_execution.options_chain_snapshots (snapshot_timestamp);

COMMENT ON TABLE fhq_execution.options_chain_snapshots IS
    'IoS-012-C: Cached options chain data per underlying/expiration/strike. ADR-013 hash-signed.';

-- ============================================================================
-- B. fhq_execution: Options Shadow Orders
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhq_execution.options_shadow_orders (
    order_id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_ref               VARCHAR(60) NOT NULL UNIQUE,
    strategy_type           VARCHAR(30) NOT NULL CHECK (strategy_type IN (
                                'CASH_SECURED_PUT', 'COVERED_CALL', 'VERTICAL_SPREAD',
                                'IRON_CONDOR', 'PROTECTIVE_PUT'
                            )),
    underlying              VARCHAR(20) NOT NULL,
    legs                    JSONB NOT NULL,          -- [{side, strike, expiration, option_type, quantity}]
    filled_prices           JSONB,                   -- [{leg_index, filled_price, fill_time}]
    greeks_at_entry         JSONB,                   -- {delta, gamma, vega, theta, rho}
    margin_requirement_est  NUMERIC(12,2),
    max_loss                NUMERIC(12,2),
    max_profit              NUMERIC(12,2),
    execution_mode          VARCHAR(20) NOT NULL DEFAULT 'SHADOW_PAPER'
                            CHECK (execution_mode = 'SHADOW_PAPER'),
    order_submitted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    order_filled_at         TIMESTAMPTZ,
    roundtrip_ms            INTEGER,
    slippage_bps            NUMERIC(8,2),
    source_hypothesis_id    UUID,
    source_agent            VARCHAR(30) NOT NULL DEFAULT 'STIG_OPTIONS_SHADOW',
    entry_regime            VARCHAR(30),
    defcon_at_entry         VARCHAR(20),
    lineage_hash            VARCHAR(64),
    chain_hash              VARCHAR(64),
    status                  VARCHAR(20) NOT NULL DEFAULT 'SUBMITTED'
                            CHECK (status IN ('SUBMITTED', 'FILLED', 'PARTIAL', 'CANCELLED', 'REJECTED')),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_oso_underlying ON fhq_execution.options_shadow_orders (underlying);
CREATE INDEX IF NOT EXISTS idx_oso_strategy   ON fhq_execution.options_shadow_orders (strategy_type);
CREATE INDEX IF NOT EXISTS idx_oso_status     ON fhq_execution.options_shadow_orders (status);
CREATE INDEX IF NOT EXISTS idx_oso_created    ON fhq_execution.options_shadow_orders (created_at);

COMMENT ON TABLE fhq_execution.options_shadow_orders IS
    'IoS-012-C: Shadow paper orders for options. execution_mode locked to SHADOW_PAPER via CHECK.';

-- ============================================================================
-- C. fhq_execution: Options Shadow Positions
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhq_execution.options_shadow_positions (
    position_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_ref            VARCHAR(60) NOT NULL UNIQUE,
    order_id                UUID NOT NULL REFERENCES fhq_execution.options_shadow_orders(order_id),
    underlying              VARCHAR(20) NOT NULL,
    strategy_type           VARCHAR(30) NOT NULL,
    position_delta          NUMERIC(10,6),
    position_gamma          NUMERIC(10,6),
    position_vega           NUMERIC(10,6),
    position_theta          NUMERIC(10,6),
    dte_remaining           INTEGER,
    theta_decay_daily       NUMERIC(10,4),
    assignment_probability  NUMERIC(6,4),
    unrealized_pnl          NUMERIC(12,4),
    status                  VARCHAR(20) NOT NULL DEFAULT 'OPEN'
                            CHECK (status IN ('OPEN', 'CLOSED', 'ROLLED', 'ASSIGNED', 'EXPIRED')),
    opened_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at               TIMESTAMPTZ,
    last_greeks_update      TIMESTAMPTZ,
    content_hash            VARCHAR(64),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_osp_status ON fhq_execution.options_shadow_positions (status);
CREATE INDEX IF NOT EXISTS idx_osp_underlying ON fhq_execution.options_shadow_positions (underlying);

COMMENT ON TABLE fhq_execution.options_shadow_positions IS
    'IoS-012-C: Open/closed shadow positions with aggregate Greeks and DTE tracking.';

-- ============================================================================
-- D. fhq_execution: Options Shadow Outcomes
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhq_execution.options_shadow_outcomes (
    outcome_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id             UUID NOT NULL REFERENCES fhq_execution.options_shadow_positions(position_id),
    order_id                UUID NOT NULL REFERENCES fhq_execution.options_shadow_orders(order_id),
    realized_pnl            NUMERIC(12,4) NOT NULL,
    realized_return_pct     NUMERIC(8,4),
    theta_pnl               NUMERIC(12,4),
    delta_pnl               NUMERIC(12,4),
    gamma_pnl               NUMERIC(12,4),
    vega_pnl                NUMERIC(12,4),
    exit_reason             VARCHAR(40) NOT NULL,
    exit_dte                INTEGER,
    holding_period_days     INTEGER,
    entry_iv                NUMERIC(10,6),
    exit_iv                 NUMERIC(10,6),
    entry_regime            VARCHAR(30),
    exit_regime             VARCHAR(30),
    content_hash            VARCHAR(64),
    chain_hash              VARCHAR(64),
    closed_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_osout_closed ON fhq_execution.options_shadow_outcomes (closed_at);
CREATE INDEX IF NOT EXISTS idx_osout_reason ON fhq_execution.options_shadow_outcomes (exit_reason);

COMMENT ON TABLE fhq_execution.options_shadow_outcomes IS
    'IoS-012-C: Closed options outcomes with Greeks-attributed P&L decomposition. ADR-013 chain-hashed.';

-- ============================================================================
-- E. fhq_execution: Options Latency Log
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhq_execution.options_latency_log (
    log_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id        UUID REFERENCES fhq_execution.options_shadow_orders(order_id),
    roundtrip_ms    INTEGER NOT NULL,
    threshold_ms    INTEGER NOT NULL DEFAULT 500,
    breach          BOOLEAN NOT NULL DEFAULT FALSE,
    action_taken    VARCHAR(40),
    logged_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_oll_breach ON fhq_execution.options_latency_log (breach) WHERE breach = TRUE;

COMMENT ON TABLE fhq_execution.options_latency_log IS
    'IoS-012-C: MiFID II Art.17 roundtrip latency measurements. Breaches trigger halt.';

-- ============================================================================
-- F. fhq_learning: Options Hypothesis Canon
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhq_learning.options_hypothesis_canon (
    hypothesis_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_type       VARCHAR(30) NOT NULL CHECK (strategy_type IN (
                            'CASH_SECURED_PUT', 'COVERED_CALL', 'VERTICAL_SPREAD',
                            'IRON_CONDOR', 'PROTECTIVE_PUT'
                        )),
    underlying          VARCHAR(20) NOT NULL,
    regime_condition    JSONB,           -- {regime_type, regime_state, ...}
    iv_rank_condition   JSONB,           -- {min_iv_rank, max_iv_rank, ...}
    dte_range           INT4RANGE,       -- [min_dte, max_dte)
    strikes             JSONB,           -- [{strike, option_type}]
    expirations         JSONB,           -- [expiration_date, ...]
    greeks_snapshot     JSONB,           -- {delta, gamma, vega, theta}
    source              VARCHAR(30) NOT NULL CHECK (source != 'ACI_DIRECT'),
    status              VARCHAR(20) NOT NULL DEFAULT 'CANDIDATE'
                        CHECK (status IN ('CANDIDATE', 'EXPERIMENT', 'PROMOTED', 'FALSIFIED', 'ARCHIVED')),
    rationale           TEXT,
    lineage_hash        VARCHAR(64),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ohc_strategy ON fhq_learning.options_hypothesis_canon (strategy_type);
CREATE INDEX IF NOT EXISTS idx_ohc_underlying ON fhq_learning.options_hypothesis_canon (underlying);
CREATE INDEX IF NOT EXISTS idx_ohc_status ON fhq_learning.options_hypothesis_canon (status);

COMMENT ON TABLE fhq_learning.options_hypothesis_canon IS
    'IoS-012-C: Options-specific hypotheses. source CHECK prevents ACI_DIRECT (MIT Quad invariant).';

-- ============================================================================
-- G. fhq_learning: Options Volatility Surface
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhq_learning.options_volatility_surface (
    surface_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    underlying          VARCHAR(20) NOT NULL,
    snapshot_date       DATE NOT NULL,
    expiration_date     DATE NOT NULL,
    strike              NUMERIC(12,4) NOT NULL,
    option_type         VARCHAR(4) NOT NULL CHECK (option_type IN ('CALL', 'PUT')),
    implied_volatility  NUMERIC(10,6),
    delta               NUMERIC(10,6),
    gamma               NUMERIC(10,6),
    vega                NUMERIC(10,6),
    theta               NUMERIC(10,6),
    iv_rank             NUMERIC(6,4),
    iv_percentile       NUMERIC(6,4),
    content_hash        VARCHAR(64),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ovs_underlying_date
    ON fhq_learning.options_volatility_surface (underlying, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_ovs_expiration
    ON fhq_learning.options_volatility_surface (expiration_date);

COMMENT ON TABLE fhq_learning.options_volatility_surface IS
    'IoS-012-C: IV surface snapshots by underlying/expiration/strike. Used for IV rank/percentile.';

-- ============================================================================
-- H. fhq_monitoring: Options Risk Monitor
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhq_monitoring.options_risk_monitor (
    monitor_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    portfolio_delta         NUMERIC(12,4),
    portfolio_gamma         NUMERIC(12,4),
    portfolio_vega          NUMERIC(12,4),
    portfolio_theta         NUMERIC(12,4),
    max_loss_estimate       NUMERIC(12,2),
    margin_utilized_pct     NUMERIC(6,2),
    positions_count         INTEGER NOT NULL DEFAULT 0,
    strategies_active       JSONB,              -- {"VERTICAL_SPREAD": 2, "IRON_CONDOR": 1, ...}
    defcon_level_at_snapshot VARCHAR(20),
    content_hash            VARCHAR(64),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orm_snapshot ON fhq_monitoring.options_risk_monitor (snapshot_at);

COMMENT ON TABLE fhq_monitoring.options_risk_monitor IS
    'IoS-012-C: Real-time aggregate portfolio Greeks exposure. DEFCON-integrated.';

-- ============================================================================
-- Migration metadata
-- ============================================================================
INSERT INTO fhq_monitoring.run_ledger (
    task_name, started_at, finished_at, exit_code, error_excerpt
) VALUES (
    'MIGRATION_350_OPTIONS_TRADING_INFRASTRUCTURE',
    NOW(), NOW(), 0,
    'IoS-012-C: 8 tables (5 execution, 2 learning, 1 monitoring). CEO-DIR-2026-OPS-AUTONOMY-001 G1.'
);

COMMIT;
