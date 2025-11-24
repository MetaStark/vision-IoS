# FINN PHASE 2 ROADMAP (OUT OF SCOPE FOR TIER-2 MANDATE)

**Status:** PLANNING (NOT APPROVED)
**Approval Required:** Separate G0-G4 Process After FINN Tier-2 G4 Canonicalization
**Authority:** CEO Approval Required for Strategic Expansion

---

## EXECUTIVE SUMMARY

This document contains **Phase 2 expansion functions** that were initially proposed in G2 materials but are **OUT OF SCOPE** for FINN Tier-2 Mandate per CEO specification.

**CEO Directive (2025-11-24):**
> "Tier-2 laget skal konvertere deterministiske Tier-4-signaler (CDS, Relevance) til auditerbar Alpha-syntese i tråd med ADR-003, ADR-008 og ADR-010."

**FINN Tier-2 Canonical Mandate (3 Components ONLY):**
1. ✅ **CDS Score** (Input from cds_engine.calculate_cds())
2. ✅ **Relevance Score** (Input from relevance_engine.calculate_relevance())
3. ✅ **Tier-2 Conflict Summary** (Output: 3-sentence Alpha synthesis, Ed25519 signed)

**Phase 2 Scope:** Functions listed below are **signal generation and validation** capabilities that extend beyond the Tier-2 synthesis mandate. They require:
- Strategic authority expansion (some require Tier-1 access)
- Separate G0-G4 governance approval process
- Independent technical validation and audit verification
- CEO canonicalization before implementation

---

## PHASE 2 FUNCTIONS (NOT APPROVED)

### **FUNCTION 1: Signal Baseline Inference**

**Status:** ❌ NOT APPROVED - OUT OF SCOPE FOR TIER-2

**Purpose:** Generate signal baseline metrics for market data streams

**Why Out of Scope:**
- FINN Tier-2 is a **synthesis layer**, not a signal generation layer
- Baseline inference requires access to raw OHLCV data (Tier-4 responsibility)
- This function belongs to **Tier-4 Deterministic Layer** or **separate baseline engine**

**Inputs:**
- Market data stream (OHLCV)
- Historical baseline window (default: 30 days)
- Asset identifier

**Outputs:**
- Baseline mean, std deviation
- Trend coefficient
- Volatility index
- Anomaly threshold

**ADR-010 Discrepancy Score Contract:**
```yaml
baseline_mean:
  weight: 0.8
  tolerance: 0.001  # 0.1% relative error

trend_coefficient:
  weight: 0.8
  tolerance: 0.001

volatility_index:
  weight: 0.6
  tolerance: 0.005

anomaly_threshold:
  weight: 0.5
  tolerance: 0.01
```

**Tier-2 Prompting Constraints:**
- **LLM Steps:** 3 steps MAX
- **Token Generation:** 2048 tokens MAX
- **Latency:** 5000ms WARN
- **Cost:** $0.04 MAX per call

**Storage:**
```sql
CREATE TABLE IF NOT EXISTS vision_signals.signal_baseline (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id VARCHAR(50) NOT NULL,
    baseline_mean NUMERIC(15,8) NOT NULL,
    baseline_std NUMERIC(15,8) NOT NULL,
    trend_coefficient NUMERIC(10,6) NOT NULL,
    volatility_index NUMERIC(10,6) NOT NULL,
    anomaly_threshold NUMERIC(10,6) NOT NULL,
    confidence_interval JSONB NOT NULL,
    computed_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    hash_chain_id VARCHAR(100) NOT NULL,
    signature_id VARCHAR(200) NOT NULL,
    signature BYTEA NOT NULL
);
```

**Approval Path:** Requires separate G0 submission → G1 (STIG) → G2 (LARS) → G3 (VEGA) → G4 (CEO)

---

### **FUNCTION 2: Noise Floor Estimation**

**Status:** ❌ NOT APPROVED - OUT OF SCOPE FOR TIER-2

**Purpose:** Estimate noise floor value for filtering spurious signals

**Why Out of Scope:**
- Signal filtering is a **preprocessing function**, not alpha synthesis
- Requires historical signal stream analysis (Tier-4 responsibility)
- This function belongs to **Tier-4 Signal Processing Layer**

**Inputs:**
- Historical signal stream
- Estimation window (default: 90 days)
- Asset identifier

**Outputs:**
- Noise floor value
- Signal-to-noise ratio (SNR)
- Filter threshold

