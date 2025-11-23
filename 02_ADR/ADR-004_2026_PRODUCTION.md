ADR-004 – Change Gates Architecture

Status: Draft for CEO Approval
Owner: LARS (CSO)
Authority Chain: ADR-001 → ADR-002 → ADR-003 → ADR-004
Classification: Governance–Critical (Class A domain)
Scope: All modifications to canonical artifacts, code, models, datasets, ADRs, and production configurations across the FjordHQ Market System.

1. Executive Summary

ADR-004 defines the Change Gate System – FjordHQ’s formal, constitutional mechanism for controlling, validating, approving and monitoring all changes to the Market System.

This ADR ensures:

absolute consistency with ADR-001 (constitutional constraints)

perfect alignment with ADR-002 (audit, hashing, VEGA)

institutional operational governance (ADR-003)

controlled evolution of all canonical artifacts

prevention of drift, silent failure, or unauthorized modification

Change Gates are the “nervous system” of FjordHQ governance.
Without ADR-004, ADR-002 cannot maintain constitutional integrity, ADR-003 cannot enforce institutional discipline, and VEGA cannot be safely activated.

2. Problem Statement

The Market System is evolving fast. Without a strict Change Gate architecture:

Models can be altered without lineage

ADRs can diverge from their canonical form

Performance logic may drift

Staging leakage may occur

VEGA cannot certify integrity

Audit logs lose evidentiary value

Regulator-level controls (GIPS, ISO 42001, DORA) break down

We need a unified, mandatory, audited pathway for every modification.

3. Decision

FjordHQ adopts a five-gate Change Control Architecture, binding across all agents (LARS, STIG, LINE, FINN, CODE, GOV).

The five gates are:

G0 – Submission

G1 – Technical Validation

G2 – Governance Validation

G3 – Audit Verification (ADR-002 Conformity)

G4 – CEO Approval & Canonicalization

Each gate has:

purpose

allowed actors

allowed inputs

required outputs

compliance evidence required

mandatory logging into existing registries

No new registries are introduced.

4. Gate Definitions
G0 – Submission Gate

Purpose:
Initial submission of proposed change.

Allowed actors:

LARS (design)

STIG (technical)

FINN (research)

CODE (engineering)

Allowed inputs:

ADR drafts

model artifacts

data transformations

pipeline adjustments

performance logic

new compliance rules

Mandatory log:
fhq_meta.adr_audit_log
event_type = 'SUBMISSION'

Output:
Change proposal ID (internal reference).

G1 – Technical Validation (STIG)

Purpose:
Ensure the change is technically valid and safe.

Checks:

schema validity

no staging leakage

deterministic build

reproducible outputs

test suite passing

hash mismatch check

dependency mapping

Mandatory log:
fhq_meta.adr_audit_log
event_type = 'G1_TECHNICAL_VALIDATION'

Allowed outcomes:

PASS → escalates

FAIL → returned to G0

G2 – Governance Validation (LARS + GOV)

Purpose:
Ensure the change respects ADRs 001–003.

Checks:

constitutional authority (ADR-001)

auditability (ADR-002)

institutional standards (ADR-003)

alignment with GIPS, ISO 42001, DORA

SMCR/MAIFA accountability

conflict-of-interest checks

Mandatory log:
fhq_meta.adr_audit_log
event_type = 'G2_GOVERNANCE_VALIDATION'

Allowed outcomes:

PASS

FAIL

REQUIRE_MODIFICATION

G3 – Audit Verification (VEGA or STIG pre-activation)

Purpose:
Enforce ADR-002: hashing, reconciliation, error classification.

Checks:

SHA-256 integrity

cross-table consistency

no critical Class A failures

evidence completeness

version lineage integrity

canonical divergence checks

Mandatory log:
fhq_meta.adr_audit_log
event_type = 'G3_AUDIT_VERIFICATION'

Allowed outcomes:

VERIFY

BLOCK (Class A)

WARN (Class B/C)

G4 – CEO Approval & Canonicalization

Purpose:
Final activation of change into canonical path.

Allows:

new ADR finalization

new model canonicalization

dataset canonicalization

modification of system Charter artifacts

new governance structures

Mandatory log:
fhq_meta.adr_audit_log
event_type = 'G4_CANONICALIZATION'

Required:

CEO digital approval

final SHA-256 hash

version increment in fhq_meta.adr_version_history

update to fhq_meta.adr_registry

This is the only gate where canonical data may be overwritten.

5. Evidence Requirements (ADR-002 Integration)

ADR-004 inherits ADR-002’s evidentiary structure.
For every gate:

timestamp

actor

event_type

sha256_hash

evidence_path

error_class

resolution_notes

No change may proceed without evidence.

6. Decision Tree (MECE)
                START
                  |
                 G0
                  |
           Is submission valid?
                /    \
             YES      NO → reject
                |
                G1
                |
           Technical valid?
                /    \
             YES      NO → return to G0
                |
                G2
                |
   Governance & compliance valid?
            /         \
         YES          NO/GAP → return to G0
                |
                G3
                |
      Audit integrity verified?
            /           \
         YES            CLASS A → BLOCK
                |
                G4 (CEO)
                |
         CANONICALIZED → ADR-002 Rhythms

7. Responsibilities

LARS – Gate G2 governance interpretation
STIG – Gate G1 technical enforcement
LINE – Operational stability checks during G1/G3
FINN – Research integrity validation (optional G1/G2)
CODE – Implements required modifications
GOV – Compliance assurance at G2
CEO – G4 approval authority
VEGA – Automated G3 gate (post-activation)

8. Implications
Positive

eliminates silent drift

ensures perfect reproducibility

enables VEGA activation

creates institutional-level change control

prevents unauthorized manipulation

enforces a constitutional spine through all future scaling

Negative

slows rapid iteration (by design)

requires strict discipline

increases evidence and audit burden

Mitigation

RegTech automation

LARS governance templates

STIG batch-validation pipelines

Clear accountability map

9. Final Decision

ADR-004 is hereby adopted as FjordHQ’s official Change Gate Architecture, mandatory for all system modifications and required for VEGA activation.

It binds:

LARS

STIG

LINE

FINN

CODE

GOV

CEO

VEGA (post-activation)

No artifact may enter canonical status except through G0 → G4.