/**
 * Deterministic Visual Mapping Functions
 * ADR-023: Visual State Vector Specification - Section 4
 *
 * These functions are monotonic, documented, and versioned.
 * Same input data always produces same visual state.
 * All functions run on BACKEND only (ADR-022: Dumb Glass).
 */

import type {
  AnimationParameters,
  VisualProperties,
  MarketRegime,
  VolatilityRegime,
  DEFCONLevel,
  RegimeColorPalettes,
} from './types';

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

/**
 * Clamp a value between min and max
 */
export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/**
 * Linear interpolation
 */
export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * clamp(t, 0, 1);
}

/**
 * Smooth step function
 */
export function smoothstep(edge0: number, edge1: number, x: number): number {
  const t = clamp((x - edge0) / (edge1 - edge0), 0, 1);
  return t * t * (3 - 2 * t);
}

// =============================================================================
// TREND MAPPING (The Current) - ADR-023 Section 4.1
// =============================================================================

export interface TrendInputs {
  ema_cross: number;        // -1.0 to +1.0 (EMA12 vs EMA26)
  macd_histogram: number;   // Normalized MACD histogram
  adx_strength: number;     // 0.0 to 1.0 (ADX/100)
  trend_stability: number;  // 0.0 to 1.0
  regime_confidence: number;// 0.0 to 1.0
}

export interface TrendOutput {
  flow_speed: number;
  flow_direction: number;
  flow_turbulence: number;
  flow_thickness: number;
  flow_glow_intensity: number;
}

/**
 * Map trend indicators to The Current stream parameters
 * Monotonic: Higher ADX = faster flow, Bullish cross = positive direction
 */
export function mapTrendToFlow(inputs: TrendInputs): TrendOutput {
  const { ema_cross, macd_histogram, adx_strength, trend_stability, regime_confidence } = inputs;

  // Flow speed: ADX drives speed (stronger trend = faster flow)
  // Range: 0.1 to 2.0
  const flow_speed = 0.1 + (adx_strength * 1.9);

  // Flow direction: Weighted average of EMA cross and MACD
  // Range: -1.0 to +1.0
  const macd_sign = macd_histogram >= 0 ? 1 : -1;
  const flow_direction = clamp((ema_cross * 0.6) + (macd_sign * 0.4), -1, 1);

  // Flow turbulence: Inverse of stability
  // Range: 0.0 to 1.0
  const flow_turbulence = 1.0 - trend_stability;

  // Flow thickness: Based on trend level
  // Range: 0.5 to 2.0
  const flow_thickness = 0.5 + (adx_strength * 1.5);

  // Flow glow: Trend level * regime confidence
  // Range: 0.0 to 1.0
  const flow_glow_intensity = adx_strength * regime_confidence;

  return {
    flow_speed: clamp(flow_speed, 0.1, 2.0),
    flow_direction: clamp(flow_direction, -1, 1),
    flow_turbulence: clamp(flow_turbulence, 0, 1),
    flow_thickness: clamp(flow_thickness, 0.5, 2.0),
    flow_glow_intensity: clamp(flow_glow_intensity, 0, 1),
  };
}

// =============================================================================
// MOMENTUM MAPPING (The Pulse) - ADR-023 Section 4.2
// =============================================================================

export interface MomentumInputs {
  rsi: number;              // 0-100
  stochastic_k: number;     // 0-100
  roc: number;              // Rate of change, normalized -1 to +1
  momentum_strength: number;// 0.0 to 1.0
}

export interface MomentumOutput {
  pulse_amplitude: number;
  pulse_frequency: number;
  pulse_wavelength: number;
  pulse_spark_rate: number;
}

/**
 * Map momentum indicators to The Pulse wave parameters
 * Monotonic: Extreme RSI = high amplitude, Fast ROC = high frequency
 */
