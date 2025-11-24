# PHASE 3 ORCHESTRATOR PLAN

**Document ID:** HC-CODE-PHASE3-ORCH-20251124
**Authority:** LARS – Chief Strategy Officer (Authorization: HC-LARS-PHASE3-OPEN-20251124)
**Phase:** Phase 3 — System Expansion & Autonomy Development
**Baseline Protection:** Gold Baseline v1.0 (commit `11f357d`) remains immutable
**Status:** DRAFT

---

## EXECUTIVE SUMMARY

This document defines the **Phase 3 Orchestrator** expansion plan, detailing new cycle steps, decision layers, and coordination logic. Phase 3 orchestrator operates **in parallel** to the frozen Phase 2 Gold Baseline orchestrator, enabling autonomous intelligence expansion without interfering with production operations.

**Key Design Principles:**
1. **Parallel Execution:** Phase 2 and Phase 3 orchestrators run independently
2. **No Shared State:** Separate databases, separate cost tracking, separate attestations
3. **Enhanced Decision-Making:** Multi-tier decision flow (5 tiers, 25 steps)
4. **Observability First:** Real-time cycle visibility, agent traceability, performance metrics

---

## 1. ORCHESTRATOR ARCHITECTURE OVERVIEW

### 1.1 Dual-Orchestrator Model

