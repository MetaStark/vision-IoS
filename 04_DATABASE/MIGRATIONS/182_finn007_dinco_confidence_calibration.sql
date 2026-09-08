-- Migration 182: DINCO Confidence Calibration Infrastructure
-- CEO-DIR-2026-FINN-007: Operation Freedom 2026 - Batch 2
-- Section 3.3: DINCO Confidence Calibration Protocol
--
-- Purpose: Implement Distractor-Normalized Coherence (DINCO) for
-- confidence calibration. Addresses over-confidence and suggestibility bias.
--
-- Research Basis: DINCO (2025) - Distractor-normalized calibration
-- "Generate distractors, score all answers, normalize primary score"
--
-- Authority: CEO-DIR-2026-FINN-007
-- Owner: FINN
-- Classification: LEARNING_INFRASTRUCTURE

BEGIN;

-- ============================================================================
-- TABLE: dinco_calibration_log
-- Tracks DINCO calibration for each hypothesis response
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.dinco_calibration_log (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Run identification
    run_id                  UUID NOT NULL,
    run_number              INTEGER NOT NULL,
    batch_id                TEXT,
    hypothesis_id           TEXT NOT NULL,

    -- DINCO scoring
    primary_answer          TEXT NOT NULL,
    primary_raw_score       NUMERIC(8,6) NOT NULL,  -- Raw model confidence
    distractor_count        INTEGER NOT NULL DEFAULT 3,
    distractor_answers      JSONB NOT NULL,         -- Array of distractor answers
    distractor_scores       JSONB NOT NULL,         -- Array of distractor scores
    total_score_sum         NUMERIC(10,6) NOT NULL, -- Sum of all scores (primary + distractors)

    -- Normalized confidence (DINCO output)
    dinco_normalized_score  NUMERIC(5,4) GENERATED ALWAYS AS (
                                CASE WHEN total_score_sum > 0
                                     THEN primary_raw_score / total_score_sum
                                     ELSE 0
                                END
                            ) STORED,

    -- Calibration thresholds
    confidence_threshold    NUMERIC(5,4) DEFAULT 0.90,
    is_confident            BOOLEAN GENERATED ALWAYS AS (
                                (CASE WHEN total_score_sum > 0
                                      THEN primary_raw_score / total_score_sum
                                      ELSE 0
                                 END) >= 0.90
                            ) STORED,

    -- Actions taken
    action_taken            TEXT CHECK (action_taken IN (
                                'ACCEPTED',           -- High confidence, proceed
                                'DEEPER_RESEARCH',    -- Low confidence, additional retrieval
                                'HUMAN_REVIEW',       -- Very low confidence, flag for review
                                'REVISED'             -- Self-critique triggered revision
                            )),
    revision_count          INTEGER DEFAULT 0,

    -- Regime context
    regime_id               TEXT NOT NULL,
    regime_confidence       NUMERIC(5,4),

    -- Timestamps
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Governance
    directive_ref           TEXT DEFAULT 'CEO-DIR-2026-FINN-007'
);

