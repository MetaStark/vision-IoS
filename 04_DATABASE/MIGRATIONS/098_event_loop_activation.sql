-- ============================================================================
-- MIGRATION 098: EVENT LOOP ACTIVATION (ELOOP v1)
-- ============================================================================
-- CEO DIRECTIVE: ARO-20251208 (Autonomy Restoration Order)
-- Authority: Tier-1 Executive Mandate
-- ADR Binding: ADR-007 (Orchestrator), ADR-014 (Agent Activation), ADR-016 (DEFCON)
-- Gate: G0→G4 Architecture Alignment
-- Executor: STIG (CTO) - EC-003_2026_PRODUCTION
-- ============================================================================
-- PURPOSE: Install the "reflexes" - Event-driven orchestrator infrastructure
-- CRITICAL: This migration TERMINATES fixed-interval execution (cron-like loops)
-- The system must react to EVENTS, not CLOCKS.
-- ============================================================================

-- Migration metadata
DO $$
BEGIN
    RAISE NOTICE '=== MIGRATION 098: EVENT LOOP ACTIVATION (ELOOP v1) ===';
    RAISE NOTICE 'CEO DIRECTIVE: ARO-20251208';
    RAISE NOTICE 'Executor: STIG (CTO)';
    RAISE NOTICE 'Timestamp: %', NOW();
    RAISE NOTICE 'CRITICAL: Terminating fixed-interval execution model';
END $$;

-- ============================================================================
-- SECTION 1: EVENT TRIGGER REGISTRY
-- ============================================================================
-- Defines what events should trigger which agents/components

CREATE TABLE IF NOT EXISTS fhq_governance.event_trigger_registry (
    trigger_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Trigger identification
    trigger_name VARCHAR(100) NOT NULL UNIQUE,
    trigger_category VARCHAR(30) NOT NULL, -- 'MARKET', 'REGIME', 'ALPHA_GRAPH', 'EXECUTION', 'CEIO'

    -- Source event pattern
    source_event_type VARCHAR(50) NOT NULL,
    source_agent VARCHAR(20),            -- Optional: filter by source agent
    source_ios_layer VARCHAR(20),        -- Optional: filter by IoS layer

    -- Conditions (JSONB for flexible filtering)
    trigger_conditions JSONB,            -- e.g., {"severity": ["WARNING", "CRITICAL"]}

    -- Target action
    target_agent VARCHAR(20) NOT NULL,
    target_action VARCHAR(100) NOT NULL, -- Function/method to invoke
    target_priority INTEGER DEFAULT 5,   -- 1-10, lower = higher priority

    -- Regime constraints (per ARO-20251208 Section 8)
    regime_filter VARCHAR(20)[],         -- Only trigger in these regimes (NULL = all)
    defcon_max INTEGER DEFAULT 5,        -- Don't trigger if DEFCON < this

    -- Execution control
    is_active BOOLEAN DEFAULT TRUE,
    cooldown_seconds INTEGER DEFAULT 0,  -- Minimum time between triggers
    last_triggered_at TIMESTAMP WITH TIME ZONE,
    trigger_count INTEGER DEFAULT 0,

    -- Lineage
    lineage_hash VARCHAR(64),
    created_by VARCHAR(20) NOT NULL,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT valid_trigger_agent CHECK (target_agent IN ('FINN', 'CEIO', 'LARS', 'LINE', 'VEGA', 'STIG', 'SYSTEM'))
);

CREATE INDEX IF NOT EXISTS idx_trigger_event_type
    ON fhq_governance.event_trigger_registry(source_event_type);

CREATE INDEX IF NOT EXISTS idx_trigger_target
    ON fhq_governance.event_trigger_registry(target_agent, target_action);

CREATE INDEX IF NOT EXISTS idx_trigger_active
    ON fhq_governance.event_trigger_registry(is_active)
    WHERE is_active = TRUE;

COMMENT ON TABLE fhq_governance.event_trigger_registry IS
'ARO-20251208 Section 4: Event trigger definitions. Maps events to agent actions.
Replaces fixed-interval cron execution with event-driven reflexes.';

-- ============================================================================
-- SECTION 2: EVENT QUEUE (Pending events to process)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.event_queue (
    queue_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Event reference
    event_id UUID NOT NULL REFERENCES fhq_governance.system_events(event_id),
    event_type VARCHAR(50) NOT NULL,

    -- Processing info
    trigger_id UUID REFERENCES fhq_governance.event_trigger_registry(trigger_id),
    target_agent VARCHAR(20) NOT NULL,
    target_action VARCHAR(100) NOT NULL,
    priority INTEGER DEFAULT 5,

    -- Status
    status VARCHAR(20) DEFAULT 'PENDING', -- 'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'SKIPPED'
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- Execution tracking
    queued_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    processing_time_ms INTEGER,

    -- Result
    result_data JSONB,
    error_message TEXT,

    -- Context at queue time
    regime_at_queue VARCHAR(20),
    defcon_at_queue INTEGER,

    CONSTRAINT valid_queue_status CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'SKIPPED'))
);

