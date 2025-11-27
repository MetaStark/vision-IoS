-- ============================================================================
-- ADR-005 HUMAN INTERACTION & APPLICATION LAYER CHARTER
-- ============================================================================
-- Migration: 019_adr005_human_interaction_layer.sql
-- Authority: LARS – Chief Strategy Officer
-- Status: CEO Approved
-- Purpose: Register ADR-005 and establish Human Interaction Layer infrastructure
--
-- ADR-005 establishes:
-- - Vision-IoS Dashboard as the ONLY authorized human interface
-- - CEO as the sole human operator
-- - Hybrid interaction model (data panels + agent chat + control actions)
-- - IoS-XXX Application Layer namespace
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. REGISTER ADR-005 IN ADR REGISTRY
-- ----------------------------------------------------------------------------

INSERT INTO fhq_meta.adr_registry (
    adr_number,
    title,
    status,
    tier,
    scope,
    author,
    purpose,
    authority_chain,
    content_hash,
    approved_by,
    approved_at,
    created_at,
    updated_at
) VALUES (
    'ADR-005',
    'Human Interaction & Application Layer Charter',
    'Approved',
    'Constitutional',
    'CEO, Vision-IoS Dashboard, Orchestrator, VEGA, all agents (LARS, STIG, LINE, FINN, VEGA), fhq_meta, fhq_data, fhq_finn, fhq_validation',
    'LARS',
    'Define the only authorized human interface to FjordHQ – the Vision-IoS Dashboard – and its integration with governance, agents, and the Application Layer (IoS-XXX).',
    'ADR-001 → ADR-002 → ADR-003 → ADR-004 → ADR-006 → ADR-007 → ADR-008 → ADR-009 → ADR-010 → ADR-011 → ADR-012',
    encode(sha256('ADR-005-human-interaction-layer-2025'::bytea), 'hex'),
    'CEO',
    NOW(),
    NOW(),
    NOW()
) ON CONFLICT (adr_number) DO UPDATE SET
    title = EXCLUDED.title,
    status = EXCLUDED.status,
    tier = EXCLUDED.tier,
    scope = EXCLUDED.scope,
    purpose = EXCLUDED.purpose,
    authority_chain = EXCLUDED.authority_chain,
    content_hash = EXCLUDED.content_hash,
    approved_by = EXCLUDED.approved_by,
    approved_at = EXCLUDED.approved_at,
    updated_at = NOW();

-- Verify ADR-005 registration
DO $$
DECLARE
    v_adr_status TEXT;
BEGIN
    SELECT status INTO v_adr_status
    FROM fhq_meta.adr_registry
    WHERE adr_number = 'ADR-005';

    IF v_adr_status != 'Approved' THEN
        RAISE EXCEPTION 'ADR-005 registration failed. Status: %', v_adr_status;
    END IF;

    RAISE NOTICE 'ADR-005 successfully registered with status: %', v_adr_status;
END $$;

-- ----------------------------------------------------------------------------
-- 2. CREATE IoS MODULE REGISTRY TABLE
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS fhq_meta.ios_module_registry (
    module_id VARCHAR(20) PRIMARY KEY,
    module_name VARCHAR(200) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'Active',
    version VARCHAR(20),
    data_lineage JSONB,  -- Array of source tables/views
    action_endpoints JSONB,  -- Registered Orchestrator action endpoints
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(50) DEFAULT 'VEGA',

    CONSTRAINT chk_ios_module_status CHECK (status IN ('Active', 'Inactive', 'Deprecated', 'Planned'))
);

CREATE INDEX IF NOT EXISTS idx_ios_module_status ON fhq_meta.ios_module_registry(status);

-- ----------------------------------------------------------------------------
-- 3. REGISTER IoS MODULES (ADR-005 Section 6.2)
-- ----------------------------------------------------------------------------

INSERT INTO fhq_meta.ios_module_registry (module_id, module_name, description, status, version, data_lineage) VALUES
    ('IoS-001', 'Market Pulse', 'High-level market state, cross-asset freshness, and volatility snapshot', 'Active', '1.0.0',
     '["fhq_data.price_series", "fhq_validation.v_data_freshness"]'::jsonb),
    ('IoS-002', 'Alpha Drift Monitor', 'Monitors strategy performance, drift vs. baselines, and alpha stability', 'Active', '1.0.0',
     '["vision_signals.alpha_signals", "vision_signals.signal_baseline"]'::jsonb),
    ('IoS-003', 'FINN Intelligence v3', 'External narrative, serper events, CDS metrics, narrative shift risk', 'Active', '3.0.0',
     '["fhq_finn.serper_events", "fhq_finn.cds_metrics", "fhq_finn.daily_briefings"]'::jsonb),
    ('IoS-006', 'Research Workspace', 'Agent chat interface for CEO interaction with LARS, FINN, STIG, LINE, VEGA', 'Planned', '0.1.0',
     '["fhq_governance.orchestrator_tasks", "fhq_meta.agent_chat_history"]'::jsonb)
ON CONFLICT (module_id) DO UPDATE SET
    module_name = EXCLUDED.module_name,
    description = EXCLUDED.description,
    status = EXCLUDED.status,
    version = EXCLUDED.version,
    data_lineage = EXCLUDED.data_lineage,
    updated_at = NOW();

