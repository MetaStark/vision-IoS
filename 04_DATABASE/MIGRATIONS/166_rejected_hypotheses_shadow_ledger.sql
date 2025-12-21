-- Migration 166: Rejected Hypotheses Shadow Ledger
-- CEO Directive: CEO-REJECTION-LEDGER-2025-12-21
-- Purpose: Passive logging of hypotheses with EQS < 0.85
-- Mode: PASSIVE / EVIDENCE-ONLY / APPEND-ONLY
-- Classification: GOVERNANCE-CRITICAL · NON-EXECUTIONAL

-- ============================================================================
-- GOVERNING PRINCIPLE
-- ============================================================================
-- "We learn first from what we did, then from what we chose not to do."
--
-- This ledger exists solely to preserve rejected hypotheses as immutable
-- evidence for future retrospective analysis. It is NOT a learning system.
--
-- CONSTRAINTS (NON-NEGOTIABLE):
-- 1. Write-only for FINN
-- 2. No strategy agent may query, tune thresholds, or derive signals
-- 3. Any learning usage requires separate G4 CEO directive
-- 4. Data retained indefinitely
-- ============================================================================

-- SCHEMA: fhq_research
-- TABLE: rejected_hypotheses
-- PURPOSE: Shadow Ledger for hypotheses with EQS < 0.85
-- MODE: Passive / Evidence-Only
-- AUDIT: Append-only, read-restricted

CREATE TABLE IF NOT EXISTS fhq_research.rejected_hypotheses (
    rejection_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rejection_timestamp     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Canonical Metadata
    target_asset            TEXT NOT NULL,
    model_version           TEXT NOT NULL,  -- FINN version at rejection time

    -- Evidence Quality (The "Why")
    eqs_total_score         NUMERIC(5,4) NOT NULL, -- e.g. 0.8200
    eqs_breakdown           JSONB NOT NULL,
    -- Example: {"technical": 0.95, "volume": 0.40, "regime": 0.90}

    -- Context & Integrity
    market_context_snapshot JSONB NOT NULL, -- Price / vol / regime at rejection time
    raw_hypothesis_hash     TEXT NOT NULL,  -- SHA-256 for deduplication & audit
    rejection_reason        TEXT NOT NULL,  -- Deterministic reason code

    -- Lineage
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- INDEXING FOR FUTURE ANALYTICS
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_rejected_asset
    ON fhq_research.rejected_hypotheses(target_asset);

CREATE INDEX IF NOT EXISTS idx_rejected_score
    ON fhq_research.rejected_hypotheses(eqs_total_score);

CREATE INDEX IF NOT EXISTS idx_rejected_breakdown
    ON fhq_research.rejected_hypotheses
    USING GIN (eqs_breakdown);

CREATE INDEX IF NOT EXISTS idx_rejected_timestamp
    ON fhq_research.rejected_hypotheses(rejection_timestamp DESC);

-- ============================================================================
-- COMMENTS (Governance Documentation)
-- ============================================================================

COMMENT ON TABLE fhq_research.rejected_hypotheses IS
'Shadow Ledger for hypotheses rejected due to EQS < 0.85.
CEO Directive: CEO-REJECTION-LEDGER-2025-12-21

MODE: Passive / Evidence-Only / Append-Only

CONSTRAINTS:
- Write-only for FINN
- No strategy agent may query, tune, or derive signals
- Learning usage requires separate G4 CEO directive
- Data retained indefinitely

PURPOSE: Preserve negative selection evidence for future retrospective analysis.
This ledger captures WHY a hypothesis was rejected, not merely that it was.';

COMMENT ON COLUMN fhq_research.rejected_hypotheses.eqs_breakdown IS
'JSONB decomposition of EQS score components.
Example: {"technical": 0.95, "volume": 0.40, "regime": 0.90, "temporal": 0.85}
Mandatory JSONB for analytical flexibility without schema churn.';

COMMENT ON COLUMN fhq_research.rejected_hypotheses.rejection_reason IS
'Deterministic reason code for rejection.
Values: EQS_BELOW_THRESHOLD, MISSING_CONFLUENCE, REGIME_MISMATCH, etc.';

-- ============================================================================
-- HELPER FUNCTION: Log Rejection (FINN-only)
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.log_rejected_hypothesis(
    p_target_asset TEXT,
    p_model_version TEXT,
    p_eqs_total_score NUMERIC,
    p_eqs_breakdown JSONB,
    p_market_context JSONB,
    p_hypothesis_hash TEXT,
    p_rejection_reason TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $function$
DECLARE
    v_rejection_id UUID;
BEGIN
    INSERT INTO fhq_research.rejected_hypotheses (
        target_asset,
        model_version,
        eqs_total_score,
        eqs_breakdown,
        market_context_snapshot,
        raw_hypothesis_hash,
        rejection_reason
    ) VALUES (
        p_target_asset,
        p_model_version,
        p_eqs_total_score,
        p_eqs_breakdown,
        p_market_context,
        p_hypothesis_hash,
        p_rejection_reason
    ) RETURNING rejection_id INTO v_rejection_id;

    RETURN v_rejection_id;
END;
$function$;

COMMENT ON FUNCTION fhq_research.log_rejected_hypothesis IS
'FINN-only function to log rejected hypotheses to shadow ledger.
CEO Directive: CEO-REJECTION-LEDGER-2025-12-21
Mode: Passive / Evidence-Only';

-- ============================================================================
-- GOVERNANCE LOG
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    agent_id,
    metadata
) VALUES (
    'MIGRATION_EXECUTED',
    'fhq_research.rejected_hypotheses',
    'SCHEMA_CREATION',
    'CEO_DIRECTIVE',
    'APPROVED',
    'CEO-REJECTION-LEDGER-2025-12-21: Passive rejection shadow ledger for EQS < 0.85',
    'STIG',
    jsonb_build_object(
        'migration_id', '166_rejected_hypotheses_shadow_ledger',
        'directive', 'CEO-REJECTION-LEDGER-2025-12-21',
        'mode', 'PASSIVE_EVIDENCE_ONLY',
        'constraints', jsonb_build_array(
            'Write-only for FINN',
            'No learning authorized',
            'No threshold tuning',
            'Data retained indefinitely'
        ),
        'executed_at', NOW()
    )
);

