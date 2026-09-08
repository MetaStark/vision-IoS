-- Migration 188: CEO-DIR-2026-FINN-017 - Production Ramp Infrastructure
-- Classification: GOVERNANCE-CRITICAL (Tier-1)
-- Authority: CEO via ADR-014, ADR-012
-- Date: 2025-12-31
--
-- This migration implements:
-- 1. Directive storage
-- 2. Pamphlet system (PLM) for Teacher/Student knowledge transfer
-- 3. Capital Ledger for tracking paper P&L
-- 4. Auto-triage routing for VEGA
-- 5. Sleep-cycle consolidation infrastructure
-- 6. Integration with ACI triangle (EC-018, EC-020, EC-021, EC-022)

BEGIN;

-- ============================================================================
-- SECTION 1: Store CEO Directive
-- ============================================================================

INSERT INTO fhq_governance.governance_documents (
    document_id,
    document_name,
    document_type,
    tier,
    version,
    content,
    created_at,
    approved_by,
    status
) VALUES (
    gen_random_uuid(),
    'CEO-DIR-2026-FINN-017',
    'CEO_DIRECTIVE',
    1,
    'v1',
    '{
        "directive_id": "CEO-DIR-2026-FINN-017",
        "title": "Production Ramp - Active Verification, State Continuity, and Capital Conversion",
        "classification": "GOVERNANCE-CRITICAL (Tier-1)",
        "status": "MANDATORY_EXECUTION",
        "authority": "CEO via ADR-014, ADR-012",
        "effective_date": "2025-12-31T23:30:00Z",
        "non_negotiables": {
            "vega_active_verification": true,
            "zea_preserved": true,
            "lsa_mandatory": true
        },
        "sections": {
            "lsa_requirements": "LSA must be produced at end of every batch, loaded at start of every run block",
            "pamphlet_system": "Teacher-Student split enforced, pamphlets required for failure/near-miss events",
            "governance_flow": "Auto-triage with proof, VEGA signs all gates, CEO sees only exceptions",
            "capital_ledger": "Dual ledger mandatory - Cognitive + Capital",
            "batch10_redefined": "Steady-State + State Persistence validation"
        }
    }',
    NOW(),
    'CEO',
    'ACTIVE'
);

-- ============================================================================
-- SECTION 2: Pamphlet System (PLM) - Per Section 4
-- Teacher-Student knowledge transfer infrastructure
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.finn_pamphlets (
    pamphlet_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Classification (Section 4.2)
    trigger_type TEXT NOT NULL CHECK (trigger_type IN (
        'DRAWDOWN_EXCURSION',      -- Paper drawdown event
        'MISSED_OPPORTUNITY',      -- Signal present, no action
        'OVER_RETRIEVAL',          -- Waste spike
        'REGIME_TRANSITION',       -- Probability threshold crossed
        'CHAIN_FAILURE',           -- SitC reasoning chain failure
        'HALLUCINATION_BLOCKED',   -- IKEA blocked output
        'COST_OVERRUN'             -- InForage budget breach
    )),

    -- Indexing (Section 4.2)
    regime_tags TEXT[] NOT NULL DEFAULT '{}',
    asset_class TEXT,
    volatility_band TEXT CHECK (volatility_band IN ('LOW', 'MEDIUM', 'HIGH', 'EXTREME')),
    failure_type TEXT,

    -- Content
    trigger_conditions JSONB NOT NULL,
    guidance_text TEXT NOT NULL,
    lesson_summary TEXT,

    -- Metrics
    effectiveness_score NUMERIC(4,3) DEFAULT 0.5,
    usage_count INT DEFAULT 0,
    last_used_at TIMESTAMPTZ,

    -- Provenance (C2PA-style)
    source_batch_id TEXT,
    source_run_number INT,
    generating_agent TEXT NOT NULL DEFAULT 'FINN',
    provenance_hash TEXT NOT NULL,
    signature TEXT,

    -- Lifecycle
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    superseded_by UUID REFERENCES fhq_meta.finn_pamphlets(pamphlet_id),

    -- ACI Triangle Integration
    sitc_chain_id UUID,  -- EC-020 chain that generated this
    inforage_cost_saved NUMERIC(10,4),  -- EC-021 cost optimization
    ikea_classification TEXT  -- EC-022 knowledge boundary
);