export function mapMomentumToPulse(inputs: MomentumInputs): MomentumOutput {
  const { rsi, stochastic_k, roc, momentum_strength } = inputs;

  // Amplitude: How extreme is momentum (distance from neutral)
  // RSI 50 = neutral, extremes (0 or 100) = max amplitude
  const rsi_extreme = Math.abs(rsi - 50) / 50;
  const stoch_extreme = Math.abs(stochastic_k - 50) / 50;
  const pulse_amplitude = (rsi_extreme * 0.5) + (stoch_extreme * 0.5);

  // Frequency: How fast is momentum changing
  // Higher ROC absolute value = faster pulse
  const pulse_frequency = 0.5 + (Math.abs(roc) * 3.5);

  // Wavelength: Inverse relationship with momentum strength
  // Range: 1.0 to 10.0
  const pulse_wavelength = 10.0 - (momentum_strength * 9.0);

  // Spark rate: Only at high momentum (>0.8)
  // Range: 0.0 to 1.0
  const pulse_spark_rate = momentum_strength > 0.8 ? momentum_strength : 0;

  return {
    pulse_amplitude: clamp(pulse_amplitude, 0, 1),
    pulse_frequency: clamp(pulse_frequency, 0.5, 4.0),
    pulse_wavelength: clamp(pulse_wavelength, 1.0, 10.0),
    pulse_spark_rate: clamp(pulse_spark_rate, 0, 1),
  };
}

// =============================================================================
// VOLATILITY MAPPING (The Weather) - ADR-023 Section 4.3
// =============================================================================

export interface VolatilityInputs {
  atr_percentile: number;     // 0.0 to 1.0 (current ATR vs historical)
  bb_width_percentile: number;// 0.0 to 1.0
  volatility_regime: VolatilityRegime;
  volatility_intensity: number; // 0.0 to 1.0
}

export interface VolatilityOutput {
  cloud_density: number;
  cloud_turbulence: number;
  cloud_height: number;
  lightning_frequency: number;
  lightning_intensity: number;
}

/**
 * Map volatility indicators to The Weather cloud parameters
 * Monotonic: Higher percentile = denser clouds, EXTREME = lightning
 */
export function mapVolatilityToWeather(inputs: VolatilityInputs): VolatilityOutput {
  const { atr_percentile, bb_width_percentile, volatility_regime, volatility_intensity } = inputs;

  // Cloud density: Average of ATR and BB percentiles
  // Range: 0.0 to 1.0
  const cloud_density = (atr_percentile * 0.6) + (bb_width_percentile * 0.4);

  // Turbulence: Driven by volatility regime
  const turbulence_map: Record<VolatilityRegime, number> = {
    LOW: 0.1,
    NORMAL: 0.3,
    HIGH: 0.6,
    EXTREME: 0.9,
  };
  const cloud_turbulence = turbulence_map[volatility_regime];

  // Cloud height: Based on intensity
  // Range: 0.5 to 2.0
  const cloud_height = 0.5 + (volatility_intensity * 1.5);

  // Lightning: Only in HIGH or EXTREME
  let lightning_frequency = 0;
  let lightning_intensity = 0;

  if (volatility_regime === 'EXTREME') {
    lightning_frequency = cloud_density * 0.8;
    lightning_intensity = volatility_intensity;
  } else if (volatility_regime === 'HIGH') {
    lightning_frequency = cloud_density * 0.3;
    lightning_intensity = volatility_intensity * 0.5;
  }

  return {
    cloud_density: clamp(cloud_density, 0, 1),
    cloud_turbulence: clamp(cloud_turbulence, 0, 1),
    cloud_height: clamp(cloud_height, 0.5, 2.0),
    lightning_frequency: clamp(lightning_frequency, 0, 1),
    lightning_intensity: clamp(lightning_intensity, 0, 1),
  };
}

// =============================================================================
// VOLUME MAPPING (The Force) - ADR-023 Section 4.4
// =============================================================================

export interface VolumeInputs {
  volume_ratio: number;     // Current vs average (e.g., 1.5 = 50% above avg)
  obv_momentum: number;     // -1.0 to +1.0
  vwap_deviation: number;   // Normalized price vs VWAP
  volume_strength: number;  // 0.0 to 1.0
}

