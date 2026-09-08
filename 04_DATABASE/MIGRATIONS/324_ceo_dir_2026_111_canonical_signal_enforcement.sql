-- CEO-DIR-2026-111 Phase 2: Canonical Signal Path Enforcement
-- Classification: MANDATORY – IMMEDIATE EXECUTION
-- Implementor: STIG
-- Date: 2026-01-20

-- =============================================================================
-- PHASE 2: ENFORCE CANONICAL SIGNAL PATH
-- IoS-007 → IoS-008 → g2_decision_plans → EC-015 (CPTO)
-- =============================================================================

BEGIN;

-- Step 1: Create canonical signal routing configuration
CREATE TABLE IF NOT EXISTS fhq_alpha.signal_routing_config (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_module TEXT NOT NULL,
    routing_mode TEXT NOT NULL DEFAULT 'CANONICAL',
    direct_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    required_signal_class TEXT,
    canonical_path_enforced BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    directive_reference TEXT,
    CONSTRAINT chk_routing_mode CHECK (routing_mode IN ('CANONICAL', 'BYPASS', 'SHADOW'))
);

-- Step 2: Register IOS012B routing - FORBID direct execution
INSERT INTO fhq_alpha.signal_routing_config (
    source_module,
    routing_mode,
    direct_execution_allowed,
    required_signal_class,
    canonical_path_enforced,
    directive_reference
) VALUES (
    'IOS012B_INVERSION',
    'CANONICAL',
    false,  -- CEO-DIR-2026-111: Direct execution FORBIDDEN
    'LOW_CONFIDENCE_INVERSION_CANDIDATE',
    true,
    'CEO-DIR-2026-111'
) ON CONFLICT DO NOTHING;

-- Step 3: Create canonical signal handoff table
-- This is the intermediate table between IoS-008 and CPTO
CREATE TABLE IF NOT EXISTS fhq_alpha.canonical_signal_handoff (
    handoff_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source identification
    source_module TEXT NOT NULL,
    source_signal_id UUID NOT NULL,

    -- Signal data (from g2_decision_plans)
    plan_id UUID REFERENCES fhq_alpha.g2_decision_plans(plan_id),
    instrument TEXT NOT NULL,
    direction TEXT NOT NULL,
    decision_confidence NUMERIC NOT NULL,

    -- Signal classification (CEO-DIR-2026-110/111)
    signal_class TEXT NOT NULL DEFAULT 'STANDARD',
    inversion_metadata JSONB,

    -- Regime context
    regime_at_handoff TEXT NOT NULL,
    regime_confidence NUMERIC,

    -- TTL enforcement
    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_until TIMESTAMPTZ NOT NULL,
    ttl_seconds INTEGER NOT NULL,

    -- Handoff status
    handoff_status TEXT NOT NULL DEFAULT 'PENDING_CPTO',
    cpto_received_at TIMESTAMPTZ,
    cpto_decision TEXT,
    cpto_decision_reason TEXT,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    shadow_generated BOOLEAN NOT NULL DEFAULT true,
    directive_reference TEXT NOT NULL DEFAULT 'CEO-DIR-2026-111',

    CONSTRAINT chk_signal_class CHECK (signal_class IN (
        'STANDARD',
        'LOW_CONFIDENCE_INVERSION_CANDIDATE',
        'HIGH_CONFIDENCE_VERIFIED',
        'EXPERIMENTAL'
    )),
    CONSTRAINT chk_handoff_status CHECK (handoff_status IN (
        'PENDING_CPTO',
        'CPTO_PROCESSING',
        'CPTO_ACCEPTED',
        'CPTO_REFUSED',
        'EXPIRED'
    ))
);

