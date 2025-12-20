-- ============================================================================
-- MIGRATION 097: SYSTEM HEARTBEAT INFRASTRUCTURE
-- ============================================================================
-- CEO DIRECTIVE: ARO-20251208 (Autonomy Restoration Order)
-- Authority: Tier-1 Executive Mandate
-- ADR Binding: ADR-007, ADR-015, ADR-016
-- Gate: G0→G4 Architecture Alignment
-- Executor: STIG (CTO) - EC-003_2026_PRODUCTION
-- ============================================================================
-- PURPOSE: Install the "pulse" - system_events table and heartbeat logging
-- The system lives only when it publishes events.
-- Without this, no real-time reaction, no DEFCON transitions, no autonomy score.
-- ============================================================================

-- Migration metadata
DO $$
BEGIN
    RAISE NOTICE '=== MIGRATION 097: SYSTEM HEARTBEAT INFRASTRUCTURE ===';
    RAISE NOTICE 'CEO DIRECTIVE: ARO-20251208';
    RAISE NOTICE 'Executor: STIG (CTO)';
    RAISE NOTICE 'Timestamp: %', NOW();
END $$;

-- ============================================================================
-- SECTION 1: CENTRAL EVENT LOG (fhq_governance.system_events)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.system_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Event classification
    event_type VARCHAR(50) NOT NULL,     -- See enum below
    event_category VARCHAR(30) NOT NULL, -- 'HEARTBEAT', 'SIGNAL', 'REGIME', 'EXECUTION', 'ERROR', 'GOVERNANCE'
    event_severity VARCHAR(20) NOT NULL DEFAULT 'INFO', -- 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'

    -- Source identification
    source_agent VARCHAR(20) NOT NULL,   -- FINN, CEIO, LARS, LINE, VEGA, STIG, SYSTEM
    source_component VARCHAR(100),       -- Specific module/function
    source_ios_layer VARCHAR(20),        -- IOS-003, IOS-007, IOS-009, IOS-012, etc.

    -- Event data
    event_title VARCHAR(200) NOT NULL,
    event_description TEXT,
    event_data JSONB,

    -- Context
    regime VARCHAR(20),                  -- Current regime at event time
    defcon_level INTEGER,                -- Current DEFCON at event time
    session_id UUID,                     -- Related session if any

    -- Correlation
    correlation_id UUID,                 -- For tracing related events
    parent_event_id UUID REFERENCES fhq_governance.system_events(event_id),
    causation_chain UUID[],              -- Chain of causing events

    -- Performance metrics
    processing_time_ms INTEGER,
    queue_depth INTEGER,

    -- Lineage
    lineage_hash VARCHAR(64),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- TTL for archival
    archive_after TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '30 days'),
    archived_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT valid_event_agent CHECK (source_agent IN ('FINN', 'CEIO', 'LARS', 'LINE', 'VEGA', 'STIG', 'SYSTEM')),
    CONSTRAINT valid_event_severity CHECK (event_severity IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    CONSTRAINT valid_event_category CHECK (event_category IN (
        'HEARTBEAT', 'SIGNAL', 'REGIME', 'EXECUTION', 'ERROR',
        'GOVERNANCE', 'MEMORY', 'PERCEPTION', 'ALPHA_GRAPH', 'CEIO', 'RESEARCH'
    ))
);

