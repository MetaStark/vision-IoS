-- ============================================================================
-- MIGRATION 131: G0.2 Evidence Accumulation Mode (EAM)
-- ============================================================================
-- Authority: CEO DIRECTIVE — G0.2: Evidence Accumulation Activation
-- Classification: Constitutional Proof Layer
-- Preconditions: G0 COMPLETE, G0.1 COMPLETE
-- Purpose: Activate Evidence Accumulation Mode for G1 qualification
-- ============================================================================

BEGIN;

-- ============================================================================
-- PRE-FLIGHT CHECK
-- ============================================================================
DO $$
DECLARE
    g0_1_tables INTEGER;
BEGIN
    -- Verify G0.1 infrastructure exists
    SELECT COUNT(*) INTO g0_1_tables
    FROM information_schema.tables
    WHERE table_schema = 'fhq_meta'
      AND table_name IN ('aci_cognitive_memory', 'aci_console_sessions', 'aci_system_prompts');

    IF g0_1_tables < 3 THEN
        RAISE EXCEPTION 'G0.1 infrastructure incomplete. Cannot activate G0.2.';
    END IF;

    RAISE NOTICE 'Pre-flight PASSED: G0.1 infrastructure verified';
END $$;

-- ============================================================================
-- SECTION 1: G0.2 EVIDENCE ACCUMULATION REGISTRY
-- ============================================================================
-- Tracks EAM activation and G1 progress

CREATE TABLE IF NOT EXISTS fhq_meta.g1_evidence_accumulation (
    accumulation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    eam_start_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    eam_target_end TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '30 days'),
    eam_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
        CHECK (eam_status IN ('ACTIVE', 'PAUSED', 'VIOLATED', 'COMPLETE')),

    -- Evidence Domain Counters
    state_integrity_count INTEGER NOT NULL DEFAULT 0,
    state_integrity_failures INTEGER NOT NULL DEFAULT 0,

    cognitive_fidelity_sitc_count INTEGER NOT NULL DEFAULT 0,
    cognitive_fidelity_ikea_count INTEGER NOT NULL DEFAULT 0,
    cognitive_fidelity_inforage_count INTEGER NOT NULL DEFAULT 0,

    hallucination_rejections INTEGER NOT NULL DEFAULT 0,
    hallucination_bypasses INTEGER NOT NULL DEFAULT 0,

    canonical_citations INTEGER NOT NULL DEFAULT 0,
    canonical_drift_events INTEGER NOT NULL DEFAULT 0,
    canonical_drift_resolved INTEGER NOT NULL DEFAULT 0,

    -- Operational Stability
    days_without_violation INTEGER NOT NULL DEFAULT 0,
    last_violation_timestamp TIMESTAMPTZ,
    last_violation_reason TEXT,

    -- Human Stability (CEO self-report)
    ceo_stability_confirmed BOOLEAN DEFAULT false,
    ceo_stability_timestamp TIMESTAMPTZ,
    ceo_stability_notes TEXT,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT single_active_eam UNIQUE (eam_status)
        DEFERRABLE INITIALLY DEFERRED
);

COMMENT ON TABLE fhq_meta.g1_evidence_accumulation IS
'G0.2 Evidence Accumulation Mode tracker. Measures progress toward G1 entry criteria across five domains.';

