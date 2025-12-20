-- ============================================================
-- MIGRATION 061: IoS-013.HCP-LAB - High-Convexity Options Laboratory
-- G0 Submission - CEO Directive
-- Date: 2025-12-01
-- Author: STIG (CTO)
-- ============================================================
--
-- MISSION: "Funding the Escape Velocity"
--
-- This migration establishes the isolated synthetic capital environment
-- for high-convexity options research. ADR-012 Capital Preservation is
-- SUSPENDED for this sandbox; Operational Safety remains ACTIVE.
--
-- Key Principle: "Small capital requires convexity, not leverage."
-- We seek Gamma (acceleration) and Vega (explosion).
-- ============================================================

BEGIN;

-- ============================================================
-- 1. SYNTHETIC LAB NAV - Isolated Virtual Capital
-- ============================================================
-- Initial State: $100,000 (Virtual USD)
-- Isolation: No flow of data or risk against production_nav

CREATE TABLE IF NOT EXISTS fhq_positions.synthetic_lab_nav (
    nav_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date DATE NOT NULL,
    snapshot_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- NAV Components
    starting_nav NUMERIC(18,2) NOT NULL,
    current_nav NUMERIC(18,2) NOT NULL,
    cash_balance NUMERIC(18,2) NOT NULL,
    positions_value NUMERIC(18,2) NOT NULL DEFAULT 0,
    unrealized_pnl NUMERIC(18,2) NOT NULL DEFAULT 0,
    realized_pnl NUMERIC(18,2) NOT NULL DEFAULT 0,

    -- Performance Metrics
    daily_return NUMERIC(10,6),
    cumulative_return NUMERIC(10,6),
    max_drawdown NUMERIC(10,6),

    -- Isolation Verification
    isolation_hash TEXT NOT NULL,  -- Hash proving no production linkage
    production_nav_at_snapshot NUMERIC(18,2),  -- For audit comparison only (READ)

    -- Governance
    created_by TEXT NOT NULL DEFAULT 'STIG',
    hash_chain_id TEXT,

    CONSTRAINT synthetic_lab_nav_unique_date UNIQUE (snapshot_date)
);

COMMENT ON TABLE fhq_positions.synthetic_lab_nav IS
'IoS-013.HCP-LAB: Isolated synthetic capital for high-convexity options research.
ADR-012 Capital Preservation SUSPENDED. Initial NAV: $100,000 virtual.';

-- ============================================================
-- 2. LAB JOURNAL - Immutable Operation Log (ADR-011)
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_positions.lab_journal (
    entry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    entry_type TEXT NOT NULL CHECK (entry_type IN (
        'NAV_INIT', 'STRUCTURE_OPEN', 'STRUCTURE_CLOSE',
        'ADJUSTMENT', 'RISK_EVENT', 'AUDIT_NOTE', 'REGIME_SHIFT'
    )),

    -- Content
    description TEXT NOT NULL,
    nav_before NUMERIC(18,2),
    nav_after NUMERIC(18,2),
    nav_delta NUMERIC(18,2),

    -- Lineage
    related_structure_id UUID,
    risk_envelope_hash TEXT,

    -- Hash Chain (ADR-011 Compliance)
    hash_prev TEXT,
    entry_hash TEXT NOT NULL,

    created_by TEXT NOT NULL DEFAULT 'HCP-LAB'
);

COMMENT ON TABLE fhq_positions.lab_journal IS
'IoS-013.HCP-LAB: Immutable log of synthetic_lab_nav evolution. Hash-chained per ADR-011.';

-- ============================================================
-- 3. STRUCTURE PLAN HCP - Options Structures
-- ============================================================
-- Advanced Structures Permitted:
-- - Ratio Backspreads (Sell 1 ATM / Buy 2 OTM)
-- - Calendar Spreads (Term Structure plays)
-- - Vol-Crush Plays (Short Straddles with wings)

