-- Migration 176: InForage Source-Tier Reconciliation
-- CEO-DIR-2025-FINN-003 Section 2.2
-- Date: 2025-12-30
-- Author: STIG (CTO)
--
-- Purpose: Add Source-Tier + Reason fields to InForage cost logging
-- to eliminate Epistemic Accounting Conflicts (EC-021).
--
-- CRITICAL RULE: A $0.00 spend is only valid if:
--   1. Source_Tier = LAKE (Internal/Cached)
--   2. reason_for_cost is explicitly provided
--
-- ADR Compliance: ADR-012 (Economic Safety), EC-021 (InForage)

BEGIN;

-- ============================================================================
-- SCHEMA: fhq_optimization (InForage domain)
-- ============================================================================

-- Add Source-Tier enumeration
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'inforage_source_tier') THEN
        CREATE TYPE fhq_optimization.inforage_source_tier AS ENUM (
            'LAKE',    -- Internal/cached (free)
            'PULSE',   -- Standard APIs (medium cost)
            'SNIPER'   -- Premium APIs (high cost)
        );
    END IF;
END $$;

-- Add new columns to inforage_cost_log
ALTER TABLE fhq_optimization.inforage_cost_log
    ADD COLUMN IF NOT EXISTS source_tier TEXT DEFAULT 'LAKE',
    ADD COLUMN IF NOT EXISTS reason_for_cost TEXT,
    ADD COLUMN IF NOT EXISTS efficiency_penalty NUMERIC(10,6) DEFAULT 0.0,
    ADD COLUMN IF NOT EXISTS retrieval_source TEXT;

-- ============================================================================
-- CONSTRAINT: Zero-cost validation
-- A $0.00 step_cost requires explicit LAKE tier with reason
-- ============================================================================

-- Create validation function
CREATE OR REPLACE FUNCTION fhq_optimization.validate_inforage_cost()
RETURNS TRIGGER AS $$
BEGIN
    -- Rule: If step_cost = 0, source_tier MUST be LAKE with reason
    IF NEW.step_cost = 0 AND (
        NEW.source_tier IS NULL OR
        NEW.source_tier != 'LAKE' OR
        NEW.reason_for_cost IS NULL OR
        NEW.reason_for_cost = ''
    ) THEN
        RAISE EXCEPTION 'CEO-DIR-2025-FINN-003 Violation: Zero-cost step requires source_tier=LAKE and explicit reason_for_cost';
    END IF;

    -- Rule: SNIPER tier requires non-zero cost
    IF NEW.source_tier = 'SNIPER' AND NEW.step_cost = 0 THEN
        RAISE EXCEPTION 'CEO-DIR-2025-FINN-003 Violation: SNIPER tier cannot have zero cost';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger (drop first if exists)
DROP TRIGGER IF EXISTS tr_validate_inforage_cost ON fhq_optimization.inforage_cost_log;

CREATE TRIGGER tr_validate_inforage_cost
    BEFORE INSERT ON fhq_optimization.inforage_cost_log
    FOR EACH ROW
    EXECUTE FUNCTION fhq_optimization.validate_inforage_cost();

