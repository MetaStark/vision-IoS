-- Migration 172: Regime Coverage Sentinels
-- Authority: CEO-DIR-2025-RC-004
-- Purpose: Install monitoring sentinels to prevent future silent regime failures
-- Created: 2025-12-26

-- =============================================================================
-- SENTINEL TABLES
-- =============================================================================

-- Table to log sentinel check results
CREATE TABLE IF NOT EXISTS vision_verification.regime_coverage_sentinel_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    check_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    check_type TEXT NOT NULL, -- 'ASSET_COVERAGE' or 'REGIME_DIVERSITY'
    check_date DATE NOT NULL,

    -- Asset coverage metrics
    asset_count INTEGER,
    asset_threshold INTEGER DEFAULT 400,

    -- Regime diversity metrics
    regime_states_count INTEGER,
    regime_states TEXT[], -- Array of observed states
    dominant_regime TEXT,
    dominant_count INTEGER,
    non_dominant_pct NUMERIC(5,2),
    diversity_threshold NUMERIC(5,2) DEFAULT 15.00,

    -- Status
    status TEXT NOT NULL, -- 'HEALTHY', 'WARNING', 'CRITICAL'
    alert_triggered BOOLEAN DEFAULT FALSE,

    -- Evidence
    evidence_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for efficient lookups
