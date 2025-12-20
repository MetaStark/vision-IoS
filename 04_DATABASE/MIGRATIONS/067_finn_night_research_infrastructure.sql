-- ============================================================================
-- MIGRATION 067: FINN Night Research Infrastructure
-- ============================================================================
-- Purpose: Create research output tables for FINN Autonomous Night Cycle
-- Author: STIG (CTO)
-- Date: 2025-12-02
-- Authority: CEO Directive HC-CEO-FINN-NIGHT-20251202
-- ADR Reference: ADR-003 (Institutional Standards), ADR-010 (Discrepancy Scoring)
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: Regime Drift Reports
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.regime_drift_reports (
    report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Report metadata
    report_date DATE NOT NULL,
    report_cycle TEXT NOT NULL DEFAULT 'NIGHTLY',

    -- Regime analysis
    current_regime TEXT NOT NULL,
    expected_regime TEXT,
    regime_confidence NUMERIC(5, 4),

    -- Drift scoring (ADR-010)
    drift_score NUMERIC(5, 4) NOT NULL,
    drift_direction TEXT CHECK (drift_direction IN ('BULLISH', 'BEARISH', 'NEUTRAL', 'UNCERTAIN')),
    drift_velocity NUMERIC(8, 4),

    -- Time window
    analysis_window_hours INTEGER NOT NULL DEFAULT 72,
    price_data_start TIMESTAMPTZ,
    price_data_end TIMESTAMPTZ,

    -- Mismatch details
    mismatch_detected BOOLEAN NOT NULL DEFAULT FALSE,
    mismatch_severity TEXT CHECK (mismatch_severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    mismatch_description TEXT,

    -- Evidence
    evidence_data JSONB,
    supporting_indicators JSONB,

    -- Governance
    ios_reference TEXT NOT NULL DEFAULT 'IoS-003',
    vega_alert_triggered BOOLEAN NOT NULL DEFAULT FALSE,
    vega_alert_time TIMESTAMPTZ,

    -- Signature
    finn_signature TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hash_chain_id TEXT
);

CREATE INDEX idx_regime_drift_date ON fhq_research.regime_drift_reports(report_date);
CREATE INDEX idx_regime_drift_score ON fhq_research.regime_drift_reports(drift_score);

-- ============================================================================
-- SECTION 2: Weak Signal Summary
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.weak_signal_summary (
    signal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Report metadata
    report_date DATE NOT NULL,
    scan_cycle TEXT NOT NULL DEFAULT 'NIGHTLY',

    -- Signal identification
    signal_type TEXT NOT NULL CHECK (signal_type IN (
        'VOL_OF_VOL',
        'CROSS_ASSET_DIVERGENCE',
        'MACRO_STRESS',
        'FUNDING_RATE_DRIFT',
        'CORRELATION_BREAK',
        'LIQUIDITY_SHIFT',
        'REGIME_TRANSITION_EARLY'
    )),
    signal_name TEXT NOT NULL,

    -- Signal metrics
    signal_strength NUMERIC(5, 4) NOT NULL,
    confidence_level NUMERIC(5, 4) NOT NULL,
    noise_ratio NUMERIC(5, 4),

    -- Classification
    high_confidence BOOLEAN NOT NULL DEFAULT FALSE,
    actionable BOOLEAN NOT NULL DEFAULT FALSE,

    -- Context
    affected_assets TEXT[],
    macro_context TEXT,
    regime_context TEXT,

    -- Evidence
    evidence_data JSONB,
    detection_method TEXT,

    -- Source IoS
    ios_reference TEXT NOT NULL DEFAULT 'IoS-006',

    -- Signature
    finn_signature TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hash_chain_id TEXT
);

CREATE INDEX idx_weak_signal_date ON fhq_research.weak_signal_summary(report_date);
CREATE INDEX idx_weak_signal_type ON fhq_research.weak_signal_summary(signal_type);
CREATE INDEX idx_weak_signal_high_conf ON fhq_research.weak_signal_summary(high_confidence) WHERE high_confidence = TRUE;

-- ============================================================================
-- SECTION 3: HCP Pre-Validation Pack
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.hcp_prevalidation (
    validation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Report metadata
    report_date DATE NOT NULL,
    validation_cycle TEXT NOT NULL DEFAULT 'NIGHTLY',

    -- HCP reference
    hcp_draft_id UUID NOT NULL,
    hcp_symbol TEXT NOT NULL,
    hcp_strategy_type TEXT,

    -- Validation metrics
    signal_strength_score NUMERIC(5, 4),
    consistency_score NUMERIC(5, 4),
    noise_level_score NUMERIC(5, 4),
    overall_quality_score NUMERIC(5, 4),

    -- Validation result
    validation_result TEXT NOT NULL CHECK (validation_result IN (
        'STRONG_PASS',
        'PASS',
        'MARGINAL',
        'WEAK',
        'FAIL',
        'REJECT'
    )),

    -- Issues detected
    issues_detected TEXT[],
    warnings TEXT[],
    recommendations TEXT[],

    -- Evidence
    evidence_data JSONB,

    -- Source IoS
    ios_reference TEXT NOT NULL DEFAULT 'IoS-013.HCP-LAB',

    -- Destination
    forwarded_to_lars BOOLEAN NOT NULL DEFAULT FALSE,
    forwarded_at TIMESTAMPTZ,

    -- Signature
    finn_signature TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hash_chain_id TEXT
);

CREATE INDEX idx_hcp_preval_date ON fhq_research.hcp_prevalidation(report_date);
CREATE INDEX idx_hcp_preval_result ON fhq_research.hcp_prevalidation(validation_result);

-- ============================================================================
-- SECTION 4: Canonical Insight Pack (EC-004 format)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.canonical_insight_packs (
    pack_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Pack metadata
    pack_date DATE NOT NULL,
    pack_cycle TEXT NOT NULL DEFAULT 'NIGHTLY',
    pack_version TEXT NOT NULL DEFAULT '1.0',

    -- Content summary
    regime_drift_included BOOLEAN NOT NULL DEFAULT FALSE,
    weak_signals_count INTEGER NOT NULL DEFAULT 0,
    hcp_validations_count INTEGER NOT NULL DEFAULT 0,

    -- Aggregate scores
    overall_market_health NUMERIC(5, 4),
    regime_stability NUMERIC(5, 4),
    opportunity_score NUMERIC(5, 4),
    risk_score NUMERIC(5, 4),

    -- Key insights (structured)
    key_insights JSONB NOT NULL,

    -- Recommendations
    recommendations JSONB,

    -- References
    regime_drift_report_id UUID REFERENCES fhq_research.regime_drift_reports(report_id),

    -- EC-004 compliance
    ec_format_version TEXT NOT NULL DEFAULT 'EC-004-v1',

    -- Governance
    discrepancy_score NUMERIC(5, 4),
    vega_review_required BOOLEAN NOT NULL DEFAULT FALSE,

    -- Signature
    finn_signature TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hash_chain_id TEXT
);

CREATE INDEX idx_insight_pack_date ON fhq_research.canonical_insight_packs(pack_date);

-- ============================================================================
-- SECTION 5: FINN Research Boundary Enforcement View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_research.v_finn_research_boundaries AS
SELECT
    'FINN_NIGHT_RESEARCH_V1' as task_name,
    ARRAY['fhq_perception', 'fhq_macro', 'fhq_positions', 'fhq_research', 'fhq_graph', 'fhq_data'] as read_allowed,
    ARRAY['fhq_research'] as write_allowed,
    ARRAY['MODEL_CREATE', 'RUNTIME_CHANGE', 'LOOP_START', 'SIGNAL_TO_LINE', 'TRADE_PROPOSAL', 'IOS_MODIFICATION'] as forbidden_actions,
    0.08 as discrepancy_threshold,
    ARRAY['IoS-003', 'IoS-006', 'IoS-013.HCP-LAB'] as ios_access;

-- ============================================================================
-- SECTION 6: Governance logging
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
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
    'SCHEMA_CREATION',
    'fhq_research.finn_night_*',
    'TABLE_SET',
    'STIG',
    NOW(),
    'COMPLETED',
    'Created FINN Night Research infrastructure: regime_drift_reports, weak_signal_summary, hcp_prevalidation, canonical_insight_packs. EC-004 format compliant.',
    false,
    'HC-FINN-RESEARCH-SCHEMA-20251202'
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'fhq_research'
  AND table_name IN ('regime_drift_reports', 'weak_signal_summary', 'hcp_prevalidation', 'canonical_insight_packs')
ORDER BY table_name;
