-- ============================================================================
-- MIGRATION 191: CEO-DIR-2026-FINN-018 SitC Execution Gate
-- ============================================================================
--
-- CEO DIRECTIVE: COGNITIVE SPINE ACTIVATION - PHASE I
--
-- "No thinking, no trading."
--
-- This migration adds the mandatory columns to fhq_cognition.search_in_chain_events
-- required for SitC to act as a HARD BLOCKING EXECUTION GATE.
--
-- Required Fields (CEO Directive Section 4.2):
--   - needle_id: Links to golden_needle being executed
--   - plan_id: SitC plan identifier
--   - asset: The asset being traded
--   - regime_context: Current market regime at reasoning time
--   - intent_summary: Human-readable summary of trade intent
--   - plan_hash: SHA-256 of the complete plan for integrity
--   - execution_gate_status: PENDING/APPROVED/BLOCKED/EXPIRED
--
-- Zero Placebo Policy (Section 5):
--   Any sitc_plan_id that does not resolve to a concrete SitC event = INVALID
--
-- Authority: CEO via ADR-014, ADR-017, ADR-020
-- Effective: Immediate
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: Add CEO-required columns to search_in_chain_events
-- ============================================================================

-- needle_id: Links to the golden needle being reasoned about
ALTER TABLE fhq_cognition.search_in_chain_events
ADD COLUMN IF NOT EXISTS needle_id UUID;

-- asset: The trading asset (e.g., BTC-USD, AAPL)
ALTER TABLE fhq_cognition.search_in_chain_events
ADD COLUMN IF NOT EXISTS asset TEXT;

-- regime_context: Market regime at reasoning time
ALTER TABLE fhq_cognition.search_in_chain_events
ADD COLUMN IF NOT EXISTS regime_context TEXT;

-- intent_summary: Human-readable trade intent
ALTER TABLE fhq_cognition.search_in_chain_events
ADD COLUMN IF NOT EXISTS intent_summary TEXT;

-- plan_hash: SHA-256 of complete SitC plan (integrity verification)
ALTER TABLE fhq_cognition.search_in_chain_events
ADD COLUMN IF NOT EXISTS plan_hash TEXT;

-- execution_gate_status: Status of execution gate check
ALTER TABLE fhq_cognition.search_in_chain_events
ADD COLUMN IF NOT EXISTS execution_gate_status TEXT DEFAULT 'PENDING'
CHECK (execution_gate_status IN ('PENDING', 'APPROVED', 'BLOCKED', 'EXPIRED', 'EXECUTED'));

-- eqs_score: Evidence Quality Score at reasoning time (0.0-1.0)
ALTER TABLE fhq_cognition.search_in_chain_events
ADD COLUMN IF NOT EXISTS eqs_score NUMERIC(5,4);

-- confidence_level: SitC confidence (HIGH/MEDIUM/LOW)
ALTER TABLE fhq_cognition.search_in_chain_events
ADD COLUMN IF NOT EXISTS confidence_level TEXT
CHECK (confidence_level IN ('HIGH', 'MEDIUM', 'LOW'));

-- reasoning_complete: Boolean flag indicating SitC completed reasoning
ALTER TABLE fhq_cognition.search_in_chain_events
ADD COLUMN IF NOT EXISTS reasoning_complete BOOLEAN DEFAULT FALSE;

-- gate_checked_at: Timestamp when execution gate was checked
ALTER TABLE fhq_cognition.search_in_chain_events
ADD COLUMN IF NOT EXISTS gate_checked_at TIMESTAMPTZ;

-- executor_session_id: Session ID of signal executor that checked gate
ALTER TABLE fhq_cognition.search_in_chain_events
ADD COLUMN IF NOT EXISTS executor_session_id TEXT;

COMMENT ON COLUMN fhq_cognition.search_in_chain_events.needle_id IS
'CEO-DIR-2026-FINN-018: Links to golden_needle being executed';

COMMENT ON COLUMN fhq_cognition.search_in_chain_events.asset IS
'CEO-DIR-2026-FINN-018: Trading asset (e.g., BTC-USD)';

COMMENT ON COLUMN fhq_cognition.search_in_chain_events.regime_context IS
'CEO-DIR-2026-FINN-018: Market regime at SitC reasoning time';

