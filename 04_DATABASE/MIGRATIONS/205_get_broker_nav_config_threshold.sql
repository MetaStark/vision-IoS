-- Migration 205: Fix get_broker_nav to read threshold from config
-- CEO-DIR-2026-SITC-DATA-BLACKOUT-FIX-001
-- Author: STIG (CTO)
-- Date: 2026-01-06
--
-- Bug: Function had hardcoded INTERVAL '5 minutes' (300s) threshold
-- Fix: Read max_snapshot_age_seconds from fhq_positions.hcp_engine_config

CREATE OR REPLACE FUNCTION fhq_execution.get_broker_nav()
 RETURNS TABLE(nav numeric, cash_balance numeric, positions_value numeric, position_count integer, snapshot_at timestamp with time zone, is_stale boolean, seconds_since_snapshot numeric)
 LANGUAGE plpgsql
AS $$
DECLARE
    v_max_age_seconds INTEGER;
BEGIN
    -- Read config from hcp_engine_config (default 1200 if not found)
    SELECT COALESCE(config_value::INTEGER, 1200) INTO v_max_age_seconds
    FROM fhq_positions.hcp_engine_config
    WHERE config_key = 'max_snapshot_age_seconds';

    IF v_max_age_seconds IS NULL THEN
        v_max_age_seconds := 1200;
    END IF;

    RETURN QUERY
    SELECT
        CAST(bs.portfolio_value AS NUMERIC(20,2)) as nav,
        CAST(bs.cash AS NUMERIC(20,2)) as cash_balance,
        CAST(bs.portfolio_value - bs.cash AS NUMERIC(20,2)) as positions_value,
        COALESCE(JSONB_ARRAY_LENGTH(bs.positions), 0)::INTEGER as position_count,
        bs.captured_at as snapshot_at,
        (EXTRACT(EPOCH FROM (NOW() - bs.captured_at)) > v_max_age_seconds) as is_stale,
        EXTRACT(EPOCH FROM (NOW() - bs.captured_at))::NUMERIC as seconds_since_snapshot
    FROM fhq_execution.broker_state_snapshots bs
    WHERE bs.broker = 'ALPACA' AND bs.broker_environment = 'PAPER'
    ORDER BY bs.captured_at DESC
    LIMIT 1;
END;
$$;

-- Verify
SELECT 'Migration 205 complete: get_broker_nav now reads threshold from config' as status;
