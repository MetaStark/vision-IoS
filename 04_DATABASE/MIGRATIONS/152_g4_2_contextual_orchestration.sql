-- ============================================================================
-- MIGRATION 152: G4.2 CONTEXTUAL ALPHA ORCHESTRATION
-- CEO Directive WAVE 16C - 2025-12-18
-- ============================================================================
-- PURPOSE: Implement Context-Gated Alpha framework with locked parameters
--
-- LOCKED INSTITUTIONAL PARAMETERS (CEO-APPROVED):
--   1. ORTHOGONALITY_THRESHOLD: 0.3 (correlation must be < 0.3)
--   2. CONTEXT_STABILITY_PERIODS: 3 (minimum periods before permit)
--   3. MINIMUM_SAMPLE_SIZE: 30 (trades required for valid classification)
--   4. CONTEXT_COVERAGE_FLOOR: 0.15 (15% minimum coverage)
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. LOCKED PARAMETERS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.g4_2_parameters (
    parameter_name TEXT PRIMARY KEY,
    parameter_value NUMERIC NOT NULL,
    description TEXT,
    locked_at TIMESTAMPTZ DEFAULT NOW(),
    locked_by TEXT DEFAULT 'CEO_DIRECTIVE_WAVE_16C',
    immutable BOOLEAN DEFAULT TRUE
);

-- Insert locked parameters (CEO-approved, immutable)
INSERT INTO fhq_canonical.g4_2_parameters (parameter_name, parameter_value, description) VALUES
    ('ORTHOGONALITY_THRESHOLD', 0.3, 'Maximum correlation between signal trigger and context features'),
    ('CONTEXT_STABILITY_PERIODS', 3, 'Minimum periods context must be stable before permit'),
    ('MINIMUM_SAMPLE_SIZE', 30, 'Minimum trades required for valid classification'),
    ('CONTEXT_COVERAGE_FLOOR', 0.15, 'Minimum fraction of backtest periods context must cover (15%)')
ON CONFLICT (parameter_name) DO NOTHING;

-- Prevent modification of locked parameters
CREATE OR REPLACE FUNCTION fhq_canonical.protect_g4_2_parameters()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.immutable = TRUE THEN
        RAISE EXCEPTION 'G4.2 parameter % is immutable (CEO Directive WAVE 16C)', OLD.parameter_name;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_protect_g4_2_parameters ON fhq_canonical.g4_2_parameters;
CREATE TRIGGER trg_protect_g4_2_parameters
    BEFORE UPDATE OR DELETE ON fhq_canonical.g4_2_parameters
    FOR EACH ROW EXECUTE FUNCTION fhq_canonical.protect_g4_2_parameters();

-- ============================================================================
-- 2. CONTEXT PROFILES TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.g4_2_context_profiles (
    profile_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    needle_id UUID NOT NULL REFERENCES fhq_canonical.golden_needles(needle_id),
    context_name TEXT NOT NULL,

    -- Context Definition (JSONB for flexibility)
    context_definition JSONB NOT NULL,
    -- Example: {"regime": "NEUTRAL", "regime_confidence_min": 0.70, "vol_state": "COMPRESSING"}

    -- Orthogonality Verification
    orthogonality_score NUMERIC,  -- Must be < 0.3 to pass
    orthogonality_verified BOOLEAN DEFAULT FALSE,
    orthogonality_features JSONB,  -- Which features were tested

    -- Coverage Statistics
    coverage_periods INT,
    total_periods INT,
    coverage_ratio NUMERIC,  -- Must be >= 0.15 to pass

    -- Governance
    created_by TEXT NOT NULL,  -- FINN
    created_at TIMESTAMPTZ DEFAULT NOW(),
    vega_reviewed BOOLEAN DEFAULT FALSE,
    vega_approved BOOLEAN DEFAULT FALSE,
    vega_reviewed_at TIMESTAMPTZ,
    vega_notes TEXT,

    -- Status
    status TEXT DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'OVERFITTED')),

    UNIQUE(needle_id, context_name)
);

CREATE INDEX IF NOT EXISTS idx_g4_2_context_profiles_needle ON fhq_canonical.g4_2_context_profiles(needle_id);
CREATE INDEX IF NOT EXISTS idx_g4_2_context_profiles_status ON fhq_canonical.g4_2_context_profiles(status);

