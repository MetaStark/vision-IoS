-- ============================================================
-- IoS GOVERNANCE RECONCILIATION
-- ============================================================
-- Migration: 056_ios_governance_reconciliation.sql
-- Authority: BOARD (Vice-CEO)
-- Technical Lead: STIG (CTO)
-- Purpose: Reconcile registry entries to reflect actual gate progression
-- ADR Compliance: ADR-013 (One-Source-Truth), ADR-004 (Change Gates)
-- ============================================================
-- RATIONALE: Registry audit revealed mismatch between operational
--            system state and governance records. This migration
--            updates registry to reflect actual gate progression
--            without prematurely elevating to constitutional status.
-- ============================================================

-- ============================================================
-- SECTION 1: EXPAND STATUS CONSTRAINT
-- ============================================================
-- Add new gate-specific status values to track progression accurately

ALTER TABLE fhq_meta.ios_registry
DROP CONSTRAINT IF EXISTS ios_registry_status_check;

ALTER TABLE fhq_meta.ios_registry
ADD CONSTRAINT ios_registry_status_check
CHECK (status = ANY (ARRAY[
    'DRAFT'::text,              -- Initial registration
    'G0_SUBMITTED'::text,       -- G0 specification submitted
    'G1_TECHNICAL'::text,       -- G1 technical validation passed
    'G2_VALIDATED'::text,       -- G2 governance validation passed
    'G3_INTEGRATED'::text,      -- G3 integration testing passed
    'G3_COMPLETE'::text,        -- G3 complete (legacy)
    'G4_CONSTITUTIONAL'::text,  -- G4 constitutional activation
    'ACTIVE'::text,             -- Production active
    'GOVERNANCE-ACTIVE'::text,  -- Active under governance review
    'DEPRECATED'::text,         -- Deprecated
    'ARCHIVED'::text            -- Archived
]));

COMMENT ON CONSTRAINT ios_registry_status_check ON fhq_meta.ios_registry IS
'ADR-004 Gate Status Progression: DRAFT → G0 → G1 → G2 → G3 → G4/ACTIVE';

-- ============================================================
-- SECTION 2: IoS-008 — Runtime Decision Engine
-- ============================================================
-- Status: G2_VALIDATED (passed G1/G2/G3 logic, no G4 activation)
-- ============================================================

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
    modification_requires,
    governance_state
) VALUES (
    'IoS-008',
    'Runtime Decision Engine',
    'GOVERNANCE RECONCILIATION: Registered at G2_VALIDATED. Core decision layer that transforms perception snapshots and alpha signals into actionable portfolio decisions. Passed G1/G2/G3 validation but has NOT undergone G4 constitutional activation.',
    '2026.PROD.G2',
    'G2_VALIDATED',
    'LINE',
    ARRAY['ADR-001', 'ADR-002', 'ADR-003', 'ADR-004', 'ADR-011', 'ADR-012', 'ADR-013'],
    ARRAY['IoS-004', 'IoS-005', 'IoS-007'],
    encode(sha256(('IoS-008-RECONCILIATION-' || NOW()::TEXT)::bytea), 'hex'),
    'TIER-1_CRITICAL',
    1.00,
    'MUTABLE',
    FALSE,
    'G4 Constitutional Activation Required',
    'G2_COMPLETE'
)
ON CONFLICT (ios_id) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    version = EXCLUDED.version,
    status = EXCLUDED.status,
    dependencies = EXCLUDED.dependencies,
    canonical = EXCLUDED.canonical,
    governance_state = EXCLUDED.governance_state,
    updated_at = NOW();

-- ============================================================
-- SECTION 3: IoS-012 — Execution Engine
-- ============================================================
-- Status: G3_INTEGRATED (passed G1/G2/G3, no G4 activation)
-- ============================================================

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
    modification_requires,
    governance_state
) VALUES (
    'IoS-012',
    'Execution Engine',
    'GOVERNANCE RECONCILIATION: Registered at G3_INTEGRATED. Order execution and position management layer. Transforms portfolio decisions from IoS-008 into executable orders. Passed G1/G2/G3 integration but has NO G4 trigger from VEGA or CEO.',
    '2026.PROD.G3',
    'G3_INTEGRATED',
    'LINE',
    ARRAY['ADR-001', 'ADR-002', 'ADR-004', 'ADR-011', 'ADR-012', 'ADR-013', 'ADR-016'],
    ARRAY['IoS-008'],
    encode(sha256(('IoS-012-RECONCILIATION-' || NOW()::TEXT)::bytea), 'hex'),
    'TIER-1_CRITICAL',
    1.00,
    'MUTABLE',
    FALSE,
    'G4 Constitutional Activation + CEO Two-Man Rule',
    'G3_COMPLETE'
)
ON CONFLICT (ios_id) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    version = EXCLUDED.version,
    status = EXCLUDED.status,
    dependencies = EXCLUDED.dependencies,
    canonical = EXCLUDED.canonical,
    governance_state = EXCLUDED.governance_state,
    updated_at = NOW();

