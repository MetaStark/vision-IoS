-- ============================================================================
-- Migration 127: ADR-022/023/024 VISUAL CINEMATIC ENGINE
-- Retail Observer Cinematic Engine - Dumb Glass Frontend Architecture
-- ============================================================================
-- Authority: CEO via STIG (CTO) per EC-003
-- ADR References: ADR-022 (Dumb Glass), ADR-023 (VSV Spec), ADR-024 (Cinematic Engine)
-- Classification: G4 CONSTITUTIONAL - VISUAL LAYER
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: Create vision_cinematic schema
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS vision_cinematic;

COMMENT ON SCHEMA vision_cinematic IS 'ADR-022/023/024: Visual Cinematic Engine - Dumb Glass Frontend Architecture';

-- ============================================================================
-- STEP 2: Visual State Vectors (VSV) - Core Table
-- Pre-computed animation parameters for each asset/timestamp
-- ============================================================================

CREATE TABLE vision_cinematic.visual_state_vectors (
    vsv_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,

    -- The Current (Trend) - Plasma River
    trend_flow_speed NUMERIC(8,4) NOT NULL DEFAULT 0.5,      -- 0.0-1.0 normalized
    trend_flow_direction NUMERIC(8,4) NOT NULL DEFAULT 0.0,  -- -1.0 to 1.0
    trend_intensity NUMERIC(8,4) NOT NULL DEFAULT 0.5,       -- 0.0-1.0
    trend_color_hue NUMERIC(8,4) NOT NULL DEFAULT 0.6,       -- HSL hue (0.0-1.0)

    -- The Pulse (Momentum) - Sinusoidal Waves
    momentum_amplitude NUMERIC(8,4) NOT NULL DEFAULT 0.5,    -- 0.0-1.0
    momentum_frequency NUMERIC(8,4) NOT NULL DEFAULT 1.0,    -- Hz
    momentum_phase NUMERIC(8,4) NOT NULL DEFAULT 0.0,        -- 0.0-2PI
    momentum_color_saturation NUMERIC(8,4) NOT NULL DEFAULT 0.7,

    -- The Weather (Volatility) - Volumetric Clouds
    volatility_density NUMERIC(8,4) NOT NULL DEFAULT 0.3,    -- 0.0-1.0
    volatility_turbulence NUMERIC(8,4) NOT NULL DEFAULT 0.5, -- 0.0-1.0
    volatility_color_lightness NUMERIC(8,4) NOT NULL DEFAULT 0.5,

    -- The Force (Volume) - Particle Channel
    volume_particle_count INTEGER NOT NULL DEFAULT 1000,      -- Particle count
    volume_particle_speed NUMERIC(8,4) NOT NULL DEFAULT 0.5, -- 0.0-1.0
    volume_glow_intensity NUMERIC(8,4) NOT NULL DEFAULT 0.5, -- 0.0-1.0

    -- Camera Parameters
    camera_shake_intensity NUMERIC(8,4) NOT NULL DEFAULT 0.0, -- 0.0-1.0
    camera_zoom_level NUMERIC(8,4) NOT NULL DEFAULT 1.0,      -- 0.5-2.0

    -- Post-processing
    bloom_intensity NUMERIC(8,4) NOT NULL DEFAULT 0.3,
    vignette_intensity NUMERIC(8,4) NOT NULL DEFAULT 0.2,
    film_grain NUMERIC(8,4) NOT NULL DEFAULT 0.05,

    -- Regime Context
    regime_label TEXT,
    regime_confidence NUMERIC(8,4),

    -- DEFCON Visual Rules
    defcon_level TEXT NOT NULL DEFAULT 'GREEN',
    defcon_degradation_factor NUMERIC(8,4) NOT NULL DEFAULT 1.0,

    -- Governance & Audit
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    computed_by TEXT NOT NULL DEFAULT 'STIG',
    mapping_version TEXT NOT NULL DEFAULT 'v1.0.0',
    source_hash TEXT NOT NULL,
    vsv_signature TEXT,

    CONSTRAINT vsv_asset_timestamp_unique UNIQUE (asset_id, timestamp)
);

CREATE INDEX idx_vsv_asset_id ON vision_cinematic.visual_state_vectors(asset_id);
CREATE INDEX idx_vsv_timestamp ON vision_cinematic.visual_state_vectors(timestamp DESC);
CREATE INDEX idx_vsv_defcon ON vision_cinematic.visual_state_vectors(defcon_level);