-- ============================================================================
-- 3. CONTEXTUAL BACKTEST RESULTS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.g4_2_contextual_backtest (
    backtest_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    needle_id UUID NOT NULL REFERENCES fhq_canonical.golden_needles(needle_id),
    profile_id UUID NOT NULL REFERENCES fhq_canonical.g4_2_context_profiles(profile_id),
    context_name TEXT NOT NULL,

    -- Window Statistics
    total_periods INT NOT NULL,
    permitted_periods INT NOT NULL,
    blocked_periods INT NOT NULL,
    suppression_rate NUMERIC NOT NULL,  -- blocked / total

    -- Trade Statistics (within permitted windows only)
    trade_count INT NOT NULL,
    winning_trades INT,
    losing_trades INT,
    win_rate NUMERIC,

    -- Performance Metrics (context-gated)
    contextual_sharpe NUMERIC,
    contextual_sortino NUMERIC,
    contextual_max_dd NUMERIC,
    contextual_total_return NUMERIC,
    contextual_cagr NUMERIC,

    -- Damage Avoided (what would have happened if we ignored context)
    ungated_sharpe NUMERIC,
    ungated_max_dd NUMERIC,
    damage_avoided_dd NUMERIC,  -- ungated_max_dd - contextual_max_dd

    -- Context Stability
    avg_context_duration INT,  -- Average periods per context window
    context_transitions INT,   -- Number of times context flipped

    -- Classification (per CEO Directive taxonomy)
    classification TEXT CHECK (classification IN (
        'VALIDATED-CONTEXTUAL',   -- Sharpe >1.5 in context, N>=30, coverage>=15%
        'UNSTABLE-CONTEXTUAL',    -- Edge exists but context too rare or unstable
        'INSUFFICIENT_SAMPLE',    -- Context valid but <30 trades remain
        'ILLUSORY'                -- Fails even with context gating
    )),

    -- Classification Reasoning
    classification_reason JSONB,

    -- Timestamps
    backtest_started_at TIMESTAMPTZ,
    backtest_completed_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(needle_id, profile_id)
);

CREATE INDEX IF NOT EXISTS idx_g4_2_backtest_needle ON fhq_canonical.g4_2_contextual_backtest(needle_id);
CREATE INDEX IF NOT EXISTS idx_g4_2_backtest_classification ON fhq_canonical.g4_2_contextual_backtest(classification);

-- ============================================================================
-- 4. SUPPRESSION LOG (Track "Silence as Position")
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.g4_2_suppression_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    needle_id UUID NOT NULL,
    profile_id UUID,

    -- Signal Details
    signal_timestamp TIMESTAMPTZ NOT NULL,
    signal_direction TEXT,  -- LONG, SHORT
    signal_strength NUMERIC,

    -- Context at Signal Time
    context_state JSONB,
    context_valid BOOLEAN NOT NULL,

    -- Action
    action TEXT NOT NULL CHECK (action IN ('PERMITTED', 'BLOCKED')),
    block_reason TEXT,

    -- Counterfactual (what would have happened)
    hypothetical_pnl NUMERIC,
    hypothetical_outcome TEXT,  -- WIN, LOSS, UNKNOWN

    logged_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_g4_2_suppression_needle ON fhq_canonical.g4_2_suppression_log(needle_id);
CREATE INDEX IF NOT EXISTS idx_g4_2_suppression_action ON fhq_canonical.g4_2_suppression_log(action);
CREATE INDEX IF NOT EXISTS idx_g4_2_suppression_ts ON fhq_canonical.g4_2_suppression_log(signal_timestamp);

-- ============================================================================
-- 5. G4.2 COMPOSITE VERDICT TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.g4_2_composite_verdict (
    verdict_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    needle_id UUID NOT NULL REFERENCES fhq_canonical.golden_needles(needle_id),

    -- Best Context (if any)
    best_context_profile_id UUID REFERENCES fhq_canonical.g4_2_context_profiles(profile_id),
    best_context_name TEXT,

    -- Aggregate Metrics
    best_contextual_sharpe NUMERIC,
    best_suppression_rate NUMERIC,
    best_trade_count INT,

    -- Final Classification
    final_classification TEXT NOT NULL CHECK (final_classification IN (
        'VALIDATED-CONTEXTUAL',
        'UNSTABLE-CONTEXTUAL',
        'INSUFFICIENT_SAMPLE',
        'ILLUSORY',
        'NO_VALID_CONTEXT'  -- No context profile passed all thresholds
    )),

    -- G5 Eligibility
    g5_eligible BOOLEAN DEFAULT FALSE,
    g5_eligibility_reason TEXT,

    -- Governance
    validated_at TIMESTAMPTZ DEFAULT NOW(),
    vega_attested BOOLEAN DEFAULT FALSE,
    vega_attestation_at TIMESTAMPTZ,

    UNIQUE(needle_id)
);

CREATE INDEX IF NOT EXISTS idx_g4_2_verdict_classification ON fhq_canonical.g4_2_composite_verdict(final_classification);
CREATE INDEX IF NOT EXISTS idx_g4_2_verdict_g5 ON fhq_canonical.g4_2_composite_verdict(g5_eligible);

-- ============================================================================
-- 6. HELPER FUNCTIONS
-- ============================================================================

