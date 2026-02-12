-- CEO-DIR-2026-GENERATION-FREEZE-ENFORCEMENT-014B
-- Add controlled_exception column to hypothesis_canon
-- Author: STIG (EC-003)
-- Date: 2026-02-12

ALTER TABLE fhq_learning.hypothesis_canon
ADD COLUMN IF NOT EXISTS controlled_exception BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN fhq_learning.hypothesis_canon.controlled_exception IS
    'Flag indicating if hypothesis is a controlled exception during generation freeze (CEO-DIR-2026-014B)';
