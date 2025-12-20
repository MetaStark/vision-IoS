-- CEO DIRECTIVE: PROOF OF LIFE / FIRST THOUGHTS
-- Inject MANUAL_SYSTEM_PROBE events for IoS-007 and CEIO

DO $$
DECLARE
    v_event_id_1 UUID := gen_random_uuid();
    v_event_id_2 UUID := gen_random_uuid();
    v_regime TEXT;
BEGIN
    -- Get current regime
    SELECT current_regime INTO v_regime FROM fhq_meta.regime_state LIMIT 1;

    -- If no regime, default to UNKNOWN
    IF v_regime IS NULL THEN
        v_regime := 'UNKNOWN';
    END IF;

    -- Insert system events
    INSERT INTO fhq_governance.system_events (
        event_id,
        event_type,
        event_category,
        event_severity,
        source_agent,
        source_component,
        source_ios_layer,
        event_title,
        event_description,
        event_data,
        regime,
        defcon_level,
        created_at
    ) VALUES
    (
        v_event_id_1,
        'MANUAL_SYSTEM_PROBE',
        'GOVERNANCE',
        'CRITICAL',
        'STIG',
        'ORCHESTRATOR',
        'IoS-007',
        'CEO PROOF OF LIFE - IoS-007 Alpha Graph',
        'Assess current global liquidity & crypto regime correlation using SPECIALE model',
        jsonb_build_object(
            'instruction', 'Assess current global liquidity & crypto regime correlation',
            'depth', 'DEEP',
            'model_override', 'SPECIALE',
            'target', 'IoS-007'
        ),
        v_regime,
        5,
        NOW()
    ),
    (
        v_event_id_2,
        'MANUAL_SYSTEM_PROBE',
        'GOVERNANCE',
        'CRITICAL',
        'STIG',
        'ORCHESTRATOR',
        'CEIO',
        'CEO PROOF OF LIFE - CEIO Deep Research',
        'Assess current global liquidity & crypto regime correlation using SPECIALE model',
        jsonb_build_object(
            'instruction', 'Assess current global liquidity & crypto regime correlation',
            'depth', 'DEEP',
            'model_override', 'SPECIALE',
            'target', 'CEIO'
        ),
        v_regime,
        5,
        NOW()
    );

    -- Insert into event queue
    INSERT INTO fhq_governance.event_queue (
        queue_id,
        event_id,
        event_type,
        target_agent,
        target_action,
        priority,
        status,
        retry_count,
        max_retries,
        queued_at,
        regime_at_queue,
        defcon_at_queue,
        result_data
    ) VALUES
    (
        gen_random_uuid(),
        v_event_id_1,
        'MANUAL_SYSTEM_PROBE',
        'LARS',
        'ios007_alpha_graph_causal_inference',
        1,
        'PENDING',
        0,
        3,
        NOW(),
        v_regime,
        5,
        jsonb_build_object(
            'instruction', 'Assess current global liquidity & crypto regime correlation',
            'depth', 'DEEP',
            'model_override', 'SPECIALE'
        )
    ),
    (
        gen_random_uuid(),
        v_event_id_2,
        'MANUAL_SYSTEM_PROBE',
        'CEIO',
        'ceio_deep_research',
        1,
        'PENDING',
        0,
        3,
        NOW(),
        v_regime,
        5,
        jsonb_build_object(
            'instruction', 'Assess current global liquidity & crypto regime correlation',
            'depth', 'DEEP',
            'model_override', 'SPECIALE'
        )
    );

    RAISE NOTICE 'CEO DIRECTIVE EXECUTED: Events % and % injected', v_event_id_1, v_event_id_2;
END $$;

-- Verify injection
SELECT
    queue_id,
    event_type,
    target_agent,
    target_action,
    status,
    queued_at
FROM fhq_governance.event_queue
WHERE event_type = 'MANUAL_SYSTEM_PROBE'
ORDER BY queued_at DESC
LIMIT 2;