-- Function to check if context passes all thresholds
CREATE OR REPLACE FUNCTION fhq_canonical.g4_2_validate_context(
    p_orthogonality_score NUMERIC,
    p_coverage_ratio NUMERIC,
    p_trade_count INT,
    p_sharpe NUMERIC
) RETURNS TABLE (
    passes_orthogonality BOOLEAN,
    passes_coverage BOOLEAN,
    passes_sample_size BOOLEAN,
    passes_sharpe BOOLEAN,
    overall_pass BOOLEAN,
    classification TEXT
) AS $$
DECLARE
    v_orth_threshold NUMERIC;
    v_coverage_floor NUMERIC;
    v_min_sample INT;
BEGIN
    -- Get locked parameters
    SELECT parameter_value INTO v_orth_threshold
    FROM fhq_canonical.g4_2_parameters WHERE parameter_name = 'ORTHOGONALITY_THRESHOLD';

    SELECT parameter_value INTO v_coverage_floor
    FROM fhq_canonical.g4_2_parameters WHERE parameter_name = 'CONTEXT_COVERAGE_FLOOR';

    SELECT parameter_value::INT INTO v_min_sample
    FROM fhq_canonical.g4_2_parameters WHERE parameter_name = 'MINIMUM_SAMPLE_SIZE';

    -- Evaluate thresholds
    passes_orthogonality := (p_orthogonality_score < v_orth_threshold);
    passes_coverage := (p_coverage_ratio >= v_coverage_floor);
    passes_sample_size := (p_trade_count >= v_min_sample);
    passes_sharpe := (p_sharpe >= 1.5);

    overall_pass := passes_orthogonality AND passes_coverage AND passes_sample_size AND passes_sharpe;

    -- Determine classification
    IF NOT passes_orthogonality THEN
        classification := 'ILLUSORY';  -- Correlated context = not real edge
    ELSIF NOT passes_coverage THEN
        classification := 'UNSTABLE-CONTEXTUAL';  -- Too rare
    ELSIF NOT passes_sample_size THEN
        classification := 'INSUFFICIENT_SAMPLE';
    ELSIF NOT passes_sharpe THEN
        classification := 'UNSTABLE-CONTEXTUAL';  -- Edge too weak
    ELSE
        classification := 'VALIDATED-CONTEXTUAL';
    END IF;

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate orthogonality between two feature series
CREATE OR REPLACE FUNCTION fhq_canonical.g4_2_calculate_orthogonality(
    p_signal_features NUMERIC[],
    p_context_features NUMERIC[]
) RETURNS NUMERIC AS $$
DECLARE
    v_correlation NUMERIC;
BEGIN
    -- Calculate Pearson correlation
    SELECT corr(s.val, c.val)
    INTO v_correlation
    FROM unnest(p_signal_features) WITH ORDINALITY AS s(val, idx)
    JOIN unnest(p_context_features) WITH ORDINALITY AS c(val, idx) ON s.idx = c.idx;

    RETURN COALESCE(ABS(v_correlation), 1.0);  -- Default to 1.0 (fail) if null
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 7. GOVERNANCE REGISTRATION
-- ============================================================================

INSERT INTO fhq_meta.ios_registry (
    ios_id, title, version, description, status,
    owner_role, governing_adrs, content_hash, created_at
) VALUES (
    'G4.2',
    'Contextual Alpha Orchestration',
    '1.0.0',
    'Context-gated signal validation per CEO Directive WAVE 16C. Implements Permission-to-Speak protocol with orthogonality constraints.',
    'ACTIVE',
    'STIG',
    ARRAY['ADR-004', 'ADR-012'],
    encode(sha256('G4.2-WAVE16C-20251218'::bytea), 'hex'),
    NOW()
) ON CONFLICT (ios_id) DO UPDATE SET
    version = EXCLUDED.version,
    description = EXCLUDED.description,
    status = EXCLUDED.status;

-- ============================================================================
-- 8. AUDIT LOG
-- ============================================================================

INSERT INTO fhq_governance.audit_log (
    event_type, event_category, target_type, target_id,
    actor_id, actor_role, event_data, event_hash, governance_gate, adr_reference
) VALUES (
    'MIGRATION',
    'OPERATIONAL',
    'SCHEMA',
    'fhq_canonical.g4_2_*',
    'STIG',
    'CTO',
    '{"directive": "WAVE_16C", "locked_params": {"orthogonality": 0.3, "stability": 3, "sample_size": 30, "coverage": 0.15}}'::jsonb,
    encode(sha256(('G4.2-MIGRATION-' || NOW()::text)::bytea), 'hex'),
    'G4',
    'ADR-004'
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_params INT;
    v_tables INT;
BEGIN
    SELECT COUNT(*) INTO v_params FROM fhq_canonical.g4_2_parameters;

    SELECT COUNT(*) INTO v_tables
    FROM information_schema.tables
    WHERE table_schema = 'fhq_canonical'
    AND table_name LIKE 'g4_2_%';

    RAISE NOTICE 'G4.2 Migration Complete: % locked parameters, % tables created', v_params, v_tables;

    IF v_params < 4 THEN
        RAISE EXCEPTION 'Missing locked parameters - migration incomplete';
    END IF;
END $$;
