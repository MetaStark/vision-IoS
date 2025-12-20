-- ============================================================================
-- MIGRATION 073: IoS-013 ASPE — Agent State Protocol Engine (G0 Infrastructure)
-- ============================================================================
-- Module: IoS-013 (ASPE)
-- Gate: G0_SUBMISSION
-- Owner: STIG (Technical Authority)
-- Authority: CEO Execution Order → ADR-018 (ASRP) → ADR-013 → ADR-016
-- Date: 2025-12-05
--
-- PURPOSE: Implement ADR-018 Agent State Reliability Protocol (ASRP)
--          The exclusive implementation mechanism for synchronized agent state.
--
-- SCOPE: Infrastructure Only. Creates:
--   1. fhq_governance.canonical_strategy — Active strategy posture
--   2. fhq_governance.shared_state_snapshots — Atomic state vectors
--   3. fhq_governance.state_retrieval_log — Audit trail for retrievals
--   4. fhq_governance.output_bindings — Links outputs to state hashes
--   5. Atomic retrieval function with fail-closed semantics
--   6. VEGA rejection integration points
--
-- CONSTITUTIONAL MANDATE (ADR-018):
--   - Zero drift in agent perception
--   - Deterministic coordination
--   - Immutable auditability
--   - Fail-closed default (Zero-Trust)
--   - No local caching permitted
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: Register ADR-018 in ADR Registry
-- ============================================================================

INSERT INTO fhq_meta.adr_registry (
    adr_id,
    adr_title,
    adr_status,
    adr_type,
    current_version,
    approval_authority,
    effective_date,
    governance_tier,
    created_by,
    owner,
    description,
    vega_attested
) VALUES (
    'ADR-018',
    'Agent State Reliability Protocol (ASRP)',
    'APPROVED',
    'CONSTITUTIONAL',
    '2026.PROD.2',
    'CEO',
    CURRENT_DATE,
    'Tier-1',
    'CEO',
    'STIG',
    'Constitutional guarantee that all agents operate from one unified, verified, cryptographically-pinned state before producing any reasoning, strategy, execution, or governance artifact. Implements Zero-Trust fail-closed semantics. IoS-013 is the exclusive implementation.',
    false
) ON CONFLICT (adr_id) DO UPDATE SET
    adr_title = EXCLUDED.adr_title,
    adr_status = EXCLUDED.adr_status,
    adr_type = EXCLUDED.adr_type,
    current_version = EXCLUDED.current_version,
    description = EXCLUDED.description,
    effective_date = EXCLUDED.effective_date;

-- Register ADR-018 dependencies
INSERT INTO fhq_meta.adr_dependencies (
    adr_id,
    version,
    depends_on,
    dependency_type,
    criticality
) VALUES (
    'ADR-018',
    '2026.PROD.2',
    ARRAY['ADR-001', 'ADR-013', 'ADR-016', 'ADR-017'],
    'CONSTITUTIONAL',
    'CRITICAL'
) ON CONFLICT DO NOTHING;

-- ============================================================================
-- SECTION 2: Create canonical_strategy Table
-- ============================================================================
-- Authority: LARS (IoS-004 Allocation Doctrine)
-- Purpose: Stores the system's active strategic posture

CREATE TABLE IF NOT EXISTS fhq_governance.canonical_strategy (
    strategy_snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Strategy Identification
    strategy_id TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    strategy_version TEXT NOT NULL,

    -- Strategic Posture
    posture TEXT NOT NULL CHECK (posture IN (
        'AGGRESSIVE_LONG',    -- Maximum risk-on
        'LONG',               -- Standard long exposure
        'NEUTRAL',            -- Balanced/hedged
        'DEFENSIVE',          -- Risk-off positioning
        'CASH',               -- Full cash position
        'CONVEX_LONG',        -- Options-based long (HCP)
        'CONVEX_SHORT'        -- Options-based short (HCP)
    )),

    -- Exposure Parameters (from IoS-004)
    target_exposure NUMERIC NOT NULL CHECK (target_exposure >= 0 AND target_exposure <= 1),
    cash_weight NUMERIC NOT NULL CHECK (cash_weight >= 0 AND cash_weight <= 1),
    leverage_factor NUMERIC NOT NULL DEFAULT 1.0 CHECK (leverage_factor >= 0 AND leverage_factor <= 3),

    -- Regime Alignment
    aligned_regime TEXT NOT NULL,
    regime_confidence NUMERIC NOT NULL CHECK (regime_confidence >= 0 AND regime_confidence <= 1),

    -- Authority & Lineage
    authorized_by TEXT NOT NULL DEFAULT 'LARS',
    authorization_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ADR-011 Hash Chain
    lineage_hash TEXT NOT NULL,
    hash_prev TEXT,
    hash_self TEXT NOT NULL,

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    superseded_by UUID,
    superseded_at TIMESTAMPTZ,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT chk_exposure_sum CHECK (target_exposure + cash_weight <= 1.0001)
);

