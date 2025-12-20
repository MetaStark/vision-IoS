# FCC Phase I System Specification

## FjordHQ Command Center - Glass Wall Observability Layer

**Document ID:** FCC-SPEC-001
**Version:** 1.0.0
**Date:** 2025-12-09
**Authority:** CEO Directive 2026
**Compliance:** ADR-001, ADR-013, ADR-019
**Author:** STIG (CTO)

---

## 1. Executive Summary

This document specifies the Phase I implementation of the FjordHQ Command Center (FCC), a Glass Wall Observability Layer that provides total transparency into the autonomous multi-agent market system without imposing friction on system operations.

**Core Principle:** READ-ONLY observation. All autonomy is preserved. No system behavior modifications.

---

## 2. Architecture Overview

### 2.1 Component Hierarchy

```
FCC (FjordHQ Command Center)
├── FCC_ADR_IOS_OVERVIEW_MODULE
│   ├── ADROverview Component
│   ├── IoSOverview Component
│   ├── AgentActivityPanel Component
│   └── GovernanceDeviations Component
├── FCC_EVENT_SOURCING_SPINE
│   ├── Event Stream Queries
│   ├── Shadow Trade Events
│   ├── Time-Travel Replay Support
│   └── Hash Chain Verification
├── FCC_ENTROPY_COLLECTOR
│   ├── Shannon Entropy Calculator
│   ├── Entropy Thresholds
│   ├── Canary Protocol Implementation
│   └── Entropy Heatmap/Radar Data
└── FCC_ALPHA_GRAPH_ENGINE_SHELL
    ├── Graph Data Structures
    ├── Edge Type Taxonomy
    ├── Ego Network Queries
    └── Graph Statistics
```

### 2.2 Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    PostgreSQL Database                       │
│  fhq_meta | fhq_governance | fhq_data | vision_signals      │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ READ-ONLY
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    FCC Query Layer                           │
│  lib/fcc/queries.ts | event-sourcing.ts | entropy-collector │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    FCC Components                            │
│  ADROverview | IoSOverview | AgentActivity | Deviations     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    CEO Glass Wall View                       │
│               /fcc - FjordHQ Command Center                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Module Specifications

### 3.1 FCC_ADR_IOS_OVERVIEW_MODULE

**Purpose:** CEO's foundation view into all ADRs, IoS modules, agent activity, and governance deviations.

**Components:**

| Component | File | Description |
|-----------|------|-------------|
| ADROverview | `components/fcc/ADROverview.tsx` | ADR registry with status, tier, VEGA attestation |
| IoSOverview | `components/fcc/IoSOverview.tsx` | IoS module cards with governance gates |
| AgentActivityPanel | `components/fcc/AgentActivityPanel.tsx` | Real-time agent heartbeats, DEFCON status |
| GovernanceDeviations | `components/fcc/GovernanceDeviations.tsx` | Active/resolved governance violations |

**Data Sources:**
- `fhq_meta.adr_registry`
- `fhq_meta.ios_registry`
- `fhq_governance.agent_heartbeats`
- `fhq_governance.defcon_state`
- `fhq_governance.asrp_violations`
- `fhq_governance.constitutional_violations`

### 3.2 FCC_EVENT_SOURCING_SPINE

**Purpose:** Backbone for Shadow Ledger parallel reality tracking and time-travel replay.

**File:** `lib/fcc/event-sourcing.ts`

**Capabilities:**
- Event stream querying (24h window)
- Shadow trade event tracking
- Entropy event collection
- Regime transition tracking
- Time-travel replay windows
- Hash chain verification (ADR-011 compliance)

**Key Functions:**
- `getEventStream()` - Query event queue
- `getShadowTradeEvents()` - Shadow Ledger data
- `getReplayWindow()` - Time-travel support
- `verifyHashChain()` - Integrity verification

### 3.3 FCC_ENTROPY_COLLECTOR

**Purpose:** System cognition metrics per CEO Directive Pillar I.

**File:** `lib/fcc/entropy-collector.ts`

**Entropy Dimensions:**
1. Policy Entropy (Agent Decision Confidence)
2. Data Entropy (Signal-to-Noise Ratio)
3. Execution Entropy (Slippage Variance)
4. Network Entropy (Latency/Packet Loss)
5. Shadow Entropy (Shadow Ledger Divergence)

**Thresholds (Table 1 from CEO Directive):**

| Level | Threshold | Color | Action |
|-------|-----------|-------|--------|
| Critical High | ≥4.0 | Red | Kill Switch Prompt |
| High | ≥3.0 | Orange | Shadow Mode Alert |
| Moderate | ≥2.0 | Yellow | Passive Monitor |
| Low | ≥1.0 | Green | Alpha Opportunity |
| Near Zero | ≤0.3 | Blue | Check for Leakage |

