-- ============================================================
-- IoS-012: EXECUTION ENGINE — G1 INFRASTRUCTURE
-- ============================================================
-- Authority: BOARD (Vice-CEO)
-- Technical Lead: STIG (CTO)
-- Operations: LINE
-- Governance: VEGA
-- Classification: Tier-1 Critical
-- Migration: 052_ios012_execution_engine.sql
-- ============================================================
--
-- "The Hand that executes The Will"
--
-- IoS-012 is the ONLY component authorized to interact with exchanges.
-- It ONLY acts on signed DecisionPlans from IoS-008.
-- ============================================================

BEGIN;

-- ============================================================
-- SECTION 1: EXECUTION LOG (Audit Trail)
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_governance.execution_log (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to DecisionPlan
    decision_id UUID NOT NULL,
    decision_hash TEXT NOT NULL,

    -- Verification Results
    signature_verified BOOLEAN NOT NULL,
    ttl_valid BOOLEAN NOT NULL,
    schema_valid BOOLEAN NOT NULL,
    context_hash_valid BOOLEAN NOT NULL,

    -- Security Status
    security_status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (security_status IN ('VERIFIED', 'REJECTED', 'SECURITY_ALERT', 'PENDING')),
    rejection_reason TEXT,

    -- Execution Details
    execution_mode TEXT NOT NULL DEFAULT 'PAPER_MOCK'
        CHECK (execution_mode IN ('PAPER_MOCK', 'PAPER_LIVE', 'LIVE')),
    execution_status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (execution_status IN ('PENDING', 'PROCESSING', 'MOCK_FILLED', 'FILLED', 'REJECTED', 'FAILED')),

    -- Order Details
    asset_id TEXT,
    order_side TEXT CHECK (order_side IN ('BUY', 'SELL', 'HOLD')),
    order_qty NUMERIC,
    order_price NUMERIC,

    -- Position Diff
    current_position NUMERIC,
    target_position NUMERIC,
    position_diff NUMERIC,

    -- Timing
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_at TIMESTAMPTZ,
    executed_at TIMESTAMPTZ,

    -- Latency Metrics
    detection_latency_ms INTEGER,
    verification_latency_ms INTEGER,
    execution_latency_ms INTEGER,

    -- Audit
    created_by TEXT NOT NULL DEFAULT 'IoS-012',
    hash_chain_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_execution_log_decision ON fhq_governance.execution_log(decision_id);
CREATE INDEX IF NOT EXISTS idx_execution_log_security ON fhq_governance.execution_log(security_status);
CREATE INDEX IF NOT EXISTS idx_execution_log_detected ON fhq_governance.execution_log(detected_at);

-- ============================================================
-- SECTION 2: SECURITY ALERTS LOG
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_governance.security_alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type TEXT NOT NULL,
    alert_severity TEXT NOT NULL CHECK (alert_severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    source_module TEXT NOT NULL,
    decision_id UUID,
    description TEXT NOT NULL,
    evidence JSONB,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by TEXT,
    acknowledged_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_security_alerts_type ON fhq_governance.security_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_security_alerts_severity ON fhq_governance.security_alerts(alert_severity);

-- ============================================================
-- SECTION 3: MOCK POSITIONS (Paper Trading State)
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_governance.mock_positions (
    position_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id TEXT NOT NULL UNIQUE,
    quantity NUMERIC NOT NULL DEFAULT 0,
    avg_entry_price NUMERIC,
    market_value NUMERIC,
    unrealized_pnl NUMERIC,
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- Initialize mock positions
INSERT INTO fhq_governance.mock_positions (asset_id, quantity, avg_entry_price)
VALUES
    ('BTC-USD', 0, NULL),
    ('ETH-USD', 0, NULL),
    ('SOL-USD', 0, NULL)
ON CONFLICT (asset_id) DO NOTHING;

-- ============================================================
-- SECTION 4: EXECUTION REPORT GENERATOR
-- ============================================================

CREATE OR REPLACE FUNCTION fhq_governance.generate_mock_execution_report(
    p_decision_id UUID,
    p_asset_id TEXT,
    p_target_allocation NUMERIC,
    p_current_position NUMERIC DEFAULT 0
)
RETURNS TABLE (
    execution_id UUID,
    decision_id UUID,
    asset_id TEXT,
    order_side TEXT,
    position_diff NUMERIC,
    execution_status TEXT,
    mock_fill_price NUMERIC,
    mock_fill_qty NUMERIC
) AS $$
DECLARE
    v_execution_id UUID;
    v_diff NUMERIC;
    v_side TEXT;
    v_mock_price NUMERIC;
BEGIN
    -- Calculate position difference
    v_diff := p_target_allocation - p_current_position;

    -- Determine order side
    IF v_diff > 0.01 THEN
        v_side := 'BUY';
    ELSIF v_diff < -0.01 THEN
        v_side := 'SELL';
    ELSE
        v_side := 'HOLD';
    END IF;

    -- Mock price (would come from market data in live)
    v_mock_price := CASE p_asset_id
        WHEN 'BTC-USD' THEN 95000
        WHEN 'ETH-USD' THEN 3500
        WHEN 'SOL-USD' THEN 230
        ELSE 100
    END;

    -- Generate execution ID
    v_execution_id := gen_random_uuid();

    RETURN QUERY SELECT
        v_execution_id,
        p_decision_id,
        p_asset_id,
        v_side,
        v_diff,
        'MOCK_FILLED'::TEXT,
        v_mock_price,
        ABS(v_diff);
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- SECTION 5: SIGNATURE VERIFICATION STUB
-- ============================================================
-- Note: Actual Ed25519 verification requires Python/cryptography library
-- This stub validates the presence of required fields

CREATE OR REPLACE FUNCTION fhq_governance.verify_decision_plan_schema(
    p_decision_id UUID
)
RETURNS TABLE (
    is_valid BOOLEAN,
    ttl_valid BOOLEAN,
    has_signature BOOLEAN,
    has_context_hash BOOLEAN,
    validation_errors TEXT[]
) AS $$
DECLARE
    v_decision RECORD;
    v_errors TEXT[] := ARRAY[]::TEXT[];
    v_ttl_valid BOOLEAN;
    v_has_sig BOOLEAN;
    v_has_hash BOOLEAN;
BEGIN
    -- Get decision
    SELECT * INTO v_decision
    FROM fhq_governance.decision_log
    WHERE decision_id = p_decision_id;

    IF v_decision IS NULL THEN
        RETURN QUERY SELECT FALSE, FALSE, FALSE, FALSE, ARRAY['Decision not found'];
        RETURN;
    END IF;

    -- Check TTL
    v_ttl_valid := NOW() < v_decision.valid_until;
    IF NOT v_ttl_valid THEN
        v_errors := array_append(v_errors, 'TTL_EXPIRED');
    END IF;

    -- Check signature presence
    v_has_sig := v_decision.governance_signature IS NOT NULL;
    IF NOT v_has_sig THEN
        v_errors := array_append(v_errors, 'MISSING_SIGNATURE');
    END IF;

    -- Check context hash
    v_has_hash := v_decision.context_hash IS NOT NULL AND v_decision.context_hash != '';
    IF NOT v_has_hash THEN
        v_errors := array_append(v_errors, 'MISSING_CONTEXT_HASH');
    END IF;

    RETURN QUERY SELECT
        (v_ttl_valid AND v_has_sig AND v_has_hash),
        v_ttl_valid,
        v_has_sig,
        v_has_hash,
        v_errors;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- SECTION 6: GOVERNANCE LOG
-- ============================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id, action_type, action_target, action_target_type,
    initiated_by, initiated_at, decision, decision_rationale,
    vega_reviewed, vega_override, hash_chain_id
) VALUES (
    gen_random_uuid(),
    'IOS_INITIATION',
    'IoS-012',
    'MODULE',
    'BOARD',
    NOW(),
    'APPROVED',
    'IoS-012 G1 Infrastructure: execution_log, security_alerts, mock_positions, verification functions. PAPER_MOCK mode only.',
    false,
    false,
    'HC-IOS012-G1-001'
);

COMMIT;

-- ============================================================
-- VERIFICATION
-- ============================================================

SELECT 'TABLES' as type, table_name
FROM information_schema.tables
WHERE table_schema = 'fhq_governance'
AND table_name IN ('execution_log', 'security_alerts', 'mock_positions')
ORDER BY table_name;

SELECT 'MOCK_POSITIONS' as type, asset_id, quantity
FROM fhq_governance.mock_positions;