-- Indexes for fast retrieval by regime
CREATE INDEX idx_pamphlets_regime ON fhq_meta.finn_pamphlets USING GIN (regime_tags);
CREATE INDEX idx_pamphlets_trigger ON fhq_meta.finn_pamphlets(trigger_type);
CREATE INDEX idx_pamphlets_active ON fhq_meta.finn_pamphlets(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_pamphlets_volatility ON fhq_meta.finn_pamphlets(volatility_band);

-- ============================================================================
-- SECTION 3: Capital Ledger - Per Section 6
-- Dual ledger: Cognitive + Capital
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_execution.capital_ledger (
    ledger_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Run Reference
    batch_id TEXT NOT NULL,
    run_number INT NOT NULL,

    -- Cognitive Ledger (existing metrics)
    rdi NUMERIC(5,4),
    waste_ratio NUMERIC(5,4),
    variance NUMERIC(5,4),
    shadow_alignment NUMERIC(5,4),
    rdi_slope NUMERIC(8,6),

    -- Capital Ledger (Section 6.1) - Paper metrics
    simulated_pnl_usd NUMERIC(12,2),
    simulated_pnl_pct NUMERIC(8,4),
    max_adverse_excursion NUMERIC(8,4),
    max_favorable_excursion NUMERIC(8,4),
    drawdown_proxy NUMERIC(5,4),
    win_rate_proxy NUMERIC(5,4),
    payoff_ratio_proxy NUMERIC(6,3),

    -- Regime-Conditioned Performance
    regime_at_entry TEXT,
    regime_at_exit TEXT,
    regime_mismatch BOOLEAN DEFAULT FALSE,

    -- Safety Gates (Section 6.2)
    tail_loss_breach BOOLEAN DEFAULT FALSE,
    regime_mismatch_event BOOLEAN DEFAULT FALSE,
    bulk_retrieval_relapse BOOLEAN DEFAULT FALSE,

    -- Evidence
    evidence_hash TEXT,
    vega_attestation_id UUID,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_batch_run UNIQUE(batch_id, run_number)
);

CREATE INDEX idx_capital_ledger_batch ON fhq_execution.capital_ledger(batch_id);
CREATE INDEX idx_capital_ledger_breaches ON fhq_execution.capital_ledger(tail_loss_breach, regime_mismatch_event);

-- ============================================================================
-- SECTION 4: Auto-Triage Routing - Per Section 5
-- VEGA always verifies, CEO sees only exceptions
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.vega_triage_rules (
    rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name TEXT NOT NULL UNIQUE,
    rule_description TEXT,

    -- Conditions for CEO escalation
    condition_type TEXT NOT NULL CHECK (condition_type IN (
        'DISCREPANCY_THRESHOLD',
        'CLASS_A_VIOLATION',
        'CLASS_B_VIOLATION',
        'CAPITAL_LEDGER_BREACH',
        'REGIME_MISMATCH',
        'TAIL_LOSS',
        'CUSTOM'
    )),

    -- Threshold values
    threshold_value NUMERIC(10,4),
    comparison_operator TEXT CHECK (comparison_operator IN ('>', '<', '>=', '<=', '=')),

    -- Escalation behavior
    escalate_to_ceo BOOLEAN NOT NULL DEFAULT FALSE,
    auto_pause BOOLEAN NOT NULL DEFAULT FALSE,

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert default triage rules per Section 5.1
INSERT INTO fhq_governance.vega_triage_rules (rule_name, rule_description, condition_type, threshold_value, comparison_operator, escalate_to_ceo, auto_pause) VALUES
('discrepancy_high', 'Escalate when discrepancy score exceeds threshold', 'DISCREPANCY_THRESHOLD', 0.7, '>', TRUE, FALSE),
('class_a_violation', 'Always escalate Class A violations', 'CLASS_A_VIOLATION', NULL, NULL, TRUE, TRUE),
('class_b_violation', 'Escalate Class B violations', 'CLASS_B_VIOLATION', NULL, NULL, TRUE, FALSE),
('capital_breach', 'Escalate capital ledger safety breaches', 'CAPITAL_LEDGER_BREACH', NULL, NULL, TRUE, TRUE),
('tail_loss', 'Escalate tail loss proxy breaches', 'TAIL_LOSS', 0.10, '>', TRUE, TRUE),
('regime_mismatch', 'Escalate regime mismatch events', 'REGIME_MISMATCH', NULL, NULL, TRUE, FALSE);

-- Triage event log
CREATE TABLE IF NOT EXISTS fhq_governance.vega_triage_log (
    triage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Event details
    event_type TEXT NOT NULL,
    event_source TEXT NOT NULL,
    event_data JSONB NOT NULL,

    -- Triage decision
    rule_matched UUID REFERENCES fhq_governance.vega_triage_rules(rule_id),
    escalated_to_ceo BOOLEAN NOT NULL DEFAULT FALSE,
    auto_paused BOOLEAN NOT NULL DEFAULT FALSE,

    -- VEGA attestation
    vega_decision TEXT NOT NULL CHECK (vega_decision IN (
        'ROUTINE_APPROVED',
        'ESCALATED_TO_CEO',
        'AUTO_PAUSED',
        'REJECTED',
        'PENDING_REVIEW'
    )),
    vega_rationale TEXT,
    vega_signature TEXT,

    -- CEO response (if escalated)
    ceo_response TEXT,
    ceo_responded_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_triage_escalated ON fhq_governance.vega_triage_log(escalated_to_ceo) WHERE escalated_to_ceo = TRUE;
CREATE INDEX idx_triage_pending ON fhq_governance.vega_triage_log(vega_decision) WHERE vega_decision = 'PENDING_REVIEW';

-- ============================================================================
-- SECTION 5: Sleep-Cycle Consolidation - Per Section 4.3
-- Daily consolidation of logs into pamphlets
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.sleep_cycle_runs (
    cycle_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Cycle info
    cycle_date DATE NOT NULL,
    cycle_type TEXT NOT NULL CHECK (cycle_type IN ('DAILY', 'WEEKLY', 'MANUAL')),

    -- Input metrics
    logs_processed INT NOT NULL DEFAULT 0,
    patterns_identified INT NOT NULL DEFAULT 0,

    -- Output
    pamphlets_created INT NOT NULL DEFAULT 0,
    pamphlets_pruned INT NOT NULL DEFAULT 0,
    lsa_updated BOOLEAN NOT NULL DEFAULT FALSE,

    -- Timing
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    duration_seconds NUMERIC(10,2),

    -- Status
    status TEXT NOT NULL CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED', 'ABORTED')),
    error_message TEXT,

    -- Evidence
    evidence_hash TEXT,

    CONSTRAINT unique_cycle_date UNIQUE(cycle_date, cycle_type)
);

-- ============================================================================
-- SECTION 6: EC Contract Registry Integration
-- Register the ACI triangle contracts
-- ============================================================================

-- Create EC registry if not exists
CREATE TABLE IF NOT EXISTS fhq_governance.ec_registry (
    ec_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    role_type TEXT NOT NULL,
    parent_executive TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    effective_date DATE NOT NULL,
    authority_chain TEXT[],
    dependencies TEXT[],
    breach_classes JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Register the ACI triangle
INSERT INTO fhq_governance.ec_registry (ec_id, title, role_type, parent_executive, status, effective_date, authority_chain, dependencies) VALUES
('EC-018', 'Meta-Alpha & Freedom Optimizer', 'Tier-2 Cognitive Authority', 'CEO', 'ACTIVE', '2025-12-09',
 ARRAY['ADR-001', 'ADR-003', 'ADR-004', 'ADR-010', 'ADR-012', 'ADR-013', 'ADR-014'],
 ARRAY['EC-020', 'EC-021', 'EC-022']),
('EC-020', 'SitC - Search-in-the-Chain', 'Tier-2 Cognitive Authority (Reasoning)', 'LARS', 'ACTIVE', '2025-12-09',
 ARRAY['ADR-001', 'ADR-007', 'ADR-010', 'ADR-017', 'ADR-021'],
 ARRAY['EC-021', 'EC-022']),
('EC-021', 'InForage - Information Economist', 'Tier-2 Cognitive Authority (Search)', 'FINN', 'ACTIVE', '2025-12-09',
 ARRAY['ADR-001', 'ADR-012', 'ADR-017', 'ADR-021'],
 ARRAY['EC-022']),
('EC-022', 'IKEA - Knowledge Boundary Officer', 'Tier-2 Cognitive Authority (Hallucination Firewall)', 'VEGA', 'ACTIVE', '2025-12-09',
 ARRAY['ADR-001', 'ADR-010', 'ADR-017', 'ADR-021'],
 ARRAY[]::TEXT[])
ON CONFLICT (ec_id) DO UPDATE SET status = 'ACTIVE';

-- ============================================================================
-- SECTION 7: Freedom Metrics Table
-- Per EC-018: Freedom = Alpha Signal Precision / Time Usage
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.freedom_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_date DATE NOT NULL,

    -- Alpha Signal Precision (numerator)
    alpha_precision NUMERIC(5,4),  -- RDI or similar
    signal_accuracy NUMERIC(5,4),
    win_rate NUMERIC(5,4),

    -- Time Usage (denominator) - CEO time
    oversight_minutes INT DEFAULT 0,
    intervention_count INT DEFAULT 0,
    anxiety_score INT CHECK (anxiety_score BETWEEN 1 AND 10),

    -- Computed Freedom Score
    freedom_score NUMERIC(8,4) GENERATED ALWAYS AS (
        CASE WHEN oversight_minutes > 0
        THEN (COALESCE(alpha_precision, 0) * 100) / oversight_minutes
        ELSE NULL END
    ) STORED,

    -- Capital metrics
    capital_usd NUMERIC(12,2),
    daily_pnl_usd NUMERIC(12,2),
    cumulative_pnl_usd NUMERIC(12,2),

    -- Target tracking
    target_capital NUMERIC(12,2) DEFAULT 1000000,  -- $1M freedom target
    progress_pct NUMERIC(8,4) GENERATED ALWAYS AS (
        CASE WHEN target_capital > 0
        THEN (capital_usd / target_capital) * 100
        ELSE 0 END
    ) STORED,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_metric_date UNIQUE(metric_date)
);

-- ============================================================================
-- SECTION 8: Paper Trading Integration
-- Connect to Alpaca Paper Trading
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_execution.alpaca_paper_config (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- API Configuration (encrypted references, not actual keys)
    api_key_reference TEXT NOT NULL,
    api_secret_reference TEXT NOT NULL,
    base_url TEXT NOT NULL DEFAULT 'https://paper-api.alpaca.markets',

    -- Trading Parameters
    max_position_size_pct NUMERIC(5,2) DEFAULT 5.0,  -- Max 5% per position
    max_daily_trades INT DEFAULT 20,
    max_leverage NUMERIC(4,2) DEFAULT 2.0,

    -- Risk Controls
    max_drawdown_pct NUMERIC(5,2) DEFAULT 10.0,
    stop_loss_pct NUMERIC(5,2) DEFAULT 5.0,

    -- Regime Controls
    allowed_regimes TEXT[] DEFAULT ARRAY['RISK_ON', 'TRENDING'],
    forbidden_regimes TEXT[] DEFAULT ARRAY['CRISIS', 'BLACK_SWAN'],

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    last_sync_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Paper trade execution log
CREATE TABLE IF NOT EXISTS fhq_execution.alpaca_paper_trades (
    trade_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Alpaca reference
    alpaca_order_id TEXT,
    alpaca_client_order_id TEXT,

    -- Trade details
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    qty NUMERIC(18,8) NOT NULL,
    order_type TEXT NOT NULL,
    time_in_force TEXT NOT NULL,

    -- Pricing
    limit_price NUMERIC(18,8),
    stop_price NUMERIC(18,8),
    filled_avg_price NUMERIC(18,8),

    -- Status
    status TEXT NOT NULL,
    filled_qty NUMERIC(18,8),

    -- FHQ Signal Reference
    signal_id UUID,
    needle_id UUID,
    decision_id UUID,

    -- Regime at execution
    regime_at_order TEXT,
    regime_check_passed BOOLEAN,

    -- Timestamps
    submitted_at TIMESTAMPTZ NOT NULL,
    filled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_alpaca_trades_symbol ON fhq_execution.alpaca_paper_trades(symbol);
CREATE INDEX idx_alpaca_trades_status ON fhq_execution.alpaca_paper_trades(status);

-- ============================================================================
-- SECTION 9: Audit Trail
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
    metadata,
    agent_id,
    timestamp
) VALUES (
    gen_random_uuid(),
    'MIGRATION_APPLIED',
    'CEO-DIR-2026-FINN-017',
    'CEO_DIRECTIVE',
    'STIG',
    NOW(),
    'EXECUTED',
    'Applied Migration 188: CEO-DIR-2026-FINN-017 Production Ramp Infrastructure - Pamphlets, Capital Ledger, Auto-Triage, Sleep-Cycle, ACI Triangle Integration, Freedom Metrics, Alpaca Paper Trading',
    jsonb_build_object(
        'migration_id', '188',
        'directive', 'CEO-DIR-2026-FINN-017',
        'tables_created', ARRAY[
            'fhq_meta.finn_pamphlets',
            'fhq_execution.capital_ledger',
            'fhq_governance.vega_triage_rules',
            'fhq_governance.vega_triage_log',
            'fhq_meta.sleep_cycle_runs',
            'fhq_governance.ec_registry',
            'fhq_meta.freedom_metrics',
            'fhq_execution.alpaca_paper_config',
            'fhq_execution.alpaca_paper_trades'
        ],
        'aci_triangle', ARRAY['EC-018', 'EC-020', 'EC-021', 'EC-022'],
        'freedom_target', 1000000
    ),
    'STIG',
    NOW()
);

COMMIT;
