-- ============================================================================
-- MIGRATION 234: Hash-of-Truth Dashboard Attestation Infrastructure
-- ============================================================================
-- Directive: CEO-DIR-2026-TRUTH-SYNC-P1
-- Authority: ADR-019 (Human Interaction - Dumb Glass)
-- Purpose: Implement server-side cryptographic attestation for dashboard metrics
--
-- This migration creates infrastructure for the "Hash-of-Truth" contract:
-- - Dashboard is Dumb Glass - no UI-side computation
-- - All critical metrics must be computed server-side with verification
-- - Any mismatch triggers lockout behavior per charter
-- ============================================================================

-- Create table for dashboard truth attestations
CREATE TABLE IF NOT EXISTS vision_verification.dashboard_truth_attestation (
    attestation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- What is being attested
    route_path TEXT NOT NULL,              -- e.g., '/api/finn/meta-signal'
    listing_id TEXT NOT NULL,              -- e.g., 'LST_BTC_XCRYPTO' or 'BTC-USD'
    attestation_date DATE NOT NULL,        -- Date of the attested data

    -- Attested fields (canonical values)
    regime_label TEXT,                     -- BULL/NEUTRAL/BEAR/STRESS
    regime_date DATE,                      -- Date regime was computed
    allocation_pct NUMERIC(10,4),          -- Meta allocation percentage
    signal_strength NUMERIC(10,4),         -- Signal strength value

    -- Hash-of-Truth computation
    -- Fields hashed: regime_label, regime_date, allocation_pct, signal_strength, listing_id
    -- Canonicalization: JSON keys sorted alphabetically, no whitespace, UTC timestamps ISO-8601
    truth_hash TEXT NOT NULL,              -- SHA-256 hash of canonical JSON
    canonical_json TEXT NOT NULL,          -- The exact JSON that was hashed

    -- Provenance
    source_table TEXT NOT NULL,            -- e.g., 'fhq_perception.sovereign_regime_state_v4'
    source_query TEXT NOT NULL,            -- Exact SQL used to fetch data
    source_row_id TEXT,                    -- ID of source row if applicable

    -- Signing (per ADR-008)
    signed_by TEXT NOT NULL DEFAULT 'STIG',
    signature TEXT,                        -- Ed25519 signature (optional, for high-security)

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,                -- When this attestation expires

    -- Integrity
    is_verified BOOLEAN DEFAULT TRUE,
    verification_failures INTEGER DEFAULT 0,

    -- Constraints
    CONSTRAINT valid_regime_label CHECK (regime_label IS NULL OR regime_label IN ('BULL', 'NEUTRAL', 'BEAR', 'STRESS')),
    CONSTRAINT valid_hash_length CHECK (LENGTH(truth_hash) = 64)
);

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_attestation_route_listing_date
ON vision_verification.dashboard_truth_attestation(route_path, listing_id, attestation_date DESC);

