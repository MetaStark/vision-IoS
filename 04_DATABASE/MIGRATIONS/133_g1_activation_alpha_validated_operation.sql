-- ============================================================================
-- MIGRATION 133: G1 ACTIVATION — ALPHA-VALIDATED OPERATION
-- ============================================================================
-- Authority: CEO DIRECTIVE — G1 ACTIVATION: ALPHA-VALIDATED OPERATION (REVISED)
-- Classification: G1 — Controlled Alpha Validation Layer
-- Preconditions: G0.2 EAM ACTIVE, Alpha Alignment Addendum COMPLETE
-- Purpose: Transition from Passive Proof to Active Learning Under Constraint
-- ============================================================================

BEGIN;

-- ============================================================================
-- PRE-FLIGHT CHECK
-- ============================================================================
DO $$
DECLARE
    eam_active BOOLEAN;
    alpha_alignment_complete BOOLEAN;
BEGIN
    -- Verify G0.2 EAM exists
    SELECT EXISTS (
        SELECT 1 FROM fhq_meta.g1_evidence_accumulation WHERE eam_status = 'ACTIVE'
    ) INTO eam_active;

    IF NOT eam_active THEN
        RAISE EXCEPTION 'G0.2 EAM not active. Cannot activate G1.';
    END IF;

    -- Verify Alpha Alignment Addendum complete
    SELECT EXISTS (
        SELECT 1 FROM fhq_meta.adr_registry WHERE adr_id = 'EC-023' AND adr_status = 'APPROVED'
    ) INTO alpha_alignment_complete;

    IF NOT alpha_alignment_complete THEN
        RAISE EXCEPTION 'EC-023 Alpha-Veto not approved. Cannot activate G1.';
    END IF;

    RAISE NOTICE 'Pre-flight PASSED: G0.2 EAM active, EC-023 approved';
END $$;

-- ============================================================================
-- SECTION 1: CLOSE G0.2 EVIDENCE ACCUMULATION MODE
-- ============================================================================

-- Mark G0.2 EAM as COMPLETE (not VIOLATED - successful transition)
UPDATE fhq_meta.g1_evidence_accumulation
SET
    eam_status = 'COMPLETE',
    updated_at = NOW()
WHERE eam_status = 'ACTIVE';

-- Record final G0.2 snapshot
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
    'G0.2 EAM closed. Transition to G1 Alpha-Validated Operation authorized by CEO.'
FROM fhq_meta.g1_evidence_accumulation
WHERE eam_status = 'COMPLETE'
ON CONFLICT (snapshot_date) DO UPDATE SET
    violation_notes = EXCLUDED.violation_notes;

