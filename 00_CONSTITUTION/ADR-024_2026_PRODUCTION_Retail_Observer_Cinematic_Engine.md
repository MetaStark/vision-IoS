# ADR-024_2026_PRODUCTION – Retail Observer Cinematic Engine (ROCE)

**Canonical Version:** 2026.PRODUCTION
**Status:** APPROVED
**Date:** 2025-12-11
**Owner:** LARS (Strategy) + STIG (Technical) + FINN (Data Mapping)
**Tier:** Tier-1 – Product Architecture
**Authority Chain:** ADR-001 → ADR-016 → ADR-022 → ADR-023 → ADR-024
**Affects:** Retail Observer, Dashboard, Video Generation, Marketing Materials
**Prevails Over:** Any prior visualization specification or mockup

---

## 1. Executive Summary

### 1.1 Mandate

Build the Retail Observer Cinematic Engine (ROCE) – a visual layer that makes IoS-001 → IoS-003 "live" on screen in 2026 AAA game quality, without:
- Leaking strategy
- Violating Dumb Glass (ADR-022)
- Compromising auditability

### 1.2 Deliverables

1. **Live Visuals**: Real-time dashboard for Retail Observer
2. **Video Generation**: Pre-rendered "Market Cinematic" clips for distribution
3. **Audit Evidence**: Frame-to-data linkage for regulatory proof

### 1.3 Quality Standard

Every frame must:
- Look like a cutscene from a 2026 AAA game
- Be driven by actual market data
- Be reconstructible from its Visual State Vector
- Be suitable for BlackRock investor deck screenshots

---

## 2. Visual Design Language

### 2.1 What "2026 Game Quality" Means

| Aspect | Requirement |
|--------|-------------|
| **Lighting** | PBR (Physically Based Rendering), real-time reflections, emissive materials |
| **Depth** | Deep DOF, soft bloom, film grain, tonemapping |
| **VFX** | Flowing energy streams, volumetric fog, particles, caustics |
| **Animation** | Data-driven waves, amplitude/phase from indicators |
| **Camera** | Slow dolly moves, parallax, subtle shake on volatility |
| **Composition** | Foreground/midground/background separation |
| **Frame Quality** | Every paused frame = portfolio-worthy screenshot |

### 2.2 The Four Data Streams

#### 2.2.1 The Current (Trend)

**Visual Form:** Thick, smooth plasma rivers flowing through the scene

| Trend State | Visual Behavior |
|-------------|-----------------|
| Strong Uptrend | Streams flow upward/forward, smooth surface, green tint |
| Strong Downtrend | Streams flow downward, increased turbulence, red tint |
| Weak/Neutral | Slow horizontal flow, blue tint |
| Unstable | Surface noise, caustic distortions |

**Technical Properties:**
- Shader: Flowmap-based with UV distortion
- Particles: Embedded light points moving along flow
- Glow: Emissive edges with bloom

#### 2.2.2 The Pulse (Momentum)

**Visual Form:** Sinusoidal light waves propagating through the scene

| Momentum State | Visual Behavior |
|----------------|-----------------|
| High Positive | Large amplitude, fast frequency, upward bias |
| High Negative | Large amplitude, fast frequency, downward bias |
| Extreme | Sparks ejected from wave peaks |
| Neutral | Low amplitude, slow oscillation |

**Technical Properties:**
- Shader: Animated sine waves with fresnel glow
- Particles: Spark bursts at amplitude peaks
- Sound sync: Optional audio pulse matching

#### 2.2.3 The Weather (Volatility)

**Visual Form:** Volumetric fog/clouds surrounding the streams

| Volatility State | Visual Behavior |
|------------------|-----------------|
| Low | Calm, thin, nearly transparent wisps |
| Normal | Gentle movement, subtle turbulence |
| High | Thick swirling clouds, dark undertones |
| Extreme | Violent turbulence, lightning effects, glitch artifacts |

**Technical Properties:**
- Shader: Raymarched volumetrics
- Particles: Lightning sprites, dust motes
- Post-process: Glitch shader at extreme levels

#### 2.2.4 The Force (Volume)

**Visual Form:** Energy channel with particles flowing through

| Volume State | Visual Behavior |
|--------------|-----------------|
| Low | Few sparse particles, dim channel |
| Normal | Steady particle stream, moderate glow |
| High | Dense particle river, bright channel |
| Spike | Shockwave effect, camera shake |

