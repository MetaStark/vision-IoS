-- =============================================================================
-- WAVE 17C + 17C.1 - AUTONOMOUS PROMOTION PIPELINE WITH ENTERPRISE SAFEGUARDS
-- =============================================================================
-- Migration: 156_wave17c_autonomous_promotion_pipeline.sql
-- Date: 2025-12-19
-- References: ADR-004, ADR-012, ADR-013, WAVE 17C, WAVE 17C.1

BEGIN;

-- =============================================================================
-- 1. PIPELINE CONFIGURATION TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS fhq_canonical.g5_promotion_config (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Rate Limiting (Section 2.1)
    max_promotions_per_hour INTEGER DEFAULT 50,
    rate_limit_enabled BOOLEAN DEFAULT TRUE,

    -- Shadow Mode (Section 3)
    shadow_mode_enabled BOOLEAN DEFAULT TRUE,
    shadow_mode_until TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '24 hours'),
    shadow_review_count INTEGER DEFAULT 0,
    shadow_review_required INTEGER DEFAULT 50,

    -- Ramp-Up (Section 3.3)
    ramp_up_percentage INTEGER DEFAULT 10,
    ramp_up_stage INTEGER DEFAULT 1,

    -- Drift Thresholds (Section 4)
    min_rolling_7day_eqs NUMERIC(5,3) DEFAULT 0.85,
    min_conversion_rate NUMERIC(5,3) DEFAULT 0.05,

    -- SLA Limits in milliseconds (Section 5)
    sla_evidence_gen_ms INTEGER DEFAULT 5000,
    sla_gate_a_eval_ms INTEGER DEFAULT 1000,
    sla_end_to_end_ms INTEGER DEFAULT 30000,

    -- Rollback Window (Section 6)
    rollback_window_hours INTEGER DEFAULT 24,

    -- Pass-Rate Anomaly Detection (Section 2.2)
    pass_rate_change_threshold NUMERIC(5,2) DEFAULT 20.0,
    pass_rate_window_minutes INTEGER DEFAULT 60,

    -- Pipeline State
    pipeline_state TEXT DEFAULT 'SHADOW' CHECK (pipeline_state IN ('SHADOW', 'RAMP_10', 'RAMP_50', 'ACTIVE', 'PAUSED', 'HALTED')),
    paused_at TIMESTAMPTZ,
    paused_reason TEXT,

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default config if not exists
INSERT INTO fhq_canonical.g5_promotion_config (is_active)
SELECT TRUE WHERE NOT EXISTS (SELECT 1 FROM fhq_canonical.g5_promotion_config WHERE is_active = TRUE);

-- =============================================================================
-- 2. RATE LIMITING TRACKING
-- =============================================================================
CREATE TABLE IF NOT EXISTS fhq_canonical.g5_promotion_rate_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hour_bucket TIMESTAMPTZ NOT NULL,
    promotions_count INTEGER DEFAULT 0,
    promotions_allowed INTEGER DEFAULT 0,
    promotions_blocked INTEGER DEFAULT 0,
    rate_limit_triggered BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_rate_log_hour UNIQUE (hour_bucket)
);

CREATE INDEX IF NOT EXISTS idx_rate_log_hour ON fhq_canonical.g5_promotion_rate_log(hour_bucket);

-- =============================================================================
-- 3. SHADOW MODE DECISIONS (Section 3.1)
-- =============================================================================
CREATE TABLE IF NOT EXISTS fhq_canonical.g5_shadow_decisions (
    shadow_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    needle_id UUID NOT NULL REFERENCES fhq_canonical.golden_needles(needle_id),

    -- What would have happened
    would_pass_gate_a BOOLEAN,
    would_pass_gate_b BOOLEAN,
    would_create_signal BOOLEAN,
    would_be_signal_state TEXT,

    -- Actual evaluation results
    gate_a_result JSONB,
    gate_b_result JSONB,

    -- Evidence linkage
    vega_attestation_id UUID,
    evidence_pack_path TEXT,

    -- Timing
    evidence_gen_ms INTEGER,
    gate_a_eval_ms INTEGER,
    total_ms INTEGER,

    -- Post-hoc review
    reviewed BOOLEAN DEFAULT FALSE,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- 4. SLA TRACKING (Section 5)
-- =============================================================================
CREATE TABLE IF NOT EXISTS fhq_canonical.g5_sla_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    needle_id UUID REFERENCES fhq_canonical.golden_needles(needle_id),
    promotion_id UUID REFERENCES fhq_canonical.g5_promotion_ledger(promotion_id),

    -- Timing measurements
    evidence_gen_start TIMESTAMPTZ,
    evidence_gen_end TIMESTAMPTZ,
    evidence_gen_ms INTEGER,
    evidence_gen_sla_breach BOOLEAN DEFAULT FALSE,

    gate_a_start TIMESTAMPTZ,
    gate_a_end TIMESTAMPTZ,
    gate_a_ms INTEGER,
    gate_a_sla_breach BOOLEAN DEFAULT FALSE,

    total_start TIMESTAMPTZ,
    total_end TIMESTAMPTZ,
    total_ms INTEGER,
    total_sla_breach BOOLEAN DEFAULT FALSE,

    any_breach BOOLEAN GENERATED ALWAYS AS (
        evidence_gen_sla_breach OR gate_a_sla_breach OR total_sla_breach
    ) STORED,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- 5. DRIFT DETECTION METRICS (Section 4)
-- =============================================================================
CREATE TABLE IF NOT EXISTS fhq_canonical.g5_drift_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    computed_at TIMESTAMPTZ DEFAULT NOW(),

    -- Rolling 7-day metrics
    rolling_7day_avg_eqs NUMERIC(5,3),
    rolling_7day_needle_count INTEGER,
    rolling_7day_signal_count INTEGER,
    rolling_7day_conversion_rate NUMERIC(5,3),

    -- Thresholds from config
    eqs_threshold NUMERIC(5,3),
    conversion_threshold NUMERIC(5,3),

    -- Breach flags
    eqs_below_threshold BOOLEAN DEFAULT FALSE,
    conversion_below_threshold BOOLEAN DEFAULT FALSE,
    any_drift_detected BOOLEAN GENERATED ALWAYS AS (
        eqs_below_threshold OR conversion_below_threshold
    ) STORED,

    -- Actions taken
    alert_sent BOOLEAN DEFAULT FALSE,
    throttling_triggered BOOLEAN DEFAULT FALSE
);