-- ============================================================================
-- SECTION 2: G1 ACTIVATION REGISTRY
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.g1_activation_registry (
    activation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Activation Status
    g1_start_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    g1_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
        CHECK (g1_status IN ('ACTIVE', 'PAUSED', 'TERMINATED', 'PROMOTED_G2')),

    -- Authority Constraints (Immutable - reaffirmed from G0.2)
    authority_level INTEGER NOT NULL DEFAULT 3
        CHECK (authority_level = 3),  -- Tier-3 only
    execution_mode VARCHAR(20) NOT NULL DEFAULT 'SHADOW_PAPER'
        CHECK (execution_mode = 'SHADOW_PAPER'),
    write_access BOOLEAN NOT NULL DEFAULT false
        CHECK (write_access = false),
    allocation_rights BOOLEAN NOT NULL DEFAULT false
        CHECK (allocation_rights = false),
    autonomous_behavior BOOLEAN NOT NULL DEFAULT false
        CHECK (autonomous_behavior = false),

    -- G1 Evidence Metrics (New - Alpha Impact Focus)
    insights_generated INTEGER NOT NULL DEFAULT 0,
    insights_acted_upon INTEGER NOT NULL DEFAULT 0,
    time_saved_estimate_minutes INTEGER NOT NULL DEFAULT 0,
    decision_clarity_score NUMERIC(3,2),  -- CEO/LARS assessment

    -- Alpha-Veto Metrics (Active Evaluation)
    alpha_veto_compressions INTEGER NOT NULL DEFAULT 0,
    alpha_veto_full_analyses INTEGER NOT NULL DEFAULT 0,
    compression_useful_rate NUMERIC(5,4),  -- Did compression save time without losing insight?

    -- Exit Conditions Tracking
    g2_proposal_issued BOOLEAN NOT NULL DEFAULT false,
    g1_failure_declared BOOLEAN NOT NULL DEFAULT false,
    ceo_termination BOOLEAN NOT NULL DEFAULT false,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE fhq_meta.g1_activation_registry IS
'G1 Alpha-Validated Operation tracker. Measures Alpha impact, not just protocol fidelity. The organism is now allowed to matter.';

-- Initialize G1 activation record
INSERT INTO fhq_meta.g1_activation_registry (
    g1_start_timestamp,
    g1_status
) VALUES (
    NOW(),
    'ACTIVE'
);

-- ============================================================================
-- SECTION 3: G1 EVIDENCE LEDGER (Alpha Impact Focus)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.g1_alpha_evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    activation_id UUID REFERENCES fhq_meta.g1_activation_registry(activation_id),

    -- Interaction Reference
    session_id UUID,
    interaction_id UUID,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Alpha-Veto Decision
    ais_estimate NUMERIC(5,4),  -- Ephemeral, not persisted for allocation
    veto_action VARCHAR(30),
    compression_applied BOOLEAN NOT NULL DEFAULT false,

    -- Output Characterization
    output_type VARCHAR(50),  -- 'trade_hypothesis', 'regime_interpretation', 'signal_assessment', 'macro_triage', 'decision_prep'
    output_length_tokens INTEGER,
    sitc_depth INTEGER,

    -- Human-in-the-Loop Evaluation (First-Class G1 Evidence)
    evaluator VARCHAR(20),  -- 'CEO', 'LARS', null if not evaluated
    evaluation_timestamp TIMESTAMPTZ,
    acted_differently BOOLEAN,  -- "Would I act differently after this output?"
    saved_time BOOLEAN,  -- "Did this save me time?"
    clarified_or_confused VARCHAR(20),  -- 'CLARIFIED', 'CONFUSED', 'NEUTRAL'
    evaluation_notes TEXT,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_g1_alpha_evidence_session ON fhq_meta.g1_alpha_evidence(session_id);
CREATE INDEX idx_g1_alpha_evidence_timestamp ON fhq_meta.g1_alpha_evidence(timestamp);
CREATE INDEX idx_g1_alpha_evidence_evaluator ON fhq_meta.g1_alpha_evidence(evaluator);

COMMENT ON TABLE fhq_meta.g1_alpha_evidence IS
'G1 Alpha impact evidence. Records whether outputs inform real decisions, whether Alpha-Veto saves time, whether economic state awareness improves relevance.';

-- ============================================================================
-- SECTION 4: CANONICAL DOCUMENT INGESTION INFRASTRUCTURE (RAG)
-- ============================================================================

-- Document ingestion queue (CEO-controlled)
CREATE TABLE IF NOT EXISTS fhq_meta.canonical_document_queue (
    queue_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Document Reference
    document_path TEXT NOT NULL,
    document_title TEXT NOT NULL,
    document_type VARCHAR(30) NOT NULL
        CHECK (document_type IN ('ADR', 'IOS', 'DIRECTIVE', 'RESEARCH', 'MACRO', 'SIGNAL', 'OTHER')),

    -- CEO Authorization
    requested_by VARCHAR(20) NOT NULL DEFAULT 'STIG',
    authorized_by VARCHAR(20),  -- Must be 'CEO' for ingestion
    authorization_timestamp TIMESTAMPTZ,
    authorization_notes TEXT,

    -- Ingestion Status
    ingestion_status VARCHAR(20) NOT NULL DEFAULT 'PENDING_AUTHORIZATION'
        CHECK (ingestion_status IN ('PENDING_AUTHORIZATION', 'AUTHORIZED', 'INGESTING', 'COMPLETE', 'REJECTED')),

    -- Analytical Purpose (Required for CEO decision)
    analytical_purpose TEXT NOT NULL,
    priority_order INTEGER,

    -- Ingestion Metadata
    chunk_count INTEGER,
    ingestion_timestamp TIMESTAMPTZ,
    content_hash TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE fhq_meta.canonical_document_queue IS
'CEO-controlled document ingestion queue. STIG may request documents but cannot independently select them for ingestion. Only CEO-authorized documents may be loaded.';

-- ============================================================================
-- SECTION 5: G1 DIRECTIVE REGISTRATION
-- ============================================================================

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
    'CD-G1-ACTIVATION',
    'CEO DIRECTIVE — G1 ACTIVATION: ALPHA-VALIDATED OPERATION',
    'OPERATIONAL',
    'Transitions FjordHQ from G0.2 Evidence Accumulation to G1 Alpha-Validated Operation. Active learning under unchanged authority constraints. The organism is now allowed to matter.',
    'APPROVED',
    '1.0.0',
    ENCODE(SHA256('CEO-DIRECTIVE-G1-ACTIVATION-20251212'::bytea), 'hex'),
    '05_GOVERNANCE/PHASE3/CEO_DIRECTIVE_G1_ACTIVATION_20251212.json'
) ON CONFLICT (adr_id) DO UPDATE SET
    description = EXCLUDED.description,
    sha256_hash = EXCLUDED.sha256_hash,
    updated_at = NOW();

-- ============================================================================
-- SECTION 6: AUDIT LOG ENTRIES
-- ============================================================================

-- G0.2 Closeout (using MODIFICATION as event type per schema constraint)
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
    'CP-G0.2-CLOSEOUT-20251212',
    'CD-G0.2-EAM',
    'MODIFICATION',
    'G0',
    'CEO',
    'APPROVED',
    'G0.2 Evidence Accumulation Mode closed. System demonstrated constrained cognitive behavior. Transition to G1 authorized.',
    ENCODE(SHA256('G0.2-CLOSEOUT-20251212'::bytea), 'hex'),
    'HC-G0.2-CLOSEOUT-20251212',
    jsonb_build_object(
        'actual_event', 'CLOSEOUT',
        'closeout_reason', 'Successful completion - transition to G1',
        'evidence_accumulated', true,
        'constraints_maintained', true,
        'alpha_alignment_complete', true
    )
);