**ADR-010 Discrepancy Score Contract:**
```yaml
noise_floor_value:
  weight: 1.0
  tolerance: 0  # Exact match required

signal_to_noise_ratio:
  weight: 0.8
  tolerance: 0.001

filter_threshold:
  weight: 0.6
  tolerance: 0.005
```

**Tier-2 Prompting Constraints:**
- **LLM Steps:** 3 steps MAX
- **Token Generation:** 1024 tokens MAX
- **Latency:** 3000ms WARN
- **Cost:** $0.04 MAX per call

**Storage:**
```sql
CREATE TABLE IF NOT EXISTS vision_core.noise_profile (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id VARCHAR(50) NOT NULL,
    noise_floor_value NUMERIC(15,8) NOT NULL CHECK (noise_floor_value >= 0),
    signal_to_noise_ratio NUMERIC(10,6) NOT NULL CHECK (signal_to_noise_ratio > 1.0),
    filter_threshold NUMERIC(10,6) NOT NULL,
    computed_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    hash_chain_id VARCHAR(100) NOT NULL,
    signature_id VARCHAR(200) NOT NULL,
    signature BYTEA NOT NULL
);
```

**Approval Path:** Requires separate G0 submission → G1 (STIG) → G2 (LARS) → G3 (VEGA) → G4 (CEO)

---

### **FUNCTION 3: Meta-State Synchronization**

**Status:** ⚠️ PENDING VEGA REVIEW - GOVERNANCE RECONCILIATION ONLY

**Purpose:** Synchronize Vision-IoS state to fhq_meta for governance reconciliation

**Why Flagged:**
- This is a **governance function**, not a FINN-specific mandate
- Required by **VEGA for ADR-010 compliance audits** (system-level, not agent-level)
- May belong to **VEGA governance layer** or **orchestrator reconciliation module**

**Governance Question for VEGA:**
- Should Meta-State Sync be a VEGA responsibility (audit verification)?
- Or should it be an Orchestrator responsibility (system reconciliation)?
- Or should FINN implement it as part of ADR-010 compliance?

**Inputs:**
- Vision-IoS execution state
- Canonical state from fhq_meta
- Reconciliation rules (ADR-010)

**Outputs:**
- Discrepancy score (0.0-1.0)
- Field-by-field comparison
- Reconciliation evidence bundle

**ADR-010 Discrepancy Score Contract:**
```yaml
execution_count:
  weight: 1.0
  tolerance: 0  # Exact match

success_rate:
  weight: 0.8
  tolerance: 0.001

last_execution_timestamp:
  weight: 0.3
  tolerance: 5  # seconds

orchestrator_version:
  weight: 0.5
  tolerance: 0  # Exact match
```

**Tier-2 Prompting Constraints:**
- **LLM Steps:** 5 steps MAX (reconciliation may require multiple comparisons)
- **Token Generation:** 4096 tokens MAX (evidence bundle can be large)
- **Latency:** 5000ms WARN
- **Cost:** $0.04 MAX per call

**Storage:**
```sql
CREATE TABLE IF NOT EXISTS vision_autonomy.meta_state_sync (
    sync_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vision_state JSONB NOT NULL,
    canonical_state JSONB NOT NULL,
    discrepancy_score NUMERIC(6,5) NOT NULL CHECK (discrepancy_score BETWEEN 0.0 AND 1.0),
    evidence_bundle JSONB NOT NULL,
    sync_timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    hash_chain_id VARCHAR(100) NOT NULL,
    signature_id VARCHAR(200) NOT NULL,
    signature BYTEA NOT NULL
);

-- If discrepancy_score > 0.10, trigger VEGA suspension request
CREATE OR REPLACE FUNCTION check_discrepancy_threshold()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.discrepancy_score > 0.10 THEN
        INSERT INTO fhq_governance.agent_suspension_requests (
            agent_id,
            reason,
            discrepancy_score,
            evidence,
            status
        ) VALUES (
            'FINN',
            'CATASTROPHIC_DISCREPANCY',
            NEW.discrepancy_score,
            NEW.evidence_bundle,
            'PENDING'
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_discrepancy_escalation
AFTER INSERT OR UPDATE ON vision_autonomy.meta_state_sync
FOR EACH ROW EXECUTE FUNCTION check_discrepancy_threshold();
```

**Approval Path:** VEGA review → LARS strategic decision → Separate G0-G4 if approved

---

### **FUNCTION 4: Alpha Signal Generation**

**Status:** ❌ NOT APPROVED - REQUIRES TIER-1 AUTHORITY

