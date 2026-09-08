-- Migration 273: UMA OKR Infrastructure
-- CEO Directive 2026-01-17: Daily OKR-driven learning acceleration
-- UMA as world-leading expert in Learning Velocity optimization
--
-- OKR = Objective + Key Results
-- Duration: 1 day to 1 week
-- Tracked and learned from

BEGIN;

-- =============================================================================
-- OKR REGISTRY
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.uma_okr_registry (
    okr_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identification
    okr_code TEXT NOT NULL UNIQUE,  -- e.g., 'OKR-2026-D17-001'
    okr_day INTEGER NOT NULL,       -- Day of year when created
    okr_week INTEGER,               -- ISO week if weekly OKR

    -- Objective (the "what" and "why")
    objective_title TEXT NOT NULL,
    objective_description TEXT NOT NULL,
    objective_rationale TEXT,       -- Why this objective matters for 1000X
    objective_category TEXT NOT NULL CHECK (objective_category IN (
        'LEARNING_VELOCITY',
        'BASELINE_ESTABLISHMENT',
        'GOVERNANCE_EFFICIENCY',
        'HYPOTHESIS_QUALITY',
        'FALSIFICATION_SPEED',
        'ROI_COMPRESSION',
        'INFRASTRUCTURE',
        'SYNTHETIC_VALIDATION'
    )),

    -- Timing
    duration_type TEXT NOT NULL CHECK (duration_type IN ('DAILY', 'WEEKLY')),
    start_date DATE NOT NULL,
    target_date DATE NOT NULL,

    -- Status
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN (
        'DRAFT',
        'ACTIVE',
        'COMPLETED',
        'PARTIALLY_COMPLETED',
        'MISSED',
        'CANCELLED'
    )),

    -- Ownership
    owner_agent TEXT NOT NULL DEFAULT 'UMA',
    supporting_agents TEXT[],

    -- Learning linkage
    friction_ids TEXT[],            -- Which frictions this addresses
    lvi_target_impact NUMERIC(4,2), -- Expected LVI improvement

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'UMA',
    completed_at TIMESTAMPTZ,

    -- Evidence
    evidence_file TEXT,
    uma_signature TEXT
);

-- =============================================================================
-- KEY RESULTS
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.uma_okr_key_results (
    kr_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    okr_id UUID NOT NULL REFERENCES fhq_governance.uma_okr_registry(okr_id),

    -- Key Result definition
    kr_number INTEGER NOT NULL,     -- 1, 2, 3...
    kr_title TEXT NOT NULL,
    kr_description TEXT,

    -- Measurement
    metric_name TEXT NOT NULL,
    metric_type TEXT NOT NULL CHECK (metric_type IN (
        'COUNT',
        'PERCENTAGE',
        'BOOLEAN',
        'NUMERIC',
        'THRESHOLD'
    )),
    baseline_value NUMERIC,
    target_value NUMERIC NOT NULL,
    current_value NUMERIC,

    -- Status
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN (
        'PENDING',
        'IN_PROGRESS',
        'ACHIEVED',
        'MISSED',
        'EXCEEDED'
    )),
    achievement_percentage NUMERIC(5,2) DEFAULT 0,

    -- Tracking
    measured_at TIMESTAMPTZ,
    measured_by TEXT,
    measurement_query TEXT,         -- SQL to verify
    measurement_evidence TEXT,      -- Hash of result

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(okr_id, kr_number)
);

-- =============================================================================
-- OKR PROGRESS LOG
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.uma_okr_progress_log (
    progress_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    okr_id UUID NOT NULL REFERENCES fhq_governance.uma_okr_registry(okr_id),
    kr_id UUID REFERENCES fhq_governance.uma_okr_key_results(kr_id),

    -- Progress update
    update_type TEXT NOT NULL CHECK (update_type IN (
        'MEASUREMENT',
        'STATUS_CHANGE',
        'BLOCKER_IDENTIFIED',
        'BLOCKER_RESOLVED',
        'NOTE'
    )),
    previous_value NUMERIC,
    new_value NUMERIC,
    delta NUMERIC,

    -- Context
    notes TEXT,
    evidence_hash TEXT,

    -- Metadata
    logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    logged_by TEXT NOT NULL DEFAULT 'UMA'
);