-- Performance indexes for event queries
CREATE INDEX IF NOT EXISTS idx_system_events_created
    ON fhq_governance.system_events(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_system_events_type
    ON fhq_governance.system_events(event_type);

CREATE INDEX IF NOT EXISTS idx_system_events_category
    ON fhq_governance.system_events(event_category);

CREATE INDEX IF NOT EXISTS idx_system_events_agent
    ON fhq_governance.system_events(source_agent);

CREATE INDEX IF NOT EXISTS idx_system_events_severity
    ON fhq_governance.system_events(event_severity)
    WHERE event_severity IN ('WARNING', 'ERROR', 'CRITICAL');

CREATE INDEX IF NOT EXISTS idx_system_events_correlation
    ON fhq_governance.system_events(correlation_id)
    WHERE correlation_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_system_events_regime
    ON fhq_governance.system_events(regime)
    WHERE regime IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_system_events_heartbeat
    ON fhq_governance.system_events(source_agent, created_at DESC)
    WHERE event_category = 'HEARTBEAT';

-- Partial index for recent events (performance optimization)
CREATE INDEX IF NOT EXISTS idx_system_events_recent
    ON fhq_governance.system_events(created_at DESC)
    WHERE created_at > NOW() - INTERVAL '1 hour';

COMMENT ON TABLE fhq_governance.system_events IS
'Central event log for FjordHQ autonomous system. ARO-20251208 Section 2.
Logs signals, regime shifts, executions, errors, and heartbeats.
Foundation for DEFCON transitions (ADR-016), drift detection (ADR-015), and autonomy scoring.';

-- ============================================================================
-- SECTION 2: AGENT HEARTBEAT TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.agent_heartbeats (
    heartbeat_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Agent identification
    agent_id VARCHAR(20) NOT NULL,
    agent_component VARCHAR(100),        -- Specific component within agent

    -- Heartbeat status
    status VARCHAR(20) NOT NULL DEFAULT 'ALIVE', -- 'ALIVE', 'DEGRADED', 'STALE', 'DEAD'
    health_score DECIMAL(5,4) DEFAULT 1.0000,

    -- Metrics
    events_processed INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    warnings_count INTEGER DEFAULT 0,
    memory_usage_mb INTEGER,
    cpu_usage_pct DECIMAL(5,2),

    -- Context
    current_task VARCHAR(200),
    current_regime VARCHAR(20),
    defcon_level INTEGER,

    -- Timing
    last_heartbeat_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    next_expected_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '30 seconds'),
    heartbeat_interval_seconds INTEGER DEFAULT 30,

    -- Staleness tracking
    consecutive_misses INTEGER DEFAULT 0,
    last_miss_at TIMESTAMP WITH TIME ZONE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Unique constraint per agent
    CONSTRAINT unique_agent_heartbeat UNIQUE (agent_id),
    CONSTRAINT valid_heartbeat_agent CHECK (agent_id IN ('FINN', 'CEIO', 'LARS', 'LINE', 'VEGA', 'STIG', 'SYSTEM', 'IOS-003', 'IOS-007', 'IOS-009', 'IOS-012'))
);

CREATE INDEX IF NOT EXISTS idx_heartbeat_status
    ON fhq_governance.agent_heartbeats(status);

CREATE INDEX IF NOT EXISTS idx_heartbeat_last
    ON fhq_governance.agent_heartbeats(last_heartbeat_at DESC);

CREATE INDEX IF NOT EXISTS idx_heartbeat_stale
    ON fhq_governance.agent_heartbeats(next_expected_at)
    WHERE status != 'DEAD';

COMMENT ON TABLE fhq_governance.agent_heartbeats IS
'Agent heartbeat tracking. ARO-20251208 Section 2.2.
Every agent must publish heartbeat every 30 seconds.
Missing heartbeat triggers DEFCON YELLOW automatically.';

