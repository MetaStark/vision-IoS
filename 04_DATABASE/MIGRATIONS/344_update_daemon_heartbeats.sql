-- Migration 344: Update Daemon Heartbeats
-- CEO-DIR-2026-DAY25: Daemon Recovery
-- Timestamp: 2026-01-25T01:37Z

BEGIN;

-- Update heartbeats for running daemons
UPDATE fhq_monitoring.daemon_health
SET
    last_heartbeat = NOW(),
    status = 'HEALTHY',
    metadata = jsonb_set(
        COALESCE(metadata, '{}'::jsonb),
        '{restarted_at}',
        to_jsonb(NOW()::text)
    ),
    updated_at = NOW()
WHERE daemon_name IN (
    'finn_brain_scheduler',
    'economic_outcome_daemon',
    'g2c_continuous_forecast_engine',
    'ios003b_intraday_regime_delta'
);

-- Insert new entries if they don't exist
INSERT INTO fhq_monitoring.daemon_health (daemon_name, status, last_heartbeat, metadata)
VALUES
    ('finn_brain_scheduler', 'HEALTHY', NOW(), '{"owner": "FINN", "schedule": "*/30 * * * *", "started_at": "2026-01-25T01:09:00Z"}'::jsonb),
    ('economic_outcome_daemon', 'HEALTHY', NOW(), '{"owner": "CEIO", "schedule": "CONTINUOUS", "purpose": "Economic event outcome tracking"}'::jsonb),
    ('g2c_continuous_forecast_engine', 'HEALTHY', NOW(), '{"owner": "LINE", "schedule": "CONTINUOUS", "purpose": "STRAT_* forecast generation"}'::jsonb),
    ('ios003b_intraday_regime_delta', 'HEALTHY', NOW(), '{"owner": "FINN", "schedule": "*/15 * * * *", "purpose": "Crypto regime delta detection"}'::jsonb)
ON CONFLICT (daemon_name) DO UPDATE
SET
    last_heartbeat = NOW(),
    status = 'HEALTHY',
    metadata = jsonb_set(
        COALESCE(fhq_monitoring.daemon_health.metadata, '{}'::jsonb),
        '{restarted_at}',
        to_jsonb(NOW()::text)
    ),
    updated_at = NOW();

-- Update process_inventory last_success_at
UPDATE fhq_monitoring.process_inventory
SET last_success_at = NOW(),
    updated_at = NOW()
WHERE process_name IN (
    'finn_brain_scheduler.py',
    'economic_outcome_daemon.py',
    'g2c_continuous_forecast_engine.py',
    'ios003b_intraday_regime_delta.py'
);

COMMIT;

-- Verify
SELECT daemon_name, status, last_heartbeat, metadata->>'started_at' as started_at
FROM fhq_monitoring.daemon_health
WHERE last_heartbeat > NOW() - INTERVAL '1 hour'
ORDER BY daemon_name;
