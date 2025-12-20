-- ============================================================
-- Migration 146: Phase 2 Strategy Engines (STIG-2025-001)
-- ============================================================
-- Authority: STIG (CTO)
-- ADR Reference: STIG-2025-001 Directive Phase 2
-- Classification: Multi-Strategy Alpha Factory
--
-- Components:
--   1. Advanced Regime Log
--   2. Cointegration Pairs (StatArb)
--   3. StatArb Signals
--   4. Grid Configs & Signals
--   5. Mean Reversion Signals
-- ============================================================

BEGIN;

DO $$
BEGIN
    RAISE NOTICE '[146] Starting Phase 2 Strategy Engines Migration';
    RAISE NOTICE '[146] Authority: STIG-2025-001 Directive';
END $$;

-- ============================================================
-- 1. ADVANCED REGIME LOG (IoS-003)
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_perception.advanced_regime_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id            TEXT NOT NULL,
    adx                 DOUBLE PRECISION,
    trend_regime        TEXT,           -- STRONG_TREND, MODERATE_TREND, WEAK_TREND, RANGE_BOUND
    atr                 DOUBLE PRECISION,
    atr_normalized      DOUBLE PRECISION,
    volatility_regime   TEXT,           -- EXTREME, HIGH, NORMAL, LOW
    volatility_shift    DOUBLE PRECISION,
    volume_ratio        DOUBLE PRECISION,
    volume_regime       TEXT,           -- SURGE, HIGH, NORMAL, LOW
    grid_safe           BOOLEAN DEFAULT FALSE,
    statarb_safe        BOOLEAN DEFAULT FALSE,
    breakout_favorable  BOOLEAN DEFAULT FALSE,
    meanrev_favorable   BOOLEAN DEFAULT FALSE,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_regime_log_asset
    ON fhq_perception.advanced_regime_log(asset_id);
CREATE INDEX IF NOT EXISTS idx_regime_log_created
    ON fhq_perception.advanced_regime_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_regime_log_grid_safe
    ON fhq_perception.advanced_regime_log(grid_safe) WHERE grid_safe = true;

COMMENT ON TABLE fhq_perception.advanced_regime_log IS
    '4D Regime classification per STIG-2025-001. f(ADX, ATR, VolShift, Volume)';

-- ============================================================
-- 2. COINTEGRATION PAIRS (StatArb)
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.cointegration_pairs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_a         TEXT NOT NULL,
    asset_b         TEXT NOT NULL,
    is_cointegrated BOOLEAN DEFAULT FALSE,
    p_value         DOUBLE PRECISION,
    hedge_ratio     DOUBLE PRECISION,
    half_life       DOUBLE PRECISION,
    correlation     DOUBLE PRECISION,
    data_points     INTEGER,
    years_tested    DOUBLE PRECISION,
    tested_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(asset_a, asset_b)
);

CREATE INDEX IF NOT EXISTS idx_coint_pairs_a
    ON fhq_alpha.cointegration_pairs(asset_a);
CREATE INDEX IF NOT EXISTS idx_coint_pairs_b
    ON fhq_alpha.cointegration_pairs(asset_b);
CREATE INDEX IF NOT EXISTS idx_coint_pairs_valid
    ON fhq_alpha.cointegration_pairs(is_cointegrated) WHERE is_cointegrated = true;

COMMENT ON TABLE fhq_alpha.cointegration_pairs IS
    'Engle-Granger cointegration test results. 3yr minimum per STIG-2025-001.';

-- ============================================================
-- 3. STATARB SIGNALS
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.statarb_signals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pair_id         TEXT NOT NULL,
    asset_a         TEXT NOT NULL,
    asset_b         TEXT NOT NULL,
    direction       TEXT,               -- LONG_A_SHORT_B, SHORT_A_LONG_B, FLAT
    z_score         DOUBLE PRECISION,
    hedge_ratio     DOUBLE PRECISION,
    confidence      DOUBLE PRECISION,
    kelly_fraction  DOUBLE PRECISION,
    entry_price_a   DOUBLE PRECISION,
    entry_price_b   DOUBLE PRECISION,
    generated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_statarb_pair
    ON fhq_alpha.statarb_signals(pair_id);
CREATE INDEX IF NOT EXISTS idx_statarb_generated
    ON fhq_alpha.statarb_signals(generated_at DESC);

