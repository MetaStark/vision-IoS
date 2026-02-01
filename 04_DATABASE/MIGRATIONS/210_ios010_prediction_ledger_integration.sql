-- ============================================================
-- MIGRATION 210: IOS-010 PREDICTION LEDGER INTEGRATION
-- ============================================================
-- Directive: CEO-DIR-2026-007
-- Authority Chain: ADR-013 -> ADR-017 -> ADR-004 -> CEO-DIR-2026-006
-- Author: STIG (CTO)
-- Date: 2026-01-07
-- Classification: STRATEGIC-FUNDAMENTAL (Class A+)
--
-- PURPOSE:
--   Implement IoS-010 Prediction Ledger integration infrastructure
--   per CEO-DIR-2026-007 mandate: "Transform FjordHQ from a system
--   that forms beliefs into a system that earns experience."
--
-- SCOPE:
--   - fhq_governance.epistemic_lessons (new table)
--   - Immutability triggers for outcome_ledger and forecast_outcome_pairs
--   - Reconciliation helper functions
--   - Suppression Regret Index computation
--   - IoS-010 daemon task registry entries
--
-- CONSTITUTIONAL ALIGNMENT:
--   - ADR-013: Canonical one-true-source for lessons
--   - ADR-017: Orchestrator integration
--   - CEO-DIR-2026-006: Epistemic Memory & Truth Reconciliation
--   - CEO-DIR-2026-007: Daemon Delivery & Orchestrator Integration
--
-- ============================================================

BEGIN;

-- ============================================================
-- SECTION 1: EPISTEMIC LESSONS TABLE
-- ============================================================
-- Per CEO-DIR-2026-006 Section 3.3 Error Taxonomy

