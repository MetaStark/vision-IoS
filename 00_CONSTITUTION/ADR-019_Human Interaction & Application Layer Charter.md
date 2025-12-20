ADR-019 — Human Interaction & Application Layer Charter

Canonical Version: 2026.PROD.2
Date: 28 November 2025
Owner: CEO
Governance Tier: Tier-1 – CONSTITUTIONAL
Approvers: CEO → VEGA

1. Purpose

ADR-019 defines the only authorized human interface to FjordHQ:
the Vision-IoS Dashboard, a governed, cryptographically verifiable control surface.

The objective is to ensure that human interaction cannot introduce:

drift

ambiguity

unauthorized execution

inconsistent data views

systemic fragility

This ADR protects the autonomy, safety, and integrity of the Intelligence Operating System.

2. Scope

This Charter governs:

Human access pathways (UI, API, emergency CLI)

Execution restrictions and governance checks

Data rendering guarantees

Narrative context injection

Read-Replica isolation

Break-Glass emergency protocol

ADR-019 is binding for all IoS modules and overrides any implementation-level shortcut.

3. The Dashboard as the Canonical Human Interface

All Operator interactions must occur exclusively through the Vision-IoS Dashboard.

The Dashboard is not a computational layer.
It is a Dumb Glass terminal that displays canonical state from the backend without altering, transforming, or calculating data.

No human may interact with IoS modules through code execution, shell access, or direct database calls except as defined under the Break-Glass Protocol.

4. Rendering Integrity — The Canonical Rendering Contract (§6.1)

To prevent UI divergence, all Dashboard views must conform to the following rules:

4.1 Dumb Glass Principle

The frontend layer is strictly prohibited from performing:

arithmetic or rounding

inference or aggregation

transformation of backend outputs

All values must be precomputed, validated, and cryptographically signed server-side.

4.2 Hash-of-Truth Verification

Every critical metric (PnL, exposure, volatility, risk envelope, regime) must display:

the canonical backend value, and

a verification hash proving the Dashboard has not altered the value

Any mismatch triggers:

automatic UI-LOCKOUT, and

a VEGA Critical Audit Event.

5. Human Context Injection — The Oracle Pathway (§6.2)

The system must support structured Human Narrative Vectors, enabling the Operator to contribute macro-context the models do not yet detect.

Examples:

Regulatory risk shifts

Geopolitical escalation

Narrative heat / sentiment

Liquidity fragility

Counterparty rumors

Rules:

Inputs must be digitally signed by the Operator

Routed into IoS-009 (Intent & Reflexivity Engine)

Treated strictly as probabilistic modifiers, never deterministic overrides

Evaluated by LARS, weighted by FINN, certified by VEGA

This channel allows the system to learn from human foresight without compromising autonomy.

6. Read-Replica Isolation — The Observability Safety Layer (§7.5)

Human observation must never affect system performance.

All Dashboard reads must target:

an asynced read replica, or

a dedicated analytical cache

It is explicitly prohibited for the Dashboard to query:

master execution tables

regime engines

high-frequency risk envelopes

IoS-012 decision surfaces

This prevents frontend activity from degrading real-time execution, preserving millisecond-grade autonomy.

7. Execution Restrictions (Corrected)

Humans may NOT:

execute any IoS module

trigger strategy logic

modify risk envelopes

override DEFCON

call backtests

mutate trading state

Except under the Break-Glass Protocol.

All human commands must remain within the Dashboard’s interaction boundaries.

8. Break-Glass Protocol — DEFCON Emergency Access (§8.1)

If the Dashboard becomes unavailable or system autonomy threatens capital integrity, the Operator may use the emergency pathway.

Conditions for Activation:

DEFCON-1 declared per ADR-016

CEO’s physical Ed25519 private key

VEGA co-signature (dual-control)

Immutable Tier-0 Audit Record created instantly

Full hash-chain continuation

Permitted Commands Only:

SYSTEM_HALT

DEFCON_RESET

POSITIONS_FLATTEN

Execution of these commands bypasses the Dashboard but never bypasses governance or cryptographic controls.

No other CLI commands are permitted.

9. Governance & Compliance

ADR-019 inherits mandatory constraints from:

ADR-001 System Charter

ADR-003 Institutional Compliance Framework

ADR-006 VEGA Governance Engine

ADR-010 Discrepancy Scoring

ADR-012 Economic Safety Architecture

ADR-013 Canonical Governance

ADR-016 DEFCON Protocol

ADR-018 Agent State Reliability Protocol

Any violation constitutes a Class A Governance Breach and forces immediate halt.

10. Amendment Procedure

CEO drafts revision

STIG — technical compatibility review

LINE — infrastructure & latency review

FINN — forecasting & research impact

VEGA — compliance, security, and governance certification

CEO — final approval

STIG — implement in database + hash-chain

11. Final Declaration

ADR-019 enshrines:

A tamper-proof human interface

Zero-drift data rendering

A safe context channel for human insight

Execution integrity through read-replicas

A cryptographically enforced emergency brake

This is the cockpit of FjordHQ.

Signed:
CEO
VEGA (Governance Authority)