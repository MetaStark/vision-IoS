-- ============================================================================
-- Migration 154: G4.1 Deep Validation Schema
-- ============================================================================
-- CEO Directive: WAVE 16B - G4.1 DEEP VALIDATION
-- Date: 2025-12-18
-- Purpose: Edge Verification, Stability & Anti-Illusion Testing
--
-- MANDATES SUPPORTED:
--   I.   Multi-Window Stability Test
--   II.  Regime Rotation Validation
--   III. Parameter Sensitivity (Anti-Curve-Fit)
--   IV.  Signal Density & Crowding Check
--
-- THIS IS NOT A PHASE CHANGE - Internal G4 Extension Only
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. G4.1 MULTI-WINDOW STABILITY RESULTS (MANDATE I)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.g4_1_stability_results (
    result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    needle_id UUID NOT NULL REFERENCES fhq_canonical.golden_needles(needle_id),

    -- Original G4 classification (for lineage)
    original_classification TEXT NOT NULL,
    original_sharpe DECIMAL(8,4),

    -- Window definitions
    window_count INTEGER NOT NULL DEFAULT 3,
    window_definitions JSONB NOT NULL,  -- [{start, end, label}]

    -- Per-window results
    window_1_sharpe DECIMAL(8,4),
    window_1_classification TEXT,
    window_1_trades INTEGER,
    window_1_passed BOOLEAN,

    window_2_sharpe DECIMAL(8,4),
    window_2_classification TEXT,
    window_2_trades INTEGER,
    window_2_passed BOOLEAN,

    window_3_sharpe DECIMAL(8,4),
    window_3_classification TEXT,
    window_3_trades INTEGER,
    window_3_passed BOOLEAN,

    -- Stability verdict
    windows_passed INTEGER NOT NULL DEFAULT 0,
    windows_failed INTEGER NOT NULL DEFAULT 0,
    stability_verdict TEXT NOT NULL CHECK (stability_verdict IN (
        'STABLE',       -- All windows pass
        'CONDITIONAL',  -- 2/3 windows pass
        'UNSTABLE',     -- 1/3 windows pass
        'ILLUSORY'      -- 0/3 windows pass
    )),

    -- Classification adjustment
    classification_downgraded BOOLEAN DEFAULT FALSE,
    new_classification TEXT,
    downgrade_reason TEXT,

    -- Audit
    tested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    test_duration_seconds DECIMAL(10,2),

    UNIQUE(needle_id)
);

CREATE INDEX IF NOT EXISTS idx_g4_1_stability_needle ON fhq_canonical.g4_1_stability_results(needle_id);
CREATE INDEX IF NOT EXISTS idx_g4_1_stability_verdict ON fhq_canonical.g4_1_stability_results(stability_verdict);

-- ============================================================================
-- 2. G4.1 REGIME ROTATION RESULTS (MANDATE II)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.g4_1_regime_rotation_results (
    result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    needle_id UUID NOT NULL REFERENCES fhq_canonical.golden_needles(needle_id),

    -- Original regime specification
    target_regime TEXT NOT NULL,
    regime_dependent BOOLEAN NOT NULL,

    -- Wrong-regime test results
    wrong_regime_tested TEXT NOT NULL,  -- Which regime was tested
    wrong_regime_sharpe DECIMAL(8,4),
    wrong_regime_trades INTEGER,
    wrong_regime_win_rate DECIMAL(5,4),

    -- Regime specificity verification
    edge_in_wrong_regime BOOLEAN,  -- True if still positive edge
    regime_specificity_confirmed BOOLEAN,

    -- Verdict
    rotation_verdict TEXT NOT NULL CHECK (rotation_verdict IN (
        'REGIME_SPECIFIC',     -- Edge only in target regime (correct)
        'REGIME_AGNOSTIC',     -- Edge works everywhere (misclassified)
        'REGIME_INVERTED',     -- Better in wrong regime (suspicious)
        'INSUFFICIENT_DATA'    -- Cannot test
    )),

    -- Classification impact
    misclassification_detected BOOLEAN DEFAULT FALSE,
    reclassification_required BOOLEAN DEFAULT FALSE,

    -- Audit
    tested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(needle_id)
);

CREATE INDEX IF NOT EXISTS idx_g4_1_regime_needle ON fhq_canonical.g4_1_regime_rotation_results(needle_id);

