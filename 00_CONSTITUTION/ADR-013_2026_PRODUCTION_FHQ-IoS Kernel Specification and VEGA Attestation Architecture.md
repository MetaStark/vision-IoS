ADR-013 – FHQ-IoS Kernel Specification & VEGA Attestation Architecture

Status: FHQ-IoS Standalone Product
Date: 2026-11-22
Author: Ørjan Skjold (CEO)

1. Purpose

This decision defines the formal Kernel Specification for the FjordHQ Intelligent Operating System (FHQ-IoS).
It establishes:

The canonical structure and integrity boundaries of the Kernel

The rules governing which components belong to the Kernel and which do not

The VEGA-based attestation process required before any Kernel snapshot can be declared valid

The format, lifecycle, and governance of Kernel versions (v1.0, v1.1, etc.)

This ADR ensures the Kernel remains immutable, attestable, and re-deployable across machines, contexts, and future product domains.

2. Context

Following the completion of ADR-011 (Fortress & VEGA Testsuite) and ADR-012 (Economic Safety Architecture), the system reached a stable and self-auditing foundation.

However, no canonical definition yet exists for:

What constitutes the Kernel

Required integrity guarantees

The deterministic folder + file layout

A cryptographically verifiable snapshot specification

The VEGA attestation protocol for certifying Kernel authenticity

The lifecycle rules for versioning and reproduction

The exclusions (e.g., venv, caches, binaries) that must never be part of the Kernel

Without a formal IEEE-style specification, future products built on FHQ-IoS risk drift, contamination, and non-deterministic deployments.

ADR-013 addresses this gap.

3. Decision

FHQ-IoS will adopt a Kernel-level specification, inspired by IEEE-style operating-system standards, covering:

3.1 Kernel Definition

The Kernel consists exclusively of:

Governance Logic

ADR-000 → ADR-012

Role architecture (LARS, STIG, VEGA)

Approval workflows

State reconciliation

Economic safety layer

Key management primitives

Audit chain & cryptographic signature paths

Execution Orchestrator (Tier-1 to Tier-4)

WorkerEngine

ProviderRouter

LLM Clients

Attestation & signature logic

ModeGuard and fallback rules

Governance-Test Infrastructure

Tier-1: Sanity

Tier-2: Governance

Tier-3: Safety

Tier-4: Autonomy

Fortress & VEGA testsuite

Schemas Required by Governance

fhq_core

fhq_orchestrator

fhq_monitoring

Cryptographic and audit tables

Canonical Documentation

ADRs

Kernel Manifest

Reconciliation Specification

Economic Safety SRS

Nothing else is allowed inside the Kernel.

3.2 Kernel Exclusions

The following MUST NOT be included:

venv/

Any Python binaries

Any compiled .pyd or .exe artifacts

Pip caches

Node modules

Supabase dumps

Market data

FINN models

Dashboard assets

Experimental code

Test outputs

Temporary .env.keys

Raw API keys

These are cleaned by automated code-team tooling (see §4.3).

3.3 Kernel Snapshot Requirements

Every Kernel snapshot must:

Be fully deterministic

Be reproducible on any machine

Contain zero binaries

Contain zero secret keys

Include a machine-readable Kernel Manifest (FHQ-IoS-MANIFEST.json)

Be hashed using SHA-256 at the folder level

Produce a VEGA-signed Kernel Integrity Certificate

3.4 VEGA Attestation

VEGA provides the cryptographic attestation pipeline consisting of:

(a) Pre-Snapshot Checks

Verify all ADRs have PRODUCTION status

Verify governance pipeline tests pass

Verify Tier-4 autonomy tests pass

Verify economic safety thresholds stable

Verify no untracked files (Git clean state)

Verify schema hash matches canonical baseline

(b) Snapshot Validation

Compute directory tree hash

Compute per-file Merkle chain

Validate against allowed manifest patterns

Confirm absence of excluded paths

Confirm deterministic layout

Sign final Kernel Hash using VEGA private key

(c) Certificate Generation
Produced in FHQ-IoS_KERNEL_vX/VEGA-CERTIFICATE.json:

Kernel version

Directory hash

Merkle root

VEGA signature

Timestamp

Host metadata

Approval chain

3.5 Kernel Versioning Rules

v1.0 – Post-ADR-012, pre-Market System

Patch (v1.0.1) – Bug fixes inside Kernel

Minor (v1.1) – Additional governance layers

Major (v2.0) – New primitives (e.g., agent-level reasoning modules)

Market System is explicitly NOT part of the Kernel.

4. Implementation
4.1 Code Team Delivery Requirements

Code team will create:

A. Kernel Build Tool

python tools/build_kernel_snapshot.py --version v1.0


Capabilities:

Clean all excluded folders

Generate manifest

Generate tree hash

Generate Merkle chain

Package Kernel

Invoke VEGA attestation API

Emit certificate

B. Kernel Manifest Generator

Ensures snapshot contains only allowed file types

Ensures deterministic ordering

Ensures integrity

C. VEGA Attestation Microservice

Detached signing service

No external dependencies

Deterministic JSON output

4.2 Folder Structure
FHQ-IoS_KERNEL_v1/
│
├── ADR/
├── orchestrator/
├── schemas/
├── tests/
├── MANIFEST.json
├── KERNEL_HASH.txt
└── VEGA-CERTIFICATE.json

5. Rationale

This decision ensures:

Governance cannot drift

Kernel copies cannot be tampered with

IP is fully portable

System can be redeployed even if entire environment is lost

Each subsystem (Market System, FINN, Dashboard) becomes a detachable "app"

VEGA acts as an autonomous, cryptographic auditor

Investors, regulators, and external parties can verify integrity without trusting you or the machine

Kernel-level attestation is the foundation that transforms FjordHQ from “a system” into “an operating system for autonomous AI governance”.

6. Consequences
Positive

Full reproducibility

Full integrity

Independent verification

Legal defensibility

Extreme modularity

Eliminates future architectural debt

Negative

Requires discipline (no rogue code inside Kernel)

Requires strict separation of all application layers

Snapshot lifecycle adds process overhead

These costs are considered acceptable and essential.

7. Alternatives Considered

Git-based tagging – insufficient (does not guarantee deterministic structure)

Docker image freeze – non-portable, binary contamination

VM snapshots – too large, not cryptographically verifiable

Manual curation – prone to drift

Decision: APPROVED

ADR-013 becomes active immediately.
Code team is finished implementing the Kernel Snapshot Toolchain.