CREATE INDEX IF NOT EXISTS idx_canonical_handoff_status
ON fhq_alpha.canonical_signal_handoff(handoff_status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_canonical_handoff_source
ON fhq_alpha.canonical_signal_handoff(source_module, created_at DESC);

-- Step 4: Update existing g2_decision_plans to set signal_class where missing
UPDATE fhq_alpha.g2_decision_plans
SET signal_class = 'STANDARD'
WHERE signal_class IS NULL;

-- Step 5: Create function to enforce canonical routing
CREATE OR REPLACE FUNCTION fhq_alpha.enforce_canonical_routing(
    p_source_module TEXT,
    p_signal_id UUID,
    p_plan_id UUID
) RETURNS BOOLEAN AS $$
DECLARE
    v_config RECORD;
    v_allowed BOOLEAN := false;
BEGIN
    -- Get routing config for source module
    SELECT * INTO v_config
    FROM fhq_alpha.signal_routing_config
    WHERE source_module = p_source_module
    LIMIT 1;

    IF v_config IS NULL THEN
        -- No config = default to canonical path
        RETURN true;
    END IF;

    -- Check if direct execution is forbidden
    IF v_config.direct_execution_allowed = false THEN
        -- Must use canonical path
        IF v_config.canonical_path_enforced THEN
            -- Check signal has correct signal_class
            PERFORM 1 FROM fhq_alpha.g2_decision_plans
            WHERE plan_id = p_plan_id
            AND signal_class = v_config.required_signal_class;

            v_allowed := FOUND;
        END IF;
    ELSE
        v_allowed := true;
    END IF;

    RETURN v_allowed;
END;
$$ LANGUAGE plpgsql;

-- Step 6: Create view for canonical signal flow monitoring
CREATE OR REPLACE VIEW fhq_alpha.v_canonical_signal_flow AS
SELECT
    h.handoff_id,
    h.source_module,
    h.source_signal_id,
    h.instrument,
    h.direction,
    h.decision_confidence,
    h.signal_class,
    h.regime_at_handoff,
    h.valid_until,
    h.ttl_seconds,
    h.handoff_status,
    h.cpto_decision,
    h.shadow_generated,
    h.created_at,
    -- TTL status
    CASE
        WHEN h.valid_until < NOW() THEN 'EXPIRED'
        WHEN h.valid_until < NOW() + INTERVAL '5 minutes' THEN 'EXPIRING_SOON'
        ELSE 'VALID'
    END as ttl_status,
    EXTRACT(EPOCH FROM (h.valid_until - NOW())) as seconds_remaining,
    -- Routing compliance
    COALESCE(rc.canonical_path_enforced, true) as canonical_enforced,
    COALESCE(rc.direct_execution_allowed, false) as direct_allowed
FROM fhq_alpha.canonical_signal_handoff h
LEFT JOIN fhq_alpha.signal_routing_config rc ON rc.source_module = h.source_module
ORDER BY h.created_at DESC;

-- Step 7: Log governance action
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
    'CANONICAL_PATH_ENFORCEMENT',
    'CEO-DIR-2026-111-PHASE-2',
    'SIGNAL_ROUTING',
    'STIG',
    NOW(),
    'APPROVED',
    'CEO-DIR-2026-111 Phase 2: Canonical signal path enforced. ' ||
    'IOS012B_INVERSION direct execution FORBIDDEN. ' ||
    'All signals must traverse IoS-007 → IoS-008 → g2_decision_plans → EC-015 (CPTO). ' ||
    'Required classification: signal_class = LOW_CONFIDENCE_INVERSION_CANDIDATE.',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-111',
        'phase', 2,
        'forbidden_paths', ARRAY['IOS012B_INVERSION direct to paper_orders'],
        'required_path', 'IoS-007 → IoS-008 → g2_decision_plans → CPTO',
        'required_signal_class', 'LOW_CONFIDENCE_INVERSION_CANDIDATE'
    ),
    false
);

COMMIT;

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Verify routing config
SELECT source_module, routing_mode, direct_execution_allowed, required_signal_class
FROM fhq_alpha.signal_routing_config
WHERE source_module = 'IOS012B_INVERSION';

-- Verify canonical_signal_handoff table exists
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'fhq_alpha' AND table_name = 'canonical_signal_handoff';
