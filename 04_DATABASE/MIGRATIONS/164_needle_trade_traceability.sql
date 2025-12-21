-- Migration 164: Canonical Needle → Trade Traceability Restoration
-- CEO Directive: CEO-G5-TRACE-2025-12-21
-- Purpose: Every trade record MUST be traceable to exactly one originating needle_id
-- Scope: trades, shadow_trades, g5_paper_trades
-- Mode: SHADOW / PAPER (Non-Blocking)

-- ============================================================================
-- ARCHITECTURAL INVARIANT (CONSTITUTIONAL)
-- ============================================================================
-- "Every trade record MUST be traceable to exactly one originating needle_id."
-- This applies to: shadow_trades, paper_trades, real_trades
-- There are no exceptions.

-- ============================================================================
-- STEP 1: Add needle_id column to fhq_execution.trades
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_execution'
        AND table_name = 'trades'
        AND column_name = 'needle_id'
    ) THEN
        ALTER TABLE fhq_execution.trades
        ADD COLUMN needle_id UUID;

        COMMENT ON COLUMN fhq_execution.trades.needle_id IS
        'Canonical needle_id from fhq_canonical.golden_needles.
        CEO Directive CEO-G5-TRACE-2025-12-21: Mandatory for traceability.
        Every trade MUST be traceable to exactly one originating needle.';

        RAISE NOTICE 'Added needle_id column to fhq_execution.trades';
    END IF;
END $$;

-- ============================================================================
-- STEP 2: Add needle_id column to fhq_execution.shadow_trades
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_execution'
        AND table_name = 'shadow_trades'
        AND column_name = 'needle_id'
    ) THEN
        ALTER TABLE fhq_execution.shadow_trades
        ADD COLUMN needle_id UUID;

        COMMENT ON COLUMN fhq_execution.shadow_trades.needle_id IS
        'Canonical needle_id from fhq_canonical.golden_needles.
        CEO Directive CEO-G5-TRACE-2025-12-21: Mandatory for traceability.
        Every shadow trade MUST be traceable to exactly one originating needle.';

        RAISE NOTICE 'Added needle_id column to fhq_execution.shadow_trades';
    END IF;
END $$;