COMMENT ON TABLE vision_cinematic.visual_state_vectors IS 'ADR-023: Pre-computed Visual State Vectors for cinematic rendering';

-- ============================================================================
-- STEP 3: Cinematic Events - Triggers for special animations
-- ============================================================================

CREATE TABLE vision_cinematic.cinematic_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- REGIME_SHIFT, VOLATILITY_STORM, VOLUME_SURGE, BREAKOUT
    event_timestamp TIMESTAMPTZ NOT NULL,

    -- Event parameters
    event_intensity NUMERIC(8,4) NOT NULL DEFAULT 0.5,
    event_duration_ms INTEGER NOT NULL DEFAULT 2000,
    event_data JSONB NOT NULL DEFAULT '{}',

    -- Animation overrides
    camera_animation TEXT,  -- SHAKE, ZOOM_IN, ZOOM_OUT, PAN
    particle_burst BOOLEAN DEFAULT FALSE,
    flash_color TEXT,       -- Hex color for flash effect

    -- Governance
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    detected_by TEXT NOT NULL DEFAULT 'STIG',
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMPTZ
);

CREATE INDEX idx_events_asset ON vision_cinematic.cinematic_events(asset_id);
CREATE INDEX idx_events_timestamp ON vision_cinematic.cinematic_events(event_timestamp DESC);
CREATE INDEX idx_events_type ON vision_cinematic.cinematic_events(event_type);

COMMENT ON TABLE vision_cinematic.cinematic_events IS 'ADR-024: Cinematic event triggers for special animations';

-- ============================================================================
-- STEP 4: Render Evidence - Frame-to-data audit trail
-- ============================================================================

CREATE TABLE vision_cinematic.render_evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vsv_id UUID REFERENCES vision_cinematic.visual_state_vectors(vsv_id),
    frame_timestamp TIMESTAMPTZ NOT NULL,

    -- What was rendered
    rendered_asset_id TEXT NOT NULL,
    rendered_params JSONB NOT NULL,

    -- Hash chain for audit
    input_data_hash TEXT NOT NULL,
    output_frame_hash TEXT NOT NULL,

    -- Client info
    client_session_id TEXT,
    client_viewport JSONB,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_render_vsv ON vision_cinematic.render_evidence(vsv_id);
CREATE INDEX idx_render_timestamp ON vision_cinematic.render_evidence(frame_timestamp DESC);

COMMENT ON TABLE vision_cinematic.render_evidence IS 'ADR-022: Frame-to-data audit trail for compliance';

-- ============================================================================
-- STEP 5: Mapping Versions - Versioned deterministic functions
-- ============================================================================

CREATE TABLE vision_cinematic.mapping_versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_tag TEXT NOT NULL UNIQUE,

    -- Mapping function definitions (stored as JSON for auditability)
    trend_mapping JSONB NOT NULL,
    momentum_mapping JSONB NOT NULL,
    volatility_mapping JSONB NOT NULL,
    volume_mapping JSONB NOT NULL,

    -- Governance
    activated_at TIMESTAMPTZ DEFAULT NOW(),
    activated_by TEXT NOT NULL,
    is_current BOOLEAN DEFAULT FALSE,

    -- Attestation
    vega_attested BOOLEAN DEFAULT FALSE,
    vega_attestation_id UUID
);

CREATE INDEX idx_mapping_current ON vision_cinematic.mapping_versions(is_current) WHERE is_current = TRUE;

COMMENT ON TABLE vision_cinematic.mapping_versions IS 'ADR-023: Versioned deterministic mapping functions';

-- ============================================================================
-- STEP 6: DEFCON Visual Rules - 5-level visual degradation
-- ============================================================================

