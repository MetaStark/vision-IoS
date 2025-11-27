ADR-013 – Canonical Governance & One-Source-of-Truth Architecture

Status: CEO Approved
Author: LARS (CSO – Logic, Analytics & Research Strategy)
Authority Chain: ADR-001 → ADR-002 → ADR-003 → ADR-004 → ADR-006 → ADR-007 → ADR-008 → ADR-009 → ADR-010 → ADR-011 → ADR-012
Tier: Constitutional Governance (Tier-1.5)
Scope: All agents, all data domains, Orchestrator, VEGA, fhq_meta, Kernel
Purpose: Establish a permanent, system-wide One-Source-of-Truth architecture for governance, data, lineage, ingestion, and all future expansions of FjordHQ.

1. Executive Summary

ADR-013 defines the canonical truth architecture for FjordHQ.

It establishes that:

there shall always exist one, and only one, authoritative source of truth

for every domain, asset, frequency, calculation method, and governance artifact

across the entire lifetime of the system

It extends the One-True-Source principle beyond ADR governance into all operational domains, including:

prices

indicators

fundamentals

sentiment

macroeconomic series

on-chain data

embeddings

research artifacts

knowledge graph metrics

future data families introduced through IoS modules

From this ADR forward, no parallel “truths” may exist inside FjordHQ, regardless of:

ingestion vendor

frequency

resolution

backfills

schema refinements

historical revisions

pipeline upgrades

Application Layer evolution

All data used for decisions, research, reporting, or strategy must come from the canonical domain store defined and governed under ADR-013.

This ADR is foundational for institutional reproducibility, non-repudiation, and consistent intelligence generation.

2. Problem Statement

Without a unifying truth architecture, complex systems exhibit:

multiple valid-looking price series for the same asset

conflicting indicator values depending on pipeline

parallel histories caused by backfills

inconsistencies between dashboard, backtests, and agent reasoning

version drift in data pipelines

missing lineage and unverifiable data provenance

inability to prove in audit which series was used for a decision

“silent forks” in the data graph

These patterns violate:

BCBS-239 – Single Source of Truth

ISO 8000-110 – Data lineage

ISO 42001 – AI traceability

GIPS 2020 – Performance rule integrity

ADR-013 resolves this permanently.

3. Decision Overview
3.1 The One-Source-of-Truth Principle

FjordHQ adopts a strict invariant:

For every domain, asset, frequency, timestamp, or artifact that influences research, strategy, risk, or reporting, there shall exist exactly one canonical source of truth.

This applies universally across:

ADR governance

price data

indicator outputs

time-series transformations

embeddings

feature engineering

risk metrics

knowledge graph structures

macro and sentiment streams

any future IoS modules

No alternative or parallel truth representations may exist in production reasoning.

3.2 Canonical Domain Stores

For every domain introduced into the system, FjordHQ must define:

one canonical table or view

one canonical lineage chain

one canonical semantics contract

one canonical timestamping standard

All other tables (vendor feeds, raw dumps, staging layers, experimental outputs) are non-canonical and may not be used by:

agents

research pipelines

strategies

dashboards

reporting

any IoS-modules

unless first transformed and reconciled into the canonical domain.

Examples (binding principles, not schemas):

Price Data
For each asset × frequency × price_type, there must be exactly one canonical price series.
Backfills or vendor replacements must extend or update this series, not create competing alternatives.

Indicator Values
For each indicator × asset × timestamp, only one canonical computation is permitted per calculation method.
All experimentation must occur in non-canonical domains.

Fundamentals, macro, sentiment, on-chain, and all future IoS families must follow the same pattern: one canonical truth per semantic domain.

3.3 Ingestion Without Multi-Truth Drift

Multi-vendor ingestion is permitted, but multi-truth output is prohibited.

All external sources must pass through:

Orchestrator

VEGA economic safety

lineage stamping (ADR-002 / ADR-010)

reconciliation logic

canonicalization pipeline

Only the reconciled, canonicalized result is allowed into production truth.

Examples:

BTC-USD daily from Binance + Yahoo + Coinbase becomes one canonical BTC-USD daily series