CREATE TABLE IF NOT EXISTS fhq_positions.structure_plan_hcp (
    structure_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Structure Identity
    structure_name TEXT NOT NULL,
    structure_type TEXT NOT NULL CHECK (structure_type IN (
        'LONG_CALL', 'LONG_PUT', 'CALL_SPREAD', 'PUT_SPREAD',
        'RATIO_BACKSPREAD_CALL', 'RATIO_BACKSPREAD_PUT',
        'CALENDAR_SPREAD', 'DIAGONAL_SPREAD',
        'STRADDLE', 'STRANGLE',
        'IRON_CONDOR', 'IRON_BUTTERFLY', 'BUTTERFLY',
        'JADE_LIZARD', 'CUSTOM'
    )),

    -- Underlying
    underlying_symbol TEXT NOT NULL,
    underlying_price_at_entry NUMERIC(12,4),

    -- Legs (JSONB for flexibility)
    -- Format: [{type: 'CALL'|'PUT', strike: X, expiry: 'YYYY-MM-DD',
    --           quantity: N, delta: D, premium: P, iv: IV}]
    legs JSONB NOT NULL,

    -- Risk Profile
    max_profit NUMERIC(18,2),
    max_loss NUMERIC(18,2),  -- NULL = unlimited (ADR-012 suspended for LAB)
    breakeven_points JSONB,  -- Array of prices
    net_premium NUMERIC(18,2),  -- Positive = credit, Negative = debit

    -- Convexity Metrics (THE CORE OF HCP-LAB)
    initial_delta NUMERIC(8,4),
    initial_gamma NUMERIC(8,6),
    initial_vega NUMERIC(8,4),
    initial_theta NUMERIC(8,4),
    convexity_score NUMERIC(6,4),  -- Custom HCP metric: gamma * vega / abs(theta)

    -- Signal Lineage (Precedence Matrix)
    ios003_regime_at_entry TEXT,  -- From IoS-003 HMM
    ios003_regime_confidence NUMERIC(5,4),
    ios007_causal_signal TEXT,    -- From IoS-007 Alpha Graph
    ios007_liquidity_state TEXT,  -- EXPANDING / CONTRACTING
    precedence_applied TEXT,      -- Which rule from Section 3.1 Precedence Matrix

    -- Status
    status TEXT NOT NULL DEFAULT 'PROPOSED' CHECK (status IN (
        'PROPOSED', 'RISK_APPROVED', 'ACTIVE', 'PARTIALLY_CLOSED',
        'CLOSED', 'EXPIRED', 'REJECTED', 'STOPPED_OUT'
    )),

    -- Risk Envelope (Required before execution)
    risk_envelope_id UUID,

    -- Execution
    entry_timestamp TIMESTAMPTZ,
    exit_timestamp TIMESTAMPTZ,
    realized_pnl NUMERIC(18,2),

    -- Governance
    hash_chain_id TEXT,
    created_by TEXT NOT NULL DEFAULT 'FINN'
);

COMMENT ON TABLE fhq_positions.structure_plan_hcp IS
'IoS-013.HCP-LAB: Options structures for high-convexity research.
OTM limits REMOVED. NAV cap REMOVED. Seek Gamma and Vega.';

-- ============================================================
-- 4. RISK ENVELOPE HCP - DeepSeek Pre-Mortem Validation
-- ============================================================
-- Before execution, StructurePlan must pass RiskEnvelope:
-- Prompt: "Simulate 3 scenarios for total loss. Calculate Vol-Crush probability."

