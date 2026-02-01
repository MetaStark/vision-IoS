-- CEO-DIR-2026-112: 48h SHADOW Learning Lockdown & Epistemic Yield Maximization
-- Classification: MANDATORY – IMMEDIATE EFFECT
-- Status: LEARNING-CRITICAL / NO-EXECUTION
-- Effective Window: Until 2026-01-22T01:15:00Z
-- Implementor: STIG
-- Date: 2026-01-20

-- =============================================================================
-- 48-HOUR SHADOW LEARNING LOCKDOWN
-- Purpose: Maximize epistemic learning yield from paper trades and refusals
-- No parameter tuning. No cadence forcing. No execution enablement.
-- Only measurement, attribution, and verification.
-- =============================================================================

BEGIN;

-- Step 1: Create SHADOW lockdown configuration table
CREATE TABLE IF NOT EXISTS fhq_governance.shadow_lockdown_config (
    lockdown_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    directive_reference TEXT NOT NULL,

    -- Lockdown window
    lockdown_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lockdown_ends_at TIMESTAMPTZ NOT NULL,
    lockdown_duration_hours INTEGER NOT NULL,

    -- Status
    lockdown_status TEXT NOT NULL DEFAULT 'ACTIVE',

    -- Forbidden actions (2.1)
    forbidden_actions JSONB NOT NULL,

    -- Allowed actions (2.2)
    allowed_actions JSONB NOT NULL,

    -- Success criteria tracking
    success_criteria JSONB NOT NULL,

    -- Violation tracking
    violations_detected INTEGER NOT NULL DEFAULT 0,
    violation_log JSONB DEFAULT '[]'::jsonb,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_current BOOLEAN NOT NULL DEFAULT true,

    CONSTRAINT chk_lockdown_status CHECK (lockdown_status IN ('ACTIVE', 'COMPLETED', 'VIOLATED', 'EXPIRED'))
);

-- Step 2: Insert CEO-DIR-2026-112 lockdown configuration
INSERT INTO fhq_governance.shadow_lockdown_config (
    directive_reference,
    lockdown_started_at,
    lockdown_ends_at,
    lockdown_duration_hours,
    lockdown_status,
    forbidden_actions,
    allowed_actions,
    success_criteria,
    is_current
) VALUES (
    'CEO-DIR-2026-112',
    NOW(),
    '2026-01-22T01:15:00Z'::timestamptz,
    48,
    'ACTIVE',
    jsonb_build_object(
        'parameter_changes', true,
        'aggression_tuning', true,
        'ttl_adjustment', true,
        'regime_threshold_changes', true,
        'execution_enablement', true,
        'manual_signal_injections', true,  -- CEO Addition
        'note', 'Any violation invalidates the learning window'
    ),
    jsonb_build_object(
        'signal_generation', true,
        'canonical_routing', true,
        'cpto_shadow_evaluation', true,
        'paper_trade_generation', true,
        'learning_logging', true,
        'evidence_logging', true,
        'note', 'Only measurement, attribution, and verification'
    ),
    jsonb_build_object(
        'calibration_curve_exists', false,
        'signal_to_cpto_verified', false,
        'median_freshness_under_5min', false,
        'learning_data_accepted', false,
        'learning_data_refused', false,
        'no_parameters_changed', true
    ),
    true
);

-- Step 3: Create learning channel attribution table (Mandate C)
CREATE TABLE IF NOT EXISTS fhq_research.learning_channel_attribution (
    attribution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to evaluation
    evaluation_id UUID NOT NULL,
    source_signal_id UUID NOT NULL,

    -- Attribution category (exactly one)
    learning_channel TEXT NOT NULL,

    -- Channel-specific data
    inversion_delta_data JSONB,      -- For INVERSION_DELTA_LEARNING
    friction_data JSONB,              -- For FRICTION_REFUSAL_LEARNING
    calibration_data JSONB,           -- For CALIBRATION_BRIER_LEARNING

    -- Surprise metric (CEO Addition - MBB edge)
    surprise_metric NUMERIC,  -- Deviation from inverted belief

    -- Attribution metadata
    attributed_by TEXT NOT NULL,
    attribution_rationale TEXT NOT NULL,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    directive_reference TEXT NOT NULL DEFAULT 'CEO-DIR-2026-112',

    CONSTRAINT chk_learning_channel CHECK (learning_channel IN (
        'INVERSION_DELTA_LEARNING',
        'FRICTION_REFUSAL_LEARNING',
        'CALIBRATION_BRIER_LEARNING'
    ))
);

