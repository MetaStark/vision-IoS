-- ============================================================================
-- CEO-DIR-2026-LVI-GOVERNANCE-SCHEMA-D-035
-- Governance Table for Canonical LVI Linkage Rules
-- ============================================================================
--
-- PURPOSE: Store canonical linkage rules enabling event-level deterministic mapping
--          between learning events and settlement records
--
-- AUTHORITY: CEO-DIR-2026-DEFINITION-D-ENFORCEMENT-034
-- EFFECTIVE: 2026-02-16 16:35:00 UTC
-- AUTHOR: STIG (EC-003)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- CREATE TABLE: lvi_linkage_rules
-- ----------------------------------------------------------------------------

CREATE TABLE fhq_governance.lvi_linkage_rules (
    rule_id UUID PRIMARY KEY,
    rule_version NUMERIC NOT NULL,
    linkage_method TEXT NOT NULL,
    deterministic_keys JSONB NOT NULL,
    tolerance_ms INTEGER,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'STIG',
    rule_hash TEXT NOT NULL UNIQUE
);

-- COMMENT ON TABLE fhq_governance.lvi_linkage_rules IS
'CEO-DIR-035: Stores canonical LVI linkage rules for deterministic event-level mapping.
Rules define exact join keys, tolerance windows, and enforcement behavior.
Version 1.0 - 2026-02-16';

-- ----------------------------------------------------------------------------
-- CREATE INDEXES
-- ----------------------------------------------------------------------------

CREATE INDEX idx_lvi_linkage_rules_method ON fhq_governance.lvi_linkage_rules (linkage_method);
CREATE INDEX idx_lvi_linkage_rules_created ON fhq_governance.lvi_linkage_rules (created_at);
CREATE INDEX idx_lvi_linkage_rules_hash ON fhq_governance.lvi_linkage_rules (rule_hash);
CREATE INDEX idx_lvi_linkage_rules_active ON fhq_governance.lvi_linkage_rules (is_active);

-- ----------------------------------------------------------------------------
-- POPULATE INITIAL RULES
-- ----------------------------------------------------------------------------

INSERT INTO fhq_governance.lvi_linkage_rules (rule_id, rule_version, linkage_method, deterministic_keys, tolerance_ms, is_active, created_by, rule_hash)
VALUES
    ('LVI-LINK-001-1.0', 1.0, 'ONE_TO_ONE_FORECAST_OUTCOME', '{"join_keys": ["forecast_id", "outcome_id"]}'::jsonb, NULL, NOW(), 'STIG', 'sha256:' || encode(sha256(('LVI-LINK-001-1.0ONE_TO_ONE_FORECAST_OUTCOME'::bytea), 'hex')),

    ('LVI-LINK-002-1.0', 1.0, 'ONE_TO_ONE_OUTCOME_SETTLEMENT', '{"join_keys": ["outcome_id", "settlement_id"], "tolerance_ms": 300000}'::jsonb, 300000, NOW(), 'STIG', 'sha256:' || encode(sha256(('LVI-LINK-002-1.0ONE_TO_ONE_OUTCOME_SETTLEMENT'::bytea), 'hex')),

    ('LVI-LINK-003-1.0', 1.0, 'ASSET_UNLOCK_DEPRECATED', '{"deprecated_reason": "Asset-level unlock creates multiplicative inflation", "tolerance_ms": 300000}'::jsonb, NULL, NOW(), 'STIG', 'sha256:' || encode(sha256(('LVI-LINK-003-1.0ASSET_UNLOCK_DEPRECATED'::bytea), 'hex')),

    ('LVI-LINK-004-1.0', 1.0, 'INFARIANT_ENFORCEMENT', '{"invariant": "eligible_events_in_settlement <= terminalized_outcomes_in_window", "action": "abort computation on violation", "severity": "CRITICAL"}'::jsonb, 0, NOW(), 'STIG', 'sha256:' || encode(sha256(('LVI-LINK-004-1.0INFARIANT_ENFORCEMENT'::bytea), 'hex'));

-- COMMENT ON INITIAL RULES
COMMENT ON COLUMN fhq_governance.lvi_linkage_rules.linkage_method IS
'LVI-LINK-001: Exact PK join between forecast_id and outcome_id';
COMMENT ON COLUMN fhq_governance.lvi_linkage_rules.linkage_method IS
'LVI-LINK-002: Exact PK join between outcome_id and settlement_id';
COMMENT ON COLUMN fhq_governance.lvi_linkage_rules.linkage_method IS
'LVI-LINK-003: Marks deprecated asset-level unlock behavior';
COMMENT ON COLUMN fhq_governance.lvi_linkage_rules.linkage_method IS
'LVI-LINK-004: Enforces hard invariant: eligible_events_in_settlement <= terminalized_outcomes_in_window';

-- ----------------------------------------------------------------------------
-- CREATE TRIGGER: Rule Deactivation
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION fhq_governance.trg_deactivate_linkage_rule()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $function$
BEGIN
    NEW.created_by := 'STIG';
    RETURN NEW;
END;
$function$;

CREATE TRIGGER trg_lvi_linkage_rules_deactivate
    BEFORE UPDATE ON fhq_governance.lvi_linkage_rules
    FOR EACH ROW
    WHEN (OLD.is_active = TRUE AND NEW.is_active = FALSE)
    EXECUTE FUNCTION fhq_governance.trg_deactivate_linkage_rule();

COMMENT ON TRIGGER trg_lvi_linkage_rules_deactivate IS
'CEO-DIR-035: Ensures linkage rules can only be deactivated (not modified) by STIG.
Prevents unauthorized rule modification that could compromise deterministic mapping.';

COMMIT;

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