export interface VolumeOutput {
  particle_density: number;
  particle_speed: number;
  channel_glow: number;
  shockwave_intensity: number;
}

/**
 * Map volume indicators to The Force particle channel parameters
 * Monotonic: Higher volume ratio = more particles, Spike = shockwave
 */
export function mapVolumeToForce(inputs: VolumeInputs): VolumeOutput {
  const { volume_ratio, obv_momentum, volume_strength } = inputs;

  // Particle density: Direct mapping from volume ratio
  // 0.5x volume = 0.25 density, 2x volume = 1.0 density
  const particle_density = clamp((volume_ratio - 0.5) / 1.5, 0, 1);

  // Particle speed: OBV momentum drives speed
  // Range: 0.5 to 3.0
  const particle_speed = 0.5 + (Math.abs(obv_momentum) * 2.5);

  // Channel glow: Direct from volume strength
  // Range: 0.0 to 1.0
  const channel_glow = volume_strength;

  // Shockwave: Only on volume spikes (volume_ratio > 2.0)
  // Range: 0.0 to 1.0
  const shockwave_intensity = volume_ratio > 2.0
    ? clamp((volume_ratio - 2.0) / 3.0, 0, 1)
    : 0;

  return {
    particle_density: clamp(particle_density, 0, 1),
    particle_speed: clamp(particle_speed, 0.5, 3.0),
    channel_glow: clamp(channel_glow, 0, 1),
    shockwave_intensity: clamp(shockwave_intensity, 0, 1),
  };
}

// =============================================================================
// REGIME COLOR MAPPING - ADR-023 Section 4.5
// =============================================================================

export interface RegimeColorOutput {
  primary_color: string;
  accent_color: string;
  background_color: string;
  emission_color: string;
}

const REGIME_PALETTES: Record<MarketRegime, RegimeColorOutput> = {
  BULL: {
    primary_color: '#00FF88',
    accent_color: '#88FFCC',
    background_color: '#0A1F1A',
    emission_color: '#00FF88',
  },
  BEAR: {
    primary_color: '#FF4466',
    accent_color: '#FF8899',
    background_color: '#1F0A0E',
    emission_color: '#FF4466',
  },
  RANGE: {
    primary_color: '#4488FF',
    accent_color: '#88BBFF',
    background_color: '#0A0E1F',
    emission_color: '#4488FF',
  },
  TRANSITION: {
    primary_color: '#FFAA00',
    accent_color: '#FFCC66',
    background_color: '#1F150A',
    emission_color: '#FFAA00',
  },
  UNKNOWN: {
    primary_color: '#666666',
    accent_color: '#999999',
    background_color: '#0F0F0F',
    emission_color: '#666666',
  },
};

/**
 * Map regime to color palette, with confidence-based desaturation
 */
export function mapRegimeToColors(
  regime: MarketRegime,
  confidence: number
): RegimeColorOutput {
  const palette = REGIME_PALETTES[regime];

  // If confidence is low, desaturate colors
  if (confidence < 0.5) {
    // Simple desaturation by blending with gray
    const desatFactor = confidence / 0.5; // 0 at confidence=0, 1 at confidence=0.5
    return {
      primary_color: blendWithGray(palette.primary_color, desatFactor),
      accent_color: blendWithGray(palette.accent_color, desatFactor),
      background_color: palette.background_color,
      emission_color: blendWithGray(palette.emission_color, desatFactor),
    };
  }

  return palette;
}

/**
 * Blend a hex color with gray based on factor
 */
function blendWithGray(hex: string, factor: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);

  const gray = (r + g + b) / 3;
  const newR = Math.round(lerp(gray, r, factor));
  const newG = Math.round(lerp(gray, g, factor));
  const newB = Math.round(lerp(gray, b, factor));

  return `#${newR.toString(16).padStart(2, '0')}${newG.toString(16).padStart(2, '0')}${newB.toString(16).padStart(2, '0')}`;
}

// =============================================================================
// GLOBAL SCENE PARAMETERS
// =============================================================================

