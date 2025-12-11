# ADR-022_2026_PRODUCTION – Dumb Glass Frontend Architecture

**Canonical Version:** 2026.PRODUCTION
**Status:** APPROVED
**Date:** 2025-12-11
**Owner:** STIG (CTO & Runtime Guardian)
**Tier:** Tier-1 – Security & Compliance
**Authority Chain:** ADR-001 → ADR-003 → ADR-016 → ADR-022
**Affects:** All Frontend Applications, Retail Observer, Dashboard, API Gateways
**Prevails Over:** Any frontend implementation that performs client-side calculations

---

## 1. Context

FjordHQ provides market intelligence through visualizations and dashboards.
The frontend layer presents critical risks if not properly constrained:

- **Strategy Leakage**: Client-side calculation logic could expose trading strategies
- **Data Integrity**: Browser-computed values cannot be cryptographically verified
- **Regulatory Exposure**: Unverifiable calculations create compliance liability
- **Consistency Risk**: Different browsers/devices could produce different results
- **Audit Failure**: Client-side logic is not auditable in the same way as server-side

The solution is radical simplification: **the frontend does nothing but display**.

**ADR-022 establishes the "Dumb Glass" doctrine.**
This is FjordHQ's security boundary for all presentation layers.

---

## 2. Decision

FjordHQ adopts the **Dumb Glass Frontend Architecture** where all frontend applications are pure visualization layers with zero computational responsibility.

### Why "Dumb Glass"?

Because intelligent frontends lead to:

- Strategy reverse-engineering by bad actors
- Inconsistent state between clients and server
- Untraceable calculation errors
- Regulatory non-compliance (no audit trail)
- Security vulnerabilities via client-side manipulation
- Split-brain visual states

Dumb Glass solves this by enforcing that:
1. **All numerics come pre-computed and signed from backend**
2. **Frontend only renders, never calculates**
3. **All state is verifiable via cryptographic hash**
4. **No business logic exists in client code**

---

## 3. Dumb Glass Principles

### 3.1 Principle of Zero Computation

The frontend SHALL NOT perform any of the following:

| Forbidden Operation | Example |
|---------------------|---------|
| Indicator calculation | Computing RSI, MACD, EMA locally |
| Statistical operations | Mean, std dev, percentiles |
| Derived values | Percentage changes, ratios |
| Conditional logic | IF price > threshold THEN show alert |
| Aggregation | Summing volumes, averaging prices |
| Interpolation | Filling missing data points |
| Normalization | Scaling values to 0-1 range |

**Exception**: Pure UI calculations (scroll position, animation timing, responsive layout) are permitted.

### 3.2 Principle of Signed State

Every data point displayed MUST include:

```typescript
interface VerifiedDataPoint {
  value: number | string;
  timestamp: string;           // ISO 8601
  state_snapshot_hash: string; // SHA-256 of source state
  signature: string;           // Ed25519 signature from backend
  signer_id: string;           // Which agent/service signed
}
```

The frontend MUST display a verification indicator showing:
- Hash verification status (valid/invalid/unverified)
- Clickable access to full state hash
- Timestamp of last verification

### 3.3 Principle of Backend Authority

The backend is the **single source of truth** for:

| Domain | Backend Provides | Frontend Receives |
|--------|------------------|-------------------|
| Prices | Canonical OHLCV | Pre-formatted display values |
| Indicators | Computed values | Final numbers + labels |
| Regime | Classification result | Enum value (BULL/BEAR/RANGE) |
| DEFCON | Current level | Enum + visual parameters |
| Visual State | Animation parameters | Deterministic mapping values |
| Labels | All text content | Localized strings |

### 3.4 Principle of Strategy Opacity

The frontend SHALL NOT expose:

- Position sizes or directions
- PnL (profit and loss)
- Exposure levels
- Trade history
- Order book intent
- Risk parameters
- Strategy weights
- DSL logic or rules
- Reasoning chains (EC-020/EC-021)

