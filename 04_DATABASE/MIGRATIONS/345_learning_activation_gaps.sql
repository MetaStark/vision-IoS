-- ============================================================================
-- Migration 345: Learning Activation Gap Resolution
-- ============================================================================
-- Directive: CEO-DIR-2026-LEARNING-ACTIVATION-001 Amendment A
-- Purpose: Close gaps blocking dynamic scaling and mechanical escalation
-- Executed by: STIG (EC-003)
-- Date: 2026-01-24
-- ============================================================================

-- ============================================================================
-- GAP 1: Duplicate Hypothesis Detection (semantic_hash)
-- ============================================================================
-- Requirement: No duplicate hypothesis embeddings > similarity threshold
-- Impact: N capped at 3 until resolved
-- ============================================================================

-- Add semantic_hash column to hypothesis_canon
ALTER TABLE fhq_learning.hypothesis_canon
ADD COLUMN IF NOT EXISTS semantic_hash TEXT;

-- Add error_frequency_percentile for error prioritization
ALTER TABLE fhq_learning.hypothesis_canon
ADD COLUMN IF NOT EXISTS error_frequency_percentile NUMERIC(5,2);

-- Add index for fast duplicate lookup
CREATE INDEX IF NOT EXISTS idx_hypothesis_semantic_hash
ON fhq_learning.hypothesis_canon(semantic_hash)
WHERE semantic_hash IS NOT NULL;

-- Function to compute semantic hash from hypothesis content
CREATE OR REPLACE FUNCTION fhq_learning.compute_hypothesis_hash(
    p_origin_rationale TEXT,
    p_causal_mechanism TEXT,
    p_expected_direction TEXT,
    p_event_type_codes TEXT[]
) RETURNS TEXT AS $$
DECLARE
    v_content TEXT;
    v_hash TEXT;
BEGIN
    -- Concatenate key semantic fields
    v_content := COALESCE(p_origin_rationale, '') || '|' ||
                 COALESCE(p_causal_mechanism, '') || '|' ||
                 COALESCE(p_expected_direction, '') || '|' ||
                 COALESCE(array_to_string(p_event_type_codes, ','), '');

    -- Compute MD5 hash (sufficient for duplicate detection)
    v_hash := md5(lower(trim(v_content)));

    RETURN v_hash;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to check for duplicate hypothesis before insertion
CREATE OR REPLACE FUNCTION fhq_learning.check_hypothesis_duplicate(
    p_origin_rationale TEXT,
    p_causal_mechanism TEXT,
    p_expected_direction TEXT,
    p_event_type_codes TEXT[],
    p_similarity_threshold NUMERIC DEFAULT 1.0  -- 1.0 = exact match only
) RETURNS TABLE (
    is_duplicate BOOLEAN,
    matching_hypothesis_code TEXT,
    matching_status TEXT,
    recommendation TEXT
) AS $$
DECLARE
    v_hash TEXT;
    v_match RECORD;
