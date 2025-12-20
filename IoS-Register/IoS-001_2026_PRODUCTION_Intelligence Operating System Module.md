IoS-001_2026_PRODUCTION
Canonical Asset & Context Registry

Intelligence Operating System Module (IoS Series)
MBB C-Suite Charter – Application Layer Foundation

Canonical Version: 2026.PRODUCTION

Status: ACTIVE (upon VEGA signature)
Phase: APPLICATION LAYER – FOUNDATIONAL
Entity: IoS-001
Owner Role: CDMO (Chief Data & Model Officer)
Strategic Authority: LARS (CSO)
Governance Authority: VEGA
Dependencies: ADR-022, ADR-023, ADR-034
Successor Modules: IoS-002, IoS-003, IoS-004, IoS-005
Effective Date: Upon VEGA Attestation
Location: fhq_meta.ios_registry + /02_IOS/IoS-001_2026_PRODUCTION.md

1. Purpose

This contract establishes IoS-001 – Canonical Asset & Context Registry, the sovereign foundation of the FjordHQ Intelligence Operating System.

IoS-001 defines the Canonical Universe of financial instruments, exchanges, regions, calendars, liquidity classes, and modelling contexts.
It ensures that every data point, indicator, forecast, regime, or trade is tagged with the correct:

Asset Identity

Exchange Identity

Geographic Context

Sector & Model Taxonomy

Training Context

Execution Constraints

Without IoS-001, no other IoS module can function.
This module replaces ad-hoc symbols with formal ontology.
It is the Constitution of the Application Layer.

2. Mandate

IoS-001 must:

2.1 Establish Canonical Asset Identity

Define one and only one authoritative representation for each tradable instrument:

Canonical ID

Ticker

MIC (Market Identifier Code)

Region

Currency

Asset Class

Lot Size

Tick Size

Trading Hours

Market Calendar

This eliminates ambiguity and ensures deterministic asset referencing across:

FINN (Research)

LARS (Strategy)

CSEO (Blueprints)

LINE (Execution)

CFAO (Validation)

VEGA (Governance)

2.2 Establish Contextual Modelling Framework

Formalize the mapping between assets and their modelling contexts:

Regime Models

Volatility Models

Perception Models

Signal Pipelines

Sector Classification

Feature Definitions

Context Windows

This enables FINN and LARS to interpret data correctly, regardless of vendor feed or timestamp distortions.

2.3 Enforce Single Source of Truth (ADR-013)

IoS-001 is the exclusive registry where:

assets are defined

modeling contexts are assigned

exchange metadata is stored

training contexts are linked

sector taxonomies are encoded

All downstream systems must query IoS-001 rather than ingesting raw metadata from external providers.

2.4 Governance Integration

IoS-001 is subject to governance by:

CDMO (Owner & Curator)

LARS (Strategic Universe Definition)

STIG (Schema Enforcement & Runtime Guarantees)

VEGA (TRiSM & Constitutional Guardrails)

No asset or context becomes active without:

Airlock Validation (CDMO)

Schema Conformance (STIG)

Context Verification (FINN/LARS)

Canonical Attestation (VEGA)

3. Architecture & Data Model

IoS-001 spans three canonical tables.

3.1 fhq_meta.exchanges

Holds exchange-level metadata.

Fields (non-exhaustive):

exchange_id (PK)

mic_code

name

region

timezone

open_time

close_time

calendar_ref

settlement_convention

vega_signature_id

Purpose: Ensure deterministic mapping of trading hours, liquidity regime, and session boundaries.

3.2 fhq_meta.assets

Defines every asset in the Canonical Universe.

Fields:

canonical_id (PK)

ticker

exchange_id

asset_class

currency

lot_size

tick_size

sector

risk_profile

active_flag

vega_signature_id

Purpose: One asset, one identity, one truth.

3.3 fhq_meta.model_context_registry

Maps functional modeling contexts to assets.

Fields:

context_id (PK)

canonical_id (FK → assets)

feature_set (indicator families)

regime_model_ref

forecast_model_ref

perception_model_ref

embedding_profile

training_schema_hash

data_vendor_source

vega_signature_id

Purpose: Every model knows its domain.
No model can run out-of-context.

4. Responsibilities of the Owner (CDMO)

CDMO must:

4.1 Curate the Canonical Universe

Approve, reject, or modify assets based on:

liquidity threshold

governance status

sector taxonomy

risk class

modeling requirements

CDMO is the gatekeeper of asset identity.

4.2 Enforce Context Economy

Apply measurable rules:

Similarity Score threshold: ≥ 0.75

Tier-specific context budget:

T1 (LARS): 128k tokens

T2 (FINN): 32k tokens

T3 (LINE): 4k tokens

Priority Weights:

Regime Alignment: 40%

Causal Centrality: 30%

Alpha Impact: 30%

Context is capital. CDMO allocates it.

4.3 Operate the Airlock Protocol

No data enters canonical tables unless:

Schema_Valid = TRUE

Null_Check < 1%

Time_Continuity = TRUE

Anomaly_Detection < 3σ

Cost_Check = TRUE

Source_Signature = VALID

Contaminated data dies in quarantine.

4.4 Maintain the Model Vault Lineage

Every model must have:

Training_Data_Hash

Code_Hash

Config_Hash

Performance_Metrics

TRiSM_Attestation_ID

Invalid lineage → automatic REVOKE.

5. Constraints

IoS-001 cannot:

Execute trades

Generate signals

Make forecasts

Define strategies

Alter ADRs

Modify agent behavior

Override VEGA

Write to non-canonical schemas

IoS-001 is definition, not inference.

6. Activation Conditions

IoS-001 becomes ACTIVE when:

CDMO provides the formal specification

STIG enforces schema migrations

FINN validates context mappings

LARS approves the Canonical Universe

VEGA attests and signs content_hash

Hash-chain is committed

Only then do downstream IoS modules unlock:

IoS-002 Feature Vectors

IoS-003 Regime Engine

IoS-004 Backtest Engine

IoS-005 Skill Metrics

7. Cryptographic Identity

All IoS-001 artifacts must include:

SHA-256 content_hash

VEGA attestation (Ed25519)

hash_chain_id

governance_action_id

lineage metadata snapshot

Unsigned = invalid.
Unattested = blocked.

8. Signatures

Owner – CDMO
Ed25519 — Registered

Strategic Authority – LARS (CSO)
Ed25519 — Registered

Governance Authority – VEGA
Ed25519 — Attested & Required

CEO
Final Constitutional Approval