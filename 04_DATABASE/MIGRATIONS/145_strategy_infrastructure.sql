-- ============================================================
-- Migration 145: Strategy Infrastructure (STIG-2025-001)
-- ============================================================
-- Authority: STIG (CTO)
-- ADR Reference: STIG-2025-001 Directive
-- Classification: Phase 1 Foundation
--
-- Components:
--   1. Circuit Breaker Events Table
--   2. Signal Cohesion Log Table
--   3. Kelly Sizing Log Table
--   4. Correlation Matrix Table
--   5. Strategy Performance Tracking
-- ============================================================

BEGIN;

-- Verify governance compliance
DO $$
BEGIN
    RAISE NOTICE '[145] Starting Strategy Infrastructure Migration';
    RAISE NOTICE '[145] Authority: STIG-2025-001 Directive';
END $$;

-- ============================================================
-- 1. CIRCUIT BREAKER EVENTS (ADR-016 DEFCON Integration)
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_monitoring.circuit_breaker_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    breaker_name    TEXT NOT NULL,
    from_state      TEXT NOT NULL,      -- CLOSED, OPEN, HALF_OPEN
    to_state        TEXT NOT NULL,
    reason          TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cb_events_breaker_name
    ON fhq_monitoring.circuit_breaker_events(breaker_name);
CREATE INDEX IF NOT EXISTS idx_cb_events_created
    ON fhq_monitoring.circuit_breaker_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cb_events_state
    ON fhq_monitoring.circuit_breaker_events(to_state);

COMMENT ON TABLE fhq_monitoring.circuit_breaker_events IS
    'Circuit breaker state transitions per STIG-2025-001. Tracks CLOSED/OPEN/HALF_OPEN states.';