**Permitted**: Market data (public), regime classification (input-side only), indicator values (derived from public data).

---

## 4. Implementation Architecture

### 4.1 Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND (Trusted Zone)                        │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ IoS-001  │───▶│ IoS-002  │───▶│ IoS-003  │───▶│  Visual  │  │
│  │ Assets   │    │Indicators│    │ Regime   │    │  State   │  │
│  └──────────┘    └──────────┘    └──────────┘    │  Vector  │  │
│                                                   └────┬─────┘  │
│                                                        │        │
│  ┌──────────────────────────────────────────────────────┴────┐  │
│  │                  Signature Service (STIG)                  │  │
│  │           Ed25519 sign every outbound payload             │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────┬────────────────────────┘
                                         │ Signed JSON
                                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   FRONTEND (Untrusted Zone)                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                     Dumb Glass Layer                      │  │
│  │  • Receives signed state vector                          │  │
│  │  • Verifies signature (optional, display-only)           │  │
│  │  • Maps values to visual properties (no calculation)     │  │
│  │  • Renders WebGL/DOM elements                            │  │
│  │  • Displays verification indicator                       │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 API Contract

All API endpoints MUST return data in display-ready format:

```typescript
// ❌ FORBIDDEN: Raw data requiring client calculation
{
  "prices": [100, 102, 98, 105, 103],
  "calculate_sma": true,
  "period": 5
}

// ✅ REQUIRED: Pre-computed, signed, display-ready
{
  "sma_value": 101.6,
  "sma_label": "SMA(5): 101.60",
  "trend_direction": "UP",
  "display_color": "#00FF88",
  "state_snapshot_hash": "sha256:abc123...",
  "signature": "ed25519:xyz789...",
  "timestamp": "2026-01-05T12:00:00Z"
}
```

### 4.3 Visual State Vector API

For the Retail Observer Cinematic Engine, backend provides:

```typescript
interface VisualStateVector {
  asset_id: string;
  timestamp: string;

  // Pre-computed animation parameters
  flow_speed: number;        // 0.1 - 2.0
  flow_direction: number;    // -1.0 to +1.0
  pulse_amplitude: number;   // 0.0 - 1.0
  pulse_frequency: number;   // 0.0 - 1.0
  turbulence: number;        // 0.0 - 1.0
  particle_density: number;  // 0.0 - 1.0

  // Pre-computed visual properties
  regime_color_primary: string;   // Hex color
  regime_color_accent: string;    // Hex color
  glow_intensity: number;         // 0.0 - 1.0
  camera_shake_amplitude: number; // 0.0 - 0.1

  // Regime & DEFCON
  regime: "BULL" | "BEAR" | "RANGE" | "TRANSITION" | "UNKNOWN";
  defcon_level: "GREEN" | "YELLOW" | "ORANGE" | "RED" | "BLACK";

  // Verification
  state_snapshot_hash: string;
  signature: string;
}
```

The frontend applies these values directly to shaders/animations without transformation.

---

## 5. DEFCON Integration

### 5.1 Visual Degradation Modes

Backend determines visual capabilities per DEFCON level:

| DEFCON | Visual State Vector Fields | Frontend Behavior |
|--------|----------------------------|-------------------|
| GREEN | All fields populated | Full rendering |
| YELLOW | Reduced particle_density | Simplified effects |
| ORANGE | Minimal fields only | Basic streams only |
| RED | Static values | Frozen display + overlay |
| BLACK | Null state | Black screen + lockdown text |

### 5.2 Overlay Requirements

At DEFCON RED or BLACK, frontend MUST display overlay text provided by backend:

```typescript
interface DEFCONOverlay {
  show_overlay: boolean;
  overlay_text: string;      // "System in Defensive Mode"
  overlay_subtext: string;   // "Data Frozen at 12:00:00 UTC"
  background_opacity: number; // 0.8 for RED, 1.0 for BLACK
}
```