CREATE INDEX IF NOT EXISTS idx_coverage_sentinel_timestamp
ON vision_verification.regime_coverage_sentinel_log(check_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_coverage_sentinel_status
ON vision_verification.regime_coverage_sentinel_log(status, check_timestamp DESC);

-- =============================================================================
-- SENTINEL VIEWS
-- =============================================================================

-- Real-time regime coverage health check
CREATE OR REPLACE VIEW vision_verification.regime_coverage_health AS
WITH latest_regime AS (
    SELECT
        timestamp::date as check_date,
        COUNT(DISTINCT asset_id) as asset_count,
        COUNT(DISTINCT regime_classification) as regime_states_count,
        array_agg(DISTINCT regime_classification ORDER BY regime_classification) as regime_states
    FROM fhq_perception.regime_daily
    WHERE timestamp >= CURRENT_DATE - INTERVAL '1 day'
    GROUP BY timestamp::date
),
regime_distribution AS (
    SELECT
        timestamp::date as check_date,
        regime_classification,
        COUNT(*) as count,
        SUM(COUNT(*)) OVER (PARTITION BY timestamp::date) as total
    FROM fhq_perception.regime_daily
    WHERE timestamp >= CURRENT_DATE - INTERVAL '1 day'
    GROUP BY timestamp::date, regime_classification
),
dominant AS (
    SELECT
        check_date,
        regime_classification as dominant_regime,
        count as dominant_count,
        total,
        ROUND(100.0 * (total - count) / NULLIF(total, 0), 2) as non_dominant_pct,
        ROW_NUMBER() OVER (PARTITION BY check_date ORDER BY count DESC) as rn
    FROM regime_distribution
)
SELECT
    lr.check_date,
    lr.asset_count,
    lr.regime_states_count,
    lr.regime_states,
    d.dominant_regime,
    d.dominant_count,
    d.non_dominant_pct,
    CASE
        WHEN lr.asset_count < 100 THEN 'CRITICAL'
        WHEN lr.asset_count < 400 THEN 'WARNING'
        WHEN d.non_dominant_pct < 15.0 THEN 'CRITICAL'
        WHEN lr.regime_states_count < 3 THEN 'WARNING'
        ELSE 'HEALTHY'
    END as health_status,
    CASE
        WHEN lr.asset_count < 100 THEN 'Asset coverage collapsed below 100'
        WHEN lr.asset_count < 400 THEN 'Asset coverage below threshold (400)'
        WHEN d.non_dominant_pct < 15.0 THEN 'Regime diversity below 15%'
        WHEN lr.regime_states_count < 3 THEN 'Fewer than 3 regime states observed'
        ELSE 'All metrics healthy'
    END as status_reason
FROM latest_regime lr
LEFT JOIN dominant d ON lr.check_date = d.check_date AND d.rn = 1;

-- Historical regime diversity trend
CREATE OR REPLACE VIEW vision_verification.regime_diversity_trend AS
WITH daily_stats AS (
    SELECT
        timestamp::date as date,
        COUNT(DISTINCT asset_id) as asset_count,
        COUNT(DISTINCT regime_classification) as regime_states
    FROM fhq_perception.regime_daily
    WHERE timestamp >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY timestamp::date
),
diversity AS (
    SELECT
        timestamp::date as date,
        regime_classification,
        COUNT(*) as count,
        SUM(COUNT(*)) OVER (PARTITION BY timestamp::date) as total
    FROM fhq_perception.regime_daily
    WHERE timestamp >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY timestamp::date, regime_classification
),
max_regime AS (
    SELECT
        date,
        MAX(count) as dominant_count,
        MAX(total) as total
    FROM diversity
    GROUP BY date
)
SELECT
    ds.date,
    ds.asset_count,
    ds.regime_states,
    mr.dominant_count,
    mr.total as total_classifications,
    ROUND(100.0 * (mr.total - mr.dominant_count) / NULLIF(mr.total, 0), 2) as non_dominant_pct,
    CASE WHEN ROUND(100.0 * (mr.total - mr.dominant_count) / NULLIF(mr.total, 0), 2) >= 15.0
         THEN 'PASS' ELSE 'FAIL' END as diversity_check
FROM daily_stats ds
JOIN max_regime mr ON ds.date = mr.date
ORDER BY ds.date DESC;

-- =============================================================================
-- SENTINEL FUNCTION
-- =============================================================================

-- Function to run sentinel check and log results
CREATE OR REPLACE FUNCTION vision_verification.run_regime_coverage_sentinel()
RETURNS TABLE (
    check_type TEXT,
    status TEXT,
    metric_value NUMERIC,
    threshold NUMERIC,
    alert_needed BOOLEAN
) AS $$
DECLARE
    v_asset_count INTEGER;
    v_regime_states INTEGER;
    v_non_dominant_pct NUMERIC;
    v_dominant_regime TEXT;
    v_dominant_count INTEGER;
    v_regime_states_arr TEXT[];
    v_check_date DATE;
    v_evidence_hash TEXT;
BEGIN
    -- Get latest date with data
    SELECT MAX(timestamp)::date INTO v_check_date
    FROM fhq_perception.regime_daily;

    -- Asset coverage check
    SELECT COUNT(DISTINCT asset_id) INTO v_asset_count
    FROM fhq_perception.regime_daily
    WHERE timestamp::date = v_check_date;

    -- Regime diversity check
    SELECT
        COUNT(DISTINCT regime_classification),
        array_agg(DISTINCT regime_classification ORDER BY regime_classification)
    INTO v_regime_states, v_regime_states_arr
    FROM fhq_perception.regime_daily
    WHERE timestamp::date = v_check_date;

    -- Get dominant regime and non-dominant percentage
    WITH regime_counts AS (
        SELECT
            regime_classification,
            COUNT(*) as cnt,
            SUM(COUNT(*)) OVER () as total
        FROM fhq_perception.regime_daily
        WHERE timestamp::date = v_check_date
        GROUP BY regime_classification
        ORDER BY cnt DESC
        LIMIT 1
    )
    SELECT
        regime_classification,
        cnt,
        ROUND(100.0 * (total - cnt) / NULLIF(total, 0), 2)
    INTO v_dominant_regime, v_dominant_count, v_non_dominant_pct
    FROM regime_counts;

    -- Generate evidence hash
    v_evidence_hash := md5(
        v_check_date::text ||
        v_asset_count::text ||
        v_regime_states::text ||
        COALESCE(v_non_dominant_pct::text, '0')
    );

    -- Log asset coverage check
    INSERT INTO vision_verification.regime_coverage_sentinel_log (
        check_type, check_date, asset_count, asset_threshold,
        status, alert_triggered, evidence_hash
    ) VALUES (
        'ASSET_COVERAGE', v_check_date, v_asset_count, 400,
        CASE WHEN v_asset_count >= 400 THEN 'HEALTHY'
             WHEN v_asset_count >= 100 THEN 'WARNING'
             ELSE 'CRITICAL' END,
        v_asset_count < 100,
        v_evidence_hash
    );

    -- Return asset coverage result
    check_type := 'ASSET_COVERAGE';
    metric_value := v_asset_count;
    threshold := 400;
    status := CASE WHEN v_asset_count >= 400 THEN 'HEALTHY'
                   WHEN v_asset_count >= 100 THEN 'WARNING'
                   ELSE 'CRITICAL' END;
    alert_needed := v_asset_count < 100;
    RETURN NEXT;

    -- Log regime diversity check
    INSERT INTO vision_verification.regime_coverage_sentinel_log (
        check_type, check_date, regime_states_count, regime_states,
        dominant_regime, dominant_count, non_dominant_pct, diversity_threshold,
        status, alert_triggered, evidence_hash
    ) VALUES (
        'REGIME_DIVERSITY', v_check_date, v_regime_states, v_regime_states_arr,
        v_dominant_regime, v_dominant_count, v_non_dominant_pct, 15.00,
        CASE WHEN v_non_dominant_pct >= 15.0 THEN 'HEALTHY'
             WHEN v_non_dominant_pct >= 5.0 THEN 'WARNING'
             ELSE 'CRITICAL' END,
        v_non_dominant_pct < 15.0,
        v_evidence_hash
    );

    -- Return regime diversity result
    check_type := 'REGIME_DIVERSITY';
    metric_value := v_non_dominant_pct;
    threshold := 15.0;
    status := CASE WHEN v_non_dominant_pct >= 15.0 THEN 'HEALTHY'
                   WHEN v_non_dominant_pct >= 5.0 THEN 'WARNING'
                   ELSE 'CRITICAL' END;
    alert_needed := v_non_dominant_pct < 15.0;
    RETURN NEXT;

    -- Return regime states check
    check_type := 'REGIME_STATES';
    metric_value := v_regime_states;
    threshold := 3;
    status := CASE WHEN v_regime_states >= 3 THEN 'HEALTHY'
                   WHEN v_regime_states >= 2 THEN 'WARNING'
                   ELSE 'CRITICAL' END;
    alert_needed := v_regime_states < 2;
    RETURN NEXT;

END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- GRANT PERMISSIONS
-- =============================================================================

GRANT SELECT ON vision_verification.regime_coverage_sentinel_log TO PUBLIC;
GRANT SELECT ON vision_verification.regime_coverage_health TO PUBLIC;
GRANT SELECT ON vision_verification.regime_diversity_trend TO PUBLIC;
GRANT EXECUTE ON FUNCTION vision_verification.run_regime_coverage_sentinel() TO PUBLIC;

-- =============================================================================
-- INITIAL SENTINEL RUN
-- =============================================================================

-- Run initial sentinel check
SELECT * FROM vision_verification.run_regime_coverage_sentinel();

-- Log migration
INSERT INTO fhq_meta.ios_audit_log (
    audit_id, ios_id, event_type, event_timestamp, actor, gate_level, event_data
) VALUES (
    gen_random_uuid(),
    'IoS-003',
    'COVERAGE_SENTINEL_INSTALLED',
    NOW(),
    'STIG',
    'G1',
    jsonb_build_object(
        'authority', 'CEO-DIR-2025-RC-004',
        'migration', '172_regime_coverage_sentinels.sql',
        'components', ARRAY['regime_coverage_sentinel_log', 'regime_coverage_health', 'regime_diversity_trend', 'run_regime_coverage_sentinel()'],
        'thresholds', jsonb_build_object(
            'asset_coverage', 400,
            'diversity_pct', 15.0,
            'regime_states', 3
        )
    )
);