BEGIN
    -- Compute hash for proposed hypothesis
    v_hash := fhq_learning.compute_hypothesis_hash(
        p_origin_rationale, p_causal_mechanism, p_expected_direction, p_event_type_codes
    );

    -- Check for exact match
    SELECT h.hypothesis_code, h.status
    INTO v_match
    FROM fhq_learning.hypothesis_canon h
    WHERE h.semantic_hash = v_hash
    LIMIT 1;

    IF v_match IS NOT NULL THEN
        RETURN QUERY SELECT
            TRUE,
            v_match.hypothesis_code,
            v_match.status,
            CASE
                WHEN v_match.status = 'FALSIFIED' THEN 'BLOCK: Structurally identical hypothesis was falsified'
                WHEN v_match.status = 'WEAKENED' THEN 'WARN: Similar hypothesis exists in weakened state'
                ELSE 'WARN: Duplicate hypothesis exists'
            END;
    ELSE
        RETURN QUERY SELECT FALSE, NULL::TEXT, NULL::TEXT, 'OK: No duplicate found';
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-compute semantic_hash on insert/update
CREATE OR REPLACE FUNCTION fhq_learning.trg_compute_semantic_hash()
RETURNS TRIGGER AS $$
BEGIN
    NEW.semantic_hash := fhq_learning.compute_hypothesis_hash(
        NEW.origin_rationale,
        NEW.causal_mechanism,
        NEW.expected_direction,
        NEW.event_type_codes
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_hypothesis_semantic_hash ON fhq_learning.hypothesis_canon;
CREATE TRIGGER trg_hypothesis_semantic_hash
BEFORE INSERT OR UPDATE ON fhq_learning.hypothesis_canon
FOR EACH ROW EXECUTE FUNCTION fhq_learning.trg_compute_semantic_hash();

-- Backfill semantic_hash for existing hypotheses
UPDATE fhq_learning.hypothesis_canon
SET semantic_hash = fhq_learning.compute_hypothesis_hash(
    origin_rationale,
    causal_mechanism,
    expected_direction,
    event_type_codes
)
WHERE semantic_hash IS NULL;

-- ============================================================================
-- GAP 2: Mechanical Escalation Function
-- ============================================================================
-- Requirement: No human interpretation layer in escalation
-- Triggers: HYPO_STALL, EXP_STALL, DEATH_TOO_SOFT, DEATH_TOO_BRUTAL
-- ============================================================================

-- Create escalation log table
CREATE TABLE IF NOT EXISTS fhq_learning.learning_escalation_log (
    escalation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trigger_code TEXT NOT NULL,
    trigger_condition TEXT NOT NULL,
    trigger_value NUMERIC,
    threshold_value NUMERIC,
    escalation_ts TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    calendar_event_id UUID,
    runbook_entry_id UUID,
    ceo_action_required BOOLEAN DEFAULT TRUE,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    acknowledged_by TEXT,
    override_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for quick lookup
CREATE INDEX IF NOT EXISTS idx_escalation_unacknowledged
ON fhq_learning.learning_escalation_log(ceo_action_required, acknowledged_at)
WHERE ceo_action_required = TRUE AND acknowledged_at IS NULL;

-- Main mechanical escalation check function
CREATE OR REPLACE FUNCTION fhq_learning.check_learning_escalation()
RETURNS TABLE (
    trigger_code TEXT,
    trigger_condition TEXT,
    current_value NUMERIC,
    threshold_value NUMERIC,
    triggered BOOLEAN,
    escalation_required BOOLEAN
) AS $$
DECLARE
    v_last_hypothesis_ts TIMESTAMP WITH TIME ZONE;
    v_last_experiment_ts TIMESTAMP WITH TIME ZONE;
    v_tier1_death_rate NUMERIC;
    v_hours_since_hypothesis NUMERIC;
    v_hours_since_experiment NUMERIC;
BEGIN
    -- Get last hypothesis timestamp
    SELECT MAX(created_at) INTO v_last_hypothesis_ts
    FROM fhq_learning.hypothesis_canon;

    -- Get last experiment completion timestamp
    SELECT MAX(completed_at) INTO v_last_experiment_ts
    FROM fhq_learning.experiment_registry
    WHERE status = 'COMPLETED';

    -- Calculate Tier-1 death rate over rolling 48h
    SELECT
        CASE
            WHEN COUNT(*) = 0 THEN NULL
            ELSE 100.0 * COUNT(*) FILTER (WHERE result IN ('FALSIFIED', 'WEAKENED')) / COUNT(*)
        END INTO v_tier1_death_rate
    FROM fhq_learning.experiment_registry
    WHERE experiment_tier = 1
      AND completed_at >= NOW() - INTERVAL '48 hours';

    -- Calculate hours since last activity
    v_hours_since_hypothesis := EXTRACT(EPOCH FROM (NOW() - COALESCE(v_last_hypothesis_ts, NOW() - INTERVAL '999 hours'))) / 3600;
    v_hours_since_experiment := EXTRACT(EPOCH FROM (NOW() - COALESCE(v_last_experiment_ts, NOW() - INTERVAL '999 hours'))) / 3600;

    -- TRIGGER 1: HYPO_STALL - No new hypothesis in 24h
    RETURN QUERY SELECT
        'HYPO_STALL'::TEXT,
        'No new hypothesis in 24h'::TEXT,
        v_hours_since_hypothesis,
        24.0::NUMERIC,
        v_hours_since_hypothesis > 24,
        v_hours_since_hypothesis > 24;

    -- TRIGGER 2: EXP_STALL - No experiment completed in 24h
    RETURN QUERY SELECT
        'EXP_STALL'::TEXT,
        'No experiment completed in 24h'::TEXT,
        v_hours_since_experiment,
        24.0::NUMERIC,
        v_hours_since_experiment > 24,
        v_hours_since_experiment > 24;

    -- TRIGGER 3: DEATH_TOO_SOFT - Tier-1 death rate <50% over rolling 48h
    RETURN QUERY SELECT
        'DEATH_TOO_SOFT'::TEXT,
        'Tier-1 death rate <50% over rolling 48h'::TEXT,
        COALESCE(v_tier1_death_rate, 0),
        50.0::NUMERIC,
        COALESCE(v_tier1_death_rate, 0) < 50 AND v_tier1_death_rate IS NOT NULL,
        COALESCE(v_tier1_death_rate, 0) < 50 AND v_tier1_death_rate IS NOT NULL;

    -- TRIGGER 4: DEATH_TOO_BRUTAL - Tier-1 death rate >95% over rolling 48h
    RETURN QUERY SELECT
        'DEATH_TOO_BRUTAL'::TEXT,
        'Tier-1 death rate >95% over rolling 48h'::TEXT,
        COALESCE(v_tier1_death_rate, 100),
        95.0::NUMERIC,
        COALESCE(v_tier1_death_rate, 100) > 95,
        COALESCE(v_tier1_death_rate, 100) > 95;
END;
$$ LANGUAGE plpgsql;

-- Function to execute escalation (create calendar event + runbook entry)
CREATE OR REPLACE FUNCTION fhq_learning.execute_learning_escalation()
RETURNS TABLE (
    escalation_id UUID,
    trigger_code TEXT,
    calendar_event_created BOOLEAN,
    runbook_entry_created BOOLEAN
) AS $$
DECLARE
    v_trigger RECORD;
    v_escalation_id UUID;
    v_calendar_event_id UUID;
    v_runbook_entry_id UUID;
BEGIN
    -- Check all triggers
    FOR v_trigger IN SELECT * FROM fhq_learning.check_learning_escalation() WHERE escalation_required = TRUE
    LOOP
        -- Check if already escalated and unacknowledged
        IF EXISTS (
            SELECT 1 FROM fhq_learning.learning_escalation_log
            WHERE trigger_code = v_trigger.trigger_code
              AND ceo_action_required = TRUE
              AND acknowledged_at IS NULL
              AND escalation_ts >= NOW() - INTERVAL '24 hours'
        ) THEN
            -- Skip - already escalated
            CONTINUE;
        END IF;

        -- Generate IDs
        v_escalation_id := gen_random_uuid();
        v_calendar_event_id := gen_random_uuid();
        v_runbook_entry_id := gen_random_uuid();

        -- Create CEO calendar alert
        INSERT INTO fhq_calendar.ceo_calendar_alerts (
            alert_id,
            alert_type,
            alert_priority,
            alert_title,
            alert_description,
            decision_required,
            decision_options,
            ceo_action_required,
            created_at
        ) VALUES (
            v_calendar_event_id,
            'LEARNING_ESCALATION',
            CASE
                WHEN v_trigger.trigger_code IN ('HYPO_STALL', 'EXP_STALL') THEN 'CRITICAL'
                ELSE 'HIGH'
            END,
            'Learning Escalation: ' || v_trigger.trigger_code,
            v_trigger.trigger_condition || ' (Current: ' || ROUND(v_trigger.current_value, 2) || ', Threshold: ' || v_trigger.threshold_value || ')',
            TRUE,
            ARRAY['ACKNOWLEDGE', 'OVERRIDE', 'INVESTIGATE'],
            TRUE,
            NOW()
        );

        -- Create runbook entry
        INSERT INTO fhq_calendar.test_runbook_entries (
            entry_id,
            entry_date,
            runbook_file_path,
            entry_content,
            db_verified,
            created_at
        ) VALUES (
            v_runbook_entry_id,
            CURRENT_DATE,
            'C:\fhq-market-system\vision-ios\12_DAILY_REPORTS\DAY' ||
                EXTRACT(DOY FROM CURRENT_DATE)::TEXT || '_RUNBOOK_' ||
                TO_CHAR(CURRENT_DATE, 'YYYYMMDD') || '.md',
            jsonb_build_object(
                'escalation_type', 'LEARNING_ESCALATION',
                'trigger_code', v_trigger.trigger_code,
                'trigger_condition', v_trigger.trigger_condition,
                'current_value', v_trigger.current_value,
                'threshold_value', v_trigger.threshold_value,
                'escalation_ts', NOW(),
                'ceo_action_required', TRUE
            ),
            TRUE,
            NOW()
        );

        -- Log escalation
        INSERT INTO fhq_learning.learning_escalation_log (
            escalation_id,
            trigger_code,
            trigger_condition,
            trigger_value,
            threshold_value,
            calendar_event_id,
            runbook_entry_id,
            ceo_action_required
        ) VALUES (
            v_escalation_id,
            v_trigger.trigger_code,
            v_trigger.trigger_condition,
            v_trigger.current_value,
            v_trigger.threshold_value,
            v_calendar_event_id,
            v_runbook_entry_id,
            TRUE
        );

        RETURN QUERY SELECT
            v_escalation_id,
            v_trigger.trigger_code,
            TRUE,
            TRUE;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Function for CEO to acknowledge escalation
CREATE OR REPLACE FUNCTION fhq_learning.acknowledge_escalation(
    p_escalation_id UUID,
    p_acknowledged_by TEXT,
    p_override_reason TEXT DEFAULT NULL
) RETURNS BOOLEAN AS $$
BEGIN
    UPDATE fhq_learning.learning_escalation_log
    SET acknowledged_at = NOW(),
        acknowledged_by = p_acknowledged_by,
        override_reason = p_override_reason,
        ceo_action_required = FALSE
    WHERE escalation_id = p_escalation_id
      AND acknowledged_at IS NULL;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- GAP 3: Learning Throughput Monitoring View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_learning.v_learning_throughput_status AS
WITH daily_stats AS (
    SELECT
        CURRENT_DATE as check_date,
        (SELECT COUNT(*) FROM fhq_learning.hypothesis_canon
         WHERE created_at >= CURRENT_DATE) as hypotheses_today,
        (SELECT COUNT(*) FROM fhq_learning.experiment_registry
         WHERE created_at >= CURRENT_DATE) as experiments_today,
        (SELECT COUNT(*) FROM fhq_learning.hypothesis_canon
         WHERE created_at >= NOW() - INTERVAL '24 hours') as hypotheses_24h,
        (SELECT COUNT(*) FROM fhq_learning.experiment_registry
         WHERE completed_at >= NOW() - INTERVAL '24 hours') as experiments_24h
),
thresholds AS (
    SELECT
        3 as min_hypotheses,
        3 as min_experiments,
        100.0 as min_error_coverage
)
SELECT
    d.check_date,
    d.hypotheses_today,
    d.hypotheses_24h,
    t.min_hypotheses,
    CASE WHEN d.hypotheses_24h >= t.min_hypotheses THEN 'PASS' ELSE 'FAIL' END as hypothesis_status,
    d.experiments_today,
    d.experiments_24h,
    t.min_experiments,
    CASE WHEN d.experiments_24h >= t.min_experiments THEN 'PASS' ELSE 'FAIL' END as experiment_status,
    CASE
        WHEN d.hypotheses_24h >= t.min_hypotheses AND d.experiments_24h >= t.min_experiments
        THEN 'LEARNING_ACTIVE'
        ELSE 'LEARNING_STALLED'
    END as overall_status
FROM daily_stats d
CROSS JOIN thresholds t;

-- ============================================================================
-- GAP 4: Dynamic Scaling Authorization View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_learning.v_dynamic_scaling_authorization AS
WITH metrics AS (
    SELECT
        -- Tier-1 death rate over 48h
        (SELECT
            CASE WHEN COUNT(*) = 0 THEN NULL
            ELSE 100.0 * COUNT(*) FILTER (WHERE result IN ('FALSIFIED', 'WEAKENED')) / COUNT(*)
            END
         FROM fhq_learning.experiment_registry
         WHERE experiment_tier = 1 AND completed_at >= NOW() - INTERVAL '48 hours'
        ) as tier1_death_rate,

        -- Check for duplicate hashes (simplified p-hacking check)
        (SELECT COUNT(*)
         FROM (
             SELECT semantic_hash, COUNT(*) as cnt
             FROM fhq_learning.hypothesis_canon
             WHERE semantic_hash IS NOT NULL
             GROUP BY semantic_hash
             HAVING COUNT(*) > 1
         ) dups
        ) as duplicate_hypothesis_count,

        -- Phase 0 end timestamp
        '2026-01-27 18:00:00+01'::TIMESTAMP WITH TIME ZONE as phase_0_end
)
SELECT
    m.tier1_death_rate,
    CASE
        WHEN m.tier1_death_rate BETWEEN 60 AND 90 THEN TRUE
        ELSE FALSE
    END as death_rate_in_range,
    m.duplicate_hypothesis_count,
    CASE WHEN m.duplicate_hypothesis_count = 0 THEN TRUE ELSE FALSE END as no_duplicates,
    m.phase_0_end,
    CASE WHEN NOW() > m.phase_0_end THEN TRUE ELSE FALSE END as phase_0_complete,
    CASE
        WHEN NOW() > m.phase_0_end
             AND m.tier1_death_rate BETWEEN 60 AND 90
             AND m.duplicate_hypothesis_count = 0
        THEN TRUE
        ELSE FALSE
    END as scaling_authorized,
    CASE
        WHEN NOW() <= m.phase_0_end THEN 'Phase 0 active until ' || m.phase_0_end::TEXT
        WHEN m.tier1_death_rate IS NULL THEN 'No experiments in 48h window'
        WHEN m.tier1_death_rate < 60 THEN 'Death rate too low: ' || ROUND(m.tier1_death_rate, 1) || '% (need 60-90%)'
        WHEN m.tier1_death_rate > 90 THEN 'Death rate too high: ' || ROUND(m.tier1_death_rate, 1) || '% (need 60-90%)'
        WHEN m.duplicate_hypothesis_count > 0 THEN 'Duplicate hypotheses detected: ' || m.duplicate_hypothesis_count
        ELSE 'All conditions met - scaling authorized'
    END as blocking_reason
FROM metrics m;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify semantic_hash column exists and is populated
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM fhq_learning.hypothesis_canon
    WHERE semantic_hash IS NOT NULL;

    RAISE NOTICE 'Semantic hash populated for % hypotheses', v_count;
END $$;

-- Verify escalation function works
DO $$
DECLARE
    v_result RECORD;
BEGIN
    FOR v_result IN SELECT * FROM fhq_learning.check_learning_escalation()
    LOOP
        RAISE NOTICE 'Trigger: %, Condition: %, Value: %, Threshold: %, Triggered: %',
            v_result.trigger_code,
            v_result.trigger_condition,
            v_result.current_value,
            v_result.threshold_value,
            v_result.triggered;
    END LOOP;
END $$;

-- Verify throughput status
DO $$
DECLARE
    v_status RECORD;
BEGIN
    SELECT * INTO v_status FROM fhq_learning.v_learning_throughput_status;
    RAISE NOTICE 'Learning Status: %, Hypotheses 24h: %, Experiments 24h: %',
        v_status.overall_status,
        v_status.hypotheses_24h,
        v_status.experiments_24h;
END $$;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
-- Gaps Closed:
-- 1. semantic_hash column + duplicate detection function
-- 2. check_learning_escalation() mechanical function
-- 3. execute_learning_escalation() with calendar + runbook integration
-- 4. v_learning_throughput_status monitoring view
-- 5. v_dynamic_scaling_authorization for Phase 0 -> Dynamic transition
-- ============================================================================
