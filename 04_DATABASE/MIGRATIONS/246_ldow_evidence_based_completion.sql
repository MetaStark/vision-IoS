-- =============================================================================
-- MIGRATION 246: LDOW EVIDENCE-BASED CYCLE COMPLETION
-- =============================================================================
-- CEO Directive: 2026-01-14 - LDOW Cycle Completion Execution
-- Author: STIG
-- Date: 2026-01-14
--
-- Purpose:
--   Upgrade cycle completion from time-based to evidence-based with:
--   - Coverage threshold (% of eligible forecasts paired)
--   - Stability threshold (metric variance on re-run)
--   - Rich evidence logging per CEO requirements
--
-- ADR-024 Compliance: Rung D eligibility requires two completed cycles
-- =============================================================================

BEGIN;

-- =============================================================================
-- SECTION 1: LDOW CYCLE COMPLETION TABLE
-- =============================================================================
-- Tracks formal cycle completion with evidence-based thresholds

CREATE TABLE IF NOT EXISTS fhq_governance.ldow_cycle_completion (
    completion_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Cycle identification
    cycle_number INTEGER NOT NULL,
    cycle_label TEXT NOT NULL,  -- e.g., "LDOW-CYCLE-1", "LDOW-CYCLE-2"
    horizon_hours INTEGER NOT NULL DEFAULT 24,

    -- Scheduling
    scheduled_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Coverage metrics (threshold 1)
    forecasts_eligible INTEGER NOT NULL DEFAULT 0,
    forecasts_paired INTEGER NOT NULL DEFAULT 0,
    forecasts_expired INTEGER NOT NULL DEFAULT 0,
    coverage_ratio NUMERIC(5,4) GENERATED ALWAYS AS (
        CASE WHEN forecasts_eligible > 0
             THEN forecasts_paired::NUMERIC / forecasts_eligible
             ELSE 0 END
    ) STORED,
    coverage_threshold NUMERIC(5,4) NOT NULL DEFAULT 0.80,  -- 80% minimum
    coverage_pass BOOLEAN GENERATED ALWAYS AS (
        CASE WHEN forecasts_eligible > 0
             THEN (forecasts_paired::NUMERIC / forecasts_eligible) >= coverage_threshold
             ELSE FALSE END
    ) STORED,

    -- Stability metrics (threshold 2)
    brier_score_run1 NUMERIC(6,5),
    brier_score_run2 NUMERIC(6,5),
    brier_variance NUMERIC(8,6) GENERATED ALWAYS AS (
        CASE WHEN brier_score_run1 IS NOT NULL AND brier_score_run2 IS NOT NULL
             THEN ABS(brier_score_run1 - brier_score_run2)
             ELSE NULL END
    ) STORED,
    stability_threshold NUMERIC(6,5) NOT NULL DEFAULT 0.05,  -- 5% max variance
    stability_pass BOOLEAN GENERATED ALWAYS AS (
        CASE WHEN brier_score_run1 IS NOT NULL AND brier_score_run2 IS NOT NULL
             THEN ABS(brier_score_run1 - brier_score_run2) <= stability_threshold
             ELSE NULL END
    ) STORED,

    -- Aggregate scoring
    calibration_error NUMERIC(6,5),
    hit_rate NUMERIC(5,4),

    -- Immutability verification (CEO requirement)
    damper_hash_at_start TEXT NOT NULL,
    damper_hash_at_end TEXT,
    damper_unchanged BOOLEAN GENERATED ALWAYS AS (
        damper_hash_at_start = damper_hash_at_end
    ) STORED,
    parameters_snapshot JSONB NOT NULL DEFAULT '{}',

    -- Cycle completion status
    completion_status TEXT NOT NULL DEFAULT 'SCHEDULED' CHECK (
        completion_status IN ('SCHEDULED', 'RUNNING', 'COVERAGE_FAIL',
                              'STABILITY_FAIL', 'DAMPER_CHANGED', 'COMPLETED', 'ERROR')
    ),

    -- Evidence chain
    evidence_id UUID,
    reconciliation_evidence_id UUID,
    evaluation_evidence_id UUID,

    -- Rung D qualification (computed via view, not generated column due to PostgreSQL limitation)
    rung_d_eligible BOOLEAN DEFAULT FALSE,

    -- Attestation
    vega_attestation_id UUID,
    vega_attested_at TIMESTAMPTZ,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'STIG',

    -- Constraints
    CONSTRAINT unique_cycle_number UNIQUE (cycle_number)
);

-- Index for quick lookup
CREATE INDEX IF NOT EXISTS idx_ldow_completion_status
    ON fhq_governance.ldow_cycle_completion(completion_status);