-- ============================================================================
-- SECTION 3: DEFCON STATE TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.defcon_state (
    state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Current DEFCON level (1-5, 1 = most severe)
    defcon_level INTEGER NOT NULL DEFAULT 5,
    previous_level INTEGER,

    -- State details
    status VARCHAR(20) NOT NULL DEFAULT 'GREEN', -- 'GREEN', 'YELLOW', 'ORANGE', 'RED', 'BLACK'
    trigger_reason VARCHAR(200),
    trigger_event_id UUID REFERENCES fhq_governance.system_events(event_id),

    -- Automatic triggers
    auto_triggered BOOLEAN DEFAULT FALSE,
    auto_trigger_type VARCHAR(50),       -- 'HEARTBEAT_MISS', 'ERROR_THRESHOLD', 'REGIME_CRISIS', etc.

    -- Duration tracking
    entered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expected_duration_minutes INTEGER,

    -- Resolution
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolved_by VARCHAR(20),
    resolution_notes TEXT,

    -- Active flag
    is_current BOOLEAN DEFAULT TRUE,

    -- Lineage
    lineage_hash VARCHAR(64),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT valid_defcon_level CHECK (defcon_level BETWEEN 1 AND 5),
    CONSTRAINT valid_defcon_status CHECK (status IN ('GREEN', 'YELLOW', 'ORANGE', 'RED', 'BLACK'))
);

CREATE INDEX IF NOT EXISTS idx_defcon_current
    ON fhq_governance.defcon_state(is_current)
    WHERE is_current = TRUE;

CREATE INDEX IF NOT EXISTS idx_defcon_level
    ON fhq_governance.defcon_state(defcon_level);

CREATE INDEX IF NOT EXISTS idx_defcon_entered
    ON fhq_governance.defcon_state(entered_at DESC);

COMMENT ON TABLE fhq_governance.defcon_state IS
'DEFCON state tracking per ADR-016. ARO-20251208.
Level 5 = GREEN (normal), Level 1 = BLACK (critical emergency).
Heartbeat misses auto-trigger YELLOW (Level 3).';

