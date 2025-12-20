-- ============================================================
-- CEO GO: REGISTER VISION-IOS PRODUCTION FUNCTIONS
-- Authority: CEO Approval
-- Executed by: STIG (CTO)
-- Migration: 046_ceo_go_function_registration.sql
-- ============================================================

BEGIN;

-- Clear test task
DELETE FROM fhq_governance.task_registry WHERE task_name = 'vision_hello_world';

-- Register all 16 production functions
INSERT INTO fhq_governance.task_registry (
    task_id, task_name, task_type, task_scope,
    owned_by_agent, executed_by_agent,
    reads_from_schemas, writes_to_schemas,
    gate_level, gate_approved, gate_approved_by, gate_approved_at,
    vega_reviewed, vega_approved, vega_reviewer, vega_review_date,
    description, parameters_schema, task_status, created_by, hash_chain_id
) VALUES
-- IoS-002: Data Foundation (3 functions)
(gen_random_uuid(), 'pipeline_ingest_history_v1', 'VISION_FUNCTION', 'IoS-002',
 'LINE', 'LINE', ARRAY['fhq_meta'], ARRAY['fhq_data'],
 'G2', true, 'CEO', NOW(), true, true, 'VEGA', NOW(),
 'Genesis historical OHLCV ingestion - Operation Data First',
 '{"tickers": "array", "start_date": "date"}'::jsonb,
 'ACTIVE', 'CEO', encode(sha256('pipeline_ingest_history_v1'::bytea), 'hex')),

(gen_random_uuid(), 'daily_ingest_worker', 'VISION_FUNCTION', 'IoS-002',
 'LINE', 'LINE', ARRAY['fhq_meta', 'fhq_data'], ARRAY['fhq_data'],
 'G2', true, 'CEO', NOW(), true, true, 'VEGA', NOW(),
 'Daily automated OHLCV data pipeline worker',
 '{"mode": "string", "batch_size": "integer"}'::jsonb,
 'ACTIVE', 'CEO', encode(sha256('daily_ingest_worker'::bytea), 'hex')),

(gen_random_uuid(), 'calc_indicators_v1', 'VISION_FUNCTION', 'IoS-002',
 'FINN', 'CODE', ARRAY['fhq_data'], ARRAY['fhq_research'],
 'G2', true, 'CEO', NOW(), true, true, 'VEGA', NOW(),
 'Technical indicator calculation engine',
 '{"tickers": "array", "indicators": "array"}'::jsonb,
 'ACTIVE', 'CEO', encode(sha256('calc_indicators_v1'::bytea), 'hex')),

-- IoS-003: Regime Modeling (1 function)
(gen_random_uuid(), 'hmm_backfill_v1', 'VISION_FUNCTION', 'IoS-003',
 'LARS', 'FINN', ARRAY['fhq_data', 'fhq_research'], ARRAY['fhq_research'],
 'G3', true, 'CEO', NOW(), true, true, 'VEGA', NOW(),
 'HMM regime model backfill - Appendix A',
 '{"model_id": "string", "lookback_days": "integer"}'::jsonb,
 'ACTIVE', 'CEO', encode(sha256('hmm_backfill_v1'::bytea), 'hex')),

-- IoS-005: Forecast Calibration (4 functions)
(gen_random_uuid(), 'ios005_scientific_audit_v1', 'VISION_FUNCTION', 'IoS-005',
 'VEGA', 'VEGA', ARRAY['fhq_research', 'fhq_macro'], ARRAY['fhq_governance'],
 'G1', true, 'CEO', NOW(), true, true, 'VEGA', NOW(),
 'G1 Scientific audit activation',
 '{"audit_scope": "string"}'::jsonb,
 'ACTIVE', 'CEO', encode(sha256('ios005_scientific_audit_v1'::bytea), 'hex')),

(gen_random_uuid(), 'ios005_g3_significance_engine', 'VISION_FUNCTION', 'IoS-005',
 'STIG', 'STIG', ARRAY['fhq_macro', 'fhq_research'], ARRAY['fhq_macro'],
 'G3', true, 'CEO', NOW(), true, true, 'VEGA', NOW(),
 'G3 Constitutional significance testing for macro features',
 '{"feature_set": "array", "threshold": "number"}'::jsonb,
 'ACTIVE', 'CEO', encode(sha256('ios005_g3_significance_engine'::bytea), 'hex')),

(gen_random_uuid(), 'ios005_g3_synthesis', 'VISION_FUNCTION', 'IoS-005',
 'STIG', 'STIG', ARRAY['fhq_macro'], ARRAY['fhq_governance'],
 'G3', true, 'CEO', NOW(), true, true, 'VEGA', NOW(),
 'G3 Macro synthesis report generator',
 '{"report_type": "string"}'::jsonb,
 'ACTIVE', 'CEO', encode(sha256('ios005_g3_synthesis'::bytea), 'hex')),

