-- =============================================================================
-- CEO-DIR-2026-082: ROI Direction Ledger (EQUITY) - Canonical Economic Truth
-- =============================================================================
--
-- STIG CTO Migration: Creates the canonical economic truth ledger for
-- STRESS inversion alpha measurement in EQUITY asset class only.
--
-- Dependencies: CEO-DIR-2026-080 (G4 Approved), CEO-DIR-2026-081 (Schema Freeze)
-- Authority: CEO Directive - G4 Constitutional Activation
--
-- CONSTRAINTS:
--   - NO GREEKS. NO IV. NO STRATEGY. NO PNL.
--   - EQUITY ONLY (hard-coded check constraint)
--   - Confidence >= 99% (inversion threshold)
--   - Append-only by design
--
-- Single Question Answered:
--   "When the system said 'this is catastrophically wrong', was the market
--    directionally exploitable?"
-- =============================================================================

BEGIN;

-- =============================================================================
-- SECTION 1: Core ROI Direction Ledger Table
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.roi_direction_ledger_equity (
    -- Identity Fields
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker VARCHAR(20) NOT NULL,
    asset_class VARCHAR(10) NOT NULL DEFAULT 'EQUITY'
        CHECK (asset_class = 'EQUITY'),  -- HARD CONSTRAINT: No contamination
    signal_timestamp TIMESTAMPTZ NOT NULL,
    reference_epoch_id VARCHAR(50) NOT NULL DEFAULT 'EPOCH-001',

    -- Signal Truth Fields
    original_prediction VARCHAR(20) NOT NULL DEFAULT 'STRESS',
    confidence DECIMAL(6,4) NOT NULL CHECK (confidence >= 0.99),  -- Must be >= 99%
    inversion_direction VARCHAR(20) NOT NULL DEFAULT 'CONTRARIAN_DOWN',
    forecast_id UUID,  -- Link to original forecast

    -- Market Truth Fields (t0 = signal generation moment)
    price_t0 DECIMAL(18,6) NOT NULL,
    price_t0_plus_1d DECIMAL(18,6),  -- NULL until captured
    price_t0_plus_3d DECIMAL(18,6),  -- NULL until captured
    price_t0_plus_5d DECIMAL(18,6),  -- NULL until captured

    -- Computed Return Fields
    return_1d DECIMAL(10,6) GENERATED ALWAYS AS (
        CASE WHEN price_t0_plus_1d IS NOT NULL AND price_t0 > 0
             THEN (price_t0_plus_1d - price_t0) / price_t0
             ELSE NULL END
    ) STORED,
    return_3d DECIMAL(10,6) GENERATED ALWAYS AS (
        CASE WHEN price_t0_plus_3d IS NOT NULL AND price_t0 > 0
             THEN (price_t0_plus_3d - price_t0) / price_t0
             ELSE NULL END
    ) STORED,
    return_5d DECIMAL(10,6) GENERATED ALWAYS AS (
        CASE WHEN price_t0_plus_5d IS NOT NULL AND price_t0 > 0
             THEN (price_t0_plus_5d - price_t0) / price_t0
             ELSE NULL END
    ) STORED,

    -- Computed Direction Correctness (CONTRARIAN_DOWN = price should drop)
    -- Note: Cannot reference generated columns, so compute from price directly
    correct_direction_1d BOOLEAN GENERATED ALWAYS AS (
        CASE WHEN price_t0_plus_1d IS NOT NULL AND price_t0 > 0
             THEN price_t0_plus_1d < price_t0
             ELSE NULL END
    ) STORED,
    correct_direction_3d BOOLEAN GENERATED ALWAYS AS (
        CASE WHEN price_t0_plus_3d IS NOT NULL AND price_t0 > 0
             THEN price_t0_plus_3d < price_t0
             ELSE NULL END
    ) STORED,
    correct_direction_5d BOOLEAN GENERATED ALWAYS AS (
        CASE WHEN price_t0_plus_5d IS NOT NULL AND price_t0 > 0
             THEN price_t0_plus_5d < price_t0
             ELSE NULL END
    ) STORED,

    -- Quality Control Fields
    inverted_brier_at_event DECIMAL(10,6) NOT NULL,
    anomaly_flag BOOLEAN DEFAULT FALSE,
    kill_switch_state_at_event VARCHAR(20) DEFAULT 'ARMED',

    -- Audit Fields
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(50) DEFAULT 'SYSTEM',

    -- Lineage
    evidence_hash VARCHAR(64),

    -- Ensure uniqueness per ticker/timestamp
    UNIQUE(ticker, signal_timestamp)
);