---

## 6. Verification Display Requirements

### 6.1 Hash Indicator

Every Dumb Glass interface MUST display:

```
┌─────────────────────────────────────┐
│  ✓ Verified State                   │
│  Hash: sha256:abc123...             │
│  Signed by: STIG                    │
│  Last update: 12:00:00 UTC          │
│  [Click to verify]                  │
└─────────────────────────────────────┘
```

### 6.2 Audit Trail Access

Clicking the verification indicator MUST show:
- Full state_snapshot_hash
- Signature details
- Link to governance evidence (if available)
- Disclaimer text

---

## 7. Forbidden Patterns

The following code patterns are PROHIBITED in frontend:

```typescript
// ❌ FORBIDDEN: Client-side indicator calculation
const sma = prices.reduce((a, b) => a + b) / prices.length;

// ❌ FORBIDDEN: Conditional logic based on data
if (price > previousPrice * 1.05) showAlert();

// ❌ FORBIDDEN: Derived percentage calculation
const change = ((current - previous) / previous) * 100;

// ❌ FORBIDDEN: Interpolation of missing data
const filled = data.map(d => d ?? interpolate(neighbors));

// ❌ FORBIDDEN: Dynamic threshold computation
const threshold = mean + (2 * stdDev);
```

### 7.1 Permitted Patterns

```typescript
// ✅ PERMITTED: Direct value rendering
<div>{stateVector.sma_label}</div>

// ✅ PERMITTED: Pre-computed color application
<div style={{ color: stateVector.regime_color_primary }} />

// ✅ PERMITTED: Animation parameter pass-through
useFrame(() => {
  mesh.rotation.y += stateVector.flow_speed * 0.01;
});

// ✅ PERMITTED: UI layout calculations
const width = window.innerWidth * 0.8;
```

---

## 8. Compliance & Audit

### 8.1 Code Review Requirements

All frontend code MUST pass review for:
- Zero calculation patterns (see Section 7)
- Proper verification display
- DEFCON overlay compliance
- No strategy-revealing logic

### 8.2 Automated Enforcement

STIG SHALL implement:
- Static analysis rules detecting calculation patterns
- CI/CD gates blocking non-compliant code
- Runtime monitoring for client-side computation attempts

### 8.3 Regulatory Alignment

Dumb Glass architecture ensures:
- **GIPS 2020**: All displayed values traceable to source
- **ISO 42001**: AI outputs clearly marked as backend-derived
- **DORA**: Frontend failure doesn't affect data integrity
- **BCBS-239**: Full lineage from database to pixel

---

## 9. Consequences

### Positive
- Zero strategy leakage risk
- Complete audit trail
- Consistent display across all clients
- Simplified frontend maintenance
- Regulatory compliance by design

### Negative
- Increased backend load
- Network dependency for all updates
- No offline calculation capability
- Higher API traffic volume

### Mitigations
- Efficient caching at API gateway
- WebSocket streams for real-time updates
- Pre-generated static snapshots for demos

---

## 10. Signatures

| Role | Signature |
|------|-----------|
| CEO | ✅ APPROVED |
| VEGA | ✅ Compliance Certified |
| STIG | ✅ Technical Authority |
| LARS | ✅ Strategic Alignment |

---

## 11. Related Documents

- **ADR-001:** System Charter
- **ADR-003:** Institutional Standards & Compliance
- **ADR-016:** DEFCON & Circuit Breaker Protocol
- **ADR-023:** Visual State Vector Specification
- **ADR-024:** Retail Observer Cinematic Engine

---

## 12. Effective Date

This ADR becomes effective immediately upon:
- VEGA compliance certification
- CEO approval
- System registration by STIG
- Frontend audit by CODE

---

# END OF ADR-022 – DUMB GLASS FRONTEND ARCHITECTURE

Approved for constitutional use within FjordHQ Market System.
