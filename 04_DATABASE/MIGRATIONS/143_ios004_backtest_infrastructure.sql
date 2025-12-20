-- ============================================================================
-- Migration 143: IoS-004 Backtest Infrastructure
-- ============================================================================
-- CEO Directive: CD-EC018-IOS004-ALPHA-PIPELINE-001
-- Date: 2025-12-15
-- Purpose: Enable automatic backtest validation of EC-018 alpha hypotheses
--
-- Components:
--   1. g1_validated_signals table - Stores validated alpha signals
--   2. backtest_results table - Detailed backtest metrics
--   3. Database trigger for automatic IoS-004 invocation
--   4. NOTIFY channel for real-time backtest queue
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. G1 VALIDATED SIGNALS TABLE
-- ============================================================================
-- Signals that have passed IoS-004 backtest validation

CREATE TABLE IF NOT EXISTS fhq_alpha.g1_validated_signals (
    signal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_proposal_id UUID NOT NULL REFERENCES fhq_alpha.g0_draft_proposals(proposal_id),
    hypothesis_id TEXT NOT NULL,

    -- Signal metadata
    title TEXT NOT NULL,
    category TEXT NOT NULL,

    -- Validated parameters
    entry_conditions JSONB NOT NULL,
    exit_conditions JSONB NOT NULL,
    regime_filter TEXT[] NOT NULL,

    -- Backtest results summary
    backtest_summary JSONB NOT NULL,
    -- {
    --   "total_signals": int,
    --   "win_rate": float,
    --   "avg_return_bps": float,
    --   "sharpe_ratio": float,
    --   "profit_factor": float,
    --   "max_drawdown_pct": float,
    --   "avg_holding_period_hours": float,
    --   "p_value": float
    -- }

    -- Confidence and meta
    confidence_score DECIMAL(5,4) NOT NULL CHECK (confidence_score BETWEEN 0 AND 1),
    decay_estimate_hours INTEGER,
    correlation_to_existing DECIMAL(5,4),

    -- State binding (ADR-018)
    state_hash_at_validation TEXT NOT NULL,
    defcon_at_validation INTEGER NOT NULL,

    -- Lifecycle
    status TEXT NOT NULL DEFAULT 'VALIDATED' CHECK (status IN (
        'VALIDATED', 'QUEUED_FOR_IOS008', 'IN_IOS008_REVIEW',
        'APPROVED_FOR_EXECUTION', 'EXPIRED', 'SUPERSEDED'
    )),

    -- Timestamps
    validated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    forwarded_to_ios008_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,

    -- Audit
    created_by TEXT DEFAULT 'IoS-004'
);

CREATE INDEX IF NOT EXISTS idx_g1_signals_status ON fhq_alpha.g1_validated_signals(status);
CREATE INDEX IF NOT EXISTS idx_g1_signals_regime ON fhq_alpha.g1_validated_signals USING GIN(regime_filter);
CREATE INDEX IF NOT EXISTS idx_g1_signals_confidence ON fhq_alpha.g1_validated_signals(confidence_score DESC);

-- ============================================================================
-- 2. BACKTEST RESULTS TABLE
-- ============================================================================
-- Detailed backtest results for each hypothesis

CREATE TABLE IF NOT EXISTS fhq_alpha.backtest_results (
    result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES fhq_alpha.g0_draft_proposals(proposal_id),

    -- Backtest parameters
    lookback_days INTEGER NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,

    -- Core metrics
    total_signals INTEGER NOT NULL,
    winning_signals INTEGER NOT NULL,
    losing_signals INTEGER NOT NULL,
    win_rate DECIMAL(5,4) NOT NULL,

    -- Return metrics
    total_return_pct DECIMAL(10,4),
    avg_return_bps DECIMAL(10,4),
    median_return_bps DECIMAL(10,4),
    std_return_bps DECIMAL(10,4),

    -- Risk metrics
    sharpe_ratio DECIMAL(8,4),
    sortino_ratio DECIMAL(8,4),
    profit_factor DECIMAL(8,4),
    max_drawdown_pct DECIMAL(8,4),
    avg_drawdown_pct DECIMAL(8,4),

    -- Timing metrics
    avg_holding_period_hours DECIMAL(10,2),
    max_holding_period_hours DECIMAL(10,2),

    -- Statistical validation
    p_value DECIMAL(10,6),
    t_statistic DECIMAL(10,4),
    is_statistically_significant BOOLEAN GENERATED ALWAYS AS (p_value <= 0.05) STORED,

    -- Outcome
    validation_outcome TEXT NOT NULL CHECK (validation_outcome IN (
        'VALIDATED', 'REJECTED', 'INSUFFICIENT_DATA', 'ERROR'
    )),
    rejection_reason TEXT,

    -- Raw data
    trade_log JSONB,  -- Array of individual trades
    equity_curve JSONB,  -- Time series of cumulative returns

    -- Timestamps
    backtest_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    backtest_completed_at TIMESTAMPTZ,
    duration_seconds DECIMAL(10,2),

    -- Audit
    backtest_version TEXT DEFAULT 'ios004-v1'
);

CREATE INDEX IF NOT EXISTS idx_backtest_proposal ON fhq_alpha.backtest_results(proposal_id);
CREATE INDEX IF NOT EXISTS idx_backtest_outcome ON fhq_alpha.backtest_results(validation_outcome);

-- ============================================================================
-- 3. BACKTEST QUEUE TABLE
-- ============================================================================
-- Queue for pending backtests

CREATE TABLE IF NOT EXISTS fhq_alpha.backtest_queue (
    queue_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES fhq_alpha.g0_draft_proposals(proposal_id),
    priority INTEGER NOT NULL DEFAULT 5,  -- 1=highest, 10=lowest
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN (
        'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'
    )),
    queued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    worker_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_backtest_queue_status ON fhq_alpha.backtest_queue(status, priority, queued_at);

