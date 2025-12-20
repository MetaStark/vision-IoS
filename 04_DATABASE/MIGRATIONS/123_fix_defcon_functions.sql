-- ============================================================================
-- Migration 123: Fix DEFCON Functions Type Mismatch
-- The defcon_state table uses TEXT for defcon_level ('GREEN', 'YELLOW', etc.)
-- but trigger_defcon_change expected INTEGER. This fixes both functions.
-- ============================================================================
-- Authority: STIG (CTO) per EC-003
-- ADR References: ADR-016 (DEFCON Protocol)
-- ============================================================================

BEGIN;

-- Fix trigger_defcon_change to work with text-based defcon_level
CREATE OR REPLACE FUNCTION fhq_governance.trigger_defcon_change(
    p_new_level integer,
    p_trigger_type character varying,
    p_reason character varying
)
RETURNS uuid
LANGUAGE plpgsql
AS $function$
DECLARE
    v_current_level_text TEXT;
    v_current_level INTEGER;
    v_new_status VARCHAR(20);
    v_state_id UUID;
BEGIN
    -- Get current level (stored as text, convert to integer for comparison)
    SELECT defcon_level INTO v_current_level_text
    FROM fhq_governance.defcon_state
    WHERE is_current = TRUE;

    -- Convert text to integer level
    v_current_level := CASE v_current_level_text
        WHEN 'GREEN' THEN 5
        WHEN 'YELLOW' THEN 3
        WHEN 'ORANGE' THEN 2
        WHEN 'RED' THEN 1
        WHEN 'BLACK' THEN 0
        ELSE 5  -- default to GREEN
    END;

    -- Don't downgrade automatically (only manual resolution can lower DEFCON)
    -- Lower number = higher alert, so we check if new_level > current (less severe)
    IF v_current_level IS NOT NULL AND p_new_level > v_current_level THEN
        RETURN NULL;
    END IF;

    -- Map level to status
    v_new_status := CASE p_new_level
        WHEN 5 THEN 'GREEN'
        WHEN 4 THEN 'GREEN'
        WHEN 3 THEN 'YELLOW'
        WHEN 2 THEN 'ORANGE'
        WHEN 1 THEN 'RED'
        ELSE 'BLACK'
    END;

    -- Mark previous as not current
    UPDATE fhq_governance.defcon_state
    SET is_current = FALSE
    WHERE is_current = TRUE;

    -- Insert new state (defcon_level stored as text)
    INSERT INTO fhq_governance.defcon_state (
        state_id, defcon_level, triggered_at, triggered_by,
        trigger_reason, is_current, created_at
    ) VALUES (
        gen_random_uuid(), v_new_status, NOW(), 'SYSTEM',
        p_reason, TRUE, NOW()
    ) RETURNING state_id INTO v_state_id;

    -- Log DEFCON change event
    INSERT INTO fhq_governance.system_events (
        event_type, event_category, event_severity,
        source_agent, event_title, event_data
    ) VALUES (
        'DEFCON_CHANGE', 'GOVERNANCE',
        CASE WHEN p_new_level <= 2 THEN 'CRITICAL' ELSE 'WARNING' END,
        'SYSTEM',
        'DEFCON changed to ' || v_new_status || ' (Level ' || p_new_level || ')',
        jsonb_build_object(
            'new_level', p_new_level,
            'previous_level', v_current_level,
            'new_status', v_new_status,
            'trigger_type', p_trigger_type,
            'reason', p_reason
        )
    );

    RETURN v_state_id;
END;
$function$;

-- Fix check_heartbeats to handle text-based defcon and varchar types
CREATE OR REPLACE FUNCTION fhq_governance.check_heartbeats()
RETURNS TABLE(
    agent_id character varying,
    status character varying,
    last_heartbeat_at timestamp with time zone,
    consecutive_misses integer,
    defcon_action character varying
)
LANGUAGE plpgsql
AS $function$
DECLARE
    v_stale_agent RECORD;
    v_defcon_triggered BOOLEAN := FALSE;
BEGIN
    -- Update status for stale agents
    FOR v_stale_agent IN
        SELECT h.agent_id, h.last_heartbeat_at, h.consecutive_misses
        FROM fhq_governance.agent_heartbeats h
        WHERE h.next_expected_at < NOW()
          AND h.status != 'DEAD'
    LOOP
        -- Increment miss counter
        UPDATE fhq_governance.agent_heartbeats
        SET
            consecutive_misses = agent_heartbeats.consecutive_misses + 1,
            status = CASE
                WHEN agent_heartbeats.consecutive_misses >= 2 THEN 'DEAD'
                WHEN agent_heartbeats.consecutive_misses >= 1 THEN 'STALE'
                ELSE 'DEGRADED'
            END,
            last_miss_at = NOW(),
            next_expected_at = NOW() + INTERVAL '30 seconds',
            updated_at = NOW()
        WHERE agent_heartbeats.agent_id = v_stale_agent.agent_id;

        -- Log miss event
        INSERT INTO fhq_governance.system_events (
            event_type, event_category, event_severity,
            source_agent, event_title, event_data
        ) VALUES (
            CASE
                WHEN v_stale_agent.consecutive_misses >= 2 THEN 'HEARTBEAT_DEAD'
                ELSE 'HEARTBEAT_MISS'
            END,
            'HEARTBEAT',
            CASE WHEN v_stale_agent.consecutive_misses >= 2 THEN 'CRITICAL' ELSE 'WARNING' END,
            v_stale_agent.agent_id,
            v_stale_agent.agent_id || ' missed heartbeat',
            jsonb_build_object(
                'consecutive_misses', v_stale_agent.consecutive_misses + 1,
                'last_heartbeat', v_stale_agent.last_heartbeat_at
            )
        );

        -- Trigger DEFCON YELLOW if any agent misses
        IF NOT v_defcon_triggered THEN
            PERFORM fhq_governance.trigger_defcon_change(
                3, -- YELLOW
                'HEARTBEAT_MISS',
                'Agent ' || v_stale_agent.agent_id || ' missed heartbeat'
            );
            v_defcon_triggered := TRUE;
        END IF;
    END LOOP;

    -- Return current status with explicit cast to varchar
    RETURN QUERY
    SELECT
        h.agent_id,
        h.status,
        h.last_heartbeat_at,
        h.consecutive_misses,
        CAST(CASE
            WHEN h.consecutive_misses >= 3 THEN 'DEFCON_RED_CANDIDATE'
            WHEN h.consecutive_misses >= 1 THEN 'DEFCON_YELLOW'
            ELSE 'NONE'
        END AS varchar) AS defcon_action
    FROM fhq_governance.agent_heartbeats h
    ORDER BY h.consecutive_misses DESC, h.last_heartbeat_at ASC;
END;
$function$;

-- Log governance action
INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    vega_reviewed,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'SCHEMA_MIGRATION',
    'fhq_governance.defcon_functions',
    'FUNCTION',
    'STIG',
    NOW(),
    'APPROVED',
    'Migration 123: Fixed type mismatch in DEFCON functions. The defcon_state table stores defcon_level as TEXT (GREEN/YELLOW/etc) but trigger_defcon_change expected INTEGER. Both trigger_defcon_change and check_heartbeats now correctly handle text-based defcon levels.',
    false,
    'MIG-123-DEFCON-FIX-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS')
);

COMMIT;

-- ============================================================================
-- Migration 123 Complete
-- ============================================================================