COMMENT ON COLUMN fhq_cognition.search_in_chain_events.intent_summary IS
'CEO-DIR-2026-FINN-018: Human-readable trade intent summary';

COMMENT ON COLUMN fhq_cognition.search_in_chain_events.plan_hash IS
'CEO-DIR-2026-FINN-018: SHA-256 hash of complete SitC plan for integrity';

COMMENT ON COLUMN fhq_cognition.search_in_chain_events.execution_gate_status IS
'CEO-DIR-2026-FINN-018: Execution gate status - PENDING/APPROVED/BLOCKED/EXPIRED/EXECUTED';

-- ============================================================================
-- STEP 2: Create index for needle_id lookups (execution gate checks)
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_sitc_events_needle_id
ON fhq_cognition.search_in_chain_events(needle_id)
WHERE needle_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sitc_events_gate_status
ON fhq_cognition.search_in_chain_events(execution_gate_status, reasoning_complete)
WHERE execution_gate_status IN ('PENDING', 'APPROVED');

CREATE INDEX IF NOT EXISTS idx_sitc_events_asset_created
ON fhq_cognition.search_in_chain_events(asset, created_at DESC)
WHERE asset IS NOT NULL;

-- ============================================================================
-- STEP 3: Create execution gate verification function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_cognition.verify_sitc_execution_gate(
    p_needle_id UUID,
    p_executor_session TEXT DEFAULT NULL
)
RETURNS TABLE (
    gate_approved BOOLEAN,
    sitc_event_id UUID,
    plan_id UUID,
    confidence_level TEXT,
    eqs_score NUMERIC,
    rejection_reason TEXT
) AS $$
DECLARE
    v_event RECORD;
    v_stale_threshold INTERVAL := INTERVAL '1 hour';
BEGIN
    -- Find valid SitC event for this needle
    SELECT * INTO v_event
    FROM fhq_cognition.search_in_chain_events
    WHERE search_in_chain_events.needle_id = p_needle_id
      AND reasoning_complete = TRUE
      AND execution_gate_status IN ('PENDING', 'APPROVED')
      AND created_at > NOW() - v_stale_threshold
    ORDER BY created_at DESC
    LIMIT 1;

    -- No SitC event found = GATE BLOCKED
    IF v_event IS NULL THEN
        RETURN QUERY SELECT
            FALSE::BOOLEAN,
            NULL::UUID,
            NULL::UUID,
            NULL::TEXT,
            NULL::NUMERIC,
            'NO_SITC_EVENT: No valid SitC reasoning found for needle'::TEXT;
        RETURN;
    END IF;

    -- SitC event found but LOW confidence = GATE BLOCKED
    IF v_event.confidence_level = 'LOW' THEN
        -- Mark as BLOCKED
        UPDATE fhq_cognition.search_in_chain_events
        SET execution_gate_status = 'BLOCKED',
            gate_checked_at = NOW(),
            executor_session_id = p_executor_session
        WHERE sitc_event_id = v_event.sitc_event_id;

        RETURN QUERY SELECT
            FALSE::BOOLEAN,
            v_event.sitc_event_id,
            v_event.protocol_id,
            v_event.confidence_level,
            v_event.eqs_score,
            'LOW_CONFIDENCE: SitC returned LOW confidence - execution blocked'::TEXT;
        RETURN;
    END IF;

    -- SitC event found with HIGH/MEDIUM confidence = GATE APPROVED
    UPDATE fhq_cognition.search_in_chain_events
    SET execution_gate_status = 'APPROVED',
        gate_checked_at = NOW(),
        executor_session_id = p_executor_session
    WHERE sitc_event_id = v_event.sitc_event_id;

    RETURN QUERY SELECT
        TRUE::BOOLEAN,
        v_event.sitc_event_id,
        v_event.protocol_id,
        v_event.confidence_level,
        v_event.eqs_score,
        NULL::TEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_cognition.verify_sitc_execution_gate IS
'CEO-DIR-2026-FINN-018: Verifies SitC reasoning exists before execution is permitted';

