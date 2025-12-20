-- ============================================================================
-- MIGRATION: 035_ios006_macro_factor_foundation.sql
-- PURPOSE: IoS-006 Global Macro & Factor Integration Engine — G0 Foundation
-- AUTHORITY: FINN (Tier-1 Research) — Owner
-- VALIDATOR: IoS-005 (Scientific Audit) — CONSTITUTIONAL
-- GOVERNANCE: VEGA (Compliance)
-- TECHNICAL: STIG (CTO)
-- EXECUTION: CODE (EC-011)
-- ADR COMPLIANCE: ADR-002, ADR-003, ADR-011, ADR-013
-- STATUS: G0 SUBMISSION
-- DATE: 2025-11-30
-- ============================================================================
--
-- STRATEGIC HYPOTHESIS:
-- "Price is the shadow, Macro is the object."
--
-- IoS-006 is a Feature Filtration System designed to reject 95% of candidates.
-- Only features that survive IoS-005 significance testing may enter future HMM v3.0.
--
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: CREATE fhq_macro SCHEMA
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS fhq_macro;

COMMENT ON SCHEMA fhq_macro IS
'IoS-006 Global Macro & Factor Integration Engine.
Houses the Macro Feature Registry (MFR), raw staging, canonical series,
and stationarity test results. All features must be registered here
before IoS-005 can test them (ADR-013 compliance).
Owner: FINN | Validator: IoS-005 | Governance: VEGA';

-- ============================================================================
-- SECTION 2: MACRO FEATURE REGISTRY (MFR) — The Canonical Truth Source
-- ============================================================================
-- Every candidate variable MUST be registered here before testing.
-- This prevents ad-hoc p-hacking and ensures ADR-013 lineage.

CREATE TABLE IF NOT EXISTS fhq_macro.feature_registry (
    feature_id TEXT PRIMARY KEY,                    -- Canonical ID (e.g., US_M2_YOY)
    feature_name TEXT NOT NULL,                     -- Human-readable name
    description TEXT,                               -- Detailed description

    -- Provenance (ADR-013 Lineage)
    provenance TEXT NOT NULL,                       -- Source (FRED, Bloomberg, Glassnode, Yahoo)
    source_ticker TEXT,                             -- Original source ticker/series ID
    source_url TEXT,                                -- API endpoint or data source URL

    -- Temporal Properties
    frequency TEXT NOT NULL CHECK (frequency IN (
        'TICK', 'MINUTE', 'HOURLY', 'DAILY', 'WEEKLY', 'MONTHLY', 'QUARTERLY', 'ANNUAL'
    )),
    lag_period_days INTEGER NOT NULL DEFAULT 0,     -- Publication delay in days
    history_start_date DATE,                        -- Earliest available data
    history_end_date DATE,                          -- Latest available data

    -- Statistical Properties
    stationarity_method TEXT CHECK (stationarity_method IN (
        'NONE', 'DIFF', 'LOG_DIFF', 'SECOND_DIFF', 'Z_SCORE', 'PCT_CHANGE', 'SEASONAL_DIFF'
    )),
    is_stationary BOOLEAN DEFAULT FALSE,            -- Has passed ADF test
    adf_p_value NUMERIC(6,5),                       -- Latest ADF test p-value
    adf_test_date TIMESTAMPTZ,                      -- When stationarity was last verified

    -- Cluster Assignment (Alpha Cubes)
    cluster TEXT NOT NULL CHECK (cluster IN (
        'LIQUIDITY',    -- Cluster A: M2, Net Liquidity, TGA
        'CREDIT',       -- Cluster B: HY Spreads, Yield Curve, MOVE
        'VOLATILITY',   -- Cluster C: VIX Term Structure, Implied vs Realized
        'FACTOR',       -- Cluster D: DXY, Real Rates, Tech Beta
        'ONCHAIN',      -- Blockchain-native metrics
        'SENTIMENT',    -- Surveys, positioning data
        'OTHER'         -- Uncategorized
    )),

    -- Economic Hypothesis
    hypothesis TEXT,                                -- Why this feature might matter
    expected_direction TEXT CHECK (expected_direction IN (
        'POSITIVE', 'NEGATIVE', 'AMBIGUOUS'
    )),

    -- Governance Status
    status TEXT NOT NULL DEFAULT 'CANDIDATE' CHECK (status IN (
        'CANDIDATE',        -- Registered, awaiting testing
        'TESTING',          -- Currently being evaluated by IoS-005
        'REJECTED',         -- Failed significance test (p >= 0.05)
        'SIGNIFICANT',      -- Passed significance test (p < 0.05)
        'GOLDEN',           -- Passed OOS validation, ready for HMM integration
        'DEPRECATED'        -- No longer maintained
    )),

    -- IoS-005 Integration
    ios005_tested BOOLEAN DEFAULT FALSE,
    ios005_p_value NUMERIC(6,5),                    -- Significance test p-value
    ios005_test_date TIMESTAMPTZ,
    ios005_evidence_hash TEXT,                      -- Link to evidence file

    -- Lineage (ADR-011)
    content_hash TEXT,
    lineage_hash TEXT,
    hash_prev TEXT,
    hash_self TEXT,

    -- Metadata
    created_by TEXT NOT NULL DEFAULT 'FINN',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT unique_feature_source UNIQUE (provenance, source_ticker)
);

