# ADR-020 Appendix B — Shadow Execution Protocol (SHADOW_PAPER Mandate)

**Classification:** BINDING REFERENCE
**Parent Document:** ADR-020_2026_PRODUCTION_Autonomous_Cognitive_Intelligence.md
**Version:** 2026.PROD.1
**Date:** 08 December 2025

---

## B.1 Purpose and Scope

The Shadow Execution Protocol (SHADOW_PAPER) enables ACI to validate its research-to-alpha pipeline through non-binding simulated execution, preserving the Zero Execution Authority (ZEA) firewall while enabling empirical feedback.

**SHADOW_PAPER does NOT execute trades.**
**SHADOW_PAPER does NOT modify capital.**
**SHADOW_PAPER only records what WOULD have happened.**

---

## B.2 SHADOW_PAPER Architecture

### B.2.1 System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    ACI Cognitive Layer                       │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │ Search  │  │ InForage│  │  IKEA   │  │ Causal  │        │
│  │ Chain   │  │ Logic   │  │ Protocol│  │ Synth   │        │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │
│       └────────────┴────────────┴────────────┘              │
│                         │                                    │
│                    ┌────▼────┐                               │
│                    │ INSIGHT │                               │
│                    │ OUTPUT  │                               │
│                    └────┬────┘                               │
└─────────────────────────┼───────────────────────────────────┘
                          │
            ══════════════╪══════════════  ZEA FIREWALL
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                 SHADOW_PAPER LAYER                           │
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │  Hypothetical│    │   Shadow    │    │  Performance│      │
│  │   Decision   │───▶│   Ledger    │───▶│   Tracker   │      │
│  │   Generator  │    │   (Read)    │    │             │      │
│  └─────────────┘    └─────────────┘    └─────────────┘      │
│                                                              │
│  ══════════════════════════════════════════════════════════ │
│  │          HARD WALL — NO WRITE TO EXECUTION             │ │
│  ══════════════════════════════════════════════════════════ │
└─────────────────────────────────────────────────────────────┘
                          ▲
                          │ READ-ONLY
                          │
