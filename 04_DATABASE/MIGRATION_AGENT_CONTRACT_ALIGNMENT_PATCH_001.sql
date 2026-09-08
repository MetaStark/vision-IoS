-- ============================================================================
-- MIGRATION: AGENT_CONTRACT_ALIGNMENT_PATCH_001
-- ============================================================================
-- Directive: CEO-DIR-2026-AGENT-CONTRACT-ALIGNMENT-002
-- Authorized: 2026-01-23 by CEO
-- Executed By: STIG (EC-003)
-- Purpose: Repair agent_ec_mapping, populate ec_registry, add missing mandates
-- ============================================================================

-- ============================================================================
-- STEP 0: PRE-FLIGHT EVIDENCE (RUN FIRST, SAVE OUTPUT)
-- ============================================================================

-- 0.1 FK Check (must return 0 rows for safe delete)
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
AND (ccu.table_name = 'agent_ec_mapping' OR tc.table_name = 'agent_ec_mapping');

-- 0.2 Pre-state snapshot (save this output for rollback)
SELECT 'agent_ec_mapping_PRE' as table_name, * FROM fhq_governance.agent_ec_mapping ORDER BY ec_id;
SELECT 'ec_registry_PRE' as table_name, * FROM fhq_governance.ec_registry ORDER BY ec_id;
SELECT 'agent_mandates_PRE' as table_name, agent_name, mandate_type, authority_type, parent_agent
FROM fhq_governance.agent_mandates ORDER BY agent_name;

-- ============================================================================
-- STEP 1: REPAIR agent_ec_mapping (WITHIN TRANSACTION)
-- ============================================================================

BEGIN;

-- 1.1 Clear incorrect mappings
DELETE FROM fhq_governance.agent_ec_mapping;

-- 1.2 Insert CORRECT mappings (based on canonical contract files)
INSERT INTO fhq_governance.agent_ec_mapping
(agent_short_name, ec_id, agent_full_name, role_description) VALUES
-- Tier-1 Constitutional
('VEGA', 'EC-001', 'VEGA - Verification & Governance Authority', 'Constitutional governance and compliance'),
-- Tier-1 Executives
('LARS', 'EC-002', 'LARS - Learning & Adaptive Research Strategist', 'Strategic direction and alpha formulation'),
('STIG', 'EC-003', 'STIG - System for Technical Implementation & Governance', 'Technical execution and infrastructure'),
('FINN', 'EC-004', 'FINN - Forecasting Intelligence Neural Network', 'Research, regime detection, and signal generation'),
('LINE', 'EC-005', 'LINE - Liquid Investment Navigation Engine', 'Execution commander and position management'),
-- Tier-2 Sub-Executives
('CODE', 'EC-006', 'CODE - Engineering Unit', 'Technical implementation and development'),
('CFAO', 'EC-007', 'CFAO - Chief Foresight & Autonomy Officer', 'Adversarial foresight and autonomy governance'),
-- EC-008 INTENTIONALLY OMITTED - It is a Charter, NOT an agent contract
('CEIO', 'EC-009', 'CEIO - Chief External Intelligence Officer', 'External intelligence and signal ingest'),
('CEO', 'EC-010', 'CEO - Sovereign Executive Authority', 'Sovereign governance authority'),
('CSEO', 'EC-011', 'CSEO - Chief Strategy & Execution Officer', 'Strategy execution bridge'),
('CDMO', 'EC-012', 'CDMO - Chief Data & Model Officer', 'Data management and model governance'),
('CRIO', 'EC-013', 'CRIO - Chief Research & Insight Officer', 'Research operations and alpha graph'),
-- Tier-2 Meta/Cognitive Executives
('UMA', 'EC-014', 'UMA - Universal Meta-Analyst', 'Learning velocity and ROI acceleration'),
('CPTO', 'EC-015', 'CPTO - Chief Precision Trading Officer', 'Precision entry and exit transformation'),
-- EC-018 has no explicit agent name in file - using functional title
('META_ALPHA', 'EC-018', 'Meta-Alpha & Freedom Optimizer', 'Meta-analysis and alpha discovery'),
-- EC-019 has no explicit agent name in file - using functional title
('HUMAN_GOV', 'EC-019', 'Operational Convergence & Human Governor', 'Operational governance and convergence'),
-- Cognitive Engines (ACI Triangle)
('SitC', 'EC-020', 'SitC - Search-in-the-Chain Protocol', 'Dynamic reasoning chain construction'),
('InForage', 'EC-021', 'InForage - Information Foraging Protocol', 'Search optimization and ROI on curiosity'),
('IKEA', 'EC-022', 'IKEA - Knowledge Boundary Officer', 'Hallucination firewall and knowledge classification');