**Purpose:** Generate actionable alpha signals from market data and research

**Why Out of Scope:**
- **Alpha Signal Generation is a Tier-1 STRATEGIC FUNCTION**
- Requires cross-asset aggregation and strategic decision-making (beyond Tier-2 synthesis)
- FINN Tier-2 mandate is to **synthesize existing signals**, not generate new alpha
- This function requires **Tier-1 authority escalation** to LARS for strategic coordination

**Critical Issue:**
- FINN (Authority Level 8) cannot execute Tier-1 strategic functions
- Alpha signal generation influences portfolio decisions (Tier-1 domain)
- Requires LARS (Authority Level 9) oversight or delegation

**Inputs:**
- Market data streams (multiple assets)
- Baseline metrics (from Function 1)
- Noise profile (from Function 2)
- Research signals (external APIs: Marketaux, FRED, Scholar)

**Outputs:**
- Alpha signal (buy/sell/hold)
- Signal strength (0.0-1.0)
- Confidence interval
- Attribution (which research signals contributed)

**ADR-010 Discrepancy Score Contract:**
```yaml
alpha_signal:
  weight: 1.0
  tolerance: 0  # Exact match (buy/sell/hold)

signal_strength:
  weight: 0.8
  tolerance: 0.05  # Absolute error

confidence_interval_lower:
  weight: 0.6
  tolerance: 0.1

confidence_interval_upper:
  weight: 0.6
  tolerance: 0.1
```

**Tier-2 Prompting Constraints:**
- **LLM Steps:** 5 steps MAX (research aggregation requires multi-step reasoning)
- **Token Generation:** 4096 tokens MAX
- **Latency:** 5000ms WARN
- **Cost:** $0.04 MAX per call
- **Anti-Hallucination:** Require citation of research sources; reject signals without attribution

**Storage:**
```sql
CREATE TABLE IF NOT EXISTS vision_signals.alpha_signals (
    signal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id VARCHAR(50) NOT NULL,
    alpha_signal VARCHAR(10) NOT NULL CHECK (alpha_signal IN ('buy', 'sell', 'hold')),
    signal_strength NUMERIC(4,3) NOT NULL CHECK (signal_strength BETWEEN 0.0 AND 1.0),
    confidence_interval_lower NUMERIC(6,4) NOT NULL,
    confidence_interval_upper NUMERIC(6,4) NOT NULL CHECK (confidence_interval_upper > confidence_interval_lower),
    attribution JSONB NOT NULL,
    computed_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    hash_chain_id VARCHAR(100) NOT NULL,
    signature_id VARCHAR(200) NOT NULL,
    signature BYTEA NOT NULL
);
```

**Approval Path:**
1. ✅ LARS strategic review (Tier-1 authority delegation decision)
2. ✅ If approved by LARS → Separate G0 submission
3. ✅ G1 (STIG) → G2 (LARS) → G3 (VEGA) → G4 (CEO)
4. ✅ Requires authority level expansion or Tier-1 wrapper

---

### **FUNCTION 5: Backtesting & Performance Attribution**

**Status:** ❌ NOT APPROVED - OUT OF SCOPE FOR TIER-2

**Purpose:** Backtest alpha signals against historical data and attribute performance

**Why Out of Scope:**
- Backtesting is a **validation and performance measurement function**
- FINN Tier-2 mandate is to **synthesize signals**, not validate performance
- This function belongs to **VEGA audit layer** or **separate backtesting engine**

**Inputs:**
- Historical alpha signals
- Historical market data (OHLCV)
- Backtesting period

**Outputs:**
- Sharpe ratio
- Max drawdown
- Win rate
- Attribution by signal source

**ADR-010 Discrepancy Score Contract:**
```yaml
sharpe_ratio:
  weight: 0.8
  tolerance: 0.05  # Absolute error

max_drawdown:
  weight: 1.0
  tolerance: 0.01  # Critical for risk (1% absolute error)

win_rate:
  weight: 0.6
  tolerance: 0.02  # 2% absolute error
```

**Tier-2 Prompting Constraints:**
- **LLM Steps:** 3 steps MAX (backtesting is deterministic, not LLM-heavy)
- **Token Generation:** 2048 tokens MAX
- **Latency:** 3000ms WARN
- **Cost:** $0.04 MAX per call

