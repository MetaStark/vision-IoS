-- CEO-DIR-2026-110: LOW_CONFIDENCE_INVERSION_CANDIDATE Signal Class
-- Mandate B: Regime-Conditional Signal Expansion
-- Classification: MANDATORY
-- Implementor: STIG
-- Date: 2026-01-20

BEGIN;

-- =============================================================================
-- B1: Define LOW_CONFIDENCE_INVERSION_CANDIDATE Signal Class
-- =============================================================================

-- Add signal_class column to g2_decision_plans if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_alpha'
        AND table_name = 'g2_decision_plans'
        AND column_name = 'signal_class'
    ) THEN
        ALTER TABLE fhq_alpha.g2_decision_plans
        ADD COLUMN signal_class TEXT DEFAULT 'STANDARD';
    END IF;
END $$;

-- Add inversion_metadata column for tracking inversion-specific data
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_alpha'
        AND table_name = 'g2_decision_plans'
        AND column_name = 'inversion_metadata'
    ) THEN
        ALTER TABLE fhq_alpha.g2_decision_plans
        ADD COLUMN inversion_metadata JSONB DEFAULT NULL;
    END IF;
END $$;

-- Create signal class enum type if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'signal_class_type') THEN
        CREATE TYPE signal_class_type AS ENUM (
            'STANDARD',                           -- Normal signal flow
            'LOW_CONFIDENCE_INVERSION_CANDIDATE', -- STRESS regime inversion candidate
            'HIGH_CONFIDENCE_VERIFIED',           -- Verified high-confidence signal
            'EXPERIMENTAL'                        -- Research/shadow signals
        );
    END IF;
END $$;

-- Add check constraint for valid signal classes
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.constraint_column_usage
        WHERE table_schema = 'fhq_alpha'
        AND table_name = 'g2_decision_plans'
        AND constraint_name = 'chk_valid_signal_class'
    ) THEN
        ALTER TABLE fhq_alpha.g2_decision_plans
        ADD CONSTRAINT chk_valid_signal_class CHECK (
            signal_class IN (
                'STANDARD',
                'LOW_CONFIDENCE_INVERSION_CANDIDATE',
                'HIGH_CONFIDENCE_VERIFIED',
                'EXPERIMENTAL'
            )
        );
    END IF;
END $$;

-- =============================================================================
-- B2: CPTO Gating for Inversion Candidates
-- =============================================================================

-- Add inversion candidate tracking to cpto_precision_log
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_alpha'
        AND table_name = 'cpto_precision_log'
        AND column_name = 'signal_class'
    ) THEN
        ALTER TABLE fhq_alpha.cpto_precision_log
        ADD COLUMN signal_class TEXT DEFAULT 'STANDARD';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_alpha'
        AND table_name = 'cpto_precision_log'
        AND column_name = 'inversion_gate_passed'
    ) THEN
        ALTER TABLE fhq_alpha.cpto_precision_log
        ADD COLUMN inversion_gate_passed BOOLEAN DEFAULT NULL;
    END IF;
END $$;

-- Add inversion-specific friction tracking columns
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_alpha'
        AND table_name = 'cpto_friction_log'
        AND column_name = 'refused_inversion_unverified'
    ) THEN
        ALTER TABLE fhq_alpha.cpto_friction_log
        ADD COLUMN refused_inversion_unverified INTEGER DEFAULT 0;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_alpha'
        AND table_name = 'cpto_friction_log'
        AND column_name = 'inversion_candidate_total'
    ) THEN
        ALTER TABLE fhq_alpha.cpto_friction_log
        ADD COLUMN inversion_candidate_total INTEGER DEFAULT 0;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_alpha'
        AND table_name = 'cpto_friction_log'
        AND column_name = 'inversion_refusal_rate'
    ) THEN
        ALTER TABLE fhq_alpha.cpto_friction_log
        ADD COLUMN inversion_refusal_rate NUMERIC DEFAULT NULL;
    END IF;
END $$;

-- Create inversion candidate friction log for CEO R2 feedback loop
CREATE TABLE IF NOT EXISTS fhq_alpha.cpto_inversion_friction_log (
    friction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    window_hours INTEGER NOT NULL DEFAULT 24,

    -- Inversion candidate counts
    inversion_candidates_received INTEGER NOT NULL DEFAULT 0,
    inversion_candidates_accepted INTEGER NOT NULL DEFAULT 0,
    inversion_candidates_refused INTEGER NOT NULL DEFAULT 0,
    inversion_refusal_rate NUMERIC NOT NULL DEFAULT 0,

    -- Refusal reasons breakdown
    refused_unverified INTEGER NOT NULL DEFAULT 0,      -- No verified_inverted=true
    refused_low_confidence INTEGER NOT NULL DEFAULT 0,  -- Below threshold
    refused_ttl INTEGER NOT NULL DEFAULT 0,
    refused_defcon INTEGER NOT NULL DEFAULT 0,
    refused_other INTEGER NOT NULL DEFAULT 0,

    -- CEO R3: 50% friction escalation
    threshold_pct NUMERIC NOT NULL DEFAULT 0.50,
    threshold_exceeded BOOLEAN NOT NULL DEFAULT false,
    strategic_friction_report_triggered BOOLEAN NOT NULL DEFAULT false,
    escalation_sent_to TEXT DEFAULT NULL,  -- LARS per CEO R3
    escalation_timestamp TIMESTAMPTZ DEFAULT NULL,

    -- Audit
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ec_contract_number TEXT NOT NULL DEFAULT 'EC-015'
);

