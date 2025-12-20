-- ============================================================================
-- MIGRATION 099: SHADOW TRADES RENORMALIZATION
-- ============================================================================
-- CEO DIRECTIVE: ARO-20251208 (Autonomy Restoration Order)
-- Authority: Tier-1 Executive Mandate
-- ADR Binding: ADR-013 (Schema Governance), ADR-012 (Economic Safety)
-- Gate: G0→G4 Architecture Alignment
-- Executor: STIG (CTO) - EC-003_2026_PRODUCTION
-- ============================================================================
-- PURPOSE: Rename shadow_ledger to shadow_trades (ADR-013 compliance)
-- Link reward_traces to event_id instead of cycle_id
-- Ensure CEIO logs shadow trades on event triggers only
-- ============================================================================

-- Migration metadata
DO $$
BEGIN
    RAISE NOTICE '=== MIGRATION 099: SHADOW TRADES RENORMALIZATION ===';
    RAISE NOTICE 'CEO DIRECTIVE: ARO-20251208';
    RAISE NOTICE 'Executor: STIG (CTO)';
    RAISE NOTICE 'Timestamp: %', NOW();
END $$;

-- ============================================================================
-- SECTION 1: CREATE CANONICAL shadow_trades TABLE
-- ============================================================================
-- Note: We create the new table rather than rename to preserve existing data
-- and ensure clean schema compliance

