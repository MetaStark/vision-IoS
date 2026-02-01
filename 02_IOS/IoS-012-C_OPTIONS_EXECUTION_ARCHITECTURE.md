# IoS-012-C: Options Execution Architecture

**Status:** G1 DRAFT — Technical Validation
**Author:** STIG (EC-003)
**Date:** 2026-02-01
**Parent:** IoS-012 (Execution Engine)
**Directive:** CEO-DIR-2026-OPS-AUTONOMY-001
**Classification:** GOVERNANCE-CRITICAL / EXECUTION-BOUND
**Gate:** ADR-004 G1 (Technical Validation)

---

## 1. Purpose

This document specifies the complete options trading architecture for FjordHQ, extending the existing execution engine (IoS-012) to support options strategies via the Alpaca Options API. All execution is restricted to `SHADOW_PAPER` mode until G4 CEO approval.

---

## 2. MIT Quad Invariant Preservation

The options architecture preserves the MIT Quad (LIDS / ACL / DSL / RISL) separation:

| Domain | Role in Options | Constraint |
|--------|----------------|------------|
| **LIDS** (IoS-003) | Reads regime state. Regime determines which options strategies are eligible. | Read-only. No options mutation. |
| **ACL** (IoS-006) | Validates macro conditions (yield curve, VIX, credit spreads). | Cannot override options decisions. |
| **DSL** (IoS-004 + IoS-012-C) | SOLE authority for options candidate generation. Receives regime + alpha graph signals. | Never receives ACI input directly. |
| **RISL** | Can freeze all options activity via DEFCON. | Cannot alter strategy parameters. |
| **ACI** (ADR-020) | May research options hypotheses under LIDS domain. | Zero Execution Authority. Shadow observation only. |

---

## 3. Architecture Flow

```
IoS-003 (Regime) --> IoS-007 (Alpha Graph) --> FINN (Hypothesis)
       |                                            |
       v                                            v
IoS-004 (Allocation) <--- Options Strategy Candidates (DSL-ONLY)
       |
       v
IoS-012-C (Options Execution) <--- NEVER receives ACI input directly
       |
       v
CPTO Options Extension (Entry Precision)
       |
       v
Unified Execution Gateway (existing, extended)
       |
       v
Alpaca Options API (SHADOW_PAPER only)
```

---

## 4. Options Strategy Representation

Strategies exist as CANDIDATES in `fhq_learning.options_hypothesis_canon`. Each candidate contains:

- `strategy_type`: VERTICAL_SPREAD, IRON_CONDOR, COVERED_CALL, CASH_SECURED_PUT, PROTECTIVE_PUT
- `underlying`: The underlying symbol (e.g., AAPL, NVDA)
- `strikes[]`: Array of strike prices for each leg
- `expirations[]`: Array of expiration dates
- `greeks_snapshot`: JSON with delta, gamma, vega, theta, rho at creation time

**Critical invariant:** Candidates are NEVER directly executed. They flow through the full promotion gate pipeline:

```
hypothesis --> experiment --> trigger --> outcome --> promotion -->
shadow --> tier --> decision --> eligibility
```

This preserves the 9-step capital pipeline invariant (IoS-012, Section 4).

---

## 5. Alpaca Integration Points

### 5.1 SDK Usage

- **Library:** `alpaca-py` SDK
- **Chain data:** `get_option_contracts()`, `get_option_chain()` for chain retrieval
- **Paper orders:** `submit_order()` with `asset_class=AssetClass.US_OPTION`
- **Multi-leg:** Alpaca MLeg API for iron condors, spreads as single order
- **Symbology:** Standard OCC/OPRA format (e.g., `AAPL240119C00150000`)

### 5.2 Order Flow

1. Shadow adapter validates `execution_mode == SHADOW_PAPER`
2. Query Alpaca options chain via `get_option_contracts()`
3. Calculate Greeks via `options_greeks_calculator`
4. Validate Greeks within DEFCON limits
5. Submit paper order via Alpaca SDK
6. Record to `fhq_execution.options_shadow_orders`
7. Monitor position lifecycle (theta decay, Greeks drift, DTE countdown)
8. Auto-close at configurable DTE threshold (default: 7 DTE)
9. Record outcome in `fhq_execution.options_shadow_outcomes`
10. Generate evidence JSON with full lineage hash