**Canary Protocol:** Automatic entropy-based alerting per Section 2.3.

### 3.4 FCC_ALPHA_GRAPH_ENGINE_SHELL

**Purpose:** Causal topology visualization foundation per CEO Directive Pillar III.

**File:** `lib/fcc/alpha-graph-engine.ts`

**Edge Type Taxonomy (Section 4.1):**

| Type | Description | Color | Style |
|------|-------------|-------|-------|
| LEADS | Temporal Precedence | Cyan | Solid + Flow |
| AMPLIFIES | Positive Feedback | Green | Pulsing |
| INVERSE | Negative Correlation | Red | Dashed |
| CORRELATES | Statistical Correlation | Purple | Solid |

**Capabilities:**
- Full graph data retrieval
- Ego network filtering
- Graph statistics computation
- Cluster generation

**Data Sources:**
- `vision_signals.alpha_graph_nodes`
- `vision_signals.alpha_graph_edges`

---

## 4. API Routes

### 4.1 Phase I Routes (Implemented)

| Route | Method | Description |
|-------|--------|-------------|
| `/fcc` | GET | Main FCC Dashboard |

### 4.2 Future Phase Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/fcc/entropy` | GET | Entropy heatmap view |
| `/fcc/shadow` | GET | Shadow Ledger view |
| `/fcc/graph` | GET | Alpha Graph visualization |
| `/fcc/replay` | GET | Time-travel replay |

---

## 5. Security & Compliance

### 5.1 Read-Only Enforcement

All FCC operations are strictly READ-ONLY:
- No INSERT, UPDATE, DELETE operations
- No system state modifications
- No agent command issuance
- No trade execution

### 5.2 ADR Compliance

| ADR | Requirement | Implementation |
|-----|-------------|----------------|
| ADR-001 | Agent authority boundaries | Observed, not modified |
| ADR-011 | Hash chain integrity | Verified via `verifyHashChain()` |
| ADR-013 | Canonical governance | Data sourced from canonical tables |
| ADR-016 | DEFCON protocol | Status displayed, not triggered |
| ADR-018 | ASRP compliance | Violations displayed only |
| ADR-019 | Human interaction layer | CEO view provided |

### 5.3 Data Lineage

Every component displays its data source for full lineage transparency:
- Tooltips show source table
- Headers include schema.table references
- Footer notes data refresh intervals

---

## 6. Performance Specifications

### 6.1 Refresh Intervals

| Data Type | Interval | Rationale |
|-----------|----------|-----------|
| Agent Heartbeats | 10s | Near real-time status |
| ADR/IoS Registry | 60s | Low change frequency |
| Entropy Snapshots | 30s | Balance freshness/load |
| Event Stream | 10s | Critical for monitoring |

### 6.2 Query Optimization

- Connection pooling via `lib/db.ts`
- Indexed queries on timestamp columns
- Limit clauses on all list queries
- Parallel data fetching via `Promise.all()`

---

## 7. Phase I Deliverables Checklist

| Deliverable | Status | Location |
|-------------|--------|----------|
| FCC_PHASE1_SYSTEM_SPEC.md | ✅ | `/FCC_PHASE1_SYSTEM_SPEC.md` |
| FCC_ADR_IOS_OVERVIEW_MODULE | ✅ | `/app/fcc/page.tsx`, `/components/fcc/*` |
| FCC_EVENT_SOURCING_SPINE | ✅ | `/lib/fcc/event-sourcing.ts` |
| FCC_ENTROPY_COLLECTOR v0.1 | ✅ | `/lib/fcc/entropy-collector.ts` |
| FCC_ALPHA_GRAPH_ENGINE_SHELL | ✅ | `/lib/fcc/alpha-graph-engine.ts` |
| FCC_PHASE1_COMPLETION_REPORT.json | ✅ | `/05_GOVERNANCE/PHASE3/` |

---

## 8. Future Phases

### Phase II: "The Brain" (Q2 2026)
- DeepSeek Chain-of-Thought integration
- Entropy metric calculation engine
- Reasoning tree visualization

### Phase III: "The Eye" (Q3 2026)
- Alpha Graph WebGL rendering
- Entropy heatmaps
- Ghost Candle charting

### Phase IV: "The Wall" (Q4 2026)
- Full UI integration
- Glass Wall UX polish
- Stress testing

---

## 9. Approval

**STIG (CTO):** Phase I implementation complete per CEO Directive 2026.

**Status:** READY FOR CEO/CFO REVIEW

---

*Document generated by STIG - System for Technical Implementation & Governance*
*FjordHQ Market System - Vision-IoS 2026*