COMMENT ON TABLE fhq_alpha.statarb_signals IS
    'Statistical arbitrage trading signals with z-score entry/exit.';

-- ============================================================
-- 4. GRID CONFIGS
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.grid_configs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id            TEXT NOT NULL UNIQUE,
    center_price        DOUBLE PRECISION,
    grid_levels         INTEGER DEFAULT 10,
    grid_spacing_atr    DOUBLE PRECISION DEFAULT 0.5,
    total_capital       DOUBLE PRECISION,
    quantity_per_level  DOUBLE PRECISION,
    upper_bound         DOUBLE PRECISION,
    lower_bound         DOUBLE PRECISION,
    atr                 DOUBLE PRECISION,
    status              TEXT DEFAULT 'ACTIVE',  -- ACTIVE, PAUSED, DISABLED_*
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_grid_config_asset
    ON fhq_alpha.grid_configs(asset_id);
CREATE INDEX IF NOT EXISTS idx_grid_config_status
    ON fhq_alpha.grid_configs(status);

COMMENT ON TABLE fhq_alpha.grid_configs IS
    'ATR-based grid configurations with regime safety gate.';

-- ============================================================
-- 5. GRID SIGNALS
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.grid_signals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id        TEXT NOT NULL,
    action          TEXT,               -- BUY, SELL, HOLD, CLOSE_ALL, DISABLED
    price           DOUBLE PRECISION,
    quantity        DOUBLE PRECISION,
    level_id        INTEGER,
    reason          TEXT,
    confidence      DOUBLE PRECISION,
    regime_safe     BOOLEAN DEFAULT TRUE,
    generated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_grid_signals_asset
    ON fhq_alpha.grid_signals(asset_id);
CREATE INDEX IF NOT EXISTS idx_grid_signals_generated
    ON fhq_alpha.grid_signals(generated_at DESC);

COMMENT ON TABLE fhq_alpha.grid_signals IS
    'Grid trading signals for level crossings.';

-- ============================================================
-- 6. MEAN REVERSION SIGNALS
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.meanrev_signals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id            TEXT NOT NULL,
    signal_type         TEXT,           -- OVERSOLD, OVERBOUGHT, NEUTRAL
    rsi_daily           DOUBLE PRECISION,
    rsi_4h              DOUBLE PRECISION,
    confluence          TEXT,           -- STRONG, MODERATE, WEAK
    confidence          DOUBLE PRECISION,
    kelly_fraction      DOUBLE PRECISION,
    position_size       DOUBLE PRECISION,
    entry_price         DOUBLE PRECISION,
    stop_loss           DOUBLE PRECISION,
    take_profit         DOUBLE PRECISION,
    regime_favorable    BOOLEAN DEFAULT TRUE,
    generated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_meanrev_asset
    ON fhq_alpha.meanrev_signals(asset_id);
CREATE INDEX IF NOT EXISTS idx_meanrev_generated
    ON fhq_alpha.meanrev_signals(generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_meanrev_type
    ON fhq_alpha.meanrev_signals(signal_type);

COMMENT ON TABLE fhq_alpha.meanrev_signals IS
    'RSI mean reversion signals with Kelly sizing.';

COMMIT;

-- ============================================================
-- VERIFICATION
-- ============================================================

DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM information_schema.tables
    WHERE table_schema IN ('fhq_perception', 'fhq_alpha')
      AND table_name IN (
          'advanced_regime_log',
          'cointegration_pairs',
          'statarb_signals',
          'grid_configs',
          'grid_signals',
          'meanrev_signals'
      );

    IF v_count >= 6 THEN
        RAISE NOTICE '[146] SUCCESS: Phase 2 Strategy Engine tables created (% tables)', v_count;
    ELSE
        RAISE WARNING '[146] INCOMPLETE: Only % tables found', v_count;
    END IF;
END $$;

-- Show table summary
SELECT
    table_schema,
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns c
     WHERE c.table_schema = t.table_schema AND c.table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema IN ('fhq_perception', 'fhq_alpha')
  AND table_name IN (
      'advanced_regime_log',
      'cointegration_pairs',
      'statarb_signals',
      'grid_configs',
      'grid_signals',
      'meanrev_signals'
  )
ORDER BY table_schema, table_name;