BTC-USD hourly from any vendor becomes one canonical hourly series

Equity backfills (5 years) must merge into the canonical listing, not create a new divergent table

3.4 Reconciliation and Canonicalization (ADR-010)

Every ingestion event must be reconciled:

vendor → staging → reconciliation → canonical

discrepancies scored under ADR-010

VEGA escalates conflicts above threshold

CEO or LARS must approve structural changes through governance gates (ADR-004)

Canonical data cannot be overwritten or replaced without:

G1 technical validation

G2 governance validation

G3 audit verification

G4 CEO canonicalization

No bypass is permitted.

3.5 Kernel-Level Enforcement

ADR-013 mandates that canonical domain enforcement is part of the Kernel:

Kernel must include:

domain registry

lineage tracker

canonicalization logic

discrepancy scoring

VEGA attestation logic

governance gate integration

immutable truth snapshotting

Kernel snapshots must be:

reproducible

deterministic

independent of staging pipeline drift

Application Layer (IoS) must bind to these canonical domains, not to raw data.

4. Scope

ADR-013 governs:

ADR lineage

data lineage

canonical domain architecture

ingestion pipelines

reconciliation logic

agent access patterns

truth selection

truth mutation policy

Kernel integration

Application Layer consumption

This ADR applies to every current and future data family brought into FjordHQ.

5. Mandatory Governance Rules
5.1 Domain Requirements

Every domain must define exactly one canonical truth store.

All non-canonical stores must be marked as raw, vendor, or staging.

No strategy, research, dashboard, or agent may read from non-canonical sources.

Any attempt to introduce a second canonical store for the same domain is a Class A governance violation.

5.2 Asset-Level Requirements

For each asset × frequency × price_type, exactly one canonical series is permitted.

Backfills must update the existing canonical series, not create alternatives.

Intraday resolutions (e.g., 1s, 1m, 1h) must each have a single canonical series.

5.3 Indicator-Level Requirements

Only one canonical value per indicator × asset × timestamp.

Experimentation must not leak into canonical domains.

Derived domains (signals, embeddings, features) must declare a canonical store.

5.4 Governance Requirements

VEGA mediates all read/write access to canonical layers.

Canonical data cannot be overwritten without ADR-004 gates.

All ingestion must be reconciled under ADR-010 discrepancy scoring.

Agents cannot bypass VEGA or Orchestrator.

6. Institutional Rationale

This architecture satisfies:

BCBS-239: single source of truth, lineage, reconciliation

ISO 8000-110: deterministic metadata, data ontology

ISO 42001: AI traceability, accountability, safety

GIPS 2020: integrity of investment rules

It ensures:

reproducibility

non-repudiation

cross-system consistency

auditability

long-term operational stability

extensibility for the Application Layer (IoS-001+)

7. Consequences
Positive

Guaranteed single truth across all domains

Zero multi-truth drift

Transparent lineage

Governance-safe ingestion

Clean Application Layer extending canonical domains

Reproducible Kernel across environments

Deterministic long-term system behavior

Negative

Slower ingestion due to stricter governance

Higher upfront discipline required

Mandatory VEGA mediation for domain mutations

Risks

Vendor feed divergence → mitigated by canonicalization

Improper pipeline configuration → caught by ADR-010

Unsupervised experimental data → blocked by domain rules

8. Next Steps

VEGA validates ADR-013 against ADR-001→ADR-012.

CEO executes G4 canonicalization.

STIG registers ADR-013 in fhq_meta.adr_registry.

VEGA certifies fully integrated canonical governance.

LARS drafts ADR-014 (Kernel Golden Master).

9. Meta-Directive for All Future ADRs

Any new governance, architecture, or data domain must:

extend this canonical lineage,

define a single domain truth store,

register under ADR-013 governance,

reject all competing data representations.

Any deviation is a Class A governance event.

10. Signatures

Prepared by:
LARS – Chief Strategy & Alpha Officer

Reviewed by:
STIG – CTO (Technical Validation)
VEGA – Governance Authority (Compliance, Lineage, Economic Safety)

Approved by:
CEO – Final Canonical Authority

To be certified by:
VEGA – Attestation of Canonical Truth Enforcement