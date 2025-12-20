-- ============================================================
-- MIGRATION 064: IoS-013.HCP-LAB G4 Final Activation
-- Constitutional Activation - Production Grade Intelligence
-- Date: 2025-12-02
-- Author: VEGA (Governance Authority)
-- Authority: CEO Directive under ADR-004 G4
-- ============================================================
--
-- G4 SCOPE: Final constitutional activation
-- MODE: PRODUCTION / PAPER TRADING / ALPACA LIVE
-- MISSION: "Funding the Escape Velocity"
-- ============================================================

BEGIN;

-- ============================================================
-- 1. VEGA 2.1: CANONICAL HASH VALIDATION
-- ============================================================
-- Record validated artifact hashes for ADR-002 lineage

CREATE TABLE IF NOT EXISTS fhq_governance.g4_artifact_hashes (
    hash_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ios_id TEXT NOT NULL,
    gate_level TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    sha256_hash TEXT NOT NULL,
    validated_at TIMESTAMPTZ DEFAULT NOW(),
    validated_by TEXT NOT NULL,
    drift_detected BOOLEAN DEFAULT FALSE,
    hash_chain_id TEXT
);

COMMENT ON TABLE fhq_governance.g4_artifact_hashes IS
'ADR-002 compliant artifact hash validation for G4 activations.';

-- Insert validated G3 artifact hashes
INSERT INTO fhq_governance.g4_artifact_hashes
(ios_id, gate_level, artifact_path, sha256_hash, validated_by, hash_chain_id)
VALUES
    ('IoS-013.HCP-LAB', 'G4', '04_DATABASE/MIGRATIONS/063_ios013_hcp_lab_g3_activation.sql',
     'fd1cb7608bc15baf75e101bda11f071f0e15487d73ff56c08e475b15fda05d99', 'VEGA', 'HC-HCP-LAB-G4-HASH-001'),
    ('IoS-013.HCP-LAB', 'G4', '03_FUNCTIONS/ios013_hcp_g3_runner.py',
     '0b6239c4ee44eafa9d7ebbc4e9fcda089819db6da1e7507eccd726c3dcb9e29f', 'VEGA', 'HC-HCP-LAB-G4-HASH-002'),
    ('IoS-013.HCP-LAB', 'G4', '03_FUNCTIONS/ios013_hcp_execution_engine.py',
     '861ddc10d40d85d25d66d1d404931d116cf4c14309574b1f0f17d440a97fde9d', 'VEGA', 'HC-HCP-LAB-G4-HASH-003'),
    ('IoS-013.HCP-LAB', 'G4', '05_GOVERNANCE/PHASE3/IOS013_HCP_LAB_G3_VALIDATION_20251202.json',
     '57de90ca0625e6c5558e4cc763bd62141628d4cb263feb52451ab7cbbe0984b4', 'VEGA', 'HC-HCP-LAB-G4-HASH-004');

-- ============================================================
-- 2. VEGA 2.2: GOVERNANCE REGISTRY UPDATE
-- ============================================================

UPDATE fhq_meta.ios_registry
SET
    version = '2026.LAB.G4',
    status = 'G4_CONSTITUTIONAL',
    governance_state = 'CONSTITUTIONAL_ACTIVE',
    description = 'G4 CONSTITUTIONAL ACTIVE. Production-grade paper trading. Alpaca SDK enabled. DeepSeek pre-mortem active. Full ADR-001 through ADR-016 governance chain binding.',
    updated_at = NOW()
WHERE ios_id = 'IoS-013.HCP-LAB';

-- ============================================================
-- 3. VEGA 2.3: G4 EVENT LOGGING
-- ============================================================

-- Log G4 activation event (using existing ios_audit_log schema)
INSERT INTO fhq_meta.ios_audit_log
(ios_id, event_type, actor, gate_level, event_data, evidence_hash, hash_chain_id)
VALUES (
    'IoS-013.HCP-LAB',
    'G4_FINAL_ACTIVATION',
    'VEGA',
    'G4',
    '{
        "g3_loops_completed": 14,
        "g3_combos_achieved": 5,
        "g3_skill_evals": 5,
        "g3_contamination_events": 0,
        "g3_safety_violations": 0,
        "g3_total_return_pct": 1.15,
        "g4_authorized_by": "CEO",
        "g4_executed_by": "VEGA",
        "activation_scope": "CONSTITUTIONAL_ACTIVE",
        "decision": "APPROVED",
        "evidence_path": "05_GOVERNANCE/PHASE4/IOS013_HCP_LAB_G4_ACTIVATION_20251202.json"
    }'::jsonb,
    'fd1cb7608bc15baf75e101bda11f071f0e15487d73ff56c08e475b15fda05d99',
    'HC-HCP-LAB-G4-ACTIVATION-20251202'
);

-- Also log to governance_actions_log
INSERT INTO fhq_governance.governance_actions_log
(action_id, action_type, action_target, action_target_type,
 initiated_by, initiated_at, decision, decision_rationale,
 vega_reviewed, hash_chain_id)
VALUES (
    gen_random_uuid(),
    'G4_FINAL_ACTIVATION',
    'IoS-013.HCP-LAB',
    'IOS_MODULE',
    'VEGA',
    NOW(),
    'APPROVED',
    'G4 Constitutional Activation by VEGA under CEO directive. All G3 exit criteria verified. Artifact hashes validated. Registry updated to CONSTITUTIONAL_ACTIVE. Ready for production paper trading.',
    true,
    'HC-HCP-LAB-G4-ACTIVATION-20251202'
);

-- ============================================================
-- 4. VEGA 2.4: LINEAGE ANCHORING (ADR-011 Fortress)
-- ============================================================

