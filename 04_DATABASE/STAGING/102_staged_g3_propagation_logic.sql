-- ============================================================================
-- MIGRATION 102: STAGED G3 PROPAGATION LOGIC (NOT FOR EXECUTION)
-- ============================================================================
-- Operation: BRIDGE BUILDER - TASK B
-- Gate: PRE-G3 (STAGING ONLY)
-- Author: STIG (CTO)
-- Date: 2025-12-09
--
-- PURPOSE: This file contains G3 integration logic for Causal Entropy.
--          IT MUST NOT BE EXECUTED until:
--          1. Warmup window expires (2025-12-11 12:00 UTC)
--          2. CEO issues G3 activation directive
--          3. VEGA completes G3 review
--
-- STORAGE: /04_DATABASE/STAGING/ (NOT /MIGRATIONS/)
-- ============================================================================

-- ============================================================================
-- DEPENDENCY MAP
-- ============================================================================
--
-- IoS-003 (Regime Perception) <- fhq_research.regime_state
--    |
--    +-- RECEIVES: Macro regime overlays from MACRO_VIX, MACRO_NET_LIQ
--    +-- RECEIVES: Shock-triggered regime overrides
--    +-- WRITES: regime_state.macro_overlay, regime_state.shock_override
--
-- IoS-006 (Macro Factors) <- fhq_macro.*
--    |
--    +-- SOURCE: macro_nodes (15 nodes)
--    +-- SOURCE: macro_edges (34 edges)
--    +-- SOURCE: shock_signatures (4 classes)
--    +-- SOURCE: shock_events (detection log)
--
-- IoS-007 (Alpha Graph) <- vision_signals.alpha_graph_*
--    |
--    +-- RECEIVES: Causal edge activations
--    +-- RECEIVES: Signal dampening from DAMPENS edges
--    +-- WRITES: alpha_signals.macro_adjustment
--
-- ============================================================================

-- ============================================================================
-- SECTION 1: PLACEHOLDER FUNCTIONS (NOT ACTIVE)
-- ============================================================================

-- 1.1 Macro Regime Propagation Function
-- This function will propagate macro regime states to IoS-003
CREATE OR REPLACE FUNCTION fhq_macro.propagate_macro_regime_to_ios003()
RETURNS TRIGGER AS $$
DECLARE
    v_current_regime TEXT;
    v_macro_overlay JSONB;
    v_propagation_allowed BOOLEAN;