-- ============================================================================
-- 3. G4.1 PARAMETER SENSITIVITY RESULTS (MANDATE III)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.g4_1_sensitivity_results (
    result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    needle_id UUID NOT NULL REFERENCES fhq_canonical.golden_needles(needle_id),

    -- Baseline parameters
    baseline_params JSONB NOT NULL,
    baseline_sharpe DECIMAL(8,4),

    -- Perturbation tests (±10%, ±20%)
    perturbation_results JSONB NOT NULL,  -- Array of {param, delta, sharpe, classification}

    -- Sensitivity metrics
    avg_sharpe_at_minus_20 DECIMAL(8,4),
    avg_sharpe_at_minus_10 DECIMAL(8,4),
    avg_sharpe_at_plus_10 DECIMAL(8,4),
    avg_sharpe_at_plus_20 DECIMAL(8,4),

    -- Degradation analysis
    max_sharpe_drop_pct DECIMAL(8,4),
    cliff_edge_detected BOOLEAN,  -- Sharp collapse at small perturbation
    smooth_degradation BOOLEAN,   -- Gradual decline (good)

    -- Sensitivity verdict
    sensitivity_verdict TEXT NOT NULL CHECK (sensitivity_verdict IN (
        'ROBUST',       -- Smooth degradation, maintains positive edge
        'SENSITIVE',    -- Some cliff edges but recoverable
        'BRITTLE',      -- Cliff-edge collapse
        'CURVE_FIT'     -- Only works at exact parameters
    )),

    -- Classification impact
    downgrade_recommended BOOLEAN DEFAULT FALSE,

    -- Audit
    tested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    perturbations_tested INTEGER,

    UNIQUE(needle_id)
);

CREATE INDEX IF NOT EXISTS idx_g4_1_sensitivity_needle ON fhq_canonical.g4_1_sensitivity_results(needle_id);

-- ============================================================================
-- 4. G4.1 SIGNAL DENSITY RESULTS (MANDATE IV)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.g4_1_density_results (
    result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    needle_id UUID NOT NULL REFERENCES fhq_canonical.golden_needles(needle_id),

    -- Signal frequency metrics
    total_signals_generated INTEGER,
    signals_per_year DECIMAL(8,2),
    signals_per_month DECIMAL(8,2),

    -- Edge vs frequency
    edge_per_signal DECIMAL(10,6),  -- Return contribution per signal
    sharpe_per_signal DECIMAL(10,6),

    -- Crowding analysis
    max_concurrent_signals INTEGER,
    avg_signal_gap_days DECIMAL(8,2),
    min_signal_gap_days DECIMAL(8,2),

    -- Density classification
    density_classification TEXT NOT NULL CHECK (density_classification IN (
        'OPTIMAL',      -- Good frequency, sustainable edge
        'SPARSE',       -- High Sharpe but rare (flag for review)
        'CROWDED',      -- Over-triggering, diminishing returns
        'THEORETICAL'   -- Too sparse for practical use
    )),

    -- Flags
    high_sharpe_extreme_sparsity BOOLEAN DEFAULT FALSE,
    crowding_risk_detected BOOLEAN DEFAULT FALSE,

    -- Practical viability
    practical_viability TEXT CHECK (practical_viability IN (
        'VIABLE',
        'CONDITIONAL',
        'IMPRACTICAL'
    )),

    -- Audit
    tested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(needle_id)
);

CREATE INDEX IF NOT EXISTS idx_g4_1_density_needle ON fhq_canonical.g4_1_density_results(needle_id);