CREATE TABLE vision_cinematic.defcon_visual_rules (
    rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    defcon_level TEXT NOT NULL UNIQUE,

    -- Visual degradation parameters
    max_particle_count INTEGER NOT NULL,
    max_bloom_intensity NUMERIC(8,4) NOT NULL,
    allow_camera_shake BOOLEAN NOT NULL,
    allow_post_processing BOOLEAN NOT NULL,
    color_desaturation NUMERIC(8,4) NOT NULL DEFAULT 0.0,

    -- Override behavior
    force_static_render BOOLEAN NOT NULL DEFAULT FALSE,
    emergency_message TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert DEFCON visual rules
INSERT INTO vision_cinematic.defcon_visual_rules
(defcon_level, max_particle_count, max_bloom_intensity, allow_camera_shake, allow_post_processing, color_desaturation, force_static_render, emergency_message) VALUES
('GREEN', 10000, 1.0, TRUE, TRUE, 0.0, FALSE, NULL),
('YELLOW', 5000, 0.7, TRUE, TRUE, 0.1, FALSE, 'ELEVATED ALERT: Enhanced monitoring active'),
('ORANGE', 2000, 0.5, FALSE, TRUE, 0.3, FALSE, 'HIGH ALERT: Reduced visual complexity'),
('RED', 500, 0.2, FALSE, FALSE, 0.6, FALSE, 'CRITICAL: Minimal rendering mode'),
('BLACK', 100, 0.0, FALSE, FALSE, 1.0, TRUE, 'SYSTEM HALT: Static display only');

COMMENT ON TABLE vision_cinematic.defcon_visual_rules IS 'ADR-016/024: DEFCON-based visual degradation rules';

-- ============================================================================
-- STEP 7: Insert initial mapping version (v1.0.0)
-- ============================================================================

INSERT INTO vision_cinematic.mapping_versions (
    version_tag,
    trend_mapping,
    momentum_mapping,
    volatility_mapping,
    volume_mapping,
    activated_by,
    is_current
) VALUES (
    'v1.0.0',
    '{
        "inputs": ["ema_20", "ema_50", "macd", "macd_signal", "adx"],
        "flow_speed": {"source": "adx", "normalize": [0, 100], "output": [0.1, 1.0]},
        "flow_direction": {"source": "macd_diff", "normalize": [-2, 2], "output": [-1.0, 1.0]},
        "intensity": {"source": "ema_crossover", "binary": true},
        "color_hue": {"source": "trend_direction", "bullish": 0.33, "bearish": 0.0, "neutral": 0.6}
    }'::jsonb,
    '{
        "inputs": ["rsi_14", "stochastic_k", "stochastic_d", "roc_10"],
        "amplitude": {"source": "rsi_14", "normalize": [30, 70], "output": [0.2, 1.0]},
        "frequency": {"source": "stochastic_k", "normalize": [0, 100], "output": [0.5, 3.0]},
        "phase": {"source": "roc_10", "normalize": [-10, 10], "output": [0, 6.28]},
        "saturation": {"source": "rsi_divergence", "normalize": [0, 1], "output": [0.5, 1.0]}
    }'::jsonb,
    '{
        "inputs": ["atr_14", "bb_width", "historical_vol_20"],
        "density": {"source": "bb_width", "normalize": [0.01, 0.1], "output": [0.1, 0.9]},
        "turbulence": {"source": "atr_14", "normalize": [0, 5], "output": [0.1, 1.0]},
        "lightness": {"source": "vol_percentile", "normalize": [0, 100], "output": [0.3, 0.8]}
    }'::jsonb,
    '{
        "inputs": ["volume", "volume_sma_20", "obv", "obv_sma"],
        "particle_count": {"source": "volume_ratio", "normalize": [0.5, 3.0], "output": [500, 5000]},
        "particle_speed": {"source": "obv_momentum", "normalize": [-1, 1], "output": [0.2, 1.0]},
        "glow_intensity": {"source": "volume_spike", "threshold": 2.0, "base": 0.3, "spike": 0.9}
    }'::jsonb,
    'STIG',
    TRUE
);

-- ============================================================================
-- STEP 8: Function to compute VSV from price/indicator data
-- ============================================================================

CREATE OR REPLACE FUNCTION vision_cinematic.compute_vsv(
    p_asset_id TEXT,
    p_timestamp TIMESTAMPTZ DEFAULT NOW()
)
RETURNS UUID AS $$
DECLARE
    v_vsv_id UUID;
    v_price RECORD;
    v_regime RECORD;
    v_defcon TEXT;
    v_source_hash TEXT;

    -- Computed values
    v_trend_flow_speed NUMERIC;
    v_trend_direction NUMERIC;
    v_momentum_amplitude NUMERIC;
    v_volatility_density NUMERIC;
    v_volume_particle_count INTEGER;
