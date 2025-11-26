-- Fix governance_state table
DROP TABLE IF EXISTS fhq_governance.governance_state CASCADE;

CREATE TABLE fhq_governance.governance_state (
    state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component_type TEXT NOT NULL,
    component_name TEXT NOT NULL,
    component_version TEXT NOT NULL,
    registration_status TEXT NOT NULL DEFAULT 'REGISTERED',
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    registered_by TEXT NOT NULL,
    authority_chain TEXT[] NOT NULL,
    adr_compliance TEXT[] NOT NULL,
    vega_attested BOOLEAN NOT NULL DEFAULT FALSE,
    vega_attestation_id UUID,
    vega_attestation_timestamp TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    deployment_environment TEXT NOT NULL DEFAULT 'PRODUCTION',
    configuration JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT governance_state_unique_component UNIQUE (component_type, component_name, component_version)
);

INSERT INTO fhq_governance.governance_state (
    component_type, component_name, component_version, registered_by,
    authority_chain, adr_compliance, configuration
) VALUES (
    'ORCHESTRATOR', 'FHQ_INTELLIGENCE_ORCHESTRATOR', '1.1.1', 'LARS',
    ARRAY['ADR-001', 'ADR-002', 'ADR-006', 'ADR-007', 'EC-001'],
    ARRAY['ADR-001', 'ADR-002', 'ADR-006', 'ADR-007', 'ADR-008', 'ADR-010', 'ADR-013'],
    '{"version": "1.1.1", "validation_status": "5/5 PASS"}'::jsonb
);

SELECT 'governance_state FIXED' AS status, COUNT(*) AS rows FROM fhq_governance.governance_state;