┌─────────────────────────┴───────────────────────────────────┐
│                   DSL EXECUTION LAYER                        │
│              (LINE operates independently)                   │
└─────────────────────────────────────────────────────────────┘
```

### B.2.2 Data Flow Rules

1. ACI insight flows DOWN to SHADOW_PAPER
2. SHADOW_PAPER reads market state (READ-ONLY)
3. SHADOW_PAPER records hypothetical outcomes
4. SHADOW_PAPER feeds performance metrics BACK to ACI
5. **NO DATA FLOWS TO DSL FROM SHADOW_PAPER**

---

## B.3 Hypothetical Decision Generation

### B.3.1 Input Requirements

SHADOW_PAPER receives from ACI:
```json
{
  "insight_id": "uuid",
  "hypothesis": "string",
  "causal_graph": {...},
  "confidence": 0.0-1.0,
  "suggested_direction": "LONG|SHORT|NEUTRAL",
  "suggested_magnitude": 0.0-1.0,
  "evidence_chain": [...],
  "timestamp": "ISO8601"
}
```

### B.3.2 Decision Mapping

SHADOW_PAPER maps insight to hypothetical action:

| Confidence | Direction | Hypothetical Action |
|------------|-----------|---------------------|
| >= 0.80 | LONG | Shadow BUY at suggested_magnitude |
| >= 0.80 | SHORT | Shadow SELL at suggested_magnitude |
| >= 0.80 | NEUTRAL | Shadow HOLD |
| < 0.80 | ANY | No shadow action (insufficient confidence) |

### B.3.3 Magnitude Scaling

Hypothetical position size:
$$\text{size}_{\text{shadow}} = \text{suggested\_magnitude} \times \text{confidence} \times K_{\text{shadow}}$$

Where $K_{\text{shadow}} = 0.1$ (10% of notional for shadow positions).

---

## B.4 Shadow Ledger Specification

### B.4.1 Schema

```sql
CREATE TABLE vision_autonomy.shadow_paper_ledger (
    ledger_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    insight_id UUID NOT NULL,
    shadow_action VARCHAR(10) NOT NULL,  -- BUY, SELL, HOLD
    asset_id VARCHAR(20) NOT NULL,
    entry_price DECIMAL(18,8),
    entry_timestamp TIMESTAMPTZ NOT NULL,
    exit_price DECIMAL(18,8),
    exit_timestamp TIMESTAMPTZ,
    hypothetical_pnl DECIMAL(18,8),
    hypothetical_return DECIMAL(8,6),
    confidence_at_entry DECIMAL(4,3),
    evidence_hash VARCHAR(64),
    status VARCHAR(20) DEFAULT 'OPEN',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### B.4.2 Ledger Rules

1. **Entry Recording:** When ACI produces high-confidence insight, record entry
2. **Price Capture:** Use market price at insight timestamp (not fill simulation)
3. **Exit Trigger:** Close shadow position after 24 hours OR contradicting insight
4. **PnL Calculation:** Simple price delta (no slippage simulation)

---

## B.5 Performance Tracking

### B.5.1 Metrics Computed

| Metric | Formula | Purpose |
|--------|---------|---------|
| Hit Rate | $\frac{\text{profitable\_shadows}}{\text{total\_shadows}}$ | Directional accuracy |
| Average Return | $\frac{\sum \text{returns}}{n}$ | Expected edge |
| Sharpe (Shadow) | $\frac{\mu_r}{\sigma_r}$ | Risk-adjusted performance |
| Confidence Calibration | $\text{corr}(\text{confidence}, \text{outcome})$ | Calibration quality |

### B.5.2 Feedback to ACI

SHADOW_PAPER reports to ACI:
```json
{
  "feedback_type": "SHADOW_PERFORMANCE",
  "period": "DAILY|WEEKLY|MONTHLY",
  "hit_rate": 0.0-1.0,
  "avg_return": float,
  "sharpe_shadow": float,
  "calibration_score": 0.0-1.0,
  "worst_miss": {...},
  "best_hit": {...}
}
```

ACI uses feedback to adjust:
- Confidence thresholds
- Evidence weighting
- Causal graph pruning

---

## B.6 ZEA Firewall Enforcement

### B.6.1 Technical Controls

1. **No DSL Imports:** SHADOW_PAPER code cannot import DSL modules
2. **No API Keys:** SHADOW_PAPER has no access to execution API credentials
3. **Database Isolation:** SHADOW_PAPER writes only to `vision_autonomy` schema
4. **Network Isolation:** SHADOW_PAPER cannot reach broker endpoints

### B.6.2 Code Audit Requirements

All SHADOW_PAPER code must pass:
- VEGA G3 Audit (no execution pathways)
- STIG Static Analysis (no credential access)
- FINN Methodology Review (valid feedback logic)

### B.6.3 Violation Response

Any detected breach of ZEA firewall:
1. Immediate SHADOW_PAPER shutdown
2. DEFCON escalation to RED
3. Class A Governance Violation logged
4. CEO notification within 5 minutes

---

## B.7 DEFCON Integration

### B.7.1 SHADOW_PAPER by DEFCON Level

| DEFCON | SHADOW_PAPER Status |
|--------|---------------------|
| 5 – GREEN | Full operation. All insights processed. |
| 4 – YELLOW | Reduced frequency. Only high-confidence (>0.85) processed. |
| 3 – ORANGE | Suspended. No new shadow positions. Existing tracked read-only. |
| 2 – RED | Frozen. All shadow positions marked ABANDONED. |
| 1 – BLACK | Purged. Shadow ledger archived and cleared. |

### B.7.2 State Transition Rules

On DEFCON escalation:
- Close all open shadow positions at current market price
- Record `exit_reason = 'DEFCON_ESCALATION'`
- Compute final metrics before state change

---

## B.8 Operational Procedures

### B.8.1 Daily Operations

1. **00:00 UTC:** Roll daily metrics
2. **Continuous:** Process incoming ACI insights
3. **Continuous:** Update open shadow positions with market prices
4. **23:59 UTC:** Generate daily performance report

### B.8.2 Weekly Review

FINN reviews SHADOW_PAPER performance:
- Identify systematic errors
- Propose calibration adjustments
- Flag evidence patterns that underperform

### B.8.3 Monthly Governance

VEGA audits SHADOW_PAPER:
- Verify ZEA firewall integrity
- Validate ledger accuracy
- Confirm no execution leakage

---

## B.9 Success Criteria for Production Graduation

Before ACI insights can influence ACTUAL execution (future ADR):

| Criterion | Threshold | Measurement Period |
|-----------|-----------|-------------------|
| Hit Rate | >= 55% | 90 days |
| Sharpe (Shadow) | >= 1.0 | 90 days |
| Calibration | >= 0.70 | 90 days |
| ZEA Violations | 0 | Lifetime |
| VEGA Audits Passed | 3 consecutive | Monthly |

**Until all criteria are met, ACI remains advisory-only.**

---

## B.10 Constitutional Guarantees

1. SHADOW_PAPER is a **learning mechanism**, not an execution pathway
2. No ACI output can bypass DSL sovereignty under any circumstance
3. LINE remains the sole execution authority
4. SHADOW_PAPER existence does not grant ACI any execution rights
5. This appendix may only be amended via G4 Constitutional process

---

*Document Hash: To be computed upon registration*
*Appendix Classification: NORMATIVE BINDING*