-- ============================================================================
-- 4. TRIGGER FUNCTION FOR AUTO-QUEUE
-- ============================================================================
-- Automatically queue new proposals for backtest

CREATE OR REPLACE FUNCTION fhq_alpha.fn_queue_proposal_for_backtest()
RETURNS TRIGGER AS $$
BEGIN
    -- Insert into backtest queue
    INSERT INTO fhq_alpha.backtest_queue (proposal_id, priority)
    VALUES (NEW.proposal_id, 5);

    -- Send notification to backtest worker
    PERFORM pg_notify('ios004_backtest_queue', json_build_object(
        'proposal_id', NEW.proposal_id,
        'hypothesis_id', NEW.hypothesis_id,
        'category', NEW.hypothesis_category,
        'queued_at', NOW()
    )::text);

    -- Log event
    INSERT INTO fhq_monitoring.system_event_log (event_type, status, metadata)
    VALUES (
        'ios004_backtest_queued',
        'triggered',
        jsonb_build_object(
            'proposal_id', NEW.proposal_id,
            'hypothesis_id', NEW.hypothesis_id,
            'source', 'EC-018',
            'trigger', 'auto_insert'
        )
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 5. CREATE TRIGGER ON G0_DRAFT_PROPOSALS
-- ============================================================================

DROP TRIGGER IF EXISTS trg_g0_proposal_to_ios004 ON fhq_alpha.g0_draft_proposals;

CREATE TRIGGER trg_g0_proposal_to_ios004
    AFTER INSERT ON fhq_alpha.g0_draft_proposals
    FOR EACH ROW
    EXECUTE FUNCTION fhq_alpha.fn_queue_proposal_for_backtest();

-- ============================================================================
-- 6. UPDATE G0_DRAFT_PROPOSALS TABLE
-- ============================================================================
-- Add columns if they don't exist

DO $$
BEGIN
    -- Add entry_conditions if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_alpha'
        AND table_name = 'g0_draft_proposals'
        AND column_name = 'entry_conditions'
    ) THEN
        ALTER TABLE fhq_alpha.g0_draft_proposals ADD COLUMN entry_conditions JSONB;
    END IF;

    -- Add exit_conditions if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_alpha'
        AND table_name = 'g0_draft_proposals'
        AND column_name = 'exit_conditions'
    ) THEN
        ALTER TABLE fhq_alpha.g0_draft_proposals ADD COLUMN exit_conditions JSONB;
    END IF;

    -- Add regime_filter if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_alpha'
        AND table_name = 'g0_draft_proposals'
        AND column_name = 'regime_filter'
    ) THEN
        ALTER TABLE fhq_alpha.g0_draft_proposals ADD COLUMN regime_filter TEXT[];
    END IF;

    -- Add rationale if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_alpha'
        AND table_name = 'g0_draft_proposals'
        AND column_name = 'rationale'
    ) THEN
        ALTER TABLE fhq_alpha.g0_draft_proposals ADD COLUMN rationale TEXT;
    END IF;

    -- Add falsification_criteria if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_alpha'
        AND table_name = 'g0_draft_proposals'
        AND column_name = 'falsification_criteria'
    ) THEN
        ALTER TABLE fhq_alpha.g0_draft_proposals ADD COLUMN falsification_criteria TEXT;
    END IF;
END $$;

-- ============================================================================
-- 7. REGISTER IN ADR REGISTRY
-- ============================================================================

INSERT INTO fhq_meta.adr_registry (
    adr_id, title, status, adr_type, document_path, hash_sha256
) VALUES (
    'IOS-004-G1',
    'IoS-004 Backtest Validation Engine - G1 Activation',
    'ACTIVE',
    'OPERATIONAL',
    '04_DATABASE/MIGRATIONS/143_ios004_backtest_infrastructure.sql',
    encode(sha256('ios004-backtest-infrastructure-v1'::bytea), 'hex')
) ON CONFLICT (adr_id) DO UPDATE SET
    status = 'ACTIVE',
    updated_at = NOW();

-- ============================================================================
-- 8. LOG ACTIVATION EVENT
-- ============================================================================

INSERT INTO fhq_monitoring.system_event_log (event_type, status, metadata)
VALUES (
    'ios004_infrastructure_activated',
    'completed',
    jsonb_build_object(
        'migration', '143_ios004_backtest_infrastructure',
        'tables_created', ARRAY['g1_validated_signals', 'backtest_results', 'backtest_queue'],
        'trigger_created', 'trg_g0_proposal_to_ios004',
        'notify_channel', 'ios004_backtest_queue',
        'timestamp', NOW()
    )
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_tables INTEGER;
    v_trigger BOOLEAN;
BEGIN
    -- Count tables
    SELECT COUNT(*) INTO v_tables
    FROM information_schema.tables
    WHERE table_schema = 'fhq_alpha'
    AND table_name IN ('g1_validated_signals', 'backtest_results', 'backtest_queue');

    -- Check trigger
    SELECT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_g0_proposal_to_ios004'
    ) INTO v_trigger;

    RAISE NOTICE '=== IoS-004 Infrastructure Verification ===';
    RAISE NOTICE 'Tables created: % / 3', v_tables;
    RAISE NOTICE 'Trigger active: %', v_trigger;

    IF v_tables = 3 AND v_trigger THEN
        RAISE NOTICE 'STATUS: SUCCESS - IoS-004 ready for operation';
    ELSE
        RAISE WARNING 'STATUS: INCOMPLETE - Manual verification required';
    END IF;
END $$;