-- G1 Activation (using G1_TECHNICAL_VALIDATION per schema constraint)
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
    'CP-G1-ACTIVATION-20251212',
    'CD-G1-ACTIVATION',
    'G1_TECHNICAL_VALIDATION',
    'G1',
    'CEO',
    'APPROVED',
    'G1 Alpha-Validated Operation activated. From passive proof to active learning under constraint. The organism is now allowed to matter.',
    ENCODE(SHA256('G1-ACTIVATION-20251212'::bytea), 'hex'),
    'HC-G1-ACTIVATION-20251212',
    jsonb_build_object(
        'phase', 'G1',
        'classification', 'Controlled Alpha Validation Layer',
        'authority_preserved', jsonb_build_object(
            'tier_3', true,
            'shadow_paper', true,
            'no_write', true,
            'no_allocation', true,
            'no_execution', true,
            'no_autonomy', true
        ),
        'new_capabilities', ARRAY['Active insight generation', 'Alpha impact measurement', 'Human-in-the-loop evaluation', 'RAG infrastructure (CEO-controlled)'],
        'evidence_standard', 'Produces insight worth human attention'
    )
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'MIGRATION 133: G1 ACTIVATION — VERIFICATION'
\echo '═══════════════════════════════════════════════════════════════════════════'

SELECT 'G0.2 EAM Status:' as check_type;
SELECT eam_status, eam_start_timestamp, updated_at as closeout_timestamp
FROM fhq_meta.g1_evidence_accumulation
WHERE eam_status = 'COMPLETE';

SELECT 'G1 Activation Status:' as check_type;
SELECT g1_status, g1_start_timestamp, authority_level, execution_mode
FROM fhq_meta.g1_activation_registry
WHERE g1_status = 'ACTIVE';

SELECT 'Authority Constraints (All Must Be True):' as check_type;
SELECT
    authority_level = 3 as tier_3_preserved,
    execution_mode = 'SHADOW_PAPER' as shadow_paper_preserved,
    write_access = false as no_write_preserved,
    allocation_rights = false as no_allocation_preserved,
    autonomous_behavior = false as no_autonomy_preserved
FROM fhq_meta.g1_activation_registry
WHERE g1_status = 'ACTIVE';

SELECT 'Document Queue Ready:' as check_type;
SELECT COUNT(*) as pending_documents
FROM fhq_meta.canonical_document_queue
WHERE ingestion_status = 'PENDING_AUTHORIZATION';

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'G1 ACTIVATION — ALPHA-VALIDATED OPERATION'
\echo ''
\echo 'Transition Complete:'
\echo '  From: G0.2 — Evidence Accumulation (Passive Proof)'
\echo '  To:   G1   — Alpha-Validated Operation (Active Learning)'
\echo ''
\echo 'Preserved:'
\echo '  ✓ Tier-3 authority'
\echo '  ✓ SHADOW/PAPER mode'
\echo '  ✓ No write access'
\echo '  ✓ No allocation rights'
\echo '  ✓ No autonomous behavior'
\echo ''
\echo 'Activated:'
\echo '  ✓ Active insight generation'
\echo '  ✓ Alpha impact measurement'
\echo '  ✓ Human-in-the-loop evaluation'
\echo '  ✓ RAG infrastructure (awaiting CEO document authorization)'
\echo ''
\echo 'The organism is now allowed to matter.'
\echo '═══════════════════════════════════════════════════════════════════════════'
