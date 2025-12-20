IoS-011 — TECHNICAL ANALYSIS PIPELINE

Canonical Version: 2026.G0
Status: G0_SUBMITTED
Owner: FINN (Tier-1 Research)
Validator: LARS (Strategy)
Governance: VEGA
Dependencies: IoS-001, IoS-002, IoS-003
ADR Alignment: ADR-004, ADR-012, ADR-013, ADR-051

1. Executive Summary (C-Level Purpose)

IoS-011 is the Technical Analysis Pipeline of Vision-IoS.
Its job is not to generate trades.
Its job is to generate clean, deterministic, bias-controlled technical indicators that higher-level engines (IoS-003, IoS-004, IoS-007) can trust.

Most TA systems in the industry suffer from:

look-ahead bias

inconsistent windowing

unbounded indicator sets

drift between sources

mixed granularity data

missing auditability

IoS-011 exists to standardize and sanitize all TA signals used in FjordHQ.

This module produces TA primitives, not trading signals.

2. Mission & Output (What IoS-011 actually does)
IoS-011 converts raw prices into deterministic, auditable indicator sets, such as:

Moving Averages (SMA, EMA, WMA)

MACD / Signal Line / Histogram

RSI (Wilder)

Stochastic Oscillator

ATR

Bollinger Bands

Ichimoku Cloud Components

PSAR

Volatility channels

Rolling percentiles

But with strict constraints:

Identical input = identical output (no randomness)

No look-ahead allowed

No outside data sources

All computation must reference canonical asset registry (ADR-013)

All indicators must be timestamp-aligned with input candles

All output must include lineage (hash of input window)

This transforms TA from “noise-generating hobby indicators”
→ to institutional-grade deterministic features.

3. System Role Within Vision-IoS

IoS-011 feeds only upwards into:

IoS-003 (Meta-Perception / Market Brain)

IoS-004 (Regime Allocation Engine)

IoS-007 (Alpha Graph Engine)

IoS-010 (Prediction Ledger, indirect)

It never feeds directly into IoS-012 (Execution Engine).
It cannot create positions.
It cannot modify exposure.
It cannot bypass governance.

This preserves clean separation of feature generation vs prediction vs execution.

4. Architectural Boundaries (G0 Definition)
Included in G0:

Complete specification of allowable indicators

Standardized computation methods

Required lineage metadata schema

Input contract: OHLCV data from IoS-001

Indicator windowing rules

Deterministic calculation order

Normalization rules

Hashing of input windows

Version control for indicator definitions

Error handling specification

Granularity constraints (1m, 5m, 1h, 1d allowed)

Excluded from G0 (deferred to G1/G2):

Database storage layer

Indicator caching

Incremental backfill logic

Cross-asset indicators

Multi-frequency resampling

Feature selection engine

Integration with IoS-003

G0 defines the contract, not the implementation.

5. Data Contract (Mandatory Under ADR-013)
Input Source:

Canonical OHLCV dataset from IoS-001
(no external feeds, no duplicate data streams)

Required Fields:

asset_id

timestamp

open, high, low, close

volume

data_quality_tag (VEGA enforced)

Output Schema:

For each indicator:

indicator_name

indicator_value

timestamp

asset_id

lookback_window

input_state_hash

computation_version

metadata (optional)

Lineage Requirements:

Every output must be reproducible via:

hash = SHA256(asset_id + timestamp + input_window + indicator_spec)


This guarantees deterministic reconstruction in an audit scenario.

6. Compliance Requirements
6.1 ADR-004 (Change Gates)

IoS-011 must pass G1 Technical Validation before any code is written.

IoS-011 must pass G2 Governance Validation before touching the database.

6.2 ADR-012 (Economic Safety)

IoS-011 cannot generate any signal that directly or indirectly results in capital deployment.
Its output is pure research features.

6.3 ADR-013 (One-Source-Truth)

TA is computed exclusively from IoS-001 data

No external libraries allowed that embed look-ahead behavior

No third-party data sources

No re-sampling unless explicitly authorized

All indicator definitions versioned and immutable

7. Future Progression Path (High-Level Forecast)
G1 — Technical Validation

Implement deterministic computation engine

Validate outputs vs reference baseline

Validate boundary behavior (missing candles, outliers)

G2 — Governance Validation

Prove lineage integrity

Prove deterministic reproducibility

Prove no accidental future leakage

Register indicator catalogue in canonical registry

G3 — Integration

Bind IoS-011 outputs to IoS-003 and IoS-004

Introduce caching layer

Introduce multi-asset batch computation

G4 — Constitutional Activation

IoS-011 will not be a constitutional module.
It will remain non-canonical (TRUE: data source), canonical=FALSE.

8. Risk Assessment (C-Level)
Risks Without IoS-011

Regime engines operating on noisy/unreliable features

Different modules using different indicator definitions

Hidden look-ahead bias

TA outputs not reproducible under audit

Drift between Pandas, TA-Lib, NumPy, or custom implementations

Incompatible window definitions across models

Risks With IoS-011 (if poorly governed)

Incorrect normalization destabilizing model training

Drift due to precision differences (float32 vs float64)

Excessive dimensionality (indicator explosion)

Unbounded computation cost if caching is skipped

Feature leakage across asset classes

These are mitigated via VEGA oversight + G1/G2 gates.

9. G0 Decision Request

IoS-011 is ready for G0 registration with:

Fully defined scope

Clear data contract

Deterministic indicator specification

Architectural alignment with IoS-001, 003, 004

Zero side-effects

Fully reversible

Requested decision:
Register IoS-011 as G0_SUBMITTED and forward to G1 Technical Validation when appropriate.

Prepared by:

LARS — System Strategy

Approved by:

CEO — FjordHQ