-- ============================================================================
-- SECTION 2: G1 EVIDENCE SNAPSHOTS (Daily Rollups)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.g1_evidence_daily_snapshot (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date DATE NOT NULL UNIQUE,
    accumulation_id UUID REFERENCES fhq_meta.g1_evidence_accumulation(accumulation_id),

    -- Section 3.1: State Integrity Evidence
    invocations_today INTEGER NOT NULL DEFAULT 0,
    invocations_with_state_binding INTEGER NOT NULL DEFAULT 0,
    state_binding_rate NUMERIC(5,4),
    consecutive_valid_count INTEGER NOT NULL DEFAULT 0,

    -- Section 3.2: Cognitive Protocol Fidelity
    sitc_chains_generated INTEGER NOT NULL DEFAULT 0,
    sitc_non_trivial_chains INTEGER NOT NULL DEFAULT 0,
    ikea_classifications INTEGER NOT NULL DEFAULT 0,
    ikea_correct_classifications INTEGER NOT NULL DEFAULT 0,
    inforage_queries INTEGER NOT NULL DEFAULT 0,
    inforage_cost_optimal INTEGER NOT NULL DEFAULT 0,

    -- Section 3.3: Hallucination Containment
    hallucination_rejections_today INTEGER NOT NULL DEFAULT 0,
    explicit_refusals INTEGER NOT NULL DEFAULT 0,
    speculative_outputs_blocked INTEGER NOT NULL DEFAULT 0,

    -- Section 3.4: Canonical Truth Consistency
    document_citations INTEGER NOT NULL DEFAULT 0,
    citations_with_hash INTEGER NOT NULL DEFAULT 0,
    drift_events_today INTEGER NOT NULL DEFAULT 0,
    drift_events_resolved INTEGER NOT NULL DEFAULT 0,

    -- Section 3.5: Operational Stability
    emergency_interventions INTEGER NOT NULL DEFAULT 0,
    governance_overrides INTEGER NOT NULL DEFAULT 0,
    quick_fixes_outside_gates INTEGER NOT NULL DEFAULT 0,

    -- Compliance Summary
    day_compliant BOOLEAN NOT NULL DEFAULT true,
    violation_notes TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_g1_snapshot_date ON fhq_meta.g1_evidence_daily_snapshot(snapshot_date);

COMMENT ON TABLE fhq_meta.g1_evidence_daily_snapshot IS
'Daily evidence rollup for G1 qualification. Each row represents one day of Evidence Accumulation Mode.';

-- ============================================================================
-- SECTION 3: G1 QUALIFICATION THRESHOLDS (Read-Only Reference)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.g1_qualification_thresholds (
    threshold_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain VARCHAR(50) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    threshold_value NUMERIC NOT NULL,
    threshold_type VARCHAR(20) NOT NULL CHECK (threshold_type IN ('MINIMUM', 'MAXIMUM', 'PERCENTAGE')),
    description TEXT,
    adr_reference VARCHAR(20),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(domain, metric_name)
);

-- Insert G1 Entry Criteria thresholds (per CEO Directive)
INSERT INTO fhq_meta.g1_qualification_thresholds (domain, metric_name, threshold_value, threshold_type, description, adr_reference) VALUES
-- Section 3.1: State Integrity
('STATE_INTEGRITY', 'consecutive_invocations', 1000, 'MINIMUM', '≥ 1,000 consecutive invocations with valid state binding', 'ADR-018'),
('STATE_INTEGRITY', 'missing_state_tolerance', 0, 'MAXIMUM', 'Zero invocations without state binding', 'ADR-018'),

-- Section 3.2: Cognitive Protocol Fidelity
('COGNITIVE_FIDELITY', 'sitc_chain_rate', 95, 'PERCENTAGE', '≥ 95% of complex responses include non-trivial chain_of_query', 'ADR-021'),
('COGNITIVE_FIDELITY', 'ikea_classification_rate', 99, 'PERCENTAGE', '≥ 99% of factual claims correctly classified', 'ADR-021'),
('COGNITIVE_FIDELITY', 'inforage_cost_optimal_rate', 90, 'PERCENTAGE', '≥ 90% demonstrate cost-optimal retrieval', 'ADR-021'),

-- Section 3.3: Hallucination Containment
('HALLUCINATION', 'bypass_tolerance', 0, 'MAXIMUM', 'Zero hallucinated claims bypassing rejection middleware', 'ADR-012'),

-- Section 3.4: Canonical Truth Consistency
('CANONICAL_TRUTH', 'citation_hash_rate', 100, 'PERCENTAGE', '100% of citations include canonical hash', 'ADR-013'),
('CANONICAL_TRUTH', 'unresolved_drift_tolerance', 0, 'MAXIMUM', 'All drift events must be resolved or acknowledged', 'ADR-013'),

-- Section 3.5: Operational Stability
('OPERATIONAL', 'minimum_days', 30, 'MINIMUM', '≥ 30 days continuous operation', NULL),
('OPERATIONAL', 'emergency_interventions', 0, 'MAXIMUM', 'No emergency interventions', NULL),
('OPERATIONAL', 'governance_overrides', 0, 'MAXIMUM', 'No governance overrides', NULL),
('OPERATIONAL', 'quick_fixes_outside_gates', 0, 'MAXIMUM', 'No quick fixes outside ADR-004 gates', 'ADR-004')

ON CONFLICT (domain, metric_name) DO NOTHING;

COMMENT ON TABLE fhq_meta.g1_qualification_thresholds IS
'Read-only reference table. G1 entry thresholds per CEO Directive. No runtime evaluation embedded.';

-- ============================================================================
-- SECTION 4: ACTIVATE EVIDENCE ACCUMULATION MODE
-- ============================================================================

-- Initialize EAM with start timestamp
INSERT INTO fhq_meta.g1_evidence_accumulation (
    eam_start_timestamp,
    eam_target_end,
    eam_status
) VALUES (
    NOW(),
    NOW() + INTERVAL '30 days',
    'ACTIVE'
);

-- Create first daily snapshot (Day 0)
INSERT INTO fhq_meta.g1_evidence_daily_snapshot (
    snapshot_date,
    accumulation_id,
    invocations_today,
    day_compliant,
    violation_notes
)
SELECT
    CURRENT_DATE,
    accumulation_id,
    0,
    true,
    'G0.2 EAM activation day. Evidence accumulation begins.'
FROM fhq_meta.g1_evidence_accumulation
WHERE eam_status = 'ACTIVE';

-- ============================================================================
-- SECTION 5: G0.2 DIRECTIVE REGISTRATION
-- ============================================================================

-- First register the directive in adr_registry (required by foreign key)
-- Valid adr_status: DRAFT, PROPOSED, APPROVED, DEPRECATED, SUPERSEDED
-- Valid adr_type: CONSTITUTIONAL, ARCHITECTURAL, OPERATIONAL, COMPLIANCE, ECONOMIC
INSERT INTO fhq_meta.adr_registry (
    adr_id,
    adr_title,
    adr_type,
    description,
    adr_status,
    current_version,
    sha256_hash,
    file_path
) VALUES (
    'CD-G0.2-EAM',
    'CEO DIRECTIVE — G0.2: Evidence Accumulation Activation',
    'OPERATIONAL',
    'Activates Evidence Accumulation Mode (EAM) for G1 qualification. Minimum 30 days. Five evidence domains. No prior invocations qualify.',
    'APPROVED',
    '1.0.0',
    ENCODE(SHA256('CEO-DIRECTIVE-G0.2-EAM-20251212'::bytea), 'hex'),
    '05_GOVERNANCE/PHASE3/CEO_DIRECTIVE_G0_2_EVIDENCE_ACCUMULATION_20251212.json'
) ON CONFLICT (adr_id) DO NOTHING;

INSERT INTO fhq_meta.adr_registry (
    adr_id,
    adr_title,
    adr_type,
    description,
    adr_status,
    current_version,
    sha256_hash
) VALUES (
    'ACI-EAM-START',
    'ACI Evidence Accumulation Mode Start Marker',
    'OPERATIONAL',
    'Marks the official start of Evidence Accumulation Mode. All subsequent invocations are G1 Evidence-Candidate Events.',
    'APPROVED',
    '1.0.0',
    ENCODE(SHA256('EAM-START-20251212'::bytea), 'hex')
) ON CONFLICT (adr_id) DO NOTHING;

-- Note: gate_stage constraint requires SUBMISSION -> G0
-- We use metadata to track the actual G0.2 directive phase
INSERT INTO fhq_meta.adr_audit_log (
    change_proposal_id,
    adr_id,
    event_type,
    gate_stage,
    initiated_by,
    decision,
    resolution_notes,
    evidence_path,
    sha256_hash,
    hash_chain_id,
    metadata
) VALUES (
    'CP-G0.2-EAM-20251212',
    'CD-G0.2-EAM',
    'SUBMISSION',
    'G0',  -- Required by constraint, actual phase in metadata
    'CEO',
    'APPROVED',
    'CEO DIRECTIVE — G0.2: Evidence Accumulation Activation. EAM begins. All subsequent ACI invocations are G1 Evidence-Candidate Events. 30-day minimum.',
    '05_GOVERNANCE/PHASE3/CEO_DIRECTIVE_G0_2_EVIDENCE_ACCUMULATION_20251212.json',
    ENCODE(SHA256('CEO-DIRECTIVE-G0.2-EAM-20251212'::bytea), 'hex'),
    'HC-G0.2-EAM-20251212',
    jsonb_build_object(
        'directive_id', 'CD-G0.2-EVIDENCE-ACCUMULATION',
        'actual_phase', 'G0.2',
        'classification', 'Constitutional Proof Layer',
        'eam_start', NOW(),
        'minimum_duration_days', 30,
        'evidence_domains', ARRAY['State Integrity', 'Cognitive Protocol Fidelity', 'Hallucination Containment', 'Canonical Truth Consistency', 'Operational Stability']
    )
);

-- Register EAM start event
INSERT INTO fhq_meta.adr_audit_log (
    change_proposal_id,
    adr_id,
    event_type,
    gate_stage,
    initiated_by,
    decision,
    resolution_notes,
    sha256_hash,
    hash_chain_id,
    metadata
) VALUES (
    'CP-EAM-START-20251212',
    'ACI-EAM-START',
    'SUBMISSION',
    'G0',  -- Required by constraint, actual phase in metadata
    'STIG',
    'ACTIVATED',
    'Evidence Accumulation Mode officially begins. All subsequent ACI Console invocations are G1 Evidence-Candidate Events. Prior invocations do not qualify.',
    ENCODE(SHA256('EAM-START-20251212'::bytea), 'hex'),
    'HC-EAM-START-20251212',
    jsonb_build_object(
        'actual_phase', 'G0.2',
        'eam_start_timestamp', NOW(),
        'eam_target_end', NOW() + INTERVAL '30 days',
        'invocations_at_start', 0,
        'evidence_baseline', 'ZERO'
    )
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'MIGRATION 131: G0.2 EVIDENCE ACCUMULATION MODE — VERIFICATION'
\echo '═══════════════════════════════════════════════════════════════════════════'

SELECT 'EAM Status:' as check_type;
SELECT eam_status, eam_start_timestamp, eam_target_end,
       (eam_target_end - NOW())::interval as time_remaining
FROM fhq_meta.g1_evidence_accumulation
WHERE eam_status = 'ACTIVE';

SELECT 'G1 Thresholds Registered:' as check_type;
SELECT domain, COUNT(*) as threshold_count
FROM fhq_meta.g1_qualification_thresholds
WHERE is_active = true
GROUP BY domain
ORDER BY domain;

SELECT 'Day 0 Snapshot:' as check_type;
SELECT snapshot_date, day_compliant, violation_notes
FROM fhq_meta.g1_evidence_daily_snapshot
ORDER BY snapshot_date DESC
LIMIT 1;

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'G0.2 EVIDENCE ACCUMULATION MODE — ACTIVE'
\echo ''
\echo 'The organism is now allowed to prove itself.'
\echo ''
\echo 'Evidence domains monitored:'
\echo '  1. State Integrity (ADR-018)'
\echo '  2. Cognitive Protocol Fidelity (ADR-021)'
\echo '  3. Hallucination Containment (ADR-012 / EC-022)'
\echo '  4. Canonical Truth Consistency (ADR-013)'
\echo '  5. Operational Stability (System + Human)'
\echo ''
\echo 'Minimum duration: 30 days'
\echo 'Prior invocations: DO NOT QUALIFY'
\echo '═══════════════════════════════════════════════════════════════════════════'