-- =============================================================================
-- 6. PASS-RATE ANOMALY TRACKING (Section 2.2)
-- =============================================================================
CREATE TABLE IF NOT EXISTS fhq_canonical.g5_pass_rate_history (
    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,

    total_evaluated INTEGER DEFAULT 0,
    total_passed INTEGER DEFAULT 0,
    pass_rate NUMERIC(5,2),

    previous_pass_rate NUMERIC(5,2),
    pass_rate_delta NUMERIC(5,2),
    anomaly_detected BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- 7. ADD COLUMNS TO PROMOTION LEDGER FOR ROLLBACK (Section 6)
-- =============================================================================
ALTER TABLE fhq_canonical.g5_promotion_ledger
    ADD COLUMN IF NOT EXISTS is_rolled_back BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS rolled_back_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS rolled_back_by TEXT,
    ADD COLUMN IF NOT EXISTS rollback_reason TEXT,
    ADD COLUMN IF NOT EXISTS rollback_ceo_approval TEXT,
    ADD COLUMN IF NOT EXISTS rollback_vega_cosign TEXT;

-- =============================================================================
-- 8. ADD COLUMNS FOR CROSS-VERIFICATION (Section 7)
-- =============================================================================
ALTER TABLE fhq_canonical.g5_promotion_ledger
    ADD COLUMN IF NOT EXISTS evidence_hash_verified TEXT,
    ADD COLUMN IF NOT EXISTS needle_lineage_hash TEXT,
    ADD COLUMN IF NOT EXISTS cross_verification_passed BOOLEAN,
    ADD COLUMN IF NOT EXISTS cross_verification_mismatch_reason TEXT;

-- =============================================================================
-- 9. ADD VEGA ATTESTATION COLUMNS TO GOLDEN NEEDLES
-- =============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'fhq_canonical'
                   AND table_name = 'golden_needles'
                   AND column_name = 'vega_attestation_id') THEN
        ALTER TABLE fhq_canonical.golden_needles ADD COLUMN vega_attestation_id UUID;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'fhq_canonical'
                   AND table_name = 'golden_needles'
                   AND column_name = 'evidence_pack_path') THEN
        ALTER TABLE fhq_canonical.golden_needles ADD COLUMN evidence_pack_path TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'fhq_canonical'
                   AND table_name = 'golden_needles'
                   AND column_name = 'evidence_generated_at') THEN
        ALTER TABLE fhq_canonical.golden_needles ADD COLUMN evidence_generated_at TIMESTAMPTZ;
    END IF;
END $$;

-- =============================================================================
-- 10. PIPELINE EVENTS LOG
-- =============================================================================
CREATE TABLE IF NOT EXISTS fhq_canonical.g5_pipeline_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL CHECK (event_type IN (
        'NEEDLE_INGESTED', 'EVIDENCE_GENERATED', 'GATE_A_EVALUATED',
        'GATE_B_EVALUATED', 'SIGNAL_CREATED', 'RATE_LIMIT_HIT',
        'SHADOW_DECISION', 'SLA_BREACH', 'PASS_RATE_ANOMALY',
        'DRIFT_DETECTED', 'PIPELINE_PAUSED', 'PIPELINE_RESUMED',
        'ROLLBACK_INITIATED', 'ROLLBACK_COMPLETED', 'RAMP_UP_ADVANCED',
        'CROSS_VERIFY_FAILED'
    )),
    needle_id UUID,
    promotion_id UUID,
    signal_id UUID,

    event_data JSONB,
    severity TEXT DEFAULT 'INFO' CHECK (severity IN ('DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')),

    defcon_escalation BOOLEAN DEFAULT FALSE,
    defcon_level_set INTEGER,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_events_type ON fhq_canonical.g5_pipeline_events(event_type);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_time ON fhq_canonical.g5_pipeline_events(created_at DESC);