-- ============================================================================
-- SECTION 4: EVENT TYPE ENUM TABLE (Reference)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.event_type_registry (
    event_type VARCHAR(50) PRIMARY KEY,
    event_category VARCHAR(30) NOT NULL,
    description TEXT,
    severity_default VARCHAR(20) DEFAULT 'INFO',
    defcon_impact INTEGER,               -- Potential DEFCON level change
    requires_ack BOOLEAN DEFAULT FALSE,  -- Requires acknowledgment
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Populate event types per ARO-20251208
INSERT INTO fhq_governance.event_type_registry (event_type, event_category, description, severity_default, defcon_impact, requires_ack) VALUES
    -- Heartbeat events
    ('HEARTBEAT_ALIVE', 'HEARTBEAT', 'Agent alive signal', 'DEBUG', NULL, FALSE),
    ('HEARTBEAT_MISS', 'HEARTBEAT', 'Agent missed heartbeat', 'WARNING', 3, TRUE),
    ('HEARTBEAT_RECOVERED', 'HEARTBEAT', 'Agent recovered from miss', 'INFO', NULL, FALSE),
    ('HEARTBEAT_DEAD', 'HEARTBEAT', 'Agent declared dead (3+ misses)', 'CRITICAL', 2, TRUE),

    -- Signal events
    ('SIGNAL_GENERATED', 'SIGNAL', 'New alpha signal generated', 'INFO', NULL, FALSE),
    ('SIGNAL_CONFIDENCE_CHANGE', 'SIGNAL', 'Signal confidence changed significantly', 'INFO', NULL, FALSE),
    ('SIGNAL_INVALIDATED', 'SIGNAL', 'Signal invalidated', 'WARNING', NULL, FALSE),

    -- Regime events
    ('REGIME_SHIFT', 'REGIME', 'Market regime changed', 'INFO', NULL, FALSE),
    ('REGIME_CRISIS_ENTER', 'REGIME', 'Entered CRISIS regime', 'WARNING', 3, TRUE),
    ('REGIME_CRISIS_EXIT', 'REGIME', 'Exited CRISIS regime', 'INFO', NULL, FALSE),

    -- Execution events (LINE)
    ('ORDER_SUBMITTED', 'EXECUTION', 'Order submitted to exchange', 'INFO', NULL, FALSE),
    ('ORDER_FILLED', 'EXECUTION', 'Order filled', 'INFO', NULL, FALSE),
    ('ORDER_REJECTED', 'EXECUTION', 'Order rejected', 'WARNING', NULL, FALSE),
    ('SLIPPAGE_ALERT', 'EXECUTION', 'Slippage exceeded threshold', 'WARNING', NULL, TRUE),
    ('KILL_SWITCH_ACTIVATED', 'EXECUTION', 'Kill switch activated', 'CRITICAL', 1, TRUE),

    -- Alpha Graph events (IOS-007)
    ('CAUSAL_EDGE_ADDED', 'ALPHA_GRAPH', 'New causal edge in Alpha Graph', 'INFO', NULL, FALSE),
    ('CAUSAL_EDGE_REMOVED', 'ALPHA_GRAPH', 'Causal edge removed', 'INFO', NULL, FALSE),
    ('GRAPH_RESTRUCTURE', 'ALPHA_GRAPH', 'Major graph restructure', 'INFO', NULL, FALSE),

    -- CEIO events
    ('CEIO_ANALYSIS_START', 'CEIO', 'CEIO analysis started', 'INFO', NULL, FALSE),
    ('CEIO_ANALYSIS_COMPLETE', 'CEIO', 'CEIO analysis completed', 'INFO', NULL, FALSE),
    ('CEIO_SHADOW_POSITION', 'CEIO', 'Shadow position created/closed', 'INFO', NULL, FALSE),
    ('CEIO_NEWS_SHOCK', 'CEIO', 'News shock detected', 'WARNING', NULL, FALSE),
    ('CEIO_SENTIMENT_SHIFT', 'CEIO', 'Sentiment shift detected', 'INFO', NULL, FALSE),

    -- Perception events (IOS-003, IOS-009)
    ('PERCEPTION_UPDATE', 'PERCEPTION', 'Perception layer updated', 'INFO', NULL, FALSE),
    ('STRESS_LEVEL_CHANGE', 'PERCEPTION', 'Market stress level changed', 'INFO', NULL, FALSE),
    ('INTENT_SHIFT', 'PERCEPTION', 'Market intent shifted', 'INFO', NULL, FALSE),

    -- Error events
    ('ERROR_RECOVERABLE', 'ERROR', 'Recoverable error occurred', 'WARNING', NULL, FALSE),
    ('ERROR_CRITICAL', 'ERROR', 'Critical error - intervention needed', 'CRITICAL', 2, TRUE),
    ('ERROR_FATAL', 'ERROR', 'Fatal error - system halt', 'CRITICAL', 1, TRUE),
    ('THROTTLE_ACTIVATED', 'ERROR', 'Rate limiting activated', 'WARNING', NULL, FALSE),

    -- Governance events
    ('GOVERNANCE_APPROVAL', 'GOVERNANCE', 'Action approved', 'INFO', NULL, FALSE),
    ('GOVERNANCE_REJECTION', 'GOVERNANCE', 'Action rejected', 'WARNING', NULL, FALSE),
    ('GOVERNANCE_OVERRIDE', 'GOVERNANCE', 'VEGA override applied', 'WARNING', NULL, TRUE),
    ('ADR_VIOLATION', 'GOVERNANCE', 'ADR compliance violation', 'ERROR', 3, TRUE),

    -- Research events (FINN)
    ('RESEARCH_CYCLE_START', 'RESEARCH', 'Research cycle started', 'INFO', NULL, FALSE),
    ('RESEARCH_CYCLE_COMPLETE', 'RESEARCH', 'Research cycle completed', 'INFO', NULL, FALSE),
    ('METHODOLOGY_UPDATE', 'RESEARCH', 'Methodology updated', 'INFO', NULL, FALSE),

    -- Memory events
    ('MEMORY_STORED', 'MEMORY', 'Memory stored', 'DEBUG', NULL, FALSE),
    ('MEMORY_RETRIEVED', 'MEMORY', 'Memory retrieved', 'DEBUG', NULL, FALSE),
    ('MEMORY_DECAY_APPLIED', 'MEMORY', 'Memory decay applied', 'DEBUG', NULL, FALSE),
    ('MEMORY_CROSS_REGIME_BLOCKED', 'MEMORY', 'Cross-regime retrieval blocked', 'WARNING', NULL, FALSE)
ON CONFLICT (event_type) DO NOTHING;

COMMENT ON TABLE fhq_governance.event_type_registry IS
'Registry of all valid event types per ARO-20251208.';

-- ============================================================================
-- SECTION 5: HEARTBEAT PUBLICATION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.publish_heartbeat(
    p_agent_id VARCHAR(20),
    p_component VARCHAR(100) DEFAULT NULL,
    p_current_task VARCHAR(200) DEFAULT NULL,
    p_health_score DECIMAL DEFAULT 1.0,
    p_events_processed INTEGER DEFAULT 0,
    p_errors_count INTEGER DEFAULT 0
) RETURNS UUID AS $$
DECLARE
    v_event_id UUID;
    v_current_regime VARCHAR(20);
    v_defcon_level INTEGER;
BEGIN
    -- Get current regime
    SELECT current_regime INTO v_current_regime
    FROM fhq_meta.regime_state
    LIMIT 1;

    -- Get current DEFCON
    SELECT defcon_level INTO v_defcon_level
    FROM fhq_governance.defcon_state
    WHERE is_current = TRUE
    LIMIT 1;

    -- Upsert agent heartbeat record
    INSERT INTO fhq_governance.agent_heartbeats (
        agent_id, agent_component, status, health_score,
        events_processed, errors_count, current_task,
        current_regime, defcon_level,
        last_heartbeat_at, next_expected_at, consecutive_misses
    ) VALUES (
        p_agent_id, p_component, 'ALIVE', p_health_score,
        p_events_processed, p_errors_count, p_current_task,
        v_current_regime, v_defcon_level,
        NOW(), NOW() + INTERVAL '30 seconds', 0
    )
    ON CONFLICT (agent_id) DO UPDATE SET
        agent_component = COALESCE(p_component, fhq_governance.agent_heartbeats.agent_component),
        status = 'ALIVE',
        health_score = p_health_score,
        events_processed = fhq_governance.agent_heartbeats.events_processed + p_events_processed,
        errors_count = fhq_governance.agent_heartbeats.errors_count + p_errors_count,
        current_task = p_current_task,
        current_regime = v_current_regime,
        defcon_level = v_defcon_level,
        last_heartbeat_at = NOW(),
        next_expected_at = NOW() + INTERVAL '30 seconds',
        consecutive_misses = 0,
        updated_at = NOW();

    -- Log heartbeat event
    INSERT INTO fhq_governance.system_events (
        event_type, event_category, event_severity,
        source_agent, source_component,
        event_title, event_data,
        regime, defcon_level
    ) VALUES (
        'HEARTBEAT_ALIVE', 'HEARTBEAT', 'DEBUG',
        p_agent_id, p_component,
        p_agent_id || ' heartbeat',
        jsonb_build_object(
            'health_score', p_health_score,
            'events_processed', p_events_processed,
            'errors_count', p_errors_count,
            'current_task', p_current_task
        ),
        v_current_regime, v_defcon_level
    ) RETURNING event_id INTO v_event_id;

    RETURN v_event_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.publish_heartbeat IS
'ARO-20251208 Section 2.2: Agents must call this every 30 seconds.';

-- ============================================================================
-- SECTION 6: HEARTBEAT CHECK FUNCTION (Detects stale agents)
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.check_heartbeats()
RETURNS TABLE (
    agent_id VARCHAR(20),
    status VARCHAR(20),
    last_heartbeat_at TIMESTAMP WITH TIME ZONE,
    consecutive_misses INTEGER,
    defcon_action VARCHAR(50)
) AS $$
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
            consecutive_misses = consecutive_misses + 1,
            status = CASE
                WHEN consecutive_misses >= 2 THEN 'DEAD'
                WHEN consecutive_misses >= 1 THEN 'STALE'
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

    -- Return current status
    RETURN QUERY
    SELECT
        h.agent_id,
        h.status,
        h.last_heartbeat_at,
        h.consecutive_misses,
        CASE
            WHEN h.consecutive_misses >= 3 THEN 'DEFCON_RED_CANDIDATE'
            WHEN h.consecutive_misses >= 1 THEN 'DEFCON_YELLOW'
            ELSE 'NONE'
        END AS defcon_action
    FROM fhq_governance.agent_heartbeats h
    ORDER BY h.consecutive_misses DESC, h.last_heartbeat_at ASC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.check_heartbeats IS
'ARO-20251208: Check for stale agents and trigger DEFCON if needed.
Should be called by event loop or scheduler.';

-- ============================================================================
-- SECTION 7: DEFCON TRANSITION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.trigger_defcon_change(
    p_new_level INTEGER,
    p_trigger_type VARCHAR(50),
    p_reason VARCHAR(200)
) RETURNS UUID AS $$
DECLARE
    v_current_level INTEGER;
    v_current_status VARCHAR(20);
    v_new_status VARCHAR(20);
    v_state_id UUID;
BEGIN
    -- Get current level
    SELECT defcon_level INTO v_current_level
    FROM fhq_governance.defcon_state
    WHERE is_current = TRUE;

    -- Don't downgrade automatically (only manual resolution can lower DEFCON)
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
    SET is_current = FALSE, resolved_at = NOW()
    WHERE is_current = TRUE;

    -- Insert new state
    INSERT INTO fhq_governance.defcon_state (
        defcon_level, previous_level, status,
        trigger_reason, auto_triggered, auto_trigger_type,
        entered_at, is_current
    ) VALUES (
        p_new_level, v_current_level, v_new_status,
        p_reason, TRUE, p_trigger_type,
        NOW(), TRUE
    ) RETURNING state_id INTO v_state_id;

    -- Log DEFCON change event
    INSERT INTO fhq_governance.system_events (
        event_type, event_category, event_severity,
        source_agent, event_title, event_data,
        defcon_level
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
        ),
        p_new_level
    );

    RETURN v_state_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.trigger_defcon_change IS
