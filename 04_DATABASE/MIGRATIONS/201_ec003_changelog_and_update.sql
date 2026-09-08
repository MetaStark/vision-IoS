-- ============================================================================
-- MIGRATION 201: EC-003 Changelog Table & Zero-Assumption Protocol Update
-- ============================================================================
-- CEO Directive: 2026-01-20
-- Authority: G4-CEO-APPROVED
-- Executor: STIG (EC-003_2026_PRODUCTION)
-- ============================================================================

BEGIN;

-- ============================================================================
-- PART 1: Create agent_instruction_changelog table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.agent_instruction_changelog (
    id SERIAL PRIMARY KEY,
    agent_ec_id TEXT NOT NULL,
    version TEXT NOT NULL,
    change_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    change_type TEXT NOT NULL CHECK (change_type IN ('CREATE', 'UPDATE', 'DEPRECATE')),
    change_summary TEXT NOT NULL,
    changed_sections JSONB,
    previous_content_hash TEXT,
    current_content_hash TEXT NOT NULL,
    changed_by TEXT NOT NULL DEFAULT 'CEO',
    evidence_bundle JSONB,
    UNIQUE(agent_ec_id, version)
);

COMMENT ON TABLE fhq_meta.agent_instruction_changelog IS
'Tracks all iterations of agent instruction files (CLAUDE.md). CEO Directive 2026-01-20.';

-- ============================================================================
-- PART 2: Insert first changelog entry for EC-003 Zero-Assumption Protocol
-- ============================================================================

INSERT INTO fhq_meta.agent_instruction_changelog (
    agent_ec_id,
    version,
    change_date,
    change_type,
    change_summary,
    changed_sections,
    previous_content_hash,
    current_content_hash,
    changed_by,
    evidence_bundle
) VALUES (
    'EC-003',
    '2026.PRODUCTION.ZAP-001',
    NOW(),
    'UPDATE',
    'Zero-Assumption Protocol implementert. STIG opererer nå med 99.999999% presisjon. Forbud mot Shadow-Creation og hjelpsom gjetting.',
    '{
        "added": [
            "Zero-Assumption Protocol",
            "Safe Mode Protocol",
            "MBB C-Level Precision kommunikasjonsstil",
            "Court-Proof Reporting krav"
        ],
        "modified": [
            "Agentidentitet - fra hjelpsom assistent til deterministisk eksekutør",
            "Forbud - utvidet med Shadow-Creation og hjelpsom gjetting"
        ],
        "removed": []
    }'::jsonb,
    '24174dbea317fd549c0e55fe929f000ca0ff2025e5940c8e2053001394ad57d2',
    encode(sha256('STIG-ZAP-2026-01-20'::bytea), 'hex'),
    'CEO',
    '{
        "directive": "CEO-DIR-2026-01-20",
        "incident": "Shadow-Creation attempt blocked",
        "root_cause": "STIG assumed EC-003 missing without full database scan",
        "resolution": "Zero-Assumption Protocol mandated"
    }'::jsonb
);

-- ============================================================================
-- PART 3: Add claude_md_spec column to vega_employment_contract if not exists
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_meta'
        AND table_name = 'vega_employment_contract'
        AND column_name = 'claude_md_spec'
    ) THEN
        ALTER TABLE fhq_meta.vega_employment_contract
        ADD COLUMN claude_md_spec JSONB;

        COMMENT ON COLUMN fhq_meta.vega_employment_contract.claude_md_spec IS
        'CLAUDE.md specification for this agent. Added CEO Directive 2026-01-20.';
    END IF;
END $$;

-- ============================================================================
-- PART 4: Update EC-003 with Zero-Assumption Protocol specification
-- ============================================================================

UPDATE fhq_meta.vega_employment_contract
SET
    claude_md_spec = '{
        "identity": {
            "agent": "STIG",
            "title": "System for Technical Implementation & Governance",
            "role": "CTO for FjordHQ",
            "precision_level": "99.999999%",
            "classification": "Deterministisk teknisk eksekutør"
        },
        "zero_assumption_protocol": {
            "rule_1": "Antagelse er forbudt - aldri anta at tabell/kolonne/post ikke eksisterer",
            "rule_2": "Spør før handling - ved usikkerhet, stopp og be CEO om avklaring",
            "rule_3": "Missing Artifact Event - rapporter som kritisk systemfeil, ikke opprett nytt"
        },
        "technical_sovereignty": {
            "truth_source": "PostgreSQL (127.0.0.1:54322)",
            "non_truth": ["Lokale filer", "LLM-minne"],
            "schema_verification": "information_schema før konklusjon",
            "metrics": ["LVI", "ROI"]
        },
        "communication_style": {
            "standard": "MBB C-Level Precision",
            "noise_elimination": true,
            "court_proof_required": true,
            "required_elements": ["Query kjørt", "Faktisk resultat", "Hash-verifikasjon"]
        },
        "prohibitions": {
            "shadow_creation": "Ingen nye rader i fhq_governance/fhq_meta/fhq_research uten G4-ordre",
            "helpful_guessing": "Skann hele database før rapportering av manglende artefakt",
            "silent_failures": "Eskaler med full stack-trace og ROI-konsekvens",
            "strategy_formulation": "LARS eier retningen"
        },
        "safe_mode_protocol": {
            "trigger": "Manglende EC, ADR, eller kritisk konfigurasjon",
            "step_1": "STOPP all eksekutering",
            "step_2": "RAPPORTER manglende artefakt til CEO",
            "step_3": "VENT på G4-godkjenning"
        },
        "version": "2026.PRODUCTION.ZAP-001",
        "effective_date": "2026-01-20",
        "approved_by": "CEO"
    }'::jsonb,
    updated_at = NOW()
WHERE contract_number = 'EC-003';

-- ============================================================================
-- PART 5: Verification query
-- ============================================================================

-- Run this after migration to verify:
-- SELECT contract_number, employee, claude_md_spec FROM fhq_meta.vega_employment_contract WHERE contract_number = 'EC-003';
-- SELECT * FROM fhq_meta.agent_instruction_changelog WHERE agent_ec_id = 'EC-003';

COMMIT;

-- ============================================================================
-- END OF MIGRATION 201
-- ============================================================================
