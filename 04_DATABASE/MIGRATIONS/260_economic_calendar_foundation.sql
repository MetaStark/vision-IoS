-- Migration 260: Economic Calendar Foundation (IoS-016 G0)
-- CEO Directive 2026-01-16C: Global Economic Calendar Integration
-- Version: 3.0 MBB++ (CEO MBB++ Refinements Applied)
-- Classification: GOVERNANCE-CRITICAL
-- Executed by: STIG (EC-003_2026_PRODUCTION)

BEGIN;

-- ============================================================================
-- Phase 1: Create fhq_calendar Schema
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS fhq_calendar;

COMMENT ON SCHEMA fhq_calendar IS
'IoS-016: Economic Calendar and Temporal Governance.
Owner: LINE (EC-005) + CEIO (EC-009).
Purpose: Single source of truth for market-moving events.
CEO Approval: Phase 1 Foundation APPROVED (2026-01-16)';

-- ============================================================================
-- Phase 2: Event Type Registry
-- CEO Refinements: #4 (consensus/actual optional), S1 (normalization unit)
-- ============================================================================

CREATE TABLE fhq_calendar.event_type_registry (
    event_type_code TEXT PRIMARY KEY,
    event_category TEXT NOT NULL CHECK (event_category IN ('MACRO', 'EQUITY', 'CRYPTO', 'CROSS_ASSET')),
    event_name TEXT NOT NULL,
    description TEXT,
    impact_rank INTEGER NOT NULL CHECK (impact_rank BETWEEN 1 AND 5),
    -- CEO Refinement #4: Optional fields governed by event-type
    consensus_available BOOLEAN NOT NULL DEFAULT FALSE,
    actual_available BOOLEAN NOT NULL DEFAULT FALSE,
    -- CEO Refinement S1: Surprise normalization per data type
    surprise_normalization_unit TEXT CHECK (surprise_normalization_unit IN ('BPS', 'PCT', 'ABSOLUTE', 'STDDEV')),
    historical_std_lookup_table TEXT,
    -- Metadata
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'STIG'
);

COMMENT ON TABLE fhq_calendar.event_type_registry IS
'Canonical event types with impact rankings (1-5). CEO Refinement #4: consensus/actual fields marked as optional per event-type rules.';

COMMENT ON COLUMN fhq_calendar.event_type_registry.surprise_normalization_unit IS
'CEO Refinement S1: BPS for rates, PCT for CPI, ABSOLUTE for counts, STDDEV for normalized.';

-- ============================================================================
-- Phase 3: Calendar Events
-- CEO Refinements: #5 (time_semantics, time_precision), S1 (surprise_score)
-- ============================================================================

CREATE TABLE fhq_calendar.calendar_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type_code TEXT NOT NULL REFERENCES fhq_calendar.event_type_registry(event_type_code),
    -- CEO Refinement #5: Time semantics and precision
    event_timestamp TIMESTAMPTZ NOT NULL,
    time_semantics TEXT NOT NULL DEFAULT 'RELEASE_TIME' CHECK (time_semantics IN ('RELEASE_TIME', 'EMBARGO_LIFT', 'PRESS_CONFERENCE_START', 'MARKET_OPEN', 'MARKET_CLOSE', 'SCHEDULED_START')),
    time_precision TEXT NOT NULL DEFAULT 'MINUTE' CHECK (time_precision IN ('DATE_ONLY', 'HOUR', 'MINUTE', 'SECOND')),
    -- CEO Refinement #4: Optional consensus/actual per event-type
    consensus_estimate NUMERIC,
    actual_value NUMERIC,
    previous_value NUMERIC,
    revision_value NUMERIC,
    -- CEO Refinement S1: Normalized surprise score
    surprise_score NUMERIC GENERATED ALWAYS AS (
        CASE
            WHEN actual_value IS NOT NULL AND consensus_estimate IS NOT NULL AND consensus_estimate != 0
            THEN (actual_value - consensus_estimate) / ABS(NULLIF(consensus_estimate, 0))
            ELSE NULL
        END
    ) STORED,
    -- Source tracking
    source_provider TEXT NOT NULL,
    source_event_id TEXT,
    -- ADR-008: Ed25519 signature by CEIO
    ceio_signature TEXT,
    -- Metadata
    ingestion_batch_id UUID,
    is_canonical BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_calendar_events_timestamp ON fhq_calendar.calendar_events(event_timestamp);