-- ============================================================================
-- TABLE: dinco_calibration_metrics
-- Aggregated calibration metrics per batch
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.dinco_calibration_metrics (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Batch identification
    batch_id                TEXT NOT NULL,
    batch_start_run         INTEGER NOT NULL,
    batch_end_run           INTEGER NOT NULL,

    -- Expected Calibration Error (ECE) calculation
    total_hypotheses        INTEGER NOT NULL DEFAULT 0,
    confident_correct       INTEGER NOT NULL DEFAULT 0,  -- High confidence, actually correct
    confident_incorrect     INTEGER NOT NULL DEFAULT 0,  -- High confidence, actually wrong
    uncertain_correct       INTEGER NOT NULL DEFAULT 0,  -- Low confidence, actually correct
    uncertain_incorrect     INTEGER NOT NULL DEFAULT 0,  -- Low confidence, actually wrong

    -- ECE = mean(|confidence - accuracy|) per bin
    ece_score               NUMERIC(5,4),
    ece_target              NUMERIC(5,4) DEFAULT 0.05,  -- Target: < 5%
    ece_status              TEXT GENERATED ALWAYS AS (
                                CASE WHEN ece_score IS NULL THEN 'PENDING'
                                     WHEN ece_score < 0.05 THEN 'PASS'
                                     WHEN ece_score < 0.10 THEN 'WARNING'
                                     ELSE 'FAIL'
                                END
                            ) STORED,

    -- Distribution metrics
    avg_normalized_score    NUMERIC(5,4),
    min_normalized_score    NUMERIC(5,4),
    max_normalized_score    NUMERIC(5,4),
    stddev_normalized_score NUMERIC(5,4),

    -- Action distribution
    accepted_count          INTEGER DEFAULT 0,
    deeper_research_count   INTEGER DEFAULT 0,
    human_review_count      INTEGER DEFAULT 0,
    revised_count           INTEGER DEFAULT 0,

    -- Timestamps
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ,

    -- Governance
    directive_ref           TEXT DEFAULT 'CEO-DIR-2026-FINN-007'
);