-- Index for cluster-based queries
CREATE INDEX IF NOT EXISTS idx_mfr_cluster ON fhq_macro.feature_registry(cluster);
CREATE INDEX IF NOT EXISTS idx_mfr_status ON fhq_macro.feature_registry(status);
CREATE INDEX IF NOT EXISTS idx_mfr_stationary ON fhq_macro.feature_registry(is_stationary);

COMMENT ON TABLE fhq_macro.feature_registry IS
'Macro Feature Registry (MFR) — The canonical truth source for all macro variables.
IoS-005 is FORBIDDEN from testing any feature not registered here.
Expected: 95% of features will be REJECTED (Null Result Regime).';

-- ============================================================================
-- SECTION 3: RAW STAGING TABLE
-- ============================================================================
-- Ingested data lands here before canonicalization.

CREATE TABLE IF NOT EXISTS fhq_macro.raw_staging (
    staging_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_id TEXT NOT NULL REFERENCES fhq_macro.feature_registry(feature_id),

    -- Data Point
    timestamp TIMESTAMPTZ NOT NULL,
    value_raw NUMERIC NOT NULL,                     -- Original value as received

    -- Ingestion Metadata
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ingested_by TEXT NOT NULL DEFAULT 'CEIO',       -- Data ingestion agent
    source_response_hash TEXT,                      -- Hash of API response for audit

    -- Quality Flags
    is_preliminary BOOLEAN DEFAULT FALSE,           -- Subject to revision
    is_revised BOOLEAN DEFAULT FALSE,               -- Has been revised from preliminary
    revision_of UUID,                               -- Reference to preliminary value

    -- Uniqueness
    CONSTRAINT unique_staging_point UNIQUE (feature_id, timestamp, is_revised)
);

CREATE INDEX IF NOT EXISTS idx_staging_feature ON fhq_macro.raw_staging(feature_id);
CREATE INDEX IF NOT EXISTS idx_staging_timestamp ON fhq_macro.raw_staging(timestamp);

COMMENT ON TABLE fhq_macro.raw_staging IS
'Raw staging area for macro data. Data flows: External Source → raw_staging → canonical_series.
Revisions are tracked via is_preliminary and is_revised flags.';

-- ============================================================================
-- SECTION 4: CANONICAL SERIES TABLE
-- ============================================================================
-- Immutable historical record per ADR-013.