export interface GlobalInputs {
  market_intensity: number;     // 0.0 to 1.0 (composite of vol + volume)
  defcon_level: DEFCONLevel;
  volatility_intensity: number;
  volume_strength: number;
}

export interface GlobalOutput {
  camera_shake_amplitude: number;
  camera_shake_frequency: number;
  global_intensity: number;
  core_pulse_rate: number;
  core_glow_intensity: number;
  core_rotation_speed: number;
}

/**
 * Map global market state to scene parameters
 */
export function mapGlobalParams(inputs: GlobalInputs): GlobalOutput {
  const { market_intensity, defcon_level, volatility_intensity, volume_strength } = inputs;

  // Camera shake only if high volatility and not in DEFCON orange or worse
  let camera_shake_amplitude = 0;
  let camera_shake_frequency = 0;

  if (defcon_level === 'GREEN' || defcon_level === 'YELLOW') {
    if (volatility_intensity > 0.7) {
      camera_shake_amplitude = (volatility_intensity - 0.7) * 0.33; // Max 0.1
      camera_shake_frequency = 2 + (volatility_intensity * 3);
    }
  }

  // Core pulse rate based on market intensity
  const core_pulse_rate = 0.5 + (market_intensity * 1.5);

  // Core glow based on average of vol and volume
  const core_glow_intensity = (volatility_intensity + volume_strength) / 2;

  // Rotation speed increases with intensity
  const core_rotation_speed = 0.1 + (market_intensity * 0.9);

  return {
    camera_shake_amplitude: clamp(camera_shake_amplitude, 0, 0.1),
    camera_shake_frequency: clamp(camera_shake_frequency, 0, 5),
    global_intensity: clamp(market_intensity, 0, 1),
    core_pulse_rate: clamp(core_pulse_rate, 0.5, 2.0),
    core_glow_intensity: clamp(core_glow_intensity, 0, 1),
    core_rotation_speed: clamp(core_rotation_speed, 0, 1),
  };
}

// =============================================================================
// POST-PROCESSING PARAMETERS
// =============================================================================

export interface PostProcessOutput {
  bloom_intensity: number;
  bloom_threshold: number;
  vignette_intensity: number;
  film_grain_intensity: number;
  chromatic_aberration: number;
}

/**
 * Map regime and DEFCON to post-processing parameters
 */
export function mapPostProcessing(
  regime: MarketRegime,
  defcon_level: DEFCONLevel,
  volatility_intensity: number
): PostProcessOutput {
  // Base values by regime
  const regimeSettings: Record<MarketRegime, Partial<PostProcessOutput>> = {
    BULL: { bloom_intensity: 0.6, vignette_intensity: 0.2, film_grain_intensity: 0.02 },
    BEAR: { bloom_intensity: 0.5, vignette_intensity: 0.3, film_grain_intensity: 0.03 },
    RANGE: { bloom_intensity: 0.4, vignette_intensity: 0.2, film_grain_intensity: 0.02 },
    TRANSITION: { bloom_intensity: 0.7, vignette_intensity: 0.25, film_grain_intensity: 0.04 },
    UNKNOWN: { bloom_intensity: 0.2, vignette_intensity: 0.4, film_grain_intensity: 0.05 },
  };

  const base = regimeSettings[regime];

  // Apply DEFCON modifications
  let multiplier = 1.0;
  let chromaticAberration = 0;

  switch (defcon_level) {
    case 'GREEN':
      multiplier = 1.0;
      break;
    case 'YELLOW':
      multiplier = 0.8;
      break;
    case 'ORANGE':
      multiplier = 0.5;
      break;
    case 'RED':
    case 'BLACK':
      multiplier = 0;
      break;
  }

  // Chromatic aberration only in high volatility
  if (volatility_intensity > 0.8 && (defcon_level === 'GREEN' || defcon_level === 'YELLOW')) {
    chromaticAberration = (volatility_intensity - 0.8) * 0.25; // Max 0.05
  }

  return {
    bloom_intensity: (base.bloom_intensity || 0.5) * multiplier,
    bloom_threshold: 0.5,
    vignette_intensity: (base.vignette_intensity || 0.2) * multiplier,
    film_grain_intensity: (base.film_grain_intensity || 0.02) * multiplier,
    chromatic_aberration: chromaticAberration,
  };
}

// =============================================================================
// FULL VSV GENERATION (combines all mapping functions)
// =============================================================================

export interface FullMappingInputs {
  // Trend
  ema_cross: number;
  macd_histogram: number;
  adx_strength: number;
  trend_stability: number;

  // Momentum
  rsi: number;
  stochastic_k: number;
  roc: number;
  momentum_strength: number;

  // Volatility
  atr_percentile: number;
  bb_width_percentile: number;
  volatility_regime: VolatilityRegime;
  volatility_intensity: number;

  // Volume
  volume_ratio: number;
  obv_momentum: number;
  vwap_deviation: number;
  volume_strength: number;

  // Regime
  regime: MarketRegime;
  regime_confidence: number;

  // DEFCON
  defcon_level: DEFCONLevel;
}

export function generateFullAnimationParams(inputs: FullMappingInputs): AnimationParameters {
  const trend = mapTrendToFlow({
    ema_cross: inputs.ema_cross,
    macd_histogram: inputs.macd_histogram,
    adx_strength: inputs.adx_strength,
    trend_stability: inputs.trend_stability,
    regime_confidence: inputs.regime_confidence,
  });

  const momentum = mapMomentumToPulse({
    rsi: inputs.rsi,
    stochastic_k: inputs.stochastic_k,
    roc: inputs.roc,
    momentum_strength: inputs.momentum_strength,
  });

  const volatility = mapVolatilityToWeather({
    atr_percentile: inputs.atr_percentile,
    bb_width_percentile: inputs.bb_width_percentile,
    volatility_regime: inputs.volatility_regime,
    volatility_intensity: inputs.volatility_intensity,
  });

  const volume = mapVolumeToForce({
    volume_ratio: inputs.volume_ratio,
    obv_momentum: inputs.obv_momentum,
    vwap_deviation: inputs.vwap_deviation,
    volume_strength: inputs.volume_strength,
  });

  const market_intensity = (inputs.volatility_intensity + inputs.volume_strength) / 2;

  const global = mapGlobalParams({
    market_intensity,
    defcon_level: inputs.defcon_level,
    volatility_intensity: inputs.volatility_intensity,
    volume_strength: inputs.volume_strength,
  });

  return {
    // Trend
    flow_speed: trend.flow_speed,
    flow_direction: trend.flow_direction,
    flow_turbulence: trend.flow_turbulence,
    flow_thickness: trend.flow_thickness,
    flow_glow_intensity: trend.flow_glow_intensity,

    // Momentum
    pulse_amplitude: momentum.pulse_amplitude,
    pulse_frequency: momentum.pulse_frequency,
    pulse_wavelength: momentum.pulse_wavelength,
    pulse_spark_rate: momentum.pulse_spark_rate,

    // Volatility
    cloud_density: volatility.cloud_density,
    cloud_turbulence: volatility.cloud_turbulence,
    cloud_height: volatility.cloud_height,
    lightning_frequency: volatility.lightning_frequency,
    lightning_intensity: volatility.lightning_intensity,

    // Volume
    particle_density: volume.particle_density,
    particle_speed: volume.particle_speed,
    channel_glow: volume.channel_glow,
    shockwave_intensity: volume.shockwave_intensity,

    // Global
    camera_shake_amplitude: global.camera_shake_amplitude,
    camera_shake_frequency: global.camera_shake_frequency,
    global_intensity: global.global_intensity,
    core_pulse_rate: global.core_pulse_rate,
    core_glow_intensity: global.core_glow_intensity,
    core_rotation_speed: global.core_rotation_speed,
  };
}

// =============================================================================
// MAPPING VERSION
// =============================================================================

export const MAPPING_VERSION = '2026.1.0';