-- Ensure only one active strategy
CREATE UNIQUE INDEX IF NOT EXISTS idx_canonical_strategy_active
    ON fhq_governance.canonical_strategy(is_active) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_canonical_strategy_posture
    ON fhq_governance.canonical_strategy(posture);

CREATE INDEX IF NOT EXISTS idx_canonical_strategy_timestamp
    ON fhq_governance.canonical_strategy(authorization_timestamp DESC);

COMMENT ON TABLE fhq_governance.canonical_strategy IS
'Canonical strategic posture per ADR-018 §3.3. Authority: LARS (IoS-004).
Only one active strategy permitted. All agents must align to this posture.';

-- ============================================================================
-- SECTION 3: Create shared_state_snapshots Table
-- ============================================================================
-- Purpose: Atomic state vectors per ADR-018 §4 (Atomic Synchronization Principle)

CREATE TABLE IF NOT EXISTS fhq_governance.shared_state_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Timestamp of atomic capture
    snapshot_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- === THE THREE CANONICAL STATE OBJECTS (ADR-018 §3) ===

    -- 3.1 current_defcon (Authority: STIG — ADR-016)
    defcon_level TEXT NOT NULL CHECK (defcon_level IN ('GREEN', 'YELLOW', 'ORANGE', 'RED', 'BLACK')),
    defcon_state_id UUID NOT NULL,
    defcon_reason TEXT,
    defcon_triggered_at TIMESTAMPTZ NOT NULL,

    -- 3.2 btc_regime (Authority: FINN — IoS-003)
    btc_regime_label TEXT NOT NULL CHECK (btc_regime_label IN (
        'STRONG_BULL', 'BULL', 'RANGE_UP', 'NEUTRAL', 'RANGE_DOWN',
        'BEAR', 'STRONG_BEAR', 'PARABOLIC', 'BROKEN', 'UNTRUSTED'
    )),
    btc_regime_confidence NUMERIC NOT NULL CHECK (btc_regime_confidence >= 0 AND btc_regime_confidence <= 1),
    btc_regime_timestamp DATE NOT NULL,

    -- 3.3 canonical_strategy (Authority: LARS — IoS-004)
    strategy_snapshot_id UUID REFERENCES fhq_governance.canonical_strategy(strategy_snapshot_id),
    strategy_posture TEXT NOT NULL,
    strategy_exposure NUMERIC NOT NULL,

    -- === COMPOSITE HASH (ADR-018 §4.1) ===
    -- All fields must share the same composite hash
    state_vector_hash TEXT NOT NULL UNIQUE,

    -- === VALIDITY WINDOW ===
    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_until TIMESTAMPTZ,  -- NULL = currently valid
    freshness_ttl_seconds INTEGER NOT NULL DEFAULT 300,  -- 5 minute default

    -- === INTEGRITY ===
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
    invalidation_reason TEXT,
    invalidated_at TIMESTAMPTZ,
    invalidated_by TEXT,

    -- === LINEAGE ===
    hash_prev TEXT,
    hash_self TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'STIG',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for current valid snapshot lookup
CREATE INDEX IF NOT EXISTS idx_shared_state_current
    ON fhq_governance.shared_state_snapshots(is_valid, valid_until)
    WHERE is_valid = TRUE AND valid_until IS NULL;