### 5.3 Latency & Slippage Measurement

All options orders capture:

| Metric | Field | Source |
|--------|-------|--------|
| Submit time | `order_submitted_at` | System clock (UTC) |
| Fill time | `order_filled_at` | Alpaca response |
| Round-trip | `roundtrip_ms` | Computed: fill - submit |
| Slippage | `slippage_bps` | abs(filled_price - mid_price_at_submission) in basis points |

**MiFID II Art. 17 threshold:** >500ms roundtrip triggers automatic halt.

All measurements signed via hash-chain (ADR-013).

---

## 6. Compute Region

| Phase | Location | Rationale |
|-------|----------|-----------|
| SHADOW_PAPER (current) | Windows x64, localhost (Norway) | Latency irrelevant for paper trading |
| PAPER (G3+) | Windows x64, localhost | Norwegian latency (~120ms to us-east) acceptable for swing/daily |
| LIVE (G4+, future) | us-east-1 (AWS) or Alpaca co-located | Decision deferred to G3 review |

Options latency tolerance is 100-500ms (not HFT). Sub-second strategies (0DTE scalping) require co-location and are explicitly blocked in Phase A.

---

## 7. Schema Design

### 7.1 New Tables in `fhq_execution`

**`options_chain_snapshots`** — Cached chain data per underlying/expiration:
- underlying, expiration_date, strike, option_type (CALL/PUT)
- bid, ask, mid, last
- delta, gamma, vega, theta, rho
- implied_volatility, open_interest, volume
- snapshot_timestamp, content_hash

**`options_shadow_orders`** — Shadow paper orders:
- order_ref, strategy_type, underlying
- legs (JSONB: array of {side, strike, expiration, option_type, quantity})
- filled_prices (JSONB), greeks_at_entry (JSONB)
- margin_requirement_est, max_loss, max_profit
- execution_mode (SHADOW_PAPER enforced)
- order_submitted_at, order_filled_at, roundtrip_ms, slippage_bps
- source_hypothesis_id, lineage_hash

**`options_shadow_positions`** — Open shadow positions:
- position_ref, order_id (FK)
- aggregate Greeks: position_delta, position_gamma, position_vega, position_theta
- dte_remaining, theta_decay_daily, assignment_probability
- unrealized_pnl, status (OPEN/CLOSED/ROLLED/ASSIGNED)

**`options_shadow_outcomes`** — Closed positions:
- outcome_id, position_id (FK)
- realized_pnl, realized_return_pct
- Greeks attribution: theta_pnl, delta_pnl, gamma_pnl, vega_pnl
- exit_reason, exit_dte, holding_period_days
- content_hash, chain_hash

**`options_latency_log`** — Roundtrip measurements:
- log_id, order_id, roundtrip_ms, threshold_ms
- breach (boolean), action_taken
- logged_at

### 7.2 New Tables in `fhq_learning`

**`options_hypothesis_canon`** — Options-specific hypotheses:
- hypothesis_id (UUID), strategy_type, underlying
- regime_condition (JSONB), iv_rank_condition (JSONB), dte_range (int4range)
- source (CHECK: NOT 'ACI_DIRECT'), status
- strikes (JSONB), expirations (JSONB), greeks_snapshot (JSONB)
- created_at, lineage_hash

**`options_volatility_surface`** — IV surface snapshots:
- surface_id, underlying, snapshot_date
- expiration_date, strike, option_type
- implied_volatility, delta, gamma, vega, theta
- iv_rank, iv_percentile
- content_hash

### 7.3 New Tables in `fhq_monitoring`

**`options_risk_monitor`** — Real-time aggregate Greeks exposure:
- monitor_id, snapshot_at
- portfolio_delta, portfolio_gamma, portfolio_vega, portfolio_theta
- max_loss_estimate, margin_utilized_pct
- positions_count, strategies_active (JSONB)
- defcon_level_at_snapshot, content_hash

See migration files `350_options_trading_infrastructure.sql` and `351_options_defcon_killswitch.sql` for complete DDL.

---

