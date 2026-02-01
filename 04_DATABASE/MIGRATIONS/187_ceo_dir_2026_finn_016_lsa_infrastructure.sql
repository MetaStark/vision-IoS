-- Migration 187: CEO-DIR-2026-FINN-016 - Steady-State Graduation & LSA Infrastructure
-- Classification: GOVERNANCE-CRITICAL (Tier-1)
-- Authority: CEO via ADR-014
-- Date: 2025-12-31

BEGIN;

-- ============================================================================
-- SECTION 1: Store CEO Directive in governance_documents
-- ============================================================================

INSERT INTO fhq_governance.governance_documents (
    document_id,
    document_name,
    document_type,
    tier,
    version,
    content,
    created_at,
    approved_by,
    status
) VALUES (
    gen_random_uuid(),
    'CEO-DIR-2026-FINN-016',
    'CEO_DIRECTIVE',
    1,
    'v2',
    '{
        "directive_id": "CEO-DIR-2026-FINN-016",
        "title": "Steady-State Graduation & Learning State Canonicalization",
        "classification": "GOVERNANCE-CRITICAL (Tier-1)",
        "status": "MANDATORY_EXECUTION",
        "authority": "CEO via ADR-014",
        "effective_date": "2025-12-31T22:00:00Z",
        "executive_intent": "Transition from batch-average to steady-state validation. Batch 10 is operational certification, not experiment.",
        "sections": {
            "graduation_criteria": {
                "steady_state_window": 50,
                "convergence_epsilon": 0.002,
                "rdi_floor": 0.58,
                "waste_ceiling": 0.33,
                "variance_cap": 0.05,
                "vitality_threshold": 0.15,
                "vitality_margin": 0.03
            },
            "lsa_requirements": {
                "storage": "fhq_meta.learning_state_artifacts",
                "integrity": ["SHA-256", "Ed25519", "VEGA-attested"],
                "contents": ["alpha_graph_weights", "success_rates", "roi_thresholds", "regime_summaries"]
            },
            "batch10_mandate": {
                "run_count": 100,
                "objective": "operational_certification",
                "parameter_freeze": true,
                "success_triggers": ["G4_recommendation", "operational_autonomy_certification"]
            }
        }
    }',
    NOW(),
    'CEO',
    'ACTIVE'
);

-- ============================================================================
-- SECTION 2: Create Learning State Artifacts (LSA) Table
-- Per Section 3: LSA must be stored, SHA-256 hashed, cryptographically signed
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.learning_state_artifacts (
    lsa_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id TEXT NOT NULL,
    directive_id TEXT NOT NULL,

    -- Learning State Content (Section 3.1)
    alpha_graph_weights JSONB NOT NULL,
    success_rates_by_path JSONB NOT NULL,
    roi_thresholds JSONB NOT NULL,
    regime_summaries JSONB NOT NULL,

    -- Derived Metrics for Warm Start
    final_base_rate NUMERIC(5,4) NOT NULL,
    final_rdi NUMERIC(5,4) NOT NULL,
    final_waste NUMERIC(5,4) NOT NULL,
    usage_rate_bounds JSONB NOT NULL,
    info_gain_bounds JSONB NOT NULL,
    redundancy_bounds JSONB NOT NULL,

    -- Integrity (Section 3.2)
    content_hash TEXT NOT NULL,  -- SHA-256 of full state
    signature TEXT,              -- Ed25519 signature
    vega_attestation_id UUID,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'FINN',

    -- Governance State
    is_canonical BOOLEAN NOT NULL DEFAULT FALSE,
    superseded_by UUID REFERENCES fhq_meta.learning_state_artifacts(lsa_id),

    -- Constraints
    CONSTRAINT lsa_unique_batch UNIQUE(batch_id),
    CONSTRAINT lsa_valid_rates CHECK (
        final_base_rate BETWEEN 0 AND 1 AND
        final_rdi BETWEEN 0 AND 1 AND
        final_waste BETWEEN 0 AND 1
    )
);

-- Index for fast lookup of canonical LSA
CREATE INDEX idx_lsa_canonical ON fhq_meta.learning_state_artifacts(is_canonical) WHERE is_canonical = TRUE;
CREATE INDEX idx_lsa_batch ON fhq_meta.learning_state_artifacts(batch_id);

-- ============================================================================
-- SECTION 3: LSA Inheritance Validation Function
-- Per Section 3.3: Missing/mismatched LSA = Class A Violation
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_meta.validate_lsa_inheritance(
    p_predecessor_batch TEXT,
    p_expected_hash TEXT
) RETURNS TABLE (
    is_valid BOOLEAN,
    violation_type TEXT,
    lsa_id UUID,
    actual_hash TEXT
) AS $$
DECLARE
    v_lsa RECORD;