**Technical Properties:**
- Particles: GPU instanced for density
- Channel: Emissive tube geometry
- Effects: Screen-space shockwaves

---

## 3. Scene Layout Specification

### 3.1 Spatial Composition

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          BACKGROUND (Z: -50 to -20)                      │
│                    Datacenter environment, server racks                  │
│                    Subtle fog, ambient occlusion                        │
├─────────────────────────────────────────────────────────────────────────┤
│                          MIDGROUND (Z: -20 to 0)                         │
│                                                                          │
│  ┌──────────┐         ┌──────────────┐         ┌──────────────────┐    │
│  │          │         │              │         │   STREAM 1       │    │
│  │  IoS-001 │────────▶│   IoS-002    │────────▶│   STREAM 2       │    │
│  │  Assets  │  cables │   REACTOR    │  energy │   STREAM 3       │    │
│  │  Grid    │         │   CORE       │  flows  │   STREAM 4       │    │
│  │          │         │              │         │                  │    │
│  └──────────┘         └──────────────┘         └──────────────────┘    │
│                                                                          │
│      LEFT                 CENTER                    RIGHT                │
├─────────────────────────────────────────────────────────────────────────┤
│                          FOREGROUND (Z: 0 to +10)                        │
│               UI panels, labels, verification indicators                 │
│               Depth blur, subtle lens effects                           │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 IoS-001: Asset Compliance Grid (Left)

**Purpose:** Visualize that assets and contexts are "locked in" and compliant.

**Visual Design:**
- 3D node graph with spherical nodes
- Connecting lines pulse with data flow
- Nodes glow when data is fresh
- Subtle rotation animation (very slow)

**Data Binding:**
- Node count = number of active assets
- Node brightness = data freshness
- Connection pulse = data flow rate

### 3.3 IoS-002: Indicator Engine Core (Center)

**Purpose:** The "heart" where all indicators converge.

**Visual Design:**
- Central reactor/sphere geometry
- Cables from IoS-001 feed into core
- Energy streams emit from core to right
- Periodic core pulse synchronized with momentum_strength

**Data Binding:**
- Core pulse rate = global momentum
- Core glow intensity = regime confidence
- Core color = regime palette
- Rotation speed = market activity

### 3.4 Signal Generation: Four Streams (Right)

**Purpose:** The visual representation of each data dimension.

**Layout:**
```
   TREND (The Current)      ═══════════════▶  Top stream, green
   MOMENTUM (The Pulse)     ≋≋≋≋≋≋≋≋≋≋≋≋≋≋▶  Upper-mid, cyan
   VOLATILITY (The Weather) ░░░░░░░░░░░░░░▶  Lower-mid, purple
   VOLUME (The Force)       ●●●●●●●●●●●●●●▶  Bottom stream, green
```

**UI Labels:**
- Each stream has floating label panel
- Labels include indicator sources (e.g., "TREND (The Current) // EMA, MACD")
- Labels animate in/out based on camera focus

### 3.5 Background: Datacenter Environment

**Purpose:** Ground the visualization in infrastructure reality.

**Visual Design:**
- Server rack silhouettes
- Subtle running lights
- Fog/haze for depth
- Non-intrusive, desaturated

**Animation:**
- Very slow ambient movement
- No attention-grabbing elements
- Reacts slightly to DEFCON level

---

## 4. Camera System Specification

### 4.1 Default Behavior

| Mode | Behavior | Duration |
|------|----------|----------|
| **Orbit** | Slow rotation around IoS-002 | 10-20 second period |
| **Idle** | Gentle float with parallax | Continuous |
| **Focus** | Dolly toward active element | On event trigger |

### 4.2 Camera Rules

1. **Maximum one movement at a time** – no combined dolly+pan+zoom
2. **No cuts faster than 3 seconds** in calm markets
3. **Minimum cut duration 0.5 seconds** even in high intensity
4. **Smooth easing** – all movements use ease-in-out curves
5. **Preserve composition** – hero elements always in frame

### 4.3 Event-Triggered Camera

| Event | Camera Response |
|-------|-----------------|
| Regime Shift | Zoom to IoS-002 core, hold 2s, pull back |
| Volatility Storm | Slight shake, pull back to wide shot |
| Volume Surge | Quick push toward Force channel, pulse back |
| DEFCON Change | Dramatic slowdown, hold on status panel |