-- ============================================================================
-- 5. G4.1 COMPOSITE VERDICT (AGGREGATED)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.g4_1_composite_verdict (
    verdict_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    needle_id UUID NOT NULL REFERENCES fhq_canonical.golden_needles(needle_id),

    -- Original G4 state (for lineage)
    g4_classification TEXT NOT NULL,
    g4_sharpe DECIMAL(8,4),

    -- Component verdicts
    stability_verdict TEXT,
    regime_verdict TEXT,
    sensitivity_verdict TEXT,
    density_verdict TEXT,

    -- Final G4.1 assessment
    edge_assessment TEXT NOT NULL CHECK (edge_assessment IN (
        'STABLE',       -- All tests pass - edge is real
        'CONDITIONAL',  -- Some concerns but edge likely real
        'FRAGILE',      -- Edge exists but unreliable
        'ILLUSORY'      -- Edge is mirage - do not proceed
    )),

    -- Classification changes
    classification_changed BOOLEAN DEFAULT FALSE,
    final_classification TEXT NOT NULL,
    classification_delta INTEGER DEFAULT 0,  -- -1, 0, +1 tier change

    -- G5 eligibility (only STABLE with PLATINUM/GOLD)
    g5_eligible BOOLEAN GENERATED ALWAYS AS (
        edge_assessment = 'STABLE' AND final_classification IN ('PLATINUM', 'GOLD')
    ) STORED,

    -- VEGA attestation
    vega_reviewed BOOLEAN DEFAULT FALSE,
    vega_attestation_hash TEXT,
    vega_attested_at TIMESTAMPTZ,

    -- Audit trail
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lineage_preserved BOOLEAN DEFAULT TRUE,

    UNIQUE(needle_id)
);

CREATE INDEX IF NOT EXISTS idx_g4_1_verdict_assessment ON fhq_canonical.g4_1_composite_verdict(edge_assessment);
CREATE INDEX IF NOT EXISTS idx_g4_1_verdict_g5 ON fhq_canonical.g4_1_composite_verdict(g5_eligible) WHERE g5_eligible = true;

-- ============================================================================
-- 6. GOVERNANCE REGISTRATION
-- ============================================================================

INSERT INTO fhq_meta.adr_registry (
    adr_id, adr_title, adr_status, adr_type, file_path, sha256_hash,
    title, status, current_version, created_by
) VALUES (
    'G4.1-DEEP-001',
    'G4.1 Deep Validation - Edge Verification & Anti-Illusion Testing',
    'APPROVED',
    'OPERATIONAL',
    '04_DATABASE/MIGRATIONS/154_g4_1_deep_validation_schema.sql',
    encode(sha256('g4.1-deep-validation-wave16b-20251218'::bytea), 'hex'),
    'G4.1 Deep Validation Schema',
    'ACTIVE',
    '1.0.0',
    'STIG'
) ON CONFLICT (adr_id) DO UPDATE SET
    adr_status = 'ACTIVE',
    status = 'ACTIVE',
    updated_at = NOW();

-- ============================================================================
-- 7. LOG ACTIVATION EVENT
-- ============================================================================

INSERT INTO fhq_monitoring.system_event_log (event_type, severity, source_system, event_message, metadata)
VALUES (
    'g4_1_deep_validation_activated',
    'INFO',
    'STIG',
    'G4.1 Deep Validation activated per CEO Directive WAVE 16B',
    jsonb_build_object(
        'directive', 'CEO DIRECTIVE WAVE 16B',
        'scope', 'G4.1 DEEP VALIDATION',
        'mandates', jsonb_build_array(
            'MANDATE I: Multi-Window Stability Test',
            'MANDATE II: Regime Rotation Validation',
            'MANDATE III: Parameter Sensitivity (Anti-Curve-Fit)',
            'MANDATE IV: Signal Density & Crowding Check'
        ),
        'tables_created', ARRAY[
            'g4_1_stability_results',
            'g4_1_regime_rotation_results',
            'g4_1_sensitivity_results',
            'g4_1_density_results',
            'g4_1_composite_verdict'
        ],
        'not_a_phase_change', true,
        'timestamp', NOW()
    )
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_tables INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_tables
    FROM information_schema.tables
    WHERE table_schema = 'fhq_canonical'
    AND table_name LIKE 'g4_1_%';

    RAISE NOTICE '=== G4.1 Deep Validation Schema Verification ===';
    RAISE NOTICE 'Tables created: % / 5', v_tables;

    IF v_tables = 5 THEN
        RAISE NOTICE 'STATUS: G4.1 SCHEMA READY';
        RAISE NOTICE 'MANDATE I (Stability): READY';
        RAISE NOTICE 'MANDATE II (Regime): READY';
        RAISE NOTICE 'MANDATE III (Sensitivity): READY';
        RAISE NOTICE 'MANDATE IV (Density): READY';
    ELSE
        RAISE WARNING 'STATUS: INCOMPLETE';
    END IF;
END $$;
