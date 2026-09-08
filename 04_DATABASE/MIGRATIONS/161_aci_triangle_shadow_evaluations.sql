-- ============================================================================
-- Migration 161: ACI Triangle Shadow Evaluations Table
-- ============================================================================
-- CEO Directive: CEO-ACI-TRIANGLE-2025-12-21
-- Purpose: Store shadow evaluation results for EC-020, EC-021, EC-022
-- Mode: SHADOW/AUDIT-ONLY (crypto assets only)
-- ============================================================================

BEGIN;

-- Create the shadow evaluations table if not exists
CREATE TABLE IF NOT EXISTS fhq_canonical.aci_triangle_shadow_evaluations (
    evaluation_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    needle_id UUID NOT NULL,

    -- EC-020 SitC: Reasoning Chain Integrity
    sitc_chain_valid BOOLEAN NOT NULL DEFAULT TRUE,
    sitc_failure_reason TEXT,  -- MISSING_PREMISE, CIRCULAR_LOGIC, NON_DETERMINISTIC, etc.
    sitc_chain_hash TEXT,      -- Hash of the reasoning chain if valid

    -- EC-021 InForage: API Budget Discipline
    inforage_cost_usd NUMERIC(10, 6) NOT NULL DEFAULT 0,
    inforage_marginal_cost_per_eqs NUMERIC(10, 6),
    inforage_budget_check_passed BOOLEAN NOT NULL DEFAULT TRUE,

    -- EC-022 IKEA: Hallucination Firewall
    ikea_flagged BOOLEAN NOT NULL DEFAULT FALSE,
    ikea_confidence_score NUMERIC(5, 4) NOT NULL DEFAULT 1.0,
    ikea_flag_reason TEXT,

    -- Shadow mode metadata
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    asset_class TEXT NOT NULL DEFAULT 'CRYPTO',
    mode TEXT NOT NULL DEFAULT 'SHADOW',

    -- Note: No FK constraint - needles may be processed before table sync
    -- Reference: fhq_canonical.golden_needles(needle_id)
    CONSTRAINT check_uuid CHECK (needle_id IS NOT NULL)
);

-- Indexes for telemetry queries
CREATE INDEX IF NOT EXISTS idx_aci_shadow_evaluated_at
    ON fhq_canonical.aci_triangle_shadow_evaluations(evaluated_at DESC);

CREATE INDEX IF NOT EXISTS idx_aci_shadow_sitc_failures
    ON fhq_canonical.aci_triangle_shadow_evaluations(sitc_chain_valid, sitc_failure_reason)
    WHERE sitc_chain_valid = FALSE;

CREATE INDEX IF NOT EXISTS idx_aci_shadow_ikea_flags
    ON fhq_canonical.aci_triangle_shadow_evaluations(ikea_flagged)
    WHERE ikea_flagged = TRUE;

CREATE INDEX IF NOT EXISTS idx_aci_shadow_needle
    ON fhq_canonical.aci_triangle_shadow_evaluations(needle_id);

-- Telemetry view for dashboard
CREATE OR REPLACE VIEW fhq_canonical.v_aci_triangle_telemetry AS
SELECT
    -- EC-020 SitC Summary
    COUNT(*) as total_evaluated,
    COUNT(*) FILTER (WHERE sitc_chain_valid = FALSE) as sitc_broken_chains,
    ROUND(
        COUNT(*) FILTER (WHERE sitc_chain_valid = FALSE)::NUMERIC /
        NULLIF(COUNT(*), 0) * 100, 2
    ) as sitc_broken_chain_rate_pct,

    -- EC-021 InForage Summary
    COALESCE(SUM(inforage_cost_usd), 0) as inforage_total_cost_usd,
    COALESCE(AVG(inforage_cost_usd), 0) as inforage_avg_cost_per_needle,
    50.0 as inforage_budget_cap_usd,  -- CEO directive cap
    ROUND(
        COALESCE(SUM(inforage_cost_usd), 0) / 50.0 * 100, 2
    ) as inforage_budget_pressure_pct,

    -- EC-022 IKEA Summary
    COUNT(*) FILTER (WHERE ikea_flagged = TRUE) as ikea_flagged_count,
    ROUND(
        COUNT(*) FILTER (WHERE ikea_flagged = TRUE)::NUMERIC /
        NULLIF(COUNT(*), 0) * 100, 2
    ) as ikea_fabrication_rate_pct,
    ROUND(AVG(ikea_confidence_score), 4) as ikea_avg_confidence,

    -- Metadata
    'SHADOW' as mode,
    'CRYPTO_ONLY' as asset_filter,
    MAX(evaluated_at) as last_evaluated_at
FROM fhq_canonical.aci_triangle_shadow_evaluations
WHERE evaluated_at > NOW() - INTERVAL '24 hours';

-- Log the migration
INSERT INTO fhq_meta.migration_log (migration_id, description, executed_by)
VALUES (
    161,
    'ACI Triangle Shadow Evaluations table per CEO-ACI-TRIANGLE-2025-12-21',
    'STIG'
)
ON CONFLICT (migration_id) DO NOTHING;

COMMIT;