-- ----------------------------------------------------------------------------
-- 4. CREATE DASHBOARD ACTION CATEGORIES TABLE (ADR-005 Section 5.3)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS fhq_meta.dashboard_action_categories (
    action_id VARCHAR(100) PRIMARY KEY,
    action_name VARCHAR(200) NOT NULL,
    category CHAR(1) NOT NULL,  -- 'A' = Observational, 'B' = Operational, 'C' = Governance
    description TEXT,
    requires_orchestrator BOOLEAN DEFAULT FALSE,
    requires_vega_check BOOLEAN DEFAULT FALSE,
    requires_gate_approval BOOLEAN DEFAULT FALSE,
    gate_level VARCHAR(5),  -- NULL, 'G1', 'G2', 'G3', 'G4'
    target_agent VARCHAR(50),
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT chk_action_category CHECK (category IN ('A', 'B', 'C')),
    CONSTRAINT chk_action_gate CHECK (gate_level IS NULL OR gate_level IN ('G1', 'G2', 'G3', 'G4'))
);

-- Insert defined actions from ADR-005
INSERT INTO fhq_meta.dashboard_action_categories VALUES
    -- Category A - Observational
    ('show_current_cds', 'Show Current CDS', 'A', 'Display current Cognitive Dissonance Score', FALSE, FALSE, FALSE, NULL, 'FINN', TRUE),
    ('list_finn_events', 'List FINN Events', 'A', 'Display latest FINN serper events', FALSE, FALSE, FALSE, NULL, 'FINN', TRUE),
    ('show_gate_status', 'Show Gate Status', 'A', 'Display G0-G4 gate status', FALSE, FALSE, FALSE, NULL, 'VEGA', TRUE),
    ('show_economic_status', 'Show Economic Safety', 'A', 'Display ADR-012 economic safety metrics', FALSE, FALSE, FALSE, NULL, 'VEGA', TRUE),

    -- Category B - Operational
    ('ingest_binance', 'Ingest Binance Now', 'B', 'Trigger immediate Binance market data ingestion', TRUE, TRUE, FALSE, NULL, 'LINE', TRUE),
    ('run_freshness_tests', 'Re-run Freshness Tests', 'B', 'Execute validation suite on freshness views', TRUE, TRUE, FALSE, NULL, 'STIG', TRUE),
    ('generate_finn_embeddings', 'Generate FINN Embeddings', 'B', 'Refresh research embeddings', TRUE, TRUE, FALSE, NULL, 'FINN', TRUE),
    ('run_reconciliation', 'Run Reconciliation Job', 'B', 'Execute ADR-010 reconciliation workflow', TRUE, TRUE, FALSE, NULL, 'VEGA', TRUE),

    -- Category C - Governance
    ('adjust_cost_ceilings', 'Adjust Cost Ceilings', 'C', 'Propose ADR-012 cost ceiling changes', TRUE, TRUE, TRUE, 'G4', 'VEGA', TRUE),
    ('propose_capital_scenarios', 'Propose Capital Scenarios', 'C', 'Generate LARS/FINN capital calibration scenarios', TRUE, TRUE, TRUE, 'G4', 'LARS', TRUE)
ON CONFLICT (action_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 5. CREATE DASHBOARD AUDIT LOG VIEW
-- ----------------------------------------------------------------------------

CREATE OR REPLACE VIEW fhq_meta.v_dashboard_audit AS
SELECT
    al.id,
    al.event_type,
    al.event_category,
    al.schema_name,
    al.table_name,
    al.record_id,
    al.change_description,
    al.changed_by,
    al.changed_at,
    CASE
        WHEN al.event_category = 'ClassA' THEN 'Governance Critical'
        WHEN al.event_category = 'ClassB' THEN 'Operational'
        WHEN al.event_category = 'ClassC' THEN 'Informational'
        ELSE 'Unknown'
    END AS category_label
FROM fhq_meta.adr_audit_log al
WHERE al.changed_at > NOW() - INTERVAL '7 days'
ORDER BY al.changed_at DESC;

-- ----------------------------------------------------------------------------
-- 6. LOG ADR-005 ACTIVATION IN AUDIT LOG
-- ----------------------------------------------------------------------------

INSERT INTO fhq_meta.adr_audit_log (
    event_type,
    event_category,
    schema_name,
    table_name,
    record_id,
    change_description,
    changed_by,
    changed_at
) VALUES (
    'ADR_ACTIVATION',
    'ClassA',
    'fhq_meta',
    'adr_registry',
    'ADR-005',
    'ADR-005 Human Interaction & Application Layer Charter activated. Vision-IoS Dashboard established as the only authorized human interface to FjordHQ. CEO designated as sole human operator.',
    'VEGA',
    NOW()
);

-- ----------------------------------------------------------------------------
-- 7. UPDATE GOVERNANCE STATE TO REFLECT ADR-005 ACTIVATION
-- ----------------------------------------------------------------------------

UPDATE fhq_governance.governance_state
SET
    current_phase = 'ADR-005_ACTIVATED',
    updated_at = NOW(),
    updated_by = 'VEGA'
WHERE governance_id = 1;

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify ADR-005 registration
SELECT adr_number, title, status, tier, approved_by
FROM fhq_meta.adr_registry
WHERE adr_number = 'ADR-005';

-- Verify IoS modules
SELECT module_id, module_name, status, version
FROM fhq_meta.ios_module_registry
ORDER BY module_id;

-- Verify action categories
SELECT action_id, action_name, category, requires_gate_approval
FROM fhq_meta.dashboard_action_categories
ORDER BY category, action_id;

-- ============================================================================
-- END OF ADR-005 MIGRATION
-- ============================================================================
