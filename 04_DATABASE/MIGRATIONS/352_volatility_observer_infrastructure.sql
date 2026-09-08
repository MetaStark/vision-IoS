-- ============================================================================
-- Migration 352: Volatility Observer Infrastructure
-- ============================================================================
-- Directive:  CEO-DIR-2026-OPS-ALPHA-002A
-- Gate:       G2 (Observational Activation)
-- Author:     STIG (EC-003)
-- Date:       2026-02-01
-- Spec:       IoS-009 Passive Mode / IoS-012-C Extension
-- ============================================================================
-- Adds OBSERVATION status to options_hypothesis_canon.
-- Creates volatility observations, strategy eligibility envelope,
-- theoretical P&L ledger, and zero-leakage audit tables.
--
-- Execution Authority: NONE
-- Capital Authority: ZERO
-- ============================================================================

BEGIN;

-- ============================================================================
-- A. ALTER options_hypothesis_canon: Add OBSERVATION status
-- ============================================================================
-- Drop existing status CHECK and replace with extended version
ALTER TABLE fhq_learning.options_hypothesis_canon
    DROP CONSTRAINT options_hypothesis_canon_status_check;

ALTER TABLE fhq_learning.options_hypothesis_canon
    ADD CONSTRAINT options_hypothesis_canon_status_check
    CHECK (status IN (
        'CANDIDATE', 'EXPERIMENT', 'PROMOTED', 'FALSIFIED', 'ARCHIVED',
        'OBSERVATION'
    ));

-- Add observation-specific columns
ALTER TABLE fhq_learning.options_hypothesis_canon
    ADD COLUMN IF NOT EXISTS observation_type VARCHAR(30),
    ADD COLUMN IF NOT EXISTS iv_at_observation NUMERIC(10,6),
    ADD COLUMN IF NOT EXISTS rv_at_observation NUMERIC(10,6),
    ADD COLUMN IF NOT EXISTS iv_rv_divergence NUMERIC(10,6),
    ADD COLUMN IF NOT EXISTS regime_at_observation VARCHAR(30),
    ADD COLUMN IF NOT EXISTS theoretical_entry_price NUMERIC(12,4),
    ADD COLUMN IF NOT EXISTS envelope_compliant BOOLEAN,
    ADD COLUMN IF NOT EXISTS observation_expired BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS theoretical_pnl NUMERIC(12,4),
    ADD COLUMN IF NOT EXISTS outcome_evaluated_at TIMESTAMPTZ;

COMMENT ON COLUMN fhq_learning.options_hypothesis_canon.observation_type IS
    'CEO-DIR-002A: Type of observation (IV_RV_DIVERGENCE, IV_RANK_EXTREME, SKEW_ANOMALY, TERM_STRUCTURE_INVERSION)';
COMMENT ON COLUMN fhq_learning.options_hypothesis_canon.envelope_compliant IS
    'CEO-DIR-002A: Whether this observation would pass the strategy eligibility envelope (TRUE/FALSE)';
COMMENT ON COLUMN fhq_learning.options_hypothesis_canon.theoretical_pnl IS
    'CEO-DIR-002A: Counterfactual P&L — what would have happened if we had traded';

