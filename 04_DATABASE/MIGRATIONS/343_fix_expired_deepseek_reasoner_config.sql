-- Migration 343: Fix Expired DeepSeek Reasoner Configuration
-- CEO-DIR-2026-DAY25 System Audit
--
-- ISSUE: 5 deepseek-reasoner configs have expired speciale API endpoint
-- base_url: https://api.deepseek.com/v3.2_speciale_expires_on_20251215
-- speciale_expires: 2025-12-15T15:59:00Z (expired 41 days ago)
--
-- FIX: Update to standard DeepSeek API endpoint

BEGIN;

-- Update expired deepseek-reasoner configs to use standard API
UPDATE fhq_meta.llm_provider_config
SET config_metadata = jsonb_build_object(
    'mode', 'thinking',
    'base_url', 'https://api.deepseek.com/v1',
    'max_tokens', COALESCE((config_metadata->>'max_tokens')::int, 8192),
    'temperature', COALESCE((config_metadata->>'temperature')::numeric, 0.3),
    'context_window', COALESCE((config_metadata->>'context_window')::int, 128000),
    'api_version', '2026-01',
    'requires_parser_wrapper', true
),
updated_at = NOW()
WHERE model_name = 'deepseek-reasoner'
  AND config_metadata->>'speciale_expires' IS NOT NULL;

-- Log via evidence file (change_log schema varies)

COMMIT;

-- Verify the fix
SELECT
    use_case,
    config_metadata->>'base_url' as base_url,
    config_metadata->>'speciale_expires' as speciale_expires,
    updated_at
FROM fhq_meta.llm_provider_config
WHERE model_name = 'deepseek-reasoner'
ORDER BY use_case;
