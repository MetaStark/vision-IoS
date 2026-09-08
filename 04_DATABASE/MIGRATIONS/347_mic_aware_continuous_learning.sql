-- Migration 347: MIC-Aware Continuous Learning
-- CEO-DIR-2026-CRYPTO-LEARNING-ACTIVATION-001
-- Eliminates Weekend Blindness via Market-Structure-Aware Learning
--
-- GOVERNING AUTHORITIES: ADR-014, ADR-011, IoS-001, IoS-005, IoS-010
-- EXECUTOR: STIG (EC-003)
-- CLASSIFICATION: STRATEGIC-CRITICAL

-- =============================================================================
-- SECTION 1: EXTEND EXCHANGES TABLE WITH MIC-AWARE SCHEDULING
-- =============================================================================

-- Add continuous market and session columns
ALTER TABLE fhq_meta.exchanges
ADD COLUMN IF NOT EXISTS is_continuous BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS open_time TIME,
ADD COLUMN IF NOT EXISTS close_time TIME,
ADD COLUMN IF NOT EXISTS trading_days INTEGER[] DEFAULT ARRAY[1,2,3,4,5], -- Mon-Fri by default
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

COMMENT ON COLUMN fhq_meta.exchanges.is_continuous IS 'TRUE = 24/7 market (crypto, forex), FALSE = session-bound';
COMMENT ON COLUMN fhq_meta.exchanges.open_time IS 'Market open time in exchange timezone';
COMMENT ON COLUMN fhq_meta.exchanges.close_time IS 'Market close time in exchange timezone';
COMMENT ON COLUMN fhq_meta.exchanges.trading_days IS 'ISO weekdays (1=Mon, 7=Sun) when market is open';

-- =============================================================================
-- SECTION 2: POPULATE MIC-AWARE SCHEDULING DATA
-- =============================================================================

-- CRYPTO: Continuous 24/7
UPDATE fhq_meta.exchanges SET
    is_continuous = TRUE,
    open_time = '00:00:00',
    close_time = '23:59:59',
    trading_days = ARRAY[1,2,3,4,5,6,7],
    updated_at = NOW()
WHERE mic = 'XCRYPTO';

-- BINANCE: Add if not exists, continuous 24/7
INSERT INTO fhq_meta.exchanges (mic, exchange_name, country_code, timezone, currency, is_continuous, open_time, close_time, trading_days)
VALUES ('BINANCE', 'Binance Exchange', 'MT', 'UTC', 'USD', TRUE, '00:00:00', '23:59:59', ARRAY[1,2,3,4,5,6,7])
ON CONFLICT (mic) DO UPDATE SET
    is_continuous = TRUE,
    open_time = '00:00:00',
    close_time = '23:59:59',
    trading_days = ARRAY[1,2,3,4,5,6,7],
    updated_at = NOW();

-- FOREX: Continuous Mon-Fri
UPDATE fhq_meta.exchanges SET
    is_continuous = TRUE,
    open_time = '00:00:00',
    close_time = '23:59:59',
    trading_days = ARRAY[1,2,3,4,5], -- Mon-Fri only
    updated_at = NOW()
WHERE mic = 'XFOREX';

-- NYSE: Session-bound
UPDATE fhq_meta.exchanges SET
    is_continuous = FALSE,
    open_time = '09:30:00',
    close_time = '16:00:00',
    trading_days = ARRAY[1,2,3,4,5],
    updated_at = NOW()
WHERE mic = 'XNYS';

-- NASDAQ: Session-bound
UPDATE fhq_meta.exchanges SET
    is_continuous = FALSE,
    open_time = '09:30:00',
    close_time = '16:00:00',
    trading_days = ARRAY[1,2,3,4,5],
    updated_at = NOW()
WHERE mic = 'XNAS';

-- Oslo: Session-bound
UPDATE fhq_meta.exchanges SET
    is_continuous = FALSE,
    open_time = '09:00:00',
    close_time = '16:30:00',
    trading_days = ARRAY[1,2,3,4,5],
    updated_at = NOW()
