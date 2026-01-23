-- Migration 341: Sentiment Timeseries Schema
-- CEO-DIR-2026-META-ANALYSIS Phase 3: Sentiment Pipeline
-- Author: STIG (EC-003)
-- Date: 2026-01-23
--
-- Purpose: Create infrastructure for news/social sentiment analysis
-- to enable 6/6 signal sources in IoS-013

BEGIN;

-- =============================================================================
-- TABLE: fhq_research.sentiment_timeseries
-- Stores sentiment analysis results for assets
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.sentiment_timeseries (
    sentiment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Asset identification
    symbol TEXT NOT NULL,
    asset_class TEXT DEFAULT 'EQUITY',  -- EQUITY, CRYPTO, FOREX, COMMODITY

    -- Sentiment metrics
    sentiment_score NUMERIC(5,4) NOT NULL,  -- -1.0 to 1.0
    sentiment_label TEXT NOT NULL,  -- VERY_BEARISH, BEARISH, NEUTRAL, BULLISH, VERY_BULLISH
    sentiment_confidence NUMERIC(5,4),  -- 0.0 to 1.0

    -- Aggregation info
    source_count INTEGER DEFAULT 1,  -- Number of sources aggregated
    bullish_count INTEGER DEFAULT 0,
    bearish_count INTEGER DEFAULT 0,
    neutral_count INTEGER DEFAULT 0,

    -- Source information
    primary_source TEXT NOT NULL,  -- SERPER, FINNHUB, TWITTER, REDDIT
    sources JSONB DEFAULT '[]',  -- Array of individual source contributions

    -- Content metadata
    headline_sample TEXT,  -- Representative headline
    keywords JSONB DEFAULT '[]',  -- Extracted keywords

    -- Timestamps
    analyzed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    data_timestamp TIMESTAMPTZ,  -- When the source data was published

    -- Analysis metadata
    model_used TEXT DEFAULT 'DEEPSEEK_R1',  -- Analysis model
    analysis_duration_ms INTEGER,

    -- Governance
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'SENTIMENT_DAEMON',
    evidence_hash TEXT,

    -- Constraints
    CONSTRAINT sentiment_score_range CHECK (sentiment_score >= -1.0 AND sentiment_score <= 1.0),
    CONSTRAINT sentiment_confidence_range CHECK (sentiment_confidence IS NULL OR (sentiment_confidence >= 0.0 AND sentiment_confidence <= 1.0)),
    CONSTRAINT valid_sentiment_label CHECK (sentiment_label IN ('VERY_BEARISH', 'BEARISH', 'NEUTRAL', 'BULLISH', 'VERY_BULLISH'))
);

-- Create index for efficient lookups
CREATE INDEX IF NOT EXISTS idx_sentiment_symbol_time
ON fhq_research.sentiment_timeseries(symbol, analyzed_at DESC);

CREATE INDEX IF NOT EXISTS idx_sentiment_analyzed_at
ON fhq_research.sentiment_timeseries(analyzed_at DESC);