## 8. Greeks Calculation Module

**File:** `03_FUNCTIONS/options_greeks_calculator.py`

### 8.1 Pricing Models

| Model | Use Case | Notes |
|-------|----------|-------|
| Black-Scholes | European-style baseline | Closed-form, fast |
| Binomial (CRR) | American-style (early exercise) | 100-step tree default |

### 8.2 Greeks

| Greek | Formula | Interpretation |
|-------|---------|----------------|
| Delta | dV/dS | Price sensitivity per $1 underlying move |
| Gamma | d²V/dS² | Delta acceleration |
| Vega | dV/dσ | Price sensitivity per 1% IV change |
| Theta | dV/dt | Time decay per day |
| Rho | dV/dr | Rate sensitivity per 1% rate change |

### 8.3 IV Metrics

- **IV Calculation:** Newton-Raphson iteration from market prices (max 100 iterations, tolerance 1e-8)
- **IV Rank:** `(current_IV - 52w_low_IV) / (52w_high_IV - 52w_low_IV)`
- **IV Percentile:** `% of days in past year where IV was lower`

All calculations deterministic and reproducible.

---

## 9. Runtime Safety & Kill-Switch

**File:** `03_FUNCTIONS/options_defcon_killswitch.py`

Integration with existing ADR-016 DEFCON system. Options-specific rules layered on top:

| DEFCON Level | Shadow Allowed | Live Allowed | Max Delta | Max Vega | Action |
|-------------|---------------|-------------|-----------|----------|--------|
| 5 (GREEN) | Yes | No* | 50.0 | 5000.0 | Normal operations |
| 4 (YELLOW) | Yes | No | 25.0 | 2500.0 | TIGHTEN_GREEKS_LIMITS |
| 3 (ORANGE) | No | No | — | — | HALT_ALL_OPTIONS |
| 2 (RED) | No | No | — | — | FLATTEN_ALL_OPTIONS |
| 1 (BLACK) | No | No | — | — | SYSTEM_ISOLATED |

*Live always False until G4 CEO approval.

### 9.1 MiFID II Art. 17 Compliance

- Latency kill-switch: roundtrip > 500ms triggers halt + alert
- Runaway order detection: > 10 options orders in 60 seconds triggers halt
- Margin breach: estimated margin > 50% of portfolio triggers halt
- Greeks breach: any single Greek exceeds DEFCON limit triggers halt for that strategy

### 9.2 ADR-019 Break-Glass Extension

| Command | Scope | Authority |
|---------|-------|-----------|
| SYSTEM_HALT | All systems | RISL (existing) |
| DEFCON_RESET | DEFCON level | RISL (existing) |
| POSITIONS_FLATTEN | All positions | RISL (existing) |
| **OPTIONS_FLATTEN** | Options positions only | RISL (new) |

### 9.3 Hash-Chain Continuity (ADR-013)

Every kill-switch event produces evidence JSON with SHA256 content_hash. Logged to `fhq_monitoring.options_killswitch_events` with `chain_hash` linking to previous event. Immutable audit trail for regulatory inspection.

---

## 10. Shadow/Paper Trading Path

**File:** `03_FUNCTIONS/options_shadow_adapter.py`

### 10.1 Execution Mode

```
execution_mode = SHADOW_PAPER  (hardcoded, non-negotiable)
```

### 10.2 Supported Strategies (SHADOW_PAPER only)

| Strategy | Risk Profile | Requires |
|----------|-------------|----------|
| Cash-Secured Put (CSP) | Defined risk (bullish) | Cash collateral |
| Covered Call (CC) | Defined risk (neutral/mild bullish) | Shares |
| Vertical Spread | Defined risk, defined reward | — |
| Iron Condor | Defined risk (range-bound) | — |
| Protective Put | Portfolio hedge | Shares |

### 10.3 Blocked Strategies

| Strategy | Reason | Enforcement |
|----------|--------|-------------|
| Naked calls | Undefined risk | Code assertion |
| Naked puts (beyond CSP) | Undefined risk | Code assertion |
| Straddles/strangles (no cap) | Undefined max loss | Code assertion |
| 0DTE strategies | Latency < 50ms not proven | Code assertion |
| Any undefined-risk strategy | Governance constraint | Code assertion |

