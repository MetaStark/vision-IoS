IoS-009 — Meta-Perception Layer

The Intent & Stress Brain of FjordHQ

Field	Value
Canonical Version	2026.PROD.G0
Status	SUBMISSION (G0)
Owner	LARS (Chief Strategy Officer)
Technical Authority	STIG (CTO)
Governance	VEGA (Compliance)
Dependencies	IoS-007 (Alpha Graph), ADR-063, ADR-064
Classification	Tier-1 Critical (Perception Brain)
1. Executive Summary

Strategic Mandate
FjordHQ now has:

Causal Reasoning (IoS-007 Alpha Graph)

Deterministic Decision Logic (IoS-008 Runtime Decision Engine)

What it does not yet have is a Meta-Perception Brain – a layer that asks:

Is the market calm or stressed?

Is “intent” shifting before price moves?

Are we operating in a normal regime, or in a reflexive feedback loop?

IoS-009 is that layer.

IoS-009 Meta-Perception Layer turns raw signals and causal structure into a PerceptionSnapshot:

“What does the market intend to do, and how stressed is the system?”

This layer does not trade, does not rebalance, and does not write to core market tables. It creates auditable perception artifacts that higher layers (IoS-008, IoS-010, IoS-012) can use to:

tighten risk,

override exposure,

or step aside when uncertainty is too high.

Key transformation (G0 scope):

Raw features → PerceptionSnapshot → IntentReport / ShockReport / OverrideSignals

G0 explicitly documents that the current implementation is a generic, self-contained Meta-Perception engine.
Actual wiring to FjordHQ schemas (fhq_*) and Vision-IoS modules will happen in G1+ under VEGA supervision.

2. Strategic Position in the Architecture

IoS-009 sits between the Alpha Graph and the Runtime Decision Engine.

graph LR
  subgraph "CAUSAL & STRUCTURAL LAYERS"
    G7[IoS-007: Alpha Graph<br/>Causal Structure]
  end

  subgraph "META-PERCEPTION LAYER"
    G9[IoS-009: Meta-Perception<br/>Intent & Stress Brain]
  end

  subgraph "DECISION & EXECUTION"
    G8[IoS-008: Decision Engine]
    G12[IoS-012: Execution Controller]
  end

  G7 --> G9
  G9 --> G8
  G8 --> G12


Upstream:

IoS-007 provides causal features, regimes, and structural context.

ADR-063/ADR-064 define the event and perception taxonomy (PERCEPTION.*).

IoS-009 (this module):

Computes entropy, intent, shocks, reflexivity, uncertainty.

Emits PerceptionSnapshot + diagnostic artifacts.

Downstream:

IoS-008 uses PerceptionSnapshot and OverrideSignals to shape allocation and risk.

IoS-010 uses PerceptionSnapshot as input to scenario generation.

IoS-012 can receive PERCEPTION.* events for execution filters (e.g. “no new risk under Stress Level 5”).

G0 explicitly records logical position and contracts, while implementation is currently generic and repository-local.

3. Functional Scope (G0)
3.1 What IoS-009 Does (Functionally)

The current implementation (branch claude/fjord-meta-perception-plan-01PsGioiNK8LwGd8inSNN9Sb, commit 8297f15) provides:

Core Perception Algorithms (pure functions)

entropy.py – market information entropy

noise.py – noise-to-signal evaluation

intent.py – Bayesian intent inference

reflexivity.py – decision–market feedback correlation

shocks.py – information shock detection

regime.py – regime pivot / transition detection

uncertainty.py – aggregate uncertainty score

state.py – PerceptionState construction

Orchestration

step.py – single step(inputs) → PerceptionSnapshot orchestrator

Diagnostics & Explainability

DiagnosticLogger – numeric trace logging of each stage

Feature-level contributions (which inputs drove which conclusions)

Feature Importance

FeatureImportance – global and per-module importance ranking

Uncertainty Override Engine

UncertaintyOverride – detects when uncertainty surpasses thresholds and emits OverrideSignals (e.g. kill/reduce risk).

Stress Scenario Simulator

StressScenarios – 6 predefined perception stress scenarios (flash crash, liquidity shock etc.)

Artifacts & Serialization

ArtifactManager – JSON / JSONL serialization of:

perception_snapshot.json

intent_report.json

shock_report.json

entropy_report.json

feature_importance_report.json

uncertainty_override_log.jsonl

STIG Adapter (Read-Only)

STIGAdapterAPI – minimal API for STIG to retrieve PerceptionSnapshot and artifacts.

No business logic inside the adapter.

3.2 What IoS-009 Does Not Do (by Design, G0)

Does not place trades

Does not change allocations

Does not write to fhq_* schemas

Does not maintain internal mutable state

Does not use LLMs, embeddings, or online-learning models

This is critical: IoS-009 v1.0 as implemented is a self-contained, pure analytical layer.
All coupling to Vision-IoS and FjordHQ data is postponed to later gates.

4. Implementation Reference (G0 – Actual Code vs Spec)

Directory Structure (as implemented):

meta_perception/
├── models/          # 13 frozen Pydantic v2 models
├── core/           # 8 pure perception algorithms (entropy, noise, intent, etc.)
├── orchestration/  # step() orchestration
├── diagnostics/    # DiagnosticLogger
├── importance/     # FeatureImportance
├── overrides/      # UncertaintyOverride
├── simulation/     # Stress scenarios (6)
├── artifacts/      # ArtifactManager (JSON/JSONL)
├── adapters/       # STIGAdapterAPI (read-only)
├── utils/          # math, validation, profiling
├── tests/          # unit + integration + scenario tests
├── config/         # default_config.yaml
└── README.md


Alignment with Planned Roadmap:

