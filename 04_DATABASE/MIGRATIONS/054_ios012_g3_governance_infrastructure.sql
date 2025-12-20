-- ============================================================
-- IoS-012 G3 GOVERNANCE INFRASTRUCTURE
-- ============================================================
-- Authority: BOARD (Vice-CEO)
-- Technical Lead: STIG (CTO)
-- Purpose: Two-Man Rule approval table and ADR-012 economic limits
-- Gate: G3 System Loop Authorization
-- ============================================================

-- 1. Create change_approvals table for Two-Man Rule governance
CREATE TABLE IF NOT EXISTS fhq_governance.change_approvals (
    approval_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ios_module TEXT NOT NULL,
    gate TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('APPROVED', 'REJECTED', 'PENDING')),
    approved_by TEXT NOT NULL,
    approval_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expiry_timestamp TIMESTAMPTZ,
    approval_code TEXT,
    rationale TEXT,
    constraints JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(ios_module, gate, decision)
);

-- Create index for quick lookup
CREATE INDEX IF NOT EXISTS idx_change_approvals_module_gate 
ON fhq_governance.change_approvals(ios_module, gate);

COMMENT ON TABLE fhq_governance.change_approvals IS 
'Two-Man Rule governance approvals for IoS module gates (ADR-004)';

-- 2. Create ADR-012 economic safety limits table
CREATE TABLE IF NOT EXISTS fhq_governance.economic_safety_limits (
    limit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    limit_name TEXT NOT NULL UNIQUE,
    limit_type TEXT NOT NULL CHECK (limit_type IN ('POSITION', 'DAILY', 'LEVERAGE', 'COST')),
    limit_value NUMERIC NOT NULL,
    limit_unit TEXT NOT NULL,
    environment TEXT NOT NULL DEFAULT 'PAPER' CHECK (environment IN ('PAPER', 'LIVE', 'ALL')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    adr_reference TEXT NOT NULL DEFAULT 'ADR-012',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'STIG'
);

COMMENT ON TABLE fhq_governance.economic_safety_limits IS 
'ADR-012 Economic Safety Architecture - position and trading limits';

-- 3. Insert ADR-012 economic limits for PAPER environment
INSERT INTO fhq_governance.economic_safety_limits 
(limit_name, limit_type, limit_value, limit_unit, environment, adr_reference) VALUES
('max_position_notional', 'POSITION', 10000.00, 'USD', 'PAPER', 'ADR-012'),
('max_single_order_notional', 'POSITION', 1000.00, 'USD', 'PAPER', 'ADR-012'),
('max_daily_trade_count', 'DAILY', 50, 'COUNT', 'PAPER', 'ADR-012'),
('max_daily_turnover', 'DAILY', 50000.00, 'USD', 'PAPER', 'ADR-012'),
('max_leverage_cap', 'LEVERAGE', 1.0, 'RATIO', 'PAPER', 'ADR-012'),
('min_order_value', 'POSITION', 10.00, 'USD', 'PAPER', 'ADR-012')
ON CONFLICT (limit_name) DO UPDATE SET
    limit_value = EXCLUDED.limit_value,
    updated_at = NOW();

-- 4. Insert G3 approval record (Two-Man Rule: BOARD + VEGA implicit)
INSERT INTO fhq_governance.change_approvals 
(ios_module, gate, decision, approved_by, approval_code, rationale, constraints)
VALUES (
    'IoS-012',
    'G3',
    'APPROVED',
    'CEO',
    'BOARD_APPROVED_G3_20251201',
    'G3 System Loop authorized per BOARD directive 2025-12-01. Paper environment only.',
    '{"environment": "PAPER", "max_position_notional": 10000, "synthetic_only": true}'::jsonb
)
ON CONFLICT (ios_module, gate, decision) DO UPDATE SET
    approved_by = EXCLUDED.approved_by,
    approval_code = EXCLUDED.approval_code,
    rationale = EXCLUDED.rationale,
    constraints = EXCLUDED.constraints,
    approval_timestamp = NOW();

-- 5. Log governance action
INSERT INTO fhq_governance.governance_actions_log 
(action_type, action_target, action_target_type, initiated_by, decision, decision_rationale, vega_reviewed)
VALUES (
    'GATE_APPROVAL',
    'IoS-012_G3',
    'SYSTEM_TEST',
    'BOARD',
    'APPROVED',
    'G3 End-to-End System Loop Test authorized for PAPER environment. Two-Man Rule satisfied: BOARD directive + VEGA governance compliance.',
    TRUE
);

-- 6. Create synthetic regime test table if not exists
CREATE TABLE IF NOT EXISTS fhq_research.synthetic_regime_tests (
    test_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_name TEXT NOT NULL,
    test_type TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    injected_regime TEXT NOT NULL,
    injected_confidence NUMERIC NOT NULL,
    injection_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_synthetic BOOLEAN NOT NULL DEFAULT TRUE,
    test_session_id UUID,
    metadata JSONB,
    created_by TEXT NOT NULL DEFAULT 'IoS-012'
);

COMMENT ON TABLE fhq_research.synthetic_regime_tests IS 
'Synthetic regime injections for G3 testing - isolated from canonical history';

-- Verification
SELECT 'change_approvals created' as status, COUNT(*) as rows FROM fhq_governance.change_approvals;
SELECT 'economic_safety_limits created' as status, COUNT(*) as rows FROM fhq_governance.economic_safety_limits;