BEGIN
    -- Find predecessor LSA
    SELECT * INTO v_lsa
    FROM fhq_meta.learning_state_artifacts
    WHERE batch_id = p_predecessor_batch
    AND is_canonical = TRUE;

    -- Check: Missing LSA
    IF v_lsa IS NULL THEN
        RETURN QUERY SELECT
            FALSE::BOOLEAN,
            'MISSING_LSA'::TEXT,
            NULL::UUID,
            NULL::TEXT;
        RETURN;
    END IF;

    -- Check: Hash mismatch
    IF v_lsa.content_hash != p_expected_hash THEN
        RETURN QUERY SELECT
            FALSE::BOOLEAN,
            'HASH_MISMATCH'::TEXT,
            v_lsa.lsa_id,
            v_lsa.content_hash;
        RETURN;
    END IF;

    -- Valid inheritance
    RETURN QUERY SELECT
        TRUE::BOOLEAN,
        NULL::TEXT,
        v_lsa.lsa_id,
        v_lsa.content_hash;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 4: Steady-State Graduation Criteria Table
-- Per Section 2: Canonical graduation criteria for all future batches
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.steady_state_criteria (
    criteria_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    directive_id TEXT NOT NULL,
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Window Configuration
    steady_state_window INT NOT NULL DEFAULT 50,

    -- 2.1 Convergence Detection
    convergence_epsilon NUMERIC(6,4) NOT NULL DEFAULT 0.002,

    -- 2.2 Target Floor
    rdi_floor NUMERIC(4,2) NOT NULL DEFAULT 0.58,

    -- 2.3 Efficiency Gate
    waste_ceiling NUMERIC(4,2) NOT NULL DEFAULT 0.33,

    -- 2.4 Variance Cap
    variance_cap NUMERIC(4,2) NOT NULL DEFAULT 0.05,

    -- 2.5 Vitality Constraint
    vitality_threshold NUMERIC(4,2) NOT NULL DEFAULT 0.15,
    vitality_margin NUMERIC(4,2) NOT NULL DEFAULT 0.03,

    -- Governance
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    superseded_by UUID REFERENCES fhq_governance.steady_state_criteria(criteria_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert canonical criteria from CEO-DIR-2026-FINN-016
INSERT INTO fhq_governance.steady_state_criteria (
    directive_id,
    steady_state_window,
    convergence_epsilon,
    rdi_floor,
    waste_ceiling,
    variance_cap,
    vitality_threshold,
    vitality_margin,
    is_active
) VALUES (
    'CEO-DIR-2026-FINN-016',
    50,
    0.002,
    0.58,
    0.33,
    0.05,
    0.15,
    0.03,
    TRUE
);

-- ============================================================================
-- SECTION 5: Batch Graduation Log
-- Track graduation attempts and outcomes per batch
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.batch_graduation_log (
    graduation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id TEXT NOT NULL,
    directive_id TEXT NOT NULL,
    criteria_id UUID REFERENCES fhq_governance.steady_state_criteria(criteria_id),

    -- Run Range
    run_start INT NOT NULL,
    run_end INT NOT NULL,
    steady_state_start INT NOT NULL,  -- First run of SS window

    -- Results
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Individual Gate Results
    convergence_slope NUMERIC(8,6),
    convergence_passed BOOLEAN,

    rdi_mean NUMERIC(5,4),
    rdi_passed BOOLEAN,

    waste_mean NUMERIC(5,4),
    waste_passed BOOLEAN,

    rdi_std_dev NUMERIC(5,4),
    variance_passed BOOLEAN,

    vitality_count INT,
    vitality_percentage NUMERIC(5,4),
    vitality_passed BOOLEAN,

    -- Overall
    all_gates_passed BOOLEAN NOT NULL,
    graduation_status TEXT NOT NULL CHECK (graduation_status IN (
        'GRADUATED',
        'REVIEW_REQUIRED',
        'FAILED',
        'PENDING'
    )),

    -- Governance Actions Triggered
    g4_recommendation_issued BOOLEAN DEFAULT FALSE,
    certification_granted BOOLEAN DEFAULT FALSE,

    -- Evidence
    evidence_path TEXT,
    evidence_hash TEXT
);

CREATE INDEX idx_graduation_batch ON fhq_governance.batch_graduation_log(batch_id);
CREATE INDEX idx_graduation_status ON fhq_governance.batch_graduation_log(graduation_status);

-- ============================================================================
-- SECTION 6: Audit Trail
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
    'MIGRATION_APPLIED',
    'CEO-DIR-2026-FINN-016',
    'CEO_DIRECTIVE',
    'STIG',
    NOW(),
    'EXECUTED',
    'Applied Migration 187: CEO-DIR-2026-FINN-016 LSA Infrastructure - Steady-State Graduation & Learning State Canonicalization',
    jsonb_build_object(
        'migration_id', '187',
        'directive', 'CEO-DIR-2026-FINN-016',
        'tables_created', ARRAY[
            'fhq_meta.learning_state_artifacts',
            'fhq_governance.steady_state_criteria',
            'fhq_governance.batch_graduation_log'
        ],
        'functions_created', ARRAY[
            'fhq_meta.validate_lsa_inheritance'
        ]
    ),
    'STIG',
    NOW()
);

COMMIT;
