-- ============================================================================
-- MIGRATION 095: CEIO Shadow Activation
-- ============================================================================
-- Authority: CEO DIRECTIVE 001-CEIO — EXECUTE SHADOW ACTIVATION
-- Executor: STIG (CTO)
-- Date: 2025-12-08
-- Mode: SHADOW_PAPER / DEFCON 5 (GREEN)
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 0: EXTEND EXECUTION MODE CONSTRAINT FOR SHADOW_PAPER
-- ============================================================================

-- Per CEO DIRECTIVE 001-CEIO, add SHADOW_PAPER to valid execution modes
ALTER TABLE fhq_governance.execution_mode
DROP CONSTRAINT IF EXISTS valid_mode_name;

ALTER TABLE fhq_governance.execution_mode
ADD CONSTRAINT valid_mode_name CHECK (
    mode_name IN ('LOCAL_DEV', 'PAPER_PROD', 'LIVE_PROD', 'SHADOW_PAPER')
);

-- ============================================================================
-- SECTION 1: SET EXECUTION MODE TO SHADOW_PAPER
-- ============================================================================

-- Deactivate current mode
UPDATE fhq_governance.execution_mode
SET is_current = false
WHERE is_current = true;

-- Insert new SHADOW_PAPER mode
INSERT INTO fhq_governance.execution_mode (
    mode_id,
    mode_name,
    set_at,
    set_by,
    reason,
    is_current,
    created_at
) VALUES (
    gen_random_uuid(),
    'SHADOW_PAPER',
    NOW(),
    'CEO_DIRECTIVE_001_CEIO',
    'CEIO Shadow Activation per CEO Directive 2025-12-08. Enabling CEIO-driven shadow execution for reinforcement learning on P&L outcomes. DEFCON 5 (GREEN). All CEIO hypotheses logged to shadow_ledger.',
    true,
    NOW()
);

-- ============================================================================
-- SECTION 2: CONFIRM DEFCON 5 (GREEN)
-- ============================================================================

-- Verify DEFCON is GREEN (Level 5)
-- No action needed if already GREEN, just log confirmation
INSERT INTO fhq_governance.defcon_transitions (
    transition_id,
    from_level,
    to_level,
    transition_type,
    reason,
    authorized_by,
    authorization_method,
    evidence_bundle,
    transition_timestamp,
    hash_chain_id
)
SELECT
    gen_random_uuid(),
    'GREEN',
    'GREEN',
    'RESET',
    'CEIO Shadow Activation confirmation: DEFCON 5 (GREEN) maintained for full ACI autonomy per ADR-020.',
    'STIG',
    'CEO',
    '{"directive": "CEO_DIRECTIVE_001_CEIO", "date": "2025-12-08"}'::jsonb,
    NOW(),
    'HC-CEIO-SHADOW-ACTIVATION-20251208'
WHERE EXISTS (SELECT 1 FROM fhq_governance.defcon_state WHERE defcon_level = 'GREEN' AND is_current = true);

-- ============================================================================
-- SECTION 3: CREATE SHADOW LEDGER TABLE (if not exists)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_optimization.shadow_ledger (
    ledger_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- CEIO Context
    ceio_trace_id UUID REFERENCES fhq_optimization.reward_traces(trace_id),
    entropy_snapshot_id UUID REFERENCES fhq_optimization.entropy_snapshots(snapshot_id),

    -- Hypothesis
    hypothesis_id UUID NOT NULL,
    hypothesis_type TEXT NOT NULL,  -- 'ALPHA_SIGNAL', 'REGIME_CALL', 'CORRELATION'
    asset_id TEXT NOT NULL,
    direction TEXT NOT NULL,        -- 'LONG', 'SHORT', 'NEUTRAL'
    confidence NUMERIC(4,3) NOT NULL,

    -- Shadow Execution
    shadow_entry_price NUMERIC(18,8),
    shadow_entry_time TIMESTAMPTZ,
    shadow_exit_price NUMERIC(18,8),
    shadow_exit_time TIMESTAMPTZ,
    shadow_pnl NUMERIC(18,8),
    shadow_return_pct NUMERIC(8,6),

    -- Status
    status TEXT DEFAULT 'OPEN',     -- 'OPEN', 'CLOSED', 'EXPIRED', 'ABORTED'
    exit_reason TEXT,               -- 'TARGET_HIT', 'STOP_LOSS', 'TIME_EXPIRY', 'DEFCON_ESCALATION', 'H_SC_ABORT'

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_direction CHECK (direction IN ('LONG', 'SHORT', 'NEUTRAL')),
    CONSTRAINT valid_status CHECK (status IN ('OPEN', 'CLOSED', 'EXPIRED', 'ABORTED')),
    CONSTRAINT valid_confidence CHECK (confidence >= 0 AND confidence <= 1)
);

