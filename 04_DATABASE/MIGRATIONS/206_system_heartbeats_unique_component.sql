-- Migration 206: Add unique constraint on system_heartbeats.component_name
-- CEO-DIR-2026-SITC-DATA-BLACKOUT-FIX-001 P2
-- Author: STIG (CTO)
-- Date: 2026-01-06
--
-- Required for ON CONFLICT upsert pattern in price_freshness_heartbeat.py

-- Drop existing non-unique index
DROP INDEX IF EXISTS fhq_governance.idx_heartbeats_component;

-- Add unique constraint
ALTER TABLE fhq_governance.system_heartbeats
    ADD CONSTRAINT uq_heartbeats_component_name UNIQUE (component_name);

-- Verify
SELECT 'Migration 206 complete: system_heartbeats.component_name is now unique' as status;