-- =============================================================================
-- SECTION 2: Derived Metrics View - Daily EV Line
-- =============================================================================

CREATE OR REPLACE VIEW fhq_research.roi_direction_equity_daily_ev AS
SELECT
    DATE(signal_timestamp) as signal_date,
    COUNT(*) as events_count,

    -- Hit Rates
    AVG(CASE WHEN correct_direction_1d THEN 1.0 ELSE 0.0 END) as hit_rate_1d,
    AVG(CASE WHEN correct_direction_3d THEN 1.0 ELSE 0.0 END) as hit_rate_3d,
    AVG(CASE WHEN correct_direction_5d THEN 1.0 ELSE 0.0 END) as hit_rate_5d,

    -- Average Returns
    AVG(return_1d) as avg_return_1d,
    AVG(return_3d) as avg_return_3d,
    AVG(return_5d) as avg_return_5d,

    -- Edge per Activation (when direction was correct)
    AVG(CASE WHEN correct_direction_1d THEN ABS(return_1d) ELSE NULL END) as edge_per_activation_1d,
    AVG(CASE WHEN correct_direction_3d THEN ABS(return_3d) ELSE NULL END) as edge_per_activation_3d,
    AVG(CASE WHEN correct_direction_5d THEN ABS(return_5d) ELSE NULL END) as edge_per_activation_5d,

    -- Quality
    AVG(inverted_brier_at_event) as avg_inverted_brier,
    SUM(CASE WHEN anomaly_flag THEN 1 ELSE 0 END) as anomaly_count

FROM fhq_research.roi_direction_ledger_equity
WHERE return_1d IS NOT NULL  -- Only completed observations
GROUP BY DATE(signal_timestamp)
ORDER BY signal_date DESC;

-- =============================================================================
-- SECTION 3: Rolling 30-Day Metrics View
-- =============================================================================

CREATE OR REPLACE VIEW fhq_research.roi_direction_equity_rolling_30d AS
SELECT
    DATE(NOW()) as calculation_date,

    -- Sample Size
    COUNT(*) as total_events,
    COUNT(*) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days') as events_30d,

    -- Hit Rates (30-day rolling)
    AVG(CASE WHEN correct_direction_1d THEN 1.0 ELSE 0.0 END)
        FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days') as hit_rate_1d_30d,
    AVG(CASE WHEN correct_direction_3d THEN 1.0 ELSE 0.0 END)
        FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days') as hit_rate_3d_30d,
    AVG(CASE WHEN correct_direction_5d THEN 1.0 ELSE 0.0 END)
        FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days') as hit_rate_5d_30d,

    -- EV Line (30-day rolling)
    AVG(return_1d) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days') as ev_1d_30d,
    AVG(return_3d) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days') as ev_3d_30d,
    AVG(return_5d) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days') as ev_5d_30d,

    -- Edge per Activation (30-day rolling)
    AVG(CASE WHEN correct_direction_1d THEN ABS(return_1d) ELSE NULL END)
        FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days') as edge_per_activation_1d_30d,
    AVG(CASE WHEN correct_direction_3d THEN ABS(return_3d) ELSE NULL END)
        FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days') as edge_per_activation_3d_30d,
    AVG(CASE WHEN correct_direction_5d THEN ABS(return_5d) ELSE NULL END)
        FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days') as edge_per_activation_5d_30d,

    -- Sample Collapse Alert
    CASE WHEN COUNT(*) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days') < 5
         THEN TRUE ELSE FALSE END as sample_collapse_alert,

    -- Quality
    AVG(inverted_brier_at_event) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days')
        as avg_inverted_brier_30d

FROM fhq_research.roi_direction_ledger_equity
WHERE return_1d IS NOT NULL;

-- =============================================================================
-- SECTION 4: Append Function (Immutable Insert)
-- =============================================================================