### 10.4 Hard Constraints (Class A Governance Breach if violated)

```python
assert execution_mode == "SHADOW_PAPER"
assert not margin_utilized
assert not capital_allocated_live
assert not requires_g3_approval()
```

---

## 11. Gap Analysis Summary

### 11.1 Infrastructure Gaps (10)

| # | Gap | Severity | Complexity |
|---|-----|----------|-----------|
| G1 | Options chain data ingestion | HIGH | MEDIUM |
| G2 | Greeks calculator | HIGH | MEDIUM |
| G3 | Options execution adapter | HIGH | HIGH |
| G4 | IV surface tracking | MEDIUM | MEDIUM |
| G5 | Options P&L attribution | MEDIUM | MEDIUM |
| G6 | Assignment risk engine | MEDIUM | HIGH |
| G7 | Options roll management | LOW | MEDIUM |
| G8 | Options regime mapping | HIGH | LOW |
| G9 | Multi-leg order builder | HIGH | MEDIUM |
| G10 | Margin calculation | MEDIUM | MEDIUM |

### 11.2 Governance Gaps (7)

| # | Gap | Status |
|---|-----|--------|
| G11 | ADR for options (ADR-025 or IoS-012-C) | BLOCKING — resolved by this document |
| G12 | G4 CEO approval for live execution | BLOCKING — not yet requested |
| G13 | VEGA attestation for options | BLOCKING — pending G2 |
| G14 | AEL Rung for options (Rung E) | BLOCKING — pending pipeline maturity |
| G15 | IoS-004 options mapping | BLOCKING — regime mapping not present |
| G16 | EC for options agent | MEDIUM — extend EC-015 CPTO or new EC-023 |
| G17 | Options in authority_matrix | MEDIUM — row not present |

### 11.3 Lineage & Hash-Chain Gaps (3)

| # | Gap | Status |
|---|-----|--------|
| G18 | Options hypothesis lineage | Resolved by this directive (hash chain in all modules) |
| G19 | Greeks snapshot signing | Resolved by this directive (SHA256 on every calculation) |
| G20 | Options evidence bundle | Resolved by this directive (court-proof evidence per trade) |

### 11.4 Hidden Governance Risks

1. **ACI Leakage Risk:** `options_hypothesis_canon.source` field enforced via CHECK constraint — cannot be 'ACI_DIRECT'.
2. **Greeks Manipulation Risk:** IV data must be < 60 seconds old for any order. Stale IV triggers automatic halt.
3. **Assignment Risk:** Phase 1 restricts to defined-risk strategies only (spreads, cash-secured).
4. **Regime Mismatch Risk:** IoS-003 regime change triggers automatic halt of new options entries + tighten stops on existing.

---

## 12. Implementation Phases

| Phase | Description | Gate | Status |
|-------|-------------|------|--------|
| **A** (this directive) | Foundation: schema, calculator, kill-switch, shadow adapter | G1 | IN PROGRESS |
| **B** (future) | VEGA attestation, LARS strategy review, FINN methodology sign-off, 30-day shadow observation | G2/G3 | PENDING |
| **C** (future) | CEO G4 authorization, execution_mode upgrade to PAPER, performance measurement | G4 | PENDING |

---

## 13. Verification Criteria

| # | Test | Expected |
|---|------|----------|
| V1 | Schema verification via information_schema | All tables exist in correct schemas |
| V2 | Greeks calculator: AAPL $150 call, 30 DTE, 25% IV | Delta ~0.55 |
| V3 | Kill-switch: DEFCON transition to ORANGE | Options halted |
| V4 | Shadow adapter: execution_mode assertion | AssertionError on non-SHADOW_PAPER |
| V5 | Hash-chain: sample options trade lineage | Valid SHA256 chain |
| V6 | Gateway: validate_options_permission() at DEFCON < GREEN | Returns blocked |
| V7 | Evidence JSON: all required fields present | Schema-valid |

---

*Document generated by STIG (EC-003) | CEO-DIR-2026-OPS-AUTONOMY-001 | G1 Technical Validation*
*Database clock: 2026-02-01 16:02 CET*
