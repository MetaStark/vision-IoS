-- Migration 346: Heartbeat Fail-Closed Enforcement
-- CEO-DIR-2026-DAY25: Daemon & Heartbeat Integrity - P0
--
-- Mandates:
-- 1. Any daemon stale > 2 cycles must flip system to DEGRADED
-- 2. Block promotions (fail-closed)
-- 3. Remove all manual-only execution paths

BEGIN;

-- Add stale_cycles and expected_interval to daemon_health if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'fhq_monitoring'
                   AND table_name = 'daemon_health'
                   AND column_name = 'expected_interval_minutes') THEN
        ALTER TABLE fhq_monitoring.daemon_health
        ADD COLUMN expected_interval_minutes INTEGER DEFAULT 30;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'fhq_monitoring'
                   AND table_name = 'daemon_health'
                   AND column_name = 'is_critical') THEN
        ALTER TABLE fhq_monitoring.daemon_health
        ADD COLUMN is_critical BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

-- Update expected intervals for critical daemons
UPDATE fhq_monitoring.daemon_health SET
    expected_interval_minutes = 30,
    is_critical = TRUE
WHERE daemon_name IN (
    'finn_brain_scheduler',
    'g2c_continuous_forecast_engine',
    'ios003b_intraday_regime_delta',
    'economic_outcome_daemon'
);

-- Create function to check daemon staleness
CREATE OR REPLACE FUNCTION fhq_monitoring.fn_check_daemon_staleness()
RETURNS TABLE (
    daemon_name TEXT,
    is_stale BOOLEAN,
    stale_cycles INTEGER,
    last_heartbeat TIMESTAMPTZ,
    expected_interval INTEGER,
    minutes_since_heartbeat NUMERIC,
    recommendation TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.daemon_name,
        CASE
            WHEN d.last_heartbeat IS NULL THEN TRUE
            WHEN EXTRACT(EPOCH FROM (NOW() - d.last_heartbeat)) / 60 > d.expected_interval_minutes * 2 THEN TRUE
            ELSE FALSE
        END as is_stale,
        CASE
            WHEN d.last_heartbeat IS NULL THEN 999
            ELSE FLOOR(EXTRACT(EPOCH FROM (NOW() - d.last_heartbeat)) / 60 / NULLIF(d.expected_interval_minutes, 0))::INTEGER
        END as stale_cycles,
        d.last_heartbeat,
        d.expected_interval_minutes as expected_interval,
        ROUND(EXTRACT(EPOCH FROM (NOW() - d.last_heartbeat)) / 60, 1) as minutes_since_heartbeat,
        CASE
            WHEN d.last_heartbeat IS NULL THEN 'CRITICAL: Never reported - start daemon immediately'
            WHEN EXTRACT(EPOCH FROM (NOW() - d.last_heartbeat)) / 60 > d.expected_interval_minutes * 2 THEN 'WARNING: Stale > 2 cycles - restart required'
            ELSE 'OK: Within expected interval'
        END as recommendation
    FROM fhq_monitoring.daemon_health d
    WHERE d.is_critical = TRUE
    ORDER BY
        CASE WHEN d.last_heartbeat IS NULL THEN 0 ELSE 1 END,
        EXTRACT(EPOCH FROM (NOW() - d.last_heartbeat)) DESC;
END;
$$ LANGUAGE plpgsql;

-- Create function to get system operational status
CREATE OR REPLACE FUNCTION fhq_monitoring.fn_get_operational_status()
RETURNS TABLE (
    status TEXT,
    stale_critical_daemons INTEGER,
    promotion_allowed BOOLEAN,
    reason TEXT
) AS $$
DECLARE
    v_stale_count INTEGER;
BEGIN
    -- Count stale critical daemons
    SELECT COUNT(*) INTO v_stale_count
    FROM fhq_monitoring.daemon_health d
    WHERE d.is_critical = TRUE
      AND (d.last_heartbeat IS NULL
           OR EXTRACT(EPOCH FROM (NOW() - d.last_heartbeat)) / 60 > d.expected_interval_minutes * 2);

    -- Return status
    IF v_stale_count > 0 THEN
        RETURN QUERY SELECT
            'DEGRADED'::TEXT,
            v_stale_count,
            FALSE,
            format('%s critical daemon(s) stale - promotions blocked (fail-closed)', v_stale_count);
    ELSE
        RETURN QUERY SELECT
            'OPERATIONAL'::TEXT,
            0,
            TRUE,
            'All critical daemons reporting - system healthy';
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Create view for dashboard
CREATE OR REPLACE VIEW fhq_monitoring.v_operational_status AS
SELECT * FROM fhq_monitoring.fn_get_operational_status();

-- Create view for daemon staleness
CREATE OR REPLACE VIEW fhq_monitoring.v_daemon_staleness AS
SELECT * FROM fhq_monitoring.fn_check_daemon_staleness();

-- Modify promotion gate to check operational status
CREATE OR REPLACE FUNCTION fhq_governance.fn_check_promotion_gate(
    p_promotion_type TEXT DEFAULT 'STANDARD'
)
RETURNS TABLE (
    gate_status TEXT,
    can_promote BOOLEAN,
    blockers JSONB
) AS $$
DECLARE
    v_op_status RECORD;
    v_blockers JSONB := '[]'::JSONB;
BEGIN
    -- Get operational status
    SELECT * INTO v_op_status FROM fhq_monitoring.fn_get_operational_status();

    -- Check if promotion is blocked
    IF NOT v_op_status.promotion_allowed THEN
        v_blockers := v_blockers || jsonb_build_object(
            'blocker', 'DAEMON_STALENESS',
            'stale_count', v_op_status.stale_critical_daemons,
            'reason', v_op_status.reason
        );
    END IF;

    -- Return gate status
    IF jsonb_array_length(v_blockers) > 0 THEN
        RETURN QUERY SELECT
            'BLOCKED'::TEXT,
            FALSE,
            v_blockers;
    ELSE
        RETURN QUERY SELECT
            'CLEAR'::TEXT,
            TRUE,
            '[]'::JSONB;
    END IF;
END;
$$ LANGUAGE plpgsql;

COMMIT;

-- Verify
SELECT 'Operational Status' as check_name;
SELECT * FROM fhq_monitoring.v_operational_status;

SELECT 'Daemon Staleness' as check_name;
SELECT daemon_name, is_stale, stale_cycles, minutes_since_heartbeat, recommendation
FROM fhq_monitoring.v_daemon_staleness;
