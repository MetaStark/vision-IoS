-- ============================================================================
-- IoS-007 G4 CONSTITUTIONAL ACTIVATION
-- ============================================================================
-- Authority: CEO (Ørjan Skjold) - Constitutional Activation Order 2025-11-30
-- Certificate: CERT-IOS007-G2-SEM-20251130
-- G3 Audit: IOS007-G3-AUDIT-20251130 (PASSED)
--
-- This migration PERMANENTLY activates IoS-007 Alpha Graph Engine as a
-- Production Canonical Module under FjordHQ Operating Law.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. SCHEMA ACTIVATION: G3STATE → G4STATE
-- ============================================================================

-- Update IoS-007 status in ios_registry to PRODUCTION/G4
UPDATE fhq_meta.ios_registry
SET
    status = 'ACTIVE',
    version = '2026.PROD.G4',
    updated_at = NOW()
WHERE ios_id = 'IoS-007';

-- Update G4 activation fields
UPDATE fhq_meta.ios_registry
SET
    title = 'Alpha Graph Engine - Causal Reasoning Core',
    description = 'G4 PRODUCTION ACTIVATED. Constitutional module for cross-asset causality inference. Schema frozen. Edge weights locked.',
    version = '2026.PROD.G4',
    status = 'ACTIVE',
    canonical = TRUE,
    immutability_level = 'G4_CONSTITUTIONAL',
    modification_requires = 'FULL_G1_G4_CYCLE',
    activated_at = NOW(),
    updated_at = NOW()
WHERE ios_id = 'IoS-007';

-- ============================================================================
-- 2. EDGE WEIGHT LOCK: Production Baseline Freeze
-- ============================================================================

-- Add production_locked flag to edges if not exists
ALTER TABLE fhq_graph.edges
ADD COLUMN IF NOT EXISTS production_locked BOOLEAN DEFAULT FALSE;

ALTER TABLE fhq_graph.edges
ADD COLUMN IF NOT EXISTS locked_at TIMESTAMPTZ;

ALTER TABLE fhq_graph.edges
ADD COLUMN IF NOT EXISTS locked_by TEXT;

ALTER TABLE fhq_graph.edges
ADD COLUMN IF NOT EXISTS baseline_strength NUMERIC(10,5);

-- Lock all edge strengths as Production Baseline Values
UPDATE fhq_graph.edges
SET
    production_locked = TRUE,
    locked_at = NOW(),
    locked_by = 'G4_CONSTITUTIONAL_ACTIVATION',
    baseline_strength = strength
WHERE production_locked IS NOT TRUE;

-- Create trigger to enforce edge weight lock
CREATE OR REPLACE FUNCTION fhq_graph.enforce_edge_weight_lock()
RETURNS TRIGGER AS $$
BEGIN
    -- Check if edge is production locked
    IF OLD.production_locked = TRUE THEN
        -- Only allow changes via IoS-005 recalibration pathway
        IF NEW.strength != OLD.strength AND
           (NEW.ios005_recalibration_id IS NULL OR NEW.ios005_recalibration_id = OLD.ios005_recalibration_id) THEN
            RAISE EXCEPTION 'G4_VIOLATION: Edge weight modification blocked. Edge % is production-locked. Use IoS-005 Recalibration Pathway.', OLD.edge_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add recalibration tracking column
ALTER TABLE fhq_graph.edges
ADD COLUMN IF NOT EXISTS ios005_recalibration_id UUID;

-- Create the enforcement trigger
DROP TRIGGER IF EXISTS trg_enforce_edge_weight_lock ON fhq_graph.edges;
CREATE TRIGGER trg_enforce_edge_weight_lock
    BEFORE UPDATE ON fhq_graph.edges
    FOR EACH ROW
    EXECUTE FUNCTION fhq_graph.enforce_edge_weight_lock();

-- ============================================================================
-- 3. IoS-005 BINDING: Statistical Contract Activation
-- ============================================================================

