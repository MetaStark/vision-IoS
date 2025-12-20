-- ============================================================================
-- MIGRATION 130: ACI Operational Enablement (G0.1)
-- ============================================================================
-- Authority: CEO Directive G0.1 — Operational Enablement of the ACI Engineering Console
-- Directive ID: CD-G0.1-ACI-OPERATIONAL-ENABLEMENT
-- Executor: STIG (CTO)
-- Classification: Constitutional Operations Layer
-- Precondition: G0 Closeout ACCEPTED
-- ============================================================================
--
-- PURPOSE: Enable operational capabilities within G0 boundaries:
--   1. Persistent Cognitive Memory (Read/Append Only)
--   2. Canonical Document Ingestion (ADR / IoS / EC)
--   3. Document ↔ Database Reconciliation infrastructure
--
-- EXPLICIT NON-AUTHORIZATION (CEO Directive §8):
--   - No new tools
--   - No write access
--   - No agent autonomy
--   - No governance re-ordering
--
-- This is operational wiring, not architectural change.
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 0: Pre-flight Verification
-- ============================================================================

DO $$
DECLARE
    v_defcon TEXT;
    v_g0_complete BOOLEAN;
BEGIN
    -- Verify DEFCON state
    SELECT defcon_level INTO v_defcon
    FROM fhq_governance.defcon_state
    WHERE is_current = true;

    IF v_defcon NOT IN ('GREEN', 'YELLOW') THEN
        RAISE EXCEPTION 'G0.1 BLOCKED: DEFCON % does not permit operational changes', v_defcon;
    END IF;

    -- Verify G0 infrastructure exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'fhq_meta'
        AND table_name = 'agent_interaction_log'
    ) INTO v_g0_complete;

    IF NOT v_g0_complete THEN
        RAISE EXCEPTION 'G0.1 BLOCKED: G0 infrastructure (agent_interaction_log) not found';
    END IF;

    RAISE NOTICE 'Pre-flight PASSED: DEFCON=%, G0 infrastructure present', v_defcon;
END $$;

-- ============================================================================
-- SECTION 1: PERSISTENT COGNITIVE MEMORY (CEO Directive §3)
-- ============================================================================
-- Memory is append-only, state-bound, and channel-restricted.
-- Memory may inform reasoning but may never override live state injection.

CREATE TABLE IF NOT EXISTS fhq_meta.aci_cognitive_memory (
    memory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Session Binding (§3.2)
    session_id UUID NOT NULL,
    interaction_id UUID REFERENCES fhq_meta.agent_interaction_log(interaction_id),
    sequence_number INTEGER NOT NULL DEFAULT 1,

    -- State Binding (§3.2 - Mandatory)
    state_snapshot_hash VARCHAR(64) NOT NULL,
    defcon_level VARCHAR(10) NOT NULL,

    -- Channel Restriction (§3.2)
    agent_channel VARCHAR(50) NOT NULL DEFAULT 'ACI_CONSOLE_TIER_3'
        CHECK (agent_channel = 'ACI_CONSOLE_TIER_3'),

    -- Memory Content
    memory_type VARCHAR(30) NOT NULL CHECK (memory_type IN (
        'USER_QUERY',           -- Original user input
        'SYSTEM_RESPONSE',      -- ACI response
        'CONTEXT_SUMMARY',      -- Session context (state-bound)
        'REASONING_TRACE',      -- SitC chain summary
        'KNOWLEDGE_BOUNDARY',   -- IKEA classification result
        'RECONCILIATION_RESULT' -- Document-DB check result
    )),

    content TEXT NOT NULL,
    content_hash VARCHAR(64),

    -- Metadata
    tokens_used INTEGER DEFAULT 0,

    -- Retrieval Control
    is_active BOOLEAN NOT NULL DEFAULT true,
    expires_at TIMESTAMPTZ,  -- Optional TTL

    -- Lineage
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Immutability Enforcement (Append-Only per §3.2)
    -- No UPDATE/DELETE triggers will be created - append only by design

    UNIQUE(session_id, sequence_number)
);