CREATE TABLE IF NOT EXISTS fhq_governance.epistemic_lessons (
    lesson_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lesson_source TEXT NOT NULL CHECK (lesson_source IN (
        'RECONCILIATION', 'SUPPRESSION', 'SKILL_METRICS', 'DRIFT_DETECTION'
    )),
    lesson_category TEXT NOT NULL CHECK (lesson_category IN (
        'CALIBRATION_ERROR', 'DIRECTIONAL_ERROR', 'TIMING_ERROR',
        'REGIME_MISCLASSIFICATION', 'SUPPRESSION_REGRET', 'SUPPRESSION_WISDOM',
        'DRIFT_DETECTED', 'SKILL_DEGRADATION', 'SKILL_IMPROVEMENT'
    )),
    lesson_severity TEXT NOT NULL CHECK (lesson_severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),

    -- Source references (nullable - depends on lesson_source)
    source_forecast_id UUID REFERENCES fhq_research.forecast_ledger(forecast_id),
    source_outcome_id UUID REFERENCES fhq_research.outcome_ledger(outcome_id),
    source_suppression_id UUID,  -- References epistemic_suppression_ledger
    source_pair_id UUID REFERENCES fhq_research.forecast_outcome_pairs(pair_id),
    source_skill_metric_id UUID REFERENCES fhq_research.forecast_skill_metrics(metric_id),

    -- Error quantification
    error_magnitude NUMERIC,
    error_direction TEXT CHECK (error_direction IN ('OVER', 'UNDER', 'WRONG', 'LATE', 'EARLY')),

    -- Context
    affected_asset_id TEXT,
    affected_regime TEXT,
    affected_horizon_hours INTEGER,

    -- Lesson content
    lesson_description TEXT NOT NULL,
    recommended_action TEXT,

    -- Feedback tracking (Phase 5 - initially NULL)
    action_taken TEXT,
    action_timestamp TIMESTAMPTZ,
    action_agent TEXT,
    action_approved_by TEXT,

    -- Governance
    lesson_hash TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'STIG',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_epistemic_lessons_category ON fhq_governance.epistemic_lessons(lesson_category);
CREATE INDEX IF NOT EXISTS idx_epistemic_lessons_severity ON fhq_governance.epistemic_lessons(lesson_severity);
CREATE INDEX IF NOT EXISTS idx_epistemic_lessons_asset ON fhq_governance.epistemic_lessons(affected_asset_id);
CREATE INDEX IF NOT EXISTS idx_epistemic_lessons_timestamp ON fhq_governance.epistemic_lessons(lesson_timestamp);
CREATE INDEX IF NOT EXISTS idx_epistemic_lessons_source ON fhq_governance.epistemic_lessons(lesson_source);

COMMENT ON TABLE fhq_governance.epistemic_lessons IS
'CEO-DIR-2026-007: Canonical store for lessons extracted from forecast reconciliation, suppression analysis, and skill metric evaluation. Phase 5 feedback loop LOCKED until 85% reconciliation rate sustained 30 days.';

-- ============================================================
-- SECTION 2: SUPPRESSION REGRET INDEX TABLE
-- ============================================================
-- Per CEO-DIR-2026-007 Section 5.2

CREATE TABLE IF NOT EXISTS fhq_governance.suppression_regret_index (
    regret_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    computation_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,

    -- Regret metrics
    total_suppressions INTEGER NOT NULL,
    correct_suppressions INTEGER NOT NULL,  -- belief_wrong, suppression was wise
    regrettable_suppressions INTEGER NOT NULL,  -- belief_correct, suppression was regret

    suppression_regret_rate NUMERIC NOT NULL,  -- regrettable / total
    suppression_wisdom_rate NUMERIC NOT NULL,  -- correct / total

    -- Alpha foregone (quantified cost of conservatism)
    estimated_alpha_foregone NUMERIC,  -- Sum of expected returns from suppressed correct beliefs
    realized_alpha_foregone NUMERIC,   -- Sum of actual returns that would have been earned

    -- Breakdown by category
    regret_by_regime JSONB,  -- {"BULL": 5, "BEAR": 3, ...}
    regret_by_asset JSONB,   -- {"BTC-USD": 2, "SPY": 1, ...}

    -- Governance
    computation_hash TEXT NOT NULL,
    computed_by TEXT NOT NULL DEFAULT 'STIG',
    is_vega_attested BOOLEAN DEFAULT FALSE,
    vega_attestation_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_suppression_regret_period ON fhq_governance.suppression_regret_index(period_start, period_end);

COMMENT ON TABLE fhq_governance.suppression_regret_index IS
'CEO-DIR-2026-007 Section 5.2: Quantified alpha foregone when policy suppressed beliefs that later reconciled as correct. "The cost of conservatism must be measurable, or it does not exist."';

-- ============================================================
-- SECTION 3: IMMUTABILITY TRIGGERS
-- ============================================================

-- Outcome immutability trigger
CREATE OR REPLACE FUNCTION fhq_research.enforce_outcome_immutability()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO fhq_governance.governance_actions_log (
        action_type, action_target, action_target_type,
        initiated_by, decision, decision_rationale, metadata
    ) VALUES (
        'IMMUTABILITY_VIOLATION_ATTEMPT',
        OLD.outcome_id::text,
        'fhq_research.outcome_ledger',
        COALESCE(current_setting('app.current_agent', true), current_user),
        'BLOCKED',
        'CEO-DIR-2026-007: outcome_ledger is immutable. ' || TG_OP || ' prohibited.',
        jsonb_build_object('attempted_operation', TG_OP, 'outcome_id', OLD.outcome_id)
    );
    RAISE EXCEPTION 'IMMUTABILITY_VIOLATION: outcome_ledger records cannot be modified';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_outcome_ledger_immutable ON fhq_research.outcome_ledger;
CREATE TRIGGER trg_outcome_ledger_immutable
    BEFORE UPDATE OR DELETE ON fhq_research.outcome_ledger
    FOR EACH ROW
    EXECUTE FUNCTION fhq_research.enforce_outcome_immutability();

-- Forecast-outcome pairs immutability trigger
CREATE OR REPLACE FUNCTION fhq_research.enforce_pair_immutability()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO fhq_governance.governance_actions_log (
        action_type, action_target, action_target_type,
        initiated_by, decision, decision_rationale, metadata
    ) VALUES (
        'IMMUTABILITY_VIOLATION_ATTEMPT',
        OLD.pair_id::text,
        'fhq_research.forecast_outcome_pairs',
        COALESCE(current_setting('app.current_agent', true), current_user),
        'BLOCKED',
        'CEO-DIR-2026-007: forecast_outcome_pairs is immutable. ' || TG_OP || ' prohibited.',
        jsonb_build_object('attempted_operation', TG_OP, 'pair_id', OLD.pair_id)
    );
    RAISE EXCEPTION 'IMMUTABILITY_VIOLATION: forecast_outcome_pairs records cannot be modified';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_pair_immutable ON fhq_research.forecast_outcome_pairs;
CREATE TRIGGER trg_pair_immutable
    BEFORE UPDATE OR DELETE ON fhq_research.forecast_outcome_pairs
    FOR EACH ROW
    EXECUTE FUNCTION fhq_research.enforce_pair_immutability();

-- ============================================================
-- SECTION 4: RECONCILIATION HELPER FUNCTIONS
-- ============================================================

-- Get unreconciled forecasts within horizon
CREATE OR REPLACE FUNCTION fhq_research.get_unreconciled_forecasts(
    p_max_age_hours INTEGER DEFAULT 168
)
RETURNS TABLE (
    forecast_id UUID,
    forecast_type TEXT,
    forecast_domain TEXT,
    forecast_value TEXT,
    forecast_probability NUMERIC,
    forecast_made_at TIMESTAMPTZ,
    forecast_valid_until TIMESTAMPTZ,
    forecast_horizon_hours INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        f.forecast_id,
        f.forecast_type,
        f.forecast_domain,
        f.forecast_value,
        f.forecast_probability,
        f.forecast_made_at,
        f.forecast_valid_until,
        f.forecast_horizon_hours
    FROM fhq_research.forecast_ledger f
    WHERE f.is_resolved = FALSE
      AND f.forecast_valid_until <= NOW()
      AND f.forecast_made_at > NOW() - (p_max_age_hours || ' hours')::interval
    ORDER BY f.forecast_valid_until ASC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Get matching outcomes for a forecast
CREATE OR REPLACE FUNCTION fhq_research.get_matching_outcomes(
    p_forecast_domain TEXT,
    p_forecast_type TEXT,
    p_valid_from TIMESTAMPTZ,
    p_valid_until TIMESTAMPTZ,
    p_tolerance_hours INTEGER DEFAULT 6
)
RETURNS TABLE (
    outcome_id UUID,
    outcome_type TEXT,
    outcome_domain TEXT,
    outcome_value TEXT,
    outcome_timestamp TIMESTAMPTZ,
    match_confidence NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        o.outcome_id,
        o.outcome_type,
        o.outcome_domain,
        o.outcome_value,
        o.outcome_timestamp,
        -- Match confidence based on temporal proximity
        1.0 - (EXTRACT(EPOCH FROM ABS(o.outcome_timestamp - p_valid_until)) /
               (p_tolerance_hours * 3600.0))::numeric AS match_confidence
    FROM fhq_research.outcome_ledger o
    WHERE o.outcome_domain = p_forecast_domain
      AND o.outcome_type = p_forecast_type
      AND o.outcome_timestamp BETWEEN p_valid_from AND (p_valid_until + (p_tolerance_hours || ' hours')::interval)
    ORDER BY ABS(EXTRACT(EPOCH FROM (o.outcome_timestamp - p_valid_until))) ASC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql STABLE;

-- Compute Brier score for a single forecast-outcome pair
CREATE OR REPLACE FUNCTION fhq_research.compute_brier_score(
    p_forecast_probability NUMERIC,
    p_forecast_value TEXT,
    p_outcome_value TEXT
)
RETURNS NUMERIC AS $$
DECLARE
    v_outcome_indicator NUMERIC;
BEGIN
    -- Binary outcome: 1 if forecast value matches outcome, 0 otherwise
    v_outcome_indicator := CASE WHEN p_forecast_value = p_outcome_value THEN 1.0 ELSE 0.0 END;

    -- Brier score = (probability - outcome)^2
    -- Lower is better (0 = perfect, 1 = worst)
    RETURN POWER(p_forecast_probability - v_outcome_indicator, 2);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================
-- SECTION 5: SUPPRESSION REGRET COMPUTATION
-- ============================================================

CREATE OR REPLACE FUNCTION fhq_governance.compute_suppression_regret(
    p_period_start TIMESTAMPTZ,
    p_period_end TIMESTAMPTZ
)
RETURNS UUID AS $$
DECLARE
    v_regret_id UUID;
    v_total INTEGER;
    v_correct INTEGER;
    v_regrettable INTEGER;
    v_regret_rate NUMERIC;
    v_wisdom_rate NUMERIC;
    v_regret_by_regime JSONB;
    v_regret_by_asset JSONB;
    v_hash TEXT;
BEGIN
    -- Count suppressions with reconciled outcomes
    WITH suppression_outcomes AS (
        SELECT
            esl.suppression_id,
            esl.asset_id,
            mbs.dominant_regime AS believed_regime,
            sps.chosen_regime AS policy_regime,
            o.outcome_value AS realized_regime,
            CASE
                WHEN mbs.dominant_regime = o.outcome_value THEN 'REGRET'  -- belief was correct
                ELSE 'WISDOM'  -- belief was wrong, suppression was wise
            END AS regret_classification
        FROM fhq_governance.epistemic_suppression_ledger esl
        JOIN fhq_perception.model_belief_state mbs ON esl.belief_id = mbs.belief_id
        JOIN fhq_perception.sovereign_policy_state sps ON esl.policy_id = sps.policy_id
        -- Match to outcomes (realized regime at T+1)
        LEFT JOIN LATERAL (
            SELECT ol.outcome_value
            FROM fhq_research.outcome_ledger ol
            WHERE ol.outcome_domain = esl.asset_id
              AND ol.outcome_type = 'REGIME_CLASSIFICATION'
              AND ol.outcome_timestamp BETWEEN mbs.belief_timestamp AND mbs.belief_timestamp + INTERVAL '48 hours'
            ORDER BY ol.outcome_timestamp ASC
            LIMIT 1
        ) o ON TRUE
        WHERE esl.suppression_timestamp BETWEEN p_period_start AND p_period_end
          AND o.outcome_value IS NOT NULL  -- Only count those with reconciled outcomes
    )
    SELECT
        COUNT(*),
        COUNT(*) FILTER (WHERE regret_classification = 'WISDOM'),
        COUNT(*) FILTER (WHERE regret_classification = 'REGRET')
    INTO v_total, v_correct, v_regrettable
    FROM suppression_outcomes;

    -- Handle edge case of no data
    IF v_total = 0 THEN
        v_regret_rate := 0;
        v_wisdom_rate := 0;
    ELSE
        v_regret_rate := v_regrettable::numeric / v_total;
        v_wisdom_rate := v_correct::numeric / v_total;
    END IF;

    -- Compute breakdown by regime
    WITH regime_breakdown AS (
        SELECT
            mbs.dominant_regime,
            COUNT(*) FILTER (WHERE mbs.dominant_regime = o.outcome_value) AS regret_count
        FROM fhq_governance.epistemic_suppression_ledger esl
        JOIN fhq_perception.model_belief_state mbs ON esl.belief_id = mbs.belief_id
        LEFT JOIN LATERAL (
            SELECT ol.outcome_value
            FROM fhq_research.outcome_ledger ol
            WHERE ol.outcome_domain = esl.asset_id
              AND ol.outcome_type = 'REGIME_CLASSIFICATION'
              AND ol.outcome_timestamp BETWEEN mbs.belief_timestamp AND mbs.belief_timestamp + INTERVAL '48 hours'
            LIMIT 1
        ) o ON TRUE
        WHERE esl.suppression_timestamp BETWEEN p_period_start AND p_period_end
        GROUP BY mbs.dominant_regime
    )
    SELECT jsonb_object_agg(dominant_regime, regret_count)
    INTO v_regret_by_regime
    FROM regime_breakdown;

    -- Compute breakdown by asset
    WITH asset_breakdown AS (
        SELECT
            esl.asset_id,
            COUNT(*) FILTER (WHERE mbs.dominant_regime = o.outcome_value) AS regret_count
        FROM fhq_governance.epistemic_suppression_ledger esl
        JOIN fhq_perception.model_belief_state mbs ON esl.belief_id = mbs.belief_id
        LEFT JOIN LATERAL (
            SELECT ol.outcome_value
            FROM fhq_research.outcome_ledger ol
            WHERE ol.outcome_domain = esl.asset_id
              AND ol.outcome_type = 'REGIME_CLASSIFICATION'
            LIMIT 1
        ) o ON TRUE
        WHERE esl.suppression_timestamp BETWEEN p_period_start AND p_period_end
        GROUP BY esl.asset_id
        HAVING COUNT(*) FILTER (WHERE mbs.dominant_regime = o.outcome_value) > 0
        ORDER BY regret_count DESC
        LIMIT 20
    )
    SELECT jsonb_object_agg(asset_id, regret_count)
    INTO v_regret_by_asset
    FROM asset_breakdown;

    -- Compute hash
    v_hash := encode(sha256(
        (p_period_start::text || p_period_end::text || v_total::text ||
         v_regret_rate::text || v_wisdom_rate::text)::bytea
    ), 'hex');

    -- Insert record
    INSERT INTO fhq_governance.suppression_regret_index (
        period_start, period_end,
        total_suppressions, correct_suppressions, regrettable_suppressions,
        suppression_regret_rate, suppression_wisdom_rate,
        regret_by_regime, regret_by_asset,
        computation_hash
    ) VALUES (
        p_period_start, p_period_end,
        v_total, v_correct, v_regrettable,
        v_regret_rate, v_wisdom_rate,
        COALESCE(v_regret_by_regime, '{}'::jsonb),
        COALESCE(v_regret_by_asset, '{}'::jsonb),
        v_hash
    )
    RETURNING regret_id INTO v_regret_id;

    RETURN v_regret_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.compute_suppression_regret(TIMESTAMPTZ, TIMESTAMPTZ) IS
'CEO-DIR-2026-007 Section 5.2: Computes Suppression Regret Index - quantified alpha foregone when policy suppressed beliefs that later reconciled as correct.';

-- ============================================================
-- SECTION 6: IOS-010 DAEMON TASK REGISTRY ENTRIES
-- ============================================================

-- belief_to_forecast_materializer
INSERT INTO fhq_governance.task_registry (
    task_id, description, domain, assigned_to, status, metadata,
    task_name, task_type, agent_id, task_description, task_config, enabled
) VALUES (
    gen_random_uuid(),
    'IoS-010: Materialize model beliefs as forecast records',
    'EPISTEMIC',
    'STIG',
    'pending',
    '{"directive": "CEO-DIR-2026-007", "ios": "IoS-010", "phase": 2}'::jsonb,
    'ios010_belief_materializer',
    'VISION_FUNCTION',
    'STIG',
    'Converts immutable model_belief_state into time-horizon-specific forecasts. No policy influence permitted.',
    jsonb_build_object(
        'script', 'ios010_belief_to_forecast_materializer.py',
        'schedule', '0 0 * * *',
        'gate_level', 'G3',
        'priority', 50,
        'timeout_seconds', 300
    ),
    TRUE
) ON CONFLICT (task_name) DO UPDATE SET
    task_config = EXCLUDED.task_config,
    enabled = TRUE,
    updated_at = NOW();

-- outcome_capture_daemon
INSERT INTO fhq_governance.task_registry (
    task_id, description, domain, assigned_to, status, metadata,
    task_name, task_type, agent_id, task_description, task_config, enabled
) VALUES (
    gen_random_uuid(),
    'IoS-010: Capture realized market outcomes',
    'EPISTEMIC',
    'STIG',
    'pending',
    '{"directive": "CEO-DIR-2026-007", "ios": "IoS-010", "phase": 2}'::jsonb,
    'ios010_outcome_capture',
    'VISION_FUNCTION',
    'STIG',
    'Captures realized market outcomes at defined T+n horizons. Outcomes are immutable and timestamp-bound.',
    jsonb_build_object(
        'script', 'ios010_outcome_capture_daemon.py',
        'schedule', '0 */4 * * *',
        'gate_level', 'G3',
        'priority', 51,
        'timeout_seconds', 300
    ),
    TRUE
) ON CONFLICT (task_name) DO UPDATE SET
    task_config = EXCLUDED.task_config,
    enabled = TRUE,
    updated_at = NOW();

-- forecast_reconciliation_daemon
INSERT INTO fhq_governance.task_registry (
    task_id, description, domain, assigned_to, status, metadata,
    task_name, task_type, agent_id, task_description, task_config, enabled
) VALUES (
    gen_random_uuid(),
    'IoS-010: Reconcile forecasts with outcomes',
    'EPISTEMIC',
    'STIG',
    'pending',
    '{"directive": "CEO-DIR-2026-007", "ios": "IoS-010", "phase": 3}'::jsonb,
    'ios010_forecast_reconciliation',
    'VISION_FUNCTION',
    'STIG',
    'Pairs forecasts with outcomes. Classifies epistemic error types per IoS-010 taxonomy.',
    jsonb_build_object(
        'script', 'ios010_forecast_reconciliation_daemon.py',
        'schedule', '30 0 * * *',
        'gate_level', 'G3',
        'priority', 52,
        'timeout_seconds', 600
    ),
    TRUE
) ON CONFLICT (task_name) DO UPDATE SET
    task_config = EXCLUDED.task_config,
    enabled = TRUE,
    updated_at = NOW();

-- skill_metrics_aggregator
INSERT INTO fhq_governance.task_registry (
    task_id, description, domain, assigned_to, status, metadata,
    task_name, task_type, agent_id, task_description, task_config, enabled
) VALUES (
    gen_random_uuid(),
    'IoS-010: Aggregate skill metrics with Suppression Regret Index',
    'EPISTEMIC',
    'STIG',
    'pending',
    '{"directive": "CEO-DIR-2026-007", "ios": "IoS-010", "phase": 4}'::jsonb,
    'ios010_skill_metrics_aggregator',
    'VISION_FUNCTION',
    'STIG',
    'Aggregates reconciliation results into rolling skill metrics. Outputs calibration, timing, regime, and suppression performance. Computes Suppression Regret Index.',
    jsonb_build_object(
        'script', 'ios010_skill_metrics_aggregator.py',
        'schedule', '0 1 * * 0',
        'gate_level', 'G3',
        'priority', 53,
        'timeout_seconds', 600
    ),
    TRUE
) ON CONFLICT (task_name) DO UPDATE SET
    task_config = EXCLUDED.task_config,
    enabled = TRUE,
    updated_at = NOW();

-- lesson_extraction_engine
INSERT INTO fhq_governance.task_registry (
    task_id, description, domain, assigned_to, status, metadata,
    task_name, task_type, agent_id, task_description, task_config, enabled
) VALUES (
    gen_random_uuid(),
    'IoS-010: Extract lessons from reconciled truth',
    'EPISTEMIC',
    'STIG',
    'pending',
    '{"directive": "CEO-DIR-2026-007", "ios": "IoS-010", "phase": 4}'::jsonb,
    'ios010_lesson_extraction',
    'VISION_FUNCTION',
    'STIG',
    'Converts reconciled truth into structured lessons. Writes to epistemic_lessons. No direct policy mutation (Phase 5 LOCKED).',
    jsonb_build_object(
        'script', 'ios010_lesson_extraction_engine.py',
        'schedule', '0 2 * * 0',
        'gate_level', 'G3',
        'priority', 54,
        'timeout_seconds', 600
    ),
    TRUE
) ON CONFLICT (task_name) DO UPDATE SET
    task_config = EXCLUDED.task_config,
    enabled = TRUE,
    updated_at = NOW();

-- ============================================================
-- SECTION 7: GOVERNANCE LOG ENTRY
-- ============================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type, action_target, action_target_type,
    initiated_by, decision, decision_rationale, metadata
) VALUES (
    'CONSTITUTIONAL_ENFORCEMENT',
    'CEO-DIR-2026-007',
    'MIGRATION',
    'CEO',
    'EXECUTED',
    'Migration 210: IoS-010 Prediction Ledger Integration deployed. FjordHQ now has epistemic memory infrastructure.',
    jsonb_build_object(
        'migration', '210_ios010_prediction_ledger_integration.sql',
        'directive', 'CEO-DIR-2026-007',
        'classification', 'STRATEGIC-FUNDAMENTAL (Class A+)',
        'tables_created', jsonb_build_array(
            'fhq_governance.epistemic_lessons',
            'fhq_governance.suppression_regret_index'
        ),
        'triggers_created', jsonb_build_array(
            'trg_outcome_ledger_immutable',
            'trg_pair_immutable'
        ),
        'functions_created', jsonb_build_array(
            'fhq_research.get_unreconciled_forecasts()',
            'fhq_research.get_matching_outcomes()',
            'fhq_research.compute_brier_score()',
            'fhq_governance.compute_suppression_regret()'
        ),
        'daemons_registered', jsonb_build_array(
            'ios010_belief_materializer',
            'ios010_outcome_capture',
            'ios010_forecast_reconciliation',
            'ios010_skill_metrics_aggregator',
            'ios010_lesson_extraction'
        ),
        'phase_5_status', 'LOCKED - awaiting 85% reconciliation rate x 30 days',
        'executed_by', 'STIG',
        'timestamp', NOW()
    )
);

COMMIT;

-- ============================================================
-- VERIFICATION
-- ============================================================

SELECT 'Migration 210: IoS-010 Prediction Ledger Integration - DEPLOYED' as status;

-- Verify tables
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'fhq_governance'
AND table_name IN ('epistemic_lessons', 'suppression_regret_index');

-- Verify task registry entries
SELECT task_name, enabled, task_config->>'schedule' as schedule
FROM fhq_governance.task_registry
WHERE task_name LIKE 'ios010_%';

-- Verify triggers
SELECT tgname FROM pg_trigger
WHERE tgname IN ('trg_outcome_ledger_immutable', 'trg_pair_immutable');