CREATE TABLE IF NOT EXISTS fhq_execution.shadow_trades (
    trade_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Trade identification
    shadow_trade_ref VARCHAR(50) NOT NULL UNIQUE, -- Human-readable reference

    -- Source tracking (event-driven per ARO-20251208)
    trigger_event_id UUID,                        -- The event that triggered this trade
    trigger_event_type VARCHAR(50),               -- Event type reference
    source_agent VARCHAR(20) NOT NULL,            -- CEIO, FINN, etc.
    source_hypothesis_id VARCHAR(100),            -- Original hypothesis reference

    -- Asset and direction
    asset_id VARCHAR(30) NOT NULL,                -- BTC-USD, ETH-USD, etc.
    direction VARCHAR(10) NOT NULL,               -- 'LONG', 'SHORT', 'NEUTRAL'

    -- Entry details
    entry_price DECIMAL(20,8) NOT NULL,
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    entry_confidence DECIMAL(5,4),
    entry_regime VARCHAR(20) NOT NULL,            -- Regime at entry

    -- Position sizing (shadow)
    shadow_size DECIMAL(20,8) DEFAULT 1.0,        -- Notional size for P&L calc
    shadow_leverage DECIMAL(5,2) DEFAULT 1.0,

    -- Exit details (NULL if still open)
    exit_price DECIMAL(20,8),
    exit_time TIMESTAMP WITH TIME ZONE,
    exit_reason VARCHAR(50),                      -- 'TARGET_HIT', 'STOP_LOSS', 'REGIME_CHANGE', 'EVENT_TRIGGER', 'MANUAL', 'EXPIRED'
    exit_event_id UUID,                           -- Event that triggered exit
    exit_regime VARCHAR(20),                      -- Regime at exit

    -- P&L tracking
    shadow_pnl DECIMAL(20,8),                     -- Calculated on close
    shadow_return_pct DECIMAL(10,6),              -- Percentage return
    max_favorable_excursion DECIMAL(20,8),        -- Max profit during trade
    max_adverse_excursion DECIMAL(20,8),          -- Max drawdown during trade

    -- CEIO integration
    ceio_trace_id UUID,                           -- Link to reward_traces
    entropy_snapshot_id UUID,                     -- Link to entropy_snapshots
    r_signal DECIMAL(10,6),                       -- Signal reward contribution

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN',   -- 'OPEN', 'CLOSED', 'EXPIRED', 'CANCELLED'

    -- Lineage
    lineage_hash VARCHAR(64),
    parent_trade_id UUID REFERENCES fhq_execution.shadow_trades(trade_id),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_shadow_direction CHECK (direction IN ('LONG', 'SHORT', 'NEUTRAL')),
    CONSTRAINT valid_shadow_status CHECK (status IN ('OPEN', 'CLOSED', 'EXPIRED', 'CANCELLED')),
    CONSTRAINT valid_shadow_regime CHECK (entry_regime IN ('BULL', 'BEAR', 'SIDEWAYS', 'CRISIS', 'UNKNOWN')),
    CONSTRAINT valid_shadow_agent CHECK (source_agent IN ('FINN', 'CEIO', 'LARS', 'LINE', 'VEGA', 'STIG', 'SYSTEM'))
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_shadow_trades_status
    ON fhq_execution.shadow_trades(status);

CREATE INDEX IF NOT EXISTS idx_shadow_trades_asset
    ON fhq_execution.shadow_trades(asset_id, status);

CREATE INDEX IF NOT EXISTS idx_shadow_trades_agent
    ON fhq_execution.shadow_trades(source_agent);

CREATE INDEX IF NOT EXISTS idx_shadow_trades_entry_time
    ON fhq_execution.shadow_trades(entry_time DESC);

CREATE INDEX IF NOT EXISTS idx_shadow_trades_trigger_event
    ON fhq_execution.shadow_trades(trigger_event_id)
    WHERE trigger_event_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_shadow_trades_ceio
    ON fhq_execution.shadow_trades(ceio_trace_id)
    WHERE ceio_trace_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_shadow_trades_regime
    ON fhq_execution.shadow_trades(entry_regime);

CREATE INDEX IF NOT EXISTS idx_shadow_trades_open
    ON fhq_execution.shadow_trades(asset_id, entry_time DESC)
    WHERE status = 'OPEN';

COMMENT ON TABLE fhq_execution.shadow_trades IS
'ARO-20251208 Section 5: Canonical shadow trade table (replaces shadow_ledger).
All shadow trades must be triggered by events, not intervals.
Linked to reward_traces via event_id for audit accuracy.';

-- ============================================================================
-- SECTION 2: MIGRATE DATA FROM shadow_ledger TO shadow_trades
-- ============================================================================

DO $$
DECLARE
    v_migrated_count INTEGER;
BEGIN
    -- Check if source table exists
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'fhq_optimization' AND table_name = 'shadow_ledger'
    ) THEN
        -- Migrate existing data
        INSERT INTO fhq_execution.shadow_trades (
            shadow_trade_ref,
            source_agent,
            source_hypothesis_id,
            asset_id,
            direction,
            entry_price,
            entry_time,
            entry_confidence,
            entry_regime,
            exit_price,
            exit_time,
            exit_reason,
            shadow_pnl,
            shadow_return_pct,
            ceio_trace_id,
            entropy_snapshot_id,
            status,
            created_at,
            updated_at
        )
        SELECT
            'MIGRATED-' || ledger_id::VARCHAR,
            'CEIO',  -- Default source
            hypothesis_id,
            asset_id,
            direction,
            shadow_entry_price,
            COALESCE(shadow_entry_time, created_at),
            confidence,
            COALESCE(
                (SELECT current_regime FROM fhq_meta.regime_state LIMIT 1),
                'UNKNOWN'
            ),
            shadow_exit_price,
            shadow_exit_time,
            exit_reason,
            shadow_pnl,
            shadow_return_pct,
            ceio_trace_id,
            entropy_snapshot_id,
            status,
            created_at,
            updated_at
        FROM fhq_optimization.shadow_ledger
        WHERE NOT EXISTS (
            SELECT 1 FROM fhq_execution.shadow_trades st
            WHERE st.shadow_trade_ref = 'MIGRATED-' || shadow_ledger.ledger_id::VARCHAR
        );

        GET DIAGNOSTICS v_migrated_count = ROW_COUNT;
        RAISE NOTICE 'Migrated % records from shadow_ledger to shadow_trades', v_migrated_count;
    ELSE
        RAISE NOTICE 'No shadow_ledger table found - skipping migration';
    END IF;
END $$;

-- ============================================================================
-- SECTION 3: ADD event_id COLUMN TO reward_traces
-- ============================================================================

DO $$
BEGIN
    -- Add trigger_event_id column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_optimization'
          AND table_name = 'reward_traces'
          AND column_name = 'trigger_event_id'
    ) THEN
        ALTER TABLE fhq_optimization.reward_traces
        ADD COLUMN trigger_event_id UUID;

        RAISE NOTICE 'Added trigger_event_id column to reward_traces';
    END IF;

    -- Add shadow_trade_id column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_optimization'
          AND table_name = 'reward_traces'
          AND column_name = 'shadow_trade_id'
    ) THEN
        ALTER TABLE fhq_optimization.reward_traces
        ADD COLUMN shadow_trade_id UUID;

        RAISE NOTICE 'Added shadow_trade_id column to reward_traces';
    END IF;