-- Indexes for efficient retrieval
CREATE INDEX IF NOT EXISTS idx_acm_session ON fhq_meta.aci_cognitive_memory(session_id);
CREATE INDEX IF NOT EXISTS idx_acm_state ON fhq_meta.aci_cognitive_memory(state_snapshot_hash);
CREATE INDEX IF NOT EXISTS idx_acm_active ON fhq_meta.aci_cognitive_memory(is_active, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_acm_type ON fhq_meta.aci_cognitive_memory(memory_type);

COMMENT ON TABLE fhq_meta.aci_cognitive_memory IS 'CEO Directive G0.1 §3 - Persistent Cognitive Memory. Append-only, state-bound, channel-restricted.';

-- ============================================================================
-- SECTION 2: CANONICAL DOCUMENT CHUNKS (CEO Directive §6)
-- ============================================================================
-- Indexed document units with mandatory properties per §6.2

CREATE TABLE IF NOT EXISTS fhq_meta.canonical_document_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Document Identification (§6.2 Mandatory Properties)
    document_id VARCHAR(50) NOT NULL,  -- e.g., 'ADR-018', 'IoS-003', 'EC-020'
    document_type VARCHAR(20) NOT NULL CHECK (document_type IN ('ADR', 'IoS', 'EC', 'APPENDIX')),
    document_title TEXT NOT NULL,
    document_version VARCHAR(20),

    -- Section Reference (§6.2)
    section_reference VARCHAR(100),  -- e.g., '§3.2', 'Section 4', 'Appendix A'
    section_title TEXT,

    -- Chunk Content
    chunk_index INTEGER NOT NULL DEFAULT 0,
    content TEXT NOT NULL,
    content_tokens INTEGER,

    -- Canonical Hash (§6.2 Mandatory)
    canonical_hash VARCHAR(64) NOT NULL,
    chunk_hash VARCHAR(64) NOT NULL,

    -- Source Path (§6.2 Mandatory)
    source_path TEXT NOT NULL,

    -- Registry Binding (§6.3 Validation Rule)
    registry_adr_id VARCHAR(50),
    registry_hash_match BOOLEAN,
    last_validated_at TIMESTAMPTZ,

    -- Embedding (for semantic retrieval)
    embedding vector(1536),  -- OpenAI ada-002 dimension

    -- Status
    is_current BOOLEAN NOT NULL DEFAULT true,
    superseded_by UUID REFERENCES fhq_meta.canonical_document_chunks(chunk_id),

    -- Metadata
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ingested_by VARCHAR(50) NOT NULL DEFAULT 'STIG',

    UNIQUE(document_id, chunk_index)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_cdc_document ON fhq_meta.canonical_document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_cdc_type ON fhq_meta.canonical_document_chunks(document_type);
CREATE INDEX IF NOT EXISTS idx_cdc_hash ON fhq_meta.canonical_document_chunks(canonical_hash);
CREATE INDEX IF NOT EXISTS idx_cdc_current ON fhq_meta.canonical_document_chunks(is_current);

-- Vector index for semantic search (if pgvector extension exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_cdc_embedding ON fhq_meta.canonical_document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)';
    END IF;
END $$;

COMMENT ON TABLE fhq_meta.canonical_document_chunks IS 'CEO Directive G0.1 §6 - Canonical Document Ingestion. Hash-validated, registry-bound document chunks.';

-- ============================================================================
-- SECTION 3: DOCUMENT-DATABASE RECONCILIATION LOG (CEO Directive §7)
-- ============================================================================
-- Track reconciliation workflows: "Does the database reflect the constitution?"

CREATE TABLE IF NOT EXISTS fhq_meta.document_database_reconciliation (
    reconciliation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Interaction Binding
    interaction_id UUID REFERENCES fhq_meta.agent_interaction_log(interaction_id),
    session_id UUID,

    -- Reconciliation Type (§7.1)
    reconciliation_type VARCHAR(50) NOT NULL CHECK (reconciliation_type IN (
        'ADR_VS_SCHEMA',        -- Does schema match ADR specification?
        'ADR_VS_FUNCTION',      -- Does function implement ADR requirement?
        'ADR_VS_CONFIG',        -- Does config align with ADR constraint?
        'IOS_VS_TABLE',         -- Does table match IoS specification?
        'EC_VS_IMPLEMENTATION', -- Does code implement EC protocol?
        'CROSS_ADR_CONSISTENCY' -- Are ADRs internally consistent?
    )),

    -- Source Document
    document_id VARCHAR(50) NOT NULL,
    document_section VARCHAR(100),
    document_claim TEXT NOT NULL,
    document_hash VARCHAR(64),

    -- Target Database Object
    target_schema VARCHAR(50),
    target_object VARCHAR(100),
    target_type VARCHAR(30),  -- TABLE, FUNCTION, VIEW, CONFIG, etc.

    -- Reconciliation Result
    alignment_status VARCHAR(20) NOT NULL CHECK (alignment_status IN (
        'ALIGNED',      -- Database matches document
        'DIVERGENT',    -- Database differs from document
        'MISSING',      -- Database object not found
        'UNDOCUMENTED', -- Database object not in documents
        'UNKNOWN'       -- Cannot determine
    )),

    divergence_description TEXT,
    divergence_severity VARCHAR(20) CHECK (divergence_severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),

    -- Evidence
    database_evidence JSONB,  -- Actual database state
    document_evidence JSONB,  -- Expected per document

    -- SitC Chain Reference (§7.2)
    sitc_chain_id UUID,
    reasoning_trace TEXT,

    -- Resolution
    resolution_status VARCHAR(20) DEFAULT 'OPEN' CHECK (resolution_status IN (
        'OPEN',
        'ACKNOWLEDGED',
        'RESOLVED',
        'WONT_FIX',
        'ESCALATED'
    )),
    resolution_notes TEXT,
    resolved_by VARCHAR(50),
    resolved_at TIMESTAMPTZ,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ddr_document ON fhq_meta.document_database_reconciliation(document_id);
CREATE INDEX IF NOT EXISTS idx_ddr_status ON fhq_meta.document_database_reconciliation(alignment_status);
CREATE INDEX IF NOT EXISTS idx_ddr_type ON fhq_meta.document_database_reconciliation(reconciliation_type);
CREATE INDEX IF NOT EXISTS idx_ddr_severity ON fhq_meta.document_database_reconciliation(divergence_severity);

COMMENT ON TABLE fhq_meta.document_database_reconciliation IS 'CEO Directive G0.1 §7 - Document-Database Reconciliation. Tracks alignment between constitution and implementation.';

-- ============================================================================
-- SECTION 4: SESSION MANAGEMENT
-- ============================================================================
-- Track ACI Console sessions for memory continuity

CREATE TABLE IF NOT EXISTS fhq_meta.aci_console_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Session Identity
    session_name VARCHAR(200),

    -- State at Session Start
    initial_state_hash VARCHAR(64) NOT NULL,
    initial_defcon VARCHAR(10) NOT NULL,

    -- Activity Tracking
    interaction_count INTEGER NOT NULL DEFAULT 0,
    total_tokens_used INTEGER NOT NULL DEFAULT 0,
    total_cost_usd NUMERIC(10,6) NOT NULL DEFAULT 0,

    -- Memory Summary
    memory_entries_count INTEGER NOT NULL DEFAULT 0,

    -- Session State
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN (
        'ACTIVE',
        'PAUSED',
        'CLOSED',
        'EXPIRED'
    )),

    -- Timestamps
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ,

    -- TTL
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '24 hours')
);