-- ============================================================
-- SECTION 4: IoS-011 — Technical Analysis Pipeline (NEW)
-- ============================================================
-- Status: G0_SUBMITTED (code exists, never registered)
-- ============================================================

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
    modification_requires,
    governance_state
) VALUES (
    'IoS-011',
    'Technical Analysis Pipeline',
    'GOVERNANCE RECONCILIATION: First-time registration at G0_SUBMITTED. Technical analysis and charting infrastructure. Code and pipeline exist but module was never formally registered in governance system.',
    '2026.PROD.G0',
    'G0_SUBMITTED',
    'FINN',
    ARRAY['ADR-001', 'ADR-002', 'ADR-003', 'ADR-011', 'ADR-013'],
    ARRAY['IoS-002'],
    encode(sha256(('IoS-011-RECONCILIATION-' || NOW()::TEXT)::bytea), 'hex'),
    'TIER-2_ANALYTICS',
    1.00,
    'MUTABLE',
    FALSE,
    'G1-G4 Full Cycle (ADR-004)',
    'G0_SUBMITTED'
)
ON CONFLICT (ios_id) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    version = EXCLUDED.version,
    status = EXCLUDED.status,
    dependencies = EXCLUDED.dependencies,
    canonical = EXCLUDED.canonical,
    governance_state = EXCLUDED.governance_state,
    updated_at = NOW();

-- ============================================================
-- SECTION 5: UPDATE IoS-009 STATUS (Consistency)
-- ============================================================
-- Update IoS-009 to use new G0_SUBMITTED status

UPDATE fhq_meta.ios_registry
SET status = 'G0_SUBMITTED',
    updated_at = NOW()
WHERE ios_id = 'IoS-009' AND status = 'DRAFT';

-- ============================================================
-- SECTION 6: GOVERNANCE ACTION LOG ENTRIES
-- ============================================================

-- IoS-008 Reconciliation
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    vega_reviewed,
    hash_chain_id
) VALUES (
    'REGISTRY_RECONCILIATION',
    'IoS-008',
    'G2_VALIDATED',
    'BOARD',
    'APPROVED',
    'IoS-008 Runtime Decision Engine governance reconciliation. Module passed G1/G2/G3 validation but has NOT undergone G4 constitutional activation. Registered at actual gate progression: G2_VALIDATED. canonical=FALSE until G4.',
    TRUE,
    'HC-IOS008-RECONCILE-' || to_char(NOW(), 'YYYYMMDD-HH24MISS')
);

-- IoS-012 Reconciliation
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    vega_reviewed,
    hash_chain_id
) VALUES (
    'REGISTRY_RECONCILIATION',
    'IoS-012',
    'G3_INTEGRATED',
    'BOARD',
    'APPROVED',
    'IoS-012 Execution Engine governance reconciliation. Module passed G1/G2/G3 integration but has NO G4 trigger from VEGA or CEO. Registered at actual gate progression: G3_INTEGRATED. canonical=FALSE until G4.',
    TRUE,
    'HC-IOS012-RECONCILE-' || to_char(NOW(), 'YYYYMMDD-HH24MISS')
);

-- IoS-011 First Registration
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    vega_reviewed,
    hash_chain_id
) VALUES (
    'REGISTRY_RECONCILIATION',
    'IoS-011',
    'G0_SUBMITTED',
    'BOARD',
    'APPROVED',
    'IoS-011 Technical Analysis Pipeline first-time governance registration. Code and pipeline exist but module was never formally registered. Registered at G0_SUBMITTED for proper governance tracking.',
    TRUE,
    'HC-IOS011-RECONCILE-' || to_char(NOW(), 'YYYYMMDD-HH24MISS')
);

