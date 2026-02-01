-- Migration 353: Micro-Regime Infrastructure
-- Directive: CEO-DIR-2026-OPS-MICROREGIME-003
-- Author: STIG (EC-003)
-- Date: 2026-02-01
-- Classification: OBSERVATIONAL METADATA ONLY — no execution table changes
--
-- This migration adds micro-regime classification infrastructure.
-- Hard constraints:
--   - NO changes to fhq_execution tables
--   - NO changes to options_shadow_orders, options_shadow_positions
--   - NO changes to options_killswitch_events
--   - Micro-regime is metadata for learning/observation only

BEGIN;

-- 1. Micro-regime classification log
-- Records each classification run with full state snapshot
CREATE TABLE IF NOT EXISTS fhq_learning.micro_regime_classifications (
    classification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    macro_regime TEXT NOT NULL DEFAULT 'CRISIS',
    micro_regime TEXT NOT NULL CHECK (micro_regime IN ('MR_ACUTE', 'MR_SYSTEMIC', 'MR_SELECTIVE', 'MR_EXHAUSTION')),
    avg_stress_prob NUMERIC(8,6) NOT NULL,
    pct_stress_assets NUMERIC(5,4) NOT NULL,
    pct_high_stress_assets NUMERIC(5,4) NOT NULL,
    total_assets_evaluated INTEGER NOT NULL,
    assets_in_stress INTEGER NOT NULL,
    assets_in_bear INTEGER NOT NULL,
    assets_in_neutral INTEGER NOT NULL,
    assets_in_bull INTEGER NOT NULL,
    is_policy_divergent BOOLEAN NOT NULL DEFAULT false,
    transition_state TEXT,
    belief_regime TEXT,
    belief_confidence NUMERIC(8,6),
    previous_micro_regime TEXT,
    regime_delta_intensity NUMERIC(8,6),
    momentum_vector TEXT CHECK (momentum_vector IN ('IMPROVING', 'DETERIORATING', 'STABLE')),
    classified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    classified_by TEXT NOT NULL DEFAULT 'micro_regime_classifier',
    evidence_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_micro_regime_classifications_at
    ON fhq_learning.micro_regime_classifications (classified_at DESC);

CREATE INDEX IF NOT EXISTS idx_micro_regime_classifications_regime
    ON fhq_learning.micro_regime_classifications (micro_regime, classified_at DESC);

-- 2. Add micro_regime column to options_hypothesis_canon (observation metadata only)
-- This column captures what micro-regime was active when an observation was created
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_learning'
        AND table_name = 'options_hypothesis_canon'
        AND column_name = 'micro_regime_at_observation'
    ) THEN
        ALTER TABLE fhq_learning.options_hypothesis_canon
            ADD COLUMN micro_regime_at_observation TEXT;
    END IF;
END $$;

-- 3. Add micro_regime column to volatility_observations (observation metadata only)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_learning'
        AND table_name = 'volatility_observations'
        AND column_name = 'micro_regime_at_observation'
    ) THEN
        ALTER TABLE fhq_learning.volatility_observations
            ADD COLUMN micro_regime_at_observation TEXT;
    END IF;
END $$;

-- 4. View: latest micro-regime classification with trend
CREATE OR REPLACE VIEW fhq_learning.v_micro_regime_current AS
SELECT
    mc.classification_id,
    mc.macro_regime,
    mc.micro_regime,
    mc.avg_stress_prob,
    mc.pct_stress_assets,
    mc.pct_high_stress_assets,
    mc.total_assets_evaluated,
    mc.assets_in_stress,
    mc.assets_in_bear,
    mc.is_policy_divergent,
    mc.transition_state,
    mc.belief_regime,
    mc.previous_micro_regime,
    mc.regime_delta_intensity,
    mc.momentum_vector,
    mc.classified_at,
    CASE
        WHEN mc.previous_micro_regime IS NULL THEN 'INITIAL'
        WHEN mc.previous_micro_regime = mc.micro_regime THEN 'STABLE'
        WHEN mc.micro_regime = 'MR_EXHAUSTION' THEN 'IMPROVING'
        WHEN mc.micro_regime = 'MR_ACUTE' THEN 'DETERIORATING'
        WHEN mc.previous_micro_regime = 'MR_ACUTE' AND mc.micro_regime != 'MR_ACUTE' THEN 'IMPROVING'
        WHEN mc.previous_micro_regime = 'MR_EXHAUSTION' AND mc.micro_regime != 'MR_EXHAUSTION' THEN 'DETERIORATING'
        ELSE 'TRANSITIONING'
    END AS trend
FROM fhq_learning.micro_regime_classifications mc
WHERE mc.classified_at = (
    SELECT MAX(classified_at) FROM fhq_learning.micro_regime_classifications
);

COMMIT;