-- Verify Step 1
SELECT 'STEP_1_VERIFY' as check_name, COUNT(*) as row_count,
       SUM(CASE WHEN ec_id = 'EC-008' THEN 1 ELSE 0 END) as ec008_count
FROM fhq_governance.agent_ec_mapping;
-- EXPECTED: row_count = 19, ec008_count = 0

COMMIT;

-- ============================================================================
-- STEP 2: EC-008 REMOVAL VERIFICATION
-- ============================================================================

-- Verify EC-008 is NOT in agent_ec_mapping
SELECT 'EC008_MAPPING_CHECK' as check_name,
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END as status
FROM fhq_governance.agent_ec_mapping WHERE ec_id = 'EC-008';

-- Verify EC-008 is NOT in agent_mandates (should already be absent)
SELECT 'EC008_MANDATE_CHECK' as check_name,
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END as status
FROM fhq_governance.agent_mandates WHERE agent_name = 'EC-008';

-- ============================================================================
-- STEP 3: POPULATE ec_registry WITH MISSING CONTRACTS
-- ============================================================================

BEGIN;

INSERT INTO fhq_governance.ec_registry
(ec_id, title, role_type, parent_executive, status, effective_date, authority_chain)
VALUES
-- Core Contracts (EC-001 through EC-013)
('EC-001', 'VEGA - Chief Governance & Verification Officer', 'Tier-1 Constitutional', 'CEO', 'ACTIVE', '2025-11-28', 'ADR-001 → ADR-003 → EC-001'),
('EC-002', 'LARS - Chief Strategy & Alpha Officer', 'Tier-1 Executive', 'CEO', 'ACTIVE', '2025-11-28', 'ADR-001 → ADR-003 → ADR-006 → EC-002'),
('EC-003', 'STIG - Chief Technology Officer', 'Tier-1 Executive', 'LARS', 'ACTIVE', '2025-11-28', 'ADR-001 → ADR-003 → ADR-007 → EC-003'),
('EC-004', 'FINN - Chief Research & Insight Officer', 'Tier-1 Executive', 'LARS', 'ACTIVE', '2025-11-28', 'ADR-001 → ADR-003 → ADR-004 → EC-004'),
('EC-005', 'LINE - Chief Operating Officer & Execution Commander', 'Tier-1 Executive', 'LARS', 'ACTIVE', '2025-11-28', 'ADR-001 → ADR-003 → ADR-006 → EC-005'),
('EC-006', 'CODE - Engineering Unit', 'Tier-2 Technical', 'STIG', 'ACTIVE', '2025-11-28', 'ADR-001 → ADR-003 → ADR-007 → EC-003 → EC-006'),
('EC-007', 'CFAO - Chief Foresight & Autonomy Officer', 'Tier-2 Sub-Executive', 'LARS', 'ACTIVE', '2025-11-28', 'ADR-001 → ADR-003 → ADR-012 → ADR-014 → ADR-016 → EC-007'),
('EC-008', 'Enterprise AI Architecture & Technology Horizon Framework', 'Charter (NOT AN AGENT)', 'N/A', 'ACTIVE', '2025-11-28', 'ADR-001 → ADR-003 → ADR-006 → ADR-012 → ADR-014 → EC-008'),
('EC-009', 'CEIO - Chief External Intelligence Officer', 'Tier-2 Sub-Executive', 'STIG', 'ACTIVE', '2025-11-28', 'ADR-001 → ADR-003 → ADR-007 → ADR-012 → ADR-014 → EC-009'),
('EC-010', 'CEO - Sovereign Executive Authority', 'Tier-0 Sovereign', 'N/A', 'ACTIVE', '2025-11-28', 'ADR-001 → EC-010'),
('EC-011', 'CSEO - Chief Strategy & Execution Officer', 'Tier-2 Sub-Executive', 'LARS', 'ACTIVE', '2025-11-28', 'ADR-001 → ADR-003 → ADR-006 → ADR-014 → EC-011'),
('EC-012', 'CDMO - Chief Data & Model Officer', 'Tier-2 Sub-Executive', 'STIG', 'ACTIVE', '2025-11-28', 'ADR-001 → ADR-003 → ADR-007 → ADR-013 → ADR-014 → EC-012'),
('EC-013', 'CRIO - Chief Research & Insight Officer', 'Tier-2 Sub-Executive', 'FINN', 'ACTIVE', '2025-11-28', 'ADR-001 → ADR-003 → ADR-004 → ADR-014 → EC-013'),
-- New Contracts (EC-015, EC-019)
('EC-015', 'CPTO - Chief Precision Trading Officer', 'Tier-2 Sub-Executive', 'FINN', 'ACTIVE', '2026-01-19', 'ADR-001 → ADR-003 → ADR-004 → EC-004 → EC-015'),
('EC-019', 'Operational Convergence & Human Governor', 'Tier-2 Governance Authority', 'CEO', 'ACTIVE', '2025-12-09', 'ADR-001 → ADR-003 → ADR-004 → EC-019')
ON CONFLICT (ec_id) DO UPDATE SET
    title = EXCLUDED.title,
    role_type = EXCLUDED.role_type,
    parent_executive = EXCLUDED.parent_executive,
    status = EXCLUDED.status;