CREATE INDEX IF NOT EXISTS idx_queue_pending
    ON fhq_governance.event_queue(status, priority ASC, queued_at ASC)
    WHERE status = 'PENDING';

CREATE INDEX IF NOT EXISTS idx_queue_agent
    ON fhq_governance.event_queue(target_agent, status);

CREATE INDEX IF NOT EXISTS idx_queue_event
    ON fhq_governance.event_queue(event_id);

COMMENT ON TABLE fhq_governance.event_queue IS
'ARO-20251208: Event queue for async processing. Events wait here until processed by ELOOP.';

-- ============================================================================
-- SECTION 3: MARKET EVENT TYPES (Type A per ARO-20251208)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.market_event_types (
    event_type_id VARCHAR(30) PRIMARY KEY,
    event_name VARCHAR(100) NOT NULL,
    description TEXT,
    default_priority INTEGER DEFAULT 5,
    typical_response_ms INTEGER,         -- Expected response time
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

INSERT INTO fhq_governance.market_event_types (event_type_id, event_name, description, default_priority, typical_response_ms) VALUES
    ('NEW_CANDLE', 'New Candle', 'New price candle closed', 5, 100),
    ('SPREAD_SPIKE', 'Spread Spike', 'Bid-ask spread exceeded threshold', 3, 50),
    ('VOLATILITY_NODE', 'Volatility Node', 'Volatility regime shift detected', 2, 100),
    ('LIQUIDITY_SHIFT', 'Liquidity Shift', 'Order book liquidity changed significantly', 3, 100),
    ('VOLUME_ANOMALY', 'Volume Anomaly', 'Unusual trading volume detected', 4, 200),
    ('PRICE_BREAKOUT', 'Price Breakout', 'Price broke key level', 2, 50),
    ('GAP_DETECTED', 'Gap Detected', 'Price gap detected', 2, 50)
ON CONFLICT (event_type_id) DO NOTHING;

COMMENT ON TABLE fhq_governance.market_event_types IS
'ARO-20251208 Section 4.1 Type A: Market event definitions.';

-- ============================================================================
-- SECTION 4: REGISTER DEFAULT EVENT TRIGGERS
-- ============================================================================

-- Market Events → CEIO Analysis
INSERT INTO fhq_governance.event_trigger_registry (
    trigger_name, trigger_category, source_event_type, target_agent, target_action,
    target_priority, cooldown_seconds, created_by
) VALUES
    ('MARKET_VOLATILITY_TO_CEIO', 'MARKET', 'VOLATILITY_NODE', 'CEIO', 'analyze_volatility_event', 2, 60, 'STIG'),
    ('MARKET_LIQUIDITY_TO_CEIO', 'MARKET', 'LIQUIDITY_SHIFT', 'CEIO', 'analyze_liquidity_event', 3, 60, 'STIG'),
    ('MARKET_BREAKOUT_TO_CEIO', 'MARKET', 'PRICE_BREAKOUT', 'CEIO', 'analyze_breakout_event', 2, 30, 'STIG')
ON CONFLICT (trigger_name) DO NOTHING;

-- Regime Events → Multiple Agents
INSERT INTO fhq_governance.event_trigger_registry (
    trigger_name, trigger_category, source_event_type, target_agent, target_action,
    target_priority, cooldown_seconds, created_by
) VALUES
    ('REGIME_SHIFT_TO_LARS', 'REGIME', 'REGIME_SHIFT', 'LARS', 'recalibrate_strategy', 1, 300, 'STIG'),
    ('REGIME_SHIFT_TO_CEIO', 'REGIME', 'REGIME_SHIFT', 'CEIO', 'update_regime_context', 2, 60, 'STIG'),
    ('REGIME_SHIFT_TO_LINE', 'REGIME', 'REGIME_SHIFT', 'LINE', 'update_execution_params', 2, 60, 'STIG'),
    ('REGIME_CRISIS_TO_VEGA', 'REGIME', 'REGIME_CRISIS_ENTER', 'VEGA', 'initiate_crisis_protocol', 1, 0, 'STIG')
ON CONFLICT (trigger_name) DO NOTHING;

-- Alpha Graph Events → CEIO
INSERT INTO fhq_governance.event_trigger_registry (
    trigger_name, trigger_category, source_event_type, target_agent, target_action,
    target_priority, cooldown_seconds, created_by
) VALUES
    ('CAUSAL_EDGE_TO_CEIO', 'ALPHA_GRAPH', 'CAUSAL_EDGE_ADDED', 'CEIO', 'process_new_edge', 4, 10, 'STIG'),
    ('GRAPH_RESTRUCTURE_TO_CEIO', 'ALPHA_GRAPH', 'GRAPH_RESTRUCTURE', 'CEIO', 'full_graph_reanalysis', 2, 300, 'STIG'),
    ('SIGNAL_CHANGE_TO_CEIO', 'ALPHA_GRAPH', 'SIGNAL_CONFIDENCE_CHANGE', 'CEIO', 'recalculate_position', 3, 30, 'STIG')
ON CONFLICT (trigger_name) DO NOTHING;

-- Execution Events → LINE/VEGA
INSERT INTO fhq_governance.event_trigger_registry (
    trigger_name, trigger_category, source_event_type, target_agent, target_action,
    target_priority, cooldown_seconds, created_by
) VALUES
    ('SLIPPAGE_TO_LINE', 'EXECUTION', 'SLIPPAGE_ALERT', 'LINE', 'adjust_execution_algo', 2, 60, 'STIG'),
    ('SLIPPAGE_TO_VEGA', 'EXECUTION', 'SLIPPAGE_ALERT', 'VEGA', 'review_slippage_event', 3, 0, 'STIG'),
    ('KILL_SWITCH_TO_VEGA', 'EXECUTION', 'KILL_SWITCH_ACTIVATED', 'VEGA', 'emergency_review', 1, 0, 'STIG')
ON CONFLICT (trigger_name) DO NOTHING;

-- CEIO Events → FINN Research
INSERT INTO fhq_governance.event_trigger_registry (
    trigger_name, trigger_category, source_event_type, target_agent, target_action,
    target_priority, cooldown_seconds, created_by
) VALUES
    ('NEWS_SHOCK_TO_FINN', 'CEIO', 'CEIO_NEWS_SHOCK', 'FINN', 'research_news_impact', 2, 120, 'STIG'),
    ('SENTIMENT_SHIFT_TO_FINN', 'CEIO', 'CEIO_SENTIMENT_SHIFT', 'FINN', 'analyze_sentiment_change', 3, 300, 'STIG')
ON CONFLICT (trigger_name) DO NOTHING;

-- Perception Events → IoS Updates
INSERT INTO fhq_governance.event_trigger_registry (
    trigger_name, trigger_category, source_event_type, target_agent, target_action,
    target_priority, cooldown_seconds, created_by
) VALUES
    ('STRESS_TO_LINE', 'PERCEPTION', 'STRESS_LEVEL_CHANGE', 'LINE', 'adjust_risk_params', 2, 60, 'STIG'),
    ('PERCEPTION_TO_CEIO', 'PERCEPTION', 'PERCEPTION_UPDATE', 'CEIO', 'update_perception_context', 4, 30, 'STIG')
ON CONFLICT (trigger_name) DO NOTHING;

-- DEFCON Events
INSERT INTO fhq_governance.event_trigger_registry (
    trigger_name, trigger_category, source_event_type, source_agent, target_agent, target_action,
    target_priority, defcon_max, created_by
) VALUES
    ('DEFCON_CHANGE_TO_ALL', 'GOVERNANCE', 'DEFCON_CHANGE', 'SYSTEM', 'LARS', 'handle_defcon_change', 1, 5, 'STIG')
ON CONFLICT (trigger_name) DO NOTHING;

-- ============================================================================
-- SECTION 5: EVENT DISPATCHER FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.dispatch_event(
    p_event_id UUID
) RETURNS INTEGER AS $$
DECLARE
    v_event RECORD;
    v_trigger RECORD;
    v_queue_count INTEGER := 0;
    v_current_regime VARCHAR(20);
    v_current_defcon INTEGER;
BEGIN
    -- Get event details
    SELECT * INTO v_event
    FROM fhq_governance.system_events
    WHERE event_id = p_event_id;

    IF v_event IS NULL THEN
        RAISE WARNING 'Event not found: %', p_event_id;
        RETURN 0;
    END IF;

    -- Get current context
    SELECT current_regime INTO v_current_regime
    FROM fhq_meta.regime_state LIMIT 1;

    SELECT defcon_level INTO v_current_defcon
    FROM fhq_governance.defcon_state
    WHERE is_current = TRUE LIMIT 1;

    -- Find matching triggers
    FOR v_trigger IN
        SELECT *
        FROM fhq_governance.event_trigger_registry
        WHERE source_event_type = v_event.event_type
          AND is_active = TRUE
          AND (source_agent IS NULL OR source_agent = v_event.source_agent)
          AND (source_ios_layer IS NULL OR source_ios_layer = v_event.source_ios_layer)
          AND (defcon_max IS NULL OR COALESCE(v_current_defcon, 5) <= defcon_max)
          AND (regime_filter IS NULL OR v_current_regime = ANY(regime_filter))
          AND (cooldown_seconds = 0 OR last_triggered_at IS NULL
               OR last_triggered_at < NOW() - (cooldown_seconds || ' seconds')::INTERVAL)
    LOOP
        -- Queue the event for processing
        INSERT INTO fhq_governance.event_queue (
            event_id, event_type, trigger_id,
            target_agent, target_action, priority,
            regime_at_queue, defcon_at_queue
        ) VALUES (
            p_event_id, v_event.event_type, v_trigger.trigger_id,
            v_trigger.target_agent, v_trigger.target_action, v_trigger.target_priority,
            v_current_regime, v_current_defcon
        );

        -- Update trigger stats
        UPDATE fhq_governance.event_trigger_registry
        SET
            last_triggered_at = NOW(),
            trigger_count = trigger_count + 1,
            updated_at = NOW()
        WHERE trigger_id = v_trigger.trigger_id;

        v_queue_count := v_queue_count + 1;
    END LOOP;

    RETURN v_queue_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.dispatch_event IS
'ARO-20251208 Section 4: Dispatches event to matching triggers, queues actions.
This is the core of event-driven architecture.';

-- ============================================================================
-- SECTION 6: PROCESS QUEUE FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.process_event_queue(
    p_target_agent VARCHAR(20) DEFAULT NULL,
    p_max_items INTEGER DEFAULT 10
) RETURNS TABLE (
    queue_id UUID,
    target_agent VARCHAR(20),
    target_action VARCHAR(100),
    status VARCHAR(20)
) AS $$
DECLARE
    v_item RECORD;
    v_start_time TIMESTAMP;
BEGIN
    -- Get pending items for processing
    FOR v_item IN
        SELECT q.*
        FROM fhq_governance.event_queue q
        WHERE q.status = 'PENDING'
          AND (p_target_agent IS NULL OR q.target_agent = p_target_agent)
        ORDER BY q.priority ASC, q.queued_at ASC
        LIMIT p_max_items
        FOR UPDATE SKIP LOCKED
    LOOP
        v_start_time := clock_timestamp();

        -- Mark as processing
        UPDATE fhq_governance.event_queue
        SET status = 'PROCESSING', started_at = NOW()
        WHERE event_queue.queue_id = v_item.queue_id;

        -- Return the item for external processing
        -- Note: Actual action execution happens outside SQL (in Python)
        queue_id := v_item.queue_id;
        target_agent := v_item.target_agent;
        target_action := v_item.target_action;
        status := 'PROCESSING';

        RETURN NEXT;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.process_event_queue IS
'ARO-20251208: Retrieves pending events from queue for processing.
Agents call this to get their pending actions.';

-- ============================================================================
-- SECTION 7: COMPLETE QUEUE ITEM FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.complete_queue_item(
    p_queue_id UUID,
    p_success BOOLEAN,
    p_result_data JSONB DEFAULT NULL,
    p_error_message TEXT DEFAULT NULL
) RETURNS VOID AS $$
DECLARE
    v_start_time TIMESTAMP;
    v_processing_time INTEGER;
BEGIN
    -- Get start time
    SELECT started_at INTO v_start_time
    FROM fhq_governance.event_queue
    WHERE queue_id = p_queue_id;

    -- Calculate processing time
    v_processing_time := EXTRACT(MILLISECONDS FROM (NOW() - v_start_time))::INTEGER;

    -- Update queue item
    UPDATE fhq_governance.event_queue
    SET
        status = CASE WHEN p_success THEN 'COMPLETED' ELSE 'FAILED' END,
        completed_at = NOW(),
        processing_time_ms = v_processing_time,
        result_data = p_result_data,
        error_message = p_error_message,
        retry_count = CASE WHEN NOT p_success THEN retry_count + 1 ELSE retry_count END
    WHERE queue_id = p_queue_id;

    -- Re-queue failed items if retries remaining
    IF NOT p_success THEN
        UPDATE fhq_governance.event_queue
        SET status = 'PENDING', started_at = NULL
        WHERE queue_id = p_queue_id
          AND retry_count < max_retries;
    END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.complete_queue_item IS
'ARO-20251208: Mark queue item as completed or failed.';

-- ============================================================================
-- SECTION 8: ELOOP CONFIGURATION TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.eloop_config (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Configuration
    config_key VARCHAR(50) NOT NULL UNIQUE,
    config_value JSONB NOT NULL,
    description TEXT,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default configuration
INSERT INTO fhq_governance.eloop_config (config_key, config_value, description) VALUES
    ('ELOOP_ENABLED', 'true', 'Master switch for event loop'),
    ('QUEUE_POLL_INTERVAL_MS', '100', 'How often to poll queue (milliseconds)'),
    ('MAX_CONCURRENT_ACTIONS', '5', 'Maximum concurrent action processing'),
    ('HEARTBEAT_INTERVAL_SECONDS', '30', 'Agent heartbeat interval'),
    ('DEFCON_AUTO_TRIGGER_ENABLED', 'true', 'Allow automatic DEFCON transitions'),
    ('FIXED_INTERVAL_DEPRECATED', 'true', 'ARO-20251208: Fixed intervals are deprecated')
ON CONFLICT (config_key) DO UPDATE SET
    config_value = EXCLUDED.config_value,
    updated_at = NOW();

COMMENT ON TABLE fhq_governance.eloop_config IS
'ARO-20251208: Event loop configuration. ELOOP v1 settings.';

-- ============================================================================
-- SECTION 9: DEPRECATE INTERVAL-BASED EXECUTION
-- ============================================================================

-- Insert governance log entry marking interval execution as deprecated
INSERT INTO fhq_governance.governance_actions_log (
    action_type, action_target, action_target_type,
    initiated_by, decision, decision_rationale,
    vega_reviewed, hash_chain_id
) VALUES (
    'ARO_DEPRECATION',
    'FIXED_INTERVAL_EXECUTION',
    'ARCHITECTURE',
    'STIG',
    'DEPRECATED',
    'ARO-20251208 Section 3: All cron-like interval loops are deprecated. ' ||
    'Event-driven architecture is now mandatory. ' ||
    '--interval and --max-cycles parameters are constitutional violations.',
    FALSE,
    'HC-ARO-20251208-INTERVAL-DEPRECATION'
);

-- ============================================================================
-- SECTION 10: REGISTER IN ADR REGISTRY
-- ============================================================================

INSERT INTO fhq_meta.adr_registry (
    adr_id, title, status, category, description, created_at
) VALUES (
    'MIG-098',
    'EVENT LOOP ACTIVATION (ELOOP v1)',
    'ACTIVE',
    'ARCHITECTURE',
    'ARO-20251208 Section 3-4: Event-driven orchestrator. Terminates fixed-interval execution.',
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
    ('FN-EL-001', 'dispatch_event', 'fhq_governance', 'ELOOP', 'ACTIVE', 'Event dispatcher to triggers'),
    ('FN-EL-002', 'process_event_queue', 'fhq_governance', 'ELOOP', 'ACTIVE', 'Queue processor'),
    ('FN-EL-003', 'complete_queue_item', 'fhq_governance', 'ELOOP', 'ACTIVE', 'Queue completion handler')
ON CONFLICT (function_id) DO UPDATE SET
    status = 'ACTIVE',
    updated_at = NOW();

-- ============================================================================
-- COMPLETION
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '=== MIGRATION 098 COMPLETE ===';
    RAISE NOTICE 'Tables created: event_trigger_registry, event_queue, market_event_types, eloop_config';
    RAISE NOTICE 'Functions created: dispatch_event, process_event_queue, complete_queue_item';
    RAISE NOTICE 'Default triggers registered: 15+ event-to-action mappings';
    RAISE NOTICE '*** CRITICAL: Fixed-interval execution is now DEPRECATED ***';
    RAISE NOTICE 'ARO-20251208 Section 3-4: COMPLETE';
END $$;

-- ============================================================================
-- ROLLBACK SCRIPT
-- ============================================================================
/*
DROP FUNCTION IF EXISTS fhq_governance.complete_queue_item;
DROP FUNCTION IF EXISTS fhq_governance.process_event_queue;
DROP FUNCTION IF EXISTS fhq_governance.dispatch_event;
DROP TABLE IF EXISTS fhq_governance.eloop_config;
DROP TABLE IF EXISTS fhq_governance.event_queue;
DROP TABLE IF EXISTS fhq_governance.market_event_types;
DROP TABLE IF EXISTS fhq_governance.event_trigger_registry;
*/