-- ============================================================================
-- STEP 3: Verify g5_paper_trades already has needle_id (it does)
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_canonical'
        AND table_name = 'g5_paper_trades'
        AND column_name = 'needle_id'
    ) THEN
        RAISE NOTICE 'g5_paper_trades already has needle_id column - COMPLIANT';
    ELSE
        -- Add if missing (shouldn't happen based on analysis)
        ALTER TABLE fhq_canonical.g5_paper_trades
        ADD COLUMN needle_id UUID;

        RAISE NOTICE 'Added needle_id column to fhq_canonical.g5_paper_trades';
    END IF;
END $$;

-- ============================================================================
-- STEP 4: Create index for efficient needle_id lookups
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_trades_needle_id
ON fhq_execution.trades (needle_id)
WHERE needle_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_shadow_trades_needle_id
ON fhq_execution.shadow_trades (needle_id)
WHERE needle_id IS NOT NULL;

-- ============================================================================
-- STEP 5: Create traceability verification view
-- ============================================================================

CREATE OR REPLACE VIEW fhq_execution.v_needle_trade_traceability AS
SELECT
    'trades' as source_table,
    t.trade_id,
    t.needle_id,
    t.asset_id,
    t.order_side,
    t.fill_status,
    t.created_at,
    CASE WHEN t.needle_id IS NOT NULL THEN TRUE ELSE FALSE END as is_traceable,
    gn.hypothesis_title,
    gn.eqs_score,
    gn.target_asset
FROM fhq_execution.trades t
LEFT JOIN fhq_canonical.golden_needles gn ON t.needle_id = gn.needle_id AND gn.is_current = TRUE

UNION ALL

SELECT
    'shadow_trades' as source_table,
    st.trade_id,
    st.needle_id,
    st.asset_id,
    st.direction as order_side,
    st.status as fill_status,
    st.created_at,
    CASE WHEN st.needle_id IS NOT NULL THEN TRUE ELSE FALSE END as is_traceable,
    gn.hypothesis_title,
    gn.eqs_score,
    gn.target_asset
FROM fhq_execution.shadow_trades st
LEFT JOIN fhq_canonical.golden_needles gn ON st.needle_id = gn.needle_id AND gn.is_current = TRUE

UNION ALL

SELECT
    'g5_paper_trades' as source_table,
    pt.trade_id,
    pt.needle_id,
    pt.symbol as asset_id,
    pt.direction as order_side,
    CASE WHEN pt.exit_timestamp IS NULL THEN 'OPEN' ELSE 'CLOSED' END as fill_status,
    pt.entry_timestamp as created_at,
    CASE WHEN pt.needle_id IS NOT NULL THEN TRUE ELSE FALSE END as is_traceable,
    gn.hypothesis_title,
    gn.eqs_score,
    gn.target_asset
FROM fhq_canonical.g5_paper_trades pt
LEFT JOIN fhq_canonical.golden_needles gn ON pt.needle_id = gn.needle_id AND gn.is_current = TRUE;

COMMENT ON VIEW fhq_execution.v_needle_trade_traceability IS
'CEO Directive CEO-G5-TRACE-2025-12-21: Unified view of needle→trade traceability.
If is_traceable = FALSE, the directive is violated for that record.';

-- ============================================================================
-- STEP 6: Create compliance summary function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_execution.check_traceability_compliance()
RETURNS TABLE (
    source_table TEXT,
    total_records BIGINT,
    traceable_records BIGINT,
    untraceable_records BIGINT,
    compliance_pct NUMERIC,
    is_compliant BOOLEAN
)
LANGUAGE plpgsql
AS $function$
BEGIN
    RETURN QUERY
    SELECT
        v.source_table,
        COUNT(*) as total_records,
        COUNT(*) FILTER (WHERE v.is_traceable = TRUE) as traceable_records,
        COUNT(*) FILTER (WHERE v.is_traceable = FALSE) as untraceable_records,
        ROUND(
            (COUNT(*) FILTER (WHERE v.is_traceable = TRUE)::NUMERIC / NULLIF(COUNT(*), 0)) * 100,
            2
        ) as compliance_pct,
        -- New trades must be 100% traceable
        -- Existing legacy trades are grandfathered but flagged
        CASE
            WHEN COUNT(*) FILTER (WHERE v.is_traceable = FALSE AND v.created_at > '2025-12-21'::DATE) = 0
            THEN TRUE
            ELSE FALSE
        END as is_compliant
    FROM fhq_execution.v_needle_trade_traceability v
    GROUP BY v.source_table;
END;
$function$;

COMMENT ON FUNCTION fhq_execution.check_traceability_compliance() IS
'CEO Directive CEO-G5-TRACE-2025-12-21: Verify needle→trade traceability compliance.
Returns compliance status for each trade table.
New trades (after 2025-12-21) MUST be 100% traceable.';

-- ============================================================================
-- STEP 7: Log migration execution
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
    'fhq_execution.trades, fhq_execution.shadow_trades',
    'SCHEMA_MODIFICATION',
    'CEO_DIRECTIVE',
    'APPROVED',
    'CEO-G5-TRACE-2025-12-21: Adding needle_id columns for canonical traceability',
    'STIG',
    jsonb_build_object(
        'migration_id', '164_needle_trade_traceability',
        'directive', 'CEO-G5-TRACE-2025-12-21',
        'invariant', 'Every trade record MUST be traceable to exactly one originating needle_id',
        'tables_modified', ARRAY['fhq_execution.trades', 'fhq_execution.shadow_trades'],
        'executed_at', NOW()
    )
);

-- ============================================================================
-- VERIFICATION QUERIES (Run after migration)
-- ============================================================================

-- Verify columns exist:
-- SELECT column_name FROM information_schema.columns
-- WHERE table_schema = 'fhq_execution' AND table_name = 'trades' AND column_name = 'needle_id';

-- Check current compliance:
-- SELECT * FROM fhq_execution.check_traceability_compliance();

-- View untraceable trades:
-- SELECT * FROM fhq_execution.v_needle_trade_traceability WHERE is_traceable = FALSE;

