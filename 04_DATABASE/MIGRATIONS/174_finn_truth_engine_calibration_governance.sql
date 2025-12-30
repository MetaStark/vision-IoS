-- Migration 174: FINN Truth Engine Calibration Governance
-- CEO-DIR-2025-FINN-001 Constitutional Control
-- Date: 2025-12-30
-- Author: STIG (CTO)
--
-- Purpose: Establish constitutional governance for pilot-calibrated parameters.
-- This prevents "shifting goalposts" accusations and ensures legal defensibility.
--
-- Non-Negotiable Rules (from Board Memorandum):
-- 1. Calibration windows are bounded (weekly runs, Sunday 00:00 UTC)
-- 2. Version tagging is mandatory (TTL_v1.2, Discrepancy_v0.9, etc.)
-- 3. Production uses LAST FROZEN VERSION only
-- 4. VEGA G3 approval required for promotion
-- 5. Rollback to previous frozen version on failure
--
-- ADR Compliance: ADR-020 (ACI), ADR-010 (Discrepancy), ADR-016 (DEFCON)
-- EC Compliance: EC-020 (SitC), EC-021 (InForage), EC-022 (IKEA)

BEGIN;

-- ============================================================================
-- SCHEMA: fhq_governance (constitutional control)
-- ============================================================================

-- Table: calibration_versions
-- Stores versioned, VEGA-approved calibration parameters
CREATE TABLE IF NOT EXISTS fhq_governance.calibration_versions (
    id SERIAL PRIMARY KEY,
    parameter_name TEXT NOT NULL,
    version TEXT NOT NULL,
    value NUMERIC NOT NULL,
    description TEXT,

    -- Calibration metadata
    calibration_window TIMESTAMPTZ NOT NULL,
    calibration_source TEXT DEFAULT 'PILOT',  -- PILOT, MANUAL, INHERITED
    source_metrics JSONB DEFAULT '{}',  -- IoS-005/IoS-010 metrics used

    -- Governance lifecycle
    proposed_at TIMESTAMPTZ DEFAULT NOW(),
    proposed_by TEXT DEFAULT 'FINN',
    frozen_at TIMESTAMPTZ,
    frozen_by TEXT,
    vega_approval_ref TEXT,  -- G3 approval reference

    -- Activation status
    is_active BOOLEAN DEFAULT FALSE,
    activated_at TIMESTAMPTZ,
    deactivated_at TIMESTAMPTZ,

    -- Rollback reference
    previous_version TEXT,
    rollback_reason TEXT,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT calibration_versions_unique UNIQUE (parameter_name, version),
    CONSTRAINT calibration_versions_frozen_has_approval
        CHECK (frozen_at IS NULL OR vega_approval_ref IS NOT NULL)
);

-- Index for active parameter lookup
CREATE INDEX IF NOT EXISTS idx_calibration_active
    ON fhq_governance.calibration_versions(parameter_name, is_active)
    WHERE is_active = TRUE;

-- Index for version history
CREATE INDEX IF NOT EXISTS idx_calibration_history
    ON fhq_governance.calibration_versions(parameter_name, frozen_at DESC);