CREATE OR REPLACE FUNCTION fhq_research.append_roi_direction_event_equity(
    p_ticker VARCHAR(20),
    p_signal_timestamp TIMESTAMPTZ,
    p_confidence DECIMAL(6,4),
    p_price_t0 DECIMAL(18,6),
    p_inverted_brier_at_event DECIMAL(10,6),
    p_forecast_id UUID DEFAULT NULL,
    p_anomaly_flag BOOLEAN DEFAULT FALSE,
    p_kill_switch_state VARCHAR(20) DEFAULT 'ARMED'
)
RETURNS UUID AS $$
DECLARE
    v_event_id UUID;
BEGIN
    -- Validate confidence threshold
    IF p_confidence < 0.99 THEN
        RAISE EXCEPTION 'CEO-DIR-2026-082 VIOLATION: Confidence % must be >= 99%% for STRESS inversion',
            p_confidence;
    END IF;

    -- Insert new event
    INSERT INTO fhq_research.roi_direction_ledger_equity (
        ticker,
        signal_timestamp,
        confidence,
        price_t0,
        inverted_brier_at_event,
        forecast_id,
        anomaly_flag,
        kill_switch_state_at_event,
        created_by,
        evidence_hash
    ) VALUES (
        p_ticker,
        p_signal_timestamp,
        p_confidence,
        p_price_t0,
        p_inverted_brier_at_event,
        p_forecast_id,
        p_anomaly_flag,
        p_kill_switch_state,
        'FINN',
        encode(sha256(
            (p_ticker || p_signal_timestamp::TEXT || p_confidence::TEXT || p_price_t0::TEXT)::bytea
        ), 'hex')
    )
    RETURNING event_id INTO v_event_id;

    RETURN v_event_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SECTION 5: Outcome Capture Function
-- =============================================================================

CREATE OR REPLACE FUNCTION fhq_research.capture_roi_direction_outcome_equity(
    p_event_id UUID,
    p_price_1d DECIMAL(18,6) DEFAULT NULL,
    p_price_3d DECIMAL(18,6) DEFAULT NULL,
    p_price_5d DECIMAL(18,6) DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    UPDATE fhq_research.roi_direction_ledger_equity
    SET
        price_t0_plus_1d = COALESCE(price_t0_plus_1d, p_price_1d),
        price_t0_plus_3d = COALESCE(price_t0_plus_3d, p_price_3d),
        price_t0_plus_5d = COALESCE(price_t0_plus_5d, p_price_5d)
    WHERE event_id = p_event_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SECTION 6: Governance Registration
-- =============================================================================

INSERT INTO fhq_meta.adr_audit_log (
    adr_id,
    event_id,
    review_status,
    detected_by,
    detected_at,
    resolution_notes,
    severity
) VALUES (
    'CEO-DIR-2026-082',
    306,
    'VERIFIED',
    'STIG',
    NOW(),
    'Created fhq_research.roi_direction_ledger_equity - Canonical Economic Truth for STRESS Inversion (EQUITY). Migration 306.',
    'LOW'
);

-- =============================================================================
-- SECTION 7: Indexes for Performance
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_roi_direction_equity_ticker
    ON fhq_research.roi_direction_ledger_equity(ticker);

CREATE INDEX IF NOT EXISTS idx_roi_direction_equity_timestamp
    ON fhq_research.roi_direction_ledger_equity(signal_timestamp);

CREATE INDEX IF NOT EXISTS idx_roi_direction_equity_forecast
    ON fhq_research.roi_direction_ledger_equity(forecast_id)
    WHERE forecast_id IS NOT NULL;

-- =============================================================================
-- SECTION 8: Comments
-- =============================================================================

COMMENT ON TABLE fhq_research.roi_direction_ledger_equity IS
    'CEO-DIR-2026-082: Canonical Economic Truth for STRESS Inversion Alpha (EQUITY ONLY).
     NO GREEKS. NO IV. NO STRATEGY. NO PNL. Direction-only measurement.';

COMMENT ON VIEW fhq_research.roi_direction_equity_daily_ev IS
    'Daily EV Line - Tells you when the weapon dulls';

COMMENT ON VIEW fhq_research.roi_direction_equity_rolling_30d IS
    'Rolling 30-day metrics - Edge per Activation tracking';

COMMIT;

-- =============================================================================
-- END OF MIGRATION: CEO-DIR-2026-082
-- "Alpha speaks first. Instruments listen."
-- =============================================================================