WHERE mic = 'XOSL';

-- =============================================================================
-- SECTION 3: CREATE MIC-AWARE SESSION FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION fhq_meta.fn_is_market_open(
    p_mic TEXT,
    p_check_time TIMESTAMPTZ DEFAULT NOW()
) RETURNS BOOLEAN
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_exchange RECORD;
    v_local_time TIME;
    v_local_dow INTEGER;
BEGIN
    -- Get exchange info
    SELECT * INTO v_exchange
    FROM fhq_meta.exchanges
    WHERE mic = p_mic;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- Continuous markets are always open (if trading day)
    IF v_exchange.is_continuous THEN
        -- Convert to exchange timezone and get day of week
        v_local_dow := EXTRACT(ISODOW FROM p_check_time AT TIME ZONE v_exchange.timezone);
        RETURN v_local_dow = ANY(v_exchange.trading_days);
    END IF;

    -- Session-bound markets
    v_local_time := (p_check_time AT TIME ZONE v_exchange.timezone)::TIME;
    v_local_dow := EXTRACT(ISODOW FROM p_check_time AT TIME ZONE v_exchange.timezone);

    RETURN v_local_dow = ANY(v_exchange.trading_days)
       AND v_local_time >= v_exchange.open_time
       AND v_local_time <= v_exchange.close_time;
END;
$$;

COMMENT ON FUNCTION fhq_meta.fn_is_market_open IS 'CEO-DIR-2026-CRYPTO-LEARNING: MIC-aware market session check';

-- =============================================================================
-- SECTION 4: CREATE ASSET-TO-MIC MAPPING VIEW
-- =============================================================================

CREATE OR REPLACE VIEW fhq_meta.v_asset_market_status AS
SELECT
    a.symbol,
    a.asset_type,
    CASE
        WHEN a.asset_type ILIKE '%crypto%' THEN 'XCRYPTO'
        WHEN a.asset_type ILIKE '%forex%' OR a.asset_type ILIKE '%fx%' THEN 'XFOREX'
        WHEN a.symbol LIKE '%.OL' THEN 'XOSL'
        ELSE 'XNYS'
    END as inferred_mic,
    fhq_meta.fn_is_market_open(
        CASE
            WHEN a.asset_type ILIKE '%crypto%' THEN 'XCRYPTO'
            WHEN a.asset_type ILIKE '%forex%' OR a.asset_type ILIKE '%fx%' THEN 'XFOREX'
            WHEN a.symbol LIKE '%.OL' THEN 'XOSL'
            ELSE 'XNYS'
        END
    ) as is_market_open,
    e.is_continuous,
    e.trading_days
FROM fhq_meta.assets a
LEFT JOIN fhq_meta.exchanges e ON e.mic = CASE
    WHEN a.asset_type ILIKE '%crypto%' THEN 'XCRYPTO'
    WHEN a.asset_type ILIKE '%forex%' OR a.asset_type ILIKE '%fx%' THEN 'XFOREX'
    WHEN a.symbol LIKE '%.OL' THEN 'XOSL'
    ELSE 'XNYS'
END;

