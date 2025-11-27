ADR-008 – Cryptographic Key Management & Rotation Architecture

Status: Approved
Date: 2025-11-22
Owner: LARS – Chief Strategy & Alpha Officer
Governance Tier: Tier-2 (Security, Integrity, Non-Repudiation)
Supersedes: None
Affects: Orchestrator, All Agents (LARS, STIG, LINE, FINN, VEGA), fhq_org, fhq_meta
Review Cycle: 12 months

1. Context

The FjordHQ Intelligence Operating System (FHQ-IoS) requires deterministic, tamper-evident, and non-repudiable signatures for all agent actions.
Previously, signatures were represented by placeholders without cryptographic guarantees. This prevented:

auditability of agent behaviour,

secure state reconciliation,

safe governance decisions (e.g. suspension),

verified lineage of all orchestration events,

compliance with established standards (ISO/IEC 11770-1, ISO 8000-110, BCBS 239).

Tier-2 of FHQ Governance introduces real Ed25519 keys, controlled rotation, secure archival, and cross-agent verification to prevent impersonation, tampering, or key compromise.

A cryptographic architecture is required that supports six agents, ensures secure signing, verifiable signatures, zero downtime during rotation, and multi-tier archival that meets regulatory expectations.

2. Decision

FHQ-IoS adopts the following Cryptographic Key Management Architecture:

2.1 Ed25519 as the Canonical Signature Scheme

All FHQ agents shall sign outbound events exclusively using Ed25519, chosen for:

strong security guarantees

deterministic signatures

low key sizes

fast verification for high-frequency orchestration loops

All verifying components (VEGA, worker, orchestrator API) must support Ed25519 from Tier-2 onwards.

2.2 Hierarchical KeyStore with Three Operational Modes

FHQ introduces a multi-backend KeyStore with a defined migration path:

Phase 1 – POC / Local:
.env storage with AES-derived Fernet encryption.

Phase 2 – Tier-2 / Production:
HashiCorp Vault using the transit secrets engine.

Phase 3 – Tier-3 / Institutional:
Hardware Security Module (HSM) via PKCS#11.

The KeyStore automatically routes key loading based on configured mode and emits audit logs on each access.

2.3 Rolling Key Rotation (Dual-Publishing)

All agents rotate keys every 90 days. Rotation uses a dual-publishing mechanism:

Old key: DEPRECATED but valid for a 24h grace period

New key: ACTIVE immediately

Both keys published in fhq_meta.agent_keys

Worker verifies signatures against all active or deprecated keys

After 24h: old key is ARCHIVED and removed from signature verification

This guarantees zero downtime, even during long-running tasks.

2.4 Multi-Tier Key Archival Strategy

To satisfy long-term regulatory retention requirements:

Tier 1 – Hot Storage (24h)

Vault

Used for immediate key retrieval during rollback windows.

Tier 2 – Warm Storage (90 days)

Encrypted filesystem

Used for audits, reconciliation, and post-mortems.

Tier 3 – Cold Storage (7 years)

Offline encrypted backup (e.g. air-gapped medium)

Ensures compliance with long-term evidence obligations.

All archival operations are logged in fhq_meta.key_archival_log.

2.5 Database Integration

The following tables become authoritative:

fhq_org.org_agents.public_key — active verification key

fhq_meta.agent_keys — key lifecycle states

fhq_meta.key_archival_log — audit trail for key archival

2.6 Mandatory Verification on Every Read

Every system component verifying signatures must:

load all ACTIVE and DEPRECATED keys for that agent

attempt verification in deterministic order

reject events that cannot be verified

log tampering attempts immediately

3. Rationale

This architecture was selected because it satisfies five core requirements:

1. Regulatory Compliance
Meets international standards:

ISO/IEC 11770-1 (Key Management)

ISO 8000-110 (Data Quality & Lineage)

BCBS 239 (Risk Data Aggregation)

GIPS transparency principles

2. Non-Repudiation & Forensic Grade Auditability
Every agent action is cryptographically tied to a specific key belonging to that agent at that time.

3. Zero Downtime Rotations
Dual-publishing eliminates service interruption and avoids stale signatures.

4. Tamper Resistance & Long-Term Verifiability
Three-tier archival ensures evidence retention for up to seven years.

5. Operational Flexibility
FHQ can start lightweight (env-based) and migrate upward to Vault or HSM without architectural changes.

4. Consequences
4.1 Positive

Full cryptographic integrity across all orchestrated actions

Verified lineage for every decision and agent state transition

Strong defence against impersonation or key compromise

Clear separation of operational, governance, and archival keys

Full Tier-2 readiness for autonomous multi-agent execution

4.2 Negative / Costs

Vault/HSM integration adds operational overhead

Key rotation requires worker support for multi-key verification

More complex governance documentation and audit handling

4.3 Risks

Misconfigured Vault could prevent signing during early Tier-2

Improper archival could cause loss of forensic evidence

Key leakage still possible if POC phase mismanaged or persisted too long
Mitigation is addressed through controlled rollout procedures.

5. Appendix A – Key Lifecycle States
State	Purpose	Verification	Retention
PENDING	Newly generated, unpublished	No	0h
ACTIVE	Primary signing & verification key	Yes	90 days
DEPRECATED	Grace-period key	Yes	24h
ARCHIVED	Retained for compliance	No	7 years
6. Appendix B – Required Migrations

Tables required:

fhq_meta.agent_keys

fhq_meta.key_archival_log

ADR-008 is hereby approved as the cryptographic standard for Tier-2.