-- Migration 253: CFAO × CRIO Synthetic Stress-Testing Integration
-- Directive B: Synthetic Regime Scenarios with CRIO Falsification
-- Architecture: CFAO Shadow Mode → Synthetic Scenarios → CRIO Falsification → UMA Analysis

BEGIN;

-- ============================================================================
-- Synthetic Scenarios Table (if not exists)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.synthetic_scenarios (
    scenario_id SERIAL PRIMARY KEY,
    scenario_type TEXT NOT NULL,  -- 'regime_shift', 'volatility_spike', 'correlation_break', 'liquidity_crisis'
    scenario_name TEXT NOT NULL,
    generation_source TEXT DEFAULT 'CFAO',  -- Always CFAO for shadow mode
    is_canonical BOOLEAN DEFAULT FALSE,  -- ALWAYS FALSE - synthetic is never canonical
    base_regime TEXT NOT NULL,
    synthetic_regime TEXT NOT NULL,
    scenario_parameters JSONB NOT NULL,
    generation_timestamp TIMESTAMPTZ DEFAULT NOW(),
    expiry_timestamp TIMESTAMPTZ,
    -- Phase B additions
    crio_falsification_result JSONB,
    uma_preparedness_score DECIMAL(5,4),
    learning_signal_weight DECIMAL(5,4),  -- NOT lvi_contribution - LVI computed at aggregation only
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE fhq_research.synthetic_scenarios IS
    'CFAO Shadow Mode synthetic scenarios. is_canonical is ALWAYS FALSE. Per EC-014 Section 5.4.';

COMMENT ON COLUMN fhq_research.synthetic_scenarios.learning_signal_weight IS
    'Scenario relevance for learning. LVI computed ONLY in UMA aggregation layer, never stored as partial.';

-- Enforce is_canonical = FALSE constraint
ALTER TABLE fhq_research.synthetic_scenarios
DROP CONSTRAINT IF EXISTS synthetic_never_canonical;

ALTER TABLE fhq_research.synthetic_scenarios
ADD CONSTRAINT synthetic_never_canonical CHECK (is_canonical = FALSE);

-- ============================================================================
-- Counterfactual Tags Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.counterfactual_tags (
    tag_id SERIAL PRIMARY KEY,
    scenario_id INTEGER REFERENCES fhq_research.synthetic_scenarios(scenario_id),
    tag_type TEXT NOT NULL,  -- 'regime_shift', 'volatility_spike', 'correlation_break', 'black_swan'
    synthetic_regime TEXT NOT NULL,
    baseline_regime TEXT NOT NULL,
    delta_magnitude DECIMAL(10,6),
    delta_description TEXT,
    crio_validated BOOLEAN DEFAULT FALSE,
    crio_validation_timestamp TIMESTAMPTZ,
    uma_reviewed BOOLEAN DEFAULT FALSE,
    uma_review_timestamp TIMESTAMPTZ,
    preparedness_gap DECIMAL(5,4),  -- Synthetic vs real readiness gap
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_tag_type CHECK (tag_type IN (
        'regime_shift', 'volatility_spike', 'correlation_break',
        'black_swan', 'liquidity_crisis', 'macro_shock'
    ))
);

COMMENT ON TABLE fhq_research.counterfactual_tags IS
    'Tags linking synthetic scenarios to counterfactual analysis. Separates reality vs possibility.';

-- ============================================================================
-- CRIO Falsification Queue
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.crio_falsification_queue (
    queue_id SERIAL PRIMARY KEY,
    scenario_id INTEGER REFERENCES fhq_research.synthetic_scenarios(scenario_id),
    queue_status TEXT DEFAULT 'PENDING',  -- 'PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED'
    priority INTEGER DEFAULT 5,  -- 1=highest, 10=lowest
    queued_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    falsification_result JSONB,
    passed BOOLEAN,
    failure_reason TEXT,
    CONSTRAINT valid_queue_status CHECK (queue_status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED'))
);

COMMENT ON TABLE fhq_research.crio_falsification_queue IS
    'Queue for CRIO falsification of synthetic scenarios. Per Directive B flow.';

-- ============================================================================
-- UMA Preparedness Analysis Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.uma_preparedness_analysis (
    analysis_id SERIAL PRIMARY KEY,
    analysis_date DATE NOT NULL DEFAULT CURRENT_DATE,
    scenario_count INTEGER NOT NULL,
    crio_validated_count INTEGER NOT NULL,
    average_preparedness_score DECIMAL(5,4),
    average_learning_signal_weight DECIMAL(5,4),
    preparedness_gap_summary JSONB,
    regime_coverage JSONB,  -- Which regimes have synthetic coverage
    recommendations JSONB,  -- UMA's focus recommendations (max 2 per EC-014)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (analysis_date)
);

COMMENT ON TABLE fhq_research.uma_preparedness_analysis IS
    'Daily UMA preparedness analysis. Feeds into LVI calculation at aggregation layer.';

-- ============================================================================
-- Integration Flow View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_research.synthetic_learning_pipeline AS
SELECT
    ss.scenario_id,
    ss.scenario_type,
    ss.scenario_name,
    ss.base_regime,
    ss.synthetic_regime,
    ss.is_canonical,
    cfq.queue_status AS crio_status,
    cfq.passed AS crio_passed,
    ct.crio_validated,
    ct.uma_reviewed,
    ct.preparedness_gap,
    ss.uma_preparedness_score,
    ss.learning_signal_weight,
    CASE
        WHEN ss.is_canonical = TRUE THEN 'ERROR: CANONICAL CONTAMINATION'
        WHEN cfq.passed IS NULL THEN 'AWAITING_CRIO'
        WHEN cfq.passed = FALSE THEN 'CRIO_FAILED'
        WHEN ct.uma_reviewed = FALSE THEN 'AWAITING_UMA'
        ELSE 'READY_FOR_LEARNING'
    END AS pipeline_status
FROM fhq_research.synthetic_scenarios ss
LEFT JOIN fhq_research.crio_falsification_queue cfq ON ss.scenario_id = cfq.scenario_id
LEFT JOIN fhq_research.counterfactual_tags ct ON ss.scenario_id = ct.scenario_id;

COMMENT ON VIEW fhq_research.synthetic_learning_pipeline IS
    'End-to-end view of CFAO → CRIO → UMA synthetic learning pipeline.';

-- ============================================================================
-- Migration Audit Log
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    metadata,
    agent_id,
    timestamp
) VALUES (
    gen_random_uuid(),
    'INFRASTRUCTURE_CREATE',
    'CFAO_CRIO_SYNTHETIC',
    'DIRECTIVE_B',
    'STIG',
    NOW(),
    'DEPLOYED',
    'CEO Directive 2026-01-16 - Directive B: CFAO x CRIO Synthetic Stress-Testing Integration',
    jsonb_build_object(
        'migration', '253_cfao_crio_synthetic_integration.sql',
        'directive', 'CEO Directive 2026-01-16 - Directive B',
        'tables_created', ARRAY['synthetic_scenarios', 'counterfactual_tags', 'crio_falsification_queue', 'uma_preparedness_analysis'],
        'views_created', ARRAY['synthetic_learning_pipeline'],
        'constraints', jsonb_build_object(
            'synthetic_never_canonical', 'is_canonical = FALSE enforced',
            'lvi_not_stored', 'learning_signal_weight only, LVI at aggregation'
        )
    ),
    'STIG',
    NOW()
);

COMMIT;

-- ============================================================================
-- Verification Queries
-- ============================================================================
-- SELECT * FROM fhq_research.synthetic_scenarios LIMIT 5;
-- SELECT * FROM fhq_research.synthetic_learning_pipeline;
-- SELECT * FROM fhq_research.counterfactual_tags;