-- =============================================================================
-- SECTION 5: CREATE LEARNING ELIGIBILITY FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION fhq_learning.fn_get_learnable_asset_classes()
RETURNS TABLE (
    asset_class TEXT,
    mic TEXT,
    is_learnable BOOLEAN,
    reason TEXT
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT
        'CRYPTO'::TEXT as asset_class,
        'XCRYPTO'::TEXT as mic,
        fhq_meta.fn_is_market_open('XCRYPTO') as is_learnable,
        CASE
            WHEN fhq_meta.fn_is_market_open('XCRYPTO') THEN 'Crypto market is 24/7 - learning enabled'
            ELSE 'Crypto market closed (should never happen)'
        END as reason
    UNION ALL
    SELECT
        'US_EQUITY'::TEXT,
        'XNYS'::TEXT,
        fhq_meta.fn_is_market_open('XNYS'),
        CASE
            WHEN fhq_meta.fn_is_market_open('XNYS') THEN 'NYSE open - learning enabled'
            ELSE 'NYSE closed - equity learning paused'
        END
    UNION ALL
    SELECT
        'FOREX'::TEXT,
        'XFOREX'::TEXT,
        fhq_meta.fn_is_market_open('XFOREX'),
        CASE
            WHEN fhq_meta.fn_is_market_open('XFOREX') THEN 'Forex market open - learning enabled'
            ELSE 'Forex market closed (weekend)'
        END;
END;
$$;

-- =============================================================================
-- SECTION 6: REGISTER CRYPTO ASSETS FOR LEARNING
-- =============================================================================

-- Ensure BTC and ETH are registered with correct asset_type
UPDATE fhq_meta.assets SET
    asset_type = 'CRYPTO',
    updated_at = NOW()
WHERE symbol IN ('BTC-USD', 'ETH-USD', 'BTCUSD', 'ETHUSD')
  AND (asset_type IS NULL OR asset_type != 'CRYPTO');

-- Insert if not exists
INSERT INTO fhq_meta.assets (symbol, asset_type, is_tradeable, data_vendor, created_at)
VALUES
    ('BTC-USD', 'CRYPTO', TRUE, 'BINANCE', NOW()),
    ('ETH-USD', 'CRYPTO', TRUE, 'BINANCE', NOW())
ON CONFLICT (symbol) DO UPDATE SET
    asset_type = 'CRYPTO',
    data_vendor = 'BINANCE',
    updated_at = NOW();

-- =============================================================================
-- SECTION 7: CREATE CRYPTO LEARNING DAEMON REGISTRATION
-- =============================================================================

INSERT INTO fhq_monitoring.daemon_health (daemon_name, status, last_heartbeat, expected_interval_minutes, is_critical, metadata)
VALUES (
    'finn_crypto_scheduler',
    'PENDING',
    NOW(),
    30,
    TRUE,
    jsonb_build_object(
        'owner', 'FINN',
        'schedule', '*/30 * * * *',
        'asset_class', 'CRYPTO',
        'mic', 'XCRYPTO',
        'directive', 'CEO-DIR-2026-CRYPTO-LEARNING-ACTIVATION-001'
    )
)
ON CONFLICT (daemon_name) DO UPDATE SET
    metadata = jsonb_build_object(
        'owner', 'FINN',
        'schedule', '*/30 * * * *',
        'asset_class', 'CRYPTO',
        'mic', 'XCRYPTO',
        'directive', 'CEO-DIR-2026-CRYPTO-LEARNING-ACTIVATION-001'
    ),
    updated_at = NOW();

-- =============================================================================
-- SECTION 8: VERIFICATION QUERIES
-- =============================================================================

-- Verify MIC-aware scheduling
DO $$
DECLARE
    v_crypto_open BOOLEAN;
    v_equity_open BOOLEAN;
BEGIN
    SELECT fhq_meta.fn_is_market_open('XCRYPTO') INTO v_crypto_open;
    SELECT fhq_meta.fn_is_market_open('XNYS') INTO v_equity_open;

    RAISE NOTICE 'MIC-Aware Scheduling Verification:';
    RAISE NOTICE '  XCRYPTO (24/7): %', CASE WHEN v_crypto_open THEN 'OPEN' ELSE 'CLOSED' END;
    RAISE NOTICE '  XNYS (Session): %', CASE WHEN v_equity_open THEN 'OPEN' ELSE 'CLOSED' END;

    -- Crypto should ALWAYS be open
    IF NOT v_crypto_open THEN
        RAISE EXCEPTION 'CRITICAL: Crypto market showing as closed - MIC configuration error';
    END IF;
END;
$$;

-- =============================================================================
-- MIGRATION COMPLETE
-- =============================================================================
-- CEO-DIR-2026-CRYPTO-LEARNING-ACTIVATION-001
-- Weekend Blindness Eliminated
-- MIC-Aware Continuous Learning Activated