(gen_random_uuid(), 'ios005_replay_macro_audit', 'VISION_FUNCTION', 'IoS-005',
 'VEGA', 'VEGA', ARRAY['fhq_macro', 'fhq_governance'], ARRAY['fhq_governance'],
 'G4', true, 'CEO', NOW(), true, true, 'VEGA', NOW(),
 'Deterministic cold-start replay audit',
 '{"replay_date": "date"}'::jsonb,
 'ACTIVE', 'CEO', encode(sha256('ios005_replay_macro_audit'::bytea), 'hex')),

-- IoS-006: Macro Factor Integration (6 functions)
(gen_random_uuid(), 'ios006_g2_macro_ingest', 'VISION_FUNCTION', 'IoS-006',
 'STIG', 'STIG', ARRAY['fhq_meta'], ARRAY['fhq_macro'],
 'G2', true, 'CEO', NOW(), true, true, 'VEGA', NOW(),
 'G2 Macro data ingest and canonicalization',
 '{"providers": "array", "series": "array"}'::jsonb,
 'ACTIVE', 'CEO', encode(sha256('ios006_g2_macro_ingest'::bytea), 'hex')),

(gen_random_uuid(), 'ios006_multi_provider_router', 'VISION_FUNCTION', 'IoS-006',
 'STIG', 'STIG', ARRAY['fhq_governance', 'fhq_macro'], ARRAY['fhq_macro'],
 'G2', true, 'CEO', NOW(), true, true, 'VEGA', NOW(),
 'G2.5 Multi-provider canonical routing',
 '{"priority": "string"}'::jsonb,
 'ACTIVE', 'CEO', encode(sha256('ios006_multi_provider_router'::bytea), 'hex')),

(gen_random_uuid(), 'ios006_g2_6_vendor_activation', 'VISION_FUNCTION', 'IoS-006',
 'STIG', 'STIG', ARRAY['fhq_governance'], ARRAY['fhq_governance', 'fhq_macro'],
 'G2', true, 'CEO', NOW(), true, true, 'VEGA', NOW(),
 'G2.6 Vendor key activation and bootstrap',
 '{"vendor": "string"}'::jsonb,
 'ACTIVE', 'CEO', encode(sha256('ios006_g2_6_vendor_activation'::bytea), 'hex')),

(gen_random_uuid(), 'ios006_g2_6_key_deployment', 'VISION_FUNCTION', 'IoS-006',
 'STIG', 'STIG', ARRAY['fhq_meta'], ARRAY['fhq_meta'],
 'G2', true, 'CEO', NOW(), true, true, 'VEGA', NOW(),
 'G2.6 Agent cryptographic key deployment',
 '{"agent_id": "string"}'::jsonb,
 'ACTIVE', 'CEO', encode(sha256('ios006_g2_6_key_deployment'::bytea), 'hex')),

(gen_random_uuid(), 'ios006_g2_7_full_bootstrap', 'VISION_FUNCTION', 'IoS-006',
 'STIG', 'STIG', ARRAY['fhq_governance', 'fhq_macro'], ARRAY['fhq_macro'],
 'G2', true, 'CEO', NOW(), true, true, 'VEGA', NOW(),
 'G2.7 Full provider bootstrap with retry',
 '{"force_retry": "boolean"}'::jsonb,
 'ACTIVE', 'CEO', encode(sha256('ios006_g2_7_full_bootstrap'::bytea), 'hex')),

(gen_random_uuid(), 'ios006_lineage_verify', 'VISION_FUNCTION', 'IoS-006',
 'LINE', 'LINE', ARRAY['fhq_data', 'fhq_macro'], ARRAY['fhq_governance'],
 'G3', true, 'CEO', NOW(), true, true, 'VEGA', NOW(),
 'Data lineage verification per ADR-011',
 '{"scope": "string"}'::jsonb,
 'ACTIVE', 'CEO', encode(sha256('ios006_lineage_verify'::bytea), 'hex')),

-- IoS-007: Alpha Graph Execution (2 functions)
(gen_random_uuid(), 'ios007_input_contract', 'VISION_FUNCTION', 'IoS-007',
 'VEGA', 'VEGA', ARRAY['fhq_meta'], ARRAY['fhq_governance'],
 'G1', true, 'CEO', NOW(), true, true, 'VEGA', NOW(),
 'Input contract validation per ADR-014',
 '{"contract_id": "string"}'::jsonb,
 'ACTIVE', 'CEO', encode(sha256('ios007_input_contract'::bytea), 'hex')),

(gen_random_uuid(), 'ios007_g1_global_execution', 'VISION_FUNCTION', 'IoS-007',
 'STIG', 'LARS', ARRAY['fhq_research', 'fhq_macro', 'fhq_data'], ARRAY['vision_signals'],
 'G1', true, 'CEO', NOW(), true, true, 'VEGA', NOW(),
 'G1 Global alpha graph execution',
 '{"execution_mode": "string"}'::jsonb,
 'ACTIVE', 'CEO', encode(sha256('ios007_g1_global_execution'::bytea), 'hex'));

COMMIT;

-- Verification query
SELECT task_name, owned_by_agent, task_scope, task_status
FROM fhq_governance.task_registry
WHERE task_type = 'VISION_FUNCTION' AND task_status = 'ACTIVE'
ORDER BY task_scope, task_name;
