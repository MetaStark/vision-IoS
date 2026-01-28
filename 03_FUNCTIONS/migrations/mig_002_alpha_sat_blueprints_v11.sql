-- Migration 002: Insert Alpha Satellite Test Blueprints V1.1
-- CEO Directive: Phase 2 Preparation & Hypothesis Swarm V1.1
-- Date: 2026-01-28
-- Author: STIG
-- Status: DESIGN ONLY - No prod deployment until Gate 2 signed

-- =============================================================================
-- ALPHA SATELLITE TEST BLUEPRINTS V1.1
-- Three hypothesis blueprints with ATR-normalized falsification criteria
-- =============================================================================

-- -----------------------------------------------------------------------------
-- GENERATOR REGISTRATION (Required by FK constraint)
-- -----------------------------------------------------------------------------
INSERT INTO fhq_learning.generator_registry (
    generator_id,
    generator_name,
    generator_type,
    description,
    owner_ec,
    status,
    constraints,
    target_causal_depth,
    created_by
) VALUES (
    'STIG-ALPHA-SAT',
    'STIG Alpha Satellite',
    'WORLD_MODEL',
    'Phase 2 Hypothesis Swarm V1.1 - Alpha Satellite test blueprints for volatility squeeze, regime alignment, and mean reversion hypotheses',
    'EC-003',
    'ACTIVE',
    '{"max_hypotheses_per_day": 10, "requires_atr_normalization": true}'::jsonb,
    2,
    'STIG'
) ON CONFLICT (generator_id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- TEST A: VOLATILITY SQUEEZE (Physics Test) V1.1
-- Hypothesis: Volatility compression contains latent energy
-- -----------------------------------------------------------------------------
INSERT INTO fhq_learning.hypothesis_canon (
    hypothesis_code,
    origin_type,
    origin_rationale,
    economic_rationale,
    causal_mechanism,
    counterfactual_scenario,
    expected_direction,
    expected_magnitude,
    expected_timeframe_hours,
    regime_validity,
    regime_conditional_confidence,
    falsification_criteria,
    initial_confidence,
    current_confidence,
    status,
    created_by,
    created_at,
    generator_id
) VALUES (
    'ALPHA_SAT_A_VOL_SQUEEZE_V1.1',
    'ECONOMIC_THEORY',
    'Volatility compression contains latent energy - market physics hypothesis',
    'Low volatility regimes precede high volatility events (volatility clustering)',
    'BBW < 10th percentile indicates compression. Energy release follows.',
    'If squeeze does NOT predict breakout, volatility is random walk.',
    'NEUTRAL',
    'SIGNIFICANT',
    48,
    ARRAY['NEUTRAL', 'LOW_VOL'],
    '{"NEUTRAL": 0.7, "LOW_VOL": 0.8}'::jsonb,
    '{
      "direction_falsified_if": "win_rate_direction < 0.52",
      "magnitude_falsified_if": "magnitude_hit_rate < 0.30",
      "magnitude_threshold_atr_multiple": 2.0,
      "min_sample_size": 30,
      "regime_model_version_required": "sovereign_v4_ddatp_1.2",
      "vol_model_version_required": "ios017_kc_bb_1.0",
      "measurement_schema": {
        "test_code": "ALPHA_SAT_A",
        "version": "1.1",
        "trigger": {
          "indicator": "BBW",
          "condition": "< 10th_percentile",
          "source_table": "fhq_indicators.volatility",
          "capture_fields": ["bbw", "bbw_percentile", "atr_14", "entry_price"]
        },
        "measurements": [
          {"name": "direction_correct", "type": "BOOLEAN", "description": "Did price move in predicted direction?"},
          {"name": "magnitude_significant", "type": "BOOLEAN", "description": "Was movement > 2x ATR?", "threshold_atr_multiple": 2.0}
        ],
        "atr_logging": {
          "field": "atr_14",
          "stored_in": "trigger_indicators.atr_14",
          "used_for": ["magnitude_threshold", "mfe_atr_multiple", "mae_atr_multiple"]
        }
      }
    }'::jsonb,
    0.65,
    0.65,
    'DRAFT',
    'STIG',
    NOW(),
    'STIG-ALPHA-SAT'
);