-- ============================================================================
-- B. fhq_learning: Volatility Observations (Detail Log)
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhq_learning.volatility_observations (
    observation_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis_id       UUID REFERENCES fhq_learning.options_hypothesis_canon(hypothesis_id),
    underlying          VARCHAR(20) NOT NULL,
    observation_type    VARCHAR(30) NOT NULL CHECK (observation_type IN (
                            'IV_RV_DIVERGENCE', 'IV_RANK_EXTREME', 'SKEW_ANOMALY',
                            'TERM_STRUCTURE_INVERSION', 'VOLATILITY_CRUSH',
                            'VOLATILITY_EXPANSION', 'PUT_CALL_SKEW'
                        )),
    -- IV data
    implied_volatility  NUMERIC(10,6) NOT NULL,
    realized_volatility NUMERIC(10,6) NOT NULL,
    iv_rv_spread        NUMERIC(10,6) NOT NULL,   -- IV - RV (positive = IV premium)
    iv_rank             NUMERIC(6,4),
    iv_percentile       NUMERIC(6,4),
    -- Market context
    underlying_price    NUMERIC(12,4) NOT NULL,
    regime              VARCHAR(30),
    regime_confidence   NUMERIC(6,4),
    vix_level           NUMERIC(8,4),
    -- Signal metadata
    signal_strength     NUMERIC(6,4),             -- 0.0 to 1.0
    signal_direction    VARCHAR(10) CHECK (signal_direction IN (
                            'SELL_VOL', 'BUY_VOL', 'NEUTRAL'
                        )),
    -- Strategy suggestion (what the system WOULD do, never executed)
    suggested_strategy  VARCHAR(30),
    suggested_strikes   JSONB,
    suggested_dte       INTEGER,
    -- Lineage
    source              VARCHAR(30) NOT NULL DEFAULT 'IoS-009_OBSERVER',
    content_hash        VARCHAR(64),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vo_underlying ON fhq_learning.volatility_observations (underlying);
CREATE INDEX IF NOT EXISTS idx_vo_type ON fhq_learning.volatility_observations (observation_type);
CREATE INDEX IF NOT EXISTS idx_vo_created ON fhq_learning.volatility_observations (created_at);
CREATE INDEX IF NOT EXISTS idx_vo_hypothesis ON fhq_learning.volatility_observations (hypothesis_id);

COMMENT ON TABLE fhq_learning.volatility_observations IS
    'CEO-DIR-002A / IoS-009: Passive volatility observations. ZERO execution authority. Data capture only.';

-- ============================================================================
-- C. fhq_learning: Strategy Eligibility Envelope (Shadow Metadata)
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhq_learning.strategy_eligibility_envelope (
    envelope_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis_id       UUID REFERENCES fhq_learning.options_hypothesis_canon(hypothesis_id),
    observation_id      UUID REFERENCES fhq_learning.volatility_observations(observation_id),
    -- Envelope criteria
    strategy_type       VARCHAR(30) NOT NULL,
    max_loss_acceptable NUMERIC(12,2),
    max_dte             INTEGER,
    min_iv_rank         NUMERIC(6,4),
    max_iv_rank         NUMERIC(6,4),
    required_regime     JSONB,                    -- ["RECOVERY", "EXPANSION"]
    min_signal_strength NUMERIC(6,4),
    -- Evaluation results
    envelope_compliant  BOOLEAN NOT NULL,
    violation_reasons   JSONB,                    -- ["REGIME_MISMATCH", "IV_RANK_LOW", ...]
    -- Metadata
    evaluated_by        VARCHAR(30) NOT NULL DEFAULT 'VOLATILITY_OBSERVER',
    content_hash        VARCHAR(64),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_see_compliant ON fhq_learning.strategy_eligibility_envelope (envelope_compliant);
CREATE INDEX IF NOT EXISTS idx_see_hypothesis ON fhq_learning.strategy_eligibility_envelope (hypothesis_id);

COMMENT ON TABLE fhq_learning.strategy_eligibility_envelope IS
    'CEO-DIR-002A: LINE role modelled but not activated. Logs theoretical compliance. No approval authority.';

-- ============================================================================
-- D. fhq_learning: Theoretical P&L Ledger (Counterfactual)
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhq_learning.theoretical_pnl_ledger (
    ledger_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis_id       UUID REFERENCES fhq_learning.options_hypothesis_canon(hypothesis_id),
    observation_id      UUID REFERENCES fhq_learning.volatility_observations(observation_id),
    underlying          VARCHAR(20) NOT NULL,
    strategy_type       VARCHAR(30) NOT NULL,
    -- Entry snapshot (what WOULD have been the entry)
    entry_price         NUMERIC(12,4),
    entry_iv            NUMERIC(10,6),
    entry_rv            NUMERIC(10,6),
    entry_underlying    NUMERIC(12,4),
    entry_regime        VARCHAR(30),
    entry_timestamp     TIMESTAMPTZ NOT NULL,
    -- Exit snapshot (at observation expiry or evaluation)
    exit_price          NUMERIC(12,4),
    exit_iv             NUMERIC(10,6),
    exit_underlying     NUMERIC(12,4),
    exit_regime         VARCHAR(30),
    exit_timestamp      TIMESTAMPTZ,
    exit_reason         VARCHAR(30),              -- 'DTE_THRESHOLD', 'TARGET_HIT', 'STOP_HIT', 'EXPIRED'
    -- Theoretical P&L decomposition
    theoretical_pnl     NUMERIC(12,4),
    theta_pnl           NUMERIC(12,4),
    delta_pnl           NUMERIC(12,4),
    vega_pnl            NUMERIC(12,4),
    gamma_pnl           NUMERIC(12,4),
    -- Classification
    outcome             VARCHAR(10) CHECK (outcome IN ('WIN', 'LOSS', 'SCRATCH', 'PENDING')),
    -- Lineage
    content_hash        VARCHAR(64),
    chain_hash          VARCHAR(64),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    evaluated_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tpl_hypothesis ON fhq_learning.theoretical_pnl_ledger (hypothesis_id);
CREATE INDEX IF NOT EXISTS idx_tpl_outcome ON fhq_learning.theoretical_pnl_ledger (outcome);
CREATE INDEX IF NOT EXISTS idx_tpl_underlying ON fhq_learning.theoretical_pnl_ledger (underlying);

COMMENT ON TABLE fhq_learning.theoretical_pnl_ledger IS
    'CEO-DIR-002A: Counterfactual P&L. What WOULD have happened. No real capital. No real orders.';

-- ============================================================================
-- E. fhq_monitoring: Options Leakage Audit
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhq_monitoring.options_leakage_audit (
    audit_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_period_start  TIMESTAMPTZ NOT NULL,
    audit_period_end    TIMESTAMPTZ NOT NULL,
    -- Counters (all must be zero for compliance)
    alpaca_order_calls  INTEGER NOT NULL DEFAULT 0,
    shadow_adapter_calls INTEGER NOT NULL DEFAULT 0,
    execution_gateway_options_calls INTEGER NOT NULL DEFAULT 0,
    broker_api_calls    INTEGER NOT NULL DEFAULT 0,
    -- Verdict
    zero_leakage        BOOLEAN NOT NULL,
    violation_details   JSONB,                    -- null if clean
    -- Lineage
    audited_by          VARCHAR(30) NOT NULL DEFAULT 'VOLATILITY_OBSERVER',
    content_hash        VARCHAR(64),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ola_leakage ON fhq_monitoring.options_leakage_audit (zero_leakage);

COMMENT ON TABLE fhq_monitoring.options_leakage_audit IS
    'CEO-DIR-002A: Zero-leakage proof. Verifies NO order calls sent to Alpaca. Court-proof audit.';

-- ============================================================================
-- F. fhq_learning: Falsification tracking view
-- ============================================================================
CREATE OR REPLACE VIEW fhq_learning.v_options_observation_summary AS
SELECT
    ohc.underlying,
    ohc.strategy_type,
    ohc.observation_type,
    ohc.regime_at_observation,
    COUNT(*) as total_observations,
    COUNT(*) FILTER (WHERE tpl.outcome = 'WIN') as wins,
    COUNT(*) FILTER (WHERE tpl.outcome = 'LOSS') as losses,
    COUNT(*) FILTER (WHERE tpl.outcome = 'SCRATCH') as scratches,
    COUNT(*) FILTER (WHERE tpl.outcome = 'PENDING') as pending,
    ROUND(AVG(tpl.theoretical_pnl)::NUMERIC, 4) as avg_theoretical_pnl,
    ROUND(AVG(ohc.iv_rv_divergence)::NUMERIC, 6) as avg_iv_rv_divergence,
    COUNT(*) FILTER (WHERE ohc.envelope_compliant = TRUE) as envelope_compliant_count,
    COUNT(*) FILTER (WHERE ohc.envelope_compliant = FALSE) as envelope_non_compliant_count
FROM fhq_learning.options_hypothesis_canon ohc
LEFT JOIN fhq_learning.theoretical_pnl_ledger tpl
    ON tpl.hypothesis_id = ohc.hypothesis_id
WHERE ohc.status = 'OBSERVATION'
GROUP BY ohc.underlying, ohc.strategy_type, ohc.observation_type, ohc.regime_at_observation;

COMMENT ON VIEW fhq_learning.v_options_observation_summary IS
    'CEO-DIR-002A: Aggregated observation statistics for the evidence bundle. Includes falsification rates per regime.';

-- ============================================================================
-- Migration metadata
-- ============================================================================
INSERT INTO fhq_monitoring.run_ledger (
    task_name, started_at, finished_at, exit_code, error_excerpt
) VALUES (
    'MIGRATION_352_VOLATILITY_OBSERVER_INFRASTRUCTURE',
    NOW(), NOW(), 0,
    'CEO-DIR-002A G2: ALTER hypothesis_canon + 4 new tables + 1 view. Observational only.'
);

COMMIT;