### 4.4 Camera Presets (TypeScript)

```typescript
const CameraPresets = {
  ORBIT_DEFAULT: {
    type: "orbit",
    target: [0, 0, 0],      // IoS-002 center
    radius: 15,
    speed: 0.01,            // radians/frame
    height: 3,
    tilt: -10               // degrees
  },

  REGIME_SHIFT_ZOOM: {
    type: "dolly",
    duration: 3000,
    from: { position: [0, 3, 15], lookAt: [0, 0, 0] },
    to: { position: [0, 1, 6], lookAt: [0, 0, -2] },
    easing: "easeInOutCubic",
    hold: 2000,
    reverse: true
  },

  VOLATILITY_SHAKE: {
    type: "shake",
    amplitude: 0.05,
    frequency: 8,
    duration: 2000,
    decay: 0.8
  },

  VOLUME_PULSE: {
    type: "dolly",
    duration: 1500,
    target: [8, 0, 0],      // Force channel position
    pushDistance: 3,
    easing: "easeOutElastic"
  }
};
```

---

## 5. Post-Processing Stack

### 5.1 Effect Chain

```
Scene Render
    │
    ▼
┌─────────────────┐
│  Depth of Field │  Focus on IoS-002, blur foreground/background
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     Bloom       │  Emissive glow, regime-tinted
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Color Grading   │  Regime-based LUT
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Vignette     │  Subtle edge darkening
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Film Grain    │  Subtle noise for cinema feel
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Chromatic Aber. │  Very subtle, on volatility only
└────────┬────────┘
         │
         ▼
Final Output
```

### 5.2 Effect Parameters by Regime

| Effect | BULL | BEAR | RANGE | TRANSITION | UNKNOWN |
|--------|------|------|-------|------------|---------|
| Bloom Intensity | 0.6 | 0.5 | 0.4 | 0.7 | 0.2 |
| Bloom Tint | Green | Red | Blue | Orange | Gray |
| Vignette | 0.2 | 0.3 | 0.2 | 0.25 | 0.4 |
| Film Grain | 0.02 | 0.03 | 0.02 | 0.04 | 0.05 |
| Saturation | 1.1 | 1.0 | 0.9 | 1.0 | 0.5 |
| Contrast | 1.1 | 1.15 | 1.0 | 1.1 | 0.9 |

### 5.3 DEFCON Effect Modifications

| DEFCON | Effect Changes |
|--------|----------------|
| GREEN | Standard effects |
| YELLOW | Reduce bloom 20%, disable film grain |
| ORANGE | Desaturate 30%, reduce all effects 50% |
| RED | Grayscale, freeze effects, add scan lines |
| BLACK | Full black with subtle static noise |

---

## 6. Event Cinematics Specification

### 6.1 "Daily Market Pulse" (15 seconds)

**Purpose:** Daily summary video for social/marketing

**Storyboard:**

| Time | Scene | Camera | Effects | Overlay |
|------|-------|--------|---------|---------|
| 0-3s | Intro | Dolly in to IoS-002 | Low light, building bloom | "TODAY'S MARKET PULSE – BTC-USD" |
| 3-7s | Activation | Hold on streams | Streams fill with color sequentially | Stream labels appear |
| 7-12s | Intensity | Orbit to side view | Full effects based on day's data | Regime badge, key metrics |
| 12-15s | Outro | Pull back wide | Effects settle | FjordHQ logo + disclaimer |

### 6.2 "Regime Shift Alert" (10 seconds)

**Purpose:** Rare event notification when regime changes

**Storyboard:**

| Time | Scene | Camera | Effects | Overlay |
|------|-------|--------|---------|---------|
| 0-3s | Normal state | Idle orbit | Current regime colors | None |
| 3-3.5s | Freeze | Stop all motion | Dim lights 50% | None |
| 3.5-5s | Transition | Zoom to core | Core color shift animation | "REGIME SHIFT DETECTED" |
| 5-8s | New state | Hold on core | New regime colors flood scene | "BULL → BEAR" (or reverse) |
| 8-10s | Resolution | Pull back | Afterglow effect | Regime badge updated |

### 6.3 "Volatility Storm" (8 seconds)

**Purpose:** Alert when volatility spikes to extreme