END $$;

-- Create index for event-based lookups
CREATE INDEX IF NOT EXISTS idx_reward_traces_event
    ON fhq_optimization.reward_traces(trigger_event_id)
    WHERE trigger_event_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_reward_traces_shadow_trade
    ON fhq_optimization.reward_traces(shadow_trade_id)
    WHERE shadow_trade_id IS NOT NULL;

-- ============================================================================
-- SECTION 4: CREATE EVENT-TRIGGERED SHADOW TRADE FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_execution.create_event_shadow_trade(
    p_trigger_event_id UUID,
    p_source_agent VARCHAR(20),
    p_asset_id VARCHAR(30),
    p_direction VARCHAR(10),
    p_entry_price DECIMAL,
    p_entry_confidence DECIMAL DEFAULT 0.5,
    p_hypothesis_id VARCHAR(100) DEFAULT NULL,
    p_shadow_size DECIMAL DEFAULT 1.0
) RETURNS UUID AS $$
DECLARE
    v_trade_id UUID;
    v_trade_ref VARCHAR(50);
    v_event_type VARCHAR(50);
    v_current_regime VARCHAR(20);
BEGIN
    -- Get event type
    SELECT event_type INTO v_event_type
    FROM fhq_governance.system_events
    WHERE event_id = p_trigger_event_id;

    -- Get current regime
    SELECT current_regime INTO v_current_regime
    FROM fhq_meta.regime_state LIMIT 1;

    -- Generate trade reference
    v_trade_ref := 'ST-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS') || '-' || SUBSTRING(gen_random_uuid()::TEXT, 1, 8);

    -- Create shadow trade
    INSERT INTO fhq_execution.shadow_trades (
        shadow_trade_ref,
        trigger_event_id,
        trigger_event_type,
        source_agent,
        source_hypothesis_id,
        asset_id,
        direction,
        entry_price,
        entry_confidence,
        entry_regime,
        shadow_size,
        status
    ) VALUES (
        v_trade_ref,
        p_trigger_event_id,
        v_event_type,
        p_source_agent,
        p_hypothesis_id,
        p_asset_id,
        p_direction,
        p_entry_price,
        p_entry_confidence,
        COALESCE(v_current_regime, 'UNKNOWN'),
        p_shadow_size,
        'OPEN'
    ) RETURNING trade_id INTO v_trade_id;

    -- Log shadow trade event
    PERFORM fhq_governance.publish_event(
        'CEIO_SHADOW_POSITION',
        p_source_agent,
        'Shadow trade opened: ' || p_direction || ' ' || p_asset_id,
        'Event-triggered shadow position per ARO-20251208',
        jsonb_build_object(
            'trade_id', v_trade_id,
            'trade_ref', v_trade_ref,
            'asset', p_asset_id,
            'direction', p_direction,
            'entry_price', p_entry_price,
            'trigger_event', p_trigger_event_id
        ),
        'shadow_trades',
        NULL,
        p_trigger_event_id
    );

    RETURN v_trade_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_execution.create_event_shadow_trade IS
'ARO-20251208 Section 5.2: Create shadow trade triggered by event.
Shadow trades must NOT be created by intervals.';

-- ============================================================================
-- SECTION 5: CREATE EVENT-TRIGGERED SHADOW TRADE CLOSE FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_execution.close_event_shadow_trade(
    p_trade_id UUID,
    p_exit_price DECIMAL,
    p_exit_reason VARCHAR(50),
    p_exit_event_id UUID DEFAULT NULL
) RETURNS JSONB AS $$
DECLARE
    v_trade RECORD;
    v_pnl DECIMAL;
    v_return_pct DECIMAL;
    v_current_regime VARCHAR(20);