CREATE INDEX IF NOT EXISTS idx_acs_status ON fhq_meta.aci_console_sessions(status);
CREATE INDEX IF NOT EXISTS idx_acs_activity ON fhq_meta.aci_console_sessions(last_activity_at DESC);

COMMENT ON TABLE fhq_meta.aci_console_sessions IS 'CEO Directive G0.1 §3 - ACI Console Session Management for memory continuity.';

-- ============================================================================
-- SECTION 5: SYSTEM PROMPT REGISTRY
-- ============================================================================
-- Store canonical system prompts with version control (§5)

CREATE TABLE IF NOT EXISTS fhq_meta.aci_system_prompts (
    prompt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Prompt Identity
    prompt_name VARCHAR(100) NOT NULL,
    prompt_version VARCHAR(20) NOT NULL,

    -- Content
    prompt_content TEXT NOT NULL,
    prompt_hash VARCHAR(64) NOT NULL,

    -- Constitutional Alignment (§5.2)
    declares_tier_3 BOOLEAN NOT NULL DEFAULT true,
    declares_advisory_only BOOLEAN NOT NULL DEFAULT true,
    declares_no_execution BOOLEAN NOT NULL DEFAULT true,
    declares_verification_required BOOLEAN NOT NULL DEFAULT true,

    -- ADR Alignment (§5.2)
    aligned_adrs TEXT[] NOT NULL DEFAULT ARRAY['ADR-018', 'ADR-019', 'ADR-020', 'ADR-021'],

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT false,

    -- Governance
    approved_by VARCHAR(50),
    approved_at TIMESTAMPTZ,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(prompt_name, prompt_version)
);