**Storyboard:**

| Time | Scene | Camera | Effects | Overlay |
|------|-------|--------|---------|---------|
| 0-2s | Building | Hold wide | Weather clouds thickening | None |
| 2-5s | Storm | Pull back + shake | Lightning, turbulence max, glitch | "VOLATILITY STORM" |
| 5-6s | Peak | Intense shake | Flash effects | "PROCEED WITH CAUTION" |
| 6-8s | Settling | Stabilize | Effects gradually calm | Volatility metric badge |

---

## 7. Technical Architecture

### 7.1 Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **3D Engine** | Three.js + React Three Fiber | Web-native, React integration |
| **Shaders** | GLSL via drei/shaderMaterial | Custom effects, performance |
| **Post-Processing** | @react-three/postprocessing | Efficient effect stack |
| **Particles** | drei Points + custom shaders | GPU instancing for density |
| **State Management** | Zustand | Lightweight, React-friendly |
| **WebSocket** | Supabase Realtime | Existing infrastructure |
| **Video Export** | CCapture.js | Frame-accurate capture |

### 7.2 Directory Structure

```
dashboard-2026/
├── app/
│   ├── cinematic/
│   │   ├── page.tsx              # Main cinematic view
│   │   └── [asset]/page.tsx      # Asset-specific view
│   └── api/
│       └── visual/
│           ├── state/route.ts    # Current VSV
│           ├── stream/route.ts   # WebSocket stream
│           └── history/route.ts  # Historical VSV
│
├── engine/
│   ├── core/
│   │   ├── CinematicCanvas.tsx   # Main R3F canvas
│   │   ├── SceneManager.tsx      # Scene composition
│   │   ├── StateProvider.tsx     # VSV state context
│   │   └── types.ts              # TypeScript interfaces
│   │
│   ├── components/
│   │   ├── IoS001AssetGrid.tsx   # Asset compliance grid
│   │   ├── IoS002Core.tsx        # Indicator reactor core
│   │   ├── streams/
│   │   │   ├── TheCurrent.tsx    # Trend stream
│   │   │   ├── ThePulse.tsx      # Momentum stream
│   │   │   ├── TheWeather.tsx    # Volatility cloud
│   │   │   └── TheForce.tsx      # Volume channel
│   │   ├── environment/
│   │   │   ├── Datacenter.tsx    # Background environment
│   │   │   └── Cables.tsx        # Connecting cables
│   │   └── ui/
│   │       ├── StreamLabels.tsx  # Floating labels
│   │       ├── RegimeBadge.tsx   # Regime indicator
│   │       └── HashVerifier.tsx  # Verification display
│   │
│   ├── shaders/
│   │   ├── flow.vert/frag        # Trend stream shader
│   │   ├── pulse.vert/frag       # Momentum wave shader
│   │   ├── volumetric.vert/frag  # Weather cloud shader
│   │   └── particle.vert/frag    # Volume particles shader
│   │
│   ├── effects/
│   │   ├── PostProcessing.tsx    # Effect stack composition
│   │   ├── BloomEffect.tsx       # Custom bloom with regime tint
│   │   └── GlitchEffect.tsx      # Volatility glitch effect
│   │
│   ├── camera/
│   │   ├── CinematicCamera.tsx   # Camera controller
│   │   ├── CameraPresets.ts      # Preset definitions
│   │   └── CameraPath.tsx        # Spline-based paths
│   │
│   ├── events/
│   │   ├── EventManager.tsx      # Event detection & dispatch
│   │   ├── RegimeShift.tsx       # Regime shift cinematic
│   │   ├── VolatilityStorm.tsx   # Volatility storm cinematic
│   │   └── VolumeSurge.tsx       # Volume surge cinematic
│   │
│   └── defcon/
│       ├── DEFCONOverlay.tsx     # Lockdown overlays
│       └── degradation.ts        # Visual degradation logic
│
├── lib/
│   ├── visual-state.ts           # VSV fetching & validation
│   ├── signature.ts              # Ed25519 verification
│   └── recording.ts              # CCapture.js wrapper
│
└── public/
    ├── textures/                 # Environment textures
    ├── models/                   # 3D model assets
    └── luts/                     # Color grading LUTs
```

### 7.3 Component Hierarchy

