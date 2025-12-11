# ADR-023_2026_PRODUCTION – Visual State Vector Specification

**Canonical Version:** 2026.PRODUCTION
**Status:** APPROVED
**Date:** 2025-12-11
**Owner:** STIG (CTO & Runtime Guardian) + FINN (Financial Intelligence)
**Tier:** Tier-2 – Data Architecture
**Authority Chain:** ADR-001 → ADR-013 → ADR-016 → ADR-022 → ADR-023
**Affects:** IoS-002, IoS-003, Visual Engine, Retail Observer, All Dashboards
**Prevails Over:** Any undocumented visual mapping or animation logic

---

## 1. Context

FjordHQ's Retail Observer Cinematic Engine requires a standardized, deterministic, and auditable mechanism for translating market data into visual parameters.

Without a formal specification:
- Visual mappings become ad-hoc and inconsistent
- Different versions of the engine produce different visuals for same data
- Audit trails cannot trace "why did the screen look like that?"
- DEFCON degradation has no clear visual protocol
- Regulatory evidence linking visuals to data is impossible

**ADR-023 establishes the Visual State Vector as the canonical interface between data and visualization.**

---

## 2. Decision

FjordHQ adopts the **Visual State Vector (VSV)** as the sole interface for data-to-visual translation.

### Core Principles

1. **Determinism**: Same input data always produces same visual state
2. **Versioning**: All mapping functions are versioned and logged
3. **Signature**: Every VSV is cryptographically signed
4. **DEFCON-Aware**: VSV adapts to operational state
5. **Auditability**: Any frame can be reconstructed from its VSV

---

## 3. Visual State Vector Schema

### 3.1 Core Structure

```typescript
interface VisualStateVector {
  // === Identity ===
  vsv_id: string;            // UUID v4
  asset_id: string;          // e.g., "BTC-USD"
  timestamp: string;         // ISO 8601 with milliseconds

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
  volatility_regime: string;    // "LOW" | "NORMAL" | "HIGH" | "EXTREME"
  volatility_trend: number;     // -1.0 (decreasing) to +1.0 (increasing)

  // === Volume (The Force) ===
  volume_strength: number;      // 0.0 - 1.0 (relative to baseline)
  volume_anomaly: number;       // 0.0 - 1.0 (deviation from expected)
  volume_momentum: number;      // -1.0 to +1.0 (acceleration)

  // === Regime & State ===
  regime: "BULL" | "BEAR" | "RANGE" | "TRANSITION" | "UNKNOWN";
  regime_confidence: number;    // 0.0 - 1.0
  regime_duration_bars: number; // How long in current regime

  // === DEFCON State ===
  defcon_level: "GREEN" | "YELLOW" | "ORANGE" | "RED" | "BLACK";
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
```

### 3.2 Animation Parameters

```typescript
interface AnimationParameters {
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
```

### 3.3 Visual Properties

```typescript
interface VisualProperties {
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
```

### 3.4 Event Triggers

```typescript
interface EventTrigger {
  event_type: "REGIME_SHIFT" | "VOLATILITY_STORM" | "VOLUME_SURGE" |
              "MOMENTUM_REVERSAL" | "TREND_BREAKOUT" | "DEFCON_CHANGE";
  event_id: string;             // UUID
  triggered_at: string;         // ISO 8601
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
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
```

---

## 4. Deterministic Mapping Functions

All mapping functions MUST be:
- **Monotonic**: Increasing input always produces increasing output
- **Bounded**: Output always within specified range
- **Documented**: Formula explicitly stated
- **Versioned**: Changes tracked in mapping_version

### 4.1 Trend Mapping (The Current)

```typescript
// Input: IoS-002 trend indicators (EMA cross, MACD, ADX)
// Output: flow_speed, flow_direction

function mapTrendToFlow(
  ema_cross: number,    // -1.0 to +1.0 (bearish to bullish)
  macd_histogram: number,  // normalized
  adx_strength: number  // 0.0 to 1.0
): { speed: number; direction: number } {

  // Flow speed: ADX drives speed (stronger trend = faster flow)
  // Range: 0.1 to 2.0
  const speed = 0.1 + (adx_strength * 1.9);

  // Flow direction: Weighted average of EMA cross and MACD
  // Range: -1.0 to +1.0
  const direction = (ema_cross * 0.6) + (Math.sign(macd_histogram) * 0.4);

  return { speed, direction: clamp(direction, -1, 1) };
}
```