CREATE INDEX IF NOT EXISTS idx_learning_attribution_channel
ON fhq_research.learning_channel_attribution(learning_channel, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_learning_attribution_eval
ON fhq_research.learning_channel_attribution(evaluation_id);

-- Step 4: Create calibration curve data table (Mandate A)
CREATE TABLE IF NOT EXISTS fhq_research.calibration_curve_data (
    curve_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Generation metadata
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    generated_by TEXT NOT NULL,
    directive_reference TEXT NOT NULL,

    -- Scope
    signal_class TEXT NOT NULL,
    sample_size INTEGER NOT NULL,
    observation_window_start TIMESTAMPTZ NOT NULL,
    observation_window_end TIMESTAMPTZ NOT NULL,

    -- Calibration buckets
    confidence_buckets JSONB NOT NULL,  -- Array of {bucket_min, bucket_max, predicted_rate, actual_rate, count}

    -- Key metrics
    reliability_score NUMERIC,      -- How well-calibrated
    resolution_score NUMERIC,       -- How discriminating
    brier_score NUMERIC,            -- Overall accuracy
    directional_bias NUMERIC,       -- +ve = overconfident, -ve = underconfident

    -- Uncertainty statement (required)
    uncertainty_statement TEXT NOT NULL,
    sample_size_warning BOOLEAN NOT NULL DEFAULT true,

    -- Status
    curve_status TEXT NOT NULL DEFAULT 'PRELIMINARY',

    CONSTRAINT chk_curve_status CHECK (curve_status IN ('PRELIMINARY', 'VALIDATED', 'SUPERSEDED'))
);

-- Step 5: Create signal flow verification view (Mandate B)
CREATE OR REPLACE VIEW fhq_research.v_signal_flow_verification AS
WITH signal_flow AS (
    SELECT
        h.handoff_id,
        h.source_module,
        h.instrument,
        h.signal_class,
        h.created_at as signal_created,
        h.cpto_received_at,
        h.handoff_status,
        h.cpto_decision,
        p.packet_id,
        p.created_at as packet_created,
        e.evaluation_id,
        e.created_at as evaluation_created,
        -- Latency calculations
        EXTRACT(EPOCH FROM (h.cpto_received_at - h.created_at)) as signal_to_cpto_seconds,
        EXTRACT(EPOCH FROM (p.created_at - h.cpto_received_at)) as cpto_to_packet_seconds,
        EXTRACT(EPOCH FROM (p.created_at - h.created_at)) as total_latency_seconds
    FROM fhq_alpha.canonical_signal_handoff h
    LEFT JOIN fhq_alpha.cpto_shadow_trade_packets p
        ON p.source_signal_id = h.source_signal_id
    LEFT JOIN fhq_research.evaluations e
        ON e.source_signal_id = h.source_signal_id
    WHERE h.created_at > NOW() - INTERVAL '48 hours'
)
SELECT
    handoff_id,
    source_module,
    instrument,
    signal_class,
    signal_created,
    cpto_received_at,
    handoff_status,
    cpto_decision,
    packet_id,
    evaluation_id,
    signal_to_cpto_seconds,
    cpto_to_packet_seconds,
    total_latency_seconds,
    CASE
        WHEN total_latency_seconds IS NULL THEN 'INCOMPLETE'
        WHEN total_latency_seconds < 300 THEN 'FRESH'
        ELSE 'STALE'
    END as freshness_status
FROM signal_flow
ORDER BY signal_created DESC;

-- Step 6: Create signal flow statistics view
CREATE OR REPLACE VIEW fhq_research.v_signal_flow_statistics AS
SELECT
    COUNT(*) as total_signals,
    COUNT(CASE WHEN handoff_status = 'CPTO_ACCEPTED' THEN 1 END) as accepted_count,
    COUNT(CASE WHEN handoff_status = 'CPTO_REFUSED' THEN 1 END) as refused_count,
    COUNT(CASE WHEN handoff_status = 'PENDING_CPTO' THEN 1 END) as pending_count,
    COUNT(CASE WHEN handoff_status = 'EXPIRED' THEN 1 END) as expired_count,

    -- Latency statistics
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_latency_seconds) as median_latency_seconds,
    MAX(total_latency_seconds) as max_latency_seconds,
    MIN(total_latency_seconds) as min_latency_seconds,
    AVG(total_latency_seconds) as avg_latency_seconds,

    -- Freshness KPI
    COUNT(CASE WHEN freshness_status = 'FRESH' THEN 1 END)::NUMERIC / NULLIF(COUNT(*), 0) as freshness_rate,

    -- Time window
    MIN(signal_created) as observation_start,
    MAX(signal_created) as observation_end,
    NOW() as generated_at
