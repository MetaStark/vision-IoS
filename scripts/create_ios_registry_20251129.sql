-- ============================================================================
-- DIRECTIVE: CREATE_IOS_REGISTRY_20251129
-- ============================================================================
-- Authority: STIG (Schema Owner)
-- Executor: CODE
-- Purpose: Create IoS Registry for Intelligence Operating System modules
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS fhq_meta.ios_registry (
    ios_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    version TEXT NOT NULL,                       -- e.g. "2026.PRODUCTION"
    status TEXT NOT NULL CHECK (status IN ('DRAFT', 'ACTIVE', 'DEPRECATED', 'ARCHIVED')),

    -- Governance & Ownership
    owner_role TEXT NOT NULL,
    governing_adrs TEXT[] DEFAULT '{}',
    dependencies TEXT[] DEFAULT '{}',

    -- Audit & Integrity
    content_hash TEXT NOT NULL,
    vega_signature_id UUID,
    hash_chain_id UUID,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    activated_at TIMESTAMPTZ
);

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION fhq_meta.ios_registry_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ios_registry_updated_at ON fhq_meta.ios_registry;

CREATE TRIGGER trg_ios_registry_updated_at
BEFORE UPDATE ON fhq_meta.ios_registry
FOR EACH ROW
EXECUTE FUNCTION fhq_meta.ios_registry_set_updated_at();

COMMENT ON TABLE fhq_meta.ios_registry
IS 'Registry for Intelligence Operating System (IoS) modules. Tracks versioning, governance linkage, audit lineage and VEGA attestations.';

COMMIT;

-- Verification
SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns
     WHERE table_schema = 'fhq_meta' AND table_name = 'ios_registry') as column_count
FROM information_schema.tables
WHERE table_schema = 'fhq_meta' AND table_name = 'ios_registry';