BEGIN
    -- SAFETY CHECK: Verify warmup has expired
    IF NOW() < '2025-12-11 12:00:00+00'::TIMESTAMPTZ THEN
        RAISE NOTICE 'G3 propagation blocked: Warmup active until 2025-12-11 12:00 UTC';
        RETURN NEW;
    END IF;

    -- SAFETY CHECK: Verify propagation is enabled
    SELECT NOT propagation_blocked INTO v_propagation_allowed
    FROM fhq_governance.system_config
    WHERE config_key = 'g3_macro_propagation';

    IF NOT COALESCE(v_propagation_allowed, FALSE) THEN
        RAISE NOTICE 'G3 propagation blocked: System config disabled';
        RETURN NEW;
    END IF;

    -- Build macro overlay from current macro node states
    SELECT jsonb_build_object(
        'vix_regime', (SELECT regime_state FROM fhq_macro.macro_nodes WHERE node_id = 'MACRO_VIX'),
        'liquidity_regime', (SELECT regime_state FROM fhq_macro.macro_nodes WHERE node_id = 'MACRO_NET_LIQ'),
        'credit_regime', (SELECT regime_state FROM fhq_macro.macro_nodes WHERE node_id = 'MACRO_HY_OAS'),
        'propagated_at', NOW()
    ) INTO v_macro_overlay;

    -- PLACEHOLDER: Update IoS-003 regime state
    -- UPDATE fhq_research.regime_state
    -- SET macro_overlay = v_macro_overlay,
    --     updated_at = NOW()
    -- WHERE asset_id IN (SELECT DISTINCT target_node_id FROM fhq_macro.macro_edges WHERE edge_type IN ('LEADS', 'TRANSMITS'));

    -- Log to governance audit
    INSERT INTO fhq_governance.causal_entropy_audit (
        operation, gate, task_group, entity_type, entity_id, operation_type,
        new_value, executed_by, warmup_active, propagation_blocked
    ) VALUES (
        'G3_PROPAGATION', 'G3', 'REGIME', 'REGIME_STATE', 'ALL_ASSETS', 'UPDATE',
        v_macro_overlay, 'SYSTEM', FALSE, FALSE
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 1.2 Shock Propagation Function
-- This function will propagate detected shocks to IoS-003 regime
CREATE OR REPLACE FUNCTION fhq_macro.propagate_shock_to_ios003()
RETURNS TRIGGER AS $$
DECLARE
    v_shock_override JSONB;
    v_propagation_allowed BOOLEAN;
    v_affected_assets TEXT[];
BEGIN
    -- SAFETY CHECK: Verify warmup has expired
    IF NOW() < '2025-12-11 12:00:00+00'::TIMESTAMPTZ THEN
        NEW.propagation_blocked := TRUE;
        NEW.propagated_at := NULL;
        RETURN NEW;
    END IF;

    -- SAFETY CHECK: Verify manual override for first-time shocks
    SELECT NOT propagation_blocked INTO v_propagation_allowed
    FROM fhq_governance.system_config
    WHERE config_key = 'g3_shock_propagation';

    IF NOT COALESCE(v_propagation_allowed, FALSE) THEN
        NEW.propagation_blocked := TRUE;
        RETURN NEW;
    END IF;

    -- Only propagate SEVERE or EXTREME shocks
    IF NEW.severity NOT IN ('SEVERE', 'EXTREME') THEN
        NEW.propagation_blocked := TRUE;
        RETURN NEW;
    END IF;

    -- Build shock override
    v_shock_override := jsonb_build_object(
        'shock_type', NEW.shock_id,
        'severity', NEW.severity,
        'confidence', NEW.confidence_score,
        'override_regime', 'BEAR',
        'minimum_duration_days', 3,
        'decay_function', 'GRADUAL',
        'triggered_at', NOW()
    );

    -- Get affected assets from shock signature bindings
    SELECT ARRAY_AGG(DISTINCT me.target_node_id)
    INTO v_affected_assets
    FROM fhq_macro.macro_edges me
    JOIN fhq_macro.shock_signatures ss ON me.source_node_id = ss.primary_indicator
    WHERE ss.shock_id = NEW.shock_id
    AND me.edge_type IN ('TRANSMITS', 'INHIBITS', 'AMPLIFIES');

    -- PLACEHOLDER: Update IoS-003 regime state with shock override
    -- UPDATE fhq_research.regime_state
    -- SET shock_override = v_shock_override,
    --     regime = 'BEAR',
    --     updated_at = NOW()
    -- WHERE asset_id = ANY(v_affected_assets);

    -- Mark as propagated
    NEW.propagation_blocked := FALSE;
    NEW.propagated_at := NOW();

    -- Log to governance audit
    INSERT INTO fhq_governance.causal_entropy_audit (
        operation, gate, task_group, entity_type, entity_id, operation_type,
        new_value, executed_by, warmup_active, propagation_blocked
    ) VALUES (
        'G3_SHOCK_PROPAGATION', 'G3', 'SHOCK', 'SHOCK_EVENT', NEW.shock_id, 'PROPAGATE',
        v_shock_override, 'SYSTEM', FALSE, FALSE
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 1.3 Causal Edge Activation Function
-- This function activates causal edges and modifies alpha signals
CREATE OR REPLACE FUNCTION fhq_macro.activate_causal_edges()
RETURNS VOID AS $$
DECLARE
    v_edge RECORD;
    v_source_state TEXT;
    v_adjustment FLOAT;
BEGIN
    -- SAFETY CHECK: Verify warmup has expired
    IF NOW() < '2025-12-11 12:00:00+00'::TIMESTAMPTZ THEN
        RAISE EXCEPTION 'G3 edge activation blocked: Warmup active';
    END IF;

    -- Process each active causal edge
    FOR v_edge IN
        SELECT * FROM fhq_macro.macro_edges
        WHERE g2_integrated = TRUE AND is_significant = TRUE
    LOOP
        -- Get source node state
        SELECT regime_state INTO v_source_state
        FROM fhq_macro.macro_nodes
        WHERE node_id = v_edge.source_node_id;

        -- Calculate adjustment based on edge type
        CASE v_edge.edge_type
            WHEN 'LEADS' THEN
                -- LEADS: Apply correlation-based adjustment with lag
                v_adjustment := v_edge.correlation_value * 0.5;

            WHEN 'AMPLIFIES' THEN
                -- AMPLIFIES: Increase vol sensitivity when source stressed
                IF v_source_state IN ('ELEVATED', 'EXTREME') THEN
                    v_adjustment := v_edge.amplification_factor - 1.0;
                ELSE
                    v_adjustment := 0;
                END IF;

            WHEN 'INHIBITS' THEN
                -- INHIBITS: Apply negative adjustment when threshold breached
                -- Threshold check would be done against current value
                v_adjustment := -1 * v_edge.inhibition_score;

            WHEN 'DAMPENS' THEN
                -- DAMPENS: Reduce signal strength
                v_adjustment := -1 * v_edge.damping_factor;

            WHEN 'TRANSMITS' THEN
                -- TRANSMITS: Regime transmission (handled separately)
                v_adjustment := 0;

            ELSE
                v_adjustment := 0;
        END CASE;

        -- PLACEHOLDER: Apply adjustment to alpha signals
        -- UPDATE vision_signals.alpha_signals
        -- SET macro_adjustment = macro_adjustment + v_adjustment,
        --     causal_source = v_edge.source_node_id,
        --     causal_edge_type = v_edge.edge_type,
        --     updated_at = NOW()
        -- WHERE symbol = v_edge.target_node_id
        -- AND signal_date = CURRENT_DATE;

        -- Log edge activation
        INSERT INTO fhq_governance.causal_edge_log (
            edge_type, source_node, target_node, parameters,
            computed_value, window_start, window_end, observations_used,
            computation_hash, computed_by
        ) VALUES (
            v_edge.edge_type, v_edge.source_node_id, v_edge.target_node_id,
            jsonb_build_object('source_state', v_source_state, 'adjustment', v_adjustment),
            v_adjustment, CURRENT_DATE - 252, CURRENT_DATE, 252,
            encode(sha256(concat(v_edge.edge_type, v_edge.source_node_id, v_edge.target_node_id, NOW()::text)::bytea), 'hex'),
            'SYSTEM'
        );
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 2: EVENT HOOKS (STAGED, NOT ACTIVE)
-- ============================================================================

-- 2.1 Trigger for macro node state changes -> regime propagation
-- NOTE: This trigger is CREATED but NOT ENABLED
CREATE OR REPLACE FUNCTION fhq_macro.on_macro_node_state_change()
RETURNS TRIGGER AS $$
BEGIN
    -- Only propagate if regime_state actually changed
    IF OLD.regime_state IS DISTINCT FROM NEW.regime_state THEN
        -- Log the state change
        INSERT INTO fhq_governance.causal_entropy_audit (
            operation, gate, entity_type, entity_id, operation_type,
            old_value, new_value, executed_by, warmup_active, propagation_blocked
        ) VALUES (
            'MACRO_STATE_CHANGE', 'G3', 'NODE', NEW.node_id, 'UPDATE',
            jsonb_build_object('regime_state', OLD.regime_state),
            jsonb_build_object('regime_state', NEW.regime_state),
            'SYSTEM',
            NOW() < '2025-12-11 12:00:00+00'::TIMESTAMPTZ,
            NOW() < '2025-12-11 12:00:00+00'::TIMESTAMPTZ
        );

        -- Call propagation function (which has its own safety checks)
        -- PERFORM fhq_macro.propagate_macro_regime_to_ios003();
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- STAGED TRIGGER (NOT ENABLED)
-- CREATE TRIGGER trg_macro_node_state_change
--     AFTER UPDATE OF regime_state ON fhq_macro.macro_nodes
--     FOR EACH ROW
--     EXECUTE FUNCTION fhq_macro.on_macro_node_state_change();

-- 2.2 Trigger for shock event detection -> shock propagation
-- NOTE: This modifies the existing warmup trigger behavior
CREATE OR REPLACE FUNCTION fhq_macro.on_shock_event_insert()
RETURNS TRIGGER AS $$
BEGIN
    -- Check warmup status
    IF NOW() < '2025-12-11 12:00:00+00'::TIMESTAMPTZ THEN
        NEW.propagation_blocked := TRUE;
        NEW.propagated_at := NULL;
        RETURN NEW;
    END IF;

    -- Post-warmup: Check if propagation is enabled
    -- Then call propagation function
    -- PERFORM fhq_macro.propagate_shock_to_ios003();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 3: SAFETY CONSTRAINTS
-- ============================================================================

-- 3.1 System config table for propagation control
CREATE TABLE IF NOT EXISTS fhq_governance.system_config (
    config_key TEXT PRIMARY KEY,
    config_value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by TEXT
);

-- Insert default config (propagation disabled)
INSERT INTO fhq_governance.system_config (config_key, config_value, description, updated_by)
VALUES
    ('g3_macro_propagation', '{"enabled": false, "requires_ceo_approval": true}'::jsonb,
     'Controls macro regime propagation to IoS-003', 'STIG'),
    ('g3_shock_propagation', '{"enabled": false, "requires_human_review": true}'::jsonb,
     'Controls shock event propagation to IoS-003', 'STIG'),
    ('g3_edge_activation', '{"enabled": false, "batch_only": true}'::jsonb,
     'Controls causal edge activation', 'STIG')
ON CONFLICT (config_key) DO NOTHING;

-- 3.2 Rollback function
CREATE OR REPLACE FUNCTION fhq_macro.rollback_g3_propagation(
    p_rollback_to TIMESTAMPTZ DEFAULT NOW() - INTERVAL '1 hour'
)
RETURNS TABLE(entities_rolled_back INT, audit_entries INT) AS $$
DECLARE
    v_entities INT := 0;
    v_audits INT := 0;
BEGIN
    -- This is a PLACEHOLDER for rollback logic
    -- In production, this would:
    -- 1. Find all propagation events since p_rollback_to
    -- 2. Reverse the regime/signal changes
    -- 3. Mark shock events as blocked again
    -- 4. Log rollback action

    RAISE NOTICE 'Rollback function called for timestamp: %', p_rollback_to;

    -- PLACEHOLDER: Count affected entities
    SELECT COUNT(*) INTO v_audits
    FROM fhq_governance.causal_entropy_audit
    WHERE executed_at > p_rollback_to
    AND gate = 'G3';

    RETURN QUERY SELECT v_entities, v_audits;
END;
$$ LANGUAGE plpgsql;

-- 3.3 Circuit breaker function
CREATE OR REPLACE FUNCTION fhq_macro.emergency_halt_g3()
RETURNS VOID AS $$
BEGIN
    -- Disable all G3 propagation
    UPDATE fhq_governance.system_config
    SET config_value = jsonb_set(config_value, '{enabled}', 'false'),
        updated_at = NOW(),
        updated_by = 'EMERGENCY_HALT'
    WHERE config_key LIKE 'g3_%';

    -- Block all pending shock propagations
    UPDATE fhq_macro.shock_events
    SET propagation_blocked = TRUE
    WHERE propagated_at IS NULL;

    -- Log emergency halt
    INSERT INTO fhq_governance.causal_entropy_audit (
        operation, gate, entity_type, operation_type,
        new_value, executed_by, warmup_active, propagation_blocked
    ) VALUES (
        'EMERGENCY_HALT', 'G3', 'SYSTEM', 'HALT',
        '{"reason": "Emergency halt triggered", "timestamp": "' || NOW() || '"}'::jsonb,
        'CIRCUIT_BREAKER', FALSE, TRUE
    );

    RAISE NOTICE 'G3 EMERGENCY HALT EXECUTED at %', NOW();
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 4: MONITORING VIEWS (READ-ONLY)
-- ============================================================================

-- 4.1 G3 Readiness Status View
CREATE OR REPLACE VIEW fhq_macro.v_g3_readiness_status AS
SELECT
    'warmup_status' AS check_name,
    CASE WHEN NOW() < '2025-12-11 12:00:00+00'::TIMESTAMPTZ
         THEN 'ACTIVE' ELSE 'EXPIRED' END AS status,
    '2025-12-11 12:00:00+00'::TIMESTAMPTZ AS expiration
UNION ALL
SELECT
    'macro_nodes' AS check_name,
    CASE WHEN (SELECT COUNT(*) FROM fhq_macro.macro_nodes WHERE g2_integrated) >= 15
         THEN 'READY' ELSE 'NOT_READY' END AS status,
    NULL AS expiration
UNION ALL
SELECT
    'macro_edges' AS check_name,
    CASE WHEN (SELECT COUNT(*) FROM fhq_macro.macro_edges WHERE g2_integrated) >= 30
         THEN 'READY' ELSE 'NOT_READY' END AS status,
    NULL AS expiration
UNION ALL
SELECT
    'shock_signatures' AS check_name,
    CASE WHEN (SELECT COUNT(*) FROM fhq_macro.shock_signatures WHERE g2_integrated) >= 4
         THEN 'READY' ELSE 'NOT_READY' END AS status,
    NULL AS expiration
UNION ALL
SELECT
    'propagation_functions' AS check_name,
    'STAGED' AS status,
    NULL AS expiration;

-- 4.2 Propagation Status View
CREATE OR REPLACE VIEW fhq_macro.v_propagation_status AS
SELECT
    sc.config_key,
    sc.config_value->>'enabled' AS enabled,
    sc.description,
    sc.updated_at,
    sc.updated_by
FROM fhq_governance.system_config sc
WHERE sc.config_key LIKE 'g3_%';

-- ============================================================================
-- SECTION 5: G3 ACTIVATION CHECKLIST (DOCUMENTATION)
-- ============================================================================
/*
G3 ACTIVATION CHECKLIST:

PRE-REQUISITES:
[ ] 1. Warmup window expired (2025-12-11 12:00 UTC)
[ ] 2. CEO G3 activation directive received
[ ] 3. VEGA G3 review completed and approved
[ ] 4. Historical shock simulation reviewed
[ ] 5. Narrative overlay reviewed

ACTIVATION STEPS:
[ ] 1. Move this file from /STAGING/ to /MIGRATIONS/
[ ] 2. Execute migration with VEGA oversight
[ ] 3. Enable propagation triggers one at a time:
       a. Enable macro regime propagation
       b. Monitor for 24 hours
       c. Enable shock propagation (with human review)
       d. Monitor for 24 hours
       e. Enable edge activation (batch mode only)

ROLLBACK PROCEDURE:
1. Call fhq_macro.emergency_halt_g3()
2. Call fhq_macro.rollback_g3_propagation(target_timestamp)
3. Disable triggers manually if needed
4. Log incident in governance audit

MONITORING:
- Check fhq_macro.v_g3_readiness_status hourly
- Check fhq_macro.v_propagation_status after each change
- Monitor fhq_governance.causal_entropy_audit for anomalies
*/

-- ============================================================================
-- DO NOT EXECUTE - STAGING ONLY
-- ============================================================================
-- This file is stored in /04_DATABASE/STAGING/
-- Move to /04_DATABASE/MIGRATIONS/ only after:
-- 1. CEO G3 directive
-- 2. VEGA G3 approval
-- 3. Warmup expiration
-- ============================================================================
