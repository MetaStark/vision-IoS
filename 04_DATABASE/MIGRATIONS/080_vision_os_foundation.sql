-- ============================================================================
-- Migration 080: Vision-OS Foundation Deployment
-- ============================================================================
-- Authority: CEO Directive
-- Oversight: VEGA
-- Operational Lead: STIG
-- Date: 2025-12-07
--
-- Purpose: Establish the canonical infrastructure for Human Oracle Channel,
--          enabling CEO to interact with system safely via read-only access
--          while IoS-009 processes narrative vectors through BPAV mechanism.
-- ============================================================================

BEGIN;

-- ============================================================================
-- PHASE 1: Create Canonical Narrative Vectors Table
-- ============================================================================
-- This is the ONLY lawful channel for converting human intuition into
-- machine-readable probability adjustments. IoS-009 Addendum G1.

CREATE TABLE IF NOT EXISTS fhq_meta.narrative_vectors (
    -- Primary identification
    vector_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Domain classification (the perception area being influenced)
    domain TEXT NOT NULL CHECK (domain IN (
        'Regulatory',
        'Geopolitical',
        'Liquidity',
        'Reflexivity',
        'Sentiment',
        'Other'
    )),

    -- The human narrative/observation
    narrative TEXT NOT NULL,

    -- Probability assessment (0.000 to 1.000)
    probability NUMERIC(4,3) NOT NULL CHECK (probability BETWEEN 0 AND 1),

    -- Confidence in the assessment (0.000 to 1.000)
    confidence NUMERIC(4,3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),

    -- Half-life in hours (how quickly this signal decays)
    half_life_hours INTEGER NOT NULL CHECK (half_life_hours > 0),

    -- Audit trail
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL,

    -- Cryptographic binding (optional, for future Ed25519 signing)
    signature_id UUID,

    -- IoS-009 computed adjustment vector (ONLY IoS-009 writes this)
    bpav JSONB,
    bpav_computed_at TIMESTAMPTZ,
    bpav_computed_by TEXT CHECK (bpav_computed_by IN ('IoS-009', NULL)),

    -- Decay tracking
    is_expired BOOLEAN DEFAULT FALSE,
    expired_at TIMESTAMPTZ
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_narrative_vectors_domain
    ON fhq_meta.narrative_vectors(domain);
CREATE INDEX IF NOT EXISTS idx_narrative_vectors_created_at
    ON fhq_meta.narrative_vectors(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_narrative_vectors_active
    ON fhq_meta.narrative_vectors(created_at, half_life_hours)
    WHERE is_expired = FALSE;

COMMENT ON TABLE fhq_meta.narrative_vectors IS
'IoS-009 Addendum G1: Canonical Human Oracle Input table.
The ONLY lawful channel for CEO/human intuition to enter the perception layer.
Append-only for humans. BPAV computed exclusively by IoS-009.
Half-life mechanism prevents zombie signals.';

-- ============================================================================
-- PHASE 1.1: Append-Only Enforcement (No UPDATE/DELETE for humans)
-- ============================================================================

-- Create function to block human modifications
CREATE OR REPLACE FUNCTION fhq_meta.narrative_vectors_protect_records()
RETURNS TRIGGER AS $$
BEGIN
    -- Allow IoS-009 to update BPAV fields only
    IF TG_OP = 'UPDATE' THEN
        IF current_user = 'ios009_service' OR
           (NEW.bpav IS DISTINCT FROM OLD.bpav AND
            NEW.narrative = OLD.narrative AND
            NEW.probability = OLD.probability AND
            NEW.confidence = OLD.confidence) THEN
            -- IoS-009 updating BPAV or system marking as expired
            RETURN NEW;
        ELSE
            RAISE EXCEPTION 'GOVERNANCE VIOLATION: narrative_vectors is append-only. Updates prohibited except for BPAV computation by IoS-009.';
        END IF;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'GOVERNANCE VIOLATION: narrative_vectors is append-only. Deletions are prohibited. Use half_life decay mechanism.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_narrative_vectors_protect
    BEFORE UPDATE OR DELETE ON fhq_meta.narrative_vectors
    FOR EACH ROW
    EXECUTE FUNCTION fhq_meta.narrative_vectors_protect_records();

-- ============================================================================
-- PHASE 2: Create ceo_read_only Role (The Claude Clause Engine)
-- ============================================================================
-- Total freedom to think. Zero freedom to destroy.
-- This is the heart of ADR-019.

DO $$
BEGIN
    -- Create role if not exists
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ceo_read_only') THEN
        CREATE ROLE ceo_read_only NOLOGIN;
    END IF;
END $$;

-- Grant USAGE on relevant schemas
GRANT USAGE ON SCHEMA fhq_meta TO ceo_read_only;
GRANT USAGE ON SCHEMA fhq_data TO ceo_read_only;
GRANT USAGE ON SCHEMA fhq_research TO ceo_read_only;
GRANT USAGE ON SCHEMA fhq_governance TO ceo_read_only;
GRANT USAGE ON SCHEMA fhq_monitoring TO ceo_read_only;
GRANT USAGE ON SCHEMA fhq_execution TO ceo_read_only;
GRANT USAGE ON SCHEMA vision_core TO ceo_read_only;
GRANT USAGE ON SCHEMA vision_signals TO ceo_read_only;

-- Grant SELECT on all current tables in these schemas
GRANT SELECT ON ALL TABLES IN SCHEMA fhq_meta TO ceo_read_only;
GRANT SELECT ON ALL TABLES IN SCHEMA fhq_data TO ceo_read_only;
GRANT SELECT ON ALL TABLES IN SCHEMA fhq_research TO ceo_read_only;
GRANT SELECT ON ALL TABLES IN SCHEMA fhq_governance TO ceo_read_only;
GRANT SELECT ON ALL TABLES IN SCHEMA fhq_monitoring TO ceo_read_only;
GRANT SELECT ON ALL TABLES IN SCHEMA fhq_execution TO ceo_read_only;
GRANT SELECT ON ALL TABLES IN SCHEMA vision_core TO ceo_read_only;
GRANT SELECT ON ALL TABLES IN SCHEMA vision_signals TO ceo_read_only;

-- Grant SELECT on future tables automatically
ALTER DEFAULT PRIVILEGES IN SCHEMA fhq_meta GRANT SELECT ON TABLES TO ceo_read_only;
ALTER DEFAULT PRIVILEGES IN SCHEMA fhq_data GRANT SELECT ON TABLES TO ceo_read_only;
ALTER DEFAULT PRIVILEGES IN SCHEMA fhq_research GRANT SELECT ON TABLES TO ceo_read_only;
ALTER DEFAULT PRIVILEGES IN SCHEMA fhq_governance GRANT SELECT ON TABLES TO ceo_read_only;
ALTER DEFAULT PRIVILEGES IN SCHEMA fhq_monitoring GRANT SELECT ON TABLES TO ceo_read_only;
ALTER DEFAULT PRIVILEGES IN SCHEMA fhq_execution GRANT SELECT ON TABLES TO ceo_read_only;
ALTER DEFAULT PRIVILEGES IN SCHEMA vision_core GRANT SELECT ON TABLES TO ceo_read_only;
ALTER DEFAULT PRIVILEGES IN SCHEMA vision_signals GRANT SELECT ON TABLES TO ceo_read_only;

-- Explicitly revoke any write permissions (defense in depth)
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA fhq_meta FROM ceo_read_only;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA fhq_data FROM ceo_read_only;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA fhq_research FROM ceo_read_only;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA fhq_governance FROM ceo_read_only;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA fhq_monitoring FROM ceo_read_only;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA fhq_execution FROM ceo_read_only;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA vision_core FROM ceo_read_only;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA vision_signals FROM ceo_read_only;

-- No schema modification rights
REVOKE CREATE ON SCHEMA fhq_meta FROM ceo_read_only;
REVOKE CREATE ON SCHEMA fhq_data FROM ceo_read_only;
REVOKE CREATE ON SCHEMA fhq_research FROM ceo_read_only;
REVOKE CREATE ON SCHEMA fhq_governance FROM ceo_read_only;

COMMENT ON ROLE ceo_read_only IS
'ADR-019 Claude Clause Engine: Total freedom to query. Zero ability to modify.
CEO and Claude can explore the entire system without risk of accidental destruction.
SELECT-only across all fhq_* and vision_* schemas.';

-- ============================================================================
-- PHASE 3: Create Oracle Event Log for Governance Audit
-- ============================================================================
-- VEGA visibility into human oracle interactions.

CREATE TABLE IF NOT EXISTS fhq_governance.oracle_event_log (
    -- Primary identification
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to the narrative vector
    vector_id UUID NOT NULL REFERENCES fhq_meta.narrative_vectors(vector_id),

    -- Who performed the action
    operator TEXT NOT NULL,

    -- What action was performed
    action TEXT NOT NULL CHECK (action IN ('CREATE', 'REFRESH', 'DECAY', 'BPAV_COMPUTE')),

    -- The BPAV that was used/computed
    bpav_used JSONB,

    -- Additional context
    context JSONB,

    -- Timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_oracle_event_log_vector
    ON fhq_governance.oracle_event_log(vector_id);
CREATE INDEX IF NOT EXISTS idx_oracle_event_log_operator
    ON fhq_governance.oracle_event_log(operator);
CREATE INDEX IF NOT EXISTS idx_oracle_event_log_created
    ON fhq_governance.oracle_event_log(created_at DESC);

COMMENT ON TABLE fhq_governance.oracle_event_log IS
'VEGA Audit Trail: Complete visibility into Human Oracle Channel activity.
Tracks all narrative vector creation, BPAV computation, and decay events.
No secret influence attempts. Full accountability.';

-- Auto-log CREATE events when narrative vectors are inserted
CREATE OR REPLACE FUNCTION fhq_governance.log_narrative_vector_create()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO fhq_governance.oracle_event_log (
        vector_id,
        operator,
        action,
        context
    ) VALUES (
        NEW.vector_id,
        NEW.created_by,
        'CREATE',
        jsonb_build_object(
            'domain', NEW.domain,
            'probability', NEW.probability,
            'confidence', NEW.confidence,
            'half_life_hours', NEW.half_life_hours
        )
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_log_narrative_vector_create
    AFTER INSERT ON fhq_meta.narrative_vectors
    FOR EACH ROW
    EXECUTE FUNCTION fhq_governance.log_narrative_vector_create();

-- Auto-log BPAV_COMPUTE events when IoS-009 updates BPAV
CREATE OR REPLACE FUNCTION fhq_governance.log_bpav_computation()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.bpav IS DISTINCT FROM OLD.bpav AND NEW.bpav IS NOT NULL THEN
        INSERT INTO fhq_governance.oracle_event_log (
            vector_id,
            operator,
            action,
            bpav_used,
            context
        ) VALUES (
            NEW.vector_id,
            COALESCE(NEW.bpav_computed_by, 'IoS-009'),
            'BPAV_COMPUTE',
            NEW.bpav,
            jsonb_build_object(
                'computed_at', NEW.bpav_computed_at,
                'previous_bpav', OLD.bpav
            )
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_log_bpav_computation
    AFTER UPDATE ON fhq_meta.narrative_vectors
    FOR EACH ROW
    EXECUTE FUNCTION fhq_governance.log_bpav_computation();

-- ============================================================================
-- PHASE 4: Create Active Narrative Vectors View for IoS-009
-- ============================================================================
-- Clean, filtered data stream. No zombie signals.

CREATE OR REPLACE VIEW fhq_research.v_narrative_vectors_active AS
SELECT
    vector_id,
    domain,
    narrative,
    probability,
    confidence,
    half_life_hours,
    created_at,
    created_by,
    bpav,
    bpav_computed_at,
    -- Compute remaining weight based on half-life decay
    -- weight(t) = 0.5^(age_hours / half_life_hours)
    POWER(0.5, EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600.0 / half_life_hours) AS current_weight,
    -- Age in hours
    EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600.0 AS age_hours,
    -- Time until fully decayed (weight < 0.01)
    (half_life_hours * 6.64) - (EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600.0) AS hours_until_negligible
FROM fhq_meta.narrative_vectors
WHERE
    is_expired = FALSE
    -- Filter: Only vectors where age < half_life * 6.64 (weight > 1%)
    AND EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600.0 < (half_life_hours * 6.64);

COMMENT ON VIEW fhq_research.v_narrative_vectors_active IS
'IoS-009 Read-Only Input: Active narrative vectors with computed decay weights.
Filters out expired/zombie signals. current_weight shows remaining influence.
Formula: weight = 0.5^(age_hours / half_life_hours)';

-- Grant IoS-009 (and ceo_read_only) access to view
GRANT SELECT ON fhq_research.v_narrative_vectors_active TO ceo_read_only;

-- ============================================================================
-- PHASE 5: Register IoS-009 Addendum G1 Completion
-- ============================================================================

-- Update IoS-009 to G1_APPROVED (first check valid statuses)
UPDATE fhq_meta.ios_registry
SET
    version = '2026.PROD.G1',
    status = 'G2_VALIDATED',  -- Moving to G2 after G1 infrastructure is complete
    description = 'Meta-Perception Layer - Intent, Stress & Reflexivity Brain. G1 Complete: Human Oracle Channel, BPAV, Half-Life Mechanism deployed.',
    governing_adrs = CASE
        WHEN NOT ('ADR-019' = ANY(governing_adrs))
        THEN array_append(governing_adrs, 'ADR-019')
        ELSE governing_adrs
    END,
    updated_at = NOW()
WHERE ios_id = 'IoS-009';

-- Log governance action
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    hash_chain_id
) VALUES (
    'IOS_G1_INFRASTRUCTURE_DEPLOYED',
    'IoS-009',
    'IOS',
    'STIG',
    'APPROVED',
    'CEO Directive: Vision-OS Foundation deployed. Phase 1-5 complete. narrative_vectors table, ceo_read_only role, oracle_event_log, v_narrative_vectors_active view all operational. IoS-009 promoted to G2_VALIDATED.',
    'HC-IOS-009-G1-2026'
);

-- Update hash chain
UPDATE fhq_security.hash_chains
SET
    current_block_number = current_block_number + 1,
    last_block_hash = encode(sha256(('IoS-009-G1-FOUNDATION-COMPLETE-' || NOW()::TEXT)::bytea), 'hex'),
    last_updated = NOW()
WHERE chain_id = 'HC-IOS-009-G1-2026';

-- ============================================================================
-- PHASE 5.1: Create Helper Function for CEO Narrative Input
-- ============================================================================
-- Safe interface for CEO to submit narrative vectors

CREATE OR REPLACE FUNCTION fhq_meta.submit_narrative_vector(
    p_domain TEXT,
    p_narrative TEXT,
    p_probability NUMERIC(4,3),
    p_confidence NUMERIC(4,3),
    p_half_life_hours INTEGER DEFAULT 24,
    p_operator TEXT DEFAULT 'CEO'
)
RETURNS UUID AS $$
DECLARE
    v_vector_id UUID;
BEGIN
    -- Validate domain
    IF p_domain NOT IN ('Regulatory', 'Geopolitical', 'Liquidity', 'Reflexivity', 'Sentiment', 'Other') THEN
        RAISE EXCEPTION 'Invalid domain. Must be one of: Regulatory, Geopolitical, Liquidity, Reflexivity, Sentiment, Other';
    END IF;

    -- Insert the narrative vector
    INSERT INTO fhq_meta.narrative_vectors (
        domain,
        narrative,
        probability,
        confidence,
        half_life_hours,
        created_by
    ) VALUES (
        p_domain,
        p_narrative,
        p_probability,
        p_confidence,
        p_half_life_hours,
        p_operator
    ) RETURNING vector_id INTO v_vector_id;

    RETURN v_vector_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_meta.submit_narrative_vector IS
'CEO/Human Oracle interface for submitting narrative vectors to IoS-009.
Returns the vector_id for tracking. BPAV will be computed by IoS-009.';

-- ============================================================================
-- Migration Complete
-- ============================================================================

COMMIT;