-- ============================================================================
-- Table: calibration_audit_log
-- Immutable audit trail for all calibration changes
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhq_governance.calibration_audit_log (
    id SERIAL PRIMARY KEY,
    calibration_id INTEGER REFERENCES fhq_governance.calibration_versions(id),
    parameter_name TEXT NOT NULL,
    version TEXT NOT NULL,
    action TEXT NOT NULL,  -- PROPOSED, FROZEN, ACTIVATED, DEACTIVATED, ROLLBACK
    old_value NUMERIC,
    new_value NUMERIC,
    actor TEXT NOT NULL,
    reason TEXT,
    metadata JSONB DEFAULT '{}',
    logged_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Function: get_active_calibration
-- Returns the currently active (frozen, VEGA-approved) calibration value
-- ============================================================================
CREATE OR REPLACE FUNCTION fhq_governance.get_active_calibration(
    p_parameter_name TEXT
) RETURNS NUMERIC AS $$
DECLARE
    v_value NUMERIC;
BEGIN
    SELECT value INTO v_value
    FROM fhq_governance.calibration_versions
    WHERE parameter_name = p_parameter_name
      AND is_active = TRUE
      AND frozen_at IS NOT NULL
      AND vega_approval_ref IS NOT NULL
    ORDER BY frozen_at DESC
    LIMIT 1;

    IF v_value IS NULL THEN
        RAISE WARNING 'No active calibration found for %', p_parameter_name;
    END IF;

    RETURN v_value;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- Function: propose_calibration
-- Proposes a new calibration version (requires VEGA approval to activate)
-- ============================================================================
CREATE OR REPLACE FUNCTION fhq_governance.propose_calibration(
    p_parameter_name TEXT,
    p_version TEXT,
    p_value NUMERIC,
    p_description TEXT DEFAULT NULL,
    p_source_metrics JSONB DEFAULT '{}',
    p_proposed_by TEXT DEFAULT 'FINN'
) RETURNS INTEGER AS $$
DECLARE
    v_id INTEGER;
    v_previous_version TEXT;
BEGIN
    -- Get current active version for reference
    SELECT version INTO v_previous_version
    FROM fhq_governance.calibration_versions
    WHERE parameter_name = p_parameter_name
      AND is_active = TRUE
    LIMIT 1;

    -- Insert new proposal
    INSERT INTO fhq_governance.calibration_versions (
        parameter_name, version, value, description,
        calibration_window, source_metrics, proposed_by,
        previous_version
    ) VALUES (
        p_parameter_name, p_version, p_value, p_description,
        date_trunc('week', NOW() AT TIME ZONE 'UTC') + interval '7 days',
        p_source_metrics, p_proposed_by,
        v_previous_version
    ) RETURNING id INTO v_id;

    -- Log the proposal
    INSERT INTO fhq_governance.calibration_audit_log (
        calibration_id, parameter_name, version, action,
        new_value, actor, metadata
    ) VALUES (
        v_id, p_parameter_name, p_version, 'PROPOSED',
        p_value, p_proposed_by, p_source_metrics
    );

    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Function: freeze_calibration
-- Freezes a proposed calibration (requires VEGA G3 approval ref)
-- ============================================================================
CREATE OR REPLACE FUNCTION fhq_governance.freeze_calibration(
    p_parameter_name TEXT,
    p_version TEXT,
    p_vega_approval_ref TEXT,
    p_frozen_by TEXT DEFAULT 'VEGA'
) RETURNS BOOLEAN AS $$
DECLARE
    v_id INTEGER;
    v_value NUMERIC;
BEGIN
    -- Validate approval ref format (G3-YYYY-NNN)
    IF p_vega_approval_ref !~ '^G3-[0-9]{4}-[0-9]{3}$' THEN
        RAISE EXCEPTION 'Invalid VEGA approval reference format. Expected G3-YYYY-NNN';
    END IF;

    -- Update the calibration
    UPDATE fhq_governance.calibration_versions
    SET frozen_at = NOW(),
        frozen_by = p_frozen_by,
        vega_approval_ref = p_vega_approval_ref,
        updated_at = NOW()
    WHERE parameter_name = p_parameter_name
      AND version = p_version
      AND frozen_at IS NULL
    RETURNING id, value INTO v_id, v_value;

    IF v_id IS NULL THEN
        RAISE EXCEPTION 'Calibration not found or already frozen: % %', p_parameter_name, p_version;
    END IF;

    -- Log the freeze
    INSERT INTO fhq_governance.calibration_audit_log (
        calibration_id, parameter_name, version, action,
        new_value, actor, reason, metadata
    ) VALUES (
        v_id, p_parameter_name, p_version, 'FROZEN',
        v_value, p_frozen_by, 'VEGA G3 Approval',
        jsonb_build_object('approval_ref', p_vega_approval_ref)
    );

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Function: activate_calibration
-- Activates a frozen calibration (deactivates previous)
-- ============================================================================
CREATE OR REPLACE FUNCTION fhq_governance.activate_calibration(
    p_parameter_name TEXT,
    p_version TEXT,
    p_activated_by TEXT DEFAULT 'STIG'
) RETURNS BOOLEAN AS $$
DECLARE
    v_id INTEGER;
    v_value NUMERIC;
    v_old_version TEXT;
BEGIN
    -- Validate calibration is frozen and approved
    SELECT id, value INTO v_id, v_value
    FROM fhq_governance.calibration_versions
    WHERE parameter_name = p_parameter_name
      AND version = p_version
      AND frozen_at IS NOT NULL
      AND vega_approval_ref IS NOT NULL;

    IF v_id IS NULL THEN
        RAISE EXCEPTION 'Calibration must be frozen and VEGA-approved before activation';
    END IF;

    -- Get old active version
    SELECT version INTO v_old_version
    FROM fhq_governance.calibration_versions
    WHERE parameter_name = p_parameter_name
      AND is_active = TRUE;

    -- Deactivate old version
    UPDATE fhq_governance.calibration_versions
    SET is_active = FALSE,
        deactivated_at = NOW(),
        updated_at = NOW()
    WHERE parameter_name = p_parameter_name
      AND is_active = TRUE;

    -- Activate new version
    UPDATE fhq_governance.calibration_versions
    SET is_active = TRUE,
        activated_at = NOW(),
        updated_at = NOW()
    WHERE id = v_id;

    -- Log activation
    INSERT INTO fhq_governance.calibration_audit_log (
        calibration_id, parameter_name, version, action,
        new_value, actor, metadata
    ) VALUES (
        v_id, p_parameter_name, p_version, 'ACTIVATED',
        v_value, p_activated_by,
        jsonb_build_object('previous_version', v_old_version)
    );

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Function: rollback_calibration
-- Emergency rollback to previous frozen version
-- ============================================================================
CREATE OR REPLACE FUNCTION fhq_governance.rollback_calibration(
    p_parameter_name TEXT,
    p_reason TEXT,
    p_rolled_back_by TEXT DEFAULT 'STIG'
) RETURNS TEXT AS $$
DECLARE
    v_current_version TEXT;
    v_previous_version TEXT;
    v_previous_id INTEGER;
BEGIN
    -- Get current active and its previous
    SELECT version, previous_version INTO v_current_version, v_previous_version
    FROM fhq_governance.calibration_versions
    WHERE parameter_name = p_parameter_name
      AND is_active = TRUE;

    IF v_previous_version IS NULL THEN
        RAISE EXCEPTION 'No previous version to rollback to for %', p_parameter_name;
    END IF;

    -- Deactivate current
    UPDATE fhq_governance.calibration_versions
    SET is_active = FALSE,
        deactivated_at = NOW(),
        rollback_reason = p_reason,
        updated_at = NOW()
    WHERE parameter_name = p_parameter_name
      AND is_active = TRUE;

    -- Activate previous
    UPDATE fhq_governance.calibration_versions
    SET is_active = TRUE,
        activated_at = NOW(),
        updated_at = NOW()
    WHERE parameter_name = p_parameter_name
      AND version = v_previous_version
    RETURNING id INTO v_previous_id;

    -- Log rollback
    INSERT INTO fhq_governance.calibration_audit_log (
        calibration_id, parameter_name, version, action,
        actor, reason, metadata
    ) VALUES (
        v_previous_id, p_parameter_name, v_previous_version, 'ROLLBACK',
        p_rolled_back_by, p_reason,
        jsonb_build_object('rolled_back_from', v_current_version)
    );

    RETURN v_previous_version;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- View: calibration_status
-- Current state of all calibration parameters
-- ============================================================================
CREATE OR REPLACE VIEW fhq_governance.calibration_status AS
SELECT
    cv.parameter_name,
    cv.version,
    cv.value,
    cv.description,
    cv.is_active,
    cv.frozen_at,
    cv.vega_approval_ref,
    cv.activated_at,
    cv.previous_version,
    CASE
        WHEN cv.is_active AND cv.frozen_at IS NOT NULL THEN 'PRODUCTION'
        WHEN cv.frozen_at IS NOT NULL THEN 'FROZEN (not active)'
        ELSE 'PROPOSED (awaiting VEGA)'
    END as status,
    cv.source_metrics
FROM fhq_governance.calibration_versions cv
ORDER BY cv.parameter_name, cv.frozen_at DESC NULLS LAST;

-- ============================================================================
-- Initial Calibration Seeds (CEO Directive defaults)
-- These are PROPOSALS - require VEGA G3 approval before activation
-- ============================================================================

-- TTL Regime Multipliers (EC-020 SitC)
INSERT INTO fhq_governance.calibration_versions
    (parameter_name, version, value, description, calibration_window, calibration_source, proposed_by)
VALUES
    ('TTL_NEUTRAL', 'v1.0', 1.0, 'TTL multiplier for NEUTRAL regime', NOW(), 'CEO_DIRECTIVE', 'STIG'),
    ('TTL_VOLATILE', 'v1.0', 0.2, 'TTL multiplier for VOLATILE regime (CEO-DIR default)', NOW(), 'CEO_DIRECTIVE', 'STIG'),
    ('TTL_BROKEN', 'v1.0', 0.2, 'TTL multiplier for BROKEN regime (CEO-DIR default)', NOW(), 'CEO_DIRECTIVE', 'STIG')
ON CONFLICT (parameter_name, version) DO NOTHING;

-- Discrepancy Thresholds (ADR-010)
INSERT INTO fhq_governance.calibration_versions
    (parameter_name, version, value, description, calibration_window, calibration_source, proposed_by)
VALUES
    ('DISCREPANCY_SOFT_FLAG', 'v1.0', 0.30, 'Soft flag threshold for discrepancy scoring', NOW(), 'CEO_DIRECTIVE', 'STIG'),
    ('DISCREPANCY_HARD_BLOCK', 'v1.0', 0.50, 'Hard block threshold (50% factual divergence)', NOW(), 'CEO_DIRECTIVE', 'STIG')
ON CONFLICT (parameter_name, version) DO NOTHING;

-- InForage Budget Thresholds (EC-021)
INSERT INTO fhq_governance.calibration_versions
    (parameter_name, version, value, description, calibration_window, calibration_source, proposed_by)
VALUES
    ('INFORAGE_DAILY_BUDGET', 'v1.0', 5.00, 'Daily LLM/API budget per EC-018', NOW(), 'CEO_DIRECTIVE', 'STIG'),
    ('INFORAGE_SCENT_PULSE', 'v1.0', 0.50, 'Minimum scent score for Pulse tier', NOW(), 'CEO_DIRECTIVE', 'STIG'),
    ('INFORAGE_SCENT_SNIPER', 'v1.0', 0.90, 'Minimum scent score for Sniper tier', NOW(), 'CEO_DIRECTIVE', 'STIG')
ON CONFLICT (parameter_name, version) DO NOTHING;

-- IKEA Confidence Thresholds (EC-022)
INSERT INTO fhq_governance.calibration_versions
    (parameter_name, version, value, description, calibration_window, calibration_source, proposed_by)
VALUES
    ('IKEA_EXTERNAL_REQUIRED', 'v1.0', 0.70, 'Below this = EXTERNAL_REQUIRED classification', NOW(), 'CEO_DIRECTIVE', 'STIG'),
    ('IKEA_PARAMETRIC_SAFE', 'v1.0', 0.95, 'Above this = safe for PARAMETRIC response', NOW(), 'CEO_DIRECTIVE', 'STIG')
ON CONFLICT (parameter_name, version) DO NOTHING;

-- SitC Chain Integrity (EC-020)
INSERT INTO fhq_governance.calibration_versions
    (parameter_name, version, value, description, calibration_window, calibration_source, proposed_by)
VALUES
    ('SITC_CHAIN_INTEGRITY_MIN', 'v1.0', 0.80, 'Minimum chain integrity score (< 0.80 = CATASTROPHIC)', NOW(), 'CEO_DIRECTIVE', 'STIG')
ON CONFLICT (parameter_name, version) DO NOTHING;

-- ============================================================================
-- Grant permissions
-- ============================================================================
GRANT SELECT ON fhq_governance.calibration_versions TO PUBLIC;
GRANT SELECT ON fhq_governance.calibration_audit_log TO PUBLIC;
GRANT SELECT ON fhq_governance.calibration_status TO PUBLIC;

-- STIG can propose and activate
GRANT INSERT, UPDATE ON fhq_governance.calibration_versions TO postgres;
GRANT INSERT ON fhq_governance.calibration_audit_log TO postgres;
GRANT USAGE ON SEQUENCE fhq_governance.calibration_versions_id_seq TO postgres;
GRANT USAGE ON SEQUENCE fhq_governance.calibration_audit_log_id_seq TO postgres;

COMMIT;

-- ============================================================================
-- Migration verification
-- ============================================================================
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM fhq_governance.calibration_versions;

    RAISE NOTICE 'Migration 174 complete: % calibration parameters seeded (awaiting VEGA G3 approval)', v_count;
    RAISE NOTICE 'Constitutional Control: All parameters require VEGA G3 approval before activation';
END $$;