-- Verify Step 3
SELECT 'STEP_3_VERIFY' as check_name, COUNT(*) as row_count
FROM fhq_governance.ec_registry;
-- EXPECTED: row_count = 20 (EC-001 through EC-015, EC-018 through EC-022)

COMMIT;

-- ============================================================================
-- STEP 4: ADD MISSING AGENTS TO agent_mandates
-- ============================================================================

BEGIN;

-- Check if CODE exists
SELECT 'CODE_EXISTS_CHECK' as check_name, COUNT(*) as exists_count
FROM fhq_governance.agent_mandates WHERE agent_name = 'CODE';

-- Insert CODE if missing
INSERT INTO fhq_governance.agent_mandates
(agent_name, mandate_version, mandate_type, authority_type, parent_agent, mandate_document)
SELECT 'CODE', '2026.PRODUCTION', 'technical', 'IMPLEMENTATION', 'STIG',
       'EC-006: Engineering Unit - Technical implementation and development'
WHERE NOT EXISTS (SELECT 1 FROM fhq_governance.agent_mandates WHERE agent_name = 'CODE');

-- Check if CPTO exists
SELECT 'CPTO_EXISTS_CHECK' as check_name, COUNT(*) as exists_count
FROM fhq_governance.agent_mandates WHERE agent_name = 'CPTO';

-- Insert CPTO if missing
INSERT INTO fhq_governance.agent_mandates
(agent_name, mandate_version, mandate_type, authority_type, parent_agent, mandate_document)
SELECT 'CPTO', '2026.PRODUCTION', 'subexecutive', 'TRANSFORMATION', 'FINN',
       'EC-015: Chief Precision Trading Officer - Precision entry and exit transformation'
WHERE NOT EXISTS (SELECT 1 FROM fhq_governance.agent_mandates WHERE agent_name = 'CPTO');

-- Insert META_ALPHA if missing (EC-018)
INSERT INTO fhq_governance.agent_mandates
(agent_name, mandate_version, mandate_type, authority_type, parent_agent, mandate_document)
SELECT 'META_ALPHA', '2026.PRODUCTION', 'cognitive', 'META_ANALYSIS', 'CEO',
       'EC-018: Meta-Alpha & Freedom Optimizer - Meta-analysis and alpha discovery'
WHERE NOT EXISTS (SELECT 1 FROM fhq_governance.agent_mandates WHERE agent_name = 'META_ALPHA');

-- Insert HUMAN_GOV if missing (EC-019)
INSERT INTO fhq_governance.agent_mandates
(agent_name, mandate_version, mandate_type, authority_type, parent_agent, mandate_document)
SELECT 'HUMAN_GOV', '2026.PRODUCTION', 'governance', 'CONVERGENCE', 'CEO',
       'EC-019: Operational Convergence & Human Governor - Operational governance'
WHERE NOT EXISTS (SELECT 1 FROM fhq_governance.agent_mandates WHERE agent_name = 'HUMAN_GOV');

-- Verify Step 4
SELECT 'STEP_4_VERIFY' as check_name, COUNT(*) as row_count
FROM fhq_governance.agent_mandates;
-- EXPECTED: 18 agents (14 original + CODE + CPTO + META_ALPHA + HUMAN_GOV)

COMMIT;