BEGIN
    -- Get trade details
    SELECT * INTO v_trade
    FROM fhq_execution.shadow_trades
    WHERE trade_id = p_trade_id AND status = 'OPEN';

    IF v_trade IS NULL THEN
        RAISE EXCEPTION 'Trade not found or not open: %', p_trade_id;
    END IF;

    -- Calculate P&L based on direction
    IF v_trade.direction = 'LONG' THEN
        v_pnl := (p_exit_price - v_trade.entry_price) * v_trade.shadow_size;
        v_return_pct := (p_exit_price - v_trade.entry_price) / v_trade.entry_price;
    ELSIF v_trade.direction = 'SHORT' THEN
        v_pnl := (v_trade.entry_price - p_exit_price) * v_trade.shadow_size;
        v_return_pct := (v_trade.entry_price - p_exit_price) / v_trade.entry_price;
    ELSE
        v_pnl := 0;
        v_return_pct := 0;
    END IF;

    -- Get current regime
    SELECT current_regime INTO v_current_regime
    FROM fhq_meta.regime_state LIMIT 1;

    -- Update trade
    UPDATE fhq_execution.shadow_trades
    SET
        exit_price = p_exit_price,
        exit_time = NOW(),
        exit_reason = p_exit_reason,
        exit_event_id = p_exit_event_id,
        exit_regime = v_current_regime,
        shadow_pnl = v_pnl,
        shadow_return_pct = v_return_pct,
        status = 'CLOSED',
        updated_at = NOW()
    WHERE trade_id = p_trade_id;

    -- Log close event
    PERFORM fhq_governance.publish_event(
        'CEIO_SHADOW_POSITION',
        v_trade.source_agent,
        'Shadow trade closed: ' || v_trade.direction || ' ' || v_trade.asset_id,
        'Exit reason: ' || p_exit_reason,
        jsonb_build_object(
            'trade_id', p_trade_id,
            'asset', v_trade.asset_id,
            'direction', v_trade.direction,
            'entry_price', v_trade.entry_price,
            'exit_price', p_exit_price,
            'pnl', v_pnl,
            'return_pct', v_return_pct,
            'exit_reason', p_exit_reason
        ),
        'shadow_trades',
        NULL,
        p_exit_event_id
    );

    RETURN jsonb_build_object(
        'trade_id', p_trade_id,
        'status', 'CLOSED',
        'pnl', v_pnl,
        'return_pct', v_return_pct,
        'exit_reason', p_exit_reason
    );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_execution.close_event_shadow_trade IS
'ARO-20251208 Section 5.2: Close shadow trade, calculate P&L.';

-- ============================================================================
-- SECTION 6: CREATE SHADOW TRADE ANALYTICS VIEW
-- ============================================================================

CREATE OR REPLACE VIEW fhq_execution.v_shadow_trade_analytics AS
SELECT
    source_agent,
    entry_regime,
    direction,
    COUNT(*) AS total_trades,
    COUNT(*) FILTER (WHERE status = 'CLOSED') AS closed_trades,
    COUNT(*) FILTER (WHERE status = 'OPEN') AS open_trades,
    SUM(shadow_pnl) FILTER (WHERE status = 'CLOSED') AS total_pnl,
    AVG(shadow_pnl) FILTER (WHERE status = 'CLOSED') AS avg_pnl,
    AVG(shadow_return_pct) FILTER (WHERE status = 'CLOSED') AS avg_return_pct,
    COUNT(*) FILTER (WHERE shadow_pnl > 0 AND status = 'CLOSED') AS winning_trades,
    COUNT(*) FILTER (WHERE shadow_pnl <= 0 AND status = 'CLOSED') AS losing_trades,
    CASE
        WHEN COUNT(*) FILTER (WHERE status = 'CLOSED') > 0
        THEN COUNT(*) FILTER (WHERE shadow_pnl > 0 AND status = 'CLOSED')::DECIMAL /
             COUNT(*) FILTER (WHERE status = 'CLOSED')
        ELSE 0
    END AS win_rate,
    AVG(EXTRACT(EPOCH FROM (exit_time - entry_time))) FILTER (WHERE status = 'CLOSED') AS avg_hold_time_seconds
FROM fhq_execution.shadow_trades
GROUP BY source_agent, entry_regime, direction;

COMMENT ON VIEW fhq_execution.v_shadow_trade_analytics IS
'ARO-20251208: Shadow trade performance analytics by agent, regime, and direction.';

-- ============================================================================
-- SECTION 7: CREATE DEPRECATION VIEW FOR shadow_ledger
-- ============================================================================