-- ============================================================================
-- Table: inforage_g1_ingest_log
-- Dedicated log for G1 evidence seeding operations
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_optimization.inforage_g1_ingest_log (
    ingest_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    directive_id TEXT NOT NULL DEFAULT 'CEO-DIR-2025-FINN-003',

    -- Ingest tracking
    batch_id TEXT NOT NULL,
    node_count INTEGER NOT NULL,

    -- Source-Tier breakdown
    lake_operations INTEGER DEFAULT 0,
    pulse_operations INTEGER DEFAULT 0,
    sniper_operations INTEGER DEFAULT 0,

    -- Cost summary
    total_cost_usd NUMERIC(10,6) DEFAULT 0.0,
    efficiency_penalty_total NUMERIC(10,6) DEFAULT 0.0,

    -- InForage formula components: Reward = Ro + λ1*Ri - λ2*Pe
    reward_outcome NUMERIC(10,6),       -- Ro (terminal outcome)
    reward_info_gain NUMERIC(10,6),     -- Ri (information gain)
    penalty_efficiency NUMERIC(10,6),   -- Pe (efficiency penalty)
    lambda_1 NUMERIC(5,4) DEFAULT 0.5,  -- Information gain weight
    lambda_2 NUMERIC(5,4) DEFAULT 0.3,  -- Efficiency penalty weight

    -- Validation
    hash_parity_confirmed BOOLEAN DEFAULT FALSE,
    ontology_validated BOOLEAN DEFAULT FALSE,

    -- Governance
    status TEXT DEFAULT 'PENDING',  -- PENDING, COMPLETED, FAILED, REJECTED
    vega_sign_off TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_g1_ingest_batch ON fhq_optimization.inforage_g1_ingest_log(batch_id);
CREATE INDEX IF NOT EXISTS idx_g1_ingest_status ON fhq_optimization.inforage_g1_ingest_log(status);

-- ============================================================================
-- Function: log_g1_retrieval
-- Records each retrieval operation during G1 ingest with proper Source-Tier
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_optimization.log_g1_retrieval(
    p_session_id UUID,
    p_step_type TEXT,
    p_source_tier TEXT,
    p_step_cost NUMERIC,
    p_reason_for_cost TEXT,
    p_retrieval_source TEXT DEFAULT NULL,
    p_efficiency_penalty NUMERIC DEFAULT 0.0
) RETURNS UUID AS $$
DECLARE
    v_log_id UUID;
    v_step_number INTEGER;
    v_cumulative_cost NUMERIC;
BEGIN
    -- Get next step number for session
    SELECT COALESCE(MAX(step_number), 0) + 1 INTO v_step_number
    FROM fhq_optimization.inforage_cost_log
    WHERE session_id = p_session_id;

    -- Calculate cumulative cost
    SELECT COALESCE(SUM(step_cost), 0) + p_step_cost INTO v_cumulative_cost
    FROM fhq_optimization.inforage_cost_log
    WHERE session_id = p_session_id;

    -- Insert log entry
    INSERT INTO fhq_optimization.inforage_cost_log (
        session_id,
        step_number,
        step_type,
        step_cost,
        cumulative_cost,
        source_tier,
        reason_for_cost,
        efficiency_penalty,
        retrieval_source,
        decision
    ) VALUES (
        p_session_id,
        v_step_number,
        p_step_type,
        p_step_cost,
        v_cumulative_cost,
        p_source_tier,
        p_reason_for_cost,
        p_efficiency_penalty,
        p_retrieval_source,
        'CONTINUE'
    )
    RETURNING log_id INTO v_log_id;

    RETURN v_log_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- View: inforage_cost_audit
-- Audit view for InForage spend transparency
-- ============================================================================

CREATE OR REPLACE VIEW fhq_optimization.inforage_cost_audit AS
SELECT
    l.session_id,
    l.step_number,
    l.step_type,
    l.source_tier,
    l.step_cost,
    l.cumulative_cost,
    l.efficiency_penalty,
    l.reason_for_cost,
    l.retrieval_source,
    l.decision,
    l.timestamp_utc,
    -- Audit flags
    CASE
        WHEN l.step_cost = 0 AND l.source_tier != 'LAKE' THEN 'VIOLATION: Zero cost without LAKE tier'
        WHEN l.step_cost = 0 AND (l.reason_for_cost IS NULL OR l.reason_for_cost = '') THEN 'VIOLATION: Zero cost without reason'
        WHEN l.source_tier = 'SNIPER' AND l.step_cost = 0 THEN 'VIOLATION: SNIPER tier with zero cost'
        ELSE 'COMPLIANT'
    END as compliance_status
FROM fhq_optimization.inforage_cost_log l
ORDER BY l.session_id, l.step_number;

-- ============================================================================
-- Grants
-- ============================================================================

GRANT SELECT ON fhq_optimization.inforage_cost_audit TO PUBLIC;
GRANT SELECT ON fhq_optimization.inforage_g1_ingest_log TO PUBLIC;
GRANT INSERT, UPDATE ON fhq_optimization.inforage_g1_ingest_log TO postgres;
GRANT EXECUTE ON FUNCTION fhq_optimization.log_g1_retrieval TO postgres;

COMMIT;

-- ============================================================================
-- Verification
-- ============================================================================

DO $$
DECLARE
    v_has_source_tier BOOLEAN;
    v_has_trigger BOOLEAN;
BEGIN
    -- Check new columns exist
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_optimization'
        AND table_name = 'inforage_cost_log'
        AND column_name = 'source_tier'
    ) INTO v_has_source_tier;

    -- Check trigger exists
    SELECT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'tr_validate_inforage_cost'
    ) INTO v_has_trigger;

    RAISE NOTICE 'Migration 176 complete:';
    RAISE NOTICE '  - source_tier column: %', CASE WHEN v_has_source_tier THEN 'ADDED' ELSE 'FAILED' END;
    RAISE NOTICE '  - Zero-cost validation trigger: %', CASE WHEN v_has_trigger THEN 'ACTIVE' ELSE 'FAILED' END;
    RAISE NOTICE '  - G1 ingest log table created';
    RAISE NOTICE '  - InForage audit view created';
    RAISE NOTICE '  - CEO-DIR-2025-FINN-003 Section 2.2 COMPLIANT';
END $$;