-- ============================================================================
-- STEP 5: POST-VERIFY GATE (ALL MUST PASS)
-- ============================================================================

-- 5.1 Mismatch count must be ZERO
WITH contract_truth AS (
    SELECT 'EC-001' as ec_id, 'VEGA' as correct_agent UNION ALL
    SELECT 'EC-002', 'LARS' UNION ALL
    SELECT 'EC-003', 'STIG' UNION ALL
    SELECT 'EC-004', 'FINN' UNION ALL
    SELECT 'EC-005', 'LINE' UNION ALL
    SELECT 'EC-006', 'CODE' UNION ALL
    SELECT 'EC-007', 'CFAO' UNION ALL
    SELECT 'EC-009', 'CEIO' UNION ALL
    SELECT 'EC-010', 'CEO' UNION ALL
    SELECT 'EC-011', 'CSEO' UNION ALL
    SELECT 'EC-012', 'CDMO' UNION ALL
    SELECT 'EC-013', 'CRIO' UNION ALL
    SELECT 'EC-014', 'UMA' UNION ALL
    SELECT 'EC-015', 'CPTO' UNION ALL
    SELECT 'EC-018', 'META_ALPHA' UNION ALL
    SELECT 'EC-019', 'HUMAN_GOV' UNION ALL
    SELECT 'EC-020', 'SitC' UNION ALL
    SELECT 'EC-021', 'InForage' UNION ALL
    SELECT 'EC-022', 'IKEA'
)
SELECT
    'MISMATCH_COUNT' as check_name,
    COUNT(*) as mismatch_count,
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END as status
FROM contract_truth ct
LEFT JOIN fhq_governance.agent_ec_mapping m ON ct.ec_id = m.ec_id
WHERE m.agent_short_name IS NULL OR m.agent_short_name != ct.correct_agent;

-- 5.2 EC-008 must be absent from agent tables
SELECT
    'EC008_ABSENT' as check_name,
    (SELECT COUNT(*) FROM fhq_governance.agent_ec_mapping WHERE ec_id = 'EC-008') as mapping_count,
    CASE WHEN (SELECT COUNT(*) FROM fhq_governance.agent_ec_mapping WHERE ec_id = 'EC-008') = 0
         THEN 'PASS' ELSE 'FAIL' END as status;

-- 5.3 ec_registry completeness
SELECT
    'EC_REGISTRY_COMPLETE' as check_name,
    COUNT(*) as total_contracts,
    CASE WHEN COUNT(*) >= 20 THEN 'PASS' ELSE 'FAIL' END as status
FROM fhq_governance.ec_registry;

-- 5.4 agent_mandates completeness
SELECT
    'AGENT_MANDATES_COMPLETE' as check_name,
    COUNT(*) as total_agents,
    CASE WHEN COUNT(*) >= 18 THEN 'PASS' ELSE 'FAIL' END as status
FROM fhq_governance.agent_mandates;

-- 5.5 Final state dump (for evidence)
SELECT 'agent_ec_mapping_POST' as table_name, * FROM fhq_governance.agent_ec_mapping ORDER BY ec_id;
SELECT 'ec_registry_POST' as table_name, ec_id, title, role_type, parent_executive, status FROM fhq_governance.ec_registry ORDER BY ec_id;
SELECT 'agent_mandates_POST' as table_name, agent_name, mandate_type, authority_type, parent_agent FROM fhq_governance.agent_mandates ORDER BY agent_name;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
-- Expected Results:
-- - agent_ec_mapping: 19 rows (no EC-008)
-- - ec_registry: 20 rows (includes EC-008 as Charter, not agent)
-- - agent_mandates: 18 agents
-- - Mismatch count: 0
-- - EC-008 absent from agent mapping: PASS
-- ============================================================================

-- Evidence Hash (run after completion):
SELECT
    'MIGRATION_EVIDENCE' as record_type,
    'AGENT_CONTRACT_ALIGNMENT_PATCH_001' as migration_id,
    NOW() as executed_at,
    (SELECT COUNT(*) FROM fhq_governance.agent_ec_mapping) as mapping_count,
    (SELECT COUNT(*) FROM fhq_governance.ec_registry) as registry_count,
    (SELECT COUNT(*) FROM fhq_governance.agent_mandates) as mandate_count,
    md5(
        (SELECT string_agg(ec_id || ':' || agent_short_name, ',' ORDER BY ec_id)
         FROM fhq_governance.agent_ec_mapping)
    ) as mapping_hash;