CREATE TABLE IF NOT EXISTS fhq_positions.risk_envelope_hcp (
    envelope_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Link to Structure
    structure_id UUID NOT NULL REFERENCES fhq_positions.structure_plan_hcp(structure_id),

    -- Pre-Mortem Scenarios (DeepSeek/FINN output)
    scenario_1_description TEXT NOT NULL,
    scenario_1_probability NUMERIC(5,4),
    scenario_1_loss NUMERIC(18,2),

    scenario_2_description TEXT NOT NULL,
    scenario_2_probability NUMERIC(5,4),
    scenario_2_loss NUMERIC(18,2),

    scenario_3_description TEXT NOT NULL,
    scenario_3_probability NUMERIC(5,4),
    scenario_3_loss NUMERIC(18,2),

    -- Vol-Crush Analysis
    vol_crush_probability NUMERIC(5,4),
    vol_crush_impact NUMERIC(18,2),
    expected_vol_regime TEXT,  -- HIGH_VOL / NORMAL / LOW_VOL / CRUSH_IMMINENT

    -- Combined Risk Score
    total_loss_probability NUMERIC(5,4),
    expected_loss NUMERIC(18,2),
    risk_reward_ratio NUMERIC(8,4),

    -- Approval
    approved BOOLEAN NOT NULL DEFAULT FALSE,
    approval_rationale TEXT,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,

    -- Hash Chain (ADR-011 compliance)
    hash_prev TEXT NOT NULL,
    version_id TEXT NOT NULL,
    envelope_hash TEXT NOT NULL,

    created_by TEXT NOT NULL DEFAULT 'FINN'
);

COMMENT ON TABLE fhq_positions.risk_envelope_hcp IS
'IoS-013.HCP-LAB: DeepSeek pre-mortem validation. Hash-chained per ADR-011.';

-- ============================================================
-- 5. PRECEDENCE MATRIX LOOKUP
-- ============================================================
-- Implements Section 3.1: IoS-007 (Causal) > IoS-003 (Regime)

CREATE TABLE IF NOT EXISTS fhq_positions.hcp_precedence_matrix (
    rule_id SERIAL PRIMARY KEY,
    ios003_price_regime TEXT NOT NULL,      -- BULL / BEAR
    ios007_liquidity_state TEXT NOT NULL,   -- EXPANDING / CONTRACTING
    recommended_action TEXT NOT NULL,
    rationale TEXT NOT NULL,
    convexity_bias TEXT NOT NULL,           -- LONG_GAMMA / SHORT_GAMMA / NEUTRAL

    UNIQUE(ios003_price_regime, ios007_liquidity_state)
);

-- Populate the Precedence Matrix from CEO Directive
INSERT INTO fhq_positions.hcp_precedence_matrix
    (ios003_price_regime, ios007_liquidity_state, recommended_action, rationale, convexity_bias)
VALUES
    ('BULL', 'EXPANDING', 'AGGRESSIVE_LONG_CALL', 'Trend + Fuel aligned', 'LONG_GAMMA'),
    ('BULL', 'CONTRACTING', 'LONG_PUT_OR_BACKSPREAD', 'Divergence = Crash Risk (High Convexity)', 'LONG_GAMMA'),
    ('BEAR', 'CONTRACTING', 'BEAR_PUT_SPREAD', 'Trend + Fuel aligned', 'LONG_GAMMA'),
    ('BEAR', 'EXPANDING', 'CALL_BACKSPREAD', 'Melt-up risk (Short squeeze)', 'LONG_GAMMA')
ON CONFLICT (ios003_price_regime, ios007_liquidity_state) DO NOTHING;

COMMENT ON TABLE fhq_positions.hcp_precedence_matrix IS
'IoS-013.HCP-LAB: Deterministic signal precedence. IoS-007 > IoS-003.';

-- ============================================================
-- 6. INITIALIZE SYNTHETIC LAB NAV
-- ============================================================
-- Initial State: $100,000 Virtual USD

INSERT INTO fhq_positions.synthetic_lab_nav (
    snapshot_date,
    starting_nav,
    current_nav,
    cash_balance,
    positions_value,
    unrealized_pnl,
    realized_pnl,
    daily_return,
    cumulative_return,
    max_drawdown,
    isolation_hash,
    created_by,
    hash_chain_id
) VALUES (
    CURRENT_DATE,
    100000.00,
    100000.00,
    100000.00,
    0.00,
    0.00,
    0.00,
    0.000000,
    0.000000,
    0.000000,
    encode(sha256(('HCP-LAB-GENESIS-' || CURRENT_DATE || '-ISOLATED')::bytea), 'hex'),
    'STIG',
    'HC-HCP-LAB-GENESIS-20251201'
);

-- ============================================================
-- 7. INITIAL LAB JOURNAL ENTRY
-- ============================================================