```
<CinematicCanvas>
  <StateProvider>
    <SceneManager>
      <!-- Background Layer -->
      <Datacenter />

      <!-- Midground Layer -->
      <IoS001AssetGrid position={[-8, 0, 0]} />
      <Cables from="ios001" to="ios002" />
      <IoS002Core position={[0, 0, 0]} />
      <Cables from="ios002" to="streams" />

      <!-- Streams -->
      <TheCurrent position={[6, 2, 0]} />
      <ThePulse position={[6, 0.7, 0]} />
      <TheWeather position={[6, -0.7, 0]} />
      <TheForce position={[6, -2, 0]} />

      <!-- UI Layer -->
      <StreamLabels />
      <RegimeBadge />

      <!-- Camera -->
      <CinematicCamera />
    </SceneManager>

    <!-- Post-Processing -->
    <PostProcessing />

    <!-- Event System -->
    <EventManager />

    <!-- DEFCON Overlay -->
    <DEFCONOverlay />
  </StateProvider>
</CinematicCanvas>
```

---

## 8. Performance Requirements

### 8.1 Target Performance

| Metric | Live Dashboard | Video Export |
|--------|----------------|--------------|
| Resolution | 1920x1080 | 3840x2160 (4K) |
| Frame Rate | 60 FPS | 60 FPS |
| GPU Memory | < 2GB | < 4GB |
| Load Time | < 3s | N/A |
| Network | < 100KB/s | N/A |

### 8.2 Optimization Strategies

1. **Level of Detail (LOD)**: Reduce particle count at distance
2. **Frustum Culling**: Don't render off-screen elements
3. **Instancing**: GPU instance all particles
4. **Texture Atlas**: Combine small textures
5. **Shader LOD**: Simplified shaders on lower-end devices
6. **Deferred Rendering**: For complex lighting

### 8.3 DEFCON Performance Scaling

| DEFCON | Particles | Effects | Quality |
|--------|-----------|---------|---------|
| GREEN | 100% | Full | Max |
| YELLOW | 50% | Reduced | High |
| ORANGE | 25% | Minimal | Medium |
| RED | 0% | Static | Low |
| BLACK | 0% | None | Minimal |

---

## 9. Compliance & Governance

### 9.1 ADR-022 Compliance Checklist

- [ ] No client-side indicator calculations
- [ ] All visual parameters from signed VSV
- [ ] Hash verification display visible
- [ ] No strategy-revealing elements
- [ ] DEFCON overlay implemented

### 9.2 Audit Requirements

Every rendered frame must be linkable to:
1. Visual State Vector ID
2. IoS-002 snapshot ID
3. IoS-003 snapshot ID
4. DEFCON level at render time
5. Mapping function version

### 9.3 Disclaimer Requirements

All public-facing renders MUST include:
```
"Data from canonical IoS-002/003 – Not investment advice"
"FjordHQ Market Intelligence System"
```

---

## 10. Delivery Phases

### Phase 1: Foundation
- [ ] Engine scaffold (Three.js + R3F)
- [ ] VSV API integration
- [ ] Basic scene layout
- [ ] Single stream visualization (The Current)

### Phase 2: Full Streams
- [ ] All four streams implemented
- [ ] IoS-001 and IoS-002 components
- [ ] Basic camera system
- [ ] DEFCON degradation

### Phase 3: Polish
- [ ] Full post-processing stack
- [ ] Event cinematics
- [ ] Camera presets
- [ ] Performance optimization

### Phase 4: Production
- [ ] Video export capability
- [ ] Retail Observer UI integration
- [ ] Documentation
- [ ] Load testing

---

## 11. Signatures

| Role | Signature | Responsibility |
|------|-----------|----------------|
| CEO | ✅ APPROVED | Strategic mandate |
| LARS | ✅ APPROVED | Visual design authority |
| STIG | ✅ APPROVED | Technical implementation |
| FINN | ✅ APPROVED | Data mapping accuracy |
| VEGA | ✅ APPROVED | Compliance certification |

---

## 12. Related Documents

- **ADR-001:** System Charter
- **ADR-016:** DEFCON & Circuit Breaker Protocol
- **ADR-022:** Dumb Glass Frontend Architecture
- **ADR-023:** Visual State Vector Specification

---

# END OF ADR-024 – RETAIL OBSERVER CINEMATIC ENGINE

Approved for constitutional use within FjordHQ Market System.