-- -----------------------------------------------------------------------------
-- TEST B: REGIME ALIGNMENT (Flow Test) V1.1
-- Hypothesis: RSI meaning is regime-dependent (Context > Signal)
-- -----------------------------------------------------------------------------
INSERT INTO fhq_learning.hypothesis_canon (
    hypothesis_code,
    origin_type,
    origin_rationale,
    economic_rationale,
    causal_mechanism,
    counterfactual_scenario,
    expected_direction,
    expected_magnitude,
    expected_timeframe_hours,
    regime_validity,
    regime_conditional_confidence,
    falsification_criteria,
    initial_confidence,
    current_confidence,
    status,
    created_by,
    created_at,
    generator_id
) VALUES (
    'ALPHA_SAT_B_REGIME_ALIGN_V1.1',
    'ECONOMIC_THEORY',
    'RSI meaning is regime-dependent (Context > Signal)',
    'Overbought in bull market = momentum continuation, not reversal',
    'RSI > 70 in STRONG_BULL = trend following outperforms mean reversion',
    'If mean reversion wins in STRONG_BULL + RSI>70, context hypothesis fails.',
    'BULLISH',
    'MODERATE',
    24,
    ARRAY['STRONG_BULL'],
    '{"STRONG_BULL": 0.75}'::jsonb,
    '{
      "falsified_if": "trend_win_rate < mean_reversion_win_rate",
      "mae_threshold_atr_multiple": 1.5,
      "mae_survival_required": true,
      "min_sample_size": 25,
      "regime_model_version_required": "sovereign_v4_ddatp_1.2",
      "measurement_schema": {
        "test_code": "ALPHA_SAT_B",
        "version": "1.1",
        "trigger": {
          "indicator": "RSI_14",
          "condition": "> 70",
          "regime_filter": "STRONG_BULL",
          "source_table": "fhq_indicators.momentum",
          "capture_fields": ["rsi_14", "atr_14", "entry_price"]
        },
        "measurements": [
          {"name": "long_win_rate", "type": "NUMERIC", "description": "Win rate on trend-following LONG signals"},
          {"name": "short_win_rate", "type": "NUMERIC", "description": "Win rate on mean-reversion SHORT signals"},
          {"name": "mae_survived", "type": "BOOLEAN", "description": "Did trade survive MAE < 1.5x ATR?", "threshold_atr_multiple": 1.5}
        ],
        "atr_logging": {
          "field": "atr_14",
          "stored_in": "trigger_indicators.atr_14",
          "used_for": ["mae_threshold", "mae_atr_multiple"]
        },
        "regime_source": "fhq_perception.sovereign_regime_state_v4"
      }
    }'::jsonb,
    0.60,
    0.60,
    'DRAFT',
    'STIG',
    NOW(),
    'STIG-ALPHA-SAT'
);

-- -----------------------------------------------------------------------------
-- TEST C: MEAN REVERSION (Elasticity Test) V1.1
-- Hypothesis: Mean reversion dominates in low-trend regimes
-- -----------------------------------------------------------------------------
INSERT INTO fhq_learning.hypothesis_canon (
    hypothesis_code,
    origin_type,
    origin_rationale,
    economic_rationale,
    causal_mechanism,
    counterfactual_scenario,
    expected_direction,
    expected_magnitude,
    expected_timeframe_hours,
    regime_validity,
    regime_conditional_confidence,
    falsification_criteria,
    initial_confidence,
    current_confidence,
    status,
    created_by,
    created_at,
    generator_id
) VALUES (
    'ALPHA_SAT_C_MEAN_REVERT_V1.1',
    'ECONOMIC_THEORY',
    'Mean reversion dominates in low-trend regimes',
    'Extended prices in NEUTRAL regime exhibit elastic snap-back to mean',
    'Price > 2 StdDev (BB Top) in NEUTRAL regime triggers reversion to 20 SMA',
    'If price does NOT return to SMA in NEUTRAL, mean reversion fails.',
    'BEARISH',
    'TO_MEAN',
    72,
    ARRAY['NEUTRAL', 'WEAK_BEAR', 'WEAK_BULL'],
    '{"NEUTRAL": 0.75, "WEAK_BEAR": 0.65, "WEAK_BULL": 0.60}'::jsonb,
    '{
      "falsified_if": "mean_touch_rate < 0.55",
      "max_time_hours": 72,
      "min_sample_size": 30,
      "regime_model_version_required": "sovereign_v4_ddatp_1.2",
      "measurement_schema": {
        "test_code": "ALPHA_SAT_C",
        "version": "1.1",
        "trigger": {
          "indicator": "BB_POSITION",
          "condition": "price > bb_upper",
          "regime_filter": "NEUTRAL",
          "source_table": "fhq_indicators.volatility",
          "capture_fields": ["bb_upper", "bb_middle", "atr_14", "entry_price"]
        },
        "measurements": [
          {"name": "touched_mean", "type": "BOOLEAN", "description": "Did price touch 20 SMA within timeframe?"},
          {"name": "time_to_mean_minutes", "type": "INTEGER", "description": "Minutes until mean touch (for distribution)"}
        ],
        "mean_source": "fhq_indicators.volatility.bb_middle"
      }
    }'::jsonb,
    0.65,
    0.65,
    'DRAFT',
    'STIG',
    NOW(),
    'STIG-ALPHA-SAT'
);

-- =============================================================================
-- VERIFICATION QUERY
-- =============================================================================
-- Run after migration to verify blueprints inserted:
-- SELECT hypothesis_code, status, initial_confidence, created_at
-- FROM fhq_learning.hypothesis_canon
-- WHERE hypothesis_code LIKE 'ALPHA_SAT_%V1.1'
-- ORDER BY hypothesis_code;
-- =============================================================================