BEGIN
    -- Get latest price data
    SELECT * INTO v_price
    FROM fhq_data.price_series
    WHERE listing_id = p_asset_id
    AND timestamp <= p_timestamp
    ORDER BY timestamp DESC
    LIMIT 1;

    IF v_price IS NULL THEN
        RAISE EXCEPTION 'No price data found for asset %', p_asset_id;
    END IF;

    -- Get current regime
    SELECT * INTO v_regime
    FROM fhq_perception.sovereign_regime_state_v4
    WHERE asset_id = p_asset_id
    ORDER BY timestamp DESC
    LIMIT 1;

    -- Get current DEFCON
    SELECT defcon_level INTO v_defcon
    FROM fhq_governance.defcon_state
    WHERE is_current = TRUE
    LIMIT 1;

    v_defcon := COALESCE(v_defcon, 'GREEN');

    -- Compute source hash for audit
    v_source_hash := encode(sha256(
        (v_price.listing_id || v_price.timestamp::text || v_price.close::text)::bytea
    ), 'hex');

    -- Simple mapping computations (real implementation would use indicator data)
    v_trend_flow_speed := 0.5 + (random() * 0.3);
    v_trend_direction := CASE
        WHEN v_regime.sovereign_regime = 'BULL_QUIET' THEN 0.7
        WHEN v_regime.sovereign_regime = 'BULL_VOLATILE' THEN 0.5
        WHEN v_regime.sovereign_regime = 'BEAR_QUIET' THEN -0.7
        WHEN v_regime.sovereign_regime = 'BEAR_VOLATILE' THEN -0.5
        ELSE 0.0
    END;
    v_momentum_amplitude := 0.5;
    v_volatility_density := CASE
        WHEN v_regime.sovereign_regime LIKE '%VOLATILE%' THEN 0.7
        ELSE 0.3
    END;
    v_volume_particle_count := COALESCE(v_price.volume::integer / 1000000, 1000);

    -- Insert VSV
    INSERT INTO vision_cinematic.visual_state_vectors (
        asset_id,
        timestamp,
        trend_flow_speed,
        trend_flow_direction,
        trend_intensity,
        trend_color_hue,
        momentum_amplitude,
        momentum_frequency,
        momentum_phase,
        momentum_color_saturation,
        volatility_density,
        volatility_turbulence,
        volatility_color_lightness,
        volume_particle_count,
        volume_particle_speed,
        volume_glow_intensity,
        camera_shake_intensity,
        camera_zoom_level,
        bloom_intensity,
        vignette_intensity,
        film_grain,
        regime_label,
        regime_confidence,
        defcon_level,
        defcon_degradation_factor,
        source_hash
    ) VALUES (
        p_asset_id,
        p_timestamp,
        v_trend_flow_speed,
        v_trend_direction,
        0.5,
        CASE WHEN v_trend_direction > 0 THEN 0.33 ELSE 0.0 END,
        v_momentum_amplitude,
        1.0,
        0.0,
        0.7,
        v_volatility_density,
        v_volatility_density * 0.8,
        0.5,
        LEAST(v_volume_particle_count, 5000),
        0.5,
        0.5,
        CASE WHEN v_volatility_density > 0.6 THEN 0.3 ELSE 0.0 END,
        1.0,
        0.3,
        0.2,
        0.05,
        v_regime.sovereign_regime,
        (v_regime.state_probabilities->>'max_prob')::numeric,
        v_defcon,
        CASE v_defcon
            WHEN 'GREEN' THEN 1.0
            WHEN 'YELLOW' THEN 0.8
            WHEN 'ORANGE' THEN 0.6
            WHEN 'RED' THEN 0.3
            WHEN 'BLACK' THEN 0.1
            ELSE 1.0
        END,
        v_source_hash
    )
    ON CONFLICT (asset_id, timestamp) DO UPDATE SET
        trend_flow_speed = EXCLUDED.trend_flow_speed,
        trend_flow_direction = EXCLUDED.trend_flow_direction,
        regime_label = EXCLUDED.regime_label,
        defcon_level = EXCLUDED.defcon_level,
        computed_at = NOW()
    RETURNING vsv_id INTO v_vsv_id;

    RETURN v_vsv_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vision_cinematic.compute_vsv IS 'ADR-023: Compute Visual State Vector from market data';

-- ============================================================================
-- STEP 9: Function to get latest VSV for an asset
-- ============================================================================

