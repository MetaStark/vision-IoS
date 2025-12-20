-- ============================================================================
-- MIGRATION 065: IoS Registry Reconciliation
-- ============================================================================
-- Purpose: Fix inconsistencies between ios_registry and governance_actions_log
-- Author: STIG (CTO)
-- Date: 2025-12-02
-- ADR Reference: ADR-002 (Audit), ADR-004 (Change Gates), ADR-013 (Infrastructure)
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: Fix missing governance_state values
-- ============================================================================

-- FIX 1: IoS-001 - Legacy active module (pre-governance formalization)
UPDATE fhq_meta.ios_registry
SET governance_state = 'G4_LEGACY_ACTIVE',
    updated_at = NOW()
WHERE ios_id = 'IoS-001' AND governance_state IS NULL;

-- FIX 2: IoS-002 - Legacy active module (pre-governance formalization)
UPDATE fhq_meta.ios_registry
SET governance_state = 'G4_LEGACY_ACTIVE',
    updated_at = NOW()
WHERE ios_id = 'IoS-002' AND governance_state IS NULL;

-- FIX 3: IoS-003 - Legacy active + missing activated_at
UPDATE fhq_meta.ios_registry
SET governance_state = 'G4_LEGACY_ACTIVE',
    activated_at = '2025-11-29T17:27:53.997Z',
    updated_at = NOW()
WHERE ios_id = 'IoS-003' AND governance_state IS NULL;

-- FIX 4: IoS-004 - Has G4 activation in governance_actions_log
UPDATE fhq_meta.ios_registry
SET governance_state = 'G4_ACTIVE',
    updated_at = NOW()
WHERE ios_id = 'IoS-004' AND governance_state IS NULL;

-- FIX 5: IoS-005 - Has G4 constitutional activation in governance_actions_log
UPDATE fhq_meta.ios_registry
SET governance_state = 'G4_CONSTITUTIONAL',
    updated_at = NOW()
WHERE ios_id = 'IoS-005' AND governance_state IS NULL;

-- FIX 6: IoS-006 - Has G4 canonical activation in governance_actions_log
UPDATE fhq_meta.ios_registry
SET governance_state = 'G4_CANONICAL',
    updated_at = NOW()
WHERE ios_id = 'IoS-006' AND governance_state IS NULL;

-- ============================================================================
-- SECTION 2: Fix missing activated_at values for G4 modules
-- ============================================================================

-- FIX 7: IoS-012 - G4 conditional activation at 2025-12-01T19:30:44.469Z
UPDATE fhq_meta.ios_registry
SET activated_at = '2025-12-01T19:30:44.469Z',
    updated_at = NOW()
WHERE ios_id = 'IoS-012' AND activated_at IS NULL;

-- FIX 8: IoS-013.HCP-LAB - G4 final activation at 2025-12-01T23:58:40.791Z
UPDATE fhq_meta.ios_registry
SET activated_at = '2025-12-01T23:58:40.791Z',
    updated_at = NOW()
WHERE ios_id = 'IoS-013.HCP-LAB' AND activated_at IS NULL;

-- ============================================================================
-- SECTION 3: Log reconciliation in governance_actions_log
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
    vega_reviewed,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'REGISTRY_INTEGRITY_RECONCILIATION',
    'ios_registry',
    'BATCH_UPDATE',
    'STIG',
    NOW(),
    'COMPLETED',
    'Fixed 8 inconsistencies: 6 missing governance_state values (IoS-001 through IoS-006), 1 missing activated_at (IoS-003), 2 missing activated_at for G4 modules (IoS-012, IoS-013.HCP-LAB). All updates derived from governance_actions_log timestamps.',
    true,
    'HC-RECONCILIATION-065-' || to_char(NOW(), 'YYYYMMDD')
);

-- ============================================================================
-- SECTION 4: Audit log entries (ADR-002 compliance)
-- ============================================================================

-- IoS-001 audit entry
INSERT INTO fhq_meta.ios_audit_log (ios_id, event_type, actor, gate_level, event_data)
VALUES ('IoS-001', 'RECONCILIATION_UPDATE', 'STIG', 'G4',
    '{"migration": "065", "field": "governance_state", "old": null, "new": "G4_LEGACY_ACTIVE"}'::jsonb);

-- IoS-002 audit entry
INSERT INTO fhq_meta.ios_audit_log (ios_id, event_type, actor, gate_level, event_data)
VALUES ('IoS-002', 'RECONCILIATION_UPDATE', 'STIG', 'G4',
    '{"migration": "065", "field": "governance_state", "old": null, "new": "G4_LEGACY_ACTIVE"}'::jsonb);

-- IoS-003 audit entry
INSERT INTO fhq_meta.ios_audit_log (ios_id, event_type, actor, gate_level, event_data)
VALUES ('IoS-003', 'RECONCILIATION_UPDATE', 'STIG', 'G4',
    '{"migration": "065", "fields": ["governance_state", "activated_at"], "governance_state": {"old": null, "new": "G4_LEGACY_ACTIVE"}, "activated_at": {"old": null, "new": "2025-11-29T17:27:53.997Z"}}'::jsonb);

-- IoS-004 audit entry
INSERT INTO fhq_meta.ios_audit_log (ios_id, event_type, actor, gate_level, event_data)
VALUES ('IoS-004', 'RECONCILIATION_UPDATE', 'STIG', 'G4',
    '{"migration": "065", "field": "governance_state", "old": null, "new": "G4_ACTIVE"}'::jsonb);

-- IoS-005 audit entry
INSERT INTO fhq_meta.ios_audit_log (ios_id, event_type, actor, gate_level, event_data)
VALUES ('IoS-005', 'RECONCILIATION_UPDATE', 'STIG', 'G4',
    '{"migration": "065", "field": "governance_state", "old": null, "new": "G4_CONSTITUTIONAL"}'::jsonb);

-- IoS-006 audit entry
INSERT INTO fhq_meta.ios_audit_log (ios_id, event_type, actor, gate_level, event_data)
VALUES ('IoS-006', 'RECONCILIATION_UPDATE', 'STIG', 'G4',
    '{"migration": "065", "field": "governance_state", "old": null, "new": "G4_CANONICAL"}'::jsonb);

-- IoS-012 audit entry
INSERT INTO fhq_meta.ios_audit_log (ios_id, event_type, actor, gate_level, event_data)
VALUES ('IoS-012', 'RECONCILIATION_UPDATE', 'STIG', 'G4',
    '{"migration": "065", "field": "activated_at", "old": null, "new": "2025-12-01T19:30:44.469Z"}'::jsonb);

-- IoS-013.HCP-LAB audit entry
INSERT INTO fhq_meta.ios_audit_log (ios_id, event_type, actor, gate_level, event_data)
VALUES ('IoS-013.HCP-LAB', 'RECONCILIATION_UPDATE', 'STIG', 'G4',
    '{"migration": "065", "field": "activated_at", "old": null, "new": "2025-12-01T23:58:40.791Z"}'::jsonb);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERY
-- ============================================================================
SELECT ios_id, status, governance_state, activated_at, updated_at
FROM fhq_meta.ios_registry
ORDER BY ios_id;