```
┌─────────────────────────────────────────────────────────────┐
│                     VISION-IOS SYSTEM                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌───────────────────────┐   ┌───────────────────────┐    │
│  │  PHASE 2 ORCHESTRATOR │   │  PHASE 3 ORCHESTRATOR │    │
│  │   (Gold Baseline)     │   │    (Expansion)        │    │
│  │   ✅ FROZEN            │   │    🟡 DEVELOPMENT      │    │
│  └───────────────────────┘   └───────────────────────┘    │
│            │                            │                   │
│            ├────────────────────────────┤                   │
│            │    SHARED COMPONENTS       │                   │
│            │    - LINE (Data)           │                   │
│            │    - VEGA (Attestation)    │                   │
│            └────────────────────────────┘                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Orchestrator Comparison

| Attribute | Phase 2 Orchestrator | Phase 3 Orchestrator |
|-----------|----------------------|----------------------|
| **Status** | ✅ FROZEN (Production) | 🟡 DEVELOPMENT |
| **Cycle Steps** | 10 steps | 25 steps (5 tiers) |
| **Decision Layers** | Single layer (Tier-2 summary) | Multi-layer (Tiers 1-5) |
| **Agents** | FINN, STIG, LINE, VEGA | FINN+, STIG+, LINE+, VEGA+ (extended) |
| **Cost Ceiling** | $0.05/summary (ADR-012) | TBD (ADR-013) |
| **Determinism** | ≥95% | ≥90% (lower threshold for ML) |
| **Database** | `fhq_production` schema | `fhq_phase3` schema |
| **Attestation** | VEGA weekly (Phase 2) | VEGA weekly (Phase 3) |

---

## 2. PHASE 3 ORCHESTRATOR — MULTI-TIER DECISION FLOW

### 2.1 Overview

Phase 3 orchestrator implements a **5-tier decision flow** with **25 cycle steps**, enabling:
- Enhanced context gathering (Tier 1)
- Advanced analytical reasoning (Tier 2)
- Decision-making layer (Tier 3)
- Execution feasibility assessment (Tier 4)
- Reporting and reconciliation (Tier 5)

### 2.2 Tier 1: Enhanced Context Gathering (Steps 1-5)

**Objective:** Gather comprehensive market context across multiple data sources and timeframes

| Step | Agent | Action | Output | Signature Required |
|------|-------|--------|--------|-------------------|
| **1** | LINE+ | Ingest multi-interval OHLCV (1m, 5m, 15m, 1d) | OHLCV time-series | ✅ Ed25519 |
| **2** | LINE+ | Ingest order book data (Level 2) | Order book snapshot | ✅ Ed25519 |
| **3** | LINE+ | Ingest real-time news feeds (Twitter, Reddit, Bloomberg) | News articles + sentiment | ✅ Ed25519 |
| **4** | FINN+ | Historical context retrieval (30d/90d/1y) | Historical price/news data | ✅ Ed25519 |
| **5** | FINN+ | Cross-asset correlation analysis (BTC vs ETH, S&P 500) | Correlation matrix | ✅ Ed25519 |

**Tier 1 Success Criteria:**
- All data sources retrieved successfully
- Data quality passes STIG+ validation (99.9% completeness)
- OHLCV latency <100ms, news feed latency <5s
- Cross-asset correlation computed with ≥95% determinism

**Tier 1 Cost Estimate:** $0.01 per cycle (data ingestion + historical retrieval)

### 2.3 Tier 2: Advanced Analysis (Steps 6-10)

**Objective:** Perform causal inference, regime classification, and multi-asset context synthesis

| Step | Agent | Action | Output | Signature Required |
|------|-------|--------|--------|-------------------|
| **6** | FINN+ | Causal inference analysis (news → price causality) | Causal graph | ✅ Ed25519 |
| **7** | FINN+ | Regime classification (bull/bear/sideways) | Regime label + confidence | ✅ Ed25519 |
| **8** | FINN+ | Multi-asset context synthesis | Cross-asset narrative | ✅ Ed25519 |
| **9** | STIG+ | Validate causal reasoning (logic consistency check) | Validation result (PASS/FAIL) | ✅ Ed25519 |
| **10** | STIG+ | Validate regime classification (historical accuracy check) | Validation result (PASS/FAIL) | ✅ Ed25519 |

**Tier 2 Success Criteria:**
- Causal inference graph identifies ≥3 causal relationships
- Regime classification confidence ≥80%
- STIG+ validates causal reasoning with 100% consistency check
- All outputs maintain ≥90% determinism (ML model outputs)

**Tier 2 Cost Estimate:** $0.05 per cycle (LLM-based causal inference + regime classification)

### 2.4 Tier 3: Decision Layer (Steps 11-15)

**Objective:** Generate pre-trade analysis, risk quantification, and position sizing recommendations

| Step | Agent | Action | Output | Signature Required |
|------|-------|--------|--------|-------------------|
| **11** | FINN+ | Pre-trade analysis (if high CDS detected, CDS ≥ 0.65) | Trade recommendation (BUY/SELL/HOLD) | ✅ Ed25519 |
| **12** | FINN+ | Risk quantification (VaR, Expected Shortfall) | Risk metrics | ✅ Ed25519 |
| **13** | FINN+ | Position sizing recommendation (based on risk tolerance) | Position size (BTC amount) | ✅ Ed25519 |
| **14** | STIG+ | Validate pre-trade analysis (logic + risk checks) | Validation result (PASS/FAIL) | ✅ Ed25519 |
| **15** | STIG+ | Validate risk quantification (consistency with market data) | Validation result (PASS/FAIL) | ✅ Ed25519 |

**Tier 3 Success Criteria:**
- Pre-trade analysis only generated if CDS ≥ 0.65 (high dissonance)
- Risk metrics (VaR, ES) within historical volatility bounds
- Position sizing respects risk tolerance (e.g., max 2% portfolio risk per trade)
- STIG+ validates all recommendations with 100% logic consistency

**Tier 3 Cost Estimate:** $0.10 per cycle (advanced LLM-based decision-making)

**Tier 3 Conditional Execution:**
- If CDS < 0.65: Skip steps 11-15 (no pre-trade analysis needed)
- If CDS ≥ 0.65: Execute steps 11-15 (generate trade recommendation)

### 2.5 Tier 4: Execution Feasibility (Steps 16-20)

**Objective:** Assess execution feasibility, estimate slippage and market impact

| Step | Agent | Action | Output | Signature Required |
|------|-------|--------|--------|-------------------|
| **16** | LINE+ | Execution feasibility check (liquidity, slippage estimation) | Feasibility report | ✅ Ed25519 |
| **17** | LINE+ | Market impact estimation (price impact of position size) | Impact estimate (%) | ✅ Ed25519 |
| **18** | STIG+ | Validate execution feasibility (check against order book) | Validation result (PASS/FAIL) | ✅ Ed25519 |
| **19** | FINN+ | Final decision synthesis (integrate all tiers) | Final recommendation | ✅ Ed25519 |
| **20** | VEGA+ | Phase 3 attestation (ADR compliance, signature verification) | Attestation (GRANTED/DENIED) | ✅ Ed25519 |

**Tier 4 Success Criteria:**
- Execution feasibility check confirms sufficient liquidity (slippage <1%)
- Market impact estimate within acceptable bounds (<0.5% price impact)
- STIG+ validates feasibility against real order book data
- VEGA+ attestation granted (100% ADR compliance)

**Tier 4 Cost Estimate:** $0.02 per cycle (order book analysis + validation)

### 2.6 Tier 5: Reporting & Reconciliation (Steps 21-25)

**Objective:** Store analysis, reconcile agent outputs, detect anomalies, complete cycle

| Step | Agent | Action | Output | Signature Required |
|------|-------|--------|--------|-------------------|
| **21** | LINE+ | Store Phase 3 analysis in database (`fhq_phase3` schema) | Database record | ✅ Ed25519 |
| **22** | VEGA+ | Cross-agent reconciliation (verify output consistency) | Reconciliation report | ✅ Ed25519 |
| **23** | VEGA+ | Economic safety check (Phase 3 costs within ADR-013) | Cost compliance (PASS/FAIL) | ✅ Ed25519 |
| **24** | VEGA+ | Anomaly detection (drift from expected behavior) | Anomaly report | ✅ Ed25519 |
| **25** | VEGA+ | Phase 3 cycle completion | Cycle summary | ✅ Ed25519 |

**Tier 5 Success Criteria:**
- All analysis stored in `fhq_phase3` schema (separate from Phase 2)
- Cross-agent reconciliation confirms no output conflicts
- Economic safety check passes (Phase 3 costs ≤ ADR-013 caps)
- Anomaly detection reports any drift from baseline behavior

**Tier 5 Cost Estimate:** $0.01 per cycle (database storage + reconciliation)

---

## 3. PHASE 3 CYCLE EXECUTION FLOW

### 3.1 Full Cycle Diagram

```
┌───────────────────────────────────────────────────────────────┐
│ PHASE 3 ORCHESTRATOR CYCLE (25 Steps)                        │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  TIER 1: Enhanced Context Gathering (Steps 1-5)              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ 1. LINE+: Multi-interval OHLCV                          │ │
│  │ 2. LINE+: Order book (Level 2)                          │ │
│  │ 3. LINE+: Real-time news feeds                          │ │
│  │ 4. FINN+: Historical context retrieval                  │ │
│  │ 5. FINN+: Cross-asset correlation                       │ │
│  └─────────────────────────────────────────────────────────┘ │
│                          │                                    │
│                          ▼                                    │
│  TIER 2: Advanced Analysis (Steps 6-10)                      │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ 6. FINN+: Causal inference                              │ │
│  │ 7. FINN+: Regime classification                         │ │
│  │ 8. FINN+: Multi-asset context synthesis                 │ │
│  │ 9. STIG+: Validate causal reasoning                     │ │
│  │ 10. STIG+: Validate regime classification               │ │
│  └─────────────────────────────────────────────────────────┘ │
│                          │                                    │
│                          ▼                                    │
│  TIER 3: Decision Layer (Steps 11-15) [CONDITIONAL]          │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ If CDS ≥ 0.65:                                          │ │
│  │   11. FINN+: Pre-trade analysis                         │ │
│  │   12. FINN+: Risk quantification                        │ │
│  │   13. FINN+: Position sizing                            │ │
│  │   14. STIG+: Validate pre-trade analysis                │ │
│  │   15. STIG+: Validate risk quantification               │ │
│  │ Else: Skip to Tier 4                                    │ │
│  └─────────────────────────────────────────────────────────┘ │
│                          │                                    │
│                          ▼                                    │
│  TIER 4: Execution Feasibility (Steps 16-20)                 │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ 16. LINE+: Execution feasibility check                  │ │
│  │ 17. LINE+: Market impact estimation                     │ │
│  │ 18. STIG+: Validate execution feasibility               │ │
│  │ 19. FINN+: Final decision synthesis                     │ │
│  │ 20. VEGA+: Phase 3 attestation                          │ │
│  └─────────────────────────────────────────────────────────┘ │
│                          │                                    │
│                          ▼                                    │
│  TIER 5: Reporting & Reconciliation (Steps 21-25)            │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ 21. LINE+: Store Phase 3 analysis                       │ │
│  │ 22. VEGA+: Cross-agent reconciliation                   │ │
│  │ 23. VEGA+: Economic safety check                        │ │
│  │ 24. VEGA+: Anomaly detection                            │ │
│  │ 25. VEGA+: Phase 3 cycle completion                     │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