CREATE INDEX IF NOT EXISTS idx_inversion_friction_window
ON fhq_alpha.cpto_inversion_friction_log(window_start, window_end);

-- =============================================================================
-- B3: Evidence Requirements for Inversion Candidates
-- =============================================================================

-- Create inversion evidence table
CREATE TABLE IF NOT EXISTS fhq_alpha.inversion_candidate_evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID NOT NULL,
    plan_id UUID REFERENCES fhq_alpha.g2_decision_plans(plan_id),

    -- Inversion classification inputs
    regime_at_signal TEXT NOT NULL,
    confidence_at_signal NUMERIC NOT NULL,
    verified_inverted BOOLEAN NOT NULL DEFAULT false,
    inversion_verification_source TEXT,  -- e.g., 'IoS-012B', 'CEO-DIR-2026-105'

    -- Evidence requirements (all must be present for verified_inverted=true)
    historical_inversion_evidence JSONB,   -- Past regime-vs-outcome data
    current_regime_mismatch_score NUMERIC, -- Degree of regime/signal mismatch
    statistical_significance_pvalue NUMERIC,
    backtested_inversion_return NUMERIC,

    -- CPTO processing outcome
    cpto_decision TEXT,  -- 'ACCEPTED', 'REFUSED', 'PENDING'
    cpto_refusal_reason TEXT,
    cpto_processed_at TIMESTAMPTZ,

    -- Friction feedback (CEO R2)
    logged_to_friction BOOLEAN DEFAULT false,
    friction_escalation_target TEXT,  -- 'FINN' per CEO R2

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    evidence_hash TEXT
);

CREATE INDEX IF NOT EXISTS idx_inversion_evidence_signal
ON fhq_alpha.inversion_candidate_evidence(signal_id);

CREATE INDEX IF NOT EXISTS idx_inversion_evidence_regime
ON fhq_alpha.inversion_candidate_evidence(regime_at_signal, verified_inverted);

-- =============================================================================
-- Signal Class Definition View
-- =============================================================================

CREATE OR REPLACE VIEW fhq_alpha.v_signal_class_definitions AS
SELECT
    'STANDARD' as signal_class,
    'Normal signal flow - standard CPTO processing' as description,
    '["TTL_CHECK", "DEFCON_CHECK", "LIQUIDITY_CHECK"]'::jsonb as required_gates,
    'EC-015' as processing_contract,
    NULL as special_friction_handling
UNION ALL
SELECT
    'LOW_CONFIDENCE_INVERSION_CANDIDATE',
    'STRESS regime inversion candidate - requires verified_inverted evidence',
    '["TTL_CHECK", "DEFCON_CHECK", "LIQUIDITY_CHECK", "INVERSION_VERIFICATION"]'::jsonb,
    'EC-015',
    'FINN escalation on refusal (CEO-DIR-2026-110 R2)'
UNION ALL
SELECT
    'HIGH_CONFIDENCE_VERIFIED',
    'Verified high-confidence signal with full evidence chain',
    '["TTL_CHECK", "DEFCON_CHECK"]'::jsonb,
    'EC-015',
    NULL
UNION ALL
SELECT
    'EXPERIMENTAL',
    'Research/shadow signals - logging only, no execution',
    '["TTL_CHECK"]'::jsonb,
    'EC-015',
    'Shadow mode only';

-- =============================================================================
-- Governance Logging
-- =============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    vega_reviewed
) VALUES (
    'SCHEMA_MIGRATION',
    'CEO-DIR-2026-110',
    'SIGNAL_CLASS_DEFINITION',
    'STIG',
    NOW(),
    'APPROVED',
    'Migration 322: LOW_CONFIDENCE_INVERSION_CANDIDATE signal class with CPTO gating and evidence requirements per CEO-DIR-2026-110 Mandate B',
    false
);

COMMIT;

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Verify signal_class column exists
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'fhq_alpha'
AND table_name = 'g2_decision_plans'
AND column_name = 'signal_class';

-- Verify inversion friction log created
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'fhq_alpha'
AND table_name = 'cpto_inversion_friction_log';

-- Verify evidence table created
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'fhq_alpha'
AND table_name = 'inversion_candidate_evidence';
