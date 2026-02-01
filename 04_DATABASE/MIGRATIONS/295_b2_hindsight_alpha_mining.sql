-- Migration 295: B2 Hindsight Alpha Mining
-- Authority: CEO-DIR-2026-064
-- Gate: ADR-004 APPROVED
-- Executed by: STIG
-- Date: 2026-01-17

BEGIN;

-- C2.3.1: Surprise Analysis Runs
CREATE TABLE IF NOT EXISTS fhq_alpha.surprise_analysis_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_timestamp TIMESTAMPTZ DEFAULT NOW(),
    analysis_window_start TIMESTAMPTZ NOT NULL,
    analysis_window_end TIMESTAMPTZ NOT NULL,
    pairs_analyzed INTEGER,
    opportunities_found INTEGER,
    top_opportunity_magnitude NUMERIC,
    execution_duration_ms INTEGER,
    evidence_ref TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- C2.3.2: Hindsight Opportunities
CREATE TABLE IF NOT EXISTS fhq_alpha.hindsight_opportunities (
    opportunity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES fhq_alpha.surprise_analysis_runs(run_id),
    forecast_id UUID NOT NULL,
    outcome_id UUID NOT NULL,
    forecast_value NUMERIC,
    outcome_value NUMERIC,
    surprise_delta NUMERIC NOT NULL,
    surprise_direction VARCHAR(10) CHECK (surprise_direction IN ('POSITIVE', 'NEGATIVE', 'NEUTRAL')),
    surprise_magnitude_rank INTEGER,
    domain TEXT,
    asset_class TEXT,
    signals_missed JSONB,
    regime_at_forecast TEXT,
    regime_at_outcome TEXT,
    learning_annotation TEXT,
    evidence_ref TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ho_run_id ON fhq_alpha.hindsight_opportunities(run_id);
CREATE INDEX IF NOT EXISTS idx_ho_magnitude_rank ON fhq_alpha.hindsight_opportunities(surprise_magnitude_rank);
CREATE INDEX IF NOT EXISTS idx_ho_domain ON fhq_alpha.hindsight_opportunities(domain);

-- C2.3.3: Surprise Delta Computation Function
CREATE OR REPLACE FUNCTION fhq_alpha.fn_compute_surprise_delta(
    p_forecast_value NUMERIC,
    p_outcome_value NUMERIC
) RETURNS TABLE (
    delta NUMERIC,
    direction VARCHAR(10),
    magnitude NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p_outcome_value - p_forecast_value AS delta,
        CASE
            WHEN p_outcome_value > p_forecast_value THEN 'POSITIVE'
            WHEN p_outcome_value < p_forecast_value THEN 'NEGATIVE'
            ELSE 'NEUTRAL'
        END::VARCHAR(10) AS direction,
        ABS(p_outcome_value - p_forecast_value) AS magnitude;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- C2.3.4: Hindsight Mining Function
CREATE OR REPLACE FUNCTION fhq_alpha.fn_mine_hindsight_opportunities(
    p_window_start TIMESTAMPTZ,
    p_window_end TIMESTAMPTZ,
    p_top_n INTEGER DEFAULT 100
) RETURNS UUID AS $$
DECLARE
    v_run_id UUID;
    v_pairs_count INTEGER;
    v_opps_count INTEGER;
    v_start_time TIMESTAMPTZ;
BEGIN
    v_start_time := clock_timestamp();

    -- Create run record
    INSERT INTO fhq_alpha.surprise_analysis_runs (
        analysis_window_start,
        analysis_window_end
    ) VALUES (
        p_window_start,
        p_window_end
    ) RETURNING run_id INTO v_run_id;

    -- Mine opportunities from forecast-outcome pairs
    WITH ranked_surprises AS (
        SELECT
            fop.forecast_id,
            fop.outcome_id,
            fl.forecast_probability AS forecast_value,
            ol.outcome_value,
            ol.outcome_value - fl.forecast_probability AS delta,
            CASE
                WHEN ol.outcome_value > fl.forecast_probability THEN 'POSITIVE'
                WHEN ol.outcome_value < fl.forecast_probability THEN 'NEGATIVE'
                ELSE 'NEUTRAL'
            END AS direction,
            fl.domain,
            ROW_NUMBER() OVER (ORDER BY ABS(ol.outcome_value - fl.forecast_probability) DESC) AS magnitude_rank
        FROM fhq_research.forecast_outcome_pairs fop
        JOIN fhq_research.forecast_ledger fl ON fop.forecast_id = fl.forecast_id
        JOIN fhq_research.outcome_ledger ol ON fop.outcome_id = ol.outcome_id
        WHERE fl.created_at BETWEEN p_window_start AND p_window_end
    )
    INSERT INTO fhq_alpha.hindsight_opportunities (
        run_id,
        forecast_id,
        outcome_id,
        forecast_value,
        outcome_value,
        surprise_delta,
        surprise_direction,
        surprise_magnitude_rank,
        domain
    )
    SELECT
        v_run_id,
        forecast_id,
        outcome_id,
        forecast_value,
        outcome_value,
        delta,
        direction,
        magnitude_rank,
        domain
    FROM ranked_surprises
    WHERE magnitude_rank <= p_top_n;

    GET DIAGNOSTICS v_opps_count = ROW_COUNT;

    -- Count total pairs in window
    SELECT count(*) INTO v_pairs_count
    FROM fhq_research.forecast_outcome_pairs fop
    JOIN fhq_research.forecast_ledger fl ON fop.forecast_id = fl.forecast_id
    WHERE fl.created_at BETWEEN p_window_start AND p_window_end;

    -- Update run record
    UPDATE fhq_alpha.surprise_analysis_runs
    SET pairs_analyzed = v_pairs_count,
        opportunities_found = v_opps_count,
        execution_duration_ms = EXTRACT(MILLISECONDS FROM (clock_timestamp() - v_start_time))::INTEGER
    WHERE run_id = v_run_id;

    RETURN v_run_id;
END;
$$ LANGUAGE plpgsql;

-- C2.3.5: Top Opportunities View
CREATE OR REPLACE VIEW fhq_alpha.v_hindsight_top_opportunities AS
SELECT
    ho.*,
    sar.run_timestamp,
    sar.analysis_window_start,
    sar.analysis_window_end
FROM fhq_alpha.hindsight_opportunities ho
JOIN fhq_alpha.surprise_analysis_runs sar ON ho.run_id = sar.run_id
WHERE ho.surprise_magnitude_rank <= 10
ORDER BY sar.run_timestamp DESC, ho.surprise_magnitude_rank;

-- Log migration to governance_actions_log
INSERT INTO fhq_governance.governance_actions_log (
    action_type, action_target, action_target_type, initiated_by, initiated_at, decision, decision_rationale, metadata, agent_id
) VALUES (
    'MIGRATION', '295_b2_hindsight_mining', 'DATABASE_SCHEMA', 'STIG', NOW(), 'EXECUTED',
    'CEO-DIR-2026-064 B2 - Hindsight Alpha Mining',
    '{"directive": "CEO-DIR-2026-064", "gap": "B2", "tables_created": ["surprise_analysis_runs", "hindsight_opportunities"], "views_created": ["v_hindsight_top_opportunities"], "functions_created": ["fn_compute_surprise_delta", "fn_mine_hindsight_opportunities"]}'::jsonb,
    'STIG'
);

COMMIT;