CREATE INDEX IF NOT EXISTS idx_ldow_completion_scheduled
    ON fhq_governance.ldow_cycle_completion(scheduled_at);

-- Trigger to compute rung_d_eligible (workaround for generated column limitation)
CREATE OR REPLACE FUNCTION fhq_governance.compute_rung_d_eligible()
RETURNS TRIGGER AS $$
BEGIN
    -- Compute rung_d_eligible based on coverage, stability, and damper immutability
    NEW.rung_d_eligible := (
        -- Coverage pass
        (CASE WHEN NEW.forecasts_eligible > 0
              THEN (NEW.forecasts_paired::NUMERIC / NEW.forecasts_eligible) >= NEW.coverage_threshold
              ELSE FALSE END)
        AND
        -- Stability pass
        (CASE WHEN NEW.brier_score_run1 IS NOT NULL AND NEW.brier_score_run2 IS NOT NULL
              THEN ABS(NEW.brier_score_run1 - NEW.brier_score_run2) <= NEW.stability_threshold
              ELSE NEW.brier_score_run1 IS NULL AND NEW.brier_score_run2 IS NULL END)
        AND
        -- Damper unchanged
        (NEW.damper_hash_at_start = NEW.damper_hash_at_end OR NEW.damper_hash_at_end IS NULL)
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_compute_rung_d_eligible
    BEFORE INSERT OR UPDATE ON fhq_governance.ldow_cycle_completion
    FOR EACH ROW
    EXECUTE FUNCTION fhq_governance.compute_rung_d_eligible();

-- =============================================================================
-- SECTION 2: CYCLE TASK EXECUTION LOG
-- =============================================================================
-- Detailed execution log per CEO evidence requirements

CREATE TABLE IF NOT EXISTS fhq_governance.ldow_task_execution_log (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Task identification
    task_id TEXT NOT NULL,
    cycle_completion_id UUID REFERENCES fhq_governance.ldow_cycle_completion(completion_id),
    task_type TEXT NOT NULL CHECK (task_type IN ('RECONCILIATION', 'EVALUATION', 'STABILITY_CHECK')),

    -- Timing
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    duration_ms INTEGER GENERATED ALWAYS AS (
        CASE WHEN ended_at IS NOT NULL
             THEN EXTRACT(EPOCH FROM (ended_at - started_at)) * 1000
             ELSE NULL END
    ) STORED,

    -- Counts (CEO requirement)
    forecasts_eligible INTEGER,
    forecasts_paired INTEGER,
    forecasts_expired INTEGER,

    -- Metrics output
    brier_score NUMERIC(6,5),
    calibration_error NUMERIC(6,5),
    hit_rate NUMERIC(5,4),

    -- Immutability confirmation (CEO requirement)
    damper_hash TEXT NOT NULL,
    parameters_unchanged BOOLEAN NOT NULL DEFAULT TRUE,

    -- Evidence
    evidence_id UUID,
    evidence_hash TEXT,

    -- Status
    execution_status TEXT NOT NULL DEFAULT 'RUNNING' CHECK (
        execution_status IN ('RUNNING', 'SUCCESS', 'FAILED', 'SKIPPED')
    ),
    error_message TEXT,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for task lookup
CREATE INDEX IF NOT EXISTS idx_task_execution_cycle
    ON fhq_governance.ldow_task_execution_log(cycle_completion_id);
CREATE INDEX IF NOT EXISTS idx_task_execution_type
    ON fhq_governance.ldow_task_execution_log(task_type);

-- =============================================================================
-- SECTION 3: THRESHOLD CONFIGURATION TABLE
-- =============================================================================
-- Configurable thresholds (proposed by STIG, reviewed by FINN, attested by VEGA)

CREATE TABLE IF NOT EXISTS fhq_governance.ldow_completion_thresholds (
    threshold_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Threshold definitions
    threshold_name TEXT NOT NULL UNIQUE,
    threshold_value NUMERIC(8,6) NOT NULL,
    threshold_unit TEXT NOT NULL,
    threshold_description TEXT,

    -- Governance
    proposed_by TEXT NOT NULL,
    proposed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    attested_by TEXT,
    attested_at TIMESTAMPTZ,

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Evidence
    evidence_id UUID,
    adr_reference TEXT DEFAULT 'ADR-024'
);

-- Insert default thresholds (STIG proposal)
INSERT INTO fhq_governance.ldow_completion_thresholds
    (threshold_name, threshold_value, threshold_unit, threshold_description, proposed_by)
VALUES
    ('COVERAGE_MINIMUM', 0.80, 'ratio',
     'Minimum % of eligible forecasts that must be paired for cycle completion', 'STIG'),
    ('STABILITY_VARIANCE_MAX', 0.05, 'brier_delta',
     'Maximum allowed variance in Brier score between consecutive reconciliation runs', 'STIG'),
    ('DAMPER_IMMUTABILITY', 1.0, 'boolean',
     'Damper hash must be unchanged between cycle start and end (1.0 = required)', 'STIG')
ON CONFLICT (threshold_name) DO NOTHING;

-- =============================================================================
-- SECTION 4: RUNG D ELIGIBILITY VIEW
-- =============================================================================
-- View for checking Rung D qualification status

CREATE OR REPLACE VIEW fhq_governance.v_rung_d_eligibility AS
WITH completed_cycles AS (
    SELECT
        cycle_number,
        cycle_label,
        completion_status,
        coverage_pass,
        stability_pass,
        damper_unchanged,
        rung_d_eligible,
        vega_attestation_id,
        completed_at
    FROM fhq_governance.ldow_cycle_completion
    WHERE completion_status = 'COMPLETED'
      AND rung_d_eligible = TRUE
    ORDER BY cycle_number
),
cycle_count AS (
    SELECT COUNT(*) as eligible_cycles FROM completed_cycles
),
attestation_check AS (
    SELECT
        COUNT(*) FILTER (WHERE vega_attestation_id IS NOT NULL) as attested_cycles
    FROM completed_cycles
)
SELECT
    cc.eligible_cycles,
    ac.attested_cycles,
    CASE
        WHEN cc.eligible_cycles >= 2 AND ac.attested_cycles >= 2 THEN TRUE
        ELSE FALSE
    END AS rung_d_qualified,
    CASE
        WHEN cc.eligible_cycles < 2 THEN 'Need ' || (2 - cc.eligible_cycles) || ' more completed cycles'
        WHEN ac.attested_cycles < 2 THEN 'Need ' || (2 - ac.attested_cycles) || ' more VEGA attestations'
        ELSE 'RUNG D QUALIFIED - Ready for human-authorized execution'
    END AS qualification_status,
    (SELECT array_agg(cycle_label ORDER BY cycle_number) FROM completed_cycles) AS completed_cycle_labels,
    NOW() AS checked_at
FROM cycle_count cc, attestation_check ac;

-- =============================================================================
-- SECTION 5: GOVERNANCE LOG
-- =============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'LDOW_EVIDENCE_COMPLETION_ACTIVATION',
    'fhq_governance.ldow_cycle_completion',
    'TABLE',
    'STIG',
    'EXECUTED',
    'CEO Directive 2026-01-14: Upgrade cycle completion from time-based to evidence-based',
    jsonb_build_object(
        'migration', '246_ldow_evidence_based_completion.sql',
        'coverage_threshold', 0.80,
        'stability_threshold', 0.05,
        'damper_immutability_required', true,
        'rung_d_cycles_required', 2,
        'timestamp', NOW()
    )
);

-- =============================================================================
-- SECTION 6: SEED LDOW CYCLES 1 AND 2
-- =============================================================================
-- Pre-register the two required cycles for Rung D qualification

INSERT INTO fhq_governance.ldow_cycle_completion (
    cycle_number,
    cycle_label,
    horizon_hours,
    scheduled_at,
    damper_hash_at_start,
    parameters_snapshot,
    completion_status
) VALUES
    (1, 'LDOW-CYCLE-1', 24, '2026-01-15 01:30:00+00',
     'da311f0ebb875122', -- Current damper hash from LDOW status
     '{"coverage_threshold": 0.80, "stability_threshold": 0.05}'::jsonb,
     'SCHEDULED'),
    (2, 'LDOW-CYCLE-2', 24, '2026-01-16 01:30:00+00',
     'da311f0ebb875122',
     '{"coverage_threshold": 0.80, "stability_threshold": 0.05}'::jsonb,
     'SCHEDULED')
ON CONFLICT (cycle_number) DO NOTHING;

COMMIT;

-- =============================================================================
-- VERIFICATION
-- =============================================================================

SELECT 'Migration 246 Complete: Evidence-Based Cycle Completion Active' AS status;

-- Show registered cycles
SELECT
    cycle_number,
    cycle_label,
    scheduled_at,
    coverage_threshold,
    stability_threshold,
    completion_status
FROM fhq_governance.ldow_cycle_completion
ORDER BY cycle_number;

-- Show threshold configuration
SELECT
    threshold_name,
    threshold_value,
    threshold_unit,
    proposed_by
FROM fhq_governance.ldow_completion_thresholds
WHERE is_active = TRUE;

-- Check Rung D eligibility
SELECT * FROM fhq_governance.v_rung_d_eligibility;
