-- ============================================================================
-- MIGRATION 135: G1 BATCH DOCUMENT INGESTION
-- ============================================================================
-- Authority: CEO DIRECTIVE - G1 DOCUMENT INGESTION & CANONICAL RECONCILIATION ORDER
-- Classification: G1 - Canonical Reconciliation Phase
-- Purpose: Batch ingest all authorized documents from ADR, IoS, EC directories
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: ADR DOCUMENTS (00_CONSTITUTION)
-- ============================================================================

-- ADR-002
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('00_CONSTITUTION/ADR-002_2026_PRODUCTION_Audit and Error Reconciliation Charter.md', 'ADR-002 - Audit and Error Reconciliation Charter', 'ADR', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Audit logging and error reconciliation requirements', 2, 'PENDING')
ON CONFLICT DO NOTHING;

-- ADR-003
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('00_CONSTITUTION/ADR-003_2026_PRODUCTION - FjordHQ Institutional Standards and Compliance Framework.md', 'ADR-003 - Institutional Standards and Compliance Framework', 'ADR', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Schema naming, MDLC, institutional standards', 3, 'PENDING')
ON CONFLICT DO NOTHING;

-- ADR-004
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('00_CONSTITUTION/ADR-004_2026_PRODUCTION_Change Gates Architecture.md', 'ADR-004 - Change Gates Architecture', 'ADR', 'STIG', 'CEO', NOW(), 'COMPLETE', 'G0-G4 gate workflow requirements', 4, 'PENDING')
ON CONFLICT DO NOTHING;

-- ADR-005
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('00_CONSTITUTION/ADR-005_2026_PRODUCTION_Mission & Vision Charter.md', 'ADR-005 - Mission and Vision Charter', 'ADR', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Strategic mission and vision alignment', 5, 'PENDING')
ON CONFLICT DO NOTHING;

-- ADR-006
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('00_CONSTITUTION/ADR-006_2026_PRODUCTION_VEGA Autonomy and Governance Engine Charter.md', 'ADR-006 - VEGA Autonomy and Governance Engine Charter', 'ADR', 'STIG', 'CEO', NOW(), 'COMPLETE', 'VEGA governance authority and veto mechanisms', 6, 'PENDING')
ON CONFLICT DO NOTHING;

-- ADR-007
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('00_CONSTITUTION/ADR-007_2026_PRODUCTION_ORCHESTRATOR.md', 'ADR-007 - LARS Orchestrator Architecture', 'ADR', 'STIG', 'CEO', NOW(), 'COMPLETE', 'LARS coordination and orchestration requirements', 7, 'PENDING')
ON CONFLICT DO NOTHING;

-- ADR-008
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('00_CONSTITUTION/ADR-008_2026_PRODUCTION_Cryptographic Key Management and Rotation Architecture.md', 'ADR-008 - Cryptographic Key Management', 'ADR', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Ed25519 signing and key rotation requirements', 8, 'PENDING')
ON CONFLICT DO NOTHING;

-- ADR-009
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('00_CONSTITUTION/ADR-009_2026_PRODUCTION_Governance Approval Workflow for Agent Suspension.md', 'ADR-009 - Agent Suspension Governance', 'ADR', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Agent suspension workflow requirements', 9, 'PENDING')
ON CONFLICT DO NOTHING;

-- ADR-010
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('00_CONSTITUTION/ADR-010_2026_PRODUCTION_State Reconciliation Methodology and Discrepancy Scoring.md', 'ADR-010 - State Reconciliation Methodology', 'ADR', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Discrepancy scoring and reconciliation methods', 10, 'PENDING')
ON CONFLICT DO NOTHING;

-- ADR-011
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('00_CONSTITUTION/ADR-011_2026_PRODUCTION_FORTRESS_AND_VEGA_TESTSUITE.md', 'ADR-011 - FORTRESS and VEGA Testsuite', 'ADR', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Hash chain validation and testing requirements', 11, 'PENDING')
ON CONFLICT DO NOTHING;

-- ADR-012
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('00_CONSTITUTION/ADR-012_2026_PRODUCTION_Economic Safety Architecture.md', 'ADR-012 - Economic Safety Architecture', 'ADR', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Cost constraints, API waterfall, execution gates', 12, 'PENDING')
ON CONFLICT DO NOTHING;

-- ADR-013
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('00_CONSTITUTION/ADR-013_2026_PRODUCTION_Canonical ADR Governance and One-True-Source Architecture.md', 'ADR-013 - Canonical Governance and One-True-Source', 'ADR', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Infrastructure sovereignty and canonical truth', 13, 'PENDING')
ON CONFLICT DO NOTHING;

-- ADR-014 (there are two versions, using the newer one)
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('00_CONSTITUTION/ADR-014_2026_PRODUCTION_Executive Activation and Sub-Executive Governance Charter.md', 'ADR-014 - Executive Activation and Sub-Executive Governance', 'ADR', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Agent activation and sub-executive governance', 14, 'PENDING')
ON CONFLICT DO NOTHING;

-- ADR-015
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('00_CONSTITUTION/ADR-015_2026_PRODUCTION_Meta-Governance Framework for ADR Ingestion and Canonical Lifecycle Integrity.md', 'ADR-015 - Meta-Governance Framework', 'ADR', 'STIG', 'CEO', NOW(), 'COMPLETE', 'ADR lifecycle and ingestion governance', 15, 'PENDING')
ON CONFLICT DO NOTHING;

-- ADR-016 (using the newer dated version)
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('00_CONSTITUTION/ADR-016_2026_PRODUCTION_DEFCON_Circuit_Breaker_Protocol.md', 'ADR-016 - DEFCON and Circuit Breaker Protocol', 'ADR', 'STIG', 'CEO', NOW(), 'COMPLETE', 'System safety and circuit breaker mechanisms', 16, 'PENDING')
ON CONFLICT DO NOTHING;

-- ADR-017
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('00_CONSTITUTION/ADR-017_THE MIT QUAD PROTOCOL FOR ALPHA SOVEREIGNTY.md', 'ADR-017 - MIT QUAD Protocol for Alpha Sovereignty', 'ADR', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Alpha signal sovereignty and validation', 17, 'PENDING')
ON CONFLICT DO NOTHING;

-- ADR-018
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('00_CONSTITUTION/ADR-018_AGENT STATE RELIABILITY PROTOCOL (ASRP).md', 'ADR-018 - Agent State Reliability Protocol (ASRP)', 'ADR', 'STIG', 'CEO', NOW(), 'COMPLETE', 'State binding and agent reliability', 18, 'PENDING')
ON CONFLICT DO NOTHING;

-- ADR-019
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('00_CONSTITUTION/ADR-019_Human Interaction & Application Layer Charter.md', 'ADR-019 - Human Interaction and Application Layer Charter', 'ADR', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Human-AI interaction and application layer', 19, 'PENDING')
ON CONFLICT DO NOTHING;

-- ADR-020
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('00_CONSTITUTION/ADR-020_Autonomous Cognitive Intelligence.md', 'ADR-020 - Autonomous Cognitive Intelligence', 'ADR', 'STIG', 'CEO', NOW(), 'COMPLETE', 'ACI Console constitutional framework', 20, 'PENDING')
ON CONFLICT DO NOTHING;

-- ADR-021
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('00_CONSTITUTION/ADR-021_2026_PRODUCTION_Cognitive_Engine_Architecture_Deep_Research_Protocol.md', 'ADR-021 - Cognitive Engine Architecture', 'ADR', 'STIG', 'CEO', NOW(), 'COMPLETE', 'SitC, InForage, IKEA cognitive engines', 21, 'PENDING')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- SECTION 2: IoS DOCUMENTS (02_IOS) - Core Production Documents
-- ============================================================================

-- IoS-001
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('02_IOS/IoS-001_2026_PRODUCTION.md', 'IoS-001 - Foundation Data Layer', 'IOS', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Market data ingestion and price series', 101, 'PENDING')
ON CONFLICT DO NOTHING;

-- IoS-002
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('02_IOS/IoS-002.md', 'IoS-002 - Technical Indicators', 'IOS', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Technical indicator calculations', 102, 'PENDING')
ON CONFLICT DO NOTHING;

-- IoS-003.v4
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('02_IOS/IoS-003.v4_2026_PRODUCTION.md', 'IoS-003.v4 - Regime Perception Engine', 'IOS', 'STIG', 'CEO', NOW(), 'COMPLETE', 'HMM regime classification', 103, 'PENDING')
ON CONFLICT DO NOTHING;

-- IoS-004
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('02_IOS/IoS-004 - Regime-Driven Allocation Engine.md', 'IoS-004 - Regime-Driven Allocation Engine', 'IOS', 'STIG', 'CEO', NOW(), 'COMPLETE', 'CRIO allocation logic', 104, 'PENDING')
ON CONFLICT DO NOTHING;

-- IoS-005
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('02_IOS/IoS-005_Forecast Calibration and Skill Engine.md', 'IoS-005 - Forecast Calibration and Skill Engine', 'IOS', 'STIG', 'CEO', NOW(), 'COMPLETE', 'FSS and forecast skill metrics', 105, 'PENDING')
ON CONFLICT DO NOTHING;

-- IoS-007
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('02_IOS/IoS-007_ALPHA GRAPH ENGINE - CAUSAL REASONING CORE.md', 'IoS-007 - Alpha Graph Engine', 'IOS', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Causal reasoning and alpha signals', 107, 'PENDING')
ON CONFLICT DO NOTHING;

-- IoS-008
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('02_IOS/IoS-008_Runtime Decision Engine.md', 'IoS-008 - Runtime Decision Engine', 'IOS', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Runtime allocation and decision logic', 108, 'PENDING')
ON CONFLICT DO NOTHING;

-- IoS-009
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('02_IOS/IoS-009 - Meta-Perception Layer.md', 'IoS-009 - Meta-Perception Layer', 'IOS', 'STIG', 'CEO', NOW(), 'COMPLETE', 'System perception and confidence', 109, 'PENDING')
ON CONFLICT DO NOTHING;

-- IoS-010
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('02_IOS/IoS-010_PREDICTION LEDGER ENGINE.md', 'IoS-010 - Prediction Ledger Engine', 'IOS', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Prediction tracking and scoring', 110, 'PENDING')
ON CONFLICT DO NOTHING;

-- IoS-011
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('02_IOS/IoS-011_TECHNICAL ANALYSIS PIPELINE.md', 'IoS-011 - Technical Analysis Pipeline', 'IOS', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Technical analysis workflow', 111, 'PENDING')
ON CONFLICT DO NOTHING;

-- IoS-012
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('02_IOS/IoS-012_EXECUTION ENGINE.md', 'IoS-012 - Execution Engine', 'IOS', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Trade execution and paper trading', 112, 'PENDING')
ON CONFLICT DO NOTHING;

-- IoS-013 (multiple components)
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('02_IOS/IoS-013.HCP-LAB.md', 'IoS-013 - HCP Lab', 'IOS', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Hypothesis testing and calibration', 113, 'PENDING')
ON CONFLICT DO NOTHING;

INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('02_IOS/IoS-013_ASPE.md', 'IoS-013 - ASPE Engine', 'IOS', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Automated strategy performance evaluation', 114, 'PENDING')
ON CONFLICT DO NOTHING;

INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('02_IOS/IoS-013_Context Definition Specification (CDS).md', 'IoS-013 - Context Definition Specification', 'IOS', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Context injection layer specification', 115, 'PENDING')
ON CONFLICT DO NOTHING;

INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('02_IOS/IoS-013_Interface Specification - Truth Gateway.md', 'IoS-013 - Truth Gateway Interface', 'IOS', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Truth gateway API specification', 116, 'PENDING')
ON CONFLICT DO NOTHING;

-- IoS-014
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('02_IOS/IoS-014_Autonomous Task Orchestration Engine.md', 'IoS-014 - Autonomous Task Orchestration Engine', 'IOS', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Task scheduling and orchestration', 117, 'PENDING')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- SECTION 3: EC DOCUMENTS (10_EMPLOYMENT CONTRACTS)
-- ============================================================================

-- EC-001 (VEGA)
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('10_EMPLOYMENT CONTRACTS/EC-001_2026_PRODUCTION.md', 'EC-001 - VEGA Employment Contract', 'DIRECTIVE', 'STIG', 'CEO', NOW(), 'COMPLETE', 'VEGA governance authority contract', 201, 'PENDING')
ON CONFLICT DO NOTHING;

-- EC-002 (LARS)
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('10_EMPLOYMENT CONTRACTS/EC-002_2026_PRODUCTION.md', 'EC-002 - LARS Employment Contract', 'DIRECTIVE', 'STIG', 'CEO', NOW(), 'COMPLETE', 'LARS orchestration authority contract', 202, 'PENDING')
ON CONFLICT DO NOTHING;

-- EC-003 (STIG)
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('10_EMPLOYMENT CONTRACTS/EC-003_2026_PRODUCTION.md', 'EC-003 - STIG Employment Contract', 'DIRECTIVE', 'STIG', 'CEO', NOW(), 'COMPLETE', 'STIG technical authority contract', 203, 'PENDING')
ON CONFLICT DO NOTHING;

-- EC-004 (LINE)
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('10_EMPLOYMENT CONTRACTS/EC-004_2026_PRODUCTION.md', 'EC-004 - LINE Employment Contract', 'DIRECTIVE', 'STIG', 'CEO', NOW(), 'COMPLETE', 'LINE operational authority contract', 204, 'PENDING')
ON CONFLICT DO NOTHING;

-- EC-005 (FINN)
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('10_EMPLOYMENT CONTRACTS/EC-005_2026_PRODUCTION.md', 'EC-005 - FINN Employment Contract', 'DIRECTIVE', 'STIG', 'CEO', NOW(), 'COMPLETE', 'FINN research authority contract', 205, 'PENDING')
ON CONFLICT DO NOTHING;

-- EC-006 (CODE)
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('10_EMPLOYMENT CONTRACTS/EC-006_2026_PRODUCTION.md', 'EC-006 - CODE Employment Contract', 'DIRECTIVE', 'STIG', 'CEO', NOW(), 'COMPLETE', 'CODE execution authority contract', 206, 'PENDING')
ON CONFLICT DO NOTHING;

-- EC-007 through EC-013
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('10_EMPLOYMENT CONTRACTS/EC-007_2026_PRODUCTION.md', 'EC-007 - Sub-Executive Contract Template', 'DIRECTIVE', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Sub-executive governance template', 207, 'PENDING')
ON CONFLICT DO NOTHING;

INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('10_EMPLOYMENT CONTRACTS/EC-008_2026_PRODUCTION.md', 'EC-008 - CDMO Employment Contract', 'DIRECTIVE', 'STIG', 'CEO', NOW(), 'COMPLETE', 'CDMO data officer contract', 208, 'PENDING')
ON CONFLICT DO NOTHING;

INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('10_EMPLOYMENT CONTRACTS/EC-009_2026_PRODUCTION.md', 'EC-009 - Employment Contract', 'DIRECTIVE', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Additional agent contract', 209, 'PENDING')
ON CONFLICT DO NOTHING;

INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('10_EMPLOYMENT CONTRACTS/EC-010_2026_PRODUCTION.md', 'EC-010 - Employment Contract', 'DIRECTIVE', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Additional agent contract', 210, 'PENDING')
ON CONFLICT DO NOTHING;

INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('10_EMPLOYMENT CONTRACTS/EC-011_2026_PRODUCTION.md', 'EC-011 - Employment Contract', 'DIRECTIVE', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Additional agent contract', 211, 'PENDING')
ON CONFLICT DO NOTHING;

INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('10_EMPLOYMENT CONTRACTS/EC-012_2026_PRODUCTION.md', 'EC-012 - Employment Contract', 'DIRECTIVE', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Additional agent contract', 212, 'PENDING')
ON CONFLICT DO NOTHING;

INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('10_EMPLOYMENT CONTRACTS/EC-013_2026_PRODUCTION.md', 'EC-013 - Employment Contract', 'DIRECTIVE', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Additional agent contract', 213, 'PENDING')
ON CONFLICT DO NOTHING;

-- EC-020 (SitC)
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('10_EMPLOYMENT CONTRACTS/EC-020_2026_PRODUCTION_SitC_Search_in_the_Chain.md', 'EC-020 - SitC Search in the Chain Protocol', 'DIRECTIVE', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Chain-of-query reasoning protocol', 220, 'PENDING')
ON CONFLICT DO NOTHING;

-- EC-021 (InForage)
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('10_EMPLOYMENT CONTRACTS/EC-021_2026_PRODUCTION_InForage_Information_Foraging.md', 'EC-021 - InForage Information Foraging Protocol', 'DIRECTIVE', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Cost-aware retrieval protocol', 221, 'PENDING')
ON CONFLICT DO NOTHING;

-- EC-022 (IKEA)
INSERT INTO fhq_meta.canonical_document_queue (document_path, document_title, document_type, requested_by, authorized_by, authorization_timestamp, ingestion_status, analytical_purpose, priority_order, reconciliation_status)
VALUES ('10_EMPLOYMENT CONTRACTS/EC-022_2026_PRODUCTION_IKEA_Knowledge_Boundary.md', 'EC-022 - IKEA Knowledge Boundary Protocol', 'DIRECTIVE', 'STIG', 'CEO', NOW(), 'COMPLETE', 'Knowledge boundary and hallucination prevention', 222, 'PENDING')
ON CONFLICT DO NOTHING;

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

\echo ''
\echo '=========================================================================='
\echo 'MIGRATION 135: G1 BATCH DOCUMENT INGESTION - VERIFICATION'
\echo '=========================================================================='

SELECT 'Documents Ingested by Type:' as check_type;
SELECT document_type, COUNT(*) as count
FROM fhq_meta.canonical_document_queue
GROUP BY document_type
ORDER BY document_type;

SELECT 'Reconciliation Status:' as check_type;
SELECT reconciliation_status, COUNT(*) as count
FROM fhq_meta.canonical_document_queue
GROUP BY reconciliation_status
ORDER BY reconciliation_status;

SELECT 'G1 Reconciliation Summary:' as check_type;
SELECT * FROM fhq_meta.v_g1_reconciliation_summary;

\echo ''
\echo '=========================================================================='
\echo 'G1 BATCH DOCUMENT INGESTION - COMPLETE'
\echo ''
\echo 'All authorized documents queued for reconciliation.'
\echo 'Discovery precedes correction.'
\echo '=========================================================================='