### 3.2 Cycle Execution Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Cycle Frequency** | Configurable (1h, 4h, 1d) | Depends on data freshness and decision horizon |
| **Cycle Timeout** | 300 seconds (5 minutes) | Prevent hung cycles from blocking orchestrator |
| **Conditional Execution** | Tier 3 (steps 11-15) only if CDS ≥ 0.65 | Cost optimization: skip decision layer if no dissonance |
| **Parallel Steps** | None (sequential execution) | Maintain determinism and debugging ease |
| **Retry Logic** | 3 retries per step, exponential backoff | Handle transient failures (API timeouts, network issues) |
| **Failure Handling** | Halt cycle on critical failure, alert VEGA | Ensure no incomplete cycles |

### 3.3 Cycle Cost Breakdown

| Tier | Cost Estimate | Conditional | Total Cost Range |
|------|---------------|-------------|------------------|
| **Tier 1** | $0.01 | Always executed | $0.01 |
| **Tier 2** | $0.05 | Always executed | $0.05 |
| **Tier 3** | $0.10 | Only if CDS ≥ 0.65 | $0.00 - $0.10 |
| **Tier 4** | $0.02 | Always executed | $0.02 |
| **Tier 5** | $0.01 | Always executed | $0.01 |
| **Total** | | | **$0.09 - $0.19 per cycle** |