-- Create trigger to enforce IoS-005 binding on inference_log
CREATE OR REPLACE FUNCTION fhq_graph.enforce_ios005_binding()
RETURNS TRIGGER AS $$
BEGIN
    -- G4 Mandate: All inference events must have IoS-005 linkage
    -- Exception: Allow initial inference creation, validation happens post-insert

    -- If this is an UPDATE (post-validation), check ios005 fields
    IF TG_OP = 'UPDATE' THEN
        -- If moving to validated state, ensure all required fields are present
        IF NEW.ios005_validated = TRUE THEN
            IF NEW.ios005_audit_id IS NULL THEN
                RAISE EXCEPTION 'G4_VIOLATION: ios005_validated=TRUE requires ios005_audit_id reference';
            END IF;
            IF NEW.ios005_evidence_hash IS NULL THEN
                RAISE EXCEPTION 'G4_VIOLATION: ios005_validated=TRUE requires ios005_evidence_hash';
            END IF;
        END IF;
    END IF;

    -- Require lineage_hash for all entries (traceability)
    IF NEW.lineage_hash IS NULL AND NEW.data_hash IS NULL THEN
        RAISE EXCEPTION 'G4_VIOLATION: Inference event requires traceability (lineage_hash or data_hash)';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the enforcement trigger
DROP TRIGGER IF EXISTS trg_enforce_ios005_binding ON fhq_graph.inference_log;
CREATE TRIGGER trg_enforce_ios005_binding
    BEFORE INSERT OR UPDATE ON fhq_graph.inference_log
    FOR EACH ROW
    EXECUTE FUNCTION fhq_graph.enforce_ios005_binding();

-- Add constraint to ensure production inference events are validated
ALTER TABLE fhq_graph.inference_log
ADD COLUMN IF NOT EXISTS production_mode BOOLEAN DEFAULT FALSE;

-- ============================================================================
-- 4. GOLDEN SAMPLE ANCHORING
-- ============================================================================

-- Create golden_samples table if not exists
CREATE TABLE IF NOT EXISTS fhq_meta.golden_samples (
    sample_id TEXT PRIMARY KEY,
    ios_id TEXT NOT NULL,
    sample_type TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    date_range_start DATE NOT NULL,
    date_range_end DATE NOT NULL,
    sample_data JSONB NOT NULL,
    sample_hash TEXT NOT NULL,
    g3_audit_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    superseded_by TEXT,
    superseded_at TIMESTAMPTZ,
    CONSTRAINT chk_sample_type CHECK (sample_type IN ('REGRESSION_BASELINE', 'CALIBRATION_ANCHOR', 'AUDIT_SNAPSHOT'))
);

-- Register the Golden Sample
INSERT INTO fhq_meta.golden_samples (
    sample_id,
    ios_id,
    sample_type,
    row_count,
    date_range_start,
    date_range_end,
    sample_data,
    sample_hash,
    g3_audit_id,
    created_at,
    created_by,
    is_active
)
VALUES (
    'GS-IOS007-20251130',
    'IoS-007',
    'REGRESSION_BASELINE',
    100,
    '2015-01-01',
    '2025-11-28',
    '{
        "description": "100-row Golden Sample representing canonical causal patterns across 10-year history",
        "sampling_method": "Percentile-based stratified sampling",
        "columns": ["sample_row", "snapshot_id", "date", "liquidity_value", "gravity_value", "node_count", "edge_count", "graph_density", "data_hash"],
        "key_samples": {
            "earliest": {"row": 1, "date": "2015-01-01", "liquidity": 96.83, "gravity": 0.055},
            "covid_crash": {"row": 42, "date": "2020-03-06", "liquidity": 688.53, "gravity": -0.167},
            "ftx_collapse": {"row": 69, "date": "2022-11-11", "liquidity": -95.42, "gravity": 0.300},
            "etf_rally": {"row": 81, "date": "2024-01-05", "liquidity": 75.04, "gravity": 0.398},
            "latest": {"row": 100, "date": "2025-10-31", "liquidity": 85.60, "gravity": 0.358}
        },
        "statistical_summary": {
            "liquidity_mean": 81.96,
            "liquidity_std": 143.23,
            "gravity_mean": 0.059,
            "gravity_std": 0.382
        }
    }'::jsonb,
    'ae93f7116c71c9b64cbc63a82dd9f033013c455fc3008a569f228f6e5dc815a9',
    'IOS007-G3-AUDIT-20251130',
    NOW(),
    'STIG',
    TRUE
)
ON CONFLICT (sample_id) DO UPDATE SET
    is_active = TRUE,
    sample_data = EXCLUDED.sample_data;