CREATE INDEX IF NOT EXISTS idx_shadow_ledger_status ON fhq_optimization.shadow_ledger(status);
CREATE INDEX IF NOT EXISTS idx_shadow_ledger_asset ON fhq_optimization.shadow_ledger(asset_id);
CREATE INDEX IF NOT EXISTS idx_shadow_ledger_ceio ON fhq_optimization.shadow_ledger(ceio_trace_id);

-- ============================================================================
-- SECTION 4: CEIO POLICY ACTIVATION FLAG
-- ============================================================================

-- Add CEIO activation flag to hyperparameters if not exists
ALTER TABLE fhq_optimization.ceio_hyperparameters
ADD COLUMN IF NOT EXISTS is_policy_active BOOLEAN DEFAULT false;

ALTER TABLE fhq_optimization.ceio_hyperparameters
ADD COLUMN IF NOT EXISTS shadow_mode_enabled BOOLEAN DEFAULT false;

-- Activate CEIO as primary policy
UPDATE fhq_optimization.ceio_hyperparameters
SET is_policy_active = true,
    shadow_mode_enabled = true,
    updated_at = NOW()
WHERE is_active = true;

-- ============================================================================
-- SECTION 5: GOVERNANCE LOG - CEIO ACTIVATION
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    vega_reviewed,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'CEIO_SHADOW_ACTIVATION',
    'CEIO_ENGINE',
    'SYSTEM',
    'STIG',
    NOW(),
    'APPROVED',
    'CEO DIRECTIVE 001-CEIO: CEIO Shadow Activation executed. Mode=SHADOW_PAPER, DEFCON=5 (GREEN), shadow_ledger=ACTIVE. CEIO is now primary research policy. H_sc abort at ≥0.80 enforced.',
    false,
    'HC-CEIO-SHADOW-ACTIVATION-20251208'
);

-- Agent notification: VEGA
INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    vega_reviewed,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'AGENT_TASK_ASSIGNMENT',
    'VEGA',
    'AGENT',
    'CEO',
    NOW(),
    'IN_PROGRESS',
    'MANDATORY: Run USD/NOK backtest using alpha_lab.core.historical_simulator to derive true α parameter. Submit CEIO_RISK_REVIEW_202512xx.json upon completion.',
    false,
    'HC-CEIO-SHADOW-ACTIVATION-20251208'
);

-- Agent notification: LINE
INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    vega_reviewed,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'AGENT_TASK_ASSIGNMENT',
    'LINE',
    'AGENT',
    'CEO',
    NOW(),
    'IN_PROGRESS',
    'MANDATORY: IoS-012 continuous SHADOW_PAPER mode. Monitor shadow orders SLA. Submit 7-day Shadow PnL Report.',
    false,
    'HC-CEIO-SHADOW-ACTIVATION-20251208'
);

-- Agent notification: FINN
INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    vega_reviewed,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'AGENT_TASK_ASSIGNMENT',
    'FINN',
    'AGENT',
    'CEO',
    NOW(),
    'IN_PROGRESS',
    'MANDATORY: Validate r_signal metrics for CEIO cycles. Define acceptable boundaries for directionally-correct vs profit-correct signals. Submit Methodology Memo.',
    false,
    'HC-CEIO-SHADOW-ACTIVATION-20251208'
);

COMMIT;

-- ============================================================================
-- MIGRATION COMPLETE
-- Mode: SHADOW_PAPER
-- DEFCON: 5 (GREEN)
-- CEIO: ACTIVE as primary research policy
-- Shadow Ledger: ACTIVE
-- ============================================================================