**Storage:**
```sql
CREATE TABLE IF NOT EXISTS vision_signals.backtest_results (
    backtest_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_source VARCHAR(100) NOT NULL,
    sharpe_ratio NUMERIC(6,4) NOT NULL CHECK (sharpe_ratio BETWEEN -10 AND 10),
    max_drawdown NUMERIC(4,3) NOT NULL CHECK (max_drawdown BETWEEN 0 AND 1),
    win_rate NUMERIC(4,3) NOT NULL CHECK (win_rate BETWEEN 0 AND 1),
    attribution JSONB NOT NULL,
    computed_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    hash_chain_id VARCHAR(100) NOT NULL,
    signature_id VARCHAR(200) NOT NULL,
    signature BYTEA NOT NULL
);
```

**Approval Path:** VEGA strategic review → Separate G0 submission → G1-G4 process

---

## GOVERNANCE PROCESS FOR PHASE 2

### Approval Requirements

**CRITICAL:** All Phase 2 functions require independent G0-G4 governance approval process per ADR-004.

**Steps:**
1. ✅ **G0 Submission:** CODE submits Phase 2 function proposal with ADR compliance analysis
2. ✅ **G1 Technical Validation:** STIG validates schema correctness, constraints, indexes
3. ✅ **G2 Governance Validation:** LARS validates authority boundaries, strategic fit, tier alignment
4. ✅ **G3 Audit Verification:** VEGA validates compliance, discrepancy contracts, economic safety
5. ✅ **G4 Canonicalization:** CEO approves and canonicalizes Phase 2 expansion

**No Phase 2 function may be implemented without completing ALL gates (G0-G4).**

---

## STRATEGIC CONSIDERATIONS

### Authority Escalation for Function 4 (Alpha Signal Generation)

**Issue:** FINN (Level 8) cannot autonomously execute Tier-1 strategic functions

**Options:**
1. **LARS Delegation:** LARS (Level 9) delegates alpha generation to FINN with oversight
2. **Tier-1 Wrapper:** Create LARS_FINN_ALPHA agent with Tier-1 access
3. **Reject Function 4:** Keep FINN Tier-2 as synthesis-only, move alpha gen to LARS

**LARS Decision Required:** Strategic coordination decision needed before G0 submission

---

### VEGA Review for Function 3 (Meta-State Synchronization)

**Issue:** Meta-State Sync is a governance reconciliation function, not FINN-specific

**Options:**
1. **VEGA Ownership:** VEGA implements as system-level audit verification
2. **Orchestrator Ownership:** Orchestrator implements as reconciliation module
3. **FINN Implementation:** FINN implements as ADR-010 compliance requirement

**VEGA Decision Required:** Governance architecture decision needed before G0 submission

---

## PHASE 2 TIMELINE (TENTATIVE)

**Earliest Start:** After FINN Tier-2 G4 Canonicalization (CEO approval)

**Recommended Sequence:**
1. **Function 3 (Meta-State Sync):** VEGA review → G0-G4 if approved (1-2 weeks)
2. **Function 1 (Baseline Inference):** G0-G4 process (2-3 weeks)
3. **Function 2 (Noise Floor):** G0-G4 process (2-3 weeks)
4. **Function 5 (Backtesting):** VEGA review → G0-G4 if approved (2-3 weeks)
5. **Function 4 (Alpha Signal Gen):** LARS strategic review → G0-G4 if approved (3-4 weeks)

**Total Estimated Timeline:** 3-6 months after FINN Tier-2 canonicalization

---

## COMPLIANCE SUMMARY

**ADR-002 (Audit Charter):** All Phase 2 functions require immutable audit trail with hash chain IDs

**ADR-003 (Institutional Standards):** All Phase 2 functions must use structured output contracts

**ADR-004 (Change Gates):** All Phase 2 functions require independent G0-G4 approval process

**ADR-007 (Provider Routing):** FINN remains Tier-2 (OpenAI GPT-4 Turbo) for all Phase 2 functions

**ADR-008 (Ed25519 Signatures):** All Phase 2 outputs must be Ed25519 signed

**ADR-010 (Discrepancy Scoring):** All Phase 2 functions must include discrepancy score contracts

**ADR-012 (Economic Safety):** All Phase 2 functions subject to rate/cost/execution limits

---

## DOCUMENT STATUS

**Status:** PLANNING (NOT APPROVED)
**Approval Required:** Separate G0-G4 Process After FINN Tier-2 G4 Canonicalization
**Authority:** CEO Approval Required for Strategic Expansion
**Maintainer:** CODE Team
**Review Cycle:** After each G4 canonicalization event

---

**End of FINN Phase 2 Roadmap**
