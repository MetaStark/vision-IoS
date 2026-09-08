-- Migration 297: B4 Orphaned Forecast Resolution
-- Authority: CEO-DIR-2026-064
-- Gate: ADR-004 APPROVED
-- Executed by: STIG
-- Date: 2026-01-17

BEGIN;

-- C4.3.1: Orphan Analysis Runs
CREATE TABLE IF NOT EXISTS fhq_research.orphan_analysis_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_timestamp TIMESTAMPTZ DEFAULT NOW(),
    orphaned_before INTEGER,
    resolved_count INTEGER,
    orphaned_after INTEGER,
    resolution_rate NUMERIC,
    evidence_ref TEXT
);

-- C4.3.2: Forecast Resolution Log
CREATE TABLE IF NOT EXISTS fhq_research.forecast_resolution_log (
    resolution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES fhq_research.orphan_analysis_runs(run_id),
    forecast_id UUID NOT NULL,
    resolution_type VARCHAR(20) CHECK (resolution_type IN ('MATCHED', 'EXPIRED', 'INVALIDATED', 'MANUAL')),
    matched_outcome_id UUID,
    match_confidence NUMERIC,
    resolution_reason TEXT,
    resolved_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_frl_forecast_id ON fhq_research.forecast_resolution_log(forecast_id);
CREATE INDEX IF NOT EXISTS idx_frl_run_id ON fhq_research.forecast_resolution_log(run_id);

-- C4.3.3: Resolution Function
CREATE OR REPLACE FUNCTION fhq_research.fn_resolve_orphaned_forecasts(
    p_match_threshold NUMERIC DEFAULT 0.8
) RETURNS UUID AS $$
DECLARE
    v_run_id UUID;
    v_orphaned_before INTEGER;
    v_resolved INTEGER := 0;
BEGIN
    -- Count orphans before
    SELECT count(*) INTO v_orphaned_before
    FROM fhq_research.forecast_ledger fl
    LEFT JOIN fhq_research.forecast_outcome_pairs fop ON fl.forecast_id = fop.forecast_id
    WHERE fop.pair_id IS NULL;

    -- Create run
    INSERT INTO fhq_research.orphan_analysis_runs (orphaned_before)
    VALUES (v_orphaned_before)
    RETURNING run_id INTO v_run_id;

    -- Attempt matching based on domain and time proximity
    WITH potential_matches AS (
        SELECT DISTINCT ON (fl.forecast_id)
            fl.forecast_id,
            ol.outcome_id,
            fl.domain,
            ol.outcome_type,
            CASE
                WHEN fl.domain = ol.outcome_type
                AND ABS(EXTRACT(EPOCH FROM (ol.captured_at - fl.forecast_time))) < 86400
                THEN 0.9
                WHEN fl.domain = ol.outcome_type THEN 0.7
                ELSE 0.5
            END AS match_score
        FROM fhq_research.forecast_ledger fl
        LEFT JOIN fhq_research.forecast_outcome_pairs fop ON fl.forecast_id = fop.forecast_id
        CROSS JOIN LATERAL (
            SELECT * FROM fhq_research.outcome_ledger ol2
            WHERE ol2.captured_at > fl.forecast_time
            ORDER BY ABS(EXTRACT(EPOCH FROM (ol2.captured_at - fl.forecast_time)))
            LIMIT 5
        ) ol
        WHERE fop.pair_id IS NULL
        ORDER BY fl.forecast_id, match_score DESC
    )
    INSERT INTO fhq_research.forecast_resolution_log (
        run_id, forecast_id, resolution_type, matched_outcome_id, match_confidence, resolution_reason
    )
    SELECT
        v_run_id,
        forecast_id,
        'MATCHED',
        outcome_id,
        match_score,
        'Auto-matched by domain and time proximity'
    FROM potential_matches
    WHERE match_score >= p_match_threshold;

    GET DIAGNOSTICS v_resolved = ROW_COUNT;

    -- Update run
    UPDATE fhq_research.orphan_analysis_runs
    SET resolved_count = v_resolved,
        orphaned_after = v_orphaned_before - v_resolved,
        resolution_rate = CASE WHEN v_orphaned_before > 0
                              THEN v_resolved::NUMERIC / v_orphaned_before
                              ELSE 0 END
    WHERE run_id = v_run_id;

    RETURN v_run_id;
END;
$$ LANGUAGE plpgsql;

-- C4.3.4: Orphan Status View
CREATE OR REPLACE VIEW fhq_research.v_orphan_status_summary AS
SELECT
    (SELECT count(*) FROM fhq_research.forecast_ledger) AS total_forecasts,
    (SELECT count(*) FROM fhq_research.forecast_ledger fl
     LEFT JOIN fhq_research.forecast_outcome_pairs fop ON fl.forecast_id = fop.forecast_id
     WHERE fop.pair_id IS NULL) AS orphaned_forecasts,
    (SELECT count(*) FROM fhq_research.forecast_outcome_pairs) AS linked_pairs,
    ROUND(
        (SELECT count(*) FROM fhq_research.forecast_outcome_pairs)::NUMERIC /
        NULLIF((SELECT count(*) FROM fhq_research.forecast_ledger), 0) * 100,
        2
    ) AS linkage_pct;

-- Log migration to governance_actions_log
INSERT INTO fhq_governance.governance_actions_log (
    action_type, action_target, action_target_type, initiated_by, initiated_at, decision, decision_rationale, metadata, agent_id
) VALUES (
    'MIGRATION', '297_b4_orphan_resolution', 'DATABASE_SCHEMA', 'STIG', NOW(), 'EXECUTED',
    'CEO-DIR-2026-064 B4 - Orphaned Forecast Resolution',
    '{"directive": "CEO-DIR-2026-064", "gap": "B4", "tables_created": ["orphan_analysis_runs", "forecast_resolution_log"], "views_created": ["v_orphan_status_summary"], "functions_created": ["fn_resolve_orphaned_forecasts"]}'::jsonb,
    'STIG'
);

COMMIT;