-- ============================================================================
-- TABLE: self_critique_records
-- Stores Constitutional AI self-critique outputs per run
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.self_critique_records (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Run identification
    run_id                  UUID NOT NULL,
    run_number              INTEGER NOT NULL,
    batch_id                TEXT,
    hypothesis_id           TEXT NOT NULL,

    -- Original output
    original_output         JSONB NOT NULL,

    -- Constitutional axioms checked
    axioms_checked          JSONB NOT NULL,  -- Array of axiom names

    -- Violations detected
    violations_detected     JSONB,           -- Array of {axiom, description, severity}
    violation_count         INTEGER GENERATED ALWAYS AS (
                                CASE WHEN violations_detected IS NULL THEN 0
                                     ELSE jsonb_array_length(violations_detected)
                                END
                            ) STORED,

    -- Critique reasoning
    critique_reasoning      TEXT NOT NULL,

    -- Revised output (if any)
    was_revised             BOOLEAN DEFAULT FALSE,
    revised_output          JSONB,
    revision_reasoning      TEXT,

    -- Quality assessment
    pre_critique_quality    NUMERIC(5,4),  -- Estimated quality before critique
    post_critique_quality   NUMERIC(5,4),  -- Estimated quality after revision
    quality_improvement     NUMERIC(5,4) GENERATED ALWAYS AS (
                                CASE WHEN pre_critique_quality IS NOT NULL
                                          AND post_critique_quality IS NOT NULL
                                     THEN post_critique_quality - pre_critique_quality
                                     ELSE NULL
                                END
                            ) STORED,

    -- Regime context
    regime_id               TEXT NOT NULL,

    -- Timestamps
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Governance
    directive_ref           TEXT DEFAULT 'CEO-DIR-2026-FINN-007'
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- DINCO calibration queries
CREATE INDEX idx_dinco_run ON fhq_research.dinco_calibration_log(run_id);
CREATE INDEX idx_dinco_batch ON fhq_research.dinco_calibration_log(batch_id);
CREATE INDEX idx_dinco_low_confidence ON fhq_research.dinco_calibration_log(dinco_normalized_score)
    WHERE dinco_normalized_score < 0.90;
CREATE INDEX idx_dinco_action ON fhq_research.dinco_calibration_log(action_taken);

-- Calibration metrics
CREATE INDEX idx_dinco_metrics_batch ON fhq_research.dinco_calibration_metrics(batch_id);
CREATE INDEX idx_dinco_metrics_ece ON fhq_research.dinco_calibration_metrics(ece_score);

-- Self-critique records
CREATE INDEX idx_critique_run ON fhq_research.self_critique_records(run_id);
CREATE INDEX idx_critique_violations ON fhq_research.self_critique_records(violation_count)
    WHERE violation_count > 0;
CREATE INDEX idx_critique_revised ON fhq_research.self_critique_records(was_revised)
    WHERE was_revised = TRUE;

-- ============================================================================
-- FUNCTION: Calculate DINCO normalized score
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.calculate_dinco_score(
    p_primary_score NUMERIC,
    p_distractor_scores JSONB
)
RETURNS NUMERIC AS $$
DECLARE
    v_total_sum NUMERIC := p_primary_score;
    v_distractor_score NUMERIC;
BEGIN
    -- Sum all distractor scores
    FOR v_distractor_score IN SELECT (value::NUMERIC) FROM jsonb_array_elements_text(p_distractor_scores)
    LOOP
        v_total_sum := v_total_sum + v_distractor_score;
    END LOOP;

    -- Return normalized score
    IF v_total_sum > 0 THEN
        RETURN ROUND(p_primary_score / v_total_sum, 4);
    ELSE
        RETURN 0;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION: Determine action based on DINCO score
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.get_dinco_action(
    p_normalized_score NUMERIC,
    p_threshold NUMERIC DEFAULT 0.90
)
RETURNS TEXT AS $$
BEGIN
    IF p_normalized_score >= p_threshold THEN
        RETURN 'ACCEPTED';
    ELSIF p_normalized_score >= 0.70 THEN
        RETURN 'DEEPER_RESEARCH';
    ELSIF p_normalized_score >= 0.50 THEN
        RETURN 'REVISED';
    ELSE
        RETURN 'HUMAN_REVIEW';
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION: Update batch calibration metrics
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.update_calibration_metrics(
    p_batch_id TEXT
)
RETURNS VOID AS $$
DECLARE
    v_metrics RECORD;
BEGIN
    -- Calculate aggregated metrics
    SELECT
        COUNT(*) as total,
        AVG(dinco_normalized_score) as avg_score,
        MIN(dinco_normalized_score) as min_score,
        MAX(dinco_normalized_score) as max_score,
        STDDEV(dinco_normalized_score) as stddev_score,
        COUNT(*) FILTER (WHERE action_taken = 'ACCEPTED') as accepted,
        COUNT(*) FILTER (WHERE action_taken = 'DEEPER_RESEARCH') as deeper,
        COUNT(*) FILTER (WHERE action_taken = 'HUMAN_REVIEW') as human,
        COUNT(*) FILTER (WHERE action_taken = 'REVISED') as revised
    INTO v_metrics
    FROM fhq_research.dinco_calibration_log
    WHERE batch_id = p_batch_id;

    -- Update or insert metrics record
    INSERT INTO fhq_research.dinco_calibration_metrics (
        batch_id,
        batch_start_run,
        batch_end_run,
        total_hypotheses,
        avg_normalized_score,
        min_normalized_score,
        max_normalized_score,
        stddev_normalized_score,
        accepted_count,
        deeper_research_count,
        human_review_count,
        revised_count,
        updated_at
    ) VALUES (
        p_batch_id,
        101,  -- Batch 2 starts at 101
        200,  -- Batch 2 ends at 200
        v_metrics.total,
        v_metrics.avg_score,
        v_metrics.min_score,
        v_metrics.max_score,
        v_metrics.stddev_score,
        v_metrics.accepted,
        v_metrics.deeper,
        v_metrics.human,
        v_metrics.revised,
        NOW()
    )
    ON CONFLICT (batch_id) DO UPDATE SET
        total_hypotheses = EXCLUDED.total_hypotheses,
        avg_normalized_score = EXCLUDED.avg_normalized_score,
        min_normalized_score = EXCLUDED.min_normalized_score,
        max_normalized_score = EXCLUDED.max_normalized_score,
        stddev_normalized_score = EXCLUDED.stddev_normalized_score,
        accepted_count = EXCLUDED.accepted_count,
        deeper_research_count = EXCLUDED.deeper_research_count,
        human_review_count = EXCLUDED.human_review_count,
        revised_count = EXCLUDED.revised_count,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VIEW: DINCO Calibration Summary
-- ============================================================================

CREATE OR REPLACE VIEW fhq_research.v_dinco_calibration_summary AS
SELECT
    batch_id,
    COUNT(*) as total_hypotheses,
    ROUND(AVG(dinco_normalized_score), 4) as avg_dinco_score,
    COUNT(*) FILTER (WHERE is_confident) as confident_count,
    COUNT(*) FILTER (WHERE NOT is_confident) as uncertain_count,
    ROUND(
        COUNT(*) FILTER (WHERE is_confident)::NUMERIC / NULLIF(COUNT(*), 0),
        4
    ) as confidence_rate,
    COUNT(*) FILTER (WHERE action_taken = 'ACCEPTED') as accepted,
    COUNT(*) FILTER (WHERE action_taken = 'DEEPER_RESEARCH') as deeper_research,
    COUNT(*) FILTER (WHERE action_taken = 'HUMAN_REVIEW') as human_review,
    COUNT(*) FILTER (WHERE action_taken = 'REVISED') as revised
FROM fhq_research.dinco_calibration_log
GROUP BY batch_id
ORDER BY batch_id;

-- ============================================================================
-- VIEW: Self-Critique Effectiveness
-- ============================================================================

CREATE OR REPLACE VIEW fhq_research.v_self_critique_effectiveness AS
SELECT
    batch_id,
    COUNT(*) as total_critiques,
    COUNT(*) FILTER (WHERE violation_count > 0) as with_violations,
    COUNT(*) FILTER (WHERE was_revised) as revised,
    ROUND(AVG(violation_count), 2) as avg_violations,
    ROUND(AVG(quality_improvement) FILTER (WHERE was_revised), 4) as avg_quality_improvement
FROM fhq_research.self_critique_records
GROUP BY batch_id
ORDER BY batch_id;

-- ============================================================================
-- APPEND-ONLY ENFORCEMENT (Per CEO-DIR-2026-FINN-006)
-- ============================================================================

-- DINCO calibration log - append only
DROP TRIGGER IF EXISTS trg_append_only_dinco ON fhq_research.dinco_calibration_log;
CREATE TRIGGER trg_append_only_dinco
    BEFORE UPDATE OR DELETE ON fhq_research.dinco_calibration_log
    FOR EACH ROW
    EXECUTE FUNCTION fhq_research.enforce_append_only();

-- Self-critique records - append only
DROP TRIGGER IF EXISTS trg_append_only_critique ON fhq_research.self_critique_records;
CREATE TRIGGER trg_append_only_critique
    BEFORE UPDATE OR DELETE ON fhq_research.self_critique_records
    FOR EACH ROW
    EXECUTE FUNCTION fhq_research.enforce_append_only();

-- ============================================================================
-- AUDIT: Log migration
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'MIGRATION_EXECUTE',
    '182_finn007_dinco_confidence_calibration',
    'DATABASE_MIGRATION',
    'STIG',
    'APPROVED',
    'CEO-DIR-2026-FINN-007 Section 3.3: DINCO Confidence Calibration Protocol',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-FINN-007',
        'section', '3.3 DINCO Confidence Calibration',
        'tables', ARRAY['dinco_calibration_log', 'dinco_calibration_metrics', 'self_critique_records'],
        'research_basis', 'DINCO (2025), Constitutional AI (SL-CAI, RLAIF)',
        'purpose', 'Address over-confidence and suggestibility bias through distractor-normalized calibration'
    )
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'fhq_research'
        AND table_name = 'dinco_calibration_log'
    ) THEN
        RAISE EXCEPTION 'Migration 182 FAILED: dinco_calibration_log not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'fhq_research'
        AND table_name = 'self_critique_records'
    ) THEN
        RAISE EXCEPTION 'Migration 182 FAILED: self_critique_records not created';
    END IF;

    RAISE NOTICE 'Migration 182 SUCCESS: DINCO calibration infrastructure created';
    RAISE NOTICE 'CEO-DIR-2026-FINN-007: Confidence calibration with ECE < 5%% target';
END $$;