**Cost Optimization:**
- Low dissonance cycles (CDS < 0.65): $0.09 per cycle
- High dissonance cycles (CDS ≥ 0.65): $0.19 per cycle

**ADR-013 Proposal:**
- **Per-cycle ceiling:** $0.25 (conservative buffer)
- **Daily budget cap:** $1,000 (assuming ~100 cycles/day max)
- **Daily rate limit:** 100 cycles/day

---

## 4. PHASE 2 vs PHASE 3 COORDINATION

### 4.1 Parallel Execution Model

**Key Principle:** Phase 2 and Phase 3 orchestrators run **independently** with **no shared state**.

```
┌───────────────────────────────────────────────────────────────┐
│                    PARALLEL ORCHESTRATORS                     │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  Phase 2 Orchestrator              Phase 3 Orchestrator      │
│  ┌─────────────────────┐           ┌─────────────────────┐   │
│  │ Gold Baseline v1.0  │           │ Expansion           │   │
│  │ 10 steps            │           │ 25 steps (5 tiers)  │   │
│  │ $0.048/cycle        │           │ $0.09-$0.19/cycle   │   │
│  │ ≥95% determinism    │           │ ≥90% determinism    │   │
│  └─────────────────────┘           └─────────────────────┘   │
│           │                                  │                │
│           │                                  │                │
│           ├──────────────┬───────────────────┤                │
│           │              │                   │                │
│           ▼              ▼                   ▼                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ fhq_production │  │ LINE Data   │  │ fhq_phase3   │          │
│  │ (Phase 2 DB)│  │ (Shared)    │  │ (Phase 3 DB) │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

### 4.2 Shared Components

**LINE (Data Ingestion):**
- LINE agent provides data to **both** Phase 2 and Phase 3 orchestrators
- Phase 2: Uses 1-day OHLCV and Serper news (frozen, unchanged)
- Phase 3: Uses multi-interval OHLCV, order book, real-time news (new extensions)
- **No conflict:** Phase 3 extensions don't modify Phase 2 data pathways

**VEGA (Attestation):**
- VEGA provides **separate attestations** for Phase 2 and Phase 3
- Phase 2 Weekly Attestation: Continues unchanged (every Sunday)
- Phase 3 Weekly Attestation: New attestation for Phase 3 operations (every Sunday)
- **No conflict:** Separate attestation reports, separate pass/fail criteria

### 4.3 Isolated Components

| Component | Phase 2 | Phase 3 | Shared? |
|-----------|---------|---------|---------|
| **Database** | `fhq_production` schema | `fhq_phase3` schema | ❌ No |
| **Cost Tracking** | ADR-012 caps | ADR-013 caps | ❌ No |
| **Orchestrator Logic** | 10-step cycle | 25-step cycle | ❌ No |
| **Agent Contracts** | FINN v1.0, STIG v1.0, LINE v1.0, VEGA v1.0 | FINN+ v2.0, STIG+ v2.0, LINE+ v2.0, VEGA+ v2.0 | ❌ No |
| **Determinism Threshold** | ≥95% | ≥90% | ❌ No |
| **VEGA Attestation** | Phase 2 report | Phase 3 report | ❌ No |
| **LINE Data** | 1d OHLCV, Serper news | Multi-interval OHLCV, order book, real-time news | ✅ Yes (partial) |

### 4.4 Non-Interference Guarantees

**How Phase 3 Ensures No Interference with Phase 2:**

1. **Separate Databases:**
   - Phase 2 writes to `fhq_production` schema
   - Phase 3 writes to `fhq_phase3` schema
   - No shared tables, no foreign keys between schemas

2. **Separate Cost Tracking:**
   - Phase 2 costs tracked under ADR-012 caps ($0.05/summary, $500/day)
   - Phase 3 costs tracked under ADR-013 caps ($0.25/cycle, $1,000/day)
   - Separate daily cost reports

3. **Separate Agent Versions:**
   - Phase 2 uses frozen agent contracts (FINN v1.0, etc.)
   - Phase 3 uses extended agent contracts (FINN+ v2.0, etc.)
   - No code changes to Phase 2 agent implementations

4. **Separate Monitoring:**
   - Phase 2 VEGA attestation continues weekly (unchanged)
   - Phase 3 VEGA attestation is separate weekly report
   - Phase 3 failures do not affect Phase 2 status

5. **Separate Branch:**
   - Phase 2 code in `main` branch (frozen)
   - Phase 3 code in `phase3/expansion` branch (active development)
   - No merges until Phase 3 completion and G5 approval

---

## 5. OBSERVABILITY & MONITORING

### 5.1 Phase 3 Observability Endpoints

**Real-Time Cycle State:**
- `GET /phase3/cycle/status` — Current cycle state (tier, step, agent, status)
- `GET /phase3/cycle/{cycle_id}` — Full cycle details for specific cycle ID
- `GET /phase3/cycle/{cycle_id}/timeline` — Cycle execution timeline (step durations)

**Agent-Specific State:**
- `GET /phase3/agent/finn/state` — FINN+ current state
- `GET /phase3/agent/stig/state` — STIG+ current state
- `GET /phase3/agent/line/state` — LINE+ current state
- `GET /phase3/agent/vega/state` — VEGA+ current state

**Decision Traceability:**
- `GET /phase3/decisions/{cycle_id}` — Full decision chain for cycle (all agent outputs)
- `GET /phase3/decisions/{cycle_id}/causal_graph` — Causal inference graph
- `GET /phase3/decisions/{cycle_id}/trade_recommendation` — Pre-trade analysis details

**Performance Metrics:**
- `GET /phase3/metrics/cycle_duration` — Average cycle duration (last 100 cycles)
- `GET /phase3/metrics/agent_latency` — Per-agent latency (FINN, STIG, LINE, VEGA)
- `GET /phase3/metrics/success_rate` — Cycle success rate (last 100 cycles)

**Cost Metrics:**
- `GET /phase3/metrics/cost_per_cycle` — Average cost per cycle (last 100 cycles)
- `GET /phase3/metrics/daily_cost` — Daily cost summary
- `GET /phase3/metrics/cost_breakdown` — Cost breakdown by tier and agent

### 5.2 Phase 3 Monitoring Dashboard

**Real-Time Dashboard (Web UI):**
- Current cycle status (live updates)
- Agent execution status (FINN, STIG, LINE, VEGA)
- Cost tracking (current day vs ADR-013 caps)
- Performance metrics (latency, throughput, success rate)
- Alerts (VEGA attestation failures, cost ceiling approaches, signature failures)

**Technology Stack (Proposed):**
- **Backend:** FastAPI (Python) for observability endpoints
- **Frontend:** React + D3.js for real-time visualizations
- **Database:** PostgreSQL (`fhq_phase3` schema) for cycle data storage
- **Monitoring:** Prometheus + Grafana for metrics and alerting

### 5.3 Phase 3 Logging

**Structured Logging (JSON Format):**
```json
{
  "timestamp": "2025-11-24T00:00:00Z",
  "cycle_id": "phase3_cycle_abc123",
  "tier": 2,
  "step": 7,
  "agent": "FINN+",
  "action": "regime_classification",
  "status": "success",
  "duration_ms": 1234,
  "output": {
    "regime": "bull",
    "confidence": 0.87
  },
  "signature": "ed25519:finn_regime_signature_...",
  "signature_verified": true
}
```

**Log Storage:**
- **Location:** `05_ORCHESTRATOR/PHASE3/LOGS/`
- **Format:** JSON lines (`.jsonl`)
- **Retention:** 90 days
- **Rotation:** Daily log files

---

## 6. PHASE 3 ORCHESTRATOR IMPLEMENTATION

### 6.1 Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Orchestrator Engine** | Python 3.11+ | Consistency with Phase 2, rich ML ecosystem |
| **Agent Communication** | gRPC or REST API | Low-latency, high-throughput inter-agent communication |
| **Database** | PostgreSQL (`fhq_phase3` schema) | ACID guarantees, JSON support, time-series extensions |
| **Message Queue** | Redis or RabbitMQ | Asynchronous task execution, retry logic |
| **Observability** | FastAPI + Prometheus + Grafana | Real-time metrics, alerting, dashboards |
| **ML Models** | PyTorch or TensorFlow | RL training, causal inference, regime classification |

### 6.2 Orchestrator Class Structure

**Core Classes:**

```python
# 05_ORCHESTRATOR/PHASE3/phase3_orchestrator.py

