-- Migration 201: Cognitive Gateway Task Registry Entry
-- CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001 Phase A Step 5
-- Author: STIG (CTO)
-- Date: 2026-01-04
--
-- Purpose: Register FINN_COGNITIVE_GATEWAY task for orchestrator invocation

BEGIN;

-- 1. Insert cognitive gateway task (idempotent - skip if exists)
INSERT INTO fhq_governance.task_registry (
    task_id,
    task_name,
    task_type,
    agent_id,
    task_description,
    task_config,
    enabled,
    status,
    domain,
    assigned_to,
    description,
    created_at,
    updated_at
)
SELECT
    gen_random_uuid(),
    'FINN_COGNITIVE_GATEWAY',
    'VISION_FUNCTION',
    'FINN',
    'Cognitive Engine gateway for FINN alpha signal generation. Single deterministic entrypoint from orchestrator to cognitive engine.',
    jsonb_build_object(
        'function_path', '03_FUNCTIONS/finn_cognitive_gateway.py',
        'timeout_seconds', 30,
        'mode', 'OFF',
        'defcon_max', 'ORANGE',
        'cost_cap_usd', 0.50
    ),
    TRUE,
    'active',
    'COGNITIVE',
    'FINN',
    'FINN Cognitive Gateway - CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001',
    NOW(),
    NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM fhq_governance.task_registry
    WHERE task_name = 'FINN_COGNITIVE_GATEWAY'
);

COMMIT;

-- Verification query
SELECT task_id, task_name, agent_id, enabled, task_config
FROM fhq_governance.task_registry
WHERE task_name = 'FINN_COGNITIVE_GATEWAY';