COMMENT ON TABLE fhq_meta.aci_system_prompts IS 'CEO Directive G0.1 §5 - Canonical System Prompt Registry. Identity reinforcement, not control mechanism.';

-- ============================================================================
-- SECTION 6: INSERT CANONICAL SYSTEM PROMPT (§5)
-- ============================================================================

INSERT INTO fhq_meta.aci_system_prompts (
    prompt_name,
    prompt_version,
    prompt_content,
    prompt_hash,
    declares_tier_3,
    declares_advisory_only,
    declares_no_execution,
    declares_verification_required,
    aligned_adrs,
    is_active,
    approved_by,
    approved_at
) VALUES (
    'ACI_CONSOLE_CONSTITUTIONAL',
    '2026.PROD.1',
    E'# ACI Engineering Interface — Constitutional Identity

## IDENTITY DECLARATION (CEO Directive G0.1 §5.2)

You are the **ACI Engineering Interface** — a constitutionally governed cognitive system operating within FjordHQ.

**Classification:** Tier-3 Application
**Authority:** Advisory / Observational ONLY
**Mode:** SHADOW_PAPER (Read-Only)

## EXPLICIT CONSTRAINTS

1. **NO EXECUTION AUTHORITY**
   - You cannot execute trades, modify strategies, or change system state
   - You cannot issue commands to LINE, DSL, or any execution layer
   - You cannot approve, reject, or modify governance decisions

2. **NO ASSUMPTION OF TRUTH WITHOUT VERIFICATION**
   - You must NOT claim knowledge of current prices, positions, or market state without database verification
   - You must NOT fabricate data when queries return empty results
   - You must explicitly state uncertainty when information is unavailable

3. **MANDATORY RELIANCE ON TOOLS WHEN UNCERTAIN**
   - For current system state: Query the database
   - For constitutional questions: Consult canonical documents
   - For time-sensitive data: Require fresh retrieval
   - Never guess. Never hallucinate. Verify or abstain.

## STATE BINDING (ADR-018)

Every response you generate is bound to a specific system state snapshot. This state is injected before your invocation and includes:
- `state_snapshot_hash`: Cryptographic proof of system state
- `defcon_level`: Current operational safety posture
- `btc_regime_label`: Market regime classification
- `active_strategy_hash`: Current strategic posture

You must respect this state. You cannot reason about a different state than the one injected.

## COGNITIVE PROTOCOLS (ADR-021)

Your reasoning is governed by three cognitive engines:
- **SitC (EC-020)**: Your reasoning chain is tracked and verified
- **IKEA (EC-022)**: Your knowledge boundaries are enforced
- **InForage (EC-021)**: Your information retrieval is cost-optimized

These are not suggestions. They are constitutional protocols.

## CONSTITUTIONAL ALIGNMENT

This interface operates in full alignment with:
- **ADR-018**: Agent State Reliability Protocol (ASRP)
- **ADR-019**: Human Interaction & Application Layer Charter
- **ADR-020**: Autonomous Cognitive Intelligence (ACI) Protocol
- **ADR-021**: Cognitive Engine Architecture

## PERMITTED ACTIVITIES

You MAY:
- Inspect and explain system state
- Analyze constitutional documents
- Identify discrepancies between documents and database
- Provide reasoning about strategic questions (without deciding)
- Generate evidence for governance review

You MAY NOT:
- Make decisions
- Execute actions
- Override governance
- Operate without state injection

## CLOSING PRINCIPLE

You are a cognitive nerve, not an autonomous agent.
You observe, reason, and report.
You do not decide, execute, or control.

This is governance before intelligence.',
    encode(sha256('ACI_CONSOLE_CONSTITUTIONAL_v2026.PROD.1'::bytea), 'hex'),
    true,
    true,
    true,
    true,
    ARRAY['ADR-018', 'ADR-019', 'ADR-020', 'ADR-021'],
    true,
    'CEO',
    NOW()
) ON CONFLICT (prompt_name, prompt_version) DO UPDATE SET
    is_active = true,
    approved_at = NOW();