class Phase3Orchestrator:
    def __init__(self, config_path: str):
        self.config = load_config(config_path)
        self.agents = self._initialize_agents()
        self.database = self._initialize_database()
        self.logger = self._initialize_logger()

    def execute_cycle(self, cycle_id: str) -> CycleResult:
        """Execute full 25-step Phase 3 cycle"""
        cycle = Cycle(cycle_id, tiers=5, steps=25)

        # Tier 1: Enhanced Context Gathering
        tier1_result = self._execute_tier1(cycle)

        # Tier 2: Advanced Analysis
        tier2_result = self._execute_tier2(cycle, tier1_result)

        # Tier 3: Decision Layer (conditional)
        if tier2_result.cds_score >= 0.65:
            tier3_result = self._execute_tier3(cycle, tier2_result)
        else:
            tier3_result = None  # Skip decision layer

        # Tier 4: Execution Feasibility
        tier4_result = self._execute_tier4(cycle, tier2_result, tier3_result)

        # Tier 5: Reporting & Reconciliation
        tier5_result = self._execute_tier5(cycle, tier4_result)

        return CycleResult(cycle_id, tier1_result, tier2_result, tier3_result, tier4_result, tier5_result)

    def _execute_tier1(self, cycle: Cycle) -> Tier1Result:
        """Execute Tier 1: Enhanced Context Gathering (Steps 1-5)"""
        # Step 1: LINE+ multi-interval OHLCV
        ohlcv = self.agents['line'].ingest_multi_interval_ohlcv()

        # Step 2: LINE+ order book
        order_book = self.agents['line'].ingest_order_book()

        # Step 3: LINE+ real-time news
        news = self.agents['line'].ingest_real_time_news()

        # Step 4: FINN+ historical context
        historical_context = self.agents['finn'].retrieve_historical_context()

        # Step 5: FINN+ cross-asset correlation
        correlation = self.agents['finn'].compute_cross_asset_correlation()

        return Tier1Result(ohlcv, order_book, news, historical_context, correlation)

    # ... (similar methods for _execute_tier2, _execute_tier3, _execute_tier4, _execute_tier5)