-- ============================================================================
-- STEP 4: Create function to mark SitC event as EXECUTED
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_cognition.mark_sitc_executed(
    p_sitc_event_id UUID,
    p_trade_id UUID DEFAULT NULL
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE fhq_cognition.search_in_chain_events
    SET execution_gate_status = 'EXECUTED',
        updated_at = NOW()
    WHERE sitc_event_id = p_sitc_event_id
      AND execution_gate_status = 'APPROVED';

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- STEP 5: Create orphan UUID detection view
-- ============================================================================

CREATE OR REPLACE VIEW fhq_cognition.sitc_orphan_uuids AS
SELECT
    gn.needle_id,
    gn.target_asset,
    gn.sitc_plan_id,
    gn.created_at as needle_created,
    CASE
        WHEN se.sitc_event_id IS NULL THEN 'ORPHAN'
        WHEN se.reasoning_complete = FALSE THEN 'INCOMPLETE'
        WHEN se.execution_gate_status = 'EXPIRED' THEN 'EXPIRED'
        ELSE 'VALID'
    END as sitc_status
FROM fhq_canonical.golden_needles gn
LEFT JOIN fhq_cognition.search_in_chain_events se
    ON gn.sitc_plan_id = se.protocol_id
WHERE gn.sitc_plan_id IS NOT NULL;

COMMENT ON VIEW fhq_cognition.sitc_orphan_uuids IS
'CEO-DIR-2026-FINN-018 Section 5: Zero Placebo Policy - Detect orphan sitc_plan_ids';

-- ============================================================================
-- STEP 6: Log directive activation (using cognitive_engine_evidence)
-- ============================================================================

INSERT INTO fhq_meta.cognitive_engine_evidence (
    evidence_id,
    engine_id,
    engine_name,
    interaction_id,
    invocation_type,
    input_context,
    decision_rationale,
    output_modification,
    state_snapshot_hash,
    cost_usd,
    created_at
) VALUES (
    gen_random_uuid(),
    'EC-020',
    'SitC',
    gen_random_uuid(),
    'CEO_DIRECTIVE_ACTIVATION',
    '{"directive": "CEO-DIR-2026-FINN-018", "phase": "I"}'::jsonb,
    'SitC elevated from descriptive component to HARD BLOCKING EXECUTION GATE. No execution permitted without active SitC reasoning.',
    '{"gate_type": "HARD_BLOCK", "zero_placebo": true}'::jsonb,
    'CEO-DIR-2026-FINN-018-ACTIVATION',
    0.0,
    NOW()
);

-- ============================================================================
-- STEP 7: Expire any stale PENDING entries older than 1 hour
-- ============================================================================

UPDATE fhq_cognition.search_in_chain_events
SET execution_gate_status = 'EXPIRED'
WHERE execution_gate_status = 'PENDING'
  AND created_at < NOW() - INTERVAL '1 hour';

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_columns_added INTEGER;
    v_function_exists BOOLEAN;
BEGIN
    -- Check columns added
    SELECT COUNT(*) INTO v_columns_added
    FROM information_schema.columns
    WHERE table_schema = 'fhq_cognition'
      AND table_name = 'search_in_chain_events'
      AND column_name IN ('needle_id', 'asset', 'regime_context', 'intent_summary',
                          'plan_hash', 'execution_gate_status', 'eqs_score',
                          'confidence_level', 'reasoning_complete');

    -- Check function exists
    SELECT EXISTS(
        SELECT 1 FROM pg_proc
        WHERE proname = 'verify_sitc_execution_gate'
    ) INTO v_function_exists;

    IF v_columns_added >= 9 AND v_function_exists THEN
        RAISE NOTICE '';
        RAISE NOTICE '============================================================';
        RAISE NOTICE 'CEO-DIR-2026-FINN-018 MIGRATION COMPLETE';
        RAISE NOTICE '============================================================';
        RAISE NOTICE 'SitC is now a HARD BLOCKING EXECUTION GATE';
        RAISE NOTICE 'Columns added: %', v_columns_added;
        RAISE NOTICE 'Gate function: verify_sitc_execution_gate()';
        RAISE NOTICE '';
        RAISE NOTICE 'ENFORCEMENT ACTIVE:';
        RAISE NOTICE '  - No execution without SitC event';
        RAISE NOTICE '  - No execution with LOW confidence';
        RAISE NOTICE '  - Orphan UUIDs = governance violation';
        RAISE NOTICE '============================================================';
    ELSE
        RAISE EXCEPTION 'Migration verification FAILED. Columns: %, Function: %',
            v_columns_added, v_function_exists;
    END IF;
END $$;