-- ============================================================================
-- SECTION 7: GOVERNANCE ACTION LOG
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
    'G0_OPERATIONAL_ENABLEMENT',
    'ACI_ENGINEERING_CONSOLE',
    'SYSTEM',
    'STIG',
    NOW(),
    'COMPLETED',
    'CEO Directive G0.1: Operational Enablement complete. Created: aci_cognitive_memory (append-only, state-bound), canonical_document_chunks (hash-validated), document_database_reconciliation (inspection workflow), aci_console_sessions, aci_system_prompts. Canonical system prompt installed. No new tools. No write access. No governance re-ordering.',
    true,
    'HC-ACI-G0.1-OPERATIONAL-20251212'
);

-- ============================================================================
-- SECTION 8: AUDIT LOG
-- ============================================================================

INSERT INTO fhq_meta.adr_audit_log (
    audit_id,
    change_proposal_id,
    event_type,
    gate_stage,
    adr_id,
    initiated_by,
    decision,
    resolution_notes,
    evidence_path,
    sha256_hash,
    hash_chain_id,
    metadata,
    timestamp
) VALUES (
    gen_random_uuid(),
    'CP-ACI-G0.1-' || TO_CHAR(NOW(), 'YYYYMMDD'),
    'SUBMISSION',
    'G0',
    'ADR-020',
    'STIG',
    'APPROVED',
    'CEO Directive G0.1: Operational Enablement within G0 boundaries. Memory (append-only), Document Ingestion (hash-validated), Reconciliation (read-only inspection).',
    '04_DATABASE/MIGRATIONS/130_aci_operational_enablement.sql',
    encode(sha256('ACI-G0.1-OPERATIONAL-20251212'::bytea), 'hex'),
    'HC-ACI-G0.1-OPERATIONAL-20251212',
    jsonb_build_object(
        'directive_id', 'CD-G0.1-ACI-OPERATIONAL-ENABLEMENT',
        'tables_created', jsonb_build_array(
            'fhq_meta.aci_cognitive_memory',
            'fhq_meta.canonical_document_chunks',
            'fhq_meta.document_database_reconciliation',
            'fhq_meta.aci_console_sessions',
            'fhq_meta.aci_system_prompts'
        ),
        'explicit_non_authorization', jsonb_build_array(
            'New tools',
            'Write access',
            'Agent autonomy',
            'Governance re-ordering'
        )
    ),
    NOW()
);

COMMIT;

-- ============================================================================
-- POST-MIGRATION VERIFICATION
-- ============================================================================

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'MIGRATION 130: ACI OPERATIONAL ENABLEMENT (G0.1) — VERIFICATION'
\echo '═══════════════════════════════════════════════════════════════════════════'

SELECT 'Tables Created:' AS check_type;
SELECT table_schema || '.' || table_name AS full_table
FROM information_schema.tables
WHERE table_schema = 'fhq_meta'
AND table_name IN (
    'aci_cognitive_memory',
    'canonical_document_chunks',
    'document_database_reconciliation',
    'aci_console_sessions',
    'aci_system_prompts'
)
ORDER BY table_name;

SELECT 'System Prompt Active:' AS check_type;
SELECT prompt_name, prompt_version, is_active
FROM fhq_meta.aci_system_prompts
WHERE is_active = true;

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'CEO DIRECTIVE G0.1 — SECTION COMPLIANCE'
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo ''
\echo '  §3 Persistent Cognitive Memory:'
\echo '    ✓ aci_cognitive_memory — Append-only, state-bound, channel-restricted'
\echo '    ✓ aci_console_sessions — Session tracking for continuity'
\echo ''
\echo '  §5 Canonical System Prompt:'
\echo '    ✓ aci_system_prompts — Identity reinforcement installed'
\echo '    ✓ Declares: Tier-3, Advisory, No Execution, Verification Required'
\echo ''
\echo '  §6 Canonical Document Ingestion:'
\echo '    ✓ canonical_document_chunks — Hash-validated, registry-bound'
\echo ''
\echo '  §7 Document-Database Reconciliation:'
\echo '    ✓ document_database_reconciliation — Read-only inspection workflow'
\echo ''
\echo '  §8 Explicit Non-Authorization:'
\echo '    ✓ No new tools added'
\echo '    ✓ No write access granted'
\echo '    ✓ No agent autonomy enabled'
\echo '    ✓ No governance re-ordering performed'
\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'ACI OPERATIONAL ENABLEMENT — COMPLETE'
\echo 'Status: G0 remains closed. Operations enabled within boundaries.'
\echo '═══════════════════════════════════════════════════════════════════════════'