-- =============================================================================
-- TABLE: fhq_research.sentiment_sources
-- Stores raw sentiment data from individual sources before aggregation
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.sentiment_sources (
    source_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to aggregated sentiment
    sentiment_id UUID REFERENCES fhq_research.sentiment_timeseries(sentiment_id),

    -- Source details
    source_type TEXT NOT NULL,  -- NEWS, SOCIAL, ANALYST
    source_name TEXT NOT NULL,  -- Specific source (Reuters, Bloomberg, Twitter, etc.)
    source_url TEXT,

    -- Content
    headline TEXT,
    snippet TEXT,
    full_content TEXT,

    -- Individual sentiment
    raw_sentiment_score NUMERIC(5,4),
    raw_sentiment_label TEXT,

    -- Metadata
    published_at TIMESTAMPTZ,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    relevance_score NUMERIC(5,4),  -- How relevant to the asset

    -- Governance
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sentiment_sources_sentiment_id
ON fhq_research.sentiment_sources(sentiment_id);

-- =============================================================================
-- VIEW: v_latest_sentiment
-- Quick access to most recent sentiment per symbol
-- =============================================================================

CREATE OR REPLACE VIEW fhq_research.v_latest_sentiment AS
SELECT DISTINCT ON (symbol)
    sentiment_id,
    symbol,
    asset_class,
    sentiment_score,
    sentiment_label,
    sentiment_confidence,
    source_count,
    primary_source,
    headline_sample,
    analyzed_at,
    EXTRACT(EPOCH FROM (NOW() - analyzed_at)) / 3600 as hours_since_update
FROM fhq_research.sentiment_timeseries
ORDER BY symbol, analyzed_at DESC;

-- =============================================================================
-- VIEW: v_sentiment_summary
-- Aggregate sentiment statistics
-- =============================================================================

CREATE OR REPLACE VIEW fhq_research.v_sentiment_summary AS
SELECT
    symbol,
    COUNT(*) as total_analyses,
    AVG(sentiment_score) as avg_sentiment,
    STDDEV(sentiment_score) as sentiment_volatility,
    MIN(sentiment_score) as min_sentiment,
    MAX(sentiment_score) as max_sentiment,
    MODE() WITHIN GROUP (ORDER BY sentiment_label) as dominant_label,
    MAX(analyzed_at) as last_analysis,
    SUM(bullish_count) as total_bullish,
    SUM(bearish_count) as total_bearish,
    SUM(neutral_count) as total_neutral
FROM fhq_research.sentiment_timeseries
WHERE analyzed_at >= NOW() - INTERVAL '7 days'
GROUP BY symbol;

-- =============================================================================
-- FUNCTION: get_sentiment_for_signal
-- Returns sentiment context for IoS-013 signal enrichment
-- =============================================================================

CREATE OR REPLACE FUNCTION fhq_research.get_sentiment_for_signal(
    p_symbol TEXT,
    p_lookback_hours INTEGER DEFAULT 24
)
RETURNS TABLE (
    sentiment_score NUMERIC,
    sentiment_label TEXT,
    sentiment_confidence NUMERIC,
    source_count INTEGER,
    hours_since_update NUMERIC,
    sentiment_trend TEXT
) AS $$
DECLARE
    v_current_score NUMERIC;
    v_prev_score NUMERIC;
BEGIN
    -- Get current sentiment
    SELECT
        st.sentiment_score,
        st.sentiment_label,
        st.sentiment_confidence,
        st.source_count,
        EXTRACT(EPOCH FROM (NOW() - st.analyzed_at)) / 3600
    INTO
        sentiment_score,
        sentiment_label,
        sentiment_confidence,
        source_count,
        hours_since_update
    FROM fhq_research.sentiment_timeseries st
    WHERE st.symbol = p_symbol
      AND st.analyzed_at >= NOW() - (p_lookback_hours || ' hours')::INTERVAL
    ORDER BY st.analyzed_at DESC
    LIMIT 1;

    -- If no recent sentiment, return NULL
    IF sentiment_score IS NULL THEN
        sentiment_score := 0;
        sentiment_label := 'NEUTRAL';
        sentiment_confidence := 0;
        source_count := 0;
        hours_since_update := NULL;
        sentiment_trend := 'NO_DATA';
        RETURN NEXT;
        RETURN;
    END IF;

    v_current_score := sentiment_score;

    -- Get previous sentiment for trend calculation
    SELECT st.sentiment_score INTO v_prev_score
    FROM fhq_research.sentiment_timeseries st
    WHERE st.symbol = p_symbol
      AND st.analyzed_at < NOW() - (p_lookback_hours / 2 || ' hours')::INTERVAL
    ORDER BY st.analyzed_at DESC
    LIMIT 1;

    -- Calculate trend
    IF v_prev_score IS NULL THEN
        sentiment_trend := 'NEW';
    ELSIF v_current_score - v_prev_score > 0.1 THEN
        sentiment_trend := 'IMPROVING';
    ELSIF v_current_score - v_prev_score < -0.1 THEN
        sentiment_trend := 'DETERIORATING';
    ELSE
        sentiment_trend := 'STABLE';
    END IF;

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- GOVERNANCE: Log migration
-- =============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'SCHEMA_MIGRATION',
    'fhq_research.sentiment_timeseries',
    'TABLE_CREATION',
    'STIG',
    'EXECUTED',
    'CEO-DIR-2026-META-ANALYSIS Phase 3: Sentiment Pipeline infrastructure',
    jsonb_build_object(
        'migration', '341_sentiment_timeseries_schema.sql',
        'tables_created', ARRAY['sentiment_timeseries', 'sentiment_sources'],
        'views_created', ARRAY['v_latest_sentiment', 'v_sentiment_summary'],
        'functions_created', ARRAY['get_sentiment_for_signal'],
        'timestamp', NOW()
    )
);

COMMIT;

-- Verification
SELECT
    'Migration 341 Complete' as status,
    (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'fhq_research' AND table_name LIKE 'sentiment%') as sentiment_tables,
    (SELECT COUNT(*) FROM information_schema.views WHERE table_schema = 'fhq_research' AND table_name LIKE '%sentiment%') as sentiment_views;