### 4.2 Momentum Mapping (The Pulse)

```typescript
// Input: IoS-002 momentum indicators (RSI, Stochastic, ROC)
// Output: pulse_amplitude, pulse_frequency

function mapMomentumToPulse(
  rsi: number,          // 0-100
  stochastic_k: number, // 0-100
  roc: number           // rate of change, normalized
): { amplitude: number; frequency: number } {

  // Amplitude: How extreme is momentum (distance from neutral)
  // RSI 50 = neutral, extremes (0 or 100) = max amplitude
  const rsi_extreme = Math.abs(rsi - 50) / 50;
  const stoch_extreme = Math.abs(stochastic_k - 50) / 50;
  const amplitude = (rsi_extreme * 0.5) + (stoch_extreme * 0.5);

  // Frequency: How fast is momentum changing
  // Higher ROC absolute value = faster pulse
  const frequency = 0.5 + (Math.abs(roc) * 3.5);

  return {
    amplitude: clamp(amplitude, 0, 1),
    frequency: clamp(frequency, 0.5, 4.0)
  };
}
```

### 4.3 Volatility Mapping (The Weather)

```typescript
// Input: IoS-002 volatility indicators (ATR, BB width, VIX proxy)
// Output: cloud_density, cloud_turbulence, lightning_frequency

function mapVolatilityToWeather(
  atr_percentile: number,    // 0.0 to 1.0 (current ATR vs historical)
  bb_width_percentile: number, // 0.0 to 1.0
  vol_regime: string         // "LOW" | "NORMAL" | "HIGH" | "EXTREME"
): { density: number; turbulence: number; lightning: number } {

  // Cloud density: Average of ATR and BB percentiles
  const density = (atr_percentile * 0.6) + (bb_width_percentile * 0.4);

  // Turbulence: Driven by volatility regime
  const turbulence_map = { LOW: 0.1, NORMAL: 0.3, HIGH: 0.6, EXTREME: 0.9 };
  const turbulence = turbulence_map[vol_regime] || 0.3;

  // Lightning: Only in HIGH or EXTREME, frequency scales with density
  const lightning = vol_regime === "EXTREME" ? density * 0.8 :
                    vol_regime === "HIGH" ? density * 0.3 : 0;

  return {
    density: clamp(density, 0, 1),
    turbulence: clamp(turbulence, 0, 1),
    lightning: clamp(lightning, 0, 1)
  };
}
```

### 4.4 Volume Mapping (The Force)

```typescript
// Input: IoS-002 volume indicators (OBV trend, VWAP deviation, volume ratio)
// Output: particle_density, particle_speed, shockwave_intensity

function mapVolumeToForce(
  volume_ratio: number,     // Current vs average (e.g., 1.5 = 50% above avg)
  obv_momentum: number,     // -1.0 to +1.0
  vwap_deviation: number    // Normalized price vs VWAP
): { density: number; speed: number; shockwave: number } {

  // Particle density: Direct mapping from volume ratio
  // 0.5x volume = 0.25 density, 2x volume = 1.0 density
  const density = clamp((volume_ratio - 0.5) / 1.5, 0, 1);

  // Particle speed: OBV momentum drives speed
  const speed = 0.5 + (Math.abs(obv_momentum) * 2.5);

  // Shockwave: Only on volume spikes (volume_ratio > 2.0)
  const shockwave = volume_ratio > 2.0 ?
    clamp((volume_ratio - 2.0) / 3.0, 0, 1) : 0;

  return {
    density: clamp(density, 0, 1),
    speed: clamp(speed, 0.5, 3.0),
    shockwave: clamp(shockwave, 0, 1)
  };
}
```

### 4.5 Regime Color Mapping

