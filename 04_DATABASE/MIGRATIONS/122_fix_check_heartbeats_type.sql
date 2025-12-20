-- ============================================================================
-- Migration 122: Fix check_heartbeats() Type Mismatch
-- Fix: Cast CASE result to varchar to match return type
-- ============================================================================
-- Authority: STIG (CTO) per EC-003
-- ADR References: ADR-016 (DEFCON Protocol)
-- Error: "Returned type text does not match expected type character varying"
-- ============================================================================

BEGIN;

-- Fix the check_heartbeats function - cast CASE result to varchar
CREATE OR REPLACE FUNCTION fhq_governance.check_heartbeats()
RETURNS TABLE(agent_id character varying, status character varying, last_heartbeat_at timestamp with time zone, consecutive_misses integer, defcon_action character varying)
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

    -- Return current status with explicit cast to varchar (FIX for type mismatch)
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
    'fhq_governance.check_heartbeats',
    'FUNCTION',
    'STIG',
    NOW(),
    'APPROVED',
    'Migration 122: Fixed type mismatch in check_heartbeats() - CASE statement now explicitly casts to varchar to match return type declaration. This resolves the error: "Returned type text does not match expected type character varying in column 5"',
    false,
    'MIG-122-HEARTBEAT-FIX-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS')
);

COMMIT;

-- ============================================================================
-- Migration 122 Complete
-- ============================================================================
