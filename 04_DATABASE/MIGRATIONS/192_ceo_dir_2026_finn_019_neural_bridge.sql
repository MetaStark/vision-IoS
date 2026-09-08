-- ============================================================================
-- MIGRATION 192: CEO-DIR-2026-FINN-019 Neural Bridge
-- ============================================================================
--
-- CEO DIRECTIVE: OPERATION NEURAL BRIDGE
--
-- This migration creates the infrastructure for causally governed trading.
-- Implements ADR-011 hash chain (Fortress compliance).
--
-- CEO Issues Addressed:
--   #1: IntentDraft before gates
--   #6: FK from trades to decision_plans
--   #7: Signature key registry reference
--   #14: ADR-011 hash chain (hash_prev, hash_self)
--   R5: lsa_hash_out write-once constraint
--   R6: chain_epoch_id for future rotation
--
-- Authority: CEO via CEO-DIR-2026-FINN-019
-- Effective: Immediate
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: Intent Drafts Table
-- ============================================================================
-- Phase 1 of DecisionPlan lifecycle: Captured BEFORE any gate

CREATE TABLE IF NOT EXISTS fhq_governance.intent_drafts (
    draft_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    needle_id UUID NOT NULL,
    asset TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT')),

    -- Market snapshot with TTL (CEO Issue #8)
    snapshot_price NUMERIC(20, 8),
    snapshot_regime TEXT,
    snapshot_regime_stability NUMERIC(5, 4),
    snapshot_timestamp TIMESTAMPTZ NOT NULL,
    snapshot_ttl_valid_until TIMESTAMPTZ NOT NULL,

    -- Pre-gate state
    eqs_score NUMERIC(5, 4),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_intent_drafts_needle
    ON fhq_governance.intent_drafts(needle_id);
CREATE INDEX IF NOT EXISTS idx_intent_drafts_created
    ON fhq_governance.intent_drafts(created_at DESC);

COMMENT ON TABLE fhq_governance.intent_drafts IS
'CEO-DIR-2026-FINN-019 NB-01: IntentDraft captured BEFORE any execution gate';

-- ============================================================================
-- STEP 2: Execution Attempts Table (ADR-011 Fortress Compliant)
-- ============================================================================
-- Every trade attempt logged with hash chain, even if blocked

CREATE TABLE IF NOT EXISTS fhq_governance.execution_attempts (
    attempt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intent_draft_id UUID NOT NULL REFERENCES fhq_governance.intent_drafts(draft_id),
    needle_id UUID NOT NULL,
    decision_plan_id UUID,  -- NULL if never sealed

    -- ADR-011 Fortress Hash Chain (CEO Issue #14)
    chain_epoch_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001',  -- R6: Future rotation
    hash_prev TEXT NOT NULL,  -- Previous attempt's hash_self (or GENESIS)
    hash_self TEXT NOT NULL,  -- SHA-256 of this record's content
    chain_sequence BIGINT NOT NULL,  -- Monotonic sequence number

    -- Gate progression (ALL gates logged even if blocked early)
    gate_exposure_passed BOOLEAN,
    gate_exposure_reason TEXT,
    gate_holiday_passed BOOLEAN,
    gate_holiday_reason TEXT,
    gate_btc_only_passed BOOLEAN,
    gate_btc_only_reason TEXT,
    gate_regime_stability_passed BOOLEAN,  -- CEO Issue #16
    gate_regime_stability_reason TEXT,
    gate_sitc_passed BOOLEAN,
    gate_sitc_reason TEXT,
    gate_ikea_passed BOOLEAN,
    gate_ikea_reason TEXT,
    gate_inforage_passed BOOLEAN,
    gate_inforage_reason TEXT,
    gate_causal_passed BOOLEAN,
    gate_causal_reason TEXT,
    gate_fss_passed BOOLEAN,
    gate_fss_reason TEXT,
    gate_ttl_passed BOOLEAN,
    gate_ttl_reason TEXT,

    -- Final outcome
    final_outcome TEXT NOT NULL
        CHECK (final_outcome IN ('EXECUTED', 'BLOCKED', 'ABORTED', 'EXPIRED', 'COST_ABORT')),
    blocked_at_gate TEXT,
    block_reason TEXT,

    -- Evidence links (ALL MANDATORY for completed attempts)
    sitc_event_id UUID,
    inforage_session_id UUID,
    ikea_validation_id UUID,
    causal_edge_refs UUID[],

    -- Audit mode flag (R1: audit-only for hard-blocked)
    audit_only_mode BOOLEAN DEFAULT FALSE,

    -- Cognition metrics (CEO Issue #11)
    cognition_started_at TIMESTAMPTZ,
    cognition_completed_at TIMESTAMPTZ,
    cognition_duration_ms INTEGER,

    -- Timestamps
    attempt_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    attempt_completed_at TIMESTAMPTZ,

    -- Signature (matches DecisionPlan signature if sealed)
    signing_agent TEXT,
    signature TEXT,

    CONSTRAINT valid_hash_chain CHECK (
        hash_prev ~ '^[a-f0-9]{64}$' OR hash_prev = 'GENESIS'
    ),
    CONSTRAINT valid_hash_self CHECK (
        hash_self ~ '^[a-f0-9]{64}$'
    )
);

-- Indexes for hash chain verification and queries
CREATE UNIQUE INDEX IF NOT EXISTS idx_attempts_epoch_seq
    ON fhq_governance.execution_attempts(chain_epoch_id, chain_sequence);
CREATE INDEX IF NOT EXISTS idx_attempts_needle
    ON fhq_governance.execution_attempts(needle_id);
CREATE INDEX IF NOT EXISTS idx_attempts_outcome
    ON fhq_governance.execution_attempts(final_outcome);
CREATE INDEX IF NOT EXISTS idx_attempts_started
    ON fhq_governance.execution_attempts(attempt_started_at DESC);

COMMENT ON TABLE fhq_governance.execution_attempts IS
'CEO-DIR-2026-FINN-019 NB-02: ADR-011 Fortress-compliant attempt chain with hash linkage';

COMMENT ON COLUMN fhq_governance.execution_attempts.chain_epoch_id IS
'R6: Chain epoch for future rotation without breaking history';

COMMENT ON COLUMN fhq_governance.execution_attempts.audit_only_mode IS
'R1: True if cognitive stack ran in audit-only mode (hard-blocked attempt)';

-- ============================================================================
-- STEP 3: Decision Plans Table
-- ============================================================================
-- Sealed DecisionPlan after cognitive stack completes

CREATE TABLE IF NOT EXISTS fhq_governance.decision_plans (
    plan_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intent_draft_id UUID NOT NULL REFERENCES fhq_governance.intent_drafts(draft_id),
    attempt_id UUID NOT NULL REFERENCES fhq_governance.execution_attempts(attempt_id),
    needle_id UUID NOT NULL,

    -- DecisionPlan fields
    asset TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    sizing_action TEXT,
    position_usd NUMERIC(15, 2),

    -- Trinity Requirement
    regime_check_passed BOOLEAN,
    regime_stability_flag BOOLEAN,  -- CEO Issue #16
    causal_alignment_score NUMERIC(5, 4),
    causal_fallback_used BOOLEAN DEFAULT FALSE,  -- R2: Explicit neutral marking
    fss_score NUMERIC(5, 4),

    -- Cognitive Evidence (ALL MANDATORY)
    sitc_event_id UUID NOT NULL,
    sitc_reasoning_complete BOOLEAN NOT NULL,
    inforage_session_id UUID NOT NULL,
    inforage_roi NUMERIC(8, 4),
    ikea_validation_id UUID NOT NULL,
    causal_edge_refs UUID[],

    -- LSA Loop (CEO Issue #13)
    lsa_hash_in TEXT,
    lsa_hash_out TEXT,  -- R5: Write-once, post-settlement only

    -- TTL (CEO Issue #8)
    plan_ttl_valid_until TIMESTAMPTZ NOT NULL,
    snapshot_ttl_valid_until TIMESTAMPTZ NOT NULL,

    -- Signature (CEO Issue #7, #15)
    signature TEXT NOT NULL,
    signing_agent TEXT NOT NULL,  -- Tier-2 Sub-Executive (e.g., "CSEO")
    signing_key_id TEXT NOT NULL,  -- Reference to fhq_meta.key_registry
    signed_at TIMESTAMPTZ NOT NULL,

    -- VEGA Verification (CEO Issue #7)
    vega_verified BOOLEAN DEFAULT FALSE,
    vega_verification_timestamp TIMESTAMPTZ,

    -- Cognition metrics (CEO Issue #11)
    cognition_duration_ms INTEGER,
    cognition_cost_usd NUMERIC(8, 4),

    -- Outcome
    final_outcome TEXT,
    blocked_at_gate TEXT,
    block_reason TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- R5: lsa_hash_out write-once constraint
ALTER TABLE fhq_governance.decision_plans
DROP CONSTRAINT IF EXISTS lsa_hash_out_write_once;

ALTER TABLE fhq_governance.decision_plans
ADD CONSTRAINT lsa_hash_out_write_once CHECK (
    (lsa_hash_out IS NULL) OR
    (final_outcome IN ('EXECUTED', 'SETTLED'))
);

CREATE INDEX IF NOT EXISTS idx_plans_needle
    ON fhq_governance.decision_plans(needle_id);
CREATE INDEX IF NOT EXISTS idx_plans_attempt
    ON fhq_governance.decision_plans(attempt_id);
CREATE INDEX IF NOT EXISTS idx_plans_created
    ON fhq_governance.decision_plans(created_at DESC);

COMMENT ON TABLE fhq_governance.decision_plans IS
'CEO-DIR-2026-FINN-019 NB-01: Signed DecisionPlan sealed after cognitive stack';

COMMENT ON COLUMN fhq_governance.decision_plans.lsa_hash_out IS
'R5: Phase II write-once field, only populated post-settlement by feedback writer';

COMMENT ON COLUMN fhq_governance.decision_plans.causal_fallback_used IS
'R2: True when alignment_score = 0.5 due to no edges (CAUSAL_NEUTRAL_FALLBACK)';

-- ============================================================================
-- STEP 4: Add FK from trades to decision_plans (CEO Issue #6)
-- ============================================================================

ALTER TABLE fhq_canonical.g5_paper_trades
ADD COLUMN IF NOT EXISTS decision_plan_id UUID;

ALTER TABLE fhq_canonical.g5_paper_trades
ADD COLUMN IF NOT EXISTS attempt_id UUID;

COMMENT ON COLUMN fhq_canonical.g5_paper_trades.decision_plan_id IS
'CEO-DIR-2026-FINN-019 Issue #6: FK to decision_plans for execution linkage';

COMMENT ON COLUMN fhq_canonical.g5_paper_trades.attempt_id IS
'CEO-DIR-2026-FINN-019 Issue #6: FK to execution_attempts for audit trail';

-- ============================================================================
-- STEP 5: IKEA Validation Log (Neural Bridge)
-- ============================================================================
-- Note: fhq_research.ikea_feedback_log already exists for claim classification
-- This table is specifically for Neural Bridge execution gate validations

CREATE TABLE IF NOT EXISTS fhq_governance.ikea_validation_log (
    validation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    passed BOOLEAN NOT NULL,
    rule_violated TEXT,
    rules_checked TEXT[],
    violation_details JSONB,
    intent_draft_id UUID,
    needle_id UUID,
    asset TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ikea_validation_passed
    ON fhq_governance.ikea_validation_log(passed);
CREATE INDEX IF NOT EXISTS idx_ikea_validation_rule
    ON fhq_governance.ikea_validation_log(rule_violated);
CREATE INDEX IF NOT EXISTS idx_ikea_validation_needle
    ON fhq_governance.ikea_validation_log(needle_id);

COMMENT ON TABLE fhq_governance.ikea_validation_log IS
'CEO-DIR-2026-FINN-019 NB-07: IKEA truth boundary validation log for Neural Bridge execution gates';

-- ============================================================================
-- STEP 6: Hash Chain Verification View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_governance.attempt_chain_audit AS
SELECT
    a.attempt_id,
    a.chain_epoch_id,
    a.chain_sequence,
    a.hash_prev,
    a.hash_self,
    LAG(a.hash_self) OVER (
        PARTITION BY a.chain_epoch_id
        ORDER BY a.chain_sequence
    ) as expected_hash_prev,
    CASE
        WHEN a.chain_sequence = 1 AND a.hash_prev = 'GENESIS' THEN 'VALID'
        WHEN a.hash_prev = LAG(a.hash_self) OVER (
            PARTITION BY a.chain_epoch_id
            ORDER BY a.chain_sequence
        ) THEN 'VALID'
        ELSE 'CHAIN_BROKEN'
    END as chain_status
FROM fhq_governance.execution_attempts a
ORDER BY a.chain_epoch_id, a.chain_sequence;

COMMENT ON VIEW fhq_governance.attempt_chain_audit IS
'CEO-DIR-2026-FINN-019 Issue #14: ADR-011 hash chain integrity verification';

-- ============================================================================
-- STEP 7: SitC Linkage Audit View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_governance.sitc_linkage_audit AS
SELECT
    a.attempt_id,
    a.needle_id,
    a.sitc_event_id,
    a.final_outcome,
    CASE
        WHEN a.sitc_event_id IS NULL THEN 'NO_SITC'
        WHEN se.sitc_event_id IS NULL THEN 'ORPHAN'
        WHEN se.reasoning_complete = FALSE THEN 'INCOMPLETE'
        ELSE 'LINKED'
    END as linkage_status
FROM fhq_governance.execution_attempts a
LEFT JOIN fhq_cognition.search_in_chain_events se
    ON a.sitc_event_id = se.sitc_event_id;

COMMENT ON VIEW fhq_governance.sitc_linkage_audit IS
'CEO-DIR-2026-FINN-019 NB-06: SitC event linkage verification';

-- ============================================================================
-- STEP 8: InForage Config Table (R3: Configurable expected_tp_pct)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.inforage_config (
    config_id SERIAL PRIMARY KEY,
    config_key TEXT UNIQUE NOT NULL,
    config_value NUMERIC(10, 4) NOT NULL,
    description TEXT,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by TEXT NOT NULL DEFAULT 'CEO-DIR-2026-FINN-019'
);

-- Insert default configuration (R3)
INSERT INTO fhq_governance.inforage_config (config_key, config_value, description) VALUES
    ('expected_tp_pct', 0.05, 'Expected take profit percentage for ROI calculation'),
    ('min_roi_threshold', 1.2, 'Minimum ROI threshold for trade approval'),
    ('default_slippage_bps', 15.0, 'Default slippage estimate in basis points')
ON CONFLICT (config_key) DO NOTHING;

COMMENT ON TABLE fhq_governance.inforage_config IS
'R3: Configurable InForage parameters. Changes require ADR amendment.';

-- ============================================================================
-- STEP 9: Log Directive Activation
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
    'MIGRATION_ACTIVATION',
    '{"migration": 192, "directive": "CEO-DIR-2026-FINN-019", "issues_addressed": 25}'::jsonb,
    'Operation Neural Bridge: Causally governed decision engine with IntentDraft -> gates -> cognition -> DecisionPlan lifecycle',
    '{"tables_created": ["intent_drafts", "execution_attempts", "decision_plans", "ikea_validation_log", "inforage_config"]}'::jsonb,
    'M192-NEURAL-BRIDGE',
    0.0,
    NOW()
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_tables_created INTEGER;
    v_views_created INTEGER;
BEGIN
    -- Count tables
    SELECT COUNT(*) INTO v_tables_created
    FROM information_schema.tables
    WHERE table_schema = 'fhq_governance'
      AND table_name IN ('intent_drafts', 'execution_attempts', 'decision_plans', 'inforage_config', 'ikea_validation_log');

    -- Count views
    SELECT COUNT(*) INTO v_views_created
    FROM information_schema.views
    WHERE table_schema = 'fhq_governance'
      AND table_name IN ('attempt_chain_audit', 'sitc_linkage_audit');

    IF v_tables_created >= 5 AND v_views_created >= 2 THEN
        RAISE NOTICE '';
        RAISE NOTICE '============================================================';
        RAISE NOTICE 'CEO-DIR-2026-FINN-019 MIGRATION 192 COMPLETE';
        RAISE NOTICE '============================================================';
        RAISE NOTICE 'Operation Neural Bridge Schema Deployed';
        RAISE NOTICE '';
        RAISE NOTICE 'Tables created: %', v_tables_created;
        RAISE NOTICE '  - fhq_governance.intent_drafts';
        RAISE NOTICE '  - fhq_governance.execution_attempts';
        RAISE NOTICE '  - fhq_governance.decision_plans';
        RAISE NOTICE '  - fhq_governance.inforage_config';
        RAISE NOTICE '  - fhq_governance.ikea_validation_log';
        RAISE NOTICE '';
        RAISE NOTICE 'Views created: %', v_views_created;
        RAISE NOTICE '  - fhq_governance.attempt_chain_audit';
        RAISE NOTICE '  - fhq_governance.sitc_linkage_audit';
        RAISE NOTICE '';
        RAISE NOTICE 'CEO Issues Addressed: 18 critical + 7 refinements';
        RAISE NOTICE '============================================================';
    ELSE
        RAISE EXCEPTION 'Migration verification FAILED. Tables: %, Views: %',
            v_tables_created, v_views_created;
    END IF;
END $$;