'ARO-20251208 + ADR-016: Trigger DEFCON level change.';

-- ============================================================================
-- SECTION 8: EVENT PUBLICATION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.publish_event(
    p_event_type VARCHAR(50),
    p_source_agent VARCHAR(20),
    p_title VARCHAR(200),
    p_description TEXT DEFAULT NULL,
    p_data JSONB DEFAULT NULL,
    p_source_component VARCHAR(100) DEFAULT NULL,
    p_source_ios_layer VARCHAR(20) DEFAULT NULL,
    p_correlation_id UUID DEFAULT NULL,
    p_severity VARCHAR(20) DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_event_id UUID;
    v_category VARCHAR(30);
    v_default_severity VARCHAR(20);
    v_current_regime VARCHAR(20);
    v_defcon_level INTEGER;
BEGIN
    -- Get event metadata from registry
    SELECT event_category, severity_default
    INTO v_category, v_default_severity
    FROM fhq_governance.event_type_registry
    WHERE event_type = p_event_type;

    -- Default if not in registry
    IF v_category IS NULL THEN
        v_category := 'GOVERNANCE';
        v_default_severity := 'INFO';
    END IF;

    -- Get current regime
    SELECT current_regime INTO v_current_regime
    FROM fhq_meta.regime_state
    LIMIT 1;

    -- Get current DEFCON
    SELECT defcon_level INTO v_defcon_level
    FROM fhq_governance.defcon_state
    WHERE is_current = TRUE
    LIMIT 1;

    -- Insert event
    INSERT INTO fhq_governance.system_events (
        event_type, event_category, event_severity,
        source_agent, source_component, source_ios_layer,
        event_title, event_description, event_data,
        regime, defcon_level, correlation_id
    ) VALUES (
        p_event_type, v_category, COALESCE(p_severity, v_default_severity),
        p_source_agent, p_source_component, p_source_ios_layer,
        p_title, p_description, p_data,
        v_current_regime, v_defcon_level, p_correlation_id
    ) RETURNING event_id INTO v_event_id;

    RETURN v_event_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.publish_event IS
'ARO-20251208 Section 2.1: Central function for publishing events to system_events.';

-- ============================================================================
-- SECTION 9: INITIALIZE DEFAULT DEFCON STATE
-- ============================================================================

INSERT INTO fhq_governance.defcon_state (
    defcon_level, status, trigger_reason,
    auto_triggered, is_current
) VALUES (
    5, 'GREEN', 'System initialization - ARO-20251208',
    FALSE, TRUE
) ON CONFLICT DO NOTHING;

-- ============================================================================
-- SECTION 10: REGISTER IN ADR REGISTRY
-- ============================================================================

INSERT INTO fhq_meta.adr_registry (
    adr_id, title, status, category, description, created_at
) VALUES (
    'MIG-097',
    'SYSTEM HEARTBEAT INFRASTRUCTURE',
    'ACTIVE',
    'GOVERNANCE',
    'ARO-20251208: System events table, heartbeat tracking, DEFCON state management.',
    NOW()
) ON CONFLICT (adr_id) DO UPDATE SET
    status = 'ACTIVE',
    updated_at = NOW();

-- ============================================================================
-- SECTION 11: REGISTER FUNCTIONS
-- ============================================================================

INSERT INTO fhq_meta.function_registry (
    function_id, function_name, function_schema, ios_layer, status, description
) VALUES
    ('FN-HB-001', 'publish_heartbeat', 'fhq_governance', 'GOVERNANCE', 'ACTIVE', 'Agent heartbeat publication'),
    ('FN-HB-002', 'check_heartbeats', 'fhq_governance', 'GOVERNANCE', 'ACTIVE', 'Detect stale agents'),
    ('FN-HB-003', 'trigger_defcon_change', 'fhq_governance', 'GOVERNANCE', 'ACTIVE', 'DEFCON level transitions'),
    ('FN-HB-004', 'publish_event', 'fhq_governance', 'GOVERNANCE', 'ACTIVE', 'Central event publication')
ON CONFLICT (function_id) DO UPDATE SET
    status = 'ACTIVE',
    updated_at = NOW();

-- ============================================================================
-- COMPLETION
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '=== MIGRATION 097 COMPLETE ===';
    RAISE NOTICE 'Tables created: system_events, agent_heartbeats, defcon_state, event_type_registry';
    RAISE NOTICE 'Functions created: publish_heartbeat, check_heartbeats, trigger_defcon_change, publish_event';
    RAISE NOTICE 'DEFCON initialized: Level 5 (GREEN)';
    RAISE NOTICE 'ARO-20251208 Section 2: COMPLETE';
END $$;

-- ============================================================================
-- ROLLBACK SCRIPT
-- ============================================================================
/*
DROP FUNCTION IF EXISTS fhq_governance.publish_event;
DROP FUNCTION IF EXISTS fhq_governance.trigger_defcon_change;
DROP FUNCTION IF EXISTS fhq_governance.check_heartbeats;
DROP FUNCTION IF EXISTS fhq_governance.publish_heartbeat;
DROP TABLE IF EXISTS fhq_governance.event_type_registry;
DROP TABLE IF EXISTS fhq_governance.defcon_state;
DROP TABLE IF EXISTS fhq_governance.agent_heartbeats;
DROP TABLE IF EXISTS fhq_governance.system_events;
*/