```typescript
function mapRegimeToColors(
  regime: string,
  confidence: number
): VisualProperties["colors"] {

  const palettes = {
    BULL: {
      primary: "#00FF88",      // Vibrant green
      accent: "#88FFCC",       // Light cyan-green
      background: "#0A1F1A",   // Dark green tint
      emission: "#00FF88"
    },
    BEAR: {
      primary: "#FF4466",      // Vibrant red
      accent: "#FF8899",       // Light pink-red
      background: "#1F0A0E",   // Dark red tint
      emission: "#FF4466"
    },
    RANGE: {
      primary: "#4488FF",      // Blue
      accent: "#88BBFF",       // Light blue
      background: "#0A0E1F",   // Dark blue tint
      emission: "#4488FF"
    },
    TRANSITION: {
      primary: "#FFAA00",      // Orange/amber
      accent: "#FFCC66",       // Light amber
      background: "#1F150A",   // Dark amber tint
      emission: "#FFAA00"
    },
    UNKNOWN: {
      primary: "#666666",      // Gray
      accent: "#999999",       // Light gray
      background: "#0F0F0F",   // Dark gray
      emission: "#666666"
    }
  };

  const palette = palettes[regime] || palettes.UNKNOWN;

  // Reduce saturation based on confidence
  // Low confidence = more desaturated
  return applyConfidenceDesaturation(palette, confidence);
}
```

---

## 5. DEFCON Degradation Specification

### 5.1 Degradation Masks

| DEFCON | Fields Populated | Fields Degraded/Null |
|--------|------------------|----------------------|
| GREEN | All fields | None |
| YELLOW | Core animation, colors | particle_density reduced 50%, no lightning |
| ORANGE | Basic flow, regime | All particles null, cloud simplified |
| RED | Static values only | All animation null, colors grayscale |
| BLACK | Null state | All visual fields null |

### 5.2 Degradation Rules

```typescript
function applyDEFCONDegradation(
  vsv: VisualStateVector,
  defcon: string
): VisualStateVector {

  switch (defcon) {
    case "GREEN":
      return vsv; // No changes

    case "YELLOW":
      return {
        ...vsv,
        animation: {
          ...vsv.animation,
          particle_density: vsv.animation.particle_density * 0.5,
          lightning_frequency: 0,
          shockwave_intensity: 0
        },
        events: vsv.events.filter(e => e.severity === "CRITICAL")
      };

    case "ORANGE":
      return {
        ...vsv,
        animation: {
          flow_speed: vsv.animation.flow_speed * 0.7,
          flow_direction: vsv.animation.flow_direction,
          flow_turbulence: 0.1,
          pulse_amplitude: vsv.animation.pulse_amplitude * 0.5,
          pulse_frequency: 1.0, // Fixed slow pulse
          cloud_density: 0.2,
          cloud_turbulence: 0.1,
          particle_density: 0,
          particle_speed: 0,
          camera_shake_amplitude: 0,
          // ... other fields reduced
        },
        events: [] // No cinematics
      };

    case "RED":
      return {
        ...vsv,
        animation: createFrozenState(),
        visuals: {
          ...vsv.visuals,
          ...createGrayscalePalette(),
          overlay_text: "System in Defensive Mode",
          overlay_subtext: `Data Frozen at ${vsv.timestamp}`,
          overlay_opacity: 0.8
        },
        events: []
      };

    case "BLACK":
      return {
        ...vsv,
        animation: null,
        visuals: {
          overlay_text: "System in Lockdown",
          overlay_subtext: "Contact administrator",
          background_color: "#000000",
          overlay_opacity: 1.0
        },
        events: []
      };
  }
}
```

---

## 6. Event Trigger Specifications

### 6.1 Regime Shift Event

**Trigger Conditions:**
- IoS-003 regime changes (BULL→BEAR, BEAR→BULL, etc.)
- Minimum confidence threshold: 0.7

**Visual Response:**
```typescript
const regimeShiftEvent: EventTrigger = {
  event_type: "REGIME_SHIFT",
  severity: "HIGH",
  duration_ms: 10000,
  parameters: {
    from_state: "BULL",
    to_state: "BEAR",
    camera_preset: "REGIME_SHIFT_ZOOM",
    overlay_text: "REGIME SHIFT DETECTED",
    overlay_subtext: "BULL → BEAR"
  }
};
```

### 6.2 Volatility Storm Event

