-- ============================================================================
-- Migration: 355_g15_generation_variance_columns.sql
-- Directive: CEO-DIR-2026-G1.5-GENERATION-VARIANCE-001
-- Purpose: Add generation_regime and causal_depth_target columns for variance tagging
-- Executor: STIG (EC-003)
-- Date: 2026-01-26
-- ============================================================================

BEGIN;

-- ============================================================================
-- ADD: generation_regime column for tracking hypothesis generation context
-- Required by Section 3.2 of CEO-DIR-2026-G1.5-GENERATION-VARIANCE-001
-- ============================================================================
ALTER TABLE fhq_learning.hypothesis_canon
ADD COLUMN IF NOT EXISTS generation_regime VARCHAR(50) DEFAULT 'STANDARD';

COMMENT ON COLUMN fhq_learning.hypothesis_canon.generation_regime IS
'Generation context: STANDARD (default), HIGH_CAUSAL_PRESSURE (G1.5 variance directive)';

-- ============================================================================
-- ADD: causal_depth_target column for tracking intended depth
-- Required by Section 3.2 of CEO-DIR-2026-G1.5-GENERATION-VARIANCE-001
-- ============================================================================
ALTER TABLE fhq_learning.hypothesis_canon
ADD COLUMN IF NOT EXISTS causal_depth_target INTEGER DEFAULT NULL;

COMMENT ON COLUMN fhq_learning.hypothesis_canon.causal_depth_target IS
'Target causal depth when generated under HIGH_CAUSAL_PRESSURE regime (4+ for variance)';

-- ============================================================================
-- INDEX: Support filtering by generation_regime for G1.5 analysis
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_hypothesis_canon_generation_regime
ON fhq_learning.hypothesis_canon(generation_regime)
WHERE generation_regime != 'STANDARD';

-- ============================================================================
-- EVIDENCE: Register migration
-- ============================================================================
INSERT INTO fhq_governance.canonical_evidence (
    evidence_type,
    evidence_category,
    agent_id,
    execution_timestamp,
    evidence_hash,
    evidence_payload,
    vega_signature,
    vega_public_key,
    registered_by,
    registered_at,
    authority,
    adr_compliance,
    audit_notes,
    immutable
) VALUES (
    'SCHEMA_MIGRATION',
    'G15_VARIANCE_DIRECTIVE',
    'STIG',
    NOW(),
    encode(sha256('355_g15_generation_variance_columns|2026-01-26|STIG'::bytea), 'hex'),
    jsonb_build_object(
        'migration', '355_g15_generation_variance_columns.sql',
        'directive', 'CEO-DIR-2026-G1.5-GENERATION-VARIANCE-001',
        'columns_added', ARRAY['generation_regime', 'causal_depth_target'],
        'purpose', 'Enable controlled generation variance tagging under G1.5 freeze',
        'freeze_preserved', true
    ),
    'PENDING_VEGA_ATTESTATION',
    'PENDING_VEGA_ATTESTATION',
    'STIG',
    NOW(),
    'CEO',
    ARRAY['ADR-011', 'ADR-013', 'G1.5'],
    'Controlled generation variance - freeze on evaluative logic preserved',
    true
);

COMMIT;
