-- Migration 294: Zero-Trust Airlock Hardening
-- Purpose: Enforce CEO-DIR-2026-063 - Prevent LLM-generated numerical data from entering canonical state
-- Directive: CEO-DIR-2026-063 Zero-Trust Data Integrity Enforcement
-- Severity: CLASS A GOVERNANCE BREACH RESPONSE
-- Executed by: STIG
-- Date: 2026-01-17

-- ============================================
-- SECTION 1: Source Lineage Enforcement Tables
-- ============================================

BEGIN;

-- Table to track approved API sources for canonical data
CREATE TABLE IF NOT EXISTS fhq_governance.approved_data_sources (
    source_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_code TEXT NOT NULL UNIQUE,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('CENTRAL_BANK', 'GOVERNMENT_AGENCY', 'OFFICIAL_STATISTICAL')),
    api_endpoint TEXT,
    verification_method TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    approved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed approved sources per CEO-DIR-2026-063
INSERT INTO fhq_governance.approved_data_sources (source_code, source_name, source_type, api_endpoint, verification_method, approved_by)
VALUES
    ('FRED', 'Federal Reserve Economic Data', 'GOVERNMENT_AGENCY', 'https://api.stlouisfed.org/fred', 'API_KEY_AUTHENTICATED', 'CEO'),
    ('BLS', 'Bureau of Labor Statistics', 'GOVERNMENT_AGENCY', 'https://api.bls.gov/publicAPI/v2', 'API_RESPONSE_HASH', 'CEO'),
    ('BEA', 'Bureau of Economic Analysis', 'GOVERNMENT_AGENCY', 'https://apps.bea.gov/api', 'API_RESPONSE_HASH', 'CEO'),
    ('FEDERAL_RESERVE', 'Federal Reserve Board', 'CENTRAL_BANK', 'https://www.federalreserve.gov/feeds', 'OFFICIAL_PUBLICATION', 'CEO'),
    ('ECB_OFFICIAL', 'European Central Bank', 'CENTRAL_BANK', 'https://sdw-wsrest.ecb.europa.eu', 'API_RESPONSE_HASH', 'CEO'),
    ('BOE_OFFICIAL', 'Bank of England', 'CENTRAL_BANK', 'https://www.bankofengland.co.uk/boeapps/database', 'API_RESPONSE_HASH', 'CEO'),
    ('BOJ_OFFICIAL', 'Bank of Japan', 'CENTRAL_BANK', 'https://www.boj.or.jp/en/statistics', 'OFFICIAL_PUBLICATION', 'CEO'),
    ('PBOC_OFFICIAL', 'People''s Bank of China', 'CENTRAL_BANK', 'http://www.pbc.gov.cn/en', 'OFFICIAL_PUBLICATION', 'CEO')
ON CONFLICT (source_code) DO NOTHING;

-- ============================================
-- SECTION 2: Data Lineage Tracking Table
-- ============================================

CREATE TABLE IF NOT EXISTS fhq_calendar.data_lineage_proof (
    lineage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL,
    source_code TEXT NOT NULL REFERENCES fhq_governance.approved_data_sources(source_code),
    api_request_timestamp TIMESTAMPTZ NOT NULL,
    api_response_hash TEXT NOT NULL,  -- SHA-256 of raw API response
    api_response_archived BOOLEAN DEFAULT FALSE,
    extracted_value NUMERIC,
    extraction_path TEXT,  -- JSONPath or XPath used to extract value
    cross_reference_source TEXT,
    cross_reference_hash TEXT,
    verified_by TEXT NOT NULL,
    verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT lineage_hash_length CHECK (length(api_response_hash) >= 64)
);

CREATE INDEX IF NOT EXISTS idx_lineage_event ON fhq_calendar.data_lineage_proof(event_id);
CREATE INDEX IF NOT EXISTS idx_lineage_source ON fhq_calendar.data_lineage_proof(source_code);

-- ============================================
-- SECTION 3: G3.75 Truth Gate Verification Table
-- ============================================

CREATE TABLE IF NOT EXISTS fhq_governance.g375_truth_gate_verifications (
    verification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gate_instance TEXT NOT NULL,  -- e.g., 'IOS016_G4_ACTIVATION'
    verified_by TEXT NOT NULL CHECK (verified_by IN ('CEO', 'LARS')),
    verification_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Spot-check records (minimum 5)
    spot_check_1_event_id UUID NOT NULL,
    spot_check_1_field TEXT NOT NULL,
    spot_check_1_system_value NUMERIC NOT NULL,
    spot_check_1_external_value NUMERIC NOT NULL,
    spot_check_1_external_source TEXT NOT NULL,
    spot_check_1_match BOOLEAN NOT NULL,

    spot_check_2_event_id UUID NOT NULL,
    spot_check_2_field TEXT NOT NULL,
    spot_check_2_system_value NUMERIC NOT NULL,
    spot_check_2_external_value NUMERIC NOT NULL,
    spot_check_2_external_source TEXT NOT NULL,
    spot_check_2_match BOOLEAN NOT NULL,

    spot_check_3_event_id UUID NOT NULL,
    spot_check_3_field TEXT NOT NULL,
    spot_check_3_system_value NUMERIC NOT NULL,
    spot_check_3_external_value NUMERIC NOT NULL,
    spot_check_3_external_source TEXT NOT NULL,
    spot_check_3_match BOOLEAN NOT NULL,

    spot_check_4_event_id UUID NOT NULL,
    spot_check_4_field TEXT NOT NULL,
    spot_check_4_system_value NUMERIC NOT NULL,
    spot_check_4_external_value NUMERIC NOT NULL,
    spot_check_4_external_source TEXT NOT NULL,
    spot_check_4_match BOOLEAN NOT NULL,

    spot_check_5_event_id UUID NOT NULL,
    spot_check_5_field TEXT NOT NULL,
    spot_check_5_system_value NUMERIC NOT NULL,
    spot_check_5_external_value NUMERIC NOT NULL,
    spot_check_5_external_source TEXT NOT NULL,
    spot_check_5_match BOOLEAN NOT NULL,

    all_checks_passed BOOLEAN GENERATED ALWAYS AS (
        spot_check_1_match AND spot_check_2_match AND spot_check_3_match AND
        spot_check_4_match AND spot_check_5_match
    ) STORED,

    g4_authorized BOOLEAN DEFAULT FALSE,
    authorization_signature TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT g375_requires_all_pass CHECK (
        (g4_authorized = FALSE) OR
        (g4_authorized = TRUE AND all_checks_passed = TRUE)
    )
);