-- Create fortress anchor table if not exists
CREATE TABLE IF NOT EXISTS fhq_governance.fortress_anchors (
    anchor_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ios_id TEXT NOT NULL,
    gate_level TEXT NOT NULL,
    anchor_type TEXT NOT NULL,
    canonical_hash TEXT NOT NULL,
    anchored_at TIMESTAMPTZ DEFAULT NOW(),
    anchored_by TEXT NOT NULL,
    parent_anchor_id UUID,
    chain_position INTEGER,
    replay_deterministic BOOLEAN DEFAULT TRUE,
    non_repudiation_proof TEXT,
    hash_chain_id TEXT
);

COMMENT ON TABLE fhq_governance.fortress_anchors IS
'ADR-011 Fortress chain anchors for deterministic replay and non-repudiation.';

-- Anchor G4 activation to Fortress chain
INSERT INTO fhq_governance.fortress_anchors
(ios_id, gate_level, anchor_type, canonical_hash, anchored_by, chain_position, non_repudiation_proof, hash_chain_id)
VALUES (
    'IoS-013.HCP-LAB',
    'G4',
    'CONSTITUTIONAL_ACTIVATION',
    'fd1cb7608bc15baf75e101bda11f071f0e15487d73ff56c08e475b15fda05d99',
    'VEGA',
    1,
    'CEO Directive G4 Final Activation issued 2025-12-02. VEGA attestation complete. All ADR-001 through ADR-016 governance bindings active.',
    'HC-HCP-LAB-G4-FORTRESS-20251202'
);

-- ============================================================
-- 5. CODE 3.2: TASK REGISTRY FOR WORKER PIPELINE
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_execution.task_registry (
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_name TEXT UNIQUE NOT NULL,
    gate_level TEXT NOT NULL,
    owned_by TEXT NOT NULL,
    executed_by TEXT NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    schedule_cron TEXT,
    last_run TIMESTAMPTZ,
    next_run TIMESTAMPTZ,
    run_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    config JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE fhq_execution.task_registry IS
'Worker pipeline task registry for autonomous execution.';

-- Register G4 runner task
INSERT INTO fhq_execution.task_registry
(task_name, gate_level, owned_by, executed_by, schedule_cron, config)
VALUES (
    'IOS013_HCP_LAB_G4_RUNNER',
    'G4',
    'LARS',
    'CODE',
    '*/15 9-16 * * 1-5',  -- Every 15 min during market hours, weekdays
    '{
        "ios_id": "IoS-013.HCP-LAB",
        "engine_version": "2026.LAB.G4",
        "execution_mode": "PAPER_TRADING",
        "broker": "ALPACA",
        "target_asset": "BITO",
        "loop_interval_minutes": 15,
        "market_timezone": "America/New_York",
        "adr012_safety_active": true,
        "deepseek_enabled": true,
        "ios005_tracking_enabled": true
    }'::jsonb
)
ON CONFLICT (task_name) DO UPDATE SET
    gate_level = 'G4',
    config = EXCLUDED.config,
    updated_at = NOW();

-- ============================================================
-- 6. CODE 3.1 & 3.3: API CONFIGURATION
-- ============================================================

-- Update HCP engine config for G4
UPDATE fhq_positions.hcp_engine_config
SET config_value = 'G4_ACTIVE', updated_at = NOW()
WHERE config_key = 'execution_mode';

INSERT INTO fhq_positions.hcp_engine_config (config_key, config_value, config_type, description) VALUES
    ('alpaca_enabled', 'true', 'BOOLEAN', 'Alpaca SDK enabled for paper trading'),
    ('alpaca_mode', 'paper', 'STRING', 'Alpaca trading mode (paper/live)'),
    ('deepseek_enabled', 'true', 'BOOLEAN', 'DeepSeek API enabled for pre-mortem'),
    ('deepseek_rate_limit', '100', 'INTEGER', 'DeepSeek calls per hour (ADR-012)'),
    ('deepseek_cost_ceiling', '50.00', 'DECIMAL', 'DeepSeek daily cost ceiling USD'),
    ('engine_version', '2026.LAB.G4', 'STRING', 'Current engine version'),
    ('g4_activated_at', NOW()::TEXT, 'TIMESTAMP', 'G4 activation timestamp'),
    ('g4_activated_by', 'CEO', 'STRING', 'G4 activation authority')
ON CONFLICT (config_key) DO UPDATE SET
    config_value = EXCLUDED.config_value,
    updated_at = NOW();

-- ============================================================
-- 7. UPDATE G3 METRICS FOR G4 TRANSITION
-- ============================================================

UPDATE fhq_positions.hcp_g3_metrics
SET
    updated_by = 'G4_ACTIVATION',
    hash_chain_id = 'HC-HCP-LAB-G4-METRICS-20251202'
WHERE metric_id = (SELECT metric_id FROM fhq_positions.hcp_g3_metrics ORDER BY recorded_at DESC LIMIT 1);

COMMIT;

-- ============================================================
-- VERIFICATION
-- ============================================================
SELECT 'G4 Activation Complete' as status;
SELECT ios_id, version, status, governance_state FROM fhq_meta.ios_registry WHERE ios_id = 'IoS-013.HCP-LAB';
SELECT event_type, ios_id, actor FROM fhq_meta.ios_audit_log WHERE ios_id = 'IoS-013.HCP-LAB' ORDER BY event_timestamp DESC LIMIT 1;
SELECT task_name, gate_level, owned_by, executed_by, enabled FROM fhq_execution.task_registry WHERE task_name = 'IOS013_HCP_LAB_G4_RUNNER';
SELECT config_key, config_value FROM fhq_positions.hcp_engine_config WHERE config_key IN ('execution_mode', 'alpaca_enabled', 'deepseek_enabled', 'engine_version') ORDER BY config_key;
