IoS-010 — PREDICTION LEDGER ENGINE

G0 SUBMISSION — Specification & Intent
Owner: FINN (Tier-1 Research)
Validator: LARS (Tier-1 Strategy)
Governance: VEGA (Tier-1 Compliance)
Version: 2026.G0
ADR Alignment: ADR-004, ADR-012, ADR-013, ADR-061
Status: Submitted for G0 Review

1. Executive Intent (Why IoS-010 Exists)

IoS-010 provides the canonical audit layer for all probabilistic forecasts generated within Vision-IoS.
Its mandate is simple and foundational:

Record every forecast with deterministic, hash-verified state context.

Record every realized outcome.

Reconcile forecasts to outcomes using deterministic matching.

Compute calibration, accuracy, and skill metrics.

Produce audit-grade evidence of strategy quality.

In short:
IoS-010 turns raw predictions into measurable truth.
It is the accountability engine required before any autonomous strategy can be authorized under ADR-012 Economic Safety.

2. Scope of G0 (What IoS-010 is, before any activation)

This G0 submission defines the pure logical contract, independent of the database or integration.

Included in scope at G0:

Pydantic models for forecasts, outcomes, pairs, and evaluations
()

Validation logic for forecast and outcome records
()

Deterministic reconciliation engine (timestamp + horizon matching)
()

Evaluation metrics: Brier, calibration, directional accuracy, MAE, skill scores
()

Calibration Curve v1.1
()

Horizon bucket derivation + utility functions
()

JSON serialization logic (pre-DB placeholder)
()

Out of scope at G0 (deferred to G1/G2):

Supabase table creation

Storage migration (file-I/O → DB-I/O)

Governance logging & lineage binding

Full integration test suite

3. Strategic Value (Why this module is required)

IoS-010 provides the measurement layer enabling:

Strategy validation (Sharpe is not enough; we need forecast skill).

Regime model assessment (IoS-003 & IoS-004 depend on it).

Risk committee approvals for autonomous operation (ADR-012).

End-to-end auditability (ADR-013 One-Source-Truth).

Without IoS-010, Vision-IoS cannot:

Prove skill over baseline

Detect model drift

Calculate calibration errors

Demonstrate economic safety

Comply with ADR-012 for autonomous trading

IoS-010 is thus a constitutional prerequisite for autonomy.

4. G0 Deliverables (What is concretely submitted)
4.1 Canonical Models

ForecastRecord

OutcomeRecord

ForecastOutcomePair

EvaluationRecord

CalibrationCurve
(all frozen, immutable models with deterministic schemas)

4.2 Deterministic Engines

Validation Engine

Reconciliation Engine

Evaluation Engine (Brier, MAE, Hit-Rate, Skill)

Calibration Engine v1.1

All logic is pure, side-effect-free, and reproducible.

4.3 Temporary Storage Layer

File-based append-only JSONL storage (ADR-061 compliance placeholder).
To be replaced entirely in G1.

5. Required DB Schema for G1 Migration

(For VEGA & STIG — not executed at G0)

Tables needed:

fhq_research.forecasts

fhq_research.outcomes

fhq_research.forecast_outcome_pairs

fhq_research.evaluations

fhq_research.calibration_curves

Each row must include:

deterministic primary keys

SHA256 input_state_hash

horizon buckets

target_type (FK → IoS-001 registry)

metadata JSONB

canonical timestamping (ADR-013)

This schema design is required for elevation to G1.

6. Governance Requirements

IoS-010 SHALL NOT advance to G1 without:

Formal Supabase schema migration scripts

ADR-013 lineage guarantees

ADR-012 economic-safety integration points

End-to-end reconciliation tests (VEGA bundle)

Zero conflict with existing IoS-* modules

G0 confirms intent, not implementation.

7. Risks Identified at G0

File-based storage violates ADR-013 if left beyond G1

Potential mismatch between target_type and IoS-001 registry

Reconciliation rules require strict temporal alignment (±6h)

Large-scale evaluations may require batching for performance

No integrity checks yet on scenario-set forecasting pipelines

These are acknowledged and deferred to G1/G2.

8. G0 Decision Request

The module satisfies all requirements for G0 Submission under ADR-004:

Clearly defined purpose

Clearly defined boundaries

Zero side effects

Fully reversible

No constitutional impact

Requested decision:
VEGA to record G0_SUBMITTED → forward IoS-010 to G1 Technical Validation.

C-Level Summary

IoS-010 is the truth layer that converts predictions into metrics, accountability, and skill measurement.
Without it, Vision-IoS cannot prove its Alpha engine works.

G0 submission confirms the architecture.
G1–G3 will make it real.
G4 will make it constitutional.