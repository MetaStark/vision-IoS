-- Migration 202: Cognitive Query Set Table
-- CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001 Phase A Step 6
-- Author: STIG (CTO)
-- Date: 2026-01-04
--
-- Purpose: Create governed query set table for pull-based orchestration.
-- Orchestrator pulls queries from this table - NO hardcoded queries in code.

BEGIN;

-- 1. Create cognitive_query_set table
CREATE TABLE IF NOT EXISTS fhq_governance.cognitive_query_set (
    query_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_template TEXT NOT NULL,
    query_type VARCHAR(50) NOT NULL,
    asset_scope VARCHAR(50),
    enabled BOOLEAN DEFAULT TRUE,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(50) NOT NULL,
    governance_approval_id UUID
);

-- 2. Add comments
COMMENT ON TABLE fhq_governance.cognitive_query_set IS
    'Governed query templates for cognitive engine. Orchestrator pulls from here - CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001';

COMMENT ON COLUMN fhq_governance.cognitive_query_set.query_template IS
    'Template with placeholders like {asset}, {regime}';

COMMENT ON COLUMN fhq_governance.cognitive_query_set.query_type IS
    'ASSET_OUTLOOK, RISK_SHIFT, MACRO_ALERT, etc.';

COMMENT ON COLUMN fhq_governance.cognitive_query_set.asset_scope IS
    'ALL, CRYPTO, EQUITIES, or specific asset ticker';

COMMENT ON COLUMN fhq_governance.cognitive_query_set.governance_approval_id IS
    'Link to G3 approval for new query types';

-- 3. Create index for enabled queries
CREATE INDEX IF NOT EXISTS idx_cognitive_query_set_enabled
ON fhq_governance.cognitive_query_set (enabled, query_type)
WHERE enabled = TRUE;

-- 4. Insert initial governed queries (CEO-approved)
INSERT INTO fhq_governance.cognitive_query_set (query_template, query_type, asset_scope, created_by)
SELECT * FROM (VALUES
    ('What is {asset} outlook given current {regime} regime?', 'ASSET_OUTLOOK', 'ALL', 'CEO'),
    ('What portfolio-level risk shift triggers are active?', 'RISK_SHIFT', 'PORTFOLIO', 'CEO'),
    ('What macro indicators suggest regime transition?', 'MACRO_ALERT', 'MACRO', 'CEO')
) AS v(query_template, query_type, asset_scope, created_by)
WHERE NOT EXISTS (
    SELECT 1 FROM fhq_governance.cognitive_query_set
    WHERE query_type = v.query_type
);

COMMIT;

-- Verification query
SELECT query_id, query_template, query_type, asset_scope, enabled, version
FROM fhq_governance.cognitive_query_set
ORDER BY query_type;