INSERT INTO fhq_positions.lab_journal (
    entry_type,
    description,
    nav_before,
    nav_after,
    nav_delta,
    hash_prev,
    entry_hash,
    created_by
) VALUES (
    'NAV_INIT',
    'HCP-LAB Genesis: $100,000 virtual capital initialized. ADR-012 Capital Preservation SUSPENDED. Operational Safety ACTIVE. Mission: Funding the Escape Velocity.',
    0.00,
    100000.00,
    100000.00,
    'GENESIS',
    encode(sha256(('HCP-LAB-GENESIS-' || NOW()::text || '-100000')::bytea), 'hex'),
    'STIG'
);

-- ============================================================
-- 8. REGISTER IoS-013.HCP-LAB IN ios_registry
-- ============================================================

INSERT INTO fhq_meta.ios_registry (
    ios_id,
    title,
    description,
    version,
    status,
    owner_role,
    governing_adrs,
    dependencies,
    content_hash,
    experimental_classification,
    risk_multiplier,
    immutability_level,
    canonical,
    modification_requires,
    governance_state,
    hash_chain
) VALUES (
    'IoS-013.HCP-LAB',
    'High-Convexity Options Laboratory',
    'G0 SUBMITTED. Isolated synthetic capital environment ($100k virtual) for high-convexity options research. ADR-012 Capital Preservation SUSPENDED (accept NAV→0). Operational Safety ACTIVE. Implements Precedence Matrix: IoS-007 (Causal) > IoS-003 (Regime). Mission: Small capital requires convexity, not leverage.',
    '2026.LAB.G0',
    'G0_SUBMITTED',
    'LARS',  -- Strategy ownership
    ARRAY['ADR-001', 'ADR-002', 'ADR-003', 'ADR-004', 'ADR-011', 'ADR-012-PARTIAL', 'ADR-013', 'ADR-016'],
    ARRAY['IoS-003', 'IoS-005', 'IoS-007', 'IoS-012'],
    encode(sha256(('IoS-013.HCP-LAB-G0-' || NOW()::text)::bytea), 'hex'),
    'HIGH_RISK_SANDBOX',
    0.00,  -- Risk multiplier 0 = no production capital at risk
    'MUTABLE',
    false,
    'G1-G4 Full Cycle (ADR-004)',
    'G0_SUBMITTED',
    'HC-HCP-LAB-20251201'
);

-- ============================================================
-- 9. LOG GOVERNANCE ACTION
-- ============================================================

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
    vega_override,
    vega_notes,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'CEO_DIRECTIVE_REGISTRATION',
    'IoS-013.HCP-LAB',
    'IOS_MODULE',
    'CEO',
    NOW(),
    'APPROVED',
    'CEO Directive: Register IoS-013.HCP-LAB as G0. High-Convexity Options Laboratory for synthetic capital research. ADR-012 Capital Preservation SUSPENDED per Section 2.4. Operational Safety remains ACTIVE.',
    false,
    false,
    'Pending VEGA G1 review. ADR-012 partial suspension requires governance attestation.',
    'HC-CEO-HCP-LAB-20251201'
);

-- ============================================================
-- 10. INDEXES FOR PERFORMANCE
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_structure_plan_hcp_status
    ON fhq_positions.structure_plan_hcp(status);

CREATE INDEX IF NOT EXISTS idx_structure_plan_hcp_underlying
    ON fhq_positions.structure_plan_hcp(underlying_symbol);

CREATE INDEX IF NOT EXISTS idx_lab_journal_timestamp
    ON fhq_positions.lab_journal(entry_timestamp);

CREATE INDEX IF NOT EXISTS idx_lab_journal_type
    ON fhq_positions.lab_journal(entry_type);

COMMIT;

-- ============================================================
-- VERIFICATION QUERIES
-- ============================================================
SELECT 'IoS-013.HCP-LAB G0 Registration Complete' as status;
SELECT ios_id, title, version, status, governance_state
FROM fhq_meta.ios_registry WHERE ios_id = 'IoS-013.HCP-LAB';
SELECT * FROM fhq_positions.synthetic_lab_nav;
SELECT * FROM fhq_positions.hcp_precedence_matrix;