-- ============================================================
-- SECTION 7: RECONCILIATION AUDIT TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_governance.registry_reconciliation_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reconciliation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    reconciliation_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    initiated_by TEXT NOT NULL,

    -- Reconciliation Details
    ios_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('REGISTERED', 'UPDATED', 'CORRECTED')),
    previous_state JSONB,
    new_state JSONB NOT NULL,

    -- Rationale
    rationale TEXT NOT NULL,
    adr_reference TEXT,

    -- Verification
    vega_reviewed BOOLEAN NOT NULL DEFAULT FALSE,
    hash_chain_id TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE fhq_governance.registry_reconciliation_log IS
'ADR-013 One-Source-Truth reconciliation audit trail. Tracks all registry corrections and updates.';

-- Log IoS-008 reconciliation
INSERT INTO fhq_governance.registry_reconciliation_log (
    initiated_by, ios_id, action, previous_state, new_state, rationale, adr_reference, vega_reviewed, hash_chain_id
) VALUES (
    'BOARD',
    'IoS-008',
    'REGISTERED',
    NULL,
    '{"status": "G2_VALIDATED", "governance_state": "G2_COMPLETE", "canonical": false, "dependencies": ["IoS-004", "IoS-005", "IoS-007"]}'::jsonb,
    'Module passed G1/G2/G3 validation but has NOT undergone G4 constitutional activation. Registered at actual gate progression.',
    'ADR-013',
    TRUE,
    'HC-IOS008-RECONCILE-' || to_char(NOW(), 'YYYYMMDD-HH24MISS')
);

-- Log IoS-012 reconciliation
INSERT INTO fhq_governance.registry_reconciliation_log (
    initiated_by, ios_id, action, previous_state, new_state, rationale, adr_reference, vega_reviewed, hash_chain_id
) VALUES (
    'BOARD',
    'IoS-012',
    'REGISTERED',
    NULL,
    '{"status": "G3_INTEGRATED", "governance_state": "G3_COMPLETE", "canonical": false, "dependencies": ["IoS-008"]}'::jsonb,
    'Module passed G1/G2/G3 integration but has NO G4 trigger from VEGA or CEO. Registered at actual gate progression.',
    'ADR-013',
    TRUE,
    'HC-IOS012-RECONCILE-' || to_char(NOW(), 'YYYYMMDD-HH24MISS')
);

-- Log IoS-011 first registration
INSERT INTO fhq_governance.registry_reconciliation_log (
    initiated_by, ios_id, action, previous_state, new_state, rationale, adr_reference, vega_reviewed, hash_chain_id
) VALUES (
    'BOARD',
    'IoS-011',
    'REGISTERED',
    NULL,
    '{"status": "G0_SUBMITTED", "governance_state": "G0_SUBMITTED", "canonical": false, "dependencies": ["IoS-002"]}'::jsonb,
    'Code and pipeline exist but module was never formally registered in governance system. First-time registration.',
    'ADR-013',
    TRUE,
    'HC-IOS011-RECONCILE-' || to_char(NOW(), 'YYYYMMDD-HH24MISS')
);

-- ============================================================
-- SECTION 8: VERIFICATION QUERIES
-- ============================================================

-- Verify all reconciled entries
SELECT 'Registry Reconciliation Complete' AS verification,
       ios_id, title, version, status, governance_state, canonical, dependencies
FROM fhq_meta.ios_registry
WHERE ios_id IN ('IoS-008', 'IoS-011', 'IoS-012', 'IoS-009')
ORDER BY ios_id;

-- Verify governance actions logged
SELECT 'Governance Actions Logged' AS verification,
       action_type, action_target, action_target_type, decision, hash_chain_id
FROM fhq_governance.governance_actions_log
WHERE action_target IN ('IoS-008', 'IoS-011', 'IoS-012')
  AND action_type = 'REGISTRY_RECONCILIATION'
ORDER BY action_target;

-- Verify reconciliation log entries
SELECT 'Reconciliation Log Entries' AS verification,
       ios_id, action, new_state->>'status' as new_status, vega_reviewed
FROM fhq_governance.registry_reconciliation_log
ORDER BY ios_id;

-- Full registry state
SELECT 'Full Registry State' AS verification,
       ios_id, status, governance_state, canonical
FROM fhq_meta.ios_registry
ORDER BY ios_id;

-- ============================================================
-- MIGRATION COMPLETE: IoS GOVERNANCE RECONCILIATION
-- ============================================================
-- Reconciled Modules:
--   IoS-008: G2_VALIDATED (canonical=FALSE)
--   IoS-011: G0_SUBMITTED (canonical=FALSE)
--   IoS-012: G3_INTEGRATED (canonical=FALSE)
-- ADR-013 One-Source-Truth: RESTORED
-- ============================================================