-- ============================================
-- SECTION 4: Drift Detection Configuration
-- ============================================

CREATE TABLE IF NOT EXISTS fhq_calendar.drift_detection_config (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type_code TEXT NOT NULL,
    threshold_type TEXT NOT NULL CHECK (threshold_type IN ('BPS', 'PERCENT', 'ABSOLUTE')),
    threshold_value NUMERIC NOT NULL,
    check_frequency TEXT NOT NULL DEFAULT 'DAILY',
    defcon_escalation_level INTEGER NOT NULL DEFAULT 3,
    freeze_decision_engine BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed drift detection thresholds per CEO-DIR-2026-063
INSERT INTO fhq_calendar.drift_detection_config
    (event_type_code, threshold_type, threshold_value, defcon_escalation_level, freeze_decision_engine)
VALUES
    ('US_FOMC', 'BPS', 5, 2, TRUE),
    ('ECB_RATE', 'BPS', 5, 2, TRUE),
    ('BOE_RATE', 'BPS', 5, 2, TRUE),
    ('BOJ_RATE', 'BPS', 5, 2, TRUE),
    ('PBOC_RATE', 'BPS', 5, 2, TRUE),
    ('US_CPI', 'PERCENT', 0.1, 3, TRUE),
    ('US_NFP', 'ABSOLUTE', 50000, 3, TRUE),
    ('US_GDP', 'PERCENT', 0.2, 3, TRUE),
    ('US_PCE', 'PERCENT', 0.1, 3, TRUE),
    ('US_PPI', 'PERCENT', 0.1, 3, TRUE)
ON CONFLICT DO NOTHING;

-- ============================================
-- SECTION 5: Drift Detection Results Table
-- ============================================

CREATE TABLE IF NOT EXISTS fhq_calendar.drift_detection_results (
    detection_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    detection_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type_code TEXT NOT NULL,
    event_id UUID,
    stored_value NUMERIC NOT NULL,
    live_api_value NUMERIC NOT NULL,
    deviation NUMERIC NOT NULL,
    threshold_value NUMERIC NOT NULL,
    threshold_breached BOOLEAN NOT NULL,
    api_source TEXT NOT NULL,
    api_response_hash TEXT NOT NULL,
    defcon_escalated BOOLEAN DEFAULT FALSE,
    decision_engine_frozen BOOLEAN DEFAULT FALSE,
    resolution_status TEXT DEFAULT 'OPEN' CHECK (resolution_status IN ('OPEN', 'INVESTIGATING', 'RESOLVED', 'FALSE_POSITIVE')),
    resolved_at TIMESTAMPTZ,
    resolved_by TEXT,
    resolution_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_drift_detection_open ON fhq_calendar.drift_detection_results(resolution_status)
    WHERE resolution_status = 'OPEN';

-- ============================================
-- SECTION 6: LLM Generation Prohibition Log
-- ============================================

CREATE TABLE IF NOT EXISTS fhq_governance.llm_generation_violations (
    violation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    violation_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_id TEXT NOT NULL,
    attempted_action TEXT NOT NULL,
    data_type TEXT NOT NULL,
    blocked BOOLEAN NOT NULL DEFAULT TRUE,
    evidence_snapshot JSONB,
    reported_to TEXT DEFAULT 'CEO',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- SECTION 7: Governance Logging
-- ============================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id, action_type, action_target, action_target_type,
    initiated_by, initiated_at, decision, decision_rationale
) VALUES (
    gen_random_uuid(),
    'ZERO_TRUST_ENFORCEMENT',
    'fhq_calendar',
    'SCHEMA',
    'STIG',
    NOW(),
    'APPROVED',
    'CEO-DIR-2026-063 Zero-Trust Data Integrity Enforcement. Created: approved_data_sources, data_lineage_proof, g375_truth_gate_verifications, drift_detection_config, drift_detection_results, llm_generation_violations tables. LLM numerical generation ABSOLUTELY PROHIBITED.'
);

COMMIT;

-- ============================================
-- VERIFICATION QUERIES
-- ============================================

-- Verify approved sources
-- SELECT * FROM fhq_governance.approved_data_sources WHERE is_active = true;

-- Verify drift detection config
-- SELECT * FROM fhq_calendar.drift_detection_config WHERE is_active = true;

-- Check for any open drift violations
-- SELECT * FROM fhq_calendar.drift_detection_results WHERE resolution_status = 'OPEN';