CREATE INDEX idx_calendar_events_type ON fhq_calendar.calendar_events(event_type_code);
CREATE INDEX idx_calendar_events_provider ON fhq_calendar.calendar_events(source_provider);

COMMENT ON TABLE fhq_calendar.calendar_events IS
'Event instances with surprise scores. CEO Refinement #5: time_semantics and time_precision for accurate temporal governance.';

-- ============================================================================
-- Phase 4: Event Asset Mapping
-- ============================================================================

CREATE TABLE fhq_calendar.event_asset_mapping (
    mapping_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type_code TEXT NOT NULL REFERENCES fhq_calendar.event_type_registry(event_type_code),
    asset_id TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    impact_multiplier NUMERIC NOT NULL DEFAULT 1.0 CHECK (impact_multiplier BETWEEN 0 AND 2),
    is_primary_affected BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(event_type_code, asset_id)
);

COMMENT ON TABLE fhq_calendar.event_asset_mapping IS
'Maps event types to affected assets with impact multipliers.';

-- ============================================================================
-- Phase 5: Staging Events (Raw Provider Data)
-- ============================================================================

CREATE TABLE fhq_calendar.staging_events (
    staging_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_provider TEXT NOT NULL,
    source_event_id TEXT,
    raw_payload JSONB NOT NULL,
    event_type_code_mapped TEXT,
    event_timestamp_parsed TIMESTAMPTZ,
    processing_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (processing_status IN ('PENDING', 'PROCESSED', 'REJECTED', 'DUPLICATE')),
    rejection_reason TEXT,
    canonical_event_id UUID REFERENCES fhq_calendar.calendar_events(event_id),
    ingestion_batch_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_staging_events_status ON fhq_calendar.staging_events(processing_status);
CREATE INDEX idx_staging_events_provider ON fhq_calendar.staging_events(source_provider);

COMMENT ON TABLE fhq_calendar.staging_events IS
'Raw provider data staging area for reconciliation before promotion to canonical.';

-- ============================================================================
-- Phase 6: Calendar Provider State
-- CEO Refinements: #3 (TOS evidencing), #8 (domain-specific reliability)
-- ============================================================================

CREATE TABLE fhq_calendar.calendar_provider_state (
    provider_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_name TEXT NOT NULL UNIQUE,
    provider_type TEXT NOT NULL CHECK (provider_type IN ('FREE', 'PAID', 'PREMIUM')),
    -- CEO Refinement #8: Domain-specific reliability scores
    reliability_macro NUMERIC(3,2) NOT NULL DEFAULT 0.50 CHECK (reliability_macro BETWEEN 0 AND 1),
    reliability_equity NUMERIC(3,2) NOT NULL DEFAULT 0.50 CHECK (reliability_equity BETWEEN 0 AND 1),
    reliability_crypto NUMERIC(3,2) NOT NULL DEFAULT 0.50 CHECK (reliability_crypto BETWEEN 0 AND 1),
    reliability_cross_asset NUMERIC(3,2) NOT NULL DEFAULT 0.50 CHECK (reliability_cross_asset BETWEEN 0 AND 1),
    -- API limits
    daily_quota INTEGER,
    current_daily_usage INTEGER NOT NULL DEFAULT 0,
    quota_reset_time TIME NOT NULL DEFAULT '00:00:00',
    -- CEO Refinement #3: TOS/License evidencing
    tos_snapshot_hash TEXT,
    tos_snapshot_date DATE,
    tos_permitted_use TEXT,
    tos_redistribution_allowed BOOLEAN DEFAULT FALSE,
    tos_evidence_uri TEXT,
    tos_verified_by TEXT,
    tos_verified_at TIMESTAMPTZ,
    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_successful_fetch TIMESTAMPTZ,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE fhq_calendar.calendar_provider_state IS
'Provider state with domain-specific reliability (CEO #8) and TOS evidencing (CEO #3).';

-- ============================================================================
-- Phase 7: Source Conflict Log (ADR-013)
-- CEO Refinement #8: Domain-aware conflict resolution
-- ============================================================================

CREATE TABLE fhq_calendar.source_conflict_log (
    conflict_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type_code TEXT NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    -- CEO Refinement #8: Domain context for reliability lookup
    event_domain TEXT NOT NULL CHECK (event_domain IN ('MACRO', 'EQUITY', 'CRYPTO', 'CROSS_ASSET')),
    -- Conflict details
    provider_a TEXT NOT NULL,
    provider_a_value JSONB NOT NULL,
    provider_a_reliability NUMERIC NOT NULL,
    provider_b TEXT NOT NULL,
    provider_b_value JSONB NOT NULL,
    provider_b_reliability NUMERIC NOT NULL,
    -- Resolution
    winning_provider TEXT NOT NULL,
    winning_reliability NUMERIC NOT NULL,
    resolution_method TEXT NOT NULL DEFAULT 'HIGHEST_DOMAIN_RELIABILITY',
    resolution_notes TEXT,
    canonical_event_id UUID REFERENCES fhq_calendar.calendar_events(event_id),
    -- Audit
    resolved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_by TEXT NOT NULL DEFAULT 'SYSTEM'
);

CREATE INDEX idx_source_conflict_timestamp ON fhq_calendar.source_conflict_log(event_timestamp);

COMMENT ON TABLE fhq_calendar.source_conflict_log IS
'ADR-013 conflict resolution log with domain-specific reliability (CEO #8).';

-- ============================================================================
-- Phase 8: Unexplained Volatility Flags (Ghost Events)
-- CEO Refinement #7: Ghost event triage
-- ============================================================================

CREATE TABLE fhq_calendar.unexplained_volatility_flags (
    flag_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id TEXT NOT NULL,
    detection_timestamp TIMESTAMPTZ NOT NULL,
    volatility_magnitude NUMERIC NOT NULL,
    expected_volatility NUMERIC NOT NULL,
    volatility_ratio NUMERIC GENERATED ALWAYS AS (
        volatility_magnitude / NULLIF(expected_volatility, 0)
    ) STORED,
    -- Flag status
    flag_status TEXT NOT NULL DEFAULT 'OPEN' CHECK (flag_status IN ('OPEN', 'INVESTIGATING', 'RESOLVED', 'FALSE_POSITIVE')),
    -- CEO Refinement #7: Ghost event triage categories
    suspected_cause TEXT CHECK (suspected_cause IN ('COVERAGE_GAP', 'TIMESTAMP_DEFECT', 'MAPPING_DEFECT', 'TRUE_GHOST', 'UNKNOWN')),
    triage_notes TEXT,
    -- Resolution
    resolved_by TEXT,
    resolved_at TIMESTAMPTZ,
    resolution_event_id UUID REFERENCES fhq_calendar.calendar_events(event_id),
    resolution_notes TEXT,
    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_volatility_flags_status ON fhq_calendar.unexplained_volatility_flags(flag_status);
CREATE INDEX idx_volatility_flags_asset ON fhq_calendar.unexplained_volatility_flags(asset_id);

COMMENT ON TABLE fhq_calendar.unexplained_volatility_flags IS
'Ghost event detection with triage categories (CEO #7): COVERAGE_GAP, TIMESTAMP_DEFECT, MAPPING_DEFECT, TRUE_GHOST.';

-- ============================================================================
-- Phase 9: Ingestion Batches (ADR-002 Audit Trail)
-- ============================================================================

CREATE TABLE fhq_calendar.ingestion_batches (
    batch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID REFERENCES fhq_calendar.calendar_provider_state(provider_id),
    batch_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    events_fetched INTEGER NOT NULL DEFAULT 0,
    events_new INTEGER NOT NULL DEFAULT 0,
    events_updated INTEGER NOT NULL DEFAULT 0,
    events_rejected INTEGER NOT NULL DEFAULT 0,
    conflicts_detected INTEGER NOT NULL DEFAULT 0,
    -- Hash chain for audit
    batch_hash TEXT NOT NULL,
    previous_batch_hash TEXT,
    -- Status
    batch_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (batch_status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')),
    error_message TEXT,
    -- Signature
    ceio_signature TEXT,
    -- Audit
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_ingestion_batches_provider ON fhq_calendar.ingestion_batches(provider_id);
CREATE INDEX idx_ingestion_batches_status ON fhq_calendar.ingestion_batches(batch_status);

COMMENT ON TABLE fhq_calendar.ingestion_batches IS
'ADR-002 audit trail for calendar ingestion with hash chain integrity.';

-- ============================================================================
-- Phase 10: Provider TOS Archive
-- CEO Refinement #3: TOS/License Evidence Storage
-- ============================================================================

CREATE TABLE fhq_calendar.provider_tos_archive (
    archive_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID NOT NULL REFERENCES fhq_calendar.calendar_provider_state(provider_id),
    tos_document_text TEXT NOT NULL,
    tos_document_hash TEXT NOT NULL,
    capture_date DATE NOT NULL,
    captured_by TEXT NOT NULL,
    capture_method TEXT NOT NULL DEFAULT 'MANUAL' CHECK (capture_method IN ('MANUAL', 'AUTOMATED', 'API')),
    vega_attested BOOLEAN NOT NULL DEFAULT FALSE,
    vega_attestation_id UUID,
    vega_attested_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tos_archive_provider ON fhq_calendar.provider_tos_archive(provider_id);

COMMENT ON TABLE fhq_calendar.provider_tos_archive IS
'CEO Refinement #3: TOS/License evidence storage for all calendar providers.';

-- ============================================================================
-- Phase 11: Leakage Detection Config
-- CEO Refinement #6: Governed leakage windows by impact_rank
-- ============================================================================

CREATE TABLE fhq_calendar.leakage_detection_config (
    impact_rank INTEGER PRIMARY KEY CHECK (impact_rank BETWEEN 1 AND 5),
    pre_event_window_hours INTEGER NOT NULL,
    post_event_window_hours INTEGER NOT NULL,
    description TEXT NOT NULL,
    -- CEO Refinement #6: Diagnostic-only flag
    is_diagnostic_only BOOLEAN NOT NULL DEFAULT TRUE,
    examples TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed leakage detection windows per CEO specification
INSERT INTO fhq_calendar.leakage_detection_config (impact_rank, pre_event_window_hours, post_event_window_hours, description, examples) VALUES
(5, 4, 24, 'Critical events (FOMC, NFP)', 'FOMC rate decisions, Non-Farm Payrolls'),
(4, 3, 12, 'High impact events (CPI, GDP)', 'CPI releases, GDP reports, Central bank minutes'),
(3, 2, 6, 'Medium impact events (Earnings, PMI)', 'Major earnings, PMI data, Trade balance'),
(2, 1, 3, 'Low impact events', 'Minor economic releases, secondary indicators'),
(1, 0, 1, 'Minimal impact events', 'Scheduled maintenance, minor announcements');

COMMENT ON TABLE fhq_calendar.leakage_detection_config IS
'CEO Refinement #6: Leakage detection windows governed by impact_rank. is_diagnostic_only=TRUE means not a trading signal.';

-- ============================================================================
-- Phase 12: Asset Brier Alerts
-- CEO Addition: STRONG SIGNAL for persistent asset-specific Brier degradation
-- ============================================================================

CREATE TABLE fhq_calendar.asset_brier_alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id TEXT NOT NULL,
    alert_level TEXT NOT NULL CHECK (alert_level IN ('AMBER', 'RED', 'CRITICAL')),
    consecutive_cycles INTEGER NOT NULL,
    avg_brier_score NUMERIC NOT NULL,
    portfolio_brier_delta NUMERIC NOT NULL,
    -- Event correlation analysis
    event_correlation TEXT CHECK (event_correlation IN ('EVENT_ADJACENT', 'EVENT_NEUTRAL', 'MIXED', 'UNKNOWN')),
    -- Alert tracking
    alert_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    investigation_status TEXT NOT NULL DEFAULT 'OPEN' CHECK (investigation_status IN ('OPEN', 'INVESTIGATING', 'RESOLVED', 'FALSE_POSITIVE', 'ACKNOWLEDGED')),
    uma_recommendation TEXT,
    -- Resolution
    resolution_notes TEXT,
    resolved_by TEXT,
    resolved_at TIMESTAMPTZ,
    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_brier_alerts_asset ON fhq_calendar.asset_brier_alerts(asset_id);
CREATE INDEX idx_brier_alerts_level ON fhq_calendar.asset_brier_alerts(alert_level);
CREATE INDEX idx_brier_alerts_status ON fhq_calendar.asset_brier_alerts(investigation_status);

COMMENT ON TABLE fhq_calendar.asset_brier_alerts IS
'CEO Strong Signal: Persistent asset-specific Brier degradation alerts. AMBER (3+ cycles), RED (5+ cycles at >0.60), CRITICAL (correlates with EVENT_NEUTRAL).';

-- ============================================================================
-- Phase 13: Seed Initial Event Types
-- ============================================================================

INSERT INTO fhq_calendar.event_type_registry (event_type_code, event_category, event_name, description, impact_rank, consensus_available, actual_available, surprise_normalization_unit) VALUES
-- US Macro Events (Impact Rank 4-5)
('US_FOMC', 'MACRO', 'FOMC Interest Rate Decision', 'Federal Reserve interest rate decision', 5, TRUE, TRUE, 'BPS'),
('US_NFP', 'MACRO', 'US Non-Farm Payrolls', 'US employment report', 5, TRUE, TRUE, 'ABSOLUTE'),
('US_CPI', 'MACRO', 'US Consumer Price Index', 'US inflation data', 4, TRUE, TRUE, 'PCT'),
('US_GDP', 'MACRO', 'US Gross Domestic Product', 'US economic growth', 4, TRUE, TRUE, 'PCT'),
('US_PCE', 'MACRO', 'US Personal Consumption Expenditures', 'Fed preferred inflation measure', 4, TRUE, TRUE, 'PCT'),
('US_PPI', 'MACRO', 'US Producer Price Index', 'Producer inflation', 3, TRUE, TRUE, 'PCT'),
('US_RETAIL', 'MACRO', 'US Retail Sales', 'Consumer spending', 3, TRUE, TRUE, 'PCT'),
('US_CLAIMS', 'MACRO', 'US Initial Jobless Claims', 'Weekly unemployment claims', 3, TRUE, TRUE, 'ABSOLUTE'),
('US_ISM_MFG', 'MACRO', 'US ISM Manufacturing PMI', 'Manufacturing activity', 3, TRUE, TRUE, 'ABSOLUTE'),
('US_ISM_SVC', 'MACRO', 'US ISM Services PMI', 'Services activity', 3, TRUE, TRUE, 'ABSOLUTE'),

-- Global Central Banks (Impact Rank 4-5)
('ECB_RATE', 'MACRO', 'ECB Interest Rate Decision', 'European Central Bank rate decision', 5, TRUE, TRUE, 'BPS'),
('BOE_RATE', 'MACRO', 'BOE Interest Rate Decision', 'Bank of England rate decision', 4, TRUE, TRUE, 'BPS'),
('BOJ_RATE', 'MACRO', 'BOJ Interest Rate Decision', 'Bank of Japan rate decision', 4, TRUE, TRUE, 'BPS'),
('PBOC_RATE', 'MACRO', 'PBOC Loan Prime Rate', 'People''s Bank of China rate', 4, TRUE, TRUE, 'BPS'),

-- Crypto Events (Impact Rank 3-5)
('BTC_HALVING', 'CRYPTO', 'Bitcoin Halving', 'Bitcoin block reward halving', 5, FALSE, FALSE, NULL),
('ETH_MERGE', 'CRYPTO', 'Ethereum Network Upgrade', 'Major Ethereum protocol upgrade', 5, FALSE, FALSE, NULL),
('SEC_CRYPTO', 'CRYPTO', 'SEC Crypto Announcement', 'US SEC crypto regulatory announcement', 4, FALSE, FALSE, NULL),

-- Equity Events (Impact Rank 2-4)
('EARNINGS_Q', 'EQUITY', 'Quarterly Earnings Release', 'Company quarterly earnings', 3, TRUE, TRUE, 'PCT'),
('DIVIDEND_EX', 'EQUITY', 'Ex-Dividend Date', 'Stock goes ex-dividend', 2, FALSE, TRUE, 'ABSOLUTE'),
('STOCK_SPLIT', 'EQUITY', 'Stock Split', 'Stock split event', 2, FALSE, TRUE, 'ABSOLUTE');

-- ============================================================================
-- Phase 14: Seed Initial Providers (Placeholder)
-- ============================================================================

INSERT INTO fhq_calendar.calendar_provider_state (provider_name, provider_type, reliability_macro, reliability_equity, reliability_crypto, reliability_cross_asset) VALUES
('FRED', 'FREE', 0.95, 0.50, 0.20, 0.70),
('INVESTING_COM', 'FREE', 0.85, 0.80, 0.60, 0.75),
('YAHOO_FINANCE', 'FREE', 0.70, 0.85, 0.50, 0.60),
('TRADINGECONOMICS', 'PAID', 0.90, 0.75, 0.40, 0.80),
('ALPHA_VANTAGE', 'PAID', 0.80, 0.85, 0.30, 0.65);

-- ============================================================================
-- Phase 15: Governance Actions Log
-- Note: IoS-016 registration tracked via governance_actions_log
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
    metadata,
    agent_id,
    timestamp
) VALUES (
    gen_random_uuid(),
    'IOS_G0_SUBMISSION',
    'IoS-016',
    'INSTITUTIONAL_OPERATING_STANDARD',
    'STIG',
    NOW(),
    'SUBMITTED',
    'CEO Directive 2026-01-16C: Global Economic Calendar Integration G0 Submission. MBB++ refinements incorporated. Phase 1 Foundation APPROVED.',
    jsonb_build_object(
        'migration', '260_economic_calendar_foundation.sql',
        'directive', 'CEO Directive 2026-01-16C',
        'version', '3.0 MBB++',
        'ceo_approval', 'Phase 1 Foundation APPROVED (2026-01-16)',
        'schema_created', 'fhq_calendar',
        'tables_created', ARRAY[
            'event_type_registry',
            'calendar_events',
            'event_asset_mapping',
            'staging_events',
            'calendar_provider_state',
            'source_conflict_log',
            'unexplained_volatility_flags',
            'ingestion_batches',
            'provider_tos_archive',
            'leakage_detection_config',
            'asset_brier_alerts'
        ],
        'ceo_refinements', jsonb_build_object(
            'refinement_1', 'ROI as ex-ante estimates with validation plan + stop-loss',
            'refinement_2', 'ADR-008 status clarified',
            'refinement_3', 'TOS/license evidencing',
            'refinement_4', 'consensus/actual optional per event-type',
            'refinement_5', 'time_semantics + time_precision fields',
            'refinement_6', 'Leakage detection windows governed by impact_rank',
            'refinement_7', 'Ghost event triage categories',
            'refinement_8', 'Source reliability per domain',
            'refinement_9', 'Scope firewall: 14-day Phase 1',
            'sharpening_S1', 'Surprise-score normalization per data type',
            'sharpening_S2', 'CFAO 48h Shadow Mode',
            'sharpening_S3', 'Asset-specific Brier alerting (AMBER/RED/CRITICAL)'
        ),
        'next_gate', 'G1 Technical Validation (Days 2-5)'
    ),
    'STIG',
    NOW()
);

COMMIT;

-- ============================================================================
-- Verification Queries
-- ============================================================================
-- SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'fhq_calendar';
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'fhq_calendar';
-- SELECT * FROM fhq_calendar.event_type_registry;
-- SELECT * FROM fhq_calendar.leakage_detection_config;
-- SELECT * FROM fhq_governance.ios_registry WHERE ios_number = 'IoS-016';
-- SELECT * FROM fhq_governance.governance_actions_log WHERE action_target = 'IoS-016' ORDER BY timestamp DESC LIMIT 1;