CREATE TABLE IF NOT EXISTS fhq_macro.canonical_series (
    series_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_id TEXT NOT NULL REFERENCES fhq_macro.feature_registry(feature_id),

    -- Data Point
    timestamp TIMESTAMPTZ NOT NULL,
    value_raw NUMERIC NOT NULL,                     -- Original value
    value_transformed NUMERIC,                      -- After stationarity transform

    -- Transformation Applied
    transformation_method TEXT,                     -- DIFF, LOG_DIFF, etc.
    transformation_params JSONB,                    -- Any parameters used

    -- Lag Adjustment
    publication_date TIMESTAMPTZ,                   -- When data was actually available
    effective_date TIMESTAMPTZ,                     -- When data can be used (after lag)

    -- Lineage (ADR-011)
    data_hash TEXT NOT NULL,
    lineage_hash TEXT,
    hash_prev TEXT,
    hash_self TEXT,

    -- Metadata
    canonicalized_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    canonicalized_by TEXT NOT NULL DEFAULT 'STIG',

    -- Uniqueness (one canonical value per feature per timestamp)
    CONSTRAINT unique_canonical_point UNIQUE (feature_id, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_canonical_feature ON fhq_macro.canonical_series(feature_id);
CREATE INDEX IF NOT EXISTS idx_canonical_timestamp ON fhq_macro.canonical_series(timestamp);
CREATE INDEX IF NOT EXISTS idx_canonical_effective ON fhq_macro.canonical_series(effective_date);

COMMENT ON TABLE fhq_macro.canonical_series IS
'Canonical (immutable) macro series per ADR-013. Contains both raw and transformed values.
effective_date accounts for publication lag to prevent look-ahead bias.';

-- ============================================================================
-- SECTION 5: STATIONARITY TESTS TABLE
-- ============================================================================
-- Records all ADF tests for audit trail.

CREATE TABLE IF NOT EXISTS fhq_macro.stationarity_tests (
    test_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_id TEXT NOT NULL REFERENCES fhq_macro.feature_registry(feature_id),

    -- Test Parameters
    test_type TEXT NOT NULL DEFAULT 'ADF',          -- Augmented Dickey-Fuller
    test_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sample_start DATE NOT NULL,
    sample_end DATE NOT NULL,
    n_observations INTEGER NOT NULL,

    -- Test Results
    test_statistic NUMERIC NOT NULL,
    p_value NUMERIC(6,5) NOT NULL,
    critical_value_1pct NUMERIC,
    critical_value_5pct NUMERIC,
    critical_value_10pct NUMERIC,

    -- Decision
    is_stationary BOOLEAN NOT NULL,                 -- p < 0.05
    transformation_required TEXT,                   -- What transform to apply if non-stationary

    -- After Transformation (if applied)
    post_transform_statistic NUMERIC,
    post_transform_p_value NUMERIC(6,5),
    post_transform_stationary BOOLEAN,

    -- Lineage
    test_config_hash TEXT,
    hash_self TEXT,

    -- Metadata
    tested_by TEXT NOT NULL DEFAULT 'STIG',

    CONSTRAINT chk_p_value_range CHECK (p_value >= 0 AND p_value <= 1)
);

CREATE INDEX IF NOT EXISTS idx_stationarity_feature ON fhq_macro.stationarity_tests(feature_id);
CREATE INDEX IF NOT EXISTS idx_stationarity_date ON fhq_macro.stationarity_tests(test_date);

COMMENT ON TABLE fhq_macro.stationarity_tests IS
'Audit trail of all stationarity (ADF) tests. Non-stationary data is NEVER passed to IoS-005.
The Stationarity Gate is a critical filter in the feature pipeline.';

-- ============================================================================
-- SECTION 6: FEATURE SIGNIFICANCE TABLE
-- ============================================================================
-- Records IoS-005 significance test results for each feature.

CREATE TABLE IF NOT EXISTS fhq_macro.feature_significance (
    significance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_id TEXT NOT NULL REFERENCES fhq_macro.feature_registry(feature_id),

    -- Test Configuration
    test_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    target_asset TEXT NOT NULL,                     -- BTC-USD, ETH-USD, PORTFOLIO
    test_type TEXT NOT NULL,                        -- CORRELATION, GRANGER, PERMUTATION
    sample_start DATE NOT NULL,
    sample_end DATE NOT NULL,
    n_observations INTEGER NOT NULL,

    -- Correlation Results
    correlation_coefficient NUMERIC(6,5),
    correlation_p_value NUMERIC(6,5),

    -- Permutation Test (IoS-005 standard)
    n_permutations INTEGER DEFAULT 1000,
    permutation_p_value NUMERIC(6,5),

    -- Bootstrap Analysis
    n_bootstrap INTEGER DEFAULT 1000,
    bootstrap_p_value NUMERIC(6,5),
    bootstrap_ci_lower NUMERIC(8,5),
    bootstrap_ci_upper NUMERIC(8,5),

    -- Granger Causality (Optional)
    granger_f_statistic NUMERIC,
    granger_p_value NUMERIC(6,5),
    optimal_lag INTEGER,

    -- Decision
    is_significant BOOLEAN NOT NULL,                -- p < 0.05 (Bonferroni adjusted)
    significance_threshold NUMERIC(6,5) DEFAULT 0.05,
    bonferroni_adjusted BOOLEAN DEFAULT FALSE,

    -- Out-of-Sample Validation
    oos_validated BOOLEAN DEFAULT FALSE,
    oos_test_date TIMESTAMPTZ,
    oos_p_value NUMERIC(6,5),
    oos_sample_start DATE,
    oos_sample_end DATE,

    -- Final Classification
    classification TEXT CHECK (classification IN (
        'REJECTED',         -- Not significant
        'SIGNIFICANT_IS',   -- Significant in-sample only
        'GOLDEN'            -- Significant in-sample AND out-of-sample
    )),

    -- Lineage
    ios005_audit_id UUID,                           -- Reference to scientific_audit_log
    evidence_hash TEXT,
    hash_self TEXT,

    -- Metadata
    tested_by TEXT NOT NULL DEFAULT 'IoS-005',

    CONSTRAINT chk_correlation_range CHECK (correlation_coefficient >= -1 AND correlation_coefficient <= 1)
);

CREATE INDEX IF NOT EXISTS idx_significance_feature ON fhq_macro.feature_significance(feature_id);
CREATE INDEX IF NOT EXISTS idx_significance_asset ON fhq_macro.feature_significance(target_asset);
CREATE INDEX IF NOT EXISTS idx_significance_result ON fhq_macro.feature_significance(is_significant);

COMMENT ON TABLE fhq_macro.feature_significance IS
'IoS-005 significance test results for macro features. Expected: 95% will be REJECTED.
Only GOLDEN features (significant + OOS validated) may enter HMM v3.0 (IoS-003B).';

-- ============================================================================
-- SECTION 7: REGISTER IoS-006 IN IOS_REGISTRY
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
    experimental_classification,
    risk_multiplier,
    immutability_level,
    canonical,
    modification_requires
) VALUES (
    'IoS-006',
    'Global Macro & Factor Integration Engine',
    'Feature Filtration System for macro variables. Implements the Macro Feature Registry (MFR), ' ||
    'stationarity pipeline, and significance testing framework. Operates under the Expected Null Result ' ||
    'Regime: 95% of candidates are expected to be rejected. Only features that survive IoS-005 audit ' ||
    'may enter future HMM v3.0 (IoS-003B). Strategic hypothesis: Price is the shadow, Macro is the object.',
    '2026.PROD.G0',
    'DRAFT',
    'FINN',
    ARRAY['ADR-002', 'ADR-003', 'ADR-011', 'ADR-013'],
    ARRAY['IoS-002', 'IoS-005'],
    encode(sha256('IoS-006_G0_FOUNDATION_20251130'::bytea), 'hex'),
    'UNCLASSIFIED',
    1.0,
    'MUTABLE',
    FALSE,
    'OWNER'
) ON CONFLICT (ios_id) DO UPDATE SET
    version = '2026.PROD.G0',
    status = 'DRAFT',
    updated_at = NOW();

-- ============================================================================
-- SECTION 8: REGISTER TASK IN TASK_REGISTRY
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
    updated_at,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'MACRO_FACTOR_ENGINE_V1',
    'FEATURE_PIPELINE',
    'IOS_006_INTERNAL',
    'FINN',
    'CODE',
    ARRAY['fhq_macro', 'fhq_market'],
    ARRAY['fhq_macro'],
    'G0',
    FALSE,
    FALSE,
    'IoS-006 Global Macro & Factor Integration Engine. Feature Filtration System implementing MFR, ' ||
    'stationarity pipeline (ADF tests), and IoS-005 significance integration. Operates under Expected ' ||
    'Null Result Regime. 95% rejection rate expected.',
    'REGISTERED',
    'STIG',
    NOW(),
    NOW(),
    'HC-IOS-006-2026'
) ON CONFLICT (task_name) DO UPDATE SET
    gate_level = 'G0',
    updated_at = NOW();

