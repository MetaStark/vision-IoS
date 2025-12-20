-- ============================================================================
-- MIGRATION 108: PHASE 3 Backfill from reward_traces
-- Authority: CEO Directive - PHASE 3 AUTHORIZATION
-- Compliance: ADR-012, ADR-013
-- Executor: STIG (CTO)
-- Date: 2025-12-10
-- ============================================================================
-- Backfill 555 historical LLM calls from reward_traces to llm_routing_log
-- All backfilled entries marked with backfill = TRUE
-- ============================================================================

BEGIN;

-- Temporarily disable triggers for backfill operation
-- This is authorized by CEO Directive PHASE 3 for historical data migration
ALTER TABLE fhq_governance.llm_routing_log DISABLE TRIGGER trg_llm_routing_budget_increment;
ALTER TABLE fhq_governance.llm_routing_log DISABLE TRIGGER trg_llm_routing_cost_ledger;

-- Backfill llm_routing_log from reward_traces
INSERT INTO fhq_governance.llm_routing_log (
    envelope_id,
    agent_id,
    request_timestamp,
    requested_provider,
    requested_tier,
    routed_provider,
    routed_tier,
    policy_satisfied,
    violation_detected,
    task_name,
    task_type,
    model,
    tokens_in,
    tokens_out,
    latency_ms,
    cost_usd,
    timestamp_utc,
    correlation_id,
    stream_mode,
    backfill
)
SELECT
    trace_id as envelope_id,
    CASE
        WHEN agent_id = 'CRIO_RESEARCHER' THEN 'CRIO'
        WHEN agent_id = 'CRIO_NIGHT_WATCH' THEN 'CRIO'
        WHEN agent_id = 'CEIO_SHADOW_RUNNER' THEN 'CEIO'
        WHEN agent_id = 'CEIO_TEST' THEN 'CEIO'
        WHEN agent_id IS NULL THEN 'CRIO'
        ELSE agent_id
    END as agent_id,
    COALESCE(timestamp_utc, created_at) as request_timestamp,
    'DEEPSEEK' as requested_provider,
    2 as requested_tier,
    'DEEPSEEK' as routed_provider,
    2 as routed_tier,
    true as policy_satisfied,
    false as violation_detected,
    COALESCE(LEFT(input_query, 200), 'BACKFILL_RESEARCH') as task_name,
    'RESEARCH' as task_type,
    CASE
        WHEN model_used = 'serper+deepseek' THEN 'deepseek-reasoner'
        WHEN model_used LIKE '%reasoner%' THEN 'deepseek-reasoner'
        ELSE COALESCE(model_used, 'deepseek-reasoner')
    END as model,
    0 as tokens_in,  -- Not captured in reward_traces
    COALESCE(total_tokens, reasoning_tokens, 0) as tokens_out,
    NULL as latency_ms,  -- Not captured
    -- Calculate cost: deepseek-reasoner output at $0.00219/1k tokens
    ROUND(COALESCE(total_tokens, reasoning_tokens, 0) / 1000.0 * 0.00219, 6) as cost_usd,
    COALESCE(timestamp_utc, created_at) as timestamp_utc,
    session_id as correlation_id,
    true as stream_mode,  -- deepseek-reasoner uses streaming
    true as backfill  -- Mark as backfilled
FROM fhq_optimization.reward_traces
WHERE trace_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM fhq_governance.llm_routing_log
    WHERE envelope_id = fhq_optimization.reward_traces.trace_id
  );

-- Re-enable triggers
ALTER TABLE fhq_governance.llm_routing_log ENABLE TRIGGER trg_llm_routing_budget_increment;
ALTER TABLE fhq_governance.llm_routing_log ENABLE TRIGGER trg_llm_routing_cost_ledger;

-- Log backfill count
DO $$
DECLARE
    backfill_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO backfill_count
    FROM fhq_governance.llm_routing_log
    WHERE backfill = true;

    RAISE NOTICE 'PHASE 3 Backfill: % rows inserted from reward_traces', backfill_count;
END $$;

-- Log audit entry
INSERT INTO fhq_meta.adr_audit_log (
    change_proposal_id,
    event_type,
    gate_stage,
    adr_id,
    initiated_by,
    decision,
    resolution_notes,
    sha256_hash
) VALUES (
    'CP-PHASE3-BACKFILL-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS'),
    'G3_AUDIT_VERIFICATION',
    'G3',
    'ADR-012',
    'STIG',
    'EXECUTED',
    'PHASE 3 Backfill: Historical LLM calls migrated from reward_traces to llm_routing_log. All entries marked backfill=TRUE.',
    encode(sha256('PHASE3_BACKFILL_REWARD_TRACES_108'::bytea), 'hex')
);

COMMIT;

-- ============================================================================
-- VERIFY BACKFILL
-- ============================================================================
SELECT
    'BACKFILL_SUMMARY' as report_type,
    COUNT(*) as total_backfilled,
    SUM(tokens_out) as total_tokens,
    SUM(cost_usd) as total_cost_usd,
    COUNT(DISTINCT agent_id) as unique_agents,
    MIN(timestamp_utc) as earliest_call,
    MAX(timestamp_utc) as latest_call
FROM fhq_governance.llm_routing_log
WHERE backfill = true;