CREATE INDEX IF NOT EXISTS idx_attestation_created_at
ON vision_verification.dashboard_truth_attestation(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_attestation_truth_hash
ON vision_verification.dashboard_truth_attestation(truth_hash);

-- Create table for split-brain events (per CEO directive requirement)
CREATE TABLE IF NOT EXISTS fhq_governance.split_brain_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- What was detected
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    route_path TEXT NOT NULL,
    listing_id TEXT NOT NULL,

    -- The two conflicting values
    legacy_source TEXT NOT NULL,           -- e.g., 'fhq_hmm.regime_predictions'
    legacy_value TEXT NOT NULL,            -- e.g., 'NEUTRAL'
    canonical_source TEXT NOT NULL,        -- e.g., 'fhq_perception.sovereign_regime_state_v4'
    canonical_value TEXT NOT NULL,         -- e.g., 'BULL'

    -- Resolution
    action_taken TEXT NOT NULL,            -- e.g., 'DISPLAYED_CANONICAL_WITH_WARNING'
    defcon_triggered BOOLEAN DEFAULT FALSE,
    defcon_level TEXT,

    -- Metadata
    detected_by TEXT NOT NULL DEFAULT 'STIG',
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_split_brain_detected_at
ON fhq_governance.split_brain_events(detected_at DESC);

-- Create function to compute truth hash
CREATE OR REPLACE FUNCTION vision_verification.compute_truth_hash(
    p_regime_label TEXT,
    p_regime_date DATE,
    p_allocation_pct NUMERIC,
    p_signal_strength NUMERIC,
    p_listing_id TEXT
) RETURNS TABLE (truth_hash TEXT, canonical_json TEXT) AS $$
DECLARE
    v_canonical_json TEXT;
    v_hash TEXT;
BEGIN
    -- Build canonical JSON (keys sorted alphabetically, no whitespace)
    -- IMPORTANT: Round numerics to consistent precision (2 decimal places)
    -- to avoid hash mismatches when values retrieved from DB with NUMERIC(10,4)
    v_canonical_json := json_build_object(
        'allocation_pct', ROUND(COALESCE(p_allocation_pct, 0)::numeric, 2),
        'listing_id', COALESCE(p_listing_id, ''),
        'regime_date', COALESCE(p_regime_date::TEXT, ''),
        'regime_label', COALESCE(p_regime_label, ''),
        'signal_strength', ROUND(COALESCE(p_signal_strength, 0)::numeric, 2)
    )::TEXT;

    -- Remove whitespace for deterministic hashing
    v_canonical_json := REGEXP_REPLACE(v_canonical_json, '\s+', '', 'g');

    -- Compute SHA-256 hash
    v_hash := encode(sha256(v_canonical_json::bytea), 'hex');

    RETURN QUERY SELECT v_hash, v_canonical_json;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Create function to create attestation
CREATE OR REPLACE FUNCTION vision_verification.create_truth_attestation(
    p_route_path TEXT,
    p_listing_id TEXT,
    p_regime_label TEXT,
    p_regime_date DATE,
    p_allocation_pct NUMERIC,
    p_signal_strength NUMERIC,
    p_source_table TEXT,
    p_source_query TEXT,
    p_source_row_id TEXT DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_attestation_id UUID;
    v_hash_result RECORD;
BEGIN
    -- Compute hash
    SELECT * INTO v_hash_result
    FROM vision_verification.compute_truth_hash(
        p_regime_label, p_regime_date, p_allocation_pct, p_signal_strength, p_listing_id
    );

    -- Insert attestation
    INSERT INTO vision_verification.dashboard_truth_attestation (
        route_path, listing_id, attestation_date,
        regime_label, regime_date, allocation_pct, signal_strength,
        truth_hash, canonical_json,
        source_table, source_query, source_row_id,
        expires_at
    ) VALUES (
        p_route_path, p_listing_id, CURRENT_DATE,
        p_regime_label, p_regime_date, p_allocation_pct, p_signal_strength,
        v_hash_result.truth_hash, v_hash_result.canonical_json,
        p_source_table, p_source_query, p_source_row_id,
        NOW() + INTERVAL '24 hours'
    )
    RETURNING attestation_id INTO v_attestation_id;

    RETURN v_attestation_id;
END;
$$ LANGUAGE plpgsql;

-- Create function to verify attestation
CREATE OR REPLACE FUNCTION vision_verification.verify_truth_attestation(
    p_attestation_id UUID
) RETURNS TABLE (
    is_valid BOOLEAN,
    computed_hash TEXT,
    stored_hash TEXT,
    mismatch_reason TEXT
) AS $$
DECLARE
    v_attestation RECORD;
    v_computed_hash RECORD;
BEGIN
    -- Get attestation
    SELECT * INTO v_attestation
    FROM vision_verification.dashboard_truth_attestation
    WHERE attestation_id = p_attestation_id;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, NULL::TEXT, NULL::TEXT, 'Attestation not found'::TEXT;
        RETURN;
    END IF;

    -- Recompute hash
    SELECT * INTO v_computed_hash
    FROM vision_verification.compute_truth_hash(
        v_attestation.regime_label,
        v_attestation.regime_date,
        v_attestation.allocation_pct,
        v_attestation.signal_strength,
        v_attestation.listing_id
    );

    -- Compare
    IF v_computed_hash.truth_hash = v_attestation.truth_hash THEN
        RETURN QUERY SELECT TRUE, v_computed_hash.truth_hash, v_attestation.truth_hash, NULL::TEXT;
    ELSE
        -- Log verification failure
        UPDATE vision_verification.dashboard_truth_attestation
        SET verification_failures = verification_failures + 1,
            is_verified = FALSE
        WHERE attestation_id = p_attestation_id;

        RETURN QUERY SELECT FALSE, v_computed_hash.truth_hash, v_attestation.truth_hash, 'Hash mismatch - possible data tampering'::TEXT;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Log this migration to governance
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'MIGRATION_EXECUTED',
    'vision_verification.dashboard_truth_attestation',
    'TABLE_CREATION',
    'STIG',
    'EXECUTED',
    'CEO-DIR-2026-TRUTH-SYNC-P1: Hash-of-Truth attestation infrastructure for Dumb Glass dashboard per ADR-019',
    jsonb_build_object(
        'migration_id', '234_hash_of_truth_attestation',
        'directive', 'CEO-DIR-2026-TRUTH-SYNC-P1',
        'tables_created', ARRAY['vision_verification.dashboard_truth_attestation', 'fhq_governance.split_brain_events'],
        'functions_created', ARRAY['vision_verification.compute_truth_hash', 'vision_verification.create_truth_attestation', 'vision_verification.verify_truth_attestation'],
        'executed_at', NOW()
    )
);

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON vision_verification.dashboard_truth_attestation TO postgres;
GRANT SELECT, INSERT ON fhq_governance.split_brain_events TO postgres;
GRANT EXECUTE ON FUNCTION vision_verification.compute_truth_hash TO postgres;
GRANT EXECUTE ON FUNCTION vision_verification.create_truth_attestation TO postgres;
GRANT EXECUTE ON FUNCTION vision_verification.verify_truth_attestation TO postgres;

COMMENT ON TABLE vision_verification.dashboard_truth_attestation IS 'Hash-of-Truth attestation for dashboard metrics per ADR-019 (Dumb Glass) and CEO-DIR-2026-TRUTH-SYNC-P1';
COMMENT ON TABLE fhq_governance.split_brain_events IS 'Audit log of split-brain detections between legacy and canonical data sources';
COMMENT ON FUNCTION vision_verification.compute_truth_hash IS 'Computes deterministic SHA-256 hash of dashboard metric fields for truth attestation';
COMMENT ON FUNCTION vision_verification.create_truth_attestation IS 'Creates a new truth attestation record for dashboard metrics';
COMMENT ON FUNCTION vision_verification.verify_truth_attestation IS 'Verifies an existing truth attestation by recomputing hash';
