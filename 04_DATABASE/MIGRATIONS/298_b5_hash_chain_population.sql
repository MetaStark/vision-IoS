-- Migration 298: B5 Hash Chain Population
-- Authority: CEO-DIR-2026-064
-- Gate: ADR-004 APPROVED
-- Executed by: STIG
-- Date: 2026-01-17
-- Note: Adapted to work with existing hash_chains schema

BEGIN;

-- C5.3.1: Hash Chain Update Function (works with existing schema)
CREATE OR REPLACE FUNCTION vision_verification.fn_update_hash_chain(
    p_chain_id TEXT,
    p_operation_type TEXT,
    p_operation_data JSONB,
    p_agent_id TEXT
) RETURNS TEXT AS $$
DECLARE
    v_current_hash TEXT;
    v_new_hash TEXT;
    v_data_to_hash TEXT;
    v_chain_length INTEGER;
BEGIN
    -- Get current chain state
    SELECT current_hash, chain_length INTO v_current_hash, v_chain_length
    FROM vision_verification.hash_chains
    WHERE chain_id = p_chain_id;

    -- If chain doesn't exist, create it
    IF v_current_hash IS NULL THEN
        v_current_hash := 'GENESIS_' || p_chain_id || '_' || NOW()::TEXT;
        v_chain_length := 0;
    END IF;

    -- Compute new hash
    v_data_to_hash := v_current_hash || '|' || p_operation_type || '|' || p_operation_data::TEXT || '|' || NOW()::TEXT;
    v_new_hash := encode(sha256(v_data_to_hash::bytea), 'hex');

    -- Update or insert chain record
    INSERT INTO vision_verification.hash_chains (
        chain_id,
        chain_type,
        chain_scope,
        genesis_hash,
        current_hash,
        chain_length,
        integrity_verified,
        created_by,
        created_at,
        updated_at
    ) VALUES (
        p_chain_id,
        p_operation_type,
        'CEO-DIR-2026-064',
        v_current_hash,
        v_new_hash,
        v_chain_length + 1,
        TRUE,
        p_agent_id,
        NOW(),
        NOW()
    )
    ON CONFLICT (chain_id) DO UPDATE SET
        current_hash = v_new_hash,
        chain_length = vision_verification.hash_chains.chain_length + 1,
        updated_at = NOW();

    RETURN v_new_hash;
END;
$$ LANGUAGE plpgsql;

-- C5.3.2: Hash Chain Verification Function
CREATE OR REPLACE FUNCTION vision_verification.fn_verify_hash_chain(
    p_chain_id TEXT DEFAULT NULL
) RETURNS TABLE (
    chain_id TEXT,
    is_valid BOOLEAN,
    chain_length INTEGER,
    last_verified TIMESTAMPTZ,
    error_message TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        hc.chain_id,
        hc.integrity_verified AS is_valid,
        hc.chain_length,
        hc.last_verification_at AS last_verified,
        CASE
            WHEN NOT hc.integrity_verified THEN 'Chain integrity compromised'
            WHEN hc.current_hash IS NULL THEN 'Chain has no current hash'
            ELSE NULL
        END AS error_message
    FROM vision_verification.hash_chains hc
    WHERE p_chain_id IS NULL OR hc.chain_id = p_chain_id
    ORDER BY hc.created_at;
END;
$$ LANGUAGE plpgsql STABLE;

-- C5.3.3: Bootstrap genesis chain for CEO-DIR-2026-064
INSERT INTO vision_verification.hash_chains (
    chain_id,
    chain_type,
    chain_scope,
    genesis_hash,
    current_hash,
    chain_length,
    integrity_verified,
    created_by,
    created_at,
    updated_at
) VALUES (
    'CEO-DIR-2026-064-B1B5',
    'DIRECTIVE_EXECUTION',
    'CEO-DIR-2026-064',
    encode(sha256(('GENESIS_CEO_DIR_2026_064_' || NOW()::TEXT)::bytea), 'hex'),
    encode(sha256(('GENESIS_CEO_DIR_2026_064_CURRENT_' || NOW()::TEXT)::bytea), 'hex'),
    1,
    TRUE,
    'STIG',
    NOW(),
    NOW()
)
ON CONFLICT (chain_id) DO NOTHING;

-- Log migration to governance_actions_log
INSERT INTO fhq_governance.governance_actions_log (
    action_type, action_target, action_target_type, initiated_by, initiated_at, decision, decision_rationale, metadata, agent_id
) VALUES (
    'MIGRATION', '298_b5_hash_chain', 'DATABASE_SCHEMA', 'STIG', NOW(), 'EXECUTED',
    'CEO-DIR-2026-064 B5 - Hash Chain Population',
    '{"directive": "CEO-DIR-2026-064", "gap": "B5", "functions_created": ["fn_update_hash_chain", "fn_verify_hash_chain"], "genesis_chain": "CEO-DIR-2026-064-B1B5"}'::jsonb,
    'STIG'
);

COMMIT;