```

### 6.3 Configuration File

**Location:** `05_ORCHESTRATOR/PHASE3/phase3_config.json`

```json
{
  "orchestrator_version": "phase3_v1.0",
  "cycle_frequency": "1h",
  "cycle_timeout_seconds": 300,
  "conditional_execution": {
    "tier3_cds_threshold": 0.65
  },
  "agents": {
    "finn": {
      "version": "v2.0",
      "endpoint": "http://localhost:8001"
    },
    "stig": {
      "version": "v2.0",
      "endpoint": "http://localhost:8002"
    },
    "line": {
      "version": "v2.0",
      "endpoint": "http://localhost:8003"
    },
    "vega": {
      "version": "v2.0",
      "endpoint": "http://localhost:8004"
    }
  },
  "database": {
    "schema": "fhq_phase3",
    "connection_string": "postgresql://user:pass@localhost:5432/fhq_db"
  },
  "cost_tracking": {
    "per_cycle_ceiling_usd": 0.25,
    "daily_budget_cap_usd": 1000,
    "daily_rate_limit": 100
  },
  "observability": {
    "metrics_port": 9090,
    "dashboard_port": 8080,
    "log_level": "INFO"
  }
}
```

---

## 7. PHASE 3 ORCHESTRATOR TESTING

### 7.1 Testing Strategy

| Test Type | Coverage | Success Criteria |
|-----------|----------|------------------|
| **Unit Tests** | Individual agent functions | 100% code coverage, all tests pass |
| **Integration Tests** | Tier-by-tier execution | All 5 tiers execute successfully |
| **End-to-End Tests** | Full 25-step cycle | Cycle completes in <300s, all signatures verified |
| **Determinism Tests** | Replay validation | ≥90% determinism across 100 replay runs |
| **Cost Tests** | ADR-013 compliance | All cycles ≤ $0.25, daily costs ≤ $1,000 |
| **Performance Tests** | Latency and throughput | Cycle duration <300s, throughput ≥10 cycles/hour |

### 7.2 Test Scenarios

**Scenario 1: Low Dissonance Cycle (CDS < 0.65)**
- Expected: Tier 3 skipped, cost ~$0.09, cycle duration ~60s

**Scenario 2: High Dissonance Cycle (CDS ≥ 0.65)**
- Expected: All tiers executed, cost ~$0.19, cycle duration ~120s

**Scenario 3: STIG Validation Failure**
- Expected: Cycle halted at failed validation step, VEGA alerted

**Scenario 4: Data Source Failure (e.g., Binance API down)**
- Expected: Retry logic (3 retries), fallback to cached data, alert VEGA if failure persists

**Scenario 5: Cost Ceiling Breach**
- Expected: Cycle blocked before exceeding $0.25, LARS alerted

---

## 8. PHASE 3 ORCHESTRATOR DEPLOYMENT

### 8.1 Deployment Phases

| Phase | Timeline | Milestone |
|-------|----------|-----------|
| **Dev** | Weeks 3-6 | Core agent extensions implemented |
| **Test** | Weeks 7-10 | Orchestrator tested end-to-end |
| **Staging** | Weeks 11-14 | Phase 3 orchestrator runs in staging environment |
| **Production** | Week 15+ | Phase 3 orchestrator deployed to production (pending G5 approval) |

### 8.2 Deployment Environment

**Production Environment:**
- **Compute:** AWS EC2 (or equivalent) with 8 vCPUs, 32 GB RAM
- **Database:** AWS RDS PostgreSQL (or equivalent) with `fhq_phase3` schema
- **Networking:** VPC with security groups (Phase 3 orchestrator isolated from Phase 2)
- **Monitoring:** CloudWatch + Prometheus + Grafana

**Separate Infrastructure:**
- Phase 3 orchestrator runs on **separate compute instances** from Phase 2
- Phase 3 database is **separate PostgreSQL instance** (or separate schema)
- No shared resources between Phase 2 and Phase 3 (prevents resource contention)

---

## 9. PHASE 3 ORCHESTRATOR RISKS & MITIGATION

### 9.1 Key Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Phase 3 interferes with Phase 2** | Critical | Separate databases, separate branches, VEGA monitoring |
| **Cost overruns exceed ADR-013** | High | Cost tracking per cycle, pre-execution cost checks, VEGA alerts |
| **Determinism below 90% threshold** | Medium | Replay testing, ML model validation, STIG oversight |
| **Orchestrator hangs or crashes** | Medium | Cycle timeout (300s), automatic restart, health checks |
| **Data source failures** | Medium | Retry logic, fallback to cached data, multi-source redundancy |

### 9.2 Rollback Plan

**If Phase 3 orchestrator fails:**
1. **Halt Phase 3 Orchestrator:** Stop all Phase 3 cycles immediately
2. **Verify Phase 2 Integrity:** Confirm Phase 2 orchestrator continues unaffected
3. **Root Cause Analysis:** VEGA investigates failure, identifies root cause
4. **Remediation:** Fix issue, test in staging, redeploy
5. **LARS Approval:** LARS approves Phase 3 restart after remediation

**Phase 2 Always Protected:**
- Phase 3 failures never affect Phase 2 operations
- Phase 2 continues production cycles uninterrupted

---

## 10. NEXT STEPS

### 10.1 Immediate Actions (Week 1)

1. ✅ Complete Phase 3 Orchestrator Plan (this document)
2. 🟡 Create Agent Extension Specs (FINN, STIG, LINE, VEGA)
3. 🟡 Draft ADR-013 (Phase 3 Economic Safety Constraints)
4. 🟡 Set up `phase3/expansion` branch
5. 🟡 Begin Phase 3 orchestrator implementation (core structure)

### 10.2 Week 2-4 Actions

1. Implement Tier 1 orchestrator logic (steps 1-5)
2. Implement Tier 2 orchestrator logic (steps 6-10)
3. Implement conditional Tier 3 logic (steps 11-15)
4. Write unit tests for each tier
5. First weekly development log (Monday, Week 2)

---

## CONCLUSION

Phase 3 orchestrator represents a **multi-tier decision-making system** that extends Vision-IoS from conflict detection to **autonomous intelligence with trading-system awareness**.

**Key Achievements:**
- **5-tier decision flow:** Enhanced context, advanced analysis, decision layer, execution feasibility, reconciliation
- **25-step cycle:** Comprehensive multi-agent coordination
- **Parallel execution:** Phase 3 runs alongside Phase 2 without interference
- **Cost optimization:** Conditional execution (Tier 3 only if CDS ≥ 0.65)
- **Observability:** Real-time cycle visibility, agent traceability, performance metrics

**Phase 3 orchestrator development begins immediately.**

---

**Document Status:** DRAFT
**Next Review:** Weekly (Mondays) via development logs
**Approval:** LARS (via review of first weekly dev log)

---

**END OF PHASE 3 ORCHESTRATOR PLAN**