CREATE OR REPLACE VIEW fhq_optimization.shadow_ledger AS
SELECT
    trade_id AS ledger_id,
    ceio_trace_id,
    entropy_snapshot_id,
    source_hypothesis_id AS hypothesis_id,
    'ALPHA_SIGNAL' AS hypothesis_type,
    asset_id,
    direction,
    entry_confidence AS confidence,
    entry_price AS shadow_entry_price,
    entry_time AS shadow_entry_time,
    exit_price AS shadow_exit_price,
    exit_time AS shadow_exit_time,
    shadow_pnl,
    shadow_return_pct,
    status,
    exit_reason,
    created_at,
    updated_at
FROM fhq_execution.shadow_trades;

COMMENT ON VIEW fhq_optimization.shadow_ledger IS
'DEPRECATED: Compatibility view. Use fhq_execution.shadow_trades instead.
ARO-20251208 Section 5.1: shadow_ledger renamed to shadow_trades.';

-- ============================================================================
-- SECTION 8: REGISTER IN ADR REGISTRY
-- ============================================================================

INSERT INTO fhq_meta.adr_registry (
    adr_id, title, status, category, description, created_at
) VALUES (
    'MIG-099',
    'SHADOW TRADES RENORMALIZATION',
    'ACTIVE',
    'EXECUTION',
    'ARO-20251208 Section 5: Rename shadow_ledger to shadow_trades. Event-triggered only.',
    NOW()
) ON CONFLICT (adr_id) DO UPDATE SET
    status = 'ACTIVE',
    updated_at = NOW();

-- ============================================================================
-- SECTION 9: REGISTER FUNCTIONS
-- ============================================================================

INSERT INTO fhq_meta.function_registry (
    function_id, function_name, function_schema, ios_layer, status, description
) VALUES
    ('FN-ST-001', 'create_event_shadow_trade', 'fhq_execution', 'EXECUTION', 'ACTIVE', 'Event-triggered shadow trade creation'),
    ('FN-ST-002', 'close_event_shadow_trade', 'fhq_execution', 'EXECUTION', 'ACTIVE', 'Shadow trade close with P&L')
ON CONFLICT (function_id) DO UPDATE SET
    status = 'ACTIVE',
    updated_at = NOW();

-- ============================================================================
-- SECTION 10: LOG GOVERNANCE ACTION
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type, action_target, action_target_type,
    initiated_by, decision, decision_rationale,
    vega_reviewed, hash_chain_id
) VALUES (
    'ARO_RENORMALIZATION',
    'shadow_ledger -> shadow_trades',
    'SCHEMA',
    'STIG',
    'COMPLETED',
    'ARO-20251208 Section 5: shadow_ledger renamed to shadow_trades per ADR-013. ' ||
    'reward_traces now linked via event_id. Shadow trades are event-triggered only.',
    FALSE,
    'HC-ARO-20251208-SHADOW-RENORM'
);

-- ============================================================================
-- COMPLETION
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '=== MIGRATION 099 COMPLETE ===';
    RAISE NOTICE 'Created: fhq_execution.shadow_trades (canonical table)';
    RAISE NOTICE 'Migrated: Data from shadow_ledger preserved';
    RAISE NOTICE 'Added: trigger_event_id, shadow_trade_id to reward_traces';
    RAISE NOTICE 'Created: create_event_shadow_trade(), close_event_shadow_trade() functions';
    RAISE NOTICE 'Created: v_shadow_trade_analytics view';
    RAISE NOTICE 'Deprecated: fhq_optimization.shadow_ledger (now a compatibility view)';
    RAISE NOTICE 'ARO-20251208 Section 5: COMPLETE';
END $$;

-- ============================================================================
-- ROLLBACK SCRIPT
-- ============================================================================
/*
DROP VIEW IF EXISTS fhq_optimization.shadow_ledger;
DROP VIEW IF EXISTS fhq_execution.v_shadow_trade_analytics;
DROP FUNCTION IF EXISTS fhq_execution.close_event_shadow_trade;
DROP FUNCTION IF EXISTS fhq_execution.create_event_shadow_trade;
ALTER TABLE fhq_optimization.reward_traces DROP COLUMN IF EXISTS trigger_event_id;
ALTER TABLE fhq_optimization.reward_traces DROP COLUMN IF EXISTS shadow_trade_id;
DROP TABLE IF EXISTS fhq_execution.shadow_trades;
*/