-- ============================================================
-- 2. SIGNAL COHESION LOG (Anti-Diworsification)
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.signal_cohesion_log (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id                TEXT NOT NULL,
    decision                TEXT NOT NULL,  -- APPROVED_DIVERSIFYING, APPROVED_SIZE_REDUCED, REJECTED_REDUNDANT
    avg_correlation         DOUBLE PRECISION,
    max_correlation         DOUBLE PRECISION,
    max_correlated_asset    TEXT,
    size_multiplier         DOUBLE PRECISION DEFAULT 1.0,
    correlation_matrix      JSONB DEFAULT '{}',
    checked_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cohesion_asset
    ON fhq_alpha.signal_cohesion_log(asset_id);
CREATE INDEX IF NOT EXISTS idx_cohesion_decision
    ON fhq_alpha.signal_cohesion_log(decision);
CREATE INDEX IF NOT EXISTS idx_cohesion_checked
    ON fhq_alpha.signal_cohesion_log(checked_at DESC);

COMMENT ON TABLE fhq_alpha.signal_cohesion_log IS
    'Signal cohesion checks per STIG-2025-001. Prevents portfolio diworsification.';

-- ============================================================
-- 3. KELLY SIZING LOG (Probabilistic Position Sizing)
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.kelly_sizing_log (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id                TEXT NOT NULL,
    sharpe                  DOUBLE PRECISION,
    confidence              DOUBLE PRECISION,
    kelly_fraction          DOUBLE PRECISION,   -- Raw Kelly f*
    recommended_fraction    DOUBLE PRECISION,   -- After adjustments
    position_category       TEXT,               -- SKIP, MINIMAL, SMALL, MEDIUM, LARGE
    dollar_amount           DOUBLE PRECISION,
    win_probability         DOUBLE PRECISION,
    metadata                JSONB DEFAULT '{}',
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kelly_asset
    ON fhq_alpha.kelly_sizing_log(asset_id);
CREATE INDEX IF NOT EXISTS idx_kelly_category
    ON fhq_alpha.kelly_sizing_log(position_category);
CREATE INDEX IF NOT EXISTS idx_kelly_created
    ON fhq_alpha.kelly_sizing_log(created_at DESC);

COMMENT ON TABLE fhq_alpha.kelly_sizing_log IS
    'Kelly Criterion position sizing per STIG-2025-001. Bayesian position sizing for low-Sharpe signals.';

-- ============================================================
-- 4. CORRELATION MATRIX (Rolling 30-day)
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.correlation_matrix (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_a         TEXT NOT NULL,
    asset_b         TEXT NOT NULL,
    correlation     DOUBLE PRECISION NOT NULL,
    lookback_days   INTEGER DEFAULT 30,
    calculated_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(asset_a, asset_b, lookback_days)
);

CREATE INDEX IF NOT EXISTS idx_corr_asset_a
    ON fhq_alpha.correlation_matrix(asset_a);
CREATE INDEX IF NOT EXISTS idx_corr_asset_b
    ON fhq_alpha.correlation_matrix(asset_b);
CREATE INDEX IF NOT EXISTS idx_corr_calculated
    ON fhq_alpha.correlation_matrix(calculated_at DESC);

COMMENT ON TABLE fhq_alpha.correlation_matrix IS
    'Asset correlation matrix for signal cohesion checks. Rolling 30-day Pearson correlations.';

-- ============================================================
-- 5. STRATEGY PERFORMANCE TRACKING
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.strategy_performance (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_name       TEXT NOT NULL,          -- statarb, grid, meanrev, volatility
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    trades_count        INTEGER DEFAULT 0,
    win_count           INTEGER DEFAULT 0,
    loss_count          INTEGER DEFAULT 0,
    total_pnl           DOUBLE PRECISION DEFAULT 0,
    realized_pnl        DOUBLE PRECISION DEFAULT 0,
    unrealized_pnl      DOUBLE PRECISION DEFAULT 0,
    sharpe_ratio        DOUBLE PRECISION,
    max_drawdown        DOUBLE PRECISION,
    win_rate            DOUBLE PRECISION,
    avg_win             DOUBLE PRECISION,
    avg_loss            DOUBLE PRECISION,
    profit_factor       DOUBLE PRECISION,
    calmar_ratio        DOUBLE PRECISION,
    metadata            JSONB DEFAULT '{}',
    calculated_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(strategy_name, period_start, period_end)
);

CREATE INDEX IF NOT EXISTS idx_strategy_perf_name
    ON fhq_alpha.strategy_performance(strategy_name);
CREATE INDEX IF NOT EXISTS idx_strategy_perf_period
    ON fhq_alpha.strategy_performance(period_end DESC);

COMMENT ON TABLE fhq_alpha.strategy_performance IS
    'Strategy performance metrics for multi-strategy orchestration. Per STIG-2025-001 Phase 2.';

-- ============================================================
-- 6. DEFCON STATUS TABLE (if not exists)
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_monitoring.defcon_status (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    current_level   TEXT NOT NULL DEFAULT 'GREEN',  -- GREEN, BLUE, YELLOW, ORANGE, RED
    trigger_reason  TEXT,
    triggered_by    TEXT,
    metadata        JSONB DEFAULT '{}',
    activated_at    TIMESTAMPTZ DEFAULT NOW(),
    deactivated_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_defcon_level
    ON fhq_monitoring.defcon_status(current_level);
CREATE INDEX IF NOT EXISTS idx_defcon_activated
    ON fhq_monitoring.defcon_status(activated_at DESC);

-- Insert default GREEN status if none exists
INSERT INTO fhq_monitoring.defcon_status (current_level, trigger_reason, triggered_by)
SELECT 'GREEN', 'System initialization', 'STIG'
WHERE NOT EXISTS (SELECT 1 FROM fhq_monitoring.defcon_status);

COMMENT ON TABLE fhq_monitoring.defcon_status IS
    'DEFCON status per ADR-016. Controls circuit breaker behavior.';

-- ============================================================
-- 7. IoS-022 REGISTRATION SKIPPED (content_hash required)
-- ============================================================
-- IoS-022 Signal Cohesion Engine registration will be done
-- via proper governance workflow with content_hash generation

-- Tables created are self-documenting via COMMENT statements

COMMIT;

-- ============================================================
-- VERIFICATION QUERIES
-- ============================================================

DO $$
DECLARE
    v_count INTEGER;
BEGIN
    -- Verify tables exist
    SELECT COUNT(*) INTO v_count
    FROM information_schema.tables
    WHERE table_schema IN ('fhq_monitoring', 'fhq_alpha')
      AND table_name IN (
          'circuit_breaker_events',
          'signal_cohesion_log',
          'kelly_sizing_log',
          'correlation_matrix',
          'strategy_performance',
          'defcon_status'
      );

    IF v_count >= 5 THEN
        RAISE NOTICE '[145] SUCCESS: Strategy Infrastructure tables created (% tables)', v_count;
    ELSE
        RAISE WARNING '[145] INCOMPLETE: Only % tables found', v_count;
    END IF;
END $$;

-- Show table summary
SELECT
    table_schema,
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns c
     WHERE c.table_schema = t.table_schema AND c.table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema IN ('fhq_monitoring', 'fhq_alpha')
  AND table_name IN (
      'circuit_breaker_events',
      'signal_cohesion_log',
      'kelly_sizing_log',
      'correlation_matrix',
      'strategy_performance',
      'defcon_status'
  )
ORDER BY table_schema, table_name;