FROM fhq_research.v_signal_flow_verification;

-- Step 7: Create SHADOW window monitoring view (for daily report)
CREATE OR REPLACE VIEW fhq_governance.v_shadow_window_status AS
SELECT
    l.lockdown_id,
    l.directive_reference,
    l.lockdown_started_at,
    l.lockdown_ends_at,
    l.lockdown_duration_hours,
    l.lockdown_status,
    l.violations_detected,

    -- Time calculations
    EXTRACT(EPOCH FROM (l.lockdown_ends_at - NOW())) / 3600 as hours_remaining,
    EXTRACT(EPOCH FROM (NOW() - l.lockdown_started_at)) / 3600 as hours_elapsed,

    -- Progress
    (EXTRACT(EPOCH FROM (NOW() - l.lockdown_started_at)) /
     EXTRACT(EPOCH FROM (l.lockdown_ends_at - l.lockdown_started_at))) * 100 as progress_percent,

    -- Status determination
    CASE
        WHEN NOW() >= l.lockdown_ends_at THEN 'EXPIRED'
        WHEN l.violations_detected > 0 THEN 'VIOLATED'
        ELSE 'ACTIVE'
    END as computed_status,

    -- Success criteria
    l.success_criteria,

    -- Auto-expiry flag for daily report
    CASE
        WHEN NOW() >= l.lockdown_ends_at THEN true
        ELSE false
    END as window_expired,

    l.created_at
FROM fhq_governance.shadow_lockdown_config l
WHERE l.is_current = true;

-- Step 8: Create learning summary view for daily report
CREATE OR REPLACE VIEW fhq_research.v_learning_summary AS
SELECT
    -- Counts by decision
    COUNT(*) as total_evaluations,
    COUNT(CASE WHEN cpto_decision = 'ACCEPTED' THEN 1 END) as accepted_count,
    COUNT(CASE WHEN cpto_decision LIKE 'BLOCKED%' THEN 1 END) as blocked_count,

    -- Learning by channel (will be populated via attribution)
    COUNT(CASE WHEN is_inversion_candidate THEN 1 END) as inversion_learning_candidates,
    COUNT(CASE WHEN refusal_category IS NOT NULL THEN 1 END) as friction_learning_events,
    COUNT(CASE WHEN brier_contribution_logged THEN 1 END) as calibration_events,

    -- Quality metrics
    AVG(slippage_saved_bps) as avg_slippage_saved_bps,
    AVG(confidence) as avg_confidence,
    AVG(CASE WHEN ttl_check_passed THEN 1.0 ELSE 0.0 END) as ttl_compliance_rate,

    -- Time window
    MIN(created_at) as first_evaluation,
    MAX(created_at) as last_evaluation,
    NOW() as generated_at
FROM fhq_research.evaluations
WHERE created_at > (SELECT lockdown_started_at FROM fhq_governance.shadow_lockdown_config WHERE is_current = true);

-- Step 9: Log governance action
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    metadata,
    vega_reviewed
) VALUES (
    'SHADOW_LOCKDOWN_ACTIVATION',
    'CEO-DIR-2026-112',
    'LEARNING_LOCKDOWN',
    'CEO',
    NOW(),
    'APPROVED',
    'CEO-DIR-2026-112: 48h SHADOW Learning Lockdown activated. ' ||
    'No parameter tuning. No cadence forcing. No execution enablement. ' ||
    'Only measurement, attribution, and verification. ' ||
    'Window expires: 2026-01-22T01:15:00Z',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-112',
        'lockdown_hours', 48,
        'lockdown_ends', '2026-01-22T01:15:00Z',
        'forbidden_actions', ARRAY[
            'parameter_changes',
            'aggression_tuning',
            'ttl_adjustment',
            'regime_threshold_changes',
            'execution_enablement',
            'manual_signal_injections'
        ],
        'mandates', ARRAY[
            'A: Calibration Curve (UMA)',
            'B: Signal-to-Paper Verification (STIG)',
            'C: Learning Channel Attribution (UMA+STIG)'
        ]
    ),
    false  -- VEGA observer only during this window
);

COMMIT;

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Verify lockdown config
SELECT directive_reference, lockdown_status, lockdown_ends_at,
       EXTRACT(EPOCH FROM (lockdown_ends_at - NOW())) / 3600 as hours_remaining
FROM fhq_governance.shadow_lockdown_config
WHERE is_current = true;

-- Check SHADOW window status
SELECT * FROM fhq_governance.v_shadow_window_status;