**Trigger Conditions:**
- volatility_intensity > 0.8
- volatility_regime transitions to "EXTREME"

**Visual Response:**
```typescript
const volatilityStormEvent: EventTrigger = {
  event_type: "VOLATILITY_STORM",
  severity: "CRITICAL",
  duration_ms: 8000,
  parameters: {
    magnitude: 0.9,
    camera_preset: "VOLATILITY_SHAKE",
    overlay_text: "VOLATILITY STORM",
    overlay_subtext: "PROCEED WITH CAUTION"
  }
};
```

### 6.3 Volume Surge Event

**Trigger Conditions:**
- volume_strength > 0.9 (top 10% historical)
- volume_ratio > 3.0 (3x average)

**Visual Response:**
```typescript
const volumeSurgeEvent: EventTrigger = {
  event_type: "VOLUME_SURGE",
  severity: "MEDIUM",
  duration_ms: 5000,
  parameters: {
    magnitude: volume_ratio / 5.0, // Normalized
    camera_preset: "VOLUME_PULSE"
  }
};
```

---

## 7. API Endpoints

### 7.1 Current State

```
GET /api/visual/state/{asset_id}

Response: VisualStateVector
```

### 7.2 WebSocket Stream

```
WS /api/visual/stream/{asset_id}

Messages: VisualStateVector (on each tick)
```

### 7.3 Historical States

```
GET /api/visual/history/{asset_id}
  ?from={ISO8601}
  &to={ISO8601}
  &resolution={1m|5m|1h|1d}

Response: VisualStateVector[]
```

### 7.4 Replay Generation

```
POST /api/visual/replay
{
  "asset_id": "BTC-USD",
  "from": "2026-01-01T00:00:00Z",
  "to": "2026-01-02T00:00:00Z",
  "resolution": "5m",
  "include_events": true
}

Response: {
  "replay_id": "uuid",
  "frames": VisualStateVector[],
  "events": EventTrigger[]
}
```

---

## 8. Verification & Audit

### 8.1 Hash Computation

```typescript
function computeStateHash(vsv: VisualStateVector): string {
  // Exclude signature and hash from the hash computation
  const { signature, state_snapshot_hash, ...hashableState } = vsv;

  // Deterministic JSON serialization
  const canonical = JSON.stringify(hashableState, Object.keys(hashableState).sort());

  return sha256(canonical);
}
```

### 8.2 Signature Verification

```typescript
function verifyVSV(vsv: VisualStateVector, publicKey: string): boolean {
  const hash = computeStateHash(vsv);
  return ed25519.verify(vsv.signature, hash, publicKey);
}
```

### 8.3 Audit Log Entry

Every VSV generation MUST log:

```typescript
interface VSVAuditEntry {
  vsv_id: string;
  asset_id: string;
  timestamp: string;
  mapping_version: string;
  ios_002_snapshot_id: string;
  ios_003_snapshot_id: string;
  defcon_level: string;
  state_snapshot_hash: string;
  generated_by: string; // "FINN" or "STIG"
  generation_time_ms: number;
}
```

---

## 9. Consequences

### Positive
- Complete determinism in visual output
- Full audit trail from data to pixel
- Versioned mapping enables A/B testing
- DEFCON degradation is systematic
- Regulatory evidence is trivial to produce

### Negative
- Backend computation overhead
- API response size increases
- Version management complexity
- Requires strict change control

### Mitigations
- Efficient caching strategies
- Differential updates via WebSocket
- Automated version tracking

---

## 10. Signatures

| Role | Signature |
|------|-----------|
| CEO | ✅ APPROVED |
| VEGA | ✅ Compliance Certified |
| STIG | ✅ Technical Authority |
| FINN | ✅ Data Mapping Authority |

---

## 11. Related Documents

- **ADR-013:** Kernel Specification & VEGA Attestation
- **ADR-016:** DEFCON & Circuit Breaker Protocol
- **ADR-022:** Dumb Glass Frontend Architecture
- **ADR-024:** Retail Observer Cinematic Engine

---

# END OF ADR-023 – VISUAL STATE VECTOR SPECIFICATION

Approved for constitutional use within FjordHQ Market System.