-- ============================================================================
-- SECTION 9: CREATE HASH CHAIN FOR IoS-006
-- ============================================================================

INSERT INTO vision_verification.hash_chains (
    chain_id,
    chain_type,
    chain_scope,
    genesis_hash,
    current_hash,
    chain_length,
    schema_frozen,
    integrity_verified,
    created_by,
    created_at,
    updated_at
) VALUES (
    'HC-IOS-006-2026',
    'IOS_MODULE',
    'fhq_macro.feature_registry',
    encode(sha256('IoS-006_GENESIS_20251130'::bytea), 'hex'),
    encode(sha256('IoS-006_GENESIS_20251130'::bytea), 'hex'),
    1,
    FALSE,
    TRUE,
    'STIG',
    NOW(),
    NOW()
) ON CONFLICT (chain_id) DO UPDATE SET
    updated_at = NOW();

-- ============================================================================
-- SECTION 10: LOG GOVERNANCE ACTION (G0 SUBMISSION)
-- ============================================================================

DO $$
DECLARE
    v_signature_id UUID := gen_random_uuid();
    v_action_id UUID := gen_random_uuid();
    v_payload JSONB;
    v_signature_value TEXT;
BEGIN
    v_payload := jsonb_build_object(
        'action_type', 'IOS_MODULE_G0_SUBMISSION',
        'action_target', 'IoS-006',
        'decision', 'APPROVED',
        'initiated_by', 'STIG',
        'timestamp', NOW()::text,
        'chain_id', 'HC-IOS-006-2026',
        'module_spec', jsonb_build_object(
            'title', 'Global Macro & Factor Integration Engine',
            'owner', 'FINN',
            'validator', 'IoS-005',
            'hypothesis', 'Price is the shadow, Macro is the object',
            'expected_rejection_rate', '95%',
            'feature_clusters', ARRAY['LIQUIDITY', 'CREDIT', 'VOLATILITY', 'FACTOR']
        )
    );

    v_signature_value := encode(sha256(v_payload::text::bytea), 'hex');

    INSERT INTO vision_verification.operation_signatures (
        signature_id, operation_type, operation_id, operation_table, operation_schema,
        signing_agent, signing_key_id, signature_value, signed_payload,
        verified, verified_at, verified_by, created_at, hash_chain_id
    ) VALUES (
        v_signature_id, 'IOS_MODULE_G0_SUBMISSION', v_action_id, 'governance_actions_log',
        'fhq_governance', 'STIG', 'STIG-EC003-IOS006-G0', v_signature_value, v_payload,
        TRUE, NOW(), 'STIG', NOW(), 'HC-IOS-006-2026'
    );

    INSERT INTO fhq_governance.governance_actions_log (
        action_id, action_type, action_target, action_target_type, initiated_by,
        initiated_at, decision, decision_rationale, vega_reviewed, vega_override,
        vega_notes, hash_chain_id, signature_id
    ) VALUES (
        v_action_id, 'IOS_MODULE_G0_SUBMISSION', 'IoS-006', 'IOS_MODULE', 'STIG', NOW(),
        'APPROVED',
        'G0 SUBMISSION: IoS-006 Global Macro & Factor Integration Engine. ' ||
        'Schema fhq_macro created with: feature_registry (MFR), raw_staging, canonical_series, ' ||
        'stationarity_tests, feature_significance tables. Dependencies: IoS-002 (Indicators), ' ||
        'IoS-005 (Constitutional Validator). Operates under Expected Null Result Regime (95% rejection). ' ||
        'Ready for G1 Technical Validation.',
        FALSE, FALSE,
        'Awaiting VEGA review. IoS-006 must demonstrate stationarity pipeline and IoS-005 integration before G1.',
        'HC-IOS-006-2026', v_signature_id
    );

    RAISE NOTICE 'IoS-006 G0 SUBMISSION: action_id=%, signature_id=%', v_action_id, v_signature_id;
END $$;

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================
-- SELECT * FROM fhq_meta.ios_registry WHERE ios_id = 'IoS-006';
-- SELECT schemaname, tablename FROM pg_tables WHERE schemaname = 'fhq_macro';
-- SELECT * FROM fhq_governance.task_registry WHERE task_name = 'MACRO_FACTOR_ENGINE_V1';
-- SELECT * FROM vision_verification.hash_chains WHERE chain_id = 'HC-IOS-006-2026';
