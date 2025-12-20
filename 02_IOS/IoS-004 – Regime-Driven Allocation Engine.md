IoS-004 — Regime-Driven Allocation Engine

Version: 2026.PROD.0
Owner: LARS
Tier: Tier-2 (Decision Layer)
Parent: IoS-003 Meta-Perception Engine
Status: Awaiting stig verification

1. Purpose & Mission

IoS-004 is FjordHQ’s first capital-allocation module - (Until further notice - ONLY PAPER MODE)
It transforms canonical regime states from IoS-003 (the HMM v2.0 Meta-Perception Engine) into deterministic, auditable portfolio weights.

Mission:
Convert market regimes into capital exposure with zero ambiguity, zero hidden assumptions, and zero leverage unless explicitly authorized.

IoS-004 provides:

A unified, deterministic exposure framework

A risk-balanced allocation protocol

Predictable capital flows for execution (IoS-005)

Full replay determinism under ADR-011

One-True-Source governance (no competing signals)

2. Dependencies
Dependency	Description	Contract
IoS-003	Canonical 9-state HMM regime engine	regime_label + confidence
Appendix_A_HMM_REGIME	Canonical HMM v2.0 specification	Feature space, training, state logic
fhq_research.regime_predictions_v2	Truth source for all regime signals	Only ACTIVE model allowed
fhq_market.prices	Daily reference prices	Used for normalizations
fhq_meta.ios_registry	IoS governance registry	Version control + ownership
task_registry	Pipeline binding	task_name = 'REGIME_ALLOCATION_ENGINE_V1'

No other model, table, or signal source is permitted.

3. Input Specification
3.1 Truth-Bound Input Source (Non-Negotiable)

All allocation decisions MUST originate from:

fhq_research.regime_predictions_v2
WHERE model_id IN (
    SELECT model_id
    FROM fhq_research.regime_model_registry
    WHERE is_active = TRUE
)


This enforces:

One-True-Model

Full lineage traceability

Deterministic system replay (ADR-011)

Legacy models, alternate tables, or external signals are strictly forbidden.

3.2 Required Input Fields
Field	Description
asset_id	Canonical symbol
timestamp	Trading date
regime_label	9 canonical HMM states
confidence	Model confidence (0–1)
model_id	Active model identifier
4. Core Logic — Allocation Engine
4.1 Regime → Exposure Mapping (Raw Targets)
Regime	Exposure Target
STRONG_BULL	1.00
BULL	0.70
RANGE_UP	0.40
PARABOLIC	1.00
NEUTRAL	0.00
BEAR	0.00
STRONG_BEAR	0.00
RANGE_DOWN	0.00
BROKEN	0.00

Raw exposures are pre-constraint values.
Portfolio-level constraints apply after this stage.

4.2 Portfolio Constraint Framework (Global Bag Limit)
4.2.1 Total Exposure Cap (Hard Rule)
Σ(exposure_constrained) ≤ 1.0


No implicit leverage is allowed.
Leverage Mode requires a separate IoS and CEO G4 authorization.

4.2.2 Equal Weight Rule (v1.0)

If more than one asset is in risk-on (exposure_raw > 0):

allocated_weight(asset) = 1.0 / N_risk_on_assets


Equal Weight overrides raw exposure when more than one asset is active.

This ensures:

Audit simplicity

Predictable diversification

Zero implicit bias toward any asset

Deterministic replay

4.2.3 Proportional Rescaling (Exposure Normalization)

If Σ(raw_exposures) > 1.0:

exposure_constrained(asset) = raw_exposure(asset) / Σ(raw_exposures)


This is applied before cash_weight computation.

4.3 Elimination of Double Hysteresis

IoS-003 already applies:

5-day persistence

Regime smoothing

Transition certainty thresholds

Volatility anomaly overrides

Additional smoothing in IoS-004 would create unacceptable lag.

Updated Rule (Critical)

IoS-004 executes immediately on the first CONFIRMED regime state emitted by IoS-003.

Only states marked CONFIRMED are valid.
Transient or anomaly-corrected states MUST be ignored.

5. Volatility Block (Safety Brake)

If either of the following is true:

confidence < 0.50

vol_shock_score (from fhq_perception.regime_daily) exceeds abnormal thresholds

Then:

exposure_raw = 0.0


This prevents capital deployment in unstable or ambiguous market conditions.

6. Output Specification

IoS-004 writes to:

fhq_positions.target_exposure_daily

Fields
Field	Description
asset_id	Canonical symbol
timestamp	Trading date
exposure_raw	Pre-constraint exposure
exposure_constrained	Final exposure after constraints
cash_weight	1.0 − Σ(exposure_constrained)
model_id	HMM model used
regime_label	Underlying regime
confidence	Model confidence
lineage_hash	ADR-011 lineage
hash_prev	Parent hash
hash_self	Row-level hash
6.1 Portfolio-Level Accounting Invariant

Invariant:

Σ(exposure_constrained) + cash_weight = 1.0


Rules:

Summation is evaluated per portfolio per date

Negative cash_weight is forbidden

If Σ(exposure_constrained) < 1.0, the remainder MUST flow to cash

This provides:

Double-entry bookkeeping

Full auditability

No leverage bleed

Clear idle capital tracking

Enforced using:

Per-day aggregate validation

AFTER INSERT/UPDATE verification triggers

Deterministic lineage hashing (ADR-011)

7. Governance & Compliance
7.1 Authority Matrix
Role	Authority
LARS	Owner, strategic decisions
VEGA	Veto power, audit enforcement
STIG	Schema + deterministic logic
CODE	Execution Engine (EC-011)
7.2 Pipeline Binding

IoS-004 is bound to:

task_registry.task_name = 'REGIME_ALLOCATION_ENGINE_V1'
owned_by_agent = LARS
executed_by_agent = CODE
gate_level = G1

7.3 Gating Requirements

IoS-004 must pass the full gate cycle:

Gate	Requirement
G0	Registration + schema creation
G1	Technical validation
G2	Governance review
G3	Audit validation
G3B	Triple Verification (hash, schema, semantic replay)
G4	CEO approval (mandatory)

Failure at any stage results in STOP_AND_WAIT_FOR_CEO.

8. Versioning

IoS-004 v2026.PROD.0

Hash Chain: HC-IOS-004-2026

All forward changes require new IoS-004 minor or major version

Leverage Mode and multi-strategy blending reserved for IoS-004B/005

IoS-004 — Final Statement

"IoS-004 transforms perception into action with institutional precision.
Every weight is justified, every exposure is traceable, and every allocation is reproducible under audit.
This is the first true capital engine of FjordHQ."