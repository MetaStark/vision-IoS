-- ============================================================================
-- MIGRATION 020 v2: Create adr_registry and register ADR-014
-- ============================================================================

-- Create table if not exists
CREATE TABLE IF NOT EXISTS fhq_meta.adr_registry (
    adr_id VARCHAR(20) PRIMARY KEY,
    adr_title TEXT NOT NULL,
    adr_status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    adr_type VARCHAR(30) NOT NULL,
    current_version VARCHAR(30) NOT NULL,
    approval_authority VARCHAR(20),
    effective_date DATE,
    created_by TEXT DEFAULT 'SYSTEM',
    owner TEXT,
    governance_tier TEXT DEFAULT 'Tier-3',
    description TEXT,
    affects TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    vega_attested BOOLEAN DEFAULT FALSE,
    review_cycle_months INTEGER DEFAULT 12,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT adr_status_check CHECK (adr_status IN ('DRAFT', 'APPROVED', 'DEPRECATED', 'SUPERSEDED')),
    CONSTRAINT adr_type_check CHECK (adr_type IN ('COMPLIANCE', 'OPERATIONAL', 'CONSTITUTIONAL', 'ARCHITECTURAL'))
);

CREATE INDEX IF NOT EXISTS idx_adr_registry_status ON fhq_meta.adr_registry(adr_status);

-- Insert ADR-014
INSERT INTO fhq_meta.adr_registry (
    adr_id, adr_title, adr_status, adr_type, current_version,
    approval_authority, effective_date, created_by, owner, governance_tier,
    description, affects, metadata
) VALUES (
    'ADR-014',
    'Executive Activation & Sub-Executive Governance Charter',
    'APPROVED',
    'CONSTITUTIONAL',
    '2026.PRODUCTION',
    'CEO',
    '2025-11-28',
    'CEO',
    'CEO',
    'Tier-1',
    'Establishes Tier-2 Sub-Executive C-Suite (CSEO, CDMO, CRIO, CEIO, CFAO) with Executive Control Framework (ECF)',
    ARRAY['fhq_governance', 'fhq_org', 'fhq_meta', 'All Tier-2 Agents'],
    '{"authority_chain": "ADR-001 → ADR-014", "sub_executives": ["CSEO","CDMO","CRIO","CEIO","CFAO"]}'::jsonb
) ON CONFLICT (adr_id) DO UPDATE SET adr_status = EXCLUDED.adr_status, updated_at = NOW();

-- Verify
SELECT adr_id, adr_title, adr_status, governance_tier FROM fhq_meta.adr_registry WHERE adr_id = 'ADR-014';

\echo '✅ ADR-014 registered'