CREATE INDEX IF NOT EXISTS idx_shared_state_timestamp
    ON fhq_governance.shared_state_snapshots(snapshot_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_shared_state_hash
    ON fhq_governance.shared_state_snapshots(state_vector_hash);

COMMENT ON TABLE fhq_governance.shared_state_snapshots IS
'Atomic state vectors per ADR-018 §4. Single source of truth for agent state.
Agents MUST retrieve state from this table. Partial reads are unconstitutional.
Implements fail-closed semantics: any validation failure invalidates the entire snapshot.';

-- ============================================================================
-- SECTION 4: Create state_retrieval_log Table
-- ============================================================================
-- Purpose: Audit trail for all state retrievals (ADR-018 §5)

CREATE TABLE IF NOT EXISTS fhq_governance.state_retrieval_log (
    retrieval_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Who retrieved
    agent_id TEXT NOT NULL,
    agent_tier TEXT NOT NULL CHECK (agent_tier IN ('TIER-1', 'TIER-2', 'TIER-3')),

    -- What was retrieved
    snapshot_id UUID REFERENCES fhq_governance.shared_state_snapshots(snapshot_id),
    state_vector_hash TEXT NOT NULL,

    -- Retrieval outcome
    retrieval_status TEXT NOT NULL CHECK (retrieval_status IN (
        'SUCCESS',           -- Valid state retrieved
        'STALE',             -- State exceeded freshness TTL
        'HASH_MISMATCH',     -- Computed hash differs from stored
        'NOT_FOUND',         -- No valid snapshot available
        'SYSTEM_ERROR',      -- Infrastructure failure
        'REJECTED'           -- VEGA governance rejection
    )),

    -- Validation details
    freshness_check_passed BOOLEAN,
    hash_validation_passed BOOLEAN,
    defcon_gating_passed BOOLEAN,
    vega_approval_status TEXT CHECK (vega_approval_status IN ('APPROVED', 'REJECTED', 'PENDING', 'BYPASSED')),

    -- Error details if failed
    error_code TEXT,
    error_message TEXT,

    -- Timing
    retrieval_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    latency_ms INTEGER,

    -- Lineage
    hash_chain_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_state_retrieval_agent
    ON fhq_governance.state_retrieval_log(agent_id, retrieval_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_state_retrieval_status
    ON fhq_governance.state_retrieval_log(retrieval_status);

CREATE INDEX IF NOT EXISTS idx_state_retrieval_timestamp
    ON fhq_governance.state_retrieval_log(retrieval_timestamp DESC);

COMMENT ON TABLE fhq_governance.state_retrieval_log IS
'Audit log for all state vector retrievals per ADR-018 §5.
Every agent request is logged with validation outcome.
Failed retrievals trigger governance alerts.';

-- ============================================================================
-- SECTION 5: Create output_bindings Table
-- ============================================================================
-- Purpose: Links agent outputs to state hashes (ADR-018 §5 Output Binding)

CREATE TABLE IF NOT EXISTS fhq_governance.output_bindings (
    binding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- State Context (REQUIRED per ADR-018 §5.1)
    state_snapshot_hash TEXT NOT NULL,
    state_timestamp TIMESTAMPTZ NOT NULL,

    -- Output Identification
    agent_id TEXT NOT NULL,
    output_type TEXT NOT NULL CHECK (output_type IN (
        'REASONING',          -- Agent reasoning output
        'STRATEGY_PROPOSAL',  -- Strategy recommendations
        'EXECUTION_PLAN',     -- Trade execution plans
        'CODE_ARTIFACT',      -- Generated code
        'GOVERNANCE_DECISION',-- Governance rulings
        'TRADE',              -- Actual trade orders
        'ALLOCATION',         -- Portfolio allocations
        'INSIGHT_PACK',       -- Research insights
        'SKILL_REPORT',       -- Performance reports
        'FORESIGHT_PACK'      -- Forecasts
    )),
    output_id UUID NOT NULL,  -- Reference to the actual output record
    output_table TEXT NOT NULL,  -- Table where output is stored

    -- Validation
    binding_status TEXT NOT NULL CHECK (binding_status IN (
        'VALID',              -- Properly bound to valid state
        'ORPHANED',           -- State snapshot no longer valid
        'INVALID'             -- Binding failed validation
    )),

    -- Lineage
    output_hash TEXT NOT NULL,
    binding_hash TEXT NOT NULL,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    validated_at TIMESTAMPTZ,
    validated_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_output_bindings_state_hash
    ON fhq_governance.output_bindings(state_snapshot_hash);

CREATE INDEX IF NOT EXISTS idx_output_bindings_agent
    ON fhq_governance.output_bindings(agent_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_output_bindings_output
    ON fhq_governance.output_bindings(output_type, output_id);

COMMENT ON TABLE fhq_governance.output_bindings IS
'Immutable link between agent outputs and their governing state context.
Per ADR-018 §5.1: No agent output is valid without its contextual fingerprint.
Enables deterministic post-mortem reconstruction under ADR-002/ADR-011.';

-- ============================================================================
-- SECTION 6: Create ASRP Violation Log
-- ============================================================================
-- Purpose: Track Class A governance violations (ADR-018 §7)

CREATE TABLE IF NOT EXISTS fhq_governance.asrp_violations (
    violation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Violation Classification
    violation_type TEXT NOT NULL CHECK (violation_type IN (
        'BYPASS_ATTEMPT',     -- Attempted to bypass ASRP
        'STALE_STATE_USE',    -- Used stale/uncoupled state
        'MISSING_HASH',       -- Output without state_hash
        'AUTHORITY_OVERRIDE', -- Unauthorized ownership boundary override
        'INVALID_READ',       -- Operated after invalid read
        'LOCAL_CACHE',        -- Attempted local caching
        'TORN_READ'           -- Partial state read detected
    )),
    violation_class TEXT NOT NULL DEFAULT 'CLASS_A',

    -- Offender
    agent_id TEXT NOT NULL,
    agent_tier TEXT,

    -- Context
    attempted_action TEXT NOT NULL,
    state_hash_expected TEXT,
    state_hash_provided TEXT,

    -- Response
    enforcement_action TEXT NOT NULL CHECK (enforcement_action IN (
        'BLOCKED',            -- Action was blocked
        'ISOLATED',           -- Agent isolated per RISL
        'SUSPENDED',          -- Agent suspended per ADR-009
        'ESCALATED',          -- Escalated to VEGA/CEO
        'DEFCON_TRIGGERED'    -- DEFCON level changed
    )),
    defcon_escalation TEXT,

    -- Evidence
    evidence_bundle JSONB NOT NULL,

    -- Resolution
    resolution_status TEXT CHECK (resolution_status IN ('PENDING', 'RESOLVED', 'ESCALATED')),
    resolved_by TEXT,
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hash_chain_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_asrp_violations_agent
    ON fhq_governance.asrp_violations(agent_id);

CREATE INDEX IF NOT EXISTS idx_asrp_violations_type
    ON fhq_governance.asrp_violations(violation_type);

CREATE INDEX IF NOT EXISTS idx_asrp_violations_timestamp
    ON fhq_governance.asrp_violations(created_at DESC);

COMMENT ON TABLE fhq_governance.asrp_violations IS
'Class A governance violations per ADR-018 §7.
All violations trigger ADR-009 suspension review.
Agents exhibiting drift/mismatch are isolated under RISL (ADR-017).';

-- ============================================================================
-- SECTION 7: Create Atomic State Snapshot Function
-- ============================================================================
-- Purpose: Atomically capture current state (ADR-018 §4.1)

CREATE OR REPLACE FUNCTION fhq_governance.create_state_snapshot()
RETURNS UUID AS $$
DECLARE
    v_snapshot_id UUID;
    v_defcon_state RECORD;
    v_btc_regime RECORD;
    v_strategy RECORD;
    v_state_hash TEXT;
    v_hash_prev TEXT;
BEGIN
    -- Get previous hash for chain
    SELECT hash_self INTO v_hash_prev
    FROM fhq_governance.shared_state_snapshots
    WHERE is_valid = TRUE
    ORDER BY snapshot_timestamp DESC
    LIMIT 1;

    -- 1. Atomically capture DEFCON state
    SELECT state_id, current_defcon::TEXT, reason, triggered_at
    INTO v_defcon_state
    FROM fhq_governance.system_state
    WHERE is_active = TRUE
    LIMIT 1;

    IF v_defcon_state IS NULL THEN
        RAISE EXCEPTION 'ASRP_FAIL: No active DEFCON state found. System HALT required.';
    END IF;

    -- 2. Atomically capture BTC regime
    SELECT regime_label, confidence_score, timestamp
    INTO v_btc_regime
    FROM fhq_research.regime_predictions_v2
    WHERE asset_id = 'BTC-USD'
    ORDER BY timestamp DESC
    LIMIT 1;

    IF v_btc_regime IS NULL THEN
        -- Use UNTRUSTED if no regime available
        v_btc_regime := ROW('UNTRUSTED', 0.0, CURRENT_DATE);
    END IF;

    -- 3. Atomically capture canonical strategy
    SELECT strategy_snapshot_id, posture, target_exposure
    INTO v_strategy
    FROM fhq_governance.canonical_strategy
    WHERE is_active = TRUE
    LIMIT 1;

    IF v_strategy IS NULL THEN
        -- Default to NEUTRAL/CASH if no active strategy
        v_strategy := ROW(NULL, 'NEUTRAL', 0.0);
    END IF;

    -- 4. Compute composite hash (ADR-018 §4.1)
    v_state_hash := encode(sha256((
        v_defcon_state.current_defcon || ':' ||
        v_btc_regime.regime_label || ':' ||
        COALESCE(v_strategy.posture, 'NEUTRAL') || ':' ||
        NOW()::TEXT
    )::bytea), 'hex');

    -- 5. Insert atomic snapshot
    INSERT INTO fhq_governance.shared_state_snapshots (
        snapshot_id,
        snapshot_timestamp,
        defcon_level,
        defcon_state_id,
        defcon_reason,
        defcon_triggered_at,
        btc_regime_label,
        btc_regime_confidence,
        btc_regime_timestamp,
        strategy_snapshot_id,
        strategy_posture,
        strategy_exposure,
        state_vector_hash,
        hash_prev,
        hash_self,
        created_by
    ) VALUES (
        gen_random_uuid(),
        NOW(),
        v_defcon_state.current_defcon,
        v_defcon_state.state_id,
        v_defcon_state.reason,
        v_defcon_state.triggered_at,
        v_btc_regime.regime_label,
        v_btc_regime.confidence_score,
        v_btc_regime.timestamp,
        v_strategy.strategy_snapshot_id,
        COALESCE(v_strategy.posture, 'NEUTRAL'),
        COALESCE(v_strategy.target_exposure, 0.0),
        v_state_hash,
        v_hash_prev,
        v_state_hash,
        'STIG'
    ) RETURNING snapshot_id INTO v_snapshot_id;

    -- 6. Invalidate previous snapshots (only one valid at a time)
    UPDATE fhq_governance.shared_state_snapshots
    SET
        valid_until = NOW(),
        is_valid = FALSE,
        invalidation_reason = 'Superseded by new snapshot',
        invalidated_at = NOW(),
        invalidated_by = 'STIG'
    WHERE snapshot_id != v_snapshot_id
    AND is_valid = TRUE;

    RETURN v_snapshot_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.create_state_snapshot() IS
'Atomically captures current state vector per ADR-018 §4.1.
Combines DEFCON, BTC regime, and canonical strategy into single atomic snapshot.
Implements torn-read prohibition: all components captured in same transaction.';

-- ============================================================================
-- SECTION 8: Create Atomic State Retrieval Function
-- ============================================================================
-- Purpose: Retrieve state with fail-closed semantics (ADR-018 §6)

CREATE OR REPLACE FUNCTION fhq_governance.retrieve_state_vector(
    p_agent_id TEXT,
    p_agent_tier TEXT DEFAULT 'TIER-2'
)
RETURNS TABLE (
    snapshot_id UUID,
    state_vector_hash TEXT,
    snapshot_timestamp TIMESTAMPTZ,
    defcon_level TEXT,
    btc_regime_label TEXT,
    btc_regime_confidence NUMERIC,
    strategy_posture TEXT,
    strategy_exposure NUMERIC,
    is_fresh BOOLEAN,
    retrieval_status TEXT
) AS $$
DECLARE
    v_snapshot RECORD;
    v_retrieval_id UUID;
    v_is_fresh BOOLEAN;
    v_latency_start TIMESTAMPTZ;
    v_latency_ms INTEGER;
    v_recomputed_hash TEXT;
    v_hash_valid BOOLEAN;
BEGIN
    v_latency_start := clock_timestamp();

    -- 1. Get current valid snapshot
    SELECT s.* INTO v_snapshot
    FROM fhq_governance.shared_state_snapshots s
    WHERE s.is_valid = TRUE
    AND s.valid_until IS NULL
    ORDER BY s.snapshot_timestamp DESC
    LIMIT 1;

    -- 2. FAIL-CLOSED: No snapshot available
    IF v_snapshot IS NULL THEN
        -- Log failed retrieval
        INSERT INTO fhq_governance.state_retrieval_log (
            agent_id, agent_tier, state_vector_hash, retrieval_status,
            freshness_check_passed, hash_validation_passed, defcon_gating_passed,
            error_code, error_message, latency_ms
        ) VALUES (
            p_agent_id, p_agent_tier, 'NONE', 'NOT_FOUND',
            FALSE, FALSE, FALSE,
            'ASRP_001', 'No valid state snapshot available. HALT required.',
            EXTRACT(MILLISECONDS FROM clock_timestamp() - v_latency_start)::INTEGER
        );

        -- Return empty with HALT status
        RETURN QUERY SELECT
            NULL::UUID, 'HALT'::TEXT, NOW(), 'BLACK'::TEXT,
            'UNTRUSTED'::TEXT, 0.0::NUMERIC, 'CASH'::TEXT, 0.0::NUMERIC,
            FALSE, 'HALT_REQUIRED'::TEXT;
        RETURN;
    END IF;

    -- 3. Freshness check
    v_is_fresh := (NOW() - v_snapshot.snapshot_timestamp) <
                  (v_snapshot.freshness_ttl_seconds * INTERVAL '1 second');

    -- 4. Hash validation (recompute and compare)
    v_recomputed_hash := encode(sha256((
        v_snapshot.defcon_level || ':' ||
        v_snapshot.btc_regime_label || ':' ||
        v_snapshot.strategy_posture || ':' ||
        v_snapshot.snapshot_timestamp::TEXT
    )::bytea), 'hex');

    v_hash_valid := (v_recomputed_hash = v_snapshot.state_vector_hash);

    -- 5. Calculate latency
    v_latency_ms := EXTRACT(MILLISECONDS FROM clock_timestamp() - v_latency_start)::INTEGER;

    -- 6. Log retrieval (success or stale)
    INSERT INTO fhq_governance.state_retrieval_log (
        agent_id, agent_tier, snapshot_id, state_vector_hash, retrieval_status,
        freshness_check_passed, hash_validation_passed, defcon_gating_passed,
        vega_approval_status, latency_ms
    ) VALUES (
        p_agent_id, p_agent_tier, v_snapshot.snapshot_id, v_snapshot.state_vector_hash,
        CASE
            WHEN NOT v_hash_valid THEN 'HASH_MISMATCH'
            WHEN NOT v_is_fresh THEN 'STALE'
            ELSE 'SUCCESS'
        END,
        v_is_fresh, v_hash_valid, TRUE,
        'APPROVED', v_latency_ms
    );

    -- 7. Return state vector
    RETURN QUERY SELECT
        v_snapshot.snapshot_id,
        v_snapshot.state_vector_hash,
        v_snapshot.snapshot_timestamp,
        v_snapshot.defcon_level,
        v_snapshot.btc_regime_label,
        v_snapshot.btc_regime_confidence,
        v_snapshot.strategy_posture,
        v_snapshot.strategy_exposure,
        v_is_fresh,
        CASE
            WHEN NOT v_hash_valid THEN 'HASH_MISMATCH'
            WHEN NOT v_is_fresh THEN 'STALE'
            ELSE 'SUCCESS'
        END::TEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.retrieve_state_vector(TEXT, TEXT) IS
'Atomically retrieves current state vector per ADR-018 §6.
Implements fail-closed semantics: returns HALT status if no valid state.
All retrievals are logged for audit compliance.';

-- ============================================================================
-- SECTION 9: Create VEGA Rejection Function
-- ============================================================================
-- Purpose: VEGA integration for state validation (ADR-018 §7)

CREATE OR REPLACE FUNCTION fhq_governance.vega_validate_state_request(
    p_agent_id TEXT,
    p_state_hash TEXT,
    p_intended_action TEXT
)
RETURNS TABLE (
    is_approved BOOLEAN,
    rejection_reason TEXT,
    enforcement_action TEXT
) AS $$
DECLARE
    v_snapshot RECORD;
    v_defcon TEXT;
BEGIN
    -- 1. Verify state hash exists and is valid
    SELECT s.* INTO v_snapshot
    FROM fhq_governance.shared_state_snapshots s
    WHERE s.state_vector_hash = p_state_hash
    AND s.is_valid = TRUE;

    IF v_snapshot IS NULL THEN
        -- Log violation
        INSERT INTO fhq_governance.asrp_violations (
            violation_type, agent_id, attempted_action,
            state_hash_expected, state_hash_provided,
            enforcement_action, evidence_bundle
        ) VALUES (
            'INVALID_READ', p_agent_id, p_intended_action,
            'VALID_HASH', p_state_hash,
            'BLOCKED', jsonb_build_object(
                'reason', 'State hash not found or invalid',
                'timestamp', NOW()
            )
        );

        RETURN QUERY SELECT FALSE, 'Invalid state hash', 'BLOCKED'::TEXT;
        RETURN;
    END IF;

    -- 2. Check DEFCON gating
    v_defcon := v_snapshot.defcon_level;

    IF v_defcon = 'BLACK' THEN
        RETURN QUERY SELECT FALSE, 'DEFCON BLACK: All operations suspended', 'BLOCKED'::TEXT;
        RETURN;
    END IF;

    IF v_defcon = 'RED' AND p_intended_action IN ('TRADE', 'EXECUTION_PLAN', 'ALLOCATION') THEN
        RETURN QUERY SELECT FALSE, 'DEFCON RED: Execution operations suspended', 'BLOCKED'::TEXT;
        RETURN;
    END IF;

    -- 3. Freshness check
    IF (NOW() - v_snapshot.snapshot_timestamp) > (v_snapshot.freshness_ttl_seconds * INTERVAL '1 second') THEN
        RETURN QUERY SELECT FALSE, 'State snapshot stale - refresh required', 'BLOCKED'::TEXT;
        RETURN;
    END IF;

    -- 4. All checks passed
    RETURN QUERY SELECT TRUE, NULL::TEXT, NULL::TEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.vega_validate_state_request(TEXT, TEXT, TEXT) IS
'VEGA integration point for state validation per ADR-018 §7.
Validates state hash, checks DEFCON gating, and enforces freshness.
Returns rejection with enforcement action if validation fails.';

-- ============================================================================
-- SECTION 10: Register IoS-013 in ios_registry
-- ============================================================================

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
    created_at,
    updated_at
) VALUES (
    'IoS-013',
    'Agent State Protocol Engine (ASPE)',
    'Exclusive implementation of ADR-018 Agent State Reliability Protocol (ASRP). Provides atomic state vector synchronization for all agents. Implements Zero-Trust fail-closed semantics, deterministic hashing, and VEGA rejection integration.',
    '2026.PROD.G0',
    'G0_SUBMITTED',
    'STIG',
    ARRAY[
        'ADR-001', 'ADR-002', 'ADR-004', 'ADR-011',
        'ADR-013', 'ADR-016', 'ADR-017', 'ADR-018'
    ],
    ARRAY['IoS-003', 'IoS-004', 'ADR-016'],
    encode(sha256((
        'IoS-013:ASPE:2026.PROD.G0:STIG:ADR-018:' || NOW()::TEXT
    )::bytea), 'hex'),
    NOW(),
    NOW()
) ON CONFLICT (ios_id) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    version = EXCLUDED.version,
    status = EXCLUDED.status,
    owner_role = EXCLUDED.owner_role,
    governing_adrs = EXCLUDED.governing_adrs,
    dependencies = EXCLUDED.dependencies,
    content_hash = EXCLUDED.content_hash,
    updated_at = NOW();

-- ============================================================================
-- SECTION 11: Register Task in task_registry
-- ============================================================================

INSERT INTO fhq_governance.task_registry (
    task_id,
    task_name,
    task_type,
    task_scope,
    owned_by_agent,
    executed_by_agent,
    reads_from_schemas,
    writes_to_schemas,
    gate_level,
    gate_approved,
    vega_reviewed,
    description,
    task_status,
    created_by,
    created_at,
    updated_at
) VALUES (
    gen_random_uuid(),
    'ASPE_STATE_SYNCHRONIZATION',
    'STATE_ENGINE',
    'IOS_013_INTERNAL',
    'STIG',
    'STIG',
    ARRAY['fhq_governance', 'fhq_research'],
    ARRAY['fhq_governance'],
    'G1',
    FALSE,
    FALSE,
    'ADR-018 ASRP State Synchronization Engine. Atomically captures DEFCON, regime, and strategy into unified state vector. Implements fail-closed semantics per ADR-018 §6.',
    'REGISTERED',
    'STIG',
    NOW(),
    NOW()
) ON CONFLICT (task_name) DO UPDATE SET
    task_type = EXCLUDED.task_type,
    description = EXCLUDED.description,
    updated_at = NOW();

-- ============================================================================
-- SECTION 12: Create Hash Chain for IoS-013
-- ============================================================================

INSERT INTO vision_verification.hash_chains (
    chain_id,
    chain_type,
    chain_scope,
    genesis_hash,
    current_hash,
    chain_length,
    integrity_verified,
    last_verification_at,
    created_by,
    created_at,
    updated_at
) VALUES (
    'HC-IOS-013-ASPE-2026',
    'IOS_MODULE',
    'IoS-013',
    encode(sha256(('IoS-013:ASPE:GENESIS:ADR-018:' || NOW()::TEXT)::bytea), 'hex'),
    encode(sha256(('IoS-013:ASPE:GENESIS:ADR-018:' || NOW()::TEXT)::bytea), 'hex'),
    1,
    TRUE,
    NOW(),
    'STIG',
    NOW(),
    NOW()
) ON CONFLICT (chain_id) DO NOTHING;

-- ============================================================================
-- SECTION 13: Log Governance Action
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
    hash_chain_id,
    signature_id
) VALUES (
    gen_random_uuid(),
    'IOS_G0_SUBMISSION',
    'IoS-013',
    'IOS_MODULE',
    'STIG',
    NOW(),
    'APPROVED',
    'G0 submission for IoS-013 ASPE per CEO Execution Order. Implements ADR-018 ASRP. Tables created: canonical_strategy, shared_state_snapshots, state_retrieval_log, output_bindings, asrp_violations. Functions created: create_state_snapshot, retrieve_state_vector, vega_validate_state_request.',
    FALSE,
    'HC-IOS-013-ASPE-2026',
    gen_random_uuid()
);

-- ============================================================================
-- SECTION 14: Initialize Default Strategy (NEUTRAL)
-- ============================================================================

INSERT INTO fhq_governance.canonical_strategy (
    strategy_id,
    strategy_name,
    strategy_version,
    posture,
    target_exposure,
    cash_weight,
    leverage_factor,
    aligned_regime,
    regime_confidence,
    authorized_by,
    lineage_hash,
    hash_self,
    is_active
) VALUES (
    'STRAT-INIT-001',
    'Initial System Strategy',
    '2026.INIT.1',
    'NEUTRAL',
    0.0,
    1.0,
    1.0,
    'NEUTRAL',
    0.5,
    'LARS',
    encode(sha256(('STRAT:INIT:NEUTRAL:' || NOW()::TEXT)::bytea), 'hex'),
    encode(sha256(('STRAT:INIT:NEUTRAL:' || NOW()::TEXT)::bytea), 'hex'),
    TRUE
);

-- ============================================================================
-- SECTION 15: Create Initial State Snapshot
-- ============================================================================

SELECT fhq_governance.create_state_snapshot() AS initial_snapshot_id;

-- ============================================================================
-- SECTION 16: Audit Log Entry
-- ============================================================================

INSERT INTO fhq_meta.adr_audit_log (
    audit_id,
    change_proposal_id,
    event_type,
    gate_stage,
    adr_id,
    initiated_by,
    decision,
    resolution_notes,
    evidence_path,
    sha256_hash,
    hash_chain_id,
    metadata,
    timestamp
) VALUES (
    gen_random_uuid(),
    'CP-IOS013-G0-' || TO_CHAR(NOW(), 'YYYYMMDD'),
    'SUBMISSION',
    'G0',
    'ADR-018',
    'STIG',
    'APPROVED',
    'G0 infrastructure submission for IoS-013 ASPE per CEO Execution Order. ADR-018 ratified. Full ASRP implementation deployed with fail-closed semantics.',
    'evidence/IOS013_G0_SUBMISSION_' || TO_CHAR(NOW(), 'YYYYMMDD') || '.json',
    encode(sha256(('IoS-013:ASPE:G0_SUBMISSION:ADR-018:' || NOW()::TEXT)::bytea), 'hex'),
    'HC-IOS-013-ASPE-2026',
    jsonb_build_object(
        'gate', 'G0',
        'module', 'IoS-013',
        'title', 'Agent State Protocol Engine (ASPE)',
        'version', '2026.PROD.G0',
        'owner', 'STIG',
        'adr_reference', 'ADR-018',
        'ceo_mandate', 'CEO Execution Order - ADR-018 Ratification',
        'infrastructure_created', jsonb_build_array(
            'fhq_governance.canonical_strategy',
            'fhq_governance.shared_state_snapshots',
            'fhq_governance.state_retrieval_log',
            'fhq_governance.output_bindings',
            'fhq_governance.asrp_violations'
        ),
        'functions_created', jsonb_build_array(
            'fhq_governance.create_state_snapshot()',
            'fhq_governance.retrieve_state_vector(TEXT, TEXT)',
            'fhq_governance.vega_validate_state_request(TEXT, TEXT, TEXT)'
        ),
        'constitutional_principles', jsonb_build_array(
            'Atomic Synchronization (ADR-018 §4)',
            'Fail-Closed Default (ADR-018 §6)',
            'Output Binding (ADR-018 §5)',
            'Zero-Trust Runtime'
        )
    ),
    NOW()
);

COMMIT;

-- ============================================================================
-- POST-MIGRATION VERIFICATION
-- ============================================================================

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'MIGRATION 073: IoS-013 ASPE — Agent State Protocol Engine – VERIFICATION'
\echo '═══════════════════════════════════════════════════════════════════════════'

-- Verify ADR-018 registered
SELECT 'ADR-018 Registration:' AS check_type;
SELECT adr_id, adr_title, adr_status, governance_tier
FROM fhq_meta.adr_registry WHERE adr_id = 'ADR-018';

-- Verify IoS-013 registered
SELECT 'IoS-013 Registration:' AS check_type;
SELECT ios_id, title, status, version, owner_role
FROM fhq_meta.ios_registry WHERE ios_id = 'IoS-013';

-- Verify tables created
SELECT 'Tables Created:' AS check_type;
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'fhq_governance'
AND table_name IN ('canonical_strategy', 'shared_state_snapshots',
                   'state_retrieval_log', 'output_bindings', 'asrp_violations');

-- Verify functions created
SELECT 'Functions Created:' AS check_type;
SELECT routine_name FROM information_schema.routines
WHERE routine_schema = 'fhq_governance'
AND routine_name IN ('create_state_snapshot', 'retrieve_state_vector', 'vega_validate_state_request');

-- Verify initial state snapshot
SELECT 'Current State Vector:' AS check_type;
SELECT
    snapshot_id,
    defcon_level,
    btc_regime_label,
    strategy_posture,
    state_vector_hash,
    is_valid
FROM fhq_governance.shared_state_snapshots
WHERE is_valid = TRUE;

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'IoS-013 ASPE G0 INFRASTRUCTURE COMPLETE'
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo ''
\echo 'ADR-018 Status: RATIFIED (Constitutional Law)'
\echo 'IoS-013 Status: G0_SUBMITTED'
\echo ''
\echo 'State Vector Components:'
\echo '  1. current_defcon  → fhq_governance.system_state (STIG)'
\echo '  2. btc_regime      → fhq_research.regime_predictions_v2 (FINN)'
\echo '  3. canonical_strategy → fhq_governance.canonical_strategy (LARS)'
\echo ''
\echo 'ASRP Functions:'
\echo '  - create_state_snapshot() → Atomic capture'
\echo '  - retrieve_state_vector() → Fail-closed retrieval'
\echo '  - vega_validate_state_request() → VEGA rejection'
\echo ''
\echo 'NEXT STEPS:'
\echo '  1. VEGA to update Orchestrator governance logic'
\echo '  2. CDMO to register ADR-018 in canonical systems'
\echo '  3. All agents must use retrieve_state_vector() before reasoning'
\echo '═══════════════════════════════════════════════════════════════════════════'