-- =============================================================================
-- OKR RETROSPECTIVE (Learning from results)
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.uma_okr_retrospective (
    retro_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    okr_id UUID NOT NULL REFERENCES fhq_governance.uma_okr_registry(okr_id),

    -- Outcome assessment
    overall_score NUMERIC(3,2),     -- 0.0 to 1.0
    key_results_achieved INTEGER,
    key_results_total INTEGER,

    -- Learning extraction
    what_worked TEXT[],
    what_didnt_work TEXT[],
    surprises TEXT[],

    -- Forward implications
    recommendations TEXT[],
    next_okr_adjustments TEXT[],
    lvi_actual_impact NUMERIC(4,2),

    -- Root cause (if missed)
    miss_category TEXT CHECK (miss_category IN (
        'SCOPE_TOO_AMBITIOUS',
        'EXTERNAL_BLOCKER',
        'RESOURCE_CONSTRAINT',
        'MEASUREMENT_ERROR',
        'PRIORITY_SHIFT',
        'NOT_APPLICABLE'
    )),
    miss_details TEXT,

    -- Metadata
    retrospective_date DATE NOT NULL,
    conducted_by TEXT NOT NULL DEFAULT 'UMA',
    ceo_reviewed BOOLEAN DEFAULT FALSE,
    ceo_notes TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- VIEWS
-- =============================================================================

CREATE OR REPLACE VIEW fhq_governance.v_active_okrs AS
SELECT
    o.okr_code,
    o.objective_title,
    o.objective_category,
    o.duration_type,
    o.start_date,
    o.target_date,
    o.target_date - CURRENT_DATE as days_remaining,
    o.status,
    o.lvi_target_impact,
    COUNT(kr.kr_id) as total_key_results,
    COUNT(kr.kr_id) FILTER (WHERE kr.status = 'ACHIEVED') as achieved_key_results,
    ROUND(AVG(kr.achievement_percentage), 1) as avg_achievement_pct
FROM fhq_governance.uma_okr_registry o
LEFT JOIN fhq_governance.uma_okr_key_results kr ON o.okr_id = kr.okr_id
WHERE o.status = 'ACTIVE'
GROUP BY o.okr_id, o.okr_code, o.objective_title, o.objective_category,
         o.duration_type, o.start_date, o.target_date, o.status, o.lvi_target_impact;

CREATE OR REPLACE VIEW fhq_governance.v_okr_performance_history AS
SELECT
    o.okr_code,
    o.objective_title,
    o.objective_category,
    o.duration_type,
    o.start_date,
    o.target_date,
    o.status,
    r.overall_score,
    r.key_results_achieved,
    r.key_results_total,
    r.lvi_actual_impact,
    o.lvi_target_impact,
    CASE
        WHEN o.lvi_target_impact > 0
        THEN ROUND((r.lvi_actual_impact / o.lvi_target_impact) * 100, 1)
        ELSE NULL
    END as lvi_delivery_pct,
    r.miss_category
FROM fhq_governance.uma_okr_registry o
LEFT JOIN fhq_governance.uma_okr_retrospective r ON o.okr_id = r.okr_id
WHERE o.status IN ('COMPLETED', 'PARTIALLY_COMPLETED', 'MISSED')
ORDER BY o.target_date DESC;

-- =============================================================================
-- FUNCTIONS
-- =============================================================================

-- Create new OKR
CREATE OR REPLACE FUNCTION fhq_governance.create_okr(
    p_objective_title TEXT,
    p_objective_description TEXT,
    p_objective_category TEXT,
    p_duration_type TEXT,
    p_target_days INTEGER DEFAULT 1,
    p_lvi_target_impact NUMERIC DEFAULT 0.1,
    p_friction_ids TEXT[] DEFAULT NULL,
    p_rationale TEXT DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_okr_id UUID;
    v_okr_code TEXT;
    v_day_of_year INTEGER;
    v_seq INTEGER;
BEGIN
    v_day_of_year := EXTRACT(DOY FROM CURRENT_DATE);

    -- Generate unique OKR code
    SELECT COALESCE(MAX(
        CASE
            WHEN okr_code ~ ('^OKR-2026-D' || v_day_of_year || '-')
            THEN SUBSTRING(okr_code FROM '-(\d+)$')::INTEGER
            ELSE 0
        END
    ), 0) + 1 INTO v_seq
    FROM fhq_governance.uma_okr_registry
    WHERE okr_day = v_day_of_year;

    v_okr_code := 'OKR-2026-D' || v_day_of_year || '-' || LPAD(v_seq::TEXT, 3, '0');

    INSERT INTO fhq_governance.uma_okr_registry (
        okr_code,
        okr_day,
        okr_week,
        objective_title,
        objective_description,
        objective_rationale,
        objective_category,
        duration_type,
        start_date,
        target_date,
        friction_ids,
        lvi_target_impact,
        status
    ) VALUES (
        v_okr_code,
        v_day_of_year,
        EXTRACT(WEEK FROM CURRENT_DATE),
        p_objective_title,
        p_objective_description,
        p_rationale,
        p_objective_category,
        p_duration_type,
        CURRENT_DATE,
        CURRENT_DATE + p_target_days,
        p_friction_ids,
        p_lvi_target_impact,
        'ACTIVE'
    )
    RETURNING okr_id INTO v_okr_id;

    RETURN v_okr_id;
END;
$$;

-- Add Key Result to OKR
CREATE OR REPLACE FUNCTION fhq_governance.add_key_result(
    p_okr_id UUID,
    p_kr_title TEXT,
    p_metric_name TEXT,
    p_metric_type TEXT,
    p_target_value NUMERIC,
    p_baseline_value NUMERIC DEFAULT NULL,
    p_kr_description TEXT DEFAULT NULL,
    p_measurement_query TEXT DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_kr_id UUID;
    v_kr_number INTEGER;
BEGIN
    SELECT COALESCE(MAX(kr_number), 0) + 1 INTO v_kr_number
    FROM fhq_governance.uma_okr_key_results
    WHERE okr_id = p_okr_id;

    INSERT INTO fhq_governance.uma_okr_key_results (
        okr_id,
        kr_number,
        kr_title,
        kr_description,
        metric_name,
        metric_type,
        baseline_value,
        target_value,
        measurement_query,
        status
    ) VALUES (
        p_okr_id,
        v_kr_number,
        p_kr_title,
        p_kr_description,
        p_metric_name,
        p_metric_type,
        p_baseline_value,
        p_target_value,
        p_measurement_query,
        'PENDING'
    )
    RETURNING kr_id INTO v_kr_id;

    RETURN v_kr_id;
END;
$$;

-- Update Key Result measurement
CREATE OR REPLACE FUNCTION fhq_governance.update_key_result(
    p_kr_id UUID,
    p_current_value NUMERIC,
    p_measured_by TEXT DEFAULT 'UMA'
)
RETURNS TABLE(
    kr_title TEXT,
    target_value NUMERIC,
    current_value NUMERIC,
    achievement_pct NUMERIC,
    status TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_target NUMERIC;
    v_baseline NUMERIC;
    v_prev_value NUMERIC;
    v_achievement NUMERIC;
    v_status TEXT;
    v_okr_id UUID;
BEGIN
    SELECT kr.target_value, kr.baseline_value, kr.current_value, kr.okr_id
    INTO v_target, v_baseline, v_prev_value, v_okr_id
    FROM fhq_governance.uma_okr_key_results kr
    WHERE kr.kr_id = p_kr_id;

    -- Calculate achievement percentage
    IF v_baseline IS NOT NULL AND v_target != v_baseline THEN
        v_achievement := ((p_current_value - v_baseline) / (v_target - v_baseline)) * 100;
    ELSE
        v_achievement := (p_current_value / NULLIF(v_target, 0)) * 100;
    END IF;

    -- Determine status
    v_status := CASE
        WHEN v_achievement >= 100 THEN 'ACHIEVED'
        WHEN v_achievement >= 110 THEN 'EXCEEDED'
        WHEN v_achievement > 0 THEN 'IN_PROGRESS'
        ELSE 'PENDING'
    END;

    -- Update the key result
    UPDATE fhq_governance.uma_okr_key_results
    SET current_value = p_current_value,
        achievement_percentage = LEAST(v_achievement, 150),  -- Cap at 150%
        status = v_status,
        measured_at = NOW(),
        measured_by = p_measured_by
    WHERE kr_id = p_kr_id;

    -- Log progress
    INSERT INTO fhq_governance.uma_okr_progress_log (
        okr_id, kr_id, update_type, previous_value, new_value, delta, logged_by
    ) VALUES (
        v_okr_id, p_kr_id, 'MEASUREMENT', v_prev_value, p_current_value,
        p_current_value - COALESCE(v_prev_value, 0), p_measured_by
    );

    RETURN QUERY
    SELECT kr.kr_title, kr.target_value, kr.current_value,
           kr.achievement_percentage, kr.status
    FROM fhq_governance.uma_okr_key_results kr
    WHERE kr.kr_id = p_kr_id;
END;
$$;

-- =============================================================================
-- GOVERNANCE LOGGING
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
    'OKR_INFRASTRUCTURE_DEPLOYED',
    'fhq_governance.uma_okr_*',
    'SCHEMA',
    'CEO',
    'APPROVED',
    'CEO Directive 2026-01-17: UMA OKR-driven learning acceleration. Daily OKRs for 1000X target.',
    jsonb_build_object(
        'tables_created', ARRAY['uma_okr_registry', 'uma_okr_key_results', 'uma_okr_progress_log', 'uma_okr_retrospective'],
        'views_created', ARRAY['v_active_okrs', 'v_okr_performance_history'],
        'uma_role', 'World-leading expert in Learning Velocity optimization'
    )
);

COMMIT;