-- =============================================================================
-- 11. VIEW: PIPELINE STATUS DASHBOARD
-- =============================================================================
CREATE OR REPLACE VIEW fhq_canonical.v_pipeline_status AS
SELECT
    pc.pipeline_state,
    pc.shadow_mode_enabled,
    pc.shadow_mode_until,
    pc.shadow_review_count,
    pc.shadow_review_required,
    pc.ramp_up_percentage,
    pc.ramp_up_stage,
    pc.max_promotions_per_hour,
    pc.rate_limit_enabled,
    pc.paused_at,
    pc.paused_reason,

    COALESCE((
        SELECT promotions_count
        FROM fhq_canonical.g5_promotion_rate_log
        WHERE hour_bucket = date_trunc('hour', NOW())
        ORDER BY created_at DESC LIMIT 1
    ), 0) as current_hour_promotions,

    (SELECT rolling_7day_avg_eqs FROM fhq_canonical.g5_drift_metrics ORDER BY computed_at DESC LIMIT 1) as latest_avg_eqs,
    (SELECT rolling_7day_conversion_rate FROM fhq_canonical.g5_drift_metrics ORDER BY computed_at DESC LIMIT 1) as latest_conversion_rate,
    (SELECT any_drift_detected FROM fhq_canonical.g5_drift_metrics ORDER BY computed_at DESC LIMIT 1) as drift_detected,

    (SELECT COUNT(*) FROM fhq_canonical.g5_sla_metrics WHERE any_breach = TRUE AND created_at > NOW() - INTERVAL '24 hours') as sla_breaches_24h,

    (SELECT COUNT(*) FROM fhq_canonical.g5_shadow_decisions WHERE reviewed = FALSE) as shadow_pending_review,

    pc.updated_at as config_updated_at
FROM fhq_canonical.g5_promotion_config pc
WHERE pc.is_active = TRUE;

-- =============================================================================
-- 12. FUNCTION: CHECK RATE LIMIT
-- =============================================================================
CREATE OR REPLACE FUNCTION fhq_canonical.check_promotion_rate_limit()
RETURNS BOOLEAN AS $$
DECLARE
    v_config RECORD;
    v_current_count INTEGER;
    v_hour_bucket TIMESTAMPTZ;
BEGIN
    SELECT * INTO v_config FROM fhq_canonical.g5_promotion_config WHERE is_active = TRUE LIMIT 1;

    IF NOT v_config.rate_limit_enabled THEN
        RETURN TRUE;
    END IF;

    v_hour_bucket := date_trunc('hour', NOW());

    SELECT promotions_count INTO v_current_count
    FROM fhq_canonical.g5_promotion_rate_log
    WHERE hour_bucket = v_hour_bucket;

    IF v_current_count IS NULL THEN
        INSERT INTO fhq_canonical.g5_promotion_rate_log (hour_bucket, promotions_count)
        VALUES (v_hour_bucket, 0)
        ON CONFLICT (hour_bucket) DO NOTHING;
        v_current_count := 0;
    END IF;

    RETURN v_current_count < v_config.max_promotions_per_hour;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 13. FUNCTION: INCREMENT RATE COUNTER
-- =============================================================================
CREATE OR REPLACE FUNCTION fhq_canonical.increment_promotion_rate()
RETURNS VOID AS $$
DECLARE
    v_hour_bucket TIMESTAMPTZ;
BEGIN
    v_hour_bucket := date_trunc('hour', NOW());

    INSERT INTO fhq_canonical.g5_promotion_rate_log (hour_bucket, promotions_count, promotions_allowed)
    VALUES (v_hour_bucket, 1, 1)
    ON CONFLICT (hour_bucket) DO UPDATE SET
        promotions_count = fhq_canonical.g5_promotion_rate_log.promotions_count + 1,
        promotions_allowed = fhq_canonical.g5_promotion_rate_log.promotions_allowed + 1;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 14. WAVE 17C ACTIVATION LOG (attestation handled separately by VEGA agent)
-- =============================================================================
INSERT INTO fhq_canonical.g5_pipeline_events (
    event_type,
    event_data,
    severity
) VALUES (
    'PIPELINE_RESUMED',
    jsonb_build_object(
        'directive', 'WAVE 17C + 17C.1',
        'title', 'Autonomous Promotion Pipeline with Enterprise Safeguards',
        'features', jsonb_build_array(
            'Rate Limiting (50/hr)',
            'Shadow Mode (24h)',
            'Ramp-Up (10%->50%->100%)',
            'Drift Detection (7-day rolling)',
            'SLA Enforcement (5s/1s/30s)',
            'Rollback Window (24h)',
            'Cross-Verification'
        ),
        'activation_date', NOW(),
        'pipeline_state', 'SHADOW'
    ),
    'INFO'
);

COMMIT;