Roadmap Component	Implemented Element	Alignment
Information Entropy Engine	core/entropy.py	✅
Noise / Stress Engine	core/noise.py	✅
Intent Detection	core/intent.py	✅
Reflexivity Engine	core/reflexivity.py	✅
Shock Detector	core/shocks.py	✅
Regime Pivot Detector	core/regime.py	✅
Uncertainty Aggregator	core/uncertainty.py	✅
Meta-Perception State	core/state.py + models/*	✅
Meta-Brain Orchestrator	orchestration/step.py	✅
Feature Importance Engine	importance/	✅
Uncertainty Override Engine	overrides/	✅
Stress Scenario Simulator	simulation/	✅
Artifact Serialization	artifacts/	✅
STIG Integration (Read-only)	adapters/STIGAdapterAPI	✅

Critical G0 Clarification

The current IoS-009 implementation is not yet wired to:

fhq_* schemas (fhq_data, fhq_research, fhq_monitoring, etc.)

IoS-007 live graph snapshots in the database

IoS-008 or IoS-010 runtime pipelines

Instead, it operates on generic, in-memory input structures defined in its own models/ and config/.

Any usage in Vision-IoS requires:

A mapping layer from fjord data (fhq_*) to IoS-009 input models

A controlled integration into the runtime loop via STIG and VEGA-approved adapters

This is intentional and must be explicitly recorded here.

5. Data Contracts & Integration (Logical, not Physical in G0)
5.1 Logical Inputs (Conceptual Contract)

IoS-009 expects, at the logical level:

Recent market features (prices, liquidity, volatility, etc.)

Causal features and regimes from IoS-007

Event / taxonomy labels defined via ADR-063/ADR-064 (PERCEPTION.*, SHOCK.*, STRESS.*)

In G0:

These inputs are provided via local models and config, not via live database calls.

Adapters to actual tables (fhq_market.*, fhq_research.*, fhq_monitoring.*) are not implemented yet and must be introduced only at G1+.

5.2 Logical Outputs

IoS-009 standardizes the following artifacts:

PerceptionSnapshot – The full meta-perception state (entropy, intent, stress, overrides)

IntentReport – Interpretable view of perceived market intent

ShockReport – Active and historical shocks

EntropyReport – Information density / randomness

FeatureImportanceReport – Which features drove which perception

UncertaintyOverrideSignals – Flags that can be consumed by IoS-008/IoS-010/IoS-012

In G0:

All artifacts are written to local artifact directories (e.g. artifacts_output/), not to fhq_*.

6. CRITICAL GOVERNANCE CHECK (G0 Reality + Future Constraint)

This section is updated to match what the code actually does today, and what must remain true when integrated into FjordHQ.

6.1 Current Implementation (as of commit 8297f15)

Do any modules write to a database?
→ No.
All current outputs are in-memory objects and JSON/JSONL artifacts on disk. There are no calls to fhq_* schemas, nor to Vision-IoS Postgres.

Do any modules call STIG for state-mutating operations?
→ No.
STIGAdapterAPI is read-only, designed to expose perception artifacts to STIG. It does not contain business logic and does not submit write operations.

Any stateful ML (embeddings, LLMs, online learning)?
→ None.

No LLMs

No embeddings

No streaming or online learning
All logic is deterministic numerical computation.

Any temporal nondeterminism?
→ None internally.

No internal random number usage (or randomness is seeded and fixed in tests).

No internal wall-clock reads in core logic.

Any timestamps are expected to be injected from the outside, not generated internally.

This matches the actual codebase and must be preserved.

6.2 Required Constraints When Adapting to FjordHQ (Future Gates)

When IoS-009 is wired into Vision-IoS (G1+), the following must be enforced:

DB Access Pattern

IoS-009 must remain read-only with respect to fhq_* schemas.

Any write operations (if ever introduced) must go through dedicated, VEGA-approved writers outside IoS-009.

STIG Integration

STIGAdapterAPI remains read-only.

All state changes triggered by perception (e.g. risk-kill signals) must flow via:
PerceptionSnapshot → IoS-008/IoS-010 → IoS-012 / governance modules, never directly from IoS-009.

No Embedded LLM / SEAL Logic in IoS-009 Core

Any future SEAL or LLM-based enhancements must sit in separate IoS modules or adapters, not in the IoS-009 core.

IoS-009 remains a deterministic, inspectable, numeric perception engine.

Time & Randomness Discipline

All timestamps, market times, and seeds to be injected from upstream (STIG/LINE), never decided internally.

This ensures reproducible perception for audit and replay.

G0’s job is to record these constraints explicitly, given that the current implementation is a generic foundation that will later be adapted.

7. G0 Scope & Limitations

To avoid any ambiguity in future audits:

IoS-009 does exist as a working, tested, deterministic Meta-Perception Engine in the codebase.

IoS-009 does not yet exist as a fully wired Vision-IoS module bound to fhq_* schemas and IoS-007 runtime data.

G0 Declares:

The logic and architecture of IoS-009 are in place.

The current implementation is environment-neutral and not yet integrated with FjordHQ’s production database or runtime orchestration.

Any integration work (G1, G2, G3, G4) must:

Respect the governance constraints above

Map clearly from fhq_* tables and IoS-007 artifacts to IoS-009 models

Be captured in migration scripts, test plans, and VEGA-reviewed evidence bundles.

8. Submission Decision (G0)

IoS-009 Meta-Perception Layer is ready to be registered in the FjordHQ IoS registry as:

Status: G0_SUBMITTED

Type: PERCEPTION_BRAIN

Implementation Basis: meta_perception/ (commit 8297f15)

Integration Status: NOT_BOUND_TO_FHQ_DB

This submission is intentionally conservative:
It recognizes the strength of the existing code, but does not pretend that it is already fully integrated with Vision-IoS.