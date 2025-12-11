/**
 * Visual Cinematic Engine Types
 * ADR-023: Visual State Vector Specification
 * ADR-024: Retail Observer Cinematic Engine
 *
 * These types define the canonical interface between market data and visualization.
 * All visual parameters are pre-computed by backend (ADR-022: Dumb Glass).
 */

// =============================================================================
// ENUMS
// =============================================================================

export type MarketRegime = 'BULL' | 'BEAR' | 'RANGE' | 'TRANSITION' | 'UNKNOWN';
export type VolatilityRegime = 'LOW' | 'NORMAL' | 'HIGH' | 'EXTREME';
export type DEFCONLevel = 'GREEN' | 'YELLOW' | 'ORANGE' | 'RED' | 'BLACK';
export type CinematicEventType =
  | 'REGIME_SHIFT'
  | 'VOLATILITY_STORM'
  | 'VOLUME_SURGE'
  | 'MOMENTUM_REVERSAL'
  | 'TREND_BREAKOUT'
  | 'DEFCON_CHANGE';
export type EventSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

// =============================================================================
// ANIMATION PARAMETERS (ADR-023 Section 3.2)
// =============================================================================

export interface AnimationParameters {
  // === The Current (Trend Stream) ===
  flow_speed: number;           // 0.1 - 2.0 (base units/second)
  flow_direction: number;       // -1.0 to +1.0 (normalized angle)
  flow_turbulence: number;      // 0.0 - 1.0 (noise amplitude)
  flow_thickness: number;       // 0.5 - 2.0 (relative scale)
  flow_glow_intensity: number;  // 0.0 - 1.0

  // === The Pulse (Momentum Wave) ===
  pulse_amplitude: number;      // 0.0 - 1.0 (wave height)
  pulse_frequency: number;      // 0.5 - 4.0 (Hz)
  pulse_wavelength: number;     // 1.0 - 10.0 (units)
  pulse_spark_rate: number;     // 0.0 - 1.0 (particles/second normalized)

  // === The Weather (Volatility Cloud) ===
  cloud_density: number;        // 0.0 - 1.0
  cloud_turbulence: number;     // 0.0 - 1.0
  cloud_height: number;         // 0.5 - 2.0 (relative scale)
  lightning_frequency: number;  // 0.0 - 1.0 (flashes/second normalized)
  lightning_intensity: number;  // 0.0 - 1.0

  // === The Force (Volume Channel) ===
  particle_density: number;     // 0.0 - 1.0 (particles/volume)
  particle_speed: number;       // 0.5 - 3.0 (units/second)
  channel_glow: number;         // 0.0 - 1.0
  shockwave_intensity: number;  // 0.0 - 1.0 (for volume spikes)

  // === Global Scene ===
  camera_shake_amplitude: number; // 0.0 - 0.1 (units)
  camera_shake_frequency: number; // 0.0 - 5.0 (Hz)
  global_intensity: number;       // 0.0 - 1.0 (market intensity index)

  // === IoS-002 Core ===
  core_pulse_rate: number;      // 0.5 - 2.0 (Hz)
  core_glow_intensity: number;  // 0.0 - 1.0
  core_rotation_speed: number;  // 0.0 - 1.0 (radians/second)
}

// =============================================================================
// VISUAL PROPERTIES (ADR-023 Section 3.3)
// =============================================================================

export interface VisualProperties {
  // === Color Palette (Regime-Driven) ===
  primary_color: string;        // Hex color for main elements
  accent_color: string;         // Hex color for highlights
  background_color: string;     // Hex color for scene background
  trend_color: string;          // The Current color
  momentum_color: string;       // The Pulse color
  volatility_color: string;     // The Weather color
  volume_color: string;         // The Force color

  // === Emissive Properties ===
  emission_intensity: number;   // 0.0 - 2.0 (HDR bloom source)
  emission_color: string;       // Hex color

  // === Post-Processing ===
  bloom_intensity: number;      // 0.0 - 1.0
  bloom_threshold: number;      // 0.0 - 1.0
  vignette_intensity: number;   // 0.0 - 0.5
  film_grain_intensity: number; // 0.0 - 0.1
  chromatic_aberration: number; // 0.0 - 0.05

  // === Depth of Field ===
  dof_focus_distance: number;   // Scene units
  dof_aperture: number;         // 0.0 - 1.0

  // === Labels ===
  trend_label: string;          // "TREND (The Current) // EMA, MACD"
  momentum_label: string;       // "MOMENTUM (The Pulse) // RSI, STOCH"
  volatility_label: string;     // "VOLATILITY (The Weather) // ATR, BB"
  volume_label: string;         // "VOLUME (The Force) // OBV, VWAP"
  regime_label: string;         // "REGIME: BULL"
  defcon_label: string;         // "DEFCON: GREEN"
}

// =============================================================================
// EVENT TRIGGER (ADR-023 Section 3.4)
// =============================================================================

export interface EventTrigger {
  event_type: CinematicEventType;
  event_id: string;             // UUID
  triggered_at: string;         // ISO 8601
  severity: EventSeverity;
  duration_ms: number;          // How long the cinematic should play

  // Event-specific parameters
  parameters: {
    from_state?: string;        // Previous state
    to_state?: string;          // New state
    magnitude?: number;         // 0.0 - 1.0
    camera_preset?: string;     // Camera behavior for this event
    overlay_text?: string;      // Text to display
    overlay_subtext?: string;   // Secondary text
  };
}

// =============================================================================
// VISUAL STATE VECTOR (ADR-023 Section 3.1)
// =============================================================================

export interface VisualStateVector {
  // === Identity ===
  vsv_id: string;               // UUID v4
  asset_id: string;             // e.g., "BTC-USD"
  timestamp: string;            // ISO 8601 with milliseconds

  // === Source Data References ===
  ios_002_snapshot_id: string;  // Reference to indicator state
  ios_003_snapshot_id: string;  // Reference to regime state

  // === Trend (The Current) ===
  trend_level: number;          // 0.0 - 1.0 (normalized strength)
  trend_direction: number;      // -1.0 (bearish) to +1.0 (bullish)
  trend_stability: number;      // 0.0 (chaotic) to 1.0 (stable)

  // === Momentum (The Pulse) ===
  momentum_strength: number;    // 0.0 - 1.0 (normalized)
  momentum_change_rate: number; // 0.0 - 1.0 (how fast momentum changes)
  momentum_divergence: number;  // -1.0 to +1.0 (price vs momentum)

  // === Volatility (The Weather) ===
  volatility_intensity: number; // 0.0 - 1.0 (normalized)
  volatility_regime: VolatilityRegime;
  volatility_trend: number;     // -1.0 (decreasing) to +1.0 (increasing)

  // === Volume (The Force) ===
  volume_strength: number;      // 0.0 - 1.0 (relative to baseline)
  volume_anomaly: number;       // 0.0 - 1.0 (deviation from expected)
  volume_momentum: number;      // -1.0 to +1.0 (acceleration)

  // === Regime & State ===
  regime: MarketRegime;
  regime_confidence: number;    // 0.0 - 1.0
  regime_duration_bars: number; // How long in current regime

  // === DEFCON State ===
  defcon_level: DEFCONLevel;
  defcon_degradation_mask: string[]; // Which fields are degraded

  // === Pre-Computed Animation Parameters ===
  animation: AnimationParameters;

  // === Pre-Computed Visual Properties ===
  visuals: VisualProperties;

  // === Event Triggers ===
  events: EventTrigger[];

  // === Verification ===
  mapping_version: string;      // e.g., "2026.1.0"
  state_snapshot_hash: string;  // SHA-256 of all source data
  signature: string;            // Ed25519 signature
  signer_id: string;            // "STIG" or "FINN"
}

// =============================================================================
// DEFCON VISUAL RULES (ADR-016/024)
// =============================================================================

export interface DEFCONVisualRules {
  defcon_level: DEFCONLevel;
  available_fields: string[];
  degraded_fields: string[];
  particle_density_multiplier: number;
  effect_intensity_multiplier: number;
  allow_cinematics: boolean;
  allow_camera_shake: boolean;
  show_overlay: boolean;
  overlay_text: string | null;
  overlay_subtext: string | null;
  overlay_opacity: number;
  desaturation_level: number;
  grayscale: boolean;
}

// =============================================================================
// CAMERA PRESETS (ADR-024 Section 4.4)
// =============================================================================

export interface CameraPreset {
  type: 'orbit' | 'dolly' | 'shake' | 'static';
  target?: [number, number, number];
  position?: { x: number; y: number; z: number };
  lookAt?: [number, number, number];
  radius?: number;
  speed?: number;
  height?: number;
  tilt?: number;
  duration?: number;
  easing?: string;
  hold?: number;
  reverse?: boolean;
  amplitude?: number;
  frequency?: number;
  decay?: number;
  pushDistance?: number;
}

export const CameraPresets: Record<string, CameraPreset> = {
  ORBIT_DEFAULT: {
    type: 'orbit',
    target: [0, 0, 0],
    radius: 15,
    speed: 0.01,
    height: 3,
    tilt: -10,
  },

  REGIME_SHIFT_ZOOM: {
    type: 'dolly',
    duration: 3000,
    position: { x: 0, y: 3, z: 15 },
    lookAt: [0, 0, 0],
    easing: 'easeInOutCubic',
    hold: 2000,
    reverse: true,
  },

  VOLATILITY_SHAKE: {
    type: 'shake',
    amplitude: 0.05,
    frequency: 8,
    duration: 2000,
    decay: 0.8,
  },

  VOLUME_PULSE: {
    type: 'dolly',
    duration: 1500,
    target: [8, 0, 0],
    pushDistance: 3,
    easing: 'easeOutElastic',
  },
};

// =============================================================================
// REGIME COLOR PALETTES
// =============================================================================

export const RegimeColorPalettes: Record<MarketRegime, {
  primary: string;
  accent: string;
  background: string;
  emission: string;
}> = {
  BULL: {
    primary: '#00FF88',
    accent: '#88FFCC',
    background: '#0A1F1A',
    emission: '#00FF88',
  },
  BEAR: {
    primary: '#FF4466',
    accent: '#FF8899',
    background: '#1F0A0E',
    emission: '#FF4466',
  },
  RANGE: {
    primary: '#4488FF',
    accent: '#88BBFF',
    background: '#0A0E1F',
    emission: '#4488FF',
  },
  TRANSITION: {
    primary: '#FFAA00',
    accent: '#FFCC66',
    background: '#1F150A',
    emission: '#FFAA00',
  },
  UNKNOWN: {
    primary: '#666666',
    accent: '#999999',
    background: '#0F0F0F',
    emission: '#666666',
  },
};

// =============================================================================
// DEFAULT VALUES
// =============================================================================

export const DEFAULT_ANIMATION_PARAMS: AnimationParameters = {
  flow_speed: 1.0,
  flow_direction: 0.0,
  flow_turbulence: 0.3,
  flow_thickness: 1.0,
  flow_glow_intensity: 0.5,
  pulse_amplitude: 0.5,
  pulse_frequency: 1.0,
  pulse_wavelength: 5.0,
  pulse_spark_rate: 0.0,
  cloud_density: 0.3,
  cloud_turbulence: 0.3,
  cloud_height: 1.0,
  lightning_frequency: 0.0,
  lightning_intensity: 0.0,
  particle_density: 0.5,
  particle_speed: 1.0,
  channel_glow: 0.5,
  shockwave_intensity: 0.0,
  camera_shake_amplitude: 0.0,
  camera_shake_frequency: 0.0,
  global_intensity: 0.5,
  core_pulse_rate: 1.0,
  core_glow_intensity: 0.5,
  core_rotation_speed: 0.1,
};

export const DEFAULT_VISUAL_PROPS: VisualProperties = {
  primary_color: '#4488FF',
  accent_color: '#88BBFF',
  background_color: '#0A0E1F',
  trend_color: '#00FF88',
  momentum_color: '#00FFFF',
  volatility_color: '#8844FF',
  volume_color: '#44FF44',
  emission_intensity: 1.0,
  emission_color: '#4488FF',
  bloom_intensity: 0.5,
  bloom_threshold: 0.5,
  vignette_intensity: 0.2,
  film_grain_intensity: 0.02,
  chromatic_aberration: 0.0,
  dof_focus_distance: 10,
  dof_aperture: 0.5,
  trend_label: 'TREND (The Current) // EMA, MACD',
  momentum_label: 'MOMENTUM (The Pulse) // RSI, STOCH',
  volatility_label: 'VOLATILITY (The Weather) // ATR, BB',
  volume_label: 'VOLUME (The Force) // OBV, VWAP',
  regime_label: 'REGIME: RANGE',
  defcon_label: 'DEFCON: GREEN',
};