-- ============================================================================
-- 5. GOVERNANCE ACTION LOG
-- ============================================================================

-- Create signature for G4 activation
INSERT INTO vision_verification.operation_signatures (
    signature_id,
    operation_type,
    operation_id,
    operation_table,
    operation_schema,
    signing_agent,
    signing_key_id,
    signature_value,
    signed_payload,
    verified,
    verified_at,
    verified_by,
    created_at,
    hash_chain_id,
    previous_signature_id
)
SELECT
    gen_random_uuid(),
    'IOS_MODULE_G4_CONSTITUTIONAL_ACTIVATION',
    gen_random_uuid(),
    'ios_registry',
    'fhq_meta',
    'STIG',
    'STIG-EC003-IOS007-G4',
    encode(sha256(('IOS007-G4-ACTIVATION-' || NOW()::text)::bytea), 'hex'),
    '{
        "ios_id": "IoS-007",
        "activation_type": "G4_CONSTITUTIONAL",
        "authority": "CEO (Ørjan Skjold)",
        "certificate": "CERT-IOS007-G2-SEM-20251130",
        "g3_audit": "IOS007-G3-AUDIT-20251130",
        "schema_state": "G4STATE",
        "edge_lock": "PRODUCTION_BASELINE_FROZEN",
        "ios005_binding": "ACTIVE",
        "golden_sample": "GS-IOS007-20251130"
    }'::jsonb,
    TRUE,
    NOW(),
    'VEGA',
    NOW(),
    'HC-IOS-007-2026',
    (SELECT signature_id FROM vision_verification.operation_signatures
     WHERE operation_type LIKE '%IOS007%' OR hash_chain_id = 'HC-IOS-007-2026'
     ORDER BY created_at DESC LIMIT 1);

-- ============================================================================
-- 6. ACTIVATION VERIFICATION
-- ============================================================================

-- Create activation verification view
CREATE OR REPLACE VIEW fhq_graph.v_g4_activation_status AS
SELECT
    'IoS-007' as ios_id,
    'Alpha Graph Engine' as module_name,
    '2026.PROD.G4' as version,
    'PRODUCTION' as schema_state,
    (SELECT COUNT(*) FROM fhq_graph.edges WHERE production_locked = TRUE) as locked_edges,
    (SELECT COUNT(*) FROM fhq_graph.edges) as total_edges,
    (SELECT COUNT(*) FROM fhq_graph.nodes) as total_nodes,
    (SELECT COUNT(*) FROM fhq_graph.snapshots) as total_snapshots,
    (SELECT is_active FROM fhq_meta.golden_samples WHERE sample_id = 'GS-IOS007-20251130') as golden_sample_active,
    NOW() as verification_timestamp;

-- ============================================================================
-- CONSTITUTIONAL DECLARATION
-- ============================================================================
-- IoS-007 Alpha Graph Engine is now a Production Canonical Module.
-- Any modification to schema, ontology, or edge weights requires:
--   1. Full ADR-004 G1→G4 migration cycle
--   2. CEO approval
--   3. VEGA certification
--
-- This is Operating Law. Violations are Class A governance infractions.
-- ============================================================================

COMMIT;

-- Final verification
SELECT * FROM fhq_graph.v_g4_activation_status;