CREATE OR REPLACE FUNCTION vision_cinematic.get_latest_vsv(
    p_asset_id TEXT
)
RETURNS TABLE (
    vsv_id UUID,
    asset_id TEXT,
    vsv_timestamp TIMESTAMPTZ,
    trend JSONB,
    momentum JSONB,
    volatility JSONB,
    volume JSONB,
    camera JSONB,
    post_processing JSONB,
    regime JSONB,
    defcon JSONB,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        v.vsv_id,
        v.asset_id,
        v.timestamp AS vsv_timestamp,
        jsonb_build_object(
            'flowSpeed', v.trend_flow_speed,
            'flowDirection', v.trend_flow_direction,
            'intensity', v.trend_intensity,
            'colorHue', v.trend_color_hue
        ) as trend,
        jsonb_build_object(
            'amplitude', v.momentum_amplitude,
            'frequency', v.momentum_frequency,
            'phase', v.momentum_phase,
            'colorSaturation', v.momentum_color_saturation
        ) as momentum,
        jsonb_build_object(
            'density', v.volatility_density,
            'turbulence', v.volatility_turbulence,
            'colorLightness', v.volatility_color_lightness
        ) as volatility,
        jsonb_build_object(
            'particleCount', v.volume_particle_count,
            'particleSpeed', v.volume_particle_speed,
            'glowIntensity', v.volume_glow_intensity
        ) as volume,
        jsonb_build_object(
            'shakeIntensity', v.camera_shake_intensity,
            'zoomLevel', v.camera_zoom_level
        ) as camera,
        jsonb_build_object(
            'bloomIntensity', v.bloom_intensity,
            'vignetteIntensity', v.vignette_intensity,
            'filmGrain', v.film_grain
        ) as post_processing,
        jsonb_build_object(
            'label', v.regime_label,
            'confidence', v.regime_confidence
        ) as regime,
        jsonb_build_object(
            'level', v.defcon_level,
            'degradationFactor', v.defcon_degradation_factor
        ) as defcon,
        jsonb_build_object(
            'computedAt', v.computed_at,
            'computedBy', v.computed_by,
            'mappingVersion', v.mapping_version,
            'sourceHash', v.source_hash
        ) as metadata
    FROM vision_cinematic.visual_state_vectors v
    WHERE v.asset_id = p_asset_id
    ORDER BY v.timestamp DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vision_cinematic.get_latest_vsv IS 'ADR-022: Get latest Visual State Vector for frontend consumption';

-- ============================================================================
-- STEP 10: Register ADRs in governance registry
-- ============================================================================

INSERT INTO fhq_meta.adr_registry (adr_id, adr_title, adr_status, adr_type, current_version, owner, governance_tier, created_at)
VALUES
    ('ADR-022', 'Dumb Glass Frontend Architecture', 'APPROVED', 'CONSTITUTIONAL', '1.0.0', 'STIG', 'G4', NOW()),
    ('ADR-023', 'Visual State Vector Specification', 'APPROVED', 'CONSTITUTIONAL', '1.0.0', 'STIG', 'G4', NOW()),
    ('ADR-024', 'Retail Observer Cinematic Engine', 'APPROVED', 'CONSTITUTIONAL', '1.0.0', 'STIG', 'G4', NOW())
ON CONFLICT (adr_id) DO UPDATE SET
    adr_status = EXCLUDED.adr_status,
    adr_type = EXCLUDED.adr_type;

-- ============================================================================
-- STEP 11: Log migration in audit trail
-- ============================================================================

INSERT INTO fhq_governance.system_events (
    event_type,
    event_category,
    event_severity,
    source_agent,
    event_title,
    event_data
) VALUES (
    'MIGRATION_APPLIED',
    'GOVERNANCE',
    'INFO',
    'STIG',
    'Migration 127: ADR-022/023/024 Visual Cinematic Engine deployed',
    jsonb_build_object(
        'migration_number', 127,
        'schema_created', 'vision_cinematic',
        'tables_created', ARRAY['visual_state_vectors', 'cinematic_events', 'render_evidence', 'mapping_versions', 'defcon_visual_rules'],
        'functions_created', ARRAY['compute_vsv', 'get_latest_vsv'],
        'adrs_registered', ARRAY['ADR-022', 'ADR-023', 'ADR-024']
    )
);

COMMIT